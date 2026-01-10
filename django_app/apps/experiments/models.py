from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class ExperimentTool(models.Model):
    """실험 도구 모델"""
    
    STATUS_CHOICES = [
        ('E', 'Enabled'),
        ('D', 'Disabled'),
    ]
    
    tool_sid = models.AutoField(primary_key=True, db_column='tool_sid')
    tool_name = models.CharField(max_length=100, unique=True, db_column='tool_name')
    category = models.CharField(max_length=100, db_column='category')
    description = models.TextField(blank=True, null=True, db_column='description')
    icon_name = models.CharField(max_length=100, blank=True, null=True, db_column='icon_name')
    img_url = models.CharField(max_length=1000, blank=True, null=True, db_column='img_url')
    guide_overview = models.TextField(blank=True, null=True, db_column='guide_overview')
    guide_usage = models.TextField(blank=True, null=True, db_column='guide_usage')
    guide_tips = models.TextField(blank=True, null=True, db_column='guide_tips')
    guide_prerequisites = models.TextField(blank=True, null=True, db_column='guide_prerequisites', help_text='JSON array of prerequisites')
    guide_inputs = models.TextField(blank=True, null=True, db_column='guide_inputs', help_text='JSON array of inputs')
    guide_outputs = models.TextField(blank=True, null=True, db_column='guide_outputs', help_text='JSON array of outputs')
    guide_limitations = models.TextField(blank=True, null=True, db_column='guide_limitations', help_text='JSON array of limitations')
    guide_recommended_workflow = models.TextField(blank=True, null=True, db_column='guide_recommended_workflow', help_text='JSON array of recommended workflow steps')
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='E',
        db_column='status'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    
    class Meta:
        db_table = 't_experiment_tool'
        ordering = ['tool_name']
        verbose_name = '실험 도구'
        verbose_name_plural = '실험 도구들'
    
    def __str__(self):
        return f"{self.tool_name} ({self.category})"


class ExperimentToolOption(models.Model):
    """실험 도구 옵션 필드 모델"""
    
    FIELD_TYPE_CHOICES = [
        ('number', 'Number'),
        ('select', 'Select'),
        ('checkbox', 'Checkbox'),
        ('text', 'Text'),
        ('textarea', 'Textarea'),
    ]
    
    option_sid = models.AutoField(primary_key=True, db_column='option_sid')
    tool = models.ForeignKey(
        ExperimentTool,
        on_delete=models.CASCADE,
        related_name='options',
        db_column='tool_sid'
    )
    field_name = models.CharField(max_length=100, db_column='field_name')
    field_label = models.CharField(max_length=255, db_column='field_label')
    field_type = models.CharField(max_length=50, choices=FIELD_TYPE_CHOICES, db_column='field_type')
    default_value = models.TextField(blank=True, null=True, db_column='default_value')
    min_value = models.SmallIntegerField(default=0, db_column='min_value')
    max_value = models.SmallIntegerField(default=100, db_column='max_value')
    step_value = models.SmallIntegerField(default=1, db_column='step_value')
    options_json = models.TextField(blank=True, null=True, db_column='options_json', help_text='JSON string for select options')
    help_text = models.TextField(blank=True, null=True, db_column='help_text', help_text='Help text for tooltip/description')
    sort_order = models.SmallIntegerField(default=0, db_column='sort_order')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_experiment_tool_option'
        ordering = ['sort_order', 'field_name']
        verbose_name = '실험 도구 옵션'
        verbose_name_plural = '실험 도구 옵션들'
    
    def __str__(self):
        return f"{self.tool.tool_name} - {self.field_label}"


