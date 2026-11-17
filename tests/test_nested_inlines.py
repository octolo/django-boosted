"""Tests for recursively nested admin inlines."""

from __future__ import annotations

import importlib
import json
import re
import secrets
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, models
from django.forms import ModelForm
from django.forms.models import BaseInlineFormSet
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext, isolate_apps
from django.urls import clear_url_caches, reverse, set_urlconf

from django_boosted import (
    AdminBoostModel,
    NestedInlineMixin,
    NestedStackedInline,
    NestedTabularInline,
)
from tests.app.models import Alphabet, City, Country


class _Inputs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        data = dict(attrs)
        name = data.get("name")
        if not name:
            return
        if data.get("type") == "checkbox":
            if "checked" not in data:
                return
            self.fields[name] = data.get("value") or "on"
            return
        self.fields[name] = data.get("value") or ""


def _inputs(html: str) -> dict[str, str]:
    parser = _Inputs()
    parser.feed(html)
    return parser.fields


def _reload_urls() -> None:
    clear_url_caches()
    import tests.urls

    importlib.reload(tests.urls)
    set_urlconf(None)


def _submit(client: Client, url: str, updates: dict[str, str]) -> Any:
    response = client.get(url)
    assert response.status_code == 200
    payload = _inputs(response.content.decode())
    payload.update(updates)
    return client.post(url, payload)


def _request(user: Any, method: str = "get") -> Any:
    factory = RequestFactory()
    request = factory.post("/") if method == "post" else factory.get("/")
    request.user = user
    return request


@pytest.fixture()
def tree(transactional_db: Any) -> Iterator[dict[str, Any]]:
    """Create an isolated four-level model tree without migrations."""
    with isolate_apps("tests.app"):

        class NestedRoot(models.Model):
            name = models.CharField(max_length=50)

            class Meta:
                app_label = "tests_app"

            def __str__(self) -> str:
                return self.name

        class NestedParent(models.Model):
            name = models.CharField(max_length=50)
            root = models.ForeignKey(
                NestedRoot, on_delete=models.CASCADE, related_name="parents"
            )

            class Meta:
                app_label = "tests_app"

            def __str__(self) -> str:
                return self.name

        class NestedChild(models.Model):
            name = models.CharField(max_length=50)
            slug = models.SlugField(blank=True)
            parent = models.ForeignKey(
                NestedParent, on_delete=models.CASCADE, related_name="children"
            )

            class Meta:
                app_label = "tests_app"

            def __str__(self) -> str:
                return self.name

        class NestedGrandchild(models.Model):
            name = models.CharField(max_length=50)
            child = models.ForeignKey(
                NestedChild,
                on_delete=models.CASCADE,
                related_name="grandchildren",
            )

            class Meta:
                app_label = "tests_app"

            def __str__(self) -> str:
                return self.name

        class NestedDetail(models.Model):
            name = models.CharField(max_length=50)
            grandchild = models.ForeignKey(
                NestedGrandchild, on_delete=models.CASCADE, related_name="details"
            )

            class Meta:
                app_label = "tests_app"

        class NestedMembership(models.Model):
            name = models.CharField(max_length=50)
            home = models.ForeignKey(
                NestedParent,
                on_delete=models.CASCADE,
                related_name="home_members",
            )
            away = models.ForeignKey(
                NestedParent,
                on_delete=models.CASCADE,
                related_name="away_members",
                null=True,
                blank=True,
            )

            class Meta:
                app_label = "tests_app"

        ordered = [
            NestedRoot,
            NestedParent,
            NestedChild,
            NestedGrandchild,
            NestedDetail,
            NestedMembership,
        ]
        with connection.schema_editor() as editor:
            for model in ordered:
                editor.create_model(model)
        user_model = get_user_model()
        user = user_model.objects.create_superuser(
            username="nested-admin",
            email="nested@example.com",
            password=secrets.token_urlsafe(16),
        )
        client = Client()
        client.force_login(user)

        def register(admin_class: type[admin.ModelAdmin]) -> None:
            if admin.site.is_registered(NestedRoot):
                admin.site.unregister(NestedRoot)
            admin.site.register(NestedRoot, admin_class)
            _reload_urls()

        try:
            yield {
                "Root": NestedRoot,
                "Parent": NestedParent,
                "Child": NestedChild,
                "Grand": NestedGrandchild,
                "Detail": NestedDetail,
                "Membership": NestedMembership,
                "user": user,
                "client": client,
                "register": register,
            }
        finally:
            if admin.site.is_registered(NestedRoot):
                admin.site.unregister(NestedRoot)
            _reload_urls()
            with connection.schema_editor() as editor:
                for model in reversed(ordered):
                    editor.delete_model(model)


