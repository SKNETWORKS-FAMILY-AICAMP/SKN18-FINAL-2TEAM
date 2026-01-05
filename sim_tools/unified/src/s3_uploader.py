import os
from pathlib import Path
import boto3
from datetime import datetime, timezone, timedelta



def _region() -> str | None:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")


def upload_file_to_s3(local_path: str, bucket: str, key: str, content_type: str | None = None) -> str:
    """
    Upload a single file to S3 and return s3:// URL.
    Requires AWS creds in env or shared config.
    """
    s3 = boto3.client("s3", region_name=_region())

    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    if extra_args:
        s3.upload_file(local_path, bucket, key, ExtraArgs=extra_args)
    else:
        s3.upload_file(local_path, bucket, key)

    return f"s3://{bucket}/{key}"


def upload_job_outputs(
    outputs_dir: str,
    job_name: str,
    bucket: str,
    prefix: str = "rfdiffusion",
    upload_logs: bool = False
) -> list[str]:
    """
    Upload:
      - {job_name}_0.pdb
      - {job_name}_0.trb
      - (optional) _logs/{job_name}.log
    to:
      s3://{bucket}/{prefix}/{job_name}/...
    """
    out = Path(outputs_dir)
    candidates = [
        out / f"{job_name}_0.pdb",
        out / f"{job_name}_0.trb",
    ]

    if upload_logs:
        candidates.append(out / "_logs" / f"{job_name}.log")

    # ✅ prefix 정규화: 앞/뒤 '/' 제거해서 key 깨짐 방지
    # job_name 형식: "<pipeline(실험ID)>__<step(툴이름)>"
    pipeline = job_name
    step = "unknown"
    if "__" in job_name:
        pipeline, step = job_name.split("__", 1)
    KST = timezone(timedelta(hours=9))
    # dt=YYYY-MM-DD
    dt = datetime.now(KST).date().strftime("%Y-%m-%d")

    # 최종 prefix: simulations/dt=2026-01-03/pipeline=26/step=rfdiffusion
    base_prefix = f"{prefix}/dt={dt}/pipeline={pipeline}/step={step}".strip("/")

    uploaded: list[str] = []
    for p in candidates:
        if not p.exists() or p.stat().st_size <= 0:
            continue

        key = f"{base_prefix}/{p.name}"
        content_type = "chemical/x-pdb" if p.suffix == ".pdb" else "application/octet-stream"
        uploaded.append(upload_file_to_s3(str(p), bucket, key, content_type=content_type))

    return uploaded