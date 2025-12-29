# Generated manually - Update guide fields and help_text after they are added
import json
from django.db import migrations


def update_guide_fields_and_help_text(apps, schema_editor):
    """Update guide fields and help_text for existing tools"""
    ExperimentTool = apps.get_model('experiments', 'ExperimentTool')
    ExperimentToolOption = apps.get_model('experiments', 'ExperimentToolOption')
    
    # Update guide fields for each tool
    tool_updates = {
        'RFdiffusion': {
            'guide_prerequisites': json.dumps([
                '목표 설계 목적(결합/효소/구조 안정화 등) 정의',
                '필요 시 고정 모티프/바인딩 잔기/길이 범위 등 제약 조건 준비',
            ], ensure_ascii=False),
            'guide_inputs': json.dumps([
                '설계 제약 조건(길이, 모티프 고정, 대칭성, 스캐폴드 등)',
                '선택: 기존 구조(PDB) 또는 모티프 좌표',
            ], ensure_ascii=False),
            'guide_outputs': json.dumps([
                '생성된 단백질 백본 구조(PDB)',
                '선택: 생성 로그/스코어/샘플 메타데이터',
            ], ensure_ascii=False),
            'guide_limitations': json.dumps([
                '\'구조 생성\'만으로 기능이 보장되지 않습니다(후속 서열 설계/검증 필요).',
                '제약을 과도하게 걸면 다양성이 급감하거나 실패율이 늘 수 있습니다.',
            ], ensure_ascii=False),
            'guide_recommended_workflow': json.dumps([
                'RFdiffusion(백본 생성) → ProteinMPNN(서열 설계) → AlphaFold2(접힘 검증) → Docking(DiffDock/Vina) → 실험/추가 최적화',
            ], ensure_ascii=False),
            'option_help': {
                'temperature': '높을수록 다양성 증가, 낮을수록 보수적으로 생성됩니다.',
                'numSteps': '스텝이 많을수록 계산량이 늘지만 더 안정적인 샘플이 나올 수 있습니다.',
                'guidanceScale': '조건(제약)을 얼마나 강하게 따를지 제어합니다.',
            },
        },
        'AlphaFold3': {
            'guide_prerequisites': json.dumps([
                '입력 서열(FASTA) 준비',
                '복합체인 경우 체인별 서열 분리 및 multimer 모드 고려',
            ], ensure_ascii=False),
            'guide_inputs': json.dumps([
                'FASTA 서열(단일/복수 체인)',
                '선택: 템플릿(구조) 활용 여부(useTemplates)',
            ], ensure_ascii=False),
            'guide_outputs': json.dumps([
                '예측 구조(PDB)',
                '신뢰도 지표(pLDDT, PAE 등 구현에 따라 제공)',
            ], ensure_ascii=False),
            'guide_limitations': json.dumps([
                '예측 구조는 \'가능한 접힘\'에 대한 추정이며, 실제 조건(리간드/환경/변형)에 따라 달라질 수 있습니다.',
                '복합체(multimer)는 체인 구성/상호작용 정보에 따라 품질 변동이 큽니다.',
            ], ensure_ascii=False),
            'guide_recommended_workflow': json.dumps([
                'ProteinMPNN/RFdiffusion 결과 서열 → AlphaFold3로 접힘 검증 → pLDDT/PAE 기반 필터링 → 후속 docking/실험 설계',
            ], ensure_ascii=False),
            'option_help': {
                'mode': '단일 단백질이면 monomer, 복합체면 multimer를 선택합니다.',
                'maxRecycles': 'recycle이 늘면 품질이 좋아질 수 있지만 시간이 증가합니다.',
                'useTemplates': '구조 템플릿을 사용할지 여부(가능하면 예측 안정성에 도움).',
            },
        },
        'ProteinMPNN': {
            'guide_prerequisites': json.dumps([
                '입력 백본 구조(PDB) 준비(체인/잔기 번호 정리 권장)',
                '기능성/결합부위 등 반드시 유지해야 하는 잔기 위치가 있다면 fixedPositions로 고정할 계획 수립',
            ], ensure_ascii=False),
            'guide_inputs': json.dumps([
                '단백질 백본 구조(PDB)',
                '설계 대상 체인(designChains)',
                '선택: 고정 잔기 목록(fixedPositions), 제외 아미노산(omitAAs)',
            ], ensure_ascii=False),
            'guide_outputs': json.dumps([
                '설계된 서열(FASTA/JSON)',
                '선택: 서열별 점수/로그(구현에 따라 제공)',
            ], ensure_ascii=False),
            'guide_limitations': json.dumps([
                '\'서열 설계\'는 구조 적합성을 높이지만 기능(결합/촉매)을 자동 보장하진 않습니다.',
                '입력 구조 품질(결손/충돌/비정상 좌표)에 따라 설계 품질이 크게 흔들릴 수 있습니다.',
            ], ensure_ascii=False),
            'guide_recommended_workflow': json.dumps([
                'RFdiffusion(백본 생성) → ProteinMPNN(서열 설계) → AlphaFold2(접힘 검증) → Docking(DiffDock/Vina) → 후보 선정/실험',
            ], ensure_ascii=False),
            'option_help': {
                'numSequences': '동일 백본에 대해 생성할 서열 샘플 개수입니다.',
                'temperature': '낮을수록 보수적(안정적 경향), 높을수록 다양성 증가.',
                'seed': '재현성을 위한 난수 시드입니다. (SMALLINT 범위: 0-32767)',
                'designChains': '멀티체인 구조에서 설계할 체인을 지정합니다.',
                'fixedPositions': '변경 금지할 잔기 위치를 JSON으로 지정합니다. 예: {"A":[1,2,3,10]}',
                'omitAAs': '설계에서 제외할 아미노산을 지정합니다(예: C 제외로 디설파이드 방지).',
                'outputFormat': '결과 서열을 FASTA 또는 JSON으로 출력합니다.',
            },
        },
    }
    
    # Update tools
    for tool_name, updates in tool_updates.items():
        try:
            tool = ExperimentTool.objects.get(tool_name=tool_name)
            
            # Update guide fields
            tool.guide_prerequisites = updates['guide_prerequisites']
            tool.guide_inputs = updates['guide_inputs']
            tool.guide_outputs = updates['guide_outputs']
            tool.guide_limitations = updates['guide_limitations']
            tool.guide_recommended_workflow = updates['guide_recommended_workflow']
            tool.save()
            
            print(f"Updated guide fields for: {tool_name}")
            
            # Update option help_text
            for field_name, help_text in updates['option_help'].items():
                try:
                    option = ExperimentToolOption.objects.get(
                        tool=tool,
                        field_name=field_name
                    )
                    option.help_text = help_text
                    option.save()
                    print(f"  Updated help_text for {field_name}")
                except ExperimentToolOption.DoesNotExist:
                    print(f"  Option not found: {field_name}")
                    
        except ExperimentTool.DoesNotExist:
            print(f"Tool not found: {tool_name}")


def reverse_update(apps, schema_editor):
    """Reverse: Clear guide fields and help_text"""
    ExperimentTool = apps.get_model('experiments', 'ExperimentTool')
    ExperimentToolOption = apps.get_model('experiments', 'ExperimentToolOption')
    
    tool_names = ['RFdiffusion', 'AlphaFold3', 'ProteinMPNN']
    for tool_name in tool_names:
        try:
            tool = ExperimentTool.objects.get(tool_name=tool_name)
            tool.guide_prerequisites = None
            tool.guide_inputs = None
            tool.guide_outputs = None
            tool.guide_limitations = None
            tool.guide_recommended_workflow = None
            tool.save()
            
            # Clear help_text for all options
            ExperimentToolOption.objects.filter(tool=tool).update(help_text='')
            print(f"Cleared guide fields and help_text for: {tool_name}")
        except ExperimentTool.DoesNotExist:
            print(f"Tool not found: {tool_name}")


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0003_add_guide_fields_and_help_text'),
    ]

    operations = [
        migrations.RunPython(update_guide_fields_and_help_text, reverse_update),
    ]

