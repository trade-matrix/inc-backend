from django.core.management.base import BaseCommand
from accounts.models import Customer

class Command(BaseCommand):
    help = 'Reset recepient code for all user accounts'

    def handle(self, *args, **options):
        #Get user accounts
        users = Customer.objects.all().update(recepient_code=None)
        self.stdout.write(self.style.SUCCESS('All user accounts have been reset'))
