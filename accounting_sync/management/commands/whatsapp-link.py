from django.core.management.base import BaseCommand
from accounting_sync.models import Customer
from accounting_sync.services.whatsapp_handler import WhatsAppMessageHandler


class Command(BaseCommand):
    help = 'Link a WhatsApp number to customer account(s)'

    def add_arguments(self, parser):
        parser.add_argument(
            'whatsapp_number',
            type=str,
            help='WhatsApp number in E.164 format (e.g., +14155552671)'
        )
        parser.add_argument(
            'customer_name',
            type=str,
            help='Customer full name'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='',
            help='Customer email address'
        )
        parser.add_argument(
            '--customer-ids',
            type=str,
            help='Comma-separated list of Customer IDs to link (e.g., 1,2,3)'
        )
        parser.add_argument(
            '--customer-external-id',
            type=str,
            help='Link by external_id instead of ID'
        )
        parser.add_argument(
            '--source-system',
            type=str,
            help='Filter customers by source system (netvisor, fennoa, procountor, shopify, etsy)'
        )

    def handle(self, *args, **options):
        whatsapp_number = options['whatsapp_number']
        customer_name = options['customer_name']
        customer_email = options.get('email', '')
        customer_ids_str = options.get('customer_ids')
        external_id = options.get('customer_external_id')
        source_system = options.get('source_system')

        # Find customers to link
        customer_ids = []

        if customer_ids_str:
            # Link by IDs
            customer_ids = [int(cid.strip()) for cid in customer_ids_str.split(',')]
            customers = Customer.objects.filter(id__in=customer_ids)

        elif external_id:
            # Link by external ID
            filters = {'external_id': external_id}
            if source_system:
                filters['source_system'] = source_system

            customers = Customer.objects.filter(**filters)
            customer_ids = list(customers.values_list('id', flat=True))

        else:
            # Try to find by customer name
            customers = Customer.objects.filter(name__icontains=customer_name)
            if source_system:
                customers = customers.filter(source_system=source_system)

            customer_ids = list(customers.values_list('id', flat=True))

        if not customer_ids:
            self.stdout.write(
                self.style.ERROR('No customers found. Please specify --customer-ids or check customer name.')
            )
            return

        self.stdout.write(f"Found {len(customer_ids)} customer(s) to link:")
        for customer in Customer.objects.filter(id__in=customer_ids):
            self.stdout.write(f"  - {customer.name} ({customer.source_system}, ID: {customer.id})")

        # Link the account
        handler = WhatsAppMessageHandler()
        result = handler.link_customer_account(
            whatsapp_number=whatsapp_number,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_ids=customer_ids
        )

        if result['status'] == 'success':
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Account linked successfully!\n"
                    f"WhatsApp number: {whatsapp_number}\n"
                    f"Verification code sent: {result['verification_code']}\n"
                    f"\nThe customer should reply with this code to complete verification."
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ Error: {result['message']}")
            )
