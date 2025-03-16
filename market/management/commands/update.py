from django.core.management.base import BaseCommand
from market.models import Pool, PoolParticipant, Wallet

class Command(BaseCommand):
    help = 'Updates user platforms based on email status (TM for no email, GC for with email)'

    def handle(self, *args, **options):
        # Update users without email to TM
        all_wallets = Wallet.objects.filter(valid_for_pool=True).update(valid_for_pool=False)
        all_pools = Pool.objects.all().update(deposits=0.00)
        all_pool_participants = PoolParticipant.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated database\n'
            )
        )
