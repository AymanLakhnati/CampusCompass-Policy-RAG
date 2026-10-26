"""Plot measured retrieval results and the implemented pipeline for the report."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/figures';OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
modes={}
for group in ['lexical','neural']:
    modes.update(json.loads((ROOT/f'results/{group}/metrics.json').read_text(encoding='utf-8'))['modes'])
keys=['bm25','tfidf','lexical_hybrid','dense','hybrid']
labels=['BM25','TF-IDF','Lexical fusion','MiniLM dense','BM25 + MiniLM']
fig,ax=plt.subplots(figsize=(9,4.25));fig.patch.set_facecolor('#ffffff')
for i,k in enumerate(keys):
    ax.barh(i-.17,modes[k]['recall_at_3']*100,height=.28,color='#087F78',label='Relevant policies retrieved at 3' if i==0 else '')
    ax.barh(i+.17,modes[k]['answerability_accuracy']*100,height=.28,color='#B4C1BD',label='Answerability decision accuracy' if i==0 else '')
    ax.text(modes[k]['recall_at_3']*100+1,i-.17,f"{modes[k]['recall_at_3']*100:.1f}%",va='center',fontsize=10,color='#173E52')
ax.set_yticks(range(5),labels);ax.invert_yaxis();ax.set_xlim(0,112);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Percent')
ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
ax.legend(loc='upper center',bbox_to_anchor=(.5,-.2),ncol=1,frameon=False,fontsize=10)
fig.tight_layout();fig.savefig(OUT/'retrieval_results.png',dpi=220,bbox_inches='tight');plt.close(fig)

fig,ax=plt.subplots(figsize=(10,3.6));ax.set_xlim(0,10);ax.set_ylim(0,3.6);ax.axis('off')
positions=[(.15,2.1,'1  Prepare request','Validate length and format\nRedact common identifiers'),(3.5,2.1,'2  Retrieve evidence','BM25 or MiniLM\nOptional rank fusion'),(6.85,2.1,'3  Apply evidence gate','Overlap threshold and\nlimited attack patterns'),(.15,.25,'4  Build response','Verbatim extraction or\nFLAN or Qwen generation'),(3.5,.25,'5  Verify model phrase','Accept exact source text\nor abstain'),(6.85,.25,'6  Expose evidence','Answer status and citations\nOriginal policy inspection')]
for x,y,title,sub in positions:
    box=FancyBboxPatch((x,y),2.95,1.15,boxstyle='round,pad=0.08,rounding_size=0.08',facecolor='#F2F6F2',edgecolor='#C9D7D3')
    ax.add_patch(box);ax.text(x+.15,y+.84,title,color='#173E52',fontsize=11,weight='bold');ax.text(x+.15,y+.31,sub,color='#51696B',fontsize=10,linespacing=1.4)
for a,b in [((3.13,2.68),(3.40,2.68)),((6.48,2.68),(6.75,2.68)),((3.13,.83),(3.40,.83)),((6.48,.83),(6.75,.83))]:
    ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':'#087F78','lw':1.7})
ax.text(5,1.6,'Evidence gate passes to response construction; failed gates return an abstention',ha='center',color='#51696B',fontsize=9)
fig.tight_layout();fig.savefig(OUT/'architecture.png',dpi=220,bbox_inches='tight');plt.close(fig)
print(OUT)
