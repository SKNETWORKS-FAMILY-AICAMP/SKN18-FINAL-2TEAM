# schedule/service.py

import json
import urllib.parse
from urllib.parse import quote  # ✅ calendar_id URL 인코딩용
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction

from .models import (
    GoogleCredentials,
    SyncedCalendar,
    Schedule,
    GoogleSyncedEvent,
    UserCalendar,
)
from django.views.decorators.http import require_GET, require_http_methods

# ---------------------------------------------------------------------
# 0) 공통: 토큰 갱신 / 자격증명 헬퍼
# ---------------------------------------------------------------------
def _refresh_google_token(creds: GoogleCredentials) -> GoogleCredentials:
    """access_token 이 만료되었을 때 refresh_token 으로 새 토큰을 받는 함수."""
    if not creds.refresh_token:
        return creds

    data = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "grant_type": "refresh_token",
    }
    res = requests.post("https://oauth2.googleapis.com/token", data=data)
    info = res.json()

    new_access = info.get("access_token")
    expires_in = info.get("expires_in", 0)

    if new_access:
        creds.access_token = new_access
        creds.expiry = timezone.now() + timedelta(seconds=expires_in)
        creds.save()

    return creds


def _get_valid_creds(user) -> GoogleCredentials:
    """DB 에서 자격증명을 가져오고, 만료되었으면 refresh 후 반환."""
    creds = GoogleCredentials.objects.get(user=user)
    if creds.expiry and creds.expiry <= timezone.now():
        creds = _refresh_google_token(creds)
    return creds


def _json_error(msg: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": msg}, status=status)


def _parse_json_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


# ✅ 추가: 기본 색상/색상 검증
DEFAULT_CAL_COLOR = "#4285F4"

def _normalize_hex_color(value: str | None) -> str:
    """
    '#RRGGBB' 형태만 허용하고 아니면 기본값으로.
    """
    if not value or not isinstance(value, str):
        return DEFAULT_CAL_COLOR
    v = value.strip()
    if len(v) == 7 and v.startswith("#"):
        hex_part = v[1:]
        try:
            int(hex_part, 16)
            return v
        except Exception:
            return DEFAULT_CAL_COLOR
    return DEFAULT_CAL_COLOR


def _owner_identifier(user) -> str:
    if not user or not getattr(user, "is_authenticated", False):
        return "system"
    raw = getattr(user, "user_id", None)
    if raw:
        return str(raw)
    return getattr(user, "email", "system")


def _user_calendar_queryset(user):
    owner_id = _owner_identifier(user)
    if not owner_id:
        return UserCalendar.objects.none()
    return UserCalendar.objects.filter(created_id=owner_id)


def _next_user_calendar_sort(owner_id: str) -> int:
    last = (
        UserCalendar.objects.filter(created_id=owner_id)
        .order_by("-sort_order")
        .values_list("sort_order", flat=True)
        .first()
    )
    return (last or 0) + 1


def _ensure_google_user_calendar(user, synced_calendar: SyncedCalendar) -> UserCalendar | None:
    owner_id = _owner_identifier(user)
    if not owner_id:
        return None

    qs = UserCalendar.objects.filter(
        created_id=owner_id,
        source_type=UserCalendar.Source.GOOGLE,
        external_id=synced_calendar.calendar_id,
    )
    calendar = qs.first()

    if calendar is None and not synced_calendar.selected:
        return None

    defaults = {
        "calendar_name": synced_calendar.summary or synced_calendar.calendar_id,
        "color": _normalize_hex_color(getattr(synced_calendar, "color", None)),
        "is_visible": 1,
        "sort_order": _next_user_calendar_sort(owner_id),
        "created_id": owner_id,
        "updated_id": owner_id,
        "source_type": UserCalendar.Source.GOOGLE,
        "external_id": synced_calendar.calendar_id,
    }

    if calendar is None:
        calendar = UserCalendar.objects.create(**defaults)
        return calendar

    updated_fields: list[str] = []
    desired_name = defaults["calendar_name"]
    if calendar.calendar_name != desired_name:
        calendar.calendar_name = desired_name
        updated_fields.append("calendar_name")

    desired_color = defaults["color"]
    if desired_color and calendar.color != desired_color:
        calendar.color = desired_color
        updated_fields.append("color")

    desired_visible = 1 if synced_calendar.selected else 0
    if calendar.is_visible != desired_visible:
        calendar.is_visible = desired_visible
        updated_fields.append("is_visible")

    if updated_fields:
        calendar.updated_id = owner_id
        updated_fields.append("updated_id")
        calendar.save(update_fields=updated_fields)

    return calendar


def _sync_user_calendars_from_google(user):
    owner_id = _owner_identifier(user)
    if not owner_id:
        return

    selected = SyncedCalendar.objects.filter(user=user, selected=True)
    keep_external_ids: set[str] = set()
    for cal in selected:
        entry = _ensure_google_user_calendar(user, cal)
        if entry:
            keep_external_ids.add(cal.calendar_id)

    qs = UserCalendar.objects.filter(
        created_id=owner_id,
        source_type=UserCalendar.Source.GOOGLE,
    )
    if keep_external_ids:
        qs = qs.exclude(external_id__in=keep_external_ids)
    qs.delete()


def _parse_google_datetime_payload(info: dict | None) -> datetime:
    """
    구글 이벤트 start/end payload를 timezone-aware datetime으로 변환.
    """
    if not info:
        return timezone.now()

    value = info.get("dateTime")
    if value:
        dt = parse_datetime(value)
        if dt is None:
            try:
                dt = datetime.fromisoformat(value)
            except Exception:
                dt = None
        if dt:
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt

    date_value = info.get("date")
    if date_value:
        try:
            base = datetime.fromisoformat(date_value)
        except Exception:
            try:
                base = datetime.strptime(date_value, "%Y-%m-%d")
            except Exception:
                return timezone.now()
        naive = datetime.combine(base.date(), datetime.min.time())
        return timezone.make_aware(naive, timezone.get_current_timezone())

    return timezone.now()


def _coerce_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    try:
        parsed = datetime.fromisoformat(value)
    except Exception:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _ensure_calendar_cache(user, creds: GoogleCredentials) -> GoogleCredentials:
    """
    Google CalendarList를 SyncedCalendar 테이블에 반영.
    """
    headers = {"Authorization": f"Bearer {creds.access_token}"}
    resp = requests.get(
        "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        headers=headers,
        timeout=10,
    )

    if resp.status_code == 401 and creds.refresh_token:
        creds = _refresh_google_token(creds)
        headers = {"Authorization": f"Bearer {creds.access_token}"}
        resp = requests.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers=headers,
            timeout=10,
        )

    if resp.status_code == 200:
        data = resp.json()
        for item in data.get("items", []):
            cid = item.get("id")
            if not cid:
                continue
            summary = item.get("summary", cid)
            SyncedCalendar.objects.update_or_create(
                user=user,
                calendar_id=cid,
                defaults={
                    "summary": summary,
                    "color": _normalize_hex_color(item.get("backgroundColor")),
                },
            )

    return creds