def _levels(
    data: dict[str, Any],
    *,
    parent: type[InlineModelAdmin] = NestedStackedInline,
    child: type[InlineModelAdmin] = NestedStackedInline,
    grand: type[InlineModelAdmin] = admin.TabularInline,
    detail: type[InlineModelAdmin] | None = None,
    form_extra: int = 0,
) -> type[AdminBoostModel]:
    class GrandInline(grand):  # type: ignore[misc, valid-type]
        model = data["Grand"]
        extra = form_extra

    class ChildInline(child):  # type: ignore[misc, valid-type]
        model = data["Child"]
        extra = form_extra
        inlines = [GrandInline]

    class ParentInline(parent):  # type: ignore[misc, valid-type]
        model = data["Parent"]
        extra = form_extra
        inlines = [ChildInline]

    if detail is not None:

        class DetailInline(detail):  # type: ignore[misc, valid-type]
            model = data["Detail"]
            extra = form_extra

        GrandInline.inlines = [DetailInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    return RootAdmin


def test_public_nested_inline_api() -> None:
    assert issubclass(NestedStackedInline, admin.StackedInline)
    assert issubclass(NestedStackedInline, NestedInlineMixin)
    assert issubclass(NestedTabularInline, admin.TabularInline)
    assert issubclass(NestedTabularInline, NestedInlineMixin)


@pytest.mark.parametrize("layout", ["stacked", "tabular"])
def test_nested_templates_delegate_leaf_rendering_to_django(layout: str) -> None:
    source = (
        Path("src/django_boosted/templates/admin_boost/edit_inline")
        .joinpath(f"{layout}.html")
        .read_text()
    )

    assert "{% if not inline_admin_formset.formset.has_nested_children %}" in source
    assert f'{{% include "admin/edit_inline/{layout}.html" %}}' in source


def test_get_inlines_can_vary_by_request(tree: dict[str, Any]) -> None:
    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        extra = 0

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0

        def get_inlines(self, request, obj=None):  # type: ignore[no-untyped-def]
            if request.GET.get("bare"):
                return []
            return [ChildInline]

    inline = ParentInline(tree["Root"], admin.site)
    bare = _request(tree["user"])
    bare.GET = {"bare": "1"}  # type: ignore[misc]
    assert inline.get_inlines(bare, None) == []
    assert inline.get_inlines(_request(tree["user"]), None) == [ChildInline]
    assert inline.get_inline_instances(bare, None) == []
    instances = inline.get_inline_instances(_request(tree["user"]), None)
    assert len(instances) == 1
    assert isinstance(instances[0], ChildInline)


def test_get_inlines_receives_each_direct_parent(tree: dict[str, Any]) -> None:
    seen: list[Any] = []

    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        extra = 0

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0

        def get_inlines(self, request, obj=None):  # type: ignore[no-untyped-def]
            seen.append(obj)
            return [ChildInline] if isinstance(obj, tree["Parent"]) else []

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    model_admin = RootAdmin(tree["Root"], admin.site)

    formsets, _inlines = model_admin._create_formsets(
        _request(tree["user"]), root, True
    )

    assert any(formset.model is tree["Child"] for formset in formsets)
    assert parent in seen
    assert root not in seen


def test_three_and_four_levels_construct(tree: dict[str, Any]) -> None:
    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    grandchild = tree["Grand"].objects.create(name="Paris", child=child)
    tree["Detail"].objects.create(name="Center", grandchild=grandchild)
    model_admin = _levels(tree, grand=NestedTabularInline, detail=admin.TabularInline)(
        tree["Root"], admin.site
    )
    before = set(model_admin.__dict__)
    formsets, _inlines = model_admin._create_formsets(
        _request(tree["user"]), root, True
    )

    assert set(model_admin.__dict__) == before
    assert formsets[1].instance is formsets[0].forms[0].instance
    depths = [
        formset._nested_metadata.depth
        for formset in formsets
        if getattr(formset, "_nested_metadata", None)
    ]
    assert max(depths) == 3
    assert any(formset.model is tree["Detail"] for formset in formsets)
    template_prefixes = [item.prefix for item in formsets[0]._nested_template_formsets]
    assert any("__prefix__" in prefix for prefix in template_prefixes)
    assert all(
        getattr(item, "_nested_metadata", None) is None
        or not item._nested_metadata.is_template
        for item in formsets
    )


def test_unsaved_parent_keeps_identity_without_child_queries(
    tree: dict[str, Any],
) -> None:
    model_admin = _levels(tree, form_extra=1)(tree["Root"], admin.site)
    with CaptureQueriesContext(connection) as queries:
        formsets, _inlines = model_admin._create_formsets(
            _request(tree["user"]), tree["Root"](), False
        )

    sql = " ".join(item["sql"] for item in queries.captured_queries)
    assert tree["Grand"]._meta.db_table not in sql
    assert formsets[1].instance is formsets[0].forms[0].instance
    assert formsets[1].instance.pk is None


def test_cycle_reports_the_class_path(tree: dict[str, Any]) -> None:
    class NodeInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0

        def get_inlines(self, request, obj=None):  # type: ignore[no-untyped-def]
            return [NodeInline]

    class RootAdmin(AdminBoostModel):
        inlines = [NodeInline]

    model_admin = RootAdmin(tree["Root"], admin.site)
    with pytest.raises(ImproperlyConfigured, match=r"NodeInline -> .*NodeInline"):
        model_admin._create_formsets(_request(tree["user"]), tree["Root"](), False)


def test_same_leaf_can_be_reused_and_prefixes_are_suffixed(
    tree: dict[str, Any],
) -> None:
    class MembersFormSet(BaseInlineFormSet):
        @classmethod
        def get_default_prefix(cls) -> str:
            return "members"

    class HomeInline(admin.TabularInline):
        model = tree["Membership"]
        fk_name = "home"
        formset = MembersFormSet
        extra = 1

    class AwayInline(admin.TabularInline):
        model = tree["Membership"]
        fk_name = "away"
        formset = MembersFormSet
        extra = 1

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 1
        inlines = [HomeInline, AwayInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    tree["Parent"].objects.create(name="Europe", root=root)
    model_admin = RootAdmin(tree["Root"], admin.site)
    formsets, _inlines = model_admin._create_formsets(
        _request(tree["user"]), root, True
    )
    prefixed = [formset.prefix for formset in formsets]
    assert "parents-0-members" in prefixed
    assert "parents-0-members-2" in prefixed
    home = next(item for item in formsets if item.fk.name == "home")
    away = next(item for item in formsets if item.fk.name == "away")
    assert home.instance is away.instance
    assert home.instance is formsets[0].forms[0].instance


def test_nested_page_renders_hierarchy_assets_and_errors(
    tree: dict[str, Any],
) -> None:
    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    tree["Grand"].objects.create(name="Paris", child=child)
    tree["register"](_levels(tree, form_extra=1))
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    response = _submit(
        tree["client"],
        url,
        {"parents-0-children-0-grandchildren-0-name": ""},
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert "parents-0-children-0-grandchildren-TOTAL_FORMS" in html
    assert "parents-__prefix__-children-__prefix__-grandchildren" in html
    assert "This field is required." in html
    assert "admin_boost/nested_inlines.css" in html
    assert "admin_boost/nested_inlines.js" in html
    assert tree["Grand"].objects.filter(name="Paris").exists()


@pytest.mark.parametrize(
    ("parent", "child", "marker"),
    [
        (NestedStackedInline, NestedStackedInline, "boosted-nested-inline"),
        (NestedStackedInline, NestedTabularInline, "boosted-nested-inline-row"),
        (NestedTabularInline, NestedStackedInline, "boosted-nested-inline-row"),
        (NestedTabularInline, NestedTabularInline, "boosted-nested-inline-row"),
    ],
)
def test_nested_layouts_render(
    tree: dict[str, Any],
    parent: type[InlineModelAdmin],
    child: type[InlineModelAdmin],
    marker: str,
) -> None:
    tree["register"](_levels(tree, parent=parent, child=child, form_extra=1))
    url = reverse("admin:tests_app_nestedroot_add")

    response = tree["client"].get(url)

    assert response.status_code == 200
    html = response.content.decode()
    assert "data-inline-type=" in html
    assert marker in html
    assert "admin_boost/nested_inlines.js" in html


@pytest.mark.parametrize("layout", [NestedStackedInline, NestedTabularInline])
def test_saved_and_unsaved_nested_owners_use_native_delete_controls(
    tree: dict[str, Any],
    layout: type[InlineModelAdmin],
) -> None:
    tree["register"](_levels(tree, parent=layout, form_extra=1))
    root = tree["Root"].objects.create(name="Earth")
    tree["Parent"].objects.create(name="Europe", root=root)
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    html = tree["client"].get(url).content.decode()
    closing_tag = "h3" if layout is NestedStackedInline else "tr"

    def row_controls(prefix: str) -> str:
        match = re.search(
            rf'id="{re.escape(prefix)}"[^>]*>(.*?)</{closing_tag}>',
            html,
            re.DOTALL,
        )
        assert match is not None
        return match.group(1)

    saved = row_controls("parents-0")
    unsaved = row_controls("parents-1")
    assert 'name="parents-0-DELETE"' in saved
    assert "boosted-nested-remove" not in saved
    assert 'name="parents-1-DELETE"' not in unsaved
    assert "boosted-nested-remove" in unsaved


def test_nested_prepopulated_fields_include_dynamic_metadata(
    tree: dict[str, Any],
) -> None:
    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        extra = 1
        prepopulated_fields = {"slug": ("name",)}

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 1
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    model_admin = RootAdmin(tree["Root"], admin.site)
    request = _request(tree["user"])
    formsets, inline_instances = model_admin._create_formsets(
        request, tree["Root"](), False
    )
    wrappers = model_admin.get_inline_formsets(
        request, formsets, inline_instances, None
    )
    child_wrapper = wrappers[0].formset.forms[0].nested_inline_admin_formsets[0]
    options = json.loads(child_wrapper.inline_formset_data())["options"]

    assert options["prepopulatedFields"] == {
        "slug": {
            "dependencies": ["name"],
            "maxLength": 50,
            "allowUnicode": False,
        }
    }
    assert child_wrapper.formset.boosted_is_nested is True


def test_save_as_new_duplicates_the_active_nested_tree(tree: dict[str, Any]) -> None:
    tree["register"](_levels(tree, form_extra=1))
    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    grand = tree["Grand"].objects.create(name="Paris", child=child)
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    response = _submit(
        tree["client"],
        url,
        {"_saveasnew": "Save as new", "name": "Earth copy"},
    )

    assert response.status_code == 302
    original = tree["Root"].objects.get(pk=root.pk)
    assert original.name == "Earth"
    assert list(original.parents.values_list("pk", "name")) == [(parent.pk, "Europe")]
    assert child.parent_id == parent.pk
    assert grand.child_id == child.pk
    copied = tree["Root"].objects.get(name="Earth copy")
    copied_parent = copied.parents.get()
    copied_child = copied_parent.children.get()
    copied_grand = copied_child.grandchildren.get()
    assert copied_parent.pk != parent.pk
    assert copied_child.pk != child.pk
    assert copied_grand.pk != grand.pk
    assert (copied_parent.name, copied_child.name, copied_grand.name) == (
        "Europe",
        "France",
        "Paris",
    )
    assert copied.parents.count() == 1
    assert tree["Child"].objects.filter(parent=parent).count() == 1
    assert tree["Grand"].objects.filter(child=child).count() == 1


def test_create_update_and_sibling_trees(tree: dict[str, Any]) -> None:
    saved: list[str] = []

    class RootAdmin(_levels(tree, form_extra=1)):  # type: ignore[misc]
        def save_formset(self, request, form, formset, change):  # type: ignore[no-untyped-def]
            assert "__prefix__" not in formset.prefix
            saved.append(formset.model._meta.model_name)
            super().save_formset(request, form, formset, change)

    tree["register"](RootAdmin)
    add_url = reverse("admin:tests_app_nestedroot_add")
    created = _submit(
        tree["client"],
        add_url,
        {
            "name": "Earth",
            "parents-0-name": "Europe",
            "parents-0-children-0-name": "France",
            "parents-0-children-0-grandchildren-0-name": "Paris",
        },
    )
    assert created.status_code == 302
    root = tree["Root"].objects.get(name="Earth")
    parent = root.parents.get(name="Europe")
    child = parent.children.get(name="France")
    assert child.grandchildren.filter(name="Paris").exists()
    assert saved == ["nestedparent", "nestedchild", "nestedgrandchild"]

    change_url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])
    updated = _submit(
        tree["client"],
        change_url,
        {
            "parents-0-name": "Asia",
            "parents-0-children-0-name": "Japan",
            "parents-0-children-0-grandchildren-0-name": "Tokyo",
            "parents-1-name": "Americas",
            "parents-1-children-0-name": "Canada",
            "parents-1-children-0-grandchildren-0-name": "Ottawa",
        },
    )
    assert updated.status_code == 302
    assert tree["Parent"].objects.filter(name="Asia", root=root).exists()
    america = tree["Parent"].objects.get(name="Americas", root=root)
    assert america.children.get().grandchildren.get().name == "Ottawa"


def test_invalid_deepest_value_rolls_back_and_correction_saves(
    tree: dict[str, Any],
) -> None:
    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    tree["Grand"].objects.create(name="Paris", child=child)
    tree["register"](_levels(tree))
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])
    failed = _submit(
        tree["client"],
        url,
        {"parents-0-children-0-grandchildren-0-name": ""},
    )

    assert failed.status_code == 200
    assert tree["Grand"].objects.get().name == "Paris"

    saved = _submit(
        tree["client"],
        url,
        {"parents-0-children-0-grandchildren-0-name": "Lyon"},
    )
    assert saved.status_code == 302
    assert tree["Grand"].objects.get().name == "Lyon"


