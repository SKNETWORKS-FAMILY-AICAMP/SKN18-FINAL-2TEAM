# /workspace/unified/src/steps/alphafold_step.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from colabdesign.af import mk_af_model


@dataclass
class AlphaFoldStepConfig:
    experiment_id: str
    outputs_dir: Path
    num_recycles: int = 1        # iterations 값을 num_recycles로 매핑할 예정(기본 1)
    use_multimer: bool = False
    initial_guess: bool = False


def _read_fasta_seqs(fasta_path: Path) -> List[str]:
    if not fasta_path.exists():
        raise FileNotFoundError(f"[alphafold] fasta not found: {fasta_path}")

    seqs = []
    buf = []
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

    # 아주 기본 정제
    seqs = [s.replace("/", "").strip().upper() for s in seqs if s.strip()]
    return seqs


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

    all_pdb_dir = out_dir / f"{exp}_af_all_pdb"
    all_pdb_dir.mkdir(parents=True, exist_ok=True)

    flags = {
        "initial_guess": bool(cfg.initial_guess),
        "best_metric": "rmsd",
        "use_multimer": bool(cfg.use_multimer),
        "model_names": ["model_1_multimer_v3" if cfg.use_multimer else "model_1_ptm"],
    }

    # 여기서는 가장 단순한 fixbb로 검증만 한다.
    # (binder/partial/fixbb 프로토콜 분기는 필요하면 이후에 contigs 기반으로 확장 가능)
    af_model = mk_af_model(protocol="fixbb", **flags)

    # 입력 구조만 읽어서 “틀”을 잡고, 이후 seq만 바꿔가며 predict
    af_model.prep_inputs(str(input_pdb), chain="A")

    rows = []
    best = {"idx": -1, "plddt": -1.0, "rmsd": 1e9, "path": None}

    for i, seq in enumerate(seqs):
        af_model.predict(seq=seq, num_recycles=int(cfg.num_recycles), verbose=False)

        # aux log에서 대표 지표 추출
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

        # best 기준: plddt 우선, 동률이면 rmsd 작은 것
        if (plddt > best["plddt"]) or (plddt == best["plddt"] and (rmsd or 1e9) < best["rmsd"]):
            best = {"idx": i, "plddt": plddt, "rmsd": (rmsd or 1e9), "path": pdb_path}

        # 내부 카운터 증가(원 코드 흐름과 비슷하게 유지)
        af_model._k += 1

    csv_path = out_dir / f"{exp}_af_results.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    best_path = out_dir / f"{exp}_af_best.pdb"
    if best["path"] is not None and Path(best["path"]).exists():
        best_path.write_text(Path(best["path"]).read_text())

    return {
        "input_pdb": str(input_pdb),
        "input_fasta": str(fasta_path),
        "csv": str(csv_path),
        "best_pdb": str(best_path),
        "all_pdb_dir": str(all_pdb_dir),
        "num_seqs": len(rows),
        "best_idx": best["idx"],
        "best_plddt": best["plddt"],
        "best_rmsd": best["rmsd"],
    }