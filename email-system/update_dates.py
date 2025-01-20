from pymongo import MongoClient
from datetime import datetime, UTC, timedelta
import os
from dotenv import load_dotenv
import argparse

def connect_to_db():
    """Connect to MongoDB database"""
    load_dotenv()
    client = MongoClient(os.getenv('MONGODB_URI'))
    return client.email_system

def update_email_dates(days_ago=15):
    """Update last_email_sent dates to specified number of days ago"""
    db = connect_to_db()
    contacts = db.contacts
    
    # Calculate the new date
    new_date = datetime.now(UTC) - timedelta(days=days_ago)
    
    try:
        # Find all contacts with a last_email_sent date
        result = contacts.update_many(
            {'last_email_sent': {'$exists': True}},
            {'$set': {'last_email_sent': new_date}}
        )
        
        # Get updated contacts for verification
        updated_contacts = list(contacts.find(
            {'last_email_sent': new_date},
            {'email': 1, 'last_email_sent': 1}
        ))
        
        print(f"\nUpdate completed:")
        print(f"Contacts found: {result.matched_count}")
        print(f"Contacts updated: {result.modified_count}")
        print("\nUpdated contacts:")
        for contact in updated_contacts:
            print(f"Email: {contact['email']}")
            print(f"New last_email_sent: {contact['last_email_sent']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error updating dates: {e}")

def main():
    parser = argparse.ArgumentParser(description='Update last_email_sent dates for testing')
    parser.add_argument('--days', type=int, default=15,
                       help='Number of days ago to set the last_email_sent date (default: 15)')
    
    args = parser.parse_args()
    
    print(f"\nUpdating last_email_sent dates to {args.days} days ago...")
    update_email_dates(args.days)

if __name__ == "__main__":
    main()