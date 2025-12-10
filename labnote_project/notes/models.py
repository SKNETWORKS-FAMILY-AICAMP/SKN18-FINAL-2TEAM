# notes/models.py
from django.db import models
from django.conf import settings

class t_note(models.Model):

    # ERD의 note_sid를 직접 PK로 지정
    note_sid = models.AutoField(primary_key=True)

    # 외래키 (varchar user_id 와 매핑 → Django 기본 User PK가 int라면 int로 변경 필요)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="owner_id"
    )

    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)

    # visibility enum(private/shared/public)
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('shared', 'Shared'),
        ('public', 'Public'),
    ]
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='private'
    )

    # 즐겨찾기
    favorite = models.BooleanField(default=False)

    # 생성/수정/삭제 날짜
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # Soft delete

    class Meta:
        db_table = "t_note"  # 테이블명을 ERD와 동일하게
        verbose_name = "실험 노트"
        verbose_name_plural = "실험 노트 목록"

    def __str__(self):
        return self.title


class NoteFile(models.Model):
    note = models.ForeignKey(t_note, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="note_files/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.note.title} - {self.file.name}"


class NoteImage(models.Model):
    note = models.ForeignKey(t_note, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="note_images/")
    annotation_data = models.JSONField(null=True, blank=True)  # Excalidraw/Canvas 데이터 저장
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.note.title}"


class NoteComment(models.Model):
    # PK: note_comment_sid
    note_comment_sid = models.AutoField(primary_key=True)

    # FK: 노트 번호
    note = models.ForeignKey(
        't_note',
        on_delete=models.CASCADE,
        related_name='comments',
        db_column="note_sid"
    )

    # 댓글 내용
    content = models.TextField()

    # 상위 댓글 (스레드형 구조)
    parent_comment = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )

    # 생성일 / 수정일
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # 생성자
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    class Meta:
        db_table = "t_note_comment"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment {self.note_comment_sid} on Note {self.note_id}"


class NoteShare(models.Model):
    PERMISSION_CHOICES = [
        ("read", "Read Only"),
        ("edit", "Edit Permission"),
    ]

    note = models.ForeignKey(t_note, on_delete=models.CASCADE)
    shared_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default="read")

    shared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("note", "shared_to")

    def __str__(self):
        return f"{self.note.title} → {self.shared_to.username} ({self.permission})"