"""Conservative reference matching; shared benchmark with the browser engine."""
import json
import math
import re
from pathlib import Path

CONFIG = json.loads((Path(__file__).resolve().parents[2] / 'src/benchmark.json').read_text(encoding='utf-8'))
PAN_HOME_BENCHMARK = CONFIG['products']
EXCHANGE_RATE_DEFAULT = 3.6725
RULE_VERSION = 3
# Catalog entries may declare this group instead of a specific fibre.
NATURAL_FIBERS = ('rattan','abaca','jute','seagrass','water_hyacinth','bamboo')

def rounded(value):
    return math.floor((value + 2.220446049250313e-16) * 100 + 0.5) / 100

def validate_rate(value):
    rate = float(value)
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError('Tỷ giá phải là số lớn hơn 0.')
    return rate

def normalize(value):
    return re.sub(r'\s+', ' ', str(value or '').lower().replace('julte','jute').replace('waterhyacinth','water hyacinth')).strip()

def dimensions(value):
    text = re.sub(r'\s+', '', normalize(value).replace('×','x').replace('cm',''))
    if '/' in text or re.search(r'\b(?:mm|inch|inches)\b',normalize(value)):
        return None
    parts = text.split('x')
    if len(parts) not in (2,3) or any(not re.fullmatch(r'[dh]?\d+(?:\.\d+)?',p) for p in parts):
        return None
    nums = [float(re.sub(r'^[dh]','',p)) for p in parts]
    if min(nums) <= 0:
        return None
    return [nums[0],nums[0],nums[1]] if len(nums)==2 else nums

def clean_dimension(desc, raw):
    if raw and not re.search(r'carton|box|packing',str(raw),re.I):
        return str(raw).strip()
    m = re.search(r'(?:full size|size)\s*:\s*([^\n\r;]+)',str(desc or ''),re.I)
    return m[1].strip() if m else 'Chưa có kích thước'

def classify(desc,size):
    text = normalize(desc)
    for pattern, category in [(r'planter|flower pot','Planter'),(r'wall d[eé]cor|wall art','Wall Decor'),
        (r'\btray\b','Tray'),(r'\bbasket\b','Basket'),(r'\bstorage\b','Storage'),
        (r'uplight|accent lamp','Accent Lamp'),(r'pendant|hanging lamp','Pendant Lamp'),
        (r'floor lamp','Floor Lamp'),(r'table lamp','Table Lamp')]:
        if re.search(pattern,text): return category
    if re.search(r'\blamp\b',text):
        dims = dimensions(size)
        if dims: return 'Floor Lamp' if dims[2]>=100 else 'Table Lamp'
    return 'Unknown'

def materials(value):
    text=normalize(value); found=[]
    if re.search(r'poly\s*rattan|resin\s*wicker',text):
        found.append('poly_rattan'); text=re.sub(r'poly\s*rattan|resin\s*wicker','',text)
    patterns={'rattan':r'\brattan\b','abaca':r'\babaca\b','jute':r'\bjute\b','seagrass':r'\bseagrass\b',
        'water_hyacinth':r'water hyacinth','bamboo':r'\bbamboo\b','capiz':r'\bcapiz\b',
        'mop':r'\bmop\b|mother of pearl','paper':r'\bpaper\b','cotton':r'\bcotton\b',
        'ceramic':r'\bceramic\b','marble':r'\bmarble\b','polyresin':r'\bpolyresin\b','wood':r'\bwood(?:en)?\b'}
    found += [key for key,pattern in patterns.items() if re.search(pattern,text)]
    if any(m in NATURAL_FIBERS for m in found): found.append('natural_fiber')
    return found

def distance(a,b):
    return min(max(abs(v-b[i])/b[i] for i,v in enumerate(a)),
               max(abs(v-b[i])/b[i] for i,v in enumerate([a[1],a[0],a[2]])))

def max_gap_cm(a,b):
    """Largest per-axis gap in cm, allowing length/width swap."""
    return min(max(abs(v-b[i]) for i,v in enumerate(x)) for x in (a,[a[1],a[0],a[2]]))

