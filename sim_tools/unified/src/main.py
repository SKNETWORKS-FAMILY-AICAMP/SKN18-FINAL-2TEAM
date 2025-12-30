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

def parse_args():
    p = argparse.ArgumentParser()

    # your original args (examples; adjust to your project)
    p.add_argument("--mode", default="backbone", choices=["backbone", "binder", "other"])
    p.add_argument("--name", default="test")
    p.add_argument("--contigs", default="100")
    p.add_argument("--iterations", type=int, default=50)

    # rf diffusion entry
    # ✅ 변경: 기본값을 여기서 resolve 하지 않음 (repo clone 전에도 argparse가 안 죽게)
    p.add_argument("--rfdiffusion_entry", default=None)

    # base dirs
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))
    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))

    return p.parse_args()

def run_cmd(cmd, env=None):
    print("[main.py] exec:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)

def pick_python() -> str:
    """
    ✅ 변경(추천): venv python을 확실히 사용하도록 고정.
    - TORCH_VENV=/opt/venv_torch 같은 값이 들어오면 그 안의 python 사용
    - 없으면 sys.executable fallback
    """
    torch_venv = os.environ.get("TORCH_VENV")
    if torch_venv:
        cand = Path(torch_venv) / "bin" / "python"
        if cand.is_file():
            return str(cand)

    # fallback (현재 실행중인 python)
    return sys.executable

def main():
    args = parse_args()

    outputs_dir = Path(args.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # environment for rf diffusion
    env = os.environ.copy()
    env.setdefault("DGLBACKEND", "pytorch")
    env.setdefault("DGL_DISABLE_GRAPHBOLT", "1")

    # ✅ 변경: 여기에서 필요할 때만 resolve
    rfd_entry = args.rfdiffusion_entry or resolve_rfdiffusion_entry()

    py = pick_python()

    # Example: call RFdiffusion run_inference.py
    # NOTE: 이 부분은 너희 기존 unified 로직이 있을 거라,
    #       실제 RFdiffusion 인자 매핑은 너희 목적에 맞게 조정 필요.
    cmd = [
        py,  # ✅ venv python
        rfd_entry,
        f"inference.output_prefix={outputs_dir / args.name}",
        f"inference.num_designs={args.iterations}",
        f"contigmap.contigs=[{args.contigs}]",
    ]

    run_cmd(cmd, env=env)

if __name__ == "__main__":
    main()