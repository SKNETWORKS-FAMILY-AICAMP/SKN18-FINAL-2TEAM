from django.db import models


class CommonCode(models.Model):
    """
    공통 코드 그룹 모델
    common_code 규칙: 약자+숫자3자리 - ex: ABC001
    """
    
    common_code = models.CharField(
        max_length=6,
        primary_key=True,
        db_column='common_code',
        help_text='공통 코드 (약자+숫자3자리, 예: ABC001)'
    )
    common_name = models.CharField(
        max_length=100,
        db_column='common_name',
        help_text='공통 코드 그룹명'
    )
    description = models.TextField(
        null=True,
        blank=True,
        db_column='description',
        help_text='설명'
    )
    use_yn = models.CharField(
        max_length=1,
        default='Y',
        db_column='use_yn',
        help_text='사용 여부 (Y/N)'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='created_at'
    )
    created_id = models.CharField(
        max_length=60,
        db_column='created_id',
        help_text='생성자 ID'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column='updated_at'
    )
    updated_id = models.CharField(
        max_length=60,
        db_column='updated_id',
        help_text='수정자 ID'
    )
    
    class Meta:
        db_table = 'tc_common'
        ordering = ['common_code']
        verbose_name = '공통 코드 그룹'
        verbose_name_plural = '공통 코드 그룹들'
        indexes = [
            models.Index(fields=['use_yn']),
        ]
    
    def __str__(self):
        return f"{self.common_code} - {self.common_name}"


class CommonCodeItem(models.Model):
    """
    공통 코드 항목 모델
    common_item_code 규칙: 약자+숫자3자리 - ex: ABC001
    """
    
    common_item_code = models.CharField(
        max_length=6,
        primary_key=True,
        db_column='common_item_code',
        help_text='공통 코드 항목 코드 (약자+숫자3자리, 예: ABC001)'
    )
    common_code = models.ForeignKey(
        CommonCode,
        on_delete=models.CASCADE,
        related_name='items',
        db_column='common_code',
        help_text='공통 코드 그룹'
    )
    common_item_name = models.CharField(
        max_length=100,
        db_column='common_item_name',
        help_text='공통 코드 항목명'
    )
    description = models.TextField(
        null=True,
        blank=True,
        db_column='description',
        help_text='설명'
    )
    use_yn = models.CharField(
        max_length=1,
        default='Y',
        db_column='use_yn',
        help_text='사용 여부 (Y/N)'
    )
    sort_order = models.IntegerField(
        default=0,
        db_column='sort_order',
        help_text='정렬 순서'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column='created_at'
    )
    created_id = models.CharField(
        max_length=60,
        db_column='created_id',
        help_text='생성자 ID'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column='updated_at'
    )
    updated_id = models.CharField(
        max_length=60,
        db_column='updated_id',
        help_text='수정자 ID'
    )
    
    class Meta:
        db_table = 'tc_common_item'
        ordering = ['common_code', 'sort_order', 'common_item_code']
        verbose_name = '공통 코드 항목'
        verbose_name_plural = '공통 코드 항목들'
        indexes = [
            models.Index(fields=['common_code', 'use_yn']),
            models.Index(fields=['sort_order']),
        ]
    
    def __str__(self):
        return f"{self.common_item_code} - {self.common_item_name} ({self.common_code.common_code})"
