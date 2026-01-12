from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from datetime import timedelta

def upload_to_shared(instance, filename):
    return f"shared/{instance.user.id}/{filename}"

def default_expire():
    # timezone-aware datetime
    return timezone.now() + timedelta(days=1)

# pdf_engine/models.py

from django.urls import reverse
from django.utils import timezone

class SharedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to=upload_to_shared)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expire_at = models.DateTimeField(default=timezone.now() + timedelta(days=1))

    def is_expired(self):
        return timezone.now() > self.expire_at

    def get_absolute_url(self):
        return reverse("share_file", args=[str(self.token)])

    def __str__(self):
        return f"{self.user.username} - {self.file.name}"
