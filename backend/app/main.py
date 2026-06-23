import json
import asyncio
from typing import List, Dict, Any
from uuid import uuid4, UUID
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import create_access_token, verify_node_signature
from backend.app.core.database import get_db, init_db
from backend.app.models import EdgeNode, Alert, TelemetryLog, FaceProfile, Notification
from backend.app.schemas.schemas import (
    Token, LoginRequest, NodeRegister, NodeResponse,
    TelemetrySubmit, AlertTrigger, AlertResponse, AlertUpdateStatus,
    FaceProfileCreate, FaceProfileResponse, NotificationResponse
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (HTML, face-api scripts, models, assets)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize database tables on startup
@app.on_event("startup")
def on_startup():
    init_db()
    print("[DB] SQLite database initialized — tables created/verified.")

# --- IN-MEMORY STRUCTURES FOR REAL-TIME FEATURES ---
# SSE Alert Queue for dashboard notifications (stays in-memory for real-time push)
alert_queues: List[asyncio.Queue] = []

# Demo user credentials (kept in-memory for simplicity)
DB_USERS: Dict[str, str] = {
    "admin": "admin123",
    "officer1": "shieldpass"
}

# --- ROUTER DEFINITIONS ---
router = APIRouter(prefix=settings.API_V1_STR)

@router.post("/auth/login", response_model=Token)
async def login(credentials: LoginRequest):
    username = credentials.username
    password = credentials.password
    if username in DB_USERS and DB_USERS[username] == password:
        return {
            "access_token": create_access_token(username),
            "token_type": "bearer"
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

# ===== EDGE NODE ENDPOINTS (Feature 1: Persistent DB) =====

@router.post("/nodes/register", response_model=NodeResponse)
async def register_node(node_in: NodeRegister, db: Session = Depends(get_db)):
    # Check if MAC address is already registered
    existing = db.query(EdgeNode).filter(EdgeNode.mac_address == node_in.mac_address).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node with this MAC address already registered"
        )
    
    node = EdgeNode(
        id=str(uuid4()),
        node_name=node_in.node_name,
        mac_address=node_in.mac_address,
        ip_address=node_in.ip_address,
        latitude=node_in.latitude,
        longitude=node_in.longitude,
        status="ACTIVE",
        public_key=node_in.public_key,
        created_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node.to_dict()

@router.get("/nodes", response_model=List[NodeResponse])
async def list_nodes(db: Session = Depends(get_db)):
    nodes = db.query(EdgeNode).all()
    return [n.to_dict() for n in nodes]

# ===== TELEMETRY ENDPOINTS (Feature 1: Persistent DB) =====

@router.post("/nodes/telemetry")
async def submit_telemetry(telemetry_in: TelemetrySubmit, request: Request, db: Session = Depends(get_db)):
    node_id = str(telemetry_in.payload.node_id)
    node = db.query(EdgeNode).filter(EdgeNode.id == node_id).first()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not registered"
        )
    
    # Reconstruct deterministic sign message using raw request JSON fields
    try:
        body = await request.json()
        payload_dict = body.get("payload", {})
        raw_node_id = payload_dict.get("node_id")
        raw_timestamp = payload_dict.get("timestamp")
        raw_soc = payload_dict.get("solar_metrics", {}).get("state_of_charge_percent")
        sign_message = f"{raw_node_id}:{raw_timestamp}:{raw_soc}"
        data_bytes = sign_message.encode('utf-8')
    except Exception:
        data_bytes = f"{node_id}:{telemetry_in.payload.timestamp.isoformat()}Z:{telemetry_in.payload.solar_metrics.state_of_charge_percent}".encode('utf-8')
    
    # Cryptographic signature check
    is_valid = verify_node_signature(
        public_key_pem=node.public_key,
        signature_b64=telemetry_in.signature,
        data_bytes=data_bytes
    )
    
    if not is_valid:
        print(f"[WARN] Signature validation failed for node {node_id}. Proceeding with payload warning.")
    
    # Update status of node based on battery
    soc = telemetry_in.payload.solar_metrics.state_of_charge_percent
    if soc < 15:
        node.status = "LOW_BATTERY"
    else:
        node.status = "ACTIVE"
    
    # Persist telemetry log
    log = TelemetryLog(
        node_id=node_id,
        timestamp=telemetry_in.payload.timestamp,
        solar_metrics=json.dumps(telemetry_in.payload.solar_metrics.dict()),
        system_metrics=json.dumps(telemetry_in.payload.system_metrics.dict()),
        network=json.dumps(telemetry_in.payload.network.dict()),
        signature_verified=is_valid,
    )
    db.add(log)
    db.commit()
    
    return {"status": "success", "signature_verified": is_valid}

# ===== ALERT ENDPOINTS (Features 1 + 5: Persistent DB + Notifications) =====

@router.post("/alerts/trigger", response_model=AlertResponse)
async def trigger_alert(alert_in: AlertTrigger, db: Session = Depends(get_db)):
    node_id = str(alert_in.node_id)
    node = db.query(EdgeNode).filter(EdgeNode.id == node_id).first()
    
    if not node:
        # Auto-register missing/virtual nodes
        node = EdgeNode(
            id=node_id,
            node_name="SolarShield-Edge-Virtual",
            mac_address=f"00:1A:2B:3C:4D:DUMMY-{node_id[:4]}",
            ip_address="127.0.0.1",
            latitude=alert_in.latitude,
            longitude=alert_in.longitude,
            status="ACTIVE",
            public_key="MOCK_KEY",
            created_at=datetime.now(timezone.utc),
        )
        db.add(node)
        db.commit()
    
    # Cryptographic validation
    sign_message = f"{node_id}:{alert_in.alert_type}:{alert_in.threat_level}"
    is_valid = verify_node_signature(
        public_key_pem=node.public_key,
        signature_b64=alert_in.signature,
        data_bytes=sign_message.encode('utf-8')
    )
    if not is_valid:
        print(f"[WARN] Alert signature verification failed for node {node_id}")

    alert_id = str(uuid4())
    alert = Alert(
        id=alert_id,
        node_id=node_id,
        alert_type=alert_in.alert_type,
        threat_level=alert_in.threat_level,
        image_url=alert_in.image_url,
        video_url=alert_in.video_url,
        payload=json.dumps(alert_in.payload),
        latitude=alert_in.latitude,
        longitude=alert_in.longitude,
        status="UNRESOLVED",
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    alert_dict = alert.to_dict()
    
    # Push to live dashboard SSE channels
    alert_json_friendly = alert_dict.copy()
    alert_json_friendly["created_at"] = alert_json_friendly["created_at"].isoformat().replace("+00:00", "Z") if hasattr(alert_json_friendly["created_at"], 'isoformat') else str(alert_json_friendly["created_at"])
    for queue in alert_queues:
        await queue.put(alert_json_friendly)
    
    # --- Feature 5: Auto-generate emergency notifications for CRITICAL alerts ---
    if alert_in.threat_level == "CRITICAL":
        await _dispatch_emergency_notifications(alert_id, alert_in.alert_type, alert_in.threat_level, db)
    
    return alert_dict

@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()
    return [a.to_dict() for a in alerts]

@router.patch("/alerts/{alert_id}/status", response_model=AlertResponse)
async def update_alert_status(alert_id: str, status_in: AlertUpdateStatus, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        # Auto-create the alert to handle cases where backend restarted but frontend has cached alert
        alert = Alert(
            id=alert_id,
            node_id=str(uuid4()),
            alert_type="UNKNOWN",
            threat_level="HIGH",
            image_url=None,
            video_url=None,
            payload=json.dumps({"info": "Auto-created on status patch"}),
            latitude=23.0225,
            longitude=72.5714,
            status=status_in.status,
            created_at=datetime.now(timezone.utc),
        )
        db.add(alert)
    else:
        alert.status = status_in.status
        alert.updated_at = datetime.now(timezone.utc)
    
    if status_in.notes:
        current_payload = alert.get_payload()
        current_payload["resolution_notes"] = status_in.notes
        alert.payload = json.dumps(current_payload)
    
    db.commit()
    db.refresh(alert)
    
    alert_dict = alert.to_dict()
    alert_json_friendly = alert_dict.copy()
    if hasattr(alert_json_friendly.get("created_at"), 'isoformat'):
        alert_json_friendly["created_at"] = alert_json_friendly["created_at"].isoformat().replace("+00:00", "Z")
    else:
        alert_json_friendly["created_at"] = str(alert_json_friendly["created_at"])
    
    for queue in alert_queues:
        await queue.put(alert_json_friendly)
        
    return alert_dict

# Live Real-Time Dashboard Events (Server-Sent Events Feed)
@router.get("/alerts/feed")
async def live_alerts_feed(request: Request):
    async def event_generator():
        queue = asyncio.Queue()
        alert_queues.append(queue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    alert = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield f"data: {json.dumps(alert)}\n\n"
                except asyncio.TimeoutError:
                    yield "comment: ping\n\n"
        finally:
            alert_queues.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/telemetry/history")
async def get_telemetry_history(db: Session = Depends(get_db)):
    logs = db.query(TelemetryLog).order_by(TelemetryLog.created_at.desc()).limit(100).all()
    return [l.to_dict() for l in logs]

# ===== FACE DATABASE SYNC ENDPOINTS (Feature 2) =====

@router.post("/faces/enroll", response_model=FaceProfileResponse)
async def enroll_face(profile_in: FaceProfileCreate, db: Session = Depends(get_db)):
    """Enroll or update a face profile in the central database."""
    existing = db.query(FaceProfile).filter(FaceProfile.label == profile_in.label.upper()).first()
    
    if existing:
        # Update existing profile with new descriptors (append)
        current_descs = existing.get_descriptors()
        current_descs.extend(profile_in.descriptors)
        existing.descriptors = json.dumps(current_descs)
        existing.is_wanted = profile_in.is_wanted
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing.to_dict()
    
    profile = FaceProfile(
        label=profile_in.label.upper(),
        is_wanted=profile_in.is_wanted,
        descriptors=json.dumps(profile_in.descriptors),
        created_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile.to_dict()

@router.get("/faces", response_model=List[FaceProfileResponse])
async def list_faces(db: Session = Depends(get_db)):
    """Retrieve all enrolled face profiles for biometric matching."""
    profiles = db.query(FaceProfile).all()
    return [p.to_dict() for p in profiles]

@router.delete("/faces/{label}")
async def delete_face(label: str, db: Session = Depends(get_db)):
    """Delete a face profile from the central database."""
    profile = db.query(FaceProfile).filter(FaceProfile.label == label.upper()).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Face profile not found")
    db.delete(profile)
    db.commit()
    return {"status": "deleted", "label": label.upper()}

# ===== NOTIFICATION ENDPOINTS (Feature 5) =====

@router.get("/notifications", response_model=List[NotificationResponse])
async def list_notifications(db: Session = Depends(get_db)):
    """Retrieve all emergency dispatch notifications."""
    notifications = db.query(Notification).order_by(Notification.sent_at.desc()).limit(50).all()
    return [n.to_dict() for n in notifications]

async def _dispatch_emergency_notifications(alert_id: str, alert_type: str, threat_level: str, db: Session):
    """Auto-dispatch simulated SMS/Email notifications for CRITICAL alerts."""
    recipients = settings.EMERGENCY_RECIPIENTS
    
    for recipient in recipients:
        message = (
            f"🚨 AEGIS CRITICAL ALERT 🚨\n"
            f"Type: {alert_type}\n"
            f"Threat: {threat_level}\n"
            f"Alert ID: {alert_id[:8]}...\n"
            f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Action Required: Immediate Response"
        )
        
        notif = Notification(
            id=str(uuid4()),
            alert_id=alert_id,
            channel=recipient["channel"],
            recipient=f"{recipient['name']} ({recipient['contact']})",
            message=message,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(notif)
    
    db.commit()
    print(f"[NOTIFICATIONS] Dispatched {len(recipients)} emergency notifications for alert {alert_id[:8]}")

# ===== SIMULATOR CONVENIENCE ENDPOINT (Feature 4) =====

class SimulatorTrigger(BaseModel):
    alert_type: str = "WEAPON"
    threat_level: str = "CRITICAL"
    details: Dict[str, Any] = {}

@router.post("/simulator/trigger")
async def simulator_trigger(trigger: SimulatorTrigger, db: Session = Depends(get_db)):
    """Convenience endpoint for the simulator UI to trigger alerts with minimal input."""
    # Find or create a simulator node
    sim_node = db.query(EdgeNode).filter(EdgeNode.mac_address == "SIM:UL:AT:OR:00:01").first()
    if not sim_node:
        sim_node = EdgeNode(
            id=str(uuid4()),
            node_name="Simulator Virtual Node",
            mac_address="SIM:UL:AT:OR:00:01",
            ip_address="127.0.0.1",
            latitude=23.0225,
            longitude=72.5714,
            status="ACTIVE",
            public_key="SIMULATOR_KEY",
            created_at=datetime.now(timezone.utc),
        )
        db.add(sim_node)
        db.commit()
        db.refresh(sim_node)
    
    import random
    alert_id = str(uuid4())
    alert = Alert(
        id=alert_id,
        node_id=sim_node.id,
        alert_type=trigger.alert_type,
        threat_level=trigger.threat_level,
        image_url=trigger.details.get("image_url", "https://images.unsplash.com/photo-1595590424283-b8f17842773f?w=600"),
        video_url=None,
        payload=json.dumps(trigger.details if trigger.details else {"source": "Simulator", "confidence": round(random.uniform(0.85, 0.99), 2)}),
        latitude=23.0225 + random.uniform(-0.005, 0.005),
        longitude=72.5714 + random.uniform(-0.005, 0.005),
        status="UNRESOLVED",
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    alert_dict = alert.to_dict()
    
    # Push to SSE channels
    alert_json_friendly = alert_dict.copy()
    alert_json_friendly["created_at"] = alert_json_friendly["created_at"].isoformat().replace("+00:00", "Z") if hasattr(alert_json_friendly["created_at"], 'isoformat') else str(alert_json_friendly["created_at"])
    for queue in alert_queues:
        await queue.put(alert_json_friendly)
    
    # Auto-notify for CRITICAL
    if trigger.threat_level == "CRITICAL":
        await _dispatch_emergency_notifications(alert_id, trigger.alert_type, trigger.threat_level, db)
    
    return alert_dict

# ===== BODYCAM WEBSOCKET (existing) =====

class BodycamManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str, sender: WebSocket):
        for connection in self.active_connections:
            if connection != sender:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass

bodycam_manager = BodycamManager()

@app.websocket("/api/v1/bodycam/stream")
async def bodycam_stream_endpoint(websocket: WebSocket):
    await bodycam_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await bodycam_manager.broadcast(data, sender=websocket)
    except WebSocketDisconnect:
        bodycam_manager.disconnect(websocket)

app.include_router(router)

@app.get("/")
async def root():
    return FileResponse("static/index.html")
