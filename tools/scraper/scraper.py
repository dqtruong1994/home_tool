"""
Human-in-the-loop reader for Pan Home listing pages (Playwright, async).

It does not hide automation and does not try to get past verification pages. When one appears it
prints a clear message, beeps, and waits for the person to complete it in the visible window.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Request, Response, Route, async_playwright

import page_scripts as js
from benchmark_export import dimensions_from_name, materials_for
from models import MaterialFilter, ProductItem, ScrapeConfig, ScraperOptions, ScrapeTarget
from network_parser import parse_products
from output import OutputWriter

SITE_HOST = 'panhomestores.com'
JSON_URL_KEYWORDS = re.compile(r'graphql|algolia|klevu|catalog|products?|search', re.I)
# Hosts/paths used by verification pages. Nothing on them is ever blocked.
VERIFICATION_URL = re.compile(r'challenges\.cloudflare\.com|/cdn-cgi/|captcha|akamai|perimeterx|datadome', re.I)
VERIFICATION_TITLE = re.compile(r'just a moment|attention required|access denied|verify', re.I)
LOAD_MORE = re.compile(r'^\s*(load|show|view)\s+more', re.I)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def log(message: str, level: str = 'INFO') -> None:
    colors = {'INFO': '', 'WARN': '\033[33m', 'ERROR': '\033[31m', 'DEBUG': '\033[90m'}
    reset = '\033[0m' if colors.get(level) else ''
    line = f"{colors.get(level, '')}[{datetime.now():%H:%M:%S}] {message}{reset}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:   # console without UTF-8: never stop scraping because of a log line
        encoding = getattr(sys.stdout, 'encoding', None) or 'ascii'
        print(line.encode(encoding, errors='replace').decode(encoding), flush=True)


def beep() -> None:
    try:
        import winsound
        winsound.Beep(880, 250)
        winsound.Beep(660, 350)
    except (ImportError, RuntimeError):
        print('\a', end='', flush=True)


def enter_pressed() -> bool:
    """Non-blocking check for Enter in the terminal."""
    if not sys.stdin or not sys.stdin.isatty():
        return False
    if sys.platform == 'win32':
        import msvcrt
        pressed = False
        while msvcrt.kbhit():
            if msvcrt.getwch() in ('\r', '\n'):
                pressed = True
        return pressed
    import select
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if ready:
        sys.stdin.readline()
        return True
    return False


class StopRun(RuntimeError):
    """Stop the whole run with a message; data saved so far is kept and the same command resumes."""


def pid_alive(pid: int) -> bool:
    if sys.platform == 'win32':
        # os.kill(pid, 0) on Windows sends CTRL_C_EVENT, so ask the OS instead.
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259                                # STILL_ACTIVE
    import os
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class RunLock:
    """One scraper per output folder: two runs would overwrite each other's products_output.json."""

    def __init__(self, directory):
        from pathlib import Path
        self.path = Path(directory) / 'run.lock'
        self.held = False

    def acquire(self) -> None:
        import os
        if self.path.exists():
            try:
                other = int(self.path.read_text().strip())
            except ValueError:
                other = 0
            if other and other != os.getpid() and pid_alive(other):
                raise StopRun(f'Đang có một lần chạy khác dùng cùng thư mục output (PID {other}).\n'
                              '  → Dừng nó trước (Ctrl+C trong terminal đang chạy), rồi chạy lại lệnh này.')
        self.path.write_text(str(os.getpid()))
        self.held = True

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False


class ChromeNotOpenError(RuntimeError):
    """No Chrome is listening on the debug port."""

    def __init__(self, cdp_url: str, detail: str):
        self.cdp_url = cdp_url
        self.detail = detail
        super().__init__(
            f'Không kết nối được Chrome ở {cdp_url}.\n'
            '  → Chưa có cửa sổ Chrome nào mở cổng debug. Nhấp đúp Mo_Chrome_Debug.bat trước, rồi chạy lại lệnh này.\n'
            '  → Chrome bạn mở bình thường KHÔNG có cổng debug; phải dùng cửa sổ do Mo_Chrome_Debug.bat mở.\n'
            '  → Nếu bạn mở Chrome ở cổng khác, thêm --cdp-url http://localhost:<cổng>.\n'
            f'  (Chi tiết: {shorten(detail.splitlines()[0] if detail else "", 120)})')


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + '…'


