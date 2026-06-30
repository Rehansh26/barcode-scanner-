from django import forms
from .models import Item, QualityCheck


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['item_name', 'description', 'category', 'location', 'status', 'quantity', 'barcode_type']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class QualityCheckForm(forms.ModelForm):
    class Meta:
        model = QualityCheck
        fields = [
            'status', 'packaging_ok', 'physical_condition_ok',
            'functionality_ok', 'labeling_ok', 'notes', 'checked_by',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What did you check? Any defects or concerns?'}),
            'checked_by': forms.TextInput(attrs={'placeholder': 'Your name (optional)'}),
        }
