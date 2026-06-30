from django import forms
from .models import Item


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['item_name', 'description', 'category', 'location', 'status', 'quantity', 'barcode_type']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
