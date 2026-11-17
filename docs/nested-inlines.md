# Nested admin inlines

`AdminBoostModel` can edit an inline tree of any finite depth on one change
page. Django builds, validates, and saves every formset. django-boosted adds
the missing parent-to-child relationship.

Requires Django `>=5.2,<6.0`.

## Classes

| Class | Use it when |
| --- | --- |
| `NestedStackedInline` | The inline owns child inlines and uses the stacked layout. |
| `NestedTabularInline` | The inline owns child inlines and uses the tabular layout. |
| `admin.StackedInline` or `admin.TabularInline` | The inline is a leaf. |
| `NestedInlineMixin` | A custom inline base must gain the same nested behavior. |

A nested class with no visible child for the current request renders Django's
native inline template.

## Basic tree

```python
from django.contrib import admin
from django_boosted import AdminBoostModel, NestedStackedInline, NestedTabularInline


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0


class BuildingInline(NestedStackedInline):
    model = Building
    inlines = [RoomInline]
    extra = 0


class CityInline(NestedTabularInline):
    model = City
    inlines = [BuildingInline]
    extra = 0


class CountryAdmin(AdminBoostModel):
    inlines = [CityInline]
```

The parent admin must inherit `AdminBoostModel`. Stacked and tabular layouts
can be mixed at any depth.

Set `extra`, `min_num`, and `max_num` explicitly on every level. Each parent
repeats its child formsets, so a large `extra` grows quickly.

## Direct parent

Child configuration receives the direct parent object, not the root object.
This applies to:

- `get_inlines(request, obj)`
- `has_view_permission`, `has_add_permission`, `has_change_permission`, and
  `has_delete_permission`
- `get_queryset`
- `get_formset`
- `get_fieldsets`, `get_readonly_fields`, and `get_prepopulated_fields`

```python
class BuildingInline(NestedStackedInline):
    model = Building

    def get_inlines(self, request, obj=None):
        if obj is None or not obj.is_active:
            return []
        return [RoomInline]
```

Returning no children makes that inline use Django's native rendering and
add/remove behavior.

An inline cycle raises `ImproperlyConfigured`.

## Saving

Django saves the flat formset list in parent-first order inside its normal
transaction. `save_formset()`, uploaded files, custom forms, and `fk_name`
keep their normal behavior.

These nested rules are added:

- deleting a parent skips validation and saving of its descendants;
- an unchanged extra parent does not create descendant rows;
- **Save as new** duplicates the active tree and points every foreign key at
  the duplicated direct parent.

## Rendering and widgets

Leaf inlines use Django's `admin/edit_inline/stacked.html` or
`admin/edit_inline/tabular.html`, including their native add and remove
controls.

An inline that owns children uses the django-boosted template so each parent
can contain its child formsets. Tabular owners repeat the model name above
each object, for example `Faculty: Sciences`.

Nested groups keep Django's field, widget, and error rendering. The following
admin widgets work at every depth:

- autocomplete fields;
- `prepopulated_fields`;
- `filter_horizontal` and `filter_vertical`;
- date and time shortcuts.

## Limits

- `GenericInlineModelAdmin` and generic relations are not supported.
- The public classes and options are not compatible with `django-nested-admin`.
- Django's native inline JavaScript cannot remove an owner row: it renumbers
  the remaining rows and would break descendant prefixes. Owner rows therefore
  use a separate add/remove controller. Leaf rows stay native.

## Sample

`tests/app/admin/campus.py` registers a campus with tabular faculties, stacked
departments, tabular courses, and stacked seminars. On the campus changelist,
**Generate sample data** creates one tree and opens its change page.
