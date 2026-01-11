from django.contrib import admin
from .models import (
    Customer, Vendor, Receivable, ReceivableLine,
    Payable, PayableLine, SyncLog
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_system', 'external_id', 'business_id', 'last_synced_at']
    list_filter = ['source_system', 'country']
    search_fields = ['name', 'business_id', 'external_id', 'email']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at']


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_system', 'external_id', 'business_id', 'last_synced_at']
    list_filter = ['source_system', 'country']
    search_fields = ['name', 'business_id', 'external_id', 'email']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at']


class ReceivableLineInline(admin.TabularInline):
    model = ReceivableLine
    extra = 0
    readonly_fields = ['line_number', 'description', 'quantity', 'unit_price', 'amount_gross']


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'customer', 'invoice_date', 'due_date',
        'amount_gross', 'amount_outstanding', 'status', 'source_system'
    ]
    list_filter = ['source_system', 'status', 'invoice_date']
    search_fields = ['invoice_number', 'reference_number', 'customer__name']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at']
    inlines = [ReceivableLineInline]
    date_hierarchy = 'invoice_date'


class PayableLineInline(admin.TabularInline):
    model = PayableLine
    extra = 0
    readonly_fields = ['line_number', 'description', 'quantity', 'unit_price', 'amount_gross']


@admin.register(Payable)
class PayableAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'vendor', 'invoice_date', 'due_date',
        'amount_gross', 'amount_outstanding', 'status', 'source_system'
    ]
    list_filter = ['source_system', 'status', 'invoice_date']
    search_fields = ['invoice_number', 'reference_number', 'vendor__name']
    readonly_fields = ['created_at', 'updated_at', 'last_synced_at']
    inlines = [PayableLineInline]
    date_hierarchy = 'invoice_date'


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = [
        'source_system', 'sync_type', 'started_at', 'status',
        'records_processed', 'records_created', 'records_updated', 'records_failed'
    ]
    list_filter = ['source_system', 'sync_type', 'status']
    readonly_fields = [
        'started_at', 'completed_at', 'records_processed',
        'records_created', 'records_updated', 'records_failed'
    ]
    date_hierarchy = 'started_at'
