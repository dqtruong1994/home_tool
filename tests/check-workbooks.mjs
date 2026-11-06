// Read-only integration check against a directory of real quotations.
// node tests/check-workbooks.mjs "D:/path/to/quotations"
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import {parseExcelClientSide} from '../src/catalog.js';
const directory=process.argv[2];
if(!directory)throw Error('Pass the quotation directory. Source files will not be modified.');
const backend=fileURLToPath(new URL('../tools/backend/',import.meta.url));
const python=`import sys,io,json,asyncio
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[2])
from main import compare_file
from fastapi import UploadFile
async def run():
 with open(sys.argv[1],'rb') as f: data=f.read()
 result=await compare_file(UploadFile(file=io.BytesIO(data)),3.6725)
 print(json.dumps(result,ensure_ascii=False))
asyncio.run(run())`;
for(const name of fs.readdirSync(directory).filter(f=>f.endsWith('.xlsx'))){
  const file=path.resolve(directory,name);
  const browser=JSON.parse(JSON.stringify(parseExcelClientSide(fs.readFileSync(file))));
  const processResult=spawnSync('python',['-B','-c',python,file,backend],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}});
  if(processResult.status!==0)throw Error(processResult.stderr);
  assert.deepEqual(browser,JSON.parse(processResult.stdout),`Browser/backend mismatch: ${name}`);
  console.log(JSON.stringify({file:name,rows:browser.items.length,candidates:browser.summary.candidate_items,
    review:browser.items.filter(it=>it.match_status==='review').length,
    workbookWarnings:browser.warnings.length,parity:'PASS'}));
}
