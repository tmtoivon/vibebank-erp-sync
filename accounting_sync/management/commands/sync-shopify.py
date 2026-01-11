from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from accounting_sync.models import (
    Customer, Receivable, ReceivableLine,
    SyncLog, ERPSystem, InvoiceStatus
)
from accounting_sync.utils.shopify_client import ShopifyClient


class Command(BaseCommand):
    help = 'Sync sales data (orders) from Shopify'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for sync (YYYY-MM-DD). Defaults to 30 days ago.'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for sync (YYYY-MM-DD). Defaults to today.'
        )
        parser.add_argument(
            '--status',
            type=str,
            default='any',
            choices=['open', 'closed', 'cancelled', 'any'],
            help='Filter orders by status (default: any)'
        )

    def handle(self, *args, **options):
        client = ShopifyClient()

        start_date = options.get('start_date')
        end_date = options.get('end_date')
        status = options.get('status', 'any')

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        created_at_min = f"{start_date}T00:00:00Z"
        created_at_max = f"{end_date}T23:59:59Z"

        self.stdout.write(f"Starting Shopify sync from {start_date} to {end_date}")

        self._sync_orders(client, created_at_min, created_at_max, status)

        self.stdout.write(self.style.SUCCESS('Shopify sync completed'))

    def _sync_orders(
        self,
        client: ShopifyClient,
        created_at_min: str,
        created_at_max: str,
        status: str
    ):
        """Sync orders from Shopify as receivables."""
        sync_log = SyncLog.objects.create(
            source_system=ERPSystem.SHOPIFY,
            sync_type='orders',
            started_at=timezone.now(),
            status='running'
        )

        try:
            self.stdout.write("Fetching orders from Shopify...")
            orders = client.get_orders(
                status=status,
                created_at_min=created_at_min,
                created_at_max=created_at_max
            )

            self.stdout.write(f"Found {len(orders)} orders")

            created_count = 0
            updated_count = 0
            failed_count = 0

            for order_data in orders:
                try:
                    with transaction.atomic():
                        created = self._process_order(order_data)
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to process order {order_data.get('order_number', order_data.get('id'))}: {str(e)}"
                        )
                    )

            sync_log.records_processed = len(orders)
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.records_failed = failed_count
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Orders sync completed: {created_count} created, {updated_count} updated, {failed_count} failed"
                )
            )

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.completed_at = timezone.now()
            sync_log.save()
            self.stdout.write(self.style.ERROR(f"Orders sync failed: {str(e)}"))
            raise

    def _process_order(self, order_data: dict) -> bool:
        """Process a single Shopify order as a receivable. Returns True if created, False if updated."""
        external_id = str(order_data.get('id', ''))
        if not external_id:
            return False

        order_number = str(order_data.get('order_number', order_data.get('name', '')))

        created_at_str = order_data.get('created_at', '')
        processed_at_str = order_data.get('processed_at', '')

        created_at = date_parser.parse(created_at_str).date() if created_at_str else timezone.now().date()
        invoice_date = date_parser.parse(processed_at_str).date() if processed_at_str else created_at

        amount_gross = Decimal(str(order_data.get('total_price', 0)))
        amount_tax = Decimal(str(order_data.get('total_tax', 0)))
        amount_net = amount_gross - amount_tax

        amount_outstanding = Decimal(str(order_data.get('total_outstanding', 0)))

        financial_status = order_data.get('financial_status', '').lower()
        status_map = {
            'pending': InvoiceStatus.SENT,
            'authorized': InvoiceStatus.SENT,
            'paid': InvoiceStatus.PAID,
            'partially_paid': InvoiceStatus.PARTIAL,
            'refunded': InvoiceStatus.CANCELLED,
            'voided': InvoiceStatus.CANCELLED,
            'partially_refunded': InvoiceStatus.PARTIAL,
        }
        status = status_map.get(financial_status, InvoiceStatus.UNKNOWN)

        customer = None
        customer_data = order_data.get('customer', {})
        if customer_data and customer_data.get('id'):
            customer_id = str(customer_data.get('id'))
            customer_email = customer_data.get('email', '')
            customer_first = customer_data.get('first_name', '')
            customer_last = customer_data.get('last_name', '')
            customer_name = f"{customer_first} {customer_last}".strip() or customer_email

            default_address = customer_data.get('default_address', {})

            customer, _ = Customer.objects.update_or_create(
                source_system=ERPSystem.SHOPIFY,
                external_id=customer_id,
                defaults={
                    'name': customer_name,
                    'email': customer_email,
                    'phone': customer_data.get('phone', default_address.get('phone', '')),
                    'address_line1': default_address.get('address1', ''),
                    'address_line2': default_address.get('address2', ''),
                    'city': default_address.get('city', ''),
                    'postal_code': default_address.get('zip', ''),
                    'country': default_address.get('country_code', ''),
                    'raw_data': customer_data,
                }
            )

        billing_address = order_data.get('billing_address', {})
        payment_terms = order_data.get('payment_terms', {})

        receivable, created = Receivable.objects.update_or_create(
            source_system=ERPSystem.SHOPIFY,
            external_id=external_id,
            defaults={
                'customer': customer,
                'invoice_number': order_number,
                'invoice_date': invoice_date,
                'due_date': invoice_date,
                'status': status,
                'currency': order_data.get('currency', 'USD'),
                'amount_net': amount_net,
                'amount_tax': amount_tax,
                'amount_gross': amount_gross,
                'amount_paid': amount_gross - amount_outstanding,
                'amount_outstanding': amount_outstanding,
                'reference_number': order_data.get('confirmation_number', ''),
                'notes': order_data.get('note', ''),
                'raw_data': order_data,
            }
        )

        self._process_order_lines(receivable, order_data.get('line_items', []))

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} order: {order_number}")

        return created

    def _process_order_lines(self, receivable: Receivable, lines_data: list):
        """Process line items for an order."""
        receivable.lines.all().delete()

        for idx, line_data in enumerate(lines_data):
            quantity = Decimal(str(line_data.get('quantity', 1)))
            unit_price = Decimal(str(line_data.get('price', 0)))

            total_discount = Decimal(str(line_data.get('total_discount', 0)))
            discount_percent = Decimal('0')
            if unit_price > 0 and quantity > 0:
                discount_percent = (total_discount / (unit_price * quantity)) * Decimal('100')

            amount_gross = Decimal(str(line_data.get('price', 0))) * quantity - total_discount

            tax_lines = line_data.get('tax_lines', [])
            amount_tax = sum(Decimal(str(tax.get('price', 0))) for tax in tax_lines)

            amount_net = amount_gross - amount_tax

            tax_percent = Decimal('0')
            if amount_net > 0:
                tax_percent = (amount_tax / amount_net) * Decimal('100')

            ReceivableLine.objects.create(
                receivable=receivable,
                line_number=idx + 1,
                product_code=line_data.get('sku', ''),
                description=line_data.get('title', line_data.get('name', '')),
                quantity=quantity,
                unit=line_data.get('fulfillment_service', ''),
                unit_price=unit_price,
                discount_percent=discount_percent,
                amount_net=amount_net,
                tax_percent=tax_percent,
                amount_tax=amount_tax,
                amount_gross=amount_gross,
                raw_data=line_data,
            )
