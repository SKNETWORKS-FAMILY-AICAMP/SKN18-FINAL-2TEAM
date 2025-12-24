########################
# RabbitMQ에서 Worker 역할
########################
import os
import json
import time
import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")
QUEUE_NAME = os.getenv("QUEUE_NAME", "alphafold_jobs")

RESULTS_DIR = os.getenv("RESULTS_DIR", "/shared/results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def process_job(job_id: str, sequence: str, mode: str) -> None:
    """
    지금은 AlphaFold를 돌리지 않고, 단순히 결과 파일을 생성하는 시뮬레이션만 함
    따라서 지금은 작업이 돌아갔다는 결과 파일만 생성함.
    나중에 여기를 AlphaFold 실행 코드로 대체하면 됨.
    """
    job_dir = os.path.join(RESULTS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    time.sleep(3) # 시뮬레이션 돌아가는 척 하는 시간 잡기

    result_path = os.path.join(job_dir, "result.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(f"job_id={job_id}\n")
        f.write(f"mode={mode}\n")
        f.write(f"sequence_length={len(sequence)}\n")
        f.write("status=MOCK_DONE\n")

def on_message(ch, method, properties, body: bytes):
    payload = json.loads(body.decode("utf-8"))
    job_id = payload["job_id"]
    sequence = payload["sequence"]
    mode = payload.get("mode", 'monomer') # 기본값은 monomer, 차후에 여기 파라미터로 다중체 모드도 받도록 확장

    print(f"[WORKER] received job_id={job_id} len={len(sequence)} mode={mode}")

    try:
        process_job(job_id, sequence, mode) # 성공하면 ack -> queue(큐)에서 메시지 삭제
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[WORKER] done job_id={job_id}")
    except Exception as e:
        print(f"[WORKER] failed job_id={job_id} error={e}") # 실패하면 nack -> queue(큐)에 메시지 다시 넣음
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def connect_with_retry(params, retries=30, delay=2):
    """
    RabbitMQ에 재시도 연결하는 함수.
    최대 30회 재시도, 재시도 간격 2초
    만든 이유: worker가 RabbitMQ보다 먼저 실행되어 연결 실패하는 상황 방지하기 위함.
    """
    for i in range(1, retries + 1):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            print(f"[WORKER] RabbitMQ not ready yet ({i}/{retries}) - retry in {delay}s")
            time.sleep(delay)
    raise RuntimeError("[WORKER] RabbitMQ connection failed after retries")

def main():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)

    connection = connect_with_retry(params) # (바로 연결 → 재시도 연결)
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)

    print("[WORKER] waiting for messages...")
    channel.start_consuming()


if __name__ == "__main__":
    main()