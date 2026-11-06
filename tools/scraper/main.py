"""
Pan Home scraper (human-in-the-loop).

  python main.py scrape [--only "Table Lamp"] [--max-pages 5] [--details]
  python main.py inspect https://www.panhomestores.com/uae_en/accessories/lighting/lamps/table-lamps
  python main.py export-benchmark [--apply]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BENCHMARK = HERE.parents[1] / 'src' / 'benchmark.json'   # repo: tools/scraper -> src/benchmark.json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Đọc sản phẩm Pan Home (có người xác minh) và xuất catalog cho app so giá.')
    sub = parser.add_subparsers(dest='command', required=True)

    def browser_args(p: argparse.ArgumentParser) -> None:
        p.add_argument('--config', default=str(HERE / 'scrape_config.json'))
        p.add_argument('--output-dir', default=str(HERE / 'output'))
        p.add_argument('--user-data-dir', default=str(HERE / 'user_data_dir'),
                       help='Profile trình duyệt, giữ cookie sau khi bạn xác minh.')
        p.add_argument('--cdp-url', default='http://localhost:9222',
                       help='Kết nối Chrome đang mở (mở bằng Mo_Chrome_Debug.bat). Mặc định http://localhost:9222.')
        p.add_argument('--launch', action='store_true',
                       help='Không kết nối Chrome đang mở; để Playwright tự mở trình duyệt mới.')
        p.add_argument('--headless', action='store_true', help='Chỉ dùng với --launch. Ẩn trình duyệt.')
        p.add_argument('--channel', default='chrome',
                       help='Trình duyệt: chrome (mặc định, dùng Chrome đã cài), msedge, hoặc chromium (bản của Playwright).')
        p.add_argument('--min-delay', type=float, default=10.0, help='Giây tối thiểu giữa 2 lần tải trang.')
        p.add_argument('--max-delay', type=float, default=18.0, help='Giây tối đa giữa 2 lần tải trang.')
        p.add_argument('--pause-every', type=int, default=12, help='Cứ N trang nghỉ dài một lần (0 = không nghỉ).')
        p.add_argument('--pause-seconds', type=float, nargs=2, default=[60.0, 120.0], metavar=('MIN', 'MAX'),
                       help='Thời gian nghỉ dài, mặc định 60 120 giây.')
        p.add_argument('--wait-timeout', type=float, default=180.0, help='Giây chờ bạn xác minh.')
        p.add_argument('--block-images', action='store_true')
        p.add_argument('--verbose', action='store_true')

    scrape = sub.add_parser('scrape', help='Đọc các danh mục trong scrape_config.json.')
    browser_args(scrape)
    scrape.add_argument('--only', action='append', default=[], help='Chỉ chạy target có tên chứa chuỗi này (lặp được).')
    scrape.add_argument('--max-pages', type=int, default=20)
    scrape.add_argument('--details', action='store_true', help='Mở thêm trang chi tiết để lấy vật liệu/kích thước.')
    scrape.add_argument('--max-details', type=int, default=50)
    scrape.add_argument('--fresh', action='store_true', help='Bỏ checkpoint, chạy lại từ đầu.')
    scrape.add_argument('--no-export', action='store_true', help='Không tự xuất benchmark.scraped.json khi xong.')

    inspect = sub.add_parser('inspect', help='Dump cấu trúc trang ra debug_structure.json.')
    browser_args(inspect)
    inspect.add_argument('url')

    def collect_args(p: argparse.ArgumentParser) -> None:
        p.add_argument('--config', default=str(HERE / 'scrape_config.json'))
        p.add_argument('--output-dir', default=str(HERE / 'output'))
        p.add_argument('--benchmark', default=str(DEFAULT_BENCHMARK), help='benchmark.json hiện tại của app.')
        p.add_argument('--port', type=int, default=8765)

    remaining = sub.add_parser('remaining', help='In các lượt lọc chưa xong kèm URL.')
    collect_args(remaining)

    listen = sub.add_parser('listen', help='Nhận dữ liệu từ bookmarklet trên Chrome thường (http://localhost:8765).')
    collect_args(listen)

    export = sub.add_parser('export-benchmark', help='Chuyển products_output.json sang định dạng benchmark.json.')
    export.add_argument('--input', default=str(HERE / 'output' / 'products_output.json'))
    export.add_argument('--benchmark', default=str(DEFAULT_BENCHMARK), help='benchmark.json hiện tại của app.')
    export.add_argument('--output', default=str(HERE / 'output' / 'benchmark.scraped.json'))
    export.add_argument('--apply', action='store_true', help='Ghi đè benchmark.json của app (có backup).')
    return parser


def run_export(args: argparse.Namespace) -> None:
    from benchmark_export import apply_benchmark, export_benchmark
    result = export_benchmark(args.input, args.benchmark, args.output)
    print(f"Đã xuất {result['exported']} sản phẩm → {result['output']}")
    for category, count in sorted(result['per_category'].items()):
        print(f'  {category}: {count}')
    if result['skipped']:
        print(f"Bỏ qua {len(result['skipped'])} sản phẩm:")
        for line in result['skipped']:
            print(f'  - {line}')
    if getattr(args, 'apply', False):
        backup = apply_benchmark(args.output, args.benchmark)
        print(f'Đã ghi đè {args.benchmark}. Bản cũ: {backup}')


def run_collector(args: argparse.Namespace) -> None:
    from collector import Collector, print_remaining
    from models import ScraperOptions, load_config
    from scraper import StopRun

    options = ScraperOptions(output_dir=args.output_dir)
    collector = Collector(options, load_config(args.config), Path(args.benchmark), args.port)
    if args.command == 'remaining':
        # Read-only: no lock, nothing is written.
        collector.scraper.products = {p.sku: p for p in collector.scraper.out.load_products()}
        collector.scraper.completed = collector.scraper.out.load_progress()
        print_remaining(collector)
        return
    try:
        collector.scraper.load_checkpoint()   # takes output/run.lock: no scrape can run at the same time
    except StopRun as ex:
        print(f'\nĐÃ DỪNG: {ex}')
        sys.exit(3)
    try:
        print_remaining(collector)
        print()
        collector.serve()
    except KeyboardInterrupt:
        print('\nĐã dừng listen. Dữ liệu đã lưu sau mỗi trang.')
    except OSError as ex:
        print(f'\nKhông mở được cổng {args.port}: {ex}. Thử --port 8766.')
        sys.exit(4)
    finally:
        collector.scraper.release_lock()


async def run_browser(args: argparse.Namespace) -> None:
    from models import ScraperOptions, load_config
    from scraper import PanHomeScraper

    options = ScraperOptions(
        headless=args.headless, channel=None if args.channel == 'chromium' else args.channel,
        user_data_dir=args.user_data_dir, cdp_url=None if args.launch else args.cdp_url,
        output_dir=args.output_dir, min_delay_s=args.min_delay, max_delay_s=max(args.min_delay, args.max_delay),
        human_wait_timeout_s=args.wait_timeout, block_images=args.block_images, verbose=args.verbose,
        pause_every=max(0, args.pause_every), pause_min_s=min(args.pause_seconds), pause_max_s=max(args.pause_seconds),
    )
    if args.command == 'scrape':
        options.max_pages = args.max_pages
        options.visit_detail_pages = args.details
        options.max_detail_pages = args.max_details
        options.fresh = args.fresh
        options.only_targets = args.only

    scraper = PanHomeScraper(options, load_config(args.config))
    try:
        await scraper.start()
        if args.command == 'inspect':
            await scraper.inspect_page_structure(args.url)
        else:
            await scraper.run()
    finally:
        await scraper.close()


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    args = build_parser().parse_args()
    if args.command == 'export-benchmark':
        run_export(args)
        return
    if args.command in ('remaining', 'listen'):
        run_collector(args)
        return
    from scraper import ChromeNotOpenError, StopRun
    try:
        asyncio.run(run_browser(args))
    except KeyboardInterrupt:
        print('\nĐã dừng. Dữ liệu đến trang gần nhất đã được lưu; chạy lại cùng lệnh để tiếp tục.')
        return
    except ChromeNotOpenError as ex:
        print(f'\n{ex}')
        sys.exit(2)
    except StopRun as ex:
        print('\a', end='')
        print(f'\nĐÃ DỪNG: {ex}')
        sys.exit(3)
    if args.command == 'scrape' and not args.no_export:
        products = Path(args.output_dir) / 'products_output.json'
        if products.exists():
            run_export(argparse.Namespace(input=str(products), benchmark=str(DEFAULT_BENCHMARK),
                                          output=str(Path(args.output_dir) / 'benchmark.scraped.json'), apply=False))


if __name__ == '__main__':
    main()
