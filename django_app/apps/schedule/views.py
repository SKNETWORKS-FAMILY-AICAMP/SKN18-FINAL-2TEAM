import json
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from django.db.models import Q, Max

from .models import (
    Schedule,
    UserCalendar,
    SyncedCalendar,
    GoogleCredentials,
    GoogleSyncedEvent,
    ScheduleInvitation,
    ScheduleShare,
)
from .recurrence import create_recurrence, expand_recurrences
from apps.account.models import LinkedAccount, CustomUser


TYPE_COLOR_MAP = {
    'E': '#3b82f6',  # 실험
    'M': '#a855f7',  # 미팅
    'A': '#f97316',  # 분석
    'S': '#ec4899',  # 세미나
}

DEFAULT_CALENDAR_NAME = "내 캘린더"


def _schedule_queryset_for_user(user):
    if not user or not user.is_authenticated:
        print("[ScheduleList] 비인증 사용자 접근 - 빈 쿼리셋 반환")
        return Schedule.objects.none()

    owner_id = _resolve_owner_id(user)
    # 본인이 생성한 일정 또는 본인에게 공유된 일정 (수락된 invitation의 shared_schedule 포함)
    # ACCEPTED invitation의 원본 일정만 포함 (PENDING은 제외 - 아직 수락하지 않은 일정은 표시하지 않음)
    accepted_invitation_schedule_ids = ScheduleInvitation.objects.filter(
        user_id=owner_id,
        status=ScheduleInvitation.Status.ACCEPTED
    ).values_list('schedule_id', flat=True)
    # Accepted invitation으로 생성된 복사본 일정
    accepted_shared_schedule_ids = ScheduleInvitation.objects.filter(
        user_id=owner_id,
        status=ScheduleInvitation.Status.ACCEPTED,
        shared_schedule__isnull=False
    ).values_list('shared_schedule_id', flat=True)
    # 수락된 공유 일정 (ScheduleShare)
    shared_schedule_ids = ScheduleShare.objects.filter(
        user_id=owner_id
    ).values_list('schedule_id', flat=True)
    filters = Q(created_id=owner_id) | Q(schedule_sid__in=accepted_invitation_schedule_ids) | Q(schedule_sid__in=accepted_shared_schedule_ids) | Q(schedule_sid__in=shared_schedule_ids)
    queryset = (
        Schedule.objects.filter(use_yn="Y")
        .filter(filters)
        .select_related("google_sync__calendar", "calendar")
        .order_by("start_date", "created_at")
    )
    try:
        print(
            f"[ScheduleList] user={owner_id} raw_user={getattr(user, 'user_id', user.pk)} "
            f"returned_count={queryset.count()}"
        )
    except Exception as exc:
        print(f"[ScheduleList] count logging 실패: {exc}")
    return queryset


def _get_google_link(schedule):
    try:
        return schedule.google_sync
    except GoogleSyncedEvent.DoesNotExist:
        return None


def _serialize_schedule(schedule: Schedule, user=None) -> dict:
    google_link = _get_google_link(schedule)
    calendar_summary = None
    calendar_id = None
    if google_link and google_link.calendar:
        calendar_summary = google_link.calendar.summary
        calendar_id = google_link.calendar.calendar_id

    calendar_obj = getattr(schedule, "calendar", None)
    if calendar_obj:
        calendar_summary = calendar_summary or calendar_obj.calendar_name
        calendar_id = calendar_id or str(calendar_obj.calendar_sid)

    # 공유 여부 확인 (본인이 생성한 일정이 아니면 공유된 일정)
    is_shared = False
    if user:
        owner_id = _resolve_owner_id(user)
        is_shared = schedule.created_id != owner_id

    return {
        "id": schedule.schedule_sid,
        "title": schedule.title,
        "description": schedule.description or "",
        "type": schedule.schedule_type,
        "get_type_display": schedule.get_schedule_type_display(),
        "status": schedule.status,
        "start_datetime": schedule.start_date.isoformat() if schedule.start_date else None,
        "end_datetime": schedule.end_date.isoformat() if schedule.end_date else None,
        "is_all_day": schedule.is_all_day == "Y",
        "location": schedule.location or "",
        "color": schedule.color,
        "linked_note": schedule.linked_note_sid,
        "repeat_type": schedule.repeat_type,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
        "source": "google" if google_link else "local",
        "calendar_name": calendar_summary,
        "calendar_id": calendar_id,
        "user_calendar_id": schedule.calendar.calendar_sid if schedule.calendar else None,
        "is_shared": is_shared,
        "created_id": schedule.created_id,
    }


