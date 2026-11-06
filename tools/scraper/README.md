# Pan Home Scraper (có người xác minh)

Đọc sản phẩm trên panhomestores.com theo danh mục và bộ lọc vật liệu (`?material=...`), lưu checkpoint JSON/CSV, rồi xuất sang định dạng `benchmark.json` của app so giá.

Tool **không** giấu dấu hiệu trình duyệt tự động và **không** tự vượt qua trang xác minh của Pan Home. Khi trang xác minh hiện ra, tool kêu bíp, in thông báo và chờ bạn tự bấm qua trong cửa sổ trình duyệt.

## Cài đặt (một lần)

```bash
cd <thư mục repo home_tool>\tools\scraper
pip install -r requirements.txt
```

Tool mặc định dùng **Chrome đã cài trên máy** (`--channel chrome`), không cần tải thêm trình duyệt. Muốn dùng Chromium của Playwright thì cài thêm `python -m playwright install chromium` và chạy với `--channel chromium`.

## Chạy

**Bước 1.** Mở Chrome có cổng debug bằng cách nhấp đúp `Mo_Chrome_Debug.bat`.

- Nó mở một cửa sổ Chrome **riêng** (profile `chrome_debug_profile/`) với cổng `9222` và vào thẳng Pan Home. Chrome 136+ không cho bật cổng debug trên profile mặc định, nên phải dùng profile riêng.
- Bấm qua bước xác minh của Pan Home trong cửa sổ này nếu có.
- Khi cửa sổ này mở, chương trình nào trên máy cũng điều khiển được nó qua cổng 9222. Không đăng nhập tài khoản quan trọng trong cửa sổ này, và đóng nó khi xong việc.

**Bước 2.** Chạy tool:

```bash
python main.py scrape
```

- Tool kết nối vào Chrome đó, mở **một tab riêng** để làm việc (không đụng các tab bạn đang mở), đi lần lượt từng danh mục/vật liệu trong `scrape_config.json`, mỗi trang cách nhau 8–15 giây. Khi xong, tool chỉ đóng tab của nó; Chrome vẫn mở.
- Khi gặp trang xác minh: bấm qua trong tab đó, rồi nhấn **Enter** ở terminal (hoặc chờ, tool tự chạy tiếp khi danh sách sản phẩm hiện lại; tối đa 3 phút).
- Dùng `--cdp-url http://localhost:XXXX` nếu bạn mở Chrome ở cổng khác. Dùng `--launch` để quay lại cách cũ (Playwright tự mở trình duyệt, profile `user_data_dir/`).
- Ngắt giữa chừng (Ctrl+C) không mất dữ liệu: chạy lại cùng lệnh sẽ tiếp tục từ trang lọc chưa xong. Dùng `--fresh` để chạy lại từ đầu.

Tùy chọn hay dùng:

| Lệnh | Tác dụng |
|---|---|
| `--only "Planter"` | Chỉ chạy danh mục có tên chứa chuỗi này (lặp được) |
| `--max-pages 3` | Giới hạn số trang mỗi bộ lọc (để thử) |
| `--details --max-details 30` | Mở thêm trang chi tiết để lấy Primary Material và Length/Width/Height |
| `--channel msedge` | Dùng Edge thay cho Chrome (`chromium` = bản của Playwright) |
| `--min-delay 10 --max-delay 20` | Đi chậm hơn nếu bị xác minh nhiều |
| `--block-images` | Chặn ảnh trên panhomestores.com (link ảnh vẫn được đọc) |

## Cách 2: tự duyệt bằng Chrome thường + bookmarklet (khi Pan Home chặn tool)

Không có trình duyệt nào bị điều khiển: bạn tự mở trang, bookmarklet đọc sản phẩm đang hiện và gửi về máy bạn.

```bash
python main.py remaining
```
In các lượt lọc còn thiếu kèm URL.

```bash
python main.py listen
```
1. Mở `http://localhost:8765/` trong Chrome thường. Kéo nút **📥 Lấy SP Pan Home** lên thanh bookmark (hoặc copy đoạn code để dán vào Console).
2. Bấm từng link trong danh sách "còn thiếu" trên trang đó để mở trang Pan Home, đợi tải xong, bấm bookmark.
3. Ô thông báo xanh hiện số sản phẩm, đã xong bộ lọc chưa, và URL tiếp theo (kể cả trang 2, 3… của bộ lọc nhiều trang).
4. Lần đầu Chrome có thể hỏi cho phép panhomestores.com truy cập thiết bị trong mạng cục bộ: bấm **Allow**. Nếu từ chối, bookmarklet tự gửi qua một tab `localhost` (cần cho phép popup).

