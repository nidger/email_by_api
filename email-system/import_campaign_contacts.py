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

def process_contact(data, known_providers, existing_business_domains, campaign_emails):
    """Extract and validate contact data"""
    business_info = data.get('business_info', {})
    email = business_info.get('email', '').lower()
    
    if not email:
        return None, "Missing email"
    
    if not is_valid_email(email):
        return None, "Invalid email format"
    
    domain = extract_domain(email)
    if not domain:
        return None, "Invalid domain format"
    
    # Check if email already exists in this campaign
    if email in campaign_emails:
        return None, "Email already exists in this campaign"
    
    # For non-provider domains, check business domain duplication
    if domain not in known_providers and domain in existing_business_domains:
        return None, f"Business domain {domain} already exists"
    
    contact_data = {
        'email': email,
        'domain': domain,
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
    """Import and process contacts for a campaign"""
    db = connect_to_db()
    contacts = db.contacts
    campaigns = db.campaigns
    
    stats = {
        'total_processed': 0,
        'new_to_master': 0,
        'existing_in_master': 0,
        'excluded_campaign_duplicate': 0,
        'excluded_business_domain': 0,
        'excluded_invalid': 0,
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
    
    # Get existing business domains (excluding provider domains)
    existing_business_domains = set(
        domain for domain in contacts.distinct('domain')
        if domain not in known_providers
    )
    
    campaign_emails = set()  # Track emails in this campaign
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
                contact_data, error = process_contact(
                    record,
                    known_providers,
                    existing_business_domains,
                    campaign_emails
                )
                
                if error:
                    if "already exists in this campaign" in error:
                        logging.info(f"Skipping campaign duplicate: {record.get('business_info', {}).get('email')}")
                        stats['excluded_campaign_duplicate'] += 1
                    elif "Business domain" in error:
                        logging.info(f"Skipping duplicate business domain: {error}")
                        stats['excluded_business_domain'] += 1
                    else:
                        logging.warning(f"Skipping record: {error}")
                        stats['excluded_invalid'] += 1
                    continue
                
                # Check if contact exists in master list
                existing_contact = contacts.find_one({'email': contact_data['email']})
                
                if existing_contact:
                    stats['existing_in_master'] += 1
                    logging.info(f"Contact exists in master list: {contact_data['email']}")
                else:
                    # Add new contact to master list
                    contacts.insert_one(contact_data)
                    stats['new_to_master'] += 1
                    logging.info(f"Added new contact to master list: {contact_data['email']}")
                    
                    # Add domain to tracking set if it's a business domain
                    if contact_data['domain'] not in known_providers:
                        existing_business_domains.add(contact_data['domain'])
                
                # Add to campaign recipients
                campaign_recipients.append(contact_data['email'])
                campaign_emails.add(contact_data['email'])
                stats['campaign_recipients'] += 1
                logging.info(f"Added to campaign: {contact_data['email']}")
                
            except Exception as e:
                logging.error(f"Error processing record: {e}")
                stats['excluded_invalid'] += 1
                
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
        logging.info(f"Existing contacts in master list: {stats['existing_in_master']}")
        logging.info(f"Excluded (campaign duplicate): {stats['excluded_campaign_duplicate']}")
        logging.info(f"Excluded (business domain): {stats['excluded_business_domain']}")
        logging.info(f"Excluded (invalid): {stats['excluded_invalid']}")
        logging.info(f"Final campaign recipients: {stats['campaign_recipients']}")

if __name__ == "__main__":
    main()