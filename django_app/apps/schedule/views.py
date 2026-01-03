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
)
from .recurrence import create_recurrence, expand_recurrences


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
    # 본인이 생성한 일정 또는 본인에게 공유된 일정
    from .models import ScheduleShare
    shared_schedule_ids = ScheduleShare.objects.filter(user_id=owner_id).values_list('schedule_id', flat=True)
    filters = Q(created_id=owner_id) | Q(schedule_sid__in=shared_schedule_ids)
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


def _user_calendar_queryset(user):
    owner_id = _resolve_owner_id(user)
    if not owner_id:
        return UserCalendar.objects.none()
    return UserCalendar.objects.filter(created_id=owner_id)


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

    owner_calendars = _user_calendar_queryset(request.user).order_by('sort_order', 'created_at')

    # ✅ Google Calendar connection (토큰 존재 여부로 판단)
    is_google_connected = GoogleCredentials.objects.filter(user=request.user).exists()

    context = {
        'is_google_connected': is_google_connected,
        'user_calendars': [_serialize_user_calendar(cal) for cal in owner_calendars],
        'schedules': [_serialize_schedule_for_template(s, request.user) for s in schedules],
        'current_date': datetime.now(),
    }
    return render(request, 'schedule/schedule.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def user_calendars_api(request: HttpRequest) -> JsonResponse:
    owner_id = _resolve_owner_id(request.user)

    if request.method == "GET":
        calendars = _user_calendar_queryset(request.user).order_by('sort_order', 'created_at')
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
        calendar.delete()
        return JsonResponse({"ok": True})

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
@require_http_methods(["GET", "PATCH"])
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
        return JsonResponse(payload)

    elif request.method == 'PATCH':
        # 공유된 일정은 수정 불가 (본인이 생성한 일정만 수정 가능)
        owner_id = _resolve_owner_id(request.user)
        if schedule.created_id != owner_id:
            return JsonResponse({'error': '공유된 일정은 수정할 수 없습니다.'}, status=403)

        import json
        data = json.loads(request.body)

        # Update status if provided
        if 'status' in data:
            status_map = {
                'scheduled': 'E',
                'in_progress': 'R',
                'completed': 'C',
            }
            schedule.schedule_status = status_map.get(data['status'], 'E')

        # Update other fields if provided
        if 'title' in data:
            schedule.title = data['title']
        if 'description' in data:
            schedule.description = data.get('description', '')
        if 'type' in data:
            schedule.schedule_type = data['type']
        if 'location' in data:
            schedule.location = data.get('location', '')
        if 'color' in data:
            schedule.color = data.get('color', '')

        if 'start_datetime' in data:
            from django.utils.dateparse import parse_datetime
            start_date = parse_datetime(data['start_datetime'])
            if start_date:
                schedule.start_date = start_date

        if 'end_datetime' in data:
            from django.utils.dateparse import parse_datetime
            end_date = parse_datetime(data['end_datetime'])
            if end_date:
                schedule.end_date = end_date

        schedule.updated_id = owner_id
        schedule.save()

        return JsonResponse({
            'id': schedule.schedule_sid,
            'title': schedule.title,
            'status': schedule.status,
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

    from .models import ScheduleShare
    
    if request.method == 'GET':
        try:
            schedule_shares = ScheduleShare.objects.filter(schedule=schedule)

            shared_users = [
                {
                    'user_id': share.user_id,
                    'email': share.user_id,  # 임시
                    'name': share.user_id,   # 임시
                    'created_at': share.created_at.isoformat() if share.created_at else None,
                }
                for share in schedule_shares
            ]

            return JsonResponse({'results': shared_users})
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
            user_id = member.get('user_id') or member.get('email') or member.get('id')
            if not user_id:
                continue
            
            # 이미 공유된 사용자인지 확인
            existing_share = ScheduleShare.objects.filter(schedule=schedule, user_id=user_id).first()
            if existing_share:
                continue
            
            # 자기 자신에게 공유하는 것은 방지
            if user_id == owner_id:
                continue
            
            share = ScheduleShare.objects.create(
                schedule=schedule,
                user_id=user_id,
                created_id=owner_id,
            )
            created_shares.append({
                'user_id': share.user_id,
                'email': share.user_id,
                'name': share.user_id,
            })
        
        return JsonResponse({
            'status': 'success',
            'message': f'{len(created_shares)}명과 공유되었습니다.',
            'shared_users': created_shares
        }, status=201)
