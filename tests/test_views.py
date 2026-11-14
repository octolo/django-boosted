import secrets

import pytest
from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.urls import reverse

from tests.app.models import City, Country


@pytest.fixture()
def superuser(db):
    User = get_user_model()
    return User.objects.create_superuser(  # type: ignore[attr-defined]
        username="admin",
        email="admin@example.com",
        password=secrets.token_urlsafe(16),
    )


@pytest.fixture()
def admin_client(superuser):
    client = DjangoClient()
    client.force_login(superuser)
    return client


@pytest.fixture()
def staff_user(db):
    User = get_user_model()
    return User.objects.create_user(  # type: ignore[attr-defined]
        username="staff",
        email="staff@example.com",
        password=secrets.token_urlsafe(16),
        is_staff=True,
    )


@pytest.fixture()
def plain_user(db):
    User = get_user_model()
    return User.objects.create_user(  # type: ignore[attr-defined]
        username="joe",
        email="joe@example.com",
        password=secrets.token_urlsafe(16),
    )


def _client(user):
    client = DjangoClient()
    client.force_login(user)
    return client


@pytest.mark.django_db()
def test_boost_view_renders_context(admin_client):
    country_obj = Country.objects.create(name="Alice")
    url = reverse(
        "admin:tests_app_country_custom_message_object_view", args=[country_obj.pk]
    )

    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert f"This is a custom message object view for {country_obj}" in content


@pytest.mark.django_db()
def test_json_object_view_returns_json(admin_client):
    country = Country.objects.create(name="France")
    url = reverse("admin:tests_app_country_custom_json_object_view", args=[country.pk])

    response = admin_client.get(url)

    assert response.status_code == 200
    assert response.json() == {"object_json": {"name": "Custom 1", "id": 1}}


@pytest.mark.django_db()
def test_form_object_view_renders_form(admin_client):
    country = Country.objects.create(name="France")
    url = reverse("admin:tests_app_country_custom_form_object_view", args=[country.pk])

    response = admin_client.get(url)

    assert response.status_code == 200
    assert 'name="name"' in response.content.decode()


@pytest.mark.django_db()
def test_list_object_view_renders_queryset(admin_client):
    country = Country.objects.create(name="France")
    url = reverse("admin:tests_app_country_custom_list_object_view", args=[country.pk])

    response = admin_client.get(url)

    assert response.status_code == 200
    assert "France" in response.content.decode()


@pytest.mark.django_db()
def test_redirect_view(admin_client):
    """Redirect view returns 302 and redirects to the expected URL."""
    country_obj = Country.objects.create(name="Bob")
    url = reverse(
        "admin:tests_app_country_custom_redirect_object_view", args=[country_obj.pk]
    )

    response = admin_client.get(url)

    assert response.status_code == 302
    changelist_url = reverse("admin:tests_app_country_changelist")
    assert response.url == changelist_url


