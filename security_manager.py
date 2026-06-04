import time
import hashlib

# 유저별 실시간 GPS 로그를 임시로 담아두는 서버 휘발성 메모리 (세션 저장소)
temporary_user_sessions = {}

# =======================================================
# [기능 1] SHA-256 기반 식별자 익명화 함수
# =======================================================
def anonymize_user_id(user_id):
    """
    유저의 실제 신원(학번, 아이디 등)을 SHA-256으로 갈아서 외계어 가상 키로 변환
    """
    hasher = hashlib.sha256(user_id.encode())
    # 보안 강화를 위해 생성된 해시값 중 앞 16자리만 추출하여 가상 키로 사용
    anonymized_key = f"anon_{hasher.hexdigest()[:16]}"
    return anonymized_key


# =======================================================
# [기능 2] 콜드 스타트 방어용 하이브리드 라우팅 함수
# =======================================================
def get_hybrid_route(user_id, current_gps, destination):
    """
    유저 데이터 개수를 체크해서 룰 기반(다익스트라)과 AI(LSTM)를 동적으로 스위칭
    """
    # 1. 유저 아이디를 먼저 익명화 처리
    anon_key = anonymize_user_id(user_id)
    
    # 2. 이 익명 유저의 과거 로그가 우리 세션 저장소에 얼마나 쌓였는지 확인
    # (여기서는 테스트를 위해 임시 세션에 쌓인 로그 개수를 기준으로 판별)
    user_logs = temporary_user_sessions.get(anon_key, [])
    
    # [조건 판별] 데이터가 부족한 서비스 초기 단계 (예: 로그가 5개 미만인 경우)
    if len(user_logs) < 5:
        print(f"[Hybrid] 신규 유저 ({anon_key}): 데이터 부족! 룰 기반 다익스트라 안심 경로를 가동합니다.")
        # 원래 너희 팀이 만든 다익스트라 함수가 있다면 여기에 연결하면 돼!
        # safe_route = run_dijkstra_algorithm(current_gps, destination)
        return "Dijkstra_Safe_Route_Data"
        
    # [조건 판별] 데이터가 충분히 쌓인 단계
    else:
        print(f"[Hybrid] 기존 유저 ({anon_key}): 데이터 충분! DBSCAN 거점 분석 및 LSTM 경로 예측을 가동합니다.")
        # 원래 너희 팀이 만든 AI 파이프라인 함수가 있다면 여기에 연결!
        # safe_route = run_lstm_prediction(anon_key)
        return "LSTM_AI_Predicted_Route_Data"


# =======================================================
# [기능 3] 서비스 종료 시 휘발성 데이터 즉시 파기 함수
# =======================================================
def terminate_and_purge_session(user_id):
    """
    유저가 목적지에 도착해 서비스를 종료하면, 메모리에 임시 보관 중이던 GPS 로그를 원천 삭제
    """
    anon_key = anonymize_user_id(user_id)
    
    print(f"[알림] 유저 {user_id} 귀가 완료 ➔ 데이터 파기 프로세스 시동")
    
    # del 명령어로 서버 메모리(딕셔너리)에서 해당 유저의 당일 로그를 흔적도 없이 삭제
    if anon_key in temporary_user_sessions:
        del temporary_user_sessions[anon_key]
        print(f"[보안] 익명 키 {anon_key}의 실시간 위치 로그가 서버 메모리에서 영구 파기되었습니다.")
    else:
        print(f"[보안] 파기할 임시 데이터가 존재하지 않습니다.")


# =======================================================
# 🧪 실제 연동 및 구동 테스트 (메인 흐름)
# =======================================================
if __name__ == "__main__":
    print("--- 🛡️ 중간 발표 피드백 반영 통합 시스템 검증 --- \n")
    
    my_id = "20251252-star"
    current_loc = {"lat": 37.56, "lng": 126.97}
    dest_loc = {"lat": 37.57, "lng": 126.98}
    
    # 1. 처음 귀가 서비스를 켰을 때 (데이터가 없을 때) -> 하이브리드 작동 확인
    print("[1회차 귀가 시도]")
    route = get_hybrid_route(my_id, current_loc, dest_loc)
    
    # 2. 실시간 이동 중이라고 가정하고 가상 데이터 강제로 쌓기
    anon_key = anonymize_user_id(my_id)
    temporary_user_sessions[anon_key] = [1, 2, 3, 4, 5, 6] # 데이터 6개 적재
    
    # 3. 데이터가 많이 쌓인 상태에서 다시 라우팅 요청 -> AI로 스위칭되는지 확인
    print("\n[6회차 귀가 시도 (데이터 누적 후)]")
    route_ai = get_hybrid_route(my_id, current_loc, dest_loc)
    
    # 4. 목적지 도착 -> 데이터 즉시 파기 확인
    print("\n[목적지 도착 시점]")
    terminate_and_purge_session(my_id)
    
    print(f"\n최종 메모리 상태 확인: {temporary_user_sessions}") 
    # 출력 결과 {} 이면 서버에 아무 흔적도 안 남고 완벽히 파기된 것!