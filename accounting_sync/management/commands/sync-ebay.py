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
from accounting_sync.utils.ebay_client import EbayClient


class Command(BaseCommand):
    help = 'Sync sales data (orders) from eBay'

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

    def handle(self, *args, **options):
        client = EbayClient()

        start_date = options.get('start_date')
        end_date = options.get('end_date')

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Convert to ISO 8601 format for eBay API
        order_creation_date_from = f"{start_date}T00:00:00.000Z"
        order_creation_date_to = f"{end_date}T23:59:59.999Z"

        self.stdout.write(f"Starting eBay sync from {start_date} to {end_date}")

        self._sync_orders(client, order_creation_date_from, order_creation_date_to)

        self.stdout.write(self.style.SUCCESS('eBay sync completed'))

    def _sync_orders(
        self,
        client: EbayClient,
        order_creation_date_from: str,
        order_creation_date_to: str
    ):
        """Sync orders from eBay as receivables."""
        sync_log = SyncLog.objects.create(
            source_system=ERPSystem.EBAY,
            sync_type='orders',
            started_at=timezone.now(),
            status='running'
        )

        try:
            self.stdout.write("Fetching orders from eBay...")
            orders = client.get_all_orders(
                order_creation_date_from=order_creation_date_from,
                order_creation_date_to=order_creation_date_to
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
                            f"Failed to process order {order_data.get('orderId')}: {str(e)}"
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
        """Process a single eBay order as a receivable. Returns True if created, False if updated."""
        external_id = order_data.get('orderId', '')
        if not external_id:
            return False

        # Get order dates
        creation_date_str = order_data.get('creationDate', '')
        creation_date = date_parser.parse(creation_date_str).date() if creation_date_str else timezone.now().date()

        # Get pricing information
        pricing_summary = order_data.get('pricingSummary', {})

        # eBay provides prices in a structured format
        total = pricing_summary.get('total', {})
        amount_gross = Decimal(str(total.get('value', 0))) if total else Decimal('0')
        currency = total.get('currency', 'USD') if total else 'USD'

        # Get tax and subtotal
        price_subtotal = pricing_summary.get('priceSubtotal', {})
        amount_net = Decimal(str(price_subtotal.get('value', 0))) if price_subtotal else Decimal('0')

        tax = pricing_summary.get('tax', {})
        amount_tax = Decimal(str(tax.get('value', 0))) if tax else Decimal('0')

        # Delivery cost
        delivery_cost = pricing_summary.get('deliveryCost', {})
        shipping_cost = Decimal(str(delivery_cost.get('value', 0))) if delivery_cost else Decimal('0')

        # Get order status
        order_fulfillment_status = order_data.get('orderFulfillmentStatus', 'UNKNOWN')
        order_payment_status = order_data.get('orderPaymentStatus', 'UNKNOWN')

        # Map eBay statuses to our statuses
        if order_payment_status == 'PAID':
            status = InvoiceStatus.PAID
        elif order_payment_status == 'PENDING':
            status = InvoiceStatus.SENT
        elif order_payment_status == 'FAILED':
            status = InvoiceStatus.CANCELLED
        else:
            status = InvoiceStatus.UNKNOWN

        # Get buyer information
        buyer = order_data.get('buyer', {})
        customer = None

        if buyer:
            buyer_username = buyer.get('username', '')

            if buyer_username:
                # Use username as external ID
                customer_name = buyer_username

                # Get email if available (may be masked by eBay)
                buyer_email = buyer.get('buyerRegistrationAddress', {}).get('email', '')

                customer, _ = Customer.objects.update_or_create(
                    source_system=ERPSystem.EBAY,
                    external_id=buyer_username,
                    defaults={
                        'name': customer_name,
                        'email': buyer_email,
                        'raw_data': buyer,
                    }
                )

        # Calculate amounts paid/outstanding
        if status == InvoiceStatus.PAID:
            amount_paid = amount_gross
            amount_outstanding = Decimal('0')
        else:
            amount_paid = Decimal('0')
            amount_outstanding = amount_gross

        # Get fulfillment start instructions for shipping info
        fulfillment_instructions = order_data.get('fulfillmentStartInstructions', [{}])
        first_instruction = fulfillment_instructions[0] if fulfillment_instructions else {}
        shipping_step = first_instruction.get('shippingStep', {})
        ship_to = shipping_step.get('shipTo', {})
        full_name = ship_to.get('fullName', '')

        # Create or update receivable
        receivable, created = Receivable.objects.update_or_create(
            source_system=ERPSystem.EBAY,
            external_id=external_id,
            defaults={
                'customer': customer,
                'invoice_number': external_id,
                'invoice_date': creation_date,
                'due_date': creation_date,
                'status': status,
                'currency': currency,
                'amount_net': amount_net,
                'amount_tax': amount_tax,
                'amount_gross': amount_gross,
                'amount_paid': amount_paid,
                'amount_outstanding': amount_outstanding,
                'notes': f"Ship to: {full_name}" if full_name else '',
                'raw_data': order_data,
            }
        )

        # Process line items
        self._process_order_lines(receivable, order_data.get('lineItems', []))

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} order: {external_id}")

        return created

    def _process_order_lines(self, receivable: Receivable, lines_data: list):
        """Process line items for an order."""
        receivable.lines.all().delete()

        for idx, line_data in enumerate(lines_data):
            quantity = Decimal(str(line_data.get('quantity', 1)))

            # Get line item cost
            line_item_cost = line_data.get('lineItemCost', {})
            unit_price = Decimal(str(line_item_cost.get('value', 0))) if line_item_cost else Decimal('0')

            # Total includes discounts
            total = line_data.get('total', {})
            line_total = Decimal(str(total.get('value', 0))) if total else Decimal('0')

            # Calculate discount
            discount_amount = (unit_price * quantity) - line_total
            discount_percent = Decimal('0')
            if unit_price > 0 and quantity > 0:
                discount_percent = (discount_amount / (unit_price * quantity)) * Decimal('100')

            # Get taxes for this line
            taxes = line_data.get('taxes', [])
            amount_tax = sum(
                Decimal(str(tax.get('amount', {}).get('value', 0)))
                for tax in taxes
            )

            amount_gross = line_total
            amount_net = amount_gross - amount_tax

            # Calculate tax percent
            tax_percent = Decimal('0')
            if amount_net > 0:
                tax_percent = (amount_tax / amount_net) * Decimal('100')

            # Get product info
            title = line_data.get('title', '')
            sku = line_data.get('sku', '')
            line_item_id = line_data.get('lineItemId', '')

            # Get listing marketplace ID for reference
            listing_marketplace_id = line_data.get('listingMarketplaceId', '')

            ReceivableLine.objects.create(
                receivable=receivable,
                line_number=idx + 1,
                product_code=sku or line_item_id,
                description=title,
                quantity=quantity,
                unit='pcs',
                unit_price=unit_price / quantity if quantity > 0 else unit_price,
                discount_percent=discount_percent,
                amount_net=amount_net,
                tax_percent=tax_percent,
                amount_tax=amount_tax,
                amount_gross=amount_gross,
                account_code=listing_marketplace_id,
                raw_data=line_data,
            )