def test_save_exception_rolls_back_the_nested_tree(tree: dict[str, Any]) -> None:
    class RootAdmin(_levels(tree, form_extra=1)):  # type: ignore[misc]
        def save_formset(self, request, form, formset, change):  # type: ignore[no-untyped-def]
            super().save_formset(request, form, formset, change)
            if formset.model is tree["Grand"]:
                raise RuntimeError("boom")

    tree["register"](RootAdmin)
    url = reverse("admin:tests_app_nestedroot_add")
    with pytest.raises(RuntimeError, match="boom"):
        _submit(
            tree["client"],
            url,
            {
                "name": "Earth",
                "parents-0-name": "Europe",
                "parents-0-children-0-name": "France",
                "parents-0-children-0-grandchildren-0-name": "Paris",
            },
        )

    assert tree["Root"].objects.count() == 0
    assert tree["Parent"].objects.count() == 0


def test_parent_forms_are_cleaned_before_descendants(tree: dict[str, Any]) -> None:
    cleaned: list[str] = []

    class ParentForm(ModelForm):
        class Meta:
            model = tree["Parent"]
            fields = "__all__"

        def clean(self) -> dict[str, Any] | None:
            cleaned.append("parent")
            return super().clean()

    class ChildForm(ModelForm):
        class Meta:
            model = tree["Child"]
            fields = "__all__"

        def clean(self) -> dict[str, Any] | None:
            cleaned.append("child")
            return super().clean()

    class GrandInline(admin.TabularInline):
        model = tree["Grand"]
        extra = 0

    class ChildInline(NestedStackedInline):
        model = tree["Child"]
        form = ChildForm
        extra = 0
        inlines = [GrandInline]

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        form = ParentForm
        extra = 0
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    tree["Grand"].objects.create(name="Paris", child=child)
    tree["register"](RootAdmin)
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    assert _submit(tree["client"], url, {}).status_code == 302
    assert cleaned.index("parent") < cleaned.index("child")


