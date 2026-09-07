import logging
from celery import shared_task
from .services import SubscriptionService

logger = logging.getLogger(__name__)


@shared_task(name="apps.subscriptions.tasks.check_expired_subscriptions_task")
def check_expired_subscriptions_task():
    """
    Celery background task to reconcile expired subscriptions.
    Transfers past-due subscriptions to EXPIRED status.
    """
    logger.info("Starting subscription expiration check task...")
    count = SubscriptionService.check_expired_subscriptions()
    logger.info(f"Subscription expiration task finished. Expired count: {count}")
    return count
