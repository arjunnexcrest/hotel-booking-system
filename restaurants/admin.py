from django.contrib import admin
from .models import Restaurant, RestaurantImage, OperatingHours, SpecialClosure


class RestaurantImageInline(admin.TabularInline):
    model = RestaurantImage
    extra = 1


class OperatingHoursInline(admin.TabularInline):
    model = OperatingHours
    extra = 7


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('name', 'hotel', 'cuisine_type', 'is_active', 'created_at')
    list_filter = ('is_active', 'hotel')
    search_fields = ('name', 'cuisine_type', 'hotel__name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [RestaurantImageInline, OperatingHoursInline]


@admin.register(SpecialClosure)
class SpecialClosureAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'closure_date', 'reason', 'is_all_day')
    list_filter = ('closure_date', 'is_all_day', 'restaurant')
    search_fields = ('restaurant__name', 'reason')
