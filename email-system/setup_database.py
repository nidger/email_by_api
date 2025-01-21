from pymongo import MongoClient, ASCENDING
from datetime import datetime, UTC
import os
import json
from dotenv import load_dotenv
import re

def extract_domain(email):
    """Extract domain from email address"""
    try:
        return email.split('@')[1].lower()
    except (IndexError, AttributeError):
        return None

def get_email_providers(file_path='email_providers.json'):
    """Load email providers from JSON file and return deduplicated list"""
    # Default providers in case file loading fails
    default_providers = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'aol.com', 'protonmail.com', 'icloud.com'
    ]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            providers = data.get('email_providers', [])
            # Ensure all providers are lowercase and unique
            providers = sorted(list({p.strip().lower() for p in providers if p.strip()}))
            return providers if providers else default_providers
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Error loading {file_path}: {e}")
        print("Using default email providers list.")
        return default_providers

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

    print("\nCreating new collections...")

    # Create contacts collection
    contacts = db.create_collection('contacts')
    contacts.create_index([('email', ASCENDING)], unique=True)
    contacts.create_index([('last_email_sent', ASCENDING)])
    print("Created contacts collection with indexes")

    # Create existing_customers collection with validation
    existing_customers = db.create_collection(
        'existing_customers',
        validator={
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['email', 'domain', 'added_date'],
                'properties': {
                    'email': {
                        'bsonType': 'string',
                        'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    },
                    'domain': {
                        'bsonType': 'string',
                        'pattern': r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    },
                    'added_date': {
                        'bsonType': 'date'
                    },
                    'source_id': {
                        'bsonType': ['string', 'null']
                    }
                }
            }
        }
    )

    # Create indexes for existing_customers
    existing_customers.create_index([('email', ASCENDING)], unique=True)
    existing_customers.create_index([('domain', ASCENDING)])
    print("Created existing_customers collection with indexes")

    # Create email_providers collection
    email_providers = db.create_collection(
        'email_providers',
        validator={
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['domain', 'added_date'],
                'properties': {
                    'domain': {
                        'bsonType': 'string',
                        'pattern': '^[a-z0-9][a-z0-9-.]+(\\.[a-z]{2,})+$'
                    },
                    'added_date': {
                        'bsonType': 'date'
                    },
                    'description': {
                        'bsonType': ['string', 'null']
                    }
                }
            }
        }
    )

    # Create index for email_providers
    email_providers.create_index([('domain', ASCENDING)], unique=True)
    print("Created email_providers collection with indexes")

    # Populate email_providers with initial data
    providers_list = get_email_providers()
    if providers_list:
        provider_documents = [
            {
                'domain': domain,
                'added_date': datetime.now(UTC),
                'description': 'Initial provider'
            }
            for domain in providers_list
        ]
        try:
            email_providers.insert_many(provider_documents)
            print(f"Successfully inserted {len(providers_list)} email providers")
        except Exception as e:
            print(f"Error inserting email providers: {e}")

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

    print("\nTesting collections with sample data...")

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
        print(f"Error during test insert into contacts: {e}")

    # Test insert into existing_customers
    try:
        test_customer = {
            'email': 'test.customer@example.com',
            'domain': 'example.com',
            'added_date': datetime.now(UTC),
            'source_id': 'TEST001'
        }
        existing_customers.insert_one(test_customer)
        print("Successfully inserted test customer")

        # Clean up test data
        existing_customers.delete_one({'email': 'test.customer@example.com'})
        print("Cleaned up test customer")

    except Exception as e:
        print(f"Error during test insert into existing_customers: {e}")

    # Test insert into email_providers
    try:
        test_provider = {
            'domain': 'test-provider.com',
            'added_date': datetime.now(UTC),
            'description': 'Test provider'
        }
        email_providers.insert_one(test_provider)
        print("Successfully inserted test email provider")

        # Clean up test data
        email_providers.delete_one({'domain': 'test-provider.com'})
        print("Cleaned up test email provider")

    except Exception as e:
        print(f"Error during test insert into email_providers: {e}")

    # Print collection info with better formatting
    print("\nDatabase setup complete. Collection information:")
    print("-" * 50)
    
    for collection_name in sorted(db.list_collection_names()):
        collection = db[collection_name]
        count = collection.count_documents({})
        indexes = list(collection.list_indexes())
        
        print(f"\nCollection: {collection_name}")
        print(f"Documents: {count}")
        print("Indexes:")
        for index in indexes:
            print(f"  - {index['name']}: {index['key']}")
        print("-" * 50)

if __name__ == "__main__":
    try:
        setup_database()
        print("\nDatabase setup completed successfully!")
    except Exception as e:
        print(f"\nError during database setup: {e}")