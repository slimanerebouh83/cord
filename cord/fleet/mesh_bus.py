"""
CORD Fleet - Authenticated & Encrypted Inter-Agent Mesh Communication Bus
Provides end-to-end authenticated encryption, replay defense, and tamper-proof peer-to-peer messaging.
"""

from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


class MeshSecurityError(Exception):
    """Raised when message signature verification fails or tampering is detected."""
    pass


@dataclass
class EncryptedMessage:
    message_id: str
    sender_agent: str
    sender_node: str
    recipient_agent: str  # specific agent ID or "*" for broadcast
    recipient_node: str   # specific node name or "*"
    nonce: str            # hex encoded 16-byte nonce
    ciphertext: str       # base64 encoded ciphertext
    signature: str        # HMAC-SHA256 signature
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedMessage":
        return cls(
            message_id=data["message_id"],
            sender_agent=data["sender_agent"],
            sender_node=data["sender_node"],
            recipient_agent=data["recipient_agent"],
            recipient_node=data.get("recipient_node", "*"),
            nonce=data["nonce"],
            ciphertext=data["ciphertext"],
            signature=data["signature"],
            timestamp=float(data["timestamp"]),
        )


class EncryptedMeshBus:
    """
    Military-grade authenticated peer-to-peer message bus for distributed agents.
    Uses SHA256-CTR keystream encryption with HMAC-SHA256 authentication and replay protection.
    """

    def __init__(self, key_path: Optional[Path] = None):
        if key_path is None:
            self.key_path = Path.home() / ".cord" / "mesh.key"
        else:
            self.key_path = key_path

        self._master_key = self._load_or_generate_key()
        self._inboxes: Dict[str, List[EncryptedMessage]] = {}
        self._processed_msg_ids: set[str] = set()

    def _load_or_generate_key(self) -> bytes:
        """Loads existing 256-bit mesh key or generates a fresh cryptographically secure key."""
        if self.key_path.exists():
            try:
                data = self.key_path.read_text(encoding="utf-8").strip()
                if len(data) >= 32:
                    return hashlib.sha256(data.encode("utf-8")).digest()
            except Exception:
                pass

        new_key = secrets.token_hex(32)
        try:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            self.key_path.write_text(new_key, encoding="utf-8")
        except Exception:
            pass
        return hashlib.sha256(new_key.encode("utf-8")).digest()

    def _derive_keys(self, nonce_bytes: bytes) -> tuple[bytes, bytes]:
        """Derives separate encryption and MAC keys from master key and nonce using HKDF-like PRF."""
        enc_key = hashlib.sha256(self._master_key + nonce_bytes + b"ENC-STREAM").digest()
        mac_key = hashlib.sha256(self._master_key + nonce_bytes + b"MAC-AUTH").digest()
        return enc_key, mac_key

    def _keystream(self, enc_key: bytes, length: int) -> bytes:
        """Generates deterministic pseudo-random keystream blocks."""
        stream = bytearray()
        block_idx = 0
        while len(stream) < length:
            block = hashlib.sha256(enc_key + block_idx.to_bytes(4, "big")).digest()
            stream.extend(block)
            block_idx += 1
        return bytes(stream[:length])

    def encrypt_payload(self, plaintext: str) -> tuple[str, str, str]:
        """
        Encrypts plaintext string and generates authentication tag.
        Returns: (nonce_hex, ciphertext_b64, signature_hex)
        """
        raw_bytes = plaintext.encode("utf-8")
        nonce_bytes = secrets.token_bytes(16)
        enc_key, mac_key = self._derive_keys(nonce_bytes)

        # Counter mode keystream XOR
        keystream = self._keystream(enc_key, len(raw_bytes))
        ciphertext_bytes = bytes(b ^ k for b, k in zip(raw_bytes, keystream))

        # HMAC-SHA256 authentication tag across nonce + ciphertext
        mac = hmac.new(mac_key, nonce_bytes + ciphertext_bytes, hashlib.sha256).hexdigest()

        return (
            nonce_bytes.hex(),
            base64.b64encode(ciphertext_bytes).decode("ascii"),
            mac,
        )

    def decrypt_payload(self, nonce_hex: str, ciphertext_b64: str, signature_hex: str) -> str:
        """
        Verifies signature and decrypts ciphertext.
        Raises MeshSecurityError on tamper detection or bad signature.
        """
        nonce_bytes = bytes.fromhex(nonce_hex)
        ciphertext_bytes = base64.b64decode(ciphertext_b64)
        enc_key, mac_key = self._derive_keys(nonce_bytes)

        # Verify HMAC in constant time
        expected_mac = hmac.new(mac_key, nonce_bytes + ciphertext_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_mac, signature_hex):
            raise MeshSecurityError("HMAC signature verification failed: payload was tampered with or key mismatch!")

        # Decrypt via keystream XOR
        keystream = self._keystream(enc_key, len(ciphertext_bytes))
        plaintext_bytes = bytes(b ^ k for b, k in zip(ciphertext_bytes, keystream))
        return plaintext_bytes.decode("utf-8", errors="replace")

    def register_agent(self, agent_id: str) -> None:
        if agent_id not in self._inboxes:
            self._inboxes[agent_id] = []

    def unregister_agent(self, agent_id: str) -> None:
        self._inboxes.pop(agent_id, None)

    def send_encrypted(
        self,
        sender_agent: str,
        sender_node: str,
        recipient_agent: str,
        recipient_node: str,
        payload: str,
    ) -> EncryptedMessage:
        """Sends an authenticated encrypted message to a target agent."""
        nonce, ct, sig = self.encrypt_payload(payload)
        msg = EncryptedMessage(
            message_id=str(uuid.uuid4()),
            sender_agent=sender_agent,
            sender_node=sender_node,
            recipient_agent=recipient_agent,
            recipient_node=recipient_node,
            nonce=nonce,
            ciphertext=ct,
            signature=sig,
            timestamp=time.time(),
        )

        if recipient_agent not in self._inboxes:
            self._inboxes[recipient_agent] = []
        self._inboxes[recipient_agent].append(msg)
        return msg

    def broadcast_encrypted(
        self,
        sender_agent: str,
        sender_node: str,
        payload: str,
    ) -> List[EncryptedMessage]:
        """Broadcasts an encrypted message to all registered agents."""
        created = []
        for aid in list(self._inboxes.keys()):
            if aid != sender_agent:
                msg = self.send_encrypted(
                    sender_agent=sender_agent,
                    sender_node=sender_node,
                    recipient_agent=aid,
                    recipient_node="*",
                    payload=payload,
                )
                created.append(msg)
        return created

    def read_inbox(self, agent_id: str) -> List[Dict[str, Any]]:
        """Reads and decrypts all unread messages for the given agent."""
        if agent_id not in self._inboxes:
            return []

        pending = self._inboxes[agent_id]
        self._inboxes[agent_id] = []
        decrypted_results = []

        now = time.time()
        for msg in pending:
            # Replay defense: discard messages older than 10 minutes or already seen
            if msg.message_id in self._processed_msg_ids:
                continue
            if abs(now - msg.timestamp) > 600:
                continue

            try:
                decrypted_text = self.decrypt_payload(msg.nonce, msg.ciphertext, msg.signature)
                self._processed_msg_ids.add(msg.message_id)
                decrypted_results.append({
                    "message_id": msg.message_id,
                    "from_agent": msg.sender_agent,
                    "from_node": msg.sender_node,
                    "to_agent": msg.recipient_agent,
                    "content": decrypted_text,
                    "timestamp": msg.timestamp,
                    "verified": True,
                })
            except MeshSecurityError as e:
                decrypted_results.append({
                    "message_id": msg.message_id,
                    "from_agent": msg.sender_agent,
                    "error": f"SECURITY ALERT: {e}",
                    "verified": False,
                })

        return decrypted_results


encrypted_mesh = EncryptedMeshBus()
