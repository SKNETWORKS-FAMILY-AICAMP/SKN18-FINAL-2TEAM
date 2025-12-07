import pandas as pd
import os
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Merge Result/Research Chunks with related Figures/Tables")
    
    # -------------------------------------------------------------------------
    # 1. 커맨드라인 인자 설정
    # -------------------------------------------------------------------------
    # 공통 기본 폴더 지정 (선택 사항)
    parser.add_argument("--base-dir", default=".", help="Base directory for input files (default: current dir)")
    
    # 개별 파일 경로 (입력하지 않으면 base-dir/파일명 으로 간주)
    parser.add_argument("--sections", default="sections.csv", help="Filename or path for sections CSV")
    parser.add_argument("--chunks", default="chunks_new7.csv", help="Filename or path for chunks CSV")
    parser.add_argument("--figures", default="figures.csv", help="Filename or path for figures CSV")
    parser.add_argument("--tables", default="tables.csv", help="Filename or path for tables CSV")
    
    # 결과물 저장 경로
    parser.add_argument("--output", default="final_result_research_dataset.csv", help="Output filename/path")

    args = parser.parse_args()

    # 경로 조립 헬퍼 함수 (절대 경로가 입력되면 그대로 사용, 아니면 base_dir 결합)
    def get_path(fname):
        if os.path.isabs(fname):
            return fname
        return os.path.join(args.base_dir, fname)

    # 최종 경로 확정
    sections_path = get_path(args.sections)
    chunks_path = get_path(args.chunks)
    figures_path = get_path(args.figures)
    tables_path = get_path(args.tables)
    output_path = args.output # 출력은 실행 위치 기준 or 절대경로

    print(f"\n[INFO] Configuration:")
    print(f" - Base Dir: {os.path.abspath(args.base_dir)}")
    print(f" - Sections: {sections_path}")
    print(f" - Chunks:   {chunks_path}")
    print(f" - Output:   {output_path}\n")

    # -------------------------------------------------------------------------
    # 2. 파일 로드 및 유효성 검사
    # -------------------------------------------------------------------------
    dfs = {}
    
    # 필수 파일 체크
    if not os.path.exists(sections_path):
        print(f"[CRITICAL] Sections file not found: {sections_path}")
        sys.exit(1)
    if not os.path.exists(chunks_path):
        print(f"[CRITICAL] Chunks file not found: {chunks_path}")
        sys.exit(1)

    # 로드 루프
    for name, path in [('sections', sections_path), ('chunks', chunks_path), 
                       ('figures', figures_path), ('tables', tables_path)]:
        if os.path.exists(path):
            try:
                print(f"[LOAD] Loading {name}...")
                dfs[name] = pd.read_csv(path)
            except Exception as e:
                print(f"[ERROR] Failed to load {name}: {e}")
                sys.exit(1)
        else:
            print(f"[WARN] {name} file not found ({path}). Skipping.")
            dfs[name] = pd.DataFrame()

    sections_df = dfs['sections']
    chunks_df = dfs['chunks']
    figures_df = dfs['figures']
    tables_df = dfs['tables']

    # -------------------------------------------------------------------------
    # 3. 데이터 필터링: Result Section & Research Article
    # -------------------------------------------------------------------------
    print("[PROCESS] Filtering for 'Result' sections in 'Research' articles...")
    
    # 소문자 변환 후 필터링
    sections_df['section_category'] = sections_df['section_category'].astype(str).str.lower()
    sections_df['article_category'] = sections_df['article_category'].astype(str).str.lower()

    target_sections = sections_df[
        (sections_df['section_category'] == 'result') & 
        (sections_df['article_category'] == 'research')
    ]

    if target_sections.empty:
        print("[WARN] No sections matched (category='result' & article='research'). Exiting.")
        sys.exit(0)

    # 타겟 ID 추출
    target_section_ids = target_sections['section_id'].astype(str).unique().tolist()
    target_pmids = target_sections['pmid'].dropna().astype(int).astype(str).unique().tolist()

    print(f" -> Found {len(target_section_ids)} target Sections.")
    print(f" -> Found {len(target_pmids)} related PMIDs.")

    # -------------------------------------------------------------------------
    # 4. 데이터 추출 및 병합
    # -------------------------------------------------------------------------
    final_data_list = []

    # [A] Chunks 처리
    if not chunks_df.empty:
        chunks_df['section_id'] = chunks_df['section_id'].astype(str)
        filtered_chunks = chunks_df[chunks_df['section_id'].isin(target_section_ids)].copy()
        
        if not filtered_chunks.empty:
            filtered_chunks['data_type'] = 'text'
            final_data_list.append(filtered_chunks)
            print(f" -> Added {len(filtered_chunks)} text chunks.")

    # [B] Figures 처리
    if not figures_df.empty:
        figures_df['pmid'] = figures_df['pmid'].astype(str)
        filtered_figs = figures_df[figures_df['pmid'].isin(target_pmids)].copy()
        
        fig_cols = ['pmid', 'fig_ids', 'fig_label', 'fig_caption', 'fig_url']
        available_cols = [c for c in fig_cols if c in filtered_figs.columns]
        
        if not filtered_figs.empty and available_cols:
            subset_figs = filtered_figs[available_cols].copy()
            subset_figs['data_type'] = 'figure'
            final_data_list.append(subset_figs)
            print(f" -> Added {len(subset_figs)} figures.")

    # [C] Tables 처리
    if not tables_df.empty:
        tables_df['pmid'] = tables_df['pmid'].astype(str)
        filtered_tabs = tables_df[tables_df['pmid'].isin(target_pmids)].copy()
        
        tab_cols = ['pmid', 'table_ids', 'table_label', 'table_caption', 'table_url']
        available_cols = [c for c in tab_cols if c in filtered_tabs.columns]
        
        if not filtered_tabs.empty and available_cols:
            subset_tabs = filtered_tabs[available_cols].copy()
            subset_tabs['data_type'] = 'table'
            final_data_list.append(subset_tabs)
            print(f" -> Added {len(subset_tabs)} tables.")

    # -------------------------------------------------------------------------
    # 5. 저장
    # -------------------------------------------------------------------------
    if final_data_list:
        final_df = pd.concat(final_data_list, ignore_index=True, sort=False)
        
        # 컬럼 순서 정리 (가독성)
        cols = final_df.columns.tolist()
        priority = ['pmid', 'data_type', 'chunk_id', 'text_chunk', 'fig_url', 'table_url']
        sorted_cols = [c for c in priority if c in cols] + [c for c in cols if c not in priority]
        final_df = final_df[sorted_cols]

        final_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[DONE] Successfully merged data.")
        print(f" -> Total Rows: {len(final_df)}")
        print(f" -> Saved to: {os.path.abspath(output_path)}")
    else:
        print("[WARN] No matching data found to merge.")

if __name__ == "__main__":
    main()