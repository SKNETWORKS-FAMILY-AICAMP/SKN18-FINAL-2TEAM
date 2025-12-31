#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CSV 파일에서 임베딩된 청크 데이터 추출 → 평가용 질문 생성
- 논문 3개 (ts_embedding_v2.csv) - 대표성 있는 청크 선별
- 임상 3개 (embedded_vectors_bge_m3_dense.csv) - 대표성 있는 청크 선별
- 프로토콜 3개 (embedded_vectors_bge_m3_dense.csv) - 대표성 있는 청크 선별
→ 각 청크당 1개의 평가용 질문 생성 (총 9개 질문)

선별 기준:
1. 텍스트 길이: 300~2000자 (너무 짧거나 긴 것 제외)
2. 내용 다양성: 서로 다른 섹션/프로토콜에서 선별
3. 품질: 내용이 충실한 청크 우선
"""

import pandas as pd
from openai import OpenAI
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import random
import json

# .env 파일에서 환경변수 로드
load_dotenv()

def get_embedding_dimension(embedding_str):
    """
    임베딩 벡터에서 차원 추출
    
    Args:
        embedding_str: JSON 형태의 임베딩 벡터 문자열 또는 리스트
    
    Returns:
        임베딩 차원 (int)
    """
    try:
        if isinstance(embedding_str, str):
            emb_vector = json.loads(embedding_str)
        elif isinstance(embedding_str, list):
            emb_vector = embedding_str
        else:
            return 0
        return len(emb_vector)
    except:
        return 0

def select_representative_chunks(df, chunk_col='text_chunk', id_col='chunk_id', 
                                 meta_col=None, n=3, min_len=300, max_len=2000):
    """
    대표성 있는 청크를 선별하는 함수
    
    Args:
        df: DataFrame
        chunk_col: 텍스트 컬럼명
        id_col: ID 컬럼명
        meta_col: 메타 정보 컬럼 (section_id, protocol_id 등)
        n: 선별할 개수
        min_len: 최소 텍스트 길이
        max_len: 최대 텍스트 길이
    
    Returns:
        선별된 DataFrame
    """
    if len(df) == 0:
        return df
    
    # 1단계: 텍스트 길이 필터링
    df_filtered = df.copy()
    df_filtered['text_length'] = df_filtered[chunk_col].astype(str).str.len()
    df_filtered = df_filtered[
        (df_filtered['text_length'] >= min_len) & 
        (df_filtered['text_length'] <= max_len)
    ]
    
    print(f"     텍스트 길이 필터링: {len(df)}개 → {len(df_filtered)}개")
    
    if len(df_filtered) == 0:
        print(f"     ⚠️  조건에 맞는 청크가 없어서 원본에서 선택합니다.")
        df_filtered = df.copy()
        df_filtered['text_length'] = df_filtered[chunk_col].astype(str).str.len()
    
    # 2단계: 다양성 확보 (메타 정보가 있으면 서로 다른 것 우선)
    if meta_col and meta_col in df_filtered.columns:
        # 메타 정보별로 그룹화하여 균등 샘플링
        unique_metas = df_filtered[meta_col].unique()
        if len(unique_metas) >= n:
            # 서로 다른 메타에서 하나씩
            selected_dfs = []
            sampled_metas = random.sample(list(unique_metas), n)
            for meta in sampled_metas:
                meta_df = df_filtered[df_filtered[meta_col] == meta].copy()
                # 각 메타에서 텍스트 길이가 중간 정도인 것 선택
                median_length = meta_df['text_length'].median()
                meta_df['diff_from_median'] = abs(meta_df['text_length'] - median_length)
                selected = meta_df.nsmallest(1, 'diff_from_median')
                selected_dfs.append(selected.drop(columns=['diff_from_median']))
            result_df = pd.concat(selected_dfs)
            print(f"     다양성 확보: {len(unique_metas)}개 메타 중 {n}개 선택")
        else:
            # 메타가 부족하면 무작위 샘플링
            result_df = df_filtered.sample(n=min(n, len(df_filtered)), random_state=42)
            print(f"     무작위 샘플링: {n}개 선택")
    else:
        # 메타 정보가 없으면 균등 간격 샘플링
        if len(df_filtered) >= n:
            # 전체를 균등하게 나눠서 샘플링
            indices = [int(i * len(df_filtered) / n) for i in range(n)]
            result_df = df_filtered.iloc[indices]
            print(f"     균등 간격 샘플링: {n}개 선택")
        else:
            result_df = df_filtered.head(n)
            print(f"     전체 선택: {len(result_df)}개")
    
    # 3단계: 텍스트 길이 순으로 정렬 (일관성)
    result_df = result_df.sort_values('text_length', ascending=False).head(n)
    
    return result_df.drop(columns=['text_length'])

def main():
    print("=" * 80)
    print("🚀 임베딩 청크 데이터 추출 & RAG 평가용 질문 생성")
    print("=" * 80)
    print("\n📌 선별 기준:")
    print("  - 텍스트 길이: 300~2000자 (논문), 250~2000자 (임상/프로토콜)")
    print("  - 내용 다양성: 서로 다른 섹션/프로토콜에서 우선 선별")
    print("  - 각 유형당 대표 청크 3개씩 선별")
    print("=" * 80)
    
    # ========================================
    # 1단계: CSV 파일 경로 확인
    # ========================================
    print("\n📂 CSV 파일 확인 중...")
    
    base_path = Path("infra/neo4j/import")
    논문_csv = base_path / "ts_embedding_v2.csv"
    프로토콜_csv = base_path / "embedded_vectors_bge_m3_dense.csv"
    
    if not 논문_csv.exists():
        print(f"❌ 논문 CSV 파일이 없습니다: {논문_csv}")
        return
    
    if not 프로토콜_csv.exists():
        print(f"❌ 프로토콜 CSV 파일이 없습니다: {프로토콜_csv}")
        return
    
    print(f"✅ 논문 CSV: {논문_csv}")
    print(f"✅ 프로토콜 CSV: {프로토콜_csv}")
    
    # ========================================
    # 2단계: 데이터 추출
    # ========================================
    print("\n📊 데이터 추출 중...")
    
    # 논문 청크 - 대표성 있는 3개 선별
    print("  📄 논문 청크 추출 및 선별...")
    try:
        # 더 많은 청크를 읽어서 그 중에서 선별 (1000개 읽기)
        논문_전체_df = pd.read_csv(
            논문_csv,
            nrows=1000,
            usecols=['chunk_id', 'text_chunk', 'section_id', 'emb_model', 'emb_dim']
        )
        print(f"     총 {len(논문_전체_df)}개 청크 로드")
        
        # 일반 논문 청크 (임상 키워드 제외)
        clinical_keywords = ['clinical trial', 'patient', 'treatment', 'therapy', 'diagnosis', 'disease', 'medical', 'NCT']
        pattern = '|'.join(clinical_keywords)
        
        # 임상 키워드가 없는 순수 논문 청크
        순수논문_df = 논문_전체_df[~논문_전체_df['text_chunk'].str.contains(pattern, case=False, na=False)]
        print(f"     순수 논문 청크: {len(순수논문_df)}개")
        
        # 대표 청크 선별
        논문_df = select_representative_chunks(
            순수논문_df,
            chunk_col='text_chunk',
            id_col='chunk_id',
            meta_col='section_id',
            n=3,
            min_len=300,
            max_len=2000
        )
        논문_df['type'] = '논문'
        print(f"     ✓ 대표 청크 {len(논문_df)}개 선별 완료")
    except Exception as e:
        print(f"     ✗ 실패: {e}")
        논문_df = pd.DataFrame()
    
    # 임상 청크 - 논문 데이터에서 임상 키워드 포함된 청크 선별
    print("  🧪 임상 청크 추출 및 선별 (논문 데이터에서)...")
    try:
        # 임상 키워드가 포함된 청크 필터링
        clinical_keywords = ['clinical trial', 'patient', 'treatment', 'therapy', 'diagnosis', 'disease', 'medical', 'NCT']
        pattern = '|'.join(clinical_keywords)
        
        임상_전체_df = 논문_전체_df[논문_전체_df['text_chunk'].str.contains(pattern, case=False, na=False)]
        print(f"     총 {len(임상_전체_df)}개 임상 관련 청크 발견")
        
        # 대표 청크 선별
        임상_df = select_representative_chunks(
            임상_전체_df,
            chunk_col='text_chunk',
            id_col='chunk_id',
            meta_col='section_id',
            n=3,
            min_len=300,
            max_len=2000
        )
        임상_df['type'] = '임상'
        print(f"     ✓ 대표 청크 {len(임상_df)}개 선별 완료")
    except Exception as e:
        print(f"     ✗ 실패: {e}")
        import traceback
        traceback.print_exc()
        임상_df = pd.DataFrame()
    
    # 프로토콜 청크 - 대표성 있는 3개 선별
    print("  🔬 프로토콜 청크 추출 및 선별...")
    try:
        # 더 많은 청크를 읽어서 그 중에서 선별 (100개 읽기)
        # 필요한 컬럼: protocol_id, url, title, chunking_id, text, embedding
        프로토콜_전체_df = pd.read_csv(
            프로토콜_csv,
            nrows=100,
            usecols=['protocol_id', 'url', 'title', 'chunking_id', 'text', 'embedding']
        )
        
        print(f"     총 {len(프로토콜_전체_df)}개 청크 로드")
        
        # 컬럼명 표준화
        if 'chunking_id' in 프로토콜_전체_df.columns:
            프로토콜_전체_df = 프로토콜_전체_df.rename(columns={'chunking_id': 'chunk_id'})
        if 'text' in 프로토콜_전체_df.columns:
            프로토콜_전체_df = 프로토콜_전체_df.rename(columns={'text': 'text_chunk'})
        
        # 프로토콜 청크 선별
        프로토콜_df = select_representative_chunks(
            프로토콜_전체_df,
            chunk_col='text_chunk',
            id_col='chunk_id',
            meta_col='protocol_id' if 'protocol_id' in 프로토콜_전체_df.columns else None,
            n=3,
            min_len=250,
            max_len=2000
        )
        프로토콜_df['type'] = '프로토콜'
        print(f"     ✓ 프로토콜 대표 청크 {len(프로토콜_df)}개 선별 완료")
        
    except Exception as e:
        print(f"     ✗ 실패: {e}")
        import traceback
        traceback.print_exc()
        프로토콜_df = pd.DataFrame()
    
    # ========================================
    # 3단계: 데이터 정리
    # ========================================
    print("\n🔄 데이터 정리 중...")
    
    전체_청크 = []
    
    # 논문 추가
    for idx, row in 논문_df.iterrows():
        전체_청크.append({
            'type': '논문',
            'id': row.get('chunk_id', f'paper_{idx}'),
            'text': str(row.get('text_chunk', '')),
            'meta': f"Section: {row.get('section_id', 'N/A')}",
            'emb_info': f"{row.get('emb_model', 'N/A')} ({row.get('emb_dim', 0)}dim)"
        })
    
    # 임상 추가 (논문 데이터에서 추출됨 - OpenAI 1536dim)
    for idx, row in 임상_df.iterrows():
        # 임상 데이터는 논문 CSV에서 가져왔으므로 OpenAI 임베딩 사용
        emb_model = row.get('emb_model', 'text-embedding-3-small')
        emb_dim = row.get('emb_dim', 1536)
        emb_info = f"{emb_model} ({emb_dim}dim)"
        
        # 임상 관련 섹션 정보
        section_id = row.get('section_id', 'N/A')
        meta_info = f"Clinical Section: {section_id}"
        
        전체_청크.append({
            'type': '임상',
            'id': row.get('chunk_id', f'clinical_{idx}'),
            'text': str(row.get('text_chunk', '')),
            'meta': meta_info,
            'emb_info': emb_info
        })
    
    # 프로토콜 추가
    for idx, row in 프로토콜_df.iterrows():
        # 임베딩 차원 추출
        emb_dim = get_embedding_dimension(row.get('embedding', '[]'))
        emb_info = f"bge-m3-dense ({emb_dim}dim)" if emb_dim > 0 else "bge-m3-dense (unknown dim)"
        
        # 프로토콜 메타 정보
        protocol_id = row.get('protocol_id', 'N/A')
        title = row.get('title', '')
        
        # 제목이 있으면 함께 표시
        if title and title != 'N/A':
            meta_info = f"Protocol ID: {protocol_id} - {title[:50]}"
        else:
            meta_info = f"Protocol ID: {protocol_id}"
        
        전체_청크.append({
            'type': '프로토콜',
            'id': row.get('chunk_id', f'protocol_{idx}'),
            'text': str(row.get('text_chunk', '')),
            'meta': meta_info,
            'emb_info': emb_info
        })
    
    print(f"\n✅ 총 {len(전체_청크)}개 청크 준비 완료!")
    
    # 청크 목록 출력
    print("\n📋 청크 목록:")
    for i, 청크 in enumerate(전체_청크, 1):
        text_preview = 청크['text'][:80].replace('\n', ' ')
        print(f"  {i}. [{청크['type']:^6}] {청크['id']:35}")
        print(f"     메타: {청크['meta']}")
        print(f"     텍스트: {text_preview}...")
        print(f"     임베딩: {청크['emb_info']}")
    
    if len(전체_청크) == 0:
        print("\n❌ 추출된 청크가 없습니다!")
        return
    
    # ========================================
    # 4단계: GPT로 질문 생성
    # ========================================
    print("\n" + "=" * 80)
    print("👨‍🍳 GPT-4로 평가용 질문 생성 시작...")
    print("=" * 80)
    
    # OpenAI API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다!")
        print("\n💡 설정 방법:")
        print("   # Windows PowerShell")
        print('   $env:OPENAI_API_KEY="sk-your-api-key"')
        print("\n   # Git Bash / Linux / Mac")
        print('   export OPENAI_API_KEY="sk-your-api-key"')
        return
    
    client = OpenAI(api_key=api_key)
    결과_목록 = []
    
    for i, 청크 in enumerate(전체_청크, 1):
        print(f"\n[{i}/{len(전체_청크)}] {청크['type']} - {청크['id']}")
        print(f"  텍스트 길이: {len(청크['text'])}자")
        
        # 텍스트가 너무 짧으면 스킵
        if len(청크['text']) < 50:
            print(f"  ⚠️  텍스트가 너무 짧아서 스킵합니다.")
            continue
        
        # GPT 프롬프트 - RAG 검색 최적화 버전
        프롬프트 = f"""다음은 {청크['type']} 데이터의 청크입니다. 이 청크를 RAG 시스템에서 검색할 수 있는 평가용 질문을 만들어주세요.

