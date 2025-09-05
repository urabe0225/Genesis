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
        if onnx_model_path:
            self.session = ort.InferenceSession(onnx_model_path)
        else:
            self.session = None
        
        # Unitree SDK initialization
        self.state_sub = ChannelSubscriber("rt/lowstate", LowState_)
        self.cmd_pub = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.state_sub.Init()
        self.cmd_pub.Init()
        
        # Safety parameters
        self.safe_kp = 5.0   # Low gain
        self.safe_kd = 0.2   # Low gain
        self.max_angle_change = 0.1  # Max angle change (rad)
        
        # Default joint angles (standing pose)
        self.default_angles = np.array([
            0.0, 0.8, -1.5,  # FR
            0.0, 0.8, -1.5,  # FL
            0.0, 1.0, -1.5,  # RR
            0.0, 1.0, -1.5   # RL
        ])
        
        self.current_target = self.default_angles.copy()
        
    def test_1_standing_pose(self):
        """Test 1: Basic standing pose"""
        print("Test 1: Setting to standing pose...")
        
        cmd = LowCmd_()
        for i in range(12):
            cmd.motor_cmd[i].mode = 1
            cmd.motor_cmd[i].q = self.default_angles[i]
            cmd.motor_cmd[i].kp = self.safe_kp
            cmd.motor_cmd[i].kd = self.safe_kd
            cmd.motor_cmd[i].dq = 0.0
            cmd.motor_cmd[i].tau = 0.0
        
        # Hold for 3 seconds
        for _ in range(150):  # 50Hz * 3sec
            self.cmd_pub.Write(cmd)
            time.sleep(0.02)
        
        print("Standing pose test completed.")
    
    def test_2_single_joint(self, joint_idx=0, amplitude=0.1):
        """Test 2: Single joint small movement"""
        print(f"Test 2: Moving joint {joint_idx} with amplitude {amplitude}")
        
        start_time = time.time()
        duration = 5.0  # 5 seconds
        
        while time.time() - start_time < duration:
            # Move joint with sine wave
            t = time.time() - start_time
            offset = amplitude * np.sin(2 * np.pi * 0.5 * t)  # 0.5Hz
            
            target_angles = self.default_angles.copy()
            target_angles[joint_idx] += offset
            
            cmd = LowCmd_()
            for i in range(12):
                cmd.motor_cmd[i].mode = 1
                cmd.motor_cmd[i].q = target_angles[i]
                cmd.motor_cmd[i].kp = self.safe_kp
                cmd.motor_cmd[i].kd = self.safe_kd
                cmd.motor_cmd[i].dq = 0.0
                cmd.motor_cmd[i].tau = 0.0
            
            self.cmd_pub.Write(cmd)
            time.sleep(0.02)
        
        print(f"Single joint test completed.")
    
    def test_3_data_collection(self):
        """Test 3: Sensor data verification"""
        print("Test 3: Collecting sensor data for 5 seconds...")
        
        start_time = time.time()
        while time.time() - start_time < 5.0:
            state = self.state_sub.Read()
            
            # IMU data
            print(f"IMU RPY: {state.imu_state.rpy}")
            print(f"Gyro: {state.imu_state.gyroscope}")
            print(f"Accel: {state.imu_state.accelerometer}")
            
            # Joint data (first 3 joints only)
            for i in range(3):
                print(f"Joint {i}: pos={state.motor_state[i].q:.3f}, vel={state.motor_state[i].dq:.3f}")
            
            print("-" * 50)
            time.sleep(1.0)
    
    def test_4_model_output_check(self):
        """Test 4: Model output verification (no movement)"""
        if self.session is None:
            print("No model loaded. Skipping model test.")
            return
        
        print("Test 4: Checking model outputs...")
        
        # Test model with dummy observations
        dummy_obs = np.zeros(45, dtype=np.float32)
        dummy_obs = dummy_obs.reshape(1, -1)
        
        for i in range(10):
            actions = self.session.run(None, {'observations': dummy_obs})[0][0]
            print(f"Model output {i}: {actions[:6]}")  # Display first 6 actions
            time.sleep(0.5)
    
    def test_5_safe_model_execution(self, duration=10.0):
        """Test 5: Model execution (low gain, small actions)"""
        if self.session is None:
            print("No model loaded. Cannot run model test.")
            return
        
        print(f"Test 5: Safe model execution for {duration} seconds...")
        
        # Observation normalization scales
        obs_scales = {
            "lin_vel": 2.0,
            "ang_vel": 0.25,
            "dof_pos": 1.0,
            "dof_vel": 0.05,
        }
        
        action_history = np.zeros((3, 12))
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Get state
            state = self.state_sub.Read()
            
            # Build observations (simplified version)
            obs = np.zeros(45)
            
            # IMU (gravity vector)
            obs[0:3] = [state.imu_state.rpy[0], state.imu_state.rpy[1], 0]
            
            # Commands (stop)
            obs[3:6] = [0.0, 0.0, 0.0]
            
            # Velocity (simplified)
            obs[6:12] = 0.0
            
            # Joint positions and velocities
            joint_pos = np.array([state.motor_state[i].q for i in range(12)])
            joint_vel = np.array([state.motor_state[i].dq for i in range(12)])
            obs[12:24] = (joint_pos - self.default_angles) * obs_scales["dof_pos"]
            obs[24:36] = joint_vel * obs_scales["dof_vel"]
            
            # Action history
            obs[36:48] = action_history.flatten()
            
            # Run model
            obs_tensor = obs.reshape(1, -1).astype(np.float32)
            actions = self.session.run(None, {'observations': obs_tensor})[0][0]
            
            # Update action history
            action_history[1:] = action_history[:-1]
            action_history[0] = actions
            
            # Limit actions for safety
            actions = np.clip(actions, -0.1, 0.1)  # Small action range
            
            # Calculate target angles
            target_angles = self.default_angles + actions * 0.1  # Small scale
            
            # Limit sudden changes
            angle_diff = target_angles - self.current_target
            angle_diff = np.clip(angle_diff, -self.max_angle_change, self.max_angle_change)
            self.current_target += angle_diff
            
            # Send command
            cmd = LowCmd_()
            for i in range(12):
                cmd.motor_cmd[i].mode = 1
                cmd.motor_cmd[i].q = self.current_target[i]
                cmd.motor_cmd[i].kp = self.safe_kp
                cmd.motor_cmd[i].kd = self.safe_kd
                cmd.motor_cmd[i].dq = 0.0
                cmd.motor_cmd[i].tau = 0.0
            
            self.cmd_pub.Write(cmd)
            time.sleep(0.02)
        
        print("Safe model execution completed.")

def main():
    print("=== Go2 Safe Testing Protocol ===")
    print("1. Standing pose test")
    print("2. Single joint movement test")
    print("3. Sensor data collection")
    print("4. Model output check")
    print("5. Safe model execution")
    
    # Model path (optional)
    model_path = "logs/go2-walking/policy_100.onnx"
    
    try:
        controller = SafeGo2Controller(model_path)
        
        input("Press Enter to start Test 1 (Standing pose)...")
        controller.test_1_standing_pose()
        
        input("Press Enter to start Test 2 (Single joint movement)...")
        controller.test_2_single_joint(joint_idx=1, amplitude=0.05)  # Small movement
        
        input("Press Enter to start Test 3 (Sensor data collection)...")
        controller.test_3_data_collection()
        
        input("Press Enter to start Test 4 (Model output check)...")
        controller.test_4_model_output_check()
        
        input("Press Enter to start Test 5 (Safe model execution)...")
        controller.test_5_safe_model_execution(duration=5.0)
        
        print("All tests completed!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    except KeyboardInterrupt:
        print("\nTesting interrupted by user.")

if __name__ == "__main__":
    main()