// =============================================
// Neo4j Article 노드 스키마 확인용 Cypher 쿼리
// =============================================
// 이 쿼리들을 Neo4j 브라우저에서 실행하여 Article 노드의 구조를 확인할 수 있습니다.

// ---------------------------------------------
// 1. Article 노드 샘플 조회 (모든 속성 포함)
// ---------------------------------------------
// Article 노드 하나를 가져와서 모든 속성을 확인
MATCH (a:Article)
RETURN properties(a) AS article_properties, labels(a) AS labels
LIMIT 1;

// ---------------------------------------------
// 2. Article 노드의 모든 속성 키 확인
// ---------------------------------------------
// Article 노드에 존재하는 모든 속성 키를 집계하여 확인
MATCH (a:Article)
WITH keys(a) AS props
UNWIND props AS prop
RETURN DISTINCT prop AS property_name, count(*) AS node_count
ORDER BY node_count DESC;

// ---------------------------------------------
// 3. 특정 속성 존재 여부 확인 (pmid, authors, month, day 등)
// ---------------------------------------------
// Article 노드에서 특정 속성들의 존재 여부를 확인
MATCH (a:Article)
RETURN 
    count(a) AS total_articles,
    count(a.pmid) AS has_pmid_count,
    count(a.authors) AS has_authors_count,
    count(a.year) AS has_year_count,
    count(a.month) AS has_month_count,
    count(a.day) AS has_day_count,
    count(a.doi) AS has_doi_count,
    count(a.title) AS has_title_count,
    count(a.date) AS has_date_count,
    count(a.publication_date) AS has_publication_date_count,
    count(a.published_date) AS has_published_date_count;

// ---------------------------------------------
// 4. Article 노드 샘플 상세 조회 (필수 필드 포함)
// ---------------------------------------------
// 필수 필드들을 포함한 Article 노드 샘플 조회
MATCH (a:Article)
OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
RETURN 
    a.title AS title,
    a.year AS year,
    a.month AS month,
    a.day AS day,
    a.date AS date,
    a.publication_date AS publication_date,
    a.pmid AS pmid,
    a.doi AS doi,
    a.authors AS authors,
    j.name AS journal_name,
    properties(a) AS all_properties
LIMIT 5;

// ---------------------------------------------
// 5. Article 노드의 날짜 관련 속성 확인
// ---------------------------------------------
// 날짜 관련 속성들의 패턴 확인
MATCH (a:Article)
WHERE a.year IS NOT NULL OR a.date IS NOT NULL OR a.publication_date IS NOT NULL
RETURN 
    a.year AS year,
    a.month AS month,
    a.day AS day,
    a.date AS date,
    a.publication_date AS publication_date,
    type(a.date) AS date_type,
    type(a.publication_date) AS publication_date_type
LIMIT 10;

// ---------------------------------------------
// 6. Article 노드의 authors 속성 확인
// ---------------------------------------------
// authors 속성이 있는 Article 노드 샘플 확인
MATCH (a:Article)
WHERE a.authors IS NOT NULL
RETURN 
    a.title AS title,
    a.authors AS authors,
    type(a.authors) AS authors_type
LIMIT 10;

// ---------------------------------------------
// 7. Article 노드의 pmid 속성 확인
// ---------------------------------------------
// pmid 속성이 있는 Article 노드 샘플 확인
MATCH (a:Article)
WHERE a.pmid IS NOT NULL
RETURN 
    a.title AS title,
    a.pmid AS pmid,
    type(a.pmid) AS pmid_type
LIMIT 10;

// ---------------------------------------------
// 8. Article 노드의 완전한 구조 확인 (Journal 관계 포함)
// ---------------------------------------------
// Article 노드와 Journal 관계를 포함한 완전한 구조 확인
MATCH (a:Article)
OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
WITH a, j
LIMIT 1
RETURN {
    article: properties(a),
    journal: properties(j),
    article_labels: labels(a),
    journal_labels: labels(j)
} AS complete_structure;

// ---------------------------------------------
// 9. Article 노드의 pmid 식별자 확인
// ---------------------------------------------
// Article 노드 자체가 pmid를 식별자로 사용하는지 확인
// (Article 노드의 ID 또는 pmid 속성으로 식별)
MATCH (a:Article)
OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
RETURN 
    id(a) AS node_id,
    elementId(a) AS element_id,
    a.pmid AS pmid_property,
    a.title AS title,
    a.year AS year,
    a.doi AS doi,
    j.name AS journal_name,
    properties(a) AS all_properties
LIMIT 10;

// ---------------------------------------------
// 10. pmid로 Article 노드 찾기
// ---------------------------------------------
// 특정 pmid로 Article 노드 검색 (pmid가 속성인 경우)
// 주의: 실제 pmid 값으로 변경해서 테스트하세요
MATCH (a:Article {pmid: 39261613})
OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
RETURN 
    a.pmid AS pmid,
    a.title AS title,
    a.year AS year,
    a.doi AS doi,
    a.authors AS authors,
    a.month AS month,
    a.day AS day,
    j.name AS journal_name,
    properties(a) AS all_properties;

// ---------------------------------------------
// 11. 모든 Article 노드의 pmid 목록 확인
// ---------------------------------------------
// Article 노드들의 pmid 값 샘플 확인
MATCH (a:Article)
WHERE a.pmid IS NOT NULL
OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
RETURN 
    a.pmid AS pmid,
    a.title AS title,
    a.year AS year,
    j.name AS journal_name
ORDER BY a.pmid
LIMIT 20;

// ---------------------------------------------
// 12. pmid를 가진 Article 노드와 Journal 관계 확인
// ---------------------------------------------
// pmid 속성이 있는 Article 노드와 Journal 관계를 포함한 구조 확인
MATCH (a:Article)
WHERE a.pmid IS NOT NULL
OPTIONAL MATCH (a)-[:PUBLISHED_IN]->(j:Journal)
RETURN 
    a.pmid AS pmid,
    a.title AS title,
    a.year AS year,
    a.month AS month,
    a.day AS day,
    a.doi AS doi,
    a.authors AS authors,
    j.name AS journal_name
LIMIT 10;

