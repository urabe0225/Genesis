#!/usr/bin/env python3
import os
import subprocess
import sys
import time

def check_environment():
    """Check current environment"""
    print("=== Environment Check ===")
    print(f"Current user: {os.getenv('USER')}")
    print(f"Current UID: {os.getuid()}")
    print(f"Python path: {sys.executable}")
    print(f"Working directory: {os.getcwd()}")
    
    # Check groups
    try:
        result = subprocess.run(['groups'], capture_output=True, text=True)
        print(f"User groups: {result.stdout.strip()}")
    except:
        print("Could not check user groups")

def check_python_packages():
    """Check if required packages are available"""
    print("\n=== Python Packages ===")
    
    packages = ['onnxruntime', 'unitree_sdk2py', 'numpy']
    for package in packages:
        try:
            __import__(package)
            print(f"✓ {package}: Available")
        except ImportError as e:
            print(f"✗ {package}: Not available ({e})")

def check_system_services():
    """Check system services"""
    print("\n=== System Services ===")
    
    services = [
        'unitree-robot-sdk',
        'unitree-robot',
        'robot-state',
        'robot-control',
        'dds'
    ]
    
    for service in services:
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service], 
                capture_output=True, text=True
            )
            status = result.stdout.strip()
            symbol = "✓" if status == "active" else "⚠"
            print(f"{symbol} {service}: {status}")
        except Exception as e:
            print(f"? {service}: Could not check ({e})")

def check_network():
    """Check network configuration"""
    print("\n=== Network Configuration ===")
    
    try:
        result = subprocess.run(['ip', 'addr'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        for line in lines:
            if 'inet ' in line and ('192.168' in line or '10.' in line):
                print(f"Network: {line.strip()}")
    except:
        print("Could not check network")

def check_devices():
    """Check device files"""
    print("\n=== Device Files ===")
    
    device_patterns = [
        '/dev/tty*',
        '/dev/unitree*',
        '/dev/robot*'
    ]
    
    for pattern in device_patterns:
        try:
            result = subprocess.run(
                f'ls {pattern} 2>/dev/null', 
                shell=True, capture_output=True, text=True
            )
            if result.stdout:
                print(f"Devices {pattern}:")
                for line in result.stdout.strip().split('\n'):
                    if line:
                        print(f"  {line}")
            else:
                print(f"No devices matching {pattern}")
        except:
            print(f"Could not check {pattern}")

def check_processes():
    """Check running processes"""
    print("\n=== Running Processes ===")
    
    process_keywords = ['unitree', 'robot', 'dds']
    
    for keyword in process_keywords:
        try:
            result = subprocess.run(
                ['pgrep', '-f', keyword], 
                capture_output=True, text=True
            )
            if result.stdout:
                pids = result.stdout.strip().split('\n')
                print(f"Processes with '{keyword}': {len(pids)} found")
                
                # Get process details
                for pid in pids[:3]:  # Show first 3
                    try:
                        cmd_result = subprocess.run(
                            ['ps', '-p', pid, '-o', 'comm='], 
                            capture_output=True, text=True
                        )
                        if cmd_result.stdout:
                            print(f"  PID {pid}: {cmd_result.stdout.strip()}")
                    except:
                        pass
            else:
                print(f"No processes with '{keyword}'")
        except:
            print(f"Could not check processes for '{keyword}'")

def main():
    print("Go2 Robot Diagnosis Tool")
    print("=" * 40)
    
    check_environment()
    check_python_packages()
    check_system_services()
    check_network()
    check_devices()
    check_processes()
    
    print("\n" + "=" * 40)
    print("Diagnosis completed.")
    
    # Recommendations
    print("\nRecommendations:")
    print("1. If packages are missing: Install in current environment")
    print("2. If services are inactive: sudo systemctl start <service>")
    print("3. If no devices found: Check hardware connections")
    print("4. If processes are missing: Restart robot services")

if __name__ == "__main__":
    main()