class PanHomeScraper:
    def __init__(self, options: ScraperOptions, config: ScrapeConfig):
        self.opt = options
        self.config = config
        self.out = OutputWriter(options.output_dir)
        self.products: dict[str, ProductItem] = {}
        self.network_products: dict[str, ProductItem] = {}
        self.completed: set[str] = set()
        self.xhr_log: list[str] = []
        self.waiting_for_human = False
        self.last_navigation = 0.0
        self.page_loads = 0
        self.inspected_once = False
        self._pw = None
        self._browser = None
        self._own_page = False
        self._context = None
        self._page: Page | None = None
        self._tasks: set[asyncio.Task] = set()
        self._lock = RunLock(options.output_dir)

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError('Call start() first.')
        return self._page

    # ------------------------------------------------------------ Step 1: browser

    def load_checkpoint(self) -> None:
        self._lock.acquire()   # before reading checkpoints, so two runs never load/overwrite the same files
        if not self.opt.fresh:
            self.products = {p.sku: p for p in self.out.load_products()}
            self.completed = self.out.load_progress()
            if self.products:
                log(f'Tiếp tục từ checkpoint: {len(self.products)} sản phẩm, {len(self.completed)} trang lọc đã xong.')

    def filter_passes(self) -> list[tuple[str, ScrapeTarget, MaterialFilter | None]]:
        """Every (progress key, target, filter) in run order: material filters first, then the whole category."""
        only = [o.lower() for o in self.opt.only_targets]
        passes = []
        for target in self.config.targets:
            if only and not any(o in target.name.lower() for o in only):
                continue
            filters: list[MaterialFilter | None] = list(target.materials)
            if target.include_unfiltered or not filters:
                filters.append(None)
            for flt in filters:
                passes.append((f"{target.name}|{flt.id if flt else 'all'}", target, flt))
        return passes

    async def start(self) -> None:
        self.load_checkpoint()

        self._pw = await async_playwright().start()
        if self.opt.cdp_url:
            # Attach to a Chrome window the person already opened with --remote-debugging-port.
            # Use its existing context; work in a tab of our own so the person's tabs are left alone.
            log(f'Kết nối Chrome đang mở qua {self.opt.cdp_url} ...')
            try:
                self._browser = await self._pw.chromium.connect_over_cdp(self.opt.cdp_url, timeout=15_000)
            except PlaywrightError as ex:
                raise ChromeNotOpenError(self.opt.cdp_url, str(ex)) from None
            if not self._browser.contexts:
                raise RuntimeError('Chrome không có cửa sổ nào đang mở.')
            self._context = self._browser.contexts[0]
            await self._context.route('**/*', self._handle_route)
            self._page = await self._context.new_page()
            self._own_page = True
        else:
            # Persistent profile: a verification completed by the person is remembered like in a normal browser.
            # No user-agent override and no automation flags are changed.
            self._context = await self._pw.chromium.launch_persistent_context(
                self.opt.user_data_dir,
                headless=self.opt.headless,
                channel=self.opt.channel,
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
            )
            await self._context.route('**/*', self._handle_route)
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        self._page.set_default_timeout(45_000)
        self._page.on('response', self._on_response)
        self._page.on('request', self._on_request)

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._browser:
            # Attached Chrome belongs to the person: close only our tab, remove our routing, then disconnect.
            try:
                if self._own_page and self._page and not self._page.is_closed():
                    await self._page.close()
                if self._context:
                    await self._context.unroute('**/*', self._handle_route)
            except PlaywrightError:
                pass
        elif self._context:
            await self._context.close()
        if self._pw:
            await self._pw.stop()
        self.release_lock()

    def release_lock(self) -> None:
        self._lock.release()

    async def _handle_route(self, route: Route) -> None:
        if self._should_block(route.request):
            await route.abort()
        else:
            await route.continue_()

    def _should_block(self, request: Request) -> bool:
        """Only fonts/media (and optionally images) on panhomestores.com, never while verification is open."""
        if self.waiting_for_human or VERIFICATION_URL.search(request.url):
            return False
        host = urlparse(request.url).hostname or ''
        if not host.endswith(SITE_HOST):
            return False
        if request.resource_type in ('font', 'media'):
            return True
        return request.resource_type == 'image' and self.opt.block_images

    # ------------------------------------------------------------ Step 2: passive network capture

    def _on_request(self, request: Request) -> None:
        if request.resource_type in ('xhr', 'fetch') and len(self.xhr_log) < 500:
            self.xhr_log.append(f'{request.method} {request.url}')

    def _on_response(self, response: Response) -> None:
        task = asyncio.create_task(self._capture_response(response))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _capture_response(self, response: Response) -> None:
        """Reads JSON the page itself loads. No extra requests are sent."""
        try:
            if response.status != 200:
                return
            if 'application/json' not in response.headers.get('content-type', '').lower():
                return
            if not JSON_URL_KEYWORDS.search(response.url):
                return
            body = await response.text()
            data = json.loads(body)
            keys = ', '.join(list(data)[:10]) if isinstance(data, dict) else type(data).__name__
            if self.opt.verbose:
                log(f'JSON bắt được: {shorten(response.url, 120)} [{keys}]', 'DEBUG')
            self.out.append_captured(response.url, body)
            found = parse_products(data, self.config.base_url)
            for item in found:
                self.network_products[item.sku] = item
            if found:
                log(f'  + {len(found)} sản phẩm từ gói JSON ({shorten(response.url, 80)})')
        except (PlaywrightError, ValueError):
            pass  # body unavailable (redirect, page closed) or not JSON after all

    # ------------------------------------------------------------ Step 3: navigation, verification, pagination

    async def run(self) -> None:
        passes = self.filter_passes()
        if not passes:
            log('Không có target nào khớp --only.', 'WARN')
            return

        for key, target, flt in passes:
            if key in self.completed:
                log(f'Bỏ qua (đã xong): {key}')
                continue
            log(f"=== {target.name} / {flt.name if flt else 'tất cả vật liệu'} ===")
            if await self.scrape_filter(target, flt):
                self.completed.add(key)
                self.out.save_progress(self.completed)

        if self.opt.visit_detail_pages:
            await self.enrich_from_detail_pages()
        self.out.save_products(self.products.values())
        log(f'Xong. Tổng {len(self.products)} sản phẩm → {self.out.dir.resolve()}')

    async def scrape_filter(self, target: ScrapeTarget, flt: MaterialFilter | None) -> bool:
        """Returns True when the filter was read to the end (so it can be skipped on resume)."""
        seen: set[str] = set()
        for page_no in range(1, self.opt.max_pages + 1):
            url = self.listing_url(target, flt, page_no)
            if not await self.goto(url, expect_listing=True):
                log(f'Bỏ qua trang: {url}', 'WARN')
                return False

            await self.auto_scroll()
            await self.click_load_more()
            listing = await self.page.evaluate(js.EXTRACT_LISTING)
            items = listing.get('items', [])
            total = listing.get('total')

            if not items:
                if page_no == 1 and total is None and not self.inspected_once:
                    log('Không tìm thấy sản phẩm bằng selector mặc định. Ghi debug_structure.json để kiểm tra.', 'WARN')
                    await self.dump_structure(url)
                    self.inspected_once = True
                log(f'  Trang {page_no}: 0 sản phẩm.')
                break

            new_on_page = 0
            for raw in items:
                if raw['sku'] not in seen:
                    seen.add(raw['sku'])
                    new_on_page += 1
                self.merge_listing_item(raw, target, flt)
            log(f"  Trang {page_no}: {len(items)} sản phẩm ({new_on_page} mới), tổng theo bộ lọc {total if total is not None else '?'}.")
            self.out.save_products(self.products.values())   # checkpoint after every page

            if new_on_page == 0:                               # Magento repeats the last page for p > last
                break
            if total is not None and len(seen) >= total:
                break
            if total is None and not listing.get('hasNext'):
                break
        return True

    def listing_url(self, target: ScrapeTarget, flt: MaterialFilter | None, page_no: int) -> str:
        query = []
        if flt:
            query.append(f'material={flt.id}')
        if page_no > 1:
            query.append(f'p={page_no}')
        url = self.config.base_url.rstrip('/') + '/' + target.category_path.strip('/')
        return url + ('?' + '&'.join(query) if query else '')

    async def goto(self, url: str, expect_listing: bool) -> bool:
        """Navigate politely; pause for the person on verification pages; retry load errors."""
        attempt = 0
        verification_rounds = 0
        while attempt < self.opt.max_retries:
            await self.polite_delay()
            try:
                log(f'→ {url}')
                await self.page.goto(url, wait_until='domcontentloaded', timeout=60_000)
                self.last_navigation = time.monotonic()

                if await self.is_verification_page():
                    verification_rounds += 1
                    if verification_rounds > self.opt.max_retries:
                        raise StopRun('Pan Home hiện trang xác minh lặp lại quá nhiều lần cho cùng một trang.\n'
                                      '  → Đợi một lúc rồi chạy lại, có thể tăng --min-delay 15 --max-delay 25.')
                    if not await self.wait_for_human(expect_listing):
                        # Every following page would wait the same 3 minutes: stop instead of skipping on.
                        raise StopRun(f'Không ai hoàn tất xác minh trong {self.opt.human_wait_timeout_s / 60:.0f} phút, nên tool dừng lại.\n'
                                      '  → Dữ liệu đến trang gần nhất đã được lưu. Khi bạn ở máy, chạy lại cùng lệnh để tiếp tục.')
                    if not self.same_page(self.page.url, url):
                        continue  # verification sent us elsewhere: load the target again

                if expect_listing:
                    await self.wait_for_listing()
                return True
            except PlaywrightError as ex:
                if self.page.is_closed() or 'has been closed' in str(ex):
                    raise StopRun('Tab hoặc cửa sổ Chrome mà tool đang dùng đã bị đóng.\n'
                                  '  → Mở lại Mo_Chrome_Debug.bat (nếu đã đóng), rồi chạy lại cùng lệnh để tiếp tục.') from None
                attempt += 1
                wait = 10 * attempt
                log(f'Lỗi tải trang (lần {attempt}/{self.opt.max_retries}): {shorten(str(ex), 160)}. Đợi {wait}s.', 'WARN')
                await asyncio.sleep(wait)
        return False

    async def polite_delay(self) -> None:
        if not self.last_navigation:
            return
        self.page_loads += 1
        if self.opt.pause_every and self.page_loads % self.opt.pause_every == 0:
            pause = random.uniform(self.opt.pause_min_s, self.opt.pause_max_s)
            log(f'Đã tải {self.page_loads} trang, nghỉ {pause:.0f}s cho đỡ dồn dập...')
            await asyncio.sleep(pause)
            return
        target = random.uniform(self.opt.min_delay_s, self.opt.max_delay_s)
        remaining = target - (time.monotonic() - self.last_navigation)
        if remaining > 0:
            await asyncio.sleep(remaining)

    @staticmethod
    def same_page(actual: str, expected: str) -> bool:
        a, e = urlparse(actual), urlparse(expected)
        return a.path.rstrip('/').lower() == e.path.rstrip('/').lower() and a.query.lower() == e.query.lower()

    async def is_verification_page(self) -> bool:
        try:
            if VERIFICATION_TITLE.search(await self.page.title()):
                return True
            return bool(await self.page.evaluate(js.IS_VERIFICATION_PAGE))
        except PlaywrightError:
            return False  # page is navigating; the caller checks again

    async def wait_for_human(self, expect_listing: bool) -> bool:
        """
        Beep, then wait until the person presses Enter or the verification page is gone
        (and, for listings, products are visible). Nothing is clicked or solved here.
        """
        self.waiting_for_human = True   # stop blocking any resource so the verification widget works
        try:
            beep()
            print()
            log('=' * 70, 'WARN')
            log('Pan Home đang hiện trang XÁC MINH.', 'WARN')
            log('→ Hãy hoàn tất xác minh trong cửa sổ trình duyệt, rồi nhấn Enter ở terminal này.', 'WARN')
            log(f'  (Hoặc tool tự chạy tiếp khi danh sách sản phẩm xuất hiện lại. Chờ tối đa {self.opt.human_wait_timeout_s / 60:.0f} phút.)', 'WARN')
            log('=' * 70, 'WARN')

            log('  Nếu bấm mãi không qua: mở một tab MỚI trong cửa sổ Chrome đó, vào panhomestores.com, xác minh ở đó,', 'WARN')
            log('  rồi quay lại đây nhấn Enter: tool sẽ tải lại trang của nó.', 'WARN')

            # Leave the verification page alone while it runs: no script is evaluated in it.
            # We only react when its main frame navigates (verification done) or when Enter is pressed.
            navigated = asyncio.Event()

            def on_navigated(frame) -> None:
                if frame == self.page.main_frame:
                    navigated.set()

            self.page.on('framenavigated', on_navigated)
            deadline = time.monotonic() + self.opt.human_wait_timeout_s
            next_reminder = time.monotonic() + 45
            try:
                while time.monotonic() < deadline:
                    enter = enter_pressed()
                    if enter:
                        log('Tải lại trang để kiểm tra...')
                        try:
                            await self.page.reload(wait_until='domcontentloaded', timeout=60_000)
                        except PlaywrightError:
                            pass
                        navigated.set()
                    if navigated.is_set():
                        navigated.clear()
                        await asyncio.sleep(3)   # let the new page settle before looking at it
                        if not await self.is_verification_page() and (not expect_listing or enter or await self.has_listing()):
                            log('Đã qua trang xác minh, chạy tiếp.')
                            self.last_navigation = time.monotonic()
                            return True
                        if enter:
                            log('Trang vẫn đang ở bước xác minh. Hoàn tất xong rồi nhấn Enter lại.', 'WARN')
                    if time.monotonic() > next_reminder:
                        beep()
                        next_reminder = time.monotonic() + 45
                    await asyncio.sleep(1)
            finally:
                self.page.remove_listener('framenavigated', on_navigated)
            log('Hết thời gian chờ xác minh.', 'WARN')
            return False
        finally:
            self.waiting_for_human = False

    async def has_listing(self) -> bool:
        try:
            return bool(await self.page.evaluate(js.HAS_LISTING))
        except PlaywrightError:
            return False

    async def wait_for_listing(self) -> None:
        try:
            await self.page.wait_for_function(js.LISTING_READY, timeout=20_000, polling=500)
        except PlaywrightError:
            pass  # empty filter page or slow render: extraction reports 0 items

    async def auto_scroll(self) -> None:
        try:
            await self.page.evaluate(js.AUTO_SCROLL, 700)
        except PlaywrightError as ex:
            if self.opt.verbose:
                log(f'Cuộn trang lỗi: {ex}', 'DEBUG')

    async def click_load_more(self) -> None:
        """Click a "Load more" button if the listing uses one instead of ?p= pages."""
        for _ in range(self.opt.max_pages):
            button = self.page.locator('button, a').filter(has_text=LOAD_MORE).first
            try:
                if await button.count() == 0 or not await button.is_visible():
                    return
                log('  Bấm "Load more"...')
                await button.click(timeout=10_000)
                await asyncio.sleep(random.uniform(2.5, 4.5))
                await self.auto_scroll()
            except PlaywrightError:
                return

    # ------------------------------------------------------------ Step 4: extraction

    def merge_listing_item(self, raw: dict, target: ScrapeTarget, flt: MaterialFilter | None) -> None:
        sku = (raw.get('sku') or '').upper()
        if not sku:
            return
        product = self.products.get(sku)
        if product is None:
            product = ProductItem(sku=sku, category=target.category_path,
                                  app_category=self.resolve_app_category(target, raw.get('name', '')))
            self.products[sku] = product

        product.name = raw.get('name') or product.name
        product.product_url = raw.get('url') or product.product_url
        product.regular_price = raw.get('regular') if raw.get('regular') is not None else product.regular_price
        product.final_price = raw.get('final') if raw.get('final') is not None else product.final_price
        image = raw.get('image')
        if image and not image.startswith('data:'):
            product.image_url = image
        product.stock_status = raw.get('stock') or product.stock_status
        product.scraped_at_utc = now_utc()
        _add_once(product.sources, 'listing')

        if flt:
            _add_once(product.filter_materials, flt.name)
            if flt.app_material:
                _add_once(product.app_materials, flt.app_material)

        # Fill gaps from JSON the page loaded (GraphQL / search responses), when the SKU matches.
        net = self.network_products.get(sku)
        if net:
            product.regular_price = product.regular_price or net.regular_price
            product.final_price = product.final_price or net.final_price
            product.image_url = product.image_url or net.image_url
            product.stock_status = product.stock_status or net.stock_status
            _add_once(product.sources, 'network')

    @staticmethod
    def resolve_app_category(target: ScrapeTarget, name: str) -> str:
        for pattern, category in target.title_category_rules.items():
            if re.search(pattern, name, re.I):
                return category
        return target.app_category

    async def enrich_from_detail_pages(self) -> None:
        """Optional: open detail pages for "Primary Material" and Length/Width/Height."""
        # Only products the catalog export would otherwise drop: no usable material or no size in the name.
        needing = [p for p in self.products.values()
                   if 'detail' not in p.sources and (not materials_for(p) or not dimensions_from_name(p.name))]
        todo = needing[: self.opt.max_detail_pages]
        log(f'Đọc trang chi tiết: {len(todo)}/{len(needing)} sản phẩm thiếu vật liệu hoặc kích thước '
            f'(giới hạn {self.opt.max_detail_pages}).')
        for product in todo:
            if not await self.goto(product.product_url, expect_listing=False):
                continue
            try:
                data = await self.page.evaluate(js.EXTRACT_DETAIL)
            except PlaywrightError as ex:
                log(f'Không đọc được trang chi tiết {product.sku}: {shorten(str(ex), 120)}', 'WARN')
                continue

            product.specifications.update({k: str(v) for k, v in (data.get('specs') or {}).items()})
            ld = data.get('ld') or {}
            image = ld.get('image')
            if isinstance(image, list) and image:
                image = image[0]
            if isinstance(image, str):
                product.image_url = image
            offers = ld.get('offers')
            offer = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offer, dict):
                try:
                    product.final_price = float(offer.get('price'))
                except (TypeError, ValueError):
                    pass
                if isinstance(offer.get('availability'), str):
                    product.stock_status = offer['availability'].rsplit('/', 1)[-1]
            product.stock_status = product.stock_status or data.get('stock')

            material = product.specifications.get('PrimaryMaterial')
            if material:
                _add_once(product.filter_materials, material)
                app_material = self.config.material_aliases.get(material.strip().lower())
                if app_material:
                    _add_once(product.app_materials, app_material)
            _add_once(product.sources, 'detail')
            self.out.save_products(self.products.values())

    # ------------------------------------------------------------ Discovery mode

    async def inspect_page_structure(self, url: str) -> None:
        """Open a page and dump its structure to debug_structure.json for tuning selectors."""
        if not await self.goto(url, expect_listing=False):
            log('Không mở được trang.', 'WARN')
            return
        await self.auto_scroll()
        await asyncio.sleep(3)
        await self.dump_structure(url)

    async def dump_structure(self, url: str) -> None:
        dom = await self.page.evaluate(js.INSPECT_STRUCTURE)
        path = self.out.save_debug_structure({
            'requested_url': url,
            'final_url': self.page.url,
            'title': await self.page.title(),
            'captured_at_utc': now_utc(),
            'dom': dom,
            'xhr_and_fetch_requests': list(dict.fromkeys(self.xhr_log))[-200:],
        })
        log(f'Đã ghi {path}')


def _add_once(values: list[str], value: str) -> None:
    if value.lower() not in (v.lower() for v in values):
        values.append(value)
