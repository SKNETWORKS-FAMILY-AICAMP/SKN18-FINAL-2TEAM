########################
# RabbitM에서 Producer 역할을 하는 API 서버
# - 단백질 서열을 받아서 RabbitMQ 큐에 작업을 넣는다.
########################
import os
import json
import uuid
import datetime
from flask import Flask, request, jsonify
import pika

##########################
# RabbitMQ 접속 정보
##########################
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")
QUEUE_NAME = os.getenv("QUEUE_NAME", "alphafold_jobs")

app = Flask(__name__)

def publish_to_queue(message: dict) -> None:
    """RabbitMQ 큐에 메시지(JSON)를 넣음"""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(host= RABBITMQ_HOST, credentials=credentials)

    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_NAME, durable=True) # durable=True -> 서버 재시작시에도 큐가 유지됨

    body = json.dumps(message).encode('utf-8')

    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=body,
        properties=pika.BasicProperties(delivery_mode=2), # delivery_mode=2 -> 메시지가 디스크에 저장되어 서버 재시작시에도 유지됨
    )

    connection.close()

@app.get("/health")
def helath():
    return jsonify({"ok": True})

@app.post("/submit")
def submit():
    """
    에제: 단백질 서열(sequence)을 받아서 RabbitMQ 큐에 작업을 넣음
    {
        "sequence": "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD"
    }
    -> AlphaFold는 아직 안 돌리고, worker가 파일을 만들어주는지부터 확인한다.
    """
    data = request.get_json(force=True)
    sequence = (data.get("sequence") or "").strip().upper()

    # 간단한 검증
    valid = set("ACDEFGHIKLMNPQRSTVWY")
    if not sequence or any(c not in valid for c in sequence):
        return jsonify({"ok": False, "error": "Invalid protein sqeuence"}), 400
    
    job_id = f"af_{uuid.uuid4().hex[:10]}"

    msg = {
        "job_id": job_id,
        "sequence": sequence,
        "mode": data.get("mode", "monomer"),
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    publish_to_queue(msg)

    return jsonify({"ok": True, "job_id": job_id}) # API는 job_id(== 접수완료)만 반환

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000) # 컨테이너 안에서 0.0.0.0으로 열어야 외부에 접근 가능함.