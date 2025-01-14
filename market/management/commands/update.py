from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import Customer
from market.models import Investment

class Command(BaseCommand):
    help = 'Updates user platforms based on email status (TM for no email, GC for with email)'

    def handle(self, *args, **options):
        # Update users without email to TM
        tm_users = Customer.objects.filter(username='amosasiam')
        #Put Gm Users in ivestment Tier 1
        investment = Investment.objects.get(title='Tier 1')
        for user in tm_users:
            investment.user.add(user)
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated platforms:\n'
                f'- {tm_users} users set to investment tier 1\n'
            )
        )
