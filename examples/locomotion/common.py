def import_onnx():
    try:
        import onnx
        import onnxruntime as ort
        print("✓ ONNX and ONNX Runtime are available")
        return True
    except ImportError:
        print("✗ ONNX or ONNX Runtime not available. Please install via 'pip install onnx onnxruntime'")
        return False
def import_unitree_sdk():
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
        return True
    except ImportError:
        print("✗ Unitree SDK not available. Please install the Unitree SDK for Python.")
        return False