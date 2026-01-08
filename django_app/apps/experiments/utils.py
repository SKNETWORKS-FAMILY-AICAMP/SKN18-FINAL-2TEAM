"""
실험 관련 유틸리티 함수
상태 업데이트, 멱등성 보장 등
"""
import logging
from django.db import transaction
from django.utils import timezone
from typing import Optional
from pathlib import Path
from apps.experiments.models import ExperimentResult
from apps.core.utils.s3_utils import  get_s3_url

logger = logging.getLogger(__name__)

def update_experiment_status(
    experiment_sid: int,
    status: str,
    progress: Optional[int] = None,
    error_message: Optional[str] = None
):
    """
    실험 상태 업데이트 (멱등성 보장)
    
    Args:
        experiment_sid: 실험 ID
        status: 상태 ('E': 준비, 'R': 진행중, 'C': 완료, 'F': 실패)
        progress: 진행률 (0-100, 선택)
        error_message: 에러 메시지 (실패 시, 선택)
    """
    from apps.experiments.models import Experiment
    
    with transaction.atomic():
        # SELECT FOR UPDATE로 동시성 제어
        experiment = Experiment.objects.select_for_update().get(
            experiment_sid=experiment_sid
        )
        
        # 상태 전이 검증
        valid_transitions = {
            'E': ['R', 'F'],  # 준비 → 진행중/실패
            'R': ['C', 'F'],  # 진행중 → 완료/실패
            'C': [],  # 완료는 최종 상태
            'F': [],  # 실패는 최종 상태
        }
        
        if status not in valid_transitions.get(experiment.status, []):
            logger.warning(
                f"Invalid status transition: {experiment.status} → {status} "
                f"for experiment {experiment_sid}"
            )
            return
        
        # 업데이트
        experiment.status = status
        if progress is not None:
            experiment.progress = progress
        experiment.updated_at = timezone.now()
        experiment.save()
        
        logger.info(
            f"Experiment {experiment_sid} status updated: {status}, "
            f"progress={progress}%"
        )


def _parse_dt_and_step_from_expected(expected_local: str) -> tuple[str, str]:
    """
    /workspace/.../outputs/simulations/dt-2026-01-07/pipeline-39/step-rfdiffusion/39_0.pdb
    이런 local 경로에서 dt(2026-01-07), step(rfdiffusion/proteinMPNN/alphafold) 추출.
    """
    p = Path(expected_local)
    parts = p.parts
    # 'simulations/dt-YYYY-MM-DD/pipeline-<id>/step-<step>' 패턴 가정
    try:
        idx = parts.index("simulations")
    except ValueError:
        raise ValueError(f"'simulations' segment not found in path: {expected_local}")

    dt_part = parts[idx + 1]          # dt-2026-01-07
    step_part = parts[idx + 3]        # step-rfdiffusion 등

    if not dt_part.startswith("dt-") or not step_part.startswith("step-"):
        raise ValueError(f"Unexpected path format: {expected_local}")

    dt = dt_part.replace("dt-", "")   # 2026-01-07
    step_cli = step_part.replace("step-", "")  # rfdiffusion / proteinMPNN / alphafold
    return dt, step_cli


def _s3_step_from_cli_step(step_cli: str) -> str:
    """
    main.py / s3_uploader.py 와 동일한 S3 step 이름으로 변환.
    """
    if step_cli == "protein_mpnn":
        return "proteinMPNN"
    if step_cli == "alphafold3":
        return "alphafold"
    # rfdiffusion 은 그대로 사용
    return step_cli


def _build_simulation_s3_prefix(dt: str, experiment_sid: int, s3_step: str) -> str:
    """
    simulations/dt=YYYY-MM-DD/pipeline=<id>/step=<step>
    """
    return f"simulations/dt={dt}/pipeline={experiment_sid}/step={s3_step}".strip("/")


