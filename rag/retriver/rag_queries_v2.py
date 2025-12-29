# -*- coding: utf-8 -*-
class GraphSchemaQueries:
    """
    전체 그래프 스키마(Constraint, Index) 통합 관리
    - queries_v2.py의 로딩 로직과 완벽히 동기화됨
    - Experiment 변수명: ep 사용
    - 작성일: 2025-12-29
    """

    # 1. 제약 조건 (Uniqueness Constraints)
    CREATE_CONSTRAINTS = [
        # [PrimeKG] BaseNode
        "CREATE CONSTRAINT base_node_index IF NOT EXISTS FOR (n:BaseNode) REQUIRE n.node_index IS UNIQUE;",

        # [Paper] Core Structures
        "CREATE CONSTRAINT article_pmid IF NOT EXISTS FOR (a:Article) REQUIRE a.pmid IS UNIQUE;",
        "CREATE CONSTRAINT section_id IF NOT EXISTS FOR (s:Section) REQUIRE s.section_id IS UNIQUE;",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;",

        # [Paper] Bibliographic & Metadata
        "CREATE CONSTRAINT reference_id IF NOT EXISTS FOR (r:Reference) REQUIRE r.uid IS UNIQUE;",
        "CREATE CONSTRAINT citedwork_uid IF NOT EXISTS FOR (w:CitedWork) REQUIRE w.uid IS UNIQUE;",
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE;",
        "CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (dom:Domain) REQUIRE dom.name IS UNIQUE;",
        "CREATE CONSTRAINT journal_name IF NOT EXISTS FOR (j:Journal) REQUIRE j.name IS UNIQUE;",
        "CREATE CONSTRAINT study_design_name IF NOT EXISTS FOR (sd:StudyDesign) REQUIRE sd.name IS UNIQUE;",

        # [Experiment] - ep 변수명 확인
        "CREATE CONSTRAINT experiment_id IF NOT EXISTS FOR (ep:Experiment) REQUIRE ep.experiment_id IS UNIQUE;",
        "CREATE CONSTRAINT category_parent_name IF NOT EXISTS FOR (cp:CategoryParent) REQUIRE cp.name IS UNIQUE;",
        "CREATE CONSTRAINT category_leaf_name IF NOT EXISTS FOR (cl:CategoryLeaf) REQUIRE cl.name IS UNIQUE;",
        "CREATE CONSTRAINT material_id IF NOT EXISTS FOR (em:ExpMaterial) REQUIRE em.material_id IS UNIQUE;",
        "CREATE CONSTRAINT equipment_id IF NOT EXISTS FOR (eq:ExpEquipment) REQUIRE eq.equipment_id IS UNIQUE;",

        # [Entity & Mention]
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;",
        "CREATE CONSTRAINT mention_id IF NOT EXISTS FOR (m:Mention) REQUIRE m.mention_id IS UNIQUE;",

        # [Protocol]
        "CREATE CONSTRAINT protocol_sid IF NOT EXISTS FOR (p:Protocol) REQUIRE p.protocol_sid IS UNIQUE;",
        "CREATE CONSTRAINT protocol_chunking_id IF NOT EXISTS FOR (pc:ProtocolChunk) REQUIRE pc.chunking_id IS UNIQUE;",
        "CREATE CONSTRAINT protocol_ref_sid IF NOT EXISTS FOR (pr:ProtocolReference) REQUIRE pr.reference_sid IS UNIQUE;",

        # [Clinical Trial]
        "CREATE CONSTRAINT nct_id IF NOT EXISTS FOR (ct:ClinicalTrial) REQUIRE ct.nct_id IS UNIQUE;"
    ]

    # 2. 일반 인덱스 (Regular Indexes)
    CREATE_INDEXES = [
        "CREATE INDEX base_node_name_idx IF NOT EXISTS FOR (n:BaseNode) ON (n.name);",
        "CREATE INDEX base_node_id_idx IF NOT EXISTS FOR (n:BaseNode) ON (n.id);",
        "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name);",
        "CREATE INDEX entity_primekg_label_idx IF NOT EXISTS FOR (e:Entity) ON (e.primekg_label);",
        "CREATE INDEX mention_nct_id_idx IF NOT EXISTS FOR (m:Mention) ON (m.nct_id);",
        "CREATE INDEX clinical_trial_nct_id_idx IF NOT EXISTS FOR (ct:ClinicalTrial) ON (ct.nct_id);"
    ]

    # 3. 벡터 인덱스 (Vector Indexes)
    CREATE_VECTOR_INDEXES = [
        """
        CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
        }}
        """,
        """
        CREATE VECTOR INDEX protocol_chunk_vector_index IF NOT EXISTS
        FOR (pc:ProtocolChunk) ON (pc.embedding)
        OPTIONS {indexConfig: {
        `vector.dimensions`: 1024,
        `vector.similarity_function`: 'cosine'
        }}
        """,
        """
        CREATE VECTOR INDEX clinicalChunkEmbeddingIndex IF NOT EXISTS
        FOR (cc:ClinicalChunk) ON (cc.embedding)
        OPTIONS {indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
        }}
        """
    ]

    # 4. 풀텍스트 인덱스 (Fulltext Indexes)
    CREATE_FULLTEXT_INDEXES = [
        # Basic Text
        "CREATE FULLTEXT INDEX entityTextIndex IF NOT EXISTS FOR (n:Entity) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX mentionTextIndex IF NOT EXISTS FOR (n:Mention) ON EACH [n.raw_text];",
        "CREATE FULLTEXT INDEX journalTextIndex IF NOT EXISTS FOR (n:Journal) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX chunkTextIndex IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text];",
        
        # Experiment Materials
        "CREATE FULLTEXT INDEX expMaterialTextIndex IF NOT EXISTS FOR (n:ExpMaterial) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX expEquipmentTextIndex IF NOT EXISTS FOR (n:ExpEquipment) ON EACH [n.name];",
        
        # Protocol & Clinical Chunks
        "CREATE FULLTEXT INDEX protocolChunkTextIndex IF NOT EXISTS FOR (n:ProtocolChunk) ON EACH [n.text];",
        "CREATE FULLTEXT INDEX clinicalChunkTextIndex IF NOT EXISTS FOR (n:ClinicalChunk) ON EACH [n.text];",
        
        # [NEW/UPDATED] Advanced Metadata & Methods
        "CREATE FULLTEXT INDEX protocolTextIndex IF NOT EXISTS FOR (n:Protocol) ON EACH [n.title];",      
        "CREATE FULLTEXT INDEX topicTextIndex IF NOT EXISTS FOR (n:Topic) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX studyDesignTextIndex IF NOT EXISTS FOR (n:StudyDesign) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX experimentTextIndex IF NOT EXISTS FOR (n:Experiment) ON EACH [n.method];", 
        "CREATE FULLTEXT INDEX categoryLeafTextIndex IF NOT EXISTS FOR (n:CategoryLeaf) ON EACH [n.name];"
    ]

