from django.db import models
from django.contrib.auth.models import User
from datetime import date

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20, default='FREE')
    daily_usage = models.IntegerField(default=0)
    last_reset = models.DateField(default=date.today)

    def reset_if_needed(self):
        if self.last_reset != date.today():
            self.daily_usage = 0
            self.last_reset = date.today()
            self.save()

    def can_use(self):
        self.reset_if_needed()
        if self.plan == 'FREE' and self.daily_usage >= 5:
            return False
        return True

    def increment(self):
        self.daily_usage += 1
        self.save()

    def __str__(self):
        return self.user.username