【원본 텍스트】
{청크['text'][:1500]}

【중요: RAG 검색 가능한 질문 작성 규칙】
1. ✅ 질문에 원본 텍스트의 핵심 키워드를 3-5개 이상 반드시 포함하세요
2. ✅ 질문의 범위를 적절히 넓게 만들어 임베딩 유사도를 높이세요
3. ✅ 원본 텍스트의 주요 개념과 맥락을 질문에 포함하세요
4. ✅ 전문 용어는 원본과 동일하게 사용하세요
5. ❌ 너무 세부적인 단일 사실만 묻지 마세요
6. ❌ 원본에 없는 용어나 개념을 사용하지 마세요
7. ❌ "무엇", "왜", "어떻게"만 묻지 말고 주제와 키워드를 명시하세요

【좋은 질문 예시】
원본: "Vitamin D3 plays a crucial role in calcium homeostasis and bone mineralization..."
❌ 나쁜 질문: "어떤 호르몬이 칼슘 항상성에 중요한가요?" (키워드 부족, 주제 불명확)
✅ 좋은 질문: "Vitamin D3가 calcium homeostasis와 bone mineralization 과정에서 수행하는 생물학적 역할과 중요성은 무엇인가요?" (핵심 키워드 포함, 주제 명확)

【출력 형식】
질문만 한 줄로 출력해주세요 (번호나 기호 없이)
"""
        
        try:
            # GPT API 호출
            system_message = """당신은 RAG 시스템 평가를 위한 질문을 생성하는 전문가입니다.

