import os
from pathlib import Path

import pandas as pd
import numpy as np

# ====================================
# 0. 파일 경로 설정
# ====================================
ROOT_DIR = Path(__file__).resolve().parents[4]
ENT_DIR = ROOT_DIR / "data" / "entities"

TS_ENTITY_MASTER_FILE = ENT_DIR / "pubmed" / "ts_entity_master.csv"
TS_MENTIONS_FILE      = ENT_DIR / "pubmed"/ "ts_section_entity_mentions.csv"
CLIN_META_FILE        = ENT_DIR / "nih" / "ts_mapped_metadata_entities.csv"
ENTITY_MASTER_OUT  = ENT_DIR / "ts_global_entity_master.csv"
MENTION_MASTER_OUT = ENT_DIR / "ts_global_mention_master.csv"


# ====================================
# 1. 임상 entityId 정규화
#    예: CHEBI:CHEBI:4672 -> CHEBI:4672
# ====================================
def normalize_entity_id(eid: str):
    if not isinstance(eid, str):
        return eid
    parts = eid.split(":")
    if len(parts) >= 3 and parts[0] == parts[1]:
        # CHEBI:CHEBI:4672, HP:HP:0030646 같은 패턴
        return f"{parts[0]}:{parts[2]}"
    return eid


# ====================================
# 2. global_entity_master 생성
#    (논문 master + 임상 meta 엔티티 통합)
# ====================================
def build_global_entity_master():
    # 2-1) 기존 논문 entity master 로드
    if not os.path.exists(TS_ENTITY_MASTER_FILE):
        raise FileNotFoundError(TS_ENTITY_MASTER_FILE)

    ts_ent = pd.read_csv(TS_ENTITY_MASTER_FILE)

    required_ent_cols = [
        "entity_id",
        "normalized_entity",
        "entity_type",
        "umls_cui",
        "primekg_label",
        "primekg_source_db",
        "primekg_source_id",
        "match_score",
    ]
    for c in required_ent_cols:
        if c not in ts_ent.columns:
            raise ValueError(f"ts_entity_master.csv 에 '{c}' 컬럼이 필요합니다.")

    # primekg_source_db + primekg_source_id -> "CHEBI:4672" 같은 key
    ts_ent["primekg_key"] = np.where(
        ts_ent["primekg_source_db"].notna() & ts_ent["primekg_source_id"].notna(),
        ts_ent["primekg_source_db"].astype(str)
        + ":"
        + ts_ent["primekg_source_id"].astype(str),
        None,
    )
    key_map = (
        ts_ent[ts_ent["primekg_key"].notna()]
        .drop_duplicates(subset=["primekg_key"])
        .set_index("primekg_key")["entity_id"]
    )

    # 2-2) 임상 meta 엔티티 로드 (없으면 PubMed 기준으로만 global master 생성)
    if not os.path.exists(CLIN_META_FILE):
        print(f"⚠ 임상(meta) 엔티티 파일 없음: {CLIN_META_FILE}")
        print("  → PubMed ts_entity_master만으로 global_entity_master를 생성합니다.")
        entity_master_global = ts_ent.copy()
        entity_master_global.to_csv(ENTITY_MASTER_OUT, index=False)
        # 임상 엔티티 매핑이 없으므로 빈 매핑 반환
        entityid_to_entityid = pd.Series(dtype=object)
        return entity_master_global, entityid_to_entityid

    clin_meta = pd.read_csv(CLIN_META_FILE)

    for c in ["entityId", "entityName", "entityType"]:
        if c not in clin_meta.columns:
            raise ValueError(
                f"nih_mapped_metadata_entities_1208.csv 에 '{c}' 컬럼이 필요합니다."
            )

    clin_meta["entityId_norm"] = clin_meta["entityId"].apply(normalize_entity_id)

    clin_all = (
        clin_meta[["entityId_norm", "entityName", "entityType"]]
        .dropna(subset=["entityId_norm"])
        .drop_duplicates(subset=["entityId_norm"])
        .reset_index(drop=True)
    )

    print(f"🧬 임상(meta) 유니크 entityId_norm 개수: {len(clin_all)}")

    # 2-3) 논문 master의 primekg_key와 매칭
    #      (이미 있는 건 entity_id 재사용)
    clin_all["entity_id"] = clin_all["entityId_norm"].map(key_map)

    # 2-4) 매칭 안된 임상 엔티티에 새 entity_id 부여
    max_existing_num = (
        ts_ent["entity_id"].str.extract(r"E(\d+)", expand=False).astype(int).max()
    )
    if pd.isna(max_existing_num):
        max_existing_num = 0

    new_ents = clin_all[clin_all["entity_id"].isna()].copy().reset_index(drop=True)
    new_ents["ent_num"] = new_ents.index + max_existing_num + 1
    new_ents["entity_id"] = new_ents["ent_num"].apply(lambda n: f"E{n:06d}")

    def get_source_db(eid_norm: str):
        if not isinstance(eid_norm, str):
            return None
        return eid_norm.split(":", 1)[0]

    def get_source_id(eid_norm: str):
        if not isinstance(eid_norm, str):
            return None
        parts = eid_norm.split(":", 1)
        return parts[1] if len(parts) == 2 else None

    new_entity_rows = pd.DataFrame(
        {
            "entity_id": new_ents["entity_id"],
            "normalized_entity": new_ents["entityName"],
            "entity_type": new_ents["entityType"],
            "umls_cui": np.nan,
            "primekg_label": np.nan,
            "primekg_source_db": new_ents["entityId_norm"].apply(get_source_db),
            "primekg_source_id": new_ents["entityId_norm"].apply(get_source_id),
            "match_score": np.nan,
        }
    )

    print(f"➕ 새로 추가되는 임상(meta) 엔티티 수: {len(new_entity_rows)}")

    # 2-5) 최종 global_entity_master 구성
    ent_cols_order = [
        "entity_id",
        "normalized_entity",
        "entity_type",
        "umls_cui",
        "primekg_label",
        "primekg_source_db",
        "primekg_source_id",
        "match_score",
    ]

    entity_master_global = pd.concat(
        [ts_ent[ent_cols_order], new_entity_rows[ent_cols_order]],
        ignore_index=True,
    )

    entity_master_global.to_csv(ENTITY_MASTER_OUT, index=False)
    print(
        f"✅ global_entity_master 저장: {ENTITY_MASTER_OUT} "
        f"(총 {len(entity_master_global)} 개)"
    )

    # 2-6) 임상 entityId_norm → entity_id 매핑 (mention에서 사용)
    clin_all2 = pd.concat(
        [
            # 기존 매칭된 것
            clin_all[clin_all["entityId_norm"].isin(key_map.index)][
                ["entityId_norm", "entity_id"]
            ],
            # 새로 만든 것
            new_ents[["entityId_norm", "entity_id"]],
        ],
        ignore_index=True,
    ).drop_duplicates(subset=["entityId_norm"])

    entityid_to_entityid = clin_all2.set_index("entityId_norm")["entity_id"]
    return entity_master_global, entityid_to_entityid


