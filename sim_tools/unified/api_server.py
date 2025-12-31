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
RUN_SH = os.environ.get("RUN_SH", f"{SCRIPT_DIR}/run.sh")
OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", "/outputs")
TORCH_VENV = os.environ.get("TORCH_VENV", "/opt/venv_torch")
PYTHONPATH = os.environ.get("PYTHONPATH", "/app/RFdiffusion")

# (선택) 아주 간단한 보호장치: 헤더에 X-API-KEY가 맞아야만 실행
API_KEY = os.environ.get("API_KEY")  # 설정 안 하면 인증 없이 동작

app = FastAPI(title="RFdiffusion Runner API")


class RunRequest(BaseModel):
    mode: Literal["backbone", "binder", "other"] = "backbone"
    name: Optional[str] = None  # 없으면 job_id로 자동 생성
    contigs: str = Field(default="100", description="e.g. 100 or 'A1-50 0 A51-100'")
    iterations: int = Field(default=1, ge=1, le=1000)


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
    status: str  # queued/running/done/failed/unknown
    log_path: str
    expected_pdb: str


def _ensure_paths():
    if not Path(RUN_SH).is_file():
        raise RuntimeError(f"run.sh not found: {RUN_SH}")
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
    # 아주 단순 규칙:
    # - name_0.pdb 있으면 done
    # - pid 파일 있고 프로세스 살아있으면 running
    # - pid 있는데 프로세스 죽었고 pdb 없으면 failed
    pdb0 = Path(OUTPUTS_DIR) / f"{name}_0.pdb"
    log_path, pid_path = _job_paths(name)

    if pdb0.exists():
        return "done"

    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            # /proc 기반 체크(리눅스)
            if Path(f"/proc/{pid}").exists():
                return "running"
            else:
                return "failed"
        except Exception:
            return "unknown"

    # 아무 기록도 없으면 unknown
    return "unknown"


@app.get("/health")
def health():
    _ensure_paths()
    return {
        "ok": True,
        "run_sh": RUN_SH,
        "outputs_dir": OUTPUTS_DIR,
        "torch_venv": TORCH_VENV,
        "pythonpath": PYTHONPATH,
    }


@app.post("/run", response_model=RunResponse)
def run(req: RunRequest, x_api_key: Optional[str] = None):
    _auth_or_throw(x_api_key)
    _ensure_paths()

    job_id = uuid.uuid4().hex[:12]
    name = req.name or f"job_{job_id}"

    # logs/pid
    log_path, pid_path = _job_paths(name)

    # run.sh에 넘길 args
    args = [
        "--mode", req.mode,
        "--name", name,
        "--contigs", req.contigs,
        "--iterations", str(req.iterations),
    ]

    # 실행 환경(중요: 너가 지금까지 맞춘 것 그대로)
    env = os.environ.copy()
    env["TORCH_VENV"] = TORCH_VENV
    env["PYTHONPATH"] = PYTHONPATH
    env.setdefault("OUTPUTS_DIR", OUTPUTS_DIR)
    env.setdefault("SCRIPT_DIR", SCRIPT_DIR)

    # "API 서버는 살아있고", 실행은 백그라운드로 돌게 만들기
    # bash run.sh ... > log 2>&1 & echo $! > pid
    cmd_str = " ".join([RUN_SH] + [subprocess.list2cmdline([a]) if " " in a else a for a in args])
    # 위 cmd_str은 간단하게 만들었지만, 공백 포함 contigs 대비해서 아래처럼 직접 리스트로 실행하고 로그만 리다이렉트
    # -> 가장 안전: Popen + stdout/stderr 파일로 연결

    with open(log_path, "ab") as f:
        p = subprocess.Popen(
            ["bash", RUN_SH, *args],
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
        cmd=["bash", RUN_SH, *args],
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