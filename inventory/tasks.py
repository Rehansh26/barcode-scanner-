import io
from celery import shared_task
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
import barcode
from barcode.writer import ImageWriter
import qrcode
import requests
from .models import Item, ScanLog, AIInsight, Category, Location, ChatMessage
from .bow import retrieve_context_for_question


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def generate_barcode_task(self, item_id):
    try:
        item = Item.objects.get(id=item_id)
    except Item.DoesNotExist:
        return None

    buffer = io.BytesIO()

    if item.barcode_type == Item.BARCODE_QR:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(item.barcode_value)
        qr.make(fit=True)
        image = qr.make_image(fill_color='black', back_color='white')
        image.save(buffer, format='PNG')
        filename = f"{item.barcode_value}_qr.png"
    else:
        writer = ImageWriter()
        code_class = barcode.get_barcode_class('code128')
        code_instance = code_class(item.barcode_value, writer=writer)
        code_instance.write(buffer)
        filename = f"{item.barcode_value}_code128.png"

    buffer.seek(0)
    item.barcode_image.save(filename, ContentFile(buffer.read()), save=False)
    item.save(update_fields=['barcode_image'])
    return item.id


@shared_task
def log_scan_task(barcode_value, matched, item_id=None, notes=''):
    ScanLog.objects.create(
        item_id=item_id,
        barcode_value=barcode_value,
        matched=matched,
        notes=notes,
    )
    return True


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def generate_ai_insight_task(self, category_id=None, location_id=None):
    items_qs = Item.objects.all()
    if category_id:
        items_qs = items_qs.filter(category_id=category_id)
    if location_id:
        items_qs = items_qs.filter(location_id=location_id)
    items_qs = items_qs.order_by('-updated_at')[:50]

    scans_qs = ScanLog.objects.select_related('item').order_by('-scanned_at')
    if category_id:
        scans_qs = scans_qs.filter(item__category_id=category_id)
    if location_id:
        scans_qs = scans_qs.filter(item__location_id=location_id)
    scans_qs = scans_qs[:50]

    item_lines = [
        f"{i.item_name} | qty:{i.quantity} | status:{i.status} | desc:{i.description}"
        for i in items_qs
    ]
    scan_lines = [
        f"{s.scanned_at.isoformat()} | {s.item.item_name if s.item else 'UNKNOWN'} | matched:{s.matched}"
        for s in scans_qs
    ]

    prompt = (
        "You are an inventory analyst. Review the item batch and recent scan logs below. "
        "Summarize current stock health, flag items at risk of running out, and note any "
        "unusual scan patterns. Keep the response under 200 words.\n\n"
        "ITEMS:\n" + "\n".join(item_lines) + "\n\nSCAN LOGS:\n" + "\n".join(scan_lines)
    )

    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                'model': settings.OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get('response', '').strip()
        if not content:
            content = 'Ollama returned an empty response for this batch.'
    except requests.RequestException as exc:
        content = f"AI insight generation failed: {exc}"

    category = Category.objects.filter(id=category_id).first() if category_id else None
    location = Location.objects.filter(id=location_id).first() if location_id else None

    insight = AIInsight.objects.create(
        title=f"Insight generated {timezone.now().strftime('%Y-%m-%d %H:%M')}",
        content=content,
        category=category,
        location=location,
        model_used=settings.OLLAMA_MODEL,
    )
    return insight.id


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def generate_chat_response_task(self, question):
    """
    RAG pipeline for the 'Ask About Your Inventory' chat:
      1. retrieve the most relevant items via bag-of-words / TF-IDF (inventory.bow)
      2. ground an Ollama prompt in ONLY that retrieved context
      3. persist the question/answer/context as a ChatMessage
    """
    ranked = retrieve_context_for_question(question, top_k=8)
    context_lines = [
        f"- {doc.label} | qty:{doc.meta.get('quantity')} | status:{doc.meta.get('status_display')} "
        f"| category:{doc.meta.get('category') or 'none'} | location:{doc.meta.get('location') or 'none'} "
        f"| barcode:{doc.meta.get('barcode_value')}"
        for doc, score in ranked
    ]
    context_block = "\n".join(context_lines) if context_lines else "(no matching inventory items found for this question)"

    prompt = (
        "You are an inventory assistant for a warehouse system. Answer the user's question "
        "using ONLY the inventory data listed below. If the data does not contain the answer, "
        "say plainly that you don't have that information instead of guessing. "
        "Keep the answer under 150 words.\n\n"
        f"RELEVANT INVENTORY DATA:\n{context_block}\n\n"
        f"QUESTION: {question}\nANSWER:"
    )

    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                'model': settings.OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        answer = payload.get('response', '').strip()
        if not answer:
            answer = 'Ollama returned an empty response.'
    except requests.RequestException as exc:
        answer = f"AI chat failed: {exc}"

    chat_message = ChatMessage.objects.create(
        question=question,
        answer=answer,
        context_used=context_block,
    )
    return chat_message.id
