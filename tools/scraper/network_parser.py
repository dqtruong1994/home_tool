"""Find product-like objects (sku + name) in JSON the page loaded itself, e.g. Magento GraphQL products.items."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

from models import ProductItem


def parse_products(data: Any, base_url: str) -> list[ProductItem]:
    return list(_walk(data, base_url, 0))


def _walk(node: Any, base_url: str, depth: int) -> Iterator[ProductItem]:
    if depth > 25:
        return
    if isinstance(node, dict):
        item = _read(node, base_url)
        if item:
            yield item
        for value in node.values():
            yield from _walk(value, base_url, depth + 1)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value, base_url, depth + 1)


def _num(value: Any) -> float | None:
    try:
        n = float(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _path(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _read(obj: dict, base_url: str) -> ProductItem | None:
    sku, name = obj.get('sku'), obj.get('name')
    if not isinstance(sku, str) or not isinstance(name, str) or not sku.strip() or not name.strip():
        return None
    item = ProductItem(sku=sku.strip().upper(), name=name.strip(), sources=['network'],
                       scraped_at_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))

    url = obj.get('canonical_url') or obj.get('url')
    if isinstance(url, str) and url:
        item.product_url = url if url.startswith('http') else base_url.rstrip('/') + '/' + url.lstrip('/')
    elif isinstance(obj.get('url_key'), str):
        item.product_url = base_url.rstrip('/') + '/' + obj['url_key'] + (obj.get('url_suffix') or '')

    # Magento GraphQL: price_range.minimum_price.{regular_price,final_price}.value
    item.regular_price = _num(_path(obj, 'price_range', 'minimum_price', 'regular_price', 'value'))
    item.final_price = _num(_path(obj, 'price_range', 'minimum_price', 'final_price', 'value'))
    currency = _path(obj, 'price_range', 'minimum_price', 'final_price', 'currency') or obj.get('currency')
    if isinstance(currency, str):
        item.currency = currency
    # Generic search-provider shapes
    item.regular_price = item.regular_price or _num(obj.get('regular_price')) or _num(obj.get('price'))
    item.final_price = item.final_price or _num(obj.get('special_price')) or _num(obj.get('final_price')) or item.regular_price

    stock = obj.get('stock_status')
    item.stock_status = stock if isinstance(stock, str) else None
    for image in (_path(obj, 'small_image', 'url'), _path(obj, 'image', 'url'), _path(obj, 'thumbnail', 'url'),
                  obj.get('image_url'), obj.get('image')):
        if isinstance(image, str) and image:
            item.image_url = image
            break
    return item
