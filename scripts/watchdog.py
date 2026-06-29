import subprocess
import time
import sys
import os

def run_watchdog():
    print("Starting ForeksTrader Watchdog...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, "..", "main.py")
    
    restart_count = 0
    max_restarts = 10
    
    while restart_count < max_restarts:
        print(f"Launching bot... (Restart count: {restart_count})")
        process = subprocess.Popen([sys.executable, main_script])
        
        # Wait for the process to exit
        process.wait()
        
        exit_code = process.returncode
        print(f"Bot exited with code {exit_code}")
        
        if exit_code == 0:
            print("Bot exited cleanly. Stopping watchdog.")
            break
            
        print("Bot crashed! Restarting in 10 seconds...")
        time.sleep(10)
        restart_count += 1
        
    if restart_count >= max_restarts:
        print("Max restarts reached. Watchdog exiting.")

if __name__ == "__main__":
    run_watchdog()
