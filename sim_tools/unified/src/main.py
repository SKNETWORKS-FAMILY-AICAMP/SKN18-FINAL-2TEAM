#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta


def resolve_rfdiffusion_entry() -> str:
    env_entry = os.environ.get("RFDIFFUSION_ENTRY")
    if env_entry and Path(env_entry).is_file():
        return str(Path(env_entry))

    candidates = [
        Path("/app/RFdiffusion/run_inference.py"),
        Path("/workspace/RFdiffusion/run_inference.py"),
        Path("/app/RFdiffusion/scripts/run_inference.py"),
    ]

    rfd_dir = os.environ.get("RFDIFFUSION_DIR")
    if rfd_dir:
        candidates.append(Path(rfd_dir) / "run_inference.py")
        candidates.append(Path(rfd_dir) / "scripts" / "run_inference.py")

    for c in candidates:
        if c.is_file():
            return str(c)

    for base in [Path("/app"), Path("/workspace")]:
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


def build_local_step_dir(outputs_root: Path, dt: str, experiment_id: str, step: str) -> Path:
    return outputs_root / f"dt={dt}" / f"pipeline={experiment_id}" / f"step={step}"


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument("--mode", default="backbone", choices=["backbone", "binder", "other"])
    p.add_argument("--name", default="test_job")  # 호환용(실제로는 experiment_id로 덮어씀)

    p.add_argument("--contigs", default="100")
    p.add_argument("--iterations", type=int, default=1)
    p.add_argument("--cautious", action="store_true")

    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))

    # ✅ 필수: API에서 내려주는 pipeline id
    p.add_argument("--experiment_id", required=True)
    # ✅ step은 unified_shell_script.sh 기준으로 맞춤
    p.add_argument("--step", required=True, choices=["rfdiffusion", "proteinMPNN", "alphafold"])
    # ✅ dt 파티션 (없으면 KST 오늘)
    p.add_argument("--dt", default=_kst_today())

    # ✅ S3 업로드 옵션
    p.add_argument("--s3_bucket", default=_get_s3_bucket_default())
    p.add_argument("--s3_base", default=_get_s3_base_default())
    p.add_argument("--s3_upload_logs", action="store_true")
    p.add_argument("--fail_on_s3_error", action="store_true")

    return p.parse_args()


def run_cmd(cmd, env=None):
    print("[main.py] exec:", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True, env=env)


def _copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main():
    args = parse_args()

    args.experiment_id = args.experiment_id.strip()
    if not args.experiment_id:
        raise SystemExit("experiment_id is required")

    args.name = args.experiment_id  # ✅ 팀장님 지시: job name = experiment_id

    dt = (args.dt or "").strip() or _kst_today()
    step = args.step

    outputs_root = Path(args.outputs_dir)
    outputs_root.mkdir(parents=True, exist_ok=True)

    step_dir = build_local_step_dir(outputs_root, dt, args.experiment_id, step)
    step_dir.mkdir(parents=True, exist_ok=True)

    # 공통 env
    env = os.environ.copy()
    env.setdefault("DGLBACKEND", "pytorch")
    env.setdefault("DGL_DISABLE_GRAPHBOLT", "1")

    print("[main.py] outputs_root :", outputs_root)
    print("[main.py] step_dir     :", step_dir)

    produced = []

    if step == "rfdiffusion":
        contig_str = str(args.contigs).strip()
        contig_override = f"contigmap.contigs=[{contig_str!r}]"

        py = pick_python()
        cmd = [
            py,
            args.rfdiffusion_entry,
            f"inference.output_prefix={step_dir / args.name}",  # ✅ step 폴더로 고정
            f"inference.num_designs={int(args.iterations)}",
            contig_override,
        ]
        if args.cautious:
            cmd.append("inference.cautious=True")

        run_cmd(cmd, env=env)

        produced = [
            step_dir / f"{args.name}_0.pdb",
            step_dir / f"{args.name}_0.trb",
        ]

    elif step == "proteinMPNN":
        # ✅ 기존 proteinmpnn_step.py는 "outputs_dir 안에서 exp_0.pdb"를 찾음
        # => rfdiffusion 결과를 proteinMPNN step 폴더로 복사해서 코드 수정 최소화
        rfd_dir = build_local_step_dir(outputs_root, dt, args.experiment_id, "rfdiffusion")
        _copy_if_exists(rfd_dir / f"{args.name}_0.pdb", step_dir / f"{args.name}_0.pdb")

        from steps.proteinmpnn_step import MPNNStepConfig, run_mpnn_only

        cfg = MPNNStepConfig(
            experiment_id=args.experiment_id,
            outputs_dir=step_dir,                # ✅ step 폴더
            contigs=str(args.contigs).strip(),
            num_seqs=int(args.iterations),
            mpnn_sampling_temp=0.1,
            rm_aa="C",
        )
        result = run_mpnn_only(cfg)
        print("[proteinMPNN] result:", result)

        produced = [
            step_dir / f"{args.name}_mpnn.fasta",
            step_dir / f"{args.name}_mpnn_results.csv",
        ]

    elif step == "alphafold":
        # ✅ 기존 alphafold_step.py는 "outputs_dir 안에서 exp_0.pdb + exp_mpnn.fasta"를 찾음
        # => rfdiffusion pdb + mpnn fasta를 alphafold step 폴더로 복사
        rfd_dir = build_local_step_dir(outputs_root, dt, args.experiment_id, "rfdiffusion")
        mpnn_dir = build_local_step_dir(outputs_root, dt, args.experiment_id, "proteinMPNN")

        _copy_if_exists(rfd_dir / f"{args.name}_0.pdb", step_dir / f"{args.name}_0.pdb")
        _copy_if_exists(mpnn_dir / f"{args.name}_mpnn.fasta", step_dir / f"{args.name}_mpnn.fasta")

        from steps.alphafold_step import AlphaFoldStepConfig, run_alphafold_only

        cfg = AlphaFoldStepConfig(
            experiment_id=args.experiment_id,
            outputs_dir=step_dir,                # ✅ step 폴더
            num_recycles=int(args.iterations),
            use_multimer=False,
            initial_guess=False,
        )
        result = run_alphafold_only(cfg)
        print("[alphafold] result:", result)

        produced = [
            step_dir / f"{args.name}_af_best.pdb",
            step_dir / f"{args.name}_af_results.csv",
        ]

    else:
        raise SystemExit(f"Unknown step: {step}")

    print(f"[main.py] step={step} produced:")
    for pth in produced:
        print(" -", pth, "(ok)" if pth.exists() else "(missing)")

    # -----------------------
    # S3 Upload
    # -----------------------
    bucket = (args.s3_bucket or "").strip()
    if not bucket:
        print("[s3] S3_BUCKET/AWS_S3_BUCKET not set; skip upload")
        return

    prefix = build_s3_prefix(
        base=args.s3_base,
        dt=dt,
        experiment_id=args.experiment_id,
        step=step,
    )

    print(f"[s3] bucket={bucket}")
    print(f"[s3] prefix={prefix}")

    try:
        from s3_uploader import upload_job_outputs
        uploaded = upload_job_outputs(
            outputs_dir=str(step_dir),     # ✅ step_dir만 업로드 => 로컬/S3 구조 자연 정렬
            job_name=args.name,
            step=step,
            bucket=bucket,
            prefix=prefix,
            upload_logs=args.s3_upload_logs,
        )
        print("[s3] uploaded:", uploaded)
    except Exception as e:
        print("[s3][ERROR]", repr(e))
        if args.fail_on_s3_error:
            raise SystemExit(2)


if __name__ == "__main__":
    main()