/* Browser mechanics fixture test; never claims model/clinical/offline validation.
   PLAYWRIGHT_MODULE may point to an existing Playwright installation. No installs. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..'), out=path.resolve(root,process.env.UI_OUTPUT || '.runtime/history-destination-ui');fs.mkdirSync(out,{recursive:true});
 const cases=JSON.parse(fs.readFileSync(path.join(root,'evaluation/dev002-v06/cases.json')));
 const units=JSON.parse(fs.readFileSync(path.join(root,'evaluation/dev002-v06/source-map.json'))).units;
 const item=cases[0], fields=Object.fromEntries(Object.entries(item.expected_assignments).map(([id,ids])=>{
  const evidence=units.filter(u=>ids.includes(u.id));return [id,{status:evidence.length?'extracted':'not_found',text:evidence.map(e=>e.text).join('\n'),evidence}];
 }));
 const url=process.env.REFERRAL_URL||'http://127.0.0.1:8001';assert.equal(new URL(url).hostname,'127.0.0.1');
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
 assert.equal(await page.locator('#schema-version').textContent(),'experimental-0.8');
 assert.equal(await page.locator('.field-group').count(),2);
 assert.equal(await page.locator('#field-birth_date').inputValue(),'');
 assert.equal(await page.locator('#field-current_fio2').inputValue(),'');
 await page.locator('#example').click();await page.waitForFunction(note=>document.getElementById('note').value===note,item.source_note);assert.equal(await page.locator('#note').inputValue(),item.source_note);
 assert.equal(await page.locator('#field-signature').inputValue(),'');assert.equal(await page.locator('#field-referral_type').inputValue(),'');
 await page.locator('#extract').click();await page.locator('#status').filter({hasText:'Ялгалт дууслаа'}).waitFor();
 assert.equal(await page.locator('#field-chronic_history').inputValue(),'');
 assert.equal(await page.locator('#field-medical_history').inputValue(),'');
 assert((await page.locator('#field-past_history_source').inputValue()).length>0);
 await page.locator('#field-medical_history').fill('Зохиомол одоогийн түүх');
 await page.locator('#field-chronic_history').fill('Зохиомол архаг түүх');
 await page.locator('#extract').click();await page.locator('#status').filter({hasText:'Ялгалт дууслаа'}).waitFor();
 assert.equal(await page.locator('#field-medical_history').inputValue(),'Зохиомол одоогийн түүх');
 assert.equal(await page.locator('#field-chronic_history').inputValue(),'Зохиомол архаг түүх');
 await page.locator('#field-patient').fill('DEV-002');
 await page.locator('#reviewed').check();await page.locator('#acknowledged').check();await page.locator('#approve').click();
 assert(await page.locator('#print').isEnabled());
 const printed=await page.locator('#print-view').textContent();
 assert(printed.includes('Зохиомол одоогийн түүх')&&printed.includes('Зохиомол архаг түүх'));
 assert(!printed.includes('Өмнөх түүх — ангилаагүй эхийн санал'));
 assert(printed.includes('энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй'));
 await page.locator('#note').fill(item.source_note+'\nЗохиомол өөрчлөлт.');
 assert.equal(await page.locator('#field-medical_history').inputValue(),'Зохиомол одоогийн түүх');
 assert(await page.locator('#approve').isDisabled());assert.equal(await page.locator('#print-view').textContent(),'');
 await page.locator('#example').click();await page.waitForFunction(note=>document.getElementById('note').value===note,item.source_note);assert.equal(await page.locator('#field-medical_history').inputValue(),'');assert.equal(await page.locator('#field-chronic_history').inputValue(),'');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'history-check.json'),JSON.stringify({status:'passed',isolated_url:url,form:'experimental-0.8',legacy_proposal_separate:true,manual_histories_preserved:true,print_attribution:true,source_reconciliation:true,example_reset:true,model_inference:false},null,2)+'\n');
 console.log('History destination browser checks passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
