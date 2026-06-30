import csv
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.db.models import Q
from django.contrib import messages
from celery.result import AsyncResult
from .models import Item, Category, Location, ScanLog, AIInsight, ChatMessage, QualityCheck
from .forms import ItemForm, QualityCheckForm
from .tasks import generate_barcode_task, log_scan_task, generate_ai_insight_task, generate_chat_response_task
from . import bow


def dashboard(request):
    items = Item.objects.select_related('category', 'location').prefetch_related('quality_checks').all()
    category_id = request.GET.get('category')
    location_id = request.GET.get('location')
    status = request.GET.get('status')
    query = request.GET.get('q')

    if category_id:
        items = items.filter(category_id=category_id)
    if location_id:
        items = items.filter(location_id=location_id)
    if status:
        items = items.filter(status=status)
    if query:
        items = items.filter(Q(item_name__icontains=query) | Q(barcode_value__icontains=query))

    recent_scans = ScanLog.objects.select_related('item').order_by('-scanned_at')[:10]

    context = {
        'items': items.order_by('-updated_at')[:100],
        'categories': Category.objects.all(),
        'locations': Location.objects.all(),
        'status_choices': Item.STATUS_CHOICES,
        'recent_scans': recent_scans,
        'selected_category': category_id or '',
        'selected_location': location_id or '',
        'selected_status': status or '',
        'query': query or '',
        'total_items': Item.objects.count(),
        'low_stock_count': Item.objects.filter(status=Item.STATUS_LOW_STOCK).count(),
        'out_of_stock_count': Item.objects.filter(status=Item.STATUS_OUT_OF_STOCK).count(),
    }
    return render(request, 'inventory/dashboard.html', context)


def item_detail(request, pk):
    item = get_object_or_404(Item.objects.select_related('category', 'location'), pk=pk)
    scan_logs = item.scan_logs.order_by('-scanned_at')[:20]
    quality_checks = item.quality_checks.all()
    quality_form = QualityCheckForm()
    return render(request, 'inventory/item_detail.html', {
        'item': item,
        'scan_logs': scan_logs,
        'quality_checks': quality_checks,
        'quality_form': quality_form,
    })


@require_POST
def quality_check_create(request, pk):
    item = get_object_or_404(Item, pk=pk)
    form = QualityCheckForm(request.POST)
    if form.is_valid():
        check = form.save(commit=False)
        check.item = item
        check.save()
        messages.success(request, f'Quality check logged: {check.get_status_display()}.')
    else:
        messages.error(request, 'Could not save quality check — please check the form.')
    return redirect('inventory:item_detail', pk=item.pk)


