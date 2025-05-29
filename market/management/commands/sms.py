from django.core.management.base import BaseCommand
from market.utils import send_sms
from accounts.models import Customer
from django.db.models import Q
from market.promo import message_decider

class Command(BaseCommand):
    help = 'Send SMS to users based on platform'

    def add_arguments(self, parser):
        parser.add_argument('--message', type=str, help='Message to send to users')
        parser.add_argument('--platform', type=str, choices=['TM', 'GC', 'ALL'], default='ALL', help='Platform to target')

    def handle(self, *args, **options):
        
        platform = options['platform']

        # Build the query based on platform
        if platform == 'TM':
            users = Customer.objects.filter(platform='TM')
        elif platform == 'GC':
            users = Customer.objects.filter(platform='GC')
        else:  # ALL
            users = Customer.objects.all()

        # Get all phone numbers
        phone_numbers = users.values_list('phone_number', flat=True)

        numers_list = list(phone_numbers)
        if not numers_list:
            self.stdout.write(self.style.WARNING('No users found for the specified platform.'))
            return
        
        # Send SMS
        success_count = 0
        fail_count = 0

        
        try:
            #customer = Customer.objects.get(phone_number=phone)
            message = message_decider(options['message'], "customer", 10)
            for phone in numers_list:
                send_sms(message, phone)
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f'Successfully sent SMS to {phone}'))

        except Exception as e:
            fail_count += 1
            self.stdout.write(self.style.ERROR(f'Failed to send SMS to {numers_list}: {str(e)}'))

        # Print summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSMS Campaign Summary:\n'
                f'Total messages sent: {success_count}\n'
                f'Failed messages: {fail_count}\n'
                f'Platform: {platform}'
            )
        )
