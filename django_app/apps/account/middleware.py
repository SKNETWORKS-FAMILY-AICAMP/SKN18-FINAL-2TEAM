"""
Account 관련 미들웨어
"""
import time
from django.db import connection
from django.utils.deprecation import MiddlewareMixin


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