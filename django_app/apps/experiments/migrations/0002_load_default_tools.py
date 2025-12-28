# Generated manually - Load default experiment tools
import json
from django.db import migrations


def load_default_tools(apps, schema_editor):
    """Load default experiment tools from experiment.js"""
    ExperimentTool = apps.get_model('experiments', 'ExperimentTool')
    ExperimentToolOption = apps.get_model('experiments', 'ExperimentToolOption')
    
    default_tools = [
        {
            'tool_sid': 1,
            'tool_name': 'RFdiffusion',
            'category': '단백질 구조 생성',
            'description': '조건 기반 단백질 백본(구조) 생성',
            'icon_name': 'fas fa-microscope',
            'img_url': None,
            'guide_overview': 'RFdiffusion은 조건(제약/스캐폴드/모티프 등)을 기반으로 단백질 백본 구조를 생성하는 diffusion 기반 모델입니다.',
            'guide_usage': json.dumps([
                '1. 목표 구조의 조건(길이/모티프/대칭성 등)을 설정합니다.',
                '2. numSteps/temperature/guidanceScale을 조정해 생성합니다.',
                '3. 생성된 백본의 물리적 타당성(충돌/2차구조/접힘 가능성)을 1차 점검합니다.',
                '4. 후속 단계(ProteinMPNN 등)로 서열을 설계합니다.',
            ], ensure_ascii=False),
            'guide_tips': '처음엔 numSteps=50~100, guidanceScale=6~10 정도로 시작하고, 원하는 형태가 안 나오면 guidanceScale과 조건을 먼저 조정하는 편이 좋습니다.',
            # Note: guide_prerequisites, guide_inputs, guide_outputs, guide_limitations, guide_recommended_workflow
            # are added in migration 0003, so we'll update them in a separate migration
            'status': 'E',
            'option_fields': [
                {'name': 'temperature', 'label': 'Temperature', 'type': 'number', 'default': '1.0', 'min': 0.1, 'max': 2.0, 'step': 0.1, 'help': '높을수록 다양성 증가, 낮을수록 보수적으로 생성됩니다.', 'options_json': None, 'sort_order': 0},
                {'name': 'numSteps', 'label': 'Number of Steps', 'type': 'number', 'default': '50', 'min': 10, 'max': 200, 'step': 1, 'help': '스텝이 많을수록 계산량이 늘지만 더 안정적인 샘플이 나올 수 있습니다.', 'options_json': None, 'sort_order': 1},
                {'name': 'guidanceScale', 'label': 'Guidance Scale', 'type': 'number', 'default': '7.5', 'min': 1, 'max': 20, 'step': 0.5, 'help': '조건(제약)을 얼마나 강하게 따를지 제어합니다.', 'options_json': None, 'sort_order': 2},
            ],
        },
        {
            'tool_sid': 2,
            'tool_name': 'AlphaFold3',
            'category': '단백질 구조 예측',
            'description': '서열 기반 단백질 3D 구조 예측',
            'icon_name': 'fas fa-flask',
            'img_url': None,
            'guide_overview': 'AlphaFold3는 단백질 서열(FASTA)을 입력으로 3D 구조를 예측하는 딥러닝 모델입니다.',
            'guide_usage': json.dumps([
                '1. 단백질 서열(FASTA)을 입력합니다.',
                '2. 예측 모드를 선택합니다 (monomer/multimer).',
                '3. maxRecycles, 템플릿 사용 여부를 설정합니다.',
                '4. 예측을 실행하고 pLDDT/PAE 등 신뢰도를 검토합니다.',
            ], ensure_ascii=False),
            'guide_tips': '신뢰도 점수가 낮은 구간(유연/무질서 가능)을 분리 분석하거나, 도메인 단위로 재예측하는 것이 도움이 될 수 있습니다.',
            # Note: guide_prerequisites, guide_inputs, guide_outputs, guide_limitations, guide_recommended_workflow
            # are added in migration 0003, so we'll update them in migration 0004
            'status': 'E',
            'option_fields': [
                {'name': 'mode', 'label': 'Prediction Mode', 'type': 'select', 'default': 'monomer', 'min': 0, 'max': 100, 'step': 1, 'help': '단일 단백질이면 monomer, 복합체면 multimer를 선택합니다.', 'options_json': json.dumps(['monomer', 'multimer'], ensure_ascii=False), 'sort_order': 0},
                {'name': 'maxRecycles', 'label': 'Max Recycles', 'type': 'number', 'default': '3', 'min': 1, 'max': 10, 'step': 1, 'help': 'recycle이 늘면 품질이 좋아질 수 있지만 시간이 증가합니다.', 'options_json': None, 'sort_order': 1},
                {'name': 'useTemplates', 'label': 'Use Templates', 'type': 'checkbox', 'default': 'true', 'min': 0, 'max': 100, 'step': 1, 'help': '구조 템플릿을 사용할지 여부(가능하면 예측 안정성에 도움).', 'options_json': None, 'sort_order': 2},
            ],
        },
        {
            'tool_sid': 3,
            'tool_name': 'ProteinMPNN',
            'category': '단백질 서열 설계',
            'description': '구조(백본) 기반 단백질 서열 설계',
            'icon_name': 'fas fa-dna',
            'img_url': None,
            'guide_overview': 'ProteinMPNN은 단백질 구조(백본)를 입력으로 받아, 해당 구조에 잘 맞는 아미노산 서열을 생성하는 구조 기반 서열 설계 도구입니다.',
            'guide_usage': json.dumps([
                '1. 입력 구조(PDB/백본)를 준비합니다.',
                '2. (멀티체인인 경우) 설계할 체인(designChains)을 지정합니다.',
                '3. 필요하면 고정할 잔기 위치(fixedPositions)를 JSON으로 지정합니다.',
                '4. 생성 개수(numSequences)와 온도(temperature)를 설정해 서열을 생성합니다.',
                '5. 생성된 서열을 AlphaFold2 등으로 접힘/신뢰도를 확인해 필터링합니다.',
            ], ensure_ascii=False),
            'guide_tips': '처음에는 temperature 0.1~0.3, numSequences 8~32 정도로 시작하고, 기능에 중요한 잔기는 fixedPositions로 고정하는 게 안전합니다.',
            # Note: guide_prerequisites, guide_inputs, guide_outputs, guide_limitations, guide_recommended_workflow
            # are added in migration 0003, so we'll update them in a separate migration
            'status': 'E',
            'option_fields': [
                {'name': 'numSequences', 'label': 'Number of Sequences', 'type': 'number', 'default': '8', 'min': 1, 'max': 128, 'step': 1, 'help': '동일 백본에 대해 생성할 서열 샘플 개수입니다.', 'options_json': None, 'sort_order': 0},
                {'name': 'temperature', 'label': 'Sampling Temperature', 'type': 'number', 'default': '0.2', 'min': 0.0, 'max': 2.0, 'step': 0.05, 'help': '낮을수록 보수적(안정적 경향), 높을수록 다양성 증가.', 'options_json': None, 'sort_order': 1},
                {'name': 'seed', 'label': 'Random Seed', 'type': 'number', 'default': '0', 'min': 0, 'max': 32767, 'step': 1, 'help': '재현성을 위한 난수 시드입니다. (SMALLINT 범위: 0-32767)', 'options_json': None, 'sort_order': 2},
                {'name': 'designChains', 'label': 'Design Chains (e.g., A or A,B)', 'type': 'text', 'default': 'A', 'help': '멀티체인 구조에서 설계할 체인을 지정합니다.', 'options_json': None, 'sort_order': 3},
                {'name': 'fixedPositions', 'label': 'Fixed Positions (JSON)', 'type': 'textarea', 'default': '', 'help': '변경 금지할 잔기 위치를 JSON으로 지정합니다. 예: {"A":[1,2,3,10]}', 'options_json': None, 'sort_order': 4},
                {'name': 'omitAAs', 'label': 'Omit Amino Acids (e.g., C or W,Y)', 'type': 'text', 'default': '', 'help': '설계에서 제외할 아미노산을 지정합니다(예: C 제외로 디설파이드 방지).', 'options_json': None, 'sort_order': 5},
                {'name': 'outputFormat', 'label': 'Output Format', 'type': 'select', 'default': 'fasta', 'help': '결과 서열을 FASTA 또는 JSON으로 출력합니다.', 'options_json': json.dumps(['fasta', 'json'], ensure_ascii=False), 'sort_order': 6},
            ],
        },
    ]
    
    # Insert tools and their options
    for tool_data in default_tools:
        option_fields = tool_data.pop('option_fields')
        
        # Check if tool already exists
        tool, created = ExperimentTool.objects.get_or_create(
            tool_sid=tool_data['tool_sid'],
            defaults=tool_data
        )
        
        if created:
            print(f"Created tool: {tool.tool_name}")
            
            # Insert option fields (only if they don't exist)
            for option_data in option_fields:
                # Check if option already exists
                existing_option = ExperimentToolOption.objects.filter(
                    tool=tool,
                    field_name=option_data['name']
                ).first()
                
                if existing_option:
                    print(f"  Option already exists: {option_data['label']}")
                    continue
                
                # Handle min/max/step values
                # Note: Database uses SMALLINT, so decimal values are stored as integers
                # For fields with decimal values, we multiply by 10 (e.g., 0.1 -> 1, 2.0 -> 20)
                field_name = option_data['name']
                original_min = option_data.get('min', 0)
                original_max = option_data.get('max', 100)
                original_step = option_data.get('step', 1)
                
                # Check if this is a decimal field (has fractional part)
                is_decimal_field = (
                    isinstance(original_min, float) and original_min != int(original_min)
                ) or (
                    isinstance(original_max, float) and original_max != int(original_max)
                ) or (
                    isinstance(original_step, float) and original_step != int(original_step)
                )
                
                if is_decimal_field:
                    # Convert decimal to integer by multiplying by 10
                    # e.g., 0.1 -> 1, 2.0 -> 20, 7.5 -> 75, 0.5 -> 5
                    min_value = int(original_min * 10)
                    max_value = int(original_max * 10)
                    step_value = int(original_step * 10)
                else:
                    min_value = int(original_min)
                    max_value = int(original_max)
                    step_value = int(original_step)
                
                ExperimentToolOption.objects.create(
                    tool=tool,
                    field_name=option_data['name'],
                    field_label=option_data['label'],
                    field_type=option_data['type'],
                    default_value=option_data.get('default'),
                    min_value=min_value,
                    max_value=max_value,
                    step_value=step_value,
                    options_json=option_data.get('options_json'),
                    # Note: help_text field is added in migration 0003
                    # We'll update it in migration 0004
                    sort_order=option_data['sort_order'],
                    created_id='system',
                    updated_id='system',
                )
                print(f"  Created option: {option_data['label']}")
        else:
            print(f"Tool already exists: {tool.tool_name}")


def reverse_migration(apps, schema_editor):
    """Reverse: Delete default tools"""
    ExperimentTool = apps.get_model('experiments', 'ExperimentTool')
    ExperimentToolOption = apps.get_model('experiments', 'ExperimentToolOption')
    
    tool_names = ['RFdiffusion', 'AlphaFold3', 'ProteinMPNN']
    for tool_name in tool_names:
        try:
            tool = ExperimentTool.objects.get(tool_name=tool_name)
            ExperimentToolOption.objects.filter(tool=tool).delete()
            tool.delete()
            print(f"Deleted tool: {tool_name}")
        except ExperimentTool.DoesNotExist:
            print(f"Tool not found: {tool_name}")


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_default_tools, reverse_migration),
    ]
