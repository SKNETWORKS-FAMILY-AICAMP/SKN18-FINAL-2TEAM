import os
from pathlib import Path
import boto3

def upload_file_to_s3(local_path: str, bucket: str, key: str, content_type: str | None = None) -> str:
    """
    Upload a single file to S3 and return s3:// URL.
    Requires AWS creds in env or shared config.
    """
    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION"))
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    s3.upload_file(local_path, bucket, key, ExtraArgs=extra_args or None)
    return f"s3://{bucket}/{key}"

def upload_job_outputs(outputs_dir: str, job_name: str, bucket: str, prefix: str = "rfdiffusion") -> list[str]:
    """
    Upload {job_name}_0.pdb and {job_name}_0.trb (if exist) to:
      s3://{bucket}/{prefix}/{job_name}/...
    """
    out = Path(outputs_dir)
    candidates = [
        out / f"{job_name}_0.pdb",
        out / f"{job_name}_0.trb",
    ]

    uploaded = []
    for p in candidates:
        if not p.exists():
            continue
        key = f"{prefix}/{job_name}/{p.name}"
        content_type = "chemical/x-pdb" if p.suffix == ".pdb" else "application/octet-stream"
        uploaded.append(upload_file_to_s3(str(p), bucket, key, content_type=content_type))
    return uploaded