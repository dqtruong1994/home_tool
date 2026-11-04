import * as XLSX from 'xlsx';

export const EXCHANGE_RATE_DEFAULT = 3.6725;

export const PAN_HOME_BENCHMARK = {
  RATTAN_ABACA_TABLE_LAMP: {
    title: "Cerah E27 Abaca Table Lamp",
    category: "Table Lamp",
    specs: "Sợi Abaca/mây tự nhiên đan thủ công / Chao vải | Dia 30 x H49 cm",
    price_aed: 429.0,
    url: "https://www.panhomestores.com/uae_en/cerah-e27-abaca-table-lamp-dia-30x49cm-natural-181plc9900036"
  },
  BAMBOO_CAPIZ_TABLE_LAMP: {
    title: "Okra E27 Bamboo & Capiz Shell Lamp",
    category: "Table Lamp",
    specs: "Nan tre đan & cẩn vỏ điệp Capiz tự nhiên | 30 x 30 x H60 cm",
    price_aed: 331.0,
    url: "https://www.panhomestores.com/uae_en/okra-e27-table-lamp-30x60cm-natural-181ato9900131"
  },
  MOP_MARBLE_TABLE_LAMP: {
    title: "Valir E27 Marble / MOP Mosaic Lamp",
    category: "Table Lamp",
    specs: "Khảm hoa văn xà cừ / Chân trụ vững | Dia 33 x H62 cm",
    price_aed: 389.0,
    url: "https://www.panhomestores.com/uae_en/valir-e27-marble-table-lamp-dia-33x62cm-black-181ato9900802"
  },
  CERAMIC_TABLE_LAMP: {
    title: "Denver E27 Ceramic Table Lamp",
    category: "Table Lamp",
    specs: "Thân gốm nghệ thuật / Chao vải dệt | 36 x 36 x H61 cm",
    price_aed: 349.0,
    url: "https://www.panhomestores.com/uae_en/denver-e27-ceramic-table-lamp-36x61cm-white-black-181aic9904485"
  },
  ACCENT_UPLIGHT_LAMP: {
    title: "Merrel G-9 Decorative Accent Lamp",
    category: "Accent Lamp",
    specs: "Đèn bàn decor nhỏ gọn / Vỏ điệp gốm | 19.5 x 19.5 x H29 cm",
    price_aed: 199.0,
    url: "https://www.panhomestores.com/uae_en/merrel-g-9-ceramic-table-lamp-19-5x19-5x29cm-black-181aic9902454"
  },
  FLOOR_LAMP_OKRA_TALL: {
    title: "Okra E27 Natural Woven Floor Lamp",
    category: "Floor Lamp",
    specs: "Cây đèn đứng sợi tự nhiên đan khung kim loại | 43 x 43 x H160 cm",
    price_aed: 649.0,
    url: "https://www.panhomestores.com/uae_en/okra-e27-floor-lamp-43x160cm-natural-181ato9900132"
  },
  FLOOR_LAMP_CALDEA: {
    title: "Caldea E27 Natural Fiber Floor Lamp",
    category: "Floor Lamp",
    specs: "Khung composite vân gỗ / Sợi tự nhiên | 82 x 82 x H160 cm",
    price_aed: 649.0,
    url: "https://www.panhomestores.com/uae_en/caldea-e27-polyresin-floor-lamp-82x160cm-brown-181hel9900722"
  },
  PENDANT_SHADE_SARI: {
    title: "Sari Handwoven Natural Pendant Shade",
    category: "Pendant Lamp",
    specs: "Chao đèn thả sợi mây tre đan thủ công | 29 x 29 x H9 cm",
    price_aed: 149.0,
    url: "https://www.panhomestores.com/uae_en/sari-handwoven-pendant-shade-29x29x9cm-natural-181ato9900183"
  },
  PENDANT_WOODEN_ASHEN: {
    title: "Ashen 24W Wooden Natural Pendant Lamp",
    category: "Pendant Lamp",
    specs: "Đèn thả thanh nan gỗ tự nhiên | 80 x 80 x H50 cm",
    price_aed: 450.0,
    url: "https://www.panhomestores.com/uae_en/ashen-24w-led-3000k-wooden-pendant-lamp-80x50cm-natural-181ato99001404"
  },
  BASKET_SEAGRASS_TEZZA: {
    title: "Tezza Seagrass Storage Basket (White Rim)",
    category: "Basket",
    specs: "Cói tự nhiên dệt phối màu có quai xách | 40 x 45 x H38 cm",
    price_aed: 119.0,
    url: "https://www.panhomestores.com/uae_en/tezza-seagrass-storage-basket-40x45x38cm-natural-white-262tbd9900160"
  },
  BASKET_SEAGRASS_ESTELLA: {
    title: "Estella Seagrass Storage Basket (Natural)",
    category: "Basket",
    specs: "Cói đan dáng tròn có quai xách chắc chắn | 28 x 30 x H30 cm",
    price_aed: 98.0,
    url: "https://www.panhomestores.com/uae_en/estella-seagrass-storage-basket-28x30x30cm-natural-262tbd9900159"
  }
};

