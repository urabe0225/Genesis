#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import numpy as np
import os
import onnxruntime as ort

def setup_cyclonedds_environment():
    """Setup CycloneDDS environment correctly"""
    print("=== Setting up CycloneDDS Environment ===")
    
    # 正しいCycloneDDS設定ファイルを作成
    config_path = "/tmp/cyclonedds_go2.xml"
    
    correct_config = """<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDX xmlns="https://cyclonedx.org/schema/cyclonedx/1.4"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="https://cyclonedx.org/schema/cyclonedx/1.4 https://raw.githubusercontent.com/CycloneDX/specification/1.4/schema/cyclonedx-1.4.xsd">
  <Domain id="any">
    <General>
      <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
      <AllowMulticast>true</AllowMulticast>
      <MaxMessageSize>65500B</MaxMessageSize>
    </General>
    <Discovery>
      <ParticipantIndex>auto</ParticipantIndex>
      <MaxAutoParticipantIndex>200</MaxAutoParticipantIndex>
      <SPDPMulticastAddress>239.255.0.1</SPDPMulticastAddress>
      <SPDPInterval>30s</SPDPInterval>
      <DefaultMulticastAddress>auto</DefaultMulticastAddress>
    </Discovery>
    <Internal>
      <MinimumSocketReceiveBufferSize>1MB</MinimumSocketReceiveBufferSize>
    </Internal>
  </Domain>
</CycloneDX>"""
    
    try:
        with open(config_path, 'w') as f:
            f.write(correct_config)
        
        # 環境変数設定
        os.environ['CYCLONEDX_URI'] = config_path
        os.environ['ROS_DOMAIN_ID'] = '0'
        
        print(f"✓ Created CycloneDDS config: {config_path}")
        print(f"✓ Set CYCLONEDX_URI: {config_path}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to setup CycloneDDS: {e}")
        return False

def test_cyclonedds_directly():
    """Test CycloneDDS directly with correct import"""
    print("\n=== Testing CycloneDDS Directly ===")
    
    try:
        # 正しいインポート
        import cyclonedds
        print("✓ cyclonedds imported successfully")
        
        # DomainParticipantを作成
        from cyclonedds.domain import DomainParticipant
        
        domain_id = 0
        participant = DomainParticipant(domain_id)
        
        if participant:
            print(f"✓ DomainParticipant created for domain {domain_id}")
            print(f"✓ Participant GUID: {participant.guid}")
            return True, participant
        else:
            print(f"✗ Failed to create DomainParticipant")
            return False, None
            
    except ImportError as e:
        print(f"✗ cyclonedds import failed: {e}")
        return False, None
    except Exception as e:
        print(f"✗ CycloneDDS test failed: {e}")
        return False, None

def test_unitree_sdk_with_cyclonedds():
    """Test Unitree SDK with properly configured CycloneDDS"""
    print("\n=== Testing Unitree SDK ===")
    
    try:
        from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_
        
        print("✓ Unitree SDK imported")
        
        # チャンネル作成
        state_channel = "rt/lowstate"
        cmd_channel = "rt/lowcmd"
        
        print(f"Creating channels: {state_channel}, {cmd_channel}")
        
        try:
            state_sub = ChannelSubscriber(state_channel, LowState_)
            print("✓ State subscriber created")
        except Exception as e:
            print(f"✗ State subscriber creation failed: {e}")
            return False, None, None
        
        try:
            cmd_pub = ChannelPublisher(cmd_channel, LowCmd_)
            print("✓ Command publisher created")
        except Exception as e:
            print(f"✗ Command publisher creation failed: {e}")
            return False, None, None
        
        # 初期化
        print("Initializing channels...")
        try:
            init1 = state_sub.Init()
            init2 = cmd_pub.Init()
            print(f"Initialization results: state={init1}, cmd={init2}")
        except Exception as e:
            print(f"✗ Channel initialization failed: {e}")
            return False, None, None
        
        # 通信テスト
        print("Testing communication (waiting 3 seconds)...")
        time.sleep(3.0)
        
        try:
            state = state_sub.Read()
            if state is not None:
                print("🎉 SUCCESS! Robot data received!")
                print(f"  IMU Roll: {state.imu_state.rpy[0]:.3f}")
                print(f"  IMU Pitch: {state.imu_state.rpy[1]:.3f}")
                print(f"  IMU Yaw: {state.imu_state.rpy[2]:.3f}")
                print(f"  Joint 0 position: {state.motor_state[0].q:.3f}")
                print(f"  Joint 0 velocity: {state.motor_state[0].dq:.3f}")
                return True, state_sub, cmd_pub
            else:
                print("⚠ No data received from robot")
                return False, state_sub, cmd_pub
        except Exception as e:
            print(f"⚠ Communication test failed: {e}")
            return False, state_sub, cmd_pub
            
    except ImportError as e:
        print(f"✗ Unitree SDK import failed: {e}")
        return False, None, None
    except Exception as e:
        print(f"✗ Unitree SDK test failed: {e}")
        return False, None, None

