"""
Collect mode: the person browses Pan Home in their normal Chrome and clicks a bookmarklet on each
listing page. The bookmarklet reads the products already shown on the page and POSTs them to this
local server, which merges them into output/products_output.json and re-exports the catalog.

No browser is automated here. The server only listens on 127.0.0.1.
"""
from __future__ import annotations

import html
import json
import shutil
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import page_scripts as js
from benchmark_export import export_benchmark
from models import MaterialFilter, ScrapeConfig, ScraperOptions, ScrapeTarget
from scraper import PanHomeScraper, log

SITE_ORIGINS = {'https://www.panhomestores.com', 'https://panhomestores.com'}
MAX_BODY = 2_000_000


@dataclass
class PassState:
    """Pages seen for one filter pass during this listen session."""
    seen: set[str] = field(default_factory=set)
    pages: set[int] = field(default_factory=set)
    total: int | None = None
    last_page_short: bool = False


class Collector:
    def __init__(self, options: ScraperOptions, config: ScrapeConfig, benchmark_path: Path, port: int):
        self.scraper = PanHomeScraper(options, config)   # used for its checkpoint, merge and URL logic only
        self.config = config
        self.benchmark_path = benchmark_path
        self.port = port
        self.state: dict[str, PassState] = {}
        self.lock = threading.Lock()
        self.passes = self.scraper.filter_passes()

    # ------------------------------------------------------------ remaining work

    def remaining(self) -> list[tuple[str, ScrapeTarget, MaterialFilter | None, str]]:
        """Filter passes not finished yet, with the next listing URL to open."""
        result = []
        for key, target, flt in self.passes:
            if key in self.scraper.completed:
                continue
            st = self.state.get(key)
            next_page = (max(st.pages) + 1) if st and st.pages else 1
            result.append((key, target, flt, self.scraper.listing_url(target, flt, next_page)))
        return result

    def match_url(self, url: str) -> tuple[str, ScrapeTarget, MaterialFilter | None, int] | None:
        """Which configured filter pass a Pan Home listing URL belongs to."""
        parsed = urlparse(url)
        base_path = urlparse(self.config.base_url).path.rstrip('/')
        path = parsed.path.rstrip('/')
        query = parse_qs(parsed.query)
        material = query.get('material', [None])[0]
        try:
            page = int(query.get('p', ['1'])[0])
        except ValueError:
            page = 1
        for key, target, flt in self.passes:
            if path != f"{base_path}/{target.category_path.strip('/')}":
                continue
            if (flt is None and material is None) or (flt is not None and material == str(flt.id)):
                return key, target, flt, page
        return None

    # ------------------------------------------------------------ handling a page

    def collect(self, payload: dict) -> dict:
        url = str(payload.get('url') or '')
        if urlparse(url).hostname not in ('www.panhomestores.com', 'panhomestores.com'):
            return {'ok': False, 'message': 'Trang này không phải panhomestores.com.'}
        items = [i for i in payload.get('items') or [] if isinstance(i, dict) and i.get('sku') and i.get('name')]
        matched = self.match_url(url)
        if matched is None:
            return {'ok': False, 'message': 'Trang này không thuộc danh mục/bộ lọc nào trong scrape_config.json.\n'
                                            'Mở đúng URL trong danh sách còn thiếu (http://localhost:%d/).' % self.port}
        key, target, flt, page = matched
        label = f"{target.name} / {flt.name if flt else 'tất cả vật liệu'}"
        if not items:
            return {'ok': False, 'message': f'{label}: không thấy sản phẩm trên trang. Đợi trang tải xong rồi bấm lại.'}

        with self.lock:
            before = len(self.scraper.products)
            for raw in items:
                self.scraper.merge_listing_item(raw, target, flt)
            st = self.state.setdefault(key, PassState())
            st.seen.update(str(i['sku']).upper() for i in items)
            st.pages.add(page)
            total = payload.get('total')
            st.total = int(total) if isinstance(total, (int, float)) else st.total
            st.last_page_short = len(items) < 48 and not payload.get('hasNext')

            done = (st.total is not None and len(st.seen) >= st.total) or \
                   (st.total is None and st.last_page_short)
            if done:
                self.scraper.completed.add(key)
            self.save()
            added = len(self.scraper.products) - before
            remaining = self.remaining()

        lines = [f'{label}, trang {page}: {len(items)} sản phẩm ({added} mới). Tổng {len(self.scraper.products)} sản phẩm.']
        if done:
            lines.append(f'✓ Xong bộ lọc này. Còn {len(remaining)} lượt.')
        else:
            nxt = self.scraper.listing_url(target, flt, max(st.pages) + 1)
            lines.append(f'Bộ lọc này còn trang tiếp ({len(st.seen)}/{st.total or "?"}). Mở: {nxt}')
        if remaining:
            lines.append(f'Tiếp theo: {remaining[0][3]}')
        else:
            lines.append('Đã đủ tất cả lượt lọc!')
        message = '\n'.join(lines)
        log(message.replace('\n', ' | '))
        next_url = remaining[0][3] if remaining else None
        return {'ok': True, 'message': message, 'done': done, 'remaining': len(remaining), 'next_url': next_url}

    def save(self) -> None:
        out = self.scraper.out
        out.save_products(self.scraper.products.values())
        out.save_progress(self.scraper.completed)
        # Rolling copy, in case another program overwrites products_output.json.
        shutil.copy2(out.products_json, out.dir / 'products_output.backup-latest.json')
        try:
            export_benchmark(out.products_json, self.benchmark_path, out.dir / 'benchmark.scraped.json')
        except SystemExit:
            pass

    # ------------------------------------------------------------ bookmarklet and pages

    def bookmarklet_source(self) -> str:
        endpoint = f'http://localhost:{self.port}'
        return f"""
(async () => {{
  const EP = {json.dumps(endpoint)};
  const toast = (msg, color) => {{
    let d = document.getElementById('__ph_collect');
    if (!d) {{
      d = document.createElement('div'); d.id = '__ph_collect';
      d.style.cssText = 'position:fixed;z-index:2147483647;top:16px;right:16px;max-width:460px;padding:12px 16px;border-radius:8px;font:14px/1.45 system-ui,sans-serif;color:#fff;box-shadow:0 6px 20px rgba(0,0,0,.35);white-space:pre-line;cursor:pointer';
      d.onclick = () => d.remove();
      document.body.appendChild(d);
    }}
    d.style.background = color || '#1f4e79'; d.textContent = msg;
  }};
  try {{
    toast('Đang đọc sản phẩm trên trang...');
    await ({js.AUTO_SCROLL.strip()})(700);
    const data = ({js.EXTRACT_LISTING.strip()})();
    data.url = location.href;
    if (!data.items.length) {{ toast('Không thấy sản phẩm trên trang này. Đợi trang tải xong rồi bấm lại.', '#a33'); return; }}
    let res;
    try {{
      const r = await fetch(EP + '/collect', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(data) }});
      res = await r.json();
    }} catch (e) {{
      const w = window.open(EP + '/relay#' + encodeURIComponent(JSON.stringify(data)), '_blank');
      toast(w ? 'Đã gửi qua tab localhost (trình duyệt chặn gửi trực tiếp).' : 'Không gửi được. Kiểm tra "python main.py listen" còn chạy, và cho phép popup.', w ? '#1f4e79' : '#a33');
      return;
    }}
    toast(res.message, res.ok ? '#2e7d32' : '#a33');
  }} catch (e) {{ toast('Lỗi: ' + e.message, '#a33'); }}
}})();
""".strip()

    def bookmarklet_href(self) -> str:
        return 'javascript:' + quote(self.bookmarklet_source(), safe='')

    def status_page(self) -> str:
        remaining = self.remaining()
        rows = ''.join(
            f'<li><a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(t.name)} / '
            f'{html.escape(f.name if f else "tất cả vật liệu")}</a> <code>{html.escape(url)}</code></li>'
            for _, t, f, url in remaining)
        return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Pan Home collector</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#1d2433}}
