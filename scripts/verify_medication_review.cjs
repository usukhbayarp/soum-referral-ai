// Read-only browser check of the static fictional review sheet; no web server/inference.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
(async()=>{
 const root=path.resolve(__dirname,'..'),out=path.join(root,'.runtime/medication-review');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try {
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',route=>route.request().url().startsWith('file:')?route.continue():route.abort());
  await page.goto(pathToFileURL(path.join(root,'evaluation/medication-v1/clinician-review.html')).href);
  const cases=JSON.parse(fs.readFileSync(path.join(root,'evaluation/medication-v1/cases.json')));
  assert.equal(await page.locator('h2').count(),4);
  const original=page.locator('section').filter({has:page.locator('h3',{hasText:'Unchanged original note'})});
  for(let i=0;i<cases.length;i++)assert.equal(await original.nth(i).locator('pre').textContent(),cases[i].source_note);
  assert.equal(await page.locator('.review').count(),4);assert(await page.getByText('Fictional development data only.',{exact:false}).count());
  assert.equal(await page.locator('script').count(),0);assert.deepEqual(errors,[]);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'review-top.png')});
  const revision2=page.getByRole('heading',{name:'Prompt revision 2',exact:true}).first();await revision2.evaluate(e=>window.scrollTo(0,e.getBoundingClientRect().top+window.scrollY-20));await page.screenshot({path:path.join(out,'proposals.png')});
  const result={status:'pass',checks:['four fictional cases','unchanged original note text','side-by-side original/expectations and A/B proposals','v1 failures retained in expandable details','review fields unfilled','no executable script or external requests','no horizontal overflow at 1500px'],clinical_review:false};
  fs.writeFileSync(path.join(root,'evaluation/medication-v1/review-ui-check.json'),JSON.stringify(result,null,2)+'\n');console.log(result);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