class GraphSearchQueries:
    """
    [검색 단계] 라우터가 결정한 도메인에 대해 'Chunk ID'를 찾아오는 쿼리들
    
    분류 기준:
    1. SEARCH (기본): 질문에 대한 답을 찾기 위해 Hybrid(Vector + Keyword) 검색 수행
    2. FILTER/LIST: 메타데이터(연도, 저널명 등) 기반의 정형적 목록 조회
    """

    # ==========================================================================
    # 1. SEARCH: Hybrid Search (Default)
    # - 모든 일반적인 질문은 이 쿼리를 사용합니다.
    # - Dual RRF (Vector Score + Fulltext Score) 알고리즘 적용
    # ==========================================================================

    SEARCH_PAPER_HYBRID = """
        // -------------------------------------------------------------------------
        // 1) Vector & Text Search (기본 내용 검색)
        //    - 임베딩(Vector)과 본문 키워드(Text)를 동시에 찾습니다.
        // -------------------------------------------------------------------------
        CALL {
            WITH $embedding AS embedding, $q AS q
            
            // (1-A) Vector Search
            CALL db.index.vector.queryNodes('chunk_vector_index', 150, embedding)
            YIELD node AS c, score AS vec_score
            RETURN c.chunk_id AS chunk_id, vec_score, 0.0 AS ft_score, 0.0 AS graph_score
            
            UNION
            
            // (1-B) Chunk Text Search
            CALL db.index.fulltext.queryNodes('chunkTextIndex', q) 
            YIELD node AS c, score AS ft_score
            RETURN c.chunk_id AS chunk_id, 0.0 AS vec_score, ft_score, 0.0 AS graph_score
        }

        UNION

        // -------------------------------------------------------------------------
        // 2) Graph Context Search (Entity & Metadata 통합)
        //    - Entity, Journal, Topic, StudyDesign 등 "연결된 노드"를 통해 찾습니다.
        // -------------------------------------------------------------------------
        CALL {
            WITH $q AS q
            
            // (2-A) Entity Path: Entity -> Mention -> Section -> Chunk
            CALL db.index.fulltext.queryNodes('entityTextIndex', q) YIELD node AS e, score
            MATCH (e)<-[:NORMALIZED_TO]-(:Mention)<-[:HAS_MENTION]-(:Section)-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.chunk_id AS chunk_id, score AS graph_score
            
            UNION
            
            // (2-B) Metadata Path: [Journal, Topic, Design] -> Article -> Chunk
            // * 핵심: 인덱스 목록을 순회하며 '연결된 Article'을 공통 패턴으로 찾음
            UNWIND ['journalTextIndex', 'topicTextIndex', 'studyDesignTextIndex'] AS idxName
            CALL db.index.fulltext.queryNodes(idxName, q) YIELD node, score
            
            // "검색된 노드(Journal/Topic/Design)와 연결된(--) Article 찾기"
            MATCH (node)<--(a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.chunk_id AS chunk_id, score AS graph_score
        }
        // (Vector/Text 블록과 컬럼 맞추기)
        RETURN chunk_id, 0.0 AS vec_score, 0.0 AS ft_score, graph_score

        // -------------------------------------------------------------------------
        // 3) Score Aggregation & Reranking
        // -------------------------------------------------------------------------
        WITH chunk_id, 
            max(vec_score) AS vec_score, 
            max(ft_score) AS ft_score, 
            max(graph_score) AS graph_score
        
        // 점수 가중치 조절 (그래프/메타데이터 매칭은 정확도가 높으므로 가산점 부여 가능)
        WITH chunk_id, (vec_score + ft_score + graph_score * 1.2) AS hy_score
        
        MATCH (c:Chunk {chunk_id: chunk_id})
        RETURN c.chunk_id AS chunk_id, hy_score
        ORDER BY hy_score DESC
        LIMIT coalesce($k, 50)
        """

    SEARCH_PROTOCOL_HYBRID = """
    // =========================================================================
    // 1. Direct Search (Vector + Text)
    //    - 이미 효율적이므로 유지하되, 리턴 컬럼만 통일
    // =========================================================================
    CALL {
        WITH $embedding AS embedding, $q AS q
        // (1-A) Vector Search
        CALL db.index.vector.queryNodes('protocol_chunk_vector_index', 150, embedding)
        YIELD node AS pc, score AS vec_score
        RETURN pc.chunking_id AS id, vec_score, 0.0 AS ft_score, 0.0 AS graph_score, 'protocol' AS type
        
        UNION
        
        // (1-B) Text Search (Chunk Body + Protocol Title)
        CALL {
            WITH q
            CALL db.index.fulltext.queryNodes('protocolChunkTextIndex', q) YIELD node AS pc, score RETURN pc, score
            UNION
            CALL db.index.fulltext.queryNodes('protocolTextIndex', q) YIELD node AS p, score
            MATCH (p)-[:HAS_CHUNK]->(pc:ProtocolChunk) RETURN pc, score
        }
        RETURN pc.chunking_id AS id, 0.0 AS vec_score, score AS ft_score, 0.0 AS graph_score, 'protocol' AS type
    }

    UNION

    // =========================================================================
    // 2. Graph Context Search (Optimized)
    //    - Strategy: [검색 -> 노드 수집 -> 중복 제거 -> 경로 확장]
    // =========================================================================
    CALL {
        WITH $q AS q
        
        // ---------------------------------------------------------------------
        // Step 1: Seed Node 발굴 (Fulltext Index Scan)
        // ---------------------------------------------------------------------
        CALL {
            WITH q
            // (A) Entity Index
            CALL db.index.fulltext.queryNodes('entityTextIndex', q) YIELD node, score RETURN node, score
            UNION
            // (B) Experiment / Metadata Indexes
            UNWIND ['experimentTextIndex', 'expMaterialTextIndex', 'expEquipmentTextIndex', 
                    'categoryLeafTextIndex', 'categoryParentTextIndex'] AS idxName
            CALL db.index.fulltext.queryNodes(idxName, q) YIELD node, score RETURN node, score
        }
        
        // [Optimization] 중복된 노드를 먼저 제거하여 확장 비용 최소화
        WITH DISTINCT node, max(score) AS node_score

        // ---------------------------------------------------------------------
        // Step 2: Path Expansion (Protocol & Paper 분리 실행)
        // ---------------------------------------------------------------------
        CALL {
            WITH node
            // Case A: Entity -> Protocol (Direct)
            MATCH (node:Entity)<-[:USED_METHOD]-(p:Protocol)-[:HAS_CHUNK]->(pc:ProtocolChunk)
            RETURN pc.chunking_id AS id, 'protocol' AS type
            
            UNION
            
            WITH node
            // Case B: Metadata -> Protocol (1~2 hops)
            // (Exp/Mat) -- (Protocol)  OR  (Mat) -- (Exp) -- (Protocol)
            MATCH (node)-[*1..2]-(p:Protocol)-[:HAS_CHUNK]->(pc:ProtocolChunk)
            RETURN pc.chunking_id AS id, 'protocol' AS type

            UNION
            
            WITH node
            // Case C: Experiment -> Entity -> Protocol (Method Sharing)
            MATCH (node:Experiment)-[:USED_METHOD]->(:Entity)<-[:USED_METHOD]-(p:Protocol)-[:HAS_CHUNK]->(pc:ProtocolChunk)
            RETURN pc.chunking_id AS id, 'protocol' AS type

            UNION
            
            WITH node
            // Case D: Metadata -> Paper (Article)
            // (Exp/Mat) -- (Article) -- (Section) -- (Chunk)
            MATCH (node)-[*1..2]-(a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
            RETURN c.chunk_id AS id, 'paper' AS type
        }
        
        RETURN id, node_score AS graph_score, type
    }

    // =========================================================================
    // 3. Aggregation (RRF Style)
    // =========================================================================
    WITH id, type,
        max(vec_score) AS vec_score,
        max(ft_score) AS ft_score,
        max(graph_score) AS graph_score
    
    // 최종 점수 계산 (Graph 점수에 가중치 1.2 부여)
    WITH id, type, (coalesce(vec_score, 0.0) + coalesce(ft_score, 0.0) + coalesce(graph_score, 0.0) * 1.2) AS hy_score
    
    RETURN id, hy_score, type
    ORDER BY hy_score DESC
    LIMIT coalesce($k, 50)
    """

    SEARCH_CLINICAL_HYBRID = """
    CALL {
        WITH $q AS q
        // 1. Entity(약물/질환) 기반 검색
        CALL db.index.fulltext.queryNodes('entityTextIndex', q) YIELD node AS e, score
        MATCH (e)<-[:HAS_ENTITY]-(t:ClinicalTrial)
        RETURN t, score
        
        UNION
        
        // 2. ClinicalTrial 직접 검색 (제목, ID)
        MATCH (t:ClinicalTrial)
        WHERE t.title CONTAINS q OR t.nct_id = q
        RETURN t, 1.0 AS score
    }
    
    // 3. 점수 집계 및 중복 제거
    WITH t, max(score) AS hy_score
    
    // 4. [Filtering] 메타데이터 기반 선택적 조회
    // 파라미터가 NULL이면 필터링하지 않음 (전체 조회)
    WHERE ($phase IS NULL OR t.phase = $phase)
    AND ($status IS NULL OR t.status = $status)
    AND ($year_from IS NULL OR (t.start_date IS NOT NULL AND t.start_date >= $year_from))
    
    // 5. 상위 결과 선정
    ORDER BY hy_score DESC, t.phase DESC
    LIMIT coalesce($k, 15)  // 상세 정보를 다 가져오므로 개수를 조금 줄임(예: 15개)

    // 6. [Assembly] 상세 정보 조회
    OPTIONAL MATCH (t)-[:HAS_ENTITY]->(e:Entity)
    WITH t, hy_score, collect(DISTINCT e.name) AS graph_entities

    RETURN 
        t.nct_id AS id,
        t.title AS title,
        t.summary AS summary,
        
        // 메타데이터
        t.phase AS phase,
        t.study_type AS study_type,
        t.status AS status,
        t.start_date AS start_date,
        
        // 리스트 데이터
        t.conditions AS conditions,
        t.interventions AS interventions,
        
        // 그래프 정보 및 점수
        graph_entities,
        hy_score,
        'ClinicalTrial_KG' AS type
    """

