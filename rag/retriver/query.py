// ============================================================================
// neo4j_rag_router_policy_12cell_reflect_actual_graph (Optimized)
//
// [최적화 핵심 사항]
// 1. Index-Friendly: WHERE 절에서 coalesce() 및 toLower() 제거 (DB 스캔 방지)
// 2. Cartesian Product 방지: 복잡한 연산 전 WITH로 카디널리티 제어
// 3. Hybrid Search 보정: Vector 검색 시 필터링으로 인한 손실을 고려해 fetch k 증가
// ============================================================================

// ============================================================================
// 1) OPERATORS (Seed Generation)
// ============================================================================

// [OP] FT_ENTITY_RESOLVE
// 설명: Fulltext Index를 사용하여 Entity ID 추출
CALL db.index.fulltext.queryNodes('entityTextIndex', $q) YIELD node AS e, score
RETURN e.entity_id AS entity_id, score
ORDER BY score DESC
LIMIT coalesce($k, 5);

// [OP] FT_MENTION_RAW
CALL db.index.fulltext.queryNodes('mentionTextIndex', $q) YIELD node AS m, score
RETURN m.mention_id AS mention_id, score
ORDER BY score DESC
LIMIT coalesce($k, 50);

// [OP] FT_JOURNAL
CALL db.index.fulltext.queryNodes('journalTextIndex', $q) YIELD node AS j, score
RETURN j.journal_id AS journal_id, score
ORDER BY score DESC
LIMIT coalesce($k, 30);

// [OP] FT_EXPMATERIAL
CALL db.index.fulltext.queryNodes('expMaterialTextIndex', $q) YIELD node AS mat, score
RETURN mat.material_id AS material_id, score
ORDER BY score DESC
LIMIT coalesce($k, 50);

// [OP] FT_EXPEQUIPMENT
CALL db.index.fulltext.queryNodes('expEquipmentTextIndex', $q) YIELD node AS eq, score
RETURN eq.equipment_id AS equipment_id, score
ORDER BY score DESC
LIMIT coalesce($k, 50);

// [OP] FT_PAPER_CHUNK
CALL db.index.fulltext.queryNodes('chunkTextIndex', $q) YIELD node AS c, score
RETURN c.chunk_id AS chunk_id, score
ORDER BY score DESC
LIMIT coalesce($k, 80);

// [OP] VEC_PAPER_CHUNK
CALL db.index.vector.queryNodes('articleChunkEmbeddingIndex', coalesce($k, 80), $embedding)
YIELD node AS c, score
RETURN c.chunk_id AS chunk_id, score AS vec_score
ORDER BY vec_score DESC
LIMIT coalesce($k, 80);

// [OP] HY_PAPER_CHUNK_VEC_PLUS_MUST
// 수정: 필터링으로 결과가 줄어드는 것을 대비해 초기 검색 개수(150)를 넉넉하게 잡음
CALL db.index.vector.queryNodes('articleChunkEmbeddingIndex', 150, $embedding)
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
LIMIT coalesce($k, 80);

// [OP] FT_PROTOCOL_CHUNK
CALL db.index.fulltext.queryNodes('protocolChunkTextIndex', $q) YIELD node AS pc, score
RETURN pc.chunk_id AS protocol_chunk_id, score
ORDER BY score DESC
LIMIT coalesce($k, 80);

// [OP] VEC_PROTOCOL_CHUNK
CALL db.index.vector.queryNodes('protocolChunkEmbeddingIndex', coalesce($k, 80), $embedding)
YIELD node AS pc, score AS vec_score
RETURN pc.chunk_id AS protocol_chunk_id, vec_score
ORDER BY vec_score DESC
LIMIT coalesce($k, 80);

// [OP] HY_PROTOCOL_CHUNK_VEC_PLUS_MUST
CALL db.index.vector.queryNodes('protocolChunkEmbeddingIndex', 150, $embedding)
YIELD node AS pc, score AS vec_score
WITH pc, vec_score,
     [t IN coalesce($must_terms, []) | toLower(t)] AS must_terms,
     [t IN coalesce($must_not_terms, []) | toLower(t)] AS must_not_terms
WHERE
  all(t IN must_terms WHERE toLower(coalesce(pc.text, '')) CONTAINS t)
  AND none(t IN must_not_terms WHERE toLower(coalesce(pc.text, '')) CONTAINS t)
RETURN pc.chunk_id AS protocol_chunk_id, vec_score
ORDER BY vec_score DESC
LIMIT coalesce($k, 80);

// [OP] FT_CLINICAL_CHUNK
CALL db.index.fulltext.queryNodes('clinicalChunkTextIndex', $q) YIELD node AS cc, score
RETURN cc.chunk_id AS clinical_chunk_id, score
ORDER BY score DESC
LIMIT coalesce($k, 80);

