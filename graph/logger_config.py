"""
Graph 모듈용 공통 Logger 설정
모든 graph 노드에서 사용할 수 있는 logger를 제공합니다.

AWS 배포 환경 고려사항:
- docker-compose.prod.yml에서 CloudWatch Logs (awslogs driver) 사용
- 프로덕션에서는 콘솔 로깅만 사용 (CloudWatch가 자동 수집)
- 로컬 개발 환경에서는 파일 로깅도 사용 가능
- 환경변수 GRAPH_LOG_TO_FILE=true로 파일 로깅 활성화 가능
"""
import logging
import logging.handlers
import os
import warnings
from pathlib import Path

# 로그 레벨 설정 (환경변수로 제어 가능)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()

# 파일 로깅 활성화 여부 (기본값: False, AWS 프로덕션 환경에서는 콘솔만 사용)
LOG_TO_FILE = os.getenv("GRAPH_LOG_TO_FILE", "false").lower() == "true"

# 로그 디렉토리 설정 (파일 로깅이 활성화된 경우에만 사용)
LOG_DIR = None
if LOG_TO_FILE:
    LOG_DIR = Path(__file__).parent.parent / "logs"
    # 로그 디렉토리 생성 (예외 처리 포함)
    try:
        LOG_DIR.mkdir(exist_ok=True)
    except (OSError, PermissionError) as e:
        # AWS 컨테이너 환경에서 권한 문제 시 파일 로깅 비활성화
        warnings.warn(f"로그 디렉토리 생성 실패: {e}. 파일 로깅을 비활성화합니다.")
        LOG_TO_FILE = False
        LOG_DIR = None

# 로그 포맷 설정
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "graph", level: str = None) -> logging.Logger:
    """
    Logger를 설정하고 반환합니다.
    
    Args:
        name: Logger 이름 (기본값: "graph")
        level: 로그 레벨 (기본값: 환경변수 LOG_LEVEL 또는 INFO)
    
    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 설정되어 있으면 재설정하지 않음
    if logger.handlers:
        return logger
    
    # 로그 레벨 설정
    log_level = level or LOG_LEVEL
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # 핸들러 생성
    handlers = []
    
    # 콘솔 핸들러 (항상 사용 - CloudWatch가 자동 수집)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    console_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)
    
    # 파일 핸들러 (환경변수로 활성화된 경우에만 사용)
    if LOG_TO_FILE and LOG_DIR is not None:
        try:
            log_file = LOG_DIR / f"{name}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_level, logging.INFO))
            file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
            file_handler.setFormatter(file_formatter)
            handlers.append(file_handler)
        except (OSError, PermissionError) as e:
            # 파일 핸들러 생성 실패 시 경고만 출력하고 계속 진행
            warnings.warn(f"파일 핸들러 생성 실패: {e}. 콘솔 로깅만 사용합니다.")
    
    # 핸들러 추가
    for handler in handlers:
        logger.addHandler(handler)
    
    logger.propagate = False
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Logger를 가져오거나 생성합니다.
    
    Args:
        name: Logger 이름 (기본값: None, 호출한 모듈의 이름 사용)
    
    Returns:
        Logger 인스턴스
    """
    if name is None:
        # 호출한 모듈의 이름을 자동으로 감지
        import inspect
        frame = inspect.currentframe().f_back
        module_name = frame.f_globals.get('__name__', 'graph')
        name = module_name
    
    logger = logging.getLogger(name)
    
    # 핸들러가 없으면 설정
    if not logger.handlers:
        setup_logger(name)
    
    return logger

