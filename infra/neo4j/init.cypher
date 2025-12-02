// =============================================
// Neo4j 초기 스키마 설정 (init.cypher)
// Bio/Med R&D Agentic Platform 용
// =============================================

// ---------------------------------------------
// 1. 노드 유니크 제약조건 (Constraints)
// ---------------------------------------------
// Protein: 유전자/단백질 심볼 기준
CREATE CONSTRAINT IF NOT EXISTS
FOR (p:Protein)
REQUIRE p.geneSymbol IS UNIQUE;

// Disease: 질병 이름 기준 (실제 운영에서는 ID 체계를 갖추는 게 좋음)
CREATE CONSTRAINT IF NOT EXISTS
FOR (d:Disease)
REQUIRE d.name IS UNIQUE;

// Publication: PubMed 논문
CREATE CONSTRAINT IF NOT EXISTS
FOR (p:Publication)
REQUIRE p.pmid IS UNIQUE;

// Trial: 임상시험 (예: ClinicalTrials.gov NCT ID)
CREATE CONSTRAINT IF NOT EXISTS
FOR (t:Trial)
REQUIRE t.nctId IS UNIQUE;

// Protocol: 실험 프로토콜 (protocols.io 등)
CREATE CONSTRAINT IF NOT EXISTS
FOR (pr:Protocol)
REQUIRE pr.protocolId IS UNIQUE;

// Experiment: 실제 실험/시뮬레이션 러닝 단위 (내부 expId)
CREATE CONSTRAINT IF NOT EXISTS
FOR (e:Experiment)
REQUIRE e.expId IS UNIQUE;

// SimulationResult: AlphaFold, RFdiffusion 등 결과
CREATE CONSTRAINT IF NOT EXISTS
FOR (s:SimulationResult)
REQUIRE s.simId IS UNIQUE;


// ---------------------------------------------
// 2. 인덱스 (검색 최적화용)
// ---------------------------------------------
CREATE INDEX IF NOT EXISTS
FOR (p:Protein)
ON (p.name);

CREATE INDEX IF NOT EXISTS
FOR (d:Disease)
ON (d.icdCode);

CREATE INDEX IF NOT EXISTS
FOR (pr:Protocol)
ON (pr.title);

CREATE INDEX IF NOT EXISTS
FOR (p:Publication)
ON (p.title);


// ---------------------------------------------
// 3. 샘플 데이터 (간단 데모용)
//    - 필요 없으면 아래 BLOCK 전체 삭제해도 됨
// ---------------------------------------------


// --- Protein 예시 ---
MERGE (p53:Protein {
  geneSymbol: 'TP53'
})
SET p53.name = 'Tumor protein p53',
    p53.uniprotId = 'P04637';

// --- Disease 예시 ---
MERGE (brca:Disease {
  name: 'Breast Cancer'
})
SET brca.icdCode = 'C50',
    brca.category = 'Malignant neoplasm';

// --- Publication (PubMed) 예시 ---
MERGE (paper:Publication {
  pmid: '12345678'
})
SET paper.title = 'p53 mutations in breast cancer',
    paper.year = 2020,
    paper.journal = 'Journal of Clinical Oncology',
    paper.doi = '10.1000/jco.123456',
    paper.source = 'pubmed';

// --- Trial (임상시험) 예시 ---
MERGE (trial:Trial {
  nctId: 'NCT00000001'
})
SET trial.title = 'Phase II study of targeted therapy in TP53-mutated breast cancer',
    trial.phase = 'Phase II',
    trial.status = 'RECRUITING';

// --- Protocol (protocols.io) 예시 ---
MERGE (proto:Protocol {
  protocolId: 'PROTO-001'
})
SET proto.title = 'In vitro assay for TP53 activity',
    proto.source = 'protocols.io',
    proto.version = '1.0';

// --- Experiment (내부 실험 엔티티) 예시 ---
MERGE (exp:Experiment {
  expId: 'EXP-0001'
})
SET exp.title = 'In vitro validation of TP53 activity in breast cancer cells',
    exp.type = 'in_vitro',
    exp.status = 'COMPLETED';

// --- SimulationResult (AlphaFold 예시) ---
MERGE (sim:SimulationResult {
  simId: 'SIM-ALPHAFOLD-0001'
})
SET sim.tool = 'AlphaFold3',
    sim.status = 'COMPLETED',
    sim.pdbPath = '/data/sim/alphafold3/TP53/model_1.pdb',
    sim.createdAt = datetime();


// ---------------------------------------------
// 4. 관계(Relationships) 샘플
// ---------------------------------------------

// Protein - Disease
MERGE (p53)-[:ASSOCIATED_WITH {evidence: 'literature'}]->(brca);

// Protein - Publication
MERGE (p53)<-[:MENTIONS_PROTEIN]-(paper);

// Disease - Publication
MERGE (brca)<-[:MENTIONS_DISEASE]-(paper);

// Trial - Disease
MERGE (trial)-[:TARGETS_DISEASE]->(brca);

// Trial - Publication
MERGE (trial)-[:HAS_PUBLICATION]->(paper);

// Protocol - Experiment
MERGE (exp)-[:USES_PROTOCOL]->(proto);

// Experiment - Disease / Protein
MERGE (exp)-[:TARGETS_DISEASE]->(brca);
MERGE (exp)-[:TARGETS_PROTEIN]->(p53);

// Experiment - SimulationResult
MERGE (exp)-[:HAS_SIMULATION_RESULT]->(sim);

// SimulationResult - Protein
MERGE (sim)-[:PREDICTS_STRUCTURE_OF]->(p53);

