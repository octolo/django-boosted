from datetime import date

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from django_boosted import (
    AdminBoostModel,
    NestedStackedInline,
    NestedTabularInline,
    admin_boost_view,
)

from ..models import Campus, Course, Department, Faculty, Seminar

_SAMPLE_TREE = (
    (
        "Sciences",
        (
            (
                "Computer science",
                {
                    "code": "CS",
                    "head": "Ada Lovelace",
                    "email": "cs@example.com",
                    "notes": "Algorithms, systems, and data.",
                },
                (("Databases", "databases"), ("Algorithms", "algorithms")),
            ),
            (
                "Physics",
                {
                    "code": "PHY",
                    "head": "Marie Curie",
                    "email": "physics@example.com",
                    "notes": "Optics and experimental physics.",
                },
                (("Optics", "optics"),),
            ),
        ),
    ),
    (
        "Humanities",
        (
            (
                "History",
                {
                    "code": "HIS",
                    "head": "Marc Bloch",
                    "email": "history@example.com",
                    "notes": "Medieval and modern history.",
                },
                (("Medieval Europe", "medieval-europe"),),
            ),
        ),
    ),
)


class CourseInline(admin.TabularInline):
    """Tabular leaf inside a stacked department."""

    model = Course
    extra = 1
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "slug", "starts_on")


class SeminarInline(admin.StackedInline):
    """Stacked sibling of the course table, under the same department."""

    model = Seminar
    extra = 1
    fields = ("title", "speaker", "room", "held_on")


class DepartmentInline(NestedStackedInline):
    """Stacked group nested under each faculty row."""

    model = Department
    extra = 1
    inlines = [CourseInline, SeminarInline]
    fields = ("name", "code", "head", "email", "established", "active", "notes")


class FacultyInline(NestedTabularInline):
    """Tabular group whose child departments use the stacked frame."""

    model = Faculty
    extra = 1
    inlines = [DepartmentInline]


class CampusAdmin(AdminBoostModel):
    inlines = [FacultyInline]
    search_fields = ["name"]
    list_display = ["name"]

    @admin_boost_view("confirm", "Generate sample data", permission="add")
    def generate_sample_data(self, request, confirmed=False):
        if not confirmed:
            return {
                "confirm": (
                    "Create a campus with faculties, departments, and courses "
                    "so the nested inlines can be tested?"
                )
            }
        campus = _create_sample_campus()
        url = reverse("admin:tests_app_campus_change", args=[campus.pk])
        return HttpResponseRedirect(url)


def _create_sample_campus() -> Campus:
    campus = Campus.objects.create(name=f"Sample campus {Campus.objects.count() + 1}")
    for faculty_name, departments in _SAMPLE_TREE:
        faculty = Faculty.objects.create(name=faculty_name, campus=campus)
        for department_name, details, courses in departments:
            department = Department.objects.create(
                name=department_name,
                faculty=faculty,
                established=date(1998, 9, 1),
                **details,
            )
            for course_name, slug in courses:
                Course.objects.create(
                    name=course_name,
                    slug=slug,
                    starts_on=date(2026, 9, 1),
                    department=department,
                )
            Seminar.objects.create(
                title=f"{department_name} seminar",
                speaker=details["head"],
                room="A12",
                held_on=date(2026, 10, 6),
                department=department,
            )
    return campus
