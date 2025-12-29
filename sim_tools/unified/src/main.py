import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run(cmd, cwd=None, env=None):
    print("[main.py] CMD:", " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def now_tag():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_env_paths():
    models_dir = Path(os.environ.get("MODELS_DIR", "/models"))
    outputs_dir = Path(os.environ.get("OUTPUTS_DIR", "/outputs"))
    models_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return models_dir, outputs_dir


def normalize_contigs(contigs: str):
    """
    입력:
      - "100" -> "100-100"
      - "10-20" -> "10-20"
      - "A10-20/B30-40" 같은 복잡한 컨티그는 그대로 둠
    """
    s = contigs.strip()
    if s.isdigit():
        n = int(s)
        return f"{n}-{n}"
    return s


def ensure_alphafold_param_symlinks(models_dir: Path):
    """
    colabdesign(알파폴드) 쪽은 종종 model_1_ptm.npz 같은 파일명을 기대함.
    우리는 /models/alphafold/params_model_1_ptm.npz 형태로 받아서,
    링크가 없으면 자동으로 만들어 재현성을 올림.
    """
    af_dir = models_dir / "alphafold"
    if not af_dir.exists():
        print(f"[main.py] NOTE: AlphaFold dir not found: {af_dir} (download_params.sh 이후 생길 수 있음)")
        return

    # 대표 파일 존재 여부
    ptm_src = af_dir / "params_model_1_ptm.npz"
    if not ptm_src.exists():
        print(f"[main.py] NOTE: AlphaFold params not found in {af_dir}.")
        return

    def link_if_exists(src_name: str, dst_name: str):
        src = af_dir / src_name
        dst = af_dir / dst_name
        if src.exists():
            try:
                if dst.is_symlink() or dst.exists():
                    dst.unlink()
                dst.symlink_to(src.name)  # 상대경로 심링크(같은 폴더 내)
            except Exception as e:
                print(f"[main.py] WARNING: symlink failed {dst} -> {src}: {e}")

    # ptm
    for i in range(1, 6):
        link_if_exists(f"params_model_{i}_ptm.npz", f"model_{i}_ptm.npz")

    # monomer
    for i in range(1, 6):
        link_if_exists(f"params_model_{i}.npz", f"model_{i}.npz")

    # multimer v3 (있으면)
    for i in range(1, 6):
        link_if_exists(f"params_model_{i}_multimer_v3.npz", f"model_{i}_multimer_v3.npz")

    print(f"[main.py] AlphaFold symlinks ensured in {af_dir}")


def run_backbone(job_dir: Path, contigs_norm: str, iterations: int, num_designs: int):
    """
    RFdiffusion backbone 생성
    """
    # RFdiffusion run_inference.py 경로
    rf_repo = Path("/app/RFdiffusion")
    run_inference = rf_repo / "run_inference.py"
    if not run_inference.exists():
        raise FileNotFoundError(f"RFdiffusion not found: {run_inference}")

    # RFdiffusion contigmap 형식: ['100-100'] 같은 리스트 형태를 hydra 문자열로 전달
    contig_arg = f"[{contigs_norm}]"
    out_prefix = job_dir / "backbone"

    cmd = [
        "python3",
        str(run_inference),
        f"inference.output_prefix={out_prefix}",
        f"inference.num_designs={num_designs}",
        f"diffuser.T={iterations}",
        f"contigmap.contigs={contig_arg}",
        "inference.dump_pdb=True",
        "inference.dump_pdb_path=/dev/shm",
    ]
    run(cmd)

    backbone_pdb = Path(str(out_prefix) + "_0.pdb")
    if not backbone_pdb.exists():
        raise FileNotFoundError(f"Backbone pdb not created: {backbone_pdb}")

    print(f"[main.py] RFdiffusion done: {backbone_pdb}")
    return backbone_pdb


def run_validate(job_dir: Path, backbone_pdb: Path, contigs_norm: str, args):
    """
    ProteinMPNN + AlphaFold 검증 (colabdesign)
    - 핵심: 파일 경로 하드코딩 금지 -> python -m 사용
    """
    # colabdesign 존재 확인
    try:
        import colabdesign  # noqa
    except Exception as e:
        raise RuntimeError(f"colabdesign not installed or import failed: {e}")

    # AlphaFold symlink 보장(없으면 여기서라도 만든다)
    models_dir, _ = get_env_paths()
    ensure_alphafold_param_symlinks(models_dir)

    cmd = [
        "python3",
        "-m",
        "colabdesign.rf.designability_test",
        f"--pdb={backbone_pdb}",
        f"--loc={job_dir}",
        f"--contig={contigs_norm}",
        f"--copies={args.copies}",
        f"--num_seqs={args.num_seqs}",
        f"--num_recycles={args.num_recycles}",
        f"--rm_aa={args.rm_aa}",
        f"--num_designs={args.num_designs}",
        f"--mpnn_sampling_temp={args.mpnn_sampling_temp}",
    ]

    # 선택 옵션들
    if args.initial_guess:
        cmd.append("--initial_guess")
    if args.use_multimer:
        cmd.append("--use_multimer")

    run(cmd)
    print(f"[main.py] validate done: job_dir={job_dir}")


def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["all", "backbone", "validate"], default="all")
    p.add_argument("--name", default="job")
    p.add_argument("--out_dir", default="", help="(optional) override OUTPUTS_DIR subfolder")
    p.add_argument("--contigs", required=True, help='e.g. "100" or "100-100"')
    p.add_argument("--iterations", type=int, default=50)
    p.add_argument("--num_designs", type=int, default=1)

    # validate 관련
    p.add_argument("--num_seqs", type=int, default=4)
    p.add_argument("--num_recycles", type=int, default=3)
    p.add_argument("--copies", type=int, default=1)
    p.add_argument("--initial_guess", action="store_true")
    p.add_argument("--use_multimer", action="store_true")
    p.add_argument("--rm_aa", default="C")
    p.add_argument("--mpnn_sampling_temp", type=float, default=0.1)

    # 고급: validate만 다시 돌릴 때 backbone pdb 위치 지정 가능
    p.add_argument("--job_dir", default="", help="(optional) existing job dir under OUTPUTS_DIR")
    p.add_argument("--backbone_pdb", default="", help="(optional) full path to backbone pdb")
    return p


