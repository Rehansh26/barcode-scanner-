from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Location(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Item(models.Model):
    BARCODE_QR = 'QR'
    BARCODE_CODE128 = 'CODE128'
    BARCODE_TYPE_CHOICES = [
        (BARCODE_QR, 'QR Code'),
        (BARCODE_CODE128, 'Code 128 Barcode'),
    ]

    STATUS_IN_STOCK = 'IN_STOCK'
    STATUS_LOW_STOCK = 'LOW_STOCK'
    STATUS_OUT_OF_STOCK = 'OUT_OF_STOCK'
    STATUS_DISCONTINUED = 'DISCONTINUED'
    STATUS_CHOICES = [
        (STATUS_IN_STOCK, 'In Stock'),
        (STATUS_LOW_STOCK, 'Low Stock'),
        (STATUS_OUT_OF_STOCK, 'Out of Stock'),
        (STATUS_DISCONTINUED, 'Discontinued'),
    ]

    item_name = models.CharField(max_length=200)
    barcode_value = models.CharField(max_length=64, unique=True)
    barcode_type = models.CharField(max_length=10, choices=BARCODE_TYPE_CHOICES, default=BARCODE_QR)
    barcode_image = models.ImageField(upload_to='barcodes/', blank=True, null=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, related_name='items', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(Location, related_name='items', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_STOCK)
    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.item_name} ({self.barcode_value})"

    @property
    def status_css(self):
        mapping = {
            self.STATUS_IN_STOCK: 'in-stock',
            self.STATUS_LOW_STOCK: 'low-stock',
            self.STATUS_OUT_OF_STOCK: 'out-of-stock',
            self.STATUS_DISCONTINUED: 'discontinued',
        }
        return mapping.get(self.status, 'in-stock')

    @property
    def latest_quality_check(self):
        return self.quality_checks.first()  # ordered by -created_at


class QualityCheck(models.Model):
    """A QA review entry for an item. Items can have multiple checks over time,
    forming a quality history; the most recent one represents current QA status."""

    STATUS_PASS = 'PASS'
    STATUS_FAIL = 'FAIL'
    STATUS_NEEDS_REVIEW = 'NEEDS_REVIEW'
    STATUS_CHOICES = [
        (STATUS_PASS, 'Pass'),
        (STATUS_FAIL, 'Fail'),
        (STATUS_NEEDS_REVIEW, 'Needs Review'),
    ]

    item = models.ForeignKey(Item, related_name='quality_checks', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEEDS_REVIEW)

    # Lightweight checklist — common QA criteria. Each defaults to unchecked/False
    # so a reviewer explicitly marks what they verified.
    packaging_ok = models.BooleanField(default=False)
    physical_condition_ok = models.BooleanField(default=False)
    functionality_ok = models.BooleanField(default=False)
    labeling_ok = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    checked_by = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.item.item_name} — {self.get_status_display()} ({self.created_at:%Y-%m-%d})"

    @property
    def status_css(self):
        mapping = {
            self.STATUS_PASS: 'in-stock',
            self.STATUS_FAIL: 'out-of-stock',
            self.STATUS_NEEDS_REVIEW: 'low-stock',
        }
        return mapping.get(self.status, 'low-stock')


class ScanLog(models.Model):
    item = models.ForeignKey(Item, related_name='scan_logs', on_delete=models.SET_NULL, null=True, blank=True)
    barcode_value = models.CharField(max_length=64)
    matched = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scanned_at']

    def __str__(self):
        return f"{self.barcode_value} @ {self.scanned_at}"


class AIInsight(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.ForeignKey(Category, related_name='ai_insights', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(Location, related_name='ai_insights', on_delete=models.SET_NULL, null=True, blank=True)
    model_used = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    """One turn of the RAG-grounded 'Ask About Your Inventory' chat assistant."""
    question = models.TextField()
    answer = models.TextField()
    context_used = models.TextField(blank=True, help_text='Bag-of-words retrieved items used to ground the answer')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.question[:60]