def test_deletions_do_not_recreate_descendants(tree: dict[str, Any]) -> None:
    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    other = tree["Parent"].objects.create(name="Asia", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    tree["Child"].objects.create(name="Japan", parent=other)
    grandchild = tree["Grand"].objects.create(name="Paris", child=child)
    tree["register"](_levels(tree, form_extra=1))
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    deleted_grand = _submit(
        tree["client"],
        url,
        {"parents-0-children-0-grandchildren-0-DELETE": "on"},
    )
    assert deleted_grand.status_code == 302
    assert not tree["Grand"].objects.filter(pk=grandchild.pk).exists()

    deleted_child = _submit(
        tree["client"],
        url,
        {
            "parents-0-children-0-DELETE": "on",
            "parents-0-children-0-grandchildren-0-name": "",
        },
    )
    assert deleted_child.status_code == 302
    assert not tree["Child"].objects.filter(name="France").exists()

    deleted_parent = _submit(
        tree["client"],
        url,
        {"parents-0-DELETE": "on", "parents-0-children-0-name": ""},
    )
    assert deleted_parent.status_code == 302
    assert not tree["Parent"].objects.filter(name="Europe").exists()
    assert tree["Parent"].objects.filter(name="Asia").exists()

    rejected = _submit(
        tree["client"],
        url,
        {
            "parents-1-name": "Americas",
            "parents-1-DELETE": "on",
            "parents-1-children-0-name": "Canada",
            "parents-1-children-0-grandchildren-0-name": "Ottawa",
        },
    )
    assert rejected.status_code == 302
    assert not tree["Parent"].objects.filter(name="Americas").exists()
    assert not tree["Child"].objects.filter(name="Canada").exists()


def test_descendants_of_unchanged_extra_parent_are_inactive(
    tree: dict[str, Any],
) -> None:
    class RejectingChildFormSet(BaseInlineFormSet):
        def clean(self) -> None:
            super().clean()
            raise ValidationError("Inactive descendants must not validate.")

    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        formset = RejectingChildFormSet
        extra = 1

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 1
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    tree["register"](RootAdmin)
    response = _submit(
        tree["client"],
        reverse("admin:tests_app_nestedroot_add"),
        {
            "name": "Earth",
            "parents-0-children-0-name": "orphan",
        },
    )

    assert response.status_code == 302
    assert tree["Root"].objects.filter(name="Earth").exists()
    assert tree["Parent"].objects.count() == 0
    assert tree["Child"].objects.count() == 0


def test_forged_delete_is_ignored(tree: dict[str, Any]) -> None:
    class GrandInline(admin.TabularInline):
        model = tree["Grand"]
        extra = 0
        can_delete = False

    class ChildInline(NestedStackedInline):
        model = tree["Child"]
        extra = 0
        inlines = [GrandInline]

        def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return False

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    grandchild = tree["Grand"].objects.create(name="Paris", child=child)
    tree["register"](RootAdmin)
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    response = _submit(
        tree["client"],
        url,
        {
            "parents-0-children-0-DELETE": "on",
            "parents-0-children-0-grandchildren-0-DELETE": "on",
        },
    )

    assert response.status_code == 302
    assert tree["Child"].objects.filter(pk=child.pk).exists()
    assert tree["Grand"].objects.filter(pk=grandchild.pk).exists()


def test_custom_form_formset_fk_name_and_files(tree: dict[str, Any]) -> None:
    class ChildForm(ModelForm):
        class Meta:
            model = tree["Child"]
            fields = "__all__"

    class ChildFormSet(BaseInlineFormSet):
        pass

    class GrandInline(admin.TabularInline):
        model = tree["Grand"]
        extra = 0

    class ChildInline(NestedTabularInline):
        model = tree["Child"]
        form = ChildForm
        formset = ChildFormSet
        extra = 0
        inlines = [GrandInline]

    class MembershipFormSet(BaseInlineFormSet):
        @classmethod
        def get_default_prefix(cls) -> str:
            return "members"

    class HomeInline(admin.TabularInline):
        model = tree["Membership"]
        fk_name = "home"
        formset = MembershipFormSet
        extra = 0

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0
        inlines = [ChildInline, HomeInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    model_admin = RootAdmin(tree["Root"], admin.site)
    formsets, _inlines = model_admin._create_formsets(
        _request(tree["user"]), root, True
    )
    child_formset = next(item for item in formsets if item.model is tree["Child"])
    home_formset = next(item for item in formsets if item.fk.name == "home")
    assert issubclass(type(child_formset), ChildFormSet)
    assert issubclass(child_formset.form, ChildForm)
    assert home_formset.fk.name == "home"
    assert child_formset.instance.pk == parent.pk

    upload = SimpleUploadedFile("note.txt", b"hello")
    posted = RequestFactory().post("/", {"name": root.name, "upload": upload})
    posted.user = tree["user"]
    params = model_admin.get_formset_kwargs(
        posted, parent, ChildInline(tree["Parent"], admin.site), "children"
    )
    assert params["files"] is posted.FILES
    bound = child_formset.__class__(**params)
    assert bound.files is posted.FILES


@pytest.mark.parametrize(
    ("permissions", "visible"),
    [
        ("full", True),
        ("view", True),
        ("no-add", True),
        ("no-change", True),
        ("no-delete", True),
        ("none", False),
    ],
)
def test_child_permission_matrix(
    tree: dict[str, Any], permissions: str, visible: bool
) -> None:
    class GrandInline(admin.TabularInline):
        model = tree["Grand"]
        extra = 0

        def has_view_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return permissions != "none"

        def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return permissions in {"full", "no-add", "no-delete"}

        def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return permissions in {"full", "no-change", "no-delete"}

        def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return permissions in {"full", "no-add", "no-change"}

    class ChildInline(NestedStackedInline):
        model = tree["Child"]
        extra = 0
        inlines = [GrandInline]

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    child = tree["Child"].objects.create(name="France", parent=parent)
    tree["Grand"].objects.create(name="secret-paris", child=child)
    seen: list[Any] = []
    original = GrandInline.has_change_permission

    def record(self, request, obj=None):  # type: ignore[no-untyped-def]
        seen.append(obj)
        return original(self, request, obj)

    GrandInline.has_change_permission = record  # type: ignore[method-assign]
    tree["register"](RootAdmin)
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])
    response = tree["client"].get(url)
    html = response.content.decode()

    assert response.status_code == 200
    assert ("secret-paris" in html) is visible
    if permissions != "none":
        assert any(getattr(obj, "name", None) == "France" for obj in seen)
    if permissions == "view":
        follow = _submit(tree["client"], url, {})
        assert follow.status_code == 302
        assert tree["Grand"].objects.get().name == "secret-paris"


