from django.db import models


class Country(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
        verbose_name = "Country"
        verbose_name_plural = "Countries"


class City(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]
    country: Country = models.ForeignKey(  # type: ignore[assignment]
        Country, on_delete=models.CASCADE, related_name="cities"
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
        verbose_name = "City"
        verbose_name_plural = "Cities"


class Campus(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
        verbose_name = "Campus"
        verbose_name_plural = "Campuses"


class Faculty(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]
    campus: Campus = models.ForeignKey(  # type: ignore[assignment]
        Campus, on_delete=models.CASCADE, related_name="faculties"
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
        verbose_name = "Faculty"
        verbose_name_plural = "Faculties"


class Department(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]
    code: str = models.CharField(max_length=20, blank=True)  # type: ignore[assignment]
    head: str = models.CharField(max_length=100, blank=True)  # type: ignore[assignment]
    email: str = models.EmailField(blank=True)  # type: ignore[assignment]
    established = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    notes: str = models.TextField(blank=True)  # type: ignore[assignment]
    faculty: Faculty = models.ForeignKey(  # type: ignore[assignment]
        Faculty, on_delete=models.CASCADE, related_name="departments"
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
        verbose_name = "Department"
        verbose_name_plural = "Departments"


class Course(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]
    slug: str = models.SlugField(max_length=100, blank=True)  # type: ignore[assignment]
    starts_on = models.DateField(null=True, blank=True)
    department: Department = models.ForeignKey(  # type: ignore[assignment]
        Department, on_delete=models.CASCADE, related_name="courses"
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
        verbose_name = "Course"
        verbose_name_plural = "Courses"


class Seminar(models.Model):
    title: str = models.CharField(max_length=100)  # type: ignore[assignment]
    speaker: str = models.CharField(max_length=100, blank=True)  # type: ignore[assignment]
    room: str = models.CharField(max_length=50, blank=True)  # type: ignore[assignment]
    held_on = models.DateField(null=True, blank=True)
    department: Department = models.ForeignKey(  # type: ignore[assignment]
        Department, on_delete=models.CASCADE, related_name="seminars"
    )

    def __str__(self) -> str:
        return str(self.title)

    class Meta:
        ordering = ["title"]
        verbose_name = "Seminar"
        verbose_name_plural = "Seminars"


class Alphabet(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]
    country: Country = models.ForeignKey(  # type: ignore[assignment]
        Country, on_delete=models.CASCADE, related_name="alphabets"
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
