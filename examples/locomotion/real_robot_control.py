import time
import numpy as np
import onnxruntime as ort
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_

class Go2RealController:
    def __init__(self, onnx_model_path):
        # ONNXモデルのロード
        self.session = ort.InferenceSession(onnx_model_path)
        
        # Unitree SDK初期化
        self.state_sub = ChannelSubscriber("rt/lowstate", LowState_)
        self.cmd_pub = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.state_sub.Init()
        self.cmd_pub.Init()
        
        # 関節名と順序の定義（学習時と同じ順序）
        self.joint_names = [
            "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
            "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint", 
            "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
            "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint"
        ]
        
        # 制御パラメータ（学習時と同じ）
        self.kp = 20.0
        self.kd = 0.5
        self.action_scale = 0.25
        
        # デフォルト関節角度
        self.default_angles = np.array([
            0.0, 0.8, -1.5,  # FR
            0.0, 0.8, -1.5,  # FL
            0.0, 1.0, -1.5,  # RR
            0.0, 1.0, -1.5   # RL
        ])
        
        # 観測値の正規化スケール
        self.obs_scales = {
            "lin_vel": 2.0,
            "ang_vel": 0.25,
            "dof_pos": 1.0,
            "dof_vel": 0.05,
        }
        
        # 履歴バッファ
        self.action_history = np.zeros((3, 12))
        
    def get_observations(self, state):
        """ロボットの状態から観測値を構築"""
        obs = np.zeros(45)
        
        # IMUデータ（重力ベクトル）
        obs[0:3] = [state.imu_state.rpy[0], state.imu_state.rpy[1], 0]  # projected gravity
        
        # 指令値（ダミー：実際はキーボード入力等から）
        obs[3:6] = [0.0, 0.0, 0.0]  # lin_vel_x, lin_vel_y, ang_vel_z commands
        
        # ベース線形速度
        obs[6:9] = [state.imu_state.accelerometer[0], 
                    state.imu_state.accelerometer[1], 
                    state.imu_state.accelerometer[2]]
        obs[6:9] *= self.obs_scales["lin_vel"]
        
        # ベース角速度
        obs[9:12] = [state.imu_state.gyroscope[0],
                     state.imu_state.gyroscope[1], 
                     state.imu_state.gyroscope[2]]
        obs[9:12] *= self.obs_scales["ang_vel"]
        
        # 関節位置（デフォルトからの差分）
        joint_pos = np.array([state.motor_state[i].q for i in range(12)])
        obs[12:24] = (joint_pos - self.default_angles) * self.obs_scales["dof_pos"]
        
        # 関節速度
        joint_vel = np.array([state.motor_state[i].dq for i in range(12)])
        obs[24:36] = joint_vel * self.obs_scales["dof_vel"]
        
        # アクション履歴
        obs[36:48] = self.action_history.flatten()
        
        return obs.astype(np.float32)
    
    def step(self, target_commands=[0.0, 0.0, 0.0]):
        """1ステップの制御実行"""
        # 状態取得
        state = self.state_sub.Read()
        
        # 観測値構築
        obs = self.get_observations(state)
        obs[3:6] = target_commands  # 指令値を更新
        
        # ポリシーから動作予測
        obs_tensor = obs.reshape(1, -1)
        actions = self.session.run(None, {'observations': obs_tensor})[0][0]
        
        # アクション履歴更新
        self.action_history[1:] = self.action_history[:-1]
        self.action_history[0] = actions
        
        # 目標関節角度計算
        target_pos = self.default_angles + actions * self.action_scale
        
        # 低レベルコマンド送信
        cmd = LowCmd_()
        for i in range(12):
            cmd.motor_cmd[i].mode = 1  # Position control mode
            cmd.motor_cmd[i].q = target_pos[i]
            cmd.motor_cmd[i].kp = self.kp
            cmd.motor_cmd[i].kd = self.kd
            cmd.motor_cmd[i].dq = 0.0
            cmd.motor_cmd[i].tau = 0.0
        
        self.cmd_pub.Write(cmd)

def main():
    # 学習済みモデルのパス
    model_path = "logs/go2-walking/policy_100.onnx"
    
    controller = Go2RealController(model_path)
    
    print("Real robot control started. Press Ctrl+C to stop.")
    
    try:
        while True:
            # キーボード入力や他の方法で指令値を設定
            commands = [0.5, 0.0, 0.0]  # 前進0.5m/s
            controller.step(commands)
            time.sleep(0.02)  # 50Hz制御
            
    except KeyboardInterrupt:
        print("Control stopped.")

if __name__ == "__main__":
    main()