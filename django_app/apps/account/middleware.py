"""
Account 관련 미들웨어
"""
import time
from datetime import datetime
from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout
from django.contrib import messages


class DatabasePerformanceMiddleware(MiddlewareMixin):
    """
    DB 연결 성능 모니터링 미들웨어
    
    로그에 연결 재사용 여부와 쿼리 시간을 기록합니다.
    """
    
    def process_request(self, request):
        """요청 시작 시 DB 연결 상태 기록"""
        # DB 연결 재사용 여부 확인
        if hasattr(connection, 'connection'):
            conn = connection.connection
            if conn:
                # 연결이 이미 존재하면 재사용 중
                self._log_connection_reuse(request, conn)
        
        # 요청 시작 시간 기록
        request._db_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """응답 완료 시 DB 성능 정보 로깅"""
        if hasattr(request, '_db_start_time'):
            elapsed = time.time() - request._db_start_time
            if elapsed > 1.0:  # 1초 이상 걸린 요청만 로깅
                conn = getattr(connection, 'connection', None)
                conn_info = "reused" if conn else "new"
                print(f"[DB Performance] {request.path} - {elapsed:.3f}s (connection: {conn_info}, queries: {len(connection.queries)})")
        
        return response
    
    def _log_connection_reuse(self, request, conn):
        """연결 재사용 여부 로깅 (디버깅용)"""
        # 연결 ID 또는 상태 정보 확인
        if hasattr(conn, 'pgconn'):
            # psycopg3
            try:
                conn_id = id(conn.pgconn)
                print(f"[DB Connection] Request {request.path[:50]} - Connection reused (ID: {conn_id})")
            except:
                pass
        elif hasattr(conn, 'get_backend_pid'):
            # psycopg2
            try:
                pid = conn.get_backend_pid()
                print(f"[DB Connection] Request {request.path[:50]} - Connection reused (PID: {pid})")
            except:
                pass


class UserActivityLoggingMiddleware(MiddlewareMixin):
    """
    사용자 활동 로깅 미들웨어
    
    인증된 사용자의 활동을 로깅합니다.
    """
    
    def process_request(self, request):
        """요청 시작 시 사용자 활동 기록"""
        if request.user.is_authenticated:
            # 세션에 마지막 활동 시간 업데이트
            request.session['last_activity'] = datetime.now().isoformat()
        
        return None


class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    세션 타임아웃 미들웨어
    
    비활성 상태가 일정 시간 지속되면 세션을 만료시킵니다.
    """
    
    # 세션 타임아웃 시간 (초 단위, 기본값: 2시간)
    SESSION_TIMEOUT = 7200  # 2 hours
    
    def process_request(self, request):
        """요청 처리 전 세션 타임아웃 확인"""
        if not request.user.is_authenticated:
            return None
        
        # 마지막 활동 시간 확인
        last_activity_str = request.session.get('last_activity')
        if not last_activity_str:
            # 마지막 활동 시간이 없으면 현재 시간으로 설정
            request.session['last_activity'] = datetime.now().isoformat()
            return None
        
        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            now = datetime.now()
            inactive_time = (now - last_activity).total_seconds()
            
            # 타임아웃 시간 초과 시 세션 만료
            if inactive_time > self.SESSION_TIMEOUT:
                logout(request)
                messages.warning(request, '세션이 만료되었습니다. 다시 로그인해주세요.')
                # 마지막 활동 시간 삭제
                if 'last_activity' in request.session:
                    del request.session['last_activity']
                return None
            
            # 마지막 활동 시간 업데이트
            request.session['last_activity'] = datetime.now().isoformat()
            
        except (ValueError, TypeError):
            # 날짜 파싱 실패 시 현재 시간으로 재설정
            request.session['last_activity'] = datetime.now().isoformat()
        
        return None