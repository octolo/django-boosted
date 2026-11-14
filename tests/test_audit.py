from types import SimpleNamespace

from django_boosted.middleware.current_user import (
    CurrentUserMiddleware,
    get_current_user,
)
from django_boosted.models import fields
from django_boosted.models.fields import AuditUserField, AuditUserValue


def test_current_user_middleware_clears_user_after_response():
    user = SimpleNamespace(username="alice")
    request = SimpleNamespace(user=user)
    middleware = CurrentUserMiddleware(lambda request: get_current_user())

    assert middleware(request) is user
    assert get_current_user() is None


def test_audit_user_field_records_current_user(monkeypatch):
    user = SimpleNamespace(pk=7, username="alice", is_authenticated=True)
    monkeypatch.setattr(fields, "get_current_user", lambda: user)
    field = AuditUserField()
    field.set_attributes_from_name("updated_by")

    value = field.pre_save(SimpleNamespace(updated_by=None), add=True)

    assert isinstance(value, AuditUserValue)
    assert value == "7_alice"


def test_created_audit_user_is_not_overwritten(monkeypatch):
    user = SimpleNamespace(pk=8, username="bob", is_authenticated=True)
    monkeypatch.setattr(fields, "get_current_user", lambda: user)
    field = AuditUserField(mode="created")
    field.set_attributes_from_name("created_by")
    instance = SimpleNamespace(created_by=AuditUserValue("7_alice", pk=7))

    assert field.pre_save(instance, add=False) == "7_alice"
