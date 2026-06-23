import base64
from datetime import datetime, timedelta
from typing import Union, Any
import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

from backend.app.core.config import settings

ALGORITHM = "HS256"

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str) -> Union[str, None]:
    try:
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_token["sub"]
    except jwt.PyJWTError:
        return None

def verify_node_signature(public_key_pem: str, signature_b64: str, data_bytes: bytes) -> bool:
    """
    Verifies that the telemetry or alert payload was signed by the registered node's private key.
    Uses RSASSA-PKCS1-v1_5 / SHA-256 for signing verification.
    """
    try:
        public_key = load_pem_public_key(public_key_pem.encode('utf-8'))
        if not isinstance(public_key, rsa.RSAPublicKey):
            return False
            
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            data_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except (InvalidSignature, ValueError, TypeError, Exception) as e:
        print(f"Cryptographic verification failed: {e}")
        return False
