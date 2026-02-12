from django.db import transaction
from django.utils import timezone

from accounts.models import DailyUsage


class QuotaExceeded(Exception):
    pass


@transaction.atomic
def consume_full_analysis_quota(user, daily_limit: int):
    usage, _ = DailyUsage.objects.select_for_update().get_or_create(
        user=user, date=timezone.localdate()
    )
    if usage.full_analysis_count >= daily_limit:
        raise QuotaExceeded("Günlük full analysis limiti aşıldı.")
    usage.full_analysis_count += 1
    usage.save(update_fields=["full_analysis_count"])
    return usage.full_analysis_count


@transaction.atomic
def consume_qa_quota(user, daily_limit: int = 30):
    usage, _ = DailyUsage.objects.select_for_update().get_or_create(
        user=user, date=timezone.localdate()
    )
    if usage.qa_count >= daily_limit:
        raise QuotaExceeded("Günlük soru limiti aşıldı.")
    usage.qa_count += 1
    usage.save(update_fields=["qa_count"])
    return usage.qa_count
