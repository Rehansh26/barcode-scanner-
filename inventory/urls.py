from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('items/<int:pk>/', views.item_detail, name='item_detail'),
    path('generate/', views.generate_barcode, name='generate_barcode'),
    path('generate/status/<str:task_id>/', views.task_status, name='task_status'),
    path('scan/', views.scan_page, name='scan_page'),
    path('scan/lookup/', views.scan_lookup, name='scan_lookup'),
    path('ai-insights/', views.ai_insights_list, name='ai_insights_list'),
    path('ai-insights/generate/', views.trigger_ai_insight, name='trigger_ai_insight'),
    path('ai-insights/status/<str:task_id>/', views.ai_task_status, name='ai_task_status'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('locations/add/', views.location_create, name='location_create'),
    path('locations/<int:pk>/delete/', views.location_delete, name='location_delete'),
    path('knowledge-graph/', views.knowledge_graph_view, name='knowledge_graph'),
    path('knowledge-graph/data/', views.knowledge_graph_data, name='knowledge_graph_data'),
    path('ai-chat/', views.ai_chat_page, name='ai_chat_page'),
    path('ai-chat/ask/', views.trigger_chat_message, name='trigger_chat_message'),
    path('ai-chat/status/<str:task_id>/', views.chat_task_status, name='chat_task_status'),
    path('search/', views.search_results, name='search_results'),
    path('items/<int:pk>/print/', views.print_label, name='print_label'),
    path('items/print-bulk/', views.print_labels_bulk, name='print_labels_bulk'),
    path('items/<int:pk>/quality-check/', views.quality_check_create, name='quality_check_create'),
]