export function cleanDimension(desc, rawSize) {
  if (rawSize && !String(rawSize).toLowerCase().includes("carton")) {
    return String(rawSize).trim();
  }
  const m = String(desc || "").match(/(?:Full size:|Size:)\s*([^\n\r;]+)/i);
  if (m) {
    return m[1].trim();
  }
  return "Theo mô tả";
}

export function matchProduct(ref, desc, matColor, sizeStr, fobPrice) {
  const descL = String(desc || "").toLowerCase();
  const matL = (String(matColor || "") + " " + descL).toLowerCase();
  
  if (descL.includes("basket")) {
    if (["50x50", "48x48", "45x45"].some(d => sizeStr.includes(d))) {
      return PAN_HOME_BENCHMARK.BASKET_SEAGRASS_TEZZA;
    }
    return PAN_HOME_BENCHMARK.BASKET_SEAGRASS_ESTELLA;
  }
  
  if (descL.includes("uplight")) {
    return PAN_HOME_BENCHMARK.ACCENT_UPLIGHT_LAMP;
  }
  
  if (descL.includes("pendant")) {
    if (sizeStr.includes("45x45") || sizeStr.includes("40x40")) {
      return PAN_HOME_BENCHMARK.PENDANT_WOODEN_ASHEN;
    }
    return PAN_HOME_BENCHMARK.PENDANT_SHADE_SARI;
  }
  
  if (["h120", "h136", "h146", "h151", "h160", "h174"].some(h => sizeStr.toLowerCase().includes(h))) {
    if (matL.includes("water hyacinth") || matL.includes("waterhyacinth")) {
      return PAN_HOME_BENCHMARK.FLOOR_LAMP_CALDEA;
    }
    return PAN_HOME_BENCHMARK.FLOOR_LAMP_OKRA_TALL;
  }
  
  if (matL.includes("mop") || matL.includes("mother of pearl")) {
    return PAN_HOME_BENCHMARK.MOP_MARBLE_TABLE_LAMP;
  }
  if (matL.includes("capiz")) {
    return PAN_HOME_BENCHMARK.BAMBOO_CAPIZ_TABLE_LAMP;
  }
  if (matL.includes("jute") || matL.includes("abaca")) {
    return PAN_HOME_BENCHMARK.RATTAN_ABACA_TABLE_LAMP;
  }
  if (matL.includes("paper")) {
    return PAN_HOME_BENCHMARK.CERAMIC_TABLE_LAMP;
  }
  if (matL.includes("seagrass") || matL.includes("rattan")) {
    return PAN_HOME_BENCHMARK.RATTAN_ABACA_TABLE_LAMP;
  }
  
  return PAN_HOME_BENCHMARK.BAMBOO_CAPIZ_TABLE_LAMP;
}

