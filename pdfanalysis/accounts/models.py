from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# Create your models here.
class User(AbstractUser):
    pass

class DailyUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    full_analysis_count = models.PositiveIntegerField(default=0)
    qa_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("user", "date")