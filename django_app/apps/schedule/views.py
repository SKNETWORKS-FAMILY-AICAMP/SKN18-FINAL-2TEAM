from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from datetime import datetime

from .models import Schedule, UserCalendar, SyncedCalendar, GoogleCredentials


@login_required
def index(request):
    """Schedule page view (인증 필수)."""
    # Load schedules for initial page render
    schedules = Schedule.objects.filter(use_yn='Y').order_by('start_date', 'created_at')[:10]

    # Load user calendars
    user_calendars = UserCalendar.objects.all().order_by('sort_order', 'created_at')

    # ✅ Google Calendar connection (토큰 존재 여부로 판단)
    is_google_connected = GoogleCredentials.objects.filter(user=request.user).exists()

    context = {
        'is_google_connected': is_google_connected,
        'user_calendars': [
            {
                'id': cal.calendar_sid,
                'name': cal.calendar_name,
                'color': cal.color or '#3b82f6',
                'visible': cal.visible,
            }
            for cal in user_calendars
        ],
        'schedules': [
            {
                'id': s.schedule_sid,
                'title': s.title,
                'start_datetime': s.start_date,
                'status': s.schedule_status,
                'get_type_display': s.get_schedule_type_display(),
                'linked_note': s.linked_note_sid,
            }
            for s in schedules
        ],
        'current_date': datetime.now(),
    }
    return render(request, 'schedule/schedule.html', context)


@require_http_methods(["GET"])
def schedule_list(request):
    """일정 목록 API 엔드포인트"""
    schedules = Schedule.objects.filter(use_yn='Y').order_by('start_date', 'created_at')

    formatted_schedules = []
    for schedule in schedules:
        # Get color based on type
        type_colors = {
            'E': '#3b82f6',  # 실험 - blue
            'M': '#a855f7',  # 미팅 - purple
            'A': '#f97316',  # 분석 - orange
            'S': '#ec4899',  # 세미나 - pink
        }
        color = schedule.color or type_colors.get(schedule.schedule_type, '#3b82f6')

        formatted_schedules.append({
            'id': schedule.schedule_sid,
            'title': schedule.title,
            'description': schedule.description or '',
            'type': schedule.schedule_type,
            'get_type_display': schedule.get_schedule_type_display(),
            'status': schedule.status,
            'start_datetime': schedule.start_date.isoformat() if schedule.start_date else None,
            'end_datetime': schedule.end_date.isoformat() if schedule.end_date else None,
            'is_all_day': schedule.is_all_day == 'Y',
            'location': schedule.location or '',
            'color': color,
            'linked_note': schedule.linked_note_sid,
            'repeat_type': schedule.repeat_type,
            'created_at': schedule.created_at.isoformat() if schedule.created_at else None,
        })

    return JsonResponse({'results': formatted_schedules})


@require_http_methods(["GET", "PATCH"])
def schedule_detail(request, schedule_id):
    """일정 상세 조회/수정 API 엔드포인트"""
    print(f"[DEBUG] schedule_detail() called - schedule_id: {schedule_id}, method: {request.method}")

    try:
        schedule = Schedule.objects.get(schedule_sid=schedule_id, use_yn='Y')
        print(f"[DEBUG] Schedule found: {schedule.title}")
    except Schedule.DoesNotExist:
        print(f"[ERROR] Schedule not found - schedule_id: {schedule_id}")
        return JsonResponse({'error': '일정을 찾을 수 없습니다.'}, status=404)

    if request.method == 'GET':
        print(f"[DEBUG] GET request - returning schedule detail")
        # Get color based on type
        type_colors = {
            'E': '#3b82f6',  # 실험 - blue
            'M': '#a855f7',  # 미팅 - purple
            'A': '#f97316',  # 분석 - orange
            'S': '#ec4899',  # 세미나 - pink
        }
        color = schedule.color or type_colors.get(schedule.schedule_type, '#3b82f6')

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

        return JsonResponse({
            'id': schedule.schedule_sid,
            'title': schedule.title,
            'description': schedule.description or '',
            'type': schedule.schedule_type,
            'get_type_display': schedule.get_schedule_type_display(),
            'status': schedule.status,
            'start_datetime': schedule.start_date.isoformat() if schedule.start_date else None,
            'end_datetime': schedule.end_date.isoformat() if schedule.end_date else None,
            'is_all_day': schedule.is_all_day == 'Y',
            'location': schedule.location or '',
            'color': color,
            'linked_note': schedule.linked_note_sid,
            'repeat_type': schedule.repeat_type,
            'created_at': schedule.created_at.isoformat() if schedule.created_at else None,
            'shared_with': shared_users,
        })

    elif request.method == 'PATCH':
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

        schedule.updated_id = request.user.username if request.user.is_authenticated else 'system'
        schedule.save()

        return JsonResponse({
            'id': schedule.schedule_sid,
            'title': schedule.title,
            'status': schedule.status,
            'message': '일정이 수정되었습니다.'
        })


@require_http_methods(["GET"])
def schedule_shared_users(request, schedule_id):
    """일정 공유 사용자 목록 API 엔드포인트"""
    try:
        schedule = Schedule.objects.get(schedule_sid=schedule_id, use_yn='Y')
    except Schedule.DoesNotExist:
        return JsonResponse({'error': '일정을 찾을 수 없습니다.'}, status=404)

    try:
        from .models import ScheduleShare
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