def _upsert_schedule_from_google_payload(
    *,
    user,
    calendar: SyncedCalendar,
    event_payload: dict,
    owner_id: str,
) -> Schedule:
    """
    Google 이벤트 JSON을 Schedule + GoogleSyncedEvent에 저장/갱신.
    """
    event_id = event_payload.get("id")
    if not event_id:
        raise ValueError("google event payload missing id")

    start_info = event_payload.get("start", {})
    end_info = event_payload.get("end", {})
    is_all_day = "date" in start_info or "date" in end_info

    start_dt = _parse_google_datetime_payload(start_info)
    end_dt = _parse_google_datetime_payload(end_info) if end_info else start_dt + timedelta(hours=1)

    # Google all-day end는 exclusive (다음 날 00:00:00)이므로 실제 종료일로 변환
    # 예: start: 2026-01-13, end: 2026-01-14 (exclusive) → 실제로는 2026-01-13 종일
    # 따라서 end_dt를 하루 빼서 같은 날로 맞춤
    if is_all_day:
        # 종일 일정의 경우 end date를 하루 빼서 저장 (같은 날짜로)
        # Google API의 exclusive end를 inclusive end로 변환
        if end_dt > start_dt:
            # end_dt가 start_dt보다 크면 (보통 하루 차이) 하루 빼기
            end_dt = end_dt - timedelta(days=1)
            # 종일 일정이므로 시간을 23:59:59로 설정
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        elif end_dt <= start_dt:
            # end_dt가 start_dt보다 작거나 같으면 같은 날로 설정
            end_dt = start_dt.replace(hour=23, minute=59, second=59)
    elif end_dt <= start_dt:
        # 일반 일정의 경우
        end_dt = start_dt + timedelta(hours=1)

    title = event_payload.get("summary") or "(제목 없음)"
    description = event_payload.get("description") or ""
    location = event_payload.get("location") or ""

    user_calendar = _ensure_google_user_calendar(user, calendar)

    with transaction.atomic():
        link = GoogleSyncedEvent.objects.select_for_update().filter(
            user=user, calendar=calendar, event_id=event_id
        ).select_related("schedule").first()

        if link and link.schedule:
            schedule = link.schedule
        else:
            schedule = Schedule.objects.create(
                title=title,
                description=description,
                schedule_type="M",
                schedule_status="E",
                use_yn="Y",
                start_date=start_dt,
                end_date=end_dt,
                is_all_day="Y" if is_all_day else "N",
                location=location,
                color=calendar.color or DEFAULT_CAL_COLOR,
                repeat_type="N",
                calendar=user_calendar,
                created_id=owner_id,
                updated_id=owner_id,
            )
            link = GoogleSyncedEvent.objects.create(
                user=user,
                calendar=calendar,
                schedule=schedule,
                event_id=event_id,
            )

        # schedule 정보 갱신
        schedule.title = title
        schedule.description = description
        schedule.location = location
        schedule.start_date = start_dt
        schedule.end_date = end_dt
        schedule.is_all_day = "Y" if is_all_day else "N"
        schedule.schedule_type = schedule.schedule_type or "M"
        schedule.schedule_status = "E"
        schedule.repeat_type = schedule.repeat_type or "N"
        schedule.color = calendar.color or schedule.color or DEFAULT_CAL_COLOR
        schedule.use_yn = "Y"
        if user_calendar and schedule.calendar_id != user_calendar.calendar_sid:
            schedule.calendar = user_calendar
        schedule.updated_id = owner_id
        if not schedule.created_id:
            schedule.created_id = owner_id
        schedule.save(
            update_fields=[
                "title",
                "description",
                "location",
                "start_date",
                "end_date",
                "is_all_day",
                "schedule_type",
                "schedule_status",
                "repeat_type",
                "color",
                "use_yn",
                "updated_id",
                "created_id",
                "updated_at",
            ]
        )

        link.summary = title
        link.status = event_payload.get("status", "confirmed")
        link.etag = event_payload.get("etag")
        updated_raw = event_payload.get("updated")
        link.google_updated = parse_datetime(updated_raw) if updated_raw else None
        link.raw_payload = event_payload
        link.save(update_fields=["summary", "status", "etag", "google_updated", "raw_payload", "updated_at"])

    return schedule


