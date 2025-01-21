# Email Campaign System

A Python-based system for managing B2B email campaigns with MongoDB and SendGrid, featuring intelligent contact handling, campaign management, and automated sending with frequency controls.

## Key Features

* Smart domain handling (business vs provider domains)
* Contact deduplication with domain-level rules
* Campaign-specific validation
* 14-day frequency control per email address
* Existing customer protection
* Comprehensive logging and statistics

## System Logic and Flow

### 1. Database Setup (`setup_database.py`)

Sets up MongoDB collections with required indexes and validation:

* contacts: Master contact list
* campaigns: Campaign definitions and recipient lists
* email_history: Record of all sent emails
* email_providers: List of known email provider domains
* existing_customers: Current customer database
* unsubscribes: Opt-out tracking

### 2. Contact Import Process (`import_contacts.py`)

Creates the master contact list with these validation rules:

**Provider Domains (e.g., gmail.com, yahoo.com)**
* Listed in email_providers collection
* Multiple contacts allowed from same domain
* Only checks for exact email duplicates
* Example: Both john@gmail.com and jane@gmail.com are allowed

**Business Domains (e.g., company.com)**
* Any domain not in email_providers list
* Only ONE contact allowed per domain
* Checks for domain-level duplicates
* Example: If john@company.com exists, jane@company.com is blocked

### 3. Campaign Creation (`import_campaign_contacts.py`)

Creates a campaign with these steps:

1. **Initial Validation**
   * Checks campaign name doesn't exist
   * Validates email format
   * Verifies against existing_customers

2. **Contact Processing Rules**
   * For Provider Domains (gmail.com):
     * Allows multiple different emails
     * Blocks exact duplicates only
   * For Business Domains (company.com):
     * Allows same contact to be added
     * Blocks different contacts from same domain
   * Maintains running statistics

3. **Campaign Creation**
   * Creates campaign record
   * Stores recipient list
   * Sets status to 'ready'
   * Records validation statistics

### 4. Email Sending Process (`send_campaign_emails.py`)

Sends emails with these checks:

1. **Pre-send Validation** (per recipient)
   * Validates email format
   * Checks unsubscribe list
   * Verifies against existing customers
   * Enforces 14-day frequency limit

2. **Frequency Control**
   * Tracks last_email_sent date per contact
   * Skips if email sent within last 14 days
   * Applies to specific email address only
   * Domain relationship doesn't affect frequency

3. **Send Process**
   * Configures SendGrid settings
   * Sends email via API
   * Records in email_history
   * Updates contact's last_email_sent
   * Updates campaign status

4. **Status Tracking**
   * Records successful sends
   * Tracks failures
   * Counts skipped emails by reason
   * Updates final campaign status

## Example Usage

1. **Setup Database**
```bash
python3 setup_database.py
```

2. **Import Master Contacts**
```bash
python3 import_contacts.py
```

3. **Create Campaign**
```bash
python3 import_campaign_contacts.py --campaign "Campaign Name"
```

4. **Send Campaign**
```bash
python3 send_campaign_emails.py --campaign "Campaign Name"
```

## Test Utilities

`update_dates.py`: Updates last_email_sent dates for testing frequency controls
```bash
python3 update_dates.py --days 15
```

## Required Environment Variables (.env)
```
MONGODB_URI=your_mongodb_connection_string
SENDGRID_API_KEY=your_sendgrid_api_key
DEFAULT_FROM_EMAIL=your_sender_email
PARTNER_WEBSITE_URL=your_website_url
```

## Contact JSON Structure
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

## Understanding Campaign Results

### Success Example
```
Campaign 'Test Campaign' completed:
Total recipients: 5
Successfully sent: 5
Failed: 0
Skipped (invalid email): 0
Skipped (frequency): 0
Skipped (unsubscribed): 0
Skipped (existing customer): 0
```

### Frequency Control Example
```
Campaign 'Test Campaign' completed:
Total recipients: 5
Successfully sent: 1
Failed: 0
Skipped (invalid email): 0
Skipped (frequency): 4  # Emails sent too recently
Skipped (unsubscribed): 0
Skipped (existing customer): 0
```

## Common Scenarios

1. **Multiple Gmail Addresses**
   * john@gmail.com - Allowed
   * jane@gmail.com - Allowed (different email)
   * john@gmail.com - Blocked (exact duplicate)

2. **Business Domain Contacts**
   * john@company.com - Allowed
   * john@company.com - Allowed (same contact, different campaign)
   * jane@company.com - Blocked (different contact, same domain)

3. **Frequency Control**
   * Day 1: Email sent to contact@example.com
   * Day 10: Attempt to send again - Blocked (within 14 days)
   * Day 15: Attempt to send again - Allowed (outside 14 days)

## Error Handling

The system provides detailed logs for:
* Invalid email formats
* Domain validation failures
* Sending failures
* Frequency control skips
* Existing customer matches
* Campaign status updates

## Monitoring

Monitor these aspects for system health:
* Campaign completion status
* Email sending success rates
* Frequency control effectiveness
* Domain validation patterns
* Existing customer protection

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify MongoDB connection and indexes
3. Confirm SendGrid API functionality
4. Review .env configuration
