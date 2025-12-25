#!/usr/bin/env python
"""
Worker 메인 진입점 - 시뮬레이션 Consumer 실행
확장 가능한 구조로 향후 다른 Consumer 추가 가능
"""
import multiprocessing
import logging
import sys
import os

# Django 설정 로드 (Consumer에서 Django ORM 사용 시 필요)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

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

