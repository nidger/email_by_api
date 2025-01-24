from sendgrid import SendGridAPIClient
from pymongo import MongoClient
from datetime import datetime, UTC
import os
import logging
import json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_sendgrid_unsubscribes(sg_client):
    """Fetch ALL unsubscribes from SendGrid (source of truth)"""
    try:
        all_unsubscribes = []
        page = 1
        page_size = 1000  # SendGrid's max per page
        
        while True:
            response = sg_client.client.suppression.unsubscribes.get(
                query_params={
                    'page_size': page_size,
                    'page': page
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"SendGrid API error: {response.body.decode('utf-8')}")
                
            data = json.loads(response.body.decode('utf-8'))
            all_unsubscribes.extend([entry['email'] for entry in data])
            
            if len(data) < page_size:
                break  # Last page
            page += 1

        return set(all_unsubscribes)
        
    except Exception as e:
        logger.error(f"Failed to fetch SendGrid unsubscribes: {str(e)}")
        raise

def sync_unsubscribes():
    """One-way sync: Overwrite MongoDB with SendGrid's unsubscribe list"""
    # Load environment variables
    load_dotenv()
    
    # Connect to services
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
    mongo_client = MongoClient(os.getenv('MONGODB_URI'))
    db = mongo_client.email_system
    
    try:
        # Get current state
        sendgrid_emails = get_sendgrid_unsubscribes(sg)
        mongo_emails = {doc['email'] for doc in db.unsubscribes.find({}, {'email': 1})}
        
        # Calculate changes needed
        to_add = sendgrid_emails - mongo_emails
        to_remove = mongo_emails - sendgrid_emails
        
        # Add new unsubscribes to MongoDB (no changes to SendGrid)
        if to_add:
            add_operations = [
                {
                    'email': email,
                    'synced_at': datetime.now(UTC),
                    'source': 'sendgrid'
                } for email in to_add
            ]
            db.unsubscribes.insert_many(add_operations, ordered=False)
            logger.info(f"Added {len(to_add)} unsubscribes to MongoDB")
        
        # Remove stale entries from MongoDB (SendGrid is authoritative)
        if to_remove:
            db.unsubscribes.delete_many({'email': {'$in': list(to_remove)}})
            logger.info(f"Removed {len(to_remove)} stale unsubscribes from MongoDB")
        
        # Final status
        current_count = db.unsubscribes.count_documents({})
        logger.info(f"Sync complete. MongoDB now has {current_count} unsubscribes (mirroring SendGrid)")
        
    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        raise
    finally:
        mongo_client.close()

if __name__ == "__main__":
    sync_unsubscribes()