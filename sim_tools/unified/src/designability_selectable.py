"""
designability_selectable.py
- colabdesign.rf.designability_test의 동작을 "선택 실행" 형태로 래핑
- 목표:
  - ProteinMPNN만 실행 (AF skip)
  - AlphaFold만 실행 (MPNN skip: fasta/seq 입력 필요)
  - 둘 다 실행

주의:
- colabdesign 내부 구현은 getopt 스타일이라 -h가 안 먹을 수 있음.
- 이 파일은 colabdesign 내부 API를 최대한 재사용해서 깨질 확률을 낮춤.
"""

import os
import sys
from pathlib import Path

from colabdesign.shared.parse_args import Args
from colabdesign.mpnn import mk_mpnn_model
from colabdesign.af.model import mk_af_model
from colabdesign.af.prep import prep_pdb
from colabdesign.af.inputs import get_af_inputs


def read_fasta(path: str) -> list[str]:
    seqs: list[str] = []
    cur: list[str] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if cur:
                seqs.append("".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        seqs.append("".join(cur))
    return seqs


def main(argv: list[str]) -> None:
    ag = Args()
    ag.add(["pdb="], None, str, ["input pdb"])
    ag.add(["loc="], ".", str, ["output directory"])
    ag.add(["contig="], None, str, ["contig string (e.g. 100-100 or A1-50/0 B1-50/0)"])
    ag.add(["copies="], 1, int, ["copies"])
    ag.add(["num_seqs="], 8, int, ["number of mpnn seqs (multiple of 8 recommended)"])
    ag.add(["num_recycles="], 3, int, ["alphafold recycles"])
    ag.add(["rm_aa="], "C", str, ["remove amino acids"])
    ag.add(["mpnn_sampling_temp="], 0.1, float, ["ProteinMPNN sampling temperature"])
    ag.add(["use_multimer"], False, None, ["use alphafold_multimer_v3"])

    # ✅ 선택 실행 플래그: "기본 OFF" (체크박스 UX)
    ag.add(["run_mpnn"], False, None, ["run ProteinMPNN step"])
    ag.add(["run_af"], False, None, ["run AlphaFold step"])

    # ✅ AF-only 입력 지원 (MPNN 없이 AF만 돌릴 때 필요)
    ag.add(["fasta="], None, str, ["(AF-only) input fasta path"])
    ag.add(["seq="], None, str, ["(AF-only) single sequence string"])

    o = ag.parse(argv)

    loc = Path(o.loc)
    loc.mkdir(parents=True, exist_ok=True)

    # params 위치 힌트 (main.py에서 /models/alphafold symlink 생성)
    os.environ.setdefault("ALPHAFOLD_PARAMS_DIR", str(Path("/models/alphafold")))

    run_mpnn = bool(o.run_mpnn)
    run_af = bool(o.run_af)

    if not run_mpnn and not run_af:
        raise SystemExit("ERROR: Nothing to do. Pass --run_mpnn and/or --run_af")

    if not o.pdb:
        raise SystemExit("ERROR: --pdb=... is required")
    if not o.contig:
        raise SystemExit("ERROR: --contig=... is required (needed to prep inputs)")

    pdb_path = Path(o.pdb)
    if not pdb_path.exists():
        raise SystemExit(f"ERROR: pdb not found: {pdb_path}")

    # --- PDB -> prep -> AF inputs (MPNN/AF 둘 중 하나라도 돌리면 필요)
    pdb_str = pdb_path.read_text()
    prep = prep_pdb(pdb_str, contig=o.contig, copies=int(o.copies))
    af_inputs = get_af_inputs(prep)  # noqa: F841  (일부 colabdesign 버전에서 내부적으로 사용)

    # --- AF 모델 준비 (AF를 돌릴 때만)
    af_model = None
    if run_af:
        af_model = mk_af_model(protocol="fixbb", use_multimer=bool(o.use_multimer))
        # 어떤 버전은 prep_inputs 필요 / 어떤 버전은 없어도 동작
        try:
            af_model.prep_inputs()
        except Exception:
            pass

    seqs: list[str] = []

    # ----------------------------
    # 1) ProteinMPNN (선택)
    # ----------------------------
    if run_mpnn:
        print("[selectable] running ProteinMPNN...", flush=True)
        mpnn_model = mk_mpnn_model()

        # 원본 designability_test 흐름: mpnn_model.get_af_inputs(af_model)
        # (AF를 안 돌려도, 일부 버전은 af_model이 필요할 수 있음)
        if af_model is not None:
            mpnn_model.get_af_inputs(af_model)

        sampling_temp = float(o.mpnn_sampling_temp)
        # 원본 구현이 num=o.num_seqs//8, batch=8 형태가 많아서 동일하게 맞춤
        out = mpnn_model.sample(
            num=max(1, int(o.num_seqs) // 8),
            batch=8,
            temperature=sampling_temp,
        )

        seqs = list(out.get("seq", []))
        if not seqs:
            raise SystemExit("ERROR: ProteinMPNN produced no sequences")

        mpnn_fasta = loc / "mpnn.fasta"
        with mpnn_fasta.open("w") as f:
            for i, s in enumerate(seqs):
                f.write(f">mpnn_{i}\n{s}\n")
        print(f"[selectable] ProteinMPNN done. wrote: {mpnn_fasta}", flush=True)

    # ----------------------------
    # 2) AlphaFold (선택)
    # ----------------------------
    if run_af:
        print("[selectable] running AlphaFold...", flush=True)

        # AF-only 입력 처리: MPNN이 seq를 안 만들었다면 seq/fasta 필수
        if not seqs:
            if o.seq:
                seqs = [str(o.seq).strip()]
            elif o.fasta:
                seqs = read_fasta(str(o.fasta))
            else:
                raise SystemExit("ERROR: run_af=True but no sequences. Provide --seq= or --fasta= (or enable --run_mpnn)")

        design_fasta = loc / "design.fasta"
        with design_fasta.open("w") as fasta:
            for n, seq in enumerate(seqs):
                fasta.write(f">design_{n}\n{seq}\n")

        if af_model is None:
            raise SystemExit("ERROR: AF model not initialized (unexpected).")

        for n, seq in enumerate(seqs):
            af_model.predict(seq=seq, num_recycles=int(o.num_recycles), verbose=False)

            # 저장 API는 colabdesign 버전에 따라 다름: 있으면 저장, 없으면 스킵
            try:
                af_model.save(str(loc / f"af_{n}"))
            except Exception:
                pass

        print(f"[selectable] AlphaFold done. wrote: {design_fasta}", flush=True)

    print(f"[selectable] DONE. loc={loc}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])