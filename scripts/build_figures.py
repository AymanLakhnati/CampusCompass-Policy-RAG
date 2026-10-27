"""Create print-ready monochrome figures with measured experiment data."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/figures';OUT.mkdir(parents=True,exist_ok=True)
FONT=Path('C:/Windows/Fonts/times.ttf');BOLD=Path('C:/Windows/Fonts/timesbd.ttf')
def font(size,bold=False):return ImageFont.truetype(str(BOLD if bold else FONT),size)
def text(d,pos,s,size=36,bold=False,anchor=None):d.text(pos,s,font=font(size,bold),fill='black',anchor=anchor)
def architecture():
    im=Image.new('RGB',(1800,650),'white');d=ImageDraw.Draw(im)
    items=[('1  Prepare request','Validate and redact inputs','Screen scope and attacks'),('2  Retrieve policies','Lexical or semantic retrieval','Rank policies by relevance'),('3  Assess support','Apply the evidence threshold','Abstain without support'),('4  Construct response','Extract or generate response','Keep full policy evidence'),('5  Validate response','Check source attribution','Constrain model wording'),('6  Return evidence','Show status and citations','Expose original evidence')]
    for i,(title,a,b) in enumerate(items):
        x=25+(i%3)*595;y=20+(i//3)*345
        d.rectangle((x,y,x+550,y+230),outline='black',width=3)
        text(d,(x+24,y+25),title,38,True);text(d,(x+24,y+95),a,36);text(d,(x+24,y+145),b,36)
        if i%3<2:
            d.line((x+553,y+115,x+587,y+115),fill='black',width=4);d.polygon([(x+587,y+115),(x+574,y+106),(x+574,y+124)],fill='black')
    text(d,(900,292),'Unsupported requests return abstention before response construction',36,anchor='mm')
    im.save(OUT/'architecture.png',dpi=(300,300))
def retrieval():
    modes={}
    for group in ['lexical','neural']:modes.update(json.loads((ROOT/f'results/{group}/metrics.json').read_text())['modes'])
    keys=['bm25','tfidf','lexical_hybrid','dense','hybrid'];labels=['BM25','TF IDF','Lexical fusion','MiniLM dense','BM25 plus MiniLM']
    im=Image.new('RGB',(1800,960),'white');d=ImageDraw.Draw(im);x0=400;x1=1630;y0=80
    for tick in [0,25,50,75,100]:
        x=x0+(x1-x0)*tick/100;d.line((x,y0,x,y0+650),fill='#cccccc',width=2);text(d,(x,y0+680),str(tick),32,anchor='mm')
    for i,(key,label) in enumerate(zip(keys,labels)):
        y=y0+i*130;text(d,(x0-22,y+38),label,34,anchor='rm')
        vals=[modes[key]['recall_at_3']*100,modes[key]['answerability_accuracy']*100]
        for j,v in enumerate(vals):
            top=y+j*48;end=x0+(x1-x0)*v/100
            d.rectangle((x0,top,end,top+35),fill='#444444' if j==0 else 'white',outline='black',width=2)
            if j:
                for xx in range(x0,int(end),14):d.line((xx,top+34,min(xx+30,end),max(top,top+34-(end-xx))),fill='black',width=1)
            text(d,(end+12,top+17),f'{v:.1f}',30,anchor='lm')
    text(d,(1000,810),'Percent',34,anchor='mm')
    d.rectangle((300,865,355,900),fill='#444444',outline='black');text(d,(375,882),'V1 macro Recall at 3',34,anchor='lm')
    d.rectangle((910,865,965,900),fill='white',outline='black');d.line((915,898,945,867),fill='black',width=2);text(d,(985,882),'V1 answerability accuracy',34,anchor='lm')
    im.save(OUT/'retrieval_results.png',dpi=(300,300))
if __name__=='__main__':architecture();retrieval();print(OUT)
