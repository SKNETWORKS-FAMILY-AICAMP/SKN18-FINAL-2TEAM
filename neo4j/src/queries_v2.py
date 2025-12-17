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
        # core
        "CREATE CONSTRAINT article_pmid IF NOT EXISTS FOR (a:Article) REQUIRE a.pmid IS UNIQUE;",
        "CREATE CONSTRAINT section_id IF NOT EXISTS FOR (s:Section) REQUIRE s.section_id IS UNIQUE;",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;",

        # bibliographic
        "CREATE CONSTRAINT reference_id IF NOT EXISTS FOR (r:Reference) REQUIRE r.uid IS UNIQUE;",
        "CREATE CONSTRAINT citedwork_uid IF NOT EXISTS FOR (w:CitedWork) REQUIRE w.uid IS UNIQUE;",

        # entity / mention / keyword
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;",
        "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name);",
        "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type);",  # optional but useful
        "CREATE CONSTRAINT mention_id IF NOT EXISTS FOR (m:Mention) REQUIRE m.mention_id IS UNIQUE;",

        # topic / domain / journal / design
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE;",
        "CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (dom:Domain) REQUIRE dom.name IS UNIQUE;",
        "CREATE CONSTRAINT journal_name IF NOT EXISTS FOR (j:Journal) REQUIRE j.name IS UNIQUE;",
        "CREATE CONSTRAINT study_design_name IF NOT EXISTS FOR (sd:StudyDesign) REQUIRE sd.name IS UNIQUE;",

        # experiments (지금 로더가 생성함)
        "CREATE CONSTRAINT experiment_id IF NOT EXISTS FOR (ep:Experiment) REQUIRE ep.experiment_id IS UNIQUE;",
        "CREATE CONSTRAINT category_parent_name IF NOT EXISTS FOR (cp:CategoryParent) REQUIRE cp.name IS UNIQUE;",
        "CREATE CONSTRAINT category_leaf_name IF NOT EXISTS FOR (cl:CategoryLeaf) REQUIRE cl.name IS UNIQUE;",
        "CREATE CONSTRAINT material_name IF NOT EXISTS FOR (em:ExpMaterial) REQUIRE em.material_id IS UNIQUE;",
        "CREATE CONSTRAINT exp_equipment_id IF NOT EXISTS FOR (eq:ExpEquipment) REQUIRE eq.equipment_id IS UNIQUE;",

        # protocol
        "CREATE CONSTRAINT protocol_reference_sid_unique IF NOT EXISTS FOR (pr:ProtocolReference) REQUIRE pr.reference_sid IS UNIQUE;",
        "CREATE CONSTRAINT protocol_chunking_id_unique IF NOT EXISTS FOR (pc:ProtocolChunk) REQUIRE pc.chunking_id IS UNIQUE;",
        "CREATE CONSTRAINT protocol_sid_unique IF NOT EXISTS FOR (p:Protocol) REQUIRE p.protocol_sid IS UNIQUE;",
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
    "LOAD CSV WITH HEADERS FROM 'file:///ts_article_enriched.csv' AS row RETURN row",
    "
        MERGE (a:Article {pmid: toInteger(row.pmid)})
        SET a.title = row.title,
            a.journal = row.journal,
            a.year = toInteger(row.year),
            a.doi = row.doi,
            a.article_category = row.article_category,
            a.abstract = row.abstract,
            a.n_sections = toInteger(row.n_sections),
            a.n_equations = toInteger(row.n_equations),
            a.n_figures = toInteger(row.n_figures),
            a.n_tables = toInteger(row.n_tables),
            a.n_references = toInteger(row.n_references),
            a.title_norm = row.title_norm,
            a.abstract_summary = row.abstract_summary

        // 1. Journal 연결
        FOREACH (ignoreMe IN CASE WHEN row.journal IS NOT NULL THEN [1] ELSE [] END |
            MERGE (j:Journal {name: row.journal}) 
            MERGE (a)-[:PUBLISHED_IN]->(j)
        )
        

        // 2. Domain 연결 (도메인별 탐색용)
        FOREACH (ignoreMe IN CASE WHEN row.domain IS NOT NULL AND row.domain <> '' THEN [1] ELSE [] END |
            MERGE (dom:Domain {name: row.domain})
            MERGE (a)-[:IN_DOMAIN]->(dom)
        )

        // 3) [상세] Detailed Topics (detailed_topics)
        FOREACH (topic IN CASE
            WHEN row.detailed_topics IS NULL OR trim(row.detailed_topics) = '' THEN []
            ELSE split(row.detailed_topics, ';')
        END |
        FOREACH (__ IN CASE WHEN trim(topic) <> '' THEN [1] ELSE [] END |
            MERGE (t:Topic {name: trim(topic)})
            MERGE (a)-[:HAS_TOPIC]->(t)
        )
        )

        // 4) [상세] Detailed Design (detailed_design)
        FOREACH (design IN CASE
            WHEN row.detailed_design IS NULL OR trim(row.detailed_design) = '' THEN []
            ELSE split(row.detailed_design, ';')
        END |
        FOREACH (__ IN CASE WHEN trim(design) <> '' THEN [1] ELSE [] END |
            MERGE (sd:StudyDesign {name: trim(design)})
            MERGE (a)-[:HAS_DESIGN]->(sd)
        )
        )
    ", {batchSize: 1000, parallel: true})
    """


    # NOTE: figures/tables/equations 메타(캡션/URL 등)는 Postgres에 저장하고,
    # Neo4j에는 Article 단위로 ID 목록만 가볍게 저장합니다.
    LOAD_FIGURES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///t_figures_filtered.csv' AS row RETURN row",
    "
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        SET a.figure_ids = apoc.coll.toSet(coalesce(a.figure_ids, []) + row.fig_id)
    ", {batchSize: 2000, parallel: false})
    """


    LOAD_TABLES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///t_tables_filtered.csv' AS row RETURN row",
    "
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        SET a.table_ids = apoc.coll.toSet(coalesce(a.table_ids, []) + row.table_id)
    ", {batchSize: 2000, parallel: false})
    """


    LOAD_EQUATIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///t_equations_filtered.csv' AS row RETURN row",
    "
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        SET a.equation_ids = apoc.coll.toSet(coalesce(a.equation_ids, []) + row.equation_id)
    ", {batchSize: 2000, parallel: false})
    """

    # [핵심 수정] 섹션 로딩 (section_meta.csv 컬럼 반영)
    # 컬럼: section_id, pmid, topic_category, path, section_category, article_category, fig_ids, table_ids, section_title
    LOAD_SECTIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///ts_section_meta_new.csv' AS row RETURN row",
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
    "LOAD CSV WITH HEADERS FROM 'file:///ts_embedding_v2.csv' AS row RETURN row",
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
    "
    MATCH (s:Section)
    RETURN s
    ",
    "
    MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
    WITH s, c ORDER BY c.seq
    WITH s, collect(c) AS chunks
    FOREACH (i IN range(0, size(chunks)-2) |
        MERGE (chunks[i])-[:NEXT]->(chunks[i+1])
    )
    ",{batchSize: 200, parallel: false})
    """

    LOAD_REFERENCES = """
        CALL apoc.periodic.iterate(
        "LOAD CSV WITH HEADERS FROM 'file:///t_references_filtered.csv' AS row RETURN row",
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
    # Entity 로딩 (entity_id 기반)
    # CSV 예시 컬럼: entity_id, normalized_entity, entity_type, umls_cui, primekg_label, primekg_source_db, primekg_source_id, match_score ...
    # =========================================================================
    LOAD_ENTITIES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file://global_entity_master.csv' AS row RETURN row",
    "
      // 1) PK는 entity_id
    MERGE (e:Entity {entity_id: row.entity_id})

      // 2) 표준 필드
    SET e.name = row.normalized_entity,
        e.type = row.entity_type,
        e.umls_cui = row.umls_cui

      // 3) PrimeKG 매핑(있을 때만 채워짐)
    SET e.primekg_label = row.primekg_label,
        e.primekg_source_db = row.primekg_source_db,
        e.primekg_source_id = row.primekg_source_id,
        e.match_score = toFloat(row.match_score)
    ",
    {batchSize: 2000, parallel: true}
    )
    """

    # =========================================================================
    # Mention 기반 Article–Entity 직접 연결
    # - (2) mention.csv로 Article–Entity 바로 연결
    # - (3) 필요 시 Mention 노드 유지 (옵션 쿼리 제공)
    # =========================================================================

    # (2) Article–Entity만 생성/집계 (Mention 노드 생성 안 함)
    LOAD_ARTICLE_ENTITY_FROM_MENTIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file://global_mention_master.csv' AS row RETURN row",
    "
    MATCH (a:Article {pmid: toInteger(row.doc_id)})
    MATCH (e:Entity {entity_id: row.entity_id})

    MERGE (a)-[r:HAS_ENTITY]->(e)
    ON CREATE SET r.count = 1
    ON MATCH  SET r.count = r.count + 1
    ",
    {batchSize: 5000, parallel: false}
    )
    """

    # (3) Mention 노드도 함께 유지 (근거/위치/표면형이 필요할 때)
    LOAD_MENTIONS_WITH_NODES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///global_mention_master.csv' AS row RETURN row",
    "
    MATCH (a:Article {pmid: toInteger(row.doc_id)})
    MATCH (s:Section {section_id: row.location_id})
    MATCH (e:Entity {entity_id: row.entity_id})

    MERGE (m:Mention {mention_id: row.mention_id})
    SET  m.source = row.source,
        m.doc_id = toInteger(row.doc_id),
        m.location_id = row.location_id,
        m.raw_text = row.raw_text,
        m.normalized_text = row.normalized_text,
        m.entity_type = row.entity_type,
        m.umls_cui = row.umls_cui

    MERGE (a)-[:HAS_MENTION]->(m)
    MERGE (m)-[:IN_SECTION]->(s)
    MERGE (m)-[:MENTION_OF]->(e)

    // Article–Entity 집계도 같이(원하면)
    MERGE (a)-[r:HAS_ENTITY]->(e)
    ON CREATE SET r.count = 1
    ON MATCH  SET r.count = r.count + 1
    ",
    {batchSize: 3000, parallel: false})


    """

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
        AND e.primekg_label IS NOT NULL
    RETURN e
    ",
    "
    MATCH (b:BaseNode {name: e.primekg_label})
    MERGE (e)-[:REFERS_TO]->(b)
    ",
    {batchSize: 1000, parallel: false}
    )
    """