@transaction.atomic
def register_experiment_results_for_step(
    experiment_sid: int,
    step_api: str,
    expected_local_path: str,
    num_designs: int | None = None,   # rfdiffusion numSteps
    num_seqs: int | None = None,      # ProteinMPNN Number of Sequences
) -> list[ExperimentResult]:
    """
    RunPod 컨테이너가 업로드한 S3 결과 파일들을
    S3 키 규칙만으로 URL(file_path)을 계산해 t_experiment_result 에 저장한다.
    S3 API(boto3)는 호출하지 않고, file_size는 None으로 둔다.
    """
    dt, _ = _parse_dt_and_step_from_expected(expected_local_path)
    s3_step = _s3_step_from_cli_step(step_api)  # rfdiffusion / proteinMPNN / alphafold
    prefix = _build_simulation_s3_prefix(dt, experiment_sid, s3_step)

    exp_id_str = str(experiment_sid).strip()
    results: list[ExperimentResult] = []

    # 1) RFdiffusion 요약: expId_i.pdb / expId_i.trb / expId_all_results.zip
    if s3_step == "rfdiffusion":
        n = int(num_designs or 1)
        for i in range(n):
            for filename, result_type, result_name in [
                (f"{exp_id_str}_{i}.pdb", "PDB",   f"RFdiffusion 구조 #{i}"),
                (f"{exp_id_str}_{i}.trb", "OTHER", f"RFdiffusion TRB #{i}"),
            ]:
                key = f"{prefix}/{filename}"
                url = get_s3_url(key)
                results.append(
                    ExperimentResult.objects.create(
                        experiment_id=experiment_sid,
                        result_name=result_name,
                        result_type=result_type,
                        file_size=None,
                        file_path=url,
                    )
                )

        zip_name = f"{exp_id_str}_all_results.zip"
        zip_key = f"{prefix}/{zip_name}"
        zip_url = get_s3_url(zip_key)
        results.append(
            ExperimentResult.objects.create(
                experiment_id=experiment_sid,
                result_name="RFdiffusion 전체 결과 ZIP",
                result_type="OTHER",
                file_size=None,
                file_path=zip_url,
            )
        )

    # 2) ProteinMPNN 요약: expId_mpnn.fasta / expId_mpnn_results.csv
    elif s3_step == "proteinMPNN":
        for filename, result_type, result_name in [
            (f"{exp_id_str}_mpnn.fasta", "FASTA", "서열 데이터 (MPNN FASTA)"),
            (f"{exp_id_str}_mpnn_results.csv", "CSV", "서열 분석 결과 (MPNN CSV)"),
        ]:
            key = f"{prefix}/{filename}"
            url = get_s3_url(key)
            results.append(
                ExperimentResult.objects.create(
                    experiment_id=experiment_sid,
                    result_name=result_name,
                    result_type=result_type,
                    file_size=None,
                    file_path=url,
                )
            )

    # 3) AlphaFold 요약: best / zip / csv
    elif s3_step == "alphafold":
        for filename, result_type, result_name in [
            (f"{exp_id_str}_af_best.pdb", "PDB",   "AlphaFold 베스트 구조"),
            (f"{exp_id_str}_af_all_pdb.zip", "OTHER", "AlphaFold 전체 구조 ZIP"),
            (f"{exp_id_str}_af_results.csv", "CSV", "AlphaFold 결과 테이블"),
        ]:
            key = f"{prefix}/{filename}"
            url = get_s3_url(key)
            results.append(
                ExperimentResult.objects.create(
                    experiment_id=experiment_sid,
                    result_name=result_name,
                    result_type=result_type,
                    file_size=None,
                    file_path=url,
                )
            )

        # 개별 구조 PDB: af_d{design}_s{seq}_k4.pdb  (k=4 고정)
        if num_designs is not None and num_seqs is not None:
            for d in range(num_designs):
                for s_idx in range(num_seqs):
                    filename = f"af_d{d}_s{s_idx}_k4.pdb"
                    key = f"{prefix}/{filename}"
                    url = get_s3_url(key)
                    results.append(
                        ExperimentResult.objects.create(
                            experiment_id=experiment_sid,
                            result_name=f"AlphaFold 구조 {filename}",
                            result_type="PDB",
                            file_size=None,
                            file_path=url,
                        )
                    )

    return results


