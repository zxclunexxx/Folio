import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from test_ui import inline_html,ROOT
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
  await page.set_content(inline_html())
  async def shot(name,full=False):
   await page.wait_for_timeout(350)
   await page.screenshot(path=str(ROOT/'docs/screenshots'/name),full_page=full,animations='disabled')
  await shot('01-overview.png');await shot('01-overview-full.png',True)
  for tab,name in [('projects','02-projects.png'),('tasks','03-tasks.png'),('income','04-income.png')]:
   await page.locator(f'.nav-item[data-tab={tab}]').click();await shot(name)
  await page.locator('[data-action=settings]').click();await page.locator('[data-action=theme][data-theme=dark]').click();await page.locator('[data-action=close]').click();await shot('05-dark.png')
  await page.locator('[data-action=settings]').click();await page.locator('[data-action=theme][data-theme=light]').click();await page.locator('[data-action=close]').click();await page.wait_for_timeout(100)
  await page.locator('.nav-item[data-tab=projects]').click();await page.locator('.project-card').first.click();await shot('06-project-detail.png')
  await page.locator('[data-action=edit-project]').click();await shot('07-project-form.png')
  await b.close()
asyncio.run(main())
