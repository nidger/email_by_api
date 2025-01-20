from pymongo import MongoClient, ASCENDING
from datetime import datetime, UTC
import os
from dotenv import load_dotenv

def setup_database():
    # Load environment variables
    load_dotenv()
    
    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URI'))
    
    # Create/Get the database
    db = client['email_system']
    
    # Drop existing collections for fresh start
    for collection in db.list_collection_names():
        db[collection].drop()
        print(f"Dropped existing collection: {collection}")

    # Create contacts collection
    contacts = db.create_collection('contacts')
    contacts.create_index([('email', ASCENDING)], unique=True)
    contacts.create_index([('last_email_sent', ASCENDING)])
    print("Created contacts collection with indexes")

    # Create campaigns collection
    campaigns = db.create_collection('campaigns')
    campaigns.create_index([('name', ASCENDING)], unique=True)
    campaigns.create_index([('status', ASCENDING)])
    print("Created campaigns collection with indexes")

    # Create email_history collection
    email_history = db.create_collection('email_history')
    email_history.create_index([('contact_email', ASCENDING)])
    email_history.create_index([('campaign_id', ASCENDING)])
    email_history.create_index([('sent_date', ASCENDING)])
    print("Created email_history collection with indexes")

    # Create unsubscribes collection
    unsubscribes = db.create_collection('unsubscribes')
    unsubscribes.create_index([('email', ASCENDING)], unique=True)
    print("Created unsubscribes collection with indexes")

    # Test insert into contacts
    try:
        test_contact = {
            'email': 'test@example.com',
            'business_name': 'Test Business',
            'first_name': 'Test',
            'surname': 'User',
            'url': 'https://example.com',
            'original_data': {},
            'last_email_sent': None,
            'added_date': datetime.now(UTC),
            'active': True
        }
        contacts.insert_one(test_contact)
        print("Successfully inserted test contact")

        # Clean up test data
        contacts.delete_one({'email': 'test@example.com'})
        print("Cleaned up test contact")

    except Exception as e:
        print(f"Error during test insert: {e}")

    # Print collection info
    print("\nDatabase setup complete. Collection information:")
    for collection_name in db.list_collection_names():
        count = db[collection_name].count_documents({})
        indexes = db[collection_name].list_indexes()
        print(f"\n{collection_name}:")
        print(f"Documents: {count}")
        print("Indexes:")
        for index in indexes:
            print(f"- {index['name']}: {index['key']}")

if __name__ == "__main__":
    try:
        setup_database()
        print("\nDatabase setup completed successfully!")
    except Exception as e:
        print(f"\nError during database setup: {e}")