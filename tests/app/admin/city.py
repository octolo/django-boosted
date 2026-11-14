from django.contrib import admin

from django_boosted import AdminBoostModel

from ..models import City


class CityInline(admin.TabularInline):
    model = City
    extra = 0
    show_change_link = True


class CityAdmin(AdminBoostModel):
    list_display = ["name", "country"]
    search_fields = ["name"]
    autocomplete_fields = ["country"]
