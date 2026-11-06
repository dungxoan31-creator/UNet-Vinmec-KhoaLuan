from pathlib import Path
from PIL import Image, ImageDraw
out=Path(__file__).parent
files=[p for p in out.glob('*.png') if not p.name.startswith(('sheet-','print-page','actual-print','synthetic','cua-'))]
for start in range(0,len(files),6):
    sheet=Image.new('RGB',(1500,1320),'#dddddd');draw=ImageDraw.Draw(sheet)
    for j,p in enumerate(files[start:start+6]):
        im=Image.open(p).convert('RGB');im.thumbnail((740,400));x=(j%2)*750;y=(j//2)*440
        draw.text((x+8,y+5),p.name,fill='black');sheet.paste(im,(x,y+25))
    sheet.save(out/f'sheet-{start//6+1}.jpg')
print('sheets',(len(files)+5)//6)
