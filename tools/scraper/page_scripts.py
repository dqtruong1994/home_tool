"""JavaScript evaluated inside Pan Home pages. Kept together so selectors are easy to tune."""

# Product URLs end with a SKU like -181ato9900131.
PRODUCT_URL_RE = r'/\/uae_en\/[^?#]+-(\d{3}[a-z0-9]{3}\d{7})$/i'

IS_VERIFICATION_PAGE = r"""
() => !!document.querySelector('#challenge-form, #challenge-stage, #cf-challenge-running, #turnstile-wrapper, iframe[src*="challenges.cloudflare.com"]')
   || /performing security verification|verify you are human|checking your browser|checking if the site connection is secure/i
        .test(document.body ? document.body.innerText : '')
"""

HAS_LISTING = r"""
() => {
  const re = %s;
  return [...document.querySelectorAll('a[href]')].some(a => re.test(a.href.split('?')[0].split('#')[0]));
}
""" % PRODUCT_URL_RE

LISTING_READY = r"""
() => {
  const re = %s;
  if ([...document.querySelectorAll('a[href]')].some(a => re.test(a.href.split('?')[0].split('#')[0]))) return true;
  return /\b0\s+Products?\b|we can.t find products|no products/i.test(document.body ? document.body.innerText : '');
}
""" % PRODUCT_URL_RE

AUTO_SCROLL = r"""
async (step) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let lastHeight = -1;
  for (let i = 0; i < 80; i++) {
    window.scrollBy(0, step);
    await sleep(350);
    const h = document.body.scrollHeight;
    if (window.scrollY + window.innerHeight >= h - 5) {
      if (h === lastHeight) break;
      lastHeight = h;
      await sleep(900);
    }
  }
  window.scrollTo(0, 0);
}
"""

# Listing cards: Magento selectors first (.product-item-info, data-price-type), then a generic fallback
# that walks up from each product link to the smallest element holding only that product.
EXTRACT_LISTING = r"""
() => {
  const re = %s;
  const clean = h => h.split('?')[0].split('#')[0];
  const num = s => {
    if (s === null || s === undefined || s === '') return null;
    const n = Number(String(s).replace(/[^\d.]/g, ''));
    return Number.isFinite(n) && n > 0 ? n : null;
  };
  const items = [];
  const seen = new Set();
  const anchors = [...document.querySelectorAll('a.product-item-link, .product-item-info a, a[href]')];
  for (const a of anchors) {
    const href = clean(a.href || '');
    const m = href.match(re);
    if (!m || seen.has(href)) continue;
    const name = (a.innerText || a.getAttribute('title') || '').trim();
    if (name.length < 8) continue;
    seen.add(href);

    let card = a.closest('.product-item-info, .product-item, li.item');
    if (!card) {
      card = a;
      while (card.parentElement) {
        const p = card.parentElement;
        const n = new Set([...p.querySelectorAll('a[href]')].map(x => clean(x.href)).filter(h => re.test(h))).size;
        if (n > 1) break;
        card = p;
      }
    }
    const text = card.innerText || '';
    const magentoFinal = card.querySelector('[data-price-type="finalPrice"]')?.getAttribute('data-price-amount');
    const magentoOld = card.querySelector('[data-price-type="oldPrice"]')?.getAttribute('data-price-amount');
    const labelledRegular = (text.match(/Regular Price\s*(?:AED)?\s*([\d,]+(?:\.\d+)?)/i) || [])[1];
    const labelledSpecial = (text.match(/Special Price\s*(?:AED)?\s*([\d,]+(?:\.\d+)?)/i) || [])[1];
    const lonePrice = (text.match(/^\s*(?:AED\s*)?([\d,]+(?:\.\d+)?)\s*$/m) || [])[1];

    const regular = num(magentoOld) ?? num(labelledRegular) ?? num(magentoFinal) ?? num(lonePrice);
    const final = num(labelledSpecial) ?? num(magentoFinal) ?? regular;
    const img = card.querySelector('img');
    const image = img ? (img.currentSrc || img.getAttribute('data-src') || img.src || '') : '';
    const stock = /out of stock|sold out/i.test(text) ? 'OutOfStock' : null;
    items.push({ sku: m[1].toUpperCase(), name, url: href, regular, final, image, stock });
  }

  const totalText = (document.body.innerText.match(/(\d[\d,]*)\s+Products?\b/i) || [])[1];
  const current = Number(new URLSearchParams(location.search).get('p') || 1);
  const hasNext = !!document.querySelector('.pages-item-next a, a.action.next, a[rel="next"]')
    || [...document.querySelectorAll('a[href]')].some(a => {
         try { const u = new URL(a.href); return u.pathname === location.pathname && Number(u.searchParams.get('p')) === current + 1; }
         catch { return false; }
       });
  return { total: totalText ? Number(totalText.replace(/,/g, '')) : null, hasNext, items };
}
""" % PRODUCT_URL_RE

