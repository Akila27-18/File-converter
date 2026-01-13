from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class UserProfile(models.Model):
    PLAN_CHOICES = (
        ("free", "Free"),
        ("pro", "Pro"),
        ("business", "Business"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    daily_usage = models.IntegerField(default=0)
    last_reset = models.DateField(auto_now=True)

    def can_use(self):
        if self.plan == "free":
            return self.daily_usage < 5
        return True

    def share_days(self):
        if self.plan == "free":
            return 1
        if self.plan == "pro":
            return 7
        return 3650  # business = no expiry

    def increment(self):
        self.daily_usage += 1
        self.save()

    def __str__(self):
        return f"{self.user.username} ({self.plan})"
