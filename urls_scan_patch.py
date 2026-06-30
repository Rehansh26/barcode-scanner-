# SCAN PATCH — urls.py additions
# Add these two lines to your urlpatterns list in inventory/urls.py
# (alongside your existing item_detail, item_create, etc. patterns)

    path('scan/', views.scan_page, name='scan_page'),
    path('scan/lookup/', views.scan_lookup, name='scan_lookup'),
