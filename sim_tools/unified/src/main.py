#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path


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


def _get_s3_bucket_default() -> str:
    """
    Priority:
      1) S3_BUCKET
      2) AWS_S3_BUCKET
    """
    return (os.environ.get("S3_BUCKET") or os.environ.get("AWS_S3_BUCKET") or "").strip()


def _get_s3_prefix_default() -> str:
    """
    Priority:
      1) S3_PREFIX
      2) AWS_S3_BASE_PATH
      3) rfdiffusion
    Normalize: strip leading/trailing slashes.
    """
    raw = os.environ.get("S3_PREFIX") or os.environ.get("AWS_S3_BASE_PATH") or "rfdiffusion"
    return str(raw).strip().strip("/")


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
    p.add_argument("--cautious", action="store_true", help="Set inference.cautious=True (skip existing outputs)")

    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))
    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))

    # ✅ S3 업로드 옵션 (S3_*가 없으면 AWS_S3_* fallback 지원)
    p.add_argument(
        "--s3_bucket",
        default=_get_s3_bucket_default(),
        help="If set, upload outputs to S3",
    )
    p.add_argument(
        "--s3_prefix",
        default=_get_s3_prefix_default(),
        help="S3 key prefix (folder path). Default uses S3_PREFIX or AWS_S3_BASE_PATH or 'rfdiffusion'",
    )
    p.add_argument("--s3_upload_logs", action="store_true", help="Also upload job log if exists")
    p.add_argument("--fail_on_s3_error", action="store_true", help="If upload fails, exit non-zero")

    return p.parse_args()


def run_cmd(cmd, env=None):
    print("[main.py] exec:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def main():
    args = parse_args()

    outputs_dir = Path(args.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("DGLBACKEND", "pytorch")
    env.setdefault("DGL_DISABLE_GRAPHBOLT", "1")

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

    # 1) RFdiffusion 실행
    run_cmd(cmd, env=env)

    # 2) 생성물 확인
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
        print("[s3] S3_BUCKET/AWS_S3_BUCKET not set; skip upload")
        return

    prefix = (args.s3_prefix or "rfdiffusion").strip().strip("/")
    print(f"[s3] bucket={bucket} prefix={prefix}")

    try:
        from s3_uploader import upload_job_outputs
    except Exception as e:
        print("[s3][ERROR] cannot import s3_uploader:", repr(e))
        if args.fail_on_s3_error:
            raise SystemExit(2)
        return

    try:
        uploaded = upload_job_outputs(
            outputs_dir=str(outputs_dir),
            job_name=args.name,
            bucket=bucket,
            prefix=prefix,
            upload_logs=args.s3_upload_logs,
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