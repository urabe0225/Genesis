#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import numpy as np
import onnxruntime as ort
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_

class WorkingGo2Controller:
    def __init__(self, onnx_model_path=None):
        self.session = None
        self.state_sub = None
        self.cmd_pub = None
        self.robot_connected = False
        
        print("=== Go2 Working Controller ===")
        print("Based on discovered Go2 processes and services")
        
        # Load ONNX model
        if onnx_model_path:
            try:
                self.session = ort.InferenceSession(onnx_model_path)
                print(f"✓ ONNX model loaded: {onnx_model_path}")
            except Exception as e:
                print(f"✗ Failed to load ONNX model: {e}")
        
        # Initialize SDK with working configuration
        self.init_go2_sdk()
        
        # Safety parameters (conservative for testing)
        self.safe_kp = 20.0   # Higher gain since Go2 is already running
        self.safe_kd = 0.5
        self.max_angle_change = 0.05
        
        # Default joint angles (Go2 standing pose)
        self.default_angles = np.array([
            0.0, 0.8, -1.5,  # FR
            0.0, 0.8, -1.5,  # FL
            0.0, 1.0, -1.5,  # RR
            0.0, 1.0, -1.5   # RL
        ])
        
        self.current_target = self.default_angles.copy()
    
    def init_go2_sdk(self):
        """Initialize SDK for Go2 (based on discovered processes)"""
        print("\nInitializing Go2 SDK...")
        
        # Go2 uses these standard channels
        state_channel = "rt/lowstate"
        cmd_channel = "rt/lowcmd"
        
        try:
            print(f"Creating channels: {state_channel}, {cmd_channel}")
            
            self.state_sub = ChannelSubscriber(state_channel, LowState_)
            self.cmd_pub = ChannelPublisher(cmd_channel, LowCmd_)
            
            print("Initializing channels...")
            init_result1 = self.state_sub.Init()
            init_result2 = self.cmd_pub.Init()
            
            print(f"State subscriber init result: {init_result1}")
            print(f"Command publisher init result: {init_result2}")
            
            # Wait for DDS to establish connection
            print("Waiting for DDS connection (3 seconds)...")
            time.sleep(3.0)
            
            # Test communication
            print("Testing robot communication...")
            test_state = self.state_sub.Read()
            
            if test_state is not None:
                print("✓ Successfully connected to Go2!")
                print(f"  IMU Roll: {test_state.imu_state.rpy[0]:.3f} rad")
                print(f"  IMU Pitch: {test_state.imu_state.rpy[1]:.3f} rad")
                print(f"  IMU Yaw: {test_state.imu_state.rpy[2]:.3f} rad")
                print(f"  Joint 0 position: {test_state.motor_state[0].q:.3f} rad")
                print(f"  Joint 0 velocity: {test_state.motor_state[0].dq:.3f} rad/s")
                
                self.robot_connected = True
            else:
                print("⚠ Channels initialized but no data received")
                
        except Exception as e:
            print(f"✗ SDK initialization failed: {e}")
            import traceback
            traceback.print_exc()
    
    def read_robot_state(self):
        """Read current robot state"""
        if not self.robot_connected:
            return None
        
        try:
            return self.state_sub.Read()
        except Exception as e:
            print(f"Error reading robot state: {e}")
            return None
    
    def send_joint_commands(self, target_positions, kp=None, kd=None):
        """Send joint position commands"""
        if not self.robot_connected:
            print("⚠ No robot connection")
            return False
        
        if kp is None:
            kp = self.safe_kp
        if kd is None:
            kd = self.safe_kd
        
        try:
            cmd = LowCmd_()
            
            for i in range(12):
                cmd.motor_cmd[i].mode = 1  # Position control mode
                cmd.motor_cmd[i].q = float(target_positions[i])
                cmd.motor_cmd[i].kp = float(kp)
                cmd.motor_cmd[i].kd = float(kd)
                cmd.motor_cmd[i].dq = 0.0
                cmd.motor_cmd[i].tau = 0.0
            
            self.cmd_pub.Write(cmd)
            return True
            
        except Exception as e:
            print(f"Error sending commands: {e}")
            return False
    
    def test_basic_movement(self):
        """Test basic robot movement"""
        print("\n=== Basic Movement Test ===")
        
        if not self.robot_connected:
            print("⚠ No robot connection")
            return
        
        print("Reading current state...")
        state = self.read_robot_state()
        if state is None:
            print("✗ Cannot read robot state")
            return
        
        current_positions = np.array([state.motor_state[i].q for i in range(12)])
        print(f"Current joint positions: {current_positions[:4]}")  # Show first 4 joints
        
        print("\nSetting to default standing pose...")
        success = self.send_joint_commands(self.default_angles)
        
        if success:
            print("✓ Commands sent successfully")
            
            # Monitor for 3 seconds
            print("Monitoring movement for 3 seconds...")
            start_time = time.time()
            
            while time.time() - start_time < 3.0:
                self.send_joint_commands(self.default_angles)  # Keep sending commands
                time.sleep(0.02)  # 50Hz
            
            print("✓ Basic movement test completed")
        else:
            print("✗ Failed to send commands")
    
    def test_model_inference(self):
        """Test model inference with real robot data"""
        print("\n=== Model Inference Test ===")
        
        if self.session is None:
            print("⚠ No model loaded")
            return
        
        if not self.robot_connected:
            print("⚠ No robot connection")
            return
        
        print("Running model inference with real robot data...")
        
        # Read robot state
        state = self.read_robot_state()
        if state is None:
            print("✗ Cannot read robot state")
            return
        
        # Build observation (simplified)
        obs = np.zeros(45, dtype=np.float32)
        
        # IMU data (gravity vector)
        obs[0:3] = [state.imu_state.rpy[0], state.imu_state.rpy[1], 0]
        
        # Command (stationary)
        obs[3:6] = [0.0, 0.0, 0.0]
        
        # Joint positions and velocities
        joint_pos = np.array([state.motor_state[i].q for i in range(12)])
        joint_vel = np.array([state.motor_state[i].dq for i in range(12)])
        
        obs[12:24] = joint_pos - self.default_angles  # Relative to default
        obs[24:36] = joint_vel * 0.05  # Scale velocities
        
        # Run model inference
        obs_tensor = obs.reshape(1, -1)
        actions = self.session.run(None, {'observations': obs_tensor})[0][0]
        
        print(f"Model actions: {actions[:6]}")  # Show first 6 actions
        print(f"Action range: [{actions.min():.3f}, {actions.max():.3f}]")
        
        # Apply actions (small scale for safety)
        target_positions = self.default_angles + actions * 0.05  # Small scale
        
        print("Applying model actions (scaled down for safety)...")
        success = self.send_joint_commands(target_positions)
        
        if success:
            print("✓ Model inference test successful")
        else:
            print("✗ Failed to apply model actions")

def main():
    print("Go2 Working Test (Based on Discovered Configuration)")
    print("=" * 60)
    
    # Path to your trained model
    model_path = "logs/go2-walking/policy_100.onnx"
    
    try:
        controller = WorkingGo2Controller(model_path)
        
        print(f"\n=== System Status ===")
        print(f"Model loaded: {'✓' if controller.session else '✗'}")
        print(f"Robot connected: {'✓' if controller.robot_connected else '✗'}")
        
        if controller.robot_connected:
            input("\nPress Enter to test basic movement...")
            controller.test_basic_movement()
            
            if controller.session:
                input("\nPress Enter to test model inference...")
                controller.test_model_inference()
            
            print("\n✓ All tests completed!")
            print("If successful, your trained model is working on the real Go2!")
        else:
            print("\n✗ Could not connect to robot")
            print("Make sure go2_bridge service is running:")
            print("  sudo systemctl status go2_bridge")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")

if __name__ == "__main__":
    main()