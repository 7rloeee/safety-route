import math
import pandas as pd
import heapq  # 다익스트라 구현을 위한 우선순위 큐
import requests
import os

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


def fetch_police_stations_kakao(lat, lng, radius=2000):
    """
    카카오 로컬 API를 사용하여 주변 경찰서/파출소/지구대 위치를 실시간으로 가져옵니다.
    """
    api_key = os.getenv("KAKAO_REST_API_KEY")
    if not api_key:
        print("⚠️ 카카오 API 키가 설정되지 않아 경찰서 정보를 가져올 수 없습니다.")
        return []

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {
        "query": "경찰서",
        "x": lng,
        "y": lat,
        "radius": radius,
        "sort": "distance"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            police_list = []
            for item in data.get("documents", []):
                police_list.append({
                    "type": "POLICE",
                    "lat": float(item["y"]),
                    "lng": float(item["x"]),
                    "name": item["place_name"]
                })
            print(f"[카카오 API] 주변 경찰관서 {len(police_list)}개 발견")
            return police_list
        else:
            print(f"⚠️ 카카오 API 호출 실패: {response.status_code}")
            return []
    except Exception as e:
        print(f"⚠️ 카카오 API 에러: {e}")
        return []


def load_public_data(cctv_path="CCTV정보_서울특별시.csv", store_path="전국안심지킴이집표준데이터.csv"):
    """
    CCTV(CSV)와 안심지킴이집(CSV) 데이터를 로드하여 통합합니다.
    경찰서는 실시간 API 호출 방식으로 전환되었습니다.
    """
    combined_data = []
    
    # 1. CCTV 데이터 로드
    try:
        df_cctv = pd.read_csv(cctv_path, encoding="cp949")
        if "WGS84위도" in df_cctv.columns and "WGS84경도" in df_cctv.columns:
            df_cctv = df_cctv.rename(columns={"WGS84위도": "lat", "WGS84경도": "lng"})
        df_cctv["type"] = "CCTV"
        df_cctv = df_cctv.dropna(subset=["lat", "lng"])
        combined_data.extend(df_cctv[["type", "lat", "lng"]].to_dict(orient="records"))
        print(f"[데이터 로드] CCTV: {len(df_cctv)}개 완료")
    except Exception as e:
        print(f"⚠️ CCTV 로드 실패: {e}")

    # 2. 안심지킴이집 데이터 로드
    try:
        try:
            df_store = pd.read_csv(store_path, encoding="cp949")
        except:
            df_store = pd.read_csv(store_path, encoding="utf-8")
            
        if "위도" in df_store.columns and "경도" in df_store.columns:
            df_store = df_store.rename(columns={"위도": "lat", "경도": "lng"})
        df_store["type"] = "STORE"
        df_store = df_store.dropna(subset=["lat", "lng"])
        combined_data.extend(df_store[["type", "lat", "lng"]].to_dict(orient="records"))
        print(f"[데이터 로드] 안심지킴이집: {len(df_store)}개 완료")
    except Exception as e:
        print(f"⚠️ 안심지킴이집 로드 실패: {e}")

    # 3. 위험 구역 (임시 데이터)
    combined_data.append({"type": "DANGER", "lat": 37.5555, "lng": 126.9480})

    print(f"✅ 정적 안전 인프라 데이터 {len(combined_data)}개 로드 완료 (경찰서는 실시간 호출)")
    return combined_data



def calculate_safety_score(current_lat, current_lng, facilities_data, radius=400):
    """
    [핵심 기능 1] 주변 안전도 점수 계산 알고리즘
    현재 위치 기준 반경 radius(미터) 이내의 시설물을 분석하여 0~100점 사이의 점수와 등급을 반환합니다.
    """
    weights = {
        "CCTV": 6,       # 안심 CCTV 가점
        "POLICE": 25,    # 파출소 가점
        "STORE": 10,     # 안심 지킴이집 편의점 가점
        "DANGER": -30    # 위험 구역 감점 요소
    }
    
    base_score = 60 
    score_modifier = 0
    
    for facility in facilities_data:
        dist = haversine_distance(current_lat, current_lng, facility["lat"], facility["lng"])
        
        if dist <= radius:
            f_type = facility.get("type", "CCTV")
            weight = weights.get(f_type, 0)
            
            # 거리 역비례 감쇄(Distance Decay): 가까울수록 영향력 증폭
            distance_factor = (radius - dist) / radius
            score_modifier += weight * distance_factor

    final_score = base_score + score_modifier
    final_score = max(0, min(100, final_score))
    
    if final_score >= 80:
        level = "매우 안전"
    elif final_score >= 45:
        level = "보통"
    else:
        level = "주의 필요"
        
    return {"score": round(final_score, 1), "level": level}


def generate_safe_waypoints(start_lat, start_lng, end_lat, end_lng, facilities_data):
    """
    [다익스트라 알고리즘 적용] 안심 경로 탐색 함수
    CCTV, 가로등(인프라) 등의 위치를 바탕으로 인센티브 및 패널티 가중치를 부여하여
    가장 안전 점수가 높은(비용이 적은) 최적 우회 경로를 실시간으로 유도하여 반환합니다.
    """
    # 1. 그래프 탐색을 위한 정점(노드) 풀 생성
    # 출발점, 공공데이터 인프라 목록, 도착점을 순서대로 하나의 리스트로 통합
    nodes = [{"type": "START", "lat": start_lat, "lng": start_lng}]
    
    # 성능 최적화: 출발지와 목적지 사이의 직선 거리를 계산하여 너무 먼 시설물은 필터링
    max_radius = haversine_distance(start_lat, start_lng, end_lat, end_lng) + 1500 # 직선 거리 + 1.5km 이내만 고려
    
    for f in facilities_data:
        # 시작점이나 끝점에서 너무 먼 시설물은 탐색에서 제외 (계산량 급감)
        if haversine_distance(start_lat, start_lng, f["lat"], f["lng"]) <= max_radius or \
           haversine_distance(end_lat, end_lng, f["lat"], f["lng"]) <= max_radius:
            nodes.append(f)
            
    nodes.append({"type": "GOAL", "lat": end_lat, "lng": end_lng})
    
    num_nodes = len(nodes)
    
    # 2. 인프라 요소별 안전 가중치 보너스/패널티 값 지정 (다익스트라는 값이 작을수록 우선 선택함)
    facility_benefits = {
        "CCTV": 20.0,      # 비용 차감 가점 (CCTV가 있는 골목길 우선 유도)
        "POLICE": 60.0,    # 최고의 안전지대이므로 비용 대폭 차감 
        "STORE": 30.0,     # 안심 지킴이집 편의점 경유 보너스
        "DANGER": -150.0   # 위험 구역은 마이너스 보너스(=비용 급증 패널티)를 주어 절대 안 가게 우회시킴
    }

    # 3. 모든 정점(지점) 간 가중치 비용(에지) 계산하여 그래프 리스트 생성
    graph = {i: [] for i in range(num_nodes)}
    
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j: continue
            
            # 두 GPS 지점 사이의 실제 물리적 거리(m) 연산
            dist = haversine_distance(nodes[i]["lat"], nodes[i]["lng"], nodes[j]["lat"], nodes[j]["lng"])
            
            # 성능 최적화: 너무 멀리 떨어진 노드끼리는 도보 이동이 불가능하다고 판단하여 간선 연결 제외 (출발/도착점 제외)
            if dist > 800 and nodes[i]["type"] != "START" and nodes[j]["type"] != "GOAL":
                continue
                
            target_type = nodes[j].get("type", "CCTV")
            benefit = facility_benefits.get(target_type, 0.0)
            
            # 다익스트라 가중치 = 실제 거리 - 안전 인센티브 (위험구역은 benefit이 음수이므로 비용이 대폭 상승)
            cost = dist - benefit
            if cost < 1: cost = 1.0  # 다익스트라 특성상 가중치 음수 방지 예외처리
                
            graph[i].append((cost, j))

    # 4. 다익스트라(Dijkstra) 최단/최적 경로 탐색 알고리즘 구동
    start_index = 0
    goal_index = num_nodes - 1
    
    distances = {i: float('inf') for i in range(num_nodes)}
    distances[start_index] = 0
    previous_nodes = {i: None for i in range(num_nodes)}  # 경로 추적용 직전 정점 저장 배열
    
    queue = [(0, start_index)]  # 우선순위 큐 초기화 (비용, 시작노드)
    
    while queue:
        current_distance, current_node = heapq.heappop(queue)
        
        if current_distance > distances[current_node]: continue
        if current_node == goal_index: break  # 목적지 연결 완료 시 연산 조기 종료
            
        for next_cost, neighbor in graph[current_node]:
            distance = current_distance + next_cost
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous_nodes[neighbor] = current_node
                heapq.heappush(queue, (distance, neighbor))

    # 5. 역추적 배열을 거슬러 올라가며 최적 위경도 경로 데이터 구축
    path_waypoints = []
    curr = goal_index
    while curr is not None:
        path_waypoints.append({"lat": nodes[curr]["lat"], "lng": nodes[curr]["lng"]})
        curr = previous_nodes[curr]
    path_waypoints.reverse()  # 출발점부터 가도록 뒤집기

    # 경로 연결 실패 예외 시 최소 기본 직선 경로 구성 반환
    if len(path_waypoints) <= 1:
        return [{"lat": start_lat, "lng": start_lng}, {"lat": end_lat, "lng": end_lng}]
        
    return path_waypoints


def detect_abnormal_behavior(gps_log, safe_route_waypoints, speed_threshold=5.0, still_time_threshold=120, route_deviation_threshold=50):
    """
    실시간 GPS 데이터를 모니터링하여 사용자의 이상 행동을 감지합니다.
    """
    if len(gps_log) < 2:
        return {"type": "none", "is_abnormal": False}

    last_point = gps_log[-1]
    second_last_point = gps_log[-2]

    dist_moved = haversine_distance(second_last_point['lat'], second_last_point['lng'],
                                    last_point['lat'], last_point['lng'])
    time_diff = last_point['timestamp'] - second_last_point['timestamp']

    if time_diff > 0:
        current_speed = dist_moved / time_diff
        
        if current_speed > speed_threshold:
            return {"type": "sudden_run", "is_abnormal": True, "message": "갑자기 뛰는 것으로 감지되었습니다."}
        
        if current_speed < 0.5 and time_diff >= still_time_threshold:
            recent_logs = [p for p in gps_log if last_point['timestamp'] - p['timestamp'] <= still_time_threshold]
            if len(recent_logs) > 1:
                total_dist_in_still_time = haversine_distance(recent_logs[0]['lat'], recent_logs[0]['lng'],
                                                              recent_logs[-1]['lat'], recent_logs[-1]['lng'])
                if total_dist_in_still_time < 5:
                    return {"type": "abnormal_still", "is_abnormal": True, "message": "장시간 비정상적으로 정지해 있습니다."}

    min_dist_to_route = float('inf')
    for wp in safe_route_waypoints:
        min_dist_to_route = min(min_dist_to_route, haversine_distance(last_point['lat'], last_point['lng'], wp['lat'], wp['lng']))

    if min_dist_to_route > route_deviation_threshold:
        return {"type": "route_deviation", "is_abnormal": True, "message": "안심 경로에서 이탈했습니다."}

    return {"type": "none", "is_abnormal": False}

