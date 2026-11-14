from __future__ import annotations

from collections.abc import Callable


def has_configured_permission(
    model_admin,
    request,
    permission: str | Callable | None,
    obj=None,
) -> bool:
    if callable(permission):
        return bool(permission(request))

    if permission in (None, "view"):
        return model_admin.has_view_permission(request, obj)
    if permission == "add":
        return model_admin.has_add_permission(request)
    if permission == "change":
        return model_admin.has_change_permission(request, obj)
    if permission == "delete":
        return model_admin.has_delete_permission(request, obj)

    user = getattr(request, "user", None)
    if not user:
        return False
    codename = permission
    if "." not in codename:
        codename = f"{model_admin.model._meta.app_label}.{codename}"
    return bool(user.has_perm(codename, obj) or user.has_perm(codename))


def requires_change_permission(permission: str | Callable | None) -> bool:
    return permission in (None, "view")
