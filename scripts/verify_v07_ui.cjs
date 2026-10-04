/* Browser mechanics fixture test; never claims model/clinical/offline validation.
   PLAYWRIGHT_MODULE may point to an existing Playwright installation. No installs. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..'), out=path.resolve(root,process.env.UI_OUTPUT || '.runtime/v07-ui');fs.mkdirSync(out,{recursive:true});
 const cases=JSON.parse(fs.readFileSync(path.join(root,'evaluation/dev002-v06/cases.json')));
 const units=JSON.parse(fs.readFileSync(path.join(root,'evaluation/dev002-v06/source-map.json'))).units;
 const item=cases[0], fields=Object.fromEntries(Object.entries(item.expected_assignments).map(([id,ids])=>{
  const evidence=units.filter(u=>ids.includes(u.id));return [id,{status:evidence.length?'extracted':'not_found',text:evidence.map(e=>e.text).join('\n'),evidence}];
 }));
 const url=process.env.REFERRAL_URL||'http://127.0.0.1:8000';assert.equal(new URL(url).hostname,'127.0.0.1');
 const browser=await chromium.launch({headless:true, ...(process.env.CHROME_EXECUTABLE ? {executablePath:process.env.CHROME_EXECUTABLE}: {})});
 try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[];
 page.on('pageerror',error=>errors.push(String(error)));page.on('dialog',d=>d.accept());
 await page.route('**/*',async route=>{
  const request=route.request(),u=new URL(request.url());
  if(u.hostname!=='127.0.0.1')return route.abort();
  if(u.pathname==='/api/extract') {
   const input=request.postDataJSON();assert.equal(input.note,item.source_note);
   return route.fulfill({json:{fields,units,request_id:input.request_id,schema_version:item.schema_version,prompt_version:item.prompt_version}});
  }
  return route.continue();
 });
 await page.goto(url);await page.locator('#field-patient').waitFor();
 assert.equal(await page.locator('.form-section').count(),6);
 assert.equal(await page.locator('#schema-version').textContent(),'experimental-0.7');
 assert.equal(await page.locator('.field-group').count(),2);
 assert.equal(await page.locator('#field-birth_date').inputValue(),'');
 assert.equal(await page.locator('#field-current_fio2').inputValue(),'');
 await page.locator('#example').click();await page.waitForFunction(note=>document.getElementById('note').value===note,item.source_note);assert.equal(await page.locator('#note').inputValue(),item.source_note);
 assert.equal(await page.locator('#field-signature').inputValue(),'');assert.equal(await page.locator('#field-referral_type').inputValue(),'');
 await page.locator('#extract').click();await page.locator('#status').filter({hasText:'Ялгалт дууслаа'}).waitFor();
 assert.equal(await page.locator('#field-initial_bp').inputValue(),'');assert.equal(await page.locator('#field-current_bp').inputValue(),'');
 assert((await page.locator('#field-regular_medication').inputValue()).includes('асуугаагүй'));
 assert(!(await page.locator('#field-treatment_source').inputValue()).includes('Амлодипин'));
 await page.locator('#initial_source-evidence button').first().click();assert.equal(await page.locator('#unit-14').getAttribute('class'),'selected');
 await page.locator('#field-patient').fill('DEV-002');
 await page.locator('#field-pending_status').selectOption('Байхгүй гэж эхэд тэмдэглэсэн');
 assert(!(await page.locator('#unresolved').textContent()).includes('Хүлээгдэж буй хариуг хянах хүн — дутуу'));
 await page.locator('#field-allergies').fill('Эмчийн хянасан зохиомол нэмэлт — Ө ө Ү ү.');
 assert((await page.locator('#allergies-original').textContent()).includes('зассан агуулгыг батлахгүй'));
 await page.locator('#reviewed').check();await page.locator('#acknowledged').check();await page.locator('#approve').click();assert.equal(await page.locator('#print').isEnabled(),true);
 assert((await page.locator('#print-view').textContent()).includes('энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй'));
 await page.locator('#field-patient').fill('DEV-002 updated');assert.equal(await page.locator('#print').isDisabled(),true);assert.equal(await page.locator('#print-view').textContent(),'');
 await page.locator('#note').fill(item.source_note+'\nШинэ зохиомол засвар.');assert.equal(await page.locator('#field-patient').inputValue(),'DEV-002 updated');
 await page.locator('#reviewed').check();await page.locator('#acknowledged').check();assert.equal(await page.locator('#approve').isDisabled(),true);
 await page.locator('#example').click();await page.waitForFunction(note=>document.getElementById('note').value===note,item.source_note);assert.equal(await page.locator('#field-patient').inputValue(),'');assert.equal(await page.locator('#field-allergies').inputValue(),'');
 await page.locator('#extract').click();await page.locator('#status').filter({hasText:'Ялгалт дууслаа'}).waitFor();
 await page.locator('#field-patient').fill('DEV-002');
 // Deliberate long-text / repeated-row stress case, not additional clinical facts.
 const long=Array.from({length:35},(_,i)=>`Мөр ${i+1}: Өвчтөний зохиомол тэмдэглэл. Үнэлээгүй гэдгийг хэвийн гэж үзэхгүй; эмч эхтэй тулгана.`).join('\n');
 await page.locator('#field-review_notes').fill(long);
 assert(await page.locator('#field-review_notes').evaluate(e=>e.scrollHeight<=e.clientHeight+2));
 for(let i=1;i<=3;i++) {
  await page.getByRole('button',{name:'Эмчилгээний мөр нэмэх',exact:true}).click();
  await page.getByRole('combobox',{name:`${i} Төрөл`,exact:true}).selectOption('medication');
  await page.getByRole('combobox',{name:`${i} Хийсэн давтамж`,exact:true}).selectOption('single');
  const data={'Эм / ажилбарын нэр':`ХЭВЛЭЛТИЙН-ТУРШИЛТ-${i}`, 'Тун, нэгж':'500 мг','Хэрэглэх зам':'Амаар','Хийсэн / сүүлд өгсөн огноо, цаг':'10:15 — огноог эмч шалгана','Баримтжуулсан үр дүн / урвал':`Туршилтын мөр ${i} төгсгөл Ө ө Ү ү.`};
  for(const [key,value] of Object.entries(data)) await page.getByRole('textbox',{name:`${i} ${key}`,exact:true}).fill(value);
 }
 await page.locator('#reviewed').check();await page.locator('#acknowledged').check();await page.locator('#approve').click();assert(await page.locator('#print').isEnabled());
 await page.screenshot({path:path.join(out,'screen.png')});
 await page.pdf({path:path.join(out,'v07-multipage.pdf'),format:'A4',printBackground:true,preferCSSPageSize:true});
 const allPrint=await page.locator('#print-view').textContent();assert(allPrint.includes('Мөр 35:'));assert(allPrint.includes('Туршилтын мөр 3 төгсгөл'));
 await page.locator('#new-referral').click();assert.equal(await page.locator('#note').inputValue(),'');assert.equal(await page.locator('.treatment-row').count(),0);assert.equal(await page.locator('#print-view').textContent(),'');
 // An asynchronously fetched example must not replace a case started in the meantime.
 await page.route('**/api/example/dev002', async route=> {await new Promise(r=>setTimeout(r,300));await route.fulfill({json:{source_note:item.source_note}});});
 const pendingExample=page.waitForResponse('**/api/example/dev002');
 await page.locator('#example').click();await page.locator('#new-referral').click();await pendingExample;
 await page.waitForTimeout(100);assert.equal(await page.locator('#note').inputValue(),'');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'browser-check.json'),JSON.stringify({status:'pass',inference:'mocked provisional assignments for UI regressions only',checks:['six sections','exact source-only example','blank referral type/signature','manual-only vital subfields','distinct medications','evidence navigation','pending conditional warnings','honest manual attribution','acknowledged missing information approval','approval revoked after edit','source reconciliation blocks approval','example replacement clears case','long textarea expands','three editable treatment rows','multipage PDF generated for separate visual inspection','new-case reset','delayed example fetch isolation'],pdf:'v07-multipage.pdf'},null,2));
 console.log('Browser v0.7 checks passed; PDF awaits visual inspection.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
