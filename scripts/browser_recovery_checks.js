// Existing Playwright tool; constructed errors and accelerated client timer only.
async (page) => {
  const checks=[];
  const check=(name,ok)=>{if(!ok)throw new Error(name);checks.push(name);};
  await page.addInitScript(()=>{
    const original=window.setTimeout;
    window.setTimeout=(callback,ms,...args)=>original(callback,ms===30000?100:ms,...args);
  });
  await page.goto('http://127.0.0.1:8766');
  await page.evaluate(()=>sessionStorage.clear());await page.reload();
  await page.locator('#file').setInputFiles({name:'timeout.txt',mimeType:'text/plain',buffer:Buffer.from('SLOW_UI_FIXTURE timeout recovery')});
  await page.route('**/api/v1/jobs/*',async route=>{
    await new Promise(resolve=>setTimeout(resolve,500));
    try{await route.continue();}catch{/* Aborted request is expected. */}
  });
  await page.locator('#analyze').click();await page.locator('#retry').waitFor({state:'visible'});
  check('timeout explains no cancellation', (await page.locator('#status').innerText()).includes('does not cancel'));
  await page.unroute('**/api/v1/jobs/*');await page.locator('#retry').click();
  await page.locator('#results').waitFor({state:'visible'});
  check('timeout recovers same job', await page.locator('#results').isVisible());
  await page.locator('#file').setInputFiles({name:'dismiss.txt',mimeType:'text/plain',buffer:Buffer.from('SLOW_UI_FIXTURE persistent status error')});
  await page.route('**/api/v1/jobs/*',route=>route.fulfill({status:500,contentType:'application/json',body:'{"error":{"message":"Constructed status failure"}}'}));
  await page.locator('#analyze').click();await page.locator('#forget').waitFor({state:'visible'});
  await page.locator('#forget').click();
  check('dismiss releases file input and clears tracking',await page.locator('#file').isEnabled() && await page.evaluate(()=>sessionStorage.getItem('litmus-last-job')===null));
  check('dismiss explains work continues',(await page.locator('#status').innerText()).includes('not cancelled'));
  await page.unroute('**/api/v1/jobs/*');
  // A separate production server verifies actual native C2PA through the browser.
  await page.goto('http://127.0.0.1:8768');await page.evaluate(()=>sessionStorage.clear());await page.reload();
  await page.locator('#file').setInputFiles('C:/Users/Ryano/Projects/litmus/tests/fixtures/c2pa/active_ai_declared.jpg');
  await page.locator('#c2pa').check();await page.locator('#analyze').click();
  await page.locator('#results').waitFor({state:'visible',timeout:15000});
  check('native C2PA explanation visible',(await page.locator('#report-content').innerText()).includes('signer is not trusted'));
  check('image quality not applicable',(await page.locator('.quality').innerText()).includes('Not applicable'));
  return {checks,client_timer:'30-second AbortController timer accelerated to 100ms by browser harness; no native cancellation',native_fixture:'constructed active_ai_declared.jpg; production trust policy'};
}
