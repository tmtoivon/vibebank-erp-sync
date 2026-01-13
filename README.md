# VibeBankERP Sync

A Django application for synchronizing receivables and payables from multiple accounting systems (Netvisor, Fennoa, and Procountor) and e-commerce platforms (Shopify, Etsy, and eBay) into a unified database.

## Features

- **Multi-system support**: Sync data from Netvisor, Fennoa, Procountor, Shopify, Etsy, and eBay
- **Unified data model**: Generic database models that work across all accounting systems
- **Receivables & Payables**: Sync both sales invoices (receivables) and purchase invoices (payables)
- **Line items**: Full support for invoice line items with tax calculations
- **Customer & Vendor tracking**: Automatic syncing of customer and vendor information
- **Audit logging**: Complete sync history with success/failure tracking
- **Incremental sync**: Date-based filtering for efficient incremental updates
- **WhatsApp Integration**: AI-powered WhatsApp bot for querying financial data via natural language
- **LLM-powered queries**: Uses Claude to understand and respond to customer questions about invoices

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd vibebank-erp-sync
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables for your accounting systems (see Configuration section below)

5. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

6. Create a superuser (optional, for accessing Django admin):
```bash
python manage.py createsuperuser
```

## Configuration

Configure your accounting system credentials using environment variables:

### Netvisor Configuration

```bash
export NETVISOR_HOST="https://integration.netvisor.fi"
export NETVISOR_SENDER="YourCompany"
export NETVISOR_CUSTOMER_ID="your_customer_id"
export NETVISOR_CUSTOMER_KEY="your_customer_key"
export NETVISOR_PARTNER_ID="your_partner_id"
export NETVISOR_PARTNER_KEY="your_partner_key"
export NETVISOR_ORGANIZATION_ID="your_organization_id"
export NETVISOR_LANGUAGE="FI"
```

### Fennoa Configuration

```bash
export FENNOA_API_KEY="your_api_key"
export FENNOA_BASE_URL="https://api.fennoa.com"
```

### Procountor Configuration

```bash
export PROCOUNTOR_API_KEY="your_api_key"
export PROCOUNTOR_COMPANY_ID="your_company_id"
export PROCOUNTOR_BASE_URL="https://api.procountor.com"
export PROCOUNTOR_CLIENT_ID="your_client_id"  # For OAuth
export PROCOUNTOR_CLIENT_SECRET="your_client_secret"  # For OAuth
```

### Shopify Configuration

```bash
export SHOPIFY_SHOP_NAME="your-shop-name"  # Without .myshopify.com
export SHOPIFY_ACCESS_TOKEN="your_access_token"
export SHOPIFY_API_VERSION="2024-01"  # API version to use
```

### Etsy Configuration

```bash
export ETSY_API_KEY="your_api_key"
export ETSY_ACCESS_TOKEN="your_access_token"
export ETSY_SHOP_ID="your_shop_id"
```

### eBay Configuration

```bash
export EBAY_CLIENT_ID="your_client_id"
export EBAY_CLIENT_SECRET="your_client_secret"
export EBAY_REFRESH_TOKEN="your_refresh_token"
export EBAY_ENVIRONMENT="production"  # or "sandbox" for testing
```