def _deactivate_missing_events(
    user,
    calendar,
    synced_ids: set[str],
    owner_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> int:
    """
    더 이상 Google에서 내려오지 않는 이벤트는 RDB에서 비활성화.
    """
    removed = 0
    qs = GoogleSyncedEvent.objects.filter(
        user=user,
        calendar=calendar,
        schedule__start_date__gte=start_dt,
        schedule__start_date__lte=end_dt,
    )
    if synced_ids:
        qs = qs.exclude(event_id__in=synced_ids)

    for link in qs.select_related("schedule"):
        if link.schedule and link.schedule.use_yn != "N":
            link.schedule.use_yn = "N"
            link.schedule.updated_id = owner_id
            link.schedule.save(update_fields=["use_yn", "updated_id", "updated_at"])
        link.status = "deleted"
        link.save(update_fields=["status", "updated_at"])
        removed += 1
    return removed


def _sync_google_events_to_db(user, *, start_dt: datetime | None = None, end_dt: datetime | None = None) -> dict:
    """
    선택된 Google 캘린더 이벤트를 RDB(t_schedule)로 동기화.
    """
    if not user or not user.is_authenticated:
        return {"synced": 0, "removed": 0, "status": "unauthenticated"}

    try:
        creds = _get_valid_creds(user)
    except GoogleCredentials.DoesNotExist:
        return {"synced": 0, "removed": 0, "status": "no_credentials"}

    start_dt = start_dt or (timezone.now() - timedelta(days=30))
    end_dt = end_dt or (timezone.now() + timedelta(days=90))

    owner_id = _owner_identifier(user)

    creds = _ensure_calendar_cache(user, creds)

    calendar_qs = SyncedCalendar.objects.filter(user=user)
    selected = calendar_qs.filter(selected=True)
    calendars = list(selected or calendar_qs)
    if not calendars:
        return {"synced": 0, "removed": 0, "status": "no_calendars"}

    synced_count = 0
    removed_count = 0

    headers = {"Authorization": f"Bearer {creds.access_token}"}
    time_min = start_dt.isoformat()
    time_max = end_dt.isoformat()

    for calendar in calendars:
        encoded_cal_id = quote(calendar.calendar_id, safe="")
        page_token = None
        current_ids: set[str] = set()

        while True:
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if page_token:
                params["pageToken"] = page_token

            res = requests.get(
                f"https://www.googleapis.com/calendar/v3/calendars/{encoded_cal_id}/events",
                headers=headers,
                params=params,
                timeout=15,
            )

            if res.status_code == 401 and creds.refresh_token:
                creds = _refresh_google_token(creds)
                headers = {"Authorization": f"Bearer {creds.access_token}"}
                continue

            if res.status_code != 200:
                break

            data = res.json()
            for item in data.get("items", []):
                event_id = item.get("id")
                if not event_id:
                    continue
                current_ids.add(event_id)
                _upsert_schedule_from_google_payload(
                    user=user,
                    calendar=calendar,
                    event_payload=item,
                    owner_id=owner_id,
                )
                synced_count += 1

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        removed_count += _deactivate_missing_events(
            user,
            calendar,
            current_ids,
            owner_id,
            start_dt,
            end_dt,
        )

    return {
        "synced": synced_count,
        "removed": removed_count,
        "status": "ok",
        "calendars": len(calendars),
    }


# ---------------------------------------------------------------------
# 반복 RRULE 생성
# ---------------------------------------------------------------------
def _build_rrule_from_payload(repeat_type: str | None, repeat_until_date: str | None) -> str | None:
    """
    repeat_type: "none" / "daily" / "weekly" / "monthly"
    repeat_until_date: "YYYY-MM-DD" or None
    """
    if not repeat_type or repeat_type == "none":
        return None

    parts: list[str] = []
    if repeat_type == "daily":
        parts.append("FREQ=DAILY")
    elif repeat_type == "weekly":
        parts.append("FREQ=WEEKLY")
    elif repeat_type == "monthly":
        parts.append("FREQ=MONTHLY")
    else:
        return None

    if repeat_until_date:
        try:
            dt = datetime.fromisoformat(repeat_until_date).date()
            until_str = dt.strftime("%Y%m%dT000000Z")
            parts.append(f"UNTIL={until_str}")
        except Exception:
            pass

    return "RRULE:" + ";".join(parts)


# ---------------------------------------------------------------------
# Google 이벤트 start/end payload 생성
# ---------------------------------------------------------------------
def _build_event_datetime_payload(
    *,
    title: str,
    all_day: bool,
    start_date: str,
    end_date: str,
    start_time: str | None = None,
    end_time: str | None = None,
    for_update: bool = False,
) -> dict:
    """
    - all_day=True  => start.date / end.date (+1day exclusive)
    - all_day=False => start.dateTime / end.dateTime
    """
    if all_day:
        try:
            s = datetime.fromisoformat(start_date).date()
            e = datetime.fromisoformat(end_date).date() + timedelta(days=1)  # exclusive
        except Exception:
            s = e = timezone.localdate()

        start_obj = {"date": s.isoformat()}
        end_obj = {"date": e.isoformat()}

        if for_update:
            start_obj["dateTime"] = None
            start_obj["timeZone"] = None
            end_obj["dateTime"] = None
            end_obj["timeZone"] = None

        return {"summary": title, "start": start_obj, "end": end_obj}

    if not start_time:
        start_time = "09:00"
    if not end_time:
        end_time = "10:00"

    start_dt = f"{start_date}T{start_time}:00+09:00"
    end_dt = f"{end_date}T{end_time}:00+09:00"

    start_obj = {"dateTime": start_dt, "timeZone": "Asia/Seoul"}
    end_obj = {"dateTime": end_dt, "timeZone": "Asia/Seoul"}

    if for_update:
        start_obj["date"] = None
        end_obj["date"] = None

    return {"summary": title, "start": start_obj, "end": end_obj}


# ---------------------------------------------------------------------
# 1) OAuth 시작
# ---------------------------------------------------------------------
def google_login(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)

    if GoogleCredentials.objects.filter(user=request.user).exists():
        return redirect("schedule:schedule")

    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.GOOGLE_CALENDAR_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)


