from pymongo import MongoClient
from datetime import datetime, UTC, timedelta
import json
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

# Set up file paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'email-system-data')

def connect_to_db():
    """Connect to MongoDB database"""
    load_dotenv()
    client = MongoClient(os.getenv('MONGODB_URI'))
    return client.email_system

def extract_domain(email):
    """Extract and validate domain from email address"""
    try:
        domain = email.split('@')[1].lower()
        # Basic domain validation
        if re.match(r'^[a-z0-9][a-z0-9-.]+\.[a-z]{2,}$', domain):
            return domain
        return None
    except (IndexError, AttributeError):
        return None

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def process_contact(data, known_providers):
    """Extract and validate contact data"""
    business_info = data.get('business_info', {})
    email = business_info.get('email')
    
    if not email:
        return None, "Missing email"
    
    if not is_valid_email(email):
        return None, "Invalid email format"
    
    domain = extract_domain(email)
    if not domain:
        return None, "Invalid domain format"
    
    # Check if domain is a known provider
    is_provider_domain = domain in known_providers
    
    contact_data = {
        'email': email,
        'domain': domain,
        'is_provider_domain': is_provider_domain,
        'business_name': business_info.get('business name'),
        'first_name': business_info.get('first name'),
        'surname': business_info.get('surname'),
        'url': data.get('url'),
        'original_data': data,
        'last_email_sent': None,
        'added_date': datetime.now(UTC),
        'active': True
    }
    
    return contact_data, None

def import_campaign_contacts(file_path, campaign_name):
    """Import and process contacts for a campaign with enhanced validation"""
    db = connect_to_db()
    contacts = db.contacts
    campaigns = db.campaigns
    
    # Calculate the date 14 days ago
    fourteen_days_ago = datetime.now(UTC) - timedelta(days=14)
    
    stats = {
        'total_processed': 0,
        'new_to_master': 0,
        'excluded_recent': 0,
        'excluded_provider_domain': 0,
        'excluded_invalid_email': 0,
        'campaign_recipients': 0
    }
    
    # Load known email providers
    known_providers = set(db.email_providers.distinct('domain'))
    logging.info(f"Loaded {len(known_providers)} known email providers")
    
    # Check if campaign already exists
    existing_campaign = campaigns.find_one({'name': campaign_name})
    if existing_campaign:
        logging.error(f"Campaign '{campaign_name}' already exists")
        return None
    
    campaign_recipients = []
    
    try:
        # Load and process the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)
            
        # Handle both single object and array of objects
        if isinstance(data, dict):
            data = [data]
            
        # Process each contact
        for record in data:
            stats['total_processed'] += 1
            
            try:
                contact_data, error = process_contact(record, known_providers)
                
                if error:
                    logging.warning(f"Skipping record: {error}")
                    stats['excluded_invalid_email'] += 1
                    continue
                
                # Skip provider domain emails
                if contact_data['is_provider_domain']:
                    logging.warning(f"Skipping provider domain email: {contact_data['email']}")
                    stats['excluded_provider_domain'] += 1
                    continue
                
                # Check existing domain
                domain = contact_data['domain']
                existing_domain = db.existing_customers.find_one({'domain': domain})
                
                # Check if contact exists and when they were last emailed
                existing_contact = contacts.find_one({'email': contact_data['email']})
                
                if existing_contact:
                    last_email_date = existing_contact.get('last_email_sent')
                    
                    # Check if contact was emailed in last 14 days
                    if last_email_date:
                        # Ensure last_email_date is UTC aware if it isn't already
                        if last_email_date.tzinfo is None:
                            last_email_date = last_email_date.replace(tzinfo=UTC)
                        if last_email_date > fourteen_days_ago:
                            logging.info(f"Contact {contact_data['email']} emailed too recently")
                            stats['excluded_recent'] += 1
                            continue
                else:
                    # Add new contact to master list
                    contacts.update_one(
                        {'email': contact_data['email']},
                        {'$set': contact_data},
                        upsert=True
                    )
                    
                    # Add to existing_customers if not already there
                    if not existing_domain:
                        db.existing_customers.update_one(
                            {'domain': domain},
                            {
                                '$set': {
                                    'email': contact_data['email'],
                                    'domain': domain,
                                    'added_date': datetime.now(UTC),
                                    'source_id': str(record.get('id', ''))
                                }
                            },
                            upsert=True
                        )
                    stats['new_to_master'] += 1
                
                # Add to campaign recipients
                campaign_recipients.append(contact_data['email'])
                stats['campaign_recipients'] += 1
                logging.info(f"Added to campaign: {contact_data['email']}")
                
            except Exception as e:
                logging.error(f"Error processing record: {e}")
                
        # Create campaign record if we have recipients
        if campaign_recipients:
            campaign_data = {
                'name': campaign_name,
                'created_date': datetime.now(UTC),
                'status': 'ready',
                'total_recipients': len(campaign_recipients),
                'recipients': campaign_recipients,
                'validation_stats': stats
            }
            
            campaigns.insert_one(campaign_data)
            logging.info(f"Created campaign '{campaign_name}' with {len(campaign_recipients)} recipients")
            
        else:
            logging.warning("No valid recipients found for campaign")
            
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON file: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return None
        
    return stats

def main():
    parser = argparse.ArgumentParser(description='Import contacts for a campaign')
    parser.add_argument('--file', default='campaign_contacts.json',
                       help='Path to JSON file (default: campaign_contacts.json)')
    parser.add_argument('--campaign', required=True,
                       help='Name of the campaign')
    
    args = parser.parse_args()
    
    # Construct full file path
    if not os.path.isabs(args.file):
        file_path = os.path.join(DATA_DIR, args.file)
    else:
        file_path = args.file
    
    logging.info(f"\nImporting campaign contacts from {file_path}")
    logging.info(f"Campaign name: {args.campaign}")
    
    stats = import_campaign_contacts(file_path, args.campaign)
    
    if stats:
        logging.info("\nCampaign import completed:")
        logging.info(f"Total contacts processed: {stats['total_processed']}")
        logging.info(f"New contacts added to master list: {stats['new_to_master']}")
        logging.info(f"Contacts excluded (emailed within 14 days): {stats['excluded_recent']}")
        logging.info(f"Contacts excluded (provider domain): {stats['excluded_provider_domain']}")
        logging.info(f"Contacts excluded (invalid email): {stats['excluded_invalid_email']}")
        logging.info(f"Final campaign recipients: {stats['campaign_recipients']}")

if __name__ == "__main__":
    main()