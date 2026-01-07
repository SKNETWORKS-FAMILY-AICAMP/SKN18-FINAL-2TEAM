# 논문 네트워크 그래프 데이터 플로우

## 전체 플로우 개요

```
사용자 메시지 전송
    ↓
AI 응답 생성 (LangGraph)
    ↓
백그라운드 스레드 시작
    ↓
RAG 결과에서 PMID 추출
    ↓
Neo4j에서 논문 네트워크 조회
    ↓
Django DB에 저장 (t_paper_graph, t_paper_node, t_paper_edge)
    ↓
프론트엔드에서 API 호출
    ↓
Sigma.js로 그래프 렌더링
```

---

## 1단계: 사용자 메시지 전송 및 AI 응답 생성

**파일**: `django_app/apps/chat/views.py` - `chat_messages()` 함수

**플로우**:
1. 사용자가 채팅 메시지 전송 (`POST /chat/api/chats/messages/`)
2. `generate_ai_response()` 호출 → LangGraph 워크플로우 실행
3. AI 응답 생성 및 `result_state` 반환 (RAG 결과 포함)

**코드 위치**:
```python
# views.py:1071-1073
ai_text, citations, scores, reference_type, chat_title, result_state = generate_ai_response(
    chat, content, return_state=True
)
```

---

## 2단계: 백그라운드에서 논문 네트워크 생성

**파일**: `django_app/apps/chat/views.py` - `chat_messages()` 함수

**플로우**:
1. AI 메시지 생성 후 백그라운드 스레드 시작
2. `generate_paper_graph_background()` 함수 실행 (비동기)

**코드 위치**:
```python
# views.py:1096-1103
thread = threading.Thread(
    target=generate_paper_graph_background,
    args=(assistant_message, result_state, content),
    daemon=True
)
thread.start()
```

---

## 3단계: RAG 결과에서 PMID 추출 및 타입 분류

**파일**: `django_app/apps/chat/services.py` - `extract_pmids_from_rag_result()` 함수

**플로우**:
1. `result_state`에서 논문 정보 추출
2. 논문 타입 분류:
   - **중심 논문 (central)**: `selected_chunks`, `web_selected_chunks`에서 추출 (AI 응답에서 직접 인용)
   - **관련 논문 (related)**: `reranked_results`, `retrieval_results`, `contexts`에서 추출 (RAG 검색 결과)
3. 최대 20개 PMID 추출

**코드 위치**:
```python
# services.py:514-597
pmids, pmid_types = extract_pmids_from_rag_result(result_state, max_count=20)
# 반환값:
# - pmids: [12345678, 23456789, ...] (최대 20개)
# - pmid_types: {12345678: 'central', 23456789: 'related', ...}
```

**데이터 소스**:
- `result_state["selected_chunks"]` → 중심 논문
- `result_state["web_selected_chunks"]` → 중심 논문
- `result_state["reranked_results"]` → 관련 논문
- `result_state["retrieval_results"]` → 관련 논문 (fallback)
- `result_state["contexts"]` → 관련 논문 (fallback)

---

## 4단계: Neo4j에서 논문 네트워크 조회

**파일**: `django_app/apps/chat/services.py` - `query_neo4j_paper_network()` 함수

**플로우**:
1. Neo4j에 연결
2. **노드 조회**: 추출된 PMID들의 논문 정보 (제목, 연도, DOI, 저널)
3. **엣지 조회**: 논문 간 인용 관계 (CitedWork를 통한 간접 관계)
4. **파생 논문 조회**: 원본 논문들이 인용하는 논문 중 원본에 없는 논문 (최대 10개)

**Cypher 쿼리**:

