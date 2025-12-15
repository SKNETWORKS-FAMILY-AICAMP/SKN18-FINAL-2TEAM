from django.db import models


class Note(models.Model):
    """
    노트 모델
    """
    
    # 상태 선택지
    STATUS_CHOICES = [
        ('E', '사용'),
        ('D', 'Disabled'),
        ('R', 'Removed'),
    ]
    
    note_sid = models.AutoField(primary_key=True, db_column='note_sid')
    owner = models.ForeignKey(
        'account.CustomUser',
        on_delete=models.CASCADE,
        db_column='owner_id'
    )
    title = models.CharField(max_length=500, db_column='title')
    content = models.TextField(null=True, blank=True, db_column='content')
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='E',
        db_column='status'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_note'
        ordering = ['-created_at']
        verbose_name = '노트'
        verbose_name_plural = '노트들'
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class NoteTag(models.Model):
    """
    노트 태그 모델
    """
    
    note_tag_sid = models.AutoField(primary_key=True, db_column='note_tag_sid')
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='tags',
        db_column='note_sid'
    )
    tag_name = models.CharField(max_length=100, db_column='tag_name')
    sort_order = models.SmallIntegerField(default=0, db_column='sort_order')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    
    class Meta:
        db_table = 't_note_tag'
        ordering = ['sort_order', 'created_at']
        verbose_name = '노트 태그'
        verbose_name_plural = '노트 태그들'
        unique_together = [['note', 'tag_name']]
        indexes = [
            models.Index(fields=['note', 'tag_name']),
        ]
    
    def __str__(self):
        return f"{self.note.title} - {self.tag_name}"


class NoteComment(models.Model):
    """
    노트 댓글 모델
    """
    
    comment_sid = models.AutoField(primary_key=True, db_column='comment_sid')
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='comments',
        db_column='note_sid'
    )
    highlighted_text = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        db_column='highlighted_text'
    )
    comment_text = models.TextField(db_column='comment_text')
    position_top = models.SmallIntegerField(default=0, db_column='position_top')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_note_comment'
        ordering = ['position_top', 'created_at']
        verbose_name = '노트 댓글'
        verbose_name_plural = '노트 댓글들'
    
    def __str__(self):
        return f"Comment {self.comment_sid} on {self.note.title}"


class NoteAttachment(models.Model):
    """
    노트 첨부 파일 모델
    """
    
    attachment_sid = models.AutoField(primary_key=True, db_column='attachment_sid')
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='attachments',
        db_column='note_sid'
    )
    file_name = models.CharField(max_length=255, db_column='file_name')
    file_size = models.BigIntegerField(null=True, blank=True, db_column='file_size')
    file_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column='file_type'
    )
    file_path = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        db_column='file_path'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_note_attachment'
        ordering = ['-created_at']
        verbose_name = '노트 첨부 파일'
        verbose_name_plural = '노트 첨부 파일들'
    
    def __str__(self):
        return f"{self.file_name} ({self.note.title})"


class NoteShare(models.Model):
    """
    노트 공유 모델
    """
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='shares',
        db_column='note_sid'
    )
    # 공유할 사용자 아이디
    user_id = models.CharField(max_length=60, db_column='user_id')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    # 노트 소유자 아이디
    created_id = models.CharField(max_length=60, db_column='created_id')
    
    class Meta:
        db_table = 't_note_share'
        ordering = ['-created_at']
        verbose_name = '노트 공유'
        verbose_name_plural = '노트 공유들'
        indexes = [
            models.Index(fields=['note', 'user_id']),
        ]
    
    def __str__(self):
        return f"{self.note.title} - {self.user_id}"
