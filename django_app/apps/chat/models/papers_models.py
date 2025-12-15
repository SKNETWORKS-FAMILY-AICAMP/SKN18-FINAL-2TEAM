from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class PaperGraph(models.Model):
    """
    논문 그래프 모델
    PaperGraphModal에서 표시되는 논문 네트워크 그래프의 메타데이터
    """
    
    # 상태 선택지
    STATUS_CHOICES = [
        ('E', '사용'),
        ('D', 'Disabled'),
    ]
    
    graph_sid = models.AutoField(primary_key=True, db_column='graph_sid')
    graph_title = models.CharField(max_length=255, null=True, blank=True, db_column='graph_title')
    graph_description = models.TextField(null=True, blank=True, db_column='graph_description')
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='E',
        db_column='status'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    updated_id = models.CharField(max_length=60, null=True, blank=True, db_column='updated_id')
    
    class Meta:
        db_table = 't_paper_graph'
        ordering = ['-created_at']
        verbose_name = '논문 그래프'
        verbose_name_plural = '논문 그래프들'
    
    def __str__(self):
        return f"Graph {self.graph_sid}: {self.graph_title or 'No title'}"


class PaperNode(models.Model):
    """
    논문 노드 모델
    PaperGraphModal에서 사용하는 논문 네트워크 그래프의 노드
    """
    
    node_sid = models.AutoField(primary_key=True, db_column='node_sid')
    graph = models.ForeignKey(
        PaperGraph,
        on_delete=models.CASCADE,
        db_column='graph_sid',
        related_name='nodes'
    )
    paper_id = models.CharField(max_length=100, db_column='paper_id')
    paper_label = models.CharField(max_length=255, db_column='paper_label')
    node_size = models.IntegerField(default=20, db_column='node_size')
    node_color = models.CharField(max_length=50, null=True, blank=True, db_column='node_color')
    x_position = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        db_column='x_position'
    )
    y_position = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        db_column='y_position'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    
    class Meta:
        db_table = 't_paper_node'
        unique_together = [['graph', 'paper_id']]
        ordering = ['paper_id']
        verbose_name = '논문 노드'
        verbose_name_plural = '논문 노드들'
    
    def __str__(self):
        return f"Node {self.node_sid}: {self.paper_label} ({self.paper_id})"


class PaperEdge(models.Model):
    """
    논문 엣지 모델
    PaperGraphModal에서 논문 간 인용 관계를 시각화하는 연결선
    """
    
    edge_sid = models.AutoField(primary_key=True, db_column='edge_sid')
    graph = models.ForeignKey(
        PaperGraph,
        on_delete=models.CASCADE,
        db_column='graph_sid',
        related_name='edges'
    )
    # source_paper_id와 target_paper_id는 같은 graph 내의 paper_id를 참조
    # Django는 복합 키를 직접 지원하지 않으므로 CharField로 저장하고
    # 필요시 PaperNode를 조회하여 사용
    source_paper_id = models.CharField(max_length=100, db_column='source_paper_id')
    target_paper_id = models.CharField(max_length=100, db_column='target_paper_id')
    edge_size = models.IntegerField(default=1, db_column='edge_size')
    edge_color = models.CharField(max_length=50, null=True, blank=True, db_column='edge_color')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    
    class Meta:
        db_table = 't_paper_edge'
        unique_together = [['graph', 'source_paper_id', 'target_paper_id']]
        verbose_name = '논문 엣지'
        verbose_name_plural = '논문 엣지들'
    
    def __str__(self):
        return f"Edge {self.edge_sid}: {self.source_paper_id} -> {self.target_paper_id}"
    
    @property
    def source_node(self):
        """소스 노드를 조회하는 프로퍼티"""
        try:
            return PaperNode.objects.get(graph=self.graph, paper_id=self.source_paper_id)
        except PaperNode.DoesNotExist:
            return None
    
    @property
    def target_node(self):
        """타겟 노드를 조회하는 프로퍼티"""
        try:
            return PaperNode.objects.get(graph=self.graph, paper_id=self.target_paper_id)
        except PaperNode.DoesNotExist:
            return None


class ChatMessagePaperGraph(models.Model):
    """
    채팅 메시지와 논문 그래프 연결 모델
    ResearchAI 컴포넌트에서 특정 메시지에 "관련 논문 상세 보기" 버튼이 표시될 때 사용
    """
    
    message = models.ForeignKey(
        'ChatMessage',
        on_delete=models.CASCADE,
        db_column='message_sid',
        related_name='paper_graphs'
    )
    graph = models.ForeignKey(
        PaperGraph,
        on_delete=models.CASCADE,
        db_column='graph_sid',
        related_name='chat_messages'
    )
    sort_order = models.SmallIntegerField(default=0, db_column='sort_order')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    created_id = models.CharField(max_length=60, db_column='created_id')
    
    class Meta:
        db_table = 't_chat_message_paper_graph'
        unique_together = [['message', 'graph']]
        ordering = ['sort_order', 'created_at']
        verbose_name = '채팅 메시지 논문 그래프'
        verbose_name_plural = '채팅 메시지 논문 그래프들'
    
    def __str__(self):
        return f"Message {self.message.message_sid} - Graph {self.graph.graph_sid}"
