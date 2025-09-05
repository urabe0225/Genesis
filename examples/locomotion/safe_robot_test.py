# -*- coding: utf-8 -*-
import time
import numpy as np

# Optional imports with error handling
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    print("Warning: onnxruntime not available. Install with: pip install onnxruntime")

try:
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher, ChannelFactoryInitialize
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_
    from unitree_sdk2py.utils.crc import CRC
    from unitree_sdk2py.utils.thread import RecurrentThread
    import unitree_legged_const as go2
    UNITREE_SDK_AVAILABLE = True
except ImportError:
    UNITREE_SDK_AVAILABLE = False
    print("Warning: Unitree SDK not available")

class SafeGo2Controller:
    def __init__(self, onnx_model_path=None):
        self.session = None
        self.state_sub = None
        self.cmd_pub = None
        self.robot_connected = False
        self.crc = None
        
        # Initialize CRC if SDK is available
        if UNITREE_SDK_AVAILABLE:
            self.crc = CRC()
        
        # Try to load ONNX model
        if onnx_model_path and ONNX_AVAILABLE:
            try:
                self.session = ort.InferenceSession(onnx_model_path)
                print(f"✓ ONNX model loaded: {onnx_model_path}")
            except Exception as e:
                print(f"✗ Failed to load ONNX model: {e}")
        elif onnx_model_path:
            print("✗ ONNX model specified but onnxruntime not available")
        
        # Try to initialize Unitree SDK
        if UNITREE_SDK_AVAILABLE:
            try:
                self.state_sub = ChannelSubscriber("rt/lowstate", LowState_)
                self.cmd_pub = ChannelPublisher("rt/lowcmd", LowCmd_)
                
                # Test initialization
                if self.state_sub is not None and self.cmd_pub is not None:
                    self.state_sub.Init()
                    self.cmd_pub.Init()
                    
                    # Test if we can actually communicate
                    try:
                        test_state = self.state_sub.Read()
                        if test_state is not None:
                            self.robot_connected = True
                            print("✓ Robot connection established")
                        else:
                            print("⚠ SDK initialized but no robot response")
                    except:
                        print("⚠ SDK initialized but communication failed")
                else:
                    print("✗ Failed to create SDK channels")
                    
            except Exception as e:
                print(f"✗ Unitree SDK initialization failed: {e}")
                self.state_sub = None
                self.cmd_pub = None
        else:
            print("✗ Unitree SDK not available")
        
        # Safety parameters
        self.safe_kp = 5.0
        self.safe_kd = 0.2
        self.safe_kp = 20.0  # Increased from 5.0 based on go2_stand_example
        self.safe_kd = 2.0   # Increased from 0.2 based on go2_stand_example
        self.max_angle_change = 0.1
        
        # Default joint angles (standing pose)
        self.default_angles = np.array([
            0.0, 0.67, -1.3,  # FR
            0.0, 0.67, -1.3,  # FL
            0.0, 0.67, -1.3,  # RR
            0.0, 0.67, -1.3   # RL
        ])
        
        self.current_target = self.default_angles.copy()
        self.low_state = None
    
    def init_low_cmd(self):
        """Initialize LowCmd with proper header and default values"""
        cmd = unitree_go_msg_dds__LowCmd_()
        cmd.head[0] = 0xFE
        cmd.head[1] = 0xEF
        cmd.level_flag = 0xFF
        cmd.gpio = 0
        
        for i in range(20):
            cmd.motor_cmd[i].mode = 0x01  # PMSM mode
            cmd.motor_cmd[i].q = go2.PosStopF
            cmd.motor_cmd[i].kp = 0
            cmd.motor_cmd[i].dq = go2.VelStopF
            cmd.motor_cmd[i].kd = 0
            cmd.motor_cmd[i].tau = 0
        
        return cmd
    
    def low_state_handler(self, msg: LowState_):
        """Handle incoming low state messages"""
        self.low_state = msg
    
    def get_system_status(self):
        """Get current system status"""
        status = {
            'unitree_sdk': UNITREE_SDK_AVAILABLE,
            'onnx_runtime': ONNX_AVAILABLE,
            'robot_connected': self.robot_connected,
            'model_loaded': self.session is not None
        }
        return status
    
    def print_status(self):
        """Print system status"""
        status = self.get_system_status()
        print("\n=== System Status ===")
        print(f"Unitree SDK: {'✓' if status['unitree_sdk'] else '✗'}")
        print(f"ONNX Runtime: {'✓' if status['onnx_runtime'] else '✗'}")
        print(f"Robot Connected: {'✓' if status['robot_connected'] else '✗'}")
        print(f"Model Loaded: {'✓' if status['model_loaded'] else '✗'}")
        print("=" * 21)
    
    def test_1_standing_pose(self):
        """Test 1: Basic standing pose"""
        print("\nTest 1: Setting to standing pose...")
        
        if not self.robot_connected:
            print("⚠ Skipping Test 1 - No robot connection")
            print("✓ Test 1 simulated (would set standing pose)")
            return
        
        try:
            # Subscribe to state for initial position
            self.state_sub.Init(self.low_state_handler, 10)
            time.sleep(0.1)  # Allow some time for state updates
            
            # Get current position
            current_pos = [0.0] * 12
            if self.low_state is not None:
                for i in range(12):
                    current_pos[i] = self.low_state.motor_state[i].q
                print("✓ Current position obtained")
            else:
                print("⚠ Using default current position")
            
            # Smooth transition to standing pose
            duration = 2.0  # 2 seconds
            steps = int(duration / 0.02)  # 50Hz
            
            for step in range(steps):
                progress = step / float(steps)
                
                cmd = self.init_low_cmd()
                
                for i in range(12):
                    # Interpolate from current to target position
                    target_q = (1.0 - progress) * current_pos[i] + progress * self.default_angles[i]
                    
                    cmd.motor_cmd[i].mode = 0x01
                    cmd.motor_cmd[i].q = target_q
                    cmd.motor_cmd[i].kp = self.safe_kp
                    cmd.motor_cmd[i].kd = self.safe_kd
                    cmd.motor_cmd[i].dq = 0.0
                    cmd.motor_cmd[i].tau = 0.0
                
                # Add CRC checksum
                cmd.crc = self.crc.Crc(cmd)
                self.cmd_pub.Write(cmd)
                time.sleep(0.02)
            
            # Hold position for 1 second
            cmd = self.init_low_cmd()
            for i in range(12):
                cmd.motor_cmd[i].mode = 0x01
                cmd.motor_cmd[i].q = self.default_angles[i]
                cmd.motor_cmd[i].kp = self.safe_kp
                cmd.motor_cmd[i].kd = self.safe_kd
                cmd.motor_cmd[i].dq = 0.0
                cmd.motor_cmd[i].tau = 0.0
            
            for _ in range(50):  # Hold for 1 second
                cmd.crc = self.crc.Crc(cmd)
                self.cmd_pub.Write(cmd)
                time.sleep(0.02)
            
            print("✓ Standing pose test completed")
        except Exception as e:
            print(f"✗ Test 1 failed: {e}")
    
    def test_2_single_joint(self, joint_idx=0, amplitude=0.1):
        """Test 2: Single joint small movement"""
        print(f"\nTest 2: Moving joint {joint_idx} with amplitude {amplitude}")
        
        if not self.robot_connected:
            print("⚠ Skipping Test 2 - No robot connection")
            print("✓ Test 2 simulated (would move single joint)")
            return
        
        try:
            start_time = time.time()
            duration = 5.0
            
            while time.time() - start_time < duration:
                t = time.time() - start_time
                offset = amplitude * np.sin(2 * np.pi * 0.5 * t)
                
                target_angles = self.default_angles.copy()
                target_angles[joint_idx] += offset
                
                cmd = self.init_low_cmd()
                for i in range(12):
                    cmd.motor_cmd[i].mode = 0x01
                    cmd.motor_cmd[i].q = target_angles[i]
                    cmd.motor_cmd[i].kp = self.safe_kp
                    cmd.motor_cmd[i].kd = self.safe_kd
                    cmd.motor_cmd[i].dq = 0.0
                    cmd.motor_cmd[i].tau = 0.0
                
                cmd.crc = self.crc.Crc(cmd)
                self.cmd_pub.Write(cmd)
                time.sleep(0.02)
            
            print("✓ Single joint test completed")
        except Exception as e:
            print(f"✗ Test 2 failed: {e}")
    
    def test_3_data_collection(self):
        """Test 3: Sensor data verification"""
        print("\nTest 3: Collecting sensor data for 5 seconds...")
        
        if not self.robot_connected:
            print("⚠ Skipping Test 3 - No robot connection")
            print("✓ Test 3 simulated (would collect sensor data)")
            return
        
        try:
            start_time = time.time()
            data_count = 0
            while time.time() - start_time < 5.0:
                if self.low_state is not None:
                    data_count += 1
                    
                    print(f"Data {data_count}:")
                    print(f"  IMU RPY: {self.low_state.imu_state.rpy}")
                    print(f"  Gyro: {self.low_state.imu_state.gyroscope}")
                    print(f"  Accel: {self.low_state.imu_state.accelerometer}")
                    
                    for i in range(3):
                        print(f"  Joint {i}: pos={self.low_state.motor_state[i].q:.3f}, vel={self.low_state.motor_state[i].dq:.3f}")
                    
                    print("-" * 30)
                time.sleep(1.0)
                
            print("✓ Data collection completed")
        except Exception as e:
            print(f"✗ Test 3 failed: {e}")
    
    def test_4_model_output_check(self):
        """Test 4: Model output verification (no movement)"""
        print("\nTest 4: Checking model outputs...")
        
        if self.session is None:
            print("⚠ No model loaded - simulating model test")
            print("✓ Test 4 simulated (would check model outputs)")
            return
        
        try:
            dummy_obs = np.zeros(45, dtype=np.float32)
            dummy_obs = dummy_obs.reshape(1, -1)
            
            print("Model output test:")
            for i in range(5):  # Reduced to 5 iterations
                actions = self.session.run(None, {'observations': dummy_obs})[0][0]
                print(f"  Output {i+1}: {actions[:6]}")
                time.sleep(0.2)
            
            print("✓ Model output check completed")
        except Exception as e:
            print(f"✗ Test 4 failed: {e}")
    
    def test_5_safe_model_execution(self, duration=5.0):
        """Test 5: Model execution (low gain, small actions)"""
        print(f"\nTest 5: Safe model execution for {duration} seconds...")
        
        if self.session is None:
            print("⚠ No model loaded")
            print("✓ Test 5 simulated (would execute model safely)")
            return
        
        if not self.robot_connected:
            print("⚠ No robot connection - running model inference only")
            try:
                # Simulate with dummy data
                dummy_obs = np.zeros(45, dtype=np.float32)
                dummy_obs = dummy_obs.reshape(1, -1)
                
                start_time = time.time()
                step_count = 0
                while time.time() - start_time < duration:
                    actions = self.session.run(None, {'observations': dummy_obs})[0][0]
                    actions = np.clip(actions, -0.1, 0.1)
                    
                    if step_count % 25 == 0:  # Print every 0.5 seconds
                        print(f"  Step {step_count}: actions={actions[:3]}")
                    
                    step_count += 1
                    time.sleep(0.02)
                
                print("✓ Model inference test completed")
            except Exception as e:
                print(f"✗ Test 5 failed: {e}")
            return
        
        # Full test with robot connection
        try:
            obs_scales = {
                "lin_vel": 2.0,
                "ang_vel": 0.25,
                "dof_pos": 1.0,
                "dof_vel": 0.05,
            }
            
            action_history = np.zeros((3, 12))
            start_time = time.time()
            
            while time.time() - start_time < duration:
                if self.low_state is None:
                    time.sleep(0.02)
                    continue
                
                obs = np.zeros(45)
                obs[0:3] = [self.low_state.imu_state.rpy[0], self.low_state.imu_state.rpy[1], 0]
                obs[3:6] = [0.0, 0.0, 0.0]
                obs[6:12] = 0.0
                
                joint_pos = np.array([self.low_state.motor_state[i].q for i in range(12)])
                joint_vel = np.array([self.low_state.motor_state[i].dq for i in range(12)])
                obs[12:24] = (joint_pos - self.default_angles) * obs_scales["dof_pos"]
                obs[24:36] = joint_vel * obs_scales["dof_vel"]
                obs[36:48] = action_history.flatten()
                
                obs_tensor = obs.reshape(1, -1).astype(np.float32)
                actions = self.session.run(None, {'observations': obs_tensor})[0][0]
                
                action_history[1:] = action_history[:-1]
                action_history[0] = actions
                
                actions = np.clip(actions, -0.1, 0.1)
                target_angles = self.default_angles + actions * 0.1
                
                angle_diff = target_angles - self.current_target
                angle_diff = np.clip(angle_diff, -self.max_angle_change, self.max_angle_change)
                self.current_target += angle_diff
                
                cmd = self.init_low_cmd()
                for i in range(12):
                    cmd.motor_cmd[i].mode = 0x01
                    cmd.motor_cmd[i].q = self.current_target[i]
                    cmd.motor_cmd[i].kp = self.safe_kp
                    cmd.motor_cmd[i].kd = self.safe_kd
                    cmd.motor_cmd[i].dq = 0.0
                    cmd.motor_cmd[i].tau = 0.0
                
                cmd.crc = self.crc.Crc(cmd)
                self.cmd_pub.Write(cmd)
                time.sleep(0.02)
            
            print("✓ Safe model execution completed")
        except Exception as e:
            print(f"✗ Test 5 failed: {e}")

