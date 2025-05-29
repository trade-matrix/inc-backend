from django.core.management.base import BaseCommand
from accounts.models import Customer
from market.models import Wallet

class Command(BaseCommand):
    help = 'Reset recepient code for all user accounts'

    def handle(self, *args, **options):
        # Get user accounts
        users = Customer.objects.all()
        
        # Reset game_track to 0 for all wallets efficiently
        updated_count = Wallet.objects.all().update(game_track=0)
        
        self.stdout.write(self.style.SUCCESS(f'{users.count()} user accounts have been reset successfully.'))
        self.stdout.write(self.style.SUCCESS(f'{updated_count} wallets have been reset successfully.'))
        self.stdout.write(self.style.SUCCESS('All user accounts have been reset successfully.'))
