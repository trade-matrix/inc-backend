from django.core.management.base import BaseCommand
from django.db.models import Sum
from market.models import Wallet

class Command(BaseCommand):
    help = 'Calculate filtered wallet balance sum'

    def handle(self, *args, **options):
        # Get filtered balance sum (e.g., verified users on platform 'TM')
        filtered_balance = Wallet.objects.filter(
            user__verified=True, 
            user__platform='TM'
        ).aggregate(Sum('balance'))['balance__sum'] or 0

        # Output the result
        self.stdout.write(
            self.style.SUCCESS(f'Filtered balance sum = {filtered_balance}')
        )