def test_safe_robot_movement(state_sub, cmd_pub):
    """Test safe robot movement"""
    print("\n=== Safe Robot Movement Test ===")
    
    if not state_sub or not cmd_pub:
        print("⚠ No valid channels available")
        return
    
    try:
        # 現在の状態を読み取り
        state = state_sub.Read()
        if state is None:
            print("✗ Cannot read robot state")
            return
        
        current_positions = np.array([state.motor_state[i].q for i in range(12)])
        print(f"Current joint positions: {current_positions[:4]}")
        
        # 安全な目標位置（現在位置からわずかに変更）
        target_positions = current_positions.copy()
        target_positions[0] += 0.02  # 最初のジョイントを2度動かす
        
        print("Sending safe movement command (2-degree movement on joint 0)...")
        
        # コマンド作成
        cmd = LowCmd_()
        for i in range(12):
            cmd.motor_cmd[i].mode = 1  # Position control mode
            cmd.motor_cmd[i].q = float(target_positions[i])
            cmd.motor_cmd[i].kp = 20.0  # 適度なゲイン
            cmd.motor_cmd[i].kd = 0.5
            cmd.motor_cmd[i].dq = 0.0
            cmd.motor_cmd[i].tau = 0.0
        
        # 1.5秒間コマンドを送信
        print("Moving robot for 1.5 seconds...")
        for step in range(75):  # 1.5秒 @ 50Hz
            cmd_pub.Write(cmd)
            time.sleep(0.02)
            
            if step % 25 == 0:
                print(f"  Step {step+1}/75")
        
        print("✓ Safe movement test completed")
        
        # 元の位置に戻す
        print("Returning to original position...")
        for i in range(12):
            cmd.motor_cmd[i].q = float(current_positions[i])
        
        for step in range(75):
            cmd_pub.Write(cmd)
            time.sleep(0.02)
        
        print("✓ Returned to original position")
        
    except Exception as e:
        print(f"✗ Movement test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("Go2 CycloneDDS Fixed Test")
    print("=" * 50)
    
    # CycloneDDS環境をセットアップ
    #if not setup_cyclonedds_environment():
    #    print("✗ Failed to setup CycloneDDS environment")
    #    return
    
    # CycloneDDSを直接テスト
    dds_ok, participant = test_cyclonedds_directly()
    
    if not dds_ok:
        print("\n✗ CycloneDDS not working")
        return
    
    # Unitree SDKをテスト
    sdk_ok, state_sub, cmd_pub = test_unitree_sdk_with_cyclonedds()
    
    if sdk_ok:
        print("\n🎉 SUCCESS! Robot connection established!")
        
        # 安全な動作をテスト
        response = input("\nTest safe robot movement (small joint movement)? (y/N): ")
        if response.lower() == 'y':
            print("\n⚠ SAFETY WARNING:")
            print("  - Robot will make a small movement")
            print("  - Make sure robot is in safe position")
            print("  - Press Ctrl+C to stop if needed")
            
            confirm = input("Continue? (y/N): ")
            if confirm.lower() == 'y':
                test_safe_robot_movement(state_sub, cmd_pub)
        
        print(f"\n✅ SUCCESS! Your Go2 is ready for:")
        print("   - Running the original safe_robot_test_fixed.py")
        print("   - Testing your trained walking model")
        print("   - Full locomotion experiments")
        
    else:
        print("\n⚠ Robot connection failed")
        print("Possible issues:")
        print("1. Robot not in correct mode (try Sport mode)")
        print("2. Network connectivity")
        print("3. Robot services not running")

if __name__ == "__main__":
    main()