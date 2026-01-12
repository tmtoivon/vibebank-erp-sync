from twilio.rest import Client
from django.conf import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Client for sending WhatsApp messages via Twilio."""

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER
        self.client = Client(self.account_sid, self.auth_token)

    def send_message(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Send a WhatsApp message.

        Args:
            to_number: Recipient WhatsApp number in E.164 format (e.g., +14155552671)
            message: Message text to send
            media_url: Optional URL to media file

        Returns:
            Message SID if successful, None if failed
        """
        try:
            # Ensure numbers have whatsapp: prefix
            from_number = f"whatsapp:{self.whatsapp_number}"
            to_whatsapp = f"whatsapp:{to_number}" if not to_number.startswith('whatsapp:') else to_number

            kwargs = {
                'body': message,
                'from_': from_number,
                'to': to_whatsapp
            }

            if media_url:
                kwargs['media_url'] = [media_url]

            message_obj = self.client.messages.create(**kwargs)

            logger.info(f"WhatsApp message sent to {to_number}, SID: {message_obj.sid}")
            return message_obj.sid

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message to {to_number}: {str(e)}")
            return None

    def send_verification_code(self, to_number: str, code: str) -> Optional[str]:
        """Send a verification code via WhatsApp."""
        message = f"""🔐 *VibeBankERP Verification*

Your verification code is: *{code}*

This code will expire in 10 minutes.

Reply with this code to link your WhatsApp account."""

        return self.send_message(to_number, message)

    def send_welcome_message(self, to_number: str, customer_name: str) -> Optional[str]:
        """Send a welcome message after successful verification."""
        message = f"""✅ *Welcome to VibeBankERP, {customer_name}!*

Your WhatsApp account has been successfully linked.

You can now ask me about:
• Your receivables (money owed to you)
• Your payables (bills you need to pay)
• Invoice details
• Payment status
• Financial summaries

Just send me a message like:
"Show my outstanding invoices"
"What's my total receivable?"
"When is invoice #123 due?"

How can I help you today?"""

        return self.send_message(to_number, message)

    def send_formatted_response(
        self,
        to_number: str,
        response_text: str,
        data: Optional[dict] = None
    ) -> Optional[str]:
        """
        Send a formatted response, optionally with structured data.

        Args:
            to_number: Recipient number
            response_text: Main response text from LLM
            data: Optional structured data to format

        Returns:
            Message SID if successful
        """
        # For now, just send the text response
        # In the future, could format data more nicely
        return self.send_message(to_number, response_text)

    def send_error_message(self, to_number: str, error_type: str = 'general') -> Optional[str]:
        """Send an error message."""
        error_messages = {
            'not_verified': """⚠️ *Account Not Verified*

Your WhatsApp account is not yet verified.

To get started, please contact our support team to link your account.""",

            'no_access': """⚠️ *Access Denied*

You don't have access to this information.

Please contact support if you believe this is an error.""",

            'general': """❌ *Error*

Sorry, something went wrong. Please try again or contact support if the problem persists.""",

            'session_expired': """⏰ *Session Expired*

Your session has expired due to inactivity.

Send any message to start a new session."""
        }

        message = error_messages.get(error_type, error_messages['general'])
        return self.send_message(to_number, message)
