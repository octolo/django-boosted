"""ModelAdmin mixin for django-boosted."""

from __future__ import annotations

import copy

from django.contrib import messages
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import unquote
from django.urls import path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _

from .fieldsets import add_to_fieldset, remove_from_fieldset
from .format import (
    boolean_icon_html,
    format_label,
    format_status,
    format_with_help_text,
)
from .inlines import (
    active_nested_formsets,
    extend_nested_formsets,
    nested_inline_formsets,
)
from .tools import (
    get_boost_list_links,
    get_boost_list_tools,
    get_boost_object_links,
    get_boost_object_tools,
    get_boost_view_config,
    get_boost_view_names,
)
from .views import ViewGenerator, setup_boost_views


class AdminBoostFormat:
    """Admin format mixin."""

    format_label = staticmethod(format_label)
    format_status = staticmethod(format_status)
    format_with_help_text = staticmethod(format_with_help_text)
    boolean_icon_html = staticmethod(boolean_icon_html)


class AdminBoostModel(ModelAdmin, AdminBoostFormat):
    change_form_template = "admin_boost/change_form.html"
    change_list_template = "admin_boost/change_list.html"
    boost_views: tuple[str, ...] = ()

    class Media:
        css = {
            "all": ("admin_boost/admin_boost.css",),
        }

    add_to_fieldset = add_to_fieldset
    remove_from_fieldset = remove_from_fieldset
    get_boost_view_names = get_boost_view_names
    get_boost_view_config = get_boost_view_config
    get_boost_object_tools = get_boost_object_tools
    get_boost_list_tools = get_boost_list_tools
    get_boost_object_links = get_boost_object_links
    get_boost_list_links = get_boost_list_links

    def get_urls(self):
        urls = super().get_urls()
        boost_urls = []
        for view_name in self.get_boost_view_names():
            view = getattr(self, view_name, None)
            config = self.get_boost_view_config(view_name)
            if not view or not config:
                continue

            path_fragment = config.get("path_fragment") or view_name.replace("_", "-")
            requires_object = config.get("requires_object", False)

            opts = self.model._meta
            path_name = f"{opts.app_label}_{opts.model_name}_{view_name}"
            if requires_object:
                boost_urls.append(
                    path(
                        f"<path:object_id>/{path_fragment}/",
                        self.admin_site.admin_view(view),
                        name=path_name,
                    )
                )
            else:
                boost_urls.append(
                    path(
                        f"{path_fragment}/",
                        self.admin_site.admin_view(view),
                        name=path_name,
                    )
                )
        return boost_urls + urls

    def __init__(self, *args, **kwargs):
        if hasattr(self, "fieldsets") and self.fieldsets is not None:
            self.fieldsets = copy.deepcopy(self.fieldsets)  # type: ignore[misc]
        if hasattr(self, "change_fieldsets"):
            self.change_fieldsets()
        super().__init__(*args, **kwargs)
        view_generator = ViewGenerator(self)
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            func = getattr(attr, "__func__", attr)
            if hasattr(func, "_admin_boost_view_config"):
                self.boost_views += (func._admin_boost_view_config["name"],)
        setup_boost_views(self, view_generator)

    def _create_formsets(self, request, obj, change):
        """Create root inline formsets and any nested descendant formsets."""
        formsets, inline_instances = super()._create_formsets(request, obj, change)  # type: ignore[misc]
        return extend_nested_formsets(self, request, obj, formsets, inline_instances)

    def get_inline_formsets(self, request, formsets, inline_instances, obj=None):
        """Return root inline wrappers, with descendants attached to parents."""
        nested = nested_inline_formsets(self, request, formsets, inline_instances, obj)
        if nested is None:
            return super().get_inline_formsets(request, formsets, inline_instances, obj)
        return nested

    def save_related(self, request, form, formsets, change):
        """Save related objects, skipping descendants of inactive ancestors."""
        active = active_nested_formsets(formsets)
        super().save_related(
            request,
            form,
            formsets if active is None else active,
            change,
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        items = list(extra_context.get("object_tools_items") or [])
        items.extend(self.get_boost_list_tools(request))
        items.extend(self.get_boost_list_links(request))
        extra_context["object_tools_items"] = items
        return super().changelist_view(request, extra_context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = None
        if object_id:
            obj = self.get_object(request, unquote(object_id))
            items = list(extra_context.get("object_tools_items") or [])
            items.extend(self.get_boost_object_tools(request, object_id))
            if obj is not None:
                items.extend(self.get_boost_object_links(request, obj))
            extra_context["object_tools_items"] = items

        if "submit_actions" not in extra_context:
            extra_context["submit_actions"] = self.get_submit_actions(request, obj)

        if request.method == "POST":
            custom_response = self._response_for_posted_action(
                request, object_id, extra_context.get("submit_actions", {})
            )
            if custom_response is not None:
                return custom_response

        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context,
        )

    def _response_for_posted_action(self, request, object_id, submit_actions):
        django_actions = {
            "_save",
            "_saveasnew",
            "_addanother",
            "_continue",
            "_saveas",
            "_save_and_continue",
        }
        for action_name in submit_actions:
            if action_name not in request.POST or action_name in django_actions:
                continue
            custom_response = self.handle_custom_action(action_name, request, object_id)
            if custom_response is not None:
                return custom_response
            return self._redirect_after_custom_action(request, object_id)
        return None

    def _redirect_after_custom_action(self, request, object_id):
        from django.shortcuts import redirect

        url = request.build_absolute_uri(request.path)
        if url_has_allowed_host_and_scheme(url, allowed_hosts=request.get_host()):
            redirect_url = request.path
        else:
            opts = self.model._meta
            redirect_url = reverse(
                f"admin:{opts.app_label}_{opts.model_name}_change",
                args=[object_id] if object_id else [],
                current_app=self.admin_site.name,
            )
        return redirect(redirect_url)

    def handle_custom_action(self, action_name, request, object_id=None):
        """Handle custom form actions. Override handle_<action_name>."""
        handler_method = getattr(self, f"handle_{action_name}", None)
        if handler_method:
            return handler_method(request, object_id)

        messages.warning(
            request,
            _(
                "Action '%(action)s' is defined but no handler method "
                "'handle_%(action)s' exists."
            )
            % {"action": action_name},
        )
        return None

    def get_action_permission(self, request, action, obj=None):
        perm = f"has_{action}_permission"
        if hasattr(self, perm):
            perm_method = getattr(self, perm)
            if callable(perm_method):
                return perm_method(request, obj)
            return perm_method
        return super().has_change_permission(request, obj)

    def get_submit_actions(self, request, obj=None):
        """Return submit actions from changeform_actions and decorators."""
        changeform_actions = dict(getattr(self, "changeform_actions", None) or {})
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            config = getattr(attr, "_changeform_action_config", None)
            if config:
                changeform_actions[config["name"]] = config["label"]
        actions_enable = {}
        for action_name, action_label in changeform_actions.items():
            perm = self.get_action_permission(request, action_name, obj)
            handle = hasattr(self, f"handle_{action_name}")
            if perm and handle:
                actions_enable[action_name] = action_label
        return actions_enable
