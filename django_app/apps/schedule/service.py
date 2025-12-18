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

from .models import GoogleCredentials, SyncedCalendar
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
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)

    GoogleCredentials.objects.filter(user=request.user).delete()
    SyncedCalendar.objects.filter(user=request.user).delete()
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

    return JsonResponse(
        {"ok": True, "updated_colors": updated_colors},
        json_dumps_params={"ensure_ascii": False}
    )
