#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import numpy as np
import os
import onnxruntime as ort

def fix_cyclonedx_config():
    """Fix CycloneDDS configuration"""
    print("=== Fixing CycloneDDS Configuration ===")
    
    config_path = "/home/unitree/cyclonedx_ws/cyclonedx.xml"
    backup_path = config_path + ".backup"
    
    # Create backup of original
    if os.path.exists(config_path):
        os.rename(config_path, backup_path)
        print(f"✓ Backed up original config to: {backup_path}")
    
    # Create correct configuration
    correct_config = """<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDX xmlns="https://cyclonedx.org/1.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="https://cyclonedx.org/1.0/">
  <Domain id="any">
    <General>
      <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
      <AllowMulticast>default</AllowMulticast>
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
        print(f"✓ Created correct config: {config_path}")
        
        # Set environment variable
        os.environ['CYCLONEDX_URI'] = config_path
        print(f"✓ Set CYCLONEDX_URI: {config_path}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to create config: {e}")
        return False

def test_fixed_connection():
    """Test connection with fixed configuration"""
    print("\n=== Testing Fixed Connection ===")
    
    try:
        # Import SDK after fixing config
        from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_
        
        print("✓ SDK imports successful")
        
        # Create channels
        state_channel = "rt/lowstate"
        cmd_channel = "rt/lowcmd"
        
        print(f"Creating channels: {state_channel}, {cmd_channel}")
        
        state_sub = ChannelSubscriber(state_channel, LowState_)
        cmd_pub = ChannelPublisher(cmd_channel, LowCmd_)
        
        print("✓ Channels created successfully")
        
        # Initialize
        init1 = state_sub.Init()
        init2 = cmd_pub.Init()
        
        print(f"Initialization: state={init1}, cmd={init2}")
        
        # Wait and test
        print("Waiting for connection...")
        time.sleep(3.0)
        
        state = state_sub.Read()
        
        if state is not None:
            print("🎉 SUCCESS! Robot connection established!")
            print(f"  IMU Roll: {state.imu_state.rpy[0]:.3f}")
            print(f"  IMU Pitch: {state.imu_state.rpy[1]:.3f}")
            print(f"  Joint 0 pos: {state.motor_state[0].q:.3f}")
            return True, state_sub, cmd_pub
        else:
            print("⚠ No data received")
            return False, state_sub, cmd_pub
            
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None

def test_safe_movement(state_sub, cmd_pub):
    """Test safe robot movement"""
    print("\n=== Safe Movement Test ===")
    
    try:
        # Read current state
        state = state_sub.Read()
        if state is None:
            print("✗ Cannot read state")
            return
        
        current_pos = [state.motor_state[i].q for i in range(12)]
        print(f"Current position: {current_pos[:4]}")
        
        # Define safe target (small movement)
        target_pos = current_pos.copy()
        target_pos[0] += 0.02  # Small movement on first joint
        
        print("Sending safe movement command...")
        
        # Create command
        cmd = LowCmd_()
        for i in range(12):
            cmd.motor_cmd[i].mode = 1
            cmd.motor_cmd[i].q = float(target_pos[i])
            cmd.motor_cmd[i].kp = 15.0
            cmd.motor_cmd[i].kd = 0.4
            cmd.motor_cmd[i].dq = 0.0
            cmd.motor_cmd[i].tau = 0.0
        
        # Send for 2 seconds
        for _ in range(100):  # 2 seconds at 50Hz
            cmd_pub.Write(cmd)
            time.sleep(0.02)
        
        print("✓ Safe movement completed")
        
    except Exception as e:
        print(f"✗ Movement test failed: {e}")

def main():
    print("Go2 Final Fix and Test")
    print("=" * 40)
    
    # Fix CycloneDDS configuration
    config_fixed = fix_cyclonedx_config()
    
    if not config_fixed:
        print("✗ Could not fix configuration")
        return
    
    # Test connection with fixed config
    success, state_sub, cmd_pub = test_fixed_connection()
    
    if success:
        print("\n✓ Connection successful!")
        
        # Test safe movement
        response = input("\nTest safe robot movement? (y/N): ")
        if response.lower() == 'y':
            test_safe_movement(state_sub, cmd_pub)
        
        print("\n🎉 SUCCESS! You can now use:")
        print("   python3 examples/locomotion/go2_working_test.py")
        
    else:
        print("\n✗ Connection still failed")
        print("Additional troubleshooting needed")

if __name__ == "__main__":
    main()