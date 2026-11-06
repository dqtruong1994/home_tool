import test from 'node:test';
import assert from 'node:assert/strict';
import * as XLSX from 'xlsx';
import {classify,dimensions,materials,matchDetails,compareRow,reprice,PAN_HOME_BENCHMARK} from '../src/comparison.js';
import {parseExcelClientSide,buildComparisonWorkbook} from '../src/catalog.js';
import fixture from './fixtures/benchmark.test.json' with { type: 'json' };

// Rules are tested against a fixed catalog, so refreshing src/benchmark.json from Pan Home
// does not break them. comparison.js and catalog.js share this object.
for (const key of Object.keys(PAN_HOME_BENCHMARK)) delete PAN_HOME_BENCHMARK[key];
Object.assign(PAN_HOME_BENCHMARK, fixture.products);

function workbook(rows) {
  const book=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book,XLSX.utils.aoa_to_sheet(rows),'Products');
  return XLSX.write(book,{type:'array',bookType:'xlsx'});
}
test('classify before material; no default lamp match',()=>{
  for(const [desc,material,size,category] of [
    ['Planter','Poly Rattan','44x44x77 cm','Planter'],
    ['Wall décor','Rattan','110cm x 80cm x 3cm','Wall Decor'],
    ['Paper Tray','Paper','40 x 28 x H20 cm','Tray'],
    ['Paper cube storage','Paper','35x35x35 cm','Storage'],
    ['Chair','Wood','40x40x80 cm','Unknown']]) {
    const result=matchDetails(desc,material,size);
    assert.equal(result.category,category);assert.equal(result.product,null);
  }
});
test('normalize dimensions and separate synthetic rattan',()=>{
  assert.deepEqual(dimensions('45 × 45 x H 50 cm'),[45,45,50]);
  assert.deepEqual(dimensions('D30 x H60 cm'),[30,30,60]);
  assert.equal(dimensions('D30/36 x H63 cm'),null);
  assert.deepEqual(materials('Poly Rattan'),['poly_rattan']);
  assert.equal(classify('floor lamp','H150'),'Floor Lamp');
  assert.deepEqual(materials('Julte / Bamboo'),['jute','bamboo','natural_fiber']);
  assert.ok(!materials('Poly Rattan').includes('natural_fiber'));
});
test('size rounding within 1 cm is not a conflict; larger gaps are',()=>{
  const rounded=matchDetails('Lamp full with Uno Shade set;\nFull size:36x36xH60 cm','Bamboo Capiz','36x36xH59.5cm');
  assert.equal(rounded.match_status,'candidate');
  assert.ok(rounded.warnings.some(w=>w.includes('làm tròn')));
  const conflict=matchDetails('Lamp full with Uno Shade set;\nFull size:36x36xH62 cm','Bamboo Capiz','36x36xH59.5cm');
  assert.equal(conflict.match_status,'review');
});
test('natural_fiber catalog entries match natural fibre sources',()=>{
  const result=matchDetails('Lamp full with Uno Shade set;\nFull size:47x47xH146 cm','rattan, color natural','47x47xH146cm');
  assert.equal(result.product?.title,PAN_HOME_BENCHMARK.FLOOR_LAMP_OKRA_TALL.title);
});
test('match only compatible reference; conflicts prevent a suggestion',()=>{
  const result=matchDetails('Table lamp','Bamboo Capiz','30x30xH60cm');
  assert.equal(result.match_status,'candidate');
  assert.equal(result.product.title,'Okra E27 Bamboo & Capiz Shell Lamp');
  assert.equal(matchDetails('Table lamp','Bamboo Capiz','60x60xH60cm').product,null);
  assert.equal(matchDetails('Pendant with shade;\nBase: Paper','Paper','34x34xH63cm').match_status,'review');
  assert.equal(matchDetails('Lamp full;\nFull size:30x30xH62cm','Bamboo Capiz','30x30xH60cm').match_status,'review');
  assert.ok(matchDetails('Storage\n26/34 x 26 x H34 cm','Paper','28/35 x 28 x H34 cm').warnings.some(w=>w.includes('khác')));
});
test('unmatched has no price; repricing covers only candidates',()=>{
  const rows=[compareRow({ref:'A',desc:'Table lamp',mat_color:'Bamboo Capiz',size:'30x30x60cm',fob_price:10},0,3.6725),
    compareRow({ref:'B',desc:'Planter',mat_color:'Rattan',size:'30x30x60cm',fob_price:20},1,3.6725)];
  const result=reprice(rows,4);
  assert.equal(result.items[0].retail_usd,82.75);
  assert.equal(result.items[1].retail_usd,null);
  assert.equal(result.summary.candidate_items,1);
  assert.equal(result.summary.total_fob_usd,30);
  assert.equal(result.summary.candidate_fob_usd,10);
  assert.equal(reprice([rows[1]],4).summary.avg_markup_ratio,null);
  for(const rate of [0,-1,NaN,Infinity,'']) assert.throws(()=>reprice(rows,rate));
  const sheet=buildComparisonWorkbook(rows,4).Sheets['So sánh giá Pan Home'];
  assert.equal(sheet.J5.v,82.75);
  assert.equal(sheet.K5.v,8.28);
  assert.equal(sheet.J6,undefined);
  assert.equal(sheet.N6.v,'Chưa có đối chiếu');
  assert.equal(sheet.L5.l.Target,rows[0].url);
});
test('import excludes invalid FOB and warns about duplicates/formula errors',()=>{
  const bytes=workbook([
    ['', 'Vendor Item Ref. No.','Description','Material','Size','FOB'],
    ['', 'A','Planter','Rattan','30x30x60cm',20],
    ['', 'A','Planter','Rattan','30x30x60cm',21],
    ['', 'B','Planter','Rattan','30x30x60cm','12 USD'],
    ['', 'C','Planter','Rattan','30x30x60cm',0],
    ['', 'D','Planter','Rattan','30x30x60cm',-5],
    ['Total',':',{f:'#REF!',t:'e',v:23}]
  ]);
  const result=parseExcelClientSide(bytes);
  assert.equal(result.items.length,2);
  assert.ok(result.items[1].warnings.some(w=>w.includes('trùng')));
  assert.ok(result.warnings.some(w=>w.includes('C7')));
  assert.equal(result.warnings.filter(w=>w.includes('FOB')).length,3);
  assert.throws(()=>parseExcelClientSide(workbook([['wrong layout']])));
});
