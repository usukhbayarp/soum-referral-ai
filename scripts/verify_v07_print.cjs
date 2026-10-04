/* Fictional manually completed print mechanics fixture. Never an extraction result. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
(async()=>{
 const root=path.resolve(__dirname,'..'), out=path.join(root,'.runtime/v07-print');fs.mkdirSync(out,{recursive:true});
 const fixture=JSON.parse(fs.readFileSync(path.join(root,'evaluation/recovery-v06/normal-print-fixture.json')));
 const note=fs.readFileSync(path.join(root,'evaluation/dev002-v06/source-note.txt'),'utf8').trimEnd();
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 const results=[];
 try {for(const mode of ['after']) {
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*', async route=>{
   const u=new URL(route.request().url());if(u.hostname!=='127.0.0.1')return route.abort();
   if(u.pathname==='/api/extract')throw Error('Print test must not run inference');
   if(mode==='before' && ['/static/app.js','/static/style.css'].includes(u.pathname)) return route.fulfill({contentType:u.pathname.endsWith('.js')?'text/javascript':'text/css',body:execFileSync('git',['show',`53e9e9543d8e90fb803950fe30ccec70c824f9a6:app${u.pathname}`],{cwd:root,encoding:'utf8'})});
   return route.continue();
  });
  await page.goto(process.env.REFERRAL_URL || 'http://127.0.0.1:8000');await page.locator('#field-patient').waitFor();
  await page.locator('#note').fill(note);
  for(const [id,value] of Object.entries(fixture.values)) {
   const e=page.locator('#field-'+id);
   if(await e.evaluate(e=>e.tagName)==='SELECT') await e.selectOption(value === "Хэрэглээгүй" ? "Өрөөний агаарт" : value);else await e.fill(value);
  }
  const names={name:'Эм / ажилбарын нэр',dose:'Тун, нэгж',frequency:'Давтамж (давтан бол)',route:'Хэрэглэх зам',time:'Хийсэн / сүүлд өгсөн огноо, цаг',response:'Баримтжуулсан үр дүн / урвал'};
  for(const [i,row] of fixture.rows.entries()) {
   await page.getByRole('button',{name:'Эмчилгээний мөр нэмэх',exact:true}).click();
   await page.getByRole('combobox',{name:`${i+1} Төрөл`,exact:true}).selectOption(row.kind);
   await page.getByRole('combobox',{name:`${i+1} Хийсэн давтамж`,exact:true}).selectOption(row.schedule);
   for(const [key,label] of Object.entries(names)) if(row[key])await page.getByRole('textbox',{name:`${i+1} ${label}`,exact:true}).fill(row[key]);
  }
  // Simulated acknowledgement for layout QA, not a clinician signature/review.
  assert.equal(await page.locator('#field-signature').inputValue(),'');
  await page.locator('#reviewed').check();await page.locator('#acknowledged').check();await page.locator('#approve').click();assert(await page.locator('#print').isEnabled());
  const text=await page.locator('#print-view').textContent();
  if(mode==='after') {
   assert(!text.includes('эхийн санал'));assert(!text.includes('Анхны ялгалтын эх — зассан утгын нотолгоо биш:'));
   assert(text.includes('энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй'));
   for(const s of ['Парацетамол','Амлодипин','асуугаагүй','үнэлээгүй','хийгээгүй','6/10','4/10','134/82','128/80','RF','CRP'])assert(text.includes(s),s);
  }
  await page.pdf({path:path.join(out,`normal-${mode}.pdf`),printBackground:true,preferCSSPageSize:true});
  assert.deepEqual(errors,[]);results.push({mode,status:'pass',inference:'none; manual fictional layout fixture',signature:'blank',pdf:`normal-${mode}.pdf`});await page.close();
 }
 fs.writeFileSync(path.join(out,'normal-browser-check.json'),JSON.stringify(results,null,2));console.log(results);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
