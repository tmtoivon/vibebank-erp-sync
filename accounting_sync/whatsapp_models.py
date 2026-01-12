from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import secrets


class WhatsAppCustomer(models.Model):
    """Links a customer's WhatsApp number to their account."""

    whatsapp_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="WhatsApp number in E.164 format (e.g., +14155552671)"
    )

    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)

    # Link to Customer model if they exist in the system
    linked_customers = models.ManyToManyField(
        'accounting_sync.Customer',
        related_name='whatsapp_links',
        blank=True
    )

    # Authentication
    verification_code = models.CharField(max_length=6, blank=True)
    verification_code_expires = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    # Session management
    is_active = models.BooleanField(default=True)
    language = models.CharField(max_length=10, default='en')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_interaction = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['whatsapp_number']),
            models.Index(fields=['is_verified', 'is_active']),
        ]

    def __str__(self):
        return f"{self.customer_name} - {self.whatsapp_number}"

    def generate_verification_code(self):
        """Generate a 6-digit verification code."""
        self.verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        self.verification_code_expires = timezone.now() + timezone.timedelta(minutes=10)
        self.save()
        return self.verification_code

    def verify_code(self, code):
        """Verify the provided code."""
        if not self.verification_code_expires:
            return False

        if timezone.now() > self.verification_code_expires:
            return False

        if self.verification_code == code:
            self.is_verified = True
            self.verification_code = ''
            self.verification_code_expires = None
            self.save()
            return True

        return False


class WhatsAppSession(models.Model):
    """Track conversation sessions and context."""

    whatsapp_customer = models.ForeignKey(
        WhatsAppCustomer,
        on_delete=models.CASCADE,
        related_name='sessions'
    )

    session_id = models.CharField(max_length=100, unique=True, db_index=True)

    # Conversation context
    context = models.JSONField(default=dict, blank=True)
    message_count = models.IntegerField(default=0)

    started_at = models.DateTimeField(default=timezone.now)
    last_message_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['is_active', 'last_message_at']),
        ]

    def __str__(self):
        return f"Session {self.session_id} - {self.whatsapp_customer.customer_name}"

    def is_expired(self):
        """Check if session has expired (30 minutes of inactivity)."""
        if not self.is_active:
            return True

        timeout = timezone.timedelta(minutes=30)
        return timezone.now() - self.last_message_at > timeout

    def end_session(self):
        """End the session."""
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()


class WhatsAppMessage(models.Model):
    """Log all WhatsApp messages for auditing and debugging."""

    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ]

    whatsapp_customer = models.ForeignKey(
        WhatsAppCustomer,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    session = models.ForeignKey(
        WhatsAppSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )

    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)

    message_sid = models.CharField(max_length=100, blank=True, db_index=True)

    content = models.TextField()
    media_url = models.URLField(blank=True)

    # LLM metadata
    llm_response_time = models.FloatField(null=True, blank=True, help_text="Response time in seconds")
    llm_tokens_used = models.IntegerField(null=True, blank=True)
    llm_model = models.CharField(max_length=50, blank=True)

    # Query results
    query_results = models.JSONField(default=dict, blank=True)

    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['whatsapp_customer', 'timestamp']),
            models.Index(fields=['direction', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.direction} - {self.whatsapp_customer.customer_name} at {self.timestamp}"


class WhatsAppAuditLog(models.Model):
    """Audit log for WhatsApp operations."""

    whatsapp_customer = models.ForeignKey(
        WhatsAppCustomer,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True
    )

    action = models.CharField(max_length=100)
    description = models.TextField()

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['whatsapp_customer', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        customer_name = self.whatsapp_customer.customer_name if self.whatsapp_customer else "Unknown"
        return f"{self.action} - {customer_name} at {self.timestamp}"
