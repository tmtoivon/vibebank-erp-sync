from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from accounting_sync.models import (
    Customer, Vendor, Receivable, ReceivableLine,
    Payable, PayableLine, SyncLog, ERPSystem, InvoiceStatus
)
from accounting_sync.utils.procountor_client import ProcountorClient


class Command(BaseCommand):
    help = 'Sync receivables and payables from Procountor'

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
        client = ProcountorClient()

        start_date = options.get('start_date')
        end_date = options.get('end_date')

        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        self.stdout.write(f"Starting Procountor sync from {start_date} to {end_date}")

        receivables_only = options.get('receivables_only', False)
        payables_only = options.get('payables_only', False)

        if not payables_only:
            self._sync_receivables(client, start_date, end_date)

        if not receivables_only:
            self._sync_payables(client, start_date, end_date)

        self.stdout.write(self.style.SUCCESS('Procountor sync completed'))

    def _sync_receivables(self, client: ProcountorClient, start_date: str, end_date: str):
        """Sync sales invoices (receivables) from Procountor."""
        sync_log = SyncLog.objects.create(
            source_system=ERPSystem.PROCOUNTOR,
            sync_type='receivables',
            started_at=timezone.now(),
            status='running'
        )

        try:
            self.stdout.write("Fetching sales invoices from Procountor...")

            all_invoices = []
            page = 0
            size = 100

            while True:
                invoices = client.get_sales_invoices(start_date, end_date, page, size)
                if not invoices:
                    break

                all_invoices.extend(invoices)

                if len(invoices) < size:
                    break

                page += 1

            self.stdout.write(f"Found {len(all_invoices)} sales invoices")

            created_count = 0
            updated_count = 0
            failed_count = 0

            for invoice_data in all_invoices:
                try:
                    with transaction.atomic():
                        created = self._process_receivable(invoice_data, client)
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to process invoice {invoice_data.get('invoiceNumber', invoice_data.get('id'))}: {str(e)}"
                        )
                    )

            sync_log.records_processed = len(all_invoices)
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

    def _process_receivable(self, invoice_data: dict, client: ProcountorClient) -> bool:
        """Process a single receivable (sales invoice). Returns True if created, False if updated."""
        external_id = str(invoice_data.get('id', ''))
        if not external_id:
            return False

        invoice_number = invoice_data.get('invoiceNumber', invoice_data.get('number', ''))

        invoice_date_str = invoice_data.get('invoiceDate', invoice_data.get('date', ''))
        due_date_str = invoice_data.get('dueDate', invoice_data.get('paymentDueDate', ''))

        invoice_date = date_parser.parse(invoice_date_str).date() if invoice_date_str else timezone.now().date()
        due_date = date_parser.parse(due_date_str).date() if due_date_str else invoice_date

        amount_gross = Decimal(str(invoice_data.get('total', invoice_data.get('totalIncludingTax', 0))))
        amount_net = Decimal(str(invoice_data.get('totalExcludingTax', invoice_data.get('netAmount', 0))))
        amount_tax = amount_gross - amount_net

        amount_paid = Decimal(str(invoice_data.get('paid', invoice_data.get('paidAmount', 0))))
        amount_outstanding = amount_gross - amount_paid

        status_str = invoice_data.get('status', '').lower()
        status_map = {
            'draft': InvoiceStatus.DRAFT,
            'sent': InvoiceStatus.SENT,
            'delivered': InvoiceStatus.SENT,
            'paid': InvoiceStatus.PAID,
            'partially_paid': InvoiceStatus.PARTIAL,
            'overdue': InvoiceStatus.OVERDUE,
            'cancelled': InvoiceStatus.CANCELLED,
            'deleted': InvoiceStatus.CANCELLED,
        }
        status = status_map.get(status_str, InvoiceStatus.UNKNOWN)

        customer = None
        customer_data = invoice_data.get('customer', invoice_data.get('partner', {}))
        if customer_data:
            customer_id = str(customer_data.get('id', ''))
            customer_name = customer_data.get('name', customer_data.get('customerName', ''))

            if customer_id and customer_name:
                customer, _ = Customer.objects.update_or_create(
                    source_system=ERPSystem.PROCOUNTOR,
                    external_id=customer_id,
                    defaults={
                        'name': customer_name,
                        'email': customer_data.get('email', ''),
                        'business_id': customer_data.get('businessId', customer_data.get('identifier', '')),
                        'address_line1': customer_data.get('streetAddress', ''),
                        'city': customer_data.get('city', ''),
                        'postal_code': customer_data.get('postCode', ''),
                        'country': customer_data.get('country', ''),
                        'raw_data': customer_data,
                    }
                )

        receivable, created = Receivable.objects.update_or_create(
            source_system=ERPSystem.PROCOUNTOR,
            external_id=external_id,
            defaults={
                'customer': customer,
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'due_date': due_date,
                'status': status,
                'currency': invoice_data.get('currency', 'EUR'),
                'amount_net': amount_net,
                'amount_tax': amount_tax,
                'amount_gross': amount_gross,
                'amount_paid': amount_paid,
                'amount_outstanding': amount_outstanding,
                'reference_number': invoice_data.get('referenceNumber', ''),
                'raw_data': invoice_data,
            }
        )

        self._process_receivable_lines(receivable, invoice_data.get('invoiceRows', invoice_data.get('lines', [])))

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} receivable: {invoice_number}")

        return created

    def _process_receivable_lines(self, receivable: Receivable, lines_data: list):
        """Process line items for a receivable."""
        receivable.lines.all().delete()

        for idx, line_data in enumerate(lines_data):
            quantity = Decimal(str(line_data.get('quantity', line_data.get('amount', 1))))
            unit_price = Decimal(str(line_data.get('unitPrice', line_data.get('price', 0))))
            tax_percent = Decimal(str(line_data.get('vatPercent', line_data.get('taxPercent', 0))))
            discount_percent = Decimal(str(line_data.get('discountPercent', 0)))

            amount_net = Decimal(str(line_data.get('sum', quantity * unit_price)))
            amount_tax = amount_net * tax_percent / Decimal('100')
            amount_gross = amount_net + amount_tax

            ReceivableLine.objects.create(
                receivable=receivable,
                line_number=idx + 1,
                product_code=line_data.get('product', line_data.get('productCode', '')),
                description=line_data.get('name', line_data.get('description', '')),
                quantity=quantity,
                unit=line_data.get('unit', ''),
                unit_price=unit_price,
                discount_percent=discount_percent,
                amount_net=amount_net,
                tax_percent=tax_percent,
                amount_tax=amount_tax,
                amount_gross=amount_gross,
                account_code=line_data.get('accountNumber', ''),
                raw_data=line_data,
            )

    def _sync_payables(self, client: ProcountorClient, start_date: str, end_date: str):
        """Sync purchase invoices (payables) from Procountor."""
        sync_log = SyncLog.objects.create(
            source_system=ERPSystem.PROCOUNTOR,
            sync_type='payables',
            started_at=timezone.now(),
            status='running'
        )

        try:
            self.stdout.write("Fetching purchase invoices from Procountor...")

            all_invoices = []
            page = 0
            size = 100

            while True:
                invoices = client.get_purchase_invoices(start_date, end_date, page, size)
                if not invoices:
                    break

                all_invoices.extend(invoices)

                if len(invoices) < size:
                    break

                page += 1

            self.stdout.write(f"Found {len(all_invoices)} purchase invoices")

            created_count = 0
            updated_count = 0
            failed_count = 0

            for invoice_data in all_invoices:
                try:
                    with transaction.atomic():
                        created = self._process_payable(invoice_data, client)
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to process invoice {invoice_data.get('invoiceNumber', invoice_data.get('id'))}: {str(e)}"
                        )
                    )

            sync_log.records_processed = len(all_invoices)
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

    def _process_payable(self, invoice_data: dict, client: ProcountorClient) -> bool:
        """Process a single payable (purchase invoice). Returns True if created, False if updated."""
        external_id = str(invoice_data.get('id', ''))
        if not external_id:
            return False

        invoice_number = invoice_data.get('invoiceNumber', invoice_data.get('number', ''))

        invoice_date_str = invoice_data.get('invoiceDate', invoice_data.get('date', ''))
        due_date_str = invoice_data.get('dueDate', invoice_data.get('paymentDueDate', ''))

        invoice_date = date_parser.parse(invoice_date_str).date() if invoice_date_str else timezone.now().date()
        due_date = date_parser.parse(due_date_str).date() if due_date_str else invoice_date

        amount_gross = Decimal(str(invoice_data.get('total', invoice_data.get('totalIncludingTax', 0))))
        amount_net = Decimal(str(invoice_data.get('totalExcludingTax', invoice_data.get('netAmount', 0))))
        amount_tax = amount_gross - amount_net

        amount_paid = Decimal(str(invoice_data.get('paid', invoice_data.get('paidAmount', 0))))
        amount_outstanding = amount_gross - amount_paid

        status_str = invoice_data.get('status', '').lower()
        status_map = {
            'unfinished': InvoiceStatus.DRAFT,
            'received': InvoiceStatus.SENT,
            'approved': InvoiceStatus.SENT,
            'paid': InvoiceStatus.PAID,
            'partly_paid': InvoiceStatus.PARTIAL,
            'overdue': InvoiceStatus.OVERDUE,
            'cancelled': InvoiceStatus.CANCELLED,
        }
        status = status_map.get(status_str, InvoiceStatus.UNKNOWN)

        vendor = None
        vendor_data = invoice_data.get('vendor', invoice_data.get('partner', {}))
        if vendor_data:
            vendor_id = str(vendor_data.get('id', ''))
            vendor_name = vendor_data.get('name', vendor_data.get('partnerName', ''))

            if vendor_id and vendor_name:
                vendor, _ = Vendor.objects.update_or_create(
                    source_system=ERPSystem.PROCOUNTOR,
                    external_id=vendor_id,
                    defaults={
                        'name': vendor_name,
                        'email': vendor_data.get('email', ''),
                        'business_id': vendor_data.get('businessId', vendor_data.get('identifier', '')),
                        'address_line1': vendor_data.get('streetAddress', ''),
                        'city': vendor_data.get('city', ''),
                        'postal_code': vendor_data.get('postCode', ''),
                        'country': vendor_data.get('country', ''),
                        'raw_data': vendor_data,
                    }
                )

        payable, created = Payable.objects.update_or_create(
            source_system=ERPSystem.PROCOUNTOR,
            external_id=external_id,
            defaults={
                'vendor': vendor,
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'due_date': due_date,
                'status': status,
                'currency': invoice_data.get('currency', 'EUR'),
                'amount_net': amount_net,
                'amount_tax': amount_tax,
                'amount_gross': amount_gross,
                'amount_paid': amount_paid,
                'amount_outstanding': amount_outstanding,
                'reference_number': invoice_data.get('referenceNumber', ''),
                'raw_data': invoice_data,
            }
        )

        self._process_payable_lines(payable, invoice_data.get('invoiceRows', invoice_data.get('lines', [])))

        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} payable: {invoice_number}")

        return created

    def _process_payable_lines(self, payable: Payable, lines_data: list):
        """Process line items for a payable."""
        payable.lines.all().delete()

        for idx, line_data in enumerate(lines_data):
            quantity = Decimal(str(line_data.get('quantity', line_data.get('amount', 1))))
            unit_price = Decimal(str(line_data.get('unitPrice', line_data.get('price', 0))))
            tax_percent = Decimal(str(line_data.get('vatPercent', line_data.get('taxPercent', 0))))
            discount_percent = Decimal(str(line_data.get('discountPercent', 0)))

            amount_net = Decimal(str(line_data.get('sum', quantity * unit_price)))
            amount_tax = amount_net * tax_percent / Decimal('100')
            amount_gross = amount_net + amount_tax

            PayableLine.objects.create(
                payable=payable,
                line_number=idx + 1,
                product_code=line_data.get('product', line_data.get('productCode', '')),
                description=line_data.get('name', line_data.get('description', '')),
                quantity=quantity,
                unit=line_data.get('unit', ''),
                unit_price=unit_price,
                discount_percent=discount_percent,
                amount_net=amount_net,
                tax_percent=tax_percent,
                amount_tax=amount_tax,
                amount_gross=amount_gross,
                account_code=line_data.get('accountNumber', ''),
                raw_data=line_data,
            )