```cypher
# 1. 논문 노드 조회
MATCH (a:Article)
WHERE a.pmid IN $pmids
OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
RETURN a.pmid, a.title, a.year, a.doi, j.name

# 2. 논문 간 인용 관계 조회
MATCH (a1:Article)-[:CITES_WORK]->(cw:CitedWork)<-[:CITES_WORK]-(a2:Article)
WHERE a1.pmid IN $pmids AND a2.pmid IN $pmids AND a1.pmid <> a2.pmid
RETURN DISTINCT a1.pmid AS source_pmid, a2.pmid AS target_pmid

# 3. 파생 논문 조회
MATCH (a1:Article)-[:CITES_WORK]->(cw:CitedWork)<-[:CITES_WORK]-(a2:Article)
WHERE a1.pmid IN $pmids AND NOT a2.pmid IN $pmids
WITH DISTINCT a2.pmid AS derived_pmid, COUNT(DISTINCT a1.pmid) AS citation_count
ORDER BY citation_count DESC
LIMIT 10
RETURN a2.pmid, a2.title, a2.year, a2.doi, j.name
```

**반환 데이터 구조**:
```python
{
    "nodes": [
        {
            "id": "12345678",
            "label": "논문 제목",
            "year": "2024",
            "doi": "10.1234/example",
            "journal": "Journal Name",
            "paper_type": "central" | "related" | "derived"
        },
        ...
    ],
    "edges": [
        ["12345678", "23456789"],  # source_pmid -> target_pmid
        ...
    ]
}
```

**코드 위치**:
```python
# services.py:600-720
paper_network = query_neo4j_paper_network(pmids, pmid_types)
```

---

## 5단계: Django DB에 저장

**파일**: `django_app/apps/chat/services.py` - `create_paper_graph_from_neo4j()` 함수

**플로우**:
1. **t_paper_graph 테이블에 그래프 생성**
   - `graph_sid` (PK, Auto)
   - `graph_title`: "관련 논문 네트워크 (20개 논문)"
   - `graph_description`: 사용자 질문 또는 기본 설명
   - `status`: 'E' (사용)
   - `created_id`: 'system'

