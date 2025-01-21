from pymongo import MongoClient
from datetime import datetime, UTC
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

def process_contact(data, known_providers, existing_contacts):
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
    
    # Check if domain is a provider domain
    is_provider_domain = domain in known_providers
    
    # For provider domains, only check exact email match
    # For business domains, check domain-level duplicates
    duplicate_check = {'email': email} if is_provider_domain else {'domain': domain}
    existing = existing_contacts.find_one(duplicate_check)
    
    if existing:
        error_msg = "Email already exists" if is_provider_domain else "Business domain already exists"
        return None, error_msg
    
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

def import_contacts(file_path):
    """Import contacts from JSON file with enhanced validation"""
    db = connect_to_db()
    contacts = db.contacts
    
    stats = {
        'processed': 0,
        'imported': 0,
        'skipped_no_email': 0,
        'skipped_invalid_email': 0,
        'skipped_duplicate_email': 0,
        'skipped_duplicate_domain': 0,
        'updated': 0,
        'errors': 0
    }
    
    # Load known email providers
    known_providers = set(db.email_providers.distinct('domain'))
    logging.info(f"Loaded {len(known_providers)} known email providers")
    
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            
        # Handle both single object and array of objects
        if isinstance(data, dict):
            data = [data]
            
        for record in data:
            stats['processed'] += 1
            
            try:
                contact_data, error = process_contact(record, known_providers, contacts)
                
                if error:
                    logging.warning(f"Skipping record: {error}")
                    if "Missing email" in error:
                        stats['skipped_no_email'] += 1
                    elif "Invalid" in error:
                        stats['skipped_invalid_email'] += 1
                    elif "Email already exists" in error:
                        stats['skipped_duplicate_email'] += 1
                    elif "Business domain already exists" in error:
                        stats['skipped_duplicate_domain'] += 1
                    continue

                # Add to contacts collection
                result = contacts.update_one(
                    {'email': contact_data['email']},
                    {'$set': contact_data},
                    upsert=True
                )
                
                if result.upserted_id:
                    stats['imported'] += 1
                    domain_type = "provider domain" if contact_data['is_provider_domain'] else "business domain"
                    logging.info(f"Imported new contact: {contact_data['email']} ({domain_type})")
                elif result.modified_count:
                    stats['updated'] += 1
                    logging.info(f"Updated existing contact: {contact_data['email']}")
                    
            except Exception as e:
                logging.error(f"Error processing record: {e}")
                stats['errors'] += 1
                
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
    parser = argparse.ArgumentParser(description='Import contacts from JSON file')
    parser.add_argument('--file', default='contacts.json', 
                       help='Path to JSON file (default: contacts.json)')
    
    args = parser.parse_args()
    
    # Construct full file path
    if not os.path.isabs(args.file):
        file_path = os.path.join(DATA_DIR, args.file)
    else:
        file_path = args.file
        
    logging.info(f"Starting import from {file_path}")
    stats = import_contacts(file_path)
    
    if stats:
        logging.info("\nImport completed:")
        logging.info(f"Processed: {stats['processed']}")
        logging.info(f"Imported: {stats['imported']}")
        logging.info(f"Updated: {stats['updated']}")
        logging.info(f"Skipped (no email): {stats['skipped_no_email']}")
        logging.info(f"Skipped (invalid email): {stats['skipped_invalid_email']}")
        logging.info(f"Skipped (duplicate email): {stats['skipped_duplicate_email']}")
        logging.info(f"Skipped (duplicate domain): {stats['skipped_duplicate_domain']}")
        logging.info(f"Errors: {stats['errors']}")

if __name__ == "__main__":
    main()