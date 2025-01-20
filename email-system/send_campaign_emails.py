from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, MailSettings, SubscriptionTracking, TrackingSettings, ClickTracking, OpenTracking
from pymongo import MongoClient
from datetime import datetime, UTC
import os
from dotenv import load_dotenv
import argparse

def connect_to_db():
    """Connect to MongoDB database"""
    load_dotenv()
    client = MongoClient(os.getenv('MONGODB_URI'))
    return client.email_system

def get_campaign_recipients(db, campaign_name):
    """Get recipients for specified campaign"""
    campaign = db.campaigns.find_one({'name': campaign_name})
    if not campaign:
        raise ValueError(f"Campaign '{campaign_name}' not found")
    return campaign.get('recipients', [])

def update_contact_send_date(db, email):
    """Update the last_email_sent date for a contact"""
    db.contacts.update_one(
        {'email': email},
        {'$set': {'last_email_sent': datetime.now(UTC)}}
    )

def update_campaign_status(db, campaign_name, status):
    """Update campaign status and completion date if completed"""
    update_data = {'status': status}
    if status == 'completed':
        update_data['completed_date'] = datetime.now(UTC)
    
    db.campaigns.update_one(
        {'name': campaign_name},
        {'$set': update_data}
    )

def send_campaign_emails(campaign_name):
    # Connect to database
    db = connect_to_db()
    
    # Get SendGrid API key
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
    
    # Get campaign recipients
    recipients = get_campaign_recipients(db, campaign_name)
    if not recipients:
        print(f"No recipients found for campaign '{campaign_name}'")
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
        'failed': 0
    }
    
    # Send emails to each recipient
    for email in recipients:
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
                print(f'Email sent successfully to {email}!')
                stats['sent'] += 1
                
                # Update contact's last_email_sent date
                update_contact_send_date(db, email)
            else:
                print(f'Unexpected status code {response.status_code} for {email}')
                stats['failed'] += 1
                
        except Exception as e:
            print(f'Error sending email to {email}: {e}')
            stats['failed'] += 1
    
    # Update campaign status based on results
    if stats['failed'] == 0:
        update_campaign_status(db, campaign_name, 'completed')
    else:
        update_campaign_status(db, campaign_name, 'completed_with_errors')
    
    # Print final statistics
    print(f"\nCampaign '{campaign_name}' completed:")
    print(f"Total recipients: {stats['total']}")
    print(f"Successfully sent: {stats['sent']}")
    print(f"Failed: {stats['failed']}")

def main():
    parser = argparse.ArgumentParser(description='Send emails for a specific campaign')
    parser.add_argument('--campaign', required=True,
                       help='Name of the campaign to send')
    
    args = parser.parse_args()
    
    try:
        send_campaign_emails(args.campaign)
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()