def _serialize_schedule_for_template(schedule: Schedule, user=None) -> dict:
    data = _serialize_schedule(schedule, user)
    data["start_display"] = schedule.start_date
    return data


def _resolve_owner_id(user):
    if not user or not getattr(user, "is_authenticated", False):
        return "system"
    value = getattr(user, "user_id", None)
    if value:
        return str(value)
    return getattr(user, "email", "system")


def _user_calendar_queryset(user, *, include_google=True):
    owner_id = _resolve_owner_id(user)
    if not owner_id:
        return UserCalendar.objects.none()
    qs = UserCalendar.objects.filter(created_id=owner_id)
    if not include_google:
        qs = qs.exclude(source_type=UserCalendar.Source.GOOGLE)
    return qs


def _serialize_user_calendar(calendar: UserCalendar) -> dict:
    return {
        "id": calendar.calendar_sid,
        "name": calendar.calendar_name,
        "color": calendar.color or TYPE_COLOR_MAP.get("E", "#3b82f6"),
        "visible": calendar.visible,
        "source_type": getattr(calendar, "source_type", UserCalendar.Source.LOCAL),
        "external_id": calendar.external_id,
    }


def _next_calendar_sort_order(owner_id: str) -> int:
    last = (
        UserCalendar.objects.filter(created_id=owner_id)
        .order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
    )
    return (last or 0) + 1


def _ensure_default_calendar(user, *, fallback_color: str | None = None) -> UserCalendar:
    owner_id = _resolve_owner_id(user)
    qs = _user_calendar_queryset(user).filter(source_type=UserCalendar.Source.LOCAL)
    calendar = qs.order_by("sort_order", "calendar_sid").first()
    if calendar:
        return calendar

    color = fallback_color or TYPE_COLOR_MAP.get("E", "#3b82f6")
    calendar = UserCalendar.objects.create(
        calendar_name=DEFAULT_CALENDAR_NAME,
        color=color,
        is_visible=1,
        sort_order=_next_calendar_sort_order(owner_id),
        created_id=owner_id,
        updated_id=owner_id,
        source_type=UserCalendar.Source.LOCAL,
    )
    return calendar


def _get_user_calendar_by_id(user, calendar_id: int | None) -> UserCalendar | None:
    if not calendar_id:
        return None
    try:
        return _user_calendar_queryset(user).get(calendar_sid=calendar_id)
    except UserCalendar.DoesNotExist:
        return None