@pytest.mark.django_db()
def test_object_tools_button_is_visible(admin_client):
    country_obj = Country.objects.create(name="Bob")
    change_url = reverse("admin:tests_app_country_change", args=[country_obj.pk])

    response = admin_client.get(change_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Redirect to changelist" in content


@pytest.mark.django_db()
def test_direct_object_link_filters_related_admin_list(admin_client):
    france = Country.objects.create(name="France")
    germany = Country.objects.create(name="Germany")
    City.objects.create(name="Paris", country=france)
    City.objects.create(name="Berlin", country=germany)
    change_url = reverse("admin:tests_app_country_change", args=[france.pk])

    response = admin_client.get(change_url)

    city_url = reverse("admin:tests_app_city_changelist")
    filtered_url = f"{city_url}?country__id__exact={france.pk}"
    assert filtered_url in response.content.decode()

    city_response = admin_client.get(filtered_url)
    content = city_response.content.decode()
    assert "Paris" in content
    assert "Berlin" not in content


@pytest.mark.django_db()
def test_index_panel_lists_global_views(superuser):
    response = _client(superuser).get(reverse("admin:index"))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="boosted-index-views-module"' in content
    assert "Global action" in content
    assert "Global countries" in content
    assert "Global hello" in content  # discovered via boosted_views.py convention


@pytest.mark.django_db()
def test_global_adminform_view_renders_raw_id_fields(superuser):
    url = reverse("admin:django_boosted_boostedview_global_action_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "vForeignKeyRawIdAdminField" in content
    assert 'id="lookup_id_user"' in content
    assert 'id="lookup_id_country"' in content


@pytest.mark.django_db()
def test_global_adminform_shows_default_save_button(superuser):
    url = reverse("admin:django_boosted_boostedview_global_action_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    assert 'name="_save"' in response.content.decode()


@pytest.mark.django_db()
def test_global_adminform_can_rename_save_button(superuser):
    url = reverse("admin:django_boosted_boostedview_global_renamed_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    assert 'value="Run it"' in response.content.decode()


@pytest.mark.django_db()
def test_global_adminform_supports_multiple_colored_buttons(superuser):
    url = reverse("admin:django_boosted_boostedview_global_multi_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="_apply"' in content
    assert 'class="success"' in content
    assert 'name="_danger"' in content
    assert 'class="danger"' in content


@pytest.mark.django_db()
def test_global_adminform_all_button_colors(superuser):
    url = reverse("admin:django_boosted_boostedview_global_colors_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    content = response.content.decode()
    colors = ("default", "success", "info", "warning", "danger", "primary", "secondary")
    for color in colors:
        assert f'class="{color}"' in content


@pytest.mark.django_db()
def test_global_adminform_honors_readonly_fields(superuser):
    url = reverse("admin:django_boosted_boostedview_global_readonly_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    assert response.context["adminform"].readonly_fields == ("token", "url")
    html = response.content.decode()
    assert 'name="token"' not in html
    assert 'name="url"' not in html
    assert 'name="name"' in html


@pytest.mark.django_db()
def test_global_adminform_readonly_fields_show_values_after_post(superuser):
    url = reverse("admin:django_boosted_boostedview_global_readonly_view")

    response = _client(superuser).post(url, {"name": "brevo"})

    assert response.status_code == 200
    html = response.content.decode()
    assert "secret-token" in html
    assert "https://example.com/hook" in html
    assert html.count('class="readonly"') >= 2
    assert 'name="token"' not in html


@pytest.mark.django_db()
def test_global_adminform_readonly_fields_work_on_a_modelform(superuser):
    url = reverse("admin:django_boosted_boostedview_global_readonly_model_view")

    response = _client(superuser).post(url, {"name": "France"})

    assert response.status_code == 200
    assert response.context["adminform"].readonly_fields == ("name",)
    html = response.content.decode()
    assert "France" in html
    assert 'name="name"' not in html
    assert 'class="readonly"' in html


@pytest.mark.django_db()
def test_global_adminform_view_post_redirects(superuser):
    country = Country.objects.create(name="France")
    url = reverse("admin:django_boosted_boostedview_global_action_view")

    response = _client(superuser).post(
        url, {"user": superuser.pk, "country": country.pk}
    )

    assert response.status_code == 302
    assert response.url == reverse("admin:index")


@pytest.mark.django_db()
def test_global_list_view_renders(superuser):
    Country.objects.create(name="Zanzibar")
    url = reverse("admin:django_boosted_boostedview_global_countries_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    assert "Zanzibar" in response.content.decode()


@pytest.mark.django_db()
def test_global_list_view_renders_boost_labels(superuser):
    Country.objects.create(name="Zanzibar")
    url = reverse("admin:django_boosted_boostedview_global_labels_view")

    response = _client(superuser).get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'class="boost-label success"' in content
    assert "boost-label danger small" in content


@pytest.mark.django_db()
def test_staff_user_can_access_global_view(staff_user):
    url = reverse("admin:django_boosted_boostedview_global_hello_view")

    response = _client(staff_user).get(url)

    assert response.status_code == 200
    assert "Hello from a global boosted view" in response.content.decode()


@pytest.mark.django_db()
def test_non_staff_cannot_access_global_view(plain_user):
    url = reverse("admin:django_boosted_boostedview_global_action_view")

    response = _client(plain_user).get(url)

    assert response.status_code in (302, 403)