# ---------------------------------------------------------------------
# 2) OAuth 콜백
# ---------------------------------------------------------------------
def google_callback(request: HttpRequest) -> HttpResponse:
    print("✅ google_callback called", request.user, "has_code=", bool(request.GET.get("code")))
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)

    if "error" in request.GET:
        print("⛔ google_callback error param:", request.GET.get("error"))
        return redirect("schedule:schedule")

    code = request.GET.get("code")
    if not code:
        print("⛔ google_callback: no code in querystring", dict(request.GET))
        return redirect("schedule:schedule")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    res = requests.post(token_url, data=data)
    print("✅ token response status:", res.status_code, "body:", res.text[:300])
    token_info = res.json()

    access_token = token_info.get("access_token")
    if not access_token:
        return redirect("schedule:schedule")

    refresh_token = token_info.get("refresh_token")
    expires_in = token_info.get("expires_in", 0)
    expiry = timezone.now() + timedelta(seconds=expires_in)

    GoogleCredentials.objects.update_or_create(
        user=request.user,
        defaults={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "scopes": settings.GOOGLE_CALENDAR_SCOPE,
            "expiry": expiry,
        },
    )
    return redirect("schedule:calendar_settings")


# ---------------------------------------------------------------------
# 3) 연동 해제
# ---------------------------------------------------------------------
def google_logout(request: HttpRequest) -> HttpResponse:
    """
    구글 계정 연동 제거
    
    안전한 처리 방식:
    1. GoogleCredentials 삭제 (동기화 토큰 제거)
    2. UserCalendar (GOOGLE) → LOCAL 변환 (UI 유지)
    3. SyncedCalendar 보존 (GoogleSyncedEvent의 calendar 참조 유지를 위해)
    4. GoogleSyncedEvent 보존 (재연동 시 event_id로 upsert 가능)
    
    주의: GoogleSyncedEvent.calendar는 SyncedCalendar를 ForeignKey로 참조하므로,
    SyncedCalendar를 삭제하면 CASCADE로 GoogleSyncedEvent도 삭제됩니다.
    따라서 event_id 매핑 정보를 보존하려면 SyncedCalendar도 보존해야 합니다.
    재연동 시 동일한 calendar_id로 SyncedCalendar가 생성되면 기존 GoogleSyncedEvent를 찾을 수 있습니다.
    """
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)

    user = request.user
    owner_id = _owner_identifier(user)
    
    # 1. GoogleCredentials 삭제 (동기화 토큰 제거 - 동기화 중단)
    GoogleCredentials.objects.filter(user=user).delete()
    
    # 2. UserCalendar (GOOGLE) → LOCAL 변환
    #    - source_type을 LOCAL로 변경
    #    - external_id는 보존 (재연동 시 calendar_id 매핑에 사용 가능)
    #    - UI는 LOCAL 캘린더로 표시되지만 external_id는 보존
    google_calendars = UserCalendar.objects.filter(
        created_id=owner_id,
        source_type=UserCalendar.Source.GOOGLE
    )
    
    for calendar in google_calendars:
        calendar.source_type = UserCalendar.Source.LOCAL
        # external_id는 보존 (재연동 시 calendar_id 매핑에 사용)
        calendar.save(update_fields=['source_type'])
    
    # 3. SyncedCalendar 보존
    #    - GoogleSyncedEvent.calendar가 SyncedCalendar를 ForeignKey로 참조 (CASCADE)
    #    - SyncedCalendar를 삭제하면 GoogleSyncedEvent도 삭제됨
    #    - 재연동 시 동일한 calendar_id로 SyncedCalendar가 생성되면
    #      GoogleSyncedEvent의 calendar 참조를 업데이트할 수 있음
    #    - 또는 재연동 시 external_id와 calendar_id를 매칭하여 처리
    #    - 현재는 보존 (동기화만 중단, 데이터는 유지)
    # SyncedCalendar.objects.filter(user=user).delete()  # 보존
    
    # 4. GoogleSyncedEvent 보존
    #    - 재연동 시 event_id로 기존 Schedule을 찾아 업데이트 가능
    #    - SyncedCalendar를 보존하므로 GoogleSyncedEvent도 보존됨
    
    return redirect("schedule:schedule")