def _parse_iso_datetime(value: str | None):
    if not value:
        return None
    dt = parse_datetime(value)
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@login_required
def index(request):
    """Schedule page view (인증 필수)."""
    # Load schedules for initial page render
    schedules = _schedule_queryset_for_user(request.user)[:10]

    # ✅ Google Calendar connection (토큰 존재 여부로 판단)
    is_google_connected = GoogleCredentials.objects.filter(user=request.user).exists()
    owner_calendars = _user_calendar_queryset(
        request.user, include_google=is_google_connected
    ).order_by('sort_order', 'created_at')
    has_linked_google_account = LinkedAccount.objects.filter(
        user=request.user, provider=LinkedAccount.Provider.GOOGLE
    ).exists()

    context = {
        'is_google_connected': is_google_connected,
        'show_google_account_hint': has_linked_google_account and not is_google_connected,
        'user_calendars': [_serialize_user_calendar(cal) for cal in owner_calendars],
        'schedules': [_serialize_schedule_for_template(s, request.user) for s in schedules],
        'current_date': datetime.now(),
        'schedule_count': schedules.count(),
    }
    return render(request, 'schedule/schedule.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def user_calendars_api(request: HttpRequest) -> JsonResponse:
    owner_id = _resolve_owner_id(request.user)

    if request.method == "GET":
        google_connected = GoogleCredentials.objects.filter(user=request.user).exists()
        calendars = _user_calendar_queryset(
            request.user, include_google=google_connected
        ).order_by('sort_order', 'created_at')
        results = [_serialize_user_calendar(cal) for cal in calendars]
        return JsonResponse({"results": results})

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "name_required"}, status=400)

    color = data.get("color") or TYPE_COLOR_MAP.get("E", "#3b82f6")
    visible = data.get("visible", True)
    source_type = data.get("source_type") or UserCalendar.Source.LOCAL
    if source_type not in UserCalendar.Source.values:
        source_type = UserCalendar.Source.LOCAL

    external_id = None
    if source_type == UserCalendar.Source.GOOGLE:
        ext = data.get("external_id")
        if isinstance(ext, str):
            external_id = ext

    calendar = UserCalendar.objects.create(
        calendar_name=name,
        color=color,
        is_visible=1 if visible else 0,
        sort_order=_next_calendar_sort_order(owner_id),
        created_id=owner_id,
        updated_id=owner_id,
        source_type=source_type,
        external_id=external_id,
    )
    return JsonResponse(_serialize_user_calendar(calendar), status=201)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def user_calendar_detail(request: HttpRequest, calendar_id: int) -> JsonResponse:
    try:
        calendar = _user_calendar_queryset(request.user).get(calendar_sid=calendar_id)
    except UserCalendar.DoesNotExist:
        return JsonResponse({"error": "calendar_not_found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_user_calendar(calendar))

    if request.method == "DELETE":
        if calendar.source_type == UserCalendar.Source.GOOGLE:
            return JsonResponse({"error": "google_calendar_readonly"}, status=400)
        
        # 캘린더 삭제 전에 해당 캘린더에 속한 일정들도 모두 삭제
        from django.db import transaction
        
        with transaction.atomic():
            # 해당 캘린더에 속한 모든 일정 삭제
            schedules_count = Schedule.objects.filter(
                calendar=calendar
            ).count()
            
            Schedule.objects.filter(
                calendar=calendar
            ).delete()
            
            # 캘린더 삭제
            calendar.delete()
        
        return JsonResponse({
            "ok": True,
            "deleted_schedules": schedules_count
        })

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    owner_id = _resolve_owner_id(request.user)
    update_fields: list[str] = []

    if "name" in data and calendar.source_type == UserCalendar.Source.LOCAL:
        new_name = (data.get("name") or "").strip()
        if new_name and new_name != calendar.calendar_name:
            calendar.calendar_name = new_name
            update_fields.append("calendar_name")

    if "color" in data:
        color = (data.get("color") or "").strip()
        if color:
            calendar.color = color
            update_fields.append("color")

    if "visible" in data:
        visible = bool(data.get("visible"))
        new_value = 1 if visible else 0
        if calendar.is_visible != new_value:
            calendar.is_visible = new_value
            update_fields.append("is_visible")

    if "sort_order" in data:
        sort_order = data.get("sort_order")
        if isinstance(sort_order, int) and sort_order >= 0:
            if calendar.sort_order != sort_order:
                calendar.sort_order = sort_order
                update_fields.append("sort_order")

    if not update_fields:
        return JsonResponse(_serialize_user_calendar(calendar))

    calendar.updated_id = owner_id
    update_fields.append("updated_id")
    calendar.save(update_fields=update_fields)
    return JsonResponse(_serialize_user_calendar(calendar))


@login_required
@require_http_methods(["GET", "POST"])
def schedule_list(request):
    """일정 목록 / 생성 API"""
    if request.method == "GET":
        schedules = _schedule_queryset_for_user(request.user)

        time_min = request.GET.get("timeMin") or request.GET.get("time_min")
        time_max = request.GET.get("timeMax") or request.GET.get("time_max")

        start_dt = _parse_iso_datetime(time_min) if time_min else None
        end_dt = _parse_iso_datetime(time_max) if time_max else None

        if not start_dt:
            start_dt = timezone.now() - timedelta(days=30)
        if not end_dt:
            end_dt = timezone.now() + timedelta(days=90)

        expanded = expand_recurrences(
            schedules,
            range_start=start_dt,
            range_end=end_dt,
        )

        formatted_schedules = []
        for occurrence in expanded:
            payload = _serialize_schedule(occurrence.base, request.user)
            payload['color'] = payload.get('color') or TYPE_COLOR_MAP.get(occurrence.base.schedule_type, '#3b82f6')
            payload['start_datetime'] = occurrence.start.isoformat()
            payload['end_datetime'] = occurrence.end.isoformat()
            payload['instance_id'] = occurrence.instance_id
            formatted_schedules.append(payload)

        log_owner = _resolve_owner_id(request.user)
        print(
            f"[ScheduleList] GET user={log_owner} range=({start_dt.isoformat()}, {end_dt.isoformat()}) "
            f"response_count={len(formatted_schedules)}"
        )
        return JsonResponse({'results': formatted_schedules})

    # POST: create schedule
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)

    title = (data.get("title") or "").strip()
    if not title:
        return JsonResponse({"error": "title_required"}, status=400)

    start_dt = _parse_iso_datetime(data.get("start_datetime"))
    end_dt = _parse_iso_datetime(data.get("end_datetime") or data.get("start_datetime"))
    if not start_dt or not end_dt:
        return JsonResponse({"error": "invalid_datetime"}, status=400)

    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=1)

    is_all_day = data.get("is_all_day")
    if isinstance(is_all_day, str):
        is_all_day = is_all_day.lower() == "true"
    is_all_day = bool(is_all_day)

    type_map = {
        "experiment": "E",
        "meeting": "M",
        "analysis": "A",
        "seminar": "S",
        "E": "E",
        "M": "M",
        "A": "A",
        "S": "S",
    }
    schedule_type = type_map.get(data.get("type"), "E")

    status_map = {
        "scheduled": "E",
        "in_progress": "R",
        "in-progress": "R",
        "completed": "C",
        "E": "E",
        "R": "R",
        "C": "C",
    }
    schedule_status = status_map.get(data.get("status"), "E")

    owner_id = _resolve_owner_id(request.user)

    linked_note = data.get("linked_note_id") or data.get("linked_note")
    try:
        linked_note = int(linked_note) if linked_note not in (None, "") else None
    except (TypeError, ValueError):
        linked_note = None

    requested_calendar_id = data.get("calendar_id") or data.get("calendar")
    calendar_obj = None
    try:
        calendar_obj = _get_user_calendar_by_id(request.user, int(requested_calendar_id))
    except (TypeError, ValueError):
        calendar_obj = None
    if not calendar_obj:
        calendar_obj = _ensure_default_calendar(
            request.user,
            fallback_color=TYPE_COLOR_MAP.get(schedule_type, '#3b82f6'),
        )

    schedule_color = data.get("color") or getattr(calendar_obj, "color", None) or TYPE_COLOR_MAP.get(schedule_type, '#3b82f6')

    # repeat_type 설정: recurrence 데이터가 있으면 freq 기반으로, 없으면 repeat 필드 기반으로
    recurrence_payload = data.get("recurrence") or {}
    freq_map = {
        "daily": "DAILY",
        "weekly": "WEEKLY",
        "monthly": "MONTHLY",
        "yearly": "YEARLY",
    }
    normalized_freq = freq_map.get(recurrence_payload.get("freq"), recurrence_payload.get("freq"))
    
    if normalized_freq:
        # recurrence 데이터가 있으면 freq를 기반으로 repeat_type 설정
        freq_to_repeat_map = {
            "DAILY": "D",
            "WEEKLY": "W",
            "MONTHLY": "M",
            "YEARLY": "Y",
        }
        repeat_type = freq_to_repeat_map.get(normalized_freq, "N")
    else:
        # recurrence 데이터가 없으면 기존 로직대로 repeat 필드 사용
        repeat_map = {
            "none": "N",
            "daily": "D",
            "weekly": "W",
            "monthly": "M",
            "yearly": "Y",
        }
        repeat_type = repeat_map.get(data.get("repeat"), "N")

    schedule = Schedule.objects.create(
        title=title,
        description=data.get("description") or "",
        schedule_type=schedule_type,
        schedule_status=schedule_status,
        use_yn="Y",
        start_date=start_dt,
        end_date=end_dt,
        is_all_day="Y" if is_all_day else "N",
        location=data.get("location") or "",
        color=schedule_color,
        linked_note_sid=linked_note,
        calendar=calendar_obj,
        repeat_type=repeat_type,
        created_id=owner_id,
        updated_id=owner_id,
    )

    recurrence_data = None
    if normalized_freq:
        recurrence_data = {
            "freq": normalized_freq,
            "interval": recurrence_payload.get("interval", 1),
            "week_days": recurrence_payload.get("week_days") or recurrence_payload.get("weekDays"),
            "month_days": recurrence_payload.get("month_days") or recurrence_payload.get("monthDays"),
            "count": recurrence_payload.get("count"),
            "until": recurrence_payload.get("until"),
            "timezone": recurrence_payload.get("timezone") or "Asia/Seoul",
        }
        create_recurrence(schedule, recurrence_data)

    payload = _serialize_schedule(schedule, request.user)
    return JsonResponse(payload, status=201)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def schedule_detail(request, schedule_id):
    """일정 상세 조회/수정 API 엔드포인트"""
    print(f"[DEBUG] schedule_detail() called - schedule_id: {schedule_id}, method: {request.method}")

    try:
        schedule = _schedule_queryset_for_user(request.user).get(schedule_sid=schedule_id)
        print(f"[DEBUG] Schedule found: {schedule.title}")
    except Schedule.DoesNotExist:
        print(f"[ERROR] Schedule not found - schedule_id: {schedule_id}")
        return JsonResponse({'error': '일정을 찾을 수 없습니다.'}, status=404)

    if request.method == 'GET':
        print(f"[DEBUG] GET request - returning schedule detail")
        payload = _serialize_schedule(schedule, request.user)
        color = payload.get('color')
        if not color:
            type_colors = {
                'E': '#3b82f6',
                'M': '#f97316',
                'A': '#f97316',
                'S': '#ec4899',
            }
            color = type_colors.get(schedule.schedule_type, '#3b82f6')

        # Load shared users
        shared_users = []
        try:
            from .models import ScheduleShare
            schedule_shares = ScheduleShare.objects.filter(schedule=schedule).select_related()
            shared_users = [
                {
                    'user_id': share.user_id,
                    'email': share.user_id,  # 임시
                    'name': share.user_id,   # 임시
                }
                for share in schedule_shares
            ]
        except Exception as e:
            print(f"[WARNING] Error loading shared users: {e}")

        payload['color'] = color
        payload['shared_with'] = shared_users
        payload['is_shared_copy'] = schedule.is_shared_copy
        payload['original_schedule_id'] = schedule.original_schedule.schedule_sid if schedule.original_schedule else None
        return JsonResponse(payload)

    elif request.method == 'PATCH':
        # 권한 체크: 공유된 일정(is_shared_copy=True)은 수정 불가
        owner_id = _resolve_owner_id(request.user)
        if schedule.is_shared_copy:
            return JsonResponse({'error': '공유받은 일정은 수정할 수 없습니다.'}, status=403)
        
        # 원본 일정 소유자만 수정 가능
        if schedule.created_id != owner_id:
            return JsonResponse({'error': '본인이 생성한 일정만 수정할 수 있습니다.'}, status=403)

        import json
        from django.db import transaction
        
        data = json.loads(request.body)
        
        # 수정할 필드 추적
        update_fields = []
        sync_fields = []  # 동기화할 필드
        
        # Update status if provided
        if 'status' in data:
            status_map = {
                'scheduled': 'E',
                'in_progress': 'R',
                'completed': 'C',
            }
            new_status = status_map.get(data['status'], 'E')
            if schedule.schedule_status != new_status:
                schedule.schedule_status = new_status
                update_fields.append('schedule_status')
                sync_fields.append('schedule_status')

        # Update other fields if provided
        if 'title' in data:
            new_title = data['title']
            if schedule.title != new_title:
                schedule.title = new_title
                update_fields.append('title')
                sync_fields.append('title')
                
        if 'description' in data:
            new_description = data.get('description', '')
            if schedule.description != new_description:
                schedule.description = new_description
                update_fields.append('description')
                sync_fields.append('description')
                
        if 'type' in data:
            new_type = data['type']
            if schedule.schedule_type != new_type:
                schedule.schedule_type = new_type
                update_fields.append('schedule_type')
                sync_fields.append('schedule_type')
                
        if 'location' in data:
            new_location = data.get('location', '')
            if schedule.location != new_location:
                schedule.location = new_location
                update_fields.append('location')
                sync_fields.append('location')
                
        if 'color' in data:
            new_color = data.get('color', '')
            if schedule.color != new_color:
                schedule.color = new_color
                update_fields.append('color')
                sync_fields.append('color')

        if 'start_datetime' in data:
            from django.utils.dateparse import parse_datetime
            start_date = parse_datetime(data['start_datetime'])
            if start_date and schedule.start_date != start_date:
                schedule.start_date = start_date
                update_fields.append('start_date')
                sync_fields.append('start_date')

        if 'end_datetime' in data:
            from django.utils.dateparse import parse_datetime
            end_date = parse_datetime(data['end_datetime'])
            if end_date and schedule.end_date != end_date:
                schedule.end_date = end_date
                update_fields.append('end_date')
                sync_fields.append('end_date')

        with transaction.atomic():
            # 원본 일정 저장
            if update_fields:
                schedule.updated_id = owner_id
                update_fields.append('updated_id')
                schedule.save(update_fields=update_fields)
            
            # 원본 일정인 경우 공유된 모든 복사본 동기화
            if sync_fields and schedule.original_schedule is None:
                for copy in schedule.shared_copies.all():
                    for field in sync_fields:
                        if hasattr(schedule, field):
                            setattr(copy, field, getattr(schedule, field))
                    copy.updated_id = owner_id
                    copy.save(update_fields=sync_fields + ['updated_id'])

        return JsonResponse({
            'id': schedule.schedule_sid,
            'title': schedule.title,
            'status': schedule.schedule_status,
            'message': '일정이 수정되었습니다.'
        })


