# -*- coding: utf-8 -*-

class GraphSchemaQueries:
    """
    전체 그래프 스키마(Constraint, Index) 통합 관리
    - DB 실존 인덱스 이름 반영 (chunk_vector_index 등)
    - 작성일: 2025-12-19
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

        # [Experiment]
        "CREATE CONSTRAINT experiment_id IF NOT EXISTS FOR (ep:Experiment) REQUIRE ep.experiment_id IS UNIQUE;",
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
        "CREATE CONSTRAINT nct_id IF NOT EXISTS FOR (ct:ClinicalTrial) REQUIRE ct.nct_id IS UNIQUE;",
        "CREATE CONSTRAINT clinical_chunk_id IF NOT EXISTS FOR (cc:ClinicalChunk) REQUIRE cc.chunk_id IS UNIQUE;"
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

    # 3. 벡터 인덱스 (Vector Indexes) - [수정됨] DB 실제 이름과 통일
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
        "CREATE FULLTEXT INDEX entityTextIndex IF NOT EXISTS FOR (n:Entity) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX mentionTextIndex IF NOT EXISTS FOR (n:Mention) ON EACH [n.raw_text];",
        "CREATE FULLTEXT INDEX journalTextIndex IF NOT EXISTS FOR (n:Journal) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX expMaterialTextIndex IF NOT EXISTS FOR (n:ExpMaterial) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX expEquipmentTextIndex IF NOT EXISTS FOR (n:ExpEquipment) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX chunkTextIndex IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text];",
        "CREATE FULLTEXT INDEX protocolChunkTextIndex IF NOT EXISTS FOR (n:ProtocolChunk) ON EACH [n.text];",
        "CREATE FULLTEXT INDEX clinicalChunkTextIndex IF NOT EXISTS FOR (n:ClinicalChunk) ON EACH [n.text];",
        "CREATE FULLTEXT INDEX protocolTextIndex IF NOT EXISTS FOR (n:Protocol) ON EACH [n.title];", 
        "CREATE FULLTEXT INDEX topicTextIndex IF NOT EXISTS FOR (n:Topic) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX studyDesignTextIndex IF NOT EXISTS FOR (n:StudyDesign) ON EACH [n.name];",
        "CREATE FULLTEXT INDEX experimentTextIndex IF NOT EXISTS FOR (n:Experiment) ON EACH [n.method];",
        "CREATE FULLTEXT INDEX categoryLeafTextIndex IF NOT EXISTS FOR (n:CategoryLeaf) ON EACH [n.name];"
    ]

class GraphSearchQueries:

    # ==========================================================================
    # 1. Basic Operators
    # ==========================================================================
    FT_ENTITY_RESOLVE = """
    CALL db.index.fulltext.queryNodes('entityTextIndex', $q) YIELD node AS e, score
    RETURN e.entity_id AS entity_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 5)
    """

    FT_MENTION_RAW = """
    CALL db.index.fulltext.queryNodes('mentionTextIndex', $q) YIELD node AS m, score
    RETURN m.mention_id AS mention_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 50)
    """

    FT_JOURNAL = """
    CALL db.index.fulltext.queryNodes('journalTextIndex', $q) YIELD node AS j, score
    RETURN j.name AS journal_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 30)
    """

    FT_EXPMATERIAL = """
    CALL db.index.fulltext.queryNodes('expMaterialTextIndex', $q) YIELD node AS mat, score
    RETURN mat.material_id AS material_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 50)
    """

    FT_EXPEQUIPMENT = """
    CALL db.index.fulltext.queryNodes('expEquipmentTextIndex', $q) YIELD node AS eq, score
    RETURN eq.equipment_id AS equipment_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 50)
    """

    # ==========================================================================
    # 2. Paper Chunk Operators
    # ==========================================================================
    FT_PAPER_CHUNK = """
    CALL db.index.fulltext.queryNodes('chunkTextIndex', $q) YIELD node AS c, score
    RETURN c.chunk_id AS chunk_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 80)
    """

    # [수정] articleChunkEmbeddingIndex -> chunk_vector_index
    VEC_PAPER_CHUNK = """
    CALL db.index.vector.queryNodes('chunk_vector_index', coalesce($k, 80), $embedding)
    YIELD node AS c, score AS vec_score
    RETURN c.chunk_id AS chunk_id, score AS vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($k, 80)
    """

    # [수정] articleChunkEmbeddingIndex -> chunk_vector_index
    HY_PAPER_CHUNK_VEC_PLUS_MUST = """
    CALL db.index.vector.queryNodes('chunk_vector_index', 150, $embedding)
    YIELD node AS c, score AS vec_score
    WITH c, vec_score,
        [t IN coalesce($must_terms, []) | toLower(t)] AS must_terms,
        [t IN coalesce($must_not_terms, []) | toLower(t)] AS must_not_terms
    WHERE
    all(t IN must_terms WHERE toLower(coalesce(c.text, '')) CONTAINS t)
    AND
    none(t IN must_not_terms WHERE toLower(coalesce(c.text, '')) CONTAINS t)
    RETURN c.chunk_id AS chunk_id, vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($k, 80)
    """

    # [수정] articleChunkEmbeddingIndex -> chunk_vector_index
    HY_PAPER_CHUNK_DUAL_RRF = """
    CALL {
    WITH $embedding AS embedding, coalesce($fetch_vec, 150) AS fetch_vec, coalesce($k_vec, 80) AS k_vec
    CALL db.index.vector.queryNodes('chunk_vector_index', fetch_vec, embedding)
    YIELD node AS c, score AS vec_score
    WITH c, vec_score, k_vec ORDER BY vec_score DESC
    WITH collect({chunk_id: c.chunk_id, vec_score: vec_score}) AS vec_raw, k_vec
    WITH vec_raw[0..k_vec] AS vec_top
    UNWIND range(0, size(vec_top)-1) AS i
    WITH vec_top[i] AS it, i + 1 AS r_vec
    RETURN collect({chunk_id: it.chunk_id, vec_score: it.vec_score, r_vec: r_vec, ft_score: null, r_ft: null}) AS vec_ranked
    }
    CALL {
        WITH $q AS q, coalesce($k_ft, 80) AS k_ft
        CALL db.index.fulltext.queryNodes('chunkTextIndex', q) YIELD node AS c, score AS ft_score
    WITH c, ft_score, k_ft ORDER BY ft_score DESC
    WITH collect({chunk_id: c.chunk_id, ft_score: ft_score}) AS ft_raw, k_ft
    WITH ft_raw[0..k_ft] AS ft_top
    UNWIND range(0, size(ft_top)-1) AS i
    WITH ft_top[i] AS it, i + 1 AS r_ft
    RETURN collect({chunk_id: it.chunk_id, vec_score: null, r_vec: null, ft_score: it.ft_score, r_ft: r_ft}) AS ft_ranked
    }
    WITH vec_ranked + ft_ranked AS rows,
        coalesce($rrf_k0, 60) AS rrf_k0,
        [t IN coalesce($must_terms, []) | toLower(t)] AS must_terms,
        [t IN coalesce($must_not_terms, []) | toLower(t)] AS must_not_terms
    UNWIND rows AS row
    WITH row.chunk_id AS chunk_id,
        max(row.vec_score) AS vec_score,
        max(row.ft_score)  AS ft_score,
        min(row.r_vec)     AS r_vec,
        min(row.r_ft)      AS r_ft,
        rrf_k0, must_terms, must_not_terms
    WITH chunk_id, vec_score, ft_score, r_vec, r_ft,
        (coalesce(vec_score, 0.0) + coalesce(ft_score, 0.0)) AS hy_score,
        must_terms, must_not_terms
    MATCH (c:Chunk {chunk_id: chunk_id})
    WHERE
    all(t IN must_terms WHERE toLower(coalesce(c.text, '')) CONTAINS t)
    AND
    none(t IN must_not_terms WHERE toLower(coalesce(c.text, '')) CONTAINS t)
    RETURN c.chunk_id AS chunk_id, hy_score, vec_score, ft_score
    ORDER BY hy_score DESC
    LIMIT coalesce($k, 120)
    """

    # ==========================================================================
    # 3. Protocol Chunk Operators
    # ==========================================================================
    FT_PROTOCOL_CHUNK = """
    CALL db.index.fulltext.queryNodes('protocolChunkTextIndex', $q) YIELD node AS pc, score
    RETURN pc.chunking_id AS protocol_chunk_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 80)
    """

    # [수정] protocolChunkEmbeddingIndex -> protocol_chunk_vector_index
    VEC_PROTOCOL_CHUNK = """
    CALL db.index.vector.queryNodes('protocol_chunk_vector_index', coalesce($k, 80), $embedding)
    YIELD node AS pc, score AS vec_score
    RETURN pc.chunking_id AS protocol_chunk_id, vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($k, 80)
    """

    # [수정] protocolChunkEmbeddingIndex -> protocol_chunk_vector_index
    HY_PROTOCOL_CHUNK_VEC_PLUS_MUST = """
    CALL db.index.vector.queryNodes('protocol_chunk_vector_index', 150, $embedding)
    YIELD node AS pc, score AS vec_score
    WITH pc, vec_score,
        [t IN coalesce($must_terms, []) | toLower(t)] AS must_terms,
        [t IN coalesce($must_not_terms, []) | toLower(t)] AS must_not_terms
    WHERE
    all(t IN must_terms WHERE toLower(coalesce(pc.text, '')) CONTAINS t)
    AND none(t IN must_not_terms WHERE toLower(coalesce(pc.text, '')) CONTAINS t)
    RETURN pc.chunking_id AS protocol_chunk_id, vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($k, 80)
    """

    # [수정] protocolChunkEmbeddingIndex -> protocol_chunk_vector_index
    HY_PROTOCOL_CHUNK_DUAL_RRF = """
    CALL {
    WITH $embedding AS embedding, coalesce($fetch_vec, 150) AS fetch_vec, coalesce($k_vec, 80) AS k_vec
    CALL db.index.vector.queryNodes('protocol_chunk_vector_index', fetch_vec, embedding)
    YIELD node AS pc, score AS vec_score
    WITH pc, vec_score, k_vec ORDER BY vec_score DESC
    WITH collect({chunk_id: pc.chunking_id, vec_score: vec_score}) AS vec_raw, k_vec
    WITH vec_raw[0..k_vec] AS vec_top
    UNWIND range(0, size(vec_top)-1) AS i
    WITH vec_top[i] AS it, i + 1 AS r_vec
    RETURN collect({chunk_id: it.chunk_id, vec_score: it.vec_score, r_vec: r_vec, ft_score: null, r_ft: null}) AS vec_ranked
    }
    CALL {
    WITH $q AS q, coalesce($k_ft, 80) AS k_ft
    CALL db.index.fulltext.queryNodes('protocolChunkTextIndex', q) YIELD node AS pc, score AS ft_score
    WITH pc, ft_score, k_ft ORDER BY ft_score DESC
    WITH collect({chunk_id: pc.chunking_id, ft_score: ft_score}) AS ft_raw, k_ft
    WITH ft_raw[0..k_ft] AS ft_top
    UNWIND range(0, size(ft_top)-1) AS i
    WITH ft_top[i] AS it, i + 1 AS r_ft
    RETURN collect({chunk_id: it.chunk_id, vec_score: null, r_vec: null, ft_score: it.ft_score, r_ft: r_ft}) AS ft_ranked
    }
    WITH vec_ranked + ft_ranked AS rows,
        coalesce($rrf_k0, 60) AS rrf_k0,
        [t IN coalesce($must_terms, []) | toLower(t)] AS must_terms,
        [t IN coalesce($must_not_terms, []) | toLower(t)] AS must_not_terms
    UNWIND rows AS row
    WITH row.chunk_id AS chunk_id,
        max(row.vec_score) AS vec_score,
        max(row.ft_score)  AS ft_score,
        min(row.r_vec)     AS r_vec,
        min(row.r_ft)      AS r_ft,
        rrf_k0, must_terms, must_not_terms
    WITH chunk_id, vec_score, ft_score, r_vec, r_ft,
        (coalesce(vec_score, 0.0) + coalesce(ft_score, 0.0)) AS hy_score,
        must_terms, must_not_terms
    MATCH (pc:ProtocolChunk {chunking_id: chunk_id})
    WHERE
    all(t IN must_terms WHERE toLower(coalesce(pc.text, '')) CONTAINS t)
    AND
    none(t IN must_not_terms WHERE toLower(coalesce(pc.text, '')) CONTAINS t)
    RETURN pc.chunking_id AS protocol_chunk_id, hy_score, vec_score, ft_score
    ORDER BY hy_score DESC
    LIMIT coalesce($k, 120)
    """

    # ==========================================================================
    # 4. Clinical Chunk Operators
    # ==========================================================================
    FT_CLINICAL_CHUNK = """
    CALL db.index.fulltext.queryNodes('clinicalChunkTextIndex', $q) YIELD node AS cc, score
    RETURN cc.chunk_id AS clinical_chunk_id, score
    ORDER BY score DESC
    LIMIT coalesce($k, 80)
    """

    VEC_CLINICAL_CHUNK = """
    CALL db.index.vector.queryNodes('clinicalChunkEmbeddingIndex', coalesce($k, 80), $embedding)
    YIELD node AS cc, score AS vec_score
    RETURN cc.chunk_id AS clinical_chunk_id, vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($k, 80)
    """

    HY_CLINICAL_CHUNK_VEC_PLUS_MUST = """
    CALL db.index.vector.queryNodes('clinicalChunkEmbeddingIndex', 150, $embedding)
    YIELD node AS cc, score AS vec_score
    WITH cc, vec_score,
        [t IN coalesce($must_terms, []) | toLower(t)] AS must_terms,
        [t IN coalesce($must_not_terms, []) | toLower(t)] AS must_not_terms
    WHERE
    all(t IN must_terms WHERE toLower(coalesce(cc.text, '')) CONTAINS t)
    AND none(t IN must_not_terms WHERE toLower(coalesce(cc.text, '')) CONTAINS t)
    RETURN cc.chunk_id AS clinical_chunk_id, vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($k, 80)
    """

    HY_CLINICAL_CHUNK_DUAL_RRF = """
    CALL {
    WITH $embedding AS embedding, coalesce($fetch_vec, 150) AS fetch_vec, coalesce($k_vec, 80) AS k_vec
    CALL db.index.vector.queryNodes('clinicalChunkEmbeddingIndex', fetch_vec, embedding)
    YIELD node AS cc, score AS vec_score
    WITH cc, vec_score, k_vec ORDER BY vec_score DESC
    WITH collect({chunk_id: cc.chunk_id, vec_score: vec_score}) AS vec_raw, k_vec
    WITH vec_raw[0..k_vec] AS vec_top
    UNWIND range(0, size(vec_top)-1) AS i
    WITH vec_top[i] AS it, i + 1 AS r_vec
    RETURN collect({chunk_id: it.chunk_id, vec_score: it.vec_score, r_vec: r_vec, ft_score: null, r_ft: null}) AS vec_ranked
    }
    CALL {
    WITH $q AS q, coalesce($k_ft, 80) AS k_ft
    CALL db.index.fulltext.queryNodes('clinicalChunkTextIndex', q) YIELD node AS cc, score AS ft_score
    WITH cc, ft_score, k_ft ORDER BY ft_score DESC
    WITH collect({chunk_id: cc.chunk_id, ft_score: ft_score}) AS ft_raw, k_ft
    WITH ft_raw[0..k_ft] AS ft_top
    UNWIND range(0, size(ft_top)-1) AS i
    WITH ft_top[i] AS it, i + 1 AS r_ft
    RETURN collect({chunk_id: it.chunk_id, vec_score: null, r_vec: null, ft_score: it.ft_score, r_ft: r_ft}) AS ft_ranked
    }
    WITH vec_ranked + ft_ranked AS rows,
        coalesce($rrf_k0, 60) AS rrf_k0,
        [t IN coalesce($must_terms, []) | toLower(t)] AS must_terms,
        [t IN coalesce($must_not_terms, []) | toLower(t)] AS must_not_terms
    UNWIND rows AS row
    WITH row.chunk_id AS chunk_id,
        max(row.vec_score) AS vec_score,
        max(row.ft_score)  AS ft_score,
        min(row.r_vec)     AS r_vec,
        min(row.r_ft)      AS r_ft,
        rrf_k0, must_terms, must_not_terms
    WITH chunk_id, vec_score, ft_score, r_vec, r_ft,
        (coalesce(vec_score, 0.0) + coalesce(ft_score, 0.0)) AS hy_score,
        must_terms, must_not_terms
    MATCH (cc:ClinicalChunk {chunk_id: chunk_id})
    WHERE
    all(t IN must_terms WHERE toLower(coalesce(cc.text, '')) CONTAINS t)
    AND
    none(t IN must_not_terms WHERE toLower(coalesce(cc.text, '')) CONTAINS t)
    RETURN cc.chunk_id AS clinical_chunk_id, hy_score, vec_score, ft_score
    ORDER BY hy_score DESC
    LIMIT coalesce($k, 120)
    """

    # ==========================================================================
    # 5. ID Lookup
    # ==========================================================================
    FT_TRIAL_ID = """
    MATCH (t:ClinicalTrial)
    WHERE t.nct_id = $q OR t.trial_id = $q
    RETURN t.nct_id AS trial_id, 1.0 AS match_quality
    LIMIT coalesce($k, 5)
    """

class GraphCellQueries:
    """
    RAG 검색 결과 조립(Retrieval & Assembly)을 위한 Cell 쿼리 저장소
    """

    # ==========================================================================
    # 2) CELLS: PAPER (T1~T4)
    # ==========================================================================
    PAPER_T1 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids
    MATCH (a:Article)-[:HAS_SECTION]->(s:Section)-[:HAS_MENTION]->(m:Mention)-[:NORMALIZED_TO]->(e)
    WITH a, count(DISTINCT m) AS mention_cnt
    ORDER BY mention_cnt DESC, coalesce(a.year, 0) DESC
    LIMIT coalesce($limit_articles, 20)

    CALL {
    WITH a
    MATCH (a)-[:HAS_SECTION]->(s:Section)-[:HAS_CHUNK]->(c:Chunk)
    WITH c LIMIT 20 
    RETURN collect(c { .chunk_id, .text, .page })[0..coalesce($evidence_per_article, 5)] AS evidence_chunks
    }
    CALL {
    WITH a
    MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(m:Mention)
    WITH m LIMIT 20
    RETURN collect(m { text: m.raw_text, .type })[0..coalesce($evidence_per_article, 5)] AS evidence_mentions
    }

    OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
    RETURN
    a { .doi, .title, .year, .abstract } AS article,
    mention_cnt,
    coalesce(a.year, -1) AS year,
    coalesce(a.pagerank, 0.0) AS pagerank,
      j.name AS journal_title,
    evidence_mentions,
    evidence_chunks
    ORDER BY mention_cnt DESC, year DESC
    """

    PAPER_T2 = """
    WITH $chunk_ids AS chunk_ids
    MATCH (c:Chunk)
    WHERE c.chunk_id IN chunk_ids
    MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c)

    WITH a, c,
        coalesce($chunk_score_by_id[c.chunk_id], 0.0) AS vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($limit_articles, 30)

    CALL {
    WITH a
    MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c2:Chunk)
    RETURN collect(c2 { .chunk_id, .text })[0..coalesce($evidence_per_article, 5)] AS evidence_chunks
    }
    OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)

    RETURN 
    a { .doi, .title, .year } AS article,
    vec_score,
      j.name AS journal_title,
    evidence_chunks
    ORDER BY vec_score DESC
    """

    PAPER_T3 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids
    MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
    WITH collect(DISTINCT a) AS candidate_articles

    CALL {
    WITH candidate_articles
    UNWIND candidate_articles AS a
    OPTIONAL MATCH (a)-[:HAS_REFERENCE]->(:Reference)-[:CITES_WORK]->(cw:CitedWork)
    WITH cw WHERE cw IS NOT NULL
    RETURN collect(DISTINCT cw { .doi, .title })[0..50] AS cited_works_from_refs
    }
    CALL {
        WITH candidate_articles
        UNWIND candidate_articles AS a
        OPTIONAL MATCH (a)-[:CITES_WORK]->(cw2:CitedWork)
        WITH cw2 WHERE cw2 IS NOT NULL
        RETURN collect(DISTINCT cw2 { .doi, .title })[0..50] AS cited_works_direct
    }

    UNWIND candidate_articles AS a
    WITH a, cited_works_from_refs, cited_works_direct
    ORDER BY coalesce(a.pagerank, 0.0) DESC
    LIMIT coalesce($limit_articles, 60)

    CALL {
    WITH a
    MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
    RETURN collect(c { .chunk_id, .text })[0..coalesce($evidence_per_article, 3)] AS evidence_chunks
    }

    RETURN
    a { .doi, .title, .year } AS article,
    a.pagerank AS pagerank,
    evidence_chunks,
    (cited_works_from_refs + cited_works_direct)[0..coalesce($set_size_target, 250)] AS cited_works_set
    """

    PAPER_T4 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids

    CALL {
    WITH e
    MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
    WITH DISTINCT a
    ORDER BY coalesce(a.year, 0) DESC, coalesce(a.pagerank, 0.0) DESC
    LIMIT coalesce($limit_articles, 30)
    
    CALL {
        WITH a
        MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
        RETURN collect(c { .text, .chunk_id })[0..3] AS chunks
    }
    RETURN collect({
        type:'paper', 
        node: a { .title, .year, .doi }, 
        evidence_chunks: chunks
    }) AS paper_rows
    }

    CALL {
    WITH e
    MATCH (e)-[:LINKS_TRIAL]->(t:ClinicalTrial)
    WITH DISTINCT t
    ORDER BY t.phase DESC, coalesce(t.year, 0) DESC
    LIMIT coalesce($limit_trials, 15)
    
    CALL {
        WITH t
        MATCH (t)-[:HAS_CHUNK]->(cc:ClinicalChunk)
        RETURN collect(cc { .text, .chunk_id })[0..3] AS clinical_chunks
    }
    RETURN collect({
        type:'clinical', 
        node: t { .nct_id, .phase, .title }, 
        evidence_chunks: clinical_chunks
    }) AS clinical_rows
    }

    CALL {
    WITH e
    MATCH (e)-[:MAPS_TO_PRIMEKG]->(p)
    OPTIONAL MATCH (p)--(nbr)
    WITH p, collect(DISTINCT nbr)[0..50] AS neighbors
    RETURN collect({
        type:'primekg', 
        node: properties(p), 
        neighbors: [x IN neighbors | properties(x)]
    }) AS primekg_rows
    }

    RETURN paper_rows, clinical_rows, primekg_rows
    """

    # ==========================================================================
    # 3) CELLS: PROTOCOL (T1~T4)
    # ==========================================================================
    PROTOCOL_T1 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids
    MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
    MATCH (a)-[:HAS_EXPERIMENT]->(exp:Experiment)

    OPTIONAL MATCH (exp)-[:LINKS_PROTOCOL]->(p:Protocol)

    WITH a, p, count(exp) AS experiment_cnt
    WHERE p IS NOT NULL
    ORDER BY coalesce(p.usage_degree, 0) DESC, experiment_cnt DESC, coalesce(a.year, 0) DESC
    LIMIT coalesce($limit_protocols, 10)

    CALL {
    WITH p
    MATCH (p)-[:HAS_CHUNK]->(pc:ProtocolChunk)
    RETURN collect(pc { .text, chunk_id: pc.chunking_id })[0..10] AS evidence_protocol_chunks
    }
    CALL {
    WITH a
    MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
    RETURN collect(c { .text, .chunk_id })[0..3] AS evidence_paper_chunks
    }

    RETURN
    p { .title, .usage_degree } AS protocol,
    p.usage_degree AS usage_degree,
    a { .title, .year } AS source_article,
    experiment_cnt,
    evidence_protocol_chunks,
    evidence_paper_chunks
    ORDER BY usage_degree DESC
    """

    PROTOCOL_T2 = """
    WITH $protocol_chunk_ids AS protocol_chunk_ids
    MATCH (pc:ProtocolChunk)
    WHERE pc.chunking_id IN protocol_chunk_ids
    MATCH (p:Protocol)-[:HAS_CHUNK]->(pc)
    MATCH (exp:Experiment)-[:LINKS_PROTOCOL]->(p)
    MATCH (a:Article)-[:HAS_EXPERIMENT]->(exp)

    WITH a, p, exp, pc,
        coalesce($chunk_score_by_id[pc.chunking_id], 0.0) AS vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($limit_protocols, 15)

    CALL {
    WITH p
    MATCH (p)-[:HAS_CHUNK]->(pc2:ProtocolChunk)
    RETURN collect(pc2 { .text })[0..coalesce($evidence_per_article, 3)] AS evidence_protocol_chunks
    }
    CALL {
    WITH a
    MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
    RETURN collect(c { .text })[0..coalesce($evidence_per_article, 3)] AS evidence_paper_chunks
    }

    RETURN
    p { .title } AS protocol,
    vec_score,
    a { .title } AS source_article,
    exp { .method_name } AS experiment,
    evidence_protocol_chunks,
    evidence_paper_chunks
    ORDER BY vec_score DESC
    """

    PROTOCOL_T3 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids
    MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
    MATCH (a)-[:HAS_EXPERIMENT]->(exp:Experiment)-[:LINKS_PROTOCOL]->(p:Protocol)

    WITH DISTINCT a, exp, p
    ORDER BY coalesce(p.usage_degree, 0) DESC, coalesce(a.year, 0) DESC
    LIMIT coalesce($limit_protocols, 15)

    CALL {
    WITH p
    MATCH (p)-[:HAS_CHUNK]->(pc:ProtocolChunk)
    RETURN collect(pc { .text })[0..5] AS evidence_protocol_chunks
    }
    CALL {
    WITH a
    MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
    RETURN collect(c { .text })[0..5] AS evidence_paper_chunks
    }

    RETURN
    p { .title } AS protocol,
    a { .title } AS example_article,
    exp { .method_name } AS experiment,
    evidence_protocol_chunks,
    evidence_paper_chunks
    ORDER BY coalesce(p.usage_degree, 0) DESC
    """

    PROTOCOL_T4 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids

    CALL {
    WITH e
    MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
    MATCH (a)-[:HAS_EXPERIMENT]->(exp:Experiment)-[:LINKS_PROTOCOL]->(p:Protocol)
    WITH DISTINCT a, exp, p
    ORDER BY coalesce(p.usage_degree, 0) DESC, coalesce(a.year, 0) DESC
    LIMIT coalesce($limit_protocols, 15)
    
    CALL {
        WITH p
        MATCH (p)-[:HAS_CHUNK]->(pc:ProtocolChunk)
        RETURN collect(pc { .text })[0..2] AS chunks
    }
    RETURN collect({
        type:'protocol', 
        protocol: p { .title }, 
        source_article: a { .title }, 
        evidence: chunks
    }) AS protocol_rows
    }

    CALL {
    WITH e
    MATCH (e)-[:LINKS_TRIAL]->(t:ClinicalTrial)
    WITH DISTINCT t
    ORDER BY t.phase DESC, coalesce(t.year, 0) DESC
    LIMIT coalesce($limit_trials, 10)
    
    CALL {
        WITH t
        MATCH (t)-[:HAS_CHUNK]->(cc:ClinicalChunk)
        RETURN collect(cc { .text })[0..2] AS chunks
    }
    RETURN collect({
        type:'clinical', 
        trial: t { .nct_id, .phase }, 
        evidence: chunks
    }) AS clinical_rows
    }

    CALL {
    WITH e
    MATCH (e)-[:MAPS_TO_PRIMEKG]->(p)
    OPTIONAL MATCH (p)--(nbr)
    WITH p, collect(DISTINCT nbr)[0..50] AS neighbors
    RETURN collect({
        type:'primekg', 
        node: properties(p), 
        neighbors: [x IN neighbors | properties(x)]
    }) AS primekg_rows
    }

    RETURN protocol_rows, clinical_rows, primekg_rows
    """

    # ==========================================================================
    # 4) CELLS: CLINICAL (T1~T4)
    # ==========================================================================
    CLINICAL_T1 = """
    WITH $trial_ids AS trial_ids
    MATCH (t:ClinicalTrial)
    WHERE t.nct_id IN trial_ids OR t.trial_id IN trial_ids
    WITH t
    LIMIT coalesce($limit_trials, 5)
    OPTIONAL MATCH (t)-[:HAS_CHUNK]->(cc:ClinicalChunk)

    WITH t, collect(cc { .text })[0..coalesce($evidence_per_trial, 3)] AS evidence_clinical_chunks
    RETURN 
      t { .nct_id, .title, .phase, .year } AS trial,
      evidence_clinical_chunks
    ORDER BY t.phase DESC, coalesce(t.year, 0) DESC
    """

    CLINICAL_T2 = """
    WITH $clinical_chunk_ids AS clinical_chunk_ids
    MATCH (cc:ClinicalChunk)
    WHERE cc.chunk_id IN clinical_chunk_ids
    MATCH (t:ClinicalTrial)-[:HAS_CHUNK]->(cc)

    WITH t, cc,
         coalesce($chunk_score_by_id[cc.chunk_id], 0.0) AS vec_score
    ORDER BY vec_score DESC
    LIMIT coalesce($limit_trials, 20)

    CALL {
      WITH t
      MATCH (t)-[:HAS_CHUNK]->(cc2:ClinicalChunk)
      RETURN collect(cc2 { .text })[0..coalesce($evidence_per_trial, 5)] AS evidence_clinical_chunks
    }
    RETURN 
      t { .nct_id, .title } AS trial,
      vec_score,
      evidence_clinical_chunks
    ORDER BY vec_score DESC
    """

    CLINICAL_T3 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids
    MATCH (e)-[:LINKS_TRIAL]->(t:ClinicalTrial)-[:HAS_CHUNK]->(cc:ClinicalChunk)

    WITH t, collect(DISTINCT cc)[0..coalesce($evidence_per_trial, 3)] AS clinical_chunks
    ORDER BY t.phase DESC,
             coalesce(t.effect_size, 0.0) DESC,
             coalesce(t.year, 0) DESC
    LIMIT coalesce($limit_trials, 50)

    RETURN 
      t { .nct_id, .title, .phase } AS trial,
      [x IN clinical_chunks | x { .text }] AS evidence_clinical_chunks
    """

    CLINICAL_T4 = """
    WITH $entity_ids AS entity_ids
    MATCH (e:Entity)
    WHERE e.entity_id IN entity_ids

    CALL {
      WITH e
      MATCH (e)-[:LINKS_TRIAL]->(t:ClinicalTrial)
      WITH DISTINCT t
      ORDER BY t.phase DESC, coalesce(t.year, 0) DESC
      LIMIT coalesce($limit_trials, 30)
      
      CALL {
        WITH t
        MATCH (t)-[:HAS_CHUNK]->(cc:ClinicalChunk)
        RETURN collect(cc { .text })[0..3] AS chunks
      }
      RETURN collect({
          type:'clinical', 
          trial: t { .nct_id, .phase }, 
          evidence: chunks
      }) AS clinical_rows
    }

    CALL {
      WITH e
      MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
      WITH DISTINCT a
      ORDER BY coalesce(a.pagerank, 0.0) DESC
      LIMIT coalesce($limit_articles, 20)
      
      CALL {
        WITH a
        MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c:Chunk)
        RETURN collect(c { .text })[0..2] AS chunks
      }
      RETURN collect({
          type:'paper', 
          article: a { .title, .year }, 
          evidence: chunks
      }) AS paper_rows
    }

    CALL {
      WITH e
      MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
      MATCH (a)-[:HAS_EXPERIMENT]->(exp:Experiment)-[:LINKS_PROTOCOL]->(p:Protocol)
      WITH DISTINCT p
      ORDER BY coalesce(p.usage_degree, 0) DESC
      LIMIT coalesce($limit_protocols, 10)
      
      CALL {
        WITH p
        MATCH (p)-[:HAS_CHUNK]->(pc:ProtocolChunk)
        RETURN collect(pc { .text })[0..2] AS chunks
      }
      RETURN collect({
          type:'protocol', 
          protocol: p { .title }, 
          evidence: chunks
      }) AS protocol_rows
    }

    CALL {
      WITH e
      MATCH (e)-[:MAPS_TO_PRIMEKG]->(p)
      OPTIONAL MATCH (p)--(nbr)
      WITH p, collect(DISTINCT nbr)[0..50] AS neighbors
      RETURN collect({
          type:'primekg', 
          node: properties(p), 
          neighbors: [x IN neighbors | properties(x)]
      }) AS primekg_rows
    }

    RETURN clinical_rows, paper_rows, protocol_rows, primekg_rows
    """
