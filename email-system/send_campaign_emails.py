from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pymongo import MongoClient
from datetime import datetime, UTC, timedelta
import os
from dotenv import load_dotenv
import argparse
import logging
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def connect_to_db():
    """Connect to MongoDB database"""
    load_dotenv()
    client = MongoClient(os.getenv('MONGODB_URI'))
    return client.email_system

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def get_campaign_recipients(db, campaign_name):
    """Get recipients for specified campaign"""
    campaign = db.campaigns.find_one({'name': campaign_name})
    if not campaign:
        raise ValueError(f"Campaign '{campaign_name}' not found")
    if campaign['status'] not in ['ready', 'sending']:
        raise ValueError(f"Campaign '{campaign_name}' has invalid status: {campaign['status']}")
    return campaign.get('recipients', [])

def extract_domain(email):
    """Extract domain from email address"""
    try:
        return email.split('@')[1].lower()
    except (IndexError, AttributeError):
        return None

def check_existing_customer(db, email):
    """Check if email or its domain exists in existing customers"""
    domain = extract_domain(email)
    if not domain:
        return False
        
    return bool(db.existing_customers.find_one({
        '$or': [
            {'email': email},
            {'domain': domain}
        ]
    }))

def record_email_history(db, email, campaign_name, status, error=None):
    """Record email send attempt in history"""
    history_record = {
        'contact_email': email,
        'campaign_id': campaign_name,
        'sent_date': datetime.now(UTC),
        'status': status
    }
    if error:
        history_record['error'] = error

    db.email_history.insert_one(history_record)

def update_contact_send_date(db, email):
    """Update the last_email_sent date for a contact"""
    db.contacts.update_one(
        {'email': email},
        {'$set': {'last_email_sent': datetime.now(UTC)}}
    )

def update_campaign_status(db, campaign_name, status, stats=None):
    """Update campaign status and completion date if completed"""
    update_data = {'status': status}
    if status in ['completed', 'completed_with_errors']:
        update_data['completed_date'] = datetime.now(UTC)
    if stats:
        update_data['statistics'] = stats

    db.campaigns.update_one(
        {'name': campaign_name},
        {'$set': update_data}
    )

def ensure_utc_datetime(dt):
    """Ensure datetime is UTC aware"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt

def send_campaign_emails(campaign_name):
    """Send campaign emails with individual frequency control"""
    # Connect to database
    db = connect_to_db()
    
    # Get SendGrid API key
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
    
    # Get campaign recipients
    recipients = get_campaign_recipients(db, campaign_name)
    if not recipients:
        logging.warning(f"No recipients found for campaign '{campaign_name}'")
        return
    
    # Update campaign status to 'sending'
    update_campaign_status(db, campaign_name, 'sending')
    
    # HTML content (NO MANUAL UNSUBSCRIBE LINKS)
    html_content = '''
    <p>This is a test email to verify our SendGrid integration is working correctly.</p>
    <p>Check out our partner website: <a href="{partner_url}">{partner_url}</a></p>
    '''.format(partner_url=os.getenv('PARTNER_WEBSITE_URL'))

    # Plain text content (NO MANUAL UNSUBSCRIBE LINKS)
    plain_text_content = '''
    This is a test email to verify our SendGrid integration is working correctly.
    Check out our partner website: {partner_url}
    '''.format(partner_url=os.getenv('PARTNER_WEBSITE_URL'))
    
    # Track send statistics
    stats = {
        'total': len(recipients),
        'sent': 0,
        'failed': 0,
        'skipped_invalid_email': 0,
        'skipped_frequency': 0,
        'skipped_existing_customer': 0
    }
    
    # Calculate cutoff date for frequency check (14 days ago)
    frequency_cutoff = datetime.now(UTC) - timedelta(days=14)
    
    # Send emails to each recipient
    for email in recipients:
        # Validate email format
        if not is_valid_email(email):
            logging.error(f"Invalid email format: {email}")
            stats['skipped_invalid_email'] += 1
            record_email_history(db, email, campaign_name, 'failed', 'Invalid email format')
            continue

        # Check if this is an existing customer
        if check_existing_customer(db, email):
            logging.info(f"Skipping existing customer: {email}")
            stats['skipped_existing_customer'] += 1
            record_email_history(db, email, campaign_name, 'skipped', 'Existing customer')
            continue

        # Check if this specific email has been sent within frequency period
        contact = db.contacts.find_one({'email': email})
        if contact and contact.get('last_email_sent'):
            last_sent = ensure_utc_datetime(contact['last_email_sent'])
            if last_sent > frequency_cutoff:
                logging.info(f"Skipping {email} - emailed too recently (last sent: {last_sent})")
                stats['skipped_frequency'] += 1
                record_email_history(db, email, campaign_name, 'skipped', 'Frequency limit')
                continue

        try:
            message = Mail(
                from_email=os.getenv('DEFAULT_FROM_EMAIL'),
                to_emails=email,
                subject=f'Test Email from Cast Iron Wholesale',
                html_content=html_content,
                plain_text_content=plain_text_content
            )
            
            # Send the email (NO TRACKING SETTINGS CONFIGURATION)
            response = sg.send(message)
            
            if response.status_code == 202:
                logging.info(f'Email sent successfully to {email}')
                stats['sent'] += 1
                
                # Update contact's last_email_sent date
                update_contact_send_date(db, email)
                record_email_history(db, email, campaign_name, 'sent')
            else:
                logging.error(f'Unexpected status code {response.status_code} for {email}')
                stats['failed'] += 1
                record_email_history(db, email, campaign_name, 'failed', 
                                  f'Status code: {response.status_code}')
                
        except Exception as e:
            logging.error(f'Error sending email to {email}: {e}')
            stats['failed'] += 1
            record_email_history(db, email, campaign_name, 'failed', str(e))
    
    # Update campaign status based on results
    final_status = 'completed' if stats['failed'] == 0 else 'completed_with_errors'
    update_campaign_status(db, campaign_name, final_status, stats)
    
    # Log final statistics
    logging.info(f"\nCampaign '{campaign_name}' completed:")
    logging.info(f"Total recipients: {stats['total']}")
    logging.info(f"Successfully sent: {stats['sent']}")
    logging.info(f"Failed: {stats['failed']}")
    logging.info(f"Skipped (invalid email): {stats['skipped_invalid_email']}")
    logging.info(f"Skipped (frequency): {stats['skipped_frequency']}")
    logging.info(f"Skipped (existing customer): {stats['skipped_existing_customer']}")

def main():
    parser = argparse.ArgumentParser(description='Send emails for a specific campaign')
    parser.add_argument('--campaign', required=True,
                       help='Name of the campaign to send')
    
    args = parser.parse_args()
    
    try:
        send_campaign_emails(args.campaign)
    except Exception as e:
        logging.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()