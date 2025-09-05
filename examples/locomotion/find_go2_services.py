#!/usr/bin/env python3
import subprocess
import os
import sys

def find_all_services():
    """Find all systemd services"""
    print("=== All Systemd Services ===")
    try:
        result = subprocess.run(['systemctl', 'list-units', '--type=service'], 
                              capture_output=True, text=True)
        
        # Filter for relevant services
        relevant_services = []
        for line in result.stdout.split('\n'):
            if any(keyword in line.lower() for keyword in 
                   ['unitree', 'go2', 'robot', 'sport', 'legged']):
                relevant_services.append(line.strip())
        
        if relevant_services:
            print("Found relevant services:")
            for service in relevant_services:
                print(f"  {service}")
        else:
            print("No relevant services found")
            
        return relevant_services
            
    except Exception as e:
        print(f"Error: {e}")
        return []

def find_all_service_files():
    """Find service definition files"""
    print("\n=== Service Files ===")
    
    service_dirs = [
        '/etc/systemd/system/',
        '/lib/systemd/system/',
        '/usr/lib/systemd/system/'
    ]
    
    relevant_files = []
    for service_dir in service_dirs:
        if os.path.exists(service_dir):
            try:
                files = os.listdir(service_dir)
                for file in files:
                    if any(keyword in file.lower() for keyword in 
                           ['unitree', 'go2', 'robot', 'sport', 'legged']) and file.endswith('.service'):
                        full_path = os.path.join(service_dir, file)
                        relevant_files.append(full_path)
                        print(f"  {full_path}")
            except PermissionError:
                print(f"  Permission denied: {service_dir}")
    
    return relevant_files

def find_running_processes():
    """Find currently running robot-related processes"""
    print("\n=== Running Robot Processes ===")
    
    keywords = ['unitree', 'go2', 'robot', 'sport', 'legged', 'sdk']
    
    for keyword in keywords:
        try:
            result = subprocess.run(['pgrep', '-af', keyword], 
                                  capture_output=True, text=True)
            if result.stdout:
                print(f"\nProcesses with '{keyword}':")
                for line in result.stdout.strip().split('\n'):
                    if line:
                        print(f"  {line}")
        except Exception as e:
            print(f"Error checking {keyword}: {e}")

def find_unitree_directories():
    """Find Unitree-related directories"""
    print("\n=== Unitree Directories ===")
    
    search_paths = [
        '/opt/',
        '/usr/local/',
        '/home/unitree/',
        '/etc/',
        '/var/lib/'
    ]
    
    for search_path in search_paths:
        try:
            if os.path.exists(search_path):
                for item in os.listdir(search_path):
                    if any(keyword in item.lower() for keyword in 
                           ['unitree', 'go2', 'robot', 'sport', 'legged']):
                        full_path = os.path.join(search_path, item)
                        if os.path.isdir(full_path):
                            print(f"  Directory: {full_path}")
                        else:
                            print(f"  File: {full_path}")
        except PermissionError:
            pass
        except Exception as e:
            print(f"Error searching {search_path}: {e}")

def check_go2_specific_paths():
    """Check Go2 specific paths and executables"""
    print("\n=== Go2 Specific Check ===")
    
    # Common Go2 paths
    go2_paths = [
        '/opt/go2/',
        '/home/unitree/go2/',
        '/usr/local/go2/',
        '/home/unitree/Unitree/',
        '/home/unitree/unitree_sdk/',
        '/home/unitree/go2_description/'
    ]
    
    for path in go2_paths:
        if os.path.exists(path):
            print(f"✓ Found: {path}")
            try:
                items = os.listdir(path)
                for item in items[:5]:  # Show first 5 items
                    print(f"    {item}")
                if len(items) > 5:
                    print(f"    ... and {len(items)-5} more items")
            except PermissionError:
                print(f"    (Permission denied)")
        else:
            print(f"✗ Not found: {path}")
    
    # Check for executables
    print("\nChecking for executables:")
    executables = [
        'go2_driver',
        'unitree_legged_sdk',
        'robot_state_publisher',
        'sport_mode'
    ]
    
    for exe in executables:
        try:
            result = subprocess.run(['which', exe], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ {exe}: {result.stdout.strip()}")
            else:
                print(f"✗ {exe}: Not found in PATH")
        except:
            print(f"? {exe}: Could not check")

def check_network_interfaces():
    """Check for robot-specific network interfaces"""
    print("\n=== Network Interfaces ===")
    
    try:
        result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        for line in lines:
            if any(keyword in line.lower() for keyword in 
                   ['eth', 'wlan', 'usb', 'can']):
                print(f"  {line.strip()}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    print("Go2 Robot Environment Investigation")
    print("=" * 50)
    
    services = find_all_services()
    service_files = find_all_service_files()
    find_running_processes()
    find_unitree_directories()
    check_go2_specific_paths()
    check_network_interfaces()
    
    print("\n" + "=" * 50)
    print("Investigation completed.")
    
    # Provide recommendations based on findings
    print("\n=== Recommendations ===")
    
    if service_files:
        print("✓ Found service files. Try starting these services:")
        for file in service_files:
            service_name = os.path.basename(file).replace('.service', '')
            print(f"  sudo systemctl start {service_name}")
    else:
        print("⚠ No systemd services found.")
    
    print("\n✓ Next steps:")
    print("1. Check running processes for active robot software")
    print("2. Look for startup scripts in /home/unitree/")
    print("3. Check Go2 documentation for correct startup procedure")
    print("4. Try direct SDK connection without services")

if __name__ == "__main__":
    main()