class Experiment(models.Model):
    """실험 모델"""
    
    STATUS_CHOICES = [
        ('E', 'Enabled'),
        ('R', 'Ready'),
        ('P', 'In Progress'),
        ('C', 'Completed'),
        ('F', 'Failed'),
        ('D', 'Disabled'),
    ]
    
    experiment_sid = models.AutoField(primary_key=True, db_column='experiment_sid')
    pipeline_name = models.CharField(max_length=255, db_column='pipeline_name')
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='R',  # Ready: 파이프라인 생성 시 기본 상태
        db_column='status'
    )
    progress = models.SmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_column='progress'
    )
    protein_sequence = models.TextField(blank=True, null=True, db_column='protein_sequence')
    protein_name = models.CharField(max_length=255, blank=True, null=True, db_column='protein_name')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    # Many-to-many relationship with tools through ExperimentToolSelection
    tools = models.ManyToManyField(
        ExperimentTool,
        through='ExperimentToolSelection',
        related_name='experiments'
    )
    
    class Meta:
        db_table = 't_experiment'
        ordering = ['-created_at']
        verbose_name = '실험'
        verbose_name_plural = '실험들'
    
    def __str__(self):
        return f"{self.pipeline_name} ({self.get_status_display()})"
    
    def get_status_display_korean(self):
        """한국어 상태 표시"""
        status_map = {
            'R': '준비',      # Ready: 파이프라인 생성됨, 아직 시작 안됨
            'E': '활성',      # Active: 워커가 시작해서 진행이 시작됨
            'P': '진행중',    # In Progress: 실제로 실행 중
            'C': '완료',      # Completed
            'F': '실패',      # Failed
            'D': '비활성',    # Disabled
        }
        return status_map.get(self.status, self.get_status_display())


class ExperimentToolSelection(models.Model):
    """실험 도구 선택 (파이프라인 구성) 모델"""
    
    selection_sid = models.AutoField(primary_key=True, db_column='selection_sid')
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name='tool_selections',
        db_column='experiment_sid'
    )
    tool = models.ForeignKey(
        ExperimentTool,
        on_delete=models.CASCADE,
        related_name='selections',
        db_column='tool_sid'
    )
    sort_order = models.SmallIntegerField(default=0, db_column='sort_order')
    tool_options_json = models.TextField(
        blank=True,
        null=True,
        db_column='tool_options_json',
        help_text='JSON string containing tool option values'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_experiment_tool_selection'
        ordering = ['sort_order']
        unique_together = [['experiment', 'tool', 'sort_order']]
        verbose_name = '실험 도구 선택'
        verbose_name_plural = '실험 도구 선택들'
    
    def __str__(self):
        return f"{self.experiment.pipeline_name} - {self.tool.tool_name} (순서: {self.sort_order})"


class ExperimentResult(models.Model):
    """실험 결과 파일 모델"""
    
    RESULT_TYPE_CHOICES = [
        ('PDB', 'PDB'),
        ('FASTA', 'FASTA'),
        ('PDF', 'PDF'),
        ('TXT', 'TXT'),
        ('LOG', 'LOG'),
        ('CSV', 'CSV'),
        ('JSON', 'JSON'),
        ('OTHER', 'Other'),
    ]
    
    result_sid = models.AutoField(primary_key=True, db_column='result_sid')
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name='results',
        db_column='experiment_sid'
    )
    result_name = models.CharField(max_length=255, db_column='result_name')
    result_type = models.CharField(max_length=50, choices=RESULT_TYPE_CHOICES, db_column='result_type')
    file_size = models.BigIntegerField(blank=True, null=True, db_column='file_size', help_text='File size in bytes')
    file_path = models.CharField(max_length=1000, blank=True, null=True, db_column='file_path')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    
    class Meta:
        db_table = 't_experiment_result'
        ordering = ['-created_at']
        verbose_name = '실험 결과'
        verbose_name_plural = '실험 결과들'
    
    def __str__(self):
        return f"{self.experiment.pipeline_name} - {self.result_name}"
    
    def get_file_size_display(self):
        """파일 크기를 읽기 쉬운 형식으로 표시"""
        if not self.file_size:
            return '0 B'
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class ExperimentViewerState(models.Model):
    """실험 뷰어 작업 상태 모델"""
    
    state_sid = models.AutoField(primary_key=True, db_column='state_sid')
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name='viewer_states',
        db_column='experiment_sid'
    )
    state_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_column='state_name',
        help_text='저장된 작업 상태 이름'
    )
    state_data = models.JSONField(
        db_column='state_data',
        help_text='JSON 형식의 뷰어 상태 데이터 (로드된 파일, 설정, 카메라 등)'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')
    updated_id = models.CharField(max_length=60, db_column='updated_id')
    
    class Meta:
        db_table = 't_experiment_viewer_state'
        ordering = ['-updated_at']
        verbose_name = '실험 뷰어 상태'
        verbose_name_plural = '실험 뷰어 상태들'
    
    def __str__(self):
        return f"{self.experiment.pipeline_name} - {self.state_name or 'Unnamed State'}"
