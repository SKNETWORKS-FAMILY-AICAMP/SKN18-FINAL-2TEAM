"""
데이터 추출 모듈 (data_extractor.py)
==================================
이 모듈은 ClinicalTrials.gov JSON 파일에서 필요한 데이터를 추출합니다.
메타데이터(부가 정보)와 핵심 청크 데이터를 추출합니다.

사용 방법:
    from data_extractor import extract_metadata, extract_core_fields
    
    metadata = extract_metadata(study)
    core_fields = extract_core_fields(study)
"""

import sys
from pathlib import Path

# 상위 디렉토리를 경로에 추가
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from cleansing.text_cleaner import clean_text


def extract_metadata(study):
    """
    한 개의 study에서 메타데이터(부가 정보)를 추출합니다.
    
    메타데이터란?
    - 연구의 기본 정보 (제목, 상태, 날짜 등)
    - 핵심 내용이 아닌 부가적인 정보
    - 예: 연구 제목, 연구 상태, 시작 날짜 등
    
    Args:
        study (dict): JSON 파일에서 읽은 하나의 study 데이터
        
    Returns:
        dict: 추출된 메타데이터 딕셔너리
        
    예시:
        >>> study = {"protocolSection": {...}}
        >>> metadata = extract_metadata(study)
        >>> metadata["nctId"]
        'NCT01234567'
    """
    ps = study.get("protocolSection", {})
    
    meta = {}
    
    # 1. 연구 식별 정보
    meta["nctId"] = ps.get("identificationModule", {}).get("nctId", "")
    meta["officialTitle"] = ps.get("identificationModule", {}).get("officialTitle", "")
    
    # 2. 연구 설명 (요약)
    meta["briefSummary"] = clean_text(ps.get("descriptionModule", {}).get("briefSummary", ""))
    
    # 3. 조건 및 키워드
    meta["conditions"] = ps.get("conditionsModule", {}).get("conditions", [])
    meta["keywords"] = ps.get("conditionsModule", {}).get("keywords", [])
    
    # 4. 중재(치료) 방법
    interventions = ps.get("armsInterventionsModule", {}).get("interventions", [])
    meta["interventions"] = [i.get("name", "") for i in interventions]
    
    # 5. 연구 설계 정보
    meta["studyType"] = ps.get("designModule", {}).get("studyType", "")
    meta["phases"] = ps.get("designModule", {}).get("phases", [])
    meta["primaryPurpose"] = ps.get("designModule", {}).get("designInfo", {}).get("primaryPurpose", "")
    
    # 6. 연구 상태
    meta["overallStatus"] = ps.get("statusModule", {}).get("overallStatus", "")
    
    # 7. 참가자 수
    meta["enrollmentCount"] = ps.get("designModule", {}).get("enrollmentInfo", {}).get("count", 0)
    
    # 8. 날짜 정보
    meta["startDate"] = ps.get("statusModule", {}).get("startDateStruct", {}).get("date", "")
    meta["completionDate"] = ps.get("statusModule", {}).get("completionDateStruct", {}).get("date", "")
    
    # 9. 후원자 정보
    meta["leadSponsor"] = ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", "")
    
    # 10. 위치 정보 (국가)
    locations = ps.get("contactsLocationsModule", {}).get("locations", [])
    meta["country"] = locations[0].get("country", "") if locations else ""
    
    # 11. 군(arm) 정보
    arm_groups = ps.get("armsInterventionsModule", {}).get("armGroups", [])
    meta["armLabel"] = arm_groups[0].get("label", "") if arm_groups else ""
    
    return meta


def extract_core_fields(study):
    """
    한 개의 study에서 핵심 청크 데이터를 추출합니다.
    
    핵심 필드란?
    - 연구의 주요 내용을 담은 중요한 텍스트
    - 자세한 설명, 결과, 자격 기준 등
    - 나중에 검색이나 분석에 사용될 주요 내용
    
    Args:
        study (dict): JSON 파일에서 읽은 하나의 study 데이터
        
    Returns:
        dict: 추출된 핵심 필드 딕셔너리
            - detailedDescription: 자세한 설명
            - armGroups: 치료군 설명
            - primaryOutcomes: 주요 결과
            - secondaryOutcomes: 부가 결과
            - eligibilityCriteria: 참가 자격 기준
            
    예시:
        >>> study = {"protocolSection": {...}}
        >>> core_fields = extract_core_fields(study)
        >>> core_fields["detailedDescription"]
        '이 연구는...'
    """
    ps = study.get("protocolSection", {})
    
    core_fields = {}
    
    # 1. 자세한 설명 (detailedDescription)
    detailed_desc = clean_text(ps.get("descriptionModule", {}).get("detailedDescription", ""))
    core_fields["detailedDescription"] = detailed_desc
    
    # 2. 치료군 설명 (armGroups)
    # 여러 개의 arm이 있을 수 있으므로 자연스럽게 연결
    arm_groups_list = []
    for arm in ps.get("armsInterventionsModule", {}).get("armGroups", []):
        arm_desc = clean_text(arm.get("description", ""))
        if arm_desc:
            arm_groups_list.append(arm_desc)
    arm_groups_text = ". ".join(arm_groups_list)  # 자연스러운 문장 연결
    core_fields["armGroups"] = arm_groups_text
    
    # 3. 주요 결과 (primaryOutcomes)
    primary_outcomes_list = []
    for po in ps.get("outcomesModule", {}).get("primaryOutcomes", []):
        po_desc = clean_text(po.get("description", ""))
        if po_desc:
            primary_outcomes_list.append(po_desc)
    primary_outcomes_text = ". ".join(primary_outcomes_list)  # 자연스러운 문장 연결
    core_fields["primaryOutcomes"] = primary_outcomes_text
    
    # 4. 부가 결과 (secondaryOutcomes)
    secondary_outcomes_list = []
    for so in ps.get("outcomesModule", {}).get("secondaryOutcomes", []):
        so_desc = clean_text(so.get("description", ""))
        if so_desc:
            secondary_outcomes_list.append(so_desc)
    secondary_outcomes_text = ". ".join(secondary_outcomes_list)  # 자연스러운 문장 연결
    core_fields["secondaryOutcomes"] = secondary_outcomes_text
    
    # 5. 참가 자격 기준 (eligibilityCriteria)
    eligibility = clean_text(ps.get("eligibilityModule", {}).get("eligibilityCriteria", ""))
    core_fields["eligibilityCriteria"] = eligibility
    
    return core_fields


