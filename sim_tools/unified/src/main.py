#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path


def resolve_rfdiffusion_entry() -> str:
    """
    Find RFdiffusion run_inference.py robustly.

    Priority:
    1) ENV: RFDIFFUSION_ENTRY (explicit file path)
    2) Common locations:
       - /app/RFdiffusion/run_inference.py
       - /workspace/RFdiffusion/run_inference.py
       - ./RFdiffusion/run_inference.py (relative to this script)
       - /app/RFdiffusion/scripts/run_inference.py (in case repo changes)
    3) Search under RFDIFFUSION_DIR env if set
    """
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

    # last resort: walk a bit (avoid walking full /)
    for base in [Path("/app"), Path("/workspace"), Path(__file__).resolve().parent]:
        try:
            for p in base.rglob("run_inference.py"):
                if "RFdiffusion" in str(p):
                    return str(p)
        except Exception:
            pass

    raise FileNotFoundError("Cannot find RFdiffusion run_inference.py")


def pick_python() -> str:
    """
    Decide which python to use.

    Priority:
    1) TORCH_VENV/bin/python if TORCH_VENV is set and exists
    2) sys.executable
    """
    torch_venv = os.environ.get("TORCH_VENV")
    if torch_venv:
        cand = Path(torch_venv) / "bin" / "python"
        if cand.exists():
            return str(cand)
    return sys.executable


def parse_args():
    p = argparse.ArgumentParser()

    # unified args
    p.add_argument("--mode", default="backbone", choices=["backbone", "binder", "other"])
    p.add_argument("--name", default="test_rfd")
    p.add_argument("--contigs", default="100", help="RFdiffusion contig string, e.g. 100 or 'A1-100' or 'A1-50 0 A51-100'")
    p.add_argument("--iterations", type=int, default=50, help="num designs")

    # rfdiffusion entry
    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())

    # base dirs
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

    # environment for rf diffusion
    env = os.environ.copy()
    env.setdefault("DGLBACKEND", "pytorch")
    env.setdefault("DGL_DISABLE_GRAPHBOLT", "1")

    # IMPORTANT:
    # RFdiffusion expects contigmap.contigs to be a LIST of STRINGS.
    # If you pass [100] (int), it will crash because it calls .strip() on the first element.
    contig_str = str(args.contigs).strip()
    contig_override = f"contigmap.contigs=['{contig_str}']"

    py = pick_python()

    cmd = [
        py,
        args.rfdiffusion_entry,
        f"inference.output_prefix={outputs_dir / args.name}",
        f"inference.num_designs={args.iterations}",
        contig_override,
    ]

    run_cmd(cmd, env=env)


if __name__ == "__main__":
    main()