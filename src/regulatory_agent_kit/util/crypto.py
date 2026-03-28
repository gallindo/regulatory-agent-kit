"""Cryptographic utilities — Ed25519 signing for audit trail entries."""

from __future__ import annotations

import base64
import json
from pathlib import Path  # noqa: TC003
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from regulatory_agent_kit.exceptions import AuditSigningError


class AuditSigner:
    """Ed25519 signing and verification for audit trail entries."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private_key = private_key
        self._public_key = private_key.public_key()

    @classmethod
    def generate_key_pair(cls) -> tuple[bytes, bytes]:
        """Generate a new Ed25519 key pair.

        Returns:
            Tuple of (private_key_pem, public_key_pem) as bytes.
        """
        private_key = Ed25519PrivateKey.generate()
        private_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )
        return private_pem, public_pem

    @classmethod
    def load_key(cls, path: Path) -> AuditSigner:
        """Load an Ed25519 private key from a PEM file."""
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        try:
            key_data = path.read_bytes()
            private_key = load_pem_private_key(key_data, password=None)
        except Exception as exc:
            msg = f"Failed to load Ed25519 private key from '{path}': {exc}"
            raise AuditSigningError(msg) from exc

        if not isinstance(private_key, Ed25519PrivateKey):
            msg = f"Key at '{path}' is not an Ed25519 private key"
            raise AuditSigningError(msg)

        return cls(private_key)

    @classmethod
    def from_private_bytes(cls, private_pem: bytes) -> AuditSigner:
        """Create an AuditSigner from PEM-encoded private key bytes."""
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private_key = load_pem_private_key(private_pem, password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            msg = "Provided bytes are not an Ed25519 private key"
            raise AuditSigningError(msg)
        return cls(private_key)

    def sign(self, payload: dict[str, Any]) -> str:
        """Sign a payload dict, returning a base64-encoded Ed25519 signature."""
        canonical = _canonicalize(payload)
        try:
            signature = self._private_key.sign(canonical)
        except Exception as exc:
            msg = f"Signing failed: {exc}"
            raise AuditSigningError(msg) from exc
        return base64.b64encode(signature).decode("ascii")

    def verify(self, payload: dict[str, Any], signature: str) -> bool:
        """Verify a payload against a base64-encoded Ed25519 signature.

        Returns True if valid, False if tampered.
        """
        canonical = _canonicalize(payload)
        try:
            sig_bytes = base64.b64decode(signature)
            self._public_key.verify(sig_bytes, canonical)
        except Exception:
            return False
        return True

    @property
    def public_key(self) -> Ed25519PublicKey:
        """Return the public key for external verification."""
        return self._public_key


def _canonicalize(payload: dict[str, Any]) -> bytes:
    """Produce a deterministic JSON serialization for signing.

    Keys are sorted recursively, ensuring identical payloads produce
    identical byte sequences regardless of dict ordering.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