**Getting eBay Credentials:**
1. Create a developer account at [eBay Developers Program](https://developer.ebay.com/)
2. Create an application to get Client ID and Client Secret
3. Generate a refresh token using OAuth 2.0 flow
4. Refresh tokens are long-lived and used to get short-lived access tokens

### WhatsApp Integration Configuration

```bash
# Twilio WhatsApp API
export TWILIO_ACCOUNT_SID="your_account_sid"
export TWILIO_AUTH_TOKEN="your_auth_token"
export TWILIO_WHATSAPP_NUMBER="+14155238886"  # Your Twilio WhatsApp number

# Anthropic API for LLM
export ANTHROPIC_API_KEY="your_anthropic_api_key"
export WHATSAPP_LLM_MODEL="claude-3-5-sonnet-20241022"  # Optional, defaults to Sonnet
```

Alternatively, you can create a `.env` file in the project root and use a package like `python-decouple` or `django-environ` to load these values.

## Usage

### Sync Commands

The application provides five management commands for syncing data:

#### Sync from Netvisor

```bash
# Sync all data (default: last 30 days)
python manage.py sync-netvisor

# Sync with custom date range
python manage.py sync-netvisor --start-date 2024-01-01 --end-date 2024-12-31

# Sync only receivables
python manage.py sync-netvisor --receivables-only

# Sync only payables
python manage.py sync-netvisor --payables-only
```

#### Sync from Fennoa

```bash
# Sync all data (default: last 30 days)
python manage.py sync-fennoa

# Sync with custom date range
python manage.py sync-fennoa --start-date 2024-01-01 --end-date 2024-12-31

# Sync only receivables
python manage.py sync-fennoa --receivables-only

# Sync only payables
python manage.py sync-fennoa --payables-only
```

#### Sync from Procountor

```bash
# Sync all data (default: last 30 days)
python manage.py sync-procountor

# Sync with custom date range
python manage.py sync-procountor --start-date 2024-01-01 --end-date 2024-12-31

# Sync only receivables
python manage.py sync-procountor --receivables-only

# Sync only payables
python manage.py sync-procountor --payables-only
```

#### Sync from Shopify

```bash
# Sync all orders (default: last 30 days)
python manage.py sync-shopify

# Sync with custom date range
python manage.py sync-shopify --start-date 2024-01-01 --end-date 2024-12-31

# Sync only specific order status
python manage.py sync-shopify --status open
python manage.py sync-shopify --status closed
python manage.py sync-shopify --status cancelled
```

#### Sync from Etsy

```bash
# Sync all receipts (default: last 30 days)
python manage.py sync-etsy

# Sync with custom date range
python manage.py sync-etsy --start-date 2024-01-01 --end-date 2024-12-31

# Sync only paid orders
python manage.py sync-etsy --paid-only

# Sync only shipped orders
python manage.py sync-etsy --shipped-only
```

#### Sync from eBay

```bash
# Sync all orders (default: last 30 days)
python manage.py sync-ebay

# Sync with custom date range
python manage.py sync-ebay --start-date 2024-01-01 --end-date 2024-12-31
```

### Scheduling Syncs

You can schedule these commands to run periodically using:

- **Cron** (Linux/Mac):
```bash
# Add to crontab (runs daily at 2 AM)
0 2 * * * cd /path/to/vibebank-erp-sync && /path/to/venv/bin/python manage.py sync-netvisor
0 2 * * * cd /path/to/vibebank-erp-sync && /path/to/venv/bin/python manage.py sync-fennoa
0 2 * * * cd /path/to/vibebank-erp-sync && /path/to/venv/bin/python manage.py sync-procountor
0 2 * * * cd /path/to/vibebank-erp-sync && /path/to/venv/bin/python manage.py sync-shopify
0 2 * * * cd /path/to/vibebank-erp-sync && /path/to/venv/bin/python manage.py sync-etsy
0 2 * * * cd /path/to/vibebank-erp-sync && /path/to/venv/bin/python manage.py sync-ebay
```

- **Django-cron** or **Celery** for more advanced scheduling
- **Task Scheduler** (Windows)

## WhatsApp Integration

VibeBankERP includes a WhatsApp integration that allows customers to query their receivables and payables using natural language through WhatsApp. The system uses Claude AI to understand queries and provide intelligent responses.

### How It Works

1. **Customer Linking**: Admin links a customer's WhatsApp number to their account(s)
2. **Verification**: Customer receives a 6-digit code via WhatsApp
3. **Authentication**: Customer replies with the code to verify their identity
4. **Natural Language Queries**: Customer can ask questions about their finances in plain language

### Setting Up WhatsApp Integration

#### 1. Set up Twilio WhatsApp

1. Create a [Twilio account](https://www.twilio.com/try-twilio)
2. Set up WhatsApp Business API or use Twilio's WhatsApp Sandbox
3. Configure webhook URL: `https://yourdomain.com/whatsapp/webhook/`
4. Copy your Account SID, Auth Token, and WhatsApp number

#### 2. Get Anthropic API Key

1. Sign up at [Anthropic Console](https://console.anthropic.com/)
2. Generate an API key
3. Add to environment variables

#### 3. Link Customer Accounts

Use the management command to link a WhatsApp number to customer accounts:

```bash
# Link by customer IDs
python manage.py whatsapp-link "+14155552671" "John Smith" \
  --email "john@example.com" \
  --customer-ids "1,2,3"

# Link by external ID
python manage.py whatsapp-link "+14155552671" "John Smith" \
  --customer-external-id "CUST123" \
  --source-system "netvisor"

# Find customers by name
python manage.py whatsapp-link "+14155552671" "John Smith"
```

The customer will receive a verification code via WhatsApp. They should reply with the code to complete verification.

#### 4. Admin Interface

Access the Django admin to:
- View all WhatsApp customers
- See conversation history and messages
- Resend verification codes
- Link/unlink customer accounts
- View audit logs

Navigate to: `http://localhost:8000/admin/`

### Example Conversations

Once linked, customers can ask questions like:

```
Customer: "Show me my outstanding invoices"
Bot: "📊 You have 3 outstanding invoices:

1. Invoice #12345 - $1,250.00
   Due: Jan 15, 2024
   Status: Overdue ⚠️

2. Invoice #12346 - $850.00
   Due: Feb 1, 2024
   Status: Sent

3. Invoice #12347 - $2,100.00
   Due: Feb 15, 2024
   Status: Sent

Total outstanding: $4,200.00"

Customer: "What's the total I owe?"
Bot: "Your total outstanding payables (bills to pay): $15,450.00"

Customer: "When is invoice 12345 due?"
Bot: "Invoice #12345 was due on Jan 15, 2024 (overdue by 12 days).
Amount: $1,250.00"
```

### WhatsApp Models

The integration includes additional models:

- **WhatsAppCustomer**: Links WhatsApp numbers to customer accounts
- **WhatsAppSession**: Manages conversation sessions
- **WhatsAppMessage**: Logs all messages for audit trail
- **WhatsAppAuditLog**: Tracks all WhatsApp operations

### Security Features

- **Verification codes**: 6-digit codes that expire in 10 minutes
- **Session management**: 30-minute inactivity timeout
- **Access control**: Customers can only see their own data
- **Audit logging**: Complete tracking of all operations
- **Admin controls**: Activate/deactivate accounts as needed

## Database Models

### Core Models

- **Customer**: Customer/client information from accounting systems
- **Vendor**: Vendor/supplier information from accounting systems
- **Receivable**: Sales invoices (accounts receivable)
- **ReceivableLine**: Line items for sales invoices
- **Payable**: Purchase invoices (accounts payable)
- **PayableLine**: Line items for purchase invoices
- **SyncLog**: Audit log of sync operations

### Key Features

- **source_system**: Tracks which ERP system the record came from
- **external_id**: Stores the original ID from the source system
- **raw_data**: JSON field storing the complete original data for reference
- **Unique constraints**: Prevents duplicate records (source_system + external_id)

## Django Admin

Access the Django admin interface to view and manage synced data:

1. Start the development server:
```bash
python manage.py runserver
```

2. Navigate to `http://localhost:8000/admin`

3. Log in with your superuser credentials

You can view:
- All receivables and payables
- Customer and vendor information
- Invoice line items
- Sync logs and statistics

## API Integration Notes

### Netvisor
- Uses XML-based API with custom MAC authentication
- Requires multiple authentication keys
- Date format: YYYY-MM-DD

### Fennoa
- REST API with Bearer token authentication
- Paginated responses (100 items per page)
- Date format: YYYY-MM-DD

### Procountor
- REST API with OAuth 2.0 or API key authentication
- Paginated responses (100 items per page)
- 0-indexed pagination
- Date format: YYYY-MM-DD

### Shopify
- REST Admin API with access token authentication
- Paginated responses (max 250 items per page)
- Cursor-based pagination with Link headers
- Date format: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
- Orders are synced as receivables

### Etsy
- REST API v3 with OAuth 2.0
- Paginated responses (max 100 items per page)
- Offset-based pagination
- Timestamps are Unix epoch seconds
- Receipts (orders) are synced as receivables
- Transactions within receipts become line items

### eBay
- REST API (Sell Fulfillment API) with OAuth 2.0
- Paginated responses (max 200 items per page)
- Offset-based pagination
- Date format: ISO 8601 (YYYY-MM-DDTHH:MM:SS.SSSZ)
- Uses refresh tokens for long-lived authentication
- Orders are synced as receivables
- Supports both production and sandbox environments

## Development

### Running Tests

```bash
python manage.py test accounting_sync
```

### Making Migrations

After modifying models:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Troubleshooting

### Authentication Errors

- Verify all API credentials are correctly set in environment variables
- Check that API keys have not expired
- Ensure proper permissions are granted in the accounting system

### Sync Failures

- Check the `SyncLog` model in Django admin for detailed error messages
- Verify date ranges are valid
- Check network connectivity to API endpoints
- Review API rate limits for your accounting system

### Data Issues

- The `raw_data` field on each model contains the original API response
- Use Django admin to inspect synced records
- Check for timezone-related issues if dates seem incorrect

## License

[Your License Here]

## Support

For issues and questions:
- Check the SyncLog entries in Django admin
- Review API documentation for your accounting system
- Contact your accounting system support for API-related issues
