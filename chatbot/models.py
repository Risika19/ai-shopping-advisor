from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    title = models.CharField(max_length=200, blank=True, default='New Chat')
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f"Chat {self.id}"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class MessageFeedback(models.Model):
    RATING_CHOICES = [
        ('thumbs_up', 'Thumbs Up'),
        ('thumbs_down', 'Thumbs Down'),
    ]

    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='feedback')
    rating = models.CharField(max_length=20, choices=RATING_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['message', 'rating']

    def __str__(self):
        return f"{self.rating} on msg {self.message.id}"


class SearchAnalytics(models.Model):
    query = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ram = models.CharField(max_length=20, blank=True)
    storage = models.CharField(max_length=50, blank=True)
    processor = models.CharField(max_length=200, blank=True)
    results_count = models.IntegerField(default=0)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Search analytics'
        ordering = ['-created_at']

    def __str__(self):
        return f"Search: {self.query[:50]}"
