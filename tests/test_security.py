from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from django_boosted import admin_boost_action
from django_boosted.admin import index
from django_boosted.admin.settings import SettingAdmin
from django_boosted.admin.views import ViewGenerator
from django_boosted.admin.views.global_admin import BoostedViewAdmin
from django_boosted.models.global_view import BoostedView
from django_boosted.models.settings import SettingModel
from tests.app.admin.country import CountryAdmin
from tests.app.models import City, Country


@pytest.fixture()
def staff_user(db, django_user_model):
    return django_user_model.objects.create_user(username="staff", is_staff=True)


@pytest.fixture()
def superuser(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="test-password",
    )


def _request(user, method="get"):
    request = getattr(RequestFactory(), method)("/")
    request.user = user
    return request


@pytest.mark.django_db()
def test_settings_admin_is_disabled_by_default_and_superuser_only(staff_user):
    assert not admin.site.is_registered(SettingModel)

    model_admin = SettingAdmin(SettingModel, admin.site)

    assert not model_admin.has_module_permission(_request(staff_user))
    assert not model_admin.has_view_permission(_request(staff_user))
    assert not model_admin.has_change_permission(_request(staff_user))


def test_settings_manager_excludes_sensitive_values():
    names = {item["name"] for item in SettingModel.objects.get_data()}

    assert "SECRET_KEY" not in names
    assert "DATABASES" not in names


@pytest.mark.django_db()
def test_custom_actions_do_not_grant_change_permission(staff_user):
    class ActionAdmin(CountryAdmin):
        changeform_actions = {"publish": "Publish"}

        def handle_publish(self, request, object_id):
            return None

    model_admin = ActionAdmin(Country, admin.site)
    request = _request(staff_user)

    assert not model_admin.has_change_permission(request)
    assert model_admin.get_submit_actions(request) == {}


@pytest.mark.django_db()
def test_decorated_action_uses_change_permission_by_default(superuser):
    class ActionAdmin(CountryAdmin):
        @admin_boost_action("publish", "Publish")
        def publish_action(self):
            return None

        def handle_publish(self, request, object_id):
            return None

    actions = ActionAdmin(Country, admin.site).get_submit_actions(_request(superuser))

    assert actions == {"publish": "Publish"}


@pytest.mark.django_db()
def test_view_only_user_cannot_post_model_view(staff_user):
    content_type = ContentType.objects.get_for_model(Country)
    staff_user.user_permissions.add(
        Permission.objects.get(content_type=content_type, codename="view_country")
    )
    model_admin = CountryAdmin(Country, admin.site)
    generator = ViewGenerator(model_admin)

    generator._check_permissions(_request(staff_user), permission="view")
    with pytest.raises(PermissionDenied):
        generator._check_permissions(
            _request(staff_user, "post"),
            permission="view",
            require_change=True,
        )


@pytest.mark.django_db()
def test_configured_model_permission_is_enforced(staff_user):
    content_type = ContentType.objects.get_for_model(Country)
    permission = Permission.objects.create(
        content_type=content_type,
        codename="run_country_report",
        name="Can run country report",
    )
    model_admin = CountryAdmin(Country, admin.site)
    generator = ViewGenerator(model_admin)
    request = _request(staff_user)

    with pytest.raises(PermissionDenied):
        generator._check_permissions(request, permission="run_country_report")

    staff_user.user_permissions.add(permission)
    request.user = type(staff_user).objects.get(pk=staff_user.pk)
    generator._check_permissions(request, permission="run_country_report")


@pytest.mark.django_db()
def test_direct_admin_link_honors_target_permission(staff_user):
    country = Country.objects.create(name="France")
    model_admin = CountryAdmin(Country, admin.site)
    request = _request(staff_user)

    assert model_admin.get_boost_object_links(request, country) == []

    content_type = ContentType.objects.get_for_model(City)
    staff_user.user_permissions.add(
        Permission.objects.get(content_type=content_type, codename="view_city")
    )
    request.user = type(staff_user).objects.get(pk=staff_user.pk)

    assert model_admin.get_boost_object_links(request, country) == [
        {
            "label": "Cities",
            "url": (
                f"{reverse('admin:tests_app_city_changelist')}"
                f"?country__id__exact={country.pk}"
            ),
        }
    ]


@pytest.mark.django_db()
def test_external_redirect_is_rejected(superuser):
    model_admin = CountryAdmin(Country, admin.site)
    view = ViewGenerator(model_admin).generate_admin_custom_redirect_view(
        lambda request: "https://attacker.example/phishing",
        "Unsafe redirect",
        requires_object=False,
    )

    response = view(_request(superuser))

    assert response.status_code == 302
    assert response.url == reverse("admin:index")


@pytest.mark.django_db()
def test_cross_model_list_requires_target_model_permission(staff_user):
    model_admin = BoostedViewAdmin(BoostedView, admin.site)
    view = ViewGenerator(model_admin).generate_admin_custom_list_view(
        lambda request: {"queryset": Country.objects.all()},
        "Countries",
        requires_object=False,
    )

    with pytest.raises(PermissionDenied):
        view(_request(staff_user))


@pytest.mark.django_db()
def test_confirm_view_executes_confirmed_post(superuser):
    calls = []

    def action(request, confirmed=False):
        calls.append(confirmed)
        return {"confirm": "Continue?"}

    view = ViewGenerator(
        CountryAdmin(Country, admin.site)
    ).generate_admin_custom_confirm_view(
        action, "Confirm action", requires_object=False
    )

    request = RequestFactory().post("/", {"action": "confirm"})
    request.user = superuser
    response = view(request)

    assert calls == [True]
    assert response.status_code == 302


def test_register_index_view_honors_permission(monkeypatch):
    monkeypatch.setattr(index, "_index_links", [])
    index.register_index_view(
        "Operations",
        "/admin/operations/",
        permission=lambda request: request.user.allowed,
    )
    request = _request(
        SimpleNamespace(allowed=True, is_staff=False, has_perm=lambda permission: False)
    )

    assert index.get_index_views(request) == [
        {"label": "Operations", "url": "/admin/operations/", "order": 0}
    ]


def test_permission_callable_is_honored():
    model_admin = SimpleNamespace(
        has_view_permission=lambda request, obj=None: True,
        model=Country,
    )
    generator = ViewGenerator(model_admin)

    with pytest.raises(PermissionDenied):
        generator._check_permissions(
            _request(SimpleNamespace()),
            permission=lambda request: False,
        )
