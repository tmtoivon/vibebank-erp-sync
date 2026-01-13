from django.db import models
from django.utils import timezone


class ERPSystem(models.TextChoices):
    NETVISOR = 'netvisor', 'Netvisor'
    FENNOA = 'fennoa', 'Fennoa'
    PROCOUNTOR = 'procountor', 'Procountor'
    SHOPIFY = 'shopify', 'Shopify'
    ETSY = 'etsy', 'Etsy'
    EBAY = 'ebay', 'eBay'


class InvoiceStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SENT = 'sent', 'Sent'
    PAID = 'paid', 'Paid'
    PARTIAL = 'partial', 'Partially Paid'
    OVERDUE = 'overdue', 'Overdue'
    CANCELLED = 'cancelled', 'Cancelled'
    UNKNOWN = 'unknown', 'Unknown'


class Customer(models.Model):
    """Customer/Client entity across all ERP systems."""

    source_system = models.CharField(
        max_length=20,
        choices=ERPSystem.choices,
        db_index=True
    )
    external_id = models.CharField(max_length=255, db_index=True)

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True)
    business_id = models.CharField(max_length=100, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, blank=True)

    raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['source_system', 'external_id']]
        indexes = [
            models.Index(fields=['source_system', 'external_id']),
            models.Index(fields=['business_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.source_system})"


class Vendor(models.Model):
    """Vendor/Supplier entity across all ERP systems."""

    source_system = models.CharField(
        max_length=20,
        choices=ERPSystem.choices,
        db_index=True
    )
    external_id = models.CharField(max_length=255, db_index=True)

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True)
    business_id = models.CharField(max_length=100, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, blank=True)

    raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['source_system', 'external_id']]
        indexes = [
            models.Index(fields=['source_system', 'external_id']),
            models.Index(fields=['business_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.source_system})"


class Receivable(models.Model):
    """Sales Invoice/Accounts Receivable across all ERP systems."""

    source_system = models.CharField(
        max_length=20,
        choices=ERPSystem.choices,
        db_index=True
    )
    external_id = models.CharField(max_length=255, db_index=True)

    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='receivables'
    )

    invoice_number = models.CharField(max_length=100, db_index=True)
    reference_number = models.CharField(max_length=100, blank=True)

    invoice_date = models.DateField()
    due_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.UNKNOWN
    )

    currency = models.CharField(max_length=3, default='EUR')

    amount_net = models.DecimalField(max_digits=15, decimal_places=2)
    amount_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_gross = models.DecimalField(max_digits=15, decimal_places=2)

    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_outstanding = models.DecimalField(max_digits=15, decimal_places=2)

    payment_terms_days = models.IntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)

    raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['source_system', 'external_id']]
        indexes = [
            models.Index(fields=['source_system', 'external_id']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
            models.Index(fields=['invoice_date']),
            models.Index(fields=['due_date']),
        ]
        ordering = ['-invoice_date']

    def __str__(self):
        return f"Receivable {self.invoice_number} - {self.customer} ({self.source_system})"


class ReceivableLine(models.Model):
    """Line items for receivables/sales invoices."""

    receivable = models.ForeignKey(
        Receivable,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    line_number = models.IntegerField(default=0)

    product_code = models.CharField(max_length=100, blank=True)
    description = models.TextField()

    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    unit = models.CharField(max_length=20, blank=True)

    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    amount_net = models.DecimalField(max_digits=15, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2)
    amount_tax = models.DecimalField(max_digits=15, decimal_places=2)
    amount_gross = models.DecimalField(max_digits=15, decimal_places=2)

    account_code = models.CharField(max_length=50, blank=True)

    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['line_number']

    def __str__(self):
        return f"Line {self.line_number}: {self.description[:50]}"


class Payable(models.Model):
    """Purchase Invoice/Accounts Payable across all ERP systems."""

    source_system = models.CharField(
        max_length=20,
        choices=ERPSystem.choices,
        db_index=True
    )
    external_id = models.CharField(max_length=255, db_index=True)

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payables'
    )

    invoice_number = models.CharField(max_length=100, db_index=True)
    reference_number = models.CharField(max_length=100, blank=True)

    invoice_date = models.DateField()
    due_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.UNKNOWN
    )

    currency = models.CharField(max_length=3, default='EUR')

    amount_net = models.DecimalField(max_digits=15, decimal_places=2)
    amount_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_gross = models.DecimalField(max_digits=15, decimal_places=2)

    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_outstanding = models.DecimalField(max_digits=15, decimal_places=2)

    payment_terms_days = models.IntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)

    raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['source_system', 'external_id']]
        indexes = [
            models.Index(fields=['source_system', 'external_id']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
            models.Index(fields=['invoice_date']),
            models.Index(fields=['due_date']),
        ]
        ordering = ['-invoice_date']

    def __str__(self):
        return f"Payable {self.invoice_number} - {self.vendor} ({self.source_system})"


class PayableLine(models.Model):
    """Line items for payables/purchase invoices."""

    payable = models.ForeignKey(
        Payable,
        on_delete=models.CASCADE,
        related_name='lines'
    )

    line_number = models.IntegerField(default=0)

    product_code = models.CharField(max_length=100, blank=True)
    description = models.TextField()

    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    unit = models.CharField(max_length=20, blank=True)

    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    amount_net = models.DecimalField(max_digits=15, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2)
    amount_tax = models.DecimalField(max_digits=15, decimal_places=2)
    amount_gross = models.DecimalField(max_digits=15, decimal_places=2)

    account_code = models.CharField(max_length=50, blank=True)

    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['line_number']

    def __str__(self):
        return f"Line {self.line_number}: {self.description[:50]}"


class SyncLog(models.Model):
    """Track sync operations for auditing and debugging."""

    source_system = models.CharField(
        max_length=20,
        choices=ERPSystem.choices,
        db_index=True
    )

    sync_type = models.CharField(max_length=50)

    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, default='running')

    records_processed = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)

    error_message = models.TextField(blank=True)

    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['source_system', 'sync_type']),
            models.Index(fields=['started_at']),
        ]

    def __str__(self):
        return f"{self.source_system} - {self.sync_type} at {self.started_at}"
