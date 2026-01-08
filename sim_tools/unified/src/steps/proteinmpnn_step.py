# /workspace/unified/src/steps/proteinmpnn_step.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

import jax
from jax import tree_util as jax_tree_util

# ------------------------------------------------------------------
# JAX 0.6.0 이후 jax.tree_map 이 제거되었기 때문에,
# colabdesign 이 오래된 API(jax.tree_map)를 기대하는 경우를 위해
# 여기서 미리 alias 를 만들어 준다.
# (이 파일이 colabdesign 보다 먼저 import 되므로 안전하게 패치 가능)
if not hasattr(jax, "tree_map"):
    jax.tree_map = jax_tree_util.tree_map  # type: ignore[attr-defined]
if not hasattr(jax, "tree_flatten"):
    jax.tree_flatten = jax_tree_util.tree_flatten  # type: ignore[attr-defined]
if not hasattr(jax, "tree_unflatten"):
    jax.tree_unflatten = jax_tree_util.tree_unflatten  # type: ignore[attr-defined]

from colabdesign.mpnn import mk_mpnn_model
from colabdesign.af import mk_af_model
from string import ascii_uppercase, ascii_lowercase

alphabet_list = list(ascii_uppercase + ascii_lowercase)


@dataclass
class MPNNStepConfig:
    experiment_id: str
    outputs_dir: Path
    contigs: str = "100"          # 현재 API/args에서 받는 contigs 그대로 사용
    copies: int = 1               # 우선 1 고정 (필요하면 args로 확장)
    rm_aa: str | None = "C"
    num_seqs: int = 8             # iterations 값을 num_seqs로 매핑할 예정
    mpnn_sampling_temp: float = 0.1
    num_designs: int = 1        # 디자인할 구조(입력 PDB) 개수


def _parse_contigs(contigs_raw: str) -> List[str]:
    """
    ColabDesign 쪽 designability_test.py 로직을 최대한 비슷하게 따라감.
    입력 예: "100" / "A1-50/30" / "50:50" 등
    """
    if not contigs_raw:
        return ["100"]

    contigs_raw = contigs_raw.strip()
    # RFdiffusion에서 contigs가 "10"처럼 단일 숫자로 오는 케이스 대응
    # 또는 "10:20"처럼 여러 개면 chain 분리 개념으로 봄
    parts = contigs_raw.replace(" ", ":").replace(",", ":").split(":")
    contigs = []
    for contig_str in parts:
        contig_str = contig_str.strip()
        if not contig_str:
            continue
        segs = []
        for x in contig_str.split("/"):
            if x != "0":
                segs.append(x)
        if segs:
            contigs.append("/".join(segs))
    return contigs or ["100"]


def _get_info(contig: str) -> Tuple[List[int], List[bool]]:
    """
    designability_test.py의 get_info 이식 + 보강
    - "10" 처럼 하이픈 없는 숫자 세그먼트도 허용
    - "A1-50/30" 같이 섞인 케이스도 허용
    """
    F: List[int] = []
    free_chain = False
    fixed_chain = False

    # contig 예시:
    #  - "10"
    #  - "1-10"
    #  - "A1-50/30"
    #  - "30/10"
    for token in contig.split("/"):
        token = token.strip()
        if not token:
            continue

        if "-" in token:
            a, b = token.split("-", 1)

            # fixed segment: "A1-50"
            if a and a[0].isalpha():
                L = int(b) - int(a[1:]) + 1
                F += [1] * L
                fixed_chain = True
            else:
                # free segment: "1-10" 같은 케이스를 길이로 해석(10)
                # (designability_test.py는 이런 형태를 거의 안 쓰지만 안전장치)
                L = int(b)
                F += [0] * L
                free_chain = True
        else:
            # hyphen 없는 숫자: "10" -> free length 10
            if token[0].isalpha():
                # 혹시 "A10" 같은 이상 케이스 방어 (사실상 안 씀)
                raise ValueError(f"invalid contig token without '-': {token}")
            L = int(token)
            F += [0] * L
            free_chain = True

    return F, [fixed_chain, free_chain]


