import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from sklearn.cluster import DBSCAN

def learn_frequent_places_from_log(gps_log, eps=0.001, min_samples=10):
    """
    [DBSCAN] GPS 로그를 분석하여 사용자가 자주 머무는 장소(거점)를 학습합니다.
    
    Args:
        gps_log (np.array): (n_samples, 2) 형태의 전체 GPS 좌표 배열.
        eps (float): 클러스터로 인정하는 점 사이의 최대 거리 (위경도 기준). 약 111m.
        min_samples (int): 클러스터를 구성하는 데 필요한 최소 데이터 개수.
    
    Returns:
        list: 학습된 거점들의 중심 좌표 리스트. 예: [[lat1, lng1], [lat2, lng2]]
    """
    model = DBSCAN(eps=eps, min_samples=min_samples)
    clusters = model.fit_predict(gps_log)
    
    frequent_places = []
    for cluster_id in set(clusters):
        if cluster_id != -1: # -1은 노이즈(이동 경로)를 의미하므로 제외
            center_point = gps_log[clusters == cluster_id].mean(axis=0)
            frequent_places.append(center_point)
    return frequent_places
class LSTMPredictor:
    """
    과거의 순차적 GPS 데이터를 학습하여 다음 목적지를 예측하는 LSTM 모델 클래스입니다.
    """
    def __init__(self, timesteps=5, n_features=2):
        """
        모델을 초기화합니다.

        Args:
            timesteps (int): 한 번에 입력으로 사용할 과거 데이터의 길이 (sequence length).
            n_features (int): 각 데이터 포인트의 차원 (위도, 경도 -> 2).
        """
        self.timesteps = timesteps
        self.n_features = n_features
        self.model = self._build_model()

    def _build_model(self):
        """
        Keras를 사용하여 LSTM 모델을 구성합니다.
        """
        model = Sequential([
            # 입력 형태: (None, timesteps, n_features) -> (배치크기, 시퀀스길이, 특성수)
            LSTM(50, activation='relu', input_shape=(self.timesteps, self.n_features)),
            Dense(25, activation='relu'),
            # 출력: 다음 좌표 (위도, 경도)
            Dense(self.n_features)
        ])
        model.compile(optimizer='adam', loss='mse')
        return model

    def _prepare_data(self, history_data):
        """
        전체 GPS 로그를 LSTM 학습에 맞는 시퀀스 데이터(X)와 정답(y)으로 변환합니다.
        예: [p1, p2, p3, p4, p5, p6] -> X=[[p1,p2,p3,p4,p5]], y=[p6]
        """
        X, y = [], []
        for i in range(len(history_data) - self.timesteps):
            # timesteps 만큼의 데이터를 하나의 시퀀스로 묶음
            sequence = history_data[i:(i + self.timesteps)]
            X.append(sequence)
            # 시퀀스 바로 다음 좌표를 정답(label)으로 설정
            label = history_data[i + self.timesteps]
            y.append(label)
        return np.array(X), np.array(y)

    def fit_model(self, history_data, epochs=200, verbose=0):
        """
        과거 누적 동선 데이터를 받아 모델을 학습시킵니다.

        Args:
            history_data (np.array): (n_samples, 2) 형태의 전체 GPS 좌표 배열.
            epochs (int): 학습 반복 횟수.
            verbose (int): 학습 과정 출력 여부 (0: 출력 안함, 1: 출력함).
        """
        print(f"[LSTM] 총 {len(history_data)}개의 과거 데이터로 경로 예측 모델 학습을 시작합니다...")
        X, y = self._prepare_data(history_data)

        # 데이터가 너무 적어 시퀀스를 만들 수 없는 경우 예외 처리
        if len(X) == 0:
            print("⚠️ [LSTM 경고] 학습 데이터가 부족하여 모델을 학습할 수 없습니다.")
            return

        self.model.fit(X, y, epochs=epochs, verbose=verbose)
        print(f"[LSTM] 모델 학습 완료! (Epochs: {epochs})")

    def predict_next_destination(self, current_sequence):
        """
        현재까지의 이동 데이터를 입력받아 다음 목적지 좌표를 예측합니다.

        Args:
            current_sequence (np.array): (timesteps, 2) 형태의 현재 이동 시퀀스.

        Returns:
            np.array: (2,) 형태의 예측된 다음 목적지 [위도, 경도] 배열.
        """
        if current_sequence.shape[0] != self.timesteps:
            raise ValueError(f"입력 시퀀스의 길이는 {self.timesteps}여야 합니다. (현재: {current_sequence.shape[0]})")

        # 모델 입력에 맞게 차원 확장: (timesteps, 2) -> (1, timesteps, 2)
        input_data = np.expand_dims(current_sequence, axis=0)
        
        predicted_point = self.model.predict(input_data, verbose=0)
        return predicted_point[0]


