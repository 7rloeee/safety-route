import numpy as np
import random
import tensorflow as tf
from tensorflow.keras import layers, models, optimizers
from collections import deque
from dqn_env import SafetyMapEnv

class DQNAgent:
    def __init__(self, state_size, action_size):
        self.state_size = state_size
        self.action_size = action_size
        self.memory = deque(maxlen=2000)
        self.gamma = 0.95    # 할인율
        self.epsilon = 1.0   # 탐험율
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001
        self.model = self._build_model()

    def _build_model(self):
        model = models.Sequential([
            layers.Input(shape=(self.state_size,)),
            layers.Dense(24, activation='relu'),
            layers.Dense(24, activation='relu'),
            layers.Dense(self.action_size, activation='linear')
        ])
        model.compile(loss='mse', optimizer=optimizers.Adam(learning_rate=self.learning_rate))
        return model

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state, train=True):
        # 학습 중일 때만 무작위 탐험(epsilon) 사용, 실제 경로 찾을 때는 최적값만 선택
        if train and (np.random.rand() <= self.epsilon):
            return random.randrange(self.action_size)
        act_values = self.model.predict(state.reshape(1, self.state_size), verbose=0)
        return np.argmax(act_values[0])

    def replay(self, batch_size):
        if len(self.memory) < batch_size:
            return
        
        minibatch = random.sample(self.memory, batch_size)
        
        states = np.array([i[0] for i in minibatch])
        actions = np.array([i[1] for i in minibatch])
        rewards = np.array([i[2] for i in minibatch])
        next_states = np.array([i[3] for i in minibatch])
        dones = np.array([i[4] for i in minibatch])

        targets = self.model.predict(states, verbose=0)
        target_next = self.model.predict(next_states, verbose=0)

        for i in range(batch_size):
            if dones[i]:
                targets[i][actions[i]] = rewards[i]
            else:
                targets[i][actions[i]] = rewards[i] + self.gamma * np.amax(target_next[i])

        self.model.fit(states, targets, epochs=1, verbose=0)
            
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def save(self, name):
        self.model.save(name)

    def load(self, name):
        self.model = models.load_model(name)

# --- 학습 시뮬레이션 및 안심경로 테스트 실행 ---
if __name__ == "__main__":
    env = SafetyMapEnv()
    agent = DQNAgent(env.state_size, env.action_size)
    episodes = 150  # 10x10 맵에서 더 완벽하게 길을 학습하도록 에피소드를 살짝 늘렸어!
    batch_size = 32

    print("===== [1] DQN 안심경로 AI 학습 시작 =====")
    for e in range(episodes):
        state = env.reset()
        for time in range(50): # 최대 50걸음
            action = agent.act(state, train=True)
            next_state, reward, done = env.step(action)
            agent.remember(state, action, reward, next_state, done)
            state = next_state
            
            if done:
                break
                
            if len(agent.memory) > batch_size:
                agent.replay(batch_size)
        
        if (e+1) % 10 == 0:
            print(f"에피소드: {e+1}/{episodes} 완료 | 현재 탐험율(Epsilon): {agent.epsilon:.2f}")

    agent.save("safety_dqn_model.h5")
    print("\n모델 저장 완료: safety_dqn_model.h5")
    
    print("\n===== [2] 학습된 AI 기반 안심경로 탐색 시작 =====")
    
    state = env.reset()
    path = [tuple(state)] # 출발지 저장 (0,0)
    total_reward = 0
    action_labels = ["위", "아래", "왼쪽", "오른쪽"]
    
    for step_count in range(50):
        action = agent.act(state, train=False) # train=False로 오직 AI의 판단으로만 이동
        next_state, reward, done = env.step(action)
        
        path.append(tuple(next_state))
        total_reward += reward
        
        print(f"걸음 {step_count+1}: 현재 위치 {state} -> 선택 행동: [{action_labels[action]}] -> 이동 위치 {next_state} (보상: {reward})")
        
        state = next_state
        if done:
            print("\n🎉 AI가 안전하게 최종 목적지(Goal)에 도착했습니다!")
            break
    else:
        print("\n⚠️ 제한 걸음 수 내에 목적지에 도착하지 못했습니다. 추가 학습이 필요할 수 있습니다.")

    print(f"\n▶ 최종 생성된 안심 경로 좌표 리스트:\n{path}")
    print(f"▶ 총 경로 안전 점수(보상 합산): {total_reward}")