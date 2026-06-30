from django.test import TestCase, Client
from django.urls import reverse
from .models import Category, Location, Item


class DashboardSmokeTest(TestCase):
    """Minimal smoke tests so the CI pipeline has a real pass/fail signal.
    Expand this as features are added."""

    def setUp(self):
        self.client = Client()

    def test_dashboard_loads(self):
        response = self.client.get(reverse('inventory:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_item_detail_loads(self):
        category = Category.objects.create(name='Electronics')
        location = Location.objects.create(name='Warehouse A')
        item = Item.objects.create(
            item_name='Test Widget',
            barcode_value='TESTBARCODE123',
            category=category,
            location=location,
            quantity=5,
        )
        response = self.client.get(reverse('inventory:item_detail', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Widget')

    def test_print_label_loads(self):
        item = Item.objects.create(item_name='Label Test', barcode_value='LBL001')
        response = self.client.get(reverse('inventory:print_label', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LBL001')
