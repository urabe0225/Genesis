import argparse
import os
import pickle
import torch
import torch.onnx
from rsl_rl.runners import OnPolicyRunner
import genesis as gs
from go2_env import Go2Env

def export_policy():
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--exp_name", type=str, default="go2-walking")
    parser.add_argument("--ckpt", type=int, default=100)
    args = parser.parse_args()

    gs.init()
    
    log_dir = f"logs/{args.exp_name}"
    env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg = pickle.load(open(f"{log_dir}/cfgs.pkl", "rb"))
    
    # ダミー環境を作成
    env = Go2Env(num_envs=1, env_cfg=env_cfg, obs_cfg=obs_cfg, 
                 reward_cfg=reward_cfg, command_cfg=command_cfg)
    
    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    resume_path = os.path.join(log_dir, f"model_{args.ckpt}.pt")
    runner.load(resume_path)
    policy = runner.get_inference_policy(device=gs.device)
    
    # ダミー入力を作成
    dummy_input = torch.randn(1, obs_cfg["num_obs"], device=gs.device)
    
    # ONNXにエクスポート
    torch.onnx.export(
        policy,
        dummy_input,
        f"{log_dir}/policy_{args.ckpt}.onnx",
        export_params=True,
        opset_version=11,
        do_constant_folding=True,
        input_names=['observations'],
        output_names=['actions'],
        dynamic_axes={'observations': {0: 'batch_size'},
                      'actions': {0: 'batch_size'}}
    )
    
    print(f"Policy exported to {log_dir}/policy_{args.ckpt}.onnx")

if __name__ == "__main__":
    export_policy()