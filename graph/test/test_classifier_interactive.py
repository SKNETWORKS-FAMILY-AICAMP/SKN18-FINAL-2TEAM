#!/usr/bin/env python3
"""
test_classifier_interactive.py
=============================
classifier.py 노드를 대화형으로 테스트하는 파일입니다.

사용법:
    python test_classifier_interactive.py

기능:
    - 터미널에서 사용자 질문을 입력받습니다
    - classifier 노드를 실행하여 질문을 분류합니다
    - 분류 결과를 출력합니다
    - 'quit' 또는 'exit'를 입력하면 종료됩니다
"""

import sys
import os

# 상위 디렉토리의 nodes 모듈을 import하기 위해 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'nodes'))

try:
    from classifier import classify_node
except ImportError as e:
    print(f"❌ Error: classifier 모듈을 import할 수 없습니다: {e}")
    print("📁 현재 경로에서 ../nodes/classifier.py 파일이 있는지 확인해주세요.")
    sys.exit(1)


def print_banner():
    """프로그램 시작 시 출력할 배너"""
    print("=" * 60)
    print("🧠 CLASSIFIER NODE 테스트 프로그램")
    print("=" * 60)
    print("📝 사용자 질문을 입력하면 5가지 카테고리로 분류합니다:")
    print("💡 'examples'를 입력하면 예시 질문들을 볼 수 있습니다.")
    print("=" * 60)


def test_classifier_with_question(question: str) -> dict:
    """
    주어진 질문으로 classifier 노드를 테스트하는 함수
    
    Args:
        question (str): 테스트할 질문
        
    Returns:
        dict: classifier 노드의 실행 결과 (state)
    """
    # classifier 노드에 전달할 state 딕셔너리 생성
    initial_state = {
        "user_question": question
    }
    
    try:
        # classifier 노드 실행
        result_state = classify_node(initial_state)
        return result_state
    except Exception as e:
        print(f"❌ 분류 중 오류 발생: {e}")
        return {"case_type": "ERROR", "error": str(e)}


def format_result(question: str, result_state: dict):
    """결과를 예쁘게 포맷팅해서 출력하는 함수"""
    print("\n" + "=" * 60)
    print("📊 분류 결과")
    print("=" * 60)
    print(f"❓ 입력 질문: {question}")
    
    case_type = result_state.get("case_type", "UNKNOWN")
    
    # 카테고리별 설명
    category_descriptions = {
        "NO_RELATION": "단백질 등 생물학적 관련 질문이 아닌 질문",
        "BIO_Q": "단백질 등 생물학적 관련 논문, 임상연구 관련 질문",
        "SIMULATION_Q": "단백질 등 생물학적 실험 경로 안내 질문",
        "PROTOCOL_Q": "단백질 등 생물학적 실험 프로토콜 질문",
        "INFERENCE_Q": "단백질 등 생물학적 실험 결과 해석 질문",
        "ERROR": "오류 발생"
    }
    
    description = category_descriptions.get(case_type, "알 수 없는 카테고리")
    
    print(f"🏷️  분류 결과: {case_type}")
    print(f"📝 설명: {description}")
    
    if "error" in result_state:
        print(f"⚠️  오류 내용: {result_state['error']}")
    
    print("=" * 60)


def main():
    """메인 함수 - 대화형 테스트 루프"""
    print_banner()
    
    while True:
        try:
            # 사용자 입력 받기
            print("\n💬 질문을 입력하세요 (quit/exit로 종료, examples로 예시 보기):")
            user_input = input(">>> ").strip()
            
            # 종료 명령어 체크
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 테스트를 종료합니다. 안녕히 가세요!")
                break
            
            # 빈 입력 체크
            if not user_input:
                print("⚠️  질문을 입력해주세요.")
                continue
            
            # classifier 테스트 실행
            print("🔄 질문을 분류하는 중...")
            result = test_classifier_with_question(user_input)
            
            # 결과 출력
            format_result(user_input, result)
            
        except KeyboardInterrupt:
            print("\n\n👋 Ctrl+C로 종료되었습니다. 안녕히 가세요!")
            break
        except Exception as e:
            print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
            print("🔄 다시 시도해주세요.")


if __name__ == "__main__":
    main()
