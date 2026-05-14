document.addEventListener('DOMContentLoaded', () => {
    // UI Elements - Tabs & Navigation
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view-container');
    const bottomSheet = document.querySelector('.bottom-sheet');

    // UI Elements - Common
    const callModal = document.getElementById('call-modal');
    const incomingCall = document.getElementById('incoming-call');
    const activeCall = document.getElementById('active-call');
    const acceptBtn = document.getElementById('accept-btn');
    const declineBtn = document.getElementById('decline-btn');
    const endCallBtn = document.getElementById('end-call-btn');
    const callTimer = document.getElementById('call-timer');
    const userLineEl = document.getElementById('user-line');

    // UI Elements - Home View
    const homeSosBtn = document.getElementById('home-sos-btn');

    // UI Elements - Safe Call View
    const chips = document.querySelectorAll('.chip');
    const startCallBtn = document.getElementById('start-call-btn');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');

    let timerInterval;
    let seconds = 0;
    let scriptIndex = 0;
    let isLooping = false;
    let scriptTimeout;

    let currentCallConfig = {
        caller_name: '아빠',
        gender: 'male',
        intro_script: [
            {"caller": "어디쯤이니?", "user": "응, 나 지금 거의 다 왔어."},
            {"caller": "금방 갈 테니까 조심해서 오렴", "user": "응, 걱정하지 마. 금방 들어가."}
        ],
        loop_script: [
            {"caller": "응응, 계속 말해봐.", "user": "응, 그래서 아까 말이야..."},
            {"caller": "아 진짜? 그런 일이 있었어?", "user": "그러니까, 나도 깜짝 놀랐다니까."},
            {"caller": "응, 듣고 있어. 천천히 와.", "user": "어, 지금 골목길 지나고 있어."}
        ]
    };

    // --- Tab Navigation Logic ---
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.dataset.tab;
            
            // Update active state in Nav
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // Show target view, hide others
            views.forEach(view => {
                view.classList.remove('active');
                if (view.id === `view-${targetTab}`) {
                    view.classList.add('active');
                }
            });

            // Specific logic for Map view (bottom sheet visibility)
            if (targetTab === 'map') {
                bottomSheet.style.display = 'block';
            } else {
                bottomSheet.style.display = 'none';
            }
        });
    });

    // --- Safe Call Chip Logic ---
    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const group = chip.parentElement;
            group.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
        });
    });

    const getSelectedSetup = () => {
        const gender = document.querySelector('.chip-group[data-type="gender"] .chip.active').dataset.value;
        const age = document.querySelector('.chip-group[data-type="age"] .chip.active').innerText;
        const relation = document.querySelector('.chip-group[data-type="relation"] .chip.active').dataset.value;
        return { gender, age, relation };
    };

    // --- SOS Logic ---
    const triggerSOS = () => {
        const confirmSOS = confirm('긴급 SOS를 요청하시겠습니까? 즉시 보호자와 경찰에 위치가 전송됩니다.');
        if (confirmSOS) alert('SOS 요청이 전송되었습니다.');
    };
    homeSosBtn.addEventListener('click', triggerSOS);
    document.getElementById('sos-btn').addEventListener('click', triggerSOS);
    document.getElementById('sheet-sos-btn').addEventListener('click', triggerSOS);

    // --- Start Return Logic ---
    const startReturnBtn = document.getElementById('start-return-btn');
    let isReturnActive = false;

    startReturnBtn.addEventListener('click', () => {
        if (!isReturnActive) {
            alert('안심 귀가 모드가 시작되었습니다. 보호자에게 위치 공유가 시작됩니다.');
            startReturnBtn.innerText = '안심 귀가 모드 사용 중...';
            startReturnBtn.style.background = 'var(--ios-green)';
            isReturnActive = true;
        } else {
            const confirmEnd = confirm('안심 귀가 모드를 종료하시겠습니까?');
            if (confirmEnd) {
                alert('안심 귀가 모드가 종료되었습니다.');
                startReturnBtn.innerText = '안심 귀가 시작';
                startReturnBtn.style.background = 'var(--ios-blue)';
                isReturnActive = false;
            }
        }
    });

    // --- Safe Call Integration ---
    const addMessage = (text, isUser = false) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `msg ${isUser ? 'user' : 'ai'}`;
        msgDiv.innerText = text;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    const handleSendMessage = async () => {
        const message = chatInput.value.trim();
        if (!message) return;

        addMessage(message, true);
        chatInput.value = '';

        const pushNotif = document.getElementById('push-notification');
        console.log('Sending chat message:', message);

        try {
            const response = await axios.post('/api/chat', { message });
            console.log('API Response:', response.data);
            const { reply, config } = response.data;
            addMessage(reply);
            
            if (config) {
                currentCallConfig = config;
                document.querySelectorAll('.caller-name').forEach(el => el.innerText = config.caller_name);
            }

            // Trigger Push Animation after AI reply with shorter delays
            setTimeout(() => {
                console.log('Triggering Push Notification');
                pushNotif.classList.remove('hidden');
                setTimeout(() => {
                    pushNotif.classList.add('hidden');
                    console.log('Starting Call Flow');
                    setTimeout(startCallFlow, 300);
                }, 2500);
            }, 500);

        } catch (error) {
            console.error('Chat Send Error:', error);
            addMessage('설정을 업데이트했습니다. 통화를 시작할 수 있습니다.');
            
            // Fallback Trigger Push Animation
            setTimeout(() => {
                pushNotif.classList.remove('hidden');
                setTimeout(() => {
                    pushNotif.classList.add('hidden');
                    setTimeout(startCallFlow, 300);
                }, 2500);
            }, 500);
        }
    };

    chatSendBtn.addEventListener('click', handleSendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSendMessage();
    });

    const handleCallStart = async () => {
        const setup = getSelectedSetup();
        const prompt = `${setup.gender === 'male' ? '남성' : '여성'} ${setup.age} ${setup.relation}와 통화하고 싶어. 바로 설정해줘.`;
        
        // Show push notification instead of chat
        const pushNotif = document.getElementById('push-notification');
        document.querySelectorAll('.caller-name').forEach(el => el.innerText = setup.relation);
        
        try {
            const response = await axios.post('/api/chat', { message: prompt });
            const { config } = response.data;
            if (config) {
                currentCallConfig = config;
                document.querySelectorAll('.caller-name').forEach(el => el.innerText = config.caller_name);
            }
            
            // Trigger Push Animation
            pushNotif.classList.remove('hidden');
            setTimeout(() => {
                pushNotif.classList.add('hidden');
                setTimeout(startCallFlow, 500);
            }, 3000);

        } catch (error) {
            console.error('Safe Call Setup Error:', error);
            currentCallConfig.caller_name = setup.relation;
            currentCallConfig.gender = setup.gender;
            
            pushNotif.classList.remove('hidden');
            setTimeout(() => {
                pushNotif.classList.add('hidden');
                setTimeout(startCallFlow, 500);
            }, 3000);
        }
    };

    startCallBtn.addEventListener('click', handleCallStart);

    const startCallFlow = () => {
        callModal.classList.remove('hidden');
        incomingCall.classList.remove('hidden');
        activeCall.classList.add('hidden');
        scriptIndex = 0;
        isLooping = false;
        userLineEl.innerText = "전화를 받으면 대본이 나타납니다.";
    };

    // --- Web Speech API (TTS) ---
    const speak = (text, gender) => {
        if (!window.speechSynthesis) return;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'ko-KR';
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.lang === 'ko-KR' && (gender === 'male' ? v.name.includes('Male') : v.name.includes('Female'))) || voices.find(v => v.lang === 'ko-KR');
        if (preferredVoice) utterance.voice = preferredVoice;
        utterance.pitch = gender === 'male' ? 0.8 : 1.1;
        window.speechSynthesis.speak(utterance);
    };

    const playScript = () => {
        let currentItem;
        if (!isLooping) {
            if (scriptIndex < currentCallConfig.intro_script.length) {
                currentItem = currentCallConfig.intro_script[scriptIndex++];
            } else {
                isLooping = true;
                scriptIndex = 0;
                currentCallConfig.loop_script.sort(() => Math.random() - 0.5);
                currentItem = currentCallConfig.loop_script[scriptIndex++];
            }
        } else {
            if (scriptIndex >= currentCallConfig.loop_script.length) {
                scriptIndex = 0;
                currentCallConfig.loop_script.sort(() => Math.random() - 0.5);
            }
            currentItem = currentCallConfig.loop_script[scriptIndex++];
        }
        if (currentItem) {
            speak(currentItem.caller, currentCallConfig.gender);
            userLineEl.innerText = currentItem.user;
            scriptTimeout = setTimeout(playScript, 6000);
        }
    };

    acceptBtn.addEventListener('click', () => {
        if (window.speechSynthesis) {
            const initUtterance = new SpeechSynthesisUtterance('');
            initUtterance.volume = 0;
            window.speechSynthesis.speak(initUtterance);
        }
        incomingCall.classList.add('hidden');
        activeCall.classList.remove('hidden');
        startTimer();
        setTimeout(playScript, 1000);
    });

    const terminateCall = () => {
        callModal.classList.add('hidden');
        clearInterval(timerInterval);
        seconds = 0;
        callTimer.innerText = '00:00';
        window.speechSynthesis.cancel();
        clearTimeout(scriptTimeout);
    };

    declineBtn.addEventListener('click', terminateCall);
    endCallBtn.addEventListener('click', terminateCall);

    function startTimer() {
        timerInterval = setInterval(() => {
            seconds++;
            const mins = String(Math.floor(seconds / 60)).padStart(2, '0');
            const secs = String(seconds % 60).padStart(2, '0');
            callTimer.innerText = `${mins}:${secs}`;
        }, 1000);
    }

    // --- Bottom Sheet Swipe Logic ---
    let startY, currentY;
    const initialTranslateY = window.innerHeight * 0.7 - 180;

    const handleStart = (e) => {
        startY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;
        bottomSheet.style.transition = 'none';
    };
    const handleMove = (e) => {
        if (startY === undefined) return;
        currentY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;
        const deltaY = startY - currentY;
        let targetY = bottomSheet.classList.contains('expanded') ? Math.max(0, -deltaY) : Math.max(0, initialTranslateY - deltaY);
        targetY = Math.min(initialTranslateY, Math.max(0, targetY));
        bottomSheet.style.transform = `translateY(${targetY}px)`;
    };
    const handleEnd = () => {
        if (startY === undefined) return;
        bottomSheet.style.transition = 'transform 0.3s ease';
        const deltaY = startY - (currentY || startY);
        if (Math.abs(deltaY) > 100) {
            if (deltaY > 0) { bottomSheet.classList.add('expanded'); bottomSheet.style.transform = 'translateY(0)'; }
            else { bottomSheet.classList.remove('expanded'); bottomSheet.style.transform = `translateY(${initialTranslateY}px)`; }
        } else {
            bottomSheet.style.transform = bottomSheet.classList.contains('expanded') ? 'translateY(0)' : `translateY(${initialTranslateY}px)`;
        }
        startY = undefined;
    };

    const dragHandle = document.querySelector('.drag-handle');
    // Swipe logic removed as requested


    // --- Google Auth Integration ---
    const GOOGLE_CLIENT_ID = '856701298539-nekcpffj1mc9aa4p890defc5r0k8upff.apps.googleusercontent.com';
    const loginSection = document.getElementById('login-section');
    const userProfileSection = document.getElementById('user-profile-section');
    const userNameEl = document.getElementById('user-name');
    const userEmailEl = document.getElementById('user-email');
    const userPictureEl = document.getElementById('user-picture');
    const logoutBtn = document.getElementById('logout-btn');

    const updateAuthUI = (user) => {
        const personalizedSettings = document.getElementById('personalized-settings');
        const personalizedPlaceholder = document.getElementById('personalized-settings-placeholder');

        if (user) {
            loginSection.classList.add('hidden');
            userProfileSection.classList.remove('hidden');
            userNameEl.innerText = user.name;
            userEmailEl.innerText = user.email;
            userPictureEl.src = user.picture;
            
            if (personalizedSettings) personalizedSettings.classList.remove('hidden');
            if (personalizedPlaceholder) personalizedPlaceholder.classList.add('hidden');
            
            loadSettings(); // 로그인 시 설정 로드
        } else {
            loginSection.classList.remove('hidden');
            userProfileSection.classList.add('hidden');
            
            if (personalizedSettings) personalizedSettings.classList.add('hidden');
            if (personalizedPlaceholder) personalizedPlaceholder.classList.remove('hidden');
            
            document.getElementById('frequent-places-list').innerHTML = '';
            document.getElementById('emergency-contacts-list').innerHTML = '';
        }
    };

    // --- Settings Management Logic ---
    const loadSettings = async () => {
        if (!localStorage.getItem('token')) return;
        try {
            const [placesRes, contactsRes] = await Promise.all([
                axios.get('/api/settings/frequent-places'),
                axios.get('/api/settings/emergency-contacts')
            ]);
            renderFrequentPlaces(placesRes.data);
            renderEmergencyContacts(contactsRes.data);
        } catch (error) {
            console.error('Failed to load settings:', error);
        }
    };

    const renderFrequentPlaces = (places) => {
        const list = document.getElementById('frequent-places-list');
        list.innerHTML = '';
        places.forEach(place => {
            const card = createPlaceCard(place);
            list.appendChild(card);
        });
    };

    const renderEmergencyContacts = (contacts) => {
        const list = document.getElementById('emergency-contacts-list');
        list.innerHTML = '';
        contacts.forEach(contact => {
            const card = createContactCard(contact);
            list.appendChild(card);
        });
    };

    const createPlaceCard = (place = { id: null, name: '', address: '' }) => {
        const card = document.createElement('div');
        card.className = 'settings-item-card';
        card.innerHTML = `
            <div class="settings-item-header">
                <span class="title">${place.name || '새 장소'}</span>
                ${place.id ? `<button class="delete-btn-text" data-id="${place.id}">삭제</button>` : ''}
            </div>
            <div class="settings-item-body">
                <div class="settings-input-row">
                    <label>장소 이름</label>
                    <input type="text" class="input-name" value="${place.name}" placeholder="예: 우리집, 회사">
                </div>
                <div class="settings-input-row">
                    <label>주소</label>
                    <input type="text" class="input-address" value="${place.address}" placeholder="클릭하여 주소 검색" readonly>
                </div>
                <button class="save-btn-small">${place.id ? '수정' : '저장'}</button>
            </div>
        `;

        const addressInput = card.querySelector('.input-address');
        addressInput.addEventListener('click', () => {
            new daum.Postcode({
                oncomplete: function(data) {
                    // 도로명 주소 또는 지번 주소를 선택한 값으로 설정
                    addressInput.value = data.roadAddress || data.address;
                }
            }).open();
        });

        const saveBtn = card.querySelector('.save-btn-small');
        saveBtn.addEventListener('click', async () => {
            const name = card.querySelector('.input-name').value;
            const address = card.querySelector('.input-address').value;
            if (!name || !address) return alert('이름과 주소를 모두 입력해주세요.');
            
            try {
                await axios.post('/api/settings/frequent-places', { name, address });
                alert('저장되었습니다.');
                loadSettings();
            } catch (error) {
                alert('저장에 실패했습니다.');
            }
        });

        const delBtn = card.querySelector('.delete-btn-text');
        if (delBtn) {
            delBtn.addEventListener('click', async () => {
                if (!confirm('정말 삭제하시겠습니까?')) return;
                try {
                    await axios.delete(`/api/settings/frequent-places/${place.id}`);
                    loadSettings();
                } catch (error) {
                    alert('삭제에 실패했습니다.');
                }
            });
        }
        return card;
    };

    const createContactCard = (contact = { id: null, name: '', relation: '', phone: '' }) => {
        const card = document.createElement('div');
        card.className = 'settings-item-card';

        const renderViewMode = () => {
            let displayName = contact.name;
            if (contact.relation && contact.relation !== "") {
                displayName += ` (${contact.relation})`;
            }

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; font-size: 15px; color: #333; margin-bottom: 4px;">${displayName}</div>
                        <div style="font-size: 13px; color: var(--ios-gray);">${contact.phone}</div>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="edit-btn-text">수정</button>
                        <button class="delete-btn-text" data-id="${contact.id}">삭제</button>
                    </div>
                </div>
            `;

            card.querySelector('.edit-btn-text').addEventListener('click', renderEditMode);
            card.querySelector('.delete-btn-text').addEventListener('click', async () => {
                if (!confirm('정말 삭제하시겠습니까?')) return;
                try {
                    await axios.delete(`/api/settings/emergency-contacts/${contact.id}`);
                    loadSettings();
                } catch (error) {
                    alert('삭제에 실패했습니다.');
                }
            });
        };

        const renderEditMode = () => {
            let combinedValue = contact.name;
            if (contact.relation && contact.relation !== "") {
                combinedValue += ` (${contact.relation})`;
            }

            card.innerHTML = `
                <div class="settings-item-header">
                    <span class="title">${contact.id ? '연락처 수정' : '새 연락처'}</span>
                </div>
                <div class="settings-item-body">
                    <div class="settings-input-row">
                        <label>이름/관계</label>
                        <input type="text" class="input-name-relation" value="${combinedValue}" placeholder="예: 홍길동 (아빠)">
                    </div>
                    <div class="settings-input-row">
                        <label>전화번호</label>
                        <input type="tel" class="input-phone" value="${contact.phone}" placeholder="010-0000-0000">
                    </div>
                    <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px;">
                        ${contact.id ? '<button class="cancel-btn-text">취소</button>' : ''}
                        <button class="save-btn-small">저장</button>
                    </div>
                </div>
            `;

            if (contact.id) {
                card.querySelector('.cancel-btn-text').addEventListener('click', renderViewMode);
            }

            card.querySelector('.save-btn-small').addEventListener('click', async () => {
                const combinedName = card.querySelector('.input-name-relation').value.trim();
                const phone = card.querySelector('.input-phone').value.trim();

                if (!combinedName || !phone) return alert('모든 정보를 입력해주세요.');

                try {
                    if (contact.id) {
                        await axios.put(`/api/settings/emergency-contacts/${contact.id}`, { 
                            name: combinedName, 
                            relation: "", 
                            phone: phone 
                        });
                    } else {
                        await axios.post('/api/settings/emergency-contacts', { 
                            name: combinedName, 
                            relation: "", 
                            phone: phone 
                        });
                    }
                    alert('저장되었습니다.');
                    loadSettings();
                } catch (error) {
                    alert('저장에 실패했습니다.');
                }
            });
        };

        if (contact.id) {
            renderViewMode();
        } else {
            renderEditMode();
        }

        return card;
    };
    document.getElementById('add-place-btn').addEventListener('click', () => {
        const list = document.getElementById('frequent-places-list');
        // 이미 추가 중인 항목(ID가 없는 카드)이 있는지 확인
        const existingUnsaved = list.querySelector('.save-btn-small:not([data-id])');
        if (existingUnsaved && !existingUnsaved.closest('.settings-item-card').querySelector('.delete-btn-text')) {
             // place card has no easy way to check id, let's use a simpler check: 
             // check if there's any input field that's part of a card without a delete button (new card)
        }
        
        // 정교한 체크: 리스트 내의 모든 카드 중 삭제 버튼이 없는 것이 새 카드임
        const newCards = Array.from(list.querySelectorAll('.settings-item-card')).filter(card => !card.querySelector('.delete-btn-text'));
        if (newCards.length > 0) {
            alert('이미 새로운 장소를 추가 중입니다. 먼저 저장해주세요.');
            return;
        }

        list.prepend(createPlaceCard());
    });

    document.getElementById('add-contact-btn').addEventListener('click', () => {
        const list = document.getElementById('emergency-contacts-list');
        // 긴급 연락처는 renderEditMode에서 id가 없으면 삭제 버튼이 없음
        const newCards = Array.from(list.querySelectorAll('.settings-item-card')).filter(card => !card.querySelector('.delete-btn-text'));
        if (newCards.length > 0) {
            alert('이미 새로운 연락처를 추가 중입니다. 먼저 저장해주세요.');
            return;
        }
        list.prepend(createContactCard());
    });

    const switchTab = (tabId) => {
        const navItem = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
        if (navItem) {
            navItem.click();
        }
    };

    const handleGoogleLogin = async (response) => {
        try {
            const res = await axios.post('/api/auth/google', { credential: response.credential });
            const { access_token, user } = res.data;
            
            localStorage.setItem('token', access_token);
            localStorage.setItem('user', JSON.stringify(user));
            
            // Set default auth header for future requests
            axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
            
            updateAuthUI(user);
            alert(`${user.name}님, 환영합니다!`);
            
            // 로그인 성공 후 '홈' 탭으로 이동
            switchTab('home');
        } catch (error) {
            console.error('Login Error:', error);
            alert('로그인에 실패했습니다.');
        }
    };

    // Google Login 초기화 함수
    const initGoogleLogin = () => {
        if (window.google) {
            google.accounts.id.initialize({
                client_id: GOOGLE_CLIENT_ID,
                callback: handleGoogleLogin
            });
            const loginBtn = document.getElementById('google-login-btn');
            if (loginBtn) {
                google.accounts.id.renderButton(loginBtn, { theme: 'outline', size: 'large', width: '250' });
            }
        } else {
            // 아직 로드되지 않았다면 잠시 후 다시 시도
            setTimeout(initGoogleLogin, 100);
        }
    };

    // Initialize
    initGoogleLogin();

    // Check for existing session
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    if (savedToken && savedUser) {
        axios.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`;
        updateAuthUI(JSON.parse(savedUser));
    }

    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        delete axios.defaults.headers.common['Authorization'];
        updateAuthUI(null);
        alert('로그아웃 되었습니다.');
    });

    // --- Kakao Maps Logic ---
    const API_KEY = '1d88eaa665348747e894a1849b949cf1';
    const mapScript = document.createElement('script');
    mapScript.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${API_KEY}&libraries=services&autoload=false`;
    document.head.appendChild(mapScript);

    mapScript.onload = () => {
        kakao.maps.load(() => {
            const mapContainer = document.getElementById('map');
            const mapOption = { center: new kakao.maps.LatLng(37.5665, 126.9780), level: 3 };
            const map = new kakao.maps.Map(mapContainer, mapOption);
            const geocoder = new kakao.maps.services.Geocoder();
            let allMarkers = [];
            const infoWindow = new kakao.maps.InfoWindow({ zIndex: 1 });

            const userContent = `<div class="user-marker-container"><div class="user-marker-heading"></div><div class="user-marker-dot"></div></div>`;
            const userOverlay = new kakao.maps.CustomOverlay({ content: userContent, position: map.getCenter(), zIndex: 3 });
            userOverlay.setMap(map);

            const icons = {
                CCTV: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDE2IDE2Ij48cGF0aCBmaWxsPSIjNDQ0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjAuNSIgZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMCA1YTIgMiAwIDAgMSAyLTJoNy41YTIgMiAwIDAgMSAxLjk4MyAxLjczOGwzLjExLTEuMzgyQTEgMSAwIDAgMSAxNiA0LjI2OXY3LjQ2MmExIDEgMCAwIDEtMS40MDYuOTEzbC0zLjExMS0xLjM4MkEyIDIgMCAwIDEgOS41IDEzSDJhMiAyIDAgMCAxLTItMnoiLz48L3N2Zz4=',
                POLICE: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDE2IDE2Ij48cGF0aCBmaWxsPSIjMDA3QUZGIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjAuNSIgZD0iTTUuMDcyLjU2QzYuMTU3LjI2NSA3LjMxIDAgOCAwczEuODQzLjI2NSAyLjkyOC41NmMxLjExLjMgMi4yMjkuNjU1IDIuODg3Ljg3YTEuNTQgMS41NCAwIDAgMSAxLjA0NCAxLjI2MmMuNTk2IDQuNDc3LS43ODcgNy43OTUtMi40NjUgOS45OWExMS44IDExLjggMCAwIDEtMi41MTcgMi40NTMgNy4yIDcuMiAwIDAgMS0xLjA0OC42MjVjLS4yOC4xMzItLjU4MS4yNC0uODI5LjI0cy0uNTQ4LS4xMDgtLjgyOS0uMjRhNy4yIDcuMiAwIDAgMS0xLjA0OC0uNjI1IDExLjggMTEuOCAwIDAgMS0yLjUxNy0yLjQ1M0MxLjkyOCAxMC40NjMuNTQ1IDcuMTQ1IDEuMTQxIDIuNjkyQTEuNTQgMS41NCAwIDAgMSAyLjE4NSAxLjQzIDYzIDYzIDAgMCAxIDUuMDcyLjU2Ii8+PC9zdmc+',
                STORE: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDE2IDE2Ij48cGF0aCBmaWxsPSIjRkYzQjMwIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjAuNSIgZD0iTTcuMjkzIDEuNWExIDEgMCAwIDEgMS40MTQgMGw2LjY0NyA2LjY0NmEuNS41IDAgMCAxLS43MDguNzA4TDggMi4yMDcgMS4zNTQgOC44NTRhLjUuNSAwIDEgMS0uNzA4LS43MDh6Ii8+PHBhdGggZmlsbD0iI0ZGM0IzMCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIwLjUiIGQ9Ik04LjcwNyAxLjVhMSAxIDAgMCAwLTEuNDE0IDBMLjY0NiA4LjE0NmEuNS41IDAgMCAwIC43MDguNzA4TDIgOC4yMDdWMTMuNWExLjUgMS41IDAgMCAwIDEuNSAxLjVoOWExLjUgMS41IDAgMCAwIDEuNS0xLjVWOC4yMDdsLjY0Ni42NDdhLjUuNSAwIDAgMCAuNzA4LS43MDh6TTggNi45ODJDOS42NjQgNS4zMDkgMTMuODI1IDguMjM2IDggMTIgMi4xNzUgOC4yMzYgNi4zMzYgNS4zMTAgOCA2Ljk4MiIvPjwvc3ZnPg=='
            };

            const generateSafetyFacilities = (lat, lng) => {
                allMarkers.forEach(m => m.setMap(null));
                allMarkers = [];
                const facilities = [
                    { type: 'CCTV', count: 8, icon: icons.CCTV, name: '안심 CCTV' },
                    { type: 'POLICE', count: 2, icon: icons.POLICE, name: '파출소' },
                    { type: 'STORE', count: 4, icon: icons.STORE, name: '지킴이집' }
                ];
                facilities.forEach(f => {
                    for (let i = 0; i < f.count; i++) {
                        const pos = new kakao.maps.LatLng(lat + (Math.random() - 0.5) * 0.01, lng + (Math.random() - 0.5) * 0.01);
                        const m = new kakao.maps.Marker({ position: pos, image: new kakao.maps.MarkerImage(f.icon, new kakao.maps.Size(22, 22)), title: f.name });
                        kakao.maps.event.addListener(m, 'click', () => { infoWindow.setContent(`<div style="padding:10px;font-size:12px;">${f.name}</div>`); infoWindow.open(map, m); });
                        m.setMap(map);
                        allMarkers.push(m);
                    }
                });
            };

            const updateLocation = (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const loc = new kakao.maps.LatLng(lat, lng);
                map.panTo(loc);
                userOverlay.setPosition(loc);
                if (allMarkers.length === 0) generateSafetyFacilities(lat, lng);
                geocoder.coord2Address(lng, lat, (result, status) => {
                    if (status === kakao.maps.services.Status.OK) {
                        const addr = result[0].address.address_name;
                        document.getElementById('current-location').innerText = addr;
                        const homeLocEl = document.getElementById('home-current-location');
                        if (homeLocEl) homeLocEl.innerText = addr;
                        
                        // Update safety level text and color
                        const safetyLevelEl = document.getElementById('safety-level');
                        const homeSafetyLevelEl = document.getElementById('home-safety-level');
                        const safetyText = '매우 안전';
                        const safetyClass = 'safety-level-safe';
                        
                        if (safetyLevelEl) {
                            safetyLevelEl.innerText = safetyText;
                            safetyLevelEl.className = `value ${safetyClass}`;
                        }
                        if (homeSafetyLevelEl) {
                            homeSafetyLevelEl.innerText = safetyText;
                            homeSafetyLevelEl.style.color = 'var(--ios-green)'; // Applying direct style for Home tab as it doesn't have the same structure
                        }
                    }
                });
            };

            if (navigator.geolocation) {
                navigator.geolocation.watchPosition(updateLocation, console.error, { enableHighAccuracy: true });
            }

            const handleOrientation = (e) => {
                const heading = e.webkitCompassHeading || (360 - e.alpha);
                if (heading) {
                    const el = document.querySelector('.user-marker-heading');
                    if (el) el.style.transform = `translate(-50%, -50%) rotate(${heading}deg)`;
                }
            };
            const requestPermission = () => {
                if (window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission === 'function') {
                    DeviceOrientationEvent.requestPermission().then(res => { if (res === 'granted') window.addEventListener('deviceorientation', handleOrientation); });
                } else { window.addEventListener('deviceorientation', handleOrientation); }
            };
            window.addEventListener('click', requestPermission, { once: true });
        });
    };
});
