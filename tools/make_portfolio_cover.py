from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
root=Path(__file__).resolve().parent.parent;ss=root/'docs/screenshots'
im=Image.new('RGB',(1600,1110),'#edeee6');d=ImageDraw.Draw(im)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
d.text((68,38),'folio.',font=ImageFont.truetype(bold,85),fill='#234c3e')
d.text((72,148),'Проекты. Задачи. Спокойствие.',font=ImageFont.truetype(font,29),fill='#6f7a68')
d.text((1218,66),'ANDROID / v1.0',font=ImageFont.truetype(bold,20),fill='#637457')
for j,(name,label) in enumerate([('01-overview.png','ОБЗОР'),('02-projects.png','ПРОЕКТЫ'),('03-tasks.png','ЗАДАЧИ'),('04-income.png','ДОХОДЫ')]):
 x=70+j*375;y=240;shot=Image.open(ss/name).convert('RGB').resize((335,725),Image.Resampling.LANCZOS)
 mask=Image.new('L',shot.size);md=ImageDraw.Draw(mask);md.rounded_rectangle((0,0,334,724),radius=22,fill=255)
 d.rounded_rectangle((x-2,y-2,x+337,y+727),radius=24,fill='#ccd4c4');im.paste(shot,(x,y),mask)
 d.text((x,y-37),label,font=ImageFont.truetype(bold,16),fill='#637457')
d.text((70,1020),'JAVA + ANDROID WEBVIEW  /  JAVASCRIPT  /  LOCAL-FIRST',font=ImageFont.truetype(font,20),fill='#6f7a68')
d.text((70,1058),'Скриншоты интерфейса · демонстрационные данные',font=ImageFont.truetype(font,17),fill='#89927f')
im.save(ss/'portfolio-cover.png',optimize=True)
