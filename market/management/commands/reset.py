from django.core.management.base import BaseCommand
from market.models import Wallet

class Command(BaseCommand):
    help = 'Calculate sum of balances that are multiples of 10 and find user with highest such balance'

    def handle(self, *args, **options):
        # Filter wallets with balances that are multiples of 10
        wallets = Wallet.objects.filter(balance__gt=0, user__verified=True, user__platform='TM')
         
        # Filter for multiples of 10
        multiples_of_10 = [wallet for wallet in wallets if wallet.balance % 10 == 0]
        
        if not multiples_of_10:
            self.stdout.write(self.style.WARNING('No wallets found with balances that are multiples of 10'))
            return
        
        # Calculate sum of all balances that are multiples of 10
        total_balance = sum(wallet.balance for wallet in multiples_of_10)
        
        # Find user with highest balance among those with multiples of 10
        highest_wallet = max(multiples_of_10, key=lambda wallet: wallet.balance)
        
        # Output the results
        self.stdout.write(self.style.SUCCESS(f'Sum of all balances that are multiples of 10: GHS {total_balance:.2f}'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('User with highest balance (multiple of 10):'))
        self.stdout.write(self.style.SUCCESS(f'Username: {highest_wallet.user.username}'))
        self.stdout.write(self.style.SUCCESS(f'Balance: GHS {highest_wallet.balance:.2f}'))
        self.stdout.write(self.style.SUCCESS(f'Phone: {highest_wallet.user.phone_number}'))