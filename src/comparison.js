import benchmark from './benchmark.json' with { type: 'json' };

export const EXCHANGE_RATE_DEFAULT = 3.6725;
export const PAN_HOME_BENCHMARK = benchmark.products;
export const RULE_VERSION = 3;
// Catalog entries may declare this group instead of a specific fibre.
const NATURAL_FIBERS = ['rattan','abaca','jute','seagrass','water_hyacinth','bamboo'];
export const roundMoney = value => Math.round((value + Number.EPSILON) * 100) / 100;
export function validateRate(rate) {
  const value = Number(rate);
  if (!Number.isFinite(value) || value <= 0) throw new Error('Tỷ giá phải là số lớn hơn 0.');
  return value;
}

export function normalizeText(value) {
  return String(value ?? '').toLowerCase().replace(/julte/g, 'jute')
    .replace(/waterhyacinth/g, 'water hyacinth').replace(/\s+/g, ' ').trim();
}

export function dimensions(value) {
  const text = normalizeText(value).replace(/×/g, 'x').replace(/cm/g, '').replace(/\s+/g, '');
  // Multiple diameters/heights must be reviewed, not silently collapsed.
  if (text.includes('/') || /\b(?:mm|inch|inches)\b/.test(normalizeText(value))) return null;
  const parts = text.split('x');
  if (parts.length < 2 || parts.length > 3 || parts.some(p => !/^[dh]?\d+(?:\.\d+)?$/.test(p))) return null;
  const nums = parts.map(p => Number(p.replace(/^[dh]/, '')));
  if (nums.some(n => n <= 0)) return null;
  return nums.length === 2 ? [nums[0], nums[0], nums[1]] : nums;
}

export function cleanDimension(desc, rawSize) {
  if (rawSize && !/carton|box|packing/i.test(String(rawSize))) return String(rawSize).trim();
  return String(desc ?? '').match(/(?:full size|size)\s*:\s*([^\n\r;]+)/i)?.[1]?.trim() || 'Chưa có kích thước';
}

export function classify(desc, size) {
  const text = normalizeText(desc);
  if (/planter|flower pot/.test(text)) return 'Planter';
  if (/wall d[eé]cor|wall art/.test(text)) return 'Wall Decor';
  if (/\btray\b/.test(text)) return 'Tray';
  if (/\bbasket\b/.test(text)) return 'Basket';
  if (/\bstorage\b/.test(text)) return 'Storage';
  if (/uplight|accent lamp/.test(text)) return 'Accent Lamp';
  if (/pendant|hanging lamp/.test(text)) return 'Pendant Lamp';
  if (/floor lamp/.test(text)) return 'Floor Lamp';
  if (/table lamp/.test(text)) return 'Table Lamp';
  if (/\blamp\b/.test(text)) {
    const dims = dimensions(size);
    return dims ? (dims[2] >= 100 ? 'Floor Lamp' : 'Table Lamp') : 'Unknown';
  }
  return 'Unknown';
}

export function materials(value) {
  let text = normalizeText(value);
  const found = [];
  if (/poly\s*rattan|resin\s*wicker/.test(text)) {
    found.push('poly_rattan'); text = text.replace(/poly\s*rattan|resin\s*wicker/g, '');
  }
  for (const [name, pattern] of Object.entries({rattan:/\brattan\b/,abaca:/\babaca\b/,jute:/\bjute\b/,
    seagrass:/\bseagrass\b/,water_hyacinth:/water hyacinth/,bamboo:/\bbamboo\b/,capiz:/\bcapiz\b/,
    mop:/\bmop\b|mother of pearl/,paper:/\bpaper\b/,cotton:/\bcotton\b/,ceramic:/\bceramic\b/,
    marble:/\bmarble\b/,polyresin:/\bpolyresin\b/,wood:/\bwood(?:en)?\b/})) {
    if (pattern.test(text)) found.push(name);
  }
  if (found.some(m => NATURAL_FIBERS.includes(m))) found.push('natural_fiber');
  return found;
}

function distance(a, b) {
  const direct = Math.max(...a.map((v, i) => Math.abs(v - b[i]) / b[i]));
  const swapped = [a[1], a[0], a[2]];
  return Math.min(direct, Math.max(...swapped.map((v, i) => Math.abs(v - b[i]) / b[i])));
}

// Largest per-axis gap in cm, allowing length/width swap.
function maxGapCm(a, b) {
  const gap = x => Math.max(...x.map((v, i) => Math.abs(v - b[i])));
  return Math.min(gap(a), gap([a[1], a[0], a[2]]));
}

