# /workspace/unified/src/steps/rfdiffusion_step.py
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any
import shutil

def resolve_rfdiffusion_entry() -> str:
    env_entry = os.environ.get("RFDIFFUSION_ENTRY")
    if env_entry and Path(env_entry).is_file():
        return str(Path(env_entry))

    candidates = [
        Path("/app/RFdiffusion/run_inference.py"),
        Path("/workspace/RFdiffusion/run_inference.py"),
        Path(__file__).resolve().parents[1] / "RFdiffusion" / "run_inference.py",
        Path("/app/RFdiffusion/scripts/run_inference.py"),
    ]
    rfd_dir = os.environ.get("RFDIFFUSION_DIR")
    if rfd_dir:
        candidates.append(Path(rfd_dir) / "run_inference.py")
        candidates.append(Path(rfd_dir) / "scripts" / "run_inference.py")

    for c in candidates:
        if c.is_file():
            return str(c)

    for base in [Path("/app"), Path("/workspace"), Path(__file__).resolve().parents[1]]:
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


def run_rfdiffusion_step(
    experiment_id: str,
    outputs_dir: Path,
    contigs: str,
    iterations: int,
    cautious: bool,
    env: Dict[str, str],
) -> Dict[str, Any]:
    outputs_dir.mkdir(parents=True, exist_ok=True)

    contig_str = str(contigs).strip()
    # 문자열 리스트로 전달
    contig_override = f"contigmap.contigs=['{contig_str}']"

    py = pick_python()
    entry = resolve_rfdiffusion_entry()

    # 이제 경로에 '=' 가 없으므로 그대로 사용
    output_prefix = str(outputs_dir / experiment_id)

    cmd = [
        py,
        entry,
        f"inference.output_prefix={output_prefix}",
        f"inference.num_designs={int(iterations)}",
        contig_override,
    ]
    if cautious:
        cmd.append("inference.cautious=True")

    print("[rfdiffusion_step] exec:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)

    # RFdiffusion이 만든 파일 목록
    produced = []
    for i in range(int(iterations)):
        produced.append(outputs_dir / f"{experiment_id}_{i}.pdb")
        produced.append(outputs_dir / f"{experiment_id}_{i}.trb")

    return {"produced": produced}

