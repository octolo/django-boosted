"""Global boosted admin views used to exercise the admin index panel and the
view generators through the Django admin interface.

Registered at startup via ``DJANGO_BOOSTED_VIEW_MODULES``.
"""

from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.db.models.fields.related import ForeignKey, ManyToOneRel
from django.urls import reverse

from django_boosted import AdminBoostFormat, admin_boost_global_view
from tests.app.forms import CountryForm
from tests.app.models import Alphabet, Country

User = get_user_model()


def _raw_id_widget(model: type[Model], field_name: str) -> ForeignKeyRawIdWidget:
    field = model._meta.get_field(field_name)
    remote_field = getattr(field, "remote_field", None)
    if not isinstance(field, ForeignKey) or not isinstance(remote_field, ManyToOneRel):
        raise TypeError(f"{model.__name__}.{field_name} is not a foreign key")
    return ForeignKeyRawIdWidget(remote_field, admin.site)


class GlobalActionForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=_raw_id_widget(LogEntry, "user"),
    )
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        widget=_raw_id_widget(Alphabet, "country"),
    )


@admin_boost_global_view("adminform", "Global action")
def global_action_view(request, form=None):
    if form is not None:  # valid POST
        return {"redirect_url": reverse("admin:index")}
    return {"form": GlobalActionForm()}


@admin_boost_global_view("adminform", "Global renamed")
def global_renamed_view(request, form=None):
    if form is not None:  # valid POST
        return {"redirect_url": reverse("admin:index")}
    return {"form": GlobalActionForm(), "save_label": "Run it"}


@admin.display(description="Name label")
def country_name_label(country):
    return AdminBoostFormat.format_label(country.name, "success")


@admin.display(description="Tag")
def country_tag_label(country):
    return AdminBoostFormat.format_label("active", "danger", size="small")


@admin_boost_global_view("list", "Global labels")
def global_labels_view(request):
    # list_display must use callables here: plain field-name strings resolve
    # against the virtual host model (BoostedView), not the queryset's model.
    return {
        "queryset": Country.objects.all(),
        "list_display": [country_name_label, country_tag_label],
    }


@admin_boost_global_view("adminform", "Global multi")
def global_multi_view(request, form=None):
    if form is not None:  # valid POST
        return {"redirect_url": reverse("admin:index")}
    return {
        "form": GlobalActionForm(),
        "save_buttons": [
            {"name": "_apply", "label": "Apply", "class": "success"},
            {"name": "_danger", "label": "Delete", "class": "danger"},
        ],
    }


BUTTON_COLORS = [
    "default",
    "success",
    "info",
    "warning",
    "danger",
    "primary",
    "secondary",
]


@admin_boost_global_view("adminform", "Global colors")
def global_colors_view(request, form=None):
    if form is not None:  # valid POST
        return {"redirect_url": reverse("admin:index")}
    return {
        "form": GlobalActionForm(),
        "save_buttons": [
            {"name": f"_{color}", "label": color.capitalize(), "class": color}
            for color in BUTTON_COLORS
        ],
    }


class ReadonlyDemoForm(forms.Form):
    name = forms.CharField()
    token = forms.CharField(required=False)
    url = forms.CharField(required=False)


@admin_boost_global_view("adminform", "Global readonly")
def global_readonly_view(request, form=None):
    readonly = ["token", "url"]
    if form is not None:
        return {
            "form": ReadonlyDemoForm(
                initial={
                    "name": form.cleaned_data["name"],
                    "token": "secret-token",
                    "url": "https://example.com/hook",
                }
            ),
            "readonly_fields": readonly,
        }
    return {"form": ReadonlyDemoForm(), "readonly_fields": readonly}


@admin_boost_global_view("adminform", "Global readonly model")
def global_readonly_model_view(request, form=None):
    if form is not None:
        return {
            "form": CountryForm(instance=Country(name=form.cleaned_data["name"])),
            "readonly_fields": ["name"],
        }
    return {"form": CountryForm(), "readonly_fields": ["name"]}


@admin_boost_global_view("list", "Global countries")
def global_countries_view(request):
    return {"queryset": Country.objects.all()}