# ==========================================================================
    # 2. FILTER / LIST: Metadata Lookup & Similarity
    # - 기본 목록 조회: 상위 저널, 프로토콜
    # - 필터링 조회: 연도, Phase, 저널명 필터
    # - [NEW] 연관성 조회: 유사 논문 추천, 관련 실험법 추천
    # ==========================================================================

    # ==========================================================================
    # 2. FILTER / LIST: Metadata & Graph Relation Lookup
    # ==========================================================================

    # 1) [Updated] 논문 필터 검색 (도메인, 연구타입 포함)
    FILTER_ARTICLES = """
    MATCH (a:Article)
    OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
    OPTIONAL MATCH (a)-[:HAS_DOMAIN]->(d:Domain)
    OPTIONAL MATCH (a)-[:HAS_DESIGN]->(sd:StudyDesign)
    
    WITH a, j, d, sd
    WHERE
    ($year_from IS NULL OR a.year >= $year_from)
    AND ($year_to IS NULL OR a.year <= $year_to)
    AND ($journal IS NULL OR toLower(j.name) CONTAINS toLower($journal))
    AND ($domain IS NULL OR toLower(d.name) CONTAINS toLower($domain))
    AND ($study_type IS NULL OR toLower(sd.name) CONTAINS toLower($study_type))
    
    RETURN
    a { .pmid, .doi, .title, .year } AS article,
    j.name AS journal,
    d.name AS domain,
    sd.name AS study_design
    ORDER BY coalesce(a.year, 0) DESC
    LIMIT coalesce($k, 50)
    """
    # 2) [Updated] 프로토콜 필터 검색 (계층 구조 및 장비 필터 적용)
    # Q: "Genetics($category) 카테고리의 PCR($method) 프로토콜 중 
    #     Thermocycler($equipment)를 쓰는 것만 보여줘"
    FILTER_PROTOCOLS = """
    MATCH (p:Protocol)
    
    // [Hierarchy Path] 카테고리 필터링을 위해 상위 노드 연결
    // Parent(대분류) -> Leaf(소분류) -> Protocol
    OPTIONAL MATCH (parent:CategoryParent)-[:HAS_LEAF]->(leaf:CategoryLeaf)-[:HAS_PROTOCOL]->(p)
    
    // [Entity Path] 방법 및 장비 필터링을 위해 Entity 연결
    OPTIONAL MATCH (p)-[:USED_METHOD]->(e:Entity)
    
    WITH p, parent, leaf, collect(toLower(e.name)) AS entity_names
    
    WHERE
      // 1. 기본 키워드 검색
    ($keyword IS NULL OR toLower(p.title) CONTAINS toLower($keyword))
    
      // 2. 카테고리 필터 (대분류 또는 소분류 이름 확인)
    AND ($category IS NULL OR 
        toLower(parent.name) CONTAINS toLower($category) OR 
        toLower(leaf.name) CONTAINS toLower($category))
      // 3. 실험 방법 필터 (연결된 Entity 이름 확인)
    AND ($method IS NULL OR any(name IN entity_names WHERE name CONTAINS toLower($method)))
    
      // 4. 장비 필터 (연결된 Entity 이름 확인 - 장비명도 Entity로 등록된 경우)
    AND ($equipment IS NULL OR any(name IN entity_names WHERE name CONTAINS toLower($equipment)))

    RETURN 
        p { 
            .protocol_sid, 
            .title, 
            .usage_degree 
        } AS protocol,
        
        // 카테고리 정보 반환
        { 
            parent: parent.name, 
            leaf: leaf.name 
        } AS category_info,
        
        // 연관된 방법/장비 리스트 (상위 5개)
        entity_names[0..5] AS related_entities
        
    ORDER BY coalesce(p.usage_degree, 0) DESC
    LIMIT coalesce($k, 30)
    """
    # 2) [Updated] 임상시험 필터 검색 (상세 조건 대거 추가)
    # - Status, StudyType, Condition(질환), Intervention(약물) 필터링 지원
    FILTER_TRIALS = """
    MATCH (t:ClinicalTrial)
    WHERE
      // 1. 기본 필터 (단계, 연도)
    ($phase IS NULL OR t.phase = $phase)
    AND ($year_from IS NULL OR (t.start_date IS NOT NULL AND t.start_date >= $year_from))

      // 2. 상태 및 유형 필터 (예: 'Recruiting', 'Interventional')
    AND ($status IS NULL OR toLower(t.status) = toLower($status))
    AND ($study_type IS NULL OR toLower(t.study_type) = toLower($study_type))

      // 3. 리스트 필터 (Conditions / Interventions)
      // * 리스트 안에 해당 검색어가 포함되어 있는지 확인 (Case-insensitive)
    AND ($condition IS NULL OR 
        any(c IN t.conditions WHERE toLower(c) CONTAINS toLower($condition)))
    AND ($intervention IS NULL OR 
        any(i IN t.interventions WHERE toLower(i) CONTAINS toLower($intervention)))

    RETURN 
        t { 
            .nct_id, 
            .title, 
            .phase, 
            .status, 
            .start_date,
            .conditions, 
            .interventions 
        } AS trial
    ORDER BY t.start_date DESC
    LIMIT coalesce($k, 50)
    """

    # --------------------------------------------------------------------------
    # [NEW] Similarity & Recommendation Queries
    # --------------------------------------------------------------------------

    # 3) 유사 논문 추천 (Topic 기반)
    LIST_SIMILAR_ARTICLES = """
    MATCH (target:Article)
    WHERE target.title CONTAINS $q
    MATCH (target)-[:HAS_TOPIC]->(t:Topic)<-[:HAS_TOPIC]-(other:Article)
    WHERE other.pmid <> target.pmid
    
    WITH other, count(t) AS shared_cnt, collect(t.name) AS topics
    ORDER BY shared_cnt DESC
    LIMIT coalesce($k, 10)

    RETURN 
        other { .title, .year, .doi } AS node,
        { type: 'HAS_COMMON_TOPIC', shared_topics: topics } AS relationship,
        shared_cnt AS score
    """

    # 4) [NEW] 유사 임상연구 추천 (Entity 공유 기반)
    # Q: "이 임상시험(NCT ID or Title)이랑 비슷한 설계나 약물을 쓰는 연구는?"
    LIST_SIMILAR_TRIALS = """
    // 1. 타겟 임상시험 찾기
    MATCH (target:ClinicalTrial)
    WHERE target.nct_id = $q OR target.title CONTAINS $q

    // 2. 공유하는 Entity 찾기 (약물, 질환, 바이오마커 등)
    MATCH (target)-[:HAS_ENTITY]->(e:Entity)<-[:HAS_ENTITY]-(other:ClinicalTrial)
    WHERE target.nct_id <> other.nct_id
    
    // 3. 공유 개수 집계
    WITH other, count(e) AS shared_cnt, collect(e.name)[0..5] AS shared_entities
    ORDER BY shared_cnt DESC
    LIMIT coalesce($k, 10)

    RETURN 
        other { 
            .nct_id, 
            .title, 
            .phase, 
            .status 
        } AS node,
        
        // 어떤 요소(Entity)들이 겹쳐서 유사하다고 판단했는지 근거 제공
        { 
            type: 'SHARED_ENTITIES', 
            entities: shared_entities,
            count: shared_cnt 
        } AS relationship,
        
        shared_cnt AS score
    """

    # 5) 유사/관련 실험 방법 추천 (Co-occurrence)
    LIST_RELATED_METHODS = """
    CALL db.index.fulltext.queryNodes('entityTextIndex', $q) YIELD node AS target, score
    MATCH (target)<-[:USED_METHOD]-(context)-[:USED_METHOD]->(related:Entity)
    WHERE related <> target
    WITH related, labels(context)[0] AS ctx_type, count(context) AS co_occurs
    RETURN 
        related { .name, .type } AS node,
        { type: 'CO_OCCURRENCE', context: ctx_type } AS relationship,
        co_occurs AS score
    ORDER BY score DESC LIMIT coalesce($k, 15)
    """


    # 7) 논문에서 사용된 실험 방법 조회 (Source 구분 포함)
    LIST_ARTICLE_METHODS = """
    MATCH (a:Article)
    WHERE a.title CONTAINS $q
    
    // Path 1: Graph상 Experiment 노드로 연결된 경우 (강한 연결)
    OPTIONAL MATCH (a)-[r1:HAS_EXPERIMENT]->(exp:Experiment)
    
    // Path 2: 텍스트에서 언급(Mention)된 경우 (약한 연결)
    OPTIONAL MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(m:Mention)-[:NORMALIZED_TO]->(e:Entity)
    
    WITH a, exp, e
    
    // 데이터를 리스트로 병합
    WITH a,
        // (1) Experiment 노드 정보
        collect(DISTINCT CASE WHEN exp IS NOT NULL THEN {
            name: exp.method,
            category: 'Experiment_Node',
            properties: exp { .material, .equipment }, // 실험 장비/재료 정보 포함
            relation: 'HAS_EXPERIMENT'
        } END) AS exp_list,
        
        // (2) Entity 언급 정보
        collect(DISTINCT CASE WHEN e IS NOT NULL THEN {
            name: e.name,
            category: 'Text_Mention',
            properties: { type: e.type },
            relation: 'MENTIONED_IN_SECTION'
        } END) AS entity_list
    
    // NULL 제거 및 통합 반환
    WITH a, [x IN (exp_list + entity_list) WHERE x IS NOT NULL] AS all_methods
    
    RETURN 
        a.title AS article_title,
        all_methods AS found_methods
    """
