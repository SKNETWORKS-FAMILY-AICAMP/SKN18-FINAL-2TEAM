import os
from pathlib import Path
import boto3


def _region() -> str | None:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")


def upload_file_to_s3(local_path: str, bucket: str, key: str, content_type: str | None = None) -> str:
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
    prefix: str,
    upload_logs: bool = False
) -> list[str]:
    """
    Upload to:
      s3://{bucket}/{prefix}/(files...)

    prefix 예:
      simulations/dt=YYYY-MM-DD/pipeline=EXPERIMENT_ID/step=rfdiffusion
    """
    out = Path(outputs_dir)

    candidates = [
        out / f"{job_name}_0.pdb",
        out / f"{job_name}_0.trb",
    ]

    if upload_logs:
        candidates.append(out / "_logs" / f"{job_name}.log")

    prefix = (prefix or "").strip().strip("/")
    if not prefix:
        raise ValueError("prefix is required")

    uploaded: list[str] = []
    for p in candidates:
        if not p.exists() or p.stat().st_size <= 0:
            continue

        key = f"{prefix}/{p.name}"
        content_type = "chemical/x-pdb" if p.suffix == ".pdb" else "application/octet-stream"
        uploaded.append(upload_file_to_s3(str(p), bucket, key, content_type=content_type))

    return uploaded