export function parseExcelClientSide(arrayBuffer, exchangeRate = EXCHANGE_RATE_DEFAULT) {
  const workbook = XLSX.read(arrayBuffer, { type: 'array' });
  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];
  
  const rawData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
  
  let startRow = 0;
  for (let r = 0; r < Math.min(30, rawData.length); r++) {
    const row = rawData[r] || [];
    const valB = String(row[1] || "").toLowerCase();
    if (valB.includes("ref") || valB.includes("item") || valB.includes("code")) {
      startRow = r + 1;
      break;
    }
  }
  if (startRow === 0) startRow = 22; // 0-based for row 23
  
  const items = [];
  let stt = 1;
  
  for (let r = startRow; r < rawData.length; r++) {
    const row = rawData[r] || [];
    const ref = row[1];
    const desc = row[2];
    const matColor = row[3];
    const sizeRaw = row[4];
    const fobVal = row[5];
    
    if (!ref || fobVal === undefined || fobVal === null || fobVal === "") continue;
    const fobPrice = parseFloat(fobVal);
    if (isNaN(fobPrice) || fobPrice <= 0) continue;
    
    const sizeClean = cleanDimension(desc, sizeRaw);
    const matched = matchProduct(String(ref), String(desc), String(matColor), sizeClean, fobPrice);
    
    const retailAed = matched.price_aed;
    const retailUsd = Number((retailAed / exchangeRate).toFixed(2));
    const ratio = Number((retailUsd / fobPrice).toFixed(2));
    
    const firstLineDesc = String(desc || "").split("\n")[0].trim();
    
    items.push({
      stt: stt++,
      ref: String(ref).trim(),
      desc: firstLineDesc,
      mat_color: String(matColor || "").trim(),
      size: sizeClean,
      fob_price: fobPrice,
      matched_title: matched.title,
      category: matched.category,
      matched_specs: matched.specs,
      retail_aed: retailAed,
      retail_usd: retailUsd,
      markup_ratio: ratio,
      url: matched.url
    });
  }
  
  const totalFob = items.reduce((acc, it) => acc + it.fob_price, 0);
  const totalRetailUsd = items.reduce((acc, it) => acc + it.retail_usd, 0);
  const totalRetailAed = items.reduce((acc, it) => acc + it.retail_aed, 0);
  const avgRatio = items.length > 0 ? Number((items.reduce((acc, it) => acc + it.markup_ratio, 0) / items.length).toFixed(2)) : 0;
  
  return {
    summary: {
      total_items: items.length,
      total_fob_usd: Number(totalFob.toFixed(2)),
      total_retail_usd: Number(totalRetailUsd.toFixed(2)),
      total_retail_aed: Number(totalRetailAed.toFixed(2)),
      avg_markup_ratio: avgRatio,
      exchange_rate: exchangeRate
    },
    items
  };
}

export function exportToExcelClientSide(items, exchangeRate = EXCHANGE_RATE_DEFAULT) {
  const wsData = [
    ["BẢNG SO SÁNH GIÁ NỘI BỘ (FOB) VÀ GIÁ GỐC NIÊM YẾT TẠI PAN HOME (panhomestores.com)"],
    [`Website đối chiếu: panhomestores.com (UAE) | Tỷ giá: 1 USD = ${exchangeRate} AED | Tiêu chí: Giá Gốc Niêm Yết (Regular Price)`],
    [],
    [
      "STT", "Mã SP Vendor", "Mô tả sản phẩm nội bộ", "Vật liệu & Màu sắc",
      "Kích thước gốc", "Giá FOB Hải Phòng (USD)", "Sản phẩm tương đồng trên Pan Home",
      "Vật liệu & Kích thước đối sánh", "Giá Gốc Niêm Yết (AED)", "Giá Gốc Quy Đổi (USD)",
      "Tỷ lệ Bán lẻ / FOB", "Link Sản Phẩm Pan Home"
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
      it.url
    ]);
  });
  
  const ws = XLSX.utils.aoa_to_sheet(wsData);
  
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
    { wch: 45 }
  ];
  
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "So sánh giá Pan Home");
  XLSX.writeFile(wb, "Ket_qua_so_sanh_gia_Pan_Home.xlsx");
}