@login_required
@require_http_methods(["GET", "POST"])
def schedule_shared_users(request, schedule_id):
    """일정 공유 사용자 목록 조회/공유 API 엔드포인트"""
    try:
        schedule = _schedule_queryset_for_user(request.user).get(schedule_sid=schedule_id)
    except Schedule.DoesNotExist:
        return JsonResponse({'error': '일정을 찾을 수 없습니다.'}, status=404)

    if request.method == 'GET':
        try:
            schedule_shares = ScheduleShare.objects.filter(schedule=schedule)
            owner_id = _resolve_owner_id(request.user)
            is_owner = schedule.created_id == owner_id

            shared_users = [
                {
                    'user_id': share.user_id,
                    'email': share.user_id,  # 임시
                    'name': share.user_id,   # 임시
                    'created_at': share.created_at.isoformat() if share.created_at else None,
                }
                for share in schedule_shares
            ]

            return JsonResponse({
                'results': shared_users,
                'is_owner': is_owner,
                'current_user_id': owner_id,
                'schedule_owner_id': schedule.created_id
            })
        except Exception as e:
            print(f"[ERROR] Error loading shared users: {e}")
            return JsonResponse({'results': []})
    
    elif request.method == 'POST':
        # 공유는 본인이 생성한 일정만 가능
        owner_id = _resolve_owner_id(request.user)
        if schedule.created_id != owner_id:
            return JsonResponse({'error': '본인이 생성한 일정만 공유할 수 있습니다.'}, status=403)
        
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "invalid_json"}, status=400)
        
        shared_members = data.get("sharedMembers", [])
        if not shared_members:
            return JsonResponse({"error": "sharedMembers_required"}, status=400)
        
        owner_id = _resolve_owner_id(request.user)
        created_shares = []
        
        for member in shared_members:
            # user_id, id, email 순서로 확인
            user_identifier = member.get('user_id') or member.get('id') or member.get('email')
            if not user_identifier:
                continue
            
            # 이메일이면 실제 user_id로 변환
            user_id = None
            if '@' in str(user_identifier):
                # 이메일인 경우 실제 user_id 찾기
                try:
                    user = CustomUser.objects.get(email=user_identifier)
                    user_id = user.user_id
                except CustomUser.DoesNotExist:
                    print(f"[WARNING] User with email {user_identifier} not found, skipping")
                    continue
            else:
                # user_id 또는 id인 경우, 실제 user_id인지 확인
                try:
                    # 먼저 user_id로 직접 조회
                    user = CustomUser.objects.get(user_id=user_identifier)
                    user_id = user.user_id
                except CustomUser.DoesNotExist:
                    # user_id가 아니면 id로 조회 시도 (만약 id가 다른 필드라면)
                    try:
                        user = CustomUser.objects.get(pk=user_identifier)
                        user_id = user.user_id
                    except (CustomUser.DoesNotExist, ValueError):
                        # 둘 다 실패하면 그냥 user_identifier를 user_id로 사용 (UUID 형식일 수 있음)
                        user_id = str(user_identifier)
            
            if not user_id:
                print(f"[WARNING] Could not resolve user_id for {user_identifier}, skipping")
                continue
            
            # 이미 초대된 사용자인지 확인 (pending invitation)
            existing_invitation = ScheduleInvitation.objects.filter(
                schedule=schedule, 
                user_id=user_id,
                status=ScheduleInvitation.Status.PENDING
            ).first()
            if existing_invitation:
                continue
            
            # 이미 수락된 공유인지 확인
            existing_share = ScheduleShare.objects.filter(schedule=schedule, user_id=user_id).first()
            if existing_share:
                continue
            
            # 자기 자신에게 공유하는 것은 방지
            if user_id == owner_id:
                continue
            
            # ScheduleInvitation 생성 (pending 상태)
            invitation = ScheduleInvitation.objects.create(
                schedule=schedule,
                user_id=user_id,
                created_id=owner_id,
                status=ScheduleInvitation.Status.PENDING,
            )
            created_shares.append({
                'user_id': invitation.user_id,
                'email': invitation.user_id,
                'name': invitation.user_id,
            })
        
        return JsonResponse({
            'status': 'success',
            'message': f'{len(created_shares)}명과 공유되었습니다.',
            'shared_users': created_shares
        }, status=201)
    
    elif request.method == 'DELETE':
        # 공유 제거 또는 일정 나가기
        owner_id = _resolve_owner_id(request.user)
        is_owner = schedule.created_id == owner_id
        
        # user_id 파라미터가 있으면 특정 사용자 공유 제거 (소유자만 가능)
        user_id_to_remove = request.GET.get('user_id')
        if user_id_to_remove:
            if not is_owner:
                return JsonResponse({'error': '본인이 생성한 일정만 공유를 제거할 수 있습니다.'}, status=403)
            
            try:
                share = ScheduleShare.objects.get(schedule=schedule, user_id=user_id_to_remove)
                share.delete()
                return JsonResponse({
                    'status': 'success',
                    'message': '공유가 제거되었습니다.'
                })
            except ScheduleShare.DoesNotExist:
                return JsonResponse({'error': '공유 정보를 찾을 수 없습니다.'}, status=404)
        
        # user_id가 없으면 일정 나가기 (공유된 사용자만 가능)
        if is_owner:
            return JsonResponse({'error': '일정 소유자는 일정에서 나갈 수 없습니다.'}, status=403)
        
        try:
            share = ScheduleShare.objects.get(schedule=schedule, user_id=owner_id)
            share.delete()
            return JsonResponse({
                'status': 'success',
                'message': '일정에서 나갔습니다.'
            })
        except ScheduleShare.DoesNotExist:
            return JsonResponse({'error': '공유 정보를 찾을 수 없습니다.'}, status=404)


