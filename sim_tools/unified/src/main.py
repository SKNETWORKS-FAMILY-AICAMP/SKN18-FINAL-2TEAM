import argparse
import os
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("[main.py] CMD:", " ".join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True)


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
    if env_entry and Path(env_entry).is_file():
        return env_entry

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

    for d in ["/app/RFdiffusion", "/workspace/RFdiffusion", "/workspace/unified/RFdiffusion", "/app/unified/RFdiffusion"]:
        hit = try_dir(d)
        if hit:
            return hit

    raise FileNotFoundError("Cannot find RFdiffusion run_inference.py")


def download_ckpt_if_missing(ckpt_path: Path) -> None:
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    if ckpt_path.exists():
        return
    url = "http://files.ipd.uw.edu/pub/RFdiffusion/6f5902ac237024bdd0c176cb93063dc4/Base_ckpt.pt"
    print(f"[main.py] CKPT missing. Downloading -> {ckpt_path}", flush=True)
    run(["wget", "-O", str(ckpt_path), url])


def contig_args(contigs: str) -> tuple[str, str]:
    contigs = contigs.strip()
    if not contigs:
        raise ValueError("contigs is empty")
    if contigs.isdigit():
        return f"[{contigs}-{contigs}]", f"{contigs}-{contigs}"
    return f"[{contigs}]", contigs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument("--mode", choices=["backbone", "designability", "full"], default="backbone")
    p.add_argument("--name", default="job")

    # RFdiffusion
    p.add_argument("--contigs", required=True, help='e.g. "100" or "A1-50/0 B1-50/0"')
    p.add_argument("--iterations", type=int, default=50)
    p.add_argument("--num_designs", type=int, default=1)

    # designability_test (bundle) opts
    p.add_argument("--copies", type=int, default=1)
    p.add_argument("--num_seqs", type=int, default=4)
    p.add_argument("--num_recycles", type=int, default=3)
    p.add_argument("--rm_aa", default="C")
    p.add_argument("--mpnn_sampling_temp", type=float, default=0.1)
    p.add_argument("--use_multimer", action="store_true")

    # dirs
    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))

    # python
    p.add_argument("--torch_py", default=os.environ.get("TORCH_PY", "/opt/venv_torch/bin/python"))
    p.add_argument("--jax_py", default=os.environ.get("JAX_PY", "/opt/venv_jax/bin/python"))

    # rfd ckpt
    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--rfd_ckpt", default=os.environ.get("RFD_CKPT", "/app/RFdiffusion/models/Base_ckpt.pt"))

    # output persistence / upload
    p.add_argument("--persist_dir", default=os.environ.get("PERSIST_DIR", ""), help="copy job_dir to this dir (optional)")
    p.add_argument("--s3_uri", default=os.environ.get("S3_URI", ""), help="upload tar.gz to s3://bucket/prefix (optional)")
    p.add_argument("--s3_profile", default=os.environ.get("AWS_PROFILE", ""), help="optional AWS profile for aws cli")

    return p.parse_args()


def run_rfd(o: argparse.Namespace, job_dir: Path) -> Path:
    contig_arg, _ = contig_args(o.contigs)
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
    if not pdb.exists():
        raise FileNotFoundError(f"Missing backbone pdb: {pdb}")
    print(f"[main.py] RFdiffusion done: {pdb}", flush=True)
    return pdb


def run_bundle_designability_test(o: argparse.Namespace, job_dir: Path, pdb_path: Path) -> None:
    _, contig_for_designability = contig_args(o.contigs)

    cmd = [
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
    ]
    if o.use_multimer:
        cmd += ["--use_multimer"]

    run(cmd)
    print(f"[main.py] designability_test done. job_dir={job_dir}", flush=True)


def persist_and_upload(o: argparse.Namespace, job_dir: Path) -> None:
    # 1) persist copy
    if o.persist_dir.strip():
        persist_root = Path(o.persist_dir)
        persist_root.mkdir(parents=True, exist_ok=True)
        dst = persist_root / job_dir.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(job_dir, dst)
        print(f"[main.py] persisted -> {dst}", flush=True)

    # 2) tar.gz
    tar_path = job_dir.with_suffix(".tar.gz")
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(job_dir, arcname=job_dir.name)
    print(f"[main.py] archived -> {tar_path}", flush=True)

    # 3) s3 upload (aws cli)
    if o.s3_uri.strip():
        env = os.environ.copy()
        if o.s3_profile.strip():
            env["AWS_PROFILE"] = o.s3_profile.strip()

        # s3://bucket/prefix  (prefix 없으면 그냥 bucket root)
        s3_uri = o.s3_uri.rstrip("/")
        dst_uri = f"{s3_uri}/{tar_path.name}"

        print(f"[main.py] uploading -> {dst_uri}", flush=True)
        subprocess.run(["aws", "s3", "cp", str(tar_path), dst_uri], check=True, env=env)
        print("[main.py] s3 upload done.", flush=True)


def main() -> None:
    o = parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = Path(o.outputs_dir) / f"{o.name}_{ts}"
    job_dir.mkdir(parents=True, exist_ok=True)

    # AF params symlink (colabdesign/alphafold 쪽에서 찾기 편하게)
    ensure_af_symlinks(Path(o.models_dir) / "alphafold")

    if o.mode == "backbone":
        run_rfd(o, job_dir)

    elif o.mode in ("designability", "full"):
        pdb = run_rfd(o, job_dir)
        run_bundle_designability_test(o, job_dir, pdb)

    print(f"[main.py] DONE. job_dir={job_dir}", flush=True)

    # 결과 저장/업로드(옵션)
    persist_and_upload(o, job_dir)


if __name__ == "__main__":
    main()