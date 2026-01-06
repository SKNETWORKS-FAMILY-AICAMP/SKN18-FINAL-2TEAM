#!/usr/bin/env python3
import os
import uuid
import subprocess
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# ---- Config ----
SCRIPT_DIR = os.environ.get("SCRIPT_DIR", "/workspace/unified")
OPS_SH = os.environ.get("OPS_SH", f"{SCRIPT_DIR}/unified_shell_script.sh")
OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", f"{SCRIPT_DIR}/outputs")

TORCH_VENV = os.environ.get("TORCH_VENV", "/opt/venv_torch")
JAX_VENV = os.environ.get("JAX_VENV", "/opt/venv_jax")

PYTHONPATH = os.environ.get("PYTHONPATH", "/app/RFdiffusion")

app = FastAPI(title="Unified Runner API")

# API step -> main.py step
STEP_FOR_MAIN = {
    "rfdiffusion": "rfdiffusion",
    "protein_mpnn": "proteinMPNN",
    "alphafold3": "alphafold",
}


def _kst_today() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).strftime("%Y-%m-%d")


def _ensure_paths():
    if not Path(OPS_SH).is_file():
        raise RuntimeError(f"unified_shell_script.sh not found: {OPS_SH}")
    Path(OUTPUTS_DIR).mkdir(parents=True, exist_ok=True)


def _job_paths(experiment_id: str):
    logs_dir = Path(OUTPUTS_DIR) / "_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{experiment_id}.log"
    pid_path = logs_dir / f"{experiment_id}.pid"
    return log_path, pid_path


def _local_step_dir(dt: str, experiment_id: str, step_main: str) -> Path:
    return Path(OUTPUTS_DIR) / f"dt={dt}" / f"pipeline={experiment_id}" / f"step={step_main}"


def _expected_files(dt: str, experiment_id: str, step_main: str) -> list[Path]:
    step_dir = _local_step_dir(dt, experiment_id, step_main)
    if step_main == "rfdiffusion":
        return [step_dir / f"{experiment_id}_0.pdb", step_dir / f"{experiment_id}_0.trb"]
    if step_main == "proteinMPNN":
        return [step_dir / f"{experiment_id}_mpnn.fasta", step_dir / f"{experiment_id}_mpnn_results.csv"]
    if step_main == "alphafold":
        return [step_dir / f"{experiment_id}_af_best.pdb", step_dir / f"{experiment_id}_af_results.csv"]
    return []


def _status(dt: str, experiment_id: str, step_main: str) -> str:
    expected = _expected_files(dt, experiment_id, step_main)
    if expected and all(p.exists() for p in expected):
        return "done"

    _log_path, pid_path = _job_paths(experiment_id)
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            if Path(f"/proc/{pid}").exists():
                return "running"
            return "failed"
        except Exception:
            return "unknown"

    return "unknown"


# ---------------- Models ----------------
class RunRequest(BaseModel):
    mode: Literal["backbone", "binder", "other"] = "backbone"
    name: Optional[str] = None  # 호환용(무시)

    contigs: str = Field(default="100")
    iterations: int = Field(default=1, ge=1)

    experiment_id: str
    step: Literal["rfdiffusion", "protein_mpnn", "alphafold3"]

    # ✅ 로컬/S3 동일 구조를 위해 dt 받기(없으면 KST 오늘)
    dt: Optional[str] = None

    s3_upload_logs: bool = Field(default=True)


class RunResponse(BaseModel):
    ok: bool
    job_id: str
    name: str
    dt: str
    step: str
    outputs_dir: str
    cmd: list[str]
    log_path: str


class StatusResponse(BaseModel):
    ok: bool
    name: str
    dt: str
    step: str
    status: str
    log_path: str
    expected_outputs: list[str]


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
def run(req: RunRequest):
    _ensure_paths()

    experiment_id = req.experiment_id.strip()
    if not experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id is required")

    dt = (req.dt or "").strip() or _kst_today()

    step_api = req.step
    step_main = STEP_FOR_MAIN[step_api]

    job_id = uuid.uuid4().hex[:12]
    log_path, pid_path = _job_paths(experiment_id)

    args = [
        "run",
        "--mode", req.mode,
        "--contigs", (req.contigs or "100"),
        "--iterations", str(req.iterations or 1),
        "--experiment_id", experiment_id,
        "--step", step_main,
        "--dt", dt,
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
    env["S3_BUCKET"] = env.get("S3_BUCKET", "")
    env["S3_BASE"] = env.get("S3_BASE", "simulations")
    env["AWS_REGION"] = env.get("AWS_REGION", env.get("AWS_DEFAULT_REGION", ""))
    env["AWS_DEFAULT_REGION"] = env.get("AWS_DEFAULT_REGION", env["AWS_REGION"])
    env["AWS_S3_BUCKET"] = env.get("AWS_S3_BUCKET", "")
    env["AWS_S3_BASE_PATH"] = env.get("AWS_S3_BASE_PATH", "")

    # ✅ 실제 실행(주석 제거)
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
        name=experiment_id,
        dt=dt,
        step=step_api,
        outputs_dir=OUTPUTS_DIR,
        cmd=["bash", OPS_SH, *args],
        log_path=str(log_path),
    )


@app.get("/status/{experiment_id}", response_model=StatusResponse)
def status(
    experiment_id: str,
    step: Literal["rfdiffusion", "protein_mpnn", "alphafold3"] = Query("rfdiffusion"),
    dt: str = Query(default_factory=_kst_today),
):
    _ensure_paths()

    experiment_id = experiment_id.strip()
    dt = (dt or "").strip() or _kst_today()

    step_main = STEP_FOR_MAIN[step]
    st = _status(dt, experiment_id, step_main)
    log_path, _ = _job_paths(experiment_id)

    expected = _expected_files(dt, experiment_id, step_main)

    return StatusResponse(
        ok=True,
        name=experiment_id,
        dt=dt,
        step=step,
        status=st,
        log_path=str(log_path),
        expected_outputs=[str(p) for p in expected],
    )