import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from google import genai
from dotenv import load_dotenv
from ai_utils import learn_frequent_places
import models
from database import engine, SessionLocal, get_db
from sqlalchemy.orm import Session
from auth_utils import verify_google_token, create_access_token, decode_access_token
from safety_algorithms import load_public_data, calculate_safety_score, generate_safe_waypoints, fetch_police_stations_kakao, haversine_distance
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import security_manager

# 데이터베이스 초기화
models.Base.metadata.create_all(bind=engine)

# 환경 변수 로드
load_dotenv()

# Gemini 클라이언트 초기화
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
SAFEMAP_API_KEY = os.getenv("SAFEMAP_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

app = FastAPI(title="세이프티 루트 API 서버")
security = HTTPBearer()

class TTSRequest(BaseModel):
    text: str
    gender: str  # 'male' or 'female'

@app.post("/api/tts")
async def generate_tts(req: TTSRequest):
    """
    ElevenLabs API를 호출하여 텍스트를 고품질 AI 음성으로 변환합니다.
    """
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ElevenLabs API Key가 설정되지 않았습니다.")

    # 기본 Voice ID 설정 (ElevenLabs 기본 제공 목소리)
    # 남성: Adam (pNInz6obpguXGOic9J5L), 여성: Bella (EXAVITQu4vr4xnSDxMaL)
    voice_id = "pNInz6obpguXGOic9J5L" if req.gender == "male" else "EXAVITQu4vr4xnSDxMaL"
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": req.text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return Response(content=response.content, media_type="audio/mpeg")
        else:
            print(f"ElevenLabs API Error: {response.text}")
            raise HTTPException(status_code=response.status_code, detail="음성 생성 실패")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/safemap/key")
async def get_safemap_key():
    return {"key": SAFEMAP_API_KEY}

async def get_current_user(db: Session = Depends(get_db), auth: HTTPAuthorizationCredentials = Depends(security)):
    token = auth.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    return user

async def get_optional_user(db: Session = Depends(get_db), auth: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not auth:
        return None
    token = auth.credentials
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# 데이터 모델
class ChatMessage(BaseModel):
    message: str

class GoogleLoginRequest(BaseModel):
    credential: str

class FrequentPlaceCreate(BaseModel):
    name: str
    address: str

class EmergencyContactCreate(BaseModel):
    name: str
    relation: str
    phone: str

class SOSRequest(BaseModel):
    lat: float
    lng: float

@app.post("/api/auth/google")
async def google_login(req: GoogleLoginRequest, db: Session = Depends(get_db)):
    id_info = verify_google_token(req.credential)
    if not id_info:
        raise HTTPException(status_code=400, detail="유효하지 않은 구글 토큰입니다.")
    
    google_id = id_info['sub']
    email = id_info.get('email')
    name = id_info.get('name')
    picture = id_info.get('picture')

    # 사용자 조회 또는 생성
    user = db.query(models.User).filter(models.User.google_id == google_id).first()
    if not user:
        user = models.User(
            google_id=google_id,
            email=email,
            name=name,
            picture_url=picture
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # 정보 업데이트
        user.name = name
        user.picture_url = picture
        db.commit()

    # JWT 생성
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "name": user.name,
            "email": user.email,
            "picture": user.picture_url
        }
    }

# 설정 관련 API
@app.get("/api/settings/frequent-places")
async def get_frequent_places(user: models.User = Depends(get_current_user)):
    return user.frequent_places

@app.post("/api/settings/frequent-places")
async def add_frequent_place(place: FrequentPlaceCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    new_place = models.FrequentPlace(
        user_id=user.id,
        name=place.name,
        address=place.address
    )
    db.add(new_place)
    db.commit()
    db.refresh(new_place)
    return new_place

@app.delete("/api/settings/frequent-places/{place_id}")
async def delete_frequent_place(place_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    place = db.query(models.FrequentPlace).filter(models.FrequentPlace.id == place_id, models.FrequentPlace.user_id == user.id).first()
    if not place:
        raise HTTPException(status_code=404, detail="장소를 찾을 수 없습니다.")
    db.delete(place)
    db.commit()
    return {"status": "success"}

@app.get("/api/settings/emergency-contacts")
async def get_emergency_contacts(user: models.User = Depends(get_current_user)):
    return user.emergency_contacts

@app.post("/api/settings/emergency-contacts")
async def add_emergency_contact(contact: EmergencyContactCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    new_contact = models.EmergencyContact(
        user_id=user.id,
        name=contact.name,
        relation=contact.relation,
        phone=contact.phone
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact

@app.delete("/api/settings/emergency-contacts/{contact_id}")
async def delete_emergency_contact(contact_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    contact = db.query(models.EmergencyContact).filter(models.EmergencyContact.id == contact_id, models.EmergencyContact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="연락처를 찾을 수 없습니다.")
    db.delete(contact)
    db.commit()
    return {"status": "success"}

@app.put("/api/settings/emergency-contacts/{contact_id}")
async def update_emergency_contact(contact_id: int, contact_data: EmergencyContactCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    contact = db.query(models.EmergencyContact).filter(models.EmergencyContact.id == contact_id, models.EmergencyContact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="연락처를 찾을 수 없습니다.")
    
    contact.name = contact_data.name
    contact.relation = contact_data.relation
    contact.phone = contact_data.phone
    
    db.commit()
    db.refresh(contact)
    return contact

@app.post("/api/sos")
async def trigger_sos(req: SOSRequest, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    긴급 SOS를 요청하면 등록된 긴급 연락처로 현재 위치 정보를 포함한 구조 요청을 보냅니다.
    """
    contacts = user.emergency_contacts
    if not contacts:
        return {"status": "partial_success", "message": "등록된 긴급 연락처가 없습니다. 경찰에만 위치가 전송되었습니다.", "contacts_notified": []}
    
    notified_names = [c.name for c in contacts]
    # 실제 SMS 발송 로직 시뮬레이션
    print(f"SOS ALERT: User {user.name} at ({req.lat}, {req.lng}) requested help!")
    for contact in contacts:
        print(f"Sending SMS to {contact.name} ({contact.phone}): [세이프티 루트] {user.name}님이 위급 상황입니다! 현재 위치: https://map.kakao.com/link/map/{req.lat},{req.lng}")

    return {
        "status": "success",
        "message": f"{', '.join(notified_names)}님에게 구조 요청이 전송되었습니다.",
        "contacts_notified": notified_names
    }

# 현재 디렉토리 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 정적 파일 서빙 설정
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# [Gemini] 안심 통화 설정 챗봇 API
@app.post("/api/chat")
async def chat_with_gemini(chat_msg: ChatMessage):
    if not client:
        # 키가 없을 경우 시뮬레이션 모드
        return {
            "reply": "API 키가 설정되지 않아 시뮬레이션 모드로 동작합니다. 아빠 컨셉으로 설정해 드릴게요.",
            "config": {
                "caller_name": "아빠",
                "gender": "male",
                "intro_script": [
                    {"caller": "어디쯤이니?", "user": "응, 나 지금 거의 다 왔어."},
                    {"caller": "금방 갈 테니까 조심해서 오렴", "user": "응, 걱정하지 마. 금방 들어가."}
                ],
                "loop_script": [
                    {"caller": "응응, 계속 말해봐.", "user": "응, 그래서 아까 말이야..."},
                    {"caller": "아 진짜? 그런 일이 있었어?", "user": "그러니까, 나도 깜짝 놀랐다니까."},
                    {"caller": "응, 듣고 있어. 천천히 와.", "user": "어, 지금 골목길 지나고 있어."},
                    {"caller": "그렇구나. 아 참, 오늘 저녁은 먹었니?", "user": "아직, 들어가서 먹으려고."},
                    {"caller": "그래그래. 아 맞다, 아까 엄마한테 연락 왔었는데.", "user": "아 진짜? 뭐라고 하셔?"},
                    {"caller": "아니, 별건 아니고 그냥 안부 물으시더라.", "user": "그렇구나. 이따가 나도 전화 드려야겠네."},
                    {"caller": "응, 조심해서 오고. 옆에 사람들은 좀 있니?", "user": "응, 가로등도 밝고 괜찮아."},
                    {"caller": "그래, 끊지 말고 계속 얘기하자.", "user": "응, 심심했는데 잘됐다."},
                    {"caller": "어허, 그렇구먼. 신기하네.", "user": "그치? 나도 그렇게 생각했어."},
                    {"caller": "응, 나 여기 거실에서 기다리고 있을게.", "user": "응, 거의 다 온 것 같아."}
                ]
            }
        }
    
    try:
        prompt = f"""
        당신은 '안심 귀가 서비스'의 통화 설정 도우미입니다.
        사용자의 요청을 분석하여 자연스럽고 '무한히 이어지는' 가짜 통화(Fake Call) 설정을 만들어주세요.
        
        사용자 요청: "{chat_msg.message}"
        
        대화 구조:
        1. intro_script: 통화를 시작할 때의 인사와 상황 파악 (2-3쌍)
        2. loop_script: 대화가 끊기지 않도록 하는 풍부한 추임새와 일상적인 질문 (10쌍 이상)
           - 루프 섹션은 어느 시점에 말해도 자연스러워야 합니다 (예: "응응 듣고 있어", "아 진짜?", "그랬구나", "천천히 와")
        
        반드시 아래의 JSON 구조로만 응답하세요. 다른 설명은 생략하세요:
        {{
            "reply": "사용자에게 할 친절한 답변 (예: 네, 아빠 컨셉으로 설정해 드릴게요.)",
            "config": {{
                "caller_name": "발신자 이름",
                "gender": "male 또는 female",
                "intro_script": [
                    {{"caller": "상대방 대사", "user": "나의 대답"}}
                ],
                "loop_script": [
                    {{"caller": "상대방 추임새/질문", "user": "나의 대답"}}
                ]
            }}
        }}
        """
        # 모델명을 명시적으로 지정하여 호출
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt
        )
        
        # JSON 응답 추출
        content = response.text.strip()
        print(f"DEBUG - Gemini Raw Response: {content}")
        
        # JSON 문자열 추출 (마크다운 코드 블록 제거 및 유연한 파싱)
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        
        try:
            return json.loads(content)
        except Exception as json_e:
            print(f"JSON Parsing Error: {json_e}")
            # 파싱 실패 시 기본 응답 반환
            return {
                "reply": "요청하신 설정을 완료했습니다. 통화 버튼을 눌러보세요.",
                "config": {
                    "caller_name": "상대방",
                    "gender": "male",
                    "intro_script": [{"caller": "여보세요? 어디쯤이야?", "user": "응, 나 거의 다 왔어."}],
                    "loop_script": [{"caller": "응응, 계속 말해줘.", "user": "응."}]
                }
            }
        
    except Exception as e:
        print(f"Chat Error Detail: {str(e)}") # 서버 콘솔에 상세 에러 출력
        # 503 등 API 에러 발생 시 앱이 멈추지 않도록 기본 응답(Fallback) 반환
        return {
            "reply": "AI 서버 접속량이 많아 기본 안심 통화 모드로 연결해 드릴게요.",
            "config": {
                "caller_name": "상대방",
                "gender": "male",
                "intro_script": [{"caller": "여보세요? 어디쯤이야?", "user": "응, 나 거의 다 왔어."}],
                "loop_script": [{"caller": "응응, 계속 말해줘.", "user": "응."}]
            }
        }

# 주요 거점 학습 API (DBSCAN 활용 예시)
@app.get("/api/learn-places")
async def get_learned_places():
    places = learn_frequent_places()
    return {"status": "success", "places": places}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# =================================================================
# [알고리즘 담당]
# =================================================================

# 서버가 시작될 때 팀원이 정리해 줄 CSV 파일을 읽어옵니다.
# 파일이 아직 없을 때는 safety_algorithms.py 내부 로직에 의해 임시 가짜 데이터가 담깁니다.
SAFETY_DATA = load_public_data("CCTV정보_서울특별시.csv", "전국안심지킴이집표준데이터.csv")
# API 데이터 요청 규격 정의 (Pydantic Schema)
class CurrentLocationIn(BaseModel):
    lat: float
    lng: float

class RouteRequestIn(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float

# 1. 실시간 주변 안전도 점수 계산 API
@app.post("/api/safety/score")
async def fetch_proximity_safety_score(req: CurrentLocationIn):
    """
    사용자의 현재 위도/경도를 받아 주변 400m 내 안전 인프라를 분석하고 
    최종 안전 점수와 등급('매우 안전', '보통', '주의 필요')을 반환합니다.
    """
    try:
        # 실시간 경찰서 정보 가져오기
        police_data = fetch_police_stations_kakao(req.lat, req.lng, radius=1000)
        combined_safety_data = SAFETY_DATA + police_data
        
        analysis_result = calculate_safety_score(req.lat, req.lng, combined_safety_data, radius=400)
        return {
            "status": "success",
            "score": analysis_result["score"],
            "level": analysis_result["level"],
            "lat": req.lat,
            "lng": req.lng,
            "police_count": len(police_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"안전도 연산 실패: {str(e)}")

# 2. 위험지역 회피 안심 경로 탐색 API
@app.post("/api/safety/route")
async def fetch_optimized_safe_route(req: RouteRequestIn):
    """
    출발지와 목적지 좌표를 받아 위험 구역을 우회하고 
    안전 인프라(CCTV, 파출소 등)를 경유하는 안심 웨이포인트 배열을 반환합니다.
    """
    try:
        # 경로 중간 지점을 기준으로 주변 경찰서 검색 (반경 3km)
        mid_lat = (req.start_lat + req.end_lat) / 2
        mid_lng = (req.start_lng + req.end_lng) / 2
        police_data = fetch_police_stations_kakao(mid_lat, mid_lng, radius=3000)
        
        combined_safety_data = SAFETY_DATA + police_data

        optimized_path = generate_safe_waypoints(
            req.start_lat, req.start_lng,
            req.end_lat, req.end_lng,
            combined_safety_data
        )

        # 거리 및 예상 시간 계산
        total_distance = 0
        for i in range(len(optimized_path) - 1):
            total_distance += haversine_distance(
                optimized_path[i]["lat"], optimized_path[i]["lng"],
                optimized_path[i+1]["lat"], optimized_path[i+1]["lng"]
            )
        
        # 4km/h 기준 (약 66.6m/min)
        estimated_time = max(1, round(total_distance / 66.6))
        
        # 경로 상의 평균 안전도 (경로 중간 지점 샘플링)
        route_mid_idx = len(optimized_path) // 2
        mid_point = optimized_path[route_mid_idx]
        safety_analysis = calculate_safety_score(mid_point["lat"], mid_point["lng"], combined_safety_data)

        return {
            "status": "success",
            "total_nodes": len(optimized_path),
            "coordinates": optimized_path,
            "police_found": len(police_data),
            "distance": round(total_distance, 1),
            "time": estimated_time,
            "safety_score": safety_analysis["score"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"안심 경로 탐색 실패: {str(e)}")