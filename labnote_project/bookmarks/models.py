from django.db import models
from django.conf import settings
from notes.models import t_note

# Enum for source type (paper/web/tool)
class SourceType(models.TextChoices):
    PAPER = 'paper', 'Paper'
    WEB = 'web', 'Web'
    TOOL = 'tool', 'Tool'

# t_bookmark
class t_bookmark(models.Model):
    # PK: bookmark_sid
    bookmark_sid = models.AutoField(primary_key=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # User who created the bookmark
    name = models.CharField(max_length=255)  # Bookmark name
    description = models.CharField(max_length=1024, blank=True)  # Bookmark description
    color = models.CharField(max_length=50, blank=True)  # Color field, if applicable
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp when the bookmark is created
    updated_at = models.DateTimeField(auto_now=True)  # Timestamp when the bookmark is last updated
    creator_id = models.CharField(max_length=255)  # Creator ID (varchar)

    def __str__(self):
        return f"Bookmark: {self.name} by {self.creator_id}"

    class Meta:
        db_table = "t_bookmark"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} bookmarked {self.bookmark_item} with note {self.note}"

# t_bookmark_item
class t_bookmark_item(models.Model):
    # PK: bookmark_item_sid
    bookmark_item_sid = models.AutoField(primary_key=True)

    bookmark = models.ForeignKey(t_bookmark, on_delete=models.CASCADE, db_column="bookmark_sid")  # FK to t_bookmark (assuming 'bookmark_sid')
    title = models.CharField(max_length=255)
    url = models.TextField()
    source_type = models.CharField(
        max_length=5,
        choices=SourceType.choices,  # Assuming SourceType is an enum defined elsewhere
    )
    source_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    creator_id = models.CharField(max_length=255)  # Assuming creator_id is a string (adjust if needed)

    def __str__(self):
        return f"Bookmark item: {self.title} by {self.creator_id}"
    
    class Meta:
        db_table = "t_bookmark_item"
        ordering = ["-created_at"]

# t_bookmark_item_notes
class t_bookmark_item_notes(models.Model):
    # PK: bookmark_item_note_sid
    bookmark_item_note_sid = models.AutoField(primary_key=True)

    bookmark_item = models.ForeignKey(t_bookmark_item, on_delete=models.CASCADE, db_column="bookmark_item_sid")
    bookmark = models.ForeignKey(t_bookmark, on_delete=models.CASCADE, db_column="bookmark_sid")
    note = models.ForeignKey(t_note, on_delete=models.CASCADE, db_column="note_sid")
    excerpt = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Note {self.note.title} for {self.bookmark_item.title}"
    
    class Meta:
        db_table = "t_bookmark_item_notes"
        ordering = ["-created_at"]