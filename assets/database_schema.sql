-- ============================================
-- HelixOps RDB 테이블 설계
-- ============================================

-- 1. 사용자 관련 테이블
-- ============================================

-- 사용자 기본 정보
CREATE TABLE zs_user (
    user_id VARCHAR(60) PRIMARY KEY NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    phone_number VARCHAR(50),
    organization VARCHAR(255),
    img_url VARCHAR(500),
    join_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    status CHAR DEFAULT 'E',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 사용자 설정
CREATE TABLE zs_user_settings (
    settings_sid SERIAL PRIMARY KEY,
    user_id VARCHAR(60) NOT NULL,
    notifications CHAR DEFAULT 'Y',
    email_alerts CHAR DEFAULT 'Y',
    dark_mode CHAR DEFAULT 'N',
    language VARCHAR(10) DEFAULT 'ko',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_user_settings UNIQUE (user_id)
);

-- 연동된 계정 (Google 등)
CREATE TABLE zs_linked_account (
    linked_account_sid SERIAL PRIMARY KEY,
    user_id VARCHAR(60) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    access_token VARCHAR(500),
    refresh_token VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_provider_user UNIQUE (user_id, provider)
);

-- 2. 코드 관리 테이블
-- ============================================

-- 공통 코드 그룹 
-- common_code 규칙 : 약자+숫자3자리 - ex: ABC001
CREATE TABLE tc_common (
    common_code CHAR(6) PRIMARY KEY,
    common_name VARCHAR(100) NOT NULL,
    description TEXT,
    use_yn CHAR DEFAULT 'Y',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 공통 코드 항목
-- common_item_code 규칙 : 약자+숫자3자리 - ex: ABC001
CREATE TABLE tc_common_item (
    common_item_code CHAR(6) PRIMARY KEY,
    common_code CHAR(6) REFERENCES tc_common(common_code),
    common_item_name VARCHAR(100) NOT NULL,
    description TEXT,
    use_yn CHAR DEFAULT 'Y',
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL,
);

-- 3. 메뉴 및 페이지 관련 테이블

-- 메뉴
CREATE TABLE zs_menu (
    menu_sid SERIAL PRIMARY KEY,
    menu_code CHAR(6) NOT NULL UNIQUE,
    menu_name VARCHAR(100) NOT NULL,
    menu_name_short VARCHAR(50),
    icon_name VARCHAR(100),
    parent_menu_sid INT,
    sort_order INT DEFAULT 0,
    status CHAR DEFAULT 'E',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 페이지
CREATE TABLE zs_page (
    page_sid SERIAL PRIMARY KEY,
    page_code CHAR(6) NOT NULL UNIQUE,
    page_name VARCHAR(100) NOT NULL,
    menu_sid INT,
    route_path VARCHAR(255),
    status CHAR DEFAULT 'E',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. 조직 관련 테이블
-- ============================================

-- 조직
CREATE TABLE zs_organization (
    organization_sid SERIAL PRIMARY KEY,
    organization_name VARCHAR(255) NOT NULL,
    created_by_user_id VARCHAR(60) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 조직 멤버
CREATE TABLE zs_organization_member (
    organization_sid INT NOT NULL,
    user_id VARCHAR(60) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_org_user UNIQUE (organization_sid, user_id)
);

-- 4. 채팅 관련 테이블
-- ============================================

-- 채팅
CREATE TABLE t_chat (
    chat_sid SERIAL PRIMARY KEY,
    title VARCHAR(500),
    preview TEXT,
    status CHAR DEFAULT 'E',
    pinned CHAR DEFAULT 'N',
    archived CHAR DEFAULT 'N',
    filter_type VARCHAR(50),
    auto_mode CHAR DEFAULT 'Y', 
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 채팅 메시지
CREATE TABLE t_chat_message (
    message_sid SERIAL PRIMARY KEY,
    chat_sid INT NOT NULL,
    role CHAR(1) NOT NULL,
    content TEXT NOT NULL,
    sort_order INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL
);

-- 채팅 참고 문헌
CREATE TABLE t_chat_reference (
    reference_sid SERIAL PRIMARY KEY,
    chat_sid INT NOT NULL,
    message_sid INT,
    source CHAR(1) NOT NULL,
    badge CHAR(1) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    journal CHAR(1) NOT NULL,
    link VARCHAR(500),
    ref_pubmed_id VARCHAR(100),
    ref_date TIMESTAMP,
    ref_authors VARCHAR(500),
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 채팅 메시지 피드백
CREATE TABLE t_chat_message_feedback (
    feedback_sid SERIAL PRIMARY KEY,
    message_sid INT NOT NULL,
    feedback_type CHAR(1) NOT NULL,
    rating SMALLINT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);


-- 5. 북마크 관련 테이블
-- ============================================

-- 북마크 카테고리
CREATE TABLE t_bookmark_category (
    category_sid SERIAL PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 북마크
CREATE TABLE t_bookmark (
    bookmark_sid SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    bookmark_url VARCHAR(1000) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 북마크 카테고리 매핑 (북마크와 카테고리의 다대다 관계)
CREATE TABLE t_bookmark_map (
    map_sid SERIAL PRIMARY KEY,
    bookmark_sid INT NOT NULL,
    category_sid INT NOT NULL,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    CONSTRAINT uk_bookmark_category UNIQUE (bookmark_sid, category_sid)
);

-- 6. 노트 관련 테이블
-- ============================================

-- 노트
CREATE TABLE t_note (
    note_sid SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    status CHAR DEFAULT 'E',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 노트 태그
CREATE TABLE t_note_tag (
    note_tag_sid SERIAL PRIMARY KEY,
    note_sid INT NOT NULL,
    tag_name VARCHAR(100) NOT NULL,
    sort_order SMALLINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    CONSTRAINT uk_note_tag UNIQUE (note_sid, tag_name)
);

-- 노트 댓글
CREATE TABLE t_note_comment (
    comment_sid SERIAL PRIMARY KEY,
    note_sid INT NOT NULL,
    highlighted_text VARCHAR(500),
    comment_text TEXT NOT NULL,
    position_top SMALLINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 노트 첨부 파일
CREATE TABLE t_note_attachment (
    attachment_sid SERIAL PRIMARY KEY,
    note_sid INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT,
    file_type VARCHAR(50),
    file_path VARCHAR(1000),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 노트 공유
CREATE TABLE t_note_share (
    note_sid INT NOT NULL,
    user_id VARCHAR(60) NOT NULL ,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL
);

-- 7. 실험 관련 테이블
-- ============================================

-- 실험 도구
CREATE TABLE t_experiment_tool (
    tool_sid SERIAL PRIMARY KEY,
    tool_name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    icon_name VARCHAR(100),
    img_url VARCHAR(1000),
    guide_overview TEXT,
    guide_usage TEXT,
    guide_tips TEXT,
    status CHAR DEFAULT 'E',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 실험 도구 옵션 필드
CREATE TABLE t_experiment_tool_option (
    option_sid SERIAL PRIMARY KEY,
    tool_sid INT NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    field_label VARCHAR(255) NOT NULL,
    field_type CHAR(50) NOT NULL,
    default_value TEXT,
    min_value SMALLINT DEFAULT 0,
    max_value SMALLINT DEFAULT 100,
    step_value SMALLINT DEFAULT 1,
    options_json TEXT,
    sort_order SMALLINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 실험
CREATE TABLE t_experiment (
    experiment_sid SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL,
    status CHAR DEFAULT 'E',
    progress SMALLINT DEFAULT 0,
    protein_sequence TEXT,
    protein_name VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 실험 도구 선택 (파이프라인 구성)
CREATE TABLE t_experiment_tool_selection (
    selection_sid SERIAL PRIMARY KEY,
    experiment_sid INT NOT NULL,
    tool_sid INT NOT NULL,
    sort_order SMALLINT DEFAULT 0,
    tool_options_json TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 실험 결과 파일
CREATE TABLE t_experiment_result (
    result_sid SERIAL PRIMARY KEY,
    experiment_sid INT NOT NULL,
    result_name VARCHAR(255) NOT NULL,
    result_type CHAR(50) NOT NULL,
    file_size BIGINT,
    file_path VARCHAR(1000),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 단백질 검색 결과 -> API 이용
/*
CREATE TABLE t_protein_search_result (
    protein_result_sid SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    protein_id VARCHAR(100),
    protein_name VARCHAR(255),
    description TEXT,
    recommended_name VARCHAR(255),
    cleaved_chains TEXT, -- JSON array
    gene VARCHAR(100),
    organism VARCHAR(255),
    taxonomic_id VARCHAR(100),
    taxonomic_lineage TEXT,
    length INT,
    mass INT,
    last_updated VARCHAR(100),
    md5_checksum VARCHAR(255),
    sequence TEXT,
    evidence_level VARCHAR(255),
    annotation_score INT,
    tags_json TEXT, -- JSON array
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES zs_user(user_id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_protein_id (protein_id)
);
*/

-- 8. 일정 관련 테이블
-- ============================================

-- 일정
CREATE TABLE t_schedule (
    schedule_sid SERIAL PRIMARY KEY,
    -- user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    schedule_type CHAR(50) NOT NULL,
    schedule_status CHAR DEFAULT 'E',
    use_yn CHAR DEFAULT 'Y',
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    is_all_day CHAR DEFAULT 'N',
    location VARCHAR(255),
    color VARCHAR(50),
    linked_note_sid INT,
    calendar_sid INT REFERENCES t_user_calendar(calendar_sid),
    repeat_type CHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 반복 규칙 (iCalendar RRULE 기반 메타데이터)
CREATE TABLE t_schedule_recurrence (
    schedule_sid INT PRIMARY KEY REFERENCES t_schedule(schedule_sid) ON DELETE CASCADE,
    freq VARCHAR(20) NOT NULL,               -- DAILY / WEEKLY / MONTHLY / YEARLY
    interval INT NOT NULL DEFAULT 1,         -- 반복 간격
    week_days JSONB DEFAULT '[]'::jsonb,     -- 반복 요일 목록 (예: ["MO","WE"])
    month_days JSONB DEFAULT '[]'::jsonb,    -- 반복 일자 목록 (예: [1, 15])
    count INT,
    until TIMESTAMP,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 반복 예외(스킵/개별 수정 표시)
CREATE TABLE t_schedule_exception (
    recurrence_exception_sid SERIAL PRIMARY KEY,
    recurrence_sid INT NOT NULL REFERENCES t_schedule_recurrence(schedule_sid) ON DELETE CASCADE,
    exception_date DATE NOT NULL,
    note VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_schedule_exception UNIQUE (recurrence_sid, exception_date)
);

-- 일정 공유
CREATE TABLE t_schedule_share (
    schedule_share_sid SERIAL PRIMARY KEY,
    schedule_sid INT NOT NULL,
    user_id VARCHAR(60) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL
);

-- 사용자 캘린더
CREATE TABLE t_user_calendar (
    calendar_sid SERIAL PRIMARY KEY,
    calendar_name VARCHAR(255) NOT NULL,
    color VARCHAR(50),
    is_visible SMALLINT DEFAULT 1,
    sort_order INT DEFAULT 0,
    source_type VARCHAR(20) NOT NULL DEFAULT 'local', -- local / google ...
    external_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- Google Calendar 연동
CREATE TABLE t_google_calendar (
    google_calendar_id SERIAL PRIMARY KEY,
    calendar_name VARCHAR(255) NOT NULL,
    calendar_email VARCHAR(255),
    color VARCHAR(50),
    is_connected CHAR DEFAULT 'N',
    is_selected SMALLINT DEFAULT 0,
    access_token VARCHAR(500),
    refresh_token VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 9. 알림 관련 테이블
-- ============================================

-- 알림
CREATE TABLE t_notification (
    notification_sid SERIAL PRIMARY KEY,
    user_id VARCHAR(60) NOT NULL,
    notification_type CHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    read_yn CHAR DEFAULT 'N',
    related_sid INT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. 피드백 관련 테이블
-- ============================================

-- 피드백
CREATE TABLE t_feedback (
    feedback_sid SERIAL PRIMARY KEY,
    -- user_id INT NOT NULL,
    category CHAR(1) NOT NULL,
    feedback_content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 11. 추천 질문 관련 테이블
-- ============================================

-- 추천 질문 (사용자가 추천 질문을 클릭했을 때 기록)
CREATE TABLE t_recommended_question (
    question_sid SERIAL PRIMARY KEY,
    question_text VARCHAR(500) NOT NULL,
    question_category CHAR(1) NOT NULL,
    sort_order INT DEFAULT 0,
    status CHAR(1) DEFAULT 'E',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. 논문 그래프 관련 테이블
-- ============================================

-- 논문 그래프 (PaperGraphModal에서 표시되는 논문 네트워크 그래프의 메타데이터)
CREATE TABLE t_paper_graph (
    graph_sid SERIAL PRIMARY KEY,
    graph_title VARCHAR(255),
    graph_description TEXT,
    status CHAR DEFAULT 'E',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL
);

-- 논문 노드 (PaperGraphModal에서 사용하는 논문 네트워크 그래프의 노드)
CREATE TABLE t_paper_node (
    node_sid SERIAL PRIMARY KEY,
    graph_sid INT NOT NULL,
    paper_id VARCHAR(100) NOT NULL,
    paper_label VARCHAR(255) NOT NULL,
    node_size INT DEFAULT 20,
    node_color VARCHAR(50),
    x_position DECIMAL(10,2),
    y_position DECIMAL(10,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL,
    CONSTRAINT uk_graph_paper UNIQUE (graph_sid, paper_id)
);

-- 논문 엣지 (인용 관계) - PaperGraphModal에서 논문 간 인용 관계를 시각화하는 연결선
CREATE TABLE t_paper_edge (
    edge_sid SERIAL PRIMARY KEY,
    graph_sid INT NOT NULL,
    source_paper_id VARCHAR(100) NOT NULL,
    target_paper_id VARCHAR(100) NOT NULL,
    edge_size INT DEFAULT 1,
    edge_color VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_id VARCHAR(60) NOT NULL,
    CONSTRAINT uk_graph_edge UNIQUE (graph_sid, source_paper_id, target_paper_id)
);

-- 채팅 메시지와 논문 그래프 연결 (ResearchAI 컴포넌트에서 특정 메시지에 "관련 논문 상세 보기" 버튼이 표시될 때 사용)
CREATE TABLE t_chat_message_paper_graph (
    message_graph_sid SERIAL PRIMARY KEY,
    message_sid INT NOT NULL,
    graph_sid INT NOT NULL,
    sort_order SMALLINT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_id VARCHAR(60) NOT NULL,
    CONSTRAINT uk_message_graph UNIQUE (message_sid, graph_sid)
);

-- ============================================
-- FOREIGN KEY 제약조건 추가 (ALTER TABLE)
-- ============================================

-- 사용자 관련 테이블
ALTER TABLE zs_user_settings
    ADD CONSTRAINT fk_user_settings_user
    FOREIGN KEY (user_id)
    REFERENCES zs_user(user_id)
    ON DELETE CASCADE;

ALTER TABLE zs_linked_account
    ADD CONSTRAINT fk_linked_account_user
    FOREIGN KEY (user_id)
    REFERENCES zs_user(user_id)
    ON DELETE CASCADE;

-- 코드 관리 테이블
ALTER TABLE tc_common_item
    ADD CONSTRAINT fk_common_code_item
    FOREIGN KEY (common_code)
    REFERENCES tc_common(common_code)
    ON DELETE CASCADE;

-- 메뉴 및 페이지 관련 테이블
ALTER TABLE zs_menu
    ADD CONSTRAINT fk_menu_parent
    FOREIGN KEY (parent_menu_sid)
    REFERENCES zs_menu(menu_sid)
    ON DELETE SET NULL;

ALTER TABLE zs_page
    ADD CONSTRAINT fk_page_menu
    FOREIGN KEY (menu_sid)
    REFERENCES zs_menu(menu_sid)
    ON DELETE SET NULL;

-- 조직 관련 테이블
ALTER TABLE zs_organization
    ADD CONSTRAINT fk_organization_user
    FOREIGN KEY (created_by_user_id)
    REFERENCES zs_user(user_id)
    ON DELETE CASCADE;

ALTER TABLE zs_organization_member
    ADD CONSTRAINT fk_org_member_organization
    FOREIGN KEY (organization_sid)
    REFERENCES zs_organization(organization_sid)
    ON DELETE CASCADE;

ALTER TABLE zs_organization_member
    ADD CONSTRAINT fk_org_member_user
    FOREIGN KEY (user_id)
    REFERENCES zs_user(user_id)
    ON DELETE CASCADE;

-- 채팅 관련 테이블
ALTER TABLE t_chat_message
    ADD CONSTRAINT fk_chat_message_chat
    FOREIGN KEY (chat_sid)
    REFERENCES t_chat(chat_sid)
    ON DELETE CASCADE;

ALTER TABLE t_chat_reference
    ADD CONSTRAINT fk_chat_reference_chat
    FOREIGN KEY (chat_sid)
    REFERENCES t_chat(chat_sid)
    ON DELETE CASCADE;

ALTER TABLE t_chat_reference
    ADD CONSTRAINT fk_chat_reference_message
    FOREIGN KEY (message_sid)
    REFERENCES t_chat_message(message_sid)
    ON DELETE SET NULL;

ALTER TABLE t_chat_message_feedback
    ADD CONSTRAINT fk_chat_message_feedback_message
    FOREIGN KEY (message_sid)
    REFERENCES t_chat_message(message_sid)
    ON DELETE CASCADE;

-- 북마크 관련 테이블
ALTER TABLE t_bookmark
    ADD CONSTRAINT fk_bookmark_category
    FOREIGN KEY (category_sid)
    REFERENCES t_bookmark_category(category_sid)
    ON DELETE SET NULL;

ALTER TABLE t_bookmark_map
    ADD CONSTRAINT fk_bookmark_map_bookmark
    FOREIGN KEY (bookmark_sid)
    REFERENCES t_bookmark(bookmark_sid)
    ON DELETE CASCADE;

ALTER TABLE t_bookmark_map
    ADD CONSTRAINT fk_bookmark_map_category
    FOREIGN KEY (category_sid)
    REFERENCES t_bookmark_category(category_sid)
    ON DELETE CASCADE;

-- 노트 관련 테이블
ALTER TABLE t_note_tag
    ADD CONSTRAINT fk_note_tag_note
    FOREIGN KEY (note_sid)
    REFERENCES t_note(note_sid)
    ON DELETE CASCADE;

ALTER TABLE t_note_comment
    ADD CONSTRAINT fk_note_comment_note
    FOREIGN KEY (note_sid)
    REFERENCES t_note(note_sid)
    ON DELETE CASCADE;

ALTER TABLE t_note_attachment
    ADD CONSTRAINT fk_note_attachment_note
    FOREIGN KEY (note_sid)
    REFERENCES t_note(note_sid)
    ON DELETE CASCADE;

ALTER TABLE t_note_share
    ADD CONSTRAINT fk_note_share_note
    FOREIGN KEY (note_sid)
    REFERENCES t_note(note_sid)
    ON DELETE CASCADE;

-- 실험 관련 테이블
ALTER TABLE t_experiment_tool_option
    ADD CONSTRAINT fk_experiment_tool_option_tool
    FOREIGN KEY (tool_sid)
    REFERENCES t_experiment_tool(tool_sid)
    ON DELETE CASCADE;

ALTER TABLE t_experiment_tool_selection
    ADD CONSTRAINT fk_experiment_tool_selection_experiment
    FOREIGN KEY (experiment_sid)
    REFERENCES t_experiment(experiment_sid)
    ON DELETE CASCADE;

ALTER TABLE t_experiment_tool_selection
    ADD CONSTRAINT fk_experiment_tool_selection_tool
    FOREIGN KEY (tool_sid)
    REFERENCES t_experiment_tool(tool_sid)
    ON DELETE CASCADE;

ALTER TABLE t_experiment_result
    ADD CONSTRAINT fk_experiment_result_experiment
    FOREIGN KEY (experiment_sid)
    REFERENCES t_experiment(experiment_sid)
    ON DELETE CASCADE;

-- 일정 관련 테이블
ALTER TABLE t_schedule
    ADD CONSTRAINT fk_schedule_note
    FOREIGN KEY (linked_note_sid)
    REFERENCES t_note(note_sid)
    ON DELETE SET NULL;

ALTER TABLE t_schedule_share
    ADD CONSTRAINT fk_schedule_share_schedule
    FOREIGN KEY (schedule_sid)
    REFERENCES t_schedule(schedule_sid)
    ON DELETE CASCADE;

-- 알림 관련 테이블
ALTER TABLE t_notification
    ADD CONSTRAINT fk_notification_user
    FOREIGN KEY (user_id)
    REFERENCES zs_user(user_id)
    ON DELETE CASCADE;

-- 논문 그래프 관련 테이블
ALTER TABLE t_paper_node
    ADD CONSTRAINT fk_paper_node_graph
    FOREIGN KEY (graph_sid)
    REFERENCES t_paper_graph(graph_sid)
    ON DELETE CASCADE;

ALTER TABLE t_paper_edge
    ADD CONSTRAINT fk_paper_edge_graph
    FOREIGN KEY (graph_sid)
    REFERENCES t_paper_graph(graph_sid)
    ON DELETE CASCADE;

ALTER TABLE t_paper_edge
    ADD CONSTRAINT fk_paper_edge_source
    FOREIGN KEY (source_paper_id)
    REFERENCES t_paper_node(paper_id)
    ON DELETE CASCADE;

ALTER TABLE t_paper_edge
    ADD CONSTRAINT fk_paper_edge_target
    FOREIGN KEY (target_paper_id)
    REFERENCES t_paper_node(paper_id)
    ON DELETE CASCADE;

ALTER TABLE t_chat_message_paper_graph
    ADD CONSTRAINT fk_chat_message_paper_graph_message
    FOREIGN KEY (message_sid)
    REFERENCES t_chat_message(message_sid)
    ON DELETE CASCADE;

ALTER TABLE t_chat_message_paper_graph
    ADD CONSTRAINT fk_chat_message_paper_graph_graph
    FOREIGN KEY (graph_sid)
    REFERENCES t_paper_graph(graph_sid)
    ON DELETE CASCADE;

-- ============================================
-- COLUMN COMMENT 추가
-- ============================================

-- zs_linked_account
COMMENT ON COLUMN zs_linked_account.provider IS 'google, github, etc.';

-- zs_organization_member
COMMENT ON COLUMN zs_organization_member.role IS 'owner, member';

-- t_chat
COMMENT ON COLUMN t_chat.filter_type IS '논문, 임상, 프로토콜, 시뮬레이션, 결과 해석';

-- t_chat_message
COMMENT ON COLUMN t_chat_message.role IS 'U:user, A:assistant';

-- t_chat_message_feedback
COMMENT ON COLUMN t_chat_message_feedback.feedback_type IS 'L:좋아요, D:싫어요, I:개선제안, E:오류신고, O:기타';
COMMENT ON COLUMN t_chat_message_feedback.rating IS '1-5 점수 (선택적)';

-- t_chat_reference
COMMENT ON COLUMN t_chat_reference.source IS 'P:PubMed, W:Web, N:NIH, T:PROTOCOL etc.';
COMMENT ON COLUMN t_chat_reference.badge IS 'H:High, M:Medium, L:Low';
COMMENT ON COLUMN t_chat_reference.journal IS 'J:Journal, B:Book, R:Report, P:Protocol etc.';

-- t_note_comment
COMMENT ON COLUMN t_note_comment.highlighted_text IS '사용자가 선택한 텍스트 (하이라이트된 부분)';
COMMENT ON COLUMN t_note_comment.comment_text IS '댓글 내용';
COMMENT ON COLUMN t_note_comment.position_top IS '노트 내용에서 선택된 텍스트의 상대적 위치(픽셀 단위). 노트 컨테이너 상단으로부터의 거리. 댓글을 표시할 때 해당 위치를 참조하여 하이라이트 표시에 사용됨';

-- t_bookmark_map
COMMENT ON COLUMN t_bookmark_map.bookmark_sid IS '북마크 ID';
COMMENT ON COLUMN t_bookmark_map.category_sid IS '카테고리 ID';
COMMENT ON COLUMN t_bookmark_map.sort_order IS '카테고리 내 정렬 순서';

-- t_experiment_tool_option
COMMENT ON COLUMN t_experiment_tool_option.field_type IS 'N: number, S: select, C: checkbox, etc';
COMMENT ON COLUMN t_experiment_tool_option.options_json IS 'JSON array for select options';

-- t_experiment
COMMENT ON COLUMN t_experiment.status IS 'E: 준비, R: 진행중, C: 완료';
COMMENT ON COLUMN t_experiment.progress IS '0-100';

-- t_experiment_tool_selection
COMMENT ON COLUMN t_experiment_tool_selection.tool_options_json IS 'JSON array for tool-specific options';

-- t_experiment_result
COMMENT ON COLUMN t_experiment_result.result_type IS 'P: PDB, F: FASTA, O: PDF, T: TXT, L: LOG, C: CSV';

-- t_schedule
COMMENT ON COLUMN t_schedule.schedule_type IS 'E: 실험, M: 미팅, A: 분석, S: 세미나';
COMMENT ON COLUMN t_schedule.schedule_status IS 'E: 예정, R: 진행중, C: 완료';
COMMENT ON COLUMN t_schedule.use_yn IS 'Y: 노출, N: 삭제(미노출)';
COMMENT ON COLUMN t_schedule.is_all_day IS 'Y: 하루 종일, N: 시간 설정';
COMMENT ON COLUMN t_schedule.repeat_type IS 'N: 반복 안 함, D: 매일, W: 매주, M: 매월, Y: 매년';

-- t_google_calendar
COMMENT ON COLUMN t_google_calendar.is_connected IS 'Y: 연결됨, N: 연결안됨';

-- t_notification
COMMENT ON COLUMN t_notification.notification_type IS 'E: 실험, M: 미팅, A: 분석, S: 세미나';
COMMENT ON COLUMN t_notification.read_yn IS 'Y: 읽음, N: 읽지 않음';
COMMENT ON COLUMN t_notification.related_sid IS 'experiment_sid, schedule_sid, note_sid, chat_sid 등';

-- t_feedback
COMMENT ON COLUMN t_feedback.category IS 'G: 일반, B: 버그, F: 기능, I: 개선';

-- t_recommended_question
COMMENT ON COLUMN t_recommended_question.question_category IS 'P: 논문, C: 임상, T: 프로토콜, S: 시뮬레이션, R: 결과 해석';
COMMENT ON COLUMN t_recommended_question.status IS 'E: 사용, D: disabled, R: Removed';

-- t_paper_graph
COMMENT ON COLUMN t_paper_graph.graph_title IS '그래프 제목 (예: 관련 논문 네트워크)';
COMMENT ON COLUMN t_paper_graph.graph_description IS '그래프 설명 (예: 논문 간 인용 관계를 시각화한 그래프)';
COMMENT ON COLUMN t_paper_graph.status IS 'E: 사용, D: 비활성';

-- t_paper_node
COMMENT ON COLUMN t_paper_node.graph_sid IS '이 노드가 속한 그래프의 ID';
COMMENT ON COLUMN t_paper_node.paper_id IS '논문 고유 식별자 (예: cobo-2011, eck-2010)';
COMMENT ON COLUMN t_paper_node.paper_label IS '논문 표시 이름 (예: Cobo, 2011, Eck, 2010)';
COMMENT ON COLUMN t_paper_node.node_size IS '그래프에서 노드의 크기(픽셀). 논문의 중요도나 인용 횟수에 따라 조정 가능';
COMMENT ON COLUMN t_paper_node.node_color IS '노드 색상 코드 (예: #9E7B9E 중심 논문, #7B9E9E 관련 논문, #5B8E7E 파생 논문)';
COMMENT ON COLUMN t_paper_node.x_position IS '그래프에서 노드의 X 좌표 위치 (레이아웃 알고리즘에 의해 계산됨)';
COMMENT ON COLUMN t_paper_node.y_position IS '그래프에서 노드의 Y 좌표 위치 (레이아웃 알고리즘에 의해 계산됨)';

-- t_paper_edge
COMMENT ON COLUMN t_paper_edge.graph_sid IS '이 엣지가 속한 그래프의 ID';
COMMENT ON COLUMN t_paper_edge.source_paper_id IS '인용하는 논문의 paper_id (출발 노드). 이 논문이 target_paper_id를 인용함';
COMMENT ON COLUMN t_paper_edge.target_paper_id IS '인용당하는 논문의 paper_id (도착 노드). source_paper가 이 논문을 인용함을 의미';
COMMENT ON COLUMN t_paper_edge.edge_size IS '엣지의 두께(픽셀). 인용 관계의 강도나 중요도를 나타낼 수 있음';
COMMENT ON COLUMN t_paper_edge.edge_color IS '엣지 색상 코드 (기본값: #CCCCCC 회색)';

-- t_chat_message_paper_graph
COMMENT ON COLUMN t_chat_message_paper_graph.message_sid IS '채팅 메시지 ID';
COMMENT ON COLUMN t_chat_message_paper_graph.graph_sid IS '연결된 논문 그래프 ID';
COMMENT ON COLUMN t_chat_message_paper_graph.sort_order IS '하나의 메시지에 여러 그래프가 연결될 경우 정렬 순서';