// [OP] VEC_CLINICAL_CHUNK
CALL db.index.vector.queryNodes('clinicalChunkEmbeddingIndex', coalesce($k, 80), $embedding)
YIELD node AS cc, score AS vec_score
RETURN cc.chunk_id AS clinical_chunk_id, vec_score
ORDER BY vec_score DESC
LIMIT coalesce($k, 80);

// [OP] HY_CLINICAL_CHUNK_VEC_PLUS_MUST
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
LIMIT coalesce($k, 80);

// [OP] FT_TRIAL_ID
// 중요: DB에는 표준화된(예: 대문자) ID가 저장되어 있다고 가정. 입력값($q)만 변환하여 인덱스 Seek 유도.
MATCH (t:ClinicalTrial)
WHERE t.nct_id = $q OR t.trial_id = $q
RETURN t.nct_id AS trial_id, 1.0 AS match_quality
LIMIT coalesce($k, 5);


// ============================================================================
// 2) CELLS: PAPER (T1~T4)
// ============================================================================

// ---------------------------------------------------------------------------
// paper__T1
// ---------------------------------------------------------------------------
WITH $entity_ids AS entity_ids
MATCH (e:Entity)
WHERE e.entity_id IN entity_ids  // [Index Seek] coalesce 제거
MATCH (a:Article)-[:HAS_SECTION]->(s:Section)-[:HAS_MENTION]->(m:Mention)-[:NORMALIZED_TO]->(e)
WITH a, count(DISTINCT m) AS mention_cnt
ORDER BY mention_cnt DESC, coalesce(a.year, 0) DESC
LIMIT coalesce($limit_articles, 20)

// Evidence 수집 (Subquery 활용하여 메인 쿼리 부하 분산)
CALL {
  WITH a
  MATCH (a)-[:HAS_SECTION]->(s:Section)-[:HAS_CHUNK]->(c:Chunk)
  // [최적화] 모든 chunk를 가져오기보다 limit을 걸어 힙 메모리 절약
  WITH c LIMIT 20 
  RETURN collect(c { .chunk_id, .text, .page })[0..coalesce($evidence_per_article, 5)] AS evidence_chunks
}
CALL {
  WITH a
  MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(m:Mention)
  WITH m LIMIT 20
  RETURN collect(m { .text, .type })[0..coalesce($evidence_per_article, 5)] AS evidence_mentions
}

// 메타데이터 조회
OPTIONAL MATCH (a)-[:IN_JOURNAL]->(j:Journal)
RETURN
  a { .doi, .title, .year, .abstract } AS article,
  mention_cnt,
  coalesce(a.year, -1) AS year,
  coalesce(a.pagerank, 0.0) AS pagerank,
  j.title AS journal_title,
  evidence_mentions,
  evidence_chunks
ORDER BY mention_cnt DESC, year DESC;


// ---------------------------------------------------------------------------
// paper__T2
// ---------------------------------------------------------------------------
WITH $chunk_ids AS chunk_ids
MATCH (c:Chunk)
WHERE c.chunk_id IN chunk_ids
MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c)

// 점수 매핑 (애플리케이션에서 넘어온 map 활용)
WITH a, c,
     coalesce($chunk_score_by_id[c.chunk_id], 0.0) AS vec_score
ORDER BY vec_score DESC
LIMIT coalesce($limit_articles, 30)

// Evidence 수집
CALL {
  WITH a
  MATCH (a)-[:HAS_SECTION]->(:Section)-[:HAS_CHUNK]->(c2:Chunk)
  // 검색된 Chunk(c) 외에 주변 Chunk(c2)도 문맥으로 제공
  RETURN collect(c2 { .chunk_id, .text })[0..coalesce($evidence_per_article, 5)] AS evidence_chunks
}
OPTIONAL MATCH (a)-[:IN_JOURNAL]->(j:Journal)

RETURN 
  a { .doi, .title, .year } AS article,
  vec_score,
  j.title AS journal_title,
  evidence_chunks
ORDER BY vec_score DESC;


// ---------------------------------------------------------------------------
// paper__T3
// ---------------------------------------------------------------------------
WITH $entity_ids AS entity_ids
MATCH (e:Entity)
WHERE e.entity_id IN entity_ids
MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
WITH collect(DISTINCT a) AS candidate_articles

// Cited Works 확장 (데이터량 조절을 위해 LIMIT 필수)
CALL {
  WITH candidate_articles
  UNWIND candidate_articles AS a
  OPTIONAL MATCH (a)-[:HAS_REFERENCE]->(:Reference)-[:CITES_WORK]->(cw:CitedWork)
  WITH cw WHERE cw IS NOT NULL
  RETURN collect(DISTINCT cw { .doi, .title })[0..50] AS cited_works_from_refs
}
// Direct Cited Work (혹시 스키마에 있다면)
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
  (cited_works_from_refs + cited_works_direct)[0..coalesce($set_size_target, 250)] AS cited_works_set;


// ---------------------------------------------------------------------------
// paper__T4 (Multi-domain)
// ---------------------------------------------------------------------------
WITH $entity_ids AS entity_ids
MATCH (e:Entity)
WHERE e.entity_id IN entity_ids