def generate_barcode(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.barcode_value = uuid.uuid4().hex[:12].upper()
            item.save()
            task = generate_barcode_task.delay(item.id)
            return JsonResponse({'task_id': task.id, 'item_id': item.id})
        return JsonResponse({'errors': form.errors}, status=400)

    # Prefill barcode_value if arriving from the scan page with an unmatched code
    form = ItemForm(initial={'barcode_value': request.GET.get('barcode_value', '')})
    context = {
        'form': form,
        'categories': Category.objects.all(),
        'locations': Location.objects.all(),
        'barcode_type_choices': Item.BARCODE_TYPE_CHOICES,
        'status_choices': Item.STATUS_CHOICES,
    }
    return render(request, 'inventory/generate_barcode.html', context)


def task_status(request, task_id):
    result = AsyncResult(task_id)
    payload = {'state': result.state, 'ready': result.ready()}
    if result.ready() and result.successful():
        item = Item.objects.filter(id=result.result).first()
        if item:
            payload['item_id'] = item.id
            payload['item_name'] = item.item_name
            payload['barcode_value'] = item.barcode_value
            payload['barcode_image_url'] = item.barcode_image.url if item.barcode_image else ''
            payload['detail_url'] = reverse('inventory:item_detail', args=[item.id])
    return JsonResponse(payload)


def scan_page(request):
    return render(request, 'inventory/scan.html')


@require_POST
def scan_lookup(request):
    barcode_value = request.POST.get('barcode_value', '').strip()
    if not barcode_value:
        return JsonResponse({'found': False, 'message': 'No barcode value received'}, status=400)

    item = Item.objects.select_related('category', 'location').filter(barcode_value=barcode_value).first()
    matched = item is not None
    log_scan_task.delay(barcode_value, matched, item.id if item else None)

    if not matched:
        return JsonResponse({'found': False, 'message': 'No matching item found', 'barcode_value': barcode_value})

    return JsonResponse({
        'found': True,
        'item': {
            'id': item.id,
            'item_name': item.item_name,
            'barcode_value': item.barcode_value,
            'description': item.description,
            'status': item.get_status_display(),
            'status_css': item.status_css,
            'quantity': item.quantity,
            'category': item.category.name if item.category else '',
            'location': item.location.name if item.location else '',
            'detail_url': reverse('inventory:item_detail', args=[item.id]),
            'barcode_image_url': item.barcode_image.url if item.barcode_image else '',
        }
    })


def ai_insights_list(request):
    insights = AIInsight.objects.select_related('category', 'location').order_by('-created_at')[:30]
    context = {
        'insights': insights,
        'categories': Category.objects.all(),
        'locations': Location.objects.all(),
    }
    return render(request, 'inventory/ai_insights.html', context)


@require_POST
def trigger_ai_insight(request):
    category_id = request.POST.get('category') or None
    location_id = request.POST.get('location') or None
    task = generate_ai_insight_task.delay(category_id, location_id)
    return JsonResponse({'task_id': task.id})


def ai_task_status(request, task_id):
    result = AsyncResult(task_id)
    payload = {'state': result.state, 'ready': result.ready()}
    if result.ready() and result.successful():
        insight = AIInsight.objects.filter(id=result.result).first()
        if insight:
            payload['title'] = insight.title
            payload['content'] = insight.content
            payload['created_at'] = insight.created_at.isoformat()
    return JsonResponse(payload)


def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="items_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Item Name', 'Barcode Value', 'Category', 'Location', 'Status', 'Quantity', 'Description', 'Created At', 'Updated At'])
    for item in Item.objects.select_related('category', 'location').all():
        writer.writerow([
            item.id,
            item.item_name,
            item.barcode_value,
            item.category.name if item.category else '',
            item.location.name if item.location else '',
            item.get_status_display(),
            item.quantity,
            item.description,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
        ])
    return response


# ---------------------------------------------------------------------------
# Category / Location management (inline dashboard CRUD)
# ---------------------------------------------------------------------------

@require_POST
def category_create(request):
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    if not name:
        messages.error(request, 'Category name is required.')
    elif Category.objects.filter(name__iexact=name).exists():
        messages.error(request, f'Category "{name}" already exists.')
    else:
        Category.objects.create(name=name, description=description)
        messages.success(request, f'Category "{name}" added.')
    return redirect('inventory:dashboard')


@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    category.delete()
    messages.success(request, f'Category "{name}" deleted. Its items keep their other fields but lose this category.')
    return redirect('inventory:dashboard')


@require_POST
def location_create(request):
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    if not name:
        messages.error(request, 'Location name is required.')
    elif Location.objects.filter(name__iexact=name).exists():
        messages.error(request, f'Location "{name}" already exists.')
    else:
        Location.objects.create(name=name, description=description)
        messages.success(request, f'Location "{name}" added.')
    return redirect('inventory:dashboard')


@require_POST
def location_delete(request, pk):
    location = get_object_or_404(Location, pk=pk)
    name = location.name
    location.delete()
    messages.success(request, f'Location "{name}" deleted. Its items keep their other fields but lose this location.')
    return redirect('inventory:dashboard')


# ---------------------------------------------------------------------------
# Knowledge graph (visual node-link graph + grouped list view)
# ---------------------------------------------------------------------------

def knowledge_graph_view(request):
    items = Item.objects.select_related('category', 'location').order_by('category__name', 'item_name')
    context = {
        'items': items,
        'item_count': Item.objects.count(),
        'category_count': Category.objects.count(),
        'location_count': Location.objects.count(),
    }
    return render(request, 'inventory/knowledge_graph.html', context)


def knowledge_graph_data(request):
    """JSON node/edge payload consumed by graph.js to render the force-directed graph."""
    nodes = []
    edges = []

    for category in Category.objects.all():
        nodes.append({'id': f'cat-{category.id}', 'label': category.name, 'type': 'category'})
    for location in Location.objects.all():
        nodes.append({'id': f'loc-{location.id}', 'label': location.name, 'type': 'location'})

    # Cap items so the graph stays readable/performant on large inventories.
    items = Item.objects.select_related('category', 'location').order_by('-updated_at')[:300]
    for item in items:
        node_id = f'item-{item.id}'
        nodes.append({
            'id': node_id,
            'label': item.item_name,
            'type': 'item',
            'status': item.status,
        })
        if item.category_id:
            edges.append({'source': node_id, 'target': f'cat-{item.category_id}'})
        if item.location_id:
            edges.append({'source': node_id, 'target': f'loc-{item.location_id}'})

    return JsonResponse({'nodes': nodes, 'edges': edges})


# ---------------------------------------------------------------------------
# RAG chat assistant ("Ask About Your Inventory")
# ---------------------------------------------------------------------------

def ai_chat_page(request):
    chat_messages = list(reversed(ChatMessage.objects.order_by('-created_at')[:30]))
    return render(request, 'inventory/ai_chat.html', {'chat_messages': chat_messages})


@require_POST
def trigger_chat_message(request):
    question = request.POST.get('question', '').strip()
    if not question:
        return JsonResponse({'error': 'Please enter a question.'}, status=400)
    task = generate_chat_response_task.delay(question)
    return JsonResponse({'task_id': task.id})


def chat_task_status(request, task_id):
    result = AsyncResult(task_id)
    payload = {'state': result.state, 'ready': result.ready()}
    if result.ready() and result.successful():
        chat_message = ChatMessage.objects.filter(id=result.result).first()
        if chat_message:
            payload['question'] = chat_message.question
            payload['answer'] = chat_message.answer
            payload['context_used'] = chat_message.context_used
            payload['created_at'] = chat_message.created_at.isoformat()
    return JsonResponse(payload)


# ---------------------------------------------------------------------------
# Global search (bag-of-words / TF-IDF ranked across items, categories, locations)
# ---------------------------------------------------------------------------

def search_results(request):
    query = request.GET.get('q', '').strip()
    grouped = {'item': [], 'category': [], 'location': []}
    total = 0

    if query:
        ranked = bow.search(query, top_k=60)
        seen_item_ids = set()
        for doc, score in ranked:
            grouped[doc.doc_type].append({'doc': doc, 'score': round(score, 3)})
            if doc.doc_type == 'item':
                seen_item_ids.add(doc.object_id)
        total = sum(len(v) for v in grouped.values())

    return render(request, 'inventory/search_results.html', {
        'query': query,
        'grouped': grouped,
        'total': total,
    })


def print_label(request, pk):
    """Single-item printable label page. Opens print-ready, triggers window.print() on load."""
    item = get_object_or_404(Item, pk=pk)
    return render(request, 'inventory/print_label.html', {
        'items': [item],
        'auto_print': True,
    })


def print_labels_bulk(request):
    """
    Printable label sheet for multiple items.
    Accepts ?ids=1,2,3 (GET) for quick links, or a POST with ids[] from a selection form.
    """
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
    else:
        raw = request.GET.get('ids', '')
        ids = [v for v in raw.split(',') if v.strip()]

    items = Item.objects.filter(pk__in=ids) if ids else Item.objects.none()

    if not items.exists():
        messages.warning(request, 'No items selected to print.')
        return redirect('inventory:dashboard')

    return render(request, 'inventory/print_label.html', {
        'items': items,
        'auto_print': True,
    })