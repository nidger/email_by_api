# delete_campaigns.py
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import argparse
import logging
from datetime import datetime, UTC

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

def delete_all_campaigns(confirm=True):
    """Delete all campaigns from the database"""
    db = connect_to_db()
    campaigns = db.campaigns
    
    count = campaigns.count_documents({})
    
    if count == 0:
        logging.info("No campaigns found in database")
        return 0
        
    if confirm:
        logging.warning(f"WARNING: This will permanently delete {count} campaigns")
        confirmation = input("Type 'DELETE' to confirm: ")
        if confirmation.strip().upper() != 'DELETE':
            logging.info("Deletion cancelled")
            return 0

    result = campaigns.delete_many({})
    
    logging.info(f"Deleted {result.deleted_count} campaigns")
    
    # Verify deletion
    remaining = campaigns.count_documents({})
    if remaining > 0:
        logging.error(f"Error: {remaining} campaigns remaining after deletion")
    else:
        logging.info("All campaigns successfully removed")
    
    return result.deleted_count

def main():
    parser = argparse.ArgumentParser(description='Delete all campaigns from the database')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    try:
        deleted_count = delete_all_campaigns(confirm=not args.force)
        exit_code = 0 if deleted_count >= 0 else 1
    except Exception as e:
        logging.error(f"Error deleting campaigns: {str(e)}")
        exit_code = 1
    
    exit(exit_code)

if __name__ == "__main__":
    main()