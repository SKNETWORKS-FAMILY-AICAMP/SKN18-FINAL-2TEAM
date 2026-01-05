#!/usr/bin/env python3
import os
import uuid
import subprocess
from pathlib import Path
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---- Config ----
SCRIPT_DIR = os.environ.get("SCRIPT_DIR", "/workspace/unified")
OPS_SH = os.environ.get("OPS_SH", f"{SCRIPT_DIR}/unified_shell_script.sh")

OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", f"{SCRIPT_DIR}/outputs")

# ✅ torch/jax venv 둘 다 전달
TORCH_VENV = os.environ.get("TORCH_VENV", "/opt/venv_torch")
JAX_VENV = os.environ.get("JAX_VENV", "/opt/venv_jax")

PYTHONPATH = os.environ.get("PYTHONPATH", "/app/RFdiffusion")

API_KEY = os.environ.get("API_KEY")  # 설정 안 하면 인증 없이 동작

app = FastAPI(title="Unified Runner API")


# ---------------- Models ----------------
class RunRequest(BaseModel):
    mode: Literal["backbone", "binder", "other"] = "backbone"

    # ⚠️ 기존 호환을 위해 남겨두되, 실제 실행에서는 무시함
    name: Optional[str] = None

    contigs: str = Field(default="100")
    iterations: int = Field(default=1, ge=1, le=1000)

    # ✅ S3 경로 규칙에 필요한 값
    experiment_id: str = Field(..., description="pipeline=EXPERIMENT_ID (queue에서 받은 값)")
    step: Literal["rfdiffusion", "alphafold", "proteinMPNN"] = Field(
        default="rfdiffusion",
        description="step=TOOL_NAME"
    )

    # ✅ (선택) 로그 업로드
    s3_upload_logs: bool = Field(default=False)


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


def _auth_or_throw(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


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

        "s3_bucket": os.environ.get("S3_BUCKET", ""),
        "s3_base": os.environ.get("S3_BASE", "simulations"),
        "aws_region": os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "")),

        "aws_s3_bucket": os.environ.get("AWS_S3_BUCKET", ""),
        "aws_s3_base_path": os.environ.get("AWS_S3_BASE_PATH", ""),
    }


@app.post("/run", response_model=RunResponse)
def run(req: RunRequest, x_api_key: Optional[str] = None):
    _auth_or_throw(x_api_key)
    _ensure_paths()

    experiment_id = req.experiment_id.strip()
    if not experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id is required")

    # ✅ 팀장님 지시: pipeline(=experiment_id) 하나가 job 하나
    name = experiment_id

    # job_id는 추적/응답용으로만 유지 (파일/폴더에는 사용 안 함)
    job_id = uuid.uuid4().hex[:12]

    log_path, pid_path = _job_paths(name)

    # ✅ main.py에 experiment_id / step 전달
    args = [
        "run",
        "--mode", req.mode,
        "--name", name,
        "--contigs", req.contigs,
        "--iterations", str(req.iterations),

        "--experiment_id", experiment_id,
        "--step", req.step,
    ]
    if req.s3_upload_logs:
        args.append("--s3_upload_logs")

    env = os.environ.copy()
    env["TORCH_VENV"] = TORCH_VENV
    env["JAX_VENV"] = JAX_VENV
    env["PYTHONPATH"] = PYTHONPATH
    env["OUTPUTS_DIR"] = OUTPUTS_DIR
    env["SCRIPT_DIR"] = SCRIPT_DIR

    # S3/AWS env 전달
    env["S3_BUCKET"] = os.environ.get("S3_BUCKET", "")
    env["S3_BASE"] = os.environ.get("S3_BASE", "simulations")
    env["AWS_REGION"] = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", ""))
    env["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", env["AWS_REGION"])

    env["AWS_S3_BUCKET"] = os.environ.get("AWS_S3_BUCKET", "")
    env["AWS_S3_BASE_PATH"] = os.environ.get("AWS_S3_BASE_PATH", "")

    with open(log_path, "ab") as f:
        p = subprocess.Popen(
            ["bash", OPS_SH, *args],
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=SCRIPT_DIR,
        )

    pid_path.write_text(str(p.pid))

    return RunResponse(
        ok=True,
        job_id=job_id,
        name=name,
        outputs_dir=OUTPUTS_DIR,
        cmd=["bash", OPS_SH, *args],
    )


@app.get("/status/{name}", response_model=StatusResponse)
def status(name: str, x_api_key: Optional[str] = None):
    _auth_or_throw(x_api_key)
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