# ---------------------------------------------------------------------
# 4) 연동 캘린더 선택 페이지
# ---------------------------------------------------------------------
def calendar_settings(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)

    try:
        creds = _get_valid_creds(request.user)
    except GoogleCredentials.DoesNotExist:
        return redirect("schedule:google_login")

    headers = {"Authorization": f"Bearer {creds.access_token}"}
    resp = requests.get(
        "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        headers=headers,
    )

    if resp.status_code == 200:
        data = resp.json()
        for item in data.get("items", []):
            cid = item["id"]
            summary = item.get("summary", cid)

            # ✅ color는 기존 DB 값 유지 (없으면 기본값)
            obj, created = SyncedCalendar.objects.update_or_create(
                user=request.user,
                calendar_id=cid,
                defaults={"summary": summary},
            )
            if not getattr(obj, "color", None):
                try:
                    obj.color = DEFAULT_CAL_COLOR
                    obj.save(update_fields=["color"])
                except Exception:
                    pass

    if request.method == "POST":
        selected_ids = request.POST.getlist("calendars")
        SyncedCalendar.objects.filter(user=request.user).update(selected=False)
        for cal in SyncedCalendar.objects.filter(user=request.user):
            cal.selected = cal.calendar_id in selected_ids
            cal.save()
        return redirect("schedule:schedule")

    calendars = SyncedCalendar.objects.filter(user=request.user).order_by("summary")
    return render(request, "schedule/calendar_settings.html", {"calendars": calendars})


