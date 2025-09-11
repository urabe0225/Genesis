import time
import sys
try:
    import onnx
    import onnxruntime as ort
    print("✓ ONNX and ONNX Runtime are available")
    ONNX_AVAILABLE = True
except ImportError:
    print("✗ ONNX or ONNX Runtime not available. Please install via 'pip install onnx onnxruntime'")
    ONNX_AVAILABLE = False
try:
    from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelPublisher, ChannelFactoryInitialize
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
    from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, LowCmd_
    from unitree_sdk2py.utils.crc import CRC
    from unitree_sdk2py.utils.thread import RecurrentThread
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
    from unitree_sdk2py.go2.sport.sport_client import SportClient
    print("✓ Unitree SDK is available")
    UNITREE_SDK_AVAILABLE = True
except ImportError:
    print("✗ Unitree SDK not available. Please install the Unitree SDK for Python.")
    UNITREE_SDK_AVAILABLE = False

class Go2Controller:
    def __init__(self, onnx_model_path=None):
        if UNITREE_SDK_AVAILABLE:
            self.crc = CRC()
        else:
            self.crc = None

        if onnx_model_path and ONNX_AVAILABLE:
            try:
                self.session = ort.InferenceSession(onnx_model_path)
                print(f"✓ ONNX model loaded: {onnx_model_path}")
            except Exception as e:
                print(f"Error loading ONNX model: {e}")
        elif onnx_model_path:
            print("✗ ONNX model specified but onnxruntime not available")

        self.Kp = 60.0
        self.Kd = 5.0

        self.low_cmd = unitree_go_msg_dds__LowCmd_()  
        self.low_state = None  

        self.startPos = [0.0] * 12
        self.standing_pose = [0.0, 1.36, -2.65, 0.0, 1.36, -2.65,
                             -0.2, 1.36, -2.65, 0.2, 1.36, -2.65]
        self.stand_pose = [0.0, 0.67, -1.3, 0.0, 0.67, -1.3,
                             0.0, 0.67, -1.3, 0.0, 0.67, -1.3]
        self.rest_pose = [-0.35, 1.36, -2.65, 0.35, 1.36, -2.65,
                             -0.5, 1.36, -2.65, 0.5, 1.36, -2.65]

        self.duration_1 = 500
        self.duration_2 = 500
        self.duration_3 = 1000
        self.duration_4 = 900
        self.percent_1 = 0
        self.percent_2 = 0
        self.percent_3 = 0
        self.percent_4 = 0

        self.firstRun = True

        # thread handling
        self.lowCmdWriteThreadPtr = None

    # Public methods
    def Init(self):
        def init_low_cmd():
            cmd = unitree_go_msg_dds__LowCmd_()
            cmd.head[0]=0xFE
            cmd.head[1]=0xEF
            cmd.level_flag = 0xFF
            cmd.gpio = 0
            for i in range(20):
                cmd.motor_cmd[i].mode = 0x01  # PMSM mode
                cmd.motor_cmd[i].q= 2.146e9
                cmd.motor_cmd[i].kp = 0
                cmd.motor_cmd[i].dq = 16000.0
                cmd.motor_cmd[i].kd = 0
                cmd.motor_cmd[i].tau = 0
            return cmd
        self.low_cmd = init_low_cmd()

        # create publisher #
        self.lowcmd_publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.lowcmd_publisher.Init()

        # create subscriber # 
        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self.lowstate_subscriber.Init(self.LowStateMessageHandler, 10)

        self.sc = SportClient()  
        self.sc.SetTimeout(5.0)
        self.sc.Init()

        self.msc = MotionSwitcherClient()
        self.msc.SetTimeout(5.0)
        self.msc.Init()

        status, result = self.msc.CheckMode()
        while result['name']:
            self.sc.StandDown()
            self.msc.ReleaseMode()
            status, result = self.msc.CheckMode()
            time.sleep(1)

    def Start(self):
        self.lowCmdWriteThreadPtr = RecurrentThread(
            interval=0.002, target=self.LowCmdWrite, name="writebasiccmd"
        )
        self.lowCmdWriteThreadPtr.Start()

    # Private methods


    def LowStateMessageHandler(self, msg: LowState_):
        self.low_state = msg
        # print("FR_0 motor state: ", msg.motor_state[go2.LegID["FR_0"]])
        # print("IMU state: ", msg.imu_state)
        # print("Battery state: voltage: ", msg.power_v, "current: ", msg.power_a)

    def LowCmdWrite(self):

        if self.firstRun:
            for i in range(12):
                self.startPos[i] = self.low_state.motor_state[i].q
            self.firstRun = False

        self.percent_1 += 1.0 / self.duration_1
        self.percent_1 = min(self.percent_1, 1)
        if self.percent_1 < 1:
            for i in range(12):
                self.low_cmd.motor_cmd[i].q = (1 - self.percent_1) * self.startPos[i] + self.percent_1 * self.standing_pose[i]
                self.low_cmd.motor_cmd[i].dq = 0
                self.low_cmd.motor_cmd[i].kp = self.Kp
                self.low_cmd.motor_cmd[i].kd = self.Kd
                self.low_cmd.motor_cmd[i].tau = 0

        if (self.percent_1 == 1) and (self.percent_2 <= 1):
            self.percent_2 += 1.0 / self.duration_2
            self.percent_2 = min(self.percent_2, 1)
            for i in range(12):
                self.low_cmd.motor_cmd[i].q = (1 - self.percent_2) * self.standing_pose[i] + self.percent_2 * self.stand_pose[i]
                self.low_cmd.motor_cmd[i].dq = 0
                self.low_cmd.motor_cmd[i].kp = self.Kp
                self.low_cmd.motor_cmd[i].kd = self.Kd
                self.low_cmd.motor_cmd[i].tau = 0

        if (self.percent_1 == 1) and (self.percent_2 == 1) and (self.percent_3 < 1):
            self.percent_3 += 1.0 / self.duration_3
            self.percent_3 = min(self.percent_3, 1)
            for i in range(12):
                self.low_cmd.motor_cmd[i].q = self.stand_pose[i] 
                self.low_cmd.motor_cmd[i].dq = 0
                self.low_cmd.motor_cmd[i].kp = self.Kp
                self.low_cmd.motor_cmd[i].kd = self.Kd
                self.low_cmd.motor_cmd[i].tau = 0

        if (self.percent_1 == 1) and (self.percent_2 == 1) and (self.percent_3 == 1) and (self.percent_4 <= 1):
            self.percent_4 += 1.0 / self.duration_4
            self.percent_4 = min(self.percent_4, 1)
            for i in range(12):
                self.low_cmd.motor_cmd[i].q = (1 - self.percent_4) * self.stand_pose[i] + self.percent_4 * self.rest_pose[i]
                self.low_cmd.motor_cmd[i].dq = 0
                self.low_cmd.motor_cmd[i].kp = self.Kp
                self.low_cmd.motor_cmd[i].kd = self.Kd
                self.low_cmd.motor_cmd[i].tau = 0

        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.lowcmd_publisher.Write(self.low_cmd)

def main():
    print("=== Go2 Safe Testing Protocol ===")
    print("WARNING: Please ensure there are no obstacles around the robot while running this example.")

    # Model path (optional)
    model_path = "logs/go2-walking/policy_100.onnx"

    try:
        if len(sys.argv)>1:
            ChannelFactoryInitialize(0, sys.argv[1])
        else:
            ChannelFactoryInitialize(0)
        go2 = Go2Controller()
        input("\nPress Enter to start Test 1 (Standing pose)...")
        #go2.test_1_standing_pose()
        go2.Init()
        go2.Start()
        while True:        
            if go2.percent_4 == 1.0: 
                time.sleep(1)
                print("Done!")
                sys.exit(-1)     
            time.sleep(1)
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\n⚠ Testing interrupted by user")



if __name__ == '__main__':
    main()