**핵심 목표:** 생성한 질문을 RAG 시스템에 입력했을 때, 원본 청크를 상위 검색 결과로 찾을 수 있어야 합니다.

**전략:**
- 질문에 원본 텍스트의 핵심 키워드와 전문 용어를 충분히 포함
- 질문과 원본 청크 간 임베딩 벡터의 코사인 유사도가 높도록 작성
- 너무 좁은 세부사항보다는 주요 개념, 프로세스, 관계를 포함한 질문 생성
- 학술 논문, 임상 시험, 실험 프로토콜의 전문적 맥락을 유지"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": 프롬프트}
                ],
                temperature=0.3,  # 더 일관되고 키워드 중심적인 질문 생성
                max_tokens=300    # 충분한 컨텍스트를 포함할 수 있도록 증가
            )
            
            질문들 = response.choices[0].message.content.strip()
            
            print(f"  ✓ 질문 생성 완료")
            print(f"  {질문들[:100]}...")
            
            # 결과 저장
            결과_목록.append({
                '유형': 청크['type'],
                '청크ID': 청크['id'],
                '메타정보': 청크['meta'],
                '임베딩정보': 청크['emb_info'],
                '원본텍스트': 청크['text'][:500] + "...",
                '텍스트길이': len(청크['text']),
                '생성된질문': 질문들
            })
            
        except Exception as e:
            print(f"  ✗ 질문 생성 실패: {e}")
            결과_목록.append({
                '유형': 청크['type'],
                '청크ID': 청크['id'],
                '메타정보': 청크['meta'],
                '임베딩정보': 청크['emb_info'],
                '원본텍스트': 청크['text'][:500],
                '텍스트길이': len(청크['text']),
                '생성된질문': f"ERROR: {str(e)}"
            })
    
    # ========================================
    # 5단계: 결과 저장
    # ========================================
    print("\n" + "=" * 80)
    print("💾 결과 저장 중...")
    print("=" * 80)
    
    # DataFrame 생성
    결과_df = pd.DataFrame(결과_목록)
    
    # 파일명에 타임스탬프 추가
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_file = f"RAG_평가용_질문_{timestamp}.xlsx"
    csv_file = f"RAG_평가용_질문_{timestamp}.csv"
    
    # 엑셀로 저장
    try:
        결과_df.to_excel(excel_file, index=False, engine='openpyxl')
        print(f"✅ 엑셀 저장: {excel_file}")
    except Exception as e:
        print(f"⚠️  엑셀 저장 실패: {e}")
    
    # CSV로도 저장 (백업)
    try:
        결과_df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"✅ CSV 저장: {csv_file}")
    except Exception as e:
        print(f"⚠️  CSV 저장 실패: {e}")
    
    # ========================================
    # 6단계: 요약 출력
    # ========================================
    print("\n" + "=" * 80)
    print("📊 최종 결과 요약")
    print("=" * 80)
    
    print(f"\n총 청크 수: {len(결과_목록)}개")
    print(f"총 질문 수: {len(결과_목록)}개 (각 청크당 1개)")
    
    유형별_통계 = 결과_df['유형'].value_counts()
    print(f"\n유형별 통계:")
    for 유형, 개수 in 유형별_통계.items():
        print(f"  - {유형}: {개수}개")
    
    print(f"\n📁 생성된 파일:")
    print(f"  - {excel_file}")
    print(f"  - {csv_file}")
    
    # ========================================
    # 7단계: 미리보기
    # ========================================
    print("\n" + "=" * 80)
    print("👀 결과 미리보기 (처음 3개)")
    print("=" * 80)
    
    for i, row in 결과_df.head(3).iterrows():
        print(f"\n[{i+1}] {row['유형']} - {row['청크ID']}")
        print(f"메타: {row['메타정보']}")
        print(f"텍스트: {row['원본텍스트'][:100]}...")
        print(f"\n생성된 질문:")
        print(row['생성된질문'])
        print("-" * 80)
    
    print("\n✨ 완료! RAG 평가용 질문이 생성되었습니다!")
    print("📝 각 청크당 1개의 평가용 질문이 생성되었습니다.")
    print("\n🎯 선별된 청크 특징:")
    print("  - 대표성: 각 유형을 잘 나타내는 청크")
    print("  - 적절한 길이: 평가에 적합한 텍스트 분량")
    print("  - 다양성: 서로 다른 주제/섹션에서 선별")


if __name__ == "__main__":
    main()

