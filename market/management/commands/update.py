from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import Customer

class Command(BaseCommand):
    help = 'Updates user platforms based on email status (TM for no email, GC for with email)'

    def handle(self, *args, **options):
        # Update users without email to TM
        tm_users = Customer.objects.filter(
            Q(email__isnull=True) | Q(email='')
        ).update(platform='TM')
        
        # Update users with email to GC
        gc_users = Customer.objects.exclude(
            Q(email__isnull=True) | Q(email='')
        ).update(platform='GC')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated platforms:\n'
                f'- {tm_users} users set to TM\n'
                f'- {gc_users} users set to GC'
            )
        )
