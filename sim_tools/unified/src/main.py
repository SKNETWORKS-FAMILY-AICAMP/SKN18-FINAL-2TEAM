import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("[main.py] CMD:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def ensure_af_symlinks(af_dir: Path) -> None:
    af_dir.mkdir(parents=True, exist_ok=True)

    def ln(src: str, dst: str) -> None:
        src_p = af_dir / src
        dst_p = af_dir / dst
        if src_p.exists():
            if dst_p.exists() or dst_p.is_symlink():
                dst_p.unlink()
            dst_p.symlink_to(src_p.name)

    for i in range(1, 6):
        ln(f"params_model_{i}_ptm.npz", f"model_{i}_ptm.npz")
        ln(f"params_model_{i}.npz", f"model_{i}.npz")
        ln(f"params_model_{i}_multimer_v3.npz", f"model_{i}_multimer_v3.npz")


def resolve_rfdiffusion_entry() -> str:
    env_entry = os.environ.get("RFDIFFUSION_ENTRY")
    if env_entry:
        p = Path(env_entry)
        if p.is_file():
            return str(p)

    def try_dir(d: str) -> str | None:
        base = Path(d)
        for sub in ["run_inference.py", "scripts/run_inference.py"]:
            cand = base / sub
            if cand.is_file():
                return str(cand)
        return None

    env_dir = os.environ.get("RFDIFFUSION_DIR")
    if env_dir:
        hit = try_dir(env_dir)
        if hit:
            return hit

    common_dirs = [
        "/app/RFdiffusion",
        "/workspace/RFdiffusion",
        "/workspace/unified/RFdiffusion",
        "/app/unified/RFdiffusion",
    ]
    for d in common_dirs:
        hit = try_dir(d)
        if hit:
            return hit

    for root in [Path("/app"), Path("/workspace")]:
        if not root.exists():
            continue
        for p in root.rglob("run_inference.py"):
            if p.is_file():
                return str(p)

    raise FileNotFoundError(
        "Cannot find RFdiffusion run_inference.py. "
        "Set RFDIFFUSION_ENTRY=/path/to/run_inference.py "
        "or RFDIFFUSION_DIR=/path/to/RFdiffusion"
    )


def download_ckpt_if_missing(ckpt_path: Path) -> None:
    """
    Safety net: If Base_ckpt.pt is missing, create directory and download it.
    (Normally download_params.sh already did this.)
    """
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    if ckpt_path.exists():
        return

    url = "http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt"
    print(f"[main.py] CKPT missing. Downloading -> {ckpt_path}", flush=True)
    run(["wget", "-O", str(ckpt_path), url])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument("--mode", choices=["backbone", "designability", "full"], required=True)
    p.add_argument("--name", default="job")

    p.add_argument("--contigs", required=True, help='e.g. "100" or "A1-50/0 B1-50/0"')
    p.add_argument("--iterations", type=int, default=50)
    p.add_argument("--num_designs", type=int, default=1)

    p.add_argument("--copies", type=int, default=1)
    p.add_argument("--num_seqs", type=int, default=4)
    p.add_argument("--num_recycles", type=int, default=3)
    p.add_argument("--rm_aa", default="C")
    p.add_argument("--mpnn_sampling_temp", type=float, default=0.1)

    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))

    p.add_argument(
        "--rfdiffusion_entry",
        default=resolve_rfdiffusion_entry(),
        help="Path to RFdiffusion run_inference.py (auto-detected if not provided)",
    )

    p.add_argument("--torch_py", default=os.environ.get("TORCH_PY", "/opt/venv_torch/bin/python"))
    p.add_argument("--jax_py", default=os.environ.get("JAX_PY", "/opt/venv_jax/bin/python"))

    # ✅ ckpt path: run.sh에서 export RFD_CKPT로 박아둔 값 우선
    p.add_argument(
        "--rfd_ckpt",
        default=os.environ.get("RFD_CKPT", "/app/RFdiffusion/models/Base_ckpt.pt"),
        help="RFdiffusion checkpoint path",
    )

    return p.parse_args()


def main() -> None:
    o = parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    outputs_dir = Path(o.outputs_dir)
    job_dir = outputs_dir / f"{o.name}_{ts}"
    job_dir.mkdir(parents=True, exist_ok=True)

    models_dir = Path(o.models_dir)
    af_dir = models_dir / "alphafold"
    ensure_af_symlinks(af_dir)

    contigs = o.contigs.strip()
    if contigs.isdigit():
        contig_arg = f"[{contigs}-{contigs}]"
        contig_for_designability = f"{contigs}-{contigs}"
    else:
        contig_arg = f"[{contigs}]"
        contig_for_designability = contigs

    out_prefix = str(job_dir / "backbone")

    entry = Path(o.rfdiffusion_entry)
    if not entry.is_file():
        raise FileNotFoundError(f"RFdiffusion entry not found: {entry}")
    print(f"[main.py] RFdiffusion entry: {entry}", flush=True)

    ckpt = Path(o.rfd_ckpt)
    download_ckpt_if_missing(ckpt)
    if not ckpt.is_file():
        raise FileNotFoundError(f"RFdiffusion ckpt not found: {ckpt}")
    print(f"[main.py] RFdiffusion ckpt: {ckpt}", flush=True)

    if o.mode in ("backbone", "full"):
        run([
            o.torch_py,
            str(entry),
            f"inference.output_prefix={out_prefix}",
            f"inference.num_designs={o.num_designs}",
            f"diffuser.T={o.iterations}",
            f"contigmap.contigs={contig_arg}",
            # ✅ Hydra struct 에러 해결: "없는 키"는 +로 추가
            f"+inference.ckpt_path={ckpt}",
            "+inference.dump_pdb=True",
            "+inference.dump_pdb_path=/dev/shm",
        ])
        print(f"[main.py] RFdiffusion done: {out_prefix}_0.pdb", flush=True)

    if o.mode in ("designability", "full"):
        pdb_path = job_dir / "backbone_0.pdb"
        if not pdb_path.exists():
            raise FileNotFoundError(f"Missing backbone pdb: {pdb_path}")

        run([
            o.jax_py, "-m", "colabdesign.rf.designability_test",
            f"--pdb={pdb_path}",
            f"--loc={job_dir}",
            f"--contig={contig_for_designability}",
            f"--copies={o.copies}",
            f"--num_seqs={o.num_seqs}",
            f"--num_recycles={o.num_recycles}",
            f"--rm_aa={o.rm_aa}",
            f"--mpnn_sampling_temp={o.mpnn_sampling_temp}",
            "--num_designs=1",
        ])
        print(f"[main.py] designability_test done. job_dir={job_dir}", flush=True)

    print(f"[main.py] DONE. job_dir={job_dir}", flush=True)


if __name__ == "__main__":
    main()