def combine_core_fields(core_fields):
    """
    여러 핵심 필드를 하나의 텍스트로 합칩니다.
    자연스러운 문장 형태를 유지하며 필드명 접두사 없이 내용만 연결합니다.
    
    Args:
        core_fields (dict): extract_core_fields()에서 반환된 딕셔너리
        
    Returns:
        str: 합쳐진 텍스트
        
    예시:
        >>> fields = {"detailedDescription": "설명1", "armGroups": "설명2"}
        >>> combined = combine_core_fields(fields)
        >>> print(combined)
        '설명1. 설명2.'
    """
    combined_parts = []
    
    # 각 필드가 있으면 내용만 추가 (필드명 접두사 없이, 자연스러운 문장 형태 유지)
    if core_fields.get("detailedDescription"):
        combined_parts.append(core_fields['detailedDescription'])
    
    if core_fields.get("armGroups"):
        combined_parts.append(core_fields['armGroups'])
    
    if core_fields.get("primaryOutcomes"):
        combined_parts.append(core_fields['primaryOutcomes'])
    
    if core_fields.get("secondaryOutcomes"):
        combined_parts.append(core_fields['secondaryOutcomes'])
    
    if core_fields.get("eligibilityCriteria"):
        combined_parts.append(core_fields['eligibilityCriteria'])
    
    # 각 부분을 ". "로 연결 (자연스러운 문장 구분)
    return ". ".join(combined_parts) if combined_parts else ""


if __name__ == "__main__":
    """
    데이터 추출 모듈 단독 실행 시 테스트를 수행합니다.
    """
    print("=" * 60)
    print("데이터 추출 모듈 테스트")
    print("=" * 60)
    
    # 샘플 study 데이터
    sample_study = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT12345678",
                "officialTitle": "Test Study"
            },
            "descriptionModule": {
                "briefSummary": "This is a brief summary.",
                "detailedDescription": "This is a detailed description."
            },
            "conditionsModule": {
                "conditions": ["Condition 1", "Condition 2"],
                "keywords": ["keyword1", "keyword2"]
            },
            "armsInterventionsModule": {
                "interventions": [{"name": "Intervention 1"}],
                "armGroups": [{"description": "Arm group description"}]
            },
            "designModule": {
                "studyType": "Interventional",
                "phases": ["Phase 1"],
                "designInfo": {"primaryPurpose": "Treatment"},
                "enrollmentInfo": {"count": 100}
            },
            "statusModule": {
                "overallStatus": "Recruiting",
                "startDateStruct": {"date": "2024-01-01"},
                "completionDateStruct": {"date": "2024-12-31"}
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Test Sponsor"}
            },
            "contactsLocationsModule": {
                "locations": [{"country": "United States"}]
            },
            "outcomesModule": {
                "primaryOutcomes": [{"description": "Primary outcome description"}],
                "secondaryOutcomes": [{"description": "Secondary outcome description"}]
            },
            "eligibilityModule": {
                "eligibilityCriteria": "Inclusion criteria here"
            }
        }
    }
    
    print("\n메타데이터 추출 테스트:")
    metadata = extract_metadata(sample_study)
    print(f"  NCT ID: {metadata.get('nctId')}")
    print(f"  제목: {metadata.get('officialTitle')}")
    print(f"  상태: {metadata.get('overallStatus')}")
    
    print("\n핵심 필드 추출 테스트:")
    core_fields = extract_core_fields(sample_study)
    print(f"  자세한 설명: {core_fields.get('detailedDescription')[:50]}...")
    print(f"  자격 기준: {core_fields.get('eligibilityCriteria')[:50]}...")
    
    print("\n필드 결합 테스트:")
    combined = combine_core_fields(core_fields)
    print(f"  결합된 텍스트 길이: {len(combined)} 문자")
    print(f"  미리보기: {combined[:100]}...")
    
    print("\n✓ 테스트 완료")
    print("=" * 60)





