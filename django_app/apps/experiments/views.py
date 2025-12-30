import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import ExperimentTool, Experiment, ExperimentToolSelection, ExperimentToolOption
from django.db import transaction
from django_app.apps.core.queue import publish_simulation



def _get_user_identifier(user):
    return str(user.user_id) if hasattr(user, 'user_id') else str(user.pk)


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
    # CustomUser는 user_id를 primary key로 사용하므로 user_id 속성 사용
    user_identifier = _get_user_identifier(request.user)
    experiments = Experiment.objects.filter(
        created_id=user_identifier
    ).prefetch_related('tools').order_by('-created_at')[:20]  # 최근 20개만
    
    context = {
        'available_tools': tools_data,
        'experiments': experiments,
    }
    
    return render(request, 'experiments/experiment.html', context)

@extend_schema(
    summary="실험 목록 조회 또는 실험 생성",
    description="GET: 실험 목록을 조회합니다. POST: 새로운 실험을 생성합니다.",
    tags=["Experiments"],
    methods=['GET'],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string'},
                            'pipeline_name': {'type': 'string'},
                            'pipeline': {'type': 'string'},
                            'created_at': {'type': 'string', 'format': 'date-time'},
                            'status': {'type': 'string'},
                            'status_display': {'type': 'string'},
                            'progress': {'type': 'integer'},
                            'tools': {'type': 'array', 'items': {'type': 'string'}},
                        }
                    }
                }
            }
        }
    }
)
@extend_schema(
    summary="실험 생성",
    description="새로운 실험을 생성합니다.",
    tags=["Experiments"],
    methods=['POST'],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'tools': {'type': 'array', 'items': {'type': 'string'}},
                'protein_sequence': {'type': 'string'},
                'pipeline_name': {'type': 'string'},
            }
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
                'data': {
                    'type': 'object',
                    'properties': {
                        'tools_count': {'type': 'integer'},
                        'sequence_length': {'type': 'integer'},
                        'pipeline_name': {'type': 'string'},
                    }
                }
            }
        }
    }
)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def experiments_api(request):
    """API endpoint router for experiments (GET /api/experiments/ and POST /api/experiments/)."""
    if request.method == 'GET':
        return _list_experiments_api(request)
    else:  # POST
        return _create_experiment_api(request)


def _list_experiments_api(request):
    """GET /api/experiments/ - 실험 목록 조회."""
    print("=" * 80)
    print("[Experiments API] ====== GET /api/experiments/ ======")
    print(f"[Experiments API] Request method: {request.method}")
    print(f"[Experiments API] Request path: {request.path}")
    print(f"[Experiments API] Request user: {request.user}")
    print(f"[Experiments API] User authenticated: {request.user.is_authenticated}")
    print(f"[Experiments API] User pk: {request.user.pk}")
    print(f"[Experiments API] User pk type: {type(request.user.pk)}")
    
    # 실험 목록 조회 (사용자별로 필터링)
    # CustomUser는 user_id를 primary key로 사용하므로 user_id 속성 사용
    user_identifier = _get_user_identifier(request.user)
    print(f"[Experiments API] User identifier (string): {user_identifier}")
    print(f"[Experiments API] User has user_id attr: {hasattr(request.user, 'user_id')}")
    if hasattr(request.user, 'user_id'):
        print(f"[Experiments API] User user_id: {request.user.user_id}")
    print(f"[Experiments API] User pk: {request.user.pk}")
    
    # 디버깅: 전체 실험 개수 확인
    all_experiments_count = Experiment.objects.count()
    print(f"[Experiments API] Total experiments in DB: {all_experiments_count}")
    
    # 디버깅: 사용자별 실험 개수 확인
    user_experiments_count = Experiment.objects.filter(created_id=user_identifier).count()
    print(f"[Experiments API] User experiments count (filtered by '{user_identifier}'): {user_experiments_count}")
    
    # 디버깅: created_id 값들 확인 (최근 5개)
    recent_experiments = Experiment.objects.all().order_by('-created_at')[:5]
    print(f"[Experiments API] Recent experiments created_id values:")
    for exp in recent_experiments:
        print(f"  - Experiment {exp.experiment_sid}: created_id='{exp.created_id}' (type: {type(exp.created_id)})")
    
    experiments = Experiment.objects.filter(
        created_id=user_identifier
    ).prefetch_related('tool_selections__tool').order_by('-created_at')[:20]  # 최근 20개만
    
    print(f"[Experiments API] Filtered experiments count: {experiments.count()}")
    
    # 실험 데이터 변환
    experiments_data = []
    for exp in experiments:
        # 상태 코드를 한국어로 변환
        status_map = {
            'E': '활성',
            'R': '준비',
            'P': '진행중',
            'C': '완료',
            'F': '실패',
            'D': '비활성',
        }
        status_display = status_map.get(exp.status, exp.status or '준비')
        
        # 도구 정보를 이름 배열로 변환
        # Many-to-Many through 관계이므로 tool_selections를 통해 접근
        tools_list = []
        tool_selections = exp.tool_selections.all().select_related('tool').order_by('sort_order')
        print(f"[Experiments API] Experiment {exp.experiment_sid}: tool_selections count = {tool_selections.count()}")
        for selection in tool_selections:
            if selection.tool:
                tools_list.append(selection.tool.tool_name)
                print(f"[Experiments API]   - Tool: {selection.tool.tool_name} (tool_sid={selection.tool.tool_sid})")
        
        # Fallback: tools.all()도 시도
        if not tools_list:
            tools_list = [tool.tool_name for tool in exp.tools.all()]
            print(f"[Experiments API] Experiment {exp.experiment_sid}: Using exp.tools.all(), found {len(tools_list)} tools")
        
        exp_data = {
            'id': exp.experiment_sid,  # experiment_sid가 primary key
            'pipeline_name': exp.pipeline_name or 'Unnamed Pipeline',
            'pipeline': exp.pipeline_name or 'Unnamed Pipeline',  # React 호환성
            'created_at': exp.created_at.isoformat() if exp.created_at else None,
            'status': exp.status or 'R',  # 상태 코드
            'status_display': status_display,  # 한국어 상태
            'progress': exp.progress if exp.progress is not None else 0,
            'tools': tools_list,  # 도구 이름 배열
        }
        experiments_data.append(exp_data)
    
    print(f"[Experiments API] Found {len(experiments_data)} experiments")
    print("[Experiments API] ====== End of request log ======")
    print("=" * 80)
    
    return Response({
        'status': 'success',
        'results': experiments_data,
    }, status=200)


