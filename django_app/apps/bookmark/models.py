from django.db import models


class BookmarkCategory(models.Model):
    """
    북마크 카테고리 모델
    """
    
    category_sid = models.AutoField(primary_key=True, db_column='category_sid')
    category_name = models.CharField(max_length=255, db_column='category_name')
    sort_order = models.IntegerField(default=0, db_column='sort_order')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_bookmark_category'
        ordering = ['sort_order', 'category_sid']
        verbose_name = '북마크 카테고리'
        verbose_name_plural = '북마크 카테고리들'
    
    def __str__(self):
        return self.category_name


class Bookmark(models.Model):
    """
    북마크 모델
    """
    
    bookmark_sid = models.AutoField(primary_key=True, db_column='bookmark_sid')
    title = models.CharField(max_length=500, db_column='title')
    bookmark_url = models.CharField(max_length=1000, db_column='bookmark_url')
    description = models.TextField(null=True, blank=True, db_column='description')
    categories = models.ManyToManyField(
        BookmarkCategory,
        through='BookmarkMap',
        related_name='bookmarks'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_bookmark'
        ordering = ['-created_at']
        verbose_name = '북마크'
        verbose_name_plural = '북마크들'
    
    def __str__(self):
        return self.title


class BookmarkMap(models.Model):
    """
    북마크와 카테고리의 다대다 관계 매핑 모델
    """
    
    bookmark = models.ForeignKey(
        Bookmark,
        on_delete=models.CASCADE,
        db_column='bookmark_sid',
        related_name='bookmark_maps'
    )
    category = models.ForeignKey(
        BookmarkCategory,
        on_delete=models.CASCADE,
        db_column='category_sid',
        related_name='bookmark_maps'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    
    class Meta:
        db_table = 't_bookmark_map'
        unique_together = [['bookmark', 'category']]
        verbose_name = '북마크 카테고리 매핑'
        verbose_name_plural = '북마크 카테고리 매핑들'
    
    def __str__(self):
        return f"{self.bookmark.title} - {self.category.category_name}"
