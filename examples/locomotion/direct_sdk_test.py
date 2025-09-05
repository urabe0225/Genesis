#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import numpy as np

def test_direct_sdk_connection():
    """Test direct SDK connection without services"""
    print("=== Direct SDK Connection Test ===")
    
    try:
        from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_
        
        print("✓ SDK imports successful")
        
        # Try different channel configurations
        channel_configs = [
            ("rt/lowstate", "rt/lowcmd"),
            ("lowstate", "lowcmd"),
            ("/lowstate", "/lowcmd"),
            ("unitree/lowstate", "unitree/lowcmd")
        ]
        
        for state_channel, cmd_channel in channel_configs:
            print(f"\nTrying channels: {state_channel}, {cmd_channel}")
            
            try:
                state_sub = ChannelSubscriber(state_channel, LowState_)
                cmd_pub = ChannelPublisher(cmd_channel, LowCmd_)
                
                print("  ✓ Created subscribers/publishers")
                
                # Initialize
                state_sub.Init()
                cmd_pub.Init()
                print("  ✓ Initialized channels")
                
                # Wait and test
                time.sleep(1.0)
                state = state_sub.Read()
                
                if state is not None:
                    print(f"  ✓ SUCCESS! Data received from {state_channel}")
                    print(f"    IMU data available: {hasattr(state, 'imu_state')}")
                    print(f"    Motor data available: {hasattr(state, 'motor_state')}")
                    return True, state_channel, cmd_channel
                else:
                    print(f"  ⚠ No data from {state_channel}")
                    
            except Exception as e:
                print(f"  ✗ Failed: {e}")
        
        print("\n✗ All channel configurations failed")
        return False, None, None
        
    except ImportError as e:
        print(f"✗ SDK import failed: {e}")
        return False, None, None

def test_alternative_methods():
    """Test alternative connection methods"""
    print("\n=== Alternative Connection Methods ===")
    
    # Try ROS if available
    try:
        import rospy
        print("✓ ROS available - checking topics...")
        
        import subprocess
        result = subprocess.run(['rostopic', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            topics = result.stdout
            robot_topics = [line for line in topics.split('\n') 
                          if any(keyword in line.lower() for keyword in 
                                ['joint', 'imu', 'robot', 'go2', 'unitree'])]
            if robot_topics:
                print("  Found robot topics:")
                for topic in robot_topics[:5]:
                    print(f"    {topic}")
            else:
                print("  No robot topics found")
        else:
            print("  ROS master not running")
            
    except ImportError:
        print("✗ ROS not available")
    
    # Check for direct device interfaces
    print("\nChecking for direct device interfaces...")
    device_paths = [
        '/dev/ttyUSB*',
        '/dev/ttyACM*', 
        '/dev/serial/by-id/*unitree*'
    ]
    
    import glob
    for pattern in device_paths:
        devices = glob.glob(pattern)
        if devices:
            print(f"✓ Found devices: {devices}")
        else:
            print(f"✗ No devices found: {pattern}")

def main():
    print("Go2 Direct Connection Test")
    print("=" * 40)
    
    # Test direct SDK connection
    success, state_channel, cmd_channel = test_direct_sdk_connection()
    
    if success:
        print(f"\n🎉 SUCCESS! Working channels found:")
        print(f"   State: {state_channel}")
        print(f"   Command: {cmd_channel}")
        print("\nYou can now use these channels for robot control!")
        
        # Create a simple test file
        test_code = f'''
# Working channel configuration found:
state_sub = ChannelSubscriber("{state_channel}", LowState_)
cmd_pub = ChannelPublisher("{cmd_channel}", LowCmd_)
'''
        with open('/home/tie305374/Genesis/working_channels.txt', 'w') as f:
            f.write(test_code)
        print("Channel config saved to: working_channels.txt")
        
    else:
        print("\n⚠ Direct SDK connection failed.")
        test_alternative_methods()
        
        print("\nNext steps:")
        print("1. Check if robot is powered on and in correct mode")
        print("2. Verify network connection to robot")
        print("3. Look for Go2-specific startup procedures")
        print("4. Check robot documentation for SDK usage")

if __name__ == "__main__":
    main()