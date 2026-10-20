// "Where do I stand" score checker. Runs entirely in the browser; nothing is sent anywhere.
(function(){
const root=document.getElementById('checker');if(!root)return;
const BASE=root.dataset.base||'';
const $=s=>root.querySelector(s);
const fmtDate=iso=>new Date(iso+'T12:00:00').toLocaleDateString('en-CA',{year:'numeric',month:'short',day:'numeric'});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let draws=[],pools=null;
Promise.all([fetch(BASE+'/data/draws.json').then(r=>r.json()),fetch(BASE+'/data/pools.json').then(r=>r.json()).catch(()=>null)]).then(([d,p])=>{
  draws=d.draws.filter(x=>x.min_score!=null);pools=p;
  const cats={};draws.forEach(x=>{(cats[x.category]=cats[x.category]||{label:x.category_label,stream:x.stream,sector:x.sector,n:0,last:x.date}).n++;if(x.date>cats[x.category].last)cats[x.category].last=x.date});
  const sel=$('#cat');sel.innerHTML='';
  const order=Object.entries(cats).sort((a,b)=>{const h=v=>v[1].sector==='health-care'?0:1;return h(a)-h(b)||a[1].label.localeCompare(b[1].label)});
  const og1=document.createElement('optgroup');og1.label='Health & care workers';const og2=document.createElement('optgroup');og2.label='All other streams & pathways';
  order.forEach(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=`${v.label} (${v.n} draws, last ${fmtDate(v.last)})`;(v.sector==='health-care'?og1:og2).appendChild(o)});
  sel.appendChild(og1);sel.appendChild(og2);
  const q=new URLSearchParams(location.search);
  if(q.get('cat')&&cats[q.get('cat')])sel.value=q.get('cat');
  if(q.get('score'))$('#score').value=q.get('score');
  if(q.get('window'))$('#window').value=q.get('window');
  $('#loading').classList.add('hidden');root.querySelector('form').classList.remove('hidden');
  if(q.get('score'))run();
}).catch(e=>{$('#loading').textContent='Could not load draw data ('+e+'). If you opened this file directly, serve the folder over http instead.'});

function run(){
  const cat=$('#cat').value,score=parseInt($('#score').value,10),win=$('#window').value;const out=$('#out');
  if(isNaN(score)||score<0||score>100){out.innerHTML='<div class="result low">Enter your Worker EOI (WEOI) score as a whole number from 0 to 100.</div>';return}
  let list=draws.filter(d=>d.category===cat).sort((a,b)=>b.date.localeCompare(a.date));
  if(win==='12m'){const cut=new Date();cut.setFullYear(cut.getFullYear()-1);const c=cut.toISOString().slice(0,10);list=list.filter(d=>d.date>=c)}
  else list=list.slice(0,parseInt(win,10));
  if(!list.length){out.innerHTML='<div class="result mid">No draws for this category in the selected window. Try a longer window.</div>';return}
  const mins=list.map(d=>d.min_score).sort((a,b)=>a-b);const lo=mins[0],hi=mins[mins.length-1];
  const med=mins.length%2?mins[(mins.length-1)/2]:(mins[mins.length/2-1]+mins[mins.length/2])/2;
  const cleared=list.filter(d=>score>=d.min_score).length;const latest=list[0];
  let cls,verdict,detail;
  if(score>=hi){cls='good';verdict='At or above every recent minimum';detail=`Your score of <b>${score}</b> meets or beats the minimum score in all ${list.length} of these draws.`}
  else if(score>=lo){cls='mid';verdict='Within the range of recent minimums';detail=`Your score of <b>${score}</b> would have met the minimum in <b>${cleared} of ${list.length}</b> recent draws. The highest recent minimum was ${hi}, so you are ${hi-score} point${hi-score===1?'':'s'} short of clearing all of them.`}
  else{cls='low';verdict='Below recent minimums';detail=`Your score of <b>${score}</b> is <b>${lo-score} point${lo-score===1?'':'s'}</b> below the lowest recent minimum (${lo}). Improving language test results is often the quickest lever. Check the official points grid.`}
  let pool='';
  if(pools&&pools.latest){const st=latest.stream;const rows=pools.latest.pools.filter(p=>p.stream===st);
    if(rows.length){pool=`<p class="small muted">Candidates currently in the pool for this stream: ${rows.map(r=>esc(r.name)+': <b>'+esc(r.count_text)+'</b>').join(' · ')} (as of ${fmtDate(pools.latest.page_last_updated)}).</p>`}}
  out.innerHTML=`<div class="result ${cls}"><div class="verdict">${verdict}</div><p style="margin:0 0 10px">${detail}</p>
  <div class="grid g4" style="margin:12px 0"><div class="stat"><div class="n">${latest.min_score}</div><div class="l">Latest minimum (${fmtDate(latest.date)})</div></div>
  <div class="stat"><div class="n">${med}</div><div class="l">Median minimum</div></div><div class="stat"><div class="n">${lo}–${hi}</div><div class="l">Range of minimums</div></div>
  <div class="stat"><div class="n">${cleared}/${list.length}</div><div class="l">Draws you'd have met</div></div></div>${pool}
  <p class="small" style="margin:8px 0 0"><b>Important:</b> AAIP says the EOI score is not the only factor it uses to choose who gets invited. Draws can target specific occupations, job offers, language levels or work permit dates. Past minimums don't guarantee future invitations. This is not immigration advice.</p></div>
  <div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Date</th><th>Draw</th><th class="num">Min score</th><th class="num">Invitations</th><th>You</th></tr></thead><tbody>
  ${list.map(d=>`<tr><td class="date">${fmtDate(d.date)}</td><td>${esc(d.stream_raw)}</td><td class="num">${d.min_score}</td><td class="num">${esc(d.invitations_text)}</td><td>${score>=d.min_score?'<span style="color:var(--ok);font-weight:700">✓ met</span>':'<span style="color:var(--bad)">✗ '+(d.min_score-score)+' short</span>'}</td></tr>`).join('')}</tbody></table></div>`;
  const u=new URL(location);u.searchParams.set('cat',cat);u.searchParams.set('score',score);u.searchParams.set('window',win);history.replaceState(null,'',u);
}
root.querySelector('form').addEventListener('submit',e=>{e.preventDefault();run()});
})();
