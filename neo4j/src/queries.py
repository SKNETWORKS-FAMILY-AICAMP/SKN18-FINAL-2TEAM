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


    # src/queries.py

# src/queries.py

# src/queries.py

class PaperRAGQueries:
    """
    사용자 데이터의 모든 컬럼 정보를 반영한 하이브리드 RAG 쿼리셋
    """

    # 1. 제약 조건 (데이터 무결성)
    CREATE_CONSTRAINTS = [
        "CREATE CONSTRAINT article_pmid IF NOT EXISTS FOR (n:Article) REQUIRE n.pmid IS UNIQUE;",
        "CREATE CONSTRAINT section_id IF NOT EXISTS FOR (n:Section) REQUIRE n.section_id IS UNIQUE;",
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE;",
        "CREATE CONSTRAINT figure_id IF NOT EXISTS FOR (n:Figure) REQUIRE n.uid IS UNIQUE;",
        "CREATE CONSTRAINT table_id IF NOT EXISTS FOR (n:Table) REQUIRE n.uid IS UNIQUE;",
        "CREATE CONSTRAINT equation_id IF NOT EXISTS FOR (n:Equation) REQUIRE n.uid IS UNIQUE;",
        "CREATE CONSTRAINT reference_id IF NOT EXISTS FOR (n:Reference) REQUIRE n.uid IS UNIQUE;",
        
        # 지식 그래프용 제약조건
        "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE;",
        "CREATE CONSTRAINT keyword_word IF NOT EXISTS FOR (n:Keyword) REQUIRE n.word IS UNIQUE;",
        "CREATE CONSTRAINT study_design_name IF NOT EXISTS FOR (n:StudyDesign) REQUIRE n.name IS UNIQUE;"
    ]

    # 2. 벡터 인덱스
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

    # 3. 논문(Article) 로딩 - article.csv
    # 모든 메타데이터(n_sections 등) 포함
    LOAD_ARTICLES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///article.csv' AS row RETURN row",
    "
        MERGE (a:Article {pmid: toInteger(row.pmid)})
        SET a.pmcid = row.pmcid,
            a.title = row.title,
            a.doi = row.doi,
            a.year = toInteger(row.year),
            a.abstract = row.abstract,
            // 추가 메타 정보 저장
            a.n_sections = toInteger(row.n_sections),
            a.n_equations = toInteger(row.n_equations),
            a.n_figures = toInteger(row.n_figures),
            a.n_tables = toInteger(row.n_tables),
            a.n_references = toInteger(row.n_references)

        // Topic Category
        FOREACH (ignoreMe IN CASE WHEN row.topic_category IS NOT NULL THEN [1] ELSE [] END |
            MERGE (t:Topic {name: row.topic_category})
            MERGE (a)-[:BELONGS_TO]->(t)
        )

        // Study Design (article_category 활용)
        FOREACH (ignoreMe IN CASE WHEN row.article_category IS NOT NULL THEN [1] ELSE [] END |
            MERGE (d:StudyDesign {name: row.article_category})
            MERGE (a)-[:HAS_DESIGN]->(d)
        )

        // Journal
        FOREACH (ignoreMe IN CASE WHEN row.journal IS NOT NULL THEN [1] ELSE [] END |
            MERGE (j:Journal {name: row.journal})
            MERGE (a)-[:PUBLISHED_IN]->(j)
        )
    ", {batchSize: 1000, parallel: true})
    """

    # 4. 그림(Figure) 로딩 - figures.csv
    LOAD_FIGURES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///figures.csv' AS row RETURN row",
    "
        MERGE (f:Asset:Figure {uid: row.fig_id})
        SET f.pmid = toInteger(row.pmid),
            f.label = row.fig_label,
            f.caption = row.fig_caption,
            f.url = row.fig_url
        
        WITH f, row
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        MERGE (a)-[:CONTAINS]->(f)
    ", {batchSize: 1000})
    """

    # 5. 표(Table) 로딩 - table.csv
    LOAD_TABLES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///table.csv' AS row RETURN row",
    "
        MERGE (t:Asset:Table {uid: row.table_id})
        SET t.pmid = toInteger(row.pmid),
            t.index = toInteger(row.table_index),
            t.label = row.table_label,
            t.caption = row.table_caption,
            t.url = row.table_url
        
        WITH t, row
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        MERGE (a)-[:CONTAINS]->(t)
    ", {batchSize: 1000})
    """

    # 6. 수식(Equation) 로딩 - equartion.csv (오타 반영)
    LOAD_EQUATIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///equartion.csv' AS row RETURN row",
    "
        MERGE (e:Asset:Equation {uid: row.equation_id})
        SET e.pmid = toInteger(row.pmid),
            e.index = toInteger(row.equation_index),
            e.display = row.display,
            e.expression = row.equation_rep,
            e.img_url = row.equation_img
        
        WITH e, row
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        MERGE (a)-[:CONTAINS]->(e)
    ", {batchSize: 1000})
    """

    # 7. 섹션(Section) 로딩 - section_meta.csv
    # fig_ids, table_ids 파싱하여 자산과 연결
    LOAD_SECTIONS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///section_meta.csv' AS row RETURN row",
    "
        MATCH (a:Article {pmid: toInteger(row.pmid)})
        MERGE (s:Section {section_id: row.section_id})
        SET s.title = row.section_title,
            s.category = row.section_category,
            s.topic_category = row.topic_category,
            s.path = row.path
        MERGE (a)-[:HAS_SECTION]->(s)

        // Figure 연결 (세미콜론 구분자 가정)
        WITH s, row
        WHERE row.fig_ids IS NOT NULL AND row.fig_ids <> ''
        UNWIND split(row.fig_ids, ';') AS fig_uid
        MATCH (f:Asset:Figure {uid: trim(fig_uid)})
        MERGE (s)-[:CONTAINS]->(f)
        
        // Table 연결 (세미콜론 구분자 가정)
        WITH s, row
        WHERE row.table_ids IS NOT NULL AND row.table_ids <> ''
        UNWIND split(row.table_ids, ';') AS tab_uid
        MATCH (t:Asset:Table {uid: trim(tab_uid)})
        MERGE (s)-[:CONTAINS]->(t)
    ", {batchSize: 1000, parallel: false})
    """

    # 8. 청크(Chunk) 로딩 - section_embedding.csv
    # 임베딩 모델 정보 등 상세 속성 모두 저장
    LOAD_CHUNKS = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///section_embedding.csv' AS row RETURN row",
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

    # 9. 청크 순서 연결
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

    # 10. 참고문헌(Reference) 로딩 - ref_id.csv
    # 저널명, 연도, DOI 등 상세 정보 저장
    LOAD_REFERENCES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///ref_id.csv' AS row RETURN row",
    "
        MATCH (source:Article {pmid: toInteger(row.pmid)})
        
        MERGE (ref:Reference {uid: row.ref_id})
        SET ref.index = toInteger(row.ref_index),
            ref.title = row.ref_title,
            ref.journal = row.ref_journal,
            ref.year = toInteger(row.ref_year),
            ref.doi = row.ref_doi,
            ref.url = row.ref_url,
            ref.target_pmid = toInteger(row.ref_pmid)

        MERGE (source)-[:HAS_BIBLIO]->(ref)

        // 타겟 논문이 DB에 있다면 연결
        WITH ref, row
        WHERE row.ref_pmid IS NOT NULL AND row.ref_pmid <> ''
        MATCH (target:Article {pmid: toInteger(row.ref_pmid)})
        MERGE (ref)-[:RESOLVES_TO]->(target)
    ", {batchSize: 2000})
    """

    # 11. 엔티티 노드 생성 (entities.csv)
    LOAD_ENTITIES = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///entities.csv' AS row RETURN row",
    "
        MERGE (e:Entity {name: row.normalized_entity})
        SET e.type = row.entity_type,
            e.cui = row.umls_cui,
            e.source = 'UMLS'
    ", {batchSize: 2000})
    """

    # 12. 키워드 생성 및 연결 (section_keywords.csv)
    LOAD_KEYWORDS_RELATION = """
    CALL apoc.periodic.iterate(
    "LOAD CSV WITH HEADERS FROM 'file:///section_keywords.csv' AS row RETURN row",
    "
        MATCH (s:Section {section_id: row.section_id})
        MATCH (e:Entity {name: row.normalized_entity})
        
        MERGE (k:Keyword {word: row.raw_keyword})
        MERGE (s)-[:HAS_KEYWORD {score: toFloat(row.score)}]->(k)
        MERGE (k)-[:NORMALIZES_TO]->(e)
    ", {batchSize: 2000})
    """

    # 13. PrimeKG 통합
    CONNECT_TO_PRIMEKG = """
    CALL apoc.periodic.iterate(
    "MATCH (e:Entity) MATCH (b:BaseNode) WHERE toLower(e.name) = toLower(b.name) RETURN e, b",
    "MERGE (e)-[:REFERS_TO]->(b)",
    {batchSize: 1000}
    )
    """