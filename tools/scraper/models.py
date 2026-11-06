"""Data models and config loading for the Pan Home scraper."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProductItem:
    """One Pan Home product as seen on listing pages (and optionally its detail page)."""
    sku: str
    name: str = ''
    product_url: str = ''
    regular_price: float | None = None
    final_price: float | None = None
    currency: str = 'AED'
    image_url: str | None = None
    category: str = ''                 # Pan Home category path, e.g. accessories/lighting/lamps/table-lamps
    app_category: str = ''             # comparator category: Table Lamp, Basket, Planter...
    filter_materials: list[str] = field(default_factory=list)   # Pan Home "Primary Material" filter names
    app_materials: list[str] = field(default_factory=list)      # comparator keys: rattan, jute, poly_rattan...
    stock_status: str | None = None
    specifications: dict[str, str] = field(default_factory=dict)  # PrimaryMaterial, Length, Width, Height...
    sources: list[str] = field(default_factory=list)              # listing, network, detail
    scraped_at_utc: str = ''

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ProductItem':
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class MaterialFilter:
    id: int
    name: str
    app_material: str | None = None


@dataclass
class ScrapeTarget:
    name: str
    category_path: str
    app_category: str
    materials: list[MaterialFilter] = field(default_factory=list)
    # regex (case-insensitive, matched on product name) -> comparator category; first match wins
    title_category_rules: dict[str, str] = field(default_factory=dict)
    # also read the whole category without a material filter (after the filters), to get every product
    include_unfiltered: bool = False


@dataclass
class ScrapeConfig:
    base_url: str
    targets: list[ScrapeTarget]
    material_aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class ScraperOptions:
    headless: bool = False                  # the person must see and answer verification pages
    channel: str | None = None              # "chrome" / "msedge" to use an installed browser
    cdp_url: str | None = None              # attach to an open Chrome (--remote-debugging-port) instead of launching
    user_data_dir: str = './user_data_dir'  # persistent profile keeps cookies after verification
    output_dir: str = './output'
    max_pages: int = 20                     # per category + material filter (Storage unfiltered ≈ 9 pages)
    min_delay_s: float = 10.0               # Pan Home asked for verification again after ~25 pages at 8-15 s
    max_delay_s: float = 18.0
    pause_every: int = 12                   # longer break every N page loads (0 = never)
    pause_min_s: float = 60.0
    pause_max_s: float = 120.0
    max_retries: int = 3
    human_wait_timeout_s: float = 180.0
    block_images: bool = False
    visit_detail_pages: bool = False
    max_detail_pages: int = 50
    fresh: bool = False
    only_targets: list[str] = field(default_factory=list)
    verbose: bool = False


def load_config(path: str | Path) -> ScrapeConfig:
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    targets = [
        ScrapeTarget(
            name=t['name'],
            category_path=t['category_path'],
            app_category=t['app_category'],
            materials=[MaterialFilter(**m) for m in t.get('materials', [])],
            title_category_rules=t.get('title_category_rules', {}),
            include_unfiltered=bool(t.get('include_unfiltered', False)),
        )
        for t in raw['targets']
    ]
    aliases = {k.lower(): v for k, v in raw.get('material_aliases', {}).items()}
    return ScrapeConfig(base_url=raw['base_url'], targets=targets, material_aliases=aliases)
