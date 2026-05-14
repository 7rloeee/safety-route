import numpy as np

class SafetyMapEnv:
    def __init__(self, grid_size=10):
        self.grid_size = grid_size
        self.state_size = 2  # (x, y) 좌표
        self.action_size = 4  # 0: 위, 1: 아래, 2: 왼쪽, 3: 오른쪽
        
        # 가상의 보상 맵 (안전 점수)
        # 기본적으로 모든 칸은 -1 (최단거리 이동 유도)
        self.reward_map = np.full((grid_size, grid_size), -1.0)
        
        # CCTV 위치 설정 (높은 보상)
        cctv_locations = [(2,2), (2,3), (4,5), (7,8), (1,7)]
        for x, y in cctv_locations:
            self.reward_map[x, y] += 20.0
            
        # 가로등 위치 설정 (중간 보상)
        light_locations = [(1,1), (3,3), (5,5), (6,6), (8,8)]
        for x, y in light_locations:
            self.reward_map[x, y] += 10.0
            
        # 위험 구역 설정 (감점)
        danger_locations = [(3,1), (3,2), (6,4), (7,4)]
        for x, y in danger_locations:
            self.reward_map[x, y] -= 50.0
            
        # 최종 목적지 (Goal)
        self.goal = (grid_size - 1, grid_size - 1)
        self.reward_map[self.goal] = 100.0
        
        self.reset()

    def reset(self):
        # 출발 지점 (0, 0)
        self.state = [0, 0]
        return np.array(self.state)

    def step(self, action):
        x, y = self.state
        
        if action == 0:   # 위
            x = max(0, x - 1)
        elif action == 1: # 아래
            x = min(self.grid_size - 1, x + 1)
        elif action == 2: # 왼쪽
            y = max(0, y - 1)
        elif action == 3: # 오른쪽
            y = min(self.grid_size - 1, y + 1)
            
        self.state = [x, y]
        reward = self.reward_map[x, y]
        done = (x, y) == self.goal
        
        return np.array(self.state), reward, done

    def get_reward_map(self):
        return self.reward_map

if __name__ == "__main__":
    env = SafetyMapEnv()
    print("가상 안전 보상 맵:\n", env.get_reward_map())
