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
Mở trình duyệt tại `http://localhost:5173`.
