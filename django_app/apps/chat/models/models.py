from django.db import models


class RecommendedQuestion(models.Model):
    """
    추천 질문 모델
    사용자가 추천 질문을 클릭했을 때 기록
    """
    
    # 카테고리 선택지
    QUESTION_CATEGORY_CHOICES = [
        ('P', '논문'),
        ('C', '임상'),
        ('T', '프로토콜'),
        ('S', '시뮬레이션'),
        ('R', '결과 해석'),
    ]
    
    # 상태 선택지
    STATUS_CHOICES = [
        ('E', '사용'),
        ('D', 'Disabled'),
        ('R', 'Removed'),
    ]
    
    question_sid = models.AutoField(primary_key=True, db_column='question_sid')
    question_text = models.CharField(max_length=500, db_column='question_text')
    question_category = models.CharField(
        max_length=1,
        choices=QUESTION_CATEGORY_CHOICES,
        db_column='question_category'
    )
    sort_order = models.IntegerField(default=0, db_column='sort_order')
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='E',
        db_column='status'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    
    class Meta:
        db_table = 't_recommended_question'
        ordering = ['sort_order', 'question_sid']
        verbose_name = '추천 질문'
        verbose_name_plural = '추천 질문들'
    
    def __str__(self):
        return f"{self.get_question_category_display()} - {self.question_text[:50]}"


class Chat(models.Model):
    """
    채팅 모델
    """
    
    # 상태 선택지
    STATUS_CHOICES = [
        ('E', '사용'),
        ('D', 'Disabled'),
        ('R', 'Removed'),
    ]
    
    # 필터 타입 선택지 (논문, 임상, 프로토콜, 시뮬레이션, 결과 해석)
    FILTER_TYPE_CHOICES = [
        ('P', '논문'),
        ('C', '임상'),
        ('T', '프로토콜'),
        ('S', '시뮬레이션'),
        ('R', '결과 해석'),
    ]
    
    chat_sid = models.AutoField(primary_key=True, db_column='chat_sid')
    title = models.CharField(max_length=500, null=True, blank=True, db_column='title')
    preview = models.TextField(null=True, blank=True, db_column='preview')
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='E',
        db_column='status'
    )
    favorite = models.CharField(   # pin기능이 곧 favorites 이므로 pin이름을 favorites로 통일
        max_length=1,
        default='N',
        db_column='favorite'
    )
    archived = models.CharField(
        max_length=1,
        default='N',
        db_column='archived'
    )
    filter_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column='filter_type'
    )
    auto_mode = models.CharField(
        max_length=1,
        default='Y',
        db_column='auto_mode'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_chat'
        ordering = ['-created_at']
        verbose_name = '채팅'
        verbose_name_plural = '채팅들'
    
    def __str__(self):
        return f"Chat {self.chat_sid}: {self.title or 'No title'}"


class ChatMessage(models.Model):
    """
    채팅 메시지 모델
    """
    
    # 역할 선택지
    ROLE_CHOICES = [
        ('U', 'User'),
        ('A', 'Assistant'),
    ]
    
    message_sid = models.AutoField(primary_key=True, db_column='message_sid')
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        db_column='chat_sid',
        related_name='messages'
    )
    role = models.CharField(
        max_length=1,
        choices=ROLE_CHOICES,
        db_column='role'
    )
    content = models.TextField(db_column='content')
    sort_order = models.IntegerField(db_column='sort_order')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    concept_graph = models.TextField(blank=True, null=True, db_column='concept_graph')  # 머메이드
    
    class Meta:
        db_table = 't_chat_message'
        ordering = ['sort_order', 'created_at']
        verbose_name = '채팅 메시지'
        verbose_name_plural = '채팅 메시지들'
    
    def __str__(self):
        return f"Message {self.message_sid} ({self.get_role_display()})"


class ChatReference(models.Model):
    """
    채팅 참고 문헌 모델
    """
    
    # 소스 선택지
    SOURCE_CHOICES = [
        ('P', 'PubMed'),
        ('W', 'Web'),
        ('N', 'NIH'),
        ('T', 'PROTOCOL'),
    ]
    
    # 배지 선택지
    BADGE_CHOICES = [
        ('H', 'High'),
        ('M', 'Medium'),
        ('L', 'Low'),
    ]
    
    # 저널 선택지
    JOURNAL_CHOICES = [
        ('J', 'Journal'),
        ('B', 'Book'),
        ('R', 'Report'),
        ('P', 'Protocol'),
    ]
    
    reference_sid = models.AutoField(primary_key=True, db_column='reference_sid')
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        db_column='chat_sid',
        related_name='references'
    )
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='message_sid',
        related_name='references'
    )
    source = models.CharField(
        max_length=1,
        choices=SOURCE_CHOICES,
        db_column='source'
    )
    badge = models.CharField(
        max_length=1,
        choices=BADGE_CHOICES,
        db_column='badge'
    )
    title = models.CharField(max_length=500, db_column='title')
    description = models.TextField(null=True, blank=True, db_column='description')
    journal = models.CharField(
        max_length=1,
        choices=JOURNAL_CHOICES,
        db_column='journal'
    )
    link = models.CharField(max_length=500, null=True, blank=True, db_column='link')
    ref_pubmed_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column='ref_pubmed_id'
    )
    ref_date = models.DateTimeField(null=True, blank=True, db_column='ref_date')
    ref_authors = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        db_column='ref_authors'
    )
    sort_order = models.IntegerField(default=0, db_column='sort_order')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    
    class Meta:
        db_table = 't_chat_reference'
        ordering = ['sort_order', 'created_at']
        verbose_name = '채팅 참고 문헌'
        verbose_name_plural = '채팅 참고 문헌들'
    
    def __str__(self):
        return f"Reference {self.reference_sid}: {self.title[:50]}"


class ChatMessageFeedback(models.Model):
    """
    채팅 메시지 피드백 모델
    """
    
    # 피드백 타입 선택지
    FEEDBACK_TYPE_CHOICES = [
        ('L', '좋아요'),
        ('D', '싫어요'),
        ('I', '개선제안'),
        ('E', '오류신고'),
        ('O', '기타'),
    ]
    
    feedback_sid = models.AutoField(primary_key=True, db_column='feedback_sid')
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        db_column='message_sid',
        related_name='feedbacks'
    )
    feedback_type = models.CharField(
        max_length=1,
        choices=FEEDBACK_TYPE_CHOICES,
        db_column='feedback_type'
    )
    rating = models.SmallIntegerField(null=True, blank=True, db_column='rating')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_chat_message_feedback'
        ordering = ['-created_at']
        verbose_name = '채팅 메시지 피드백'
        verbose_name_plural = '채팅 메시지 피드백들'
    
    def __str__(self):
        return f"Feedback {self.feedback_sid} ({self.get_feedback_type_display()})"
