"""
Neoplasms_US 폴더의 모든 페이지(1~23)를 처리하는 스크립트
"""
import os

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    
    # Page 1부터 23까지 처리
    pages = list(range(1, 24))  # 1, 2, 3, ..., 23
    
    print("=" * 60)
    print(f"총 {len(pages)}개 페이지 처리 시작 (Page 1~23)")
    print("=" * 60)
    
    success_count = 0
    fail_count = 0
    
    for page_num in pages:
        input_file = os.path.join(project_root, "US", "Neoplasms_us", "Neoplasms_US", f"Neoplasms_US_Page_{page_num}.json")
        chunk_output = f"test_chunk12(pg{page_num}).csv"
        metadata_output = f"test_metadata12(pg{page_num}).csv"
        
        print(f"\n[Page {page_num}] 처리 중...")
        print(f"  입력: Neoplasms_US_Page_{page_num}.json")
        
        # main.py 실행
        cmd = f'python main.py --input "{input_file}" --output-chunk "{chunk_output}" --output-metadata "{metadata_output}"'
        result = os.system(cmd)
        
        if result == 0:
            success_count += 1
            print(f"✓ Page {page_num} 처리 완료")
            print(f"  - {chunk_output}")
            print(f"  - {metadata_output}")
        else:
            fail_count += 1
            print(f"✗ Page {page_num} 처리 실패")
    
    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)
    print(f"✓ 성공: {success_count}개 페이지")
    if fail_count > 0:
        print(f"✗ 실패: {fail_count}개 페이지")
    print(f"✓ 각 페이지별로 개별 파일 생성됨")
    print("=" * 60)

if __name__ == "__main__":
    main()

