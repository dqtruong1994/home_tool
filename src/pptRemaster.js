import JSZip from 'jszip';
import pptxgen from 'pptxgenjs';

/**
 * Extracts dominant color (Hue, Sat, Val) from image data URL using Offscreen Canvas
 */
function getDominantHsv(img) {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 40;
    canvas.height = 40;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, 40, 40);
    const data = ctx.getImageData(0, 0, 40, 40).data;

    let rTotal = 0, gTotal = 0, bTotal = 0, count = 0;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i + 1], b = data[i + 2];
      // Skip pure white/gray background
      if (r > 230 && g > 230 && b > 230) continue;
      if (Math.abs(r - g) < 15 && Math.abs(g - b) < 15 && r > 180) continue;
      rTotal += r;
      gTotal += g;
      bTotal += b;
      count++;
    }

    if (count === 0) return { h: 0, s: 0, v: 0.5 };
    const r = (rTotal / count) / 255;
    const g = (gTotal / count) / 255;
    const b = (bTotal / count) / 255;

    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const d = max - min;
    let h = 0;
    if (d !== 0) {
      if (max === r) h = ((g - b) / d) % 6;
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h = Math.round(h * 60);
      if (h < 0) h += 360;
    }
    const s = max === 0 ? 0 : d / max;
    const v = max;
    return { h, s, v };
  } catch (e) {
    return { h: 0, s: 0, v: 0.5 };
  }
}

/**
 * Extracts all product images from uploaded raw PPTX file
 */
export async function extractImagesFromPptx(file) {
  const zip = new JSZip();
  const buffer = await file.arrayBuffer();
  const unzipped = await zip.loadAsync(buffer);
  
  const mediaFiles = [];
  unzipped.forEach((relativePath, zipEntry) => {
    if (relativePath.startsWith('ppt/media/') && !zipEntry.dir) {
      const ext = relativePath.split('.').pop().toLowerCase();
      if (['png', 'jpeg', 'jpg', 'webp'].includes(ext)) {
        mediaFiles.push(zipEntry);
      }
    }
  });

  const extracted = [];
  for (const entry of mediaFiles) {
    const blob = await entry.async('blob');
    if (blob.size < 15000) continue; // Skip small icons, logos

    const dataUrl = await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    });

    const imgMetrics = await new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const hsv = getDominantHsv(img);
        resolve({
          width: img.naturalWidth,
          height: img.naturalHeight,
          ratio: img.naturalWidth / img.naturalHeight,
          hsv
        });
      };
      img.onerror = () => resolve(null);
      img.src = dataUrl;
    });

    if (imgMetrics && imgMetrics.width >= 100 && imgMetrics.height >= 100) {
      extracted.push({
        dataUrl,
        size: blob.size,
        ...imgMetrics
      });
    }
  }

  // Sort by color hue & brightness
  extracted.sort((a, b) => {
    const hDiff = Math.floor(a.hsv.h / 45) - Math.floor(b.hsv.h / 45);
    if (hDiff !== 0) return hDiff;
    return a.hsv.v - b.hsv.v;
  });

  return extracted;
}

/**
 * Generates Remastered PPT 2 with Uniform Height Layout (A5 Landscape)
 */
