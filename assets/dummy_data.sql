-- t_recommended_question 테이블 더미 데이터 삽입
-- 카테고리: P(논문), C(임상), T(프로토콜), S(시뮬레이션), R(결과 해석)
-- 상태: E(사용), D(Disabled), R(Removed)

INSERT INTO t_recommended_question (question_text, question_category, sort_order, status, created_at, updated_at) VALUES
('CRISPR-Cas9 유전자 편집 기술의 최신 연구 동향은 무엇인가요?', 'P', 1, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('단백질 구조 예측을 위한 딥러닝 모델에 대한 논문을 추천해주세요', 'P', 2, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('암 면역치료와 관련된 최근 5년간의 주요 논문들을 알려주세요', 'P', 3, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('RNA-seq 데이터 분석 방법론에 대한 리뷰 논문이 있나요?', 'P', 4, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('세포 분화 메커니즘 연구에서 중요한 논문들을 찾아주세요', 'P', 5, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('유전자 치료 임상시험의 현재 진행 상황은 어떠한가요?', 'C', 1, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('개인 맞춤형 암 치료의 임상 적용 사례를 알려주세요', 'C', 2, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('희귀질환 치료제 개발 현황에 대해 설명해주세요', 'C', 3, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('바이오마커를 활용한 조기 진단 방법의 임상 효과는?', 'C', 4, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('세포 배양 실험의 표준 프로토콜을 알려주세요', 'T', 1, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('PCR 실험을 수행하는 방법을 단계별로 설명해주세요', 'T', 2, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('단백질 추출 및 정제 프로토콜을 찾고 있습니다', 'T', 3, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('Western Blot 실험 절차를 자세히 알려주세요', 'T', 4, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('세포 사멸 분석을 위한 프로토콜이 있나요?', 'T', 5, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('단백질-리간드 결합 시뮬레이션을 어떻게 수행하나요?', 'S', 1, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('분자 동역학 시뮬레이션의 파라미터 설정 방법은?', 'S', 2, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('약물-단백질 상호작용 예측 시뮬레이션 도구를 추천해주세요', 'S', 3, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('세포 네트워크 모델링 시뮬레이션에 대해 설명해주세요', 'S', 4, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('RNA-seq 분석 결과의 fold change 해석 방법은?', 'R', 1, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('단백질 구조 예측 결과의 신뢰도를 어떻게 평가하나요?', 'R', 2, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('유전자 발현 데이터의 통계적 유의성을 판단하는 기준은?', 'R', 3, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('생물정보학 분석 결과를 논문에 표현하는 방법은?', 'R', 4, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('차등 발현 유전자 분석 결과를 해석하는 방법을 알려주세요', 'R', 5, 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- t_chat 테이블 더미 데이터 삽입
-- 상태: E(사용), D(Disabled), R(Removed)
-- pinned: Y(고정), N(일반)
-- archived: Y(보관), N(일반)
-- filter_type: P(논문), C(임상), T(프로토콜), S(시뮬레이션), R(결과 해석)
-- auto_mode: Y(자동), N(수동)

INSERT INTO t_chat (title, preview, status, pinned, archived, filter_type, auto_mode, created_id, updated_id, created_at, updated_at) VALUES
('CRISPR-Cas9 유전자 편집 기술 연구', 'CRISPR-Cas9 유전자 편집 기술의 최신 연구 동향에 대해 논의했습니다.', 'E', 'N', 'N', 'P', 'Y', 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('단백질 구조 예측 딥러닝 모델', '단백질 구조 예측을 위한 딥러닝 모델에 대한 논문 추천을 요청했습니다.', 'E', 'Y', 'N', 'P', 'Y', 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('암 면역치료 임상시험', '암 면역치료와 관련된 최근 5년간의 주요 논문들을 조회했습니다.', 'E', 'N', 'N', 'C', 'Y', 'user002', 'user002', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- t_chat_message 테이블 더미 데이터 삽입
-- role: U(User), A(Assistant)
-- sort_order: 메시지 순서 (1부터 시작)

-- Chat 1: CRISPR-Cas9 유전자 편집 기술 연구
INSERT INTO t_chat_message (chat_sid, role, content, sort_order, created_id, created_at) VALUES
(1, 'U', 'CRISPR-Cas9 유전자 편집 기술의 최신 연구 동향은 무엇인가요?', 1, 'user001', CURRENT_TIMESTAMP),
(1, 'A', 'CRISPR-Cas9 유전자 편집 기술은 최근 몇 년간 급속도로 발전하고 있습니다. 주요 동향으로는:\n\n1. **정밀도 향상**: Base editing과 Prime editing 기술로 더 정확한 편집이 가능해졌습니다.\n2. **전달 시스템 개선**: 비바이러스 벡터와 나노입자를 활용한 효율적인 전달 방법이 개발되었습니다.\n3. **임상 적용 확대**: 혈액 질환, 암, 유전 질환 등 다양한 질병에 대한 임상시험이 진행 중입니다.\n4. **안전성 개선**: Off-target 효과를 최소화하는 새로운 Cas 변형체들이 개발되고 있습니다.', 2, 'system', CURRENT_TIMESTAMP),
(1, 'U', '특히 암 치료 분야에서의 적용 사례를 더 자세히 알려주세요.', 3, 'user001', CURRENT_TIMESTAMP),
(1, 'A', '암 치료 분야에서 CRISPR-Cas9는 주로 CAR-T 세포 치료에 활용되고 있습니다:\n\n- **CAR-T 세포 제조**: 환자의 T세포를 추출하여 암 세포를 인식하는 CAR(Chimeric Antigen Receptor) 유전자를 삽입\n- **면역 억제 회피**: PD-1, CTLA-4 등 면역 체크포인트 유전자를 제거하여 항암 효과 증대\n- **안전성 강화**: Allogeneic CAR-T 세포 제조 시 거부 반응을 줄이기 위한 유전자 편집\n\n현재 급성 림프구성 백혈병(ALL), 비호지킨 림프종 등에서 유망한 결과를 보이고 있습니다.', 4, 'system', CURRENT_TIMESTAMP);

-- Chat 2: 단백질 구조 예측 딥러닝 모델
INSERT INTO t_chat_message (chat_sid, role, content, sort_order, created_id, created_at) VALUES
(2, 'U', '단백질 구조 예측을 위한 딥러닝 모델에 대한 논문을 추천해주세요', 1, 'user001', CURRENT_TIMESTAMP),
(2, 'A', '단백질 구조 예측 분야의 주요 딥러닝 모델 논문들을 추천드립니다:\n\n1. **AlphaFold2** (Nature, 2021)\n   - Google DeepMind의 획기적인 단백질 구조 예측 모델\n   - 거의 실험 수준의 정확도 달성\n\n2. **RoseTTAFold** (Science, 2021)\n   - University of Washington의 오픈소스 모델\n   - AlphaFold2보다 빠른 예측 속도\n\n3. **ESMFold** (Science, 2022)\n   - Meta의 대규모 언어 모델 기반 접근법\n   - 단백질 서열만으로 구조 예측 가능\n\n4. **OmegaFold** (Nature Machine Intelligence, 2022)\n   - 중국 연구팀의 경량화 모델\n   - 높은 정확도와 효율성', 2, 'system', CURRENT_TIMESTAMP);

INSERT INTO t_chat_message (chat_sid, role, content, sort_order, created_id, created_at) VALUES
(3, 'U', 'EGFR 변이 단백질에 새로운 저분자 후보 약물을 투여했을 때, 결합 안정성과 신호전달 억제 효과를 시뮬레이션으로 보고 싶어요.', 1, 'user001', CURRENT_TIMESTAMP),
(3, 'A', '연구 목적을 정리하면 **"EGFR 변이 단백질–후보 약물 간 결합 안정성과 저해 가능성 평가 + 필요 시 단백질/리간드 설계"**입니다.
아래와 같은 워크플로우로 시뮬레이션 파이프라인을 구성해보겠습니다.

**1. 단계. 단백질 구조 확보·정제**

도구: AlphaFold / ColabFold
변이가 포함된 EGFR 서열을 AlphaFold 또는 ColabFold에 입력해 3D 구조를 예측합니다.
기존 PDB 구조가 있다면, ColabFold로 와일드타입 vs 변이 구조를 함께 비교하며 정제합니다.
활성 부위(ATP 결합 부위, TK 도메인 등)를 중심으로 품질이 좋은 모델을 선택합니다.

**2. 단계. 단백질/결합부위 설계(옵션)**

도구: RFdiffusion + ProteinMPNN
만약 새로운 결합 포켓 생성 또는 안정성 향상을 원하면, RFdiffusion을 사용해 EGFR 주변에 원하는 형상의 결합 부위를 제안받습니다.
RFdiffusion이 제안한 구조를 기반으로 ProteinMPNN을 이용해 해당 구조를 지지할 수 있는 아미노산 서열을 최적화합니다.
이렇게 얻은 후보 서열을 다시 AlphaFold/ColabFold로 접어 구조를 검증합니다.
이 단계는 "단백질 자체를 조금 설계해서 약물이 더 잘 붙게 하거나 안정성을 올리고 싶을 때" 선택적으로 사용합니다.

**3. 단계. 도킹 및 결합 안정성 평가**

도구: DiffDock
위에서 얻은 EGFR 구조(원본 또는 설계 버전)에 후보 저분자 약물을 입력해 DiffDock으로 도킹을 수행합니다.
여러 포즈 중 결합 에너지·입체적 충돌·활성 부위 차단 여부를 기준으로 상위 포즈를 선별합니다.
필요하다면 선택된 포즈를 기반으로 후속 분자동역학(MD) 시뮬레이션 또는 에너지 분석을 추가합니다(플랫폼 내 다른 모듈과 연동).

**4. 단계. 결과 정리 및 비교 해석**

기존 EGFR 저해제와 같은 조건으로 DiffDock/시뮬레이션을 돌려 결합 에너지, 결합부위 중첩 정도, 상호작용 잔기 패턴을 비교합니다.
"후보 약물이 기존 약물과 유사하거나 더 유리한 결합 양상을 보이는지" 중심으로 자동 리포트를 생성합니다.
리포트에는 "추가 in vitro 검증 필요 포인트"와 "추가로 시뮬레이션해볼 조건(농도, 변이 조합 등)"도 함께 제안합니다.', 2, 'system', CURRENT_TIMESTAMP);


-- Chat 6: Eukaryotic cell 설명 (마크다운 테이블 포함)
INSERT INTO t_chat (title, preview, status, pinned, archived, filter_type, auto_mode, created_id, updated_id, created_at, updated_at) VALUES
('Eukaryotic cell 설명', 'Eukaryotic cell(진핵세포)에 대한 상세한 설명을 요청했습니다.', 'E', 'N', 'N', 'P', 'Y', 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

INSERT INTO t_chat_message (chat_sid, role, content, sort_order, created_id, created_at) VALUES
(6, 'U', 'Eukaryotic cell이 뭐야?', 1, 'user001', CURRENT_TIMESTAMP),
(6, 'A', 'Eukaryotic cell(진핵세포)는 분명한 막으로 둘러싸인 핵과 다양한 세포 소기관을 지니는 진핵생물을 구성하는 기본 단위입니다. 진핵세포는 박테리아 및 고세균과 같은 원핵세포(prokaryote)와 구별되며, 동물, 식물, 곰팡이, 그리고 많은 단세포 생물이 이에 해당합니다.

**1. 진핵세포란 무엇인가?**

핵심 정의:
진핵세포는 유전물질(DNA)이 핵막으로 둘러싸인 '핵' 내에 저장되어 있는 세포입니다. 이 점이 원핵세포와의 가장 큰 차별점이며, 동물, 식물, 곰팡이, 해조류 등 모든 다세포 생명체의 기본 구조입니다.

이름 유래:
'Eukaryote'는 그리스어 'eu(좋은, 참된)' + 'karyon(견과, 핵)'에서 유래되었습니다. 즉, '참된 핵을 가진 세포'를 뜻합니다.

**2. 주요 구조적 특징**

핵(Nucleus):
이중막(핵막)으로 둘러싸여 있으며, 유전정보(염색체)가 저장 및 관리됩니다. 핵막에는 핵공(구멍)이 있어 물질이 출입할 수 있습니다.

세포 소기관(Organelles, 막으로 경계됨):
• 미토콘드리아: "세포 발전소"로 불리며, 산소를 사용해 에너지원(ATP) 생성.
• 골지체(Golgi apparatus): 단백질을 변형, 분류, 수송.
• 소포체(Endoplasmic Reticulum, ER): 단백질 및 지질 합성, 운반.
• 리소좀: 분해효소 보유, 세포 내 대사 및 청소 담당.
• 엽록체(Chloroplast): 식물/일부 조류에서 발견, 광합성 담당(내부 DNA 보유).

세포골격(Cytoskeleton):
액틴 마이크로필라멘트, 미세소관 등으로 복잡하게 구성되어 세포 형태 유지, 이동, 내부 운송, 세포분열에 기여.

생식 및 분열:
• 유성 생식: 감수분열 및 배우자(난자·정자) 융합을 통해 유전적 다양성 확보.
• 무성 분열: 체세포분열(유사분열, mitosis)을 통해 새로운 개체 생성.

**3. 진핵세포의 다양성과 진화**

생물 다양성:
가장 거대한 청목균류(glaucophytes)부터 블루웰, 거대나무에 이르기까지 단세포부터 다세포에 이르기까지 다양한 생명체를 구성합니다. 단세포 진핵생물(예: 원생생물)과 다세포 진핵생물(동물, 식물, 곰팡이 등) 모두 포함합니다.

기원 및 진화:
진핵세포는 약 16~28억 년 전, 고세균(특히 Promethearchaeota) 조상과 산소흡성 세균이 내공생(symbiogenesis)을 통해 탄생했다고 추정됩니다. 이 내공생 과정은 미토콘드리아(산소호흡), 아울러 식물에서는 시아노박테리아의 추가 내공생으로 엽록체(광합성)가 유래하였습니다.

다세포성 및 계통 분화:
복잡한 다세포 생명체는 진핵생물 내에서 반복적으로 독립적으로 진화하였으며, 진핵세포의 크기는 원핵세포의 약 10,000배에 달할 정도로 큽니다.

**4. 진핵세포의 기능적 특징**

세포 내 수송/물질대사:
내부 막구조(소포, 소포체, 골지체 등)와 소기관 간의 복잡한 분자 수송, 에너지 대사, 단백질 가공 및 분해 과정이 발달되어 있습니다.

세포골격 및 이동:
액틴, 마이오신, 튜불린 등으로 구성된 세포골격을 활용하여 세포 움직임, 구조유지, 분열 및 내·외부 물질 운반에 관여합니다.

유전 및 생식:
유성(감수분열, 배우자 융합) 및 무성(유사분열) 생식을 통한 유전자 재조합 및 다양성 부여.

**5. 진핵세포와 원핵세포의 주요 차이**

| 특징 | 진핵세포 | 원핵세포 |
|------|---------|---------|
| 핵 구조 | 핵막으로 둘러싼 핵 존재 | 핵 없음(유전물질 노출) |
| 소기관 | 다양한 막성 소기관 있음 | 없음 |
| 크기 | 대체로 큼(10,000배 이상) | 대체로 작음 |
| 세포골격 | 잘 발달함 | 발달 미약 또는 없음 |
| 분열 방식 | 유사/감수분열 | 이분법적 분열 |
| 생식 방법 | 유성 및 무성 생식 | 주로 무성 생식 |

**6. 최근 과학적 연구 동향**

진핵세포 기원의 분자생물학적, 구조생물학적 증거(예: 고세균에서 진핵세포형 세포골격 확인 등)가 꾸준히 축적되고 있습니다. 고해상도 이미징(크라이오전자현미경 등)을 통한 세포 구조 연구가 활성화되어 세포의 미세환경 이해가 증진되고 있습니다.', 2, 'system', CURRENT_TIMESTAMP);

-- t_chat_reference 테이블 더미 데이터 삽입
-- source: P(PubMed), W(Web), N(NIH), T(PROTOCOL)
-- badge: H(High), M(Medium), L(Low)
-- journal: J(Journal), B(Book), R(Report), P(Protocol)
-- Chat 6 (Eukaryotic cell 설명)의 assistant 메시지(message_sid=2)에 연결

INSERT INTO t_chat_reference (chat_sid, message_sid, source, badge, title, description, journal, link, ref_pubmed_id, ref_date, ref_authors, sort_order, created_at) VALUES
(6, 2, 'P', 'H', 'The emerging view on the origin and early evolution of eukaryotic cells.', 'The origin of the eukaryotic cell, with its compartmentalized nature and generally large size compared with bacterial and archaeal cells, represents a cornerstone events in th...', 'J', 'PubMed : 39261613', '39261613', '2024-09-12'::timestamp, 'Vosseberg J et al.', 1, CURRENT_TIMESTAMP),
(6, 2, 'P', 'H', 'Eukaryotic cells.', '', 'J', 'PubMed : 21592757', '21592757', '2011-05-20'::timestamp, 'Hetzer M et al.', 2, CURRENT_TIMESTAMP),
(6, 2, 'W', 'L', 'Prokaryotes vs Eukaryotes: Key Cell Differences', 'Eukaryotic cells are cells containing membrane-bound organelles and are the basis for both unicellular and multicellular organisms.', 'J', '', NULL, '2025-06-08'::timestamp, '', 3, CURRENT_TIMESTAMP),
(6, 2, 'W', 'L', 'Intro to eukaryotic cells (article)', 'Overview of eukaryotic cells and how they differ from prokaryotic cells (nucleus, membrane-bound organelles, and linear chromosomes).', 'J', '', NULL, NULL, '', 4, CURRENT_TIMESTAMP),
(6, 2, 'P', 'H', 'Cell structure and function in eukaryotic organisms', 'Comprehensive analysis of structural components and their functional roles in eukaryotic cells, including organelle interactions.', 'J', 'PubMed : 30154821', '30154821', '2023-03-15'::timestamp, 'Thompson A et al.', 5, CURRENT_TIMESTAMP),
(6, 2, 'P', 'L', 'Comparative genomics of eukaryotic cells', 'A comparative study examining genomic features across various eukaryotic cell types and organisms.', 'J', 'PubMed : 28934567', '28934567', '2022-11-08'::timestamp, 'Martinez L et al.', 6, CURRENT_TIMESTAMP),
(6, 2, 'W', 'L', 'Eukaryotic Cell Biology - Comprehensive Guide', 'Detailed educational resource covering all aspects of eukaryotic cell biology, from basic structure to advanced molecular mechanisms.', 'J', '', NULL, '2024-02-20'::timestamp, '', 7, CURRENT_TIMESTAMP),
(6, 2, 'P', 'H', 'Molecular mechanisms in eukaryotic cell division', 'Investigation of key molecular pathways and regulatory mechanisms controlling cell division in eukaryotic organisms.', 'J', 'PubMed : 32456789', '32456789', '2023-07-22'::timestamp, 'Chen Y et al.', 8, CURRENT_TIMESTAMP),
(6, 2, 'P', 'L', 'Evolution and diversity of eukaryotic cells', 'Exploring the evolutionary history and remarkable diversity of eukaryotic cell types across different kingdoms of life.', 'J', 'PubMed : 29876543', '29876543', '2023-05-10'::timestamp, 'Anderson R et al.', 9, CURRENT_TIMESTAMP);

-- t_paper_graph 테이블 더미 데이터 삽입
INSERT INTO t_paper_graph (graph_title, graph_description, status, created_id, updated_id, created_at, updated_at) VALUES
('관련 논문 네트워크', '논문 간 인용 관계를 시각화한 그래프', 'E', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- t_paper_node 테이블 더미 데이터 삽입 (graph_sid=1)
INSERT INTO t_paper_node (graph_sid, paper_id, paper_label, node_size, node_color, x_position, y_position, created_id, created_at) VALUES
(1, 'cobo-2011', 'Cobo, 2011', 35, '#9E7B9E', 0.00, 0.00, 'system', CURRENT_TIMESTAMP),
(1, 'eck-2010', 'Eck, 2010', 28, '#7B9E9E', -2.00, -1.00, 'system', CURRENT_TIMESTAMP),
(1, 'eck-2009', 'Eck, 2009', 30, '#7B9E9E', -1.50, 1.50, 'system', CURRENT_TIMESTAMP),
(1, 'callon-1991', 'Callon, 1991', 25, '#9E9E9E', -2.50, 1.00, 'system', CURRENT_TIMESTAMP),
(1, 'waltman-2010', 'Waltman, 2010', 22, '#9E9E9E', -3.00, -0.50, 'system', CURRENT_TIMESTAMP),
(1, 'noyons-1999', 'Noyons, 1999', 22, '#9E9E9E', -3.50, -1.50, 'system', CURRENT_TIMESTAMP),
(1, 'small-1999', 'Small, 1999', 20, '#9E9E9E', -3.00, 0.50, 'system', CURRENT_TIMESTAMP),
(1, 'coulter-1998', 'Coulter, 1998', 18, '#9E9E9E', -3.00, 1.50, 'system', CURRENT_TIMESTAMP),
(1, 'callon-1983', 'Callon, 1983', 20, '#9E9E9E', -2.50, 2.50, 'system', CURRENT_TIMESTAMP),
(1, 'small-1973', 'Small, 1973', 26, '#9E9E9E', -4.50, -1.00, 'system', CURRENT_TIMESTAMP),
(1, 'kessler-1963', 'Kessler, 1963', 24, '#9E9E9E', -5.00, 0.00, 'system', CURRENT_TIMESTAMP),
(1, 'bornner-2005', 'Bornner, 2005', 22, '#9E9E9E', -2.00, 2.00, 'system', CURRENT_TIMESTAMP),
(1, 'boyack-2004', 'Boyack, 2004', 20, '#9E9E9E', -1.50, 3.00, 'system', CURRENT_TIMESTAMP),
(1, 'rusydiana-2021', 'Rusydiana, 2021', 18, '#5B7E8E', -4.50, 2.50, 'system', CURRENT_TIMESTAMP),
(1, 'aria-2017', 'Aria, 2017', 32, '#5B8E7E', 1.50, 0.00, 'system', CURRENT_TIMESTAMP),
(1, 'bales-2019', 'Bales, 2019', 24, '#5B8E7E', 1.00, -1.50, 'system', CURRENT_TIMESTAMP),
(1, 'cobo-2012', 'Cobo, 2012', 20, '#5B8E7E', 0.50, 1.00, 'system', CURRENT_TIMESTAMP),
(1, 'eck-2014', 'Eck, 2014', 20, '#7B9E9E', -1.00, -2.00, 'system', CURRENT_TIMESTAMP),
(1, 'smyrnova-trybulska-2017', 'Smyrnova-Trybulska, 2017', 28, '#7B9E9E', 1.50, -3.00, 'system', CURRENT_TIMESTAMP),
(1, 'lou-2020', 'Lou, 2020', 22, '#5B8E7E', 2.50, -2.00, 'system', CURRENT_TIMESTAMP),
(1, 'ju-2018', 'Ju, 2018', 20, '#5B8E7E', 3.00, -1.00, 'system', CURRENT_TIMESTAMP),
(1, 'moral-munoz-2020', 'Moral Munoz, 2020', 24, '#5B8E7E', 2.00, -0.50, 'system', CURRENT_TIMESTAMP),
(1, 'moral-munoz-2019', 'Moral Munoz, 2019', 22, '#5B8E7E', 2.50, 0.50, 'system', CURRENT_TIMESTAMP),
(1, 'moral-munoz-2014', 'Moral Munoz, 2014', 20, '#5B8E7E', 2.00, 1.50, 'system', CURRENT_TIMESTAMP),
(1, 'baier-fuentes-2018', 'Baier Fuentes, 2018', 22, '#5B8E7E', 3.00, -2.50, 'system', CURRENT_TIMESTAMP),
(1, 'baier-fuentes-2021', 'Baier Fuentes, 2021', 20, '#5B8E7E', 3.50, -0.50, 'system', CURRENT_TIMESTAMP),
(1, 'guerrero-2019', 'Guerrero, 2019', 20, '#5B8E7E', 3.50, -2.00, 'system', CURRENT_TIMESTAMP),
(1, 'cobo-2018', 'Cobo, 2018', 20, '#5B8E7E', 2.50, 1.50, 'system', CURRENT_TIMESTAMP),
(1, 'cobo-2015', 'Cobo, 2015', 18, '#5B8E7E', 1.50, 2.00, 'system', CURRENT_TIMESTAMP),
(1, 'martinez-2015', 'Martinez, 2015', 18, '#5B8E7E', 1.00, 2.50, 'system', CURRENT_TIMESTAMP),
(1, 'cobo-2017', 'Cobo, 2017', 18, '#5B8E7E', 2.00, 2.50, 'system', CURRENT_TIMESTAMP),
(1, 'gutierrez-salcedo-2017', 'Gutierrez Salcedo, 2017', 20, '#5B8E7E', 1.50, 1.50, 'system', CURRENT_TIMESTAMP),
(1, 'herrera-viedma-2016', 'Herrera Viedma, 2016', 18, '#5B8E7E', 1.00, 3.00, 'system', CURRENT_TIMESTAMP),
(1, 'murgado-armenteros-2014', 'Murgado Armenteros, 2014', 20, '#5B8E7E', 0.50, 3.00, 'system', CURRENT_TIMESTAMP),
(1, 'martinez-2014', 'Martinez, 2014', 20, '#5B8E7E', 0.00, 3.50, 'system', CURRENT_TIMESTAMP),
(1, 'jiang-2019', 'Jiang, 2019', 22, '#5B8E7E', 1.00, 4.00, 'system', CURRENT_TIMESTAMP),
(1, 'martinez-estevez-2022', 'Martinez Estevez, 2022', 18, '#5B8E7E', 3.00, 2.50, 'system', CURRENT_TIMESTAMP),
(1, 'salovic-2022', 'Salovic, 2022', 18, '#5B8E7E', 3.50, 1.00, 'system', CURRENT_TIMESTAMP);

-- t_paper_edge 테이블 더미 데이터 삽입 (graph_sid=1)
INSERT INTO t_paper_edge (graph_sid, source_paper_id, target_paper_id, edge_size, edge_color, created_at) VALUES
-- Central cluster connections
(1, 'cobo-2011', 'eck-2010', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2011', 'eck-2009', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2011', 'aria-2017', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2011', 'cobo-2012', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2011', 'gutierrez-salcedo-2017', 1, NULL, CURRENT_TIMESTAMP),
(1, 'eck-2010', 'eck-2009', 1, NULL, CURRENT_TIMESTAMP),
(1, 'eck-2010', 'waltman-2010', 1, NULL, CURRENT_TIMESTAMP),
(1, 'eck-2010', 'noyons-1999', 1, NULL, CURRENT_TIMESTAMP),
(1, 'eck-2010', 'eck-2014', 1, NULL, CURRENT_TIMESTAMP),
(1, 'eck-2009', 'callon-1991', 1, NULL, CURRENT_TIMESTAMP),
(1, 'eck-2009', 'bornner-2005', 1, NULL, CURRENT_TIMESTAMP),
(1, 'callon-1991', 'callon-1983', 1, NULL, CURRENT_TIMESTAMP),
(1, 'callon-1991', 'coulter-1998', 1, NULL, CURRENT_TIMESTAMP),
(1, 'callon-1991', 'small-1999', 1, NULL, CURRENT_TIMESTAMP),
(1, 'waltman-2010', 'noyons-1999', 1, NULL, CURRENT_TIMESTAMP),
(1, 'noyons-1999', 'small-1973', 1, NULL, CURRENT_TIMESTAMP),
(1, 'small-1973', 'kessler-1963', 1, NULL, CURRENT_TIMESTAMP),
(1, 'boyack-2004', 'bornner-2005', 1, NULL, CURRENT_TIMESTAMP),
(1, 'rusydiana-2021', 'small-1973', 1, NULL, CURRENT_TIMESTAMP),
(1, 'aria-2017', 'bales-2019', 1, NULL, CURRENT_TIMESTAMP),
(1, 'aria-2017', 'moral-munoz-2020', 1, NULL, CURRENT_TIMESTAMP),
(1, 'aria-2017', 'moral-munoz-2019', 1, NULL, CURRENT_TIMESTAMP),
(1, 'aria-2017', 'cobo-2012', 1, NULL, CURRENT_TIMESTAMP),
(1, 'aria-2017', 'gutierrez-salcedo-2017', 1, NULL, CURRENT_TIMESTAMP),
(1, 'bales-2019', 'smyrnova-trybulska-2017', 1, NULL, CURRENT_TIMESTAMP),
(1, 'bales-2019', 'lou-2020', 1, NULL, CURRENT_TIMESTAMP),
(1, 'smyrnova-trybulska-2017', 'lou-2020', 1, NULL, CURRENT_TIMESTAMP),
(1, 'smyrnova-trybulska-2017', 'baier-fuentes-2018', 1, NULL, CURRENT_TIMESTAMP),
(1, 'lou-2020', 'ju-2018', 1, NULL, CURRENT_TIMESTAMP),
(1, 'lou-2020', 'baier-fuentes-2018', 1, NULL, CURRENT_TIMESTAMP),
(1, 'ju-2018', 'baier-fuentes-2018', 1, NULL, CURRENT_TIMESTAMP),
(1, 'ju-2018', 'moral-munoz-2020', 1, NULL, CURRENT_TIMESTAMP),
(1, 'moral-munoz-2020', 'moral-munoz-2019', 1, NULL, CURRENT_TIMESTAMP),
(1, 'moral-munoz-2020', 'baier-fuentes-2021', 1, NULL, CURRENT_TIMESTAMP),
(1, 'moral-munoz-2020', 'guerrero-2019', 1, NULL, CURRENT_TIMESTAMP),
(1, 'moral-munoz-2019', 'moral-munoz-2014', 1, NULL, CURRENT_TIMESTAMP),
(1, 'moral-munoz-2019', 'gutierrez-salcedo-2017', 1, NULL, CURRENT_TIMESTAMP),
(1, 'baier-fuentes-2018', 'baier-fuentes-2021', 1, NULL, CURRENT_TIMESTAMP),
(1, 'baier-fuentes-2021', 'guerrero-2019', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2012', 'cobo-2018', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2018', 'cobo-2015', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2018', 'cobo-2017', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2018', 'martinez-estevez-2022', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2015', 'martinez-2015', 1, NULL, CURRENT_TIMESTAMP),
(1, 'cobo-2017', 'martinez-estevez-2022', 1, NULL, CURRENT_TIMESTAMP),
(1, 'gutierrez-salcedo-2017', 'moral-munoz-2014', 1, NULL, CURRENT_TIMESTAMP),
(1, 'gutierrez-salcedo-2017', 'herrera-viedma-2016', 1, NULL, CURRENT_TIMESTAMP),
(1, 'gutierrez-salcedo-2017', 'murgado-armenteros-2014', 1, NULL, CURRENT_TIMESTAMP),
(1, 'herrera-viedma-2016', 'martinez-2014', 1, NULL, CURRENT_TIMESTAMP),
(1, 'murgado-armenteros-2014', 'martinez-2014', 1, NULL, CURRENT_TIMESTAMP),
(1, 'martinez-2014', 'jiang-2019', 1, NULL, CURRENT_TIMESTAMP),
(1, 'salovic-2022', 'martinez-estevez-2022', 1, NULL, CURRENT_TIMESTAMP);

-- t_chat_message_paper_graph 테이블 더미 데이터 삽입
-- Chat 6 (Eukaryotic cell 설명)의 assistant 메시지에 논문 그래프(graph_sid=1) 연결
-- 참고: message_sid는 SERIAL이므로 자동 증가합니다. Chat 6의 assistant 메시지는 
-- Chat 1(4개) + Chat 2(2개) + Chat 3(4개) + Chat 4(4개) + Chat 5(4개) + Chat 6의 첫 번째 메시지(1개) = 19번째 메시지 이후
-- 따라서 Chat 6의 assistant 메시지는 message_sid=20입니다.
-- 하지만 실제 데이터베이스에서 확인 후 수정이 필요할 수 있습니다.
INSERT INTO t_chat_message_paper_graph (message_sid, graph_sid, sort_order, created_id, created_at) VALUES
(6, 1, 0, 'system', CURRENT_TIMESTAMP);

-- t_schedule 테이블 더미 데이터 삽입
-- schedule_type: E(실험), M(미팅), A(분석), S(세미나)
-- schedule_status: E(예정), R(진행중), C(완료)
-- repeat_type: N(반복 안 함), D(매일), W(매주), M(매월), Y(매년)
-- is_all_day: Y(하루 종일), N(시간 설정)
-- use_yn: Y(노출), N(삭제/미노출)

INSERT INTO t_schedule (title, description, schedule_type, schedule_status, use_yn, start_date, end_date, is_all_day, location, color, linked_note_sid, repeat_type, created_id, updated_id, created_at, updated_at) VALUES
('PCR 반응 조건 최적화', 'PCR 반응 조건을 최적화하기 위한 실험입니다. 다양한 온도와 시간 조건을 테스트하여 최적의 결과를 도출합니다.', 'E', 'E', 'Y', '2025-11-30 10:00:00'::timestamp, '2025-11-30 12:00:00'::timestamp, 'N', '3층 실험실 A', '#3b82f6', NULL, 'N', 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('주간 연구 진행 보고', '주간 연구 진행 상황을 공유하고 다음 주 계획을 논의합니다.', 'M', 'E', 'Y', '2025-11-30 14:00:00'::timestamp, '2025-11-30 15:30:00'::timestamp, 'N', '회의실 B', '#8b5cf6', NULL, 'N', 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('세포 배양 관찰', '세포 배양 상태를 현미경으로 관찰하고 기록합니다.', 'E', 'R', 'Y', '2025-11-30 16:00:00'::timestamp, '2025-11-30 17:00:00'::timestamp, 'N', '4층 세포배양실', '#10b981', NULL, 'N', 'user002', 'user002', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- ============================================
-- 공통 코드 테이블 더미 데이터 삽입
-- ============================================

-- tc_common: 공통 코드 그룹
-- common_code 규칙: 약자+숫자3자리 (예: SCH001, CHT001, EXP001 등)

INSERT INTO tc_common (common_code, common_name, description, use_yn, created_id, updated_id, created_at, updated_at) VALUES
-- 일정 관련 코드
('SCH001', '일정 타입', '일정의 종류를 구분하는 코드', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCH002', '일정 상태', '일정의 진행 상태를 나타내는 코드', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCH003', '반복 타입', '일정의 반복 주기를 나타내는 코드', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 채팅 관련 코드
('CHT001', '채팅 메시지 역할', '채팅 메시지의 발신자 역할 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHT002', '채팅 참고 문헌 소스', '채팅 참고 문헌의 출처 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHT003', '채팅 참고 문헌 배지', '채팅 참고 문헌의 중요도 배지', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHT004', '채팅 참고 문헌 저널', '채팅 참고 문헌의 저널 타입', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHT005', '채팅 필터 타입', '채팅의 필터 타입 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 실험 관련 코드
('EXP001', '실험 상태', '실험의 진행 상태를 나타내는 코드', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('EXP002', '실험 결과 타입', '실험 결과 파일의 타입 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 사용자 관련 코드
('USR001', '사용자 상태', '사용자의 계정 상태 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 알림 관련 코드
('NOT001', '알림 타입', '알림의 종류를 구분하는 코드', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('NOT002', '알림 읽음 여부', '알림의 읽음 상태 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 피드백 관련 코드
('FDB001', '피드백 카테고리', '피드백의 카테고리 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 추천 질문 관련 코드
('QST001', '추천 질문 카테고리', '추천 질문의 카테고리 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('QST002', '추천 질문 상태', '추천 질문의 사용 상태 구분', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 공통 사용 여부 코드
('COM001', '사용 여부', '일반적인 사용 여부 구분 코드', 'Y', 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- tc_common_item: 공통 코드 항목
-- common_item_code 규칙: 약자+숫자3자리 (예: SCH001001, CHT001001 등)

INSERT INTO tc_common_item (common_item_code, common_code, common_item_name, description, use_yn, sort_order, created_id, updated_id, created_at, updated_at) VALUES
-- 일정 타입 (SCH001)
('SCI001', 'SCH001', '실험', '실험 관련 일정', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCI002', 'SCH001', '미팅', '미팅 관련 일정', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCI003', 'SCH001', '분석', '분석 관련 일정', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCI004', 'SCH001', '세미나', '세미나 관련 일정', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 일정 상태 (SCH002)
('SCS001', 'SCH002', '예정', '일정이 예정된 상태', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCS002', 'SCH002', '진행중', '일정이 진행 중인 상태', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCS003', 'SCH002', '완료', '일정이 완료된 상태', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 반복 타입 (SCH003)
('SCR001', 'SCH003', '반복 안 함', '반복하지 않는 일정', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCR002', 'SCH003', '매일', '매일 반복하는 일정', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCR003', 'SCH003', '매주', '매주 반복하는 일정', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCR004', 'SCH003', '매월', '매월 반복하는 일정', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('SCR005', 'SCH003', '매년', '매년 반복하는 일정', 'Y', 5, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 채팅 메시지 역할 (CHT001)
('CHR001', 'CHT001', '사용자', '사용자가 작성한 메시지', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHR002', 'CHT001', '어시스턴트', 'AI 어시스턴트가 작성한 메시지', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 채팅 참고 문헌 소스 (CHT002)
('CHS001', 'CHT002', 'PubMed', 'PubMed에서 가져온 참고 문헌', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHS002', 'CHT002', 'Web', '웹에서 가져온 참고 문헌', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHS003', 'CHT002', 'NIH', 'NIH에서 가져온 참고 문헌', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHS004', 'CHT002', 'PROTOCOL', '프로토콜에서 가져온 참고 문헌', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 채팅 참고 문헌 배지 (CHT003)
('CHB001', 'CHT003', 'High', '높은 중요도의 참고 문헌', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHB002', 'CHT003', 'Medium', '중간 중요도의 참고 문헌', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CHB003', 'CHT003', 'Low', '낮은 중요도의 참고 문헌', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 채팅 참고 문헌 저널 (CHT004)
('RFT001', 'CHT004', 'Journal', '학술지 형태의 참고 문헌', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('RFT002', 'CHT004', 'Book', '도서 형태의 참고 문헌', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('RFT003', 'CHT004', 'Report', '보고서 형태의 참고 문헌', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('RFT004', 'CHT004', 'Protocol', '프로토콜 형태의 참고 문헌', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 채팅 필터 타입 (CHT005)
('CFT001', 'CHT005', '논문', '논문 관련 필터', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CFT002', 'CHT005', '임상', '임상 관련 필터', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CFT003', 'CHT005', '프로토콜', '프로토콜 관련 필터', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CFT004', 'CHT005', '시뮬레이션', '시뮬레이션 관련 필터', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('CFT005', 'CHT005', '결과 해석', '결과 해석 관련 필터', 'Y', 5, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 실험 상태 (EXP001)
('EXS001', 'EXP001', '준비', '실험이 준비된 상태', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('EXS002', 'EXP001', '진행중', '실험이 진행 중인 상태', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('EXS003', 'EXP001', '완료', '실험이 완료된 상태', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 실험 결과 타입 (EXP002)
('ERT001', 'EXP002', 'PDB', 'PDB 파일 형식', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('ERT002', 'EXP002', 'FASTA', 'FASTA 파일 형식', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('ERT003', 'EXP002', 'PDF', 'PDF 파일 형식', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('ERT004', 'EXP002', 'TXT', '텍스트 파일 형식', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('ERT005', 'EXP002', 'LOG', '로그 파일 형식', 'Y', 5, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('ERT006', 'EXP002', 'CSV', 'CSV 파일 형식', 'Y', 6, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 사용자 상태 (USR001)
('USS001', 'USR001', '활성', '활성 상태의 사용자', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('USS002', 'USR001', '비활성', '비활성 상태의 사용자', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 알림 타입 (NOT001)
('NTI001', 'NOT001', '실험', '실험 관련 알림', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('NTI002', 'NOT001', '미팅', '미팅 관련 알림', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('NTI003', 'NOT001', '분석', '분석 관련 알림', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('NTI004', 'NOT001', '세미나', '세미나 관련 알림', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 알림 읽음 여부 (NOT002)
('NTS001', 'NOT002', '읽음', '알림을 읽은 상태', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('NTS002', 'NOT002', '읽지 않음', '알림을 읽지 않은 상태', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 피드백 카테고리 (FDB001)
('FCT001', 'FDB001', '일반', '일반적인 피드백', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('FCT002', 'FDB001', '버그', '버그 신고 피드백', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('FCT003', 'FDB001', '기능', '기능 요청 피드백', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('FCT004', 'FDB001', '개선', '개선 제안 피드백', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 추천 질문 카테고리 (QST001)
('QSC001', 'QST001', '논문', '논문 관련 추천 질문', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('QSC002', 'QST001', '임상', '임상 관련 추천 질문', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('QSC003', 'QST001', '프로토콜', '프로토콜 관련 추천 질문', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('QSC004', 'QST001', '시뮬레이션', '시뮬레이션 관련 추천 질문', 'Y', 4, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('QSC005', 'QST001', '결과 해석', '결과 해석 관련 추천 질문', 'Y', 5, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 추천 질문 상태 (QST002)
('QSS001', 'QST002', '사용', '사용 중인 추천 질문', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('QSS002', 'QST002', '비활성', '비활성화된 추천 질문', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('QSS003', 'QST002', '삭제', '삭제된 추천 질문', 'Y', 3, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
-- 사용 여부 (COM001)
('COU001', 'COM001', '사용', '사용 중인 항목', 'Y', 1, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('COU002', 'COM001', '미사용', '사용하지 않는 항목', 'Y', 2, 'system', 'system', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- ============================================
-- t_user_calendar 테이블 더미 데이터 삽입
-- ============================================
-- is_visible: 1(보임), 0(숨김)
-- sort_order: 정렬 순서 (낮을수록 먼저 표시)

INSERT INTO t_user_calendar (calendar_name, color, is_visible, sort_order, created_id, updated_id, created_at, updated_at) VALUES
('실험 일정', '#3b82f6', 1, 1, 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('미팅 일정', '#8b5cf6', 1, 2, 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
('개인 일정', '#10b981', 1, 3, 'user001', 'user001', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