def test_permissions_can_differ_between_parent_objects(tree: dict[str, Any]) -> None:
    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        extra = 0

        def _allowed(self, obj: Any) -> bool:
            return not (obj is not None and obj.name == "hidden-parent")

        def has_view_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return self._allowed(obj)

        def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return self._allowed(obj)

        def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return self._allowed(obj)

        def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return self._allowed(obj)

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    visible = tree["Parent"].objects.create(name="visible-parent", root=root)
    hidden = tree["Parent"].objects.create(name="hidden-parent", root=root)
    tree["Child"].objects.create(name="shown-child", parent=visible)
    tree["Child"].objects.create(name="hidden-child", parent=hidden)
    tree["register"](RootAdmin)
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    html = tree["client"].get(url).content.decode()

    assert "shown-child" in html
    assert "hidden-child" not in html


def test_object_permission_controls_nested_queryset(tree: dict[str, Any]) -> None:
    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        extra = 0

        def _allowed(self, obj: Any) -> bool:
            return isinstance(obj, tree["Parent"])

        def has_view_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return self._allowed(obj)

        def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return self._allowed(obj)

        def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return False

        def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return False

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    tree["Child"].objects.create(name="visible-child", parent=parent)
    tree["register"](RootAdmin)
    url = reverse("admin:tests_app_nestedroot_change", args=[root.pk])

    response = tree["client"].get(url)

    assert response.status_code == 200
    assert "visible-child" in response.content.decode()


