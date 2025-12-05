import pandas as pd
import csv
import os

def clean_large_csv_chunked(input_path, output_path, chunk_size=5000):
    print(f"🧹 CSV 정제 시작 (Chunk 단위): {input_path} -> {output_path}")
    
    # 1. 기존 출력 파일이 있다면 삭제 (초기화)
    if os.path.exists(output_path):
        os.remove(output_path)
    
    try:
        # 2. 청크 단위로 읽기 위한 Iterator 생성
        # engine='python': 속도는 조금 느리지만, 깨진 따옴표/특수문자를 훨씬 더 유연하게 처리함 (필수)
        # on_bad_lines='warn': 정말 심각하게 깨진 라인은 경고만 띄우고 건너뜀
        chunk_iter = pd.read_csv(
            input_path, 
            chunksize=chunk_size, 
            on_bad_lines='warn', 
            engine='python' 
        )
        
        chunk_count = 0
        total_rows = 0
        
        for chunk in chunk_iter:
            # 3. 데이터 전처리 (선택 사항: 줄바꿈 문자 제거 등)
            # 텍스트 필드 내의 엔터키(\n)는 CSV를 깰 수 있으므로 공백으로 치환하면 더 안전함
            # for col in chunk.select_dtypes(include=['object']).columns:
            #     chunk[col] = chunk[col].astype(str).str.replace(r'[\r\n]+', ' ', regex=True)

            # 4. 파일에 이어 쓰기 (Append Mode)
            # 첫 번째 청크일 때만 헤더(컬럼명)를 기록
            write_header = (chunk_count == 0)
            
            chunk.to_csv(
                output_path, 
                mode='a',                      # 이어 쓰기 모드
                index=False, 
                header=write_header,           # 첫 청크만 헤더 포함
                quoting=csv.QUOTE_NONNUMERIC,  # 핵심: 모든 텍스트를 따옴표로 감싸고, 내부 따옴표는 이스케이프 처리
                escapechar='\\'                # 백슬래시로 이스케이프 (Neo4j 호환성 증대)
            )
            
            chunk_count += 1
            total_rows += len(chunk)
            print(f"   Processing chunk {chunk_count}... (Total rows: {total_rows})", end='\r')

        print(f"\n✅ 정제 완료! 총 처리된 행: {total_rows}")
        print(f"📂 생성된 파일: {output_path}")
        return True

    except Exception as e:
        print(f"\n❌ 처리 중 오류 발생: {e}")
        return False

# --- 실행 설정 ---
# 실제 파일 경로에 맞게 수정해주세요.
# Docker를 쓰고 계시다면, 호스트 머신의 neo4j/import 폴더 경로를 지정해야 합니다.
if __name__ == "__main__":
    base_path = "C:/dev/study/skn18_fianl-2team/neo4j/my-rag-project/import" 
    input_csv = os.path.join(base_path, "disease_features.csv")
    output_csv = os.path.join(base_path, "disease_features_cleaned.csv")

    # 함수 실행
    clean_large_csv_chunked(input_csv, output_csv)