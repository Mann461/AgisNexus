import os
import sys
import time
import subprocess
import threading

def run_backend():
    print("[LAUNCH] Starting FastAPI Backend on http://localhost:8000...")
    # Run from root directory, specify package module path
    root_dir = os.getcwd()
    cmd = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    try:
        subprocess.run(cmd, cwd=root_dir, check=True)
    except Exception as e:
        print(f"[BACKEND ERROR] Server exited: {e}")

def run_edge_node():
    print("[LAUNCH] Starting Edge Node AI Simulator in 3 seconds...")
    time.sleep(3)
    
    edge_script = os.path.join(os.getcwd(), "ai-edge-node", "main.py")
    cmd = [sys.executable, edge_script]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"[EDGE ERROR] Node simulator exited: {e}")

if __name__ == "__main__":
    # Start threads for backend and edge node
    t1 = threading.Thread(target=run_backend, daemon=True)
    t2 = threading.Thread(target=run_edge_node, daemon=True)
    
    t1.start()
    t2.start()
    
    print("\n=======================================================")
    print(" SolarShield AI Demo Suite is running!")
    print(" - Backend: http://localhost:8000")
    print(" - API Docs: http://localhost:8000/docs")
    print(" - Dashboard: Double-click frontend/index.html to view")
    print("=======================================================\n")
    
    try:
        while True:
            time.sleep(1)
            if not t1.is_alive():
                print("[FATAL ERROR] FastAPI Backend server has stopped unexpectedly. Please check for port conflicts (e.g. port 8000 already in use) or import errors.")
                sys.exit(1)
            if not t2.is_alive():
                print("[WARN] Edge Node simulator thread has stopped.")
    except KeyboardInterrupt:
        print("\nShutting down demo suite...")
