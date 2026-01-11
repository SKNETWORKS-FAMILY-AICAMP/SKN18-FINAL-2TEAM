-- SQL INSERT statements for default experiment tools
-- This file is for reference only. The actual migration uses Python (0002_load_default_tools.py)
-- Note: New fields added: help_text, guide_prerequisites, guide_inputs, guide_outputs, guide_limitations, guide_recommended_workflow

-- Insert Experiment Tools (RFdiffusion, AlphaFold3, ProteinMPNN)
INSERT INTO t_experiment_tool (tool_sid, tool_name, category, description, icon_name, guide_overview, guide_usage, guide_tips, guide_prerequisites, guide_inputs, guide_outputs, guide_limitations, guide_recommended_workflow, status, created_at, updated_at)
VALUES 
(1, 'RFdiffusion', '단백질 구조 생성', '조건 기반 단백질 백본(구조) 생성', 'fas fa-microscope', 
 'RFdiffusion은 조건(제약/스캐폴드/모티프 등)을 기반으로 단백질 백본 구조를 생성하는 diffusion 기반 모델입니다.',
 '["1. 목표 구조의 조건(길이/모티프/대칭성 등)을 설정합니다.", "2. numSteps/temperature/guidanceScale을 조정해 생성합니다.", "3. 생성된 백본의 물리적 타당성(충돌/2차구조/접힘 가능성)을 1차 점검합니다.", "4. 후속 단계(ProteinMPNN 등)로 서열을 설계합니다."]',
 '처음엔 numSteps=50~100, guidanceScale=6~10 정도로 시작하고, 원하는 형태가 안 나오면 guidanceScale과 조건을 먼저 조정하는 편이 좋습니다.',
 '["목표 설계 목적(결합/효소/구조 안정화 등) 정의", "필요 시 고정 모티프/바인딩 잔기/길이 범위 등 제약 조건 준비"]',
 '["설계 제약 조건(길이, 모티프 고정, 대칭성, 스캐폴드 등)", "선택: 기존 구조(PDB) 또는 모티프 좌표"]',
 '["생성된 단백질 백본 구조(PDB)", "선택: 생성 로그/스코어/샘플 메타데이터"]',
 '["\'구조 생성\'만으로 기능이 보장되지 않습니다(후속 서열 설계/검증 필요).", "제약을 과도하게 걸면 다양성이 급감하거나 실패율이 늘 수 있습니다."]',
 '["RFdiffusion(백본 생성) → ProteinMPNN(서열 설계) → AlphaFold2(접힘 검증) → Docking(DiffDock/Vina) → 실험/추가 최적화"]',
 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

(2, 'AlphaFold3', '단백질 구조 예측', '서열 기반 단백질 3D 구조 예측', 'fas fa-flask',
 'AlphaFold3는 단백질 서열(FASTA)을 입력으로 3D 구조를 예측하는 딥러닝 모델입니다.',
 '["1. 단백질 서열(FASTA)을 입력합니다.", "2. 예측 모드를 선택합니다 (monomer/multimer).", "3. maxRecycles, 템플릿 사용 여부를 설정합니다.", "4. 예측을 실행하고 pLDDT/PAE 등 신뢰도를 검토합니다."]',
 '신뢰도 점수가 낮은 구간(유연/무질서 가능)을 분리 분석하거나, 도메인 단위로 재예측하는 것이 도움이 될 수 있습니다.',
 '["입력 서열(FASTA) 준비", "복합체인 경우 체인별 서열 분리 및 multimer 모드 고려"]',
 '["FASTA 서열(단일/복수 체인)", "선택: 템플릿(구조) 활용 여부(useTemplates)"]',
 '["예측 구조(PDB)", "신뢰도 지표(pLDDT, PAE 등 구현에 따라 제공)"]',
 '["예측 구조는 \'가능한 접힘\'에 대한 추정이며, 실제 조건(리간드/환경/변형)에 따라 달라질 수 있습니다.", "복합체(multimer)는 체인 구성/상호작용 정보에 따라 품질 변동이 큽니다."]',
 '["ProteinMPNN/RFdiffusion 결과 서열 → AlphaFold3로 접힘 검증 → pLDDT/PAE 기반 필터링 → 후속 docking/실험 설계"]',
 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),

(3, 'ProteinMPNN', '단백질 서열 설계', '구조(백본) 기반 단백질 서열 설계', 'fas fa-dna',
 'ProteinMPNN은 단백질 구조(백본)를 입력으로 받아, 해당 구조에 잘 맞는 아미노산 서열을 생성하는 구조 기반 서열 설계 도구입니다.',
 '["1. 입력 구조(PDB/백본)를 준비합니다.", "2. (멀티체인인 경우) 설계할 체인(designChains)을 지정합니다.", "3. 필요하면 고정할 잔기 위치(fixedPositions)를 JSON으로 지정합니다.", "4. 생성 개수(numSequences)와 온도(temperature)를 설정해 서열을 생성합니다.", "5. 생성된 서열을 AlphaFold2 등으로 접힘/신뢰도를 확인해 필터링합니다."]',
 '처음에는 temperature 0.1~0.3, numSequences 8~32 정도로 시작하고, 기능에 중요한 잔기는 fixedPositions로 고정하는 게 안전합니다.',
 '["입력 백본 구조(PDB) 준비(체인/잔기 번호 정리 권장)", "기능성/결합부위 등 반드시 유지해야 하는 잔기 위치가 있다면 fixedPositions로 고정할 계획 수립"]',
 '["단백질 백본 구조(PDB)", "설계 대상 체인(designChains)", "선택: 고정 잔기 목록(fixedPositions), 제외 아미노산(omitAAs)"]',
 '["설계된 서열(FASTA/JSON)", "선택: 서열별 점수/로그(구현에 따라 제공)"]',
 '["\'서열 설계\'는 구조 적합성을 높이지만 기능(결합/촉매)을 자동 보장하진 않습니다.", "입력 구조 품질(결손/충돌/비정상 좌표)에 따라 설계 품질이 크게 흔들릴 수 있습니다."]',
 '["RFdiffusion(백본 생성) → ProteinMPNN(서열 설계) → AlphaFold2(접힘 검증) → Docking(DiffDock/Vina) → 후보 선정/실험"]',
 'E', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (tool_sid) DO NOTHING;

-- Insert Experiment Tool Options for RFdiffusion (tool_sid = 1)
INSERT INTO t_experiment_tool_option (tool_sid, field_name, field_label, field_type, default_value, min_value, max_value, step_value, options_json, help_text, sort_order, created_at, created_id, updated_at, updated_id)
VALUES
(1, 'temperature', 'Temperature', 'number', '1.0', 1, 20, 1, NULL, '높을수록 다양성 증가, 낮을수록 보수적으로 생성됩니다.', 0, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(1, 'numSteps', 'Number of Steps', 'number', '5', 10, 200, 1, NULL, '스텝이 많을수록 계산량이 늘지만 더 안정적인 샘플이 나올 수 있습니다.', 1, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(1, 'guidanceScale', 'Guidance Scale', 'number', '7.5', 10, 200, 5, NULL, '조건(제약)을 얼마나 강하게 따를지 제어합니다.', 2, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system')
ON CONFLICT DO NOTHING;

-- Insert Experiment Tool Options for AlphaFold3 (tool_sid = 2)
INSERT INTO t_experiment_tool_option (tool_sid, field_name, field_label, field_type, default_value, min_value, max_value, step_value, options_json, help_text, sort_order, created_at, created_id, updated_at, updated_id)
VALUES
(2, 'mode', 'Prediction Mode', 'select', 'monomer', 0, 100, 1, '["monomer", "multimer"]', '단일 단백질이면 monomer, 복합체면 multimer를 선택합니다.', 0, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(2, 'maxRecycles', 'Max Recycles', 'number', '3', 1, 10, 1, NULL, 'recycle이 늘면 품질이 좋아질 수 있지만 시간이 증가합니다.', 1, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(2, 'useTemplates', 'Use Templates', 'checkbox', 'true', 0, 100, 1, NULL, '구조 템플릿을 사용할지 여부(가능하면 예측 안정성에 도움).', 2, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system')
ON CONFLICT DO NOTHING;

-- Insert Experiment Tool Options for ProteinMPNN (tool_sid = 3)
INSERT INTO t_experiment_tool_option (tool_sid, field_name, field_label, field_type, default_value, min_value, max_value, step_value, options_json, help_text, sort_order, created_at, created_id, updated_at, updated_id)
VALUES
(3, 'numSequences', 'Number of Sequences', 'number', '8', 1, 128, 1, NULL, '동일 백본에 대해 생성할 서열 샘플 개수입니다.', 0, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(3, 'temperature', 'Sampling Temperature', 'number', '2', 0, 20, 1, NULL, '낮을수록 보수적(안정적 경향), 높을수록 다양성 증가.', 1, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(3, 'seed', 'Random Seed', 'number', '0', 0, 999999, 1, NULL, '재현성을 위한 난수 시드입니다.', 2, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(3, 'designChains', 'Design Chains (e.g., A or A,B)', 'text', 'A', 0, 100, 1, NULL, '멀티체인 구조에서 설계할 체인을 지정합니다.', 3, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(3, 'fixedPositions', 'Fixed Positions (JSON)', 'textarea', '', 0, 100, 1, NULL, '변경 금지할 잔기 위치를 JSON으로 지정합니다. 예: {"A":[1,2,3,10]}', 4, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(3, 'omitAAs', 'Omit Amino Acids (e.g., C or W,Y)', 'text', '', 0, 100, 1, NULL, '설계에서 제외할 아미노산을 지정합니다(예: C 제외로 디설파이드 방지).', 5, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system'),
(3, 'outputFormat', 'Output Format', 'select', 'fasta', 0, 100, 1, '["fasta", "json"]', '결과 서열을 FASTA 또는 JSON으로 출력합니다.', 6, CURRENT_TIMESTAMP, 'system', CURRENT_TIMESTAMP, 'system')
ON CONFLICT DO NOTHING;
