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


class Alphabet(models.Model):
    name: str = models.CharField(max_length=100)  # type: ignore[assignment]
    country: Country = models.ForeignKey(  # type: ignore[assignment]
        Country, on_delete=models.CASCADE, related_name="alphabets"
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ["name"]
