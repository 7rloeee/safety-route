import math
import pandas as pd

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


def generate_safe_waypoints(start_lat, start_lng, end_lat, end_lng, facilities_data):
    """
    [핵심 기능 2] 안심 경로 계산 알고리즘
    출발지와 목적지 사이에서 위험 구역(DANGER)을 회피하고, 안전 인프라가 밀집한 경유지를 동적으로 찾아 경로 노드를 반환합니다.
    """
    total_dist = haversine_distance(start_lat, start_lng, end_lat, end_lng)
    
    # 이동 거리가 너무 짧으면(150m 미만) 우회 의미가 없으므로 바로 직선 노드 반환
    if total_dist < 150:
        return [{"lat": start_lat, "lng": start_lng}, {"lat": end_lat, "lng": end_lng}]
        
    # 벡터 상의 중간 중심점 계산
    mid_lat = (start_lat + end_lat) / 2
    mid_lng = (start_lng + end_lng) / 2
    
    best_waypoint = None
    best_utility = -9999
    
    # 전체 인프라 중 중간 지점 주변에 있으면서 안전 효율이 가장 높은 우회 거점 탐색
    for f in facilities_data:
        if f["type"] in ["CCTV", "POLICE", "STORE"]:
            d_to_mid = haversine_distance(mid_lat, mid_lng, f["lat"], f["lng"])
            
            # 목적지 방향과 너무 동떨어지지 않은 인프라 필터링 (전체 반경의 40% 이내 탐색)
            if d_to_mid < total_dist * 0.4:
                # 인프라 종류별 기본 선호도 스코어링
                utility = 50 if f["type"] == "POLICE" else 20
                
                # 안전 거점 근처에 혹시 위험 요소(DANGER)가 인접해 있다면 패널티 부여
                for danger in [d for d in facilities_data if d["type"] == "DANGER"]:
                    if haversine_distance(f["lat"], f["lng"], danger["lat"], danger["lng"]) < 150:
                        utility -= 40
                        
                if utility > best_utility:
                    best_utility = utility
                    best_waypoint = {"lat": f["lat"], "lng": f["lng"]}
                    
    # 빌드된 경로 배열 취합
    route = [{"lat": start_lat, "lng": start_lng}]
    if best_waypoint:
        route.append(best_waypoint)  # 최적 안심 경유지 삽입
    route.append({"lat": end_lat, "lng": end_lng})
    
    return route