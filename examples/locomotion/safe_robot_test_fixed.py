# -*- coding: utf-8 -*-
import time
import numpy as np
import onnxruntime as ort
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_

class SafeGo2Controller:
    def __init__(self, onnx_model_path=None):
        self.session = None
        self.state_sub = None
        self.cmd_pub = None
        self.robot_connected = False
        
        # Load ONNX model
        if onnx_model_path:
            try:
                self.session = ort.InferenceSession(onnx_model_path)
                print(f"✓ ONNX model loaded: {onnx_model_path}")
            except Exception as e:
                print(f"✗ Failed to load ONNX model: {e}")
        
        # Initialize Unitree SDK with better error handling
        self.init_sdk()
        
        # Safety parameters
        self.safe_kp = 5.0
        self.safe_kd = 0.2
        self.max_angle_change = 0.1
        
        # Default joint angles (standing pose)
        self.default_angles = np.array([
            0.0, 0.8, -1.5,  # FR
            0.0, 0.8, -1.5,  # FL
            0.0, 1.0, -1.5,  # RR
            0.0, 1.0, -1.5   # RL
        ])
        
        self.current_target = self.default_angles.copy()
    
    def init_sdk(self):
        """Initialize SDK with retry and better error handling"""
        print("Initializing Unitree SDK...")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}/{max_retries}")
                
                # Create subscribers and publishers
                self.state_sub = ChannelSubscriber("rt/lowstate", LowState_)
                self.cmd_pub = ChannelPublisher("rt/lowcmd", LowCmd_)
                
                # Initialize
                init_result1 = self.state_sub.Init()
                init_result2 = self.cmd_pub.Init()
                
                print(f"State subscriber init: {init_result1}")
                print(f"Command publisher init: {init_result2}")
                
                # Wait for initialization
                time.sleep(2.0)
                
                # Test communication
                print("Testing communication...")
                test_state = self.state_sub.Read()
                
                if test_state is not None:
                    print("✓ Robot communication established")
                    self.robot_connected = True
                    
                    # Print some basic info
                    print(f"IMU data available: {hasattr(test_state, 'imu_state')}")
                    print(f"Motor data available: {hasattr(test_state, 'motor_state')}")
                    return
                else:
                    print(f"⚠ Attempt {attempt + 1}: No data received")
                    
            except Exception as e:
                print(f"⚠ Attempt {attempt + 1} failed: {e}")
                
            # Wait before retry
            if attempt < max_retries - 1:
                print("Waiting before retry...")
                time.sleep(3.0)
        
        print("✗ Failed to establish robot connection after all attempts")
        print("Make sure robot services are running:")
        print("  sudo systemctl start unitree-robot-sdk")
        print("  sudo systemctl start unitree-robot")
    
    def test_connection(self):
        """Simple connection test"""
        print("\n=== Connection Test ===")
        
        if not self.robot_connected:
            print("✗ No robot connection")
            return False
        
        try:
            state = self.state_sub.Read()
            if state is not None:
                print("✓ Successfully read robot state")
                print(f"IMU Roll: {state.imu_state.rpy[0]:.3f}")
                print(f"IMU Pitch: {state.imu_state.rpy[1]:.3f}")
                print(f"IMU Yaw: {state.imu_state.rpy[2]:.3f}")
                print(f"First joint position: {state.motor_state[0].q:.3f}")
                return True
            else:
                print("✗ Failed to read robot state")
                return False
        except Exception as e:
            print(f"✗ Connection test failed: {e}")
            return False
    
    def test_1_standing_pose(self):
        """Test 1: Set robot to standing pose"""
        print("\n=== Test 1: Standing Pose ===")
        
        if not self.robot_connected:
            print("⚠ Skipping - no robot connection")
            return
        
        if not self.test_connection():
            print("⚠ Skipping - connection test failed")
            return
        
        print("Setting robot to standing pose...")
        print("This will take 3 seconds...")
        
        try:
            cmd = LowCmd_()
            for i in range(12):
                cmd.motor_cmd[i].mode = 1  # Position control mode
                cmd.motor_cmd[i].q = self.default_angles[i]
                cmd.motor_cmd[i].kp = self.safe_kp
                cmd.motor_cmd[i].kd = self.safe_kd
                cmd.motor_cmd[i].dq = 0.0
                cmd.motor_cmd[i].tau = 0.0
            
            # Send commands for 3 seconds
            for step in range(150):  # 50Hz * 3 seconds
                self.cmd_pub.Write(cmd)
                time.sleep(0.02)
                
                # Print progress every 50 steps (1 second)
                if step % 50 == 0:
                    print(f"Progress: {step//50 + 1}/3 seconds")
            
            print("✓ Standing pose test completed")
            
        except Exception as e:
            print(f"✗ Standing pose test failed: {e}")

def main():
    print("=== Go2 Safe Testing Protocol ===")
    
    # Check if model exists
    model_path = "logs/go2-walking/policy_100.onnx"
    
    try:
        controller = SafeGo2Controller(model_path)
        
        print(f"\n=== System Status ===")
        print(f"Model loaded: {'✓' if controller.session else '✗'}")
        print(f"Robot connected: {'✓' if controller.robot_connected else '✗'}")
        
        if controller.robot_connected:
            input("\nPress Enter to run connection test...")
            controller.test_connection()
            
            input("\nPress Enter to start standing pose test...")
            controller.test_1_standing_pose()
            
            print("\n✓ Basic tests completed!")
            print("If successful, you can now run full tests.")
        else:
            print("\n⚠ Robot not connected. Please:")
            print("1. Run: python3 examples/locomotion/start_robot_services.py")
            print("2. Wait for services to start")
            print("3. Run this test again")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")

if __name__ == "__main__":
    main()