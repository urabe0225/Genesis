#!/usr/bin/env python3
import subprocess
import time
import sys

def start_service(service_name):
    """Start a systemd service"""
    try:
        print(f"Starting {service_name}...")
        result = subprocess.run(
            ['sudo', 'systemctl', 'start', service_name],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"✓ {service_name} started")
            return True
        else:
            print(f"✗ Failed to start {service_name}: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Error starting {service_name}: {e}")
        return False

def check_service_status(service_name):
    """Check if service is active"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True, text=True
        )
        return result.stdout.strip() == 'active'
    except:
        return False

def main():
    print("=== Starting Go2 Robot Services ===")
    
    # List of services to start in order
    services = [
        'unitree-robot-sdk',
        'unitree-robot', 
        'robot-state',
        'robot-control'
    ]
    
    # Start services
    success_count = 0
    for service in services:
        if start_service(service):
            success_count += 1
            time.sleep(2)  # Wait between services
    
    print(f"\n{success_count}/{len(services)} services started successfully")
    
    # Final status check
    print("\n=== Final Service Status ===")
    for service in services:
        status = "✓ Active" if check_service_status(service) else "✗ Inactive"
        print(f"{service}: {status}")
    
    if success_count == len(services):
        print("\n✓ All services started! Ready to test robot connection.")
        print("Run: python3 examples/locomotion/safe_robot_test.py")
    else:
        print("\n⚠ Some services failed to start. Check system logs:")
        print("sudo journalctl -u unitree-robot-sdk -f")

if __name__ == "__main__":
    main()