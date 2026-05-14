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
        # 심층 신경망 모델 구성
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

    def act(self, state):
        if np.random.rand() <= self.epsilon:
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

        # 배치를 한 번에 예측하여 속도 향상 (벡터화)
        targets = self.model.predict(states, verbose=0)
        target_next = self.model.predict(next_states, verbose=0)

        for i in range(batch_size):
            if dones[i]:
                targets[i][actions[i]] = rewards[i]
            else:
                targets[i][actions[i]] = rewards[i] + self.gamma * np.amax(target_next[i])

        # 배치를 한 번에 학습
        self.model.fit(states, targets, epochs=1, verbose=0)
            
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def save(self, name):
        self.model.save(name)

    def load(self, name):
        self.model = models.load_model(name)

# --- 학습 시뮬레이션 실행 ---
if __name__ == "__main__":
    env = SafetyMapEnv()
    agent = DQNAgent(env.state_size, env.action_size)
    episodes = 100
    batch_size = 32

    print("DQN 학습 시작...")
    for e in range(episodes):
        state = env.reset()
        for time in range(50): # 최대 50걸음
            action = agent.act(state)
            next_state, reward, done = env.step(action)
            agent.remember(state, action, reward, next_state, done)
            state = next_state
            
            if done:
                print(f"에피소드: {e+1}/{episodes}, 성공! 점수: {time}, 탐험율: {agent.epsilon:.2}")
                break
                
            if len(agent.memory) > batch_size:
                agent.replay(batch_size)
        
        if (e+1) % 10 == 0:
            print(f"진행 중... {e+1} 에피소드 완료")

    agent.save("safety_dqn_model.h5")
    print("모델 저장 완료: safety_dqn_model.h5")
