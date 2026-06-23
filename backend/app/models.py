"""
SQLAlchemy ORM models for the SolarShield AI platform.
Maps to SQLite tables for persistent storage of nodes, alerts, telemetry, face profiles, and notifications.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Float, Integer, Text, DateTime, Boolean, JSON
from backend.app.core.database import Base


def generate_uuid():
    return str(uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class EdgeNode(Base):
    __tablename__ = "edge_nodes"

    id = Column(String, primary_key=True, default=generate_uuid)
    node_name = Column(String(100), nullable=False)
    mac_address = Column(String(17), unique=True, nullable=False)
    ip_address = Column(String(45), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String(20), default="ACTIVE")
    public_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "node_name": self.node_name,
            "mac_address": self.mac_address,
            "ip_address": self.ip_address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "status": self.status,
            "public_key": self.public_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String, primary_key=True, default=generate_uuid)
    node_id = Column(String, nullable=False)
    alert_type = Column(String(50), nullable=False)
    threat_level = Column(String(20), nullable=False)
    image_url = Column(String(255), nullable=True)
    video_url = Column(String(255), nullable=True)
    payload = Column(Text, nullable=False, default="{}")  # Store as JSON string
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(String(20), default="UNRESOLVED")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def get_payload(self):
        try:
            return json.loads(self.payload) if isinstance(self.payload, str) else self.payload
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "node_id": self.node_id,
            "alert_type": self.alert_type,
            "threat_level": self.threat_level,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "payload": self.get_payload(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    solar_metrics = Column(Text, nullable=False, default="{}")
    system_metrics = Column(Text, nullable=False, default="{}")
    network = Column(Text, nullable=False, default="{}")
    signature_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "solar_metrics": json.loads(self.solar_metrics) if isinstance(self.solar_metrics, str) else self.solar_metrics,
            "system_metrics": json.loads(self.system_metrics) if isinstance(self.system_metrics, str) else self.system_metrics,
            "network": json.loads(self.network) if isinstance(self.network, str) else self.network,
            "signature_verified": self.signature_verified,
        }


class FaceProfile(Base):
    __tablename__ = "face_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(100), unique=True, nullable=False)
    is_wanted = Column(Boolean, default=False)
    descriptors = Column(Text, nullable=False, default="[]")  # JSON array of float arrays
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def get_descriptors(self):
        try:
            return json.loads(self.descriptors) if isinstance(self.descriptors, str) else self.descriptors
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "is_wanted": self.is_wanted,
            "descriptors": self.get_descriptors(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    alert_id = Column(String, nullable=False)
    channel = Column(String(20), nullable=False)  # SMS, EMAIL
    recipient = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "message": self.message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }
