"""
URL configuration for vibebank_erp project.
"""
from django.contrib import admin
from django.urls import path, include
from accounting_sync.views import whatsapp_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # WhatsApp webhook endpoints
    path('whatsapp/webhook/', whatsapp_views.whatsapp_webhook, name='whatsapp-webhook'),
    path('whatsapp/webhook/verify/', whatsapp_views.whatsapp_webhook_verify, name='whatsapp-webhook-verify'),

    # WhatsApp admin endpoints
    path('admin/whatsapp/link-customer/', whatsapp_views.link_customer_form, name='whatsapp-link-customer'),
    path('admin/whatsapp/test-message/', whatsapp_views.test_whatsapp_message, name='whatsapp-test-message'),
    path('admin/whatsapp/resend-code/<int:whatsapp_customer_id>/', whatsapp_views.send_verification_code, name='admin:resend-verification-code'),
]
