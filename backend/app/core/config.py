import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SolarShield AI - Autonomous Smart Policing Network"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "SUPER_SECRET_HMAC_KEY_FOR_DEMO_2026")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 week
    
    # Database URIs (can be overridden with env variables)
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "solarshield_db")
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB: str = "solarshield_diagnostics"

    # SQLite for zero-config persistent storage (demo default)
    SQLITE_DATABASE_URL: str = "sqlite:///./solarshield.db"

    # Simulated emergency dispatch recipients
    EMERGENCY_RECIPIENTS: list = [
        {"name": "Inspector Sharma", "channel": "SMS", "contact": "+91-98765-43210"},
        {"name": "Control Room Alpha", "channel": "EMAIL", "contact": "control@aegis-hq.gov.in"},
        {"name": "SP Office Ahmedabad", "channel": "SMS", "contact": "+91-79-2550-1234"},
    ]

    # Cryptographic keys verification path
    KEYS_DIR: str = os.getenv("KEYS_DIR", "./keys")

settings = Settings()
