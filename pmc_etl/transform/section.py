import pandas as pd
import ast

# 1. 파일 로드 (경로는 실제 환경에 맞게 수정해주세요)
df_sections = pd.read_csv('C:/dev/study/skn18_fianl-2team/SKN18-FINAL-2TEAM/data/pmc_1000/t_sections.csv')
df_figures = pd.read_csv('C:/dev/study/skn18_fianl-2team/SKN18-FINAL-2TEAM/data/pmc_1000/t_figures.csv')
df_embedding = pd.read_csv('C:/dev/study/skn18_fianl-2team/SKN18-FINAL-2TEAM/data/pmc_1000/embedding_new.csv')

# ==========================================
# Step 1: t_sections 필터링 및 텍스트 병합
# ==========================================

# 1-1. topic_category(사용자 언급: section_category)에서 'Result'가 포함된 행만 필터링
# 대소문자 구분 없이 'result'가 포함된 것을 찾습니다.
df_result_sections = df_sections[
    df_sections['section_category'].str.contains('result', case=False, na=False)
].copy()

# 1-2. embedding_new.csv에서 raw text 가져오기 (section_id 기준)
# 필요한 컬럼만 선택하여 병합
df_text_mapped = pd.merge(
    df_result_sections,
    df_embedding[['section_id', 'text_chunk']], 
    on='section_id', 
    how='left'
)

# ==========================================
# Step 2: fig_ids 파싱 및 Explode (핵심 단계)
# ==========================================
# fig_ids가 "fig1, fig2" 처럼 문자열로 되어 있거나 "['fig1', 'fig2']" 리스트 형태일 수 있습니다.
# 데이터 형태에 맞춰 아래 전처리 함수가 필요합니다.

def parse_fig_ids(x):
    if pd.isna(x):
        return []
    
    # 만약 데이터가 "['fig1', 'fig2']" 형태의 문자열이라면:
    if str(x).startswith('['):
        try:
            return ast.literal_eval(x)
        except:
            return []
            
    # 만약 "fig1;fig2" 혹은 "fig1,fig2" 형태라면 (세미콜론이나 콤마 기준 split)
    # 여기서는 데이터 특성에 맞게 구분자(delimiter)를 수정해야 할 수 있습니다.
    return str(x).replace(' ', '').split(',') 

# fig_ids 컬럼을 실제 리스트로 변환
df_text_mapped['fig_id_list'] = df_text_mapped['fig_ids'].apply(parse_fig_ids)

# 리스트를 행으로 분리 (Explode) -> 한 섹션에 그림이 3개면 3개의 행으로 늘어남
df_exploded = df_text_mapped.explode('fig_id_list')

# ==========================================
# Step 3: Figures.csv와 최종 병합
# ==========================================

# figures.csv의 original_label_id와 위에서 분리한 fig_id_list를 매칭
# pmid도 함께 키로 사용해야 정확합니다.

df_final = pd.merge(
    df_figures,
    df_exploded[['pmid', 'fig_id_list', 'topic_category', 'text_chunk']], # 가져올 컬럼들
    left_on=['pmid', 'original_label_id'], # figures.csv의 키
    right_on=['pmid', 'fig_id_list'],      # t_sections의 키
    how='left' # figures.csv 기준 (매칭되는 섹션이 없으면 빈칸)
)

# 중복된 컬럼 정리 (fig_id_list는 original_label_id와 같으므로 삭제)
df_final = df_final.drop(columns=['fig_id_list'])

# 결과 확인
print(f"Original Figures Rows: {len(df_figures)}")
print(f"Merged Figures Rows: {len(df_final)}")
print(df_final[['original_label_id', 'topic_category', 'text_chunk']].head())

# 저장
df_final.to_csv('figures_with_context.csv', index=False, encoding='utf-8-sig')