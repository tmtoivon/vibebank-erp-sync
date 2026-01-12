from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
import logging

from accounting_sync.services.whatsapp_handler import WhatsAppMessageHandler
from accounting_sync.whatsapp_models import WhatsAppCustomer
from accounting_sync.models import Customer

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def whatsapp_webhook(request):
    """
    Webhook endpoint for receiving WhatsApp messages from Twilio.

    Twilio will POST to this endpoint when a message is received.
    """
    try:
        # Get message data from Twilio
        from_number = request.POST.get('From', '')
        message_body = request.POST.get('Body', '')
        message_sid = request.POST.get('MessageSid', '')

        logger.info(f"Received WhatsApp message from {from_number}: {message_body[:50]}...")

        # Handle the message
        handler = WhatsAppMessageHandler()
        result = handler.handle_message(
            from_number=from_number,
            message_body=message_body,
            message_sid=message_sid
        )

        # Twilio expects empty 200 response (we already sent the reply via API)
        return HttpResponse(status=200)

    except Exception as e:
        logger.error(f"Error in WhatsApp webhook: {str(e)}")
        return HttpResponse(status=500)


@require_GET
def whatsapp_webhook_verify(request):
    """
    Verification endpoint for WhatsApp webhook.

    Used by some platforms to verify the webhook URL.
    """
    # Return 200 for GET requests (verification)
    return HttpResponse("WhatsApp webhook is active", status=200)


@staff_member_required
def link_customer_form(request):
    """
    Admin form to link a WhatsApp number to customer accounts.
    """
    if request.method == 'POST':
        whatsapp_number = request.POST.get('whatsapp_number', '')
        customer_name = request.POST.get('customer_name', '')
        customer_email = request.POST.get('customer_email', '')
        customer_ids = request.POST.getlist('customer_ids')

        if not whatsapp_number:
            messages.error(request, 'WhatsApp number is required')
        elif not customer_name:
            messages.error(request, 'Customer name is required')
        elif not customer_ids:
            messages.error(request, 'At least one customer must be selected')
        else:
            # Process the linking
            handler = WhatsAppMessageHandler()
            result = handler.link_customer_account(
                whatsapp_number=whatsapp_number,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_ids=[int(cid) for cid in customer_ids]
            )

            if result['status'] == 'success':
                messages.success(
                    request,
                    f"Account linked successfully! Verification code sent to {whatsapp_number}. "
                    f"Code: {result['verification_code']}"
                )
            else:
                messages.error(request, f"Error: {result['message']}")

    # Get all customers for the form
    customers = Customer.objects.all().order_by('name')

    context = {
        'customers': customers,
        'title': 'Link WhatsApp Account'
    }

    return render(request, 'admin/whatsapp_link_customer.html', context)


@staff_member_required
def send_verification_code(request, whatsapp_customer_id):
    """
    Resend verification code to a WhatsApp customer.
    """
    whatsapp_customer = get_object_or_404(WhatsAppCustomer, id=whatsapp_customer_id)

    if whatsapp_customer.is_verified:
        return JsonResponse({
            'status': 'error',
            'message': 'Customer is already verified'
        })

    # Generate new code
    code = whatsapp_customer.generate_verification_code()

    # Send via WhatsApp
    from accounting_sync.utils.whatsapp_client import WhatsAppClient
    client = WhatsAppClient()
    message_sid = client.send_verification_code(
        whatsapp_customer.whatsapp_number,
        code
    )

    if message_sid:
        return JsonResponse({
            'status': 'success',
            'message': f'Verification code sent: {code}',
            'code': code
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to send verification code'
        })


@staff_member_required
def test_whatsapp_message(request):
    """
    Test endpoint for sending a test WhatsApp message.
    """
    if request.method == 'POST':
        to_number = request.POST.get('to_number', '')
        message = request.POST.get('message', '')

        if not to_number or not message:
            return JsonResponse({
                'status': 'error',
                'message': 'Both to_number and message are required'
            })

        from accounting_sync.utils.whatsapp_client import WhatsAppClient
        client = WhatsAppClient()
        message_sid = client.send_message(to_number, message)

        if message_sid:
            return JsonResponse({
                'status': 'success',
                'message': f'Message sent successfully. SID: {message_sid}',
                'message_sid': message_sid
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send message'
            })

    return render(request, 'admin/whatsapp_test_message.html', {
        'title': 'Test WhatsApp Message'
    })
