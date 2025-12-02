# kg/etl

### 실행 예시

```bash
# RAG 문서/엔터티 기반으로 KG 채우기 전체
python -m kg.etl.kg_pipeline_runner --source all

# PubMed만 대상으로 KG 업데이트
python -m kg.etl.kg_pipeline_runner --source pubmed

# 시뮬레이션 결과만 KG에 반영
python -m kg.etl.kg_pipeline_runner --run sim

# constraints + metrics만 다시 계산
python -m kg.etl.kg_pipeline_runner --run maintenance
```