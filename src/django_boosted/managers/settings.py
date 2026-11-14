from __future__ import annotations

from typing import Any

from django.conf import settings
from virtualqueryset.managers import VirtualManager  # type: ignore[import-untyped]

_UNAVAILABLE = object()
_SENSITIVE_FRAGMENTS = (
    "API_KEY",
    "AUTH",
    "COOKIE",
    "CREDENTIAL",
    "DATABASE",
    "PASSWORD",
    "PRIVATE",
    "SECRET",
    "TOKEN",
)


def _read_setting(name: str) -> Any:
    """Return a setting value, or a sentinel when access raises."""
    try:
        return getattr(settings, name)
    except Exception:  # pragma: no cover - defensive against lazy settings
        return _UNAVAILABLE


def _is_sensitive_setting(name: str) -> bool:
    return any(fragment in name for fragment in _SENSITIVE_FRAGMENTS)


class SettingManager(VirtualManager):
    """
    Collects Django configuration settings as a virtual queryset.

    Each entry exposes the setting name and its raw value. The value keeps its
    original Python type so the admin can decide how to render it (simple text,
    pretty JSON or an opaque "complexe" placeholder).
    """

    def get_data(self) -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = []
        for name in dir(settings):
            if not name.isupper() or _is_sensitive_setting(name):
                continue
            value = _read_setting(name)
            if value is _UNAVAILABLE:
                continue
            data.append({"name": name, "value": value})
        return data

    def get_queryset(self):
        return super().get_queryset().order_by("name")
