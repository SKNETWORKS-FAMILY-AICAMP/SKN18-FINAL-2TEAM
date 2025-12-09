# notes/models.py
from django.db import models
from django.conf import settings

class Note(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)     # 실험 기록 본문
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_locked = models.BooleanField(default=False)  # 수정 불가 모드(전자서명 후)

    def __str__(self):
        return self.title


class NoteFile(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="note_files/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.note.title} - {self.file.name}"


class NoteImage(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="note_images/")
    annotation_data = models.JSONField(null=True, blank=True)  # Excalidraw/Canvas 데이터 저장
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.note.title}"


class NoteComment(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.note}"


class NoteShare(models.Model):
    PERMISSION_CHOICES = [
        ("read", "Read Only"),
        ("edit", "Edit Permission"),
    ]

    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    shared_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default="read")

    shared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("note", "shared_to")

    def __str__(self):
        return f"{self.note.title} → {self.shared_to.username} ({self.permission})"