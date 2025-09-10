import time
import sys

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.utils.thread import RecurrentThread
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient

class SafeGo2Controller:
    def __init__(self):
        self.Kp = 60.0
        self.Kd = 5.0
        self.crc = CRC()
        
        self.low_cmd = unitree_go_msg_dds__LowCmd_()
        self.low_state = None  

        self.startPos = [0.0] * 12
        self.standing_pose = [0.0, 1.36, -2.65, 0.0, 1.36, -2.65,
                             -0.2, 1.36, -2.65, 0.2, 1.36, -2.65]
        self.stand_pose = [0.0, 0.67, -1.3] * 4  # 4脚 × 3関節
        self.rest_pose = [-0.35, 1.36, -2.65, 0.35, 1.36, -2.65,
                             -0.5, 1.36, -2.65, 0.5, 1.36, -2.65]

        self.durations = [500, 500, 1000, 900]  # ms
        self.percents = [0.0, 0.0, 0.0]#[1.0, 0.0, 1.0, 0.0]
        self.process = 0.0
        self.low_level = False
        # thread handling
        self.lowCmdWriteThreadPtr = None

    def Init(self):
        def init_command():
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

        def get_position():
            for i in range(12):
                self.startPos[i] = self.low_state.motor_state[i].q

        def mode_release():
            max_attempts = 5
            attempt = 0
            msc = MotionSwitcherClient()
            sc = SportClient()  
            while attempt < max_attempts:
                status, result = msc.CheckMode()

                if not result or not result.get('name'):
                    print("✓ All modes released successfully")
                    return True
                    
                mode_name = result['name']
                print(f"Releasing mode: {mode_name} (attempt {attempt + 1})")
                
                sc.StandDown()
                msc.ReleaseMode()
                time.sleep(1)
                attempt += 1
            
            print("⚠ Warning: Could not release all modes")
            return False

        self.low_cmd = init_command()

        # create publisher
        self.lowcmd_publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.lowcmd_publisher.Init()

        # create subscriber
        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self.lowstate_subscriber.Init(self.LowStateMessageHandler, 10)

        mode_release()
        get_position()

    def Start(self):
        self.lowCmdWriteThreadPtr = RecurrentThread(
            interval=0.002, target=self.LowCmdWrite, name="writebasiccmd"
        )
        self.lowCmdWriteThreadPtr.Start()
        while True:        
            if self.percents[2] == 1.0: 
                time.sleep(1)
                print("Done!")
                sys.exit(-1)     
            time.sleep(1)
        """"""
        self.percents = [0.0, 0.0, 0.0]
        self.lowCmdWriteThreadPtr = RecurrentThread(
            interval=0.002, target=self.LowCmdWrite, name="writebasiccmd"
        )
        self.lowCmdWriteThreadPtr.Start()
        while True:        
            if self.percents[2] == 1.0: 
                time.sleep(1)
                print("Done!")
                sys.exit(-1)     
            time.sleep(1)
        """"""

    def LowStateMessageHandler(self, msg: LowState_):
        self.low_state = msg
        # print("FR_0 motor state: ", msg.motor_state[go2.LegID["FR_0"]])
        # print("IMU state: ", msg.imu_state)
        # print("Battery state: voltage: ", msg.power_v, "current: ", msg.power_a)

    def input_low_cmd(self, motor_id, q, dq, tau):
        self.low_cmd.motor_cmd[motor_id].q = q
        self.low_cmd.motor_cmd[motor_id].dq = dq
        self.low_cmd.motor_cmd[motor_id].kp = self.Kp
        self.low_cmd.motor_cmd[motor_id].kd = self.Kd
        self.low_cmd.motor_cmd[motor_id].tau = tau

    def clock(self,i):
        self.percents[i] += 1.0 / self.durations[i]
        self.percents[i] = min(self.percents[i], 1)

    def LowCmdWrite(self):
        self.clock(0)
        if self.percents[0] < 1:
            for i in range(12):
                self.input_low_cmd(i,
                                   (1 - self.percents[0]) * self.startPos[i] + self.percents[0] * self.standing_pose[i],
                                   0,
                                   0)
        
        if (self.percents[0] == 1) and (self.percents[1] <= 1):
            self.clock(1)
            for i in range(12):
                self.input_low_cmd(i,
                                   (1 - self.percents[1]) * self.standing_pose[i] + self.percents[1] * self.stand_pose[i],
                                   0,
                                   0)
        """
        if (self.percents[0] == 1) and (self.percents[1] == 1) and (self.percents[2] < 1):
            self.clock(2)
            for i in range(12):
                self.input_low_cmd(i,
                                   self.stand_pose[i],
                                   0,
                                   0)
        """
        if (self.percents[0] == 1) and (self.percents[1] == 1) and (self.percents[2] <= 1):
            self.clock(2)
            for i in range(12):
                self.input_low_cmd(i,
                                   (1 - self.percents[2]) * self.stand_pose[i] + self.percents[2] * self.rest_pose[i],
                                   0,
                                   0)

        self.low_cmd.crc = self.crc.Crc(self.low_cmd)
        self.lowcmd_publisher.Write(self.low_cmd)

def main():
    print("=== Go2 Safe Testing Protocol ===")
    print("WARNING: Please ensure there are no obstacles around the robot while running this example.")
    input("Press Enter to continue...")

    # Model path (optional)
    model_path = "logs/go2-walking/policy_100.onnx"

    try:
        if len(sys.argv)>1:
            ChannelFactoryInitialize(0, sys.argv[1])
        else:
            ChannelFactoryInitialize(0)
        controller = SafeGo2Controller()
        input("\nPress Enter to start Test 1 (Standing pose)...")
        controller.Init()
        controller.Start()

    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\n⚠ Testing interrupted by user")

if __name__ == '__main__':
    main()

    

