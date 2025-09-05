#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import numpy as np
import os

def setup_unitree_dds_environment():
    """Setup DDS environment specifically for Unitree SDK"""
    print("=== Setting up Unitree DDS Environment ===")
    
    # Unitree SDK用の環境変数設定
    os.environ.pop('CYCLONEDX_URI', None)  # 既存の設定をクリア
    os.environ['ROS_DOMAIN_ID'] = '0'
    
    # Unitree SDK用のシンプルなDDS設定
    simple_config = """<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDX>
  <Domain>
    <General>
      <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
    </General>
  </Domain>
</CycloneDX>"""
    
    config_path = "/tmp/unitree_dds.xml"
    
    try:
        with open(config_path, 'w') as f:
            f.write(simple_config)
        
        os.environ['CYCLONEDX_URI'] = config_path
        print(f"✓ Created Unitree DDS config: {config_path}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to setup Unitree DDS: {e}")
        return False

def initialize_dds_manually():
    """Manually initialize DDS before Unitree SDK"""
    print("\n=== Manual DDS Initialization ===")
    
    try:
        import cyclonedx
        from cyclonedx.domain import DomainParticipant
        
        # グローバルなDomainParticipantを作成
        global_participant = DomainParticipant(0)
        
        if global_participant:
            print(f"✓ Global DomainParticipant created: {global_participant.guid}")
            
            # 少し待ってDDSが安定するのを待つ
            time.sleep(2.0)
            return True, global_participant
        else:
            print("✗ Failed to create global DomainParticipant")
            return False, None
            
    except Exception as e:
        print(f"✗ Manual DDS initialization failed: {e}")
        return False, None

def test_unitree_sdk_step_by_step():
    """Test Unitree SDK step by step with detailed error handling"""
    print("\n=== Step-by-Step Unitree SDK Test ===")
    
    try:
        # Step 1: Import SDK modules
        print("Step 1: Importing Unitree SDK modules...")
        from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher
        print("✓ Channel classes imported")
        
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_
        print("✓ Message types imported")
        
        # Step 2: Try creating channels with different approaches
        print("\nStep 2: Testing different channel creation approaches...")
        
        approaches = [
            ("rt/lowstate", "rt/lowcmd"),
            ("lowstate", "lowcmd"),
            ("/rt/lowstate", "/rt/lowcmd"),
        ]
        
        for i, (state_ch, cmd_ch) in enumerate(approaches):
            print(f"\nApproach {i+1}: {state_ch}, {cmd_ch}")
            
            try:
                print("  Creating state subscriber...")
                state_sub = ChannelSubscriber(state_ch, LowState_)
                print("  ✓ State subscriber created")
                
                print("  Creating command publisher...")
                cmd_pub = ChannelPublisher(cmd_ch, LowCmd_)
                print("  ✓ Command publisher created")
                
                print("  Initializing channels...")
                init1 = state_sub.Init()
                init2 = cmd_pub.Init()
                print(f"  ✓ Initialization: state={init1}, cmd={init2}")
                
                # 通信テスト
                print("  Testing communication...")
                time.sleep(1.0)
                
                state = state_sub.Read()
                if state is not None:
                    print(f"  🎉 SUCCESS with approach {i+1}!")
                    return True, state_sub, cmd_pub
                else:
                    print(f"  ⚠ No data with approach {i+1}")
                    
            except Exception as e:
                print(f"  ✗ Approach {i+1} failed: {e}")
                continue
        
        print("\n✗ All approaches failed")
        return False, None, None
        
    except ImportError as e:
        print(f"✗ SDK import failed: {e}")
        return False, None, None

def check_robot_services_and_processes():
    """Check if robot services and processes are in the right state"""
    print("\n=== Robot Services and Processes Check ===")
    
    import subprocess
    
    # Check Go2 processes
    try:
        result = subprocess.run(['pgrep', '-af', 'go2'], capture_output=True, text=True)
        if result.stdout:
            print("✓ Go2 processes running:")
            for line in result.stdout.strip().split('\n'):
                print(f"  {line}")
        else:
            print("⚠ No Go2 processes found")
    except Exception as e:
        print(f"⚠ Could not check Go2 processes: {e}")
    
    # Check DDS-related processes
    try:
        result = subprocess.run(['pgrep', '-af', 'dds'], capture_output=True, text=True)
        if result.stdout:
            print("✓ DDS processes running:")
            for line in result.stdout.strip().split('\n'):
                print(f"  {line}")
        else:
            print("⚠ No DDS processes found")
    except Exception as e:
        print(f"⚠ Could not check DDS processes: {e}")
    
    # Check services
    services = ['go2_bridge', 'unitree_slam']
    for service in services:
        try:
            result = subprocess.run(['systemctl', 'is-active', service], 
                                  capture_output=True, text=True)
            status = result.stdout.strip()
            symbol = "✓" if status == "active" else "⚠"
            print(f"{symbol} {service}: {status}")
        except Exception as e:
            print(f"? {service}: Could not check")

def try_alternative_robot_interface():
    """Try alternative methods to interface with the robot"""
    print("\n=== Alternative Robot Interface ===")
    
    # Check if there are any ROS topics
    try:
        import subprocess
        result = subprocess.run(['rostopic', 'list'], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0 and result.stdout:
            print("✓ ROS topics available:")
            topics = result.stdout.strip().split('\n')
            robot_topics = [t for t in topics if any(k in t.lower() 
                           for k in ['joint', 'imu', 'robot', 'go2', 'unitree'])]
            
            if robot_topics:
                print("  Robot-related topics:")
                for topic in robot_topics[:5]:
                    print(f"    {topic}")
                print("\n✓ ROS interface might be available as alternative")
            else:
                print("  No robot-related topics found")
        else:
            print("⚠ ROS not available or no topics")
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠ ROS not available")
    except Exception as e:
        print(f"⚠ ROS check failed: {e}")

def main():
    print("Go2 Unitree DDS Fix")
    print("=" * 40)
    
    # Check current robot state
    check_robot_services_and_processes()
    
    # Setup Unitree-specific DDS environment
    #if not setup_unitree_dds_environment():
    #    print("✗ Failed to setup DDS environment")
    #    return
    
    # Initialize DDS manually
    dds_ok, participant = initialize_dds_manually()
    
    if not dds_ok:
        print("✗ Manual DDS initialization failed")
        try_alternative_robot_interface()
        return
    
    # Try Unitree SDK step by step
    sdk_ok, state_sub, cmd_pub = test_unitree_sdk_step_by_step()
    
    if sdk_ok:
        print("\n🎉 SUCCESS! Robot connection established!")
        print("You can now run your locomotion experiments!")
        
    else:
        print("\n⚠ Unitree SDK connection failed")
        print("\nTroubleshooting suggestions:")
        print("1. Restart Go2 services:")
        print("   sudo systemctl restart go2_bridge")
        print("2. Check robot mode (should be in Sport mode)")
        print("3. Try alternative interfaces:")
        try_alternative_robot_interface()

if __name__ == "__main__":
    main()