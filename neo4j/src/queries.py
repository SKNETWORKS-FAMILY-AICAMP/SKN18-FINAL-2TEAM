# src/queries.py

class PrimeKGQueries:

    """
    PrimeKG 데이터 로딩을 위한 Cypher 쿼리 저장소
    """

    # 1. 제약 조건 (인덱스) 생성
    # 검색 속도 향상 및 중복 방지를 위해 필수
    # IF NOT EXISTS를 사용하여 이미 존재하는 경우 오류 방지
    # 참고: n.id는 중복될 수 있으므로 UNIQUE 제약 조건 제거
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:BaseNode) REQUIRE n.node_index IS UNIQUE;",
        # n.id는 중복 가능하므로 UNIQUE 제약 조건 제거
        # "CREATE CONSTRAINT IF NOT EXISTS FOR (n:BaseNode) REQUIRE n.id IS UNIQUE;"
    ]

    # 2. 노드 로딩 (nodes.csv)
    # node_index가 모두 고유하므로 CREATE 사용 (MERGE보다 빠름)
    # node_index는 UNIQUE 제약 조건이 있으므로 중복 체크 불필요
    # 모든 CSV 컬럼 정보 저장: node_index, node_id, node_type, node_name, node_source
    LOAD_NODES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row RETURN row",
    "
      // node_type(예: gene/protein)을 라벨 포맷(GeneProtein)으로 변환
    WITH row, apoc.text.capitalizeAll(replace(row.node_type, '/', '_')) as label
    
      // node_index가 고유하므로 CREATE 사용 (MERGE보다 빠름)
      // 동적 라벨 + BaseNode 라벨 생성
      // 모든 CSV 컬럼 정보를 속성으로 저장
    CALL apoc.create.node([label, 'BaseNode'], {
        node_index: toInteger(row.node_index), 
        id: row.node_id,
        node_type: row.node_type, 
        name: row.node_name, 
        source: row.node_source
    }) YIELD node
    RETURN count(*)
    ",
    {batchSize: 1000, parallel: true}
    )
    """

# 3. 엣지(관계) 로딩 (edges.csv)
    # 수정: CSV의 모든 컬럼(relation, display_relation, x_index, y_index)을 엣지 속성으로 저장
    LOAD_EDGES = """
    CALL apoc.periodic.iterate(
      "LOAD CSV WITH HEADERS FROM 'file:///edges.csv' AS row RETURN row",
      "
      // 1. 관계 타입 포맷팅 (예: drug target -> DRUG_TARGET)
      WITH row, toUpper(replace(row.display_relation, ' ', '_')) as relType
      
      // 2. 출발/도착 노드 찾기
      MATCH (a:BaseNode {node_index: toInteger(row.x_index)})
      MATCH (b:BaseNode {node_index: toInteger(row.y_index)})
      
      // 3. 관계 생성 및 모든 속성 저장
      // {key: value} 형태로 4가지 정보를 모두 넣습니다.
      CALL apoc.create.relationship(a, relType, {
          relation: row.relation,
          display_relation: row.display_relation,
          x_index: toInteger(row.x_index), 
          y_index: toInteger(row.y_index)
      }, b) YIELD rel
      
      RETURN count(*)
      ",
      {batchSize: 1000, parallel: false}
    )
    """

# 4. 질병 상세 정보 업데이트 (disease_features.csv)
    # 수정: CSV의 모든 컬럼을 속성으로 저장하여 RAG 검색 범위 확장
    UPDATE_DISEASE_FEATURES = """
    CALL apoc.periodic.iterate(
      "LOAD CSV WITH HEADERS FROM 'file:///disease_features_cleaned.csv' AS row RETURN row",
      "
      MATCH (n:BaseNode {node_index: toInteger(row.node_index)})
      SET 
          // 1. 식별자 및 이름
          n.mondo_id = row.mondo_id,
          n.mondo_name = row.mondo_name,
          
          // 2. 그룹 정보 (BERT)
          n.group_id_bert = row.group_id_bert,
          n.group_name_bert = row.group_name_bert,
          
          // 3. 정의 및 설명 (Mondo, UMLS)
          n.mondo_definition = row.mondo_definition,
          n.umls_description = row.umls_description,
          
          // 4. Orphanet 희귀질환 정보
          n.orphanet_definition = row.orphanet_definition,
          n.orphanet_prevalence = row.orphanet_prevalence,
          n.orphanet_epidemiology = row.orphanet_epidemiology,
          n.orphanet_clinical_description = row.orphanet_clinical_description,
          n.orphanet_management_and_treatment = row.orphanet_management_and_treatment,
          
          // 5. Mayo Clinic 임상 정보 (RAG 핵심 데이터)
          n.mayo_symptoms = row.mayo_symptoms,
          n.mayo_causes = row.mayo_causes,
          n.mayo_risk_factors = row.mayo_risk_factors,
          n.mayo_complications = row.mayo_complications,
          n.mayo_prevention = row.mayo_prevention,
          n.mayo_see_doc = row.mayo_see_doc
      ",
      {batchSize: 1000, parallel: true}
    )
    """

    # 5. 약물 상세 정보 업데이트 (drug_features.csv)
    # 숫자 데이터 변환(toFloat) 포함
# 5. 약물 상세 정보 업데이트 (drug_features.csv)
    # node_index 매칭 후 전체 약물 특성 업데이트
    UPDATE_DRUG_FEATURES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///drug_features.csv' AS row RETURN row",
    "
    MATCH (n:BaseNode {node_index: toInteger(row.node_index)})
    SET 
        n.description = row.description,
        n.half_life = row.half_life,
        n.indication = row.indication,
        n.mechanism_of_action = row.mechanism_of_action,
        n.protein_binding = row.protein_binding,
        n.pharmacodynamics = row.pharmacodynamics,
        n.state = row.state,
        n.atc_1 = row.atc_1,
        n.atc_2 = row.atc_2,
        n.atc_3 = row.atc_3,
        n.atc_4 = row.atc_4,
        n.category = row.category,
        n.group = row.group,
        n.pathway = row.pathway,
        n.molecular_weight = toFloat(row.molecular_weight),
        n.tpsa = toFloat(row.tpsa),
        n.clogp = toFloat(row.clogp)
    ",
    {batchSize: 1000, parallel: true}
    )
    """

    # 6. 질병 그룹 정보 업데이트 (kg_grouped_diseases.csv)
    UPDATE_DISEASE_GROUPS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///kg_grouped_diseases.csv' AS row RETURN row",
    "
    MATCH (n:BaseNode {node_index: toInteger(row.node_id)})
    SET 
        n.group_name_bert = row.group_name_bert,
        n.group_name_auto = row.group_name_auto
    ",
    {batchSize: 1000, parallel: true}
    )
    """


class PaperRAGQueries:
    """
    article_cleaned.csv 및 section_meta.csv의 실제 컬럼 반영 쿼리셋
    """

    # 1. 제약 조건 & 인덱스 (기존 유지)
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT article_pmid IF NOT EXISTS FOR (n:Article) REQUIRE n.pmid IS UNIQUE;",
        "CREATE CONSTRAINT section_id IF NOT EXISTS FOR (n:Section) REQUIRE n.section_id IS UNIQUE;",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE;",
        "CREATE CONSTRAINT figure_id IF NOT EXISTS FOR (n:Figure) REQUIRE n.uid IS UNIQUE;",
        "CREATE CONSTRAINT table_id IF NOT EXISTS FOR (n:Table) REQUIRE n.uid IS UNIQUE;",
        "CREATE CONSTRAINT equation_id IF NOT EXISTS FOR (n:Equation) REQUIRE n.uid IS UNIQUE;",
        "CREATE CONSTRAINT reference_id IF NOT EXISTS FOR (n:Reference) REQUIRE n.uid IS UNIQUE;",
        "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE;",
        "CREATE CONSTRAINT keyword_word IF NOT EXISTS FOR (n:Keyword) REQUIRE n.word IS UNIQUE;",
        "CREATE CONSTRAINT study_design_name IF NOT EXISTS FOR (n:StudyDesign) REQUIRE n.name IS UNIQUE;"
    ]

    CREATE_VECTOR_INDEX = [
        """
        CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
        }}
        """
    ]

    # ... (LOAD_ARTICLES, LOAD_FIGURES, LOAD_TABLES, LOAD_EQUATIONS 등은 기존 article_cleaned.csv 기준 유지) ...
    # 편의를 위해 LOAD_SECTIONS만 수정된 버전을 강조하고 나머지는 생략하지 않고 포함합니다.

# src/queries.py

    LOAD_ARTICLES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///article_enriched.csv' AS row RETURN row",
    "
        MERGE (a:Article {pmid: toInteger(row.pmid)})
        SET a.pmcid = row.pmcid,
            a.title = row.title,
            a.doi = row.doi,
            a.year = toInteger(row.year),
            a.abstract = row.abstract,
            a.n_sections = toInteger(row.n_sections),
            a.n_equations = toInteger(row.n_equations),
            a.n_figures = toInteger(row.n_figures),
            a.n_tables = toInteger(row.n_tables),
            a.n_references = toInteger(row.n_references)

        // 1. Journal 연결
        FOREACH (ignoreMe IN CASE WHEN row.journal IS NOT NULL THEN [1] ELSE [] END |
            MERGE (j:Journal {name: row.journal}) 
            MERGE (a)-[:PUBLISHED_IN]->(j)
        )
        
        // 2. [대분류] Topic Category (기존 컬럼)
        FOREACH (ignoreMe IN CASE WHEN row.topic_category IS NOT NULL AND row.topic_category <> '' THEN [1] ELSE [] END |
            MERGE (t:Topic {name: row.topic_category})
            MERGE (a)-[:BELONGS_TO]->(t)
        )
        
        // 3. [상세] Detailed Topics (세미콜론 분리 -> Topic 노드 연결)
        // 예: 'Lung Cancer; Immunotherapy' -> 각각 별도 Topic 노드로 연결
        FOREACH (topic IN split(row.detailed_topics, ';') | 
            MERGE (dt:Topic {name: trim(topic)}) 
            MERGE (a)-[:BELONGS_TO]->(dt)
        )

        // 4. [대분류] Study Design (article_category 컬럼 활용)
        // 예: 'Research Article', 'Review' 등 큰 범주
        FOREACH (ignoreMe IN CASE WHEN row.article_category IS NOT NULL AND row.article_category <> '' THEN [1] ELSE [] END |
            MERGE (d:StudyDesign {name: row.article_category}) 
            MERGE (a)-[:HAS_DESIGN]->(d)
        )

        // 5. [상세] Detailed Design (세미콜론 분리 -> StudyDesign 노드 연결)
        // 예: 'In Vivo; Clinical Trial' -> 구체적인 실험 설계 연결
        FOREACH (design IN split(row.detailed_design, ';') | 
            MERGE (dd:StudyDesign {name: trim(design)}) 
            MERGE (a)-[:HAS_DESIGN]->(dd)
        )
    ", {batchSize: 1000, parallel: true})
    """

    LOAD_FIGURES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///figures.csv' AS row RETURN row",
    "
        MERGE (f:Asset:Figure {uid: row.fig_id})
        SET f.pmid = toInteger(row.pmid), f.label = row.fig_label, f.caption = row.fig_caption, f.url = row.fig_url
        WITH f, row MATCH (a:Article {pmid: toInteger(row.pmid)}) MERGE (a)-[:CONTAINS]->(f)
    ", {batchSize: 1000})
    """

    LOAD_TABLES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///tables.csv' AS row RETURN row",
    "
        MERGE (t:Asset:Table {uid: row.table_id})
        SET t.pmid = toInteger(row.pmid), t.label = row.table_label, t.caption = row.table_caption, t.url = row.table_url
        WITH t, row MATCH (a:Article {pmid: toInteger(row.pmid)}) MERGE (a)-[:CONTAINS]->(t)
    ", {batchSize: 1000})
    """

    LOAD_EQUATIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///equations.csv' AS row RETURN row",
    "
        MERGE (e:Asset:Equation {uid: row.equation_id})
        SET e.pmid = toInteger(row.pmid), e.expression = row.equation_rep, e.img_url = row.equation_img
        WITH e, row MATCH (a:Article {pmid: toInteger(row.pmid)}) MERGE (a)-[:CONTAINS]->(e)
    ", {batchSize: 1000})
    """

    # [핵심 수정] 섹션 로딩 (section_meta.csv 컬럼 반영)
    # 컬럼: section_id, pmid, topic_category, path, section_category, article_category, fig_ids, table_ids, section_title
    LOAD_SECTIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///section_meta.csv' AS row RETURN row",
    "
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        MERGE (s:Section {section_id: row.section_id})
        SET s.title = row.section_title,
            s.category = row.section_category,
            s.article_category = row.article_category, // 섹션에도 메타정보 저장
            s.topic_category = row.topic_category,     // 섹션에도 메타정보 저장
            s.path = row.path
        MERGE (a)-[:HAS_SECTION]->(s)
    ", {batchSize: 1000, parallel: false})
    """

    LOAD_CHUNKS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///embedding_new_v2.csv' AS row RETURN row",
    "
        MATCH (s:Section {section_id: row.section_id})
        MERGE (c:Chunk {chunk_id: row.chunk_id})
        SET c.text = row.text_chunk,
            c.seq = toInteger(row.chunk_seq),
            c.start_char = toInteger(row.start_char),
            c.end_char = toInteger(row.end_char),
            c.emb_model = row.emb_model,
            c.emb_dim = toInteger(row.emb_dim),
            c.embedding = apoc.convert.fromJsonList(row.embedding)
        MERGE (s)-[:HAS_CHUNK]->(c)
    ", {batchSize: 1000, parallel: true})
    """

    LINK_CHUNKS_NEXT = """
    CALL apoc.periodic.iterate(
    "MATCH (s:Section)-[:HAS_CHUNK]->(c) RETURN s, c ORDER BY s.section_id, c.seq",
    "
        WITH s, collect(c) as chunks
        FOREACH (i in range(0, size(chunks)-2) |
            FOREACH (c1 in [chunks[i]] |
                FOREACH (c2 in [chunks[i+1]] |
                    MERGE (c1)-[:NEXT]->(c2)
                )))
    ", {batchSize: 100, parallel: false})
    """
    LOAD_REFERENCES = """
        CALL apoc.periodic.iterate(
        "LOAD CSV WITH HEADERS FROM 'file:///references.csv' AS row RETURN row",
        "
            MATCH (source:Article {pmid: toInteger(row.pmid)})
            
            // 1. 개별 Reference 노드 (원본 보존용) - 항상 생성
            MERGE (ref:Reference {uid: row.ref_id})
            SET ref.title = row.ref_title, 
                ref.year = toInteger(row.ref_year),
                ref.journal = row.ref_journal
            MERGE (source)-[:HAS_BIBLIO]->(ref)

            // =========================================================
            // 2. [핵심] 통합 ID 생성 (우선순위 로직)
            // 가장 확실한 식별자 하나를 골라서 'master_key'로 삼습니다.
            // =========================================================
            WITH source, ref, row,
                CASE 
                    // (1) PMID가 있으면 무조건 이걸로 묶음
                    WHEN row.ref_pmid IS NOT NULL AND row.ref_pmid <> '' 
                    THEN 'pmid:' + row.ref_pmid
                    
                    // (2) PMID 없고 DOI 있으면 이걸로 묶음
                    WHEN row.ref_doi IS NOT NULL AND row.ref_doi <> '' 
                    THEN 'doi:' + row.ref_doi
                    
                    // (3) DOI도 없고 URL 있으면 이걸로 묶음
                    WHEN row.ref_url IS NOT NULL AND row.ref_url <> '' 
                    THEN 'url:' + row.ref_url
                    
                    // (4) [요청하신 부분] 다 없으면 '저널+제목(정규화)+년도'로 묶음
                    // 제목은 특수문자 제거된 title_norm을 쓰는 게 안전합니다.
                    WHEN row.ref_journal IS NOT NULL AND row.ref_title_norm IS NOT NULL AND row.ref_year IS NOT NULL 
                    THEN 'meta:' + toLower(trim(row.ref_journal)) + '_' + row.ref_title_norm + '_' + toString(row.ref_year)
                    
                    ELSE null 
                END as master_key

            // 키가 만들어진 경우에만 통합 노드 생성
            WHERE master_key IS NOT NULL

            // 3. 'CitedWork' (공통 문헌) 노드 병합
            // master_key가 같으면, 서로 다른 논문의 참고문헌이어도 이 노드 하나로 모입니다.
            MERGE (work:CitedWork {uid: master_key})
            ON CREATE SET 
                work.title = row.ref_title,
                work.year = toInteger(row.ref_year),
                work.doi = row.ref_doi,
                work.type = 'CitedWork'

            // 4. 연결: Reference(개별) -> CitedWork(공통)
            MERGE (ref)-[:POINTS_TO]->(work)
            
            // 5. (옵션) 논문 -> CitedWork 직접 연결 (분석 편의성)
            // 논문 A가 CitedWork B를 인용함 (이게 진짜 인용 네트워크)
            MERGE (source)-[:CITES_WORK]->(work)

    ", {batchSize: 2000})
    """


    # =========================================================================
    LOAD_ENTITIES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///entity_dedup.csv' AS row RETURN row",
    "
      // 1. Entity 노드 생성 (normalized_entity가 ID 역할)
    MERGE (e:Entity {name: row.normalized_entity})

      // 2. 메타데이터 설정
    SET e.type = row.entity_type,
        e.umls_cui = row.umls_cui,
        e.mapped_db = row.mapped_db,
        e.mapped_id = row.mapped_id,
        e.standard_name = row.standard_name,
        e.match_score = toFloat(row.match_score)
    ",
    {batchSize: 2000, parallel: true}
    )
    """

    # 17. 키워드 관계 연결 (기존 유지 - 파일명이 keyword_relation.csv 등이라면)
    LOAD_KEYWORDS_RELATION = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///section_keywords_v2.csv' AS row RETURN row",
    "
    MATCH (s:Section {section_id: row.section_id})
    MATCH (e:Entity {name: row.normalized_entity}) 
    MERGE (k:Keyword {word: row.raw_keyword})
    MERGE (s)-[:HAS_KEYWORD {score: toFloat(row.score)}]->(k)
    MERGE (k)-[:NORMALIZES_TO]->(e)
    ", {batchSize: 2000})
    """

    # (주의: 키워드/엔티티 관계 파일명이 정확해야 합니다. 위는 예시입니다.)

    # =========================================================================
    # [수정됨] 18. PrimeKG 지식 연결 (1차: 이름 기준)
    # 설명: Entity 이름과 BaseNode 이름이 정확히 같은 경우 연결
    # =========================================================================
    CONNECT_TO_PRIMEKG = """
    CALL apoc.periodic.iterate(
    "
    MATCH (e:Entity)
    WHERE NOT (e)-[:REFERS_TO]->(:BaseNode)
    RETURN e
    ",
    "
    MATCH (b:BaseNode {name: e.name})
    MERGE (e)-[:REFERS_TO]->(b)
    ",
    {batchSize: 1000, parallel: false}
    )
    """

    # =========================================================================
    # [신규] 19. PrimeKG 지식 연결 (2차: standard_name 기준)
    # 설명: 1차에서 연결 안 된 것들 중, standard_name이 BaseNode 이름과 같은 경우 연결
    # =========================================================================
    CONNECT_TO_PRIMEKG_SECONDARY = """
    CALL apoc.periodic.iterate(
    "
    MATCH (e:Entity)
    WHERE NOT (e)-[:REFERS_TO]->(:BaseNode) 
        AND e.standard_name IS NOT NULL
    RETURN e
    ",
    "
    MATCH (b:BaseNode {name: e.standard_name})
    MERGE (e)-[:REFERS_TO]->(b)
    ",
    {batchSize: 1000, parallel: false}
    )
    """

# 13. 실험(Experiment) 로딩 - paper_experiments_table.csv
    # Article과 직접 연결되도록 수정된 버전
    LOAD_EXPERIMENTS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///paper_experiments_table.csv' AS row RETURN row",
    "
        // 1) 기본 값 정리
        WITH
        row,
        toInteger(row.pmid) AS pmid_int,
        trim(row.method)    AS method,
        trim(row.condition) AS condition,
        trim(row.category_parent) AS cat_parent,
        trim(row.category_leaf)   AS cat_leaf,
        trim(row.materials)  AS materials,
        trim(row.equipment)  AS equipment,
          // 실험 고유 ID (문자열) 생성: pmid|method|condition
        toString(toInteger(row.pmid)) + '|' +
        coalesce(trim(row.method), '') + '|' +
        coalesce(trim(row.condition), '') AS exp_id

        // 2) 논문(Article) 찾아오기
        MATCH (a:Article {pmid: pmid_int})

        // 3) Experiment 노드 생성/업데이트
        MERGE (e:Experiment {experiment_id: exp_id})
        SET e.method    = method,
            e.condition = condition

        // Article - Experiment 관계
        MERGE (a)-[:HAS_EXPERIMENT]->(e)

        // 4) 카테고리 노드 생성 및 연결
        MERGE (cp:CategoryParent {name: cat_parent})
        MERGE (cl:CategoryLeaf   {name: cat_leaf})
        MERGE (cp)-[:HAS_LEAF]->(cl)
        MERGE (e)-[:HAS_PARENT_CATEGORY]->(cp)
        MERGE (e)-[:HAS_LEAF_CATEGORY]->(cl)

        // 5) 재료(Material) 노드/관계
        FOREACH (m IN CASE
                        WHEN materials IS NULL OR materials = '' THEN []
                        ELSE split(materials, ',')
                    END |
        MERGE (mat:Material {name: trim(m)})
        MERGE (e)-[:USES_MATERIAL]->(mat)
        )

        // 6) 장비(Equipment) 노드/관계
        FOREACH (eq IN CASE
                        WHEN equipment IS NULL OR equipment = '' THEN []
                        ELSE split(equipment, ',')
                    END |
        MERGE (equip:Equipment {name: trim(eq)})
        MERGE (e)-[:USES_EQUIPMENT]->(equip)
        )
    ",
    {batchSize: 1000, parallel: true}
    )
    """


class ProtocolQueries:
    """
    Protocol 데이터용 쿼리셋
    """
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT protocol_sid IF NOT EXISTS FOR (p:Protocol) REQUIRE p.protocol_sid IS UNIQUE;",
        "CREATE CONSTRAINT protocol_chunk_id IF NOT EXISTS FOR (c:ProtocolChunk) REQUIRE c.chunking_id IS UNIQUE;",
        "CREATE CONSTRAINT protocol_ref_sid IF NOT EXISTS FOR (r:ProtocolReference) REQUIRE r.reference_sid IS UNIQUE;"
    ]

    CREATE_VECTOR_INDEX = [
        """
        CREATE VECTOR INDEX protocol_chunk_vector_index IF NOT EXISTS
        FOR (c:ProtocolChunk) ON (c.embedding)
        OPTIONS {indexConfig: {
        `vector.dimensions`: 1024,
        `vector.similarity_function`: 'cosine'
        }}
        """
    ]

    LOAD_PROTOCOL_METADATA = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///t_protocol_metadata_Cell_labeled.csv' AS row RETURN row",
    "MERGE (p:Protocol {protocol_sid: row.protocol_sid})
     SET p.title = row.title, p.url = row.url, p.type = 'Protocol'
     MERGE (cp:CategoryParent {name: trim(row.category_parent)})
     MERGE (cl:CategoryLeaf {name: trim(row.category_leaf)})
     MERGE (cp)-[:HAS_LEAF]->(cl)
     MERGE (p)-[:HAS_PARENT_CATEGORY]->(cp)
     MERGE (p)-[:HAS_LEAF_CATEGORY]->(cl)",
    {batchSize: 1000, parallel: true}
    )
    """
    
    LOAD_PROTOCOL_MATERIALS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///t_protocol_materials_Cell.csv' AS row RETURN row",
    "MATCH (p:Protocol {protocol_sid: row.protocol_sid})
     MERGE (m:Material {name: trim(row.materials)})
     MERGE (p)-[:USES_MATERIAL]->(m)",
    {batchSize: 2000, parallel: false}
    )
    """

    LOAD_PROTOCOL_REFERENCES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///t_protocol_references_Cell.csv' AS row RETURN row",
    "MATCH (p:Protocol {protocol_sid: row.protocol_sid})
     MERGE (r:ProtocolReference {reference_sid: row.reference_sid})
     SET r.title = row.reference
     MERGE (p)-[:HAS_REFERENCE]->(r)",
    {batchSize: 2000, parallel: false}
    )
    """

    LOAD_PROTOCOL_CHUNKS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///embedded_vectors_bge_m3_dense.csv' AS row RETURN row",
    "MATCH (p:Protocol {protocol_sid: row.protocol_id})
     MERGE (c:ProtocolChunk {chunking_id: row.chunking_id})
     SET c.text = row.text, c.url = row.url, c.title = row.title,
         c.embedding = apoc.convert.fromJsonList(row.embedding)
     MERGE (p)-[:HAS_CHUNK]->(c)",
    {batchSize: 1000, parallel: true}
    )
    """