export function matchDetails(desc, material, rawSize) {
  const size = cleanDimension(desc, rawSize);
  const category = classify(desc, size);
  const warnings = [];
  const dims = dimensions(size);
  const described = String(desc ?? '').match(/(?:full size|size)\s*:\s*([^\n\r;]+)/i)?.[1]
    || String(desc ?? '').split('\n').find(line => /^\s*[dD\d][\d\s.dDhHxX×/cmCM]+$/.test(line) && /[x×]/i.test(line));
  const descDims = dimensions(described);
  if (rawSize && /carton|box|packing/i.test(String(rawSize))) warnings.push('Kích thước lấy từ mô tả vì cột kích thước chứa thông tin đóng gói.');
  let conflict = false;
  const tokens = text => String(text ?? '').match(/\d+(?:\.\d+)?/g)?.map(Number);
  const gap = dims && descDims ? maxGapCm(dims, descDims) : null;
  const sizeConflict = described && (gap != null ? gap > benchmark.sizeRoundingToleranceCm
    : JSON.stringify(tokens(size)) !== JSON.stringify(tokens(described)));
  if (sizeConflict) {
    warnings.push('Kích thước trong mô tả khác cột Item Size. Cần xác nhận.'); conflict = true;
  } else if (gap > 0.001) {
    warnings.push('Kích thước trong mô tả lệch tối đa 1 cm so với cột Item Size (làm tròn). Dùng cột Item Size.');
  }
  if (!dims) warnings.push('Kích thước thiếu, có nhiều giá trị hoặc chưa hỗ trợ đơn vị. Cần kiểm tra.');
  if (/pendant/i.test(desc) && /\bbase\s*:/i.test(desc)) {
    warnings.push('Mô tả ghi Pendant nhưng có chân đế Base. Kiểm tra ảnh và loại đèn.'); conflict = true;
  }
  if (/julte/i.test(material + ' ' + desc)) warnings.push('Đã chuẩn hóa từ Julte thành Jute; cần xác nhận vật liệu.');
  const sourceMaterials = materials(material || desc);
  const candidates = Object.values(PAN_HOME_BENCHMARK).filter(p => p.category === category);
  let reason = 'Chưa có đối chiếu cùng loại trong catalog.';
  let product = null;
  if (conflict || !dims || category === 'Unknown') reason = 'Cần kiểm tra dữ liệu trước khi đối chiếu.';
  else if (candidates.length) {
    const matches = candidates.filter(p => p.scope === 'complete' && p.materials.every(m => sourceMaterials.includes(m))
      && distance(dims, p.dimensions) <= benchmark.dimensionTolerance);
    matches.sort((a,b) => distance(dims,a.dimensions)-distance(dims,b.dimensions));
    product = matches[0] || null;
    reason = product ? 'Gợi ý cùng loại/vật liệu, mỗi chiều lệch tối đa 20%. Cần xác nhận ảnh, phụ kiện và giá.'
      : 'Chưa có đối chiếu phù hợp vật liệu, kích thước hoặc cấu hình sản phẩm.';
  }
  if (product) warnings.push(product.price_checked_at
    ? `Giá catalog lấy ngày ${product.price_checked_at}. Cần xác nhận giá hiện hành.`
    : 'Giá catalog chưa có ngày xác minh. Chỉ dùng tham khảo.');
  return {size, category, warnings, product, match_reason:reason,
    match_status:product ? 'candidate' : (conflict || !dims || category === 'Unknown' ? 'review' : 'unmatched')};
}

export function compareRow(row, index, rate) {
  const details = matchDetails(row.desc, row.mat_color, row.size);
  const p = details.product;
  return {...row, stt:index+1, ...details, product:undefined,
    matched_title:p?.title || 'Chưa có đối chiếu', matched_specs:p?.specs || '',
    retail_aed:p?.price_aed ?? null, retail_usd:p ? roundMoney(p.price_aed/rate) : null,
    markup_ratio:p ? roundMoney(roundMoney(p.price_aed/rate)/row.fob_price) : null,
    url:p?.url || '', price_checked_at:p?.price_checked_at ?? null};
}

export function reprice(items, rate, warnings = []) {
  rate = validateRate(rate);
  const updated = items.map(it => ({...it,
    retail_usd:it.retail_aed == null ? null : roundMoney(it.retail_aed/rate),
    markup_ratio:it.retail_aed == null ? null : roundMoney(roundMoney(it.retail_aed/rate)/it.fob_price)}));
  const candidates = updated.filter(it => it.retail_aed != null);
  const sum = (rows,key) => roundMoney(rows.reduce((a,r) => a+r[key],0));
  return {rule_version:RULE_VERSION,warnings,items:updated,summary:{
    total_items:updated.length,candidate_items:candidates.length,unmatched_items:updated.length-candidates.length,
    total_fob_usd:sum(updated,'fob_price'),candidate_fob_usd:sum(candidates,'fob_price'),
    total_retail_usd:candidates.length ? sum(candidates,'retail_usd') : null,
    total_retail_aed:candidates.length ? sum(candidates,'retail_aed') : null,
    avg_markup_ratio:candidates.length ? roundMoney(candidates.reduce((a,r)=>a+r.markup_ratio,0)/candidates.length) : null,
    exchange_rate:rate}};
}