# ---------------------------------------------------------------------
# 5) 이벤트 READ (FullCalendar용)
# ---------------------------------------------------------------------
def google_events_api(request: HttpRequest) -> JsonResponse:
    print("✅ google_events_api CALLED")

    if not request.user.is_authenticated:
        print("⛔ not authenticated")
        return JsonResponse([], safe=False)

    try:
        creds = _get_valid_creds(request.user)
        print("✅ creds ok / has refresh_token =", bool(creds.refresh_token))
    except GoogleCredentials.DoesNotExist:
        print("⛔ creds does not exist")
        return JsonResponse([], safe=False)

    headers = {"Authorization": f"Bearer {creds.access_token}"}

    synced = list(SyncedCalendar.objects.filter(user=request.user, selected=True))
    print("✅ synced selected count =", len(synced))

    if not synced:
        calendar_ids = ["primary"]
        color_map = {"primary": DEFAULT_CAL_COLOR}
    else:
        calendar_ids = [c.calendar_id for c in synced]
        color_map = {c.calendar_id: _normalize_hex_color(getattr(c, "color", None)) for c in synced}

    time_min = request.GET.get("start")
    time_max = request.GET.get("end")

    if not time_min or not time_max:
        now = timezone.now()
        time_min = (now - timedelta(days=30)).isoformat()
        time_max = (now + timedelta(days=60)).isoformat()

    params = {"timeMin": time_min, "timeMax": time_max, "singleEvents": True, "orderBy": "startTime"}

    results = []

    for cal_id in calendar_ids:
        encoded_cal_id = quote(cal_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_cal_id}/events"

        res = requests.get(url, headers=headers, params=params)

        if res.status_code == 401:
            print("⚠️ 401 from Google. Try refresh token once. cal_id =", cal_id)
            if not creds.refresh_token:
                print("⛔ no refresh_token. Need reconnect.")
                continue

            creds = _refresh_google_token(creds)
            headers = {"Authorization": f"Bearer {creds.access_token}"}
            res = requests.get(url, headers=headers, params=params)

        if res.status_code != 200:
            print("❌ Google API failed:", cal_id, res.status_code, res.text[:200])
            continue

        for item in res.json().get("items", []):
            event_id = item["id"]
            title = item.get("summary", "(제목 없음)")
            start_info = item.get("start", {})
            end_info = item.get("end", {})

            if "date" in start_info:
                all_day = True
                start = start_info["date"]
                end_raw = end_info.get("date", start)
                try:
                    end_dt = datetime.fromisoformat(end_raw) - timedelta(days=1)
                    end = end_dt.date().isoformat()
                except Exception:
                    end = start
            else:
                all_day = False
                start = start_info.get("dateTime")
                end = end_info.get("dateTime")

            results.append({
                "id": event_id,
                "title": title,
                "start": start,
                "end": end,
                "allDay": all_day,

                # ✅ 캘린더별 색 적용
                "color": color_map.get(cal_id, DEFAULT_CAL_COLOR),

                "extendedProps": {
                    "googleEventId": event_id,
                    "calendarId": cal_id,
                    "description": item.get("description", "") or "",
                    "location": item.get("location", "") or "",
                },
            })

    return JsonResponse(results, safe=False, json_dumps_params={"ensure_ascii": False})


