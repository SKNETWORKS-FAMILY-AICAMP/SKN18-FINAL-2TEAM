import argparse
import os
import subprocess
from datetime import datetime

def run(cmd: list[str], cwd: str | None = None):
    print("[main.py] CMD:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def normalize_contigs(contigs: str) -> str:
    # 코랩 free-mode처럼 숫자만 주면 "L-L"로 바꿈: "300" -> "300-300"
    if contigs.isdigit():
        return f"{contigs}-{contigs}"
    return contigs

def parse_args():
    p = argparse.ArgumentParser()

    # mode
    p.add_argument("--mode", default="all", choices=["all", "backbone", "validate"])

    # common job info
    p.add_argument("--name", default="job")
    p.add_argument("--out_dir", default="/outputs")

    # RFdiffusion (backbone)
    p.add_argument("--contigs", required=True)  # ex "300"
    p.add_argument("--iterations", type=int, default=50)
    p.add_argument("--num_designs", type=int, default=1)

    # validate (ProteinMPNN + AlphaFold)  -> colabdesign/rf/designability_test.py
    p.add_argument("--num_seqs", type=int, default=8)
    p.add_argument("--num_recycles", type=int, default=1)
    p.add_argument("--initial_guess", action="store_true")
    p.add_argument("--use_multimer", action="store_true")
    p.add_argument("--rm_aa", default="C")
    p.add_argument("--mpnn_sampling_temp", type=float, default=0.1)

    # validate-only mode에서 backbone pdb가 이미 있을 때
    p.add_argument("--job_dir", default="")  # validate-only일 때 /outputs/name_xxx 형태

    return p.parse_args()

def make_job_dir(out_dir: str, name: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    job_dir = os.path.join(out_dir, f"{name}_{ts}")
    os.makedirs(job_dir, exist_ok=True)
    return job_dir

def run_rfdiffusion(job_dir: str, name: str, contigs: str, iterations: int, num_designs: int):
    contigs_norm = normalize_contigs(contigs)

    # RFdiffusion은 output_prefix 기반으로 outputs 파일 생성
    # -> /outputs/.../backbone_0.pdb 형태로 만들기 위해 prefix를 job_dir/backbone 로 설정
    out_prefix = os.path.join(job_dir, "backbone")

    cmd = [
        "python",
        "/app/RFdiffusion/run_inference.py",
        f"inference.output_prefix={out_prefix}",
        f"inference.num_designs={num_designs}",
        f"diffuser.T={iterations}",
        f"contigmap.contigs=[{contigs_norm}]",
        "inference.dump_pdb=True",
        "inference.dump_pdb_path=/dev/shm",
    ]
    run(cmd)

    # RFdiffusion이 생성하는 파일명은 보통 {output_prefix}_{n}.pdb 형태
    # => job_dir/backbone_0.pdb 가 있어야 validate로 이어갈 수 있음
    backbone0 = f"{out_prefix}_0.pdb"
    if not os.path.isfile(backbone0):
        raise FileNotFoundError(f"RFdiffusion output not found: {backbone0}")
    return backbone0, contigs_norm

def run_validate(job_dir: str, backbone_pdb: str, contigs_norm: str, copies: int, args):
    # 코랩: python colabdesign/rf/designability_test.py {opts}
    # 여기선 job_dir을 loc으로 줘서 결과를 job_dir 아래에 모으기
    contigs_str = contigs_norm  # free 모드(단일 구간) 기준
    # 코랩은 contigs list를 ":"로 join하지만, 단일이면 그냥 하나로 넣어도 됨

    cmd = [
        "python",
        "/usr/local/lib/python3.*/dist-packages/colabdesign/rf/designability_test.py",
        f"--pdb={backbone_pdb}",
        f"--loc={job_dir}",
        f"--contig={contigs_str}",
        f"--copies={copies}",
        f"--num_seqs={args.num_seqs}",
        f"--num_recycles={args.num_recycles}",
        f"--rm_aa={args.rm_aa}",
        f"--mpnn_sampling_temp={args.mpnn_sampling_temp}",
        f"--num_designs={args.num_designs}",
    ]

    if args.initial_guess:
        cmd.append("--initial_guess")
    if args.use_multimer:
        cmd.append("--use_multimer")

    # 와일드카드 경로(/usr/local/lib/python3.*/...)는 쉘에서만 풀리므로
    # bash -lc로 실행
    run(["bash", "-lc", " ".join(cmd)])

def main():
    args = parse_args()

    if args.mode in ["all", "backbone"]:
        job_dir = make_job_dir(args.out_dir, args.name)
        backbone_pdb, contigs_norm = run_rfdiffusion(
            job_dir=job_dir,
            name=args.name,
            contigs=args.contigs,
            iterations=args.iterations,
            num_designs=args.num_designs,
        )
        print(f"[main.py] RFdiffusion done: {backbone_pdb}")

        if args.mode == "backbone":
            print(f"[main.py] DONE (backbone only). job_dir={job_dir}")
            return

        # all -> validate까지 이어감
        copies = 1
        run_validate(job_dir, backbone_pdb, contigs_norm, copies, args)
        print(f"[main.py] DONE (all). job_dir={job_dir}")
        return

    # validate-only
    if args.mode == "validate":
        if not args.job_dir:
            raise ValueError("--job_dir is required for --mode validate")
        job_dir = args.job_dir

        # validate-only이면 backbone pdb 경로를 job_dir에서 찾음
        backbone_pdb = os.path.join(job_dir, "backbone_0.pdb")
        if not os.path.isfile(backbone_pdb):
            raise FileNotFoundError(f"backbone pdb not found: {backbone_pdb}")

        contigs_norm = normalize_contigs(args.contigs)
        copies = 1
        run_validate(job_dir, backbone_pdb, contigs_norm, copies, args)
        print(f"[main.py] DONE (validate). job_dir={job_dir}")
        return

if __name__ == "__main__":
    main()