import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
import json

def generate_virtual_gps_data():
    """
    알고리즘 테스트를 위한 가상 GPS 로그 데이터를 생성합니다.
    집(Home)과 학교(School) 주변에 좌표가 밀집된 형태입니다.
    """
    # 집 주변 (서울역 인근)
    home_lat, home_lng = 37.5546, 126.9706
    # 학교 주변 (이대역 인근)
    school_lat, school_lng = 37.5567, 126.9451
    
    # 데이터 생성 (집 100개, 학교 100개, 이동 중 20개)
    home_points = np.random.normal(loc=[home_lat, home_lng], scale=0.0005, size=(100, 2))
    school_points = np.random.normal(loc=[school_lat, school_lng], scale=0.0005, size=(100, 2))
    travel_points = np.linspace([home_lat, home_lng], [school_lat, school_lng], 20)
    
    all_points = np.vstack([home_points, school_points, travel_points])
    df = pd.DataFrame(all_points, columns=['lat', 'lng'])
    
    # CSV 파일로 저장
    df.to_csv('user_gps_log.csv', index=False)
    print("가상 GPS 로그 파일(user_gps_log.csv) 생성 완료")
    return df

def learn_frequent_places(csv_path='user_gps_log.csv'):
    """
    DBSCAN 알고리즘을 사용하여 밀집된 거점을 학습합니다.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        df = generate_virtual_gps_data()
        
    # DBSCAN 모델 설정 (eps: 약 50m 반경, min_samples: 최소 10개 좌표)
    # 위경도 0.001도는 대략 111m이므로 eps=0.0005는 약 55m
    model = DBSCAN(eps=0.0005, min_samples=10)
    clusters = model.fit_predict(df[['lat', 'lng']])
    
    df['cluster'] = clusters
    
    # 클러스터별 중심점(거점) 계산 (노이즈 -1 제외)
    frequent_places = []
    for cluster_id in set(clusters):
        if cluster_id == -1: continue
        
        center = df[df['cluster'] == cluster_id][['lat', 'lng']].mean().to_dict()
        frequent_places.append({
            "id": int(cluster_id),
            "lat": center['lat'],
            "lng": center['lng'],
            "name": f"거점 {cluster_id + 1}"
        })
        
    return frequent_places

if __name__ == "__main__":
    # 독립 실행 시 테스트
    places = learn_frequent_places()
    print("학습된 주요 거점:", json.dumps(places, indent=2, ensure_ascii=False))
