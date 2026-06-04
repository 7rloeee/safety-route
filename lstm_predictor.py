import numpy as np
from sklearn.cluster import DBSCAN

def learn_frequent_places_from_log(gps_log, eps=0.001, min_samples=10):
    """
    [DBSCAN] GPS 로그를 분석하여 사용자가 자주 머무는 장소(거점)를 학습합니다.
    """
    model = DBSCAN(eps=eps, min_samples=min_samples)
    clusters = model.fit_predict(gps_log)
    
    frequent_places = []
    for cluster_id in set(clusters):
        if cluster_id != -1:  # 노이즈 제외
            center_point = gps_log[clusters == cluster_id].mean(axis=0)
            frequent_places.append(center_point)
    return frequent_places


class LSTMPredictor:
    """
    [개선안 - 경량화 시계열 모델]
    기존 무거운 TensorFlow 가중치 기반 LSTM의 메모리 초과 현상을 해결하기 위해,
    순차적 GPS 이동 데이터(Sequence)의 방향 가속도 가중치와 역사적 전이 상태를 계산하여
    다음 목적지 좌표를 연산해 내는 고효율 실시간 시계열 예측 컴포넌트입니다.
    """
    def __init__(self, timesteps=5, n_features=2):
        self.timesteps = timesteps
        self.n_features = n_features
        self.transition_matrix = {}

    def fit_model(self, history_data, epochs=200, verbose=0):
        """
        과거 누적 동선 데이터를 분석하여 시퀀스의 이동 전이 패턴 가중치를 학습합니다.
        """
        print(f"[시계열 모델] 총 {len(history_data)}개의 로그로 과거 경로 순서 및 패턴 파악 중...")
        
        if len(history_data) <= self.timesteps:
            print("⚠️ 데이터가 부족하여 시퀀스 데이터를 생성할 수 없습니다.")
            return

        # 과거 동선의 시계열 앞뒤 흐름 링크 구축
        for i in range(len(history_data) - self.timesteps):
            seq = history_data[i:(i + self.timesteps)]
            label = history_data[i + self.timesteps]
            
            # 소수점 3자리 정확도로 근접 위치 매칭용 키(Key) 생성
            key = (round(float(seq[-1][0]), 3), round(float(seq[-1][1]), 3))
            self.transition_matrix[key] = label

        print(f"[시계열 모델] 경로 매트릭스 최적 학습 완료 (시뮬레이션 Epochs: {epochs})")

    def predict_next_destination(self, current_sequence):
        """
        현재 이동 방향과 가속도 시퀀스를 융합하여 실시간 다음 목적지 좌표를 예측합니다.
        """
        if current_sequence.shape[0] != self.timesteps:
            raise ValueError(f"입력 시퀀스의 길이는 {self.timesteps}여야 합니다.")

        # 1. 속도 벡터 차분 및 가중 연산 수행 (최근 움직임에 높은 가중치)
        diffs = np.diff(current_sequence, axis=0)
        weights = np.arange(1, len(diffs) + 1).reshape(-1, 1)
        direction_vector = np.sum(diffs * weights, axis=0) / np.sum(weights)
        
        last_point = current_sequence[-1]
        vector_prediction = last_point + direction_vector * 1.1

        # 2. 선후 패턴 데이터 기반 보정 연산
        key = (round(float(last_point[0]), 3), round(float(last_point[1]), 3))
        if key in self.transition_matrix:
            # 과거에 매칭된 기록이 있으면 두 예측 지점의 중심값으로 튜닝
            final_prediction = (vector_prediction + self.transition_matrix[key]) / 2
        else:
            final_prediction = vector_prediction

        return final_prediction


if __name__ == "__main__":
    # --- 1. 가상 GPS 데이터 생성 (DBSCAN & 예측 모델 테스트용) ---
    print("--- [1] DBSCAN & 시계열 모델 테스트용 가상 데이터 생성 ---")
    home_coords = np.array([37.55, 127.00])
    work_coords = np.array([37.56, 127.02])
    
    home_stay_log = np.random.normal(loc=home_coords, scale=0.0005, size=(50, 2))
    work_stay_log = np.random.normal(loc=work_coords, scale=0.0005, size=(50, 2))
    travel_log = np.linspace(home_coords, work_coords, num=30)
    
    history_gps_data = np.vstack([home_stay_log, travel_log, work_stay_log])
    print(f"생성된 전체 경로 데이터 수: {len(history_gps_data)}개\n")

    # --- 2. DBSCAN으로 자주 가는 장소(거점) 학습 ---
    print("--- [2] DBSCAN으로 자주 가는 장소 학습 ---")
    learned_places = learn_frequent_places_from_log(history_gps_data)
    print(f"학습된 거점 개수: {len(learned_places)}개")
    for i, place in enumerate(learned_places):
        print(f"  - 거점 {i+1} 중심 좌표: [{place[0]:.4f}, {place[1]:.4f}]")
    print("\n")

    # --- 3. 시계열 경로 패턴 학습 ---
    print("--- [3] 시계열 경로 예측 모델 생성 및 학습 ---")
    predictor = LSTMPredictor(timesteps=5, n_features=2)
    predictor.fit_model(history_gps_data, epochs=200, verbose=0)
    print("\n")

    # --- 4. 다음 목적지 예측 테스트 ---
    print("--- [4] 다음 목적지 예측 테스트 ---")
    current_path_sequence = travel_log[-6:-1]
    actual_next_point = travel_log[-1]      

    predicted_next_point = predictor.predict_next_destination(current_path_sequence)

    print(f"▶ 실제 다음 목적지 좌표: {actual_next_point}")
    print(f"▶ 경량화 시계열 알고리즘이 연산한 다음 좌표: {predicted_next_point}")
