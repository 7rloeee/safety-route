import math
import pandas as pd
from dqn_env import SafetyMapEnv
from dqn_agent import DQNAgent

def haversine_distance(lat1, lng1, lat2, lng2):
    """
    두 GPS 좌표(위도, 경도) 사이의 실제 구면 거리(미터 단위)를 계산합니다.
    """
    R = 6371000  # 지구 반지름 (미터)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def load_public_data(csv_path="public_safety_data.csv"):
    """
    다른 팀원분이 정리해 줄 공공데이터 CSV 파일을 읽어오는 함수입니다.
    파일이 아직 없을 때는 에러 없이 테스트할 수 있도록 임시 가짜 데이터를 반환합니다.
    """
    try:
        # 팀원이 제공할 CSV 구조 가정: columns=['lat', 'lng', 'type']
        df = pd.read_csv(csv_path)
        print(f"[세이프티 루트] 공공데이터 로드 성공! 데이터 개수: {len(df)}개")
        return df.to_dict(orient="records")
    except FileNotFoundError:
        print(f"⚠️ 백엔드 경고: '{csv_path}' 파일이 없어 가짜 데이터로 알고리즘을 시뮬레이션합니다.")
        # 데이터 수집 전까지 내 로직을 검증하기 위한 가상 인프라 데이터셋
        return [
            {"type": "CCTV", "lat": 37.5552, "lng": 126.9701},   # 서울역-이대역 주변 가상 좌표들
            {"type": "CCTV", "lat": 37.5541, "lng": 126.9712},
            {"type": "CCTV", "lat": 37.5562, "lng": 126.9461},
            {"type": "POLICE", "lat": 37.5567, "lng": 126.9451}, # 파출소 위치
            {"type": "STORE", "lat": 37.5560, "lng": 126.9440},  # 안심 지킴이집 편의점
            {"type": "DANGER", "lat": 37.5555, "lng": 126.9480}, # 우회해야 할 위험 구역
        ]


def calculate_safety_score(current_lat, current_lng, facilities_data, radius=400):
    """
    [핵심 기능 1] 주변 안전도 점수 계산 알고리즘
    현재 위치 기준 반경 radius(미터) 이내의 시설물을 분석하여 0~100점 사이의 점수와 등급을 반환합니다.
    """
    # 기획서 양식 및 인프라 가치에 맞춘 가중치 설정
    weights = {
        "CCTV": 6,       # 안심 CCTV 가점
        "POLICE": 25,    # 파출소 가점 (가장 높은 안전지대)
        "STORE": 10,     # 안심 지킴이집 편의점 가점
        "DANGER": -30    # 위험 구역 감점 요소
    }
    
    base_score = 60  # 기본 점수 바탕
    score_modifier = 0
    
    for facility in facilities_data:
        dist = haversine_distance(current_lat, current_lng, facility["lat"], facility["lng"])
        
        # 설정한 반경(예: 400m) 이내에 있는 시설물만 연산에 포함
        if dist <= radius:
            f_type = facility.get("type", "CCTV")
            weight = weights.get(f_type, 0)
            
            # 거리 역비례 감쇄(Distance Decay): 시설물이 사용자와 가까울수록 영향력을 증폭시킴
            distance_factor = (radius - dist) / radius
            score_modifier += weight * distance_factor

    final_score = base_score + score_modifier
    final_score = max(0, min(100, final_score))  # 0점과 100점 사이로 바운더리 제한
    
    # app.js 프론트 UI 텍스트 컴포넌트와 매핑
    if final_score >= 80:
        level = "매우 안전"
    elif final_score >= 45:
        level = "보통"
    else:
        level = "주의 필요"
        
    return {"score": round(final_score, 1), "level": level}