# 1) Paper Search (Hybrid + Graph Context + PrimeKG Expansion)
    SEARCH_KG_PAPER_HYBRID = """
    // -------------------------------------------------------------------------
    // 1. Vector & Text Search (기본 내용 검색)
    // -------------------------------------------------------------------------
    CALL {
        WITH $embedding AS embedding, $q AS q
        // (1-A) Vector
        CALL db.index.vector.queryNodes('chunk_vector_index', 150, embedding)
        YIELD node AS c, score AS vec_score
        RETURN c.chunk_id AS chunk_id, vec_score, 0.0 AS ft_score, 0.0 AS graph_score
        
        UNION
        
        // (1-B) Fulltext
        CALL db.index.fulltext.queryNodes('chunkTextIndex', q) 
        YIELD node AS c, score AS ft_score
        RETURN c.chunk_id AS chunk_id, 0.0 AS vec_score, ft_score, 0.0 AS graph_score
    }

    UNION

    // -------------------------------------------------------------------------
    // 2. Graph Context Search (Entity + Metadata + KG Expansion)
    // -------------------------------------------------------------------------
    CALL {
        WITH $q AS q
        
        // (2-A) Direct Entity Path: 검색된 Entity가 포함된 Chunk
        CALL db.index.fulltext.queryNodes('entityTextIndex', q) YIELD node AS e, score
        MATCH (e)<-[:NORMALIZED_TO]-(:Mention)<-[:HAS_MENTION]-(:Section)-[:HAS_CHUNK]->(c:Chunk)
        RETURN c.chunk_id AS chunk_id, score AS graph_score
        
        UNION
        
        // (2-B) Metadata Path: Journal, Topic, StudyDesign 등 연결된 Chunk
        UNWIND ['journalTextIndex', 'topicTextIndex', 'studyDesignTextIndex'] AS idxName
        CALL db.index.fulltext.queryNodes(idxName, q) YIELD node, score
        MATCH (node)<--(a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
        RETURN c.chunk_id AS chunk_id, score AS graph_score

        UNION

        // (2-C) [NEW] PrimeKG Expansion Path
        // Logic: 검색어 -> Entity -> (PrimeKG Neighbor) -> Neighbor Entity -> Chunk
        CALL db.index.fulltext.queryNodes('entityTextIndex', q) YIELD node AS seed, score
        
        // PrimeKG 상에서 1-hop 이웃 찾기
        MATCH (seed)-[:MAPS_TO_PRIMEKG]->(:BaseNode)--(:BaseNode)<-[:MAPS_TO_PRIMEKG]-(neighbor:Entity)
        
        // 이웃 Entity가 언급된 Chunk 찾기
        MATCH (neighbor)<-[:NORMALIZED_TO]-(:Mention)<-[:HAS_MENTION]-(:Section)-[:HAS_CHUNK]->(c:Chunk)
        
        // * 가중치 조정: 간접 연결이므로 점수를 0.7배로 낮춤
        RETURN c.chunk_id AS chunk_id, (score * 0.7) AS graph_score
    }

    // -------------------------------------------------------------------------
    // 3. Score Aggregation
    // -------------------------------------------------------------------------
    WITH chunk_id, 
         max(vec_score) AS vs, 
         max(ft_score) AS fs, 
         max(graph_score) AS gs
    
    // 최종 점수 합산 (그래프 점수에 가중치 1.2 부여)
    WITH chunk_id, (coalesce(vs,0.0) + coalesce(fs,0.0) + coalesce(gs,0.0) * 1.2) AS hy_score
    
    MATCH (c:Chunk {chunk_id: chunk_id})
    RETURN c.chunk_id AS chunk_id, hy_score
    ORDER BY hy_score DESC
    LIMIT coalesce($k, 50)
    """
    # 3) Clinical Search (Metadata + KG Entity + PrimeKG Expansion)
    SEARCH_KG_CLINICAL_HYBRID = """
    CALL {
        WITH $q AS q
        
        // (1) Direct Entity Search (기존)
        // 검색어와 정확히 매칭되는 Entity(약물/질환)가 포함된 임상시험
        CALL db.index.fulltext.queryNodes('entityTextIndex', q) YIELD node AS e, score
        MATCH (e)<-[:HAS_ENTITY]-(t:ClinicalTrial)
        RETURN t, score
        
        UNION
        
        // (2) Direct Metadata Search (기존)
        // 제목이나 NCT ID에 검색어가 포함된 임상시험
        MATCH (t:ClinicalTrial)
        WHERE t.title CONTAINS q OR t.nct_id = q
        RETURN t, 1.0 AS score

        UNION

        // (3) [NEW] PrimeKG Expansion Path
        // Logic: 검색어 -> Seed Entity -> (PrimeKG Neighbor) -> Neighbor Entity -> ClinicalTrial
        CALL db.index.fulltext.queryNodes('entityTextIndex', q) YIELD node AS seed, score
        
        // PrimeKG 상에서 이웃 찾기 (예: 'Lung Cancer' -> 'Cisplatin')
        MATCH (seed)-[:MAPS_TO_PRIMEKG]->(:BaseNode)--(:BaseNode)<-[:MAPS_TO_PRIMEKG]-(neighbor:Entity)
        
        // 이웃 Entity가 포함된 임상시험 찾기
        MATCH (neighbor)<-[:HAS_ENTITY]-(t:ClinicalTrial)
        
        // * 가중치 조정: 간접 연결이므로 점수 0.7배
        RETURN t, (score * 0.7) AS score
    }
    
    // -------------------------------------------------------------------------
    // 4. Aggregation & Filtering
    // -------------------------------------------------------------------------
    WITH t, max(score) AS hy_score
    
    // 필터링 적용 (Phase, Status, Year)
    WHERE ($phase IS NULL OR t.phase = $phase)
      AND ($status IS NULL OR t.status = $status)
      AND ($year_from IS NULL OR (t.start_date IS NOT NULL AND t.start_date >= $year_from))
    
    // 정렬 및 상위 N개 선정
    ORDER BY hy_score DESC, t.phase DESC
    LIMIT coalesce($k, 15)
    
    // -------------------------------------------------------------------------
    // 5. Assembly (상세 정보 조회)
    // -------------------------------------------------------------------------
    OPTIONAL MATCH (t)-[:HAS_ENTITY]->(e:Entity)
    WITH t, hy_score, collect(DISTINCT e.name) AS graph_entities

    RETURN 
        t.nct_id AS id,
        t.title AS title,
        t.summary AS summary,
        
        // 메타데이터
        t.phase AS phase,
        t.study_type AS study_type,
        t.status AS status,
        t.start_date AS start_date,
        
        // 리스트 데이터
        t.conditions AS conditions,
        t.interventions AS interventions,
        
        // 그래프 정보 및 점수
        graph_entities,
        hy_score,
        'ClinicalTrial_KG' AS type
    """