@login_required
@require_http_methods(["GET"])
def invitation_list(request: HttpRequest) -> JsonResponse:
    """받은 invitation 목록 조회"""
    owner_id = _resolve_owner_id(request.user)
    
    try:
        invitations = ScheduleInvitation.objects.filter(
            user_id=owner_id,
            status=ScheduleInvitation.Status.PENDING
        ).select_related('schedule', 'schedule__calendar').order_by('-created_at')
        
        invitation_list = []
        for invitation in invitations:
            schedule = invitation.schedule
            # 공유한 사용자 정보 (created_id로 찾기)
            sharer_id = invitation.created_id
            sharer_name = None
            sharer_email = None
            
            # CustomUser에서 사용자 정보 조회
            try:
                sharer_user = CustomUser.objects.get(user_id=sharer_id)
                sharer_name = sharer_user.full_name or sharer_user.email.split('@')[0] if sharer_user.email else None
                sharer_email = sharer_user.email
            except CustomUser.DoesNotExist:
                # 사용자를 찾을 수 없으면 sharer_id를 그대로 사용
                sharer_name = sharer_id
                sharer_email = None
            
            invitation_list.append({
                'id': invitation.invitation_sid,
                'schedule_id': schedule.schedule_sid,
                'schedule_title': schedule.title,
                'schedule_description': schedule.description or '',
                'schedule_start_date': schedule.start_date.isoformat() if schedule.start_date else None,
                'schedule_end_date': schedule.end_date.isoformat() if schedule.end_date else None,
                'schedule_type': schedule.schedule_type,
                'schedule_location': schedule.location or '',
                'sharer_id': sharer_id,
                'sharer_name': sharer_name,
                'sharer_email': sharer_email,
                'created_at': invitation.created_at.isoformat() if invitation.created_at else None,
            })
        
        return JsonResponse({
            'results': invitation_list,
            'count': len(invitation_list)
        })
    except Exception as e:
        print(f"[ERROR] Error loading invitations: {e}")
        return JsonResponse({'results': [], 'count': 0})