# 13. 실험(Experiment) 로딩 - paper_experiments_table.csv
    # Article과 직접 연결되도록 수정된 버전
    LOAD_EXPERIMENTS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///ts_paper_experiments_table.csv' AS row RETURN row",
    "
    WITH
        row,
        toInteger(row.pmid) AS pmid_int,
        trim(row.experiment_id) AS exp_id,
        toInteger(row.experiment_index) AS exp_idx,
        trim(row.method)    AS method,
        trim(row.condition) AS condition,
        trim(row.category_parent) AS cat_parent,
        trim(row.category_leaf)   AS cat_leaf,
        trim(row.materials)  AS materials,
        trim(row.equipment)  AS equipment
    WHERE exp_id IS NOT NULL AND exp_id <> ''

    MATCH (a:Article {pmid: pmid_int})

    MERGE (ep:Experiment {experiment_id: exp_id})
    SET ep.experiment_index = exp_idx,
        ep.method = method,
        ep.condition = condition,
        ep.pmid = pmid_int

    MERGE (a)-[:HAS_EXPERIMENT]->(ep)

    MERGE (cp:CategoryParent {name: cat_parent})
    MERGE (cl:CategoryLeaf   {name: cat_leaf})
    MERGE (cp)-[:HAS_LEAF]->(cl)
    MERGE (ep)-[:HAS_PARENT_CATEGORY]->(cp)
    MERGE (ep)-[:HAS_LEAF_CATEGORY]->(cl)

    // ✅ 파생 Material (Experiment 하위)
    FOREACH (m IN CASE
                    WHEN materials IS NULL OR materials = '' THEN []
                    ELSE [x IN split(materials, ',') WHERE trim(x) <> '']
                END |
        MERGE (em:ExpMaterial {material_id: exp_id + '|' + trim(m)})
        SET em.name = trim(m),
            em.experiment_id = exp_id
        MERGE (ep)-[:HAS_MATERIAL]->(em)
    )

    // ✅ 파생 Equipment (Experiment 하위)
    FOREACH (q IN CASE
                    WHEN equipment IS NULL OR equipment = '' THEN []
                    ELSE [x IN split(equipment, ',') WHERE trim(x) <> '']
                END |
        MERGE (eq:ExpEquipment {equipment_id: exp_id + '|' + trim(q)})
        SET eq.name = trim(q),
            eq.experiment_id = exp_id
        MERGE (ep)-[:HAS_EQUIPMENT]->(eq)
    )
    ",
    {batchSize: 1000, parallel: false}
    );
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
    "LOAD CSV WITH HEADERS FROM 'file:///ts_protocol_metadata_Cell_labeled.csv' AS row RETURN row",
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
    
    # LOAD_PROTOCOL_MATERIALS = """
    # CALL apoc.periodic.iterate(
    # "LOAD CSV WITH HEADERS FROM 'file:///t_protocol_materials_Cell.csv' AS row RETURN row",
    # "MATCH (p:Protocol {protocol_sid: row.protocol_sid})
    # MERGE (m:Material {name: trim(row.materials)})
    # MERGE (p)-[:USES_MATERIAL]->(m)",
    # {batchSize: 2000, parallel: false}
    # )
    # """

    # LOAD_PROTOCOL_REFERENCES = """
    # CALL apoc.periodic.iterate(
    # "LOAD CSV WITH HEADERS FROM 'file:///t_protocol_references_Cell.csv' AS row RETURN row",
    # "MATCH (p:Protocol {protocol_sid: row.protocol_sid})
    # MERGE (pr:ProtocolReference {reference_sid: row.reference_sid})
    # SET pr.title = row.reference
    # MERGE (p)-[:HAS_REFERENCE]->(pr)",
    # {batchSize: 2000, parallel: false}
    # )
    # """

    LOAD_PROTOCOL_CHUNKS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///embedded_vectors_bge_m3_dense.csv' AS row RETURN row",
    "MATCH (p:Protocol {protocol_sid: row.protocol_id})
    MERGE (pc:ProtocolChunk {chunking_id: row.chunking_id})
    SET pc.text = row.text, pc.url = row.url, pc.title = row.title,
        pc.embedding = apoc.convert.fromJsonList(row.embedding)
    MERGE (p)-[:HAS_CHUNK]->(pc)",
    {batchSize: 1000, parallel: true}
    )
    """
# src/queries.py (맨 아래에 추가)

class ClinicalTrialQueries:
    """
    ClinicalTrials.gov 데이터 로딩 및 (기존 Mention/Entity 기반) 연결 쿼리
    - 새 Entity/Mention 적재 없이, 이미 존재하는 노드들만 연결
    """

    # 1) 제약 조건
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT nct_id IF NOT EXISTS FOR (ct:ClinicalTrial) REQUIRE ct.nct_id IS UNIQUE;",
    ]

    # 2) 임상실험 메타데이터 로딩
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
        ct.conditions = CASE
                            WHEN row.conditions IS NULL OR trim(row.conditions) = '' THEN []
                            ELSE split(row.conditions, '|')
                        END,
        ct.keywords = CASE
                        WHEN row.keywords IS NULL OR trim(row.keywords) = '' THEN []
                        ELSE split(row.keywords, '|')
                        END,
        ct.interventions = CASE
                            WHEN row.interventions IS NULL OR trim(row.interventions) = '' THEN []
                            ELSE split(row.interventions, '|')
                            END
    ",
    {batchSize: 1000, parallel: true}
    )
    """

