import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("[main.py] CMD:", " ".join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True)


def resolve_rfdiffusion_entry() -> str:
    # 1) env override
    env_entry = os.environ.get("RFDIFFUSION_ENTRY")
    if env_entry and Path(env_entry).is_file():
        return env_entry

    # 2) common locations
    base_dirs = [
        os.environ.get("RFDIFFUSION_DIR", ""),
        "/app/RFdiffusion",
        "/workspace/RFdiffusion",
        "/workspace/unified/RFdiffusion",
    ]
    candidates = ["scripts/run_inference.py", "run_inference.py"]

    for d in [x for x in base_dirs if x]:
        base = Path(d)
        for sub in candidates:
            p = base / sub
            if p.is_file():
                return str(p)

    raise FileNotFoundError("Cannot find RFdiffusion run_inference.py. Check /app/RFdiffusion clone.")


def download_ckpt_if_missing(ckpt_path: Path) -> None:
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    if ckpt_path.exists():
        return
    url = "http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt"
    print(f"[main.py] CKPT missing. Downloading -> {ckpt_path}", flush=True)
    run(["wget", "-O", str(ckpt_path), url])


def contig_args(contigs: str) -> str:
    contigs = contigs.strip()
    if not contigs:
        raise ValueError("contigs is empty")
    if contigs.isdigit():
        return f"[{contigs}-{contigs}]"
    return f"[{contigs}]"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["backbone"], default="backbone")
    p.add_argument("--name", default="job")
    p.add_argument("--contigs", required=True, help='e.g. "100" or "A1-50/0 B1-50/0"')
    p.add_argument("--iterations", type=int, default=50)
    p.add_argument("--num_designs", type=int, default=1)

    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))

    p.add_argument("--torch_py", default=os.environ.get("TORCH_PY", "/opt/venv_torch/bin/python"))
    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--rfd_ckpt", default=os.environ.get("RFD_CKPT", "/app/RFdiffusion/models/Base_ckpt.pt"))
    return p.parse_args()


def run_rfd(o: argparse.Namespace, job_dir: Path) -> Path:
    contig_arg = contig_args(o.contigs)
    out_prefix = str(job_dir / "backbone")

    entry = Path(o.rfdiffusion_entry)
    if not entry.is_file():
        raise FileNotFoundError(f"RFdiffusion entry not found: {entry}")

    ckpt = Path(o.rfd_ckpt)
    download_ckpt_if_missing(ckpt)
    if not ckpt.is_file():
        raise FileNotFoundError(f"RFdiffusion ckpt not found: {ckpt}")

    print(f"[main.py] RFdiffusion entry: {entry}", flush=True)
    print(f"[main.py] RFdiffusion ckpt: {ckpt}", flush=True)

    run([
        o.torch_py,
        str(entry),
        f"inference.output_prefix={out_prefix}",
        f"inference.num_designs={o.num_designs}",
        f"diffuser.T={o.iterations}",
        f"contigmap.contigs={contig_arg}",
        f"+inference.ckpt_path={ckpt}",
        "+inference.dump_pdb=True",
        "+inference.dump_pdb_path=/dev/shm",
    ])

    pdb = job_dir / "backbone_0.pdb"
    print(f"[main.py] RFdiffusion done: {pdb}", flush=True)
    return pdb


def main() -> None:
    o = parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = Path(o.outputs_dir) / f"{o.name}_{ts}"
    job_dir.mkdir(parents=True, exist_ok=True)

    run_rfd(o, job_dir)
    print(f"[main.py] DONE. job_dir={job_dir}", flush=True)


if __name__ == "__main__":
    main()