export async function generateRemasteredPptx(products, options) {
  const {
    collectionTitle = "Handcrafted Navy & Natural Resin Collection",
    subtitle = "Presentation for Pan Home // 11.2026",
    materialNote = "Material: Resin wicker, iron frame // Render artwork",
    targetPerSlide = 4
  } = options;

  const pres = new pptxgen();

  // A5 Landscape: 8.26 x 5.82 inches
  pres.defineLayout({ name: 'A5_LANDSCAPE', width: 8.26, height: 5.82 });
  pres.layout = 'A5_LANDSCAPE';

  // Motives Palette
  const COLOR_NAVY = '1F4E79';
  const COLOR_GOLD = 'B8860B';
  const COLOR_MUTED = '78909C';
  const COLOR_BG_LIGHT = 'F8FAFC';

  // 1. COVER SLIDE
  const cover = pres.addSlide();
  cover.background = { color: COLOR_BG_LIGHT };

  cover.addText("PRODUCT COLLECTION", {
    x: 0.8, y: 1.5, w: 6.6, h: 0.4,
    fontFace: "Segoe UI", fontSize: 13, bold: true, color: COLOR_GOLD
  });

  cover.addText(collectionTitle.toUpperCase(), {
    x: 0.8, y: 2.0, w: 6.6, h: 1.0,
    fontFace: "Segoe UI", fontSize: 24, bold: true, color: COLOR_NAVY,
    wrap: true
  });

  cover.addText(`${subtitle}\nAuto-Remastered Presentation (Uniform Height Engine)`, {
    x: 0.8, y: 3.2, w: 6.6, h: 0.8,
    fontFace: "Segoe UI", fontSize: 11, color: COLOR_MUTED,
    wrap: true
  });

  // Group items into slides
  const slidesData = [];
  for (let i = 0; i < products.length; i += targetPerSlide) {
    slidesData.push(products.slice(i, i + targetPerSlide));
  }
  const totalSlides = slidesData.length;

  const contentLeft = 0.4;
  const contentTop = 1.10;
  const contentW = 7.46;
  const contentH = 3.90;

  // 2. CONTENT SLIDES
  for (let sIdx = 0; sIdx < slidesData.length; sIdx++) {
    const slideItems = slidesData[sIdx];
    const slide = pres.addSlide();
    slide.background = { color: 'FFFFFF' };

    // Header Title
    slide.addText(collectionTitle.toUpperCase(), {
      x: 0.4, y: 0.25, w: 5.0, h: 0.35,
      fontFace: "Segoe UI", fontSize: 11, bold: true, color: COLOR_NAVY
    });

    slide.addText(subtitle, {
      x: 0.4, y: 0.55, w: 5.0, h: 0.25,
      fontFace: "Segoe UI", fontSize: 8.5, color: COLOR_MUTED
    });

    // Page Number (e.g. 01 / 10)
    const pageNumStr = `${String(sIdx + 1).padStart(2, '0')} / ${String(totalSlides).padStart(2, '0')}`;
    slide.addText(pageNumStr, {
      x: 6.0, y: 0.25, w: 1.86, h: 0.4,
      fontFace: "Segoe UI", fontSize: 9, color: COLOR_MUTED, align: "right"
    });

    const num = slideItems.length;
    const ratios = slideItems.map(p => p.ratio);

    // ========================================================
    // UNIFORM HEIGHT ENGINE (ĐỒNG BỘ THUỘC TÍNH HEIGHT 100%)
    // ========================================================
    if (num === 4) {
      const gapX = 0.35;
      const gapY = 0.25;
      const maxRowH = (contentH - gapY) / 2;
      const usableW = contentW - gapX;

      const hRow1 = Math.min(maxRowH, usableW / (ratios[0] + ratios[1]));
      const hRow2 = Math.min(maxRowH, usableW / (ratios[2] + ratios[3]));
      const targetH = Math.min(hRow1, hRow2);

      // Row 1
      const w0 = ratios[0] * targetH;
      const w1 = ratios[1] * targetH;
      const row1Gap = contentW - (w0 + w1);
      const topRow1 = contentTop;

      slide.addImage({ data: slideItems[0].dataUrl, x: contentLeft, y: topRow1, w: w0, h: targetH });
      slide.addImage({ data: slideItems[1].dataUrl, x: contentLeft + w0 + row1Gap, y: topRow1, w: w1, h: targetH });

      // Row 2
      const w2 = ratios[2] * targetH;
      const w3 = ratios[3] * targetH;
      const row2Gap = contentW - (w2 + w3);
      const topRow2 = topRow1 + targetH + gapY;

      slide.addImage({ data: slideItems[2].dataUrl, x: contentLeft, y: topRow2, w: w2, h: targetH });
      slide.addImage({ data: slideItems[3].dataUrl, x: contentLeft + w2 + row2Gap, y: topRow2, w: w3, h: targetH });

    } else if (num === 3) {
      const minGap = 0.25;
      const usableW = contentW - minGap * 2;
      const totalR = ratios[0] + ratios[1] + ratios[2];
      const targetH = Math.min(contentH, usableW / totalR);

      const widths = ratios.map(r => r * targetH);
      const totalImgW = widths.reduce((a, b) => a + b, 0);
      const actualGap = (contentW - totalImgW) / 2;
      const topY = contentTop + (contentH - targetH) / 2;

      let curX = contentLeft;
      for (let i = 0; i < 3; i++) {
        slide.addImage({ data: slideItems[i].dataUrl, x: curX, y: topY, w: widths[i], h: targetH });
        curX += widths[i] + actualGap;
      }

    } else if (num === 2) {
      const minGap = 0.4;
      const usableW = contentW - minGap;
      const totalR = ratios[0] + ratios[1];
      const targetH = Math.min(contentH, usableW / totalR);

      const widths = ratios.map(r => r * targetH);
      const totalImgW = widths.reduce((a, b) => a + b, 0);
      const actualGap = contentW - totalImgW;
      const topY = contentTop + (contentH - targetH) / 2;

      slide.addImage({ data: slideItems[0].dataUrl, x: contentLeft, y: topY, w: widths[0], h: targetH });
      slide.addImage({ data: slideItems[1].dataUrl, x: contentLeft + widths[0] + actualGap, y: topY, w: widths[1], h: targetH });

    } else if (num === 1) {
      const r = ratios[0];
      let w, h;
      if (r > contentW / contentH) {
        w = contentW;
        h = contentW / r;
      } else {
        h = contentH;
        w = contentH * r;
      }
      const topY = contentTop + (contentH - h) / 2;
      const leftX = contentLeft + (contentW - w) / 2;
      slide.addImage({ data: slideItems[0].dataUrl, x: leftX, y: topY, w: w, h });
    }

    // Footer note
    slide.addText(materialNote, {
      x: 0.4, y: 5.15, w: 7.46, h: 0.4,
      fontFace: "Segoe UI", fontSize: 8.5, italic: true, color: COLOR_MUTED
    });
  }

  const outFileName = `Presentation_${collectionTitle.replace(/[^a-zA-Z0-9]/g, '_')}_Remastered.pptx`;
  await pres.writeFile({ fileName: outFileName });
  return {
    totalImages: products.length,
    totalSlides: totalSlides + 1,
    fileName: outFileName
  };
}
