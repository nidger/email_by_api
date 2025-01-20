from pymongo import MongoClient
from datetime import datetime, UTC
import json
import os
from dotenv import load_dotenv
import argparse

def connect_to_db():
    """Connect to MongoDB database"""
    load_dotenv()
    client = MongoClient(os.getenv('MONGODB_URI'))
    return client.email_system

def process_contact(data):
    """Extract relevant fields from contact data"""
    business_info = data.get('business_info', {})
    
    return {
        'email': business_info.get('email'),
        'business_name': business_info.get('business name'),
        'first_name': business_info.get('first name'),
        'surname': business_info.get('surname'),
        'url': data.get('url'),
        'original_data': data,
        'last_email_sent': None,
        'added_date': datetime.now(UTC),
        'active': True
    }

def import_contacts(file_path):
    """Import contacts from JSON file"""
    db = connect_to_db()
    contacts = db.contacts
    
    stats = {
        'processed': 0,
        'imported': 0,
        'skipped_no_email': 0,
        'updated': 0,
        'errors': 0
    }
    
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            
        # Handle both single object and array of objects
        if isinstance(data, dict):
            data = [data]
            
        for record in data:
            stats['processed'] += 1
            
            try:
                contact_data = process_contact(record)
                
                # Skip records without email
                if not contact_data['email']:
                    stats['skipped_no_email'] += 1
                    continue
                
                # Use update_one with upsert to handle duplicates
                result = contacts.update_one(
                    {'email': contact_data['email']},
                    {'$set': contact_data},
                    upsert=True
                )
                
                if result.upserted_id:
                    stats['imported'] += 1
                elif result.modified_count:
                    stats['updated'] += 1
                    
            except Exception as e:
                print(f"Error processing record: {e}")
                stats['errors'] += 1
                
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON file at {file_path}")
        return None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None
        
    return stats

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Import contacts from JSON file')
    parser.add_argument('--file', default='contacts.json', 
                       help='Path to JSON file (default: contacts.json)')
    
    args = parser.parse_args()
    
    # Process import
    print(f"Importing contacts from {args.file}")
    stats = import_contacts(args.file)
    
    if stats:
        print("\nImport completed:")
        print(f"Processed: {stats['processed']}")
        print(f"Imported: {stats['imported']}")
        print(f"Updated: {stats['updated']}")
        print(f"Skipped (no email): {stats['skipped_no_email']}")
        print(f"Errors: {stats['errors']}")

if __name__ == "__main__":
    main()