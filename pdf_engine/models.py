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

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import uuid

class SharedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to="shared/")
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expire_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expire_at
