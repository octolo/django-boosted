"""Admin form view generator for django-boosted."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

from django.contrib.admin.helpers import AdminErrorList, AdminForm
from django.forms import Form, ModelForm
from django.http import HttpResponse, HttpResponseBase
from django.template.response import TemplateResponse

from .base import ViewGenerator, redirect_to_allowed_url

_NO_FORM = object()
_SAVE_BUTTON_CLASSES = {
    "default",
    "success",
    "info",
    "warning",
    "danger",
    "primary",
    "secondary",
}


def _readonly_names(payload) -> tuple:
    if isinstance(payload, dict):
        return tuple(payload.get("readonly_fields") or ())
    return ()


def _adapt_plain_form(form, readonly, model_admin) -> None:
    """Give a plain form the ModelForm surface AdminReadonlyField expects."""
    if isinstance(form, ModelForm):
        return
    form._meta = SimpleNamespace(
        labels={name: field.label for name, field in form.fields.items()},
        help_texts={name: field.help_text or "" for name, field in form.fields.items()},
        model=model_admin.model,
    )
    form.instance = model_admin.model()
    for name in readonly:
        if name in form.fields:
            setattr(form.instance, name, form[name].value() or "")


def _adminform(form, payload, model_admin):
    """Build Django's AdminForm, honoring ``readonly_fields`` from the payload."""
    readonly = _readonly_names(payload)
    if readonly:
        _adapt_plain_form(form, readonly, model_admin)

    return AdminForm(
        form,
        [(None, {"fields": list(form.fields.keys())})],
        {},
        readonly_fields=readonly,
        model_admin=model_admin,
    )


def _call_view(
    view_func,
    request,
    obj,
    requires_object,
    args,
    kwargs,
    *,
    form=_NO_FORM,
):
    call_args = (request, obj, *args) if requires_object else (request, *args)
    call_kwargs = dict(kwargs)
    if form is not _NO_FORM:
        call_kwargs["form"] = form
    return view_func(*call_args, **call_kwargs)


def _bind_form(form, request):
    if isinstance(form, ModelForm):
        return form.__class__(
            request.POST,
            request.FILES,
            instance=getattr(form, "instance", None),
        )
    return form.__class__(request.POST, request.FILES)


def _process_post(
    request,
    view_func,
    obj,
    form,
    payload,
    requires_object,
    args,
    kwargs,
):
    if request.method != "POST":
        return form, payload, None

    form = _bind_form(form, request)
    if not form.is_valid():
        if isinstance(payload, dict):
            payload["form"] = form
        return form, payload, None

    result = _call_view(
        view_func,
        request,
        obj,
        requires_object,
        args,
        kwargs,
        form=form,
    )
    if isinstance(result, (HttpResponse, HttpResponseBase)):
        return form, payload, result
    if isinstance(result, dict) and "redirect_url" in result:
        return form, result, redirect_to_allowed_url(request, result["redirect_url"])
    if isinstance(result, dict):
        return result.get("form", form), result, None
    return form, payload, None


def _permission_value(payload, key, default):
    if isinstance(payload, dict) and key in payload:
        return payload[key]
    return default


def _form_from_payload(payload):
    if isinstance(payload, dict):
        return payload.get("form")
    if isinstance(payload, Form):
        return payload
    return None


def _sanitize_save_buttons(buttons):
    sanitized = []
    for button in buttons or []:
        item = dict(button)
        if item.get("class") not in _SAVE_BUTTON_CLASSES:
            item["class"] = "default"
        sanitized.append(item)
    return sanitized


def _merge_payload_context(context, payload, form, model_admin):
    if not isinstance(payload, dict):
        return

    new_form = payload.get("form", form)
    if new_form != form:
        form = new_form
        context["adminform"] = _adminform(form, payload, model_admin)
        context["errors"] = AdminErrorList(form, [])
        context["media"] = model_admin.media + form.media

    excluded_keys = {
        "form",
        "has_add_permission",
        "has_change_permission",
        "has_delete_permission",
    }
    extra_context = {k: v for k, v in payload.items() if k not in excluded_keys}
    if "save_buttons" in extra_context:
        extra_context["save_buttons"] = _sanitize_save_buttons(
            extra_context["save_buttons"]
        )
    context.update(extra_context)


class AdminFormViewMixin(ViewGenerator):
    """Mixin for admin form view generation."""

    def generate_admin_custom_adminform_view(
        self,
        view_func: Callable,
        label: str,
        *,
        template_name: str = "admin_boost/change_form.html",
        path_fragment: str | None = None,
        requires_object: bool = True,
        permission: str = "view",
        hidden: bool = False,
    ) -> Callable:
        def wrapper(request, object_id=None, *args, **kwargs):
            obj, redirect = self._check_permissions(
                request,
                object_id if requires_object else None,
                permission=permission,
                require_change=request.method == "POST",
            )
            if redirect:
                return redirect

            payload = _call_view(
                view_func,
                request,
                obj,
                requires_object,
                args,
                kwargs,
            )

            if isinstance(payload, (HttpResponse, HttpResponseBase)):
                return payload

            form = _form_from_payload(payload)

            if form is None:
                raise ValueError(
                    f"{view_func.__name__} must return a form or a dict with a "
                    "'form' key"
                )

            form, payload, response = _process_post(
                request,
                view_func,
                obj,
                form,
                payload,
                requires_object,
                args,
                kwargs,
            )
            if response is not None:
                return response

            context = self._build_base_context(request, obj)
            context["title"] = label

            adminform = _adminform(form, payload, self.model_admin)

            # Get permission values from payload or model_admin defaults
            has_add_perm = _permission_value(
                payload,
                "has_add_permission",
                self.model_admin.has_add_permission(request),
            )
            has_change_perm = _permission_value(
                payload,
                "has_change_permission",
                self.model_admin.has_change_permission(request, obj),
            )
            has_delete_perm = _permission_value(
                payload,
                "has_delete_permission",
                self.model_admin.has_delete_permission(request, obj),
            )

            context.update(
                {
                    "adminform": adminform,
                    "errors": AdminErrorList(form, []),
                    "inline_admin_formsets": [],
                    "inline_admin_formset": [],
                    # Required for Django 4.2+
                    "has_editable_inline_admin_formsets": False,
                    "media": self.model_admin.media + form.media,
                    "preserved_filters": "",
                    "prepopulated_fields": {},
                    "prepopulated_fields_json": "[]",
                    "has_view_permission": self.model_admin.has_view_permission(
                        request, obj
                    ),
                    "has_add_permission": has_add_perm,
                    "has_change_permission": has_change_perm,
                    "has_delete_permission": has_delete_perm,
                    "show_save": True,
                    "show_save_and_continue": False,
                    "show_save_and_add_another": False,
                    "show_delete": False,
                    "show_close": False,
                    "add": False,
                    "change": True,
                    "is_popup": False,
                    "save_as": False,
                    "save_on_top": False,
                }
            )

            _merge_payload_context(context, payload, form, self.model_admin)

            request.current_app = self.model_admin.admin_site.name
            return TemplateResponse(request, template_name, context)

        path_fragment = path_fragment or view_func.__name__.replace("_", "-")
        wrapper._admin_boost_config = {  # type: ignore[attr-defined]
            "label": label,
            "path_fragment": path_fragment,
            "permission": permission,
            "view_type": "adminform",
            "requires_object": requires_object,
            "show_in_object_tools": not hidden,
        }
        return wrapper