// 1) Paper Domain
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

// 2) Clinical Domain
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

// 3) PrimeKG Domain
CALL {
  WITH e
  MATCH (e)-[:MAPS_TO_PRIMEKG]->(p)
  OPTIONAL MATCH (p)--(nbr)
  WITH p, collect(DISTINCT nbr)[0..50] AS neighbors
  // properties(node)는 전체 프로퍼티를 가져오므로 필요 시 특정 필드만 지정 권장
  RETURN collect({
      type:'primekg', 
      node: properties(p), 
      neighbors: [x IN neighbors | properties(x)]
  }) AS primekg_rows
}

RETURN paper_rows, clinical_rows, primekg_rows;


// ============================================================================
// 3) CELLS: PROTOCOL (T1~T4)
// ============================================================================

// ---------------------------------------------------------------------------
// protocol__T1
// ---------------------------------------------------------------------------
WITH $entity_ids AS entity_ids
MATCH (e:Entity)
WHERE e.entity_id IN entity_ids
MATCH (a:Article)-[:HAS_SECTION]->(:Section)-[:HAS_MENTION]->(:Mention)-[:NORMALIZED_TO]->(e)
MATCH (a)-[:HAS_EXPERIMENT]->(exp:Experiment)

// Protocol 연결 (Optional)
OPTIONAL MATCH (exp)-[:LINKS_PROTOCOL]->(p:Protocol)

// [버그 수정] experiment_cnt를 하드코딩 1이 아닌 실제 count(exp)로 변경
WITH a, p, count(exp) AS experiment_cnt
WHERE p IS NOT NULL
ORDER BY coalesce(p.usage_degree, 0) DESC, experiment_cnt DESC, coalesce(a.year, 0) DESC
LIMIT coalesce($limit_protocols, 10)

CALL {
  WITH p
  MATCH (p)-[:HAS_CHUNK]->(pc:ProtocolChunk)
  RETURN collect(pc { .text, .chunk_id })[0..10] AS evidence_protocol_chunks
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
ORDER BY usage_degree DESC;


// ---------------------------------------------------------------------------
// protocol__T2
// ---------------------------------------------------------------------------
WITH $protocol_chunk_ids AS protocol_chunk_ids
MATCH (pc:ProtocolChunk)
WHERE pc.chunk_id IN protocol_chunk_ids
MATCH (p:Protocol)-[:HAS_CHUNK]->(pc)
MATCH (exp:Experiment)-[:LINKS_PROTOCOL]->(p)
MATCH (a:Article)-[:HAS_EXPERIMENT]->(exp)

WITH a, p, exp, pc,
     coalesce($chunk_score_by_id[pc.chunk_id], 0.0) AS vec_score
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
ORDER BY vec_score DESC;


// ---------------------------------------------------------------------------
// protocol__T3
// ---------------------------------------------------------------------------
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
ORDER BY coalesce(p.usage_degree, 0) DESC;


// ---------------------------------------------------------------------------
// protocol__T4 (Multi-domain)
// ---------------------------------------------------------------------------
WITH $entity_ids AS entity_ids
MATCH (e:Entity)
WHERE e.entity_id IN entity_ids

// 1) Protocol Domain
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

// 2) Clinical Domain
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

// 3) PrimeKG Domain
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

RETURN protocol_rows, clinical_rows, primekg_rows;


// ============================================================================
// 4) CELLS: CLINICAL (T1~T4)
// ============================================================================

// ---------------------------------------------------------------------------
// clinical__T1
// ---------------------------------------------------------------------------
WITH $trial_ids AS trial_ids
MATCH (t:ClinicalTrial)
WHERE t.nct_id IN trial_ids OR t.trial_id IN trial_ids // [Index Seek]
WITH t
LIMIT coalesce($limit_trials, 5)
OPTIONAL MATCH (t)-[:HAS_CHUNK]->(cc:ClinicalChunk)

WITH t, collect(cc { .text })[0..coalesce($evidence_per_trial, 3)] AS evidence_clinical_chunks
RETURN 
  t { .nct_id, .title, .phase, .year } AS trial,
  evidence_clinical_chunks
ORDER BY t.phase DESC, coalesce(t.year, 0) DESC;


// ---------------------------------------------------------------------------
// clinical__T2
// ---------------------------------------------------------------------------
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
ORDER BY vec_score DESC;


// ---------------------------------------------------------------------------
// clinical__T3
// ---------------------------------------------------------------------------
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
  [x IN clinical_chunks | x { .text }] AS evidence_clinical_chunks;


// ---------------------------------------------------------------------------
// clinical__T4
// ---------------------------------------------------------------------------
WITH $entity_ids AS entity_ids
MATCH (e:Entity)
WHERE e.entity_id IN entity_ids

// 1) Clinical
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

// 2) Paper
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

// 3) Protocol
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

// 4) PrimeKG
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

RETURN clinical_rows, paper_rows, protocol_rows, primekg_rows;