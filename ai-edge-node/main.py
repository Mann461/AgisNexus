import os
import sys
import time
import json
import base64
import random
import requests
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, PrivateFormat, NoEncryption

# --- CONFIGURATION ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")
NODE_NAME = "SolarShield-Edge-01"
MAC_ADDRESS = "00:1A:2B:3C:4D:5E"
LATITUDE = 23.0225
LONGITUDE = 72.5714

# --- CRYPTOGRAPHIC KEYS INITIALIZATION ---
print("Generating RSA key pair for cryptographic identity...")
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)
public_key = private_key.public_key()

private_key_pem = private_key.private_bytes(
    encoding=Encoding.PEM,
    format=PrivateFormat.PKCS8,
    encryption_algorithm=NoEncryption()
).decode('utf-8')

public_key_pem = public_key.public_bytes(
    encoding=Encoding.PEM,
    format=PublicFormat.SubjectPublicKeyInfo
).decode('utf-8')

# --- LOCAL STATE ---
node_id = None
battery_charge = 100.0  # Percentage
charging = True

# --- HELPER FUNCTIONS ---
def sign_payload(message_bytes: bytes) -> str:
    signature = private_key.sign(
        message_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode('utf-8')

def register_with_backend():
    global node_id
    payload = {
        "node_name": NODE_NAME,
        "mac_address": MAC_ADDRESS,
        "ip_address": "192.168.1.150",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "public_key": public_key_pem
    }
    
    url = f"{BACKEND_URL}/nodes/register"
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            res_data = response.json()
            node_id = res_data["id"]
            print(f"[SUCCESS] Node registered. Assigned UUID: {node_id}")
            return True
        elif response.status_code == 400:
            # Already registered or MAC collision, try to fetch nodes to get existing ID
            print("[INFO] Node already registered on backend. Mocking reconnection...")
            list_resp = requests.get(f"{BACKEND_URL}/nodes")
            if list_resp.status_code == 200:
                for n in list_resp.json():
                    if n["mac_address"] == MAC_ADDRESS:
                        node_id = n["id"]
                        print(f"[SUCCESS] Connected back to existing Node UUID: {node_id}")
                        return True
            return False
        else:
            print(f"[ERROR] Registration failed: {response.text}")
            return False
    except Exception as e:
        print(f"[CONNECTION ERROR] Failed to reach backend: {e}")
        return False

def simulate_detection() -> dict:
    """
    Simulates AI detections across categories requested by user:
    Face Detection, Weapon Detection, Violence/Fight, ALPR, Loitering, etc.
    """
    incident_types = [
        {"type": "WEAPON", "threat": "CRITICAL", "details": {"weapon": "Handgun", "confidence": 0.94}},
        {"type": "VIOLENCE", "threat": "HIGH", "details": {"type": "Fight detected", "participants": 2, "confidence": 0.89}},
        {"type": "CRIMINAL_MATCH", "threat": "CRITICAL", "details": {"criminal_id": "CRIM-9981", "name": "Wanted Suspect", "similarity": 0.91}},
        {"type": "LPR", "threat": "LOW", "details": {"plate": "KA-51-MD-2026", "match_flag": True, "owner": "Registered Stolen Vehicle"}},
        {"type": "GEOFENCE_BREACH", "threat": "MEDIUM", "details": {"zone": "Restricted Substation Area", "duration_seconds": 15}}
    ]
    
    # Randomly select a simulated incident
    incident = random.choice(incident_types)
    return incident

def send_telemetry():
    global battery_charge, charging
    
    # Simulate solar charge cycle
    # During day (even simulated seconds), voltage fluctuates and charges.
    # If SoC is full, charge slows down.
    if charging:
        battery_charge += random.uniform(0.5, 1.5)
        if battery_charge >= 100.0:
            battery_charge = 100.0
            charging = False
    else:
        battery_charge -= random.uniform(0.2, 0.8)
        if battery_charge <= 20.0:
            charging = True
            
    panel_voltage = random.uniform(15.0, 21.0) if charging else random.uniform(11.0, 13.0)
    charge_current = random.uniform(2.0, 6.0) if charging else 0.0
    load_current = random.uniform(1.8, 3.2)
    
    telemetry_payload = {
        "node_id": node_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "solar_metrics": {
            "panel_voltage_v": round(panel_voltage, 2),
            "battery_voltage_v": round(random.uniform(12.8, 13.6), 2),
            "charge_current_a": round(charge_current, 2),
            "load_current_a": round(load_current, 2),
            "battery_temp_c": round(random.uniform(28.0, 38.0), 1),
            "state_of_charge_percent": int(battery_charge)
        },
        "system_metrics": {
            "cpu_usage_percent": round(random.uniform(30.0, 65.0), 1),
            "gpu_usage_percent": round(random.uniform(40.0, 85.0), 1),
            "ram_usage_mb": random.randint(2800, 3600),
            "disk_usage_percent": round(random.uniform(12.0, 16.0), 2),
            "temperature_c": round(random.uniform(45.0, 62.0), 1)
        },
        "network": {
            "signal_strength_dbm": random.randint(-85, -50),
            "mode": "WIFI"
        }
    }
    
    # Sign telemetry
    # Message schema: "node_id:timestamp:state_of_charge"
    sign_message = f"{node_id}:{telemetry_payload['timestamp']}:{telemetry_payload['solar_metrics']['state_of_charge_percent']}"
    sig = sign_payload(sign_message.encode('utf-8'))
    
    submit_data = {
        "payload": telemetry_payload,
        "signature": sig
    }
    
    try:
        resp = requests.post(f"{BACKEND_URL}/nodes/telemetry", json=submit_data)
        if resp.status_code == 200:
            print(f"[TELEMETRY SENT] SoC: {int(battery_charge)}% | Panel V: {round(panel_voltage, 1)}V | Sig Valid: {resp.json().get('signature_verified')}")
    except Exception as e:
        print(f"[TELEMETRY ERROR] Failed to send: {e}")

def trigger_incident_alert():
    detection = simulate_detection()
    
    # 1. Sign alert message
    # Message schema to sign: "node_id:alert_type:threat_level"
    sign_message = f"{node_id}:{detection['type']}:{detection['threat']}"
    sig = sign_payload(sign_message.encode('utf-8'))
    
    alert_payload = {
        "node_id": node_id,
        "alert_type": detection["type"],
        "threat_level": detection["threat"],
        "image_url": f"/static/evidence/event_{int(time.time())}.jpg",
        "video_url": f"/static/evidence/event_{int(time.time())}.mp4",
        "payload": detection["details"],
        "latitude": LATITUDE + random.uniform(-0.001, 0.001),
        "longitude": LONGITUDE + random.uniform(-0.001, 0.001),
        "signature": sig
    }
    
    try:
        resp = requests.post(f"{BACKEND_URL}/alerts/trigger", json=alert_payload)
        if resp.status_code == 200:
            print(f"[ALERT TRIGGERED] {detection['type']} | Threat: {detection['threat']} | Details: {detection['details']}")
    except Exception as e:
        print(f"[ALERT ERROR] Failed to trigger: {e}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    print("--------------------------------------------------")
    print("SolarShield AI - Autonomous Edge Node Simulator")
    print("--------------------------------------------------")
    
    # Wait a second for backend server to boot if run in parallel
    time.sleep(2)
    
    # Locked to Ahmedabad coordinates
    
    registered = False
    while not registered:
        registered = register_with_backend()
        if not registered:
            print("Retrying registration in 5 seconds...")
            time.sleep(5)
            
    # Main simulation loop
    loop_count = 0
    while True:
        loop_count += 1
        
        # Power-aware adjustment: throttle rate if battery is low
        # Adaptive processing rate:
        # > 50% battery -> Run detection frame simulations faster (every 5 seconds)
        # 15-50% battery -> Throttled detection frame simulations (every 10 seconds)
        # < 15% battery -> Low-power mode, sleep 20 seconds, send basic telemetry only.
        
        sleep_time = 5.0
        if battery_charge < 15.0:
            sleep_time = 15.0
            print("[BATTERY SAVING MODE] Power low. Throttling frequency, disabling heavy AI inferences.")
        elif battery_charge < 50.0:
            sleep_time = 8.0
            print("[ADAPTIVE THROTTLE] Medium battery. Adjusting frame capture rates.")
            
        time.sleep(sleep_time)
        
        # Every step, send telemetry
        send_telemetry()
