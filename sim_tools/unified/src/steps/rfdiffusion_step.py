# /workspace/unified/src/steps/rfdiffusion_step.py
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

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
    """
    RFdiffusion 단일 스텝 실행 전용.
    - experiment_id: 파일 prefix (job name)
    - outputs_dir: 결과 폴더(Path)
    """
    outputs_dir.mkdir(parents=True, exist_ok=True)

    contig_str = str(contigs).strip()
    contig_override = f"contigmap.contigs=[{contig_str!r}]"

    py = pick_python()
    entry = resolve_rfdiffusion_entry()
    cmd = [
        py,
        entry,
        f"inference.output_prefix={outputs_dir / experiment_id}",
        f"inference.num_designs={int(iterations)}",
        contig_override,
    ]
    if cautious:
        cmd.append("inference.cautious=True")

    print("[rfdiffusion_step] exec:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)

    n = int(iterations)
    produced = []
    for i in range(n):
        produced.append(outputs_dir / f"{experiment_id}_{i}.pdb")
        produced.append(outputs_dir / f"{experiment_id}_{i}.trb")

    return {"produced": produced}
