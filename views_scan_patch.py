"""
SCAN PATCH — views.py additions
=================================
Add these two views to inventory/views.py.

ASSUMPTIONS (adjust to match your actual Item model/fields):
  - Your Item model has a field that stores the barcode value.
    This patch assumes it's called `barcode` (CharField).
    If yours is named differently (e.g. `sku`, `code`), do a find/replace
    of `barcode=code` and `Item.barcode` below.
  - You have an existing "add item" view/URL named `item_create` that
    renders a form. This patch tries to prefill it via a GET querystring
    param `?barcode=<value>` — your add-item view/template needs to read
    that querystring and prefill the form's initial barcode field.
    If your add-item view doesn't support that yet, see the note at the
    bottom of this file for the one-line addition needed.

Add this import at the top of views.py if not already present:
    from django.shortcuts import render, redirect, get_object_or_404
    from django.urls import reverse
"""

def scan_page(request):
    """Renders the camera/upload scan UI. No backend decoding —
    decoding happens client-side in the browser via ZXing."""
    return render(request, "inventory/scan.html")


def scan_lookup(request):
    """Receives a decoded barcode value (?code=...) and either:
      - redirects to the existing item's detail page if found, or
      - redirects to the add-item form with the code prefilled.
    """
    code = request.GET.get("code", "").strip()
    if not code:
        return redirect("scan_page")

    item = Item.objects.filter(barcode=code).first()
    if item:
        return redirect("item_detail", pk=item.pk)

    # No existing item — send to add-item form with barcode prefilled.
    return redirect(f"{reverse('item_create')}?barcode={code}")


# --------------------------------------------------------------------
# NOTE: prefilling the add-item form
# --------------------------------------------------------------------
# In your existing item_create view, add this near the top (GET branch)
# so the form shows up with the scanned code already filled in:
#
#   def item_create(request):
#       initial = {}
#       if request.method == "GET" and request.GET.get("barcode"):
#           initial["barcode"] = request.GET["barcode"]
#       if request.method == "POST":
#           form = ItemForm(request.POST)
#           ...
#       else:
#           form = ItemForm(initial=initial)
#       ...
#
# If your item_create already uses `initial=...` for something else,
# just merge `barcode` into that existing dict instead of overwriting it.
