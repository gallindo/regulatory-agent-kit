"""Tests for Ed25519 audit signing (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulatory_agent_kit.exceptions import AuditSigningError
from regulatory_agent_kit.util.crypto import AuditSigner, _canonicalize


class TestKeyGeneration:
    def test_generate_key_pair(self) -> None:
        private_pem, public_pem = AuditSigner.generate_key_pair()
        assert private_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
        assert public_pem.startswith(b"-----BEGIN PUBLIC KEY-----")

    def test_load_from_bytes(self) -> None:
        private_pem, _ = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)
        assert signer.public_key is not None

    def test_load_from_file(self, tmp_path: Path) -> None:
        private_pem, _ = AuditSigner.generate_key_pair()
        key_file = tmp_path / "key.pem"
        key_file.write_bytes(private_pem)
        signer = AuditSigner.load_key(key_file)
        assert signer.public_key is not None

    def test_load_nonexistent_raises(self) -> None:
        with pytest.raises(AuditSigningError):
            AuditSigner.load_key(Path("/nonexistent/key.pem"))


class TestSignAndVerify:
    def test_sign_and_verify(self) -> None:
        private_pem, _ = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)

        payload = {"event_type": "llm_call", "model": "claude", "tokens": 100}
        signature = signer.sign(payload)
        assert isinstance(signature, str)
        assert len(signature) > 0
        assert signer.verify(payload, signature) is True

    def test_tampered_payload_rejected(self) -> None:
        private_pem, _ = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)

        payload = {"key": "value"}
        signature = signer.sign(payload)

        # Modify payload
        payload["key"] = "tampered"
        assert signer.verify(payload, signature) is False

    def test_added_field_rejected(self) -> None:
        private_pem, _ = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)

        payload = {"key": "value"}
        signature = signer.sign(payload)

        payload["extra"] = "injected"
        assert signer.verify(payload, signature) is False

    def test_removed_field_rejected(self) -> None:
        private_pem, _ = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)

        payload = {"a": 1, "b": 2}
        signature = signer.sign(payload)

        del payload["b"]
        assert signer.verify(payload, signature) is False

    def test_invalid_signature_rejected(self) -> None:
        private_pem, _ = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)
        assert signer.verify({"key": "value"}, "invalidsig") is False


class TestCanonicalize:
    def test_deterministic_key_ordering(self) -> None:
        assert _canonicalize({"b": 1, "a": 2}) == _canonicalize({"a": 2, "b": 1})

    def test_nested_dicts_sorted(self) -> None:
        d1 = {"z": {"b": 1, "a": 2}, "a": 0}
        d2 = {"a": 0, "z": {"a": 2, "b": 1}}
        assert _canonicalize(d1) == _canonicalize(d2)