def test_add_permission_denial_limits_new_rows(tree: dict[str, Any]) -> None:
    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        extra = 3

        def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return False

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 0
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    tree["Child"].objects.create(name="existing-child", parent=parent)
    model_admin = RootAdmin(tree["Root"], admin.site)
    _formsets, inlines = model_admin._create_formsets(
        _request(tree["user"]), root, True
    )

    assert inlines[1].max_num == 0


def test_uneditable_root_disables_nested_permissions(tree: dict[str, Any]) -> None:
    class ChildInline(admin.TabularInline):
        model = tree["Child"]
        extra = 2

    class ParentInline(NestedStackedInline):
        model = tree["Parent"]
        extra = 1
        inlines = [ChildInline]

    class RootAdmin(AdminBoostModel):
        inlines = [ParentInline]

        def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
            return False

    root = tree["Root"].objects.create(name="Earth")
    parent = tree["Parent"].objects.create(name="Europe", root=root)
    tree["Child"].objects.create(name="France", parent=parent)
    model_admin = RootAdmin(tree["Root"], admin.site)
    request = _request(tree["user"])
    formsets, inline_instances = model_admin._create_formsets(request, root, True)
    wrappers = model_admin.get_inline_formsets(
        request, formsets, inline_instances, root
    )
    child_wrappers = wrappers[0].formset.forms[0].nested_inline_admin_formsets

    assert all(formset.extra == 0 and formset.max_num == 0 for formset in formsets)
    assert wrappers[0].has_add_permission is False
    assert wrappers[0].has_change_permission is False
    assert wrappers[0].has_delete_permission is False
    assert child_wrappers[0].has_add_permission is False
    assert child_wrappers[0].has_change_permission is False
    assert child_wrappers[0].has_delete_permission is False


