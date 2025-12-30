import argparse
import os
import subprocess
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


def parse_steps(s: str | None) -> list[str]:
    if not s:
        return []
    return [x.strip().lower() for x in s.split(",") if x.strip()]


def contig_args(contigs: str) -> tuple[str, str]:
    contigs = contigs.strip()
    if not contigs:
        raise ValueError("contigs is empty")
    if contigs.isdigit():
        return f"[{contigs}-{contigs}]", f"{contigs}-{contigs}"
    return f"[{contigs}]", contigs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    # 기존 모드 유지(호환)
    p.add_argument("--mode", choices=["backbone", "designability", "full"], default="backbone")

    # ✅ 체크박스형 실행: steps (rfd, bundle, mpnn, af)
    p.add_argument("--steps", default="", help="comma-separated: rfd,bundle,mpnn,af")

    p.add_argument("--name", default="job")

    # RFdiffusion 입력
    p.add_argument("--contigs", default="", help='e.g. "100" or "A1-50/0 B1-50/0"')
    p.add_argument("--iterations", type=int, default=50)
    p.add_argument("--num_designs", type=int, default=1)

    # ✅ bundle 단독 실행 시 contig를 따로 넣을 수 있도록
    # (없으면 --contigs fallback)
    p.add_argument("--bundle_contig", default="", help="contig for bundle step (fallback to --contigs)")

    # MPNN/AF 단독 실행용 입력(미래 확장)
    p.add_argument("--pdb", default="", help="Input PDB for mpnn/bundle (or af-prep)")
    p.add_argument("--fasta", default="", help="Input FASTA for AF-only step")

    # bundle 옵션 (designability_selectable 또는 기존 bundle에 넘길 값들)
    p.add_argument("--copies", type=int, default=1)
    p.add_argument("--num_seqs", type=int, default=4)
    p.add_argument("--num_recycles", type=int, default=3)
    p.add_argument("--rm_aa", default="C")
    p.add_argument("--mpnn_sampling_temp", type=float, default=0.1)

    p.add_argument("--models_dir", default=os.environ.get("MODELS_DIR", "/models"))
    p.add_argument("--outputs_dir", default=os.environ.get("OUTPUTS_DIR", "/outputs"))

    p.add_argument("--rfdiffusion_entry", default=resolve_rfdiffusion_entry())
    p.add_argument("--torch_py", default=os.environ.get("TORCH_PY", "/opt/venv_torch/bin/python"))
    p.add_argument("--jax_py", default=os.environ.get("JAX_PY", "/opt/venv_jax/bin/python"))

    p.add_argument("--rfd_ckpt", default=os.environ.get("RFD_CKPT", "/app/RFdiffusion/models/Base_ckpt.pt"))

    # (옵션) 나중에 ProteinMPNN/AF-only runner 붙일 때
    p.add_argument("--mpnn_entry", default=os.environ.get("MPNN_ENTRY", ""))
    p.add_argument("--af_entry", default=os.environ.get("AF_ENTRY", ""))

    return p.parse_args()


def run_rfd(o: argparse.Namespace, job_dir: Path) -> Path:
    if not o.contigs:
        raise ValueError("--contigs is required for rfd step")

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
    print(f"[main.py] RFdiffusion done: {pdb}", flush=True)
    return pdb


def get_bundle_contig(o: argparse.Namespace) -> str:
    # bundle_contig 우선, 없으면 contigs fallback
    contig = (o.bundle_contig or o.contigs).strip()
    return contig


def run_bundle_selectable(o: argparse.Namespace, job_dir: Path, pdb_path: Path) -> None:
    contig = get_bundle_contig(o)
    if not contig:
        raise ValueError("bundle step needs contig. Provide --bundle_contig or --contigs")

    # designability_selectable.py 경로
    selectable = Path(__file__).with_name("designability_selectable.py")
    if not selectable.exists():
        raise FileNotFoundError(f"Missing selectable runner: {selectable}")

    # contig_for_designability는 "100-100" 같은 형태여야 하는 경우가 많음
    _, contig_for_designability = contig_args(contig)

    cmd = [
        o.jax_py, str(selectable),
        f"--pdb={pdb_path}",
        f"--loc={job_dir}",
        f"--contig={contig_for_designability}",
        f"--copies={o.copies}",
        f"--num_seqs={o.num_seqs}",
        f"--num_recycles={o.num_recycles}",
        f"--rm_aa={o.rm_aa}",
        f"--mpnn_sampling_temp={o.mpnn_sampling_temp}",
    ]

    # ✅ 여기서 “체크박스” 역할: 필요할 때만 플래그 추가
    # bundle은 원래 "mpnn + af" 같이 돌리려는 목적이니 기본은 둘 다 ON으로 호출해도 되고,
    # user가 bundle에서 선택하고 싶으면 main.py에서 조건 분기하면 됨.
    cmd += ["--run_mpnn", "--run_af"]

    run(cmd)
    print("[main.py] bundle(selectable) done.", flush=True)


def main() -> None:
    o = parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = Path(o.outputs_dir) / f"{o.name}_{ts}"
    job_dir.mkdir(parents=True, exist_ok=True)

    # AF params symlink (AF 관련 모듈들에서 쓰기 좋음)
    ensure_af_symlinks(Path(o.models_dir) / "alphafold")

    steps = parse_steps(o.steps)

    # ✅ steps가 비어 있으면 기존 mode 로직으로 동작(호환)
    if not steps:
        if o.mode == "backbone":
            run_rfd(o, job_dir)
        elif o.mode == "designability":
            pdb = run_rfd(o, job_dir)
            run_bundle_selectable(o, job_dir, pdb)
        else:  # full
            pdb = run_rfd(o, job_dir)
            run_bundle_selectable(o, job_dir, pdb)

        print(f"[main.py] DONE. job_dir={job_dir}", flush=True)
        return

    # ✅ 체크박스형 steps 실행
    pdb_path = Path(o.pdb) if o.pdb else None
    fasta_path = Path(o.fasta) if o.fasta else None

    if "rfd" in steps:
        pdb_path = run_rfd(o, job_dir)

    if "bundle" in steps:
        if not pdb_path or not pdb_path.exists():
            raise FileNotFoundError("bundle step needs a PDB. Run rfd first or pass --pdb=/path/to.pdb")
        run_bundle_selectable(o, job_dir, pdb_path)

    # mpnn / af "완전 단독"은 추후 실제 엔트리(ProteinMPNN runner, AF-only runner) 붙이면 확장 가능
    if "mpnn" in steps:
        raise RuntimeError("mpnn step (standalone) is not wired yet. Use bundle for now or provide an MPNN runner.")

    if "af" in steps:
        raise RuntimeError("af step (standalone) is not wired yet. Use bundle (with --run_af) or provide an AF-only runner.")

    print(f"[main.py] DONE. job_dir={job_dir}", flush=True)


if __name__ == "__main__":
    main()