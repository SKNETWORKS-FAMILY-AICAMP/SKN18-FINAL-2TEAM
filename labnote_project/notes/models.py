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
        db_column="owner_id",
        to_field='user_id'
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


class t_note_tag(models.Model):
    # PK: note_tag_sid
    note_tag_sid = models.AutoField(primary_key=True)

    note = models.ForeignKey('t_note', on_delete=models.CASCADE, related_name='tags', db_column="note_sid")  # ForeignKey to t_note
    tag = models.CharField(max_length=255)  # Store tag name
    created_at = models.DateTimeField(auto_now_add=True)  # Automatically set the timestamp when created

    class Meta:
        db_table = "t_note_tag"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Tag {self.tag} for {self.note.title}"


class t_note_comment(models.Model):
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


class t_note_share(models.Model):
    PERMISSION_CHOICES = [
        ("view", "View"),
        ("comment", "Comment"),
        ("edit", "Edit"),
    ]
    # PK: note_share_sid
    note_share_sid = models.AutoField(primary_key=True)

    note = models.ForeignKey('t_note', on_delete=models.CASCADE, db_column="note_sid")
    sharer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column="sharer_id")
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default="view")
    shared_at = models.DateTimeField(auto_now_add=True, db_column="shared_at")
    expires_at = models.DateTimeField(null=True, blank=True, db_column="expires_at")

    class Meta:
        db_table = "t_note_share"
        unique_together = ("note", "sharer")

    def __str__(self):
        return f"{self.note.title} → {self.sharer.username} ({self.permission})"