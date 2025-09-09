import time
import sys
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_
from unitree_sdk2py.utils.crc import CRC

class SimpleGo2Controller:
    def __init__(self):
        self.low_cmd = None
        self.cmd_pub = None
        self.crc = CRC()
        
        # 立ち姿勢の角度（12関節）
        self.standing_pose = [0.0, 0.67, -1.3] * 4  # 4脚 × 3関節
    
    def init_command(self):
        """基本的なコマンド初期化"""
        cmd = LowCmd_()
        cmd.head[0] = 0xFE
        cmd.head[1] = 0xEF
        cmd.level_flag = 0xFF
        
        for i in range(12):
            cmd.motor_cmd[i].mode = 0x01  # PMSM mode
            cmd.motor_cmd[i].q = self.standing_pose[i]
            cmd.motor_cmd[i].kp = 20.0    # 低ゲイン
            cmd.motor_cmd[i].kd = 2.0
            cmd.motor_cmd[i].dq = 0.0
            cmd.motor_cmd[i].tau = 0.0
        
        return cmd
    
    def run(self):
        """5秒間立ち姿勢を維持"""
        self.cmd_pub = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.cmd_pub.Init()
        
        cmd = self.init_command()
        
        print("Standing for 5 seconds...")
        for _ in range(250):  # 5秒 × 50Hz
            cmd.crc = self.crc.Crc(cmd)
            self.cmd_pub.Write(cmd)
            time.sleep(0.02)
        
        print("Done!")

def main():
    print("Simple Stand Test")
    input("Press Enter to start...")
    
    if len(sys.argv) > 1:
        ChannelFactoryInitialize(0, sys.argv[1])
    else:
        ChannelFactoryInitialize(0)
    
    controller = SimpleGo2Controller()
    controller.run()

if __name__ == '__main__':
    main()