from django.contrib import admin
from .models import Category, Location, Item, ScanLog, AIInsight, ChatMessage, QualityCheck


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['item_name', 'barcode_value', 'category', 'location', 'status', 'quantity', 'updated_at']
    list_filter = ['status', 'category', 'location']
    search_fields = ['item_name', 'barcode_value']


@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ['barcode_value', 'item', 'matched', 'scanned_at']
    list_filter = ['matched']


@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'location', 'model_used', 'created_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['question', 'created_at']
    search_fields = ['question', 'answer']


@admin.register(QualityCheck)
class QualityCheckAdmin(admin.ModelAdmin):
    list_display = ['item', 'status', 'checked_by', 'created_at']
    list_filter = ['status']
    search_fields = ['item__item_name', 'notes', 'checked_by']
