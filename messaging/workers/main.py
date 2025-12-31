#!/usr/bin/env python
"""
Worker 메인 진입점 - 시뮬레이션 Consumer 실행
확장 가능한 구조로 향후 다른 Consumer 추가 가능
"""
import multiprocessing
import logging
import sys
import os
import django
from pathlib import Path  

# 프로젝트 루트 기준으로 django_app 추가
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../SKN18-FINAL-2TEAM
DJANGO_APP_DIR = PROJECT_ROOT / "django_app"
if str(DJANGO_APP_DIR) not in sys.path:
    sys.path.insert(0, str(DJANGO_APP_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_simulation_consumers():
    """시뮬레이션 Consumer들을 별도 프로세스로 실행"""
    from messaging.consumers.simulation_consumer import start_simulation_consumer
    
    tools = ["alphafold3", "protein_mpnn", "rfdiffusion"]
    processes = []
    
    for tool_name in tools:
        p = multiprocessing.Process(
            target=start_simulation_consumer,
            args=(tool_name,),
            name=f"sim-{tool_name}"
        )
        p.start()
        processes.append(p)
        logger.info(f"Started {tool_name} consumer (PID: {p.pid})")
    
    # 모든 프로세스 종료 대기
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("Shutting down workers...")
        for p in processes:
            p.terminate()
            p.join()


if __name__ == "__main__":
    logger.info("Starting simulation workers...")
    run_simulation_consumers()

