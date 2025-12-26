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
   - Amazon EventBridge (키워드별 ETL 스케줄러)
   - AWS CloudFormation (Nested Stack: CoreInfra / Protocols / NIH)

필요 시 `skn18-final-infra-cf.yaml`을 통해 루트 스택을 배포하고, 각 Nested Stack이 위 서비스들을 생성하거나 참조합니다.
