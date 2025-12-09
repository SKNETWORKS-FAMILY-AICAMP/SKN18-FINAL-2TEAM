# bookmarks/models.py
from django.db import models
from django.conf import settings
from notes.models import Note

class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "note")

    def __str__(self):
        return f"{self.user} bookmarked {self.note}"