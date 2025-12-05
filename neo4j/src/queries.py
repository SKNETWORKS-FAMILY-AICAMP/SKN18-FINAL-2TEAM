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