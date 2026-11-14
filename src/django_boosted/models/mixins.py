"""Model mixins for django-boosted."""

from django.conf import settings
from django.db import models

from django_boosted.models.fields import AuditUserField

FORMAT_FIELDS = getattr(
    settings, "DJANGO_BOOSTED_AUDIT_USER_FORMAT_FIELDS", ("pk", "username")
)
SEPARATOR = getattr(settings, "DJANGO_BOOSTED_AUDIT_USER_SEPARATOR", "_")


class AuditMixin(models.Model):
    """Add created and updated user and timestamp fields.

    created_by and updated_by store a concatenation of user attributes.
    Default format: ('pk', 'username') joined with '_'.
    Override audit_user_format and audit_user_separator on the model.
    """

    created_by = AuditUserField(
        format_fields=FORMAT_FIELDS, separator=SEPARATOR, mode="created"
    )
    updated_by = AuditUserField(
        format_fields=FORMAT_FIELDS, separator=SEPARATOR, mode="updated"
    )
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, null=True, blank=True
    )
    updated_at: models.DateTimeField = models.DateTimeField(
        auto_now=True, null=True, blank=True
    )

    class Meta:
        abstract = True