2. **t_paper_node 테이블에 노드 생성**
   - `node_sid` (PK, Auto)
   - `graph_sid` (FK → t_paper_graph)
   - `paper_id`: PMID (문자열)
   - `paper_label`: 논문 제목
   - `node_size`: 타입별 크기 (중심=35, 관련=25, 파생=20)
   - `node_color`: 타입별 색상 (중심=#FF6B6B, 관련=#4ECDC4, 파생=#95E1D3)
   - `x_position`, `y_position`: 원형 레이아웃 좌표
     - 중심 논문: 반지름 0.3 (중앙)
     - 관련 논문: 반지름 0.7 (중간)
     - 파생 논문: 반지름 1.2 (외곽)

3. **t_paper_edge 테이블에 엣지 생성**
   - `edge_sid` (PK, Auto)
   - `graph_sid` (FK → t_paper_graph)
   - `source_paper_id`: 출발 노드의 paper_id
   - `target_paper_id`: 도착 노드의 paper_id
   - `edge_size`: 1
   - `edge_color`: '#CCCCCC'

4. **t_chat_message_paper_graph 테이블에 연결**
   - `message_sid` (FK → t_chat_message)
   - `graph_sid` (FK → t_paper_graph)
   - `sort_order`: 0

**코드 위치**:
```python
# services.py:723-850
create_paper_graph_from_neo4j(
    message=assistant_message,
    paper_network=paper_network,
    graph_title=graph_title,
    graph_description=graph_description
)
```

**DB 테이블 구조**:

```
t_paper_graph (그래프 메타데이터)
├── graph_sid (PK)
├── graph_title
├── graph_description
├── status
└── created_at

t_paper_node (논문 노드)
├── node_sid (PK)
├── graph_sid (FK → t_paper_graph)
├── paper_id (PMID)
├── paper_label (제목)
├── node_size (크기)
├── node_color (색상)
├── x_position (X 좌표)
└── y_position (Y 좌표)

t_paper_edge (논문 간 엣지)
├── edge_sid (PK)
├── graph_sid (FK → t_paper_graph)
├── source_paper_id (출발 노드)
├── target_paper_id (도착 노드)
├── edge_size
└── edge_color

t_chat_message_paper_graph (메시지-그래프 연결)
├── message_sid (FK → t_chat_message)
├── graph_sid (FK → t_paper_graph)
└── sort_order
```

---

## 6단계: 프론트엔드에서 API 호출

**파일**: `django_app/static/js/pages/chat.js` - `handleMessageAction()` 함수

**플로우**:
1. 사용자가 "관련 논문 네트워크" 버튼 클릭
2. `GET /chat/api/messages/{message_id}/paper-graphs/` API 호출

**코드 위치**:
```javascript
// chat.js:1710-1751
fetch(`/chat/api/messages/${actualMessageId}/paper-graphs/`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
})
.then(response => response.json())
.then(data => {
    const graph = data.paper_graphs[0];
    graphData = {
        nodes: graph.nodes || [],
        edges: graph.edges || [],
        title: graph.title || '관련 논문 네트워크',
        description: graph.description || ''
    };
    window.PaperGraphModal.open(graphData);
});
```

---

## 7단계: API에서 DB 데이터 조회 및 포맷팅

**파일**: `django_app/apps/chat/views.py` - `message_paper_graphs_api()` 함수

**플로우**:
1. `ChatMessagePaperGraph` 조회 (메시지와 연결된 그래프)
2. `PaperNode` 조회 (그래프의 모든 노드)
3. `PaperEdge` 조회 (그래프의 모든 엣지)
4. 데이터 포맷팅:
   - 노드: `{id, label, size, x, y, color, paper_type}`
   - 엣지: `[[source_id, target_id], ...]`

**SQL 쿼리 (Django ORM)**:
```python
# 1. 메시지와 연결된 그래프 조회
ChatMessagePaperGraph.objects.filter(message=message)
    .select_related('graph')
    .order_by('sort_order', 'created_at')

# 2. 노드 조회
PaperNode.objects.filter(graph=graph).values(
    'paper_id', 'paper_label', 'node_size', 'node_color',
    'x_position', 'y_position'
)

# 3. 엣지 조회
PaperEdge.objects.filter(graph=graph).values(
    'source_paper_id', 'target_paper_id'
)
```

**API 응답 구조**:
```json
{
    "status": "success",
    "message_id": 84,
    "paper_graphs": [
        {
            "id": 2,
            "title": "관련 논문 네트워크 (20개 논문)",
            "description": "mRNA 백신의 면역 반응 메커니즘을 설명해주세요",
            "nodes": [
                {
                    "id": "38585714",
                    "label": "논문 제목...",
                    "size": 35,
                    "x": 200.0,
                    "y": 0.0,
                    "color": "#FF6B6B",
                    "paper_type": "central"
                },
                ...
            ],
            "edges": [
                ["39726007", "39111829"],
                ["39811667", "39386662"],
                ...
            ]
        }
    ]
}
```

**코드 위치**:
```python
# views.py:160-244
def message_paper_graphs_api(request, message_id):
    # ... DB 조회 및 포맷팅 ...
    return JsonResponse({
        'status': 'success',
        'message_id': message_id,
        'paper_graphs': message_graphs,
    })
```

---

## 8단계: 프론트엔드에서 Sigma.js로 그래프 렌더링

**파일**: `django_app/static/js/components/modals/paper_graph_modal.js` - `renderGraph()` 함수

**플로우**:
1. `PaperGraphModal.open(graphData)` 호출
2. Graphology로 그래프 객체 생성
3. 노드 추가 (API에서 받은 노드 데이터 사용)
4. 엣지 추가 (API에서 받은 엣지 데이터 사용)
5. Sigma.js로 그래프 렌더링

**코드 위치**:
```javascript
// paper_graph_modal.js:223-320
function renderGraph(containerElement, data = null) {
    // 1. Graphology Graph 객체 생성
    const graph = new Graph();
    
    // 2. 노드 추가
    nodesToUse.forEach((node) => {
        graph.addNode(String(node.id), {
            label: node.label,
            size: node.size,
            x: node.x,
            y: node.y,
            color: node.color,
        });
    });
    
    // 3. 엣지 추가
    edgesToUse.forEach(([source, target]) => {
        graph.addEdge(String(source), String(target), {
            size: 1,
            color: '#CCCCCC',
        });
    });
    
    // 4. Sigma 인스턴스 생성 및 렌더링
    sigmaInstance = new Sigma(graph, containerElement, {
        renderEdgeLabels: false,
        defaultNodeColor: '#5B8E7E',
        defaultEdgeColor: '#CCCCCC',
        labelFont: 'Arial',
        labelSize: 10,
        labelDensity: 0.1,
    });
}
```

**시각화 결과**:
- **노드**: 원형으로 표시, 색상과 크기로 논문 타입 구분
- **엣지**: 회색 선으로 논문 간 인용 관계 표시
- **인터랙션**: 호버/클릭 시 라벨 표시

---

## 데이터 흐름 요약

### 생성 단계 (백그라운드)
```
result_state (LangGraph)
    ↓ extract_pmids_from_rag_result()
pmids + pmid_types
    ↓ query_neo4j_paper_network()
paper_network {nodes, edges}
    ↓ create_paper_graph_from_neo4j()
t_paper_graph (1개)
t_paper_node (N개)
t_paper_edge (M개)
t_chat_message_paper_graph (1개)
```

### 조회 단계 (API)
```
GET /chat/api/messages/{id}/paper-graphs/
    ↓ message_paper_graphs_api()
t_chat_message_paper_graph 조회
    ↓
t_paper_graph 조회
    ↓
t_paper_node 조회 (N개)
t_paper_edge 조회 (M개)
    ↓ 포맷팅
JSON 응답 {nodes: [...], edges: [...]}
```

### 렌더링 단계 (프론트엔드)
```
JSON 데이터
    ↓ PaperGraphModal.open()
Graphology Graph 객체
    ↓ Sigma.js
화면에 그래프 렌더링
```

---

## 주요 테이블 관계

```
t_chat_message (메시지)
    ↓ (1:N)
t_chat_message_paper_graph (연결 테이블)
    ↓ (N:1)
t_paper_graph (그래프)
    ↓ (1:N)
t_paper_node (노드)
t_paper_edge (엣지)
```

**Foreign Key 관계**:
- `t_paper_node.graph_sid` → `t_paper_graph.graph_sid`
- `t_paper_edge.graph_sid` → `t_paper_graph.graph_sid`
- `t_chat_message_paper_graph.message_sid` → `t_chat_message.message_sid`
- `t_chat_message_paper_graph.graph_sid` → `t_paper_graph.graph_sid`

---

## 논문 타입별 특징

| 타입 | 색상 | 크기 | 위치 | 데이터 소스 |
|------|------|------|------|------------|
| **중심 (central)** | #FF6B6B (빨강) | 35 | 중심 (반지름 0.3) | selected_chunks, web_selected_chunks |
| **관련 (related)** | #4ECDC4 (청록) | 25 | 중간 (반지름 0.7) | reranked_results, retrieval_results |
| **파생 (derived)** | #95E1D3 (연한 청록) | 20 | 외곽 (반지름 1.2) | Neo4j 인용 관계로 발견 |

---

## 확인 방법

1. **DB 확인**:
   ```sql
   -- 그래프 조회
   SELECT * FROM t_paper_graph ORDER BY created_at DESC LIMIT 1;
   
   -- 노드 조회
   SELECT * FROM t_paper_node WHERE graph_sid = 2;
   
   -- 엣지 조회
   SELECT * FROM t_paper_edge WHERE graph_sid = 2;
   ```

2. **API 확인**:
   ```bash
   curl http://localhost:8000/chat/api/messages/84/paper-graphs/
   ```

3. **브라우저 콘솔**:
   - Network 탭에서 API 응답 확인
   - Console에서 `[PaperGraph]` 로그 확인