class GraphCellQueries:
    """
    [조립 단계] 검색된 ID들을 기반으로 LLM이 읽을 문맥(Context)을 생성
    - 텍스트 청크(Chunk) + 그래프 메타데이터(Graph Info)를 함께 반환하여 답변 품질 향상
    """


    # ==========================================================================
    # 1. Paper Assembly (Text + Meta + Optional PrimeKG)
    # ==========================================================================
    ASSEMBLY_PAPER = """
    WITH $chunk_ids AS chunk_ids
    MATCH (c:Chunk) WHERE c.chunk_id IN chunk_ids
    MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c)
    WITH DISTINCT a LIMIT 10
    
    // 1. [Graph Context] 논문 메타데이터
    OPTIONAL MATCH (a)-[:HAS_TOPIC]->(t:Topic)
    OPTIONAL MATCH (a)-[:HAS_EXPERIMENT]->(exp:Experiment)
    OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
    OPTIONAL MATCH (a)-[:HAS_DOMAIN]->(d:Domain)
    OPTIONAL MATCH (a)-[:HAS_DESIGN]->(sd:StudyDesign)
    
    // 2. [PrimeKG Context] 조건부 실행 (Flag가 True일 때만 수행)
    CALL {
        WITH a
        // (1) Guard Clause: 파라미터가 True인지 확인. 아니면 즉시 종료(OPTIONAL MATCH가 null 반환)
        OPTIONAL MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e:Entity)
        WHERE coalesce($include_primekg, false) = true
        
        WITH DISTINCT e LIMIT 5
        
        // (2) PrimeKG 탐색 (Entity가 존재할 때만 실행됨)
        OPTIONAL MATCH (e)-[:MAPS_TO_PRIMEKG]->(p:BaseNode)-[r]-(nbr:BaseNode)
        
        // (3) 결과 수집 (null 제외)
        WITH e, r, nbr
        WHERE e IS NOT NULL AND nbr IS NOT NULL
        
        RETURN collect(DISTINCT {
            source: e.name,
            relation: type(r),
            target: nbr.name
        })[0..10] AS primekg_facts
    }
    
    WITH a, j, primekg_facts,
         collect(DISTINCT t.name)[0..3] AS topics,
         collect(DISTINCT exp.method)[0..5] AS exps,
         collect(DISTINCT d.name)[0..3] AS domains,
         collect(DISTINCT sd.name)[0..3] AS designs
    
    // 3. [Text Context] 본문 청크
    CALL { 
        WITH a 
        MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(ac:Chunk) 
        WITH ac ORDER BY ac.chunk_id ASC
        RETURN collect(ac{.text, .chunk_id})[0..5] AS chunks 
    }
    
    RETURN 
        a { .title, .year, .doi, .abstract } AS doc,
        j.name AS source,
        'Paper' AS type,
        
        {
            topics: topics,
            experiments: exps,
            domains: domains,
            designs: designs,
            // Flag가 False면 빈 리스트([])가 반환됨
            primekg_insights: coalesce(primekg_facts, [])
        } AS graph_context,
        
        chunks AS evidence_chunks
    """

    # ==========================================================================
    # 2. Protocol Assembly (Text + Meta + Optional PrimeKG)
    # ==========================================================================
    ASSEMBLY_PROTOCOL = """
    WITH $chunk_ids AS chunk_ids
    MATCH (pc:ProtocolChunk) WHERE pc.chunking_id IN chunk_ids
    MATCH (p:Protocol)-[:HAS_CHUNK]->(pc)
    WITH DISTINCT p LIMIT 10
    
    // 1. [Graph Context] 카테고리 및 Entity
    OPTIONAL MATCH (parent:CategoryParent)-[:HAS_LEAF]->(leaf:CategoryLeaf)-[:HAS_PROTOCOL]->(p)
    OPTIONAL MATCH (p)-[:USED_METHOD]->(e:Entity)
    
    // 2. [PrimeKG Context] 조건부 실행
    CALL {
        WITH p
        // (1) Guard Clause & Entity Fetch
        OPTIONAL MATCH (p)-[:USED_METHOD]->(e:Entity)
        WHERE coalesce($include_primekg, false) = true
        
        WITH DISTINCT e LIMIT 5
        
        // (2) PrimeKG 탐색
        OPTIONAL MATCH (e)-[:MAPS_TO_PRIMEKG]->(:BaseNode)-[r]-(nbr:BaseNode)
        
        // (3) 결과 수집
        WITH e, r, nbr
        WHERE e IS NOT NULL AND nbr IS NOT NULL
        
        RETURN collect(DISTINCT {
            source: e.name,
            relation: type(r),
            target: nbr.name
        })[0..10] AS primekg_facts
    }
    
    WITH p, primekg_facts,
         collect(DISTINCT parent.name) + collect(DISTINCT leaf.name) AS categories,
         collect(DISTINCT e.name)[0..5] AS entities
    
    // 3. [Text Context]
    CALL { 
        WITH p 
        MATCH (p)-[:HAS_CHUNK]->(apc:ProtocolChunk) 
        RETURN collect(apc{.text, chunk_id: apc.chunking_id})[0..5] AS chunks 
    }
    
    RETURN 
        p { .title, .protocol_sid, .usage_degree } AS doc,
        'Protocol' AS type,
        {
            categories: categories,
            entities: entities,
            primekg_insights: coalesce(primekg_facts, [])
        } AS graph_context,
        chunks AS evidence_chunks
    """

    # ==========================================================================
    # 3. Clinical Assembly (Meta + Optional PrimeKG)
    # ==========================================================================
    ASSEMBLY_CLINICAL_KG = """
    WITH $trial_ids AS trial_ids
    MATCH (t:ClinicalTrial) WHERE t.nct_id IN trial_ids OR t.trial_id IN trial_ids
    WITH DISTINCT t LIMIT 10
    
    // 1. [Graph Context] 연결된 약물/질환
    OPTIONAL MATCH (t)-[:HAS_ENTITY]->(e:Entity)
    
    // 2. [PrimeKG Context] 조건부 실행
    CALL {
        WITH t
        // (1) Guard Clause & Entity Fetch
        OPTIONAL MATCH (t)-[:HAS_ENTITY]->(e:Entity)
        WHERE coalesce($include_primekg, false) = true
        
        WITH DISTINCT e LIMIT 5
        
        // (2) PrimeKG 탐색
        OPTIONAL MATCH (e)-[:MAPS_TO_PRIMEKG]->(:BaseNode)-[r]-(nbr:BaseNode)
        
        // (3) 결과 수집
        WITH e, r, nbr
        WHERE e IS NOT NULL AND nbr IS NOT NULL
        
        RETURN collect(DISTINCT {
            source: e.name,
            relation: type(r),
            target: nbr.name
        })[0..10] AS primekg_facts
    }

    WITH t, primekg_facts, collect(DISTINCT e.name)[0..5] AS entities
    
    RETURN 
        t.nct_id AS id,
        t.title AS title,
        t.summary AS summary,
        t.phase AS phase,
        t.status AS status,
        t.study_type AS study_type,
        t.start_date AS start_date,
        t.conditions AS conditions,
        t.interventions AS interventions,
        
        // PrimeKG 정보 포함
        {
            entities: entities,
            primekg_insights: coalesce(primekg_facts, [])
        } AS graph_context,
        
        'ClinicalTrial_KG' AS type
    ORDER BY t.phase DESC
    LIMIT coalesce($limit_docs, 10)
    """