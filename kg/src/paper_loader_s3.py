import os
import sys
from typing import Iterator, Optional

from tqdm import tqdm

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError as exc:  # pragma: no cover - dependency check
    raise ImportError("boto3 is required to download Neo4j data from S3.") from exc

# src 폴더 경로 설정 (paper_loader_s3.py가 프로젝트 루트에 있다고 가정)
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from db_connector import Neo4jConnector  # type: ignore  # pylint: disable=wrong-import-position
from queries_v2 import (  # type: ignore  # pylint: disable=wrong-import-position
    PaperRAGQueries,
    ProtocolQueries,
    ClinicalTrialQueries,
)


DEFAULT_S3_BUCKET = "skn18-etl-data"
DEFAULT_S3_PREFIX = "neo4j-data/"
DEFAULT_IMPORT_DIR = "/var/lib/neo4j/import"


def _normalize_prefix(prefix: str) -> str:
    prefix = prefix or ""
    prefix = prefix.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


class Neo4jS3Syncer:
    """Downloads Neo4j import files from S3 into the host import directory."""

    def __init__(
        self,
        bucket: str,
        prefix: str,
        local_dir: str,
        skip_existing: bool = True,
    ) -> None:
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.local_dir = local_dir
        self.skip_existing = skip_existing
        self.s3 = boto3.client("s3")

    def sync(self) -> None:
        """Download every object under the prefix into the local directory."""
        print(
            f"[S3] Syncing s3://{self.bucket}/{self.prefix or ''} "
            f"-> {self.local_dir} (skip_existing={self.skip_existing})"
        )
        os.makedirs(self.local_dir, exist_ok=True)

        objects_found = False
        downloaded = 0
        for obj in tqdm(self._iter_objects(), desc="Downloading Neo4j data", unit="file"):
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
            except ClientError as err:  # pragma: no cover - network interaction
                raise RuntimeError(
                    f"Failed to download s3://{self.bucket}/{key}: {err}"
                ) from err

        if not objects_found:
            raise RuntimeError(
                f"No objects found in s3://{self.bucket}/{self.prefix or ''}"
            )

        if downloaded == 0:
            print("[S3] All files already exist locally.")
        else:
            print(f"[S3] Downloaded {downloaded} files.")

    def _iter_objects(self) -> Iterator[dict]:
        paginator = self.s3.get_paginator("list_objects_v2")
        pagination_config = {"PageSize": 50}
        params = {"Bucket": self.bucket}
        if self.prefix:
            params["Prefix"] = self.prefix

        try:
            for page in paginator.paginate(**params, PaginationConfig=pagination_config):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith("/"):
                        continue
                    yield obj
        except ClientError as err:  # pragma: no cover - network interaction
            raise RuntimeError(
                f"Failed to list objects for s3://{self.bucket}/{self.prefix or ''}: {err}"
            ) from err

    def _relative_path(self, key: str) -> str:
        if self.prefix and key.startswith(self.prefix):
            return key[len(self.prefix) :]
        return key

    def _should_skip(self, dest_path: str, expected_size: Optional[int]) -> bool:
        if not self.skip_existing or not os.path.exists(dest_path):
            return False
        if expected_size is None:
            return True
        try:
            return os.path.getsize(dest_path) == expected_size
        except OSError:
            return False


