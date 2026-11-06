# Home Tool (All-in-One)

Hệ thống web merchandising và chào hàng quốc tế tích hợp 2 công cụ cốt lõi:
1. **📊 Pan Home Price Comparator**: Đọc file báo giá Excel (FOB Hải Phòng), lọc sạch dữ liệu kích thước, đối chuẩn tự động với giá bán lẻ niêm yết tại Pan Home UAE (`panhomestores.com`), tính tỷ lệ markup và xuất file Excel chuẩn format kèm hyperlink trực tiếp.
2. **🎨 PPT 1 ➔ PPT 2 Remaster Engine**: Tự động bóc tách ảnh từ các file PowerPoint thô của nhà máy, gom nhóm theo tông màu sắc & chất liệu, dàn trang theo chuẩn A5 Landscape với **thuộc tính `Height` đồng bộ 100%** (các ảnh trên hàng bằng nhau tuyệt đối, chân đế và đỉnh thẳng tắp).

---

## Công Nghệ
- **Frontend**: React 18 + Vite + TailwindCSS + Lucide Icons
- **Engine xử lý Excel**: `xlsx` (SheetJS)
- **Engine xử lý PPTX**: `jszip` + `pptxgenjs` (100% Client-Side in Browser)
- **Hosting**: Cloudflare Pages (Free & Unlimited Bandwidth)

---

## Hướng Dẫn Chạy Cục Bộ (Local)
```bash
npm install
npm run dev
```
Mở trình duyệt tại `http://localhost:3000`.

## Rule so sánh giá (v3)

Frontend đọc và xuất Excel ngay trong trình duyệt, không gọi localhost của người xem khi chạy trên Cloudflare. Backend Python vẫn cung cấp API riêng và dùng chung catalog `src/benchmark.json`.

- Đọc sheet đầu tiên, cột B–F: mã hàng, mô tả, vật liệu, kích thước, FOB USD. Không tự lấy dòng 23 khi thiếu tiêu đề. Giá phải là số hữu hạn lớn hơn 0.
- Phân loại trước: Planter, Wall Decor, Tray, Basket, Storage, Accent Lamp, Pendant Lamp, Floor Lamp, Table Lamp. Không nhận diện được thì để Unknown. Mô tả chỉ ghi Lamp được phân loại sơ bộ theo chiều cao: từ 100 cm là Floor Lamp; đây là quy ước, không xác nhận loại hàng qua ảnh.
- Chuẩn hóa dấu nhân, khoảng trắng, đường kính và chiều cao. Kích thước có nhiều đường kính/chiều cao hoặc đơn vị chưa hỗ trợ được chuyển sang kiểm tra thủ công. Nếu cột kích thước ghi carton, lấy Size/Full size từ mô tả.
- Phân biệt mây tự nhiên và Poly Rattan. Julte được chuẩn hóa thành Jute kèm cảnh báo. Wicker chỉ là mô tả cách đan, không tự suy ra vật liệu.
- Gợi ý phải cùng loại, chứa các vật liệu đã khai báo của sản phẩm catalog và mỗi chiều lệch không quá 20% so với catalog; có thể hoán đổi dài/rộng. Ngưỡng đề xuất nằm ở `dimensionTolerance`. Kích thước trong mô tả lệch cột Item Size không quá `sizeRoundingToleranceCm` (1 cm) mỗi chiều được coi là làm tròn, chỉ cảnh báo. Vật liệu `natural_fiber` trong catalog khớp với rattan, abaca, jute, seagrass, lục bình hoặc tre (không gồm Poly Rattan). Chỉ xếp hạng theo độ lệch kích thước sau khi lọc các điều kiện này.
- Không tự ghép sản phẩm thiếu đối chiếu. Không tự so chao đèn riêng với đèn hoàn chỉnh. Mâu thuẫn kích thước hoặc Pendant có Base sẽ yêu cầu kiểm tra, chưa tính giá.
- Gợi ý chưa xác nhận hình dáng, màu sắc, ảnh, phụ kiện hay giá hiện hành. Catalog `src/benchmark.json` (403 sản phẩm, lấy ngày 2026-11-06) được tạo bằng `scraper/` từ trang danh mục panhomestores.com: `price_aed` là giá gốc, `sale_price_aed` là giá đang bán, `price_checked_at` là ngày lấy. Túi, bộ nhiều món, kệ/giá/tủ, móc treo, chậu treo và đèn nhiều bóng bị loại khỏi catalog vì không so được với hàng báo giá. Cập nhật catalog: xem `tools/scraper/README.md`.
- Tổng FOB cộng mỗi mã một lần, không phải giá trị đơn hàng. Tổng giá tham khảo và tỷ lệ bình quân chỉ tính dòng có gợi ý. Giá trống được giữ trống khi xuất Excel, không đổi thành 0.
- Đổi tỷ giá sẽ tính lại ngay. Workbook xuất có loại hàng, trạng thái, lý do, cảnh báo và dòng nguồn. Các file nguồn không bị sửa.

## Kiểm tra

```bash
npm test
npm run build
node tests/check-workbooks.mjs "D:/Others/document/compare price"
```

`npm test` và test backend dùng catalog cố định `tests/fixtures/benchmark.test.json`, nên cập nhật `src/benchmark.json` không làm hỏng test. Kiểm tra workbook dùng catalog thật. Kiểm tra workbook cần Python và các dependency backend. Script đọc file nguồn, đối chiếu toàn bộ kết quả frontend/backend, không ghi lại file Excel. Chạy `python -B -m unittest test_comparison -v` trong thư mục `tools/backend` để kiểm tra API và xuất Excel.

## Thư mục `tools/`

- `tools/backend`: API Python (FastAPI) dùng chung catalog `src/benchmark.json`. Cài: `pip install -r tools/backend/requirements.txt`.
- `tools/scraper`: lấy dữ liệu sản phẩm Pan Home và xuất catalog cho app. Hướng dẫn trong `tools/scraper/README.md`; dữ liệu đã lấy nằm ở `tools/scraper/output/`.
