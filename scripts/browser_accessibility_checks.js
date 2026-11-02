// Run in the existing Playwright tool with scripts/smoke_local_ui.py on 8766.
async (page) => {
  const checks=[];
  const check=(name,ok)=>{if(!ok)throw Error(name);checks.push(name);};
  await page.goto('http://127.0.0.1:8766');
  await page.evaluate(()=>sessionStorage.clear());await page.reload();
  await page.keyboard.press('Tab');
  check('skip link is first keyboard target',await page.getByRole('link',{name:'Skip to analysis'}).evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Enter');
  check('skip link targets workspace',await page.evaluate(()=>document.activeElement.id==='workspace'));
  await page.locator('#file').setInputFiles({name:'constructed-accessibility.txt',mimeType:'text/plain',buffer:Buffer.from('SLOW_UI_FIXTURE In conclusion, this could be clearer.')});
  await page.getByRole('checkbox',{name:/Content observations/}).check();
  await page.route('**/api/v1/jobs/*',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:{message:'Constructed status failure'}})}));
  await page.locator('#analyze').click();await page.locator('#retry').waitFor({state:'visible'});
  await page.locator('#retry').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>document.getElementById('status').textContent.includes('Constructed status failure'));
  check('failed keyboard retry keeps focus on status',await page.evaluate(()=>document.activeElement.id==='status'));
  check('status remains a polite live region',await page.locator('#status').getAttribute('aria-live')==='polite');
  await page.keyboard.press('Tab');
  check('next keyboard target is retry',await page.evaluate(()=>document.activeElement.id==='retry'));
  await page.keyboard.press('Tab');await page.keyboard.press('Enter');
  check('dismiss returns focus to file selection',await page.evaluate(()=>document.activeElement.id==='file'));
  check('dismiss explicitly does not cancel native work',(await page.locator('#status').innerText()).includes('not cancelled'));
  await page.unroute('**/api/v1/jobs/*');
  // The intentionally slow job is still running after dismissal.
  await page.waitForTimeout(3200);
  await page.locator('#analyze').click();await page.locator('#results').waitFor({state:'visible'});
  check('completed report focuses heading',await page.evaluate(()=>document.activeElement.id==='results-title'));
  const downloaded=page.waitForEvent('download');await page.locator('#download').focus();await page.keyboard.press('Enter');
  const stream=await (await downloaded).createReadStream();let data='';for await(const chunk of stream)data+=chunk;
  check('keyboard export is valid JSON',JSON.parse(data).input.file_name==='constructed-accessibility.txt');
  const evidence={checks,browserVersion:page.context().browser().version(),scope:'Chromium keyboard and accessibility-tree checks, NOT screen-reader speech verification',baselineFailure:'Before fix, keyboard retry moved focus to BODY',snapshot:await page.locator('main').ariaSnapshot()};
  return evidence;
}
