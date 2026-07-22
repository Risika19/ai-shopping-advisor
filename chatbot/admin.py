from django.contrib import admin
from .models import ChatSession, ChatMessage, SearchAnalytics


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'session_key', 'message_count', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('title', 'user__username', 'session_key')
    inlines = [ChatMessageInline]
    readonly_fields = ('created_at', 'updated_at')

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('role', 'session', 'content_preview', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content',)
    readonly_fields = ('created_at',)

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = 'Content'


@admin.register(SearchAnalytics)
class SearchAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('query', 'category', 'brand', 'budget', 'results_count', 'created_at')
    list_filter = ('category', 'brand', 'created_at')
    search_fields = ('query', 'category', 'brand')
