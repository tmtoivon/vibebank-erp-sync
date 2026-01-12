from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Customer, Vendor, Receivable, ReceivableLine,
    Payable, PayableLine, SyncLog
)
from .whatsapp_models import (
    WhatsAppCustomer, WhatsAppSession, WhatsAppMessage, WhatsAppAuditLog
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


# WhatsApp Integration Admin


@admin.register(WhatsAppCustomer)
class WhatsAppCustomerAdmin(admin.ModelAdmin):
    list_display = [
        'customer_name', 'whatsapp_number', 'is_verified', 'is_active',
        'linked_customers_count', 'last_interaction', 'verification_actions'
    ]
    list_filter = ['is_verified', 'is_active', 'language', 'created_at']
    search_fields = ['customer_name', 'customer_email', 'whatsapp_number']
    readonly_fields = ['created_at', 'updated_at', 'last_interaction']
    filter_horizontal = ['linked_customers']

    def linked_customers_count(self, obj):
        return obj.linked_customers.count()
    linked_customers_count.short_description = 'Linked Customers'

    def verification_actions(self, obj):
        if obj.is_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        else:
            url = reverse('admin:resend-verification-code', args=[obj.id])
            return format_html(
                '<a class="button" href="{}">Resend Code</a>',
                url
            )
    verification_actions.short_description = 'Actions'

    actions = ['send_verification_code', 'deactivate_accounts', 'activate_accounts']

    def send_verification_code(self, request, queryset):
        from accounting_sync.utils.whatsapp_client import WhatsAppClient
        client = WhatsAppClient()
        count = 0

        for customer in queryset.filter(is_verified=False):
            code = customer.generate_verification_code()
            if client.send_verification_code(customer.whatsapp_number, code):
                count += 1

        self.message_user(request, f'Verification codes sent to {count} customers')
    send_verification_code.short_description = 'Send verification code to selected'

    def deactivate_accounts(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} accounts deactivated')
    deactivate_accounts.short_description = 'Deactivate selected accounts'

    def activate_accounts(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} accounts activated')
    activate_accounts.short_description = 'Activate selected accounts'


@admin.register(WhatsAppSession)
class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id', 'whatsapp_customer', 'message_count',
        'started_at', 'last_message_at', 'is_active', 'duration'
    ]
    list_filter = ['is_active', 'started_at']
    search_fields = ['session_id', 'whatsapp_customer__customer_name']
    readonly_fields = ['session_id', 'started_at', 'last_message_at', 'ended_at']

    def duration(self, obj):
        if obj.ended_at:
            delta = obj.ended_at - obj.started_at
        else:
            from django.utils import timezone
            delta = timezone.now() - obj.started_at

        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} min"
    duration.short_description = 'Duration'


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'whatsapp_customer', 'direction', 'content_preview',
        'llm_model', 'llm_tokens_used'
    ]
    list_filter = ['direction', 'llm_model', 'timestamp']
    search_fields = ['whatsapp_customer__customer_name', 'content', 'message_sid']
    readonly_fields = [
        'timestamp', 'whatsapp_customer', 'session', 'direction',
        'message_sid', 'content', 'llm_response_time', 'llm_tokens_used',
        'llm_model', 'query_results'
    ]
    date_hierarchy = 'timestamp'

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Message'

    def has_add_permission(self, request):
        return False


@admin.register(WhatsAppAuditLog)
class WhatsAppAuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'whatsapp_customer', 'action', 'description']
    list_filter = ['action', 'timestamp']
    search_fields = ['whatsapp_customer__customer_name', 'action', 'description']
    readonly_fields = [
        'timestamp', 'whatsapp_customer', 'action', 'description',
        'ip_address', 'user_agent', 'metadata'
    ]
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False
