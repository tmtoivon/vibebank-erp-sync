from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta

from accounting_sync.models import (
    Customer, Receivable, ReceivableLine,
    SyncLog, ERPSystem, InvoiceStatus
)
from accounting_sync.utils.etsy_client import EtsyClient


class Command(BaseCommand):
    help = 'Sync sales data (receipts) from Etsy'

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
            '--paid-only',
            action='store_true',
            help='Sync only paid orders'
        )
        parser.add_argument(
            '--shipped-only',
            action='store_true',
            help='Sync only shipped orders'
        )

    def handle(self, *args, **options):
        client = EtsyClient()

        start_date = options.get('start_date')
        end_date = options.get('end_date')

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        min_created = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
        max_created = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp()) + 86400

        paid_only = options.get('paid_only', False)
        shipped_only = options.get('shipped_only', False)

        self.stdout.write(f"Starting Etsy sync from {start_date} to {end_date}")

        self._sync_receipts(client, min_created, max_created, paid_only, shipped_only)

        self.stdout.write(self.style.SUCCESS('Etsy sync completed'))

    def _sync_receipts(
        self,
        client: EtsyClient,
        min_created: int,
        max_created: int,
        paid_only: bool,
        shipped_only: bool
    ):
        """Sync receipts (orders) from Etsy as receivables."""
        sync_log = SyncLog.objects.create(
            source_system=ERPSystem.ETSY,
            sync_type='receipts',
            started_at=timezone.now(),
            status='running'
        )

        try:
            self.stdout.write("Fetching receipts from Etsy...")

            kwargs = {}
            if paid_only:
                kwargs['was_paid'] = True
            if shipped_only:
                kwargs['was_shipped'] = True

            receipts = client.get_all_receipts(
                min_created=min_created,
                max_created=max_created,
                **kwargs
            )

            self.stdout.write(f"Found {len(receipts)} receipts")

            created_count = 0
            updated_count = 0
            failed_count = 0

            for receipt_data in receipts:
                try:
                    with transaction.atomic():
                        created = self._process_receipt(receipt_data, client)
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to process receipt {receipt_data.get('receipt_id')}: {str(e)}"
                        )
                    )

            sync_log.records_processed = len(receipts)
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.records_failed = failed_count
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Receipts sync completed: {created_count} created, {updated_count} updated, {failed_count} failed"
                )
            )

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.completed_at = timezone.now()
            sync_log.save()
            self.stdout.write(self.style.ERROR(f"Receipts sync failed: {str(e)}"))
            raise

    def _process_receipt(self, receipt_data: dict, client: EtsyClient) -> bool:
        """Process a single Etsy receipt as a receivable. Returns True if created, False if updated."""
        external_id = str(receipt_data.get('receipt_id', ''))
        if not external_id:
            return False

        receipt_id_num = int(external_id)

        created_timestamp = receipt_data.get('create_timestamp', 0)
        created_at = datetime.fromtimestamp(created_timestamp).date() if created_timestamp else timezone.now().date()

        amount_gross = Decimal(str(receipt_data.get('grandtotal', {}).get('amount', 0))) / Decimal('100')
        amount_discount = Decimal(str(receipt_data.get('discount_amt', {}).get('amount', 0))) / Decimal('100')
        amount_tax = Decimal(str(receipt_data.get('total_tax_cost', {}).get('amount', 0))) / Decimal('100')

        subtotal = Decimal(str(receipt_data.get('subtotal', {}).get('amount', 0))) / Decimal('100')
        amount_net = subtotal - amount_discount

        was_paid = receipt_data.get('was_paid', False)
        was_shipped = receipt_data.get('was_shipped', False)
        is_gift = receipt_data.get('is_gift', False)

        if was_paid:
            status = InvoiceStatus.PAID
        elif receipt_data.get('status') == 'canceled':
            status = InvoiceStatus.CANCELLED
        else:
            status = InvoiceStatus.SENT

        customer = None
        buyer_user_id = receipt_data.get('buyer_user_id')
        buyer_email = receipt_data.get('buyer_email', '')
        name = receipt_data.get('name', '')

        if buyer_user_id:
            customer, _ = Customer.objects.update_or_create(
                source_system=ERPSystem.ETSY,
                external_id=str(buyer_user_id),
                defaults={
                    'name': name if name else buyer_email,
                    'email': buyer_email,
                    'address_line1': receipt_data.get('first_line', ''),
                    'address_line2': receipt_data.get('second_line', ''),
                    'city': receipt_data.get('city', ''),
                    'postal_code': receipt_data.get('zip', ''),
                    'country': receipt_data.get('country_iso', ''),
                    'raw_data': {
                        'buyer_user_id': buyer_user_id,
                        'buyer_email': buyer_email,
                        'name': name,
                    },
                }
            )

        message_from_buyer = receipt_data.get('message_from_buyer', '')
        gift_message = receipt_data.get('gift_message', '')
        notes = f"{message_from_buyer}\n{gift_message}".strip() if message_from_buyer or gift_message else ''

        receivable, created = Receivable.objects.update_or_create(
            source_system=ERPSystem.ETSY,
            external_id=external_id,
            defaults={
                'customer': customer,
                'invoice_number': external_id,
                'invoice_date': created_at,
                'due_date': created_at,
                'status': status,
                'currency': receipt_data.get('grandtotal', {}).get('currency_code', 'USD'),
                'amount_net': amount_net,
                'amount_tax': amount_tax,
                'amount_gross': amount_gross,
                'amount_paid': amount_gross if was_paid else Decimal('0'),
                'amount_outstanding': Decimal('0') if was_paid else amount_gross,
                'notes': notes,
                'raw_data': receipt_data,
            }
        )

        try:
            transactions = client.get_shop_receipt_transactions(receipt_id_num)
            self._process_receipt_transactions(receivable, transactions)
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Could not fetch transactions for receipt {external_id}: {str(e)}")
            )

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} receipt: {external_id}")

        return created

    def _process_receipt_transactions(self, receivable: Receivable, transactions_data: list):
        """Process transaction line items for a receipt."""
        receivable.lines.all().delete()

        for idx, transaction_data in enumerate(transactions_data):
            quantity = Decimal(str(transaction_data.get('quantity', 1)))
            unit_price = Decimal(str(transaction_data.get('price', {}).get('amount', 0))) / Decimal('100')

            product_data = transaction_data.get('product_data', {})
            sku = product_data.get('sku', '') if product_data else ''

            amount_gross = unit_price * quantity

            variations = transaction_data.get('variations', [])
            variation_text = ', '.join([
                f"{v.get('formatted_name', '')}: {v.get('formatted_value', '')}"
                for v in variations if v.get('formatted_name')
            ])

            title = transaction_data.get('title', '')
            description = f"{title} {variation_text}".strip() if variation_text else title

            shipping_cost = Decimal(str(transaction_data.get('shipping_cost', {}).get('amount', 0))) / Decimal('100')

            amount_net = amount_gross
            tax_percent = Decimal('0')
            amount_tax = Decimal('0')

            ReceivableLine.objects.create(
                receivable=receivable,
                line_number=idx + 1,
                product_code=sku,
                description=description,
                quantity=quantity,
                unit='pcs',
                unit_price=unit_price,
                discount_percent=Decimal('0'),
                amount_net=amount_net,
                tax_percent=tax_percent,
                amount_tax=amount_tax,
                amount_gross=amount_gross,
                raw_data=transaction_data,
            )

        if receivable.lines.count() == 0 and receivable.amount_gross > 0:
            ReceivableLine.objects.create(
                receivable=receivable,
                line_number=1,
                product_code='',
                description='Etsy Order',
                quantity=Decimal('1'),
                unit='pcs',
                unit_price=receivable.amount_gross,
                discount_percent=Decimal('0'),
                amount_net=receivable.amount_net,
                tax_percent=Decimal('0'),
                amount_tax=receivable.amount_tax,
                amount_gross=receivable.amount_gross,
                raw_data={},
            )