# [NEW] ★ 임상시험 전용 멘션 로더 (이게 없어서 연결이 안 된 겁니다)
    LOAD_TRIAL_MENTIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///global_mention_master.csv' AS row RETURN row",
    "
    // 1. NCT ID로 시작하는 행만 필터링 (논문 데이터 제외)
    WHERE row.doc_id STARTS WITH 'NCT'
    
    // 2. ClinicalTrial 노드 찾기
    MATCH (ct:ClinicalTrial {nct_id: row.doc_id})
    MATCH (e:Entity {entity_id: row.entity_id})

    // 3. Mention 노드 생성
    MERGE (m:Mention {mention_id: row.mention_id})
    SET m.source = row.source,
        m.doc_id = row.doc_id,
        m.location_id = row.location_id,
        m.raw_text = row.raw_text,
        m.normalized_text = row.normalized_text,
        m.entity_type = row.entity_type,
        m.umls_cui = row.umls_cui

    // 4. 즉시 연결 (별도 쿼리로 분리할 필요 없이 여기서 바로 연결)
    MERGE (ct)-[:HAS_MENTION]->(m)
    MERGE (m)-[:MENTION_OF]->(e)
    ",
    {batchSize: 5000, parallel: false}
    )
    """

    # [수정] 4. 연결 집계 최적화 (이건 그대로 사용)
    LINK_TRIAL_ENTITIES_FROM_MENTIONS = """
    CALL apoc.periodic.iterate(
    "
    MATCH (ct:ClinicalTrial)
    WHERE (ct)-[:HAS_MENTION]->()
    RETURN ct
    ",
    "
    MATCH (ct)-[:HAS_MENTION]->(m:Mention)-[:MENTION_OF]->(e:Entity)
    WITH ct, e, count(m) as mention_count
    
    MERGE (ct)-[r:HAS_ENTITY]->(e)
    SET r.count = mention_count
    ",
    { batchSize: 100, parallel: false }
    )
    """
