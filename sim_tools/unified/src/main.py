#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from steps.rfdiffusion_step import run_rfdiffusion_step
from datetime import datetime, timezone, timedelta


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
    return (os.environ.get("S3_BUCKET") or os.environ.get("AWS_S3_BUCKET") or "").strip()


def _get_s3_base_default() -> str:
    return (os.environ.get("S3_BASE") or "simulations").strip().strip("/")


def _kst_today() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).strftime("%Y-%m-%d")


def build_s3_prefix(base: str, dt: str, experiment_id: str, step: str) -> str:
    base = (base or "simulations").strip().strip("/")
    dt = dt.strip()
    experiment_id = experiment_id.strip()
    step = step.strip()
    return f"{base}/dt={dt}/pipeline={experiment_id}/step={step}"


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument("--mode", default="backbone", choices=["backbone", "binder", "other"])

    # ⚠️ 여전히 받을 수는 있지만 실제로는 experiment_id로 덮어씀 (호환용)
    p.add_argument("--name", default="test_job")

    p.add_argument("--contigs", default="100")
    p.add_argument("--iterations", type=int, default=1)
    p.add_argument("--cautious", action="store_true")

    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))
    p.add_argument("--protein_sequence", default="")
    p.add_argument("--af_sequence_only", action="store_true")
    p.add_argument("--experiment_id", required=True)
    p.add_argument(
        "--step",
        required=True,
        choices=["rfdiffusion", "protein_mpnn", "alphafold3"],
    )
    p.add_argument("--num_designs", type=int, default=1)



    # ✅ S3 업로드 옵션 (S3_*가 없으면 AWS_S3_* fallback 지원)
    # S3 업로드 옵션
    p.add_argument("--s3_bucket", default=_get_s3_bucket_default())
    p.add_argument("--s3_base", default=_get_s3_base_default())
    p.add_argument("--s3_upload_logs", action="store_true")
    p.add_argument("--fail_on_s3_error", action="store_true")


    # (옵션) 이후 확장용: MPNN/AF 세부파라미터를 CLI로 받게 하고 싶으면 여기에 추가하면 됨
    return p.parse_args()


def run_cmd(cmd, env=None):
    print("[main.py] exec:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)

def _kst_today() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).strftime("%Y-%m-%d")

def main():
    args = parse_args()

    # experiment_id / name 공통 처리
    exp_id = args.experiment_id.strip()
    args.name = exp_id

    # 🔹 S3와 동일한 루트: .../outputs/simulations/dt=YYYY-MM-DD/pipeline=exp_id
    outputs_root = Path(args.outputs_dir) / "simulations"
    outputs_root.mkdir(parents=True, exist_ok=True)

    dt = _kst_today()
    root = outputs_root / f"dt-{dt}"
    pipeline_dir = root / f"pipeline-{exp_id}"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("DGLBACKEND", "pytorch")
    env.setdefault("DGL_DISABLE_GRAPHBOLT", "1")

    step = args.step


    if step == "rfdiffusion":
            step_dir = pipeline_dir / "step-rfdiffusion"
            step_dir.mkdir(parents=True, exist_ok=True)
            result = run_rfdiffusion_step(
                experiment_id=exp_id,
                outputs_dir=step_dir,
                contigs=args.contigs,
                iterations=args.iterations,
                cautious=args.cautious,
                env=env,
            )
            produced = result["produced"]

    elif step == "protein_mpnn":
        from steps.proteinmpnn_step import MPNNStepConfig, run_mpnn_only
        step_dir = pipeline_dir / "step-proteinMPNN"
        step_dir.mkdir(parents=True, exist_ok=True)

        cfg = MPNNStepConfig(
            experiment_id=exp_id,
            outputs_dir=step_dir,
            contigs=str(args.contigs).strip(),
            num_seqs=int(args.iterations),
            num_designs=int(args.num_designs),
            mpnn_sampling_temp=0.1,
            rm_aa="C",
        )
        result = run_mpnn_only(cfg)
        produced = [
            step_dir / f"{args.name}_mpnn.fasta",
            step_dir / f"{args.name}_mpnn_results.csv",
        ]

    elif step == "alphafold3":
        from steps.alphafold_step import AlphaFoldStepConfig, run_alphafold_only
        step_dir = pipeline_dir / "step-alphafold"
        step_dir.mkdir(parents=True, exist_ok=True)
        max_seqs = int(os.environ.get("AF_MAX_SEQS", "0")) or None
        seq = (args.protein_sequence or "").strip()
        
        cfg = AlphaFoldStepConfig(
                experiment_id=exp_id,
                outputs_dir=step_dir,
                num_recycles=int(args.iterations),
                use_multimer=False,
                initial_guess=False,
                max_seqs=max_seqs,
                protein_sequence=seq if args.af_sequence_only else None,
        )

        # MPNN FASTA 가 있으면 그 서열들을, 없으면 cfg.protein_sequence 하나를 사용
        result = run_alphafold_only(cfg)

        produced = [
            step_dir / f"{args.name}_af_best.pdb",
            step_dir / f"{args.name}_af_results.csv",
        ]

    else:
        raise SystemExit(f"Unknown step: {step}")


    # -----------------------
    # 2) 생성물 확인
    # -----------------------
    print(f"[main.py] step={step} produced:")
    for pth in produced:
        if pth.exists():
            print(" -", pth, f"({pth.stat().st_size} bytes)")
        else:
            print(" -", pth, "(missing)")

    # -----------------------
    # 3) S3 업로드 (옵션)
    # -----------------------
    bucket = (args.s3_bucket or "").strip()
    if not bucket:
        print("[s3] S3_BUCKET/AWS_S3_BUCKET not set; skip upload")
        return

    if step == "protein_mpnn":
        s3_step = "proteinMPNN"
    elif step == "alphafold3":
        s3_step = "alphafold"
    else:
        s3_step = step

    prefix = build_s3_prefix(
        base=args.s3_base,
        dt=dt,
        experiment_id=exp_id,
        step=s3_step,
    )

    print(f"[s3] bucket={bucket}")
    print(f"[s3] prefix={prefix}")

    try:
        from s3_uploader import upload_job_outputs
    except Exception as e:
        print("[s3][ERROR] cannot import s3_uploader:", repr(e))
        if args.fail_on_s3_error:
            raise SystemExit(2)
        return

    try:
        uploaded = upload_job_outputs(
            outputs_dir=str(step_dir),
            job_name=exp_id,
            step=s3_step,
            bucket=bucket,
            prefix="simulations",
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