# @transaction.atomic
# def register_experiment_results_for_step(
#     experiment_sid: int,
#     step_api: str,             # "rfdiffusion" / "protein_mpnn" / "alphafold3"
#     expected_local_path: str,  # unified /status 가 준 expected_pdb 로컬 경로
# ) -> list[ExperimentResult]:
#     """
#     RunPod 컨테이너가 업로드한 S3 결과 파일들을
#     t_experiment_result 에 URL(file_path) + file_size 기준으로 저장.
#     S3 list_objects_v2 로 실제 존재하는 객체만 기록한다.
#     """
#     dt, _ = _parse_dt_and_step_from_expected(expected_local_path)
#     s3_step = _s3_step_from_cli_step(step_api)  # rfdiffusion / proteinMPNN / alphafold
#     prefix = _build_simulation_s3_prefix(dt, experiment_sid, s3_step)

#     s3 = get_s3_client()
#     bucket = get_s3_bucket()

#     exp_id_str = str(experiment_sid).strip()
#     results: list[ExperimentResult] = []

#     continuation: str | None = None
#     while True:
#         params: dict = {"Bucket": bucket, "Prefix": f"{prefix}/"}
#         if continuation:
#             params["ContinuationToken"] = continuation

#         resp = s3.list_objects_v2(**params)
#         for obj in resp.get("Contents", []):
#             key = obj["Key"]
#             name = key.split("/")[-1]
#             url = get_s3_url(key, bucket=bucket)
#             size = obj.get("Size")
#             created = False

#             # 1) RFdiffusion: expId_i.pdb / expId_i.trb / expId_all_results.zip
#             if s3_step == "rfdiffusion":
#                 lower = name.lower()
#                 if lower.endswith(".pdb") and name.startswith(f"{exp_id_str}_"):
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name=f"RFdiffusion 구조 {name}",
#                             result_type="PDB",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True
#                 elif lower.endswith(".trb") and name.startswith(f"{exp_id_str}_"):
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name=f"RFdiffusion TRB {name}",
#                             result_type="OTHER",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True
#                 elif name == f"{exp_id_str}_all_results.zip":
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name="RFdiffusion 전체 결과 ZIP",
#                             result_type="OTHER",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True

#             # 2) ProteinMPNN: expId_mpnn.fasta / expId_mpnn_results.csv
#             elif s3_step == "proteinMPNN":
#                 if name == f"{exp_id_str}_mpnn.fasta":
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name="서열 데이터 (MPNN FASTA)",
#                             result_type="FASTA",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True
#                 elif name == f"{exp_id_str}_mpnn_results.csv":
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name="서열 분석 결과 (MPNN CSV)",
#                             result_type="CSV",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True

#             # 3) AlphaFold: best / zip / csv / af_d*_s*_k*.pdb
#             elif s3_step == "alphafold":
#                 if name == f"{exp_id_str}_af_best.pdb":
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name="AlphaFold 베스트 구조",
#                             result_type="PDB",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True
#                 elif name == f"{exp_id_str}_af_all_pdb.zip":
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name="AlphaFold 전체 구조 ZIP",
#                             result_type="OTHER",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True
#                 elif name == f"{exp_id_str}_af_results.csv":
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name="AlphaFold 결과 테이블",
#                             result_type="CSV",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True
#                 # 개별 구조 PDB: af_d0_s0_k0.pdb 같은 형태
#                 elif name.lower().endswith(".pdb") and name.startswith("af_d"):
#                     results.append(
#                         ExperimentResult.objects.create(
#                             experiment_id=experiment_sid,
#                             result_name=f"AlphaFold 구조 {name}",
#                             result_type="PDB",
#                             file_size=size,
#                             file_path=url,
#                         )
#                     )
#                     created = True

#             # 4) 공통 로그(.log) - 위에서 처리 안 된 경우만
#             if (not created) and name.lower().endswith(".log"):
#                 results.append(
#                     ExperimentResult.objects.create(
#                         experiment_id=experiment_sid,
#                         result_name=f"{s3_step} 로그 ({name})",
#                         result_type="LOG",
#                         file_size=size,
#                         file_path=url,
#                     )
#                 )

#         if not resp.get("IsTruncated"):
#             break
#         continuation = resp.get("NextContinuationToken")

#     return results

