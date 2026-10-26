// Dependency-free JavaScript initialization check: node tests/check_web_init.js
const fs=require('fs'), vm=require('vm'), path=require('path'), assert=require('assert');
const html=fs.readFileSync(path.join(__dirname,'../src/campuscompass/web.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();
function element(){return {value:'',textContent:'',children:[],classList:{remove(){}},append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items}}}
const document={getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},querySelectorAll(){return []},createElement:element};
const policy={id:'P05',title:'Grade appeal',department:'Academic Affairs',version:'1.0',effective_date:'2026-09-01',text:'Appeal within ten working days.'};
const fetch=async url=>({ok:true,json:async()=>url==='/api/policies'?[policy]:{status:'abstained',answer:'No verifiable excerpt.',answer_method:'local flan with exact-source gate',citations:[],retrieved:[{id:'P05',title:'Grade appeal',score:1}],confidence:.5,latency_ms:12,mode:'bm25'}});
vm.runInNewContext(script,{document,fetch,console});
assert.equal(typeof elements.get('form').onsubmit,'function');
assert.equal(typeof elements.get('backend').onchange,'function');
console.log('Web initialization passed: submit and engine-change handlers attached.');
setImmediate(async()=>{
  try{
    await elements.get('form').onsubmit({preventDefault(){}});
    const candidate=elements.get('sources').children[0];
    assert(candidate,'Abstained response must expose candidate evidence.');
    assert(candidate.children[0].textContent.includes('Retrieved candidate — not a validated answer'));
    assert(candidate.children[1].textContent.includes('Academic Affairs'));
    assert.equal(candidate.children[2].children[1].textContent,policy.text);
    assert(!html.includes('fonts.googleapis.com'));
    console.log('Abstention candidates retain explicit warning, metadata, and original text. No remote font import.');
  }catch(error){console.error(error);process.exitCode=1}
});