# Detail page: opens the spec accordions, then reads ld+json and labelled spec rows.
EXTRACT_DETAIL = r"""
async () => {
  for (const el of document.querySelectorAll('h2, h3, h4, button, [role="button"], .title, div')) {
    const t = (el.innerText || '').trim();
    if ((t === 'Material' || t === 'General specifications' || t === 'Weight & Dimensions') && el.children.length < 4) {
      try { el.click(); } catch {}
    }
  }
  await new Promise(r => setTimeout(r, 800));

  const result = { ld: null, specs: {}, stock: null };
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const j = JSON.parse(s.textContent);
      const list = Array.isArray(j) ? j : (j['@graph'] || [j]);
      const p = list.find(x => x && (x['@type'] === 'Product' || (Array.isArray(x['@type']) && x['@type'].includes('Product'))));
      if (p) { result.ld = p; break; }
    } catch {}
  }
  const text = (document.querySelector('main') || document.body).innerText;
  const grab = label => { const m = text.match(new RegExp(label + '\\s*\\n\\s*([^\\n]+)', 'i')); return m ? m[1].trim() : null; };
  const labels = [
    ['PrimaryMaterial', 'Primary Material'], ['Length', 'Length \\(cm\\)'], ['Width', 'Width \\(cm\\)'],
    ['Height', 'Height \\(cm\\)'], ['Diameter', 'Diameter \\(cm\\)'], ['Weight', 'Weight \\(kg\\)'], ['Color', 'Colou?r']
  ];
  for (const [key, label] of labels) { const v = grab(label); if (v) result.specs[key] = v; }
  if (/out of stock/i.test(text)) result.stock = 'OutOfStock';
  else if (/in stock/i.test(text)) result.stock = 'InStock';
  return result;
}
"""

INSPECT_STRUCTURE = r"""
() => {
  const re = %s;
  const counts = {};
  for (const el of document.querySelectorAll('[class]')) {
    for (const c of el.classList) counts[c] = (counts[c] || 0) + 1;
  }
  const topClasses = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 120);
  const ldJson = [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent.slice(0, 3000));
  const candidates = ['.product-item-info', '.product-item', '.product-item-link', 'li.item.product',
    '[data-price-type="finalPrice"]', '[data-price-type="oldPrice"]', '.price-box', '.pages-item-next',
    '[data-product-id]', '[data-sku]'];
  const selectorCounts = Object.fromEntries(candidates.map(s => [s, document.querySelectorAll(s).length]));
  const productLinks = [...new Set([...document.querySelectorAll('a[href]')].map(a => a.href.split('?')[0]).filter(h => re.test(h)))];
  const sampleCard = (() => {
    const a = [...document.querySelectorAll('a[href]')].find(x => re.test(x.href.split('?')[0]) && (x.innerText || '').trim().length > 8);
    if (!a) return null;
    let c = a; for (let i = 0; i < 6 && c.parentElement; i++) c = c.parentElement;
    return { text: (c.innerText || '').slice(0, 800), html: c.outerHTML.replace(/\s+/g, ' ').slice(0, 4000) };
  })();
  return {
    topClasses, ldJson, selectorCounts,
    productLinkCount: productLinks.length,
    productLinksSample: productLinks.slice(0, 20),
    productCountText: (document.body.innerText.match(/\d[\d,]*\s+Products?\b/i) || [null])[0],
    sampleCard
  };
}
""" % PRODUCT_URL_RE
