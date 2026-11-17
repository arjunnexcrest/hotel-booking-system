from django.contrib import admin
from .models import Hotel, HotelImage, HotelDocument, HotelApproval


class HotelImageInline(admin.TabularInline):
    model = HotelImage
    extra = 1


class HotelDocumentInline(admin.TabularInline):
    model = HotelDocument
    extra = 1


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'phone', 'email', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active', 'city', 'state')
    search_fields = ('name', 'city', 'email', 'phone')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [HotelImageInline, HotelDocumentInline]


@admin.register(HotelDocument)
class HotelDocumentAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'document_type', 'status', 'created_at')
    list_filter = ('document_type', 'status')
    search_fields = ('hotel__name',)


@admin.register(HotelApproval)
class HotelApprovalAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'reviewed_by', 'decision', 'created_at')
    list_filter = ('decision', 'created_at')
    search_fields = ('hotel__name', 'reviewed_by__username', 'reason')
