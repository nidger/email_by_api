from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, MailSettings, SubscriptionTracking, TrackingSettings, ClickTracking, OpenTracking
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

def extract_domain(email):
    """Extract and validate domain from email address"""
    try:
        domain = email.split('@')[1].lower()
        if re.match(r'^[a-z0-9][a-z0-9-.]+\.[a-z]{2,}$', domain):
            return domain
        return None
    except (IndexError, AttributeError):
        return None

def validate_domain(db, email):
    """
    Validate email domain against rules:
    - Not a known provider domain
    - Domain exists in existing_customers
    Returns (is_valid, reason)
    """
    domain = extract_domain(email)
    if not domain:
        return False, "Invalid domain format"

    # Check if domain is a known provider
    provider_exists = db.email_providers.find_one({'domain': domain})
    if provider_exists:
        return False, "Provider domain not allowed"

    # Verify domain exists in existing_customers
    customer_exists = db.existing_customers.find_one({'domain': domain})
    if not customer_exists:
        return False, "Domain not in existing customers"

    return True, None

def check_domain_frequency(db, domain):
    """
    Check if domain has received an email within frequency limit
    Returns (can_send, reason)
    """
    # Get most recent email to this domain
    last_email = db.email_history.find_one(
        {'domain': domain},
        sort=[('sent_date', -1)]
    )

    if last_email:
        days_since_last = (datetime.now(UTC) - last_email['sent_date']).days
        if days_since_last < 14:  # Using same frequency rule as individual emails
            return False, f"Domain emailed {days_since_last} days ago"

    return True, None

def get_campaign_recipients(db, campaign_name):
    """Get recipients for specified campaign"""
    campaign = db.campaigns.find_one({'name': campaign_name})
    if not campaign:
        raise ValueError(f"Campaign '{campaign_name}' not found")
    if campaign['status'] not in ['ready', 'sending']:
        raise ValueError(f"Campaign '{campaign_name}' has invalid status: {campaign['status']}")
    return campaign.get('recipients', [])

def record_email_history(db, email, domain, campaign_name, status, error=None):
    """Record email send attempt in history"""
    history_record = {
        'contact_email': email,
        'domain': domain,
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

def send_campaign_emails(campaign_name):
    """Send campaign emails with domain validation and tracking"""
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
    
    # Set up tracking settings
    tracking_settings = TrackingSettings()
    tracking_settings.click_tracking = ClickTracking(enable=True)
    tracking_settings.open_tracking = OpenTracking(enable=True)
    
    # Set up subscription tracking
    subscription_tracking = SubscriptionTracking()
    subscription_tracking.enable = True
    tracking_settings.subscription_tracking = subscription_tracking
    
    # Email content
    html_content = '''
    <p>This is a test email to verify our SendGrid integration is working correctly.</p>
    <p>Check out our partner website: <a href="{partner_url}">{partner_url}</a></p>
    '''.format(partner_url=os.getenv('PARTNER_WEBSITE_URL'))
    
    plain_text_content = '''
    This is a test email to verify our SendGrid integration is working correctly.
    Check out our partner website: {partner_url}
    '''.format(partner_url=os.getenv('PARTNER_WEBSITE_URL'))
    
    # Track send statistics
    stats = {
        'total': len(recipients),
        'sent': 0,
        'failed': 0,
        'skipped_provider_domain': 0,
        'skipped_invalid_domain': 0,
        'skipped_frequency': 0,
        'skipped_not_customer': 0
    }
    
    # Send emails to each recipient
    for email in recipients:
        domain = extract_domain(email)
        if not domain:
            logging.error(f"Invalid email format: {email}")
            stats['skipped_invalid_domain'] += 1
            record_email_history(db, email, None, campaign_name, 'failed', 'Invalid email format')
            continue

        # Validate domain
        is_valid, reason = validate_domain(db, email)
        if not is_valid:
            logging.warning(f"Domain validation failed for {email}: {reason}")
            if 'provider' in reason.lower():
                stats['skipped_provider_domain'] += 1
            elif 'customer' in reason.lower():
                stats['skipped_not_customer'] += 1
            record_email_history(db, email, domain, campaign_name, 'skipped', reason)
            continue

        # Check domain frequency
        can_send, freq_reason = check_domain_frequency(db, domain)
        if not can_send:
            logging.warning(f"Frequency check failed for {email}: {freq_reason}")
            stats['skipped_frequency'] += 1
            record_email_history(db, email, domain, campaign_name, 'skipped', freq_reason)
            continue

        try:
            message = Mail(
                from_email=os.getenv('DEFAULT_FROM_EMAIL'),
                to_emails=email,
                subject=f'Test Email from Cast Iron Wholesale',
                html_content=html_content,
                plain_text_content=plain_text_content
            )
            
            message.tracking_settings = tracking_settings
            
            # Send the email
            response = sg.send(message)
            
            if response.status_code == 202:
                logging.info(f'Email sent successfully to {email}')
                stats['sent'] += 1
                
                # Update contact's last_email_sent date
                update_contact_send_date(db, email)
                record_email_history(db, email, domain, campaign_name, 'sent')
            else:
                logging.error(f'Unexpected status code {response.status_code} for {email}')
                stats['failed'] += 1
                record_email_history(db, email, domain, campaign_name, 'failed', 
                                  f'Status code: {response.status_code}')
                
        except Exception as e:
            logging.error(f'Error sending email to {email}: {e}')
            stats['failed'] += 1
            record_email_history(db, email, domain, campaign_name, 'failed', str(e))
    
    # Update campaign status based on results
    final_status = 'completed' if stats['failed'] == 0 else 'completed_with_errors'
    update_campaign_status(db, campaign_name, final_status, stats)
    
    # Log final statistics
    logging.info(f"\nCampaign '{campaign_name}' completed:")
    logging.info(f"Total recipients: {stats['total']}")
    logging.info(f"Successfully sent: {stats['sent']}")
    logging.info(f"Failed: {stats['failed']}")
    logging.info(f"Skipped (provider domain): {stats['skipped_provider_domain']}")
    logging.info(f"Skipped (invalid domain): {stats['skipped_invalid_domain']}")
    logging.info(f"Skipped (frequency): {stats['skipped_frequency']}")
    logging.info(f"Skipped (not customer): {stats['skipped_not_customer']}")

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