import argparse
import os
import pickle
from importlib import metadata
import sys
import select
import tty
import termios

import torch

try:
    try:
        if metadata.version("rsl-rl"):
            raise ImportError
    except metadata.PackageNotFoundError:
        if metadata.version("rsl-rl-lib") != "2.2.4":
            raise ImportError
except (metadata.PackageNotFoundError, ImportError) as e:
    raise ImportError("Please uninstall 'rsl_rl' and install 'rsl-rl-lib==2.2.4'.") from e
from rsl_rl.runners import OnPolicyRunner

import genesis as gs

from go2_env import Go2Env

class KeyboardController:
    def __init__(self):
        self.lin_vel_x = 0.0
        self.lin_vel_y = 0.0
        self.ang_vel = 0.0
        self.running = True
        self.old_settings = None
        self.vel_step = 0.2  # 速度変化のステップ
        
    def init_keyboard(self):
        """キーボード設定を初期化"""
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        
    def restore_keyboard(self):
        """キーボード設定を復元"""
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
    
    def get_key_non_blocking(self):
        """ノンブロッキングでキー入力を取得"""
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            key = sys.stdin.read(1)
            # 矢印キーの場合は追加の文字を読み取る
            if key == '\x1b':  # ESCシーケンスの開始
                next_chars = sys.stdin.read(2)
                if next_chars == '[A':  # 上矢印
                    return 'UP'
                elif next_chars == '[B':  # 下矢印
                    return 'DOWN'
                elif next_chars == '[C':  # 右矢印
                    return 'RIGHT'
                elif next_chars == '[D':  # 左矢印
                    return 'LEFT'
                else:
                    return '\x1b'  # ESCキー
            return key
        return None
    
    def update_commands(self):
        """キー入力に基づいてコマンドを更新"""
        key = self.get_key_non_blocking()
        
        if key is not None:
            if key == '\x1b':  # ESC
                self.running = False
                print("\nExiting...")
                return False
            elif key == 'UP':  # ↑: 前進
                self.lin_vel_x = min(self.lin_vel_x + self.vel_step, 1.0)
                self.lin_vel_y = 0.0  # 横移動をリセット
                self.ang_vel = 0.0    # 回転をリセット
                print(f"Forward: {self.lin_vel_x:.1f} m/s")
            elif key == 'DOWN':  # ↓: 後退
                self.lin_vel_x = max(self.lin_vel_x - self.vel_step, -1.0)
                self.lin_vel_y = 0.0  # 横移動をリセット
                self.ang_vel = 0.0    # 回転をリセット
                print(f"Backward: {self.lin_vel_x:.1f} m/s")
            elif key == 'RIGHT':  # →: 右回転
                self.ang_vel = max(self.ang_vel - self.vel_step, -1.0)
                self.lin_vel_x = 0.0  # 前後移動をリセット
                self.lin_vel_y = 0.0  # 横移動をリセット
                print(f"Turn right: {self.ang_vel:.1f} rad/s")
            elif key == 'LEFT':  # ←: 左回転
                self.ang_vel = min(self.ang_vel + self.vel_step, 1.0)
                self.lin_vel_x = 0.0  # 前後移動をリセット
                self.lin_vel_y = 0.0  # 横移動をリセット
                print(f"Turn left: {self.ang_vel:.1f} rad/s")
            elif key.lower() == ' ':  # スペースキー: 停止
                self.lin_vel_x = 0.0
                self.lin_vel_y = 0.0
                self.ang_vel = 0.0
                print("Stop")
        
        return True
    
    def get_commands(self):
        return [self.lin_vel_x, self.lin_vel_y, self.ang_vel]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exp_name", type=str, default="go2-walking")
    parser.add_argument("--ckpt", type=int, default=100)
    args = parser.parse_args()

    gs.init()

    log_dir = f"logs/{args.exp_name}"
    env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg = pickle.load(open(f"logs/{args.exp_name}/cfgs.pkl", "rb"))
    reward_cfg["reward_scales"] = {}

    env = Go2Env(
        num_envs=1,
        env_cfg=env_cfg,
        obs_cfg=obs_cfg,
        reward_cfg=reward_cfg,
        command_cfg=command_cfg,
        show_viewer=True,
    )

    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    resume_path = os.path.join(log_dir, f"model_{args.ckpt}.pt")
    runner.load(resume_path)
    policy = runner.get_inference_policy(device=gs.device)

    # キーボードコントローラーの初期化
    kb_controller = KeyboardController()
    kb_controller.init_keyboard()
    
    print("Keyboard control:")
    print("↑: Forward")
    print("↓: Backward") 
    print("←: Turn left")
    print("→: Turn right")
    print("SPACE: Stop")
    print("ESC: Quit")
    print("\nPress arrow keys to control the robot...")

    obs, _ = env.reset()
    
    try:
        with torch.no_grad():
            while kb_controller.running:
                # キーボード入力の更新
                if not kb_controller.update_commands():
                    break
                
                # キーボードからの指令を環境に設定
                commands = kb_controller.get_commands()
                if hasattr(env, 'set_commands'):
                    env.set_commands(commands)
                
                actions = policy(obs)
                obs, rews, dones, infos = env.step(actions)
                
    except KeyboardInterrupt:
        print("\nControl interrupted")
    finally:
        kb_controller.restore_keyboard()

if __name__ == "__main__":
    main()

"""
# evaluation
python examples/locomotion/go2_eval.py -e go2-walking -v --ckpt 100
"""
