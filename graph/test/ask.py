#!/usr/bin/env python3
"""
ask.py
=============================
사용자 입력을 받아서 graph/compile.py의 워크플로우를 테스트하는 파일

사용법:
    python ask.py

기능:
    - 그래프 컴파일 테스트
    - 사용자 질문 입력받아서 실행
    - 전체 워크플로우 결과 확인
    - 'quit' 또는 'exit'로 종료
"""

import sys
import os
import traceback

# 상위 디렉토리 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

# DB 초기화 모듈 임포트
sys.path.append(os.path.join(os.path.dirname(__file__), '../../infra/db'))
from memory_db_stetting import init_db

def print_banner():
    """프로그램 시작 배너"""
    print("=" * 80)
    print("🧪 GRAPH WORKFLOW 테스트 프로그램")
    print("=" * 80)
    print("📊 graph/compile.py의 전체 워크플로우를 테스트합니다")
    print("💬 질문을 입력하면 분류부터 답변 생성까지 전체 과정을 실행합니다")
    print("🔄 'quit' 또는 'exit'를 입력하면 종료됩니다")
    print("=" * 80)


def initialize_db():
    """DB 테이블 초기화"""
    try:
        print("\n🔧 DB 테이블 초기화 중...")
        init_db()
        print("✅ DB 테이블 초기화 완료!")
        return True
    except Exception as e:
        print(f"⚠️  DB 초기화 실패: {e}")
        print("   계속 진행합니다 (기존 테이블 사용)")
        return False


def test_graph_compilation():
    """그래프 컴파일 테스트"""
    print("\n🔧 그래프 컴파일 테스트 중...")
    
    try:
        from compile import create_workflow
        print("✅ compile.py 모듈 import 성공")
        
        # 워크플로우 생성 및 컴파일
        app = create_workflow()
        print("✅ 그래프 컴파일 성공")
        
        return app
        
    except Exception as e:
        print(f"❌ 그래프 컴파일 실패: {e}")
        print(f"📄 상세 오류:\n{traceback.format_exc()}")
        return None


def create_test_state(question, conversation_id="test_room_001"):
    """테스트용 state 생성"""
    return {
        "question": question,
        "conversation_id": conversation_id,
        "user_id": "test_user",
    }


def run_workflow_test(app, question):
    """워크플로우 실행 테스트"""
    print(f"\n🎯 질문: {question}")
    print("-" * 60)
    
    try:
        # 초기 state 생성
        initial_state = create_test_state(question)
        
        # 워크플로우 실행
        print("🔄 워크플로우 실행 중...")
        result = app.invoke(initial_state)
        
        # 결과 분석
        case_type = result.get("case_type", "UNKNOWN")
        final_answer = result.get("final_answer", "답변 없음")
        
        print(f"\n📊 실행 결과:")
        print(f"🏷️  분류: {case_type}")
        print(f"💬 답변: {final_answer}")
        
        # 추가 정보 표시
        if result.get("extracted_keywords"):
            print(f"🔍 키워드: {result['extracted_keywords']}")
        
        if result.get("extracted_entities"):
            print(f"🏢 엔티티: {result['extracted_entities']}")
        
        if result.get("used_web_search"):
            print(f"🌐 웹 검색 사용됨")
        
        if result.get("selected_chunks"):
            print(f"📄 선택된 청크: {len(result['selected_chunks'])}개")
        
        if result.get("web_selected_chunks"):
            print(f"🌐 웹 청크: {len(result['web_selected_chunks'])}개")
        
        return True, result
        
    except Exception as e:
        print(f"❌ 워크플로우 실행 실패: {e}")
        print(f"📄 상세 오류:\n{traceback.format_exc()}")
        return False, None


def main():
    """메인 함수"""
    print_banner()
    
    # DB 초기화 (테이블이 없으면 자동 생성)
    initialize_db()
    
    # 그래프 컴파일 테스트
    app = test_graph_compilation()
    if not app:
        print("\n❌ 그래프 컴파일에 실패했습니다. 프로그램을 종료합니다.")
        return
    
    print("\n✅ 그래프 컴파일 완료! 이제 질문을 입력해보세요.")
    
    # 대화형 테스트 루프
    while True:
        try:
            print("\n" + "=" * 80)
            user_input = input("💬 질문을 입력하세요 (quit/exit로 종료): ").strip()
            
            # 종료 명령어 체크
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 테스트를 종료합니다!")
                break
            
            # 빈 입력 체크
            if not user_input:
                print("⚠️  질문을 입력해주세요.")
                continue
            
            # 워크플로우 실행
            success, result = run_workflow_test(app, user_input)
            
            if not success:
                print("❌ 실행에 실패했습니다. 다시 시도해주세요.")
            
        except KeyboardInterrupt:
            print("\n\n👋 Ctrl+C로 종료되었습니다!")
            break
        except Exception as e:
            print(f"\n❌ 예상치 못한 오류: {e}")
            print("🔄 다시 시도해주세요.")


if __name__ == "__main__":
    main()
