"""SMSE-Registry-Agent — in-memory, keyed (asset, timestamp).

v0 stores nothing durable. The Supabase sink (sfx_market_data.smse_outputs, INFRA-001
``sync-smse``) is out of scope; a persistent backend implements ``RegistrySink``.
"""

from __future__ import annotations

from typing import Protocol

from smse_engine.schema import SMSERecord


class RegistryConflictError(RuntimeError):
    """Same (asset, timestamp) re-submitted with different content."""


class RegistrySink(Protocol):
    def put(self, record: SMSERecord) -> bool: ...


class InMemoryRegistry:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], SMSERecord] = {}

    def put(self, record: SMSERecord) -> bool:
        """Idempotent insert. Returns True if newly stored, False if an identical replay."""
        key = (record.smse.asset, record.smse.timestamp)
        existing = self._rows.get(key)
        if existing is None:
            self._rows[key] = record
            return True
        if existing.smse != record.smse:
            raise RegistryConflictError(f"conflicting SMSE_v1 for {key}")
        return False

    def get(self, asset: str, timestamp: str) -> SMSERecord | None:
        return self._rows.get((asset, timestamp))

    def __len__(self) -> int:
        return len(self._rows)
