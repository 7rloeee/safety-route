import os
from dotenv import load_dotenv
from safety_algorithms import fetch_police_stations_kakao

load_dotenv()

def test_kakao_api():
    # 서울역 좌표 (테스트용)
    test_lat = 37.5547
    test_lng = 126.9707
    
    print(f"--- 카카오 API 테스트 시작 (위도: {test_lat}, 경도: {test_lng}) ---")
    police_stations = fetch_police_stations_kakao(test_lat, test_lng, radius=2000)
    
    if police_stations:
        print(f"SUCCESS: {len(police_stations)}개의 경찰관서를 찾았습니다.")
        for ps in police_stations:
            print(f"- {ps['name']} ({ps['lat']}, {ps['lng']})")
    else:
        print("FAILED: 경찰관서를 찾지 못했습니다. API 키나 네트워크 설정을 확인하세요.")

if __name__ == "__main__":
    test_kakao_api()
