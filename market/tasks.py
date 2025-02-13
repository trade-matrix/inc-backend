from celery import shared_task
from .models import Pool
from .utils import distribute_pool_earnings
import logging

logger = logging.getLogger(__name__)

@shared_task
def distribute_pool_task():
    """
    Task to distribute earnings for all active pools
    """
    try:
        # Get all active pools (you might want to add a status field to Pool model)
        pools = Pool.objects.all()
        
        for pool in pools:
            distribute_pool_earnings(pool.id)
            logger.info(f"Successfully distributed earnings for pool {pool.id}")
            
    except Exception as e:
        logger.error(f"Error in distribute_pool_task: {str(e)}")
