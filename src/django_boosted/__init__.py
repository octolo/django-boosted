"""Public exports for django-boosted."""

from importlib.metadata import version

from .admin import (
    AdminBoostFormat,
    AdminBoostModel,
    NestedInlineMixin,
    NestedStackedInline,
    NestedTabularInline,
    admin_boost_global_view,
    register_index_view,
)
from .decorators import admin_boost_action, admin_boost_link, admin_boost_view
from .middleware import CurrentUserMiddleware, get_current_user

try:
    from django_boosted.rest_framework.metadata import BoostedRestFrameworkMetadata
except ImportError:
    _drf_metadata = None
else:
    _drf_metadata = BoostedRestFrameworkMetadata

__version__ = version("django-boosted")

_MODEL_EXPORTS = frozenset(
    {
        "AuditMixin",
        "AuditUserField",
        "AuditUserValue",
        "format_audit_user",
    }
)


def __getattr__(name):
    """Load model exports on demand so import does not touch the app registry."""
    if name not in _MODEL_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import models

    return getattr(models, name)


__all__ = [
    "AdminBoostFormat",
    "AdminBoostModel",
    "AuditMixin",
    "AuditUserField",
    "AuditUserValue",
    "CurrentUserMiddleware",
    "NestedInlineMixin",
    "NestedStackedInline",
    "NestedTabularInline",
    "admin_boost_action",
    "admin_boost_global_view",
    "admin_boost_link",
    "admin_boost_view",
    "format_audit_user",
    "get_current_user",
    "register_index_view",
]

if _drf_metadata is not None:
    __all__.append(_drf_metadata.__name__)
