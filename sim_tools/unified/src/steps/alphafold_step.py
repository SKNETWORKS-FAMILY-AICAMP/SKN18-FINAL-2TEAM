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
    num_recycles: int = 1
    use_multimer: bool = False
    initial_guess: bool = False


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

    return [s.replace("/", "").strip().upper() for s in seqs if s.strip()]


def _ensure_colabdesign_params_visible():
    """
    ColabDesign(af)에서 보통 ./params 아래의 params_model_*.npz 를 찾는 경우가 많아서,
    실행 cwd(/workspace/unified) 기준으로 params 링크를 강제로 보장한다.
    """
    models_dir = Path(os.environ.get("MODELS_DIR", "/models"))
    real_params_dir = Path(os.environ.get("AF_DIR", str(models_dir / "alphafold")))

    # 실제 params 존재 확인
    need = real_params_dir / "params_model_1_ptm.npz"
    if not need.exists():
        sample = sorted([p.name for p in real_params_dir.glob("params_model_*.npz")])[:10]
        raise FileNotFoundError(
            "[alphafold] AlphaFold params not found.\n"
            f" - expected: {need}\n"
            f" - AF_DIR={real_params_dir}\n"
            f" - found_sample={sample}\n"
        )

    # cwd 기준 ./params 만들기 (symlink)
    cwd_params = Path.cwd() / "params"
    try:
        if cwd_params.is_symlink() or cwd_params.exists():
            # 이미 있으면 그대로 둠 (다른 곳 가리키면 덮어씀)
            cwd_params.unlink()
        cwd_params.symlink_to(real_params_dir, target_is_directory=True)
    except Exception:
        # symlink 실패 환경 대비: 디렉토리 생성 + 파일 일부라도 복사하는 fallback(무겁긴 하지만)
        cwd_params.mkdir(parents=True, exist_ok=True)
        # 최소한 ptm/multimer 파일은 보장
        for p in real_params_dir.glob("params_model_*.npz"):
            dst = cwd_params / p.name
            if not dst.exists():
                try:
                    dst.write_bytes(p.read_bytes())
                except Exception:
                    pass


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

    # ✅ 핵심: ColabDesign이 params를 찾을 수 있게 ./params 보장
    _ensure_colabdesign_params_visible()

    all_pdb_dir = out_dir / f"{exp}_af_all_pdb"
    all_pdb_dir.mkdir(parents=True, exist_ok=True)

    model_name = "model_1_multimer_v3" if cfg.use_multimer else "model_1_ptm"

    flags = {
        "initial_guess": bool(cfg.initial_guess),
        "best_metric": "rmsd",
        "use_multimer": bool(cfg.use_multimer),
        "model_names": [model_name],
    }

    # ✅ params_dir 같은 kwarg 절대 금지 (너 로그에서 바로 죽는 거 확인됨)
    af_model = mk_af_model(protocol="fixbb", **flags)

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
            {"n": i, "plddt": plddt, "ptm": ptm, "pae": pae, "rmsd": rmsd, "pdb": str(pdb_path), "seq": seq}
        )

        if (plddt > best["plddt"]) or (plddt == best["plddt"] and (rmsd or 1e9) < best["rmsd"]):
            best = {"idx": i, "plddt": plddt, "rmsd": (rmsd or 1e9), "path": pdb_path}

        af_model._k += 1

    csv_path = out_dir / f"{exp}_af_results.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    best_path = out_dir / f"{exp}_af_best.pdb"
    if best["path"] is not None and Path(best["path"]).exists():
        best_path.write_text(Path(best["path"]).read_text())

    return {
        "input_pdb": str(input_pdb),
        "input_fasta": str(fasta_path),
        "model_name": model_name,
        "csv": str(csv_path),
        "best_pdb": str(best_path),
        "all_pdb_dir": str(all_pdb_dir),
        "num_seqs": len(rows),
        "best_idx": best["idx"],
        "best_plddt": best["plddt"],
        "best_rmsd": best["rmsd"],
    }