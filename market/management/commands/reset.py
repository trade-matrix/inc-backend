from django.core.management.base import BaseCommand
from market.models import Wallet

class Command(BaseCommand):
    help = 'Resets all wallet balances, deposits, and game amounts to zero'

    def handle(self, *args, **options):
        updated = Wallet.objects.filter(user__platform="TM",user__verified=True).update(
            balance=0,
            deposit=20,
            amount_from_games=0
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully reset {updated} wallet(s) to zero')
        )
