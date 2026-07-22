from django.db import models


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('Laptop', 'Laptop'),
        ('Mobile', 'Mobile'),
        ('Headphone', 'Headphone'),
        ('Smartwatch', 'Smartwatch'),
    ]

    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    ram = models.CharField(max_length=50, blank=True, help_text='e.g. 8GB, 16GB')
    storage = models.CharField(max_length=50, blank=True, help_text='e.g. 256GB SSD, 128GB')
    processor = models.CharField(max_length=200, blank=True, help_text='e.g. Intel i5, Snapdragon 8')
    battery = models.CharField(max_length=100, blank=True, help_text='e.g. 5000mAh')
    display = models.CharField(max_length=200, blank=True, help_text='e.g. 6.5" AMOLED')
    camera = models.CharField(max_length=200, blank=True, help_text='e.g. 48MP + 12MP')
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    description = models.TextField(blank=True)
    features = models.TextField(blank=True, help_text='Comma-separated features')
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.brand} {self.name} ({self.category})'

    class Meta:
        ordering = ['-created_at']


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    sentiment = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - {self.product.name} ({self.rating}/5)'
