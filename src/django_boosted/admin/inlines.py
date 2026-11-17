"""Recursive admin inlines built on Django's native inline classes."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from types import MethodType
from typing import Any, cast

from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.options import InlineModelAdmin
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.forms import Media
from django.forms.formsets import DELETION_FIELD_NAME
from django.forms.models import BaseInlineFormSet
from django.http import HttpRequest

# Wrapper permissions follow ModelAdmin.get_inline_formsets() in Django >=5.2,<6.
_NESTED_ASSETS = Media(
    css={"all": ("admin_boost/nested_inlines.css",)},
    js=("admin_boost/nested_inlines.js",),
)


@dataclass(slots=True)
class NestedFormsetMetadata:
    """Request-local relationship between a nested formset and its parent."""

    inline: InlineModelAdmin
    parent_form: Any
    parent_object: models.Model
    depth: int
    is_template: bool = False


class NestedInlineAdminFormSet(helpers.InlineAdminFormSet):
    """Inline wrapper that renders and loads media for nested descendants."""

    def __iter__(self) -> Iterator[helpers.InlineAdminForm]:
        rendered = list(super().__iter__())
        templates = getattr(self.formset, "_nested_template_admin_formsets", None)
        if templates and rendered and self.has_add_permission:
            rendered[-1].form.nested_inline_admin_formsets = list(templates)  # type: ignore[attr-defined]
        return iter(rendered)

    def inline_formset_data(self) -> str:
        data = json.loads(super().inline_formset_data())
        fields = {}
        for name, dependencies in self.prepopulated_fields.items():
            field = self.formset.empty_form.fields[name]
            fields[name] = {
                "dependencies": list(dependencies),
                "maxLength": field.max_length or 50,
                "allowUnicode": getattr(field, "allow_unicode", False),
            }
        data["options"]["prepopulatedFields"] = fields
        return json.dumps(data)

    @property
    def media(self) -> Media:
        media = super().media
        for form in self.formset.forms:
            media += _media_for(getattr(form, "nested_inline_admin_formsets", ()))
        media += _media_for(
            getattr(self.formset, "_nested_template_admin_formsets", ())
        )
        if getattr(self.formset, "has_nested_children", False):
            media += _NESTED_ASSETS
        return media


class NestedInlineMixin:
    """Add recursive inline classes to a Django inline.

    Child permission methods receive the direct parent object. A node that
    owns children must use this mixin; its leaves can stay native inlines.
    """

    inlines: list[type[InlineModelAdmin]] | tuple[type[InlineModelAdmin], ...] = ()

    def get_inlines(
        self,
        request: HttpRequest,
        obj: models.Model | None,
    ) -> list[type[InlineModelAdmin]] | tuple[type[InlineModelAdmin], ...]:
        """Return the child inline classes for one direct parent.

        Args:
            request: The current admin request.
            obj: The direct parent instance, when one exists.

        Returns:
            Configured inline classes. Override this to vary them per request
            or parent object.
        """
        return self.inlines

    def get_inline_instances(
        self,
        request: HttpRequest,
        obj: models.Model | None = None,
    ) -> list[InlineModelAdmin]:
        """Return the permitted direct child inline instances.

        Args:
            request: The current admin request.
            obj: The direct parent instance, when one exists.

        Returns:
            Instantiated child inlines that the user may view or edit.

        Raises:
            ImproperlyConfigured: The inline class graph contains a cycle.
        """
        return list(
            _iter_child_inlines(
                self,
                request,
                obj,
                (cast(type[InlineModelAdmin], type(self)),),
            )
        )


class NestedStackedInline(NestedInlineMixin, admin.StackedInline):
    """Stacked inline that can render and save nested inlines."""

    template = "admin_boost/edit_inline/stacked.html"


class NestedTabularInline(NestedInlineMixin, admin.TabularInline):
    """Tabular inline that can render and save nested inlines."""

    template = "admin_boost/edit_inline/tabular.html"


def extend_nested_formsets(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    obj: models.Model | None,
    formsets: list[Any],
    inline_instances: list[InlineModelAdmin],
) -> tuple[list[Any], list[InlineModelAdmin]]:
    """Append descendant formsets in parent-first order.

    Args:
        model_admin: Admin hosting the root change form.
        request: The current admin request.
        obj: Root object passed to Django's formset construction.
        formsets: Root formsets already created by Django.
        inline_instances: Inline instances matching ``formsets``.

    Returns:
        The original lists when no configured descendant exists. Otherwise,
        both lists include real descendant formsets and exclude empty-form
        templates.
    """
    if not any(isinstance(inline, NestedInlineMixin) for inline in inline_instances):
        return formsets, inline_instances
    flat_formsets: list[Any] = []
    flat_inlines: list[InlineModelAdmin] = []
    for formset, inline in zip(formsets, inline_instances, strict=True):
        flat_formsets.append(formset)
        flat_inlines.append(inline)
        if isinstance(inline, NestedInlineMixin):
            _populate_level(
                model_admin,
                request,
                formset,
                inline,
                (type(inline),),
                is_template=False,
                sink=(flat_formsets, flat_inlines),
            )
    if len(flat_formsets) == len(formsets):
        return formsets, inline_instances
    return flat_formsets, flat_inlines


def nested_inline_formsets(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    formsets: list[Any],
    inline_instances: list[InlineModelAdmin],
    obj: models.Model | None,
) -> list[NestedInlineAdminFormSet] | None:
    """Build nested admin wrappers, returning only the root level.

    Args:
        model_admin: Admin hosting the root change form.
        request: The current admin request.
        formsets: Flat real formsets, including descendants.
        inline_instances: Inline instances matching ``formsets``.
        obj: Root object being added or changed.

    Returns:
        ``None`` when the formsets have no nested metadata. Otherwise, the
        root wrappers with child wrappers attached to their parent forms.
    """
    if not _contains_nested(formsets):
        return None
    cache: dict[int, NestedInlineAdminFormSet] = {}
    roots: list[NestedInlineAdminFormSet] = []
    for formset, inline in zip(formsets, inline_instances, strict=True):
        if getattr(formset, "_nested_metadata", None) is not None:
            continue
        roots.append(
            _attach_admin_formset(model_admin, request, formset, inline, obj, cache)
        )
    return roots


def active_nested_formsets(formsets: Sequence[Any]) -> list[Any] | None:
    """Return formsets whose ancestor chain can be saved."""
    if not any(getattr(formset, "_nested_metadata", None) for formset in formsets):
        return None
    active = []
    for formset in formsets:
        if _has_inactive_ancestor(formset):
            _mark_formset_skipped(formset)
            continue
        active.append(formset)
    return active


def _ancestor_forms(formset: Any) -> Iterator[Any]:
    metadata = getattr(formset, "_nested_metadata", None)
    while metadata is not None and metadata.parent_form is not None:
        yield metadata.parent_form
        owning = getattr(metadata.parent_form, "_nested_owning_formset", None)
        metadata = getattr(owning, "_nested_metadata", None)


def _has_inactive_ancestor(formset: Any) -> bool:
    return any(
        _form_marked_for_deletion(form)
        or (form.instance._state.adding and not form.has_changed())
        for form in _ancestor_forms(formset)
    )


def _mark_formset_skipped(formset: Any) -> None:
    formset.new_objects = []
    formset.changed_objects = []
    formset.deleted_objects = []


def _contains_nested(formsets: Sequence[Any]) -> bool:
    return any(
        getattr(formset, "_nested_metadata", None) is not None
        or getattr(formset, "has_nested_children", False)
        for formset in formsets
    )


def _iter_child_inlines(
    parent_inline: NestedInlineMixin,
    request: HttpRequest,
    parent_obj: models.Model | None,
    stack: tuple[type[InlineModelAdmin], ...],
) -> Iterator[InlineModelAdmin]:
    """Yield visible children using Django's inline permission filter.

    Mirrors ``ModelAdmin.get_inline_instances()`` for Django >=5.2,<6. Calling
    that method directly would evaluate ``get_inlines()`` twice and could hide
    a cycle behind a permission check, so the short filter stays explicit.
    """
    for inline_class in parent_inline.get_inlines(request, parent_obj):
        _ensure_acyclic(stack, inline_class)
        parent = cast(InlineModelAdmin, parent_inline)
        inline = inline_class(parent.model, parent.admin_site)
        _bind_direct_parent_permission(inline, parent_obj)
        if not _inline_is_visible(inline, request, parent_obj):
            continue
        if request is not None and not inline.has_add_permission(request, parent_obj):
            inline.max_num = 0
        yield inline


def _bind_direct_parent_permission(
    inline: InlineModelAdmin,
    parent_obj: models.Model | None,
) -> None:
    permission = inline.has_view_or_change_permission

    def with_direct_parent(
        self: InlineModelAdmin,
        request: HttpRequest,
        obj: models.Model | None = None,
    ) -> bool:
        return permission(request, parent_obj if obj is None else obj)

    inline.has_view_or_change_permission = MethodType(  # type: ignore[method-assign]
        with_direct_parent, inline
    )


def _ensure_acyclic(
    stack: tuple[type[InlineModelAdmin], ...],
    inline_class: type[InlineModelAdmin],
) -> None:
    if inline_class not in stack:
        return
    path = " -> ".join(item.__qualname__ for item in (*stack, inline_class))
    raise ImproperlyConfigured(f"Cyclic nested inlines: {path}")


def _inline_is_visible(
    inline: InlineModelAdmin,
    request: HttpRequest | None,
    parent_obj: models.Model | None,
) -> bool:
    if request is None:
        return True
    return bool(
        inline.has_view_or_change_permission(request, parent_obj)
        or inline.has_add_permission(request, parent_obj)
        or inline.has_delete_permission(request, parent_obj)
    )


def _populate_level(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    formset: Any,
    inline: InlineModelAdmin,
    stack: tuple[type[InlineModelAdmin], ...],
    *,
    is_template: bool,
    sink: tuple[list[Any], list[InlineModelAdmin]] | None,
    depth: int = 1,
) -> None:
    if not isinstance(inline, NestedInlineMixin):
        return
    # Evaluate the cached forms now so later saves reuse these instances.
    forms = formset.forms
    for form in forms:
        form._nested_owning_formset = formset
        children = _build_children(
            model_admin,
            request,
            inline,
            form,
            stack,
            is_template=is_template,
            sink=sink,
            depth=depth,
        )
        form._nested_child_formsets = children
        if children:
            formset.has_nested_children = True
    templates = _build_children(
        model_admin,
        request,
        inline,
        formset.empty_form,
        stack,
        is_template=True,
        sink=None,
        depth=depth,
    )
    formset._nested_template_formsets = templates
    if templates:
        formset.has_nested_children = True


def _build_children(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    parent_inline: NestedInlineMixin,
    parent_form: Any,
    stack: tuple[type[InlineModelAdmin], ...],
    *,
    is_template: bool,
    sink: tuple[list[Any], list[InlineModelAdmin]] | None,
    depth: int,
) -> list[Any]:
    counters: dict[str, int] = {}
    children: list[Any] = []
    for child in _iter_child_inlines(
        parent_inline, request, parent_form.instance, stack
    ):
        formset = _make_formset(
            model_admin,
            request,
            parent_form,
            child,
            counters,
            is_template=is_template,
            depth=depth,
        )
        children.append(formset)
        if sink is not None and not is_template:
            sink[0].append(formset)
            sink[1].append(child)
        _populate_level(
            model_admin,
            request,
            formset,
            child,
            (*stack, type(child)),
            is_template=is_template,
            sink=sink,
            depth=depth + 1,
        )
    return children


def _make_formset(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    parent_form: Any,
    inline: InlineModelAdmin,
    counters: dict[str, int],
    *,
    is_template: bool,
    depth: int,
) -> Any:
    parent = parent_form.instance
    formset_class = _with_inactive_ancestor_behavior(
        inline.get_formset(request, parent)
    )
    prefix = _scoped_prefix(
        counters, parent_form.prefix, formset_class.get_default_prefix()
    )
    params = model_admin.get_formset_kwargs(request, parent, inline, prefix)
    if is_template:
        params.pop("data", None)
        params.pop("files", None)
        params.pop("save_as_new", None)
    formset = formset_class(**params)
    metadata = NestedFormsetMetadata(
        inline=inline,
        parent_form=parent_form,
        parent_object=parent,
        depth=depth,
        is_template=is_template,
    )
    formset._nested_metadata = metadata  # type: ignore[attr-defined]
    formset.boosted_is_nested = True  # type: ignore[attr-defined]
    if not is_template:
        _relax_view_only_forms(request, parent, inline, formset)
    return formset


def _scoped_prefix(counters: dict[str, int], parent_prefix: str, default: str) -> str:
    base = f"{parent_prefix}-{default}" if parent_prefix else default
    counters[base] = counters.get(base, 0) + 1
    if counters[base] == 1 and base:
        return base
    return f"{base}-{counters[base]}"


def _with_inactive_ancestor_behavior(
    formset_class: type[BaseInlineFormSet],
) -> type[BaseInlineFormSet]:
    class DeletedAncestorInlineFormSet(formset_class):  # type: ignore[misc, valid-type]
        def is_valid(self) -> bool:
            if _has_inactive_ancestor(self):
                _mark_formset_skipped(self)
                return True
            return super().is_valid()

    return DeletedAncestorInlineFormSet


def _relax_view_only_forms(
    request: HttpRequest,
    parent: models.Model,
    inline: InlineModelAdmin,
    formset: Any,
) -> None:
    """Mirror the view-only bypass in Django 5.2 ``_create_formsets()``.

    The nested copy uses the direct parent, the descendant prefix, and the
    child delete permission. Django's root method cannot construct these
    formsets or distinguish their parents.
    """
    if inline.has_change_permission(request, parent):
        return
    for index, form in enumerate(formset.initial_forms):
        if _posted_deletion(request, parent, formset, index, inline):
            continue
        form._errors = {}
        form.cleaned_data = form.initial


def _posted_deletion(
    request: HttpRequest,
    parent: models.Model,
    formset: Any,
    index: int,
    inline: InlineModelAdmin,
) -> bool:
    key = f"{formset.prefix}-{index}-{DELETION_FIELD_NAME}"
    return inline.has_delete_permission(request, parent) and key in request.POST


def _form_marked_for_deletion(form: Any) -> bool:
    owning = getattr(form, "_nested_owning_formset", None)
    if owning is not None and not owning.can_delete:
        return False
    cleaned = getattr(form, "cleaned_data", None)
    if isinstance(cleaned, dict) and DELETION_FIELD_NAME in cleaned:
        return bool(cleaned[DELETION_FIELD_NAME])
    key = f"{form.prefix}-{DELETION_FIELD_NAME}"
    return bool(getattr(form, "is_bound", False) and key in form.data)


def _attach_admin_formset(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    formset: Any,
    inline: InlineModelAdmin,
    root_obj: models.Model | None,
    cache: dict[int, NestedInlineAdminFormSet],
) -> NestedInlineAdminFormSet:
    cached = cache.get(id(formset))
    if cached is not None:
        return cached
    wrapper = _build_admin_formset(
        model_admin,
        request,
        formset,
        inline,
        root_obj,
        _direct_parent(formset, root_obj),
    )
    cache[id(formset)] = wrapper
    for form in formset.forms:
        form.nested_inline_admin_formsets = _attach_children(
            model_admin,
            request,
            getattr(form, "_nested_child_formsets", ()),
            root_obj,
            cache,
        )
    formset._nested_template_admin_formsets = _attach_children(
        model_admin,
        request,
        getattr(formset, "_nested_template_formsets", ()),
        root_obj,
        cache,
    )
    return wrapper


def _attach_children(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    formsets: Sequence[Any],
    root_obj: models.Model | None,
    cache: dict[int, NestedInlineAdminFormSet],
) -> list[NestedInlineAdminFormSet]:
    wrappers = []
    for formset in formsets:
        inline = formset._nested_metadata.inline
        wrappers.append(
            _attach_admin_formset(
                model_admin, request, formset, inline, root_obj, cache
            )
        )
    return wrappers


def _direct_parent(formset: Any, root_obj: models.Model | None) -> models.Model | None:
    metadata = getattr(formset, "_nested_metadata", None)
    if metadata is None:
        return root_obj
    return metadata.parent_object


def _build_admin_formset(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    formset: Any,
    inline: InlineModelAdmin,
    root_obj: models.Model | None,
    parent_obj: models.Model | None,
) -> NestedInlineAdminFormSet:
    """Build one inline wrapper.

    Mirrors the per-formset body of Django 5.2 ``ModelAdmin.get_inline_formsets()``
    for Django >=5.2,<6. Native delegation is impossible: root editability and
    direct-parent permissions require two different objects, while Django's
    method accepts only one. Passing a child as ``obj`` would also evaluate the
    root admin's permissions against the wrong model.
    """
    editable = _root_is_editable(model_admin, request, root_obj)
    if editable:
        permissions = _inline_permissions(inline, request, parent_obj)
    else:
        permissions = (False, False, False)
        formset.extra = 0
        formset.max_num = 0
    return NestedInlineAdminFormSet(
        inline,
        formset,
        list(inline.get_fieldsets(request, parent_obj)),
        dict(inline.get_prepopulated_fields(request, parent_obj)),
        list(inline.get_readonly_fields(request, parent_obj)),
        model_admin=model_admin,
        has_add_permission=permissions[0],
        has_change_permission=permissions[1],
        has_delete_permission=permissions[2],
        has_view_permission=inline.has_view_permission(request, parent_obj),
    )


def _root_is_editable(
    model_admin: admin.ModelAdmin,
    request: HttpRequest,
    root_obj: models.Model | None,
) -> bool:
    if root_obj is None or root_obj._state.adding:
        return model_admin.has_add_permission(request)
    return model_admin.has_change_permission(request, root_obj)


def _inline_permissions(
    inline: InlineModelAdmin,
    request: HttpRequest,
    parent_obj: models.Model | None,
) -> tuple[bool, bool, bool]:
    return (
        inline.has_add_permission(request, parent_obj),
        inline.has_change_permission(request, parent_obj),
        inline.has_delete_permission(request, parent_obj),
    )


def _media_for(wrappers: Sequence[NestedInlineAdminFormSet]) -> Media:
    media = Media()
    for wrapper in wrappers:
        media += wrapper.media
    return media