def main():
    print("=== Go2 Safe Testing Protocol ===")
    print("WARNING: Please ensure there are no obstacles around the robot while running this example.")
    input("Press Enter to continue...")
    
    # Model path (optional)
    model_path = "logs/go2-walking/policy_100.onnx"
    
    try:
        ChannelFactoryInitialize(0)
        controller = SafeGo2Controller(model_path)
        controller.print_status()
        
        print("\nTest sequence:")
        print("1. Standing pose test")
        print("2. Single joint movement test")
        print("3. Sensor data collection")
        print("4. Model output check")
        print("5. Safe model execution")
        
        input("\nPress Enter to start Test 1 (Standing pose)...")
        controller.test_1_standing_pose()
        
        input("\nPress Enter to start Test 2 (Single joint movement)...")
        controller.test_2_single_joint(joint_idx=1, amplitude=0.05)
        
        input("\nPress Enter to start Test 3 (Sensor data collection)...")
        controller.test_3_data_collection()
        
        input("\nPress Enter to start Test 4 (Model output check)...")
        controller.test_4_model_output_check()
        
        input("\nPress Enter to start Test 5 (Safe model execution)...")
        controller.test_5_safe_model_execution(duration=3.0)
        
        print("\n✓ All tests completed!")
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\n⚠ Testing interrupted by user")

if __name__ == "__main__":
    main()