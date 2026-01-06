# /workspace/unified/src/steps/alphafold_step.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List
import os  
import pandas as pd
import jax
from jax import tree_util as jax_tree_util
from colabdesign.af import mk_af_model

# JAX 0.6.0 호환용: colabdesign 이 jax.tree_* 옛 API를 기대해서 alias 로 맞춰 줌
if not hasattr(jax, "tree_map"):
    jax.tree_map = jax_tree_util.tree_map  # type: ignore[attr-defined]
if not hasattr(jax, "tree_flatten"):
    jax.tree_flatten = jax_tree_util.tree_flatten  # type: ignore[attr-defined]
if not hasattr(jax, "tree_unflatten"):
    jax.tree_unflatten = jax_tree_util.tree_unflatten

@dataclass
class AlphaFoldStepConfig:
    experiment_id: str
    outputs_dir: Path
    num_recycles: int = 1
    use_multimer: bool = False
    initial_guess: bool = False
    max_seqs: int | None = None
    protein_sequence: str | None = None


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

def read_mpnn_fasta_with_meta(fasta_path: Path):
    """
    ProteinMPNN 이 만든 FASTA 파일에서
    '>design=0;mpnn_0|score=...' 형태의 헤더를 파싱해서
    (design_idx, seq_idx, seq) 튜플 리스트로 반환한다.
    """
    if not fasta_path.exists():
        raise FileNotFoundError(f"[alphafold] fasta not found: {fasta_path}")

    entries = []
    design_idx = 0
    seq_idx = 0
    seq_buf: list[str] = []

    def flush_current():
        nonlocal seq_buf, design_idx, seq_idx
        if not seq_buf:
            return
        seq = "".join(seq_buf).strip().replace("/", "").upper()
        if seq:
            entries.append((design_idx, seq_idx, seq))
        seq_buf = []

    for line in fasta_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            # 직전 서열 먼저 기록
            flush_current()

            # 예: >design=0;mpnn_0|score=1.23456
            header = line[1:]
            design_idx = 0
            seq_idx = 0
            try:
                # design=숫자
                if "design=" in header:
                    part = header.split("design=", 1)[1]
                    design_str = part.split(";", 1)[0]
                    design_idx = int(design_str)

                # mpnn_숫자
                if "mpnn_" in header:
                    part = header.split("mpnn_", 1)[1]
                    num_str = ""
                    for ch in part:
                        if ch.isdigit():
                            num_str += ch
                        else:
                            break
                    if num_str:
                        seq_idx = int(num_str)
            except Exception:
                # 헤더 파싱 실패하면 기본값(0,0) 유지
                design_idx = 0
                seq_idx = 0
            continue

        # 서열 라인
        seq_buf.append(line)

    # 마지막 서열 flush
    flush_current()

    return entries


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

    # RFdiffusion 결과가 있는 디렉터리에서 디자인별 PDB들을 모은다.
    rfd_dir = out_dir.parent / "step-rfdiffusion"
    pdb_paths = sorted(rfd_dir.glob(f"{exp}_*.pdb"))

    if not pdb_paths:
        raise FileNotFoundError(
            f"[alphafold] no RFdiffusion pdb found under {rfd_dir} "
            f"(expected {exp}_0.pdb, {exp}_1.pdb, ...)"
        )

    # 디자인 인덱스 -> PDB 경로 매핑 (예: 0 -> exp_0.pdb, 1 -> exp_1.pdb ...)
    pdb_map: dict[int, Path] = {}
    for p in pdb_paths:
        stem = p.stem  # "17_0" 같은 형식
        try:
            idx = int(stem.split("_")[-1])
        except ValueError:
            continue
        pdb_map[idx] = p

    # 최소한 0번 디자인은 fallback 으로 쓸 수 있게 확보
    if 0 not in pdb_map:
        pdb_map[0] = pdb_paths[0]

        # 최소한 0번 디자인은 fallback 으로 쓸 수 있게 확보
    if 0 not in pdb_map:
        pdb_map[0] = pdb_paths[0]

    # 🔹 ProteinMPNN 출력 폴더에서 FASTA 읽기
    mpnn_dir = out_dir.parent / "step-proteinMPNN"
    fasta_path = mpnn_dir / f"{exp}_mpnn.fasta"

    entries = read_mpnn_fasta_with_meta(fasta_path)  # 함수 이름은 실제 정의와 맞춰서 (_read_... 이면 그걸로)
    if not entries:
        raise RuntimeError(f"[alphafold] no sequences in fasta: {fasta_path}")


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

    top_k = 5
    rows = []
    best = {"idx": -1, "plddt": -1.0, "rmsd": 1e9, "path": None}

    for design_idx, seq_idx, seq in entries:
        # 이 서열에 해당하는 디자인의 PDB 사용, 없으면 0번 디자인으로 fallback
        input_pdb = pdb_map.get(design_idx, pdb_map[0])

        # 디자인별 PDB로 입력 준비
        af_model.prep_inputs(str(input_pdb), chain="A")

        for k in range(top_k):
            af_model.predict(seq=seq, num_recycles=int(cfg.num_recycles), verbose=False)

        aux = af_model.aux.get("log", {})
        plddt = float(aux.get("plddt", 0.0))
        ptm = float(aux.get("ptm", 0.0)) if "ptm" in aux else None
        pae = float(aux.get("pae", 0.0)) if "pae" in aux else None
        rmsd = float(aux.get("rmsd", 0.0)) if "rmsd" in aux else None

        pdb_path = all_pdb_dir / f"af_d{design_idx}_s{seq_idx}_k{k}.pdb"
        af_model.save_current_pdb(str(pdb_path))
        rows.append(
            {
                "design": design_idx,
                "seq_idx": seq_idx,
                "k": k,
                "plddt": plddt,
                "ptm": ptm,
                "pae": pae,
                "rmsd": rmsd,
                "pdb": str(pdb_path),
                "seq": seq,
            }
        )

        if (plddt > best["plddt"]) or (
            plddt == best["plddt"] and (rmsd or 1e9) < best["rmsd"]
        ):
            best = {"idx": design_idx, "plddt": plddt, "rmsd": (rmsd or 1e9), "path": pdb_path}

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