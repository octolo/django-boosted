try:
    from django_boosted.rest_framework.metadata import BoostedRestFrameworkMetadata
except ImportError:
    __all__ = []
else:
    __all__ = ["BoostedRestFrameworkMetadata"]
