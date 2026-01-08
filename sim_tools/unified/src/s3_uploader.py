import os
from pathlib import Path
import boto3
import zipfile
from datetime import datetime, timezone, timedelta



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


def _zip_dir(src_dir: Path, zip_path: Path) -> Path | None:
    if not src_dir.exists() or not src_dir.is_dir():
        return None

    files = [p for p in src_dir.rglob("*") if p.is_file()]
    if not files:
        return None

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=str(f.relative_to(src_dir)))
    return zip_path if zip_path.exists() and zip_path.stat().st_size > 0 else None


def upload_job_outputs(
    outputs_dir: str,
    job_name: str,
    step: str,
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
    step = (step or "").strip()

    candidates: list[Path] = []

    if step == "rfdiffusion":
        pdb_files = sorted(out.glob(f"{job_name}_*.pdb"))
        trb_files = sorted(out.glob(f"{job_name}_*.trb"))
        candidates += pdb_files + trb_files

        # PDB + TRB 전체를 합친 ZIP도 함께 업로드
        all_files = [*pdb_files, *trb_files]
        if all_files:
            zip_path = out / f"{job_name}_all_results.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for f in all_files:
                    if f.exists():
                        zf.write(f, arcname=f.name)
            if zip_path.exists() and zip_path.stat().st_size > 0:
                candidates.append(zip_path)

    elif step == "proteinMPNN":
        candidates += [
            out / f"{job_name}_mpnn.fasta",
            out / f"{job_name}_mpnn_results.csv",
        ]

    elif step == "alphafold":
        # 기본 결과 파일: best PDB + CSV
        candidates += [
            out / f"{job_name}_af_best.pdb",
            out / f"{job_name}_af_results.csv",
        ]

        # all_pdb 폴더가 있으면: 개별 PDB 전부 + ZIP 업로드
        all_dir = out / f"{job_name}_af_all_pdb"
        zip_path = out / f"{job_name}_af_all_pdb.zip"

        if all_dir.exists() and all_dir.is_dir():
            # 폴더 안의 모든 PDB 개별 업로드
            all_pdbs = sorted(all_dir.glob("*.pdb"))
            candidates += all_pdbs

            # 전체를 ZIP 으로도 업로드
            z = _zip_dir(all_dir, zip_path)
            if z is not None:
                candidates.append(z)

    else:
        raise ValueError(f"Unknown step for upload: {step}")

    if upload_logs:
        candidates.append(out / "_logs" / f"{job_name}.log")


    # job_name = experiment_id
    pipeline = job_name
    step_folder = step  # rfdiffusion / proteinMPNN / alphafold

    if "__" in job_name:
        pipeline, step = job_name.split("__", 1)

    KST = timezone(timedelta(hours=9))
    dt = datetime.now(KST).date().strftime("%Y-%m-%d")

    # 최종 prefix: simulations/dt=2026-01-03/pipeline=26/step=rfdiffusion
    base_prefix = f"{prefix}/dt={dt}/pipeline={pipeline}/step={step_folder}".strip("/")
    uploaded: list[str] = []
    for p in candidates:
        if not p.exists() or p.stat().st_size <= 0:
            continue

        key = f"{base_prefix}/{p.name}"
        
        if p.suffix == ".pdb":
            content_type = "chemical/x-pdb"
        elif p.suffix in [".fasta", ".fa"]:
            content_type = "text/plain"
        elif p.suffix == ".csv":
            content_type = "text/csv"
        elif p.suffix == ".zip":
            content_type = "application/zip"
        else:
            content_type = "application/octet-stream"

        uploaded.append(upload_file_to_s3(str(p), bucket, key, content_type=content_type))

    return uploaded
