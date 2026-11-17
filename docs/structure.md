## Project Structure

Django Boosted follows a standard Django app structure with clear separation between admin utilities, models, managers, and templates.

### General Structure

```
django-boosted/
├── src/
│   └── django_boosted/       # Main package directory
│       ├── __init__.py       # Package exports
│       ├── admin/            # Admin utilities
│       │   ├── __init__.py   # Admin exports
│       │   ├── model.py      # AdminBoostModel
│       │   ├── permissions.py # Permission helpers
│       │   ├── views/        # View generators and setup logic
│       │   ├── fieldsets.py # Fieldset utilities
│       │   ├── format.py    # Formatting utilities
│       │   ├── tools.py     # Admin tools
│       │   └── urls.py      # URL registration
│       ├── models/           # Django models
│       │   └── urls.py      # URL model
│       ├── managers/         # Custom managers
│       │   └── urls.py      # URL manager
│       ├── rest_framework/  # DRF integration
│       │   ├── __init__.py  # Conditional DRF imports
│       │   └── metadata.py  # Custom metadata class
│       ├── templatetags/    # Template tags
│       │   └── boosted_tags.py
│       ├── templates/       # Django templates
│       │   └── admin_boost/
│       ├── static/          # Static files
│       │   └── admin_boost/
│       ├── apps.py          # App configuration
│       └── decorators.py    # Main decorators module
├── tests/                    # Test suite
│   └── ...
├── docs/                     # Documentation
│   └── ...
├── pyproject.toml            # Project configuration
└── README.md                 # Project documentation
```

### Module Organization Principles

- **Single Responsibility**: Each module should have a clear, single purpose
- **Separation of Concerns**: Keep admin, models, managers, and templates separate
- **Django Conventions**: Follow Django's app structure conventions
- **Clear Exports**: Use `__init__.py` to define public API
- **Logical Grouping**: Organize related functionality together

### Admin Organization

The `admin/` directory contains Django admin utilities:

- **`model.py`**: `AdminBoostModel`
- **`inlines.py`**: recursive nested admin inlines. Usage is documented in `docs/nested-inlines.md`.
- **`permissions.py`**: model view permission resolution
- **`views/`**: `ViewGenerator`, specialized view types, and decorator setup
- **`../decorators.py`**: `@admin_boost_view` and `@admin_boost_action`
- **`urls.py`**: URL registration utilities
- **`fieldsets.py`**: Fieldset manipulation utilities
- **`format.py`**: Formatting utilities for admin
- **`tools.py`**: Admin tool utilities

### Package Exports

The public API is defined in `src/django_boosted/__init__.py`:
- `AdminBoostModel`: Main admin model mixin
- `NestedInlineMixin`, `NestedStackedInline`, `NestedTabularInline`: recursive admin inlines
- `admin_boost_view`: Decorator for defining custom views
- Conditional DRF exports when DRF is installed
