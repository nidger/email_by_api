# Email Campaign System

A Python-based system for managing email campaigns with MongoDB and SendGrid, featuring contact management, campaign creation, automated sending with frequency controls, and intelligent email provider validation.

## Project Structure

```
email_by_api_v2/
├── .env (environment variables - not in Git)
├── .gitignore
├── email-system/ (Git-tracked code)
│   ├── setup_database.py        # Database initialization
│   ├── import_contacts.py       # Master contact list management
│   ├── import_campaign_contacts.py  # Campaign-specific imports
│   ├── send_campaign_emails.py  # Email sending logic
│   ├── update_dates.py         # Testing utility
│   └── email_providers.json    # Validated provider list
└── email-system-data/ (local data only - not in Git)
    ├── contacts.json          # Your contact data
    └── campaign_contacts.json  # Campaign-specific contacts
```

## Requirements

```
python-dotenv
pymongo
sendgrid
```

## Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/nidger/email_by_api.git
```

2. Create a `.env` file in the root directory with:
- MONGODB_URI
- SENDGRID_API_KEY
- DEFAULT_FROM_EMAIL
- PARTNER_WEBSITE_URL

Note: The .env file and all data files are not tracked in Git for security.

## Database Collections

### Core Collections
- `contacts`: Master list of all contacts
  - Unique email index
  - Last email tracking
  - Business information storage

- `campaigns`: Campaign information
  - Unique campaign name index
  - Status tracking
  - Recipient list management

- `email_history`: Record of all sent emails
  - Contact email tracking
  - Campaign association
  - Sending date indexing

- `unsubscribes`: Unsubscribed contact tracking
  - Unique email enforcement
  - Timestamp tracking

### New Features
- `email_providers`: Known email provider domains
  - Validates contact email domains
  - Prevents common typos
  - Helps identify business vs personal emails
  - Automatic updates from JSON source

- `existing_customers`: Customer tracking
  - Domain-based duplicate detection
  - Source tracking
  - Added date monitoring

## Contact Processing Rules

### Validation Rules
1. Email format validation
2. Domain verification against email_providers list
3. Business domain identification
4. Duplicate detection at both email and domain levels

### Sending Rules
1. 14-day minimum between emails to same contact
2. Automatic duplicate handling across campaigns
3. Domain-based frequency controls
4. Complete contact history tracking

### Data Management
1. Automatic domain extraction and validation
2. Business information preservation
3. Source tracking for all contacts
4. Activity status monitoring

## Usage Instructions

### 1. Database Setup

Initialize the database structure and email providers:
```bash
python3 setup_database.py
```

This will:
- Create all required collections
- Set up indexes
- Import validated email providers
- Establish validation rules

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

### 4. Testing Tools

Update email dates for testing frequency rules:
```bash
python3 update_dates.py --days 15
```

## Data Format Requirements

### Contact JSON Structure
```json
{
  "store_name": "Example Store",
  "business_info": {
    "business name": "Business Name",
    "first name": "First",
    "surname": "Last",
    "email": "email@example.com",
    "address": "Full Address",
    "phone number": "Contact Number",
    "vat number": "VAT Number"
  },
  "url": "Store URL",
  "scraped_at": "ISO DateTime"
}
```

### Email Providers JSON
```json
{
  "email_providers": [
    "provider1.com",
    "provider2.com"
  ]
}
```

## Error Handling

The system includes comprehensive error handling for:
- Email validation failures
- Domain verification issues
- Duplicate detection
- SendGrid API errors
- Campaign status monitoring
- Data format validation

## Development Guidelines

### Version Control
- All code changes should be made in the `email-system/` directory
- Never commit data files or .env
- Update email_providers.json when new providers are validated

### Testing
- Use update_dates.py for frequency rule testing
- Validate new email providers before adding
- Test campaign imports with sample data
- Verify duplicate detection logic

## Security Considerations

1. Data Protection
   - All contact data stays local
   - No sensitive data in Git
   - Secure credential management

2. Email Security
   - Domain validation
   - Frequency controls
   - Unsubscribe tracking

## Author

[Your Name]

## License

[Your License Choice - no licence chosen yet]