if __name__ == "__main__":
    # --- 1. 가상 GPS 데이터 생성 (DBSCAN & LSTM 테스트용) ---
    # '집'과 '회사' 주변에 머무른 기록과 그 사이를 이동한 기록을 시뮬레이션
    print("--- [1] DBSCAN & LSTM 테스트용 가상 데이터 생성 ---")
    home_coords = np.array([37.55, 127.00]) # 집
    work_coords = np.array([37.56, 127.02]) # 회사
    
    # 집 주변에 머무른 기록 (50개)
    home_stay_log = np.random.normal(loc=home_coords, scale=0.0005, size=(50, 2))
    # 회사 주변에 머무른 기록 (50개)
    work_stay_log = np.random.normal(loc=work_coords, scale=0.0005, size=(50, 2))
    # 집 -> 회사 이동 경로 (30개)
    travel_log = np.linspace(home_coords, work_coords, num=30)
    
    # 전체 이동 기록 합치기
    history_gps_data = np.vstack([home_stay_log, travel_log, work_stay_log])
    print(f"생성된 전체 경로 데이터 수: {len(history_gps_data)}개")
    print(f"데이터 형태: '집' 주변 50개 + 이동 30개 + '회사' 주변 50개\n")

    # --- 2. DBSCAN으로 자주 가는 장소(거점) 학습 ---
    print("--- [2] DBSCAN으로 자주 가는 장소 학습 ---")
    learned_places = learn_frequent_places_from_log(history_gps_data)
    print(f"학습된 거점 개수: {len(learned_places)}개")
    for i, place in enumerate(learned_places):
        print(f"  - 거점 {i+1} 중심 좌표: [{place[0]:.4f}, {place[1]:.4f}]")
    print("\n")

    # --- 3. LSTM 모델 생성 및 전체 경로 패턴 학습 ---
    print("--- [3] LSTM 모델 생성 및 학습 ---")
    # 5개의 과거 좌표를 보고 다음 좌표를 예측하도록 설정
    predictor = LSTMPredictor(timesteps=5, n_features=2)
    predictor.fit_model(history_gps_data, epochs=200, verbose=0)
    print("\n")

    # --- 4. 다음 목적지 예측 테스트 ---
    print("--- [4] 다음 목적지 예측 테스트 ---")
    # '집 -> 회사' 이동 경로의 마지막 5개 좌표를 '현재 이동 경로'로 사용
    # 모델은 이 시퀀스를 기반으로 '회사' 방향의 다음 좌표를 예측해야 함
    current_path_sequence = travel_log[-6:-1] # 이동 경로의 마지막 부분
    actual_next_point = travel_log[-1]      # 실제 이동 경로의 최종 목적지

    predicted_next_point = predictor.predict_next_destination(current_path_sequence)

    print(f"▶ 현재까지의 이동 경로 (5개 좌표):\n{current_path_sequence}")
    print(f"▶ 실제 다음 목적지 좌표: {actual_next_point}")
    print(f"▶ LSTM 모델이 예측한 다음 목적지 좌표: {predicted_next_point}")