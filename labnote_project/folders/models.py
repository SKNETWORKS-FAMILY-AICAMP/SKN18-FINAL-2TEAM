# folders/models.py
from django.db import models
from django.conf import settings

class Folder(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Folder"
        verbose_name_plural = "Folders"

    def __str__(self):
        return self.name


class FolderNote(models.Model):
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE)
    note = models.ForeignKey("notes.Note", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("folder", "note")
        verbose_name = "Folder-Note Mapping"

    def __str__(self):
        return f"{self.folder} - {self.note}"