def main():
    args = build_parser().parse_args()
    models_dir, outputs_dir = get_env_paths()

    contigs_norm = normalize_contigs(args.contigs)

    # job_dir 결정 로직 (재현성 위해 timestamp 기본)
    if args.job_dir:
        job_dir = Path(args.job_dir)
        if not job_dir.is_absolute():
            job_dir = outputs_dir / job_dir
    else:
        base = args.out_dir.strip()
        root = outputs_dir / base if base else outputs_dir
        job_dir = root / f"{args.name}_{now_tag()}"
    job_dir.mkdir(parents=True, exist_ok=True)

    # MODELS_DIR/OUTPUTS_DIR 로그
    print(f"[main.py] MODELS_DIR={models_dir}")
    print(f"[main.py] OUTPUTS_DIR={outputs_dir}")
    print(f"[main.py] job_dir={job_dir}")

    backbone_pdb = None

    if args.mode in ("all", "backbone"):
        backbone_pdb = run_backbone(
            job_dir=job_dir,
            contigs_norm=contigs_norm,
            iterations=args.iterations,
            num_designs=args.num_designs,
        )

    if args.mode in ("all", "validate"):
        if args.backbone_pdb:
            backbone_pdb = Path(args.backbone_pdb)
        elif backbone_pdb is None:
            # validate-only인데 backbone_pdb를 안줬으면 job_dir에서 찾는다
            candidate = job_dir / "backbone_0.pdb"
            if candidate.exists():
                backbone_pdb = candidate
            else:
                raise FileNotFoundError(
                    "validate mode requires backbone pdb.\n"
                    "Provide --backbone_pdb=/path/to/backbone_0.pdb OR run --mode backbone first."
                )

        run_validate(job_dir, backbone_pdb, contigs_norm, args)

    if args.mode == "backbone":
        print(f"[main.py] DONE (backbone only). job_dir={job_dir}")
    elif args.mode == "validate":
        print(f"[main.py] DONE (validate only). job_dir={job_dir}")
    else:
        print(f"[main.py] DONE (all). job_dir={job_dir}")


if __name__ == "__main__":
    main()