"""UI tests in isolated Chromium document. Browser policy disallows URL navigation,
so document assets are inlined and localStorage uses an in-memory Storage adapter.
Android runtime/device and HTTP service-worker installation are not covered.
"""
import asyncio, json, re
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parent.parent

def inline_html(storage=None):
 html=(ROOT/'web/index.html').read_text()
 html=re.sub(r'<link[^>]+>', '',html)
 icons=(ROOT/'web/assets/icons.js').read_text();js=(ROOT/'web/app.js').read_text();css=(ROOT/'web/style.css').read_text()
 storage=storage or {}
 shim=f'''<script>window.__storage={json.dumps(storage)};Object.defineProperty(window,'localStorage',{{value:{{getItem(k){{return Object.prototype.hasOwnProperty.call(window.__storage,k)?window.__storage[k]:null;}},setItem(k,v){{window.__storage[k]=String(v);}},removeItem(k){{delete window.__storage[k];}},clear(){{window.__storage={{}};}}}}}});</script>'''
 html=html.replace('</head>',f'<style>{css}</style>{shim}</head>')
 html=html.replace('<script src="assets/icons.js"></script>',f'<script>{icons}</script>').replace('<script src="app.js"></script>',f'<script>{js}</script>')
 return html

async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=await b.new_page(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.set_content(inline_html());await page.wait_for_timeout(350)
  print('initial',errors,await page.evaluate('({projects:Folio.snapshot().projects.length,tasks:Folio.snapshot().tasks.length,overflow:document.documentElement.scrollWidth>innerWidth})'))
  await page.screenshot(path=str(ROOT/'docs/screenshots/01-overview.png'),full_page=False)
  await page.screenshot(path=str(ROOT/'docs/screenshots/01-overview-full.png'),full_page=True)
  print('title',await page.title())
  await b.close()

if __name__=='__main__':asyncio.run(main())
