from django.db import models
from core.models import TimeStampedModel


class Restaurant(TimeStampedModel):
    """
    Dining facility or dining area operating within a hotel.
    """
    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='restaurants'
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    cuisine_type = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'restaurants'
        unique_together = ('hotel', 'slug')
        indexes = [
            models.Index(fields=['hotel', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.hotel.name})"


class RestaurantImage(TimeStampedModel):
    """
    Image gallery for restaurants/dining areas.
    """
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='restaurants/images/')
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = 'restaurant_images'

    def __str__(self):
        return f"Image for {self.restaurant.name}"


class OperatingHours(TimeStampedModel):
    """
    Weekly operating schedule for a restaurant.
    """
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, 'Monday'
        TUESDAY = 1, 'Tuesday'
        WEDNESDAY = 2, 'Wednesday'
        THURSDAY = 3, 'Thursday'
        FRIDAY = 4, 'Friday'
        SATURDAY = 5, 'Saturday'
        SUNDAY = 6, 'Sunday'

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='operating_hours'
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        db_table = 'operating_hours'
        unique_together = ('restaurant', 'day_of_week')
        ordering = ['day_of_week', 'opening_time']

    def __str__(self):
        status = "Closed" if self.is_closed else f"{self.opening_time} - {self.closing_time}"
        return f"{self.restaurant.name}: {self.get_day_of_week_display()} ({status})"


class SpecialClosure(TimeStampedModel):
    """
    Special holiday, maintenance or blackout closures.
    """
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='special_closures'
    )
    closure_date = models.DateField()
    reason = models.CharField(max_length=255)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=True)

    class Meta:
        db_table = 'special_closures'

    def __str__(self):
        return f"{self.restaurant.name} closed on {self.closure_date} ({self.reason})"
