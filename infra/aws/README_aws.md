# AWS 솔루션 목록

다음 리소스는 `infra/aws/cloudformation`의 템플릿에서 사용 중인 AWS 서비스입니다.

1. **네트워크**
   - Amazon VPC (사설망)
   - Public Subnet
   - Internet Gateway & RouteTable
2. **보안**
   - EC2 Security Group (PostgreSQL/SSH 제어)
   - IAM Role (`skn18-lambda-etl-role`)
3. **스토리지**
   - Amazon S3 (ETL 결과 저장 버킷)
   - AWS Systems Manager Parameter Store (구성/비밀 키 관리)
4. **컴퓨팅**
   - Amazon EC2 (pgvector 컨테이너 실행)
     - AMI: `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64` Parameter Store 경로를 참조하여 최신 Amazon Linux 2023 이미지를 사용
   - AWS Lambda (Protocols/NIH ETL 함수)
   - Lambda Layers (Common / Protocols / NIH 의존성 패키지)
5. **오케스트레이션**
   - Amazon EventBridge (ETL 스케줄러)
   - AWS Step Functions (Protocols Ingest Lambda 병렬 실행)
   - AWS CloudFormation (Nested Stack: CoreInfra / Protocols / NIH)

필요 시 `skn18-final-infra-cf.yaml`을 통해 루트 스택을 배포하고, 각 Nested Stack이 위 서비스들을 생성하거나 참조합니다.

## Protocols Ingest Step Function

Protocols Ingest Lambda 6개(Cell, DNA, Mouse, Protein, RNA, Vivo)는 Step Function을 통해 병렬로 실행됩니다:

- **State Machine**: `skn18-protocols-ingest-parallel`
- **실행 방식**: Parallel 상태로 6개 Lambda 동시 실행
- **스케줄링**: EventBridge Rule이 하루에 한 번 Step Function 실행
- **장점**: 
  - 처리 시간 단축 (병렬 실행)
  - 실행 상태 중앙 모니터링
  - 에러 추적 및 관리 용이