# ---------------------------------------------------------------------
# 6) CREATE
# ---------------------------------------------------------------------
def google_event_create(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error("login_required", status=401)
    if request.method != "POST":
        return _json_error("POST only", status=405)

    body = _parse_json_body(request)

    title = (body.get("title") or "").strip() or "(제목 없음)"
    calendar_id = body.get("calendar_id") or "primary"
    all_day = bool(body.get("all_day"))
    start_date = body.get("start_date")
    end_date = body.get("end_date") or start_date
    start_time = body.get("start_time")
    end_time = body.get("end_time")

    description = (body.get("description") or "").strip()
    location = (body.get("location") or "").strip()

    reminder_enabled = body.get("reminder_enabled", True)
    if isinstance(reminder_enabled, str):
        reminder_enabled = reminder_enabled.lower() == "true"
    try:
        reminder_minutes = int(body.get("reminder_minutes", 10))
    except Exception:
        reminder_minutes = 10

    repeat_type = body.get("repeat_type")
    repeat_until_date = body.get("repeat_until_date")
    rrule = _build_rrule_from_payload(repeat_type, repeat_until_date)

    if not start_date:
        return _json_error("start_date required")

    try:
        creds = _get_valid_creds(request.user)
    except GoogleCredentials.DoesNotExist:
        return _json_error("no_google_credentials", status=401)

    headers = {"Authorization": f"Bearer {creds.access_token}"}

    encoded_calendar_id = quote(calendar_id, safe="")
    url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events"

    payload = _build_event_datetime_payload(
        title=title,
        all_day=all_day,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        for_update=False,
    )

    if description:
        payload["description"] = description
    if location:
        payload["location"] = location

    if rrule:
        payload["recurrence"] = [rrule]

    if reminder_enabled:
        payload["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        }
    else:
        payload["reminders"] = {"useDefault": False, "overrides": []}

    res = requests.post(url, headers=headers, json=payload)
    if res.status_code not in (200, 201):
        return _json_error(f"google_create_failed: {res.text}", status=400)

    created = res.json()
    return JsonResponse({"ok": True, "id": created.get("id"), "calendarId": calendar_id})


# ---------------------------------------------------------------------
# 7) UPDATE
# ---------------------------------------------------------------------
def google_event_update(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error("login_required", status=401)
    if request.method != "POST":
        return _json_error("POST only", status=405)

    body = _parse_json_body(request)

    event_id = body.get("event_id")
    calendar_id = body.get("calendar_id") or "primary"
    if not event_id:
        return _json_error("event_id required")

    title = (body.get("title") or "").strip() or "(제목 없음)"
    all_day = bool(body.get("all_day"))
    start_date = body.get("start_date")
    end_date = body.get("end_date") or start_date
    start_time = body.get("start_time")
    end_time = body.get("end_time")

    description = (body.get("description") or "").strip()
    location = (body.get("location") or "").strip()

    reminder_enabled = body.get("reminder_enabled")
    if isinstance(reminder_enabled, str):
        reminder_enabled = reminder_enabled.lower() == "true"
    reminder_minutes_raw = body.get("reminder_minutes")
    try:
        reminder_minutes = int(reminder_minutes_raw) if reminder_minutes_raw is not None else None
    except Exception:
        reminder_minutes = None

    repeat_type = body.get("repeat_type")
    repeat_until_date = body.get("repeat_until_date")
    rrule = _build_rrule_from_payload(repeat_type, repeat_until_date)

    try:
        creds = _get_valid_creds(request.user)
    except GoogleCredentials.DoesNotExist:
        return _json_error("no_google_credentials", status=401)

    headers = {"Authorization": f"Bearer {creds.access_token}"}

    encoded_calendar_id = quote(calendar_id, safe="")
    url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events/{event_id}"

    if start_date:
        payload = _build_event_datetime_payload(
            title=title,
            all_day=all_day,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            for_update=True,
        )
    else:
        payload = {"summary": title}

    payload["description"] = description if description else ""
    payload["location"] = location if location else ""

    if repeat_type is not None:
        payload["recurrence"] = [rrule] if rrule else []

    if reminder_enabled is not None:
        if reminder_enabled and reminder_minutes is not None:
            payload["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}],
            }
        else:
            payload["reminders"] = {"useDefault": False, "overrides": []}

    res = requests.patch(url, headers=headers, json=payload)
    if res.status_code not in (200, 201):
        return _json_error(f"google_update_failed: {res.text}", status=400)

    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------
# 8) DELETE
# ---------------------------------------------------------------------
def google_event_delete(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error("login_required", status=401)
    if request.method != "POST":
        return _json_error("POST only", status=405)

    body = _parse_json_body(request)

    event_id = body.get("event_id")
    calendar_id = body.get("calendar_id") or "primary"
    if not event_id:
        return _json_error("event_id required")

    try:
        creds = _get_valid_creds(request.user)
    except GoogleCredentials.DoesNotExist:
        return _json_error("no_google_credentials", status=401)

    headers = {"Authorization": f"Bearer {creds.access_token}"}

    encoded_calendar_id = quote(calendar_id, safe="")
    url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events/{event_id}"

    res = requests.delete(url, headers=headers)
    if res.status_code not in (200, 204):
        return _json_error(f"google_delete_failed: {res.text}", status=400)

    return JsonResponse({"ok": True})


##############################
# 9) ✅ 구글 캘린더 연동 상태 API
##############################
@require_GET
def google_calendar_status(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"connected": False}, status=401)

    connected = GoogleCredentials.objects.filter(user=request.user).exists()
    return JsonResponse({"connected": connected})


@require_http_methods(["GET", "POST"])
def google_calendar_calendars_api(request: HttpRequest) -> JsonResponse:
    """
    모달용:
    - GET  : 구글에서 가져온 캘린더를 SyncedCalendar에 저장해둔 목록 반환 (✅ color 포함)
    - POST : 선택/색상 저장

    지원 payload A (권장/신규):
      {
        "calendars": [
          {"calendar_id":"id1", "selected":true, "color":"#ff0000", "name":"..." },
          {"calendar_id":"id2", "selected":false, "color":"#00ff00"}
        ]
      }

    지원 payload B (JS에서 많이 쓰는 형태):
      {
        "selected_calendar_ids": ["id1","id2"],
        "calendar_colors": {"id1":"#ff0000","id2":"#00ff00"}
      }

    ✅ 호환: calendar-colors 도 허용
    """
    if not request.user.is_authenticated:
        return _json_error("login_required", status=401)

    try:
        creds = _get_valid_creds(request.user)
    except GoogleCredentials.DoesNotExist:
        return JsonResponse([], safe=False)

    # -----------------------------------------------------------------
    # GET: 구글 CalendarList 불러와 DB 갱신 후 반환
    # -----------------------------------------------------------------
    if request.method == "GET":
        headers = {"Authorization": f"Bearer {creds.access_token}"}
        resp = requests.get(
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers=headers,
        )

        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                cid = item["id"]
                summary = item.get("summary", cid)

                obj, _ = SyncedCalendar.objects.update_or_create(
                    user=request.user,
                    calendar_id=cid,
                    defaults={"summary": summary},
                )

                # ✅ color가 비어있으면 기본값으로 세팅
                if not getattr(obj, "color", None):
                    try:
                        obj.color = DEFAULT_CAL_COLOR
                        obj.save(update_fields=["color"])
                    except Exception:
                        pass

        rows = SyncedCalendar.objects.filter(user=request.user).order_by("summary")
        result = [
            {
                "id": r.calendar_id,
                "name": r.summary,
                "email": r.calendar_id,
                "selected": bool(r.selected),
                "color": _normalize_hex_color(getattr(r, "color", None)),
            }
            for r in rows
        ]
        return JsonResponse(result, safe=False, json_dumps_params={"ensure_ascii": False})

    # -----------------------------------------------------------------
    # POST: 선택/색상 저장
    # -----------------------------------------------------------------
    body = _parse_json_body(request)

    # ✅ 1) 신규 payload: calendars: [...]
    calendars_payload = body.get("calendars")
    if isinstance(calendars_payload, list) and len(calendars_payload) > 0:
        SyncedCalendar.objects.filter(user=request.user).update(selected=False)

        updated = 0
        for item in calendars_payload:
            if not isinstance(item, dict):
                continue

            cal_id = item.get("calendar_id") or item.get("email") or item.get("id")
            if not cal_id:
                continue

            selected = bool(item.get("selected", False))
            color = _normalize_hex_color(item.get("color"))
            name = item.get("name") or item.get("summary") or cal_id

            obj, _ = SyncedCalendar.objects.update_or_create(
                user=request.user,
                calendar_id=cal_id,
                defaults={"summary": name},
            )

            try:
                obj.selected = selected
                obj.color = color
                obj.save(update_fields=["selected", "color"])
                updated += 1
            except Exception:
                pass

        _sync_user_calendars_from_google(request.user)
        return JsonResponse({"ok": True, "updated": updated}, json_dumps_params={"ensure_ascii": False})

    # ✅ 2) JS payload: selected_calendar_ids + calendar_colors(dict)
    selected_ids = body.get("selected_calendar_ids", [])
    if not isinstance(selected_ids, list):
        selected_ids = []

    # calendar_colors (언더스코어/대시 둘 다 허용)
    calendar_colors = body.get("calendar_colors")
    if calendar_colors is None:
        calendar_colors = body.get("calendar-colors")
    if not isinstance(calendar_colors, dict):
        calendar_colors = {}

    # (A) selected 저장
    SyncedCalendar.objects.filter(user=request.user).update(selected=False)
    SyncedCalendar.objects.filter(
        user=request.user,
        calendar_id__in=selected_ids
    ).update(selected=True)

    # (B) color 저장 (넘어온 것만 업데이트)
    updated_colors = 0
    for cal_id, color in calendar_colors.items():
        if not isinstance(cal_id, str):
            continue
        normalized = _normalize_hex_color(color)
        updated_colors += SyncedCalendar.objects.filter(
            user=request.user,
            calendar_id=cal_id
        ).update(color=normalized)

    _sync_user_calendars_from_google(request.user)
    return JsonResponse(
        {"ok": True, "updated_colors": updated_colors},
        json_dumps_params={"ensure_ascii": False}
    )


@require_http_methods(["POST"])
def google_events_sync(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return _json_error("login_required", status=401)

    body = _parse_json_body(request)
    start_raw = body.get("timeMin") or body.get("time_min")
    end_raw = body.get("timeMax") or body.get("time_max")

    start_dt = _coerce_to_datetime(start_raw)
    end_dt = _coerce_to_datetime(end_raw)

    summary = _sync_google_events_to_db(
        request.user,
        start_dt=start_dt,
        end_dt=end_dt,
    )
    status_code = 200 if summary.get("status") in {"ok", "no_calendars", "no_credentials"} else 400
    return JsonResponse(summary, status=status_code, json_dumps_params={"ensure_ascii": False})
