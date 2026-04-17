from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any, Callable, Protocol

_ENTRY_POINT_GROUP = "a0.computer_use_backends"


@dataclass(frozen=True)
class ComputerUseBackendSpec:
    backend_id: str
    backend_family: str
    priority: int
    detect: Callable[[], bool]
    features: tuple[str, ...]
    interpreter_strategy: str
    helper_target: str
    trust_mode_support: tuple[str, ...]
    support_reason: Callable[[], str] = lambda: ""

    def supports_trust_mode(self, mode: str) -> bool:
        return str(mode or "").strip().lower() in self.trust_mode_support


@dataclass(frozen=True)
class ComputerUseBackendSelection:
    spec: ComputerUseBackendSpec | None
    supported: bool
    support_reason: str


class ComputerUseBackend(Protocol):
    spec: ComputerUseBackendSpec

    def hello_metadata(self) -> dict[str, Any]:
        ...

    def helper_command(self) -> list[str]:
        ...


_BUILTIN_SPECS: dict[str, ComputerUseBackendSpec] = {}
_EXTRA_SPECS: dict[str, ComputerUseBackendSpec] = {}


def register_builtin_backend_spec(spec: ComputerUseBackendSpec) -> ComputerUseBackendSpec:
    _BUILTIN_SPECS[spec.backend_id] = spec
    return spec


def register_backend_spec(spec: ComputerUseBackendSpec) -> ComputerUseBackendSpec:
    _EXTRA_SPECS[spec.backend_id] = spec
    return spec


def clear_backend_specs() -> None:
    _EXTRA_SPECS.clear()


def _coerce_spec(candidate: object) -> ComputerUseBackendSpec | None:
    if isinstance(candidate, ComputerUseBackendSpec):
        return candidate

    spec = getattr(candidate, "spec", None)
    if isinstance(spec, ComputerUseBackendSpec):
        return spec

    if callable(candidate):
        try:
            loaded = candidate()
        except Exception:
            return None
        if isinstance(loaded, ComputerUseBackendSpec):
            return loaded
        spec = getattr(loaded, "spec", None)
        if isinstance(spec, ComputerUseBackendSpec):
            return spec

    return None


def _entry_point_specs() -> list[ComputerUseBackendSpec]:
    try:
        entry_points = metadata.entry_points()
    except Exception:
        return []

    if hasattr(entry_points, "select"):
        group = entry_points.select(group=_ENTRY_POINT_GROUP)
    else:  # pragma: no cover - legacy importlib.metadata shape
        group = entry_points.get(_ENTRY_POINT_GROUP, [])

    specs: list[ComputerUseBackendSpec] = []
    for entry_point in group:
        try:
            candidate = entry_point.load()
        except Exception:
            continue
        spec = _coerce_spec(candidate)
        if spec is not None:
            specs.append(spec)
    return specs


def available_backend_specs() -> list[ComputerUseBackendSpec]:
    merged: dict[str, ComputerUseBackendSpec] = {}
    for source in (_BUILTIN_SPECS.values(), _entry_point_specs(), _EXTRA_SPECS.values()):
        for spec in source:
            merged[spec.backend_id] = spec
    return sorted(merged.values(), key=lambda item: (-item.priority, item.backend_id))


def resolve_backend_selection() -> ComputerUseBackendSelection:
    specs = sorted(available_backend_specs(), key=lambda item: (-item.priority, item.backend_id))
    if not specs:
        return ComputerUseBackendSelection(
            spec=None,
            supported=False,
            support_reason="No computer-use backend specs are registered.",
        )

    detect_error: str | None = None
    for spec in specs:
        try:
            if spec.detect():
                reason = str(spec.support_reason() or "").strip() or "Detected computer-use backend."
                return ComputerUseBackendSelection(spec=spec, supported=True, support_reason=reason)
        except Exception as exc:
            if detect_error is None:
                detect_error = f"{spec.backend_id} detect() failed: {exc}"
            continue

    spec = specs[0]
    reason = str(spec.support_reason() or "").strip()
    if not reason:
        reason = detect_error or f"No detected backend matched {spec.backend_id!r}."
    return ComputerUseBackendSelection(spec=spec, supported=False, support_reason=reason)
