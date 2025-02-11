from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import Customer
from market.models import Transaction

class Command(BaseCommand):
    help = 'Updates user platforms based on email status (TM for no email, GC for with email)'

    def handle(self, *args, **options):
        # Update users without email to TM
        tm_users = Customer.objects.filter(verified=True, username__startswith='bernard_')
        #Put Gm Users in ivestment Tier 1
        for user in tm_users:
            customer = Customer.objects.get(username="Khalebb")
            transaction = Transaction.objects.create(
                    user=customer, 
                    amount=10.00, 
                    status='completed', 
                    type='referal', 
                    reffered=user.username, 
                    image='https://darkpass.s3.us-east-005.backblazeb2.com/investment/male.png'
                )
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated referals:\n'
            )
        )