@login_required
@require_http_methods(["POST"])
def accept_invitation(request: HttpRequest, invitation_id: int) -> JsonResponse:
    """Invitation 수락 - 선택한 캘린더에 일정 복사"""
    from django.db import transaction
    
    owner_id = _resolve_owner_id(request.user)
    
    try:
        invitation = ScheduleInvitation.objects.get(
            invitation_sid=invitation_id,
            user_id=owner_id,
            status=ScheduleInvitation.Status.PENDING
        )
    except ScheduleInvitation.DoesNotExist:
        return JsonResponse({'error': '초대를 찾을 수 없습니다.'}, status=404)
    
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid_json"}, status=400)
    
    calendar_id = data.get("calendar_id")
    if not calendar_id:
        return JsonResponse({"error": "calendar_id_required"}, status=400)
    
    # 공유자의 캘린더 확인
    try:
        calendar = UserCalendar.objects.get(
            calendar_sid=calendar_id,
            created_id=owner_id
        )
    except UserCalendar.DoesNotExist:
        return JsonResponse({'error': '캘린더를 찾을 수 없습니다.'}, status=404)
    
    original_schedule = invitation.schedule
    
    with transaction.atomic():
        # 일정 복사
        copied_schedule = Schedule.objects.create(
            title=original_schedule.title,
            description=original_schedule.description,
            schedule_type=original_schedule.schedule_type,
            schedule_status=original_schedule.schedule_status,
            start_date=original_schedule.start_date,
            end_date=original_schedule.end_date,
            is_all_day=original_schedule.is_all_day,
            location=original_schedule.location,
            color=original_schedule.color,
            calendar=calendar,
            repeat_type=original_schedule.repeat_type,
            linked_note_sid=original_schedule.linked_note_sid,
            original_schedule=original_schedule,
            is_shared_copy=True,
            created_id=owner_id,
            updated_id=owner_id,
            use_yn='Y',
        )
        
        # ScheduleInvitation 업데이트
        invitation.status = ScheduleInvitation.Status.ACCEPTED
        invitation.shared_schedule = copied_schedule
        invitation.accepted_calendar = calendar
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        # ScheduleShare 생성 (수락된 공유 기록)
        ScheduleShare.objects.create(
            schedule=original_schedule,
            user_id=owner_id,
            shared_schedule=copied_schedule,
            created_id=invitation.created_id,
        )
    
    return JsonResponse({
        'status': 'success',
        'message': '초대를 수락했습니다.',
        'schedule_id': copied_schedule.schedule_sid,
        'calendar_id': calendar.calendar_sid
    })


@login_required
@require_http_methods(["POST"])
def reject_invitation(request: HttpRequest, invitation_id: int) -> JsonResponse:
    """Invitation 거절"""
    owner_id = _resolve_owner_id(request.user)
    
    try:
        invitation = ScheduleInvitation.objects.get(
            invitation_sid=invitation_id,
            user_id=owner_id,
            status=ScheduleInvitation.Status.PENDING
        )
    except ScheduleInvitation.DoesNotExist:
        return JsonResponse({'error': '초대를 찾을 수 없습니다.'}, status=404)
    
    invitation.status = ScheduleInvitation.Status.REJECTED
    invitation.rejected_at = timezone.now()
    invitation.save()
    
    return JsonResponse({
        'status': 'success',
        'message': '초대를 거절했습니다.'
    })
