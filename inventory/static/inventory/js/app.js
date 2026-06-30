function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

function statusBadgeClass(statusCode) {
  const map = {
    IN_STOCK: 'badge-in-stock',
    LOW_STOCK: 'badge-low-stock',
    OUT_OF_STOCK: 'badge-out-of-stock',
    DISCONTINUED: 'badge-discontinued',
  };
  return map[statusCode] || 'badge-in-stock';
}
