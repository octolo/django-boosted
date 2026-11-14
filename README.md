# django-boosted

Lightweight helpers to extend Django’s admin with extra views, custom forms, and the matching UI affordances (object tools, permissions, standard responses).

## Features

- **`@admin_boost_view` decorator** – fetches the target object, checks permissions, and builds the default context before rendering your template.
- **`AdminBoostModel`** – registers custom URLs, protects them with `admin_site.admin_view`, and injects extra object-tool buttons into the change form.
- **`AuditMixin`** – adds `created_by`, `updated_by`, `created_at`, `updated_at` with automatic user tracking via middleware.
- **Additional templates** – a change form template that renders the injected buttons plus a simple “Hello” view as a teaching aid.

## Installation

```bash
pip install django-boosted
```

## Quick start

```python
# app/admin.py
from django.contrib import admin
from django_boosted import AdminBoostModel, admin_boost_view
from .models import Client


class ClientAdmin(AdminBoostModel):
    @admin_boost_view("message", "Say hello")
    def hello_view(self, request, obj):
        return {"message": f"Hello {obj}!"}


admin.site.register(Client, ClientAdmin)
```

With `APP_DIRS=True`, Django discovers the packaged templates automatically.

## Direct admin links

Use `@admin_boost_link` to add an object-tool button that points directly to an
existing URL, without creating an intermediate view:

```python
from django.urls import reverse
from django_boosted import AdminBoostModel, admin_boost_link


class CountryAdmin(AdminBoostModel):
    @admin_boost_link("Cities", permission="locations.view_city")
    def city_list_link(self, request, obj):
        url = reverse("admin:locations_city_changelist")
        return f"{url}?country__id__exact={obj.pk}"
```

Set `requires_object=False` to place a direct link in changelist tools instead.
The decorated method then receives only `request`.

## Object forms

```python
# app/admin.py
from django import forms
from django.contrib import admin
from django_boosted import AdminBoostModel, admin_boost_view
from .models import Company


class SyncFullGroupForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Company.objects.all())
    option = forms.ChoiceField(
        label="sync method",
        choices=[("method1", "Method 1"), ("method2", "Method 2")],
    )


class CompanyAdmin(AdminBoostModel):
    @admin_boost_view(
        "adminform",
        "Sync Full Group",
    )
    def sync_full_group_view(self, request, obj, form=None):
        if form is not None:
            group = form.cleaned_data["group"]
            option = form.cleaned_data["option"]
            # Process the validated values.
            return {"redirect_url": request.path}
        return {"form": SyncFullGroupForm()}


admin.site.register(Company, CompanyAdmin)
```

On GET, return a form. On a valid POST, the same function is called with the
bound form in the `form` argument. Model views require `change` permission for
POST requests unless a dedicated `permission` is configured.

## Global admin views & index panel

Register object-less admin views that reuse the existing view generators
(`adminform`, `form`, `confirm`, `message`, `list`, `json`, `redirect`) — you only
write the useful code that returns a form or a context dict, no template needed.
Registered views are listed in a "Boosted" box on the admin index page, right
before "Recent actions".

```python
# app/boosted_views.py  (or app/admin.py)
from django import forms
from django.contrib import messages
from django.urls import reverse
from django_boosted import admin_boost_global_view


class ResyncForm(forms.Form):
    mode = forms.ChoiceField(choices=[("fast", "Fast"), ("full", "Full")])


@admin_boost_global_view("adminform", "Resync all")
def resync_all(request, form=None):
    if form is not None:  # valid POST
        # ... global logic ...
        messages.success(request, "Resync started")
        return {"redirect_url": reverse("admin:index")}
    return {"form": ResyncForm()}
```

Discovery — the decorator runs only if its module is imported. django-boosted
imports, at startup:
- a conventional `boosted_views.py` module in each installed app (auto), and
- every module listed in `DJANGO_BOOSTED_VIEW_MODULES` (for files outside an app).

```python
# settings.py
DJANGO_BOOSTED_VIEW_MODULES = ["myproject.ops.boosted_views"]
```

Views defined in an app's `admin.py` also work, since Django already imports it.

