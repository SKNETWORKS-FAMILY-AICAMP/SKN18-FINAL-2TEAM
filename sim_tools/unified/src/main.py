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


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument("--mode", default="backbone", choices=["backbone", "binder", "other"])
    p.add_argument("--name", default="test_rfd")
    p.add_argument(
        "--contigs",
        default="100",
        help="RFdiffusion contig string, e.g. 100 or 'A1-100' or 'A1-50 0 A51-100'"
    )
    p.add_argument("--iterations", type=int, default=50, help="num designs")

    # (선택) 기존 출력 있으면 스킵하는 cautious 모드 강제
    p.add_argument("--cautious", action="store_true", help="Set inference.cautious=True (skip existing outputs)")

    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))
    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))

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

    # RFdiffusion expects contigmap.contigs to be LIST[str]
    # safest: python repr -> 제대로 escaping된 문자열이 들어감
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

    run_cmd(cmd, env=env)


if __name__ == "__main__":
    main()