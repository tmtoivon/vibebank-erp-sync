from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

from accounting_sync.models import (
    Customer, Vendor, Receivable, ReceivableLine,
    Payable, PayableLine, SyncLog, ERPSystem, InvoiceStatus
)
from accounting_sync.utils.netvisor_client import NetvisorClient


class Command(BaseCommand):
    help = 'Sync receivables and payables from Netvisor'

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
            '--receivables-only',
            action='store_true',
            help='Sync only receivables (sales invoices)'
        )
        parser.add_argument(
            '--payables-only',
            action='store_true',
            help='Sync only payables (purchase invoices)'
        )

    def handle(self, *args, **options):
        client = NetvisorClient()

        start_date = options.get('start_date')
        end_date = options.get('end_date')

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        self.stdout.write(f"Starting Netvisor sync from {start_date} to {end_date}")

        receivables_only = options.get('receivables_only', False)
        payables_only = options.get('payables_only', False)

        if not payables_only:
            self._sync_receivables(client, start_date, end_date)

        if not receivables_only:
            self._sync_payables(client, start_date, end_date)

        self.stdout.write(self.style.SUCCESS('Netvisor sync completed'))

    def _sync_receivables(self, client: NetvisorClient, start_date: str, end_date: str):
        """Sync sales invoices (receivables) from Netvisor."""
        sync_log = SyncLog.objects.create(
            source_system=ERPSystem.NETVISOR,
            sync_type='receivables',
            started_at=timezone.now(),
            status='running'
        )

        try:
            self.stdout.write("Fetching sales invoices from Netvisor...")
            invoices = client.get_sales_invoices(start_date, end_date)

            self.stdout.write(f"Found {len(invoices)} sales invoices")

            created_count = 0
            updated_count = 0
            failed_count = 0

            for invoice_data in invoices:
                try:
                    with transaction.atomic():
                        self._process_receivable(invoice_data, client)
                        created_count += 1

                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"Failed to process invoice {invoice_data.get('invoice_number')}: {str(e)}")
                    )

            sync_log.records_processed = len(invoices)
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.records_failed = failed_count
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Receivables sync completed: {created_count} created, {updated_count} updated, {failed_count} failed"
                )
            )

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.completed_at = timezone.now()
            sync_log.save()
            self.stdout.write(self.style.ERROR(f"Receivables sync failed: {str(e)}"))
            raise

    def _process_receivable(self, invoice_data: dict, client: NetvisorClient):
        """Process a single receivable (sales invoice)."""
        external_id = invoice_data.get('id')
        if not external_id:
            return

        invoice_number = invoice_data.get('invoice_number', '')
        invoice_date_str = invoice_data.get('invoice_date', '')
        due_date_str = invoice_data.get('due_date', '')
        amount_str = invoice_data.get('amount', '0')

        invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date() if invoice_date_str else timezone.now().date()
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else invoice_date

        amount = Decimal(amount_str.replace(',', '.')) if amount_str else Decimal('0')

        status_map = {
            'open': InvoiceStatus.SENT,
            'paid': InvoiceStatus.PAID,
            'overdue': InvoiceStatus.OVERDUE,
            'cancelled': InvoiceStatus.CANCELLED,
        }
        status = status_map.get(invoice_data.get('status', '').lower(), InvoiceStatus.UNKNOWN)

        customer = None
        customer_name = invoice_data.get('customer_name', '')
        if customer_name:
            customer, _ = Customer.objects.get_or_create(
                source_system=ERPSystem.NETVISOR,
                external_id=f"customer_{external_id}",
                defaults={'name': customer_name}
            )

        receivable, created = Receivable.objects.update_or_create(
            source_system=ERPSystem.NETVISOR,
            external_id=external_id,
            defaults={
                'customer': customer,
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'due_date': due_date,
                'status': status,
                'currency': 'EUR',
                'amount_net': amount,
                'amount_tax': Decimal('0'),
                'amount_gross': amount,
                'amount_paid': Decimal('0') if status != InvoiceStatus.PAID else amount,
                'amount_outstanding': Decimal('0') if status == InvoiceStatus.PAID else amount,
                'raw_data': invoice_data,
            }
        )

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} receivable: {invoice_number}")

    def _sync_payables(self, client: NetvisorClient, start_date: str, end_date: str):
        """Sync purchase invoices (payables) from Netvisor."""
        sync_log = SyncLog.objects.create(
            source_system=ERPSystem.NETVISOR,
            sync_type='payables',
            started_at=timezone.now(),
            status='running'
        )

        try:
            self.stdout.write("Fetching purchase invoices from Netvisor...")
            invoices = client.get_purchase_invoices(start_date, end_date)

            self.stdout.write(f"Found {len(invoices)} purchase invoices")

            created_count = 0
            updated_count = 0
            failed_count = 0

            for invoice_data in invoices:
                try:
                    with transaction.atomic():
                        self._process_payable(invoice_data, client)
                        created_count += 1

                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"Failed to process invoice {invoice_data.get('invoice_number')}: {str(e)}")
                    )

            sync_log.records_processed = len(invoices)
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.records_failed = failed_count
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Payables sync completed: {created_count} created, {updated_count} updated, {failed_count} failed"
                )
            )

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.completed_at = timezone.now()
            sync_log.save()
            self.stdout.write(self.style.ERROR(f"Payables sync failed: {str(e)}"))
            raise

    def _process_payable(self, invoice_data: dict, client: NetvisorClient):
        """Process a single payable (purchase invoice)."""
        external_id = invoice_data.get('id')
        if not external_id:
            return

        invoice_number = invoice_data.get('invoice_number', '')
        invoice_date_str = invoice_data.get('invoice_date', '')
        due_date_str = invoice_data.get('due_date', '')
        amount_str = invoice_data.get('amount', '0')

        invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date() if invoice_date_str else timezone.now().date()
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else invoice_date

        amount = Decimal(amount_str.replace(',', '.')) if amount_str else Decimal('0')

        status_map = {
            'open': InvoiceStatus.SENT,
            'paid': InvoiceStatus.PAID,
            'approved': InvoiceStatus.SENT,
        }
        status = status_map.get(invoice_data.get('status', '').lower(), InvoiceStatus.UNKNOWN)

        vendor = None
        vendor_name = invoice_data.get('vendor_name', '')
        if vendor_name:
            vendor, _ = Vendor.objects.get_or_create(
                source_system=ERPSystem.NETVISOR,
                external_id=f"vendor_{external_id}",
                defaults={'name': vendor_name}
            )

        payable, created = Payable.objects.update_or_create(
            source_system=ERPSystem.NETVISOR,
            external_id=external_id,
            defaults={
                'vendor': vendor,
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'due_date': due_date,
                'status': status,
                'currency': 'EUR',
                'amount_net': amount,
                'amount_tax': Decimal('0'),
                'amount_gross': amount,
                'amount_paid': Decimal('0') if status != InvoiceStatus.PAID else amount,
                'amount_outstanding': Decimal('0') if status == InvoiceStatus.PAID else amount,
                'raw_data': invoice_data,
            }
        )

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} payable: {invoice_number}")
