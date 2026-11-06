"""
Convert scraped products into the comparator catalog format (src/benchmark.json of the app):
{title, category, specs, price_aed, sale_price_aed, url, dimensions[3], materials[], price_checked_at, scope}.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from models import ProductItem
from output import load_products, write_atomic

# Last "AxB(xC) cm" group in the name, optionally prefixed with Dia: "Dia 35x53cm", "24x24x40.5cm", "Dia14.2x24.5cm".
NAME_DIMENSIONS = re.compile(r'(?:dia\.?\s*)?(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)(?:\s*x\s*(\d+(?:\.\d+)?))?\s*cm', re.I)

POLY_RATTAN = re.compile(r'poly\s*(?:rattan|wicker)|resin\s*wicker', re.I)
# Materials named in the product title. Added on top of the filter material so that, for example, a ceramic
# lamp that also appears under the Bamboo filter is not offered as a match for a bamboo-only lamp.
NAME_MATERIALS = [
    (re.compile(r'\brattan\b', re.I), 'rattan'),
    (re.compile(r'\babaca\b', re.I), 'abaca'),
    (re.compile(r'\bjute\b', re.I), 'jute'),
    (re.compile(r'\bsea\s*grass\b', re.I), 'seagrass'),
    (re.compile(r'water\s*hyacinth', re.I), 'water_hyacinth'),
    (re.compile(r'\bbamboo\b', re.I), 'bamboo'),
    (re.compile(r'\bcapiz\b', re.I), 'capiz'),
    (re.compile(r'\bpaper\b', re.I), 'paper'),
    (re.compile(r'\bcotton\b', re.I), 'cotton'),
    (re.compile(r'\bceramic\b', re.I), 'ceramic'),
    (re.compile(r'\bmarble\b', re.I), 'marble'),
    (re.compile(r'\bpolyresin\b', re.I), 'polyresin'),
    (re.compile(r'\bwood(?:en)?\b', re.I), 'wood'),
]


# Product types sold under the same Pan Home categories that are not comparable with a single
# lamp / basket / planter / storage piece in the quotations. They are left out of the catalog.
NOT_COMPARABLE = [
    (re.compile(r'\bbags?\b', re.I), 'túi'),
    (re.compile(r'\b\d+[- ]piece\b|\bset of\b|\bset\b', re.I), 'bộ nhiều món'),
    (re.compile(r'planter stand|\b\d+[- ]tier\b|\b(rack|shelf|shelves|trolley|cart|cabinet|drawers?)\b', re.I),
     'kệ/giá/tủ/ngăn kéo'),
    (re.compile(r'\bhangers?\b|hanging planter', re.I), 'móc treo/chậu treo'),
    (re.compile(r'\b\d+[- ]lights?\b|chandelier', re.I), 'đèn nhiều bóng'),
    (re.compile(r'\borgani[sz]er\b', re.I), 'hộp chia ngăn'),
]


def not_comparable_reason(name: str) -> str | None:
    for pattern, label in NOT_COMPARABLE:
        if pattern.search(name):
            return label
    return None


def dimensions_from_name(name: str) -> list[float] | None:
    """Two numbers follow the comparator convention [A, A, B] (diameter x height); three are kept as is."""
    matches = list(NAME_DIMENSIONS.finditer(name))
    if not matches:
        return None
    m = matches[-1]
    a, b = float(m[1]), float(m[2])
    return [a, b, float(m[3])] if m[3] else [a, a, b]


def dimensions_from_specs(p: ProductItem) -> list[float] | None:
    """Detail-page Length/Width/Height or Diameter/Height, when the detail page was read."""
    def read(key: str) -> float | None:
        try:
            value = float(str(p.specifications.get(key, '')).strip())
            return value if value > 0 else None
        except ValueError:
            return None
    h = read('Height')
    if h is None:
        return None
    if read('Length') and read('Width'):
        return [read('Length'), read('Width'), h]
    if read('Diameter'):
        return [read('Diameter'), read('Diameter'), h]
    return None


def materials_for(p: ProductItem) -> list[str]:
    found = list(p.app_materials)
    name = p.name
    if POLY_RATTAN.search(name):
        if 'poly_rattan' not in found:
            found.append('poly_rattan')
        name = POLY_RATTAN.sub('', name)
    for pattern, key in NAME_MATERIALS:
        if pattern.search(name) and key not in found:
            found.append(key)
    return found


def is_shade_only(name: str) -> bool:
    return bool(re.search(r'\bshade\b', name, re.I)) and not re.search(r'\bwith\b.*\bshade\b|\blamp\b', name, re.I)


def _fmt(n: float) -> str:
    return f'{n:g}'


def build_catalog(products: list[ProductItem]) -> tuple[dict, list[str]]:
    catalog: dict[str, dict] = {}
    skipped: list[str] = []
    for p in sorted(products, key=lambda x: (x.app_category, x.name)):
        price = p.regular_price or p.final_price
        if not price:
            skipped.append(f'{p.sku} {p.name}: không có giá')
            continue
        if not p.app_category:
            skipped.append(f'{p.sku} {p.name}: không có loại hàng')
            continue
        reason = not_comparable_reason(p.name)
        if reason:
            skipped.append(f'{p.sku} {p.name}: loại hàng không so được ({reason})')
            continue
        dims = dimensions_from_specs(p) or dimensions_from_name(p.name)
        if not dims:
            skipped.append(f'{p.sku} {p.name}: không đọc được kích thước')
            continue
        materials = materials_for(p)
        if not materials:
            skipped.append(f'{p.sku} {p.name}: không có vật liệu so khớp được')
            continue

        checked_at = (p.scraped_at_utc or datetime.now(timezone.utc).isoformat())[:10]
        sale = p.final_price
        price_text = (f'Giá gốc {_fmt(price)} AED, đang bán {_fmt(sale)} AED' if sale and sale < price
                      else f'Giá {_fmt(price)} AED')
        catalog[p.sku] = {
            'title': p.name,
            'category': p.app_category,
            'specs': f"Vật liệu Pan Home: {', '.join(p.filter_materials) or '?'} | "
                     f"{' x '.join(_fmt(d) for d in dims)} cm | {price_text} ({checked_at})",
            'price_aed': price,
            'sale_price_aed': sale,
            'url': p.product_url,
            'dimensions': dims,
            'materials': materials,
            'price_checked_at': checked_at,
            'scope': 'shade_only' if is_shade_only(p.name) else 'complete',
            'source': 'panhomestores.com listing' + (' + detail' if 'detail' in p.sources else ''),
        }
    return catalog, skipped


def export_benchmark(products_json: str | Path, existing_benchmark: str | Path, output_path: str | Path) -> dict:
    products = load_products(products_json)
    if not products:
        raise SystemExit(f'Không có sản phẩm trong {products_json}.')
    existing = Path(existing_benchmark)
    # Keep the comparator's tolerances; replace only the product list.
    root = (json.loads(existing.read_text(encoding='utf-8')) if existing.exists()
            else {'dimensionTolerance': 0.2, 'sizeRoundingToleranceCm': 1})
    catalog, skipped = build_catalog(products)
    root['products'] = catalog
    write_atomic(Path(output_path), json.dumps(root, ensure_ascii=False, indent=2))
    per_category: dict[str, int] = {}
    for item in catalog.values():
        per_category[item['category']] = per_category.get(item['category'], 0) + 1
    return {'exported': len(catalog), 'skipped': skipped, 'per_category': per_category,
            'output': str(Path(output_path).resolve())}


def apply_benchmark(generated: str | Path, benchmark_path: str | Path) -> Path:
    """Copy the generated catalog over the comparator's benchmark.json, keeping a dated backup."""
    benchmark_path = Path(benchmark_path)
    backup = benchmark_path.with_name(f'benchmark.backup-{datetime.now():%Y%m%d-%H%M%S}.json')
    if benchmark_path.exists():
        shutil.copy2(benchmark_path, backup)
    shutil.copy2(generated, benchmark_path)
    return backup
