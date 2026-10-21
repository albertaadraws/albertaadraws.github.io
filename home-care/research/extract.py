import re,sys,os,json
from bs4 import BeautifulSoup
KW={'personal care':r'personal care|bathing','companionship':r'companion','respite':r'respite','nursing':r'\bnurs(e|ing)\b|\bLPN\b|\bRN\b','dementia':r'dementia|alzheimer|memory','palliative':r'palliative|end[- ]of[- ]life|hospice','overnight/24h':r'overnight|24[- /]?(hour|7)|live-in','housekeeping':r'housekeeping|meal prep','disability':r'disabilit',
'CDHCI':r'client[- ]directed|CDHCI|blue cross|self[- ]managed|AHS[- ]fund|government[- ]fund','languages':r'punjabi|urdu|tagalog|filipino|hindi|mandarin|cantonese|arabic|french|spanish|ukrainian|vietnamese|korean|somali|amharic|tigrinya|gujarati|farsi|persian|polish|russian|languages?',
'areas':r'st\.? albert|sherwood park|spruce grove|stony plain|leduc|beaumont|fort saskatchewan|devon|morinville|parkland|strathcona|sturgeon|nisku|ardrossan|gibbons'}
for f in sys.argv[1:]:
    t=BeautifulSoup(open(f,errors='ignore').read(),'html.parser')
    for s in t(['script','style','noscript']): s.decompose()
    txt=re.sub(r'\s+',' ',t.get_text(' '))
    out={'file':os.path.basename(f),'title':(t.title.string.strip() if t.title and t.title.string else ''),'len':len(txt)}
    out['phones']=sorted(set(re.findall(r'\(?\b[2-8]\d{2}\)?[-. ]\d{3}[-. ]\d{4}\b',txt)))[:6]
    for k,p in KW.items():
        ms=[txt[max(0,m.start()-70):m.end()+70] for m in re.finditer(p,txt,re.I)][:3]
        if ms: out[k]=ms
    open(f.replace('.html','.txt'),'w').write(txt)
    print(json.dumps(out,ensure_ascii=False)); print()
