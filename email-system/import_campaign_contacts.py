from pymongo import MongoClient
from datetime import datetime, UTC, timedelta
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

def import_campaign_contacts(file_path, campaign_name):
    """Import and process contacts for a campaign"""
    db = connect_to_db()
    contacts = db.contacts
    campaigns = db.campaigns
    
    # Calculate the date 14 days ago
    fourteen_days_ago = datetime.now(UTC) - timedelta(days=14)
    
    stats = {
        'total_processed': 0,
        'new_to_master': 0,
        'excluded_recent': 0,
        'campaign_recipients': 0
    }
    
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
                contact_data = process_contact(record)
                
                # Skip records without email
                if not contact_data['email']:
                    continue
                
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
                            stats['excluded_recent'] += 1
                            continue
                else:
                    # Add new contact to master list
                    contacts.update_one(
                        {'email': contact_data['email']},
                        {'$set': contact_data},
                        upsert=True
                    )
                    stats['new_to_master'] += 1
                
                # Add to campaign recipients
                campaign_recipients.append(contact_data['email'])
                stats['campaign_recipients'] += 1
                
            except Exception as e:
                print(f"Error processing record: {e}")
                
        # Create campaign record
        if campaign_recipients:
            campaign_data = {
                'name': campaign_name,
                'created_date': datetime.now(UTC),
                'status': 'ready',
                'total_recipients': len(campaign_recipients),
                'recipients': campaign_recipients
            }
            
            campaigns.update_one(
                {'name': campaign_name},
                {'$set': campaign_data},
                upsert=True
            )
            
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
    parser = argparse.ArgumentParser(description='Import contacts for a campaign')
    parser.add_argument('--file', default='campaign_contacts.json',
                       help='Path to JSON file (default: campaign_contacts.json)')
    parser.add_argument('--campaign', required=True,
                       help='Name of the campaign')
    
    args = parser.parse_args()
    
    # Process import
    print(f"\nImporting campaign contacts from {args.file}")
    print(f"Campaign name: {args.campaign}")
    
    stats = import_campaign_contacts(args.file, args.campaign)
    
    if stats:
        print("\nCampaign import completed:")
        print(f"Total contacts processed: {stats['total_processed']}")
        print(f"New contacts added to master list: {stats['new_to_master']}")
        print(f"Contacts excluded (emailed within 14 days): {stats['excluded_recent']}")
        print(f"Final campaign recipients: {stats['campaign_recipients']}")

if __name__ == "__main__":
    main()