Mỗi lần gửi: sản phẩm được ghép vào `products_output.json` (theo SKU), lượt lọc đủ trang được đánh dấu xong trong `progress.json`, `benchmark.scraped.json` được xuất lại, và có bản sao `products_output.backup-latest.json`. Server chỉ nghe ở 127.0.0.1 và chỉ nhận dữ liệu từ trang panhomestores.com. Không chạy `listen` cùng lúc với `scrape` (tool tự chặn).

## Kết quả (thư mục `output/`)

| File | Nội dung |
|---|---|
| `products_output.json` / `.csv` | Toàn bộ sản phẩm: SKU, tên, link, giá gốc, giá khuyến mãi, ảnh, danh mục, vật liệu, tồn kho. Ghi lại sau mỗi trang |
| `progress.json` | Các trang lọc đã xong, để chạy tiếp |
| `benchmark.scraped.json` | Catalog cho app so giá, tự xuất khi scrape xong |
| `captured_json.jsonl` | Các gói JSON (GraphQL/search) mà trang tự tải, nếu có |
| `debug_structure.json` | Cấu trúc trang khi selector không tìm thấy sản phẩm |

## Đưa catalog vào app so giá

```bash
python main.py export-benchmark
```

Xem lại `output/benchmark.scraped.json`, rồi ghi đè catalog của app (tự backup bản cũ cạnh file):

```bash
python main.py export-benchmark --apply
```

Mỗi sản phẩm trong catalog có `price_aed` (giá gốc), `sale_price_aed` (giá đang bán), `price_checked_at` (ngày lấy giá), `dimensions`, `materials`. App so với **giá gốc**.

Quy tắc chuyển đổi:
- Kích thước lấy từ trang chi tiết nếu có (`--details`), không thì từ tên sản phẩm (`Dia 35x53cm` → `[35, 35, 53]`, `24x24x40.5cm` → `[24, 24, 40.5]`). Không đọc được kích thước thì bỏ qua và liệt kê.
- Vật liệu = vật liệu của bộ lọc + vật liệu ghi trong tên. Ví dụ đèn gốm xuất hiện trong bộ lọc Bamboo sẽ có `["bamboo", "ceramic"]`, nên không bị ghép với đèn chỉ có tre.
- Raffia, Banana Bark, Palm Leaf, Corn Leaf được gom vào `natural_fiber`. Poly Wicker là `poly_rattan`.

## Khi selector không còn đúng

```bash
python main.py inspect "https://www.panhomestores.com/uae_en/accessories/lighting/lamps/table-lamps"
```

Mở `output/debug_structure.json` để xem class CSS, `ld+json`, các XHR/fetch và một thẻ sản phẩm mẫu, rồi sửa `page_scripts.py`.

## Thêm danh mục hoặc vật liệu

Sửa `scrape_config.json`. Mã bộ lọc vật liệu lấy từ link bộ lọc "Primary Material" trên trang danh mục (`?material=3992` là Rattan). Mã đang dùng được ghi nhận ngày 2026-11-06.

Mỗi danh mục:
- `materials`: các bộ lọc vật liệu được đọc trước. Sản phẩm thấy ở bộ lọc nào thì được gắn vật liệu đó. `app_material: null` (ví dụ Metal) nghĩa là chỉ ghi lại để tham khảo, app so giá không dùng vật liệu này để ghép.
- `include_unfiltered: true`: sau các bộ lọc, đọc thêm toàn bộ danh mục không lọc (đủ mọi trang), để lấy cả sản phẩm không thuộc bộ lọc nào. Sản phẩm đã gặp ở bộ lọc vẫn giữ vật liệu.
- Sản phẩm chỉ thấy ở lượt không lọc, tên không ghi vật liệu, sẽ bị bỏ khi xuất catalog. Chạy `--details` để đọc "Primary Material" ở trang chi tiết cho riêng các sản phẩm này.

Với cấu hình hiện tại, chạy full khoảng 70 lượt lọc, khoảng 95 lần tải trang, mất 20 phút, lấy khoảng 1.000 sản phẩm.

## Kiểm tra

```bash
python -m unittest test_benchmark_export -v
```
