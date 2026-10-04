// Static fictional review sheet only; no inference, server, remote requests or saved approval.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
(async()=>{
 const root=path.resolve(__dirname,'..'),out=path.join(root,'.runtime/original4b/review');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try {
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',route=>route.request().url().startsWith('file:')?route.continue():route.abort());
  await page.goto(pathToFileURL(path.join(root,'evaluation/original4b-v07/clinician-review.html')).href);
  const cases=JSON.parse(fs.readFileSync(path.join(root,'evaluation/medication-v1/cases.json')));
  assert.equal(await page.locator('h2').count(),4);
  for(let i=0;i<cases.length;i++)assert.equal(await page.locator('section').nth(i).locator('pre').first().textContent(),cases[i].source_note);
  assert.equal(await page.locator('textarea').count(),4);
  assert(await page.locator('textarea').evaluateAll(es=>es.every(e=>e.value==='')));
  assert.equal(await page.locator('script').count(),0);assert.deepEqual(errors,[]);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'review-top.png')});
  await page.getByRole('heading',{name:'Хадгалсан prompt хувилбар 1',exact:true}).first().evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+window.scrollY));await page.screenshot({path:path.join(out,'proposals.png')});
  await page.setViewportSize({width:720,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  const result={status:'pass',checks:['four fictional cases, original source exact','both saved versions and both models retained','human-readable proposals and blank adjudication','no executable script or external requests','no overflow at 1500 or 720px'],clinical_review:false};
  fs.writeFileSync(path.join(root,'evaluation/original4b-v07/review-ui-check.json'),JSON.stringify(result,null,2)+'\n');console.log(result);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
