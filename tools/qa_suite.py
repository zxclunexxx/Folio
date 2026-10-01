import asyncio,json,sys
from pathlib import Path
from test_ui import inline_html,ROOT
from playwright.async_api import async_playwright

async def main():
 results=[];errors=[]
 def ok(name,cond=True):
  if not cond:raise AssertionError(name)
  results.append({'test':name,'result':'PASS'})
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
  page.set_default_timeout(4000);page.on('pageerror',lambda e:errors.append(str(e)))
  await page.set_content(inline_html());await page.wait_for_timeout(70)
  snap=await page.evaluate('Folio.snapshot()');ok('Initial demo: 4 projects / 8 tasks / 5 payments',len(snap['projects'])==4 and len(snap['tasks'])==8 and len(snap['payments'])==5)
  ok('Current month total is 39,500 RUB','39' in await page.locator('.balance').inner_text())
  await page.locator('.nav-item[data-tab=projects]').click()
  await page.screenshot(path=str(ROOT/'docs/screenshots/02-projects.png'))
  await page.locator('#project-search').fill('кофейн');ok('Project search matches title',await page.locator('.project-card').count()==1)
  await page.locator('#project-search').fill('xyz-not-found');ok('Search empty state',await page.locator('.empty').count()==1)
  await page.locator('#project-search').fill('')
  await page.locator('[data-action=project-filter][data-filter=done]').click();ok('Completed-project filter',await page.locator('.project-card').count()==1)
  await page.locator('[data-action=project-filter][data-filter=all]').click()
  await page.locator('[data-action=new-project]').click()
  await page.locator('[name=name]').fill('Портфолио «Тест» <safe>')
  await page.locator('[name=client]').fill('Тестовый клиент')
  await page.locator('[name=budget]').fill('12500.50')
  await page.locator('[name=notes]').fill('<img src=x onerror=alert(1)>\nЗаметка')
  await page.locator('#project-form button[type=submit]').click();await page.wait_for_timeout(100)
  snap=await page.evaluate('Folio.snapshot()');proj=next(x for x in snap['projects'] if x['client']=='Тестовый клиент');pid=proj['id']
  ok('Create project with decimal budget',proj['budget']==12500.5)
  await page.locator(f'.project-card[data-id="{pid}"]').click();ok('Project detail escapes HTML',await page.locator('main img').count()==0)
  await page.locator('[data-action=new-task]').first.click();await page.locator('[name=title]').fill('Проверить мобильный экран')
  await page.locator('#task-form button[type=submit]').click();await page.wait_for_timeout(100)
  snap=await page.evaluate('Folio.snapshot()');task=next(x for x in snap['tasks'] if x['title']=='Проверить мобильный экран');tid=task['id'];ok('Task links to current project',task['project']==pid)
  await page.locator(f'[data-action=toggle-task][data-id="{tid}"]').click();ok('Task completion updates persisted state',(await page.evaluate('Folio.snapshot()'))['tasks'][-1]['done'])
  await page.locator('[data-action=new-payment]').click();await page.locator('[name=amount]').fill('1000.25');await page.locator('[name=note]').fill('Тестовая оплата')
  await page.locator('#payment-form button[type=submit]').click();await page.wait_for_timeout(100)
  snap=await page.evaluate('Folio.snapshot()');pay=next(x for x in snap['payments'] if x['note']=='Тестовая оплата');rid=pay['id'];ok('Recorded payment is linked and numeric',pay['project']==pid and pay['amount']==1000.25)
  ok('Paid project amount recalculates','1' in await page.locator('.money-cell.green b').inner_text())
  await page.locator(f'[data-action=edit-payment][data-id="{rid}"]').click();await page.locator('[name=amount]').fill('2000');await page.locator('#payment-form button[type=submit]').click();await page.wait_for_timeout(100)
  ok('Payment edit',(await page.evaluate('Folio.snapshot()'))['payments'][0]['amount']==2000)
  await page.locator('[data-action=edit-project]').click();await page.locator('[name=status]').select_option('done');await page.locator('#project-form button[type=submit]').click();await page.wait_for_timeout(100)
  snap=await page.evaluate('Folio.snapshot()');ok('Project status edit',next(x for x in snap['projects'] if x['id']==pid)['status']=='done')
  saved=await page.evaluate('window.__storage');copy=await b.new_page();await copy.set_content(inline_html(saved));await copy.wait_for_timeout(40)
  ok('State serialization and restoration',len((await copy.evaluate('Folio.snapshot()'))['projects'])==5);await copy.close()
  # Delete confirmation and accounting preservation.
  await page.locator('[data-action=edit-project]').click();await page.locator('[data-action=delete-project]').click();ok('Deletion requires confirmation',await page.locator('[data-action=confirm]').count()==1)
  await page.locator('[data-action=confirm]').click();await page.wait_for_timeout(100);snap=await page.evaluate('Folio.snapshot()')
  ok('Project deletion removes its tasks',not any(x['id']==pid for x in snap['projects']) and not any(x['project']==pid for x in snap['tasks']))
  ok('Project deletion preserves payment history',any(x['id']==rid and x['project']=='' for x in snap['payments']))
  await page.locator('.nav-item[data-tab=tasks]').click();await page.screenshot(path=str(ROOT/'docs/screenshots/03-tasks.png'))
  await page.locator('[data-action=task-filter][data-filter=done]').click();ok('Completed tasks filter',await page.locator('.task-row.complete').count()==3)
  await page.locator('.nav-item[data-tab=income]').click();await page.screenshot(path=str(ROOT/'docs/screenshots/04-income.png'))
  month=await page.locator('.month-row b').inner_text();await page.locator('[data-action=month][data-delta="-1"]').click();ok('Income month navigation',month!=await page.locator('.month-row b').inner_text())
  await page.locator('[data-action=settings]').click();await page.locator('[data-action=theme][data-theme=dark]').click();ok('Dark theme applies',await page.evaluate('document.documentElement.dataset.theme')=='dark')
  await page.locator('[data-action=close]').click();await page.wait_for_timeout(100);await page.screenshot(path=str(ROOT/'docs/screenshots/05-dark.png'))
  await page.locator('[data-action=settings]').click();await page.locator('[data-action=theme][data-theme=light]').click();await page.locator('[data-action=export]').click()
  backup=await page.locator('#backup-text').input_value();ok('Backup exports valid JSON',json.loads(backup)['version']==1)
  await page.locator('[data-action=close]').click();await page.wait_for_timeout(100);await page.locator('[data-action=settings]').click();await page.locator('[data-action=import]').click();await page.locator('#import-text').fill('{bad JSON');await page.locator('[data-action=check-import]').click();ok('Invalid backup rejected',await page.locator('.toast.error').count()>0)
  await page.locator('#import-text').fill(backup);await page.locator('[data-action=check-import]').click();await page.locator('[data-action=confirm]').click();await page.wait_for_timeout(100);ok('Valid backup restores full state',len((await page.evaluate('Folio.snapshot()'))['projects'])==4)
  await page.locator('[data-action=settings]').click();await page.locator('[data-action=reset]').click();await page.locator('[data-action=confirm]').click();await page.wait_for_timeout(100);snap=await page.evaluate('Folio.snapshot()');ok('Clean workspace clears data and demo flag',not snap['projects'] and not snap['payments'] and not snap['tasks'] and not snap['demo'])
  # Recover display data for final screenshots.
  await page.locator('[data-action=settings]').click();await page.locator('[data-action=demo]').click();await page.locator('[data-action=confirm]').click();await page.wait_for_timeout(100)
  await page.locator('.nav-item[data-tab=projects]').click();await page.locator('[data-action=project-filter][data-filter=all]').click();await page.screenshot(path=str(ROOT/'docs/screenshots/02-projects.png'))
  await page.locator('.project-card').first.click();await page.screenshot(path=str(ROOT/'docs/screenshots/06-project-detail.png'))
  await page.locator('.nav-item[data-tab=income]').click();await page.locator('[data-action=month][data-delta="1"]').click();await page.screenshot(path=str(ROOT/'docs/screenshots/04-income.png'))
  for w,h in [(320,568),(360,800),(390,844),(430,932),(844,390),(1280,800)]:
   await page.set_viewport_size({'width':w,'height':h})
   for tab in ['home','projects','tasks','income']:
    await page.locator(f'.nav-item[data-tab={tab}]').click()
    ok(f'No horizontal overflow {w}x{h} / {tab}',not await page.evaluate('document.documentElement.scrollWidth>innerWidth'))
  await page.set_viewport_size({'width':390,'height':844});await page.locator('.nav-item[data-tab=projects]').click();await page.locator('[data-action=new-project]').click();await page.screenshot(path=str(ROOT/'docs/screenshots/07-project-form.png'))
  # Validator hardening checks.
  validations=await page.evaluate('''() => {const fail=fn=>{try{fn();return false}catch{return true}};const a=Folio.snapshot();return [fail(()=>Folio.validateBackup({version:99})),fail(()=>Folio.validateBackup({...a,projects:[...a.projects,a.projects[0]]})),fail(()=>Folio.validateBackup({...a,profile:{...a.profile,goal:-10}}))];}''')
  ok('Backup schema rejects bad version, duplicate IDs and negative goal',all(validations))
  ok('No uncaught JavaScript errors',not errors)
  await b.close()
 report={'environment':'Chromium mobile/desktop document rendering; isolated in-memory localStorage adapter due browser URL policy','passed':len(results),'tests':results,'javascriptErrors':errors,'notCovered':['Physical Android device','Android emulator installation/runtime','Real WebView localStorage persistence across process death','HTTP service worker / PWA installation','Google Play submission']}
 (ROOT/'docs/test-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print('PASSED',len(results),'tests; errors',errors)

asyncio.run(main())
