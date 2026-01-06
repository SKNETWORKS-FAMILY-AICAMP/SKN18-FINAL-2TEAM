#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---- Config ----
SCRIPT_DIR = os.environ.get("SCRIPT_DIR", "/workspace/unified")
OPS_SH = os.environ.get("OPS_SH", f"{SCRIPT_DIR}/unified_shell_script.sh")
OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", f"{SCRIPT_DIR}/outputs")

TORCH_VENV = os.environ.get("TORCH_VENV", "/opt/venv_torch")
JAX_VENV = os.environ.get("JAX_VENV", "/opt/venv_jax")

# unified_shell_script.sh 내부에서 PYTHONPATH도 세팅하지만, 안전하게 기본값 유지
PYTHONPATH = os.environ.get("PYTHONPATH", "/app/RFdiffusion")

app = FastAPI(title="Unified Runner API")

STEP_FOR_CLI = {
    "rfdiffusion": "rfdiffusion",
    "protein_mpnn": "proteinMPNN",
    "alphafold3": "alphafold",
}
# ---------------- Models ----------------
class RunRequest(BaseModel):
    mode: Literal["backbone", "binder", "other"] = "backbone"

    # # ⚠️ 기존 호환을 위해 남겨두되, 실제 실행에서는 무시함
    name: Optional[str] = None
    contigs: str = Field(default="100")
    iterations: int = Field(default=1)   
    s3_upload_logs: bool = Field(default=True)
    experiment_id: str            # 파이프라인 ID (experiment_sid 문자열)
    step: Literal["rfdiffusion", "protein_mpnn", "alphafold3"]
    # options: dict = Field(default_factory=dict)

class RunResponse(BaseModel):
    ok: bool
    job_id: str
    name: str
    outputs_dir: str
    cmd: list[str]


class StatusResponse(BaseModel):
    ok: bool
    job_id: str
    name: str
    status: str
    log_path: str
    expected_pdb: str


# ---------------- Utils ----------------
def _ensure_paths():
    if not Path(OPS_SH).is_file():
        raise RuntimeError(f"unified_shell_script.sh not found: {OPS_SH}")
    Path(OUTPUTS_DIR).mkdir(parents=True, exist_ok=True)


def _job_paths(name: str):
    logs_dir = Path(OUTPUTS_DIR) / "_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{name}.log"
    pid_path = logs_dir / f"{name}.pid"
    return log_path, pid_path


def _status_from_files(name: str) -> str:
    pdb0 = Path(OUTPUTS_DIR) / f"{name}_0.pdb"
    _log_path, pid_path = _job_paths(name)

    if pdb0.exists():
        return "done"

    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            if Path(f"/proc/{pid}").exists():
                return "running"
            else:
                return "failed"
        except Exception:
            return "unknown"

    return "unknown"


# ---------------- Routes ----------------
@app.get("/health")
def health():
    _ensure_paths()
    return {
        "ok": True,
        "ops_sh": OPS_SH,
        "outputs_dir": OUTPUTS_DIR,
        "torch_venv": TORCH_VENV,
        "jax_venv": JAX_VENV,
        "pythonpath": PYTHONPATH,

        # 디버깅용 환경 변수 노출
        "enable_jax_cuda": os.environ.get("ENABLE_JAX_CUDA", ""),
        "ld_library_path": os.environ.get("LD_LIBRARY_PATH", ""),

        "s3_bucket": os.environ.get("S3_BUCKET", ""),
        "s3_base": os.environ.get("S3_BASE", "simulations"),
        "aws_region": os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "")),

        "aws_s3_bucket": os.environ.get("AWS_S3_BUCKET", ""),
        "aws_s3_base_path": os.environ.get("AWS_S3_BASE_PATH", ""),
    }


@app.post("/run", response_model=RunResponse)
def run(req: RunRequest):
    _ensure_paths()

    experiment_id = req.experiment_id.strip()
    if not experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id is required")

    step_api = req.step
    opts = req.options or {}
    step_cli = STEP_FOR_CLI[step_api] 
    # job_name = f"{exp_id}__{step}"  

    contigs = req.contigs or "100"
    iterations = req.iterations or 1
    cautious = False

    if step_api == "rfdiffusion":
        contigs = str(opts.get("contigs") or contigs)
        iterations = int(opts.get("numSteps") or iterations)
        cautious = bool(opts.get("cautious") or False)

    elif step_api == "protein_mpnn":
        iterations = int(opts.get("numSequences") or iterations)

    elif step_api == "alphafold3":
        iterations = int(opts.get("maxRecycles") or iterations)


    args = [
        "run",
        "--mode", req.mode,
        "--contigs", contigs,
        "--iterations", str(iterations),
        "--experiment_id", experiment_id,
        "--step", step_cli,
    ]
    if req.s3_upload_logs:
        args.append("--s3_upload_logs")
    if cautious:
        args.append("--cautious")

    env = os.environ.copy()

    # ✅ venv / 경로 전달
    env["TORCH_VENV"] = TORCH_VENV
    env["JAX_VENV"] = JAX_VENV
    env["PYTHONPATH"] = PYTHONPATH
    env["OUTPUTS_DIR"] = OUTPUTS_DIR
    env["SCRIPT_DIR"] = SCRIPT_DIR

    # ✅ GPU/JAX 이슈 재발 방지: 기본으로 세팅
    env["ENABLE_JAX_CUDA"] = env.get("ENABLE_JAX_CUDA", "1")
    env["LD_LIBRARY_PATH"] = ""  # 외부 LD_LIBRARY_PATH 오염 차단 (unified_shell_script.sh가 step별로 재설정)

    # ✅ S3/AWS env 전달
    env["S3_BUCKET"] = env.get("S3_BUCKET", "")
    env["S3_BASE"] = env.get("S3_BASE", "simulations")
    env["AWS_REGION"] = env.get("AWS_REGION", env.get("AWS_DEFAULT_REGION", ""))
    env["AWS_DEFAULT_REGION"] = env.get("AWS_DEFAULT_REGION", env["AWS_REGION"])
    env["AWS_S3_BUCKET"] = env.get("AWS_S3_BUCKET", "")
    env["AWS_S3_BASE_PATH"] = env.get("AWS_S3_BASE_PATH", "")

    # with open(log_path, "ab") as f:
    #     p = subprocess.Popen(
    #         ["bash", OPS_SH, *args],
    #         env=env,
    #         stdout=f,
    #         stderr=subprocess.STDOUT,
    #         cwd=SCRIPT_DIR,
    #     )

    # pid_path.write_text(str(p.pid))

    # return RunResponse(
    #     ok=True,
    #     job_id=job_id,
    #     outputs_dir=OUTPUTS_DIR,
    #     cmd=["bash", OPS_SH, *args],
    # )


@app.get("/status/{name}", response_model=StatusResponse)
def status(name: str):
    _ensure_paths()

    log_path, _ = _job_paths(name)
    st = _status_from_files(name)

    return StatusResponse(
        ok=True,
        job_id="(use name)",
        name=name,
        status=st,
        log_path=str(log_path),
        expected_pdb=str(Path(OUTPUTS_DIR) / f"{name}_0.pdb"),
    )