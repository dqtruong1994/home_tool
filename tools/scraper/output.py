"""Checkpoint files: products_output.json/.csv, progress.json, captured_json.jsonl, debug_structure.json."""
from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from models import ProductItem

CSV_COLUMNS = ['sku', 'name', 'product_url', 'regular_price', 'final_price', 'currency', 'image_url', 'category',
               'app_category', 'filter_materials', 'app_materials', 'stock_status', 'specifications', 'sources',
               'scraped_at_utc']


def write_atomic(path: Path, content: str, bom: bool = False) -> None:
    """Write to a temp file then replace, so an interrupted run never leaves a half-written checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(content, encoding='utf-8-sig' if bom else 'utf-8', newline='')
    os.replace(tmp, path)


def load_products(path: str | Path) -> list[ProductItem]:
    path = Path(path)
    if not path.exists():
        return []
    return [ProductItem.from_dict(d) for d in json.loads(path.read_text(encoding='utf-8'))]


class OutputWriter:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.products_json = self.dir / 'products_output.json'
        self.products_csv = self.dir / 'products_output.csv'
        self.progress = self.dir / 'progress.json'
        self.captured = self.dir / 'captured_json.jsonl'
        self.debug_structure = self.dir / 'debug_structure.json'

    def load_products(self) -> list[ProductItem]:
        return load_products(self.products_json)

    def load_progress(self) -> set[str]:
        return set(json.loads(self.progress.read_text(encoding='utf-8'))) if self.progress.exists() else set()

    def save_progress(self, completed: Iterable[str]) -> None:
        write_atomic(self.progress, json.dumps(sorted(completed), ensure_ascii=False, indent=2))

    def save_products(self, products: Iterable[ProductItem]) -> None:
        items = sorted(products, key=lambda p: (p.app_category, p.name))
        write_atomic(self.products_json, json.dumps([p.to_dict() for p in items], ensure_ascii=False, indent=2))
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(CSV_COLUMNS)
        for p in items:
            writer.writerow([
                p.sku, p.name, p.product_url,
                '' if p.regular_price is None else p.regular_price,
                '' if p.final_price is None else p.final_price,
                p.currency, p.image_url or '', p.category, p.app_category,
                ' | '.join(p.filter_materials), ' | '.join(p.app_materials), p.stock_status or '',
                ' | '.join(f'{k}: {v}' for k, v in p.specifications.items()), ' | '.join(p.sources),
                p.scraped_at_utc,
            ])
        write_atomic(self.products_csv, buffer.getvalue(), bom=True)   # BOM so Excel opens UTF-8 correctly

    def append_captured(self, url: str, body: str) -> None:
        line = json.dumps({'url': url, 'captured_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                           'length': len(body), 'body': body[:20_000]}, ensure_ascii=False)
        with self.captured.open('a', encoding='utf-8') as f:
            f.write(line + '\n')

    def save_debug_structure(self, data: dict) -> Path:
        write_atomic(self.debug_structure, json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return self.debug_structure.resolve()