# ====================================
# 3. global_mention_master 생성
#    (논문 mention + 임상(meta) mention)
# ====================================
def build_global_mention_master(entityid_to_entityid: pd.Series):
    # -------- A) 논문 mention 표준화 --------
    if not os.path.exists(TS_MENTIONS_FILE):
        raise FileNotFoundError(TS_MENTIONS_FILE)

    ts_mentions = pd.read_csv(TS_MENTIONS_FILE)

    required_cols = [
        "mention_id",
        "section_id",
        "raw_keyword",
        "normalized_entity",
        "entity_type",
        "umls_cui",
        "entity_id",
    ]
    for c in required_cols:
        if c not in ts_mentions.columns:
            raise ValueError(
                f"ts_section_entity_mentions.csv 에 '{c}' 컬럼이 필요합니다."
            )

    paper = ts_mentions.copy()
    # section_id: "31013562_sec0" -> doc_id: "31013562"
    paper["doc_id"] = paper["section_id"].astype(str).str.split("_", n=1, expand=True)[
        0
    ]
    paper["location_id"] = paper["section_id"]
    paper["source"] = "paper"
    paper["raw_text"] = paper["raw_keyword"]
    paper["normalized_text"] = paper["normalized_entity"]

    paper_mention = paper[
        [
            "mention_id",
            "source",
            "doc_id",
            "location_id",
            "raw_text",
            "normalized_text",
            "entity_id",
            "entity_type",
            "umls_cui",
        ]
    ]

    print(f"📄 논문 mention 수: {len(paper_mention)}")

    # 논문 mention_id 마지막 번호 (M0000001 -> 1) 파악
    last_num = (
        paper_mention["mention_id"]
        .str.extract(r"M(\d+)", expand=False)
        .astype(int)
        .max()
    )
    if pd.isna(last_num):
        last_num = 0

    # -------- B) 임상(meta) mention 표준화 --------
    clin_meta = pd.read_csv(CLIN_META_FILE)

    for c in ["nctId", "sourceType", "entityId", "entityName"]:
        if c not in clin_meta.columns:
            raise ValueError(
                f"nih_mapped_metadata_entities_1208.csv 에 '{c}' 컬럼이 필요합니다."
            )

    clin_meta["entityId_norm"] = clin_meta["entityId"].apply(normalize_entity_id)
    clin_meta["entity_id"] = clin_meta["entityId_norm"].map(entityid_to_entityid)

    clin = clin_meta.copy()
    clin["source"] = "clinical_meta"
    clin["doc_id"] = clin["nctId"]
    clin["location_id"] = clin["sourceType"]
    clin["raw_text"] = clin["entityName"]
    clin["normalized_text"] = clin["entityName"]
    clin["umls_cui"] = None

    clin_std = clin[
        [
            "source",
            "doc_id",
            "location_id",
            "raw_text",
            "normalized_text",
            "entity_id",
            "entityType",
            "umls_cui",
        ]
    ].rename(columns={"entityType": "entity_type"})

    # 임상 mention_id 채번 (논문 다음 번호부터)
    clin_std = clin_std.reset_index(drop=True)
    clin_std["mention_id"] = clin_std.index + last_num + 1
    clin_std["mention_id"] = clin_std["mention_id"].apply(lambda n: f"M{n:07d}")

    clin_std = clin_std[
        [
            "mention_id",
            "source",
            "doc_id",
            "location_id",
            "raw_text",
            "normalized_text",
            "entity_id",
            "entity_type",
            "umls_cui",
        ]
    ]

    print(f"🏥 임상(meta) mention 수: {len(clin_std)}")

    # -------- C) 최종 global_mention_master --------
    mention_master_global = pd.concat(
        [paper_mention, clin_std], ignore_index=True
    )

    n_unique_mentions = mention_master_global["mention_id"].nunique()
    n_missing_entity = mention_master_global["entity_id"].isna().sum()

    print(f"🔎 mention_id 유니크: {n_unique_mentions} / 총 {len(mention_master_global)}")
    print(f"🔎 entity_id 누락 개수: {n_missing_entity}")

    mention_master_global.to_csv(MENTION_MASTER_OUT, index=False)
    print(f"✅ global_mention_master 저장: {MENTION_MASTER_OUT}")


def main():
    entity_master_global, entityid_to_entityid = build_global_entity_master()
    build_global_mention_master(entityid_to_entityid)


if __name__ == "__main__":
    main()
