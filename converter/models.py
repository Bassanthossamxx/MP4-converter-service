from django.db import models

class ConversionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"

class Mp4Cache(models.Model):
    original_url = models.URLField(unique=True)
    mp4_path = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ConversionStatus.choices,
        default=ConversionStatus.PENDING
    )
    job_id = models.CharField(max_length=100, unique=True)
    error_message = models.TextField(null=True, blank=True)  # Store error details
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.status} — {self.original_url}"