def _infer_protocol_and_prep_flags(contigs: List[str], copies: int, rm_aa: str | None):
    """
    designability_test.py의 protocol 분기 + prep_flags 생성 로직
    """
    chains = alphabet_list[: len(contigs)]
    info = [_get_info(x) for x in contigs]

    fixed_pos = []
    fixed_chains = []
    free_chains = []
    both_chains = []
    for pos, (fixed_chain, free_chain) in info:
        fixed_pos += pos
        fixed_chains += [fixed_chain and not free_chain]
        free_chains += [free_chain and not fixed_chain]
        both_chains += [fixed_chain and free_chain]

    flags = {
        "initial_guess": False,
        "best_metric": "rmsd",
        "use_multimer": False,
        "model_names": ["model_1_ptm"],
    }

    if sum(both_chains) == 0 and sum(fixed_chains) > 0 and sum(free_chains) > 0:
        protocol = "binder"
        target_chains = []
        binder_chains = []
        for n, x in enumerate(fixed_chains):
            if x:
                target_chains.append(chains[n])
            else:
                binder_chains.append(chains[n])
        af_model = mk_af_model(protocol="binder", **flags)
        prep_flags = {
            "target_chain": ",".join(target_chains),
            "binder_chain": ",".join(binder_chains),
            "rm_aa": rm_aa,
        }
        fixed_pos_arr = None

    elif sum(fixed_pos) > 0:
        protocol = "partial"
        af_model = mk_af_model(protocol="fixbb", use_templates=True, **flags)
        rm_template = np.array(fixed_pos) == 0
        prep_flags = {
            "chain": ",".join(chains),
            "rm_template": rm_template,
            "rm_template_seq": rm_template,
            "copies": copies,
            "homooligomer": copies > 1,
            "rm_aa": rm_aa,
        }
        fixed_pos_arr = np.array(fixed_pos)

    else:
        protocol = "fixbb"
        af_model = mk_af_model(protocol="fixbb", **flags)
        prep_flags = {
            "chain": ",".join(chains),
            "copies": copies,
            "homooligomer": copies > 1,
            "rm_aa": rm_aa,
        }
        fixed_pos_arr = None

    return protocol, af_model, prep_flags, fixed_pos_arr


def run_mpnn_only(cfg: MPNNStepConfig) -> dict:
    """
    MPNN-only:
      - 입력 구조(pdb)로 af_model.prep_inputs만 써서 컨텍스트 구성
      - MPNN sample만 수행
      - AlphaFold predict는 절대 안 함
    """
    exp = cfg.experiment_id
    out_dir = cfg.outputs_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rfd_dir = out_dir.parent / "step-rfdiffusion"
    pdb_paths = sorted(rfd_dir.glob(f"{exp}_*.pdb"))
    # for design_idx in range(cfg.num_designs):
    #     input_pdb = out_dir / f"{exp}_{design_idx}.pdb"
    # if not input_pdb.exists():
    #     raise FileNotFoundError(
    #         f"[proteinMPNN] input pdb not found: {input_pdb} "
    #         f"(먼저 step=rfdiffusion을 같은 experiment_id로 실행해야 함)"
    #     )

    contigs = _parse_contigs(cfg.contigs)
    rm_aa = cfg.rm_aa if (cfg.rm_aa and cfg.rm_aa.strip()) else None

    protocol, af_model, prep_flags, fixed_pos_arr = _infer_protocol_and_prep_flags(
        contigs=contigs,
        copies=cfg.copies,
        rm_aa=rm_aa,
    )

    mpnn_model = mk_mpnn_model()

    fasta_path = out_dir / f"{exp}_mpnn.fasta"
    csv_path = out_dir / f"{exp}_mpnn_results.csv"

    all_rows = []
    # RFdiffusion이 실제로 만들어 놓은 PDB 개수만큼 반복하면서,
    # 각 design(백본)에 대해 MPNN 샘플을 생성
    with open(fasta_path, "w") as f:
        for design_idx, input_pdb in enumerate(pdb_paths):
            if not input_pdb.exists():
                continue

            af_model.prep_inputs(str(input_pdb), **prep_flags)
            if protocol == "partial" and fixed_pos_arr is not None:
                p = np.where(fixed_pos_arr)[0]
                af_model.opt["fix_pos"] = p[p < af_model._len]

            mpnn_model.get_af_inputs(af_model)

            # 샘플 개수/배치 설정
            batch_size = min(8, cfg.num_seqs)
            num_batches = (cfg.num_seqs + batch_size - 1) // batch_size

            out = mpnn_model.sample(
                num=num_batches,
                batch=batch_size,
                temperature=float(cfg.mpnn_sampling_temp),
            )

            seqs = out.get("seq", [])
            scores = out.get("score", [])

            for i, seq in enumerate(seqs[:cfg.num_seqs]):
                seq_clean = re.sub(r"[^A-Z/]", "", seq).replace("/", "")
                score = float(scores[i]) if i < len(scores) else float("nan")
                f.write(
                    f">design={design_idx};mpnn_{i}|score={score:.6f}\n{seq_clean}\n"
                )
                all_rows.append(
                    {
                        "design": design_idx,
                        "n": i,
                        "mpnn_score": score,
                        "seq": seq_clean,
                    }
                )

    pd.DataFrame(all_rows).to_csv(csv_path, index=False)

    return {
        "input_pdb": None,
        "fasta": str(fasta_path),
        "csv": str(csv_path),
        "num_seqs": len(all_rows),   # 🔹 전체 생성된 서열 개수
        "protocol": protocol,
    }
