import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import ExperimentTool, Experiment


@login_required
def index(request):
    """Experiments page view (인증 필수)."""
    # 활성화된 실험 도구 조회 (옵션 필드 포함)
    available_tools = ExperimentTool.objects.filter(
        status='E'
    ).prefetch_related('options').order_by('tool_name')
    
    # 템플릿에서 사용할 수 있도록 도구 데이터 변환
    tools_data = []
    for tool in available_tools:
        # 옵션 필드 변환
        option_fields = []
        for option in tool.options.all():
            option_field = {
                'name': option.field_name,
                'label': option.field_label,
                'type': option.field_type,
                'default': option.default_value or '',
            }
            
            # 필드 타입별 추가 속성
            if option.field_type == 'number':
                # 소수점 값 처리: 데이터베이스에 SMALLINT로 저장되므로
                # 소수점 값은 10배로 저장됨 (예: 0.1 -> 1, 2.0 -> 20, 7.5 -> 75)
                # 프론트엔드에서 사용할 수 있도록 원래 값으로 변환
                # 단, 10 이상의 값은 정수로 저장된 것으로 간주
                if option.min_value < 10 and option.min_value > 0:
                    option_field['min'] = option.min_value / 10.0
                else:
                    option_field['min'] = float(option.min_value)
                
                if option.max_value <= 100 and option.max_value > 0:
                    option_field['max'] = option.max_value / 10.0
                else:
                    option_field['max'] = float(option.max_value)
                
                if option.step_value < 10 and option.step_value > 0:
                    option_field['step'] = option.step_value / 10.0
                else:
                    option_field['step'] = float(option.step_value)
            elif option.field_type == 'select':
                # JSON 문자열 파싱
                if option.options_json:
                    try:
                        option_field['options'] = json.loads(option.options_json)
                    except json.JSONDecodeError:
                        option_field['options'] = []
                else:
                    option_field['options'] = []
            
            option_fields.append(option_field)
        
        # Guide 정보 변환
        guide_usage = []
        if tool.guide_usage:
            try:
                guide_usage = json.loads(tool.guide_usage)
            except json.JSONDecodeError:
                guide_usage = []
        
        tool_data = {
            'id': tool.tool_sid,
            'name': tool.tool_name,
            'category': tool.category,
            'description': tool.description or '',
            'icon': tool.icon_name or 'fa-solid fa-cog',
            'optionFields': option_fields,
            'guide': {
                'overview': tool.guide_overview or '',
                'usage': guide_usage,
                'tips': tool.guide_tips or '',
            },
        }
        tools_data.append(tool_data)
    
    # 실험 목록 조회 (사용자별로 필터링)
    # created_id는 user_id (UUID 문자열)를 저장
    # CustomUser는 user_id를 primary key로 사용하므로 pk 또는 user_id 사용 가능
    user_identifier = str(request.user.pk)  # pk는 primary key를 반환 (CustomUser의 경우 user_id)
    experiments = Experiment.objects.filter(
        created_id=user_identifier
    ).prefetch_related('tools').order_by('-created_at')[:20]  # 최근 20개만
    
    context = {
        'available_tools': tools_data,
        'experiments': experiments,
    }
    
    return render(request, 'experiments/experiment.html', context)