class PaperLoader:
    """Neo4j 적재/연결 로더 (paper_loader_v2 내용을 내장)."""

    def __init__(self, uri: str, user: str, password: str):
        self.connector = Neo4jConnector(uri, user, password)

    def _run(self, query: str, desc: str = ""):
        if desc:
            pass
        self.connector.execute_query(query)

    def clear_graph(self):
        labels_to_clear = [
            "Article",
            "Section",
            "Chunk",
            "Reference",
            "CitedWork",
            "Entity",
            "Mention",
            "Topic",
            "Domain",
            "Journal",
            "StudyDesign",
            "Experiment",
            "CategoryParent",
            "CategoryLeaf",
            "ExpMaterial",
            "ExpEquipment",
            "Material",
            "Equipment",
            "Protocol",
            "ProtocolChunk",
            "ProtocolReference",
            "ClinicalTrial",
        ]

        print("[CLEAR] Start clearing graph (excluding BaseNode)...")
        for label in tqdm(labels_to_clear, desc="Clearing Labels"):
            q = f"""
            CALL apoc.periodic.iterate(
              "MATCH (n:{label}) RETURN n",
              "DETACH DELETE n",
              {{batchSize: 5000, parallel: true}}
            )
            """
            self._run(q, desc=f"[CLEAR] :{label}")

        cleanup_rels = [
            (
                """
                MATCH (p:Protocol)-[r:HAS_CHUNK]->(n)
                WHERE n:Chunk OR n.chunk_id IS NOT NULL
                DELETE r
                RETURN count(r) AS removed
                """,
                "cleanup Protocol-[:HAS_CHUNK]->Chunk",
            ),
            (
                """
                MATCH (s:Section)-[r:HAS_CHUNK]->(n)
                WHERE n:ProtocolChunk OR n.chunking_id IS NOT NULL
                DELETE r
                RETURN count(r) AS removed
                """,
                "cleanup Section-[:HAS_CHUNK]->ProtocolChunk",
            ),
        ]
        for q, d in cleanup_rels:
            self._run(q, desc=d)

    def load(self, clear: bool = False):
        if clear:
            self.clear_graph()

        paper_indices = []
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_CONSTRAINTS", []))
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_INDEXES", []))
        paper_indices.extend(getattr(PaperRAGQueries, "CREATE_VECTOR_INDEX", []))

        protocol_indices = []
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_CONSTRAINTS", []))
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_INDEXES", []))
        protocol_indices.extend(getattr(ProtocolQueries, "CREATE_VECTOR_INDEX", []))

        clinical_indices = []
        clinical_indices.extend(getattr(ClinicalTrialQueries, "CREATE_CONSTRAINTS", []))
        clinical_indices.extend(getattr(ClinicalTrialQueries, "CREATE_INDEXES", []))

        tasks = [
            ("1. [Paper] 제약조건/인덱스 생성", paper_indices),
            ("2. [Paper] Article 로딩", PaperRAGQueries.LOAD_ARTICLES),
            (
                "3. [Paper] Figure/Table/Equation 메타 로딩",
                [
                    PaperRAGQueries.LOAD_FIGURES,
                    PaperRAGQueries.LOAD_TABLES,
                    PaperRAGQueries.LOAD_EQUATIONS,
                ],
            ),
            (
                "4. [Paper] Section/Chunk 로딩",
                [
                    PaperRAGQueries.LOAD_SECTIONS,
                    PaperRAGQueries.LOAD_CHUNKS,
                ],
            ),
            ("5. [Paper] Chunk NEXT 연결", PaperRAGQueries.LINK_CHUNKS_NEXT),
            ("6. [Paper] References 로딩", PaperRAGQueries.LOAD_REFERENCES),
            (
                "7. [Paper] Experiments(+ExpMaterial/ExpEquipment) 로딩",
                PaperRAGQueries.LOAD_EXPERIMENTS,
            ),
            ("8. [Paper] Entities 로딩(entity_id 기반)", PaperRAGQueries.LOAD_ENTITIES),
            ("9-1. [Paper] Mentions 노드 생성 (집계 제외)", PaperRAGQueries.LOAD_MENTIONS_FAST),
            ("9-2. [Paper] Mentions-Section 연결", PaperRAGQueries.LINK_MENTIONS_TO_SECTIONS),
            ("9-3. [Paper] Article-Entity 집계 계산", PaperRAGQueries.CALC_ARTICLE_ENTITY_AGGREGATION),
            ("12. [Protocol] 제약조건/인덱스 생성", protocol_indices),
            ("13. [Protocol] 메타데이터 로딩", ProtocolQueries.LOAD_PROTOCOL_METADATA),
            ("15. [Protocol] Chunk/임베딩 로딩", ProtocolQueries.LOAD_PROTOCOL_CHUNKS),
            (
                "16. [Migration] Experiment: CategoryLeaf -> Entity(Method)",
                PaperRAGQueries.query_exp_migration,
            ),
            (
                "17. [Migration] Protocol: CategoryLeaf -> Entity(Method)",
                ProtocolQueries.query_proto_migration,
            ),
            ("10. [Paper] PrimeKG 1차(name) 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG),
            ("11. [Paper] PrimeKG 2차(primekg_label) 연결", PaperRAGQueries.CONNECT_TO_PRIMEKG_SECONDARY),
            ("18. [ClinicalTrial] 제약조건/인덱스 생성", clinical_indices),
            ("19. [ClinicalTrial] 메타데이터 로딩", ClinicalTrialQueries.LOAD_METADATA),
            ("20. [ClinicalTrial] Trial용 Mention 생성 및 연결", ClinicalTrialQueries.LOAD_TRIAL_MENTIONS),
            ("21. [ClinicalTrial] (mention 기반) Trial -> Entity 집계", ClinicalTrialQueries.LINK_TRIAL_ENTITIES_FROM_MENTIONS),
            (
                "99. [Cleanup] 구버전(CategoryLeaf) 연결 삭제 및 고아 노드 정리",
                [
                    "MATCH (:Experiment)-[r:HAS_LEAF_CATEGORY]->() DELETE r",
                    "MATCH (:Protocol)-[r:HAS_LEAF_CATEGORY]->() DELETE r",
                    "MATCH (n:CategoryLeaf) WHERE NOT (n)--() DELETE n",
                ],
            ),
        ]

        for desc, q in tqdm(tasks, desc="Neo4j Full Loading & Migration"):
            if isinstance(q, list):
                for sub_q in q:
                    self._run(sub_q, desc=desc)
            else:
                self._run(q, desc=desc)


class PaperLoaderS3(PaperLoader):
    """PaperLoader wrapper that ensures data is synced from S3 first."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        bucket: str,
        prefix: str,
        import_dir: str,
    ):
        super().__init__(uri, user, password)
        self.syncer = Neo4jS3Syncer(bucket, prefix, import_dir)

    def load_with_data(self, clear: bool = True, download: bool = True) -> None:
        if download:
            self.syncer.sync()
        super().load(clear=clear)


def _env_bool(name: str, default: bool) -> bool:
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
        return None


if __name__ == "__main__":
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
                raise RuntimeError("Neo4j 비밀번호를 가져올 수 없습니다.")
            else:
                # 로컬 환경에서는 기본값 사용
                PASSWORD = "neo4jpass"
                print("ℹ️  환경 변수 NEO4J_PASSWORD가 설정되지 않았습니다. 기본값을 사용합니다.")

    S3_BUCKET = os.getenv("NEO4J_S3_BUCKET", DEFAULT_S3_BUCKET)
    S3_PREFIX = os.getenv("NEO4J_S3_PREFIX", DEFAULT_S3_PREFIX)
    IMPORT_DIR = os.getenv("NEO4J_IMPORT_DIR", DEFAULT_IMPORT_DIR)

    CLEAR_GRAPH = _env_bool("NEO4J_CLEAR", True)
    DOWNLOAD_DATA = _env_bool("NEO4J_DOWNLOAD", True)

    loader = PaperLoaderS3(URI, USER, PASSWORD, S3_BUCKET, S3_PREFIX, IMPORT_DIR)

    if loader.connector.test_connection():
        print("🚀 [Full Load & Migration] S3 동기화 후 데이터 적재를 시작합니다.")
        loader.load_with_data(clear=CLEAR_GRAPH, download=DOWNLOAD_DATA)
    else:
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
        raise RuntimeError("Neo4j 연결에 실패했습니다. 환경 변수를 확인하세요.")
