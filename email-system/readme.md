# Email Campaign System

A Python-based system for managing email campaigns with MongoDB and SendGrid, featuring contact management, campaign creation, and automated sending with frequency controls.

## Requirements

```
python-dotenv
pymongo
sendgrid
```

Environment variables needed in `.env`:
- MONGODB_URI
- SENDGRID_API_KEY

## System Components

- `setup_database.py`: Initialize MongoDB collections and indexes
- `import_contacts.py`: Add contacts to master list
- `import_campaign_contacts.py`: Create campaigns from contact lists
- `send_campaign_emails.py`: Send campaign emails
- `update_dates.py`: Testing utility to modify last email dates

## Usage Instructions

### 1. Database Setup

Run once to initialize the database structure:
```bash
python3 setup_database.py
```

### 2. Contact Management

#### Import Contacts to Master List
```bash
python3 import_contacts.py
```
or specify a file:
```bash
python3 import_contacts.py --file your_contacts.json
```

#### Create a Campaign
```bash
python3 import_campaign_contacts.py --campaign "Campaign Name"
```
Options:
- `--campaign`: Name of your campaign (required)
- `--file`: JSON file with contacts (defaults to 'campaign_contacts.json')

### 3. Sending Campaigns
```bash
python3 send_campaign_emails.py --campaign "Campaign Name"
```
This will:
- Send emails to all eligible recipients
- Update contact email dates
- Show sending statistics

### 4. Testing Tools

Update email dates for testing frequency rules:
```bash
python3 update_dates.py --days 15
```
Options:
- `--days`: Number of days to set last email date (defaults to 15)

## Workflow Example

```bash
# First time setup
python3 setup_database.py

# Import new contacts
python3 import_contacts.py --file new_contacts.json

# Create campaign
python3 import_campaign_contacts.py --campaign "January Newsletter"

# Send emails
python3 send_campaign_emails.py --campaign "January Newsletter"

# For testing - update dates to send again
python3 update_dates.py --days 15
```

## Important Notes

### Contact Rules
- 14-day minimum between emails to the same contact
- Automatic duplicate handling
- Complete contact history stored

### File Format
Contacts JSON must follow this structure:
```json
{
  "store_name": "Example Store",
  "business_info": {
    "business name": "Business Name",
    "first name": "First",
    "surname": "Last",
    "email": "email@example.com"
  }
}
```

### Database Collections
- contacts: Master list of all contacts
- campaigns: Campaign information
- email_history: Record of all sent emails
- unsubscribes: Tracking unsubscribed contacts

## Troubleshooting

If you encounter timezone warnings when running campaigns, ensure all scripts are using UTC-aware datetime objects.

For testing purposes, use `update_dates.py` to reset email dates rather than manually modifying the database.

## Error Handling

The system includes:
- Duplicate email prevention
- Missing data handling
- SendGrid error tracking
- Campaign status monitoring

## Author

[Your Name]

## License

[Your License Choice - no licence chosen yet]