Options: `path_fragment`, `template_name`, `permission` (a permission codename,
a `callable(request) -> bool`, or `None` for any staff user), `order`,
`show_in_index`. Use `register_index_view(label, url, ...)` to add a plain link
(e.g. `reverse_lazy(...)` to an existing admin view).

`adminform` views render the standard admin change-form "Save" button. To rename
it, return `save_label` in the context dict:

```python
@admin_boost_global_view("adminform", "Resync all")
def resync_all(request, form=None):
    if form is not None:
        return {"redirect_url": reverse("admin:index")}
    return {"form": ResyncForm(), "save_label": "Run resync"}
```

To render fields as Django admin readonly (plain text, not an input), return
`readonly_fields`. Works with a regular `Form` or a `ModelForm`. Include the
key on every return that still shows the form:

```python
@admin_boost_global_view("adminform", "Generate token")
def generate_token(request, form=None):
    if form is not None:
        return {
            "form": ResultForm(initial={"token": token, "url": url}),
            "readonly_fields": ["token", "url"],
        }
    return {"form": GenerateForm(), "readonly_fields": ["token", "url"]}
```

For several buttons (with a color class each), return `save_buttons`; inspect
`request.POST` to know which one was pressed. Available classes: `default`,
`success`, `info`, `warning`, `danger`, `primary`, `secondary`.

```python
@admin_boost_global_view("adminform", "Resync all")
def resync_all(request, form=None):
    if form is not None:
        if "_full" in request.POST:
            ...  # full resync
        return {"redirect_url": reverse("admin:index")}
    return {
        "form": ResyncForm(),
        "save_buttons": [
            {"name": "_fast", "label": "Fast", "class": "success"},
            {"name": "_full", "label": "Full", "class": "danger"},
        ],
    }
```

The box is wired via `admin.site.index_template`. If you use a custom `AdminSite`,
set `index_template = "admin_boost/index.html"` on it.

## Audit (created_by / updated_by)

1. Add `CurrentUserMiddleware` to `MIDDLEWARE` (after `AuthenticationMiddleware`):

```python
MIDDLEWARE = [
    ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    ...
    "django_boosted.middleware.CurrentUserMiddleware",
]
```

2. Use `AuditMixin` on your models:

```python
from django.db import models
from django_boosted import AuditMixin


class Article(AuditMixin, models.Model):
    title = models.CharField(max_length=200)
```

The mixin automatically sets `created_by` on first save and `updated_by` on each save when a user is authenticated.

`created_by` and `updated_by` use `AuditUserField`: auto-filled with configurable concatenation. Default: `('pk', 'username')` joined with `_`. Override `audit_user_format` and `audit_user_separator` on the model, or use the field directly:

```python
# Via mixin
class Article(AuditMixin, models.Model):
    audit_user_format = ("pk", "email")
    audit_user_separator = "-"


# Or use AuditUserField standalone
from django_boosted import AuditUserField


class Log(models.Model):
    editor = AuditUserField(format_fields=("pk", "username"), mode="updated")
```

**Settings**:
- `DJANGO_BOOSTED_AUDIT_USER_FALLBACK` — default value when no request user (migrations, commands, scripts). Example: `"robot_octolo"`. If not set, default is `None`.
- `DJANGO_BOOSTED_AUDIT_USER_FORMAT_FIELDS` — tuple of user attributes for the stored value. Default: `("pk", "username")`.
- `DJANGO_BOOSTED_AUDIT_USER_SEPARATOR` — separator between format fields. Default: `"_"`.

In templates or Python, `created_by` and `updated_by` return `AuditUserValue` (str subclass) with `admin_url`:

```python
obj.created_by  # "42-johndoe"
obj.created_by.admin_url  # "/admin/auth/user/42/change/"
```

## Settings inspection and secret fields

The settings admin is disabled by default because Django settings commonly
contain credentials. Superusers can opt in explicitly:

```python
DJANGO_BOOSTED_ENABLE_SETTINGS_ADMIN = True
```

Sensitive setting names are still excluded. `SecretCharField`,
`SecretTextField`, and `SecretJsonField` only mask values in the interface;
they do not encrypt data at rest or prevent a browser from reading an editable
field value.

## Development commands

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
python -m pytest --cov
python -m bandit -r src -c pyproject.toml
python -m pip_audit
```

## License

MIT — see the `LICENSE` file. Contributions welcome!