# src/queries.py (맨 아래에 추가)

class ClinicalTrialQueries:
    """
    ClinicalTrials.gov 데이터 로딩 및 연결 쿼리
    """
    
    # 1. 제약 조건
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT nct_id IF NOT EXISTS FOR (c:ClinicalTrial) REQUIRE c.nct_id IS UNIQUE;"
    ]

    # 2. 임상실험 메타데이터 로딩
    # 파일명: clinical_metadata.csv
    # 컬럼: nctId, officialTitle, briefSummary, conditions, keywords, interventions, ...
    LOAD_METADATA = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///nih_metadata1208.csv' AS row RETURN row",
    "
    MERGE (ct:ClinicalTrial {nct_id: row.nctId})
    SET ct.title = row.officialTitle,
        ct.summary = row.briefSummary,
        ct.study_type = row.studyType,
        ct.phase = row.phases,
        ct.status = row.overallStatus,
        ct.start_date = row.startDate,
        ct.completion_date = row.completionDate,
        ct.conditions = split(row.conditions, '|'),  // 구분자가 | 또는 , 인지 확인 필요 (여기선 | 가정)
        ct.keywords = split(row.keywords, '|'),
        ct.interventions = split(row.interventions, '|')
    ",
    {batchSize: 1000, parallel: true}
    )
    """

    # 3. 임상실험 엔티티 연결 (ClinicalTrial -> Entity)
    # 파일명: clinical_meta_entity.csv
    # 컬럼: nctId, entityName, entityType, score, ...
    # 핵심: 기존 Entity 노드와 이름(name)으로 병합하여 논문 데이터와 연결점 생성
    LOAD_CLINICAL_ENTITIES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///nih_mapped_metadata_entities_1208.csv' AS row RETURN row",
    "
    MATCH (ct:ClinicalTrial {nct_id: row.nctId})
    
      // 1. Entity 노드 병합 (논문에서 생성된 것과 동일한 이름이면 재사용)
    MERGE (e:Entity {name: row.entityName})
    ON CREATE SET 
        e.type = row.entityType, 
        e.source = 'ClinicalTrial' // 출처 표시 (기존에 없던 경우만)
    
      // 2. 관계 생성 (ClinicalTrial -> Entity)
    MERGE (ct)-[r:HAS_CLINICAL_ENTITY]->(e)
    SET r.score = toFloat(row.score),
        r.source_type = row.sourceType
    ",
    {batchSize: 2000, parallel: false}
    )
    """