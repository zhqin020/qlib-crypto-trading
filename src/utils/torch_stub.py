"""Utility helpers to provide a lightweight torch stub in testing environments."""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any


def _create_stub() -> ModuleType:
    torch_stub = ModuleType("torch")
    cuda_stub = SimpleNamespace(
        is_available=lambda: False,
        device_count=lambda: 0,
        get_device_name=lambda idx: f"GPU {idx}",
        memory_allocated=lambda idx: 0.0,
        memory_reserved=lambda idx: 0.0,
        empty_cache=lambda: None,
    )
    torch_stub.cuda = cuda_stub  # type: ignore[attr-defined]
    return torch_stub


def ensure_torch_available() -> ModuleType:
    """Ensure ``import torch`` succeeds even if PyTorch isn't installed.

    Returns the actual torch module when present, otherwise registers and returns
    a very small stub that exposes the CUDA helpers our tests patch.
    """
    try:
        import torch  # type: ignore
        return torch  # type: ignore[return-value]
    except ModuleNotFoundError:
        existing = sys.modules.get("torch")
        if isinstance(existing, ModuleType):
            return existing

        stub = _create_stub()
        sys.modules["torch"] = stub
        return stub


def reset_stub_for_tests():  # pragma: no cover - convenience helper
    """Force reinstallation of the stub (used in tests that reload modules)."""
    sys.modules.pop("torch", None)
    ensure_torch_available()


__all__ = ["ensure_torch_available", "reset_stub_for_tests"]
