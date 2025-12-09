# attachments/models.py
from django.db import models
from django.conf import settings
from notes.models import Note

class Attachment(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    file = models.FileField(upload_to="attachments/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.file.name