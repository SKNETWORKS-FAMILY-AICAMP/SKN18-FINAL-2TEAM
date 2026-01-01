#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional


def resolve_rfdiffusion_entry() -> str:
    env_entry = os.environ.get("RFDIFFUSION_ENTRY")
    if env_entry and Path(env_entry).is_file():
        return str(Path(env_entry))

    candidates = [
        Path("/app/RFdiffusion/run_inference.py"),
        Path("/workspace/RFdiffusion/run_inference.py"),
        Path(__file__).resolve().parent / "RFdiffusion" / "run_inference.py",
        Path("/app/RFdiffusion/scripts/run_inference.py"),
    ]

    rfd_dir = os.environ.get("RFDIFFUSION_DIR")
    if rfd_dir:
        candidates.append(Path(rfd_dir) / "run_inference.py")
        candidates.append(Path(rfd_dir) / "scripts" / "run_inference.py")

    for c in candidates:
        if c.is_file():
            return str(c)

    for base in [Path("/app"), Path("/workspace"), Path(__file__).resolve().parent]:
        try:
            for p in base.rglob("run_inference.py"):
                if "RFdiffusion" in str(p):
                    return str(p)
        except Exception:
            pass

    raise FileNotFoundError("Cannot find RFdiffusion run_inference.py")


def pick_python() -> str:
    torch_venv = os.environ.get("TORCH_VENV")
    if torch_venv:
        cand = Path(torch_venv) / "bin" / "python"
        if cand.exists():
            return str(cand)
    return sys.executable


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument("--mode", default="backbone", choices=["backbone", "binder", "other"])
    p.add_argument("--name", default="test_rfd")
    p.add_argument(
        "--contigs",
        default="100",
        help="RFdiffusion contig string, e.g. 100 or 'A1-100' or 'A1-50 0 A51-100'",
    )
    p.add_argument("--iterations", type=int, default=50, help="num designs")

    # (선택) 기존 출력 있으면 스킵하는 cautious 모드 강제
    p.add_argument("--cautious", action="store_true", help="Set inference.cautious=True (skip existing outputs)")

    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))
    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))

    # ✅ S3 업로드 옵션
    p.add_argument("--s3_bucket", default=os.environ.get("S3_BUCKET", ""), help="If set, upload outputs to S3")
    p.add_argument("--s3_prefix", default=os.environ.get("S3_PREFIX", "rfdiffusion"))
    p.add_argument("--s3_upload_logs", action="store_true", help="Also upload job log if exists")

    # 업로드 실패를 job 실패로 볼지 여부(기본: 업로드 실패해도 run 자체는 성공으로 유지)
    p.add_argument("--fail_on_s3_error", action="store_true", help="If upload fails, exit non-zero")

    return p.parse_args()


def run_cmd(cmd, env=None):
    print("[main.py] exec:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def guess_job_log_path(outputs_dir: Path, job_name: str) -> Path:
    # unified 쪽 convention: outputs/_logs/{job_name}.log
    return outputs_dir / "_logs" / f"{job_name}.log"


def s3_upload_files(
    files: List[Path],
    bucket: str,
    prefix: str,
    job_name: str,
    region: Optional[str] = None,
) -> List[str]:
    """
    Upload files to: s3://{bucket}/{prefix}/{job_name}/{filename}
    Return list of s3:// urls.
    """
    import boto3

    region_name = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    s3 = boto3.client("s3", region_name=region_name)

    uploaded = []
    for f in files:
        if not f.exists() or f.stat().st_size <= 0:
            continue
        key = f"{prefix.rstrip('/')}/{job_name}/{f.name}"
        print(f"[s3] upload: {f} -> s3://{bucket}/{key}")
        s3.upload_file(str(f), bucket, key)
        uploaded.append(f"s3://{bucket}/{key}")
    return uploaded


def main():
    args = parse_args()

    outputs_dir = Path(args.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("DGLBACKEND", "pytorch")
    env.setdefault("DGL_DISABLE_GRAPHBOLT", "1")

    # RFdiffusion expects contigmap.contigs to be LIST[str]
    contig_str = str(args.contigs).strip()
    contig_override = f"contigmap.contigs=[{contig_str!r}]"

    py = pick_python()

    cmd = [
        py,
        args.rfdiffusion_entry,
        f"inference.output_prefix={outputs_dir / args.name}",
        f"inference.num_designs={args.iterations}",
        contig_override,
    ]

    if args.cautious:
        cmd.append("inference.cautious=True")

    # 1) run RFdiffusion (실패하면 여기서 예외로 종료)
    run_cmd(cmd, env=env)

    # 2) 성공했으면 결과물 찾기
    produced = [
        outputs_dir / f"{args.name}_0.pdb",
        outputs_dir / f"{args.name}_0.trb",
    ]

    print("[main.py] produced:")
    for p in produced:
        if p.exists():
            print(" -", p, f"({p.stat().st_size} bytes)")
        else:
            print(" -", p, "(missing)")

    # 3) (옵션) S3 업로드
    bucket = (args.s3_bucket or "").strip()
    if not bucket:
        print("[s3] S3_BUCKET not set; skip upload")
        return

    files_to_upload = list(produced)

    if args.s3_upload_logs:
        log_path = guess_job_log_path(outputs_dir, args.name)
        files_to_upload.append(log_path)

    try:
        uploaded = s3_upload_files(
            files=files_to_upload,
            bucket=bucket,
            prefix=args.s3_prefix,
            job_name=args.name,
        )
        if uploaded:
            print("[s3] uploaded:")
            for u in uploaded:
                print(" -", u)
        else:
            print("[s3] nothing uploaded (no files found?)")
    except Exception as e:
        print("[s3][ERROR]", repr(e))
        if args.fail_on_s3_error:
            raise SystemExit(2)


if __name__ == "__main__":
    main()