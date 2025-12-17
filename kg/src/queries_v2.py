class PrimeKGQueries:

    """
    PrimeKG 데이터 로딩을 위한 Cypher 쿼리 저장소
    """

    # 1. 제약 조건 (Unique Constraints)
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:BaseNode) REQUIRE n.node_index IS UNIQUE;",
    ]

    # [신규] 1-2. 검색 속도 향상을 위한 인덱스 (이름 기반 검색 필수)
    CREATE_INDEXES = [
        "CREATE INDEX base_node_name_idx IF NOT EXISTS FOR (n:BaseNode) ON (n.name);",
        "CREATE INDEX base_node_id_idx IF NOT EXISTS FOR (n:BaseNode) ON (n.id);"
    ]

    # 2. 노드 로딩 (nodes.csv)
    LOAD_NODES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row RETURN row",
    "
      WITH row, apoc.text.capitalizeAll(replace(row.node_type, '/', '_')) as label
    CALL apoc.create.node([label, 'BaseNode'], {
        node_index: toInteger(row.node_index), 
        id: row.node_id,
        node_type: row.node_type, 
        name: row.node_name, 
        source: row.node_source
    }) YIELD node
    RETURN count(*)
    ",
    {batchSize: 2000, parallel: true}
    )
    """

    # 3. 엣지(관계) 로딩 (edges.csv)
    LOAD_EDGES = """
    CALL apoc.periodic.iterate(
      "LOAD CSV WITH HEADERS FROM 'file:///edges.csv' AS row RETURN row",
      "
      WITH row, toUpper(replace(row.display_relation, ' ', '_')) as relType
      MATCH (a:BaseNode {node_index: toInteger(row.x_index)})
      MATCH (b:BaseNode {node_index: toInteger(row.y_index)})
      
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
    UPDATE_DISEASE_FEATURES = """
    CALL apoc.periodic.iterate(
      "LOAD CSV WITH HEADERS FROM 'file:///disease_features_cleaned.csv' AS row RETURN row",
      "
      MATCH (n:BaseNode {node_index: toInteger(row.node_index)})
      SET 
          n.mondo_id = row.mondo_id,
          n.mondo_name = row.mondo_name,
          n.group_id_bert = row.group_id_bert,
          n.group_name_bert = row.group_name_bert,
          n.mondo_definition = row.mondo_definition,
          n.umls_description = row.umls_description,
          n.orphanet_definition = row.orphanet_definition,
          n.orphanet_prevalence = row.orphanet_prevalence,
          n.orphanet_epidemiology = row.orphanet_epidemiology,
          n.orphanet_clinical_description = row.orphanet_clinical_description,
          n.orphanet_management_and_treatment = row.orphanet_management_and_treatment,
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

    # 1. 제약 조건 & 인덱스
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
        "CREATE CONSTRAINT mention_id IF NOT EXISTS FOR (m:Mention) REQUIRE m.mention_id IS UNIQUE;",

        # topic / domain / journal / design
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE;",
        "CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (dom:Domain) REQUIRE dom.name IS UNIQUE;",
        "CREATE CONSTRAINT journal_name IF NOT EXISTS FOR (j:Journal) REQUIRE j.name IS UNIQUE;",
        "CREATE CONSTRAINT study_design_name IF NOT EXISTS FOR (sd:StudyDesign) REQUIRE sd.name IS UNIQUE;",

        # experiments
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

    # [신규] 1-2. 연결 속도 향상을 위한 인덱스
    CREATE_INDEXES = [
        # Entity 연결용
        "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name);",
        "CREATE INDEX entity_primekg_label_idx IF NOT EXISTS FOR (e:Entity) ON (e.primekg_label);",
        # Mention을 통한 ClinicalTrial 연결용
        "CREATE INDEX mention_nct_id_idx IF NOT EXISTS FOR (m:Mention) ON (m.nct_id);"
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

    # --- Loading Queries (Articles, Figures, Tables, Equations 생략 없이 포함) ---

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

        FOREACH (ignoreMe IN CASE WHEN row.journal IS NOT NULL THEN [1] ELSE [] END |
            MERGE (j:Journal {name: row.journal}) 
            MERGE (a)-[:PUBLISHED_IN]->(j)
        )
        
        FOREACH (ignoreMe IN CASE WHEN row.domain IS NOT NULL AND row.domain <> '' THEN [1] ELSE [] END |
            MERGE (dom:Domain {name: row.domain})
            MERGE (a)-[:IN_DOMAIN]->(dom)
        )

        FOREACH (topic IN CASE
            WHEN row.detailed_topics IS NULL OR trim(row.detailed_topics) = '' THEN []
            ELSE split(row.detailed_topics, ';')
        END |
        FOREACH (__ IN CASE WHEN trim(topic) <> '' THEN [1] ELSE [] END |
            MERGE (t:Topic {name: trim(topic)})
            MERGE (a)-[:HAS_TOPIC]->(t)
        )
        )

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

    LOAD_SECTIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///ts_section_meta_new.csv' AS row RETURN row",
    "
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        MERGE (s:Section {section_id: row.section_id})
        SET s.title = row.section_title,
            s.category = row.section_category,
            s.article_category = row.article_category,
            s.topic_category = row.topic_category,
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
    MATCH (s:Section)-[:HAS_CHUNK]->(c:Chunk)
    WITH s, c
    ORDER BY s.section_id, c.seq
    WITH s, collect(c) AS chunks
    RETURN chunks
    ",
    "
    CALL apoc.nodes.link(chunks, 'NEXT')
    RETURN 0
    ",
    {batchSize: 1000, parallel: false, iterateList: true}
    )
    """

    LOAD_REFERENCES = """
        CALL apoc.periodic.iterate(
        "LOAD CSV WITH HEADERS FROM 'file:///t_references_filtered.csv' AS row RETURN row",
        "
            MATCH (source:Article {pmid: toInteger(row.pmid)})
            
            MERGE (ref:Reference {uid: row.ref_id})
            SET ref.title = row.ref_title, 
                ref.year = toInteger(row.ref_year),
                ref.journal = row.ref_journal
            MERGE (source)-[:HAS_BIBLIO]->(ref)

            WITH source, ref, row,
                CASE 
                    WHEN row.ref_pmid IS NOT NULL AND row.ref_pmid <> '' THEN 'pmid:' + row.ref_pmid
                    WHEN row.ref_doi IS NOT NULL AND row.ref_doi <> '' THEN 'doi:' + row.ref_doi
                    WHEN row.ref_url IS NOT NULL AND row.ref_url <> '' THEN 'url:' + row.ref_url
                    WHEN row.ref_journal IS NOT NULL AND row.ref_title_norm IS NOT NULL AND row.ref_year IS NOT NULL 
                    THEN 'meta:' + toLower(trim(row.ref_journal)) + '_' + row.ref_title_norm + '_' + toString(row.ref_year)
                    ELSE null 
                END as master_key

            WHERE master_key IS NOT NULL

            MERGE (work:CitedWork {uid: master_key})
            ON CREATE SET 
                work.title = row.ref_title,
                work.year = toInteger(row.ref_year),
                work.doi = row.ref_doi,
                work.type = 'CitedWork'

            MERGE (ref)-[:POINTS_TO]->(work)
            MERGE (source)-[:CITES_WORK]->(work)

    ", {batchSize: 2000})
    """

    LOAD_ENTITIES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///global_entity_master.csv' AS row RETURN row",
    "
    MERGE (e:Entity {entity_id: row.entity_id})
    SET e.name = row.normalized_entity,
        e.type = row.entity_type,
        e.umls_cui = row.umls_cui,
        e.primekg_label = row.primekg_label,
        e.primekg_source_db = row.primekg_source_db,
        e.primekg_source_id = row.primekg_source_id,
        e.match_score = toFloat(row.match_score)
    ",
    {batchSize: 2000, parallel: true}
    )
    """

    LOAD_ARTICLE_ENTITY_FROM_MENTIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///global_mention_master.csv' AS row RETURN row",
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

    # [수정] Mentions 로딩 속도 개선 (BatchSize 증가)
    LOAD_MENTIONS_FAST = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///global_mention_master.csv' AS row RETURN row",
    "
    MATCH (a:Article {pmid: toInteger(row.doc_id)})
    MATCH (e:Entity {entity_id: row.entity_id})
    
    // Mention 노드 생성 (MERGE 대신 CREATE가 빠르지만 중복방지 위해 MERGE 유지, 인덱스 필수)
    MERGE (m:Mention {mention_id: row.mention_id})
    SET m.source = row.source,
        m.doc_id = toInteger(row.doc_id),
        m.location_id = row.location_id,
        m.raw_text = row.raw_text,
        m.normalized_text = row.normalized_text,
        m.entity_type = row.entity_type,
        m.umls_cui = row.umls_cui,
        m.nct_id = row.nct_id

    // 핵심 연결만 수행 (집계 로직 제거)
    MERGE (a)-[:HAS_MENTION]->(m)
    MERGE (m)-[:MENTION_OF]->(e)
    ",
    {batchSize: 5000, parallel: false} 
    )
    """

    # 2단계: 섹션 연결 (별도 패스로 분리하여 메인 로딩 가속화)
    # location_id가 있는 경우에만 실행
    LINK_MENTIONS_TO_SECTIONS = """
    CALL apoc.periodic.iterate(
    "
    MATCH (m:Mention)
    WHERE m.location_id IS NOT NULL AND m.location_id <> ''
      AND NOT (m)-[:IN_SECTION]->(:Section) // 이미 연결된 건 패스
    RETURN m
    ",
    "
    MATCH (s:Section {section_id: m.location_id})
    MERGE (m)-[:IN_SECTION]->(s)
    ",
    {batchSize: 5000, parallel: false}
    )
    """

    # 3단계: 집계 (Aggregation) - 로딩 완료 후 한방에 계산
    # Row-by-Row로 +1 하는 것보다 이게 훨씬 빠르고 Lock이 안 걸림
    # 3단계: 집계 (Aggregation) - 최적화 버전
    CALC_ARTICLE_ENTITY_AGGREGATION = """
    CALL apoc.periodic.iterate(
    "
    // [최적화 1] 멘션이 있는 논문만 가져오기 (불필요한 NULL 체크 제거)
    MATCH (a:Article)
    WHERE (a)-[:HAS_MENTION]->() 
    RETURN a
    ",
    "
    // [최적화 2] 해당 논문의 멘션을 통해 Entity 집계
    MATCH (a)-[:HAS_MENTION]->(m:Mention)-[:MENTION_OF]->(e:Entity)
    WITH a, e, count(m) as mention_count
    
    // [최적화 3] 관계 생성
    MERGE (a)-[r:HAS_ENTITY]->(e)
    SET r.count = mention_count
    ",
    {
        batchSize: 100,       // [중요] 1000은 너무 큽니다. 50~100 추천
        parallel: false,       // [중요] 병렬 처리 활성화
        concurrency: 4,       // CPU 코어 수에 맞춰 조절 (보통 4~8)
        retries: 3            // 병렬 처리 시 락 충돌 대비 재시도 설정
    }
    )
    """

    # [수정] PrimeKG 연결 속도 개선 (Index 활용, parallel:false)
    # 인덱스(base_node_name_idx)가 있어야 빠릅니다.
    CONNECT_TO_PRIMEKG = """
    CALL apoc.periodic.iterate(
    "
    MATCH (e:Entity)
    WHERE e.name IS NOT NULL
      AND NOT (e)-[:REFERS_TO]->(:BaseNode)
    RETURN e
    ",
    "
    MATCH (b:BaseNode {name: e.name})
    MERGE (e)-[:REFERS_TO]->(b)
    ",
    {batchSize: 2000, parallel: false}
    )
    """

    # [수정] 2차 PrimeKG 연결 (Label 기준)
    CONNECT_TO_PRIMEKG_SECONDARY = """
    CALL apoc.periodic.iterate(
    "
    MATCH (e:Entity)
    WHERE e.primekg_label IS NOT NULL
      AND NOT (e)-[:REFERS_TO]->(:BaseNode)
    RETURN e
    ",
    "
    MATCH (b:BaseNode {name: e.primekg_label})
    MERGE (e)-[:REFERS_TO]->(b)
    ",
    {batchSize: 2000, parallel: false}
    )
    """

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

    FOREACH (m IN CASE
                    WHEN materials IS NULL OR materials = '' THEN []
                    ELSE [x IN split(materials, ',') WHERE trim(x) <> '']
                END |
        MERGE (em:ExpMaterial {material_id: exp_id + '|' + trim(m)})
        SET em.name = trim(m),
            em.experiment_id = exp_id
        MERGE (ep)-[:HAS_MATERIAL]->(em)
    )

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

    #1. 실험(Experiment) 변환: 기존에 연결된 CategoryLeaf를 찾아 Entity로 복제 연결
    query_exp_migration = """
        CALL apoc.periodic.iterate(
            "MATCH (ep:Experiment)-[:HAS_LEAF_CATEGORY]->(cl:CategoryLeaf) RETURN ep, cl",
            "
            // [수정] apoc.text.toUpper -> toUpper (표준 함수 사용)
            MERGE (e:Entity {entity_id: 'METHOD_' + toUpper(replace(cl.name, ' ', '_'))})
            ON CREATE SET 
                e.name = cl.name,
                e.type = 'Method',
                e.source = 'Graph_Migration'
            MERGE (ep)-[:USED_METHOD]->(e)
            ",
            {batchSize: 2000, parallel: false}
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

# 2. 프로토콜(Protocol) 변환: 기존에 연결된 CategoryLeaf를 찾아 Entity로 복제 연결
    query_proto_migration = """
        CALL apoc.periodic.iterate(
            "MATCH (p:Protocol)-[:HAS_LEAF_CATEGORY]->(cl:CategoryLeaf) RETURN p, cl",
            "
            // [수정] apoc.text.toUpper -> toUpper (표준 함수 사용)
            MERGE (e:Entity {entity_id: 'METHOD_' + toUpper(replace(cl.name, ' ', '_'))})
            ON CREATE SET 
                e.name = cl.name,
                e.type = 'Method',
                e.source = 'Graph_Migration'
            MERGE (p)-[:USED_METHOD]->(e)
            ",
            {batchSize: 2000, parallel: false}
        )
        """

class ClinicalTrialQueries:
    """
    ClinicalTrials.gov 데이터 로딩 및 연결 쿼리
    """

    # 1. 제약 조건
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT nct_id IF NOT EXISTS FOR (ct:ClinicalTrial) REQUIRE ct.nct_id IS UNIQUE;",
    ]

    # [신규] 1-2. 인덱스 (Mention의 nct_id는 PaperRAGQueries에서 생성, 여기서는 CT 자체 인덱스 확인)
    CREATE_INDEXES = [
        "CREATE INDEX clinical_trial_nct_id_idx IF NOT EXISTS FOR (ct:ClinicalTrial) ON (ct.nct_id);"
    ]

    # 2. 임상실험 메타데이터 로딩
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
