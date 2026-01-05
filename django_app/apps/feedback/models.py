from django.db import models


class Feedback(models.Model):
    """
    사용자 피드백 저장 모델
    t_feedback 테이블과 매핑되며 단순한 제안/버그 신고 등을 저장한다.
    """

    class Category(models.TextChoices):
        GENERAL = "G", "일반"
        BUG = "B", "버그 리포트"
        FEATURE = "F", "기능 제안"
        IMPROVEMENT = "I", "개선 사항"

    feedback_sid = models.AutoField(primary_key=True, db_column="feedback_sid")
    category = models.CharField(
        max_length=1,
        choices=Category.choices,
        db_column="category",
    )
    feedback_content = models.TextField(db_column="feedback_content")
    created_at = models.DateTimeField(auto_now_add=True, db_column="created_at")
    created_id = models.CharField(max_length=60, db_column="created_id")
    updated_at = models.DateTimeField(auto_now=True, db_column="updated_at")
    updated_id = models.CharField(max_length=60, db_column="updated_id")

    class Meta:
        db_table = "t_feedback"
        ordering = ["-created_at"]
        verbose_name = "피드백"
        verbose_name_plural = "피드백 목록"

    def __str__(self):
        label = self.get_category_display()
        return f"[{label}] {self.feedback_content[:30]}"
