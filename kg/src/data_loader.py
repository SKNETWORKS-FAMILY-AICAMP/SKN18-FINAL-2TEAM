import time
import sys
import os
from tqdm import tqdm
from typing import Optional

# src 폴더 경로 설정 수정
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from db_connector import Neo4jConnector
from queries_v2 import PrimeKGQueries

# S3 동기화 기능 (선택적)
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _normalize_prefix(prefix: str) -> str:
    """S3 prefix 정규화"""
    prefix = prefix or ""
    prefix = prefix.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


class Neo4jS3Syncer:
    """S3에서 Neo4j import 파일 다운로드 (PrimeKG용)"""
    
    def __init__(
        self,
        bucket: str,
        prefix: str,
        local_dir: str,
        skip_existing: bool = True,
    ) -> None:
        if not HAS_BOTO3:
            raise ImportError("boto3 is required for S3 sync")
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.local_dir = local_dir
        self.skip_existing = skip_existing
        self.s3 = boto3.client("s3")
    
    def sync(self) -> None:
        """S3에서 모든 파일을 로컬 디렉토리로 다운로드"""
        print(
            f"[S3] Syncing s3://{self.bucket}/{self.prefix or ''} "
            f"-> {self.local_dir} (skip_existing={self.skip_existing})"
        )
        os.makedirs(self.local_dir, exist_ok=True)
        
        objects_found = False
        downloaded = 0
        for obj in tqdm(self._iter_objects(), desc="Downloading PrimeKG data", unit="file"):
            objects_found = True
            key = obj["Key"]
            rel_path = self._relative_path(key)
            if not rel_path:
                continue
            
            dest_path = os.path.join(self.local_dir, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            if self._should_skip(dest_path, obj.get("Size")):
                continue
            
            try:
                self.s3.download_file(self.bucket, key, dest_path)
                downloaded += 1
            except ClientError as err:
                raise RuntimeError(
                    f"Failed to download s3://{self.bucket}/{key}: {err}"
                ) from err
        
        if not objects_found:
            print(f"[S3] Warning: No objects found in s3://{self.bucket}/{self.prefix or ''}")
        elif downloaded == 0:
            print("[S3] All files already exist locally.")
        else:
            print(f"[S3] Downloaded {downloaded} files.")
    
    def _iter_objects(self):
        """S3 객체 반복자"""
        paginator = self.s3.get_paginator("list_objects_v2")
        params = {"Bucket": self.bucket}
        if self.prefix:
            params["Prefix"] = self.prefix
        
        try:
            for page in paginator.paginate(**params, PaginationConfig={"PageSize": 50}):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith("/"):
                        continue
                    yield obj
        except ClientError as err:
            raise RuntimeError(
                f"Failed to list objects for s3://{self.bucket}/{self.prefix or ''}: {err}"
            ) from err
    
    def _relative_path(self, key: str) -> str:
        """S3 key에서 상대 경로 추출"""
        if self.prefix and key.startswith(self.prefix):
            return key[len(self.prefix):]
        return key
    
    def _should_skip(self, dest_path: str, expected_size: Optional[int]) -> bool:
        """파일을 건너뛸지 결정"""
        if not self.skip_existing or not os.path.exists(dest_path):
            return False
        if expected_size is None:
            return True
        try:
            return os.path.getsize(dest_path) == expected_size
        except OSError:
            return False


class PrimeKGLoader:
    def __init__(self, uri, user, password, import_dir: Optional[str] = None):
        self.connector = Neo4jConnector(uri, user, password)
        # import 디렉토리 설정 (AWS 환경 감지)
        if import_dir:
            self.import_dir = import_dir
        elif os.path.exists("/var/lib/neo4j/import"):
            # AWS EC2 환경
            self.import_dir = "/var/lib/neo4j/import"
        else:
            # 로컬 환경
            self.import_dir = "import"
    
    def clear_database(self):
        """데이터베이스의 모든 노드와 관계 삭제 (배치 처리로 메모리 절약)"""
        print("\n🗑️  기존 데이터 삭제 중...")
        try:
            # 제약 조건 삭제
            print("  제약 조건 삭제 중...")
            drop_constraints_query = """
            SHOW CONSTRAINTS
            """
            constraints = self.connector.execute_query(drop_constraints_query)
            for constraint in constraints:
                constraint_name = constraint.get('name', '')
                if constraint_name:
                    try:
                        self.connector.execute_query(f"DROP CONSTRAINT {constraint_name} IF EXISTS")
                    except:
                        pass
            
            # APOC를 사용한 배치 삭제 (메모리 효율적)
            print("  노드와 관계 삭제 중... (배치 처리)")
            try:
                # APOC를 사용한 배치 삭제
                batch_delete_query = """
                CALL apoc.periodic.iterate(
                "MATCH (n) RETURN n",
                "DETACH DELETE n",
                {batchSize: 1000, parallel: false}
                )
                """
                self.connector.execute_query(batch_delete_query)
                print("✅ 데이터베이스가 초기화되었습니다.\n")
            except Exception as apoc_error:
                # APOC가 없거나 실패한 경우, 작은 배치로 직접 삭제
                print("  APOC 배치 삭제 실패, 직접 삭제 시도...")
                try:
                    # 관계 먼저 삭제
                    rel_count = 1
                    while rel_count > 0:
                        delete_rels_query = """
                        MATCH ()-[r]->()
                        WITH r LIMIT 10000
                        DELETE r
                        RETURN count(r) as deleted
                        """
                        result = self.connector.execute_query(delete_rels_query)
                        rel_count = result[0]['deleted'] if result else 0
                        if rel_count > 0:
                            print(f"    관계 {rel_count}개 삭제됨...")
                    
                    # 노드 삭제
                    node_count = 1
                    while node_count > 0:
                        delete_nodes_query = """
                        MATCH (n)
                        WITH n LIMIT 10000
                        DELETE n
                        RETURN count(n) as deleted
                        """
                        result = self.connector.execute_query(delete_nodes_query)
                        node_count = result[0]['deleted'] if result else 0
                        if node_count > 0:
                            print(f"    노드 {node_count}개 삭제됨...")
                    
                    print("✅ 데이터베이스가 초기화되었습니다.\n")
                except Exception as direct_error:
                    print(f"⚠️  직접 삭제도 실패: {direct_error}")
                    print("💡 해결 방법:")
                    print("   1. Neo4j 컨테이너 재시작: docker restart neo4j-final")
                    print("   2. 데이터 폴더 삭제 후 재시작")
                    raise direct_error
        except Exception as e:
            print(f"⚠️  초기화 중 오류: {e}")
            print("💡 해결 방법:")
            print("   1. Neo4j 컨테이너 재시작 후 다시 시도")
            print("   2. 또는 데이터 폴더를 직접 삭제")
            raise

    def run_query_with_status(self, query, max_retries=3, retry_delay=5):
        """실제 쿼리를 실행하는 내부 함수 (재시도 로직 포함)"""
        for attempt in range(max_retries):
            try:
                with self.connector.driver.session() as session:
                    # 쿼리가 리스트인 경우 (예: 인덱스 생성) 하나씩 실행
                    if isinstance(query, list):
                        for q in query:
                            try:
                                result = session.run(q)
                                # 제약 조건 생성의 경우 결과 확인
                                summary = result.consume()
                                if 'CONSTRAINT' in q.upper() and 'IF NOT EXISTS' not in q.upper():
                                    # 제약 조건이 이미 존재하는 경우 무시
                                    pass
                            except Exception as constraint_error:
                                # 제약 조건이 이미 존재하는 경우 무시 (IF NOT EXISTS가 없는 경우)
                                error_msg = str(constraint_error)
                                if 'EquivalentSchemaRuleAlreadyExists' in error_msg or 'already exists' in error_msg.lower():
                                    print(f"  ℹ️  제약 조건이 이미 존재합니다: {q[:60]}...")
                                    continue
                                else:
                                    raise constraint_error
                    else:
                        result = session.run(query)
                        # APOC 쿼리의 경우 결과 확인
                        if 'apoc.periodic.iterate' in query:
                            summary = result.consume()
                            if summary.counters.nodes_created == 0 and 'LOAD_NODES' in str(query):
                                print(f"  ⚠️  경고: 노드가 생성되지 않았을 수 있습니다.")
                return True
            except Exception as e:
                # 제약 조건이 이미 존재하는 경우는 오류로 처리하지 않음
                error_msg = str(e)
                if 'EquivalentSchemaRuleAlreadyExists' in error_msg or 'already exists' in error_msg.lower():
                    print(f"  ℹ️  제약 조건이 이미 존재합니다. 계속 진행합니다.")
                    return True
                
                if attempt < max_retries - 1:
                    print(f"  ⚠️  시도 {attempt + 1}/{max_retries} 실패, {retry_delay}초 후 재시도...")
                    time.sleep(retry_delay)
                else:
                    raise e
        return False
    
    def verify_data(self):
        """로드된 데이터 검증"""
        print("\n" + "=" * 60)
        print("📊 데이터 검증 중...")
        print("=" * 60)
        
        # CSV 파일 행 수 확인 (pandas 선택적)
        csv_stats = {}
        try:
            import pandas as pd
            HAS_PANDAS = True
        except ImportError:
            HAS_PANDAS = False
            print("  ℹ️  pandas가 설치되지 않아 CSV 파일 검증을 건너뜁니다.")
            print("     Neo4j 데이터만 검증합니다.")
        
        if HAS_PANDAS:
            csv_files = {
                'nodes': os.path.join(self.import_dir, 'nodes.csv'),
                'edges': os.path.join(self.import_dir, 'edges.csv'),
                'disease_features': os.path.join(self.import_dir, 'disease_features.csv'),
                'drug_features': os.path.join(self.import_dir, 'drug_features.csv'),
                'kg_grouped_diseases': os.path.join(self.import_dir, 'kg_grouped_diseases.csv')
            }
            
            for name, path in csv_files.items():
                if os.path.exists(path):
                    try:
                        df = pd.read_csv(path)
                        csv_stats[name] = len(df)
                    except Exception as e:
                        print(f"  ⚠️  {name} 파일 읽기 실패: {e}")
                        csv_stats[name] = 0
        
        # Neo4j 데이터 확인
        node_count = self.connector.execute_query("MATCH (n:BaseNode) RETURN count(n) as count")[0]['count']
        rel_count = self.connector.execute_query("MATCH ()-[r]->() RETURN count(r) as count")[0]['count']
        rel_types = self.connector.execute_query("MATCH ()-[r]->() RETURN count(DISTINCT type(r)) as count")[0]['count']
        
        if HAS_PANDAS and csv_stats:
            print(f"\n📈 CSV 파일 통계:")
            for name, count in csv_stats.items():
                print(f"  {name:25s}: {count:,} 행")
        
        print(f"\n📈 Neo4j 데이터 통계:")
        print(f"  노드 수                    : {node_count:,}")
        print(f"  관계 수                    : {rel_count:,}")
        print(f"  관계 타입 종류             : {rel_types}개")
        
        # 관계 타입별 상세 확인
        rel_type_query = """
        MATCH ()-[r]->()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY count DESC
        """
        rel_types_detail = self.connector.execute_query(rel_type_query)
        print(f"\n📋 관계 타입별 상세:")
        for rel_info in rel_types_detail:
            print(f"  {rel_info['rel_type']:30s}: {rel_info['count']:,}")
        
        # 검증 결과
        print("\n" + "=" * 60)
        issues = []
        
        if HAS_PANDAS:
            if 'nodes' in csv_stats and node_count < csv_stats['nodes'] * 0.9:
                issues.append(f"⚠️  노드 수 불일치: CSV {csv_stats['nodes']:,}개 vs Neo4j {node_count:,}개")
            
            if 'edges' in csv_stats and rel_count < csv_stats['edges'] * 0.9:
                issues.append(f"⚠️  관계 수 불일치: CSV {csv_stats['edges']:,}개 vs Neo4j {rel_count:,}개")
        
        if rel_types < 10:  # 예상 관계 타입이 18개이므로
            issues.append(f"⚠️  관계 타입이 적습니다: {rel_types}개 (예상: 18개)")
        
        if issues:
            print("❌ 검증 실패:")
            for issue in issues:
                print(f"  {issue}")
            print("\n💡 해결 방법:")
            print("  1. --clear 옵션으로 데이터베이스를 초기화하고 재로드")
            print("  2. Neo4j 로그 확인: docker logs neo4j-final")
            print("  3. 메모리 부족 시 배치 크기 조정 (queries_v2.py의 batchSize 수정)")
        else:
            print("✅ 데이터 검증 통과!")
        
        print("=" * 60 + "\n")
        
        return len(issues) == 0

    def load_all(self, verify=True):
        print("\n🚀 PrimeKG 데이터 로딩을 시작합니다... (Neo4j)\n")

        # 1. 작업 목록 정의 (표시 이름, 실행할 쿼리)
        tasks = [
            ("1/6 인덱스 생성 (필수)", PrimeKGQueries.CREATE_CONSTRAINTS),
            ("2/6 노드 로딩 (nodes.csv)", PrimeKGQueries.LOAD_NODES),
            ("3/6 엣지 연결 (edges.csv - 오래 걸림)", PrimeKGQueries.LOAD_EDGES),
            ("4/6 질병 상세정보 추가 (disease_features)", PrimeKGQueries.UPDATE_DISEASE_FEATURES),
            ("5/6 약물 상세정보 추가 (drug_features)", PrimeKGQueries.UPDATE_DRUG_FEATURES),
            ("6/6 질병 그룹 매핑 (grouped_diseases)", PrimeKGQueries.UPDATE_DISEASE_GROUPS)
        ]

        # 2. tqdm을 사용한 진행바 생성
        failed_tasks = []
        
        with tqdm(total=len(tasks), ncols=100, colour='green') as pbar:
            
            for task_name, query in tasks:
                # 진행바 옆에 현재 작업 이름 표시
                pbar.set_description(f"Processing: {task_name}")
                
                try:
                    # 쿼리 실행 (재시도 로직 포함)
                    success = self.run_query_with_status(query, max_retries=3)
                    
                    if success:
                        # 성공 시 진행바 1칸 전진
                        pbar.update(1)
                    else:
                        failed_tasks.append(task_name)
                        print(f"\n⚠️  [{task_name}] 재시도 후에도 실패했습니다.")
                        pbar.update(1)  # 실패해도 진행바는 업데이트
                    
                except Exception as e:
                    # 에러 발생 시 상세 정보 출력
                    failed_tasks.append(task_name)
                    print(f"\n❌ 오류 발생 [{task_name}]: {e}")
                    print(f"   오류 타입: {type(e).__name__}")
                    import traceback
                    print(f"   상세 정보:\n{traceback.format_exc()}")
                    # 계속 진행 (다음 작업 시도)
                    pbar.update(1)

        # 결과 요약
        print("\n" + "=" * 60)
        if failed_tasks:
            print(f"⚠️  실패한 작업: {len(failed_tasks)}개")
            for task in failed_tasks:
                print(f"  - {task}")
            print("\n💡 해결 방법:")
            print("  1. Neo4j 로그 확인: docker logs neo4j-final")
            print("  2. --clear 옵션으로 재시도")
            print("  3. Docker 컨테이너 재시작: docker restart neo4j-final")
        else:
            print("✨ 모든 데이터 로딩 작업이 완료되었습니다!")
        print("=" * 60)
        
        # 데이터 검증
        if verify:
            self.verify_data()
        
        self.connector.close()


def _env_bool(name: str, default: bool) -> bool:
    """환경 변수를 boolean으로 변환"""
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_aws_region() -> str:
    """AWS 리전 감지 (여러 방법 시도)"""
    # 1. 환경 변수 확인
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    if region:
        return region
    
    # 2. boto3 세션에서 리전 가져오기
    try:
        import boto3
        session = boto3.Session()
        if session.region_name:
            return session.region_name
    except:
        pass
    
    # 3. EC2 메타데이터에서 리전 가져오기
    try:
        import urllib.request
        url = "http://169.254.169.254/latest/meta-data/placement/region"
        with urllib.request.urlopen(url, timeout=5) as response:
            region = response.read().decode().strip()
            if region:
                return region
    except:
        pass
    
    # 4. 기본값 사용
    return "ap-northeast-2"


def _get_neo4j_password_from_parameter_store() -> Optional[str]:
    """AWS Parameter Store에서 Neo4j 비밀번호 가져오기"""
    if not HAS_BOTO3:
        return None
    
    try:
        import boto3
        
        # AWS 리전 감지
        region = _get_aws_region()
        if not region:
            print("⚠️  AWS 리전을 감지할 수 없습니다.")
            return None
        
        # Parameter Store에서 비밀번호 가져오기
        ssm = boto3.client("ssm", region_name=region)
        response = ssm.get_parameter(
            Name="/skn18/neo4j-password",
            WithDecryption=True
        )
        password = response["Parameter"]["Value"]
        print(f"✅ Parameter Store에서 Neo4j 비밀번호를 가져왔습니다. (Region: {region})")
        return password
    except Exception as e:
        print(f"⚠️  Parameter Store에서 비밀번호를 가져오지 못했습니다: {e}")
        print(f"   리전: {_get_aws_region()}")
        print("   환경 변수로 직접 설정하거나 AWS CLI로 확인하세요:")
        print("   aws ssm get-parameter --name /skn18/neo4j-password --with-decryption --query 'Parameter.Value' --output text")
        return None


if __name__ == "__main__":
    import argparse
    
    # 환경 변수에서 설정 읽기 (AWS 환경 지원)
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    
    # 비밀번호 가져오기 (환경 변수 → Parameter Store → 기본값 순서)
    PASSWORD = os.getenv("NEO4J_PASSWORD")
    if not PASSWORD:
        # AWS 환경에서 Parameter Store에서 가져오기 시도
        PASSWORD = _get_neo4j_password_from_parameter_store()
        if not PASSWORD:
            # AWS EC2 환경인지 확인
            is_ec2 = os.path.exists("/var/lib/neo4j/import") or os.path.exists("/sys/hypervisor/uuid")
            if is_ec2:
                # EC2 환경에서는 기본값 사용하지 않고 에러
                print("\n❌ Neo4j 비밀번호를 가져올 수 없습니다.")
                print("   AWS EC2 환경에서는 다음 중 하나를 수행하세요:")
                print("   1. 환경 변수로 설정:")
                print("      export NEO4J_PASSWORD='<비밀번호>'")
                print("   2. Parameter Store에서 직접 확인:")
                print("      aws ssm get-parameter --name /skn18/neo4j-password --with-decryption --query 'Parameter.Value' --output text")
                print("   3. Parameter Store에 비밀번호가 저장되어 있는지 확인:")
                print("      aws ssm get-parameter --name /skn18/neo4j-password --with-decryption")
                exit(1)
            else:
                # 로컬 환경에서는 기본값 사용
                PASSWORD = "neo4jpass"
                print("ℹ️  환경 변수 NEO4J_PASSWORD가 설정되지 않았습니다. 기본값을 사용합니다.")
    
    IMPORT_DIR = os.getenv("NEO4J_IMPORT_DIR", None)  # None이면 자동 감지
    
    # S3 설정 (선택적)
    S3_BUCKET = os.getenv("NEO4J_S3_BUCKET", "skn18-etl-data")
    S3_PREFIX = os.getenv("NEO4J_S3_PREFIX", "neo4j-data/")  # PrimeKG 데이터 prefix (s3://skn18-etl-data/neo4j-data/)
    DOWNLOAD_FROM_S3 = _env_bool("NEO4J_DOWNLOAD", False)
    
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='PrimeKG 데이터를 Neo4j에 로드')
    parser.add_argument('--clear', action='store_true', help='기존 데이터를 삭제하고 새로 로드')
    parser.add_argument('--no-verify', action='store_true', help='데이터 검증 건너뛰기')
    parser.add_argument('--download', action='store_true', help='S3에서 데이터 다운로드 (AWS 환경)')
    parser.add_argument('--import-dir', type=str, help='Neo4j import 디렉토리 경로 (기본값: 자동 감지)')
    args = parser.parse_args()
    
    # import 디렉토리 설정
    if args.import_dir:
        import_dir = args.import_dir
    elif IMPORT_DIR:
        import_dir = IMPORT_DIR
    else:
        import_dir = None  # 자동 감지
    
    loader = PrimeKGLoader(URI, USER, PASSWORD, import_dir=import_dir)
    
    # S3에서 데이터 다운로드 (선택적)
    if args.download or DOWNLOAD_FROM_S3:
        if not HAS_BOTO3:
            print("⚠️  boto3가 설치되지 않았습니다. S3 다운로드를 건너뜁니다.")
        else:
            print(f"\n📥 S3에서 PrimeKG 데이터 다운로드 중...")
            print(f"   Bucket: {S3_BUCKET}")
            print(f"   Prefix: {S3_PREFIX}")
            print(f"   Destination: {loader.import_dir}")
            try:
                syncer = Neo4jS3Syncer(S3_BUCKET, S3_PREFIX, loader.import_dir)
                syncer.sync()
                print("✅ S3 다운로드 완료\n")
            except Exception as e:
                print(f"⚠️  S3 다운로드 실패: {e}")
                print("   로컬 파일이 있으면 계속 진행합니다...\n")
    
    # 연결 테스트
    if not loader.connector.test_connection():
        print("❌ Neo4j 연결에 실패했습니다.")
        print(f"   URI: {URI}")
        print(f"   User: {USER}")
        print(f"   Password: {'설정됨' if PASSWORD else '설정되지 않음'}")
        print("\n💡 해결 방법:")
        print("   1. Neo4j Docker 컨테이너가 실행 중인지 확인:")
        print("      docker ps | grep neo4j")
        print("   2. AWS EC2 환경인 경우 Parameter Store에서 비밀번호 확인:")
        print("      aws ssm get-parameter --name /skn18/neo4j-password --with-decryption --query 'Parameter.Value' --output text")
        print("   3. 환경 변수로 비밀번호 설정:")
        print("      export NEO4J_PASSWORD='<비밀번호>'")
        print("   4. Neo4j 컨테이너 로그 확인:")
        print("      docker logs neo4j-final")
        exit(1)
    
    # 기존 데이터 삭제 옵션
    if args.clear:
        loader.clear_database()
    
    loader.load_all(verify=not args.no_verify)
