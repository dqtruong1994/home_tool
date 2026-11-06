import * as XLSX from 'xlsx';
import {compareRow, reprice, validateRate, EXCHANGE_RATE_DEFAULT} from './comparison.js';
export {EXCHANGE_RATE_DEFAULT, PAN_HOME_BENCHMARK, cleanDimension, reprice} from './comparison.js';

export function parseExcelClientSide(arrayBuffer, exchangeRate = EXCHANGE_RATE_DEFAULT) {
  const rate = validateRate(exchangeRate);
  const workbook = XLSX.read(arrayBuffer, {type:'array'});
  const name = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[name];
  if (!worksheet) throw new Error('Workbook không có sheet.');
  const rows = XLSX.utils.sheet_to_json(worksheet, {header:1, blankrows:true, defval:null});
  const header = rows.findIndex(row => /ref|item|code/i.test(String(row[1] ?? '')));
  if (header < 0) throw new Error('Không tìm thấy tiêu đề mã hàng ở cột B. Cần kiểm tra bố cục.');
  const items = [], warnings = [];
  for (const [address, cell] of Object.entries(worksheet)) {
    if (!address.startsWith('!') && (cell.t === 'e' || String(cell.f || '').includes('#REF!'))) warnings.push(`${name}!${address}: ô có lỗi công thức.`);
  }
  if (/HS Code/i.test(String(rows[header][3]))) warnings.push('Cột D ghi HS Code. Đang đọc nội dung làm vật liệu; cần xác nhận tiêu đề.');
  const seen = new Set();
  for (let r=header+1;r<rows.length;r++) {
    const row=rows[r];
    if (!row[1] || row[1] === ':' || (!row[2] && row[5] == null)) continue;
    const raw = row[5];
    const price = typeof raw === 'number' ? raw : /^\s*\d+(?:\.\d+)?\s*$/.test(String(raw ?? '')) ? Number(raw) : NaN;
    if (!Number.isFinite(price) || price <= 0) {
      warnings.push(`${name}!F${r+1}: giá FOB không hợp lệ, dòng không được nhập.`); continue;
    }
    const ref=String(row[1]).trim();
    const item=compareRow({ref,desc:String(row[2] ?? '').replace(/\r\n?/g,'\n'),mat_color:String(row[3] ?? '').trim(),size:String(row[4] ?? ''),fob_price:price,source_sheet:name,source_row:r+1},items.length,rate);
    if (seen.has(ref)) item.warnings.push('Mã hàng trùng trong file. Chưa tự gộp.');
    seen.add(ref);items.push(item);
  }
  if (!items.length) throw new Error('Không tìm thấy dòng sản phẩm có FOB hợp lệ.');
  if (workbook.SheetNames.length > 1) warnings.push(`Chỉ đọc sheet đầu tiên: ${name}. Các sheet khác chưa được nhập.`);
  return reprice(items,rate,warnings);
}

export function buildComparisonWorkbook(items, exchangeRate = EXCHANGE_RATE_DEFAULT) {
  exchangeRate = validateRate(exchangeRate);
  items = reprice(items, exchangeRate).items;
  const wsData = [
    ["BẢNG SO SÁNH FOB VÀ GIÁ CATALOG THAM KHẢO PAN HOME"],
    [`Tỷ giá: 1 USD = ${exchangeRate} AED. Giá catalog tham khảo, chưa xác minh ngày cập nhật. Không phải giá trị đơn hàng.`],
    [],
    [
      "STT", "Mã SP Vendor", "Mô tả sản phẩm nội bộ", "Vật liệu & Màu sắc",
      "Kích thước gốc", "Giá FOB Hải Phòng (USD)", "Sản phẩm tương đồng trên Pan Home",
      "Vật liệu & Kích thước đối sánh", "Giá Gốc Niêm Yết (AED)", "Giá Gốc Quy Đổi (USD)",
      "Tỷ lệ Bán lẻ / FOB", "Link Sản Phẩm Pan Home", "Loại hàng", "Trạng thái", "Lý do", "Cảnh báo", "Dòng nguồn"
    ]
  ];
  
  items.forEach(it => {
    wsData.push([
      it.stt,
      it.ref,
      it.desc,
      it.mat_color,
      it.size,
      it.fob_price,
      it.matched_title,
      it.matched_specs,
      it.retail_aed,
      it.retail_usd,
      it.markup_ratio,
      it.url, it.category, it.match_status === 'candidate' ? 'Gợi ý cần xác nhận' : it.match_status === 'review' ? 'Cần kiểm tra' : 'Chưa có đối chiếu',
      it.match_reason, (it.warnings || []).join(' '), `${it.source_sheet}!${it.source_row}`
    ]);
  });
  
  const ws = XLSX.utils.aoa_to_sheet(wsData);
  items.forEach((it, index) => {
    if (it.url) ws[`L${index+5}`].l = {Target:it.url};
    for (const col of ['B','C','D','E','G','H','M','N','O','P','Q']) {
      const cell=ws[`${col}${index+5}`]; if (cell) cell.t='s';
    }
  });
  
  // Set column widths
  ws['!cols'] = [
    { wch: 6 },
    { wch: 14 },
    { wch: 32 },
    { wch: 25 },
    { wch: 18 },
    { wch: 18 },
    { wch: 35 },
    { wch: 42 },
    { wch: 18 },
    { wch: 18 },
    { wch: 18 },
    { wch: 45 }, { wch: 18 }, { wch: 24 }, { wch: 55 }, { wch: 65 }, { wch: 22 }
  ];
  
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "So sánh giá Pan Home");
  return wb;
}

export function exportToExcelClientSide(items, exchangeRate = EXCHANGE_RATE_DEFAULT) {
  XLSX.writeFile(buildComparisonWorkbook(items, exchangeRate), "Ket_qua_so_sanh_gia_Pan_Home.xlsx");
}