def _create_experiment_api(request):
    """POST /api/experiments/ - 실험 생성."""
    print("=" * 80)
    print("[Experiments API] ====== POST /api/experiments/ ======")
    print(f"[Experiments API] Request method: {request.method}")
    print(f"[Experiments API] Request path: {request.path}")
    print(f"[Experiments API] Request user: {request.user}")
    print(f"[Experiments API] User authenticated: {request.user.is_authenticated}")
    
    # Parse request body
    try:
        body = request.data if hasattr(request, 'data') else json.loads(request.body)
        print(f"[Experiments API] Request body (parsed): {json.dumps(body, indent=2, ensure_ascii=False)}")
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"[Experiments API] Error parsing JSON: {e}")
        print(f"[Experiments API] Raw request body: {request.body}")
        return Response({'error': 'Invalid JSON'}, status=400)
    
    # Log request data
    print(f"[Experiments API] Tools: {body.get('tools', [])}")
    print(f"[Experiments API] Protein sequence length: {len(body.get('protein_sequence', ''))}")
    print(f"[Experiments API] Pipeline name: {body.get('pipeline_name', 'N/A')}")
    
    # Log headers
    print(f"[Experiments API] Content-Type: {request.content_type}")
    print(f"[Experiments API] CSRF Token: {request.headers.get('X-CSRFToken', 'Not provided')}")
    
    # Log request metadata
    print(f"[Experiments API] Request META keys: {list(request.META.keys())}")
    print(f"[Experiments API] Remote address: {request.META.get('REMOTE_ADDR', 'N/A')}")
    print(f"[Experiments API] User agent: {request.META.get('HTTP_USER_AGENT', 'N/A')}")
    
    print("[Experiments API] ====== End of request log ======")
    print("=" * 80)


    # ------------------------
    # 1) 입력값 검증
    # ------------------------
    tools = body.get("tools") or []
    if not isinstance(tools, list) or not tools:
        return Response(
            {"error": "tools is required and must be a non-empty list"},
            status=400,
        )

    protein_sequence = (body.get("protein_sequence") or "").strip()
    if not protein_sequence:
        return Response({"error": "protein_sequence is required"}, status=400)

    pipeline_name = (body.get("pipeline_name") or "").strip()
    if not pipeline_name:
        pipeline_name = f"Pipeline {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"

    protein_name = (body.get("protein_name") or "").strip()
    tool_options = body.get("tool_options") or {}
    if not isinstance(tool_options, dict):
        tool_options = {}

    # 새로: 옵션 정의(테이블 t_experiment_tool_option용)
    tool_option_defs = body.get("tool_option_defs") or {}
    if not isinstance(tool_option_defs, dict):
        tool_option_defs = {}

    # ------------------------
    # 2) 사용자 식별자
    # ------------------------
    user_identifier = _get_user_identifier(request.user)
    created_tools = []
    # ------------------------
    # 3) t_experiment + t_experiment_tool_selection + t_experiment_tool_option 한번에
    # ------------------------
    with transaction.atomic():
        # t_experiment insert
        experiment = Experiment.objects.create(
            pipeline_name=pipeline_name,
            status="R",  # Ready
            progress=0,
            protein_sequence=protein_sequence,
            protein_name=protein_name or None,
            created_id=user_identifier,
            updated_id=user_identifier,
        )
        print(f"[Experiments API] Created Experiment: experiment_sid={experiment.experiment_sid}")

        # 각 tool_sid 기준으로 selection + option 정의 생성
        for sort_order, raw_tool_id in enumerate(tools):
            try:
                tool_id = int(raw_tool_id)
            except (TypeError, ValueError):
                print(f"[Experiments API] Invalid tool id in tools list: {raw_tool_id}")
                continue

            tool = ExperimentTool.objects.filter(tool_sid=tool_id, status="E").first()
            if not tool:
                print(f"[Experiments API] Tool not found or disabled: tool_sid={tool_id}")
                continue

        # 1) 사용자가 보낸 옵션 값 (일부만 있을 수 있음)
            user_options = (
                tool_options.get(str(tool_id))
                or tool_options.get(tool_id)
                or {}
            )
            if not isinstance(user_options, dict):
                user_options = {}

            # 2) 도구 정의 테이블에서 기본값 가져오기
            merged_options = {}
            for opt in ExperimentToolOption.objects.filter(tool=tool).order_by("sort_order", "field_name"):
                if opt.default_value is not None:
                    merged_options[opt.field_name] = opt.default_value

            # 3) 사용자가 변경한 값으로 덮어쓰기
            for key, value in user_options.items():
                merged_options[key] = value

            # 4) JSON 저장
            try:
                options_json = json.dumps(merged_options, ensure_ascii=False)
            except TypeError:
                options_json = "{}"

            selection = ExperimentToolSelection.objects.create(
                experiment=experiment,
                tool=tool,
                sort_order=sort_order,
                tool_options_json=options_json,
                created_id=user_identifier,
                updated_id=user_identifier,
            )
            created_tools.append(tool.tool_name)

    # 여기부터 메시지 큐 발행 로직
    # 1) 어떤 tool_name 으로 보낼지 결정
    #    - 예: 파이프라인의 첫 도구를 기준으로
    first_selection = experiment.tool_selections.select_related('tool').order_by('sort_order').first()
    if not first_selection:
        # 도구가 하나도 없다면 큐에 보낼 게 없음
        return Response(
            {"error": "No tools selected for this experiment"},
            status=400,
        )

    TOOL_NAME_QUEUE_MAP = {
    "RFdiffusion": "rfdiffusion",
    "ProteinMPNN": "protein_mpnn",
    "AlphaFold3": "alphafold3",
    }

    tool_name_display = first_selection.tool.tool_name  # DB 값
    tool_name_for_queue = TOOL_NAME_QUEUE_MAP.get(tool_name_display)
    
    if not tool_name_for_queue:
        return Response(
            {"error": f"Unsupported tool for queue: {tool_name_display}"},
            status=400,
    )

    # 2) 큐에 넣을 payload 구성 (예시)
    tool_selections_payload = []
    for sel in experiment.tool_selections.select_related('tool').order_by('sort_order'):
        try:
            tool_options = json.loads(sel.tool_options_json or "{}")
        except json.JSONDecodeError:
            tool_options = {}

        tool_selections_payload.append({
            "selection_sid": sel.selection_sid,
            "tool_sid": sel.tool_id,
            "tool_name": sel.tool.tool_name,
            "sort_order": sel.sort_order,
            "tool_options": tool_options,
        })

    payload = {
        "protein_sequence": experiment.protein_sequence,
        "protein_name": experiment.protein_name,
        "tool_selections": tool_selections_payload,
    }

    user_id = getattr(request.user, "user_id", None) or getattr(request.user, "pk", None)
    
    # 3) 메시지 큐에 작업 발행
    try:
        task_id = publish_simulation(
            tool_name=tool_name_for_queue,
            experiment_sid=experiment.experiment_sid,
            payload=payload,
            user_id=user_id,
        )
    except Exception as e:
        print(f"Failed to publish simulation task: {e}")
        return Response(
            {
                "status": "error",
                "message": "Failed to enqueue simulation task",
                "detail": str(e),
            },
            status=500,
        )
    
    # 4) 상태를 'R'(진행중)으로 업데이트
    experiment.status = 'R'
    experiment.progress = 0
    experiment.save(update_fields=['status', 'progress', 'updated_at'])

    # 5) 클라이언트 응답 (실험 생성 + 큐 등록 정보 포함)
    return Response(
        {
            "status": "queued",  # 큐에 올라갔다는 상태
            "message": "Simulation task has been queued",
            "experiment_sid": experiment.experiment_sid,
            "task_id": task_id,
            # 실험 상세 정보도 함께 내려줌
            "data": {
                "id": experiment.experiment_sid,
                "pipeline_name": experiment.pipeline_name,
                "status": experiment.status,
                "progress": experiment.progress,
                "tools": created_tools,
                "tools_count": len(body.get("tools", [])),
                "sequence_length": len(body.get("protein_sequence", "")),
                "pipeline_name_input": body.get("pipeline_name", ""),
            },
        },
        status=200,
    )