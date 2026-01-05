# /workspace/unified/src/steps/alphafold_step.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd
from colabdesign.af import mk_af_model


@dataclass
class AlphaFoldStepConfig:
    experiment_id: str
    outputs_dir: Path
    num_recycles: int = 1        # iterations 값을 num_recycles로 매핑
    use_multimer: bool = False
    initial_guess: bool = False
    # ✅ AlphaFold params 위치 (env로 지정 가능)
    alphafold_params_dir: str | None = None


def _read_fasta_seqs(fasta_path: Path) -> List[str]:
    if not fasta_path.exists():
        raise FileNotFoundError(f"[alphafold] fasta not found: {fasta_path}")

    seqs: List[str] = []
    buf: List[str] = []
    for line in fasta_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if buf:
                seqs.append("".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        seqs.append("".join(buf))

    # 기본 정제
    seqs = [s.replace("/", "").strip().upper() for s in seqs if s.strip()]
    return seqs


def _resolve_af_params_dir(cfg: AlphaFoldStepConfig) -> Path:
    # 1) cfg에 명시된 값
    if cfg.alphafold_params_dir:
        return Path(cfg.alphafold_params_dir)

    # 2) env 우선순위: ALPHAFOLD_PARAMS_DIR -> AF_DIR -> MODELS_DIR/alphafold
    env_dir = (
        os.environ.get("ALPHAFOLD_PARAMS_DIR")
        or os.environ.get("AF_DIR")
        or ""
    )
    if env_dir.strip():
        return Path(env_dir.strip())

    models_dir = os.environ.get("MODELS_DIR", "/models")
    return Path(models_dir) / "alphafold"


def _assert_params_exist(params_dir: Path, use_multimer: bool):
    # ColabDesign이 보통 찾는 파일들 (tar에서 풀린 파일명 기준)
    required = []
    if use_multimer:
        required.append(params_dir / "params_model_1_multimer_v3.npz")
    else:
        required.append(params_dir / "params_model_1_ptm.npz")

    missing = [str(p) for p in required if not p.exists()]
    if missing:
        # 디버깅 도움용: params_dir 내용 일부 보여주기
        sample = sorted([p.name for p in params_dir.glob("params_model_*.npz")])[:10]
        raise FileNotFoundError(
            "[alphafold] AlphaFold params not found.\n"
            f" - params_dir={params_dir}\n"
            f" - missing={missing}\n"
            f" - found_sample={sample}\n"
            "Fix: ensure params are extracted into /models/alphafold (or set ALPHAFOLD_PARAMS_DIR/AF_DIR)."
        )


def _mk_af_model_with_params(protocol: str, flags: dict, params_dir: Path):
    """
    ColabDesign 버전 차이 대비:
    - mk_af_model이 data_dir/params_dir/weights_dir 등을 받을 수도 있음
    - 못 받으면 모델 생성 후 속성(params_dir/data_dir 등)을 강제로 세팅
    """
    # 1) kwarg로 넘기기 (가능한 키를 순서대로 시도)
    for key in ("params_dir", "data_dir", "weights_dir"):
        try:
            return mk_af_model(protocol=protocol, **flags, **{key: str(params_dir)})
        except TypeError:
            pass

    # 2) kwarg가 전부 실패하면 생성 후 속성 세팅 시도
    af_model = mk_af_model(protocol=protocol, **flags)

    # 흔한 속성명들(버전별 상이)을 최대한 커버
    for attr in ("params_dir", "data_dir", "weights_dir"):
        if hasattr(af_model, attr):
            try:
                setattr(af_model, attr, str(params_dir))
            except Exception:
                pass

    return af_model


def run_alphafold_only(cfg: AlphaFoldStepConfig) -> dict:
    exp = cfg.experiment_id
    out_dir = cfg.outputs_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    input_pdb = out_dir / f"{exp}_0.pdb"
    if not input_pdb.exists():
        raise FileNotFoundError(
            f"[alphafold] input pdb not found: {input_pdb} "
            f"(먼저 step=rfdiffusion을 같은 experiment_id로 실행해야 함)"
        )

    fasta_path = out_dir / f"{exp}_mpnn.fasta"
    seqs = _read_fasta_seqs(fasta_path)
    if not seqs:
        raise RuntimeError(f"[alphafold] no sequences in fasta: {fasta_path}")

    # ✅ params dir 확정 + 존재 체크
    params_dir = _resolve_af_params_dir(cfg)
    _assert_params_exist(params_dir, use_multimer=bool(cfg.use_multimer))

    all_pdb_dir = out_dir / f"{exp}_af_all_pdb"
    all_pdb_dir.mkdir(parents=True, exist_ok=True)

    model_name = "model_1_multimer_v3" if cfg.use_multimer else "model_1_ptm"

    flags = {
        "initial_guess": bool(cfg.initial_guess),
        "best_metric": "rmsd",
        "use_multimer": bool(cfg.use_multimer),
        "model_names": [model_name],
    }

    # ✅ params_dir를 확실히 전달해서 mk_af_model이 모델 파라미터를 찾게 함
    af_model = _mk_af_model_with_params(protocol="fixbb", flags=flags, params_dir=params_dir)

    # 입력 구조만 읽어서 “틀” 잡기
    af_model.prep_inputs(str(input_pdb), chain="A")

    rows = []
    best = {"idx": -1, "plddt": -1.0, "rmsd": 1e9, "path": None}

    for i, seq in enumerate(seqs):
        af_model.predict(seq=seq, num_recycles=int(cfg.num_recycles), verbose=False)

        aux = af_model.aux.get("log", {})
        plddt = float(aux.get("plddt", 0.0))
        ptm = float(aux.get("ptm", 0.0)) if "ptm" in aux else None
        pae = float(aux.get("pae", 0.0)) if "pae" in aux else None
        rmsd = float(aux.get("rmsd", 0.0)) if "rmsd" in aux else None

        pdb_path = all_pdb_dir / f"af_n{i}.pdb"
        af_model.save_current_pdb(str(pdb_path))

        rows.append(
            {
                "n": i,
                "plddt": plddt,
                "ptm": ptm,
                "pae": pae,
                "rmsd": rmsd,
                "pdb": str(pdb_path),
                "seq": seq,
            }
        )

        if (plddt > best["plddt"]) or (plddt == best["plddt"] and (rmsd or 1e9) < best["rmsd"]):
            best = {"idx": i, "plddt": plddt, "rmsd": (rmsd or 1e9), "path": pdb_path}

        # ColabDesign 내부 카운터 증가(기존 흐름 유지)
        af_model._k += 1

    csv_path = out_dir / f"{exp}_af_results.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    best_path = out_dir / f"{exp}_af_best.pdb"
    if best["path"] is not None and Path(best["path"]).exists():
        best_path.write_text(Path(best["path"]).read_text())

    return {
        "input_pdb": str(input_pdb),
        "input_fasta": str(fasta_path),
        "alphafold_params_dir": str(params_dir),
        "model_name": model_name,
        "csv": str(csv_path),
        "best_pdb": str(best_path),
        "all_pdb_dir": str(all_pdb_dir),
        "num_seqs": len(rows),
        "best_idx": best["idx"],
        "best_plddt": best["plddt"],
        "best_rmsd": best["rmsd"],
    }