@pytest.mark.django_db()
def test_native_inlines_and_object_tools_remain_unchanged() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        username="plain-admin",
        email="plain@example.com",
        password=secrets.token_urlsafe(16),
    )
    client = Client()
    client.force_login(user)
    country = Country.objects.create(name="France")
    city = City.objects.create(name="Lyon", country=country)
    country_url = reverse("admin:tests_app_country_change", args=[country.pk])

    response = _submit(client, country_url, {"cities-0-name": "Nice"})

    assert response.status_code == 302
    assert City.objects.get(pk=city.pk).name == "Nice"
    page = client.get(country_url).content.decode()
    assert "nested_inlines.js" not in page
    assert "Redirect to changelist" in page
    assert "Save" in page
    alphabet = Alphabet.objects.create(name="Latin", country=country)
    alphabet_url = reverse("admin:tests_app_alphabet_change", args=[alphabet.pk])
    alphabet_page = client.get(alphabet_url)
    assert alphabet_page.status_code == 200
    assert "nested_inlines.js" not in alphabet_page.content.decode()
    assert "Latin" in alphabet_page.content.decode()


def test_tabular_owner_rows_use_native_column_count(tree: dict[str, Any]) -> None:
    tree["register"](_levels(tree, parent=NestedTabularInline, form_extra=1))
    url = reverse("admin:tests_app_nestedroot_add")
    html = tree["client"].get(url).content.decode()
    header = re.search(
        r'id="parents-group".*?<thead><tr>(.*?)</tr></thead>',
        html,
        re.DOTALL,
    )

    assert header is not None
    columns = header.group(1).count("<th")
    assert columns > 1
    assert 'colspan="100"' not in html
    assert html.count(f'colspan="{columns}"') == 4


def test_nested_javascript_keeps_stable_prefixes() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "src/django_boosted/static/admin_boost/nested_inlines.js"
    ).read_text()

    assert "TOTAL_FORMS" in script
    assert "__prefix__" in script
    assert "formset:added" in script
    assert "boostedNestedInitialized" in script
    assert "CSS.escape" in script
    assert "djangoAdminSelect2" in script
    assert "prepopulate" in script
    assert "SelectFilter.init" in script
    assert "nestedAutocompletes" in script
    assert "nextIndex -=" not in script
    assert 'className = "addlink"' in script
    assert 'setAttribute("role", "button")' in script
    assert "emptyRow.children.length" in script
    assert "colSpan = 100" not in script
    assert "precedingCompanionRows" in script
    assert "boosted-nested-form-companion" in script