def match_details(desc,material,raw_size):
    size=clean_dimension(desc,raw_size); category=classify(desc,size); warnings=[]; conflict=False
    dims=dimensions(size)
    m=re.search(r'(?:full size|size)\s*:\s*([^\n\r;]+)',desc,re.I)
    described=m[1] if m else next((line for line in desc.split('\n') if re.fullmatch(r'\s*[dD\d][\d\s.dDhHxX×/cmCM]+',line) and re.search(r'[x×]',line,re.I)),None)
    desc_dims=dimensions(described)
    if raw_size and re.search(r'carton|box|packing',raw_size,re.I):
        warnings.append('Kích thước lấy từ mô tả vì cột kích thước chứa thông tin đóng gói.')
    def tokens(text): return [float(n) for n in re.findall(r'\d+(?:\.\d+)?',str(text or ''))]
    gap=max_gap_cm(dims,desc_dims) if dims and desc_dims else None
    size_conflict=bool(described) and (gap>CONFIG['sizeRoundingToleranceCm'] if gap is not None else tokens(size)!=tokens(described))
    if size_conflict:
        warnings.append('Kích thước trong mô tả khác cột Item Size. Cần xác nhận.'); conflict=True
    elif gap is not None and gap>0.001:
        warnings.append('Kích thước trong mô tả lệch tối đa 1 cm so với cột Item Size (làm tròn). Dùng cột Item Size.')
    if not dims: warnings.append('Kích thước thiếu, có nhiều giá trị hoặc chưa hỗ trợ đơn vị. Cần kiểm tra.')
    if re.search('pendant',desc,re.I) and re.search(r'\bbase\s*:',desc,re.I):
        warnings.append('Mô tả ghi Pendant nhưng có chân đế Base. Kiểm tra ảnh và loại đèn.'); conflict=True
    if re.search('julte',material+' '+desc,re.I): warnings.append('Đã chuẩn hóa từ Julte thành Jute; cần xác nhận vật liệu.')
    source_materials=materials(material or desc)
    candidates=[p for p in PAN_HOME_BENCHMARK.values() if p['category']==category]
    reason='Chưa có đối chiếu cùng loại trong catalog.'; product=None
    if conflict or not dims or category=='Unknown': reason='Cần kiểm tra dữ liệu trước khi đối chiếu.'
    elif candidates:
        matches=[p for p in candidates if p['scope']=='complete' and all(m in source_materials for m in p['materials'])
                 and distance(dims,p['dimensions'])<=CONFIG['dimensionTolerance']]
        matches.sort(key=lambda p:distance(dims,p['dimensions']))
        product=matches[0] if matches else None
        reason=('Gợi ý cùng loại/vật liệu, mỗi chiều lệch tối đa 20%. Cần xác nhận ảnh, phụ kiện và giá.' if product
                else 'Chưa có đối chiếu phù hợp vật liệu, kích thước hoặc cấu hình sản phẩm.')
    if product:
        warnings.append(f"Giá catalog lấy ngày {product['price_checked_at']}. Cần xác nhận giá hiện hành."
                        if product.get('price_checked_at') else 'Giá catalog chưa có ngày xác minh. Chỉ dùng tham khảo.')
    return dict(size=size,category=category,warnings=warnings,product=product,match_reason=reason,
                match_status='candidate' if product else 'review' if conflict or not dims or category=='Unknown' else 'unmatched')

def compare_row(row,index,rate):
    detail=match_details(row['desc'],row['mat_color'],row['size']); p=detail.pop('product')
    usd=rounded(p['price_aed']/rate) if p else None
    return dict(row,stt=index+1,**detail,matched_title=p['title'] if p else 'Chưa có đối chiếu',
                matched_specs=p['specs'] if p else '',retail_aed=p['price_aed'] if p else None,
                retail_usd=usd,markup_ratio=rounded(usd/row['fob_price']) if p else None,
                url=p['url'] if p else '',price_checked_at=p.get('price_checked_at') if p else None)

def reprice(items,rate,warnings=None):
    rate=validate_rate(rate); updated=[]
    for item in items:
        usd=rounded(item['retail_aed']/rate) if item['retail_aed'] is not None else None
        updated.append(dict(item,retail_usd=usd,markup_ratio=rounded(usd/item['fob_price']) if usd is not None else None))
    candidates=[x for x in updated if x['retail_aed'] is not None]
    def total(rows,key): return rounded(sum(x[key] for x in rows))
    return dict(rule_version=RULE_VERSION,warnings=warnings or [],items=updated,summary=dict(
        total_items=len(updated),candidate_items=len(candidates),unmatched_items=len(updated)-len(candidates),
        total_fob_usd=total(updated,'fob_price'),candidate_fob_usd=total(candidates,'fob_price'),
        total_retail_usd=total(candidates,'retail_usd') if candidates else None,
        total_retail_aed=total(candidates,'retail_aed') if candidates else None,
        avg_markup_ratio=rounded(sum(x['markup_ratio'] for x in candidates)/len(candidates)) if candidates else None,
        exchange_rate=rate))
