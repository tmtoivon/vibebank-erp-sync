# VibeBankERP Sync

A Django application for synchronizing receivables and payables from multiple accounting systems (Netvisor, Fennoa, and Procountor) and e-commerce platforms (Shopify and Etsy) into a unified database.

## Features

- **Multi-system support**: Sync data from Netvisor, Fennoa, Procountor, Shopify, and Etsy
- **Unified data model**: Generic database models that work across all accounting systems
- **Receivables & Payables**: Sync both sales invoices (receivables) and purchase invoices (payables)
- **Line items**: Full support for invoice line items with tax calculations
- **Customer & Vendor tracking**: Automatic syncing of customer and vendor information
- **Audit logging**: Complete sync history with success/failure tracking
- **Incremental sync**: Date-based filtering for efficient incremental updates

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
```

- **Django-cron** or **Celery** for more advanced scheduling
- **Task Scheduler** (Windows)

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