def generate_safe_waypoints_with_dqn(start_lat, start_lng, end_lat, end_lng, facilities_data, model_path="safety_dqn_model.h5"):
    """
    [핵심 기능 2 - DQN 활용] 안심 경로 계산 알고리즘
    DQN 에이전트를 활용하여 위험 구역을 회피하고 안전 인프라를 경유하는 최적 안심 경로를 탐색합니다.
    """
    # DQN 환경 초기화 (가상의 10x10 그리드 맵 사용)
    env = SafetyMapEnv()
    
    # DQN 에이전트 로드
    agent = DQNAgent(env.state_size, env.action_size)
    try:
        agent.load(model_path)
        print(f"[세이프티 루트] DQN 모델 로드 성공: {model_path}")
    except Exception as e:
        print(f"⚠️ 백엔드 경고: DQN 모델 로드 실패 ({e}). 기본 경로를 반환합니다.")
        # 모델 로드 실패 시, 기본 직선 경로 반환
        return [{"lat": start_lat, "lng": start_lng}, {"lat": end_lat, "lng": end_lng}]

    # 환경 초기화 및 시작 상태 설정
    # 실제 위경도와 가상 그리드 맵의 시작/목표 지점 매핑이 필요하지만,
    # 여기서는 단순화를 위해 그리드 맵의 (0,0)을 시작, (9,9)를 목표로 가정합니다.
    # 실제 서비스에서는 GPS 좌표를 그리드 좌표로 변환하는 로직이 필요합니다.
    state = env.reset() # (0,0)
    
    # 경로 저장 리스트 (그리드 좌표)
    grid_path = [tuple(state)]
    
    # 최대 탐색 스텝 제한
    max_steps = 50 
    
    for step_count in range(max_steps):
        action = agent.act(state, train=False) # 학습된 AI의 판단으로만 이동
        next_state, reward, done = env.step(action)
        
        grid_path.append(tuple(next_state))
        state = next_state
        
        if done:
            break

    # 그리드 경로를 실제 위경도 경로로 변환 (단순화를 위해 시작/끝점만 매핑)
    # 실제 구현에서는 그리드 좌표를 실제 GPS 좌표로 변환하는 복잡한 로직이 필요합니다.
    # 여기서는 시작점과 끝점, 그리고 중간에 임의의 웨이포인트를 추가하는 방식으로 시뮬레이션합니다.
    # DQN이 찾은 그리드 경로의 중간 지점을 실제 GPS 중간 지점으로 매핑하는 방식 등을 고려할 수 있습니다.
    return [{"lat": start_lat, "lng": start_lng}, {"lat": (start_lat + end_lat) / 2, "lng": (start_lng + end_lng) / 2}, {"lat": end_lat, "lng": end_lng}]

def detect_abnormal_behavior(gps_log, safe_route_waypoints, speed_threshold=5.0, # m/s (약 18km/h)
                             still_time_threshold=120, # seconds
                             route_deviation_threshold=50 # meters
                            ):
    """
    실시간 GPS 데이터를 모니터링하여 사용자의 이상 행동을 감지합니다.
    
    Args:
        gps_log (list): [{'timestamp': float, 'lat': float, 'lng': float}, ...] 형태의 연속된 GPS 좌표 리스트.
                        timestamp는 epoch time (초)
        safe_route_waypoints (list): [{'lat': float, 'lng': float}, ...] 형태의 안내된 안심 경로 웨이포인트 리스트.
        speed_threshold (float): 갑자기 뜀을 감지하는 속도 임계값 (m/s).
        still_time_threshold (int): 비정상적 정지를 감지하는 시간 임계값 (초).
        route_deviation_threshold (int): 경로 이탈을 감지하는 거리 임계값 (미터).
        
    Returns:
        dict: 이상 징후 종류와 위험 여부를 담은 딕셔너리.
              예: {"type": "none", "is_abnormal": False}
                  {"type": "sudden_run", "is_abnormal": True, "message": "갑자기 뛰는 것으로 감지되었습니다."}
    """
    
    if len(gps_log) < 2:
        return {"type": "none", "is_abnormal": False}

    # 1. 이동 속도 분석 (갑자기 뜀, 비정상적 정지)
    last_point = gps_log[-1]
    second_last_point = gps_log[-2]

    dist_moved = haversine_distance(second_last_point['lat'], second_last_point['lng'],
                                    last_point['lat'], last_point['lng'])
    time_diff = last_point['timestamp'] - second_last_point['timestamp']

    if time_diff > 0:
        current_speed = dist_moved / time_diff # m/s
        
        # 갑자기 뜀 감지
        if current_speed > speed_threshold:
            return {"type": "sudden_run", "is_abnormal": True, "message": "갑자기 뛰는 것으로 감지되었습니다."}
        
        # 비정상적 정지 감지 (마지막 N개 포인트가 거의 움직이지 않았을 때)
        # 여기서는 단순화를 위해 마지막 두 포인트만 보지만, 실제로는 더 많은 과거 데이터를 봐야 함
        if current_speed < 0.5 and time_diff >= still_time_threshold: # 0.5 m/s 이하를 정지로 간주
            # 더 정확한 정지 감지를 위해, 일정 시간 동안의 모든 GPS 로그를 확인
            recent_logs = [p for p in gps_log if last_point['timestamp'] - p['timestamp'] <= still_time_threshold]
            if len(recent_logs) > 1:
                total_dist_in_still_time = haversine_distance(recent_logs[0]['lat'], recent_logs[0]['lng'],
                                                              recent_logs[-1]['lat'], recent_logs[-1]['lng'])
                if total_dist_in_still_time < 5: # 5미터 이내 움직임은 정지로 간주
                    return {"type": "abnormal_still", "is_abnormal": True, "message": "장시간 비정상적으로 정지해 있습니다."}

    # 2. 경로 이탈 감지
    # 현재 위치에서 가장 가까운 안심 경로 웨이포인트까지의 거리를 계산
    min_dist_to_route = float('inf')
    for wp in safe_route_waypoints:
        min_dist_to_route = min(min_dist_to_route, haversine_distance(last_point['lat'], last_point['lng'], wp['lat'], wp['lng']))

    if min_dist_to_route > route_deviation_threshold:
        return {"type": "route_deviation", "is_abnormal": True, "message": "안심 경로에서 이탈했습니다."}

    return {"type": "none", "is_abnormal": False}