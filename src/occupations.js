// NOC lookup: which draws named this occupation code (2025 Draw Summary PDF) + whether it got invitations in 2025.
(function(){
const box=document.getElementById('noc-lookup');if(!box)return;const BASE=box.dataset.base||'';
const inp=box.querySelector('input'),out=box.querySelector('.out');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
Promise.all([fetch(BASE+'/data/draws.json').then(r=>r.json()),fetch(BASE+'/data/occupations.json').then(r=>r.json())]).then(([d,o])=>{
  const invited={};(o.years||[]).forEach(y=>y.nocs_invited.forEach(n=>{(invited[n.code]=invited[n.code]||{title:n.title,years:[]}).years.push(y.year)}));
  const named={};d.draws.forEach(x=>(x.nocs||[]).forEach(n=>{(named[n.code]=named[n.code]||{title:n.title,draws:[]}).draws.push(x)}));
  const titles={};Object.entries(invited).forEach(([k,v])=>titles[k]=v.title);Object.entries(named).forEach(([k,v])=>titles[k]=titles[k]||v.title);
  const go=()=>{const q=inp.value.trim().toLowerCase();if(q.length<2){out.innerHTML='';return}
    const hits=Object.keys(titles).filter(k=>k.startsWith(q)||titles[k].toLowerCase().includes(q)).sort().slice(0,25);
    if(!hits.length){out.innerHTML='<p class="muted">No match in the published draw lists. Many draws (e.g. general Alberta Opportunity Stream draws) don\'t list occupations, so no match doesn\'t mean no chance.</p>';return}
    out.innerHTML=hits.map(k=>{const inv=invited[k],nm=named[k];
      return `<div class="card" style="margin-bottom:8px"><b>NOC ${k}</b> – ${esc(titles[k])}<div class="small" style="margin-top:4px">${inv?'<span class="pill">Received AAIP invitations in '+inv.years.join(', ')+'</span> ':''}${nm?'Named in '+nm.draws.length+' targeted draw'+(nm.draws.length>1?'s':'')+': '+nm.draws.map(x=>esc(x.date+' '+x.stream_raw)).join('; '):'Not named in a targeted draw list.'}</div></div>`}).join('');};
  inp.addEventListener('input',go);go();
});
})();
