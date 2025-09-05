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
    
    # 推論用ポリシー関数ではなく、実際のactor-criticモデルを取得
    actor_critic = runner.alg.actor_critic
    actor_critic.eval()  # 評価モードに設定
    
    # ダミー入力を作成
    dummy_input = torch.randn(1, obs_cfg["num_obs"], device=gs.device)
    
    # Actorのみをエクスポート（アクションのみが必要）
    actor_model = actor_critic.actor
    
    # ONNXにエクスポート
    torch.onnx.export(
        actor_model,
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
    
    # エクスポートの検証
    try:
        import onnxruntime as ort
        ort_session = ort.InferenceSession(f"{log_dir}/policy_{args.ckpt}.onnx")
        
        # テスト入力
        test_input = dummy_input.cpu().numpy()
        ort_outputs = ort_session.run(None, {'observations': test_input})
        
        # PyTorchでの出力と比較
        with torch.no_grad():
            torch_output = actor_model(dummy_input)
        
        print(f"ONNX export verification:")
        print(f"PyTorch output shape: {torch_output.shape}")
        print(f"ONNX output shape: {ort_outputs[0].shape}")
        print(f"Max difference: {torch.max(torch.abs(torch_output.cpu() - torch.tensor(ort_outputs[0]))).item()}")
        
    except ImportError:
        print("onnxruntime not installed. Install with: pip install onnxruntime")
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    export_policy()