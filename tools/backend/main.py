import io
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Pan Home Price Comparison API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from comparison import (EXCHANGE_RATE_DEFAULT, PAN_HOME_BENCHMARK, compare_row, reprice, validate_rate)
import math

class CompareItem(BaseModel):
    stt: int
    ref: str
    desc: str
    mat_color: str
    size: str
    fob_price: float
    matched_title: str
    category: str
    matched_specs: str
    retail_aed: Optional[float] = None
    retail_usd: Optional[float] = None
    markup_ratio: Optional[float] = None
    url: str = ''
    match_status: str = 'unmatched'
    match_reason: str = ''
    warnings: List[str] = []
    source_sheet: str = ''
    source_row: int = 0

class ExportRequest(BaseModel):
    items: List[CompareItem]
    exchange_rate: Optional[float] = EXCHANGE_RATE_DEFAULT

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Pan Home Price Comparator"}

@app.get("/api/catalog")
def get_catalog():
    return PAN_HOME_BENCHMARK

@app.post("/api/compare")
async def compare_file(file: UploadFile = File(...), rate: float = Form(EXCHANGE_RATE_DEFAULT)):
    try:
        rate = validate_rate(rate)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    contents = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        formulas = openpyxl.load_workbook(io.BytesIO(contents), data_only=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Không thể đọc file Excel: {exc}")
    sheet = wb.worksheets[0]
    header = next((r for r in range(1,sheet.max_row+1) if re.search(r'ref|item|code',str(sheet.cell(r,2).value or ''),re.I)),None)
    if header is None:
        raise HTTPException(status_code=400, detail='Không tìm thấy tiêu đề mã hàng ở cột B. Cần kiểm tra bố cục.')
    warnings = []
    for row in formulas.worksheets[0]:
        for cell in row:
            if cell.data_type == 'e' or (cell.data_type == 'f' and '#REF!' in str(cell.value)):
                warnings.append(f'{sheet.title}!{cell.coordinate}: ô có lỗi công thức.')
    if re.search('HS Code',str(sheet.cell(header,4).value or ''),re.I):
        warnings.append('Cột D ghi HS Code. Đang đọc nội dung làm vật liệu; cần xác nhận tiêu đề.')
    items = []; seen = set()
    for r in range(header+1,sheet.max_row+1):
        ref,desc,material,size,raw = [sheet.cell(r,c).value for c in range(2,7)]
        if not ref or ref == ':' or (not desc and raw is None): continue
        if isinstance(raw,(int,float)) and not isinstance(raw,bool): price=float(raw)
        elif re.fullmatch(r'\s*\d+(?:\.\d+)?\s*',str(raw or '')): price=float(raw)
        else: price=float('nan')
        if not math.isfinite(price) or price <= 0:
            warnings.append(f'{sheet.title}!F{r}: giá FOB không hợp lệ, dòng không được nhập.'); continue
        ref=str(ref).strip()
        item=compare_row(dict(ref=ref,desc=str(desc or ''),mat_color=str(material or '').strip(),size=str(size or ''),
                             fob_price=price,source_sheet=sheet.title,source_row=r),len(items),rate)
        if ref in seen: item['warnings'].append('Mã hàng trùng trong file. Chưa tự gộp.')
        seen.add(ref);items.append(item)
    if not items:
        raise HTTPException(status_code=400,detail='Không tìm thấy dòng sản phẩm có FOB hợp lệ.')
    if len(wb.worksheets)>1: warnings.append(f'Chỉ đọc sheet đầu tiên: {sheet.title}. Các sheet khác chưa được nhập.')
    return reprice(items,rate,warnings)

@app.post("/api/export")
def export_excel(payload: ExportRequest):
    try:
        rate = validate_rate(payload.exchange_rate)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    wb_out = openpyxl.Workbook()
    ws = wb_out.active
    ws.title = "So sánh giá Pan Home"
    ws.views.sheetView[0].showGridLines = True
    
    # Title Block
    ws.merge_cells("A1:L1")
    title_cell = ws["A1"]
    title_cell.value = "BẢNG SO SÁNH FOB VÀ GIÁ CATALOG THAM KHẢO PAN HOME"
    title_cell.font = Font(name="Segoe UI", size=15, bold=True, color="1F4E79")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36
    
    ws.merge_cells("A2:L2")
    sub_cell = ws["A2"]
    sub_cell.value = f"Tỷ giá: 1 USD = {rate} AED. Giá catalog tham khảo, chưa xác minh ngày cập nhật. Không phải giá trị đơn hàng."
    sub_cell.font = Font(name="Segoe UI", size=10, italic=True, color="595959")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 22
    
    headers = [
        "STT", "Mã SP Vendor", "Mô tả sản phẩm nội bộ", "Vật liệu & Màu sắc",
        "Kích thước gốc", "Giá FOB Hải Phòng (USD)", "Sản phẩm tương đồng trên Pan Home",
        "Vật liệu & Kích thước đối sánh", "Giá Gốc Niêm Yết (AED)", "Giá Gốc Quy Đổi (USD)",
        "Tỷ lệ Bán lẻ / FOB", "Đường Link Sản Phẩm", "Loại hàng", "Trạng thái", "Lý do", "Cảnh báo", "Dòng nguồn"
    ]
    
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9')
    )
    
    ws.row_dimensions[4].height = 32
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    regular_font = Font(name="Segoe UI", size=9.5)
    bold_font = Font(name="Segoe UI", size=9.5, bold=True)
    link_font = Font(name="Segoe UI", size=9.5, color="0563C1", underline="single")
    
    row_out = 5
    for it in payload.items:
        current_fill = zebra_fill if (it.stt % 2 == 0) else white_fill
        ws.row_dimensions[row_out].height = 24
        
        ws.cell(row_out, 1, it.stt).alignment = Alignment(horizontal="center", vertical="center")
        
        c2 = ws.cell(row_out, 2, it.ref)
        c2.font = bold_font
        c2.alignment = Alignment(horizontal="center", vertical="center")
        
        ws.cell(row_out, 3, it.desc).alignment = Alignment(horizontal="left", vertical="center")
        ws.cell(row_out, 4, it.mat_color).alignment = Alignment(horizontal="left", vertical="center")
        ws.cell(row_out, 5, it.size).alignment = Alignment(horizontal="center", vertical="center")
        
        c6 = ws.cell(row_out, 6, it.fob_price)
        c6.number_format = '"$"#,##0.00'
        c6.alignment = Alignment(horizontal="right", vertical="center")
        c6.font = bold_font
        
        ws.cell(row_out, 7, it.matched_title).alignment = Alignment(horizontal="left", vertical="center")
        ws.cell(row_out, 8, it.matched_specs).alignment = Alignment(horizontal="left", vertical="center")
        
        c9 = ws.cell(row_out, 9, it.retail_aed)
        c9.number_format = '#,##0.00 "AED"'
        c9.alignment = Alignment(horizontal="right", vertical="center")
        
        c10 = ws.cell(row_out, 10, f'=ROUND(I{row_out}/{rate},2)' if it.retail_aed is not None else None)
        c10.number_format = '"$"#,##0.00'
        c10.alignment = Alignment(horizontal="right", vertical="center")
        c10.font = bold_font
        
        c11 = ws.cell(row_out, 11, f'=ROUND(J{row_out}/F{row_out},2)' if it.retail_aed is not None and it.fob_price > 0 else None)
        c11.number_format = '0.00"x"'
        c11.alignment = Alignment(horizontal="right", vertical="center")
        
        c12 = ws.cell(row_out, 12, "Mở SP Pan Home" if it.url else '')
        if it.url: c12.hyperlink = it.url
        c12.font = link_font
        c12.alignment = Alignment(horizontal="center", vertical="center")
        
        status = {'candidate':'Gợi ý cần xác nhận','review':'Cần kiểm tra','unmatched':'Chưa có đối chiếu'}
        for col_i, value in enumerate([it.category,status.get(it.match_status,it.match_status),it.match_reason,' '.join(it.warnings),f'{it.source_sheet}!{it.source_row}'],13):
            ws.cell(row_out,col_i,value)
        for col_i in [2,3,4,5,7,8,13,14,15,16,17]:
            ws.cell(row_out,col_i).data_type = 's'
        for col_i in range(1, 18):
            cell = ws.cell(row_out, col_i)
            cell.border = thin_border
            if col_i != 12 and col_i not in (2, 6, 10):
                cell.font = regular_font
            cell.fill = current_fill
            
        row_out += 1
        
    col_widths = {1: 6, 2: 14, 3: 32, 4: 25, 5: 18, 6: 18, 7: 35, 8: 42, 9: 18, 10: 18, 11: 18, 12: 20,13:18,14:24,15:55,16:65,17:22}
    for col_i, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col_i)].width = width
        
    stream = io.BytesIO()
    wb_out.save(stream)
    stream.seek(0)
    
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Ket_qua_so_sanh_gia_Pan_Home.xlsx"}
    )
