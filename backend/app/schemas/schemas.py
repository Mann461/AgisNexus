from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str

class NodeRegister(BaseModel):
    node_name: str
    mac_address: str
    ip_address: str
    latitude: float
    longitude: float
    public_key: str

class NodeResponse(BaseModel):
    id: UUID
    node_name: str
    mac_address: str
    ip_address: str
    latitude: float
    longitude: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class SolarMetrics(BaseModel):
    panel_voltage_v: float
    battery_voltage_v: float
    charge_current_a: float
    load_current_a: float
    battery_temp_c: float
    state_of_charge_percent: int

class SystemMetrics(BaseModel):
    cpu_usage_percent: float
    gpu_usage_percent: float
    ram_usage_mb: int
    disk_usage_percent: float
    temperature_c: float

class NetworkMetrics(BaseModel):
    signal_strength_dbm: int
    mode: str

class TelemetryPayload(BaseModel):
    node_id: UUID
    timestamp: datetime
    solar_metrics: SolarMetrics
    system_metrics: SystemMetrics
    network: NetworkMetrics

class TelemetrySubmit(BaseModel):
    payload: TelemetryPayload
    signature: str # Base64 signature of the JSON representation of the payload

class AlertTrigger(BaseModel):
    node_id: UUID
    alert_type: str # WEAPON, VIOLENCE, CRIMINAL_MATCH, MISSING_PERSON, LPR, GEOFENCE_BREACH
    threat_level: str # CRITICAL, HIGH, MEDIUM, LOW
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    payload: Dict[str, Any] # e.g. bounding boxes, plate details, face matching confidence
    latitude: float
    longitude: float
    signature: str # Base64 signature of stringified JSON representation of coordinates + type + threat

class AlertResponse(BaseModel):
    id: UUID
    node_id: UUID
    alert_type: str
    threat_level: str
    image_url: Optional[str]
    video_url: Optional[str]
    payload: Dict[str, Any]
    latitude: float
    longitude: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class AlertUpdateStatus(BaseModel):
    status: str # UNRESOLVED, ACKNOWLEDGED, DISPATCHED, RESOLVED
    notes: Optional[str] = None

# --- Feature 2: Face Database Sync Schemas ---
class FaceProfileCreate(BaseModel):
    label: str
    is_wanted: bool = False
    descriptors: list  # List of float arrays (face descriptor vectors)

class FaceProfileResponse(BaseModel):
    id: int
    label: str
    is_wanted: bool
    descriptors: list
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

# --- Feature 5: Notification Schemas ---
class NotificationResponse(BaseModel):
    id: str
    alert_id: str
    channel: str  # SMS, EMAIL
    recipient: str
    message: str
    sent_at: Optional[str] = None

    class Config:
        from_attributes = True
