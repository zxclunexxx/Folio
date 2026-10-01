from pathlib import Path
import re,base64
root=Path(__file__).resolve().parent.parent
html=(root/'web/index.html').read_text()
html=re.sub(r'<link[^>]+>','',html)
css=(root/'web/style.css').read_text();js=(root/'web/app.js').read_text();icons=(root/'web/assets/icons.js').read_text()
js=js.replace("if('serviceWorker'in navigator&&/^https?:$/.test(location.protocol)){navigator.serviceWorker.register('sw.js').catch(()=>{});}", "// Single-file preview: service worker intentionally omitted.")
icon=base64.b64encode((root/'web/assets/icon-192.png').read_bytes()).decode()
html=html.replace('</head>',f'<link rel="icon" href="data:image/png;base64,{icon}"><style>{css}</style></head>')
html=html.replace('<script src="assets/icons.js"></script>',f'<script>{icons}</script>').replace('<script src="app.js"></script>',f'<script>{js}</script>')
(root/'PREVIEW.html').write_text(html)
print('Created PREVIEW.html; production storage, no test adapters.')