code{{font-size:12px;color:#555;word-break:break-all}} li{{margin:6px 0}} .bm{{display:inline-block;padding:10px 16px;background:#1f4e79;color:#fff;border-radius:8px;text-decoration:none;font-weight:600}}
textarea{{width:100%;height:120px;font:12px monospace}} .muted{{color:#666}}</style></head><body>
<h1>Pan Home collector</h1>
<p><b>{len(self.scraper.products)}</b> sản phẩm đã có. Còn <b>{len(remaining)}</b> lượt lọc. <a href="/">Tải lại trang này</a> để cập nhật.</p>
<h2>1. Kéo nút này lên thanh bookmark của Chrome</h2>
<p><a class="bm" href="{html.escape(self.bookmarklet_href())}">📥 Lấy SP Pan Home</a></p>
<p class="muted">Không kéo được? Mở DevTools (F12) → Console trên trang Pan Home, dán đoạn dưới rồi Enter:</p>
<textarea readonly onclick="this.select()">{html.escape(self.bookmarklet_source())}</textarea>
<h2>2. Mở từng trang còn thiếu, đợi tải xong, bấm bookmark</h2>
<p class="muted">Bấm vào link sẽ mở trang Pan Home ở tab mới. Mỗi trang bấm bookmark một lần; ô thông báo xanh hiện kết quả và URL tiếp theo.
Bộ lọc nhiều trang (ví dụ Storage tất cả vật liệu) sẽ hiện link trang 2, 3... ở đây sau mỗi lần gửi.</p>
<ol>{rows or '<li>Đã đủ tất cả lượt lọc!</li>'}</ol>
</body></html>"""

    @staticmethod
    def relay_page() -> str:
        return """<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Gửi dữ liệu</title></head>
<body style="font:15px system-ui;padding:24px"><p id="m">Đang gửi...</p><script>
(async () => {
  const m = document.getElementById('m');
  try {
    const data = JSON.parse(decodeURIComponent(location.hash.slice(1)));
    const r = await fetch('/collect', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const res = await r.json();
    m.style.whiteSpace = 'pre-line'; m.style.color = res.ok ? '#2e7d32' : '#a33'; m.textContent = res.message;
    if (res.ok) setTimeout(() => window.close(), 4000);
  } catch (e) { m.textContent = 'Lỗi: ' + e.message; }
})();
</script></body></html>"""

    # ------------------------------------------------------------ server

    def serve(self) -> None:
        collector = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 15   # Chrome preconnects idle sockets; never let one hold a worker forever

            def _cors(self) -> None:
                origin = self.headers.get('Origin', '')
                if origin in SITE_ORIGINS:
                    self.send_header('Access-Control-Allow-Origin', origin)
                    self.send_header('Vary', 'Origin')
                    self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    self.send_header('Access-Control-Allow-Private-Network', 'true')

            def _send(self, code: int, body: str, content_type: str) -> None:
                data = body.encode('utf-8')
                self.send_response(code)
                self._cors()
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(data)

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_GET(self) -> None:
                path = urlparse(self.path).path
                if path == '/':
                    self._send(200, collector.status_page(), 'text/html; charset=utf-8')
                elif path == '/relay':
                    self._send(200, collector.relay_page(), 'text/html; charset=utf-8')
                elif path == '/remaining':
                    data = [{'key': k, 'url': u} for k, _, _, u in collector.remaining()]
                    self._send(200, json.dumps(data, ensure_ascii=False), 'application/json; charset=utf-8')
                else:
                    self._send(404, 'Not found', 'text/plain; charset=utf-8')

            def do_POST(self) -> None:
                if urlparse(self.path).path != '/collect':
                    self._send(404, 'Not found', 'text/plain; charset=utf-8')
                    return
                origin = self.headers.get('Origin', '')
                own = {f'http://localhost:{collector.port}', f'http://127.0.0.1:{collector.port}'}
                if origin not in SITE_ORIGINS | own:
                    self._send(403, json.dumps({'ok': False, 'message': 'Nguồn gửi không được phép.'}), 'application/json')
                    return
                length = int(self.headers.get('Content-Length') or 0)
                if length <= 0 or length > MAX_BODY:
                    self._send(400, json.dumps({'ok': False, 'message': 'Dữ liệu rỗng hoặc quá lớn.'}), 'application/json')
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode('utf-8'))
                    result = collector.collect(payload)
                except (ValueError, TypeError) as ex:
                    result = {'ok': False, 'message': f'Dữ liệu không hợp lệ: {ex}'}
                self._send(200, json.dumps(result, ensure_ascii=False), 'application/json; charset=utf-8')

            def log_message(self, *args) -> None:
                pass

        # Threaded: an idle preconnected socket from Chrome must not block the real requests.
        # collect() serialises writes with self.lock.
        server = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
        server.daemon_threads = True
        log(f'Đang nghe ở http://localhost:{self.port}/  (mở trang này trong Chrome để lấy bookmarklet và danh sách URL)')
        log('Nhấn Ctrl+C để dừng.')
        try:
            server.serve_forever()
        finally:
            server.server_close()


def print_remaining(collector: Collector) -> None:
    remaining = collector.remaining()
    print(f'Còn {len(remaining)} lượt lọc chưa xong ({len(collector.scraper.products)} sản phẩm đã có):')
    for i, (key, target, flt, url) in enumerate(remaining, 1):
        print(f"{i:2}. {target.name} / {flt.name if flt else 'tất cả vật liệu'}  [{key}]")
        print(f'    {url}')
