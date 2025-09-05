#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import numpy as np
import os
import sys

def setup_cyclonedds():
    """Setup CycloneDDS environment"""
    print("=== Setting up CycloneDDS ===")
    
    # Go2のCycloneDDS設定ファイルパス
    cyclone_config = "/home/unitree/cyclonedx_ws/cyclonedx.xml"
    
    # 設定ファイルが存在するか確認
    if os.path.exists(cyclone_config):
        print(f"✓ Found CycloneDDS config: {cyclone_config}")
        os.environ['CYCLONEDX_URI'] = cyclone_config
    else:
        print(f"⚠ Config file not found: {cyclone_config}")
        # デフォルト設定を作成
        create_default_cyclonedds_config()
    
    # その他のDDS環境変数
    os.environ['ROS_DOMAIN_ID'] = '0'
    
    print("CycloneDDS environment configured")

def create_default_cyclonedds_config():
    """Create a default CycloneDDS configuration"""
    print("Creating default CycloneDDS configuration...")
    
    config_content = """<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDX xmlns="https://cyclonedx.org/1.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="https://cyclonedx.org/1.0/">
  <General>
    <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
  </General>
  <Discovery>
    <ParticipantIndex>auto</ParticipantIndex>
    <MaxAutoParticipantIndex>200</MaxAutoParticipantIndex>
  </Discovery>
</CycloneDX>"""
    
    # 設定ファイルを作成
    config_dir = "/tmp"
    config_file = os.path.join(config_dir, "cyclonedds.xml")
    
    try:
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        os.environ['CYCLONEDX_URI'] = config_file
        print(f"✓ Created config: {config_file}")
        
    except Exception as e:
        print(f"✗ Failed to create config: {e}")

def test_cyclonedx_directly():
    """Test CycloneDDS directly"""
    print("\n=== Direct CycloneDDS Test ===")
    
    try:
        # CycloneDDSを直接インポート
        import cyclonedx
        print("✓ CycloneDDS imported successfully")
        
        # DomainParticipantを作成
        domain_id = 0
        participant = cyclonedx.DomainParticipant(domain_id)
        
        if participant:
            print(f"✓ DomainParticipant created for domain {domain_id}")
            return True
        else:
            print(f"✗ Failed to create DomainParticipant")
            return False
            
    except ImportError as e:
        print(f"✗ CycloneDDS import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ CycloneDDS test failed: {e}")
        return False

def test_unitree_sdk_with_fixed_dds():
    """Test Unitree SDK with fixed DDS"""
    print("\n=== Unitree SDK Test (Fixed DDS) ===")
    
    try:
        # Unitree SDKをインポート
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
            print(f"✗ State subscriber failed: {e}")
            return False
        
        try:
            cmd_pub = ChannelPublisher(cmd_channel, LowCmd_)
            print("✓ Command publisher created")
        except Exception as e:
            print(f"✗ Command publisher failed: {e}")
            return False
        
        # 初期化
        print("Initializing channels...")
        init1 = state_sub.Init()
        init2 = cmd_pub.Init()
        
        print(f"Initialization results: state={init1}, cmd={init2}")
        
        # 通信テスト
        print("Testing communication...")
        time.sleep(2.0)
        
        try:
            state = state_sub.Read()
            if state is not None:
                print("✓ Successfully received robot state!")
                print(f"  IMU Roll: {state.imu_state.rpy[0]:.3f}")
                print(f"  IMU Pitch: {state.imu_state.rpy[1]:.3f}")
                print(f"  Joint 0 pos: {state.motor_state[0].q:.3f}")
                return True, state_sub, cmd_pub
            else:
                print("⚠ No data received")
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

def test_basic_robot_control(state_sub, cmd_pub):
    """Test basic robot control"""
    print("\n=== Basic Robot Control Test ===")
    
    if not state_sub or not cmd_pub:
        print("⚠ No valid channels")
        return
    
    try:
        # 現在の状態を読み取り
        state = state_sub.Read()
        if state is None:
            print("✗ Cannot read robot state")
            return
        
        current_positions = [state.motor_state[i].q for i in range(12)]
        print(f"Current positions: {current_positions[:4]}")
        
        # 安全な目標位置（現在位置から少しずつ変更）
        target_positions = current_positions.copy()
        target_positions[0] += 0.05  # 最初のジョイントを少し動かす
        
        print("Sending safe movement command...")
        
        # コマンド作成
        cmd = LowCmd_()
        for i in range(12):
            cmd.motor_cmd[i].mode = 1  # Position control
            cmd.motor_cmd[i].q = float(target_positions[i])
            cmd.motor_cmd[i].kp = 10.0  # 適度なゲイン
            cmd.motor_cmd[i].kd = 0.3
            cmd.motor_cmd[i].dq = 0.0
            cmd.motor_cmd[i].tau = 0.0
        
        # コマンド送信（短時間）
        for _ in range(50):  # 1秒間
            cmd_pub.Write(cmd)
            time.sleep(0.02)
        
        print("✓ Basic control test completed")
        
    except Exception as e:
        print(f"✗ Control test failed: {e}")

def main():
    print("Go2 CycloneDDS Fix and Test")
    print("=" * 50)
    
    # CycloneDDS環境をセットアップ
    setup_cyclonedds()
    
    # CycloneDDSを直接テスト
    dds_ok = test_cyclonedx_directly()
    
    if dds_ok:
        print("\n✓ CycloneDDS working, testing Unitree SDK...")
        
        # Unitree SDKをテスト
        sdk_ok, state_sub, cmd_pub = test_unitree_sdk_with_fixed_dds()
        
        if sdk_ok:
            print("\n🎉 SUCCESS! Robot connection established!")
            
            # 基本制御をテスト
            response = input("\nTest basic robot movement? (y/N): ")
            if response.lower() == 'y':
                test_basic_robot_control(state_sub, cmd_pub)
            
            print("\n✓ You can now use the original go2_working_test.py")
        else:
            print("\n⚠ SDK connection failed despite DDS working")
    else:
        print("\n✗ CycloneDDS not working")
        print("Try:")
        print("1. Check if CycloneDDS is properly installed")
        print("2. Restart Go2 services")
        print("3. Check network configuration")

if __name__ == "__main__":
    main()