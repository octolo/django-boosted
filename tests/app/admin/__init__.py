from django import get_version
from django.contrib import admin

from django_boosted import __version__ as admin_boost_version

from ..models import Alphabet, Campus, City, Country
from .alphabet import AlphabetAdmin
from .campus import CampusAdmin
from .city import CityAdmin
from .country import CountryAdmin

__all__ = ["AlphabetAdmin", "CampusAdmin", "CityAdmin", "CountryAdmin"]

admin.site.register(Country, CountryAdmin)
admin.site.register(Alphabet, AlphabetAdmin)
admin.site.register(Campus, CampusAdmin)
admin.site.register(City, CityAdmin)

admin.site.site_header = (
    f"Django ({get_version()}) Admin boost ({admin_boost_version}) - Administration"
)
admin.site.site_title = f"Django ({get_version()}) Admin boost ({admin_boost_version})"
admin.site.index_title = "Administration"
