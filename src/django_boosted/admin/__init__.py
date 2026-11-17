"""Admin module for django-boosted."""

from .index import admin_boost_global_view, get_index_views, register_index_view
from .inlines import NestedInlineMixin, NestedStackedInline, NestedTabularInline
from .model import AdminBoostFormat, AdminBoostModel

__all__ = [
    "AdminBoostFormat",
    "AdminBoostModel",
    "NestedInlineMixin",
    "NestedStackedInline",
    "NestedTabularInline",
    "admin_boost_global_view",
    "get_index_views",
    "register_index_view",
]
