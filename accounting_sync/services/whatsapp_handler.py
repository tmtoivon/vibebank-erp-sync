from django.utils import timezone
from django.db import transaction
import uuid
import time
import logging

from accounting_sync.whatsapp_models import (
    WhatsAppCustomer, WhatsAppSession, WhatsAppMessage, WhatsAppAuditLog
)
from accounting_sync.services.llm_service import FinancialDataQueryService
from accounting_sync.utils.whatsapp_client import WhatsAppClient

logger = logging.getLogger(__name__)


class WhatsAppMessageHandler:
    """Handle incoming WhatsApp messages and generate responses."""

    def __init__(self):
        self.whatsapp_client = WhatsAppClient()

    def handle_message(
        self,
        from_number: str,
        message_body: str,
        message_sid: str = ''
    ) -> dict:
        """
        Handle an incoming WhatsApp message.

        Args:
            from_number: Sender's WhatsApp number
            message_body: Message content
            message_sid: Twilio message SID

        Returns:
            dict with status and response
        """
        try:
            # Get or create WhatsApp customer
            whatsapp_customer = self._get_or_create_customer(from_number)

            # Log the incoming message
            self._log_message(
                whatsapp_customer=whatsapp_customer,
                direction='inbound',
                content=message_body,
                message_sid=message_sid
            )

            # Update last interaction
            whatsapp_customer.last_interaction = timezone.now()
            whatsapp_customer.save()

            # Check if this is a verification code
            if not whatsapp_customer.is_verified:
                return self._handle_verification(whatsapp_customer, message_body)

            # Check if account is active
            if not whatsapp_customer.is_active:
                self.whatsapp_client.send_error_message(from_number, 'no_access')
                return {'status': 'error', 'message': 'Account inactive'}

            # Get or create session
            session = self._get_or_create_session(whatsapp_customer)

            # Check if session expired
            if session.is_expired():
                session.end_session()
                session = self._get_or_create_session(whatsapp_customer)
                self.whatsapp_client.send_message(
                    from_number,
                    "👋 Welcome back! Starting a new session. How can I help you?"
                )

            # Process the message with LLM
            response = self._process_with_llm(
                whatsapp_customer=whatsapp_customer,
                session=session,
                message_body=message_body
            )

            # Send response
            self.whatsapp_client.send_formatted_response(
                to_number=from_number,
                response_text=response['response'],
                data=response.get('data')
            )

            # Log the outbound message
            self._log_message(
                whatsapp_customer=whatsapp_customer,
                direction='outbound',
                content=response['response'],
                session=session,
                llm_tokens_used=response.get('tokens_used'),
                llm_model=response.get('model'),
                query_results=response.get('data', {})
            )

            # Update session
            session.message_count += 1
            session.last_message_at = timezone.now()
            session.save()

            return {
                'status': 'success',
                'response': response['response']
            }

        except Exception as e:
            logger.error(f"Error handling WhatsApp message from {from_number}: {str(e)}")
            self.whatsapp_client.send_error_message(from_number, 'general')
            return {'status': 'error', 'message': str(e)}

    def _get_or_create_customer(self, from_number: str) -> WhatsAppCustomer:
        """Get or create a WhatsApp customer."""
        # Clean the number (remove whatsapp: prefix if present)
        clean_number = from_number.replace('whatsapp:', '')

        customer, created = WhatsAppCustomer.objects.get_or_create(
            whatsapp_number=clean_number,
            defaults={
                'customer_name': clean_number,
                'is_verified': False,
                'is_active': True
            }
        )

        if created:
            # Log the new customer
            WhatsAppAuditLog.objects.create(
                whatsapp_customer=customer,
                action='customer_created',
                description=f'New WhatsApp customer created: {clean_number}'
            )

            # Send welcome message for new users
            self.whatsapp_client.send_message(
                clean_number,
                """👋 *Welcome to VibeBankERP!*

To get started, you need to link your account.

Please contact our support team with your WhatsApp number to receive a verification code."""
            )

        return customer

    def _handle_verification(self, whatsapp_customer: WhatsAppCustomer, code: str) -> dict:
        """Handle verification code submission."""
        # Clean the code (remove spaces, dashes, etc.)
        clean_code = ''.join(filter(str.isdigit, code))

        if whatsapp_customer.verify_code(clean_code):
            # Verification successful
            WhatsAppAuditLog.objects.create(
                whatsapp_customer=whatsapp_customer,
                action='account_verified',
                description='Account successfully verified'
            )

            self.whatsapp_client.send_welcome_message(
                whatsapp_customer.whatsapp_number,
                whatsapp_customer.customer_name
            )

            return {
                'status': 'success',
                'message': 'Verification successful'
            }
        else:
            # Verification failed
            self.whatsapp_client.send_message(
                whatsapp_customer.whatsapp_number,
                """❌ *Invalid Verification Code*

The code you entered is incorrect or has expired.

Please request a new verification code from our support team."""
            )

            return {
                'status': 'error',
                'message': 'Invalid verification code'
            }

    def _get_or_create_session(self, whatsapp_customer: WhatsAppCustomer) -> WhatsAppSession:
        """Get active session or create a new one."""
        # Try to get active session
        active_session = whatsapp_customer.sessions.filter(
            is_active=True
        ).first()

        if active_session and not active_session.is_expired():
            return active_session

        # End old session if exists
        if active_session:
            active_session.end_session()

        # Create new session
        session = WhatsAppSession.objects.create(
            whatsapp_customer=whatsapp_customer,
            session_id=str(uuid.uuid4()),
            is_active=True
        )

        WhatsAppAuditLog.objects.create(
            whatsapp_customer=whatsapp_customer,
            action='session_started',
            description=f'New session started: {session.session_id}'
        )

        return session

    def _process_with_llm(
        self,
        whatsapp_customer: WhatsAppCustomer,
        session: WhatsAppSession,
        message_body: str
    ) -> dict:
        """Process message with LLM and return response."""
        start_time = time.time()

        try:
            # Initialize the LLM service
            llm_service = FinancialDataQueryService(whatsapp_customer)

            # Get conversation history from session context
            conversation_history = session.context.get('conversation_history', [])

            # Query the LLM
            result = llm_service.query(message_body, conversation_history)

            # Update conversation history
            conversation_history.append({
                'role': 'user',
                'content': message_body
            })
            conversation_history.append({
                'role': 'assistant',
                'content': result['response']
            })

            # Keep only last 10 messages to avoid token limits
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]

            session.context['conversation_history'] = conversation_history
            session.save()

            # Calculate response time
            response_time = time.time() - start_time
            result['response_time'] = response_time

            return result

        except Exception as e:
            logger.error(f"Error processing message with LLM: {str(e)}")
            return {
                'response': "I apologize, but I'm having trouble processing your request right now. Please try again later.",
                'data': {},
                'tokens_used': 0,
                'model': '',
                'response_time': time.time() - start_time
            }

    def _log_message(
        self,
        whatsapp_customer: WhatsAppCustomer,
        direction: str,
        content: str,
        message_sid: str = '',
        session: WhatsAppSession = None,
        llm_tokens_used: int = None,
        llm_model: str = '',
        query_results: dict = None
    ):
        """Log a WhatsApp message."""
        WhatsAppMessage.objects.create(
            whatsapp_customer=whatsapp_customer,
            session=session,
            direction=direction,
            message_sid=message_sid,
            content=content,
            llm_tokens_used=llm_tokens_used,
            llm_model=llm_model,
            query_results=query_results or {}
        )

    def link_customer_account(
        self,
        whatsapp_number: str,
        customer_name: str,
        customer_email: str,
        customer_ids: list
    ) -> dict:
        """
        Link a WhatsApp number to customer accounts.

        This should be called by admin/support to set up the link.

        Args:
            whatsapp_number: WhatsApp number in E.164 format
            customer_name: Customer's full name
            customer_email: Customer's email
            customer_ids: List of Customer IDs to link

        Returns:
            dict with status and verification code
        """
        try:
            with transaction.atomic():
                # Get or create WhatsApp customer
                whatsapp_customer, created = WhatsAppCustomer.objects.get_or_create(
                    whatsapp_number=whatsapp_number,
                    defaults={
                        'customer_name': customer_name,
                        'customer_email': customer_email,
                        'is_verified': False,
                        'is_active': True
                    }
                )

                if not created:
                    # Update existing customer
                    whatsapp_customer.customer_name = customer_name
                    whatsapp_customer.customer_email = customer_email
                    whatsapp_customer.is_active = True
                    whatsapp_customer.save()

                # Link customer accounts
                from accounting_sync.models import Customer
                customers = Customer.objects.filter(id__in=customer_ids)
                whatsapp_customer.linked_customers.set(customers)

                # Generate verification code
                verification_code = whatsapp_customer.generate_verification_code()

                # Send verification code
                self.whatsapp_client.send_verification_code(
                    whatsapp_number,
                    verification_code
                )

                # Log the action
                WhatsAppAuditLog.objects.create(
                    whatsapp_customer=whatsapp_customer,
                    action='account_linked',
                    description=f'Account linked with {len(customers)} customer(s)',
                    metadata={'customer_ids': customer_ids}
                )

                return {
                    'status': 'success',
                    'message': 'Verification code sent',
                    'verification_code': verification_code,
                    'whatsapp_customer_id': whatsapp_customer.id
                }

        except Exception as e:
            logger.error(f"Error linking customer account: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
