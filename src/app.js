// Mobile menu
document.addEventListener('click',e=>{if(e.target.closest('.menu-btn')){document.querySelector('nav.main').classList.toggle('open')}});
// Newsletter forms: TODO connect to a real provider (Buttondown / beehiiv / Kit). Nothing is sent anywhere yet.
document.querySelectorAll('form[data-newsletter]').forEach(f=>f.addEventListener('submit',e=>{
  e.preventDefault();
  const m=f.parentElement.querySelector('.nl-msg');
  if(m){m.textContent='Thanks! Signups open soon - this form is not connected to an email service yet (preview build).';m.classList.remove('hidden')}
}));
// Table filter (all draws page)
const ft=document.querySelector('[data-filter-table]');
if(ft){const tb=document.querySelector(ft.dataset.filterTable);const sels=ft.querySelectorAll('select,input');
 const run=()=>{const v={};sels.forEach(s=>v[s.name]=s.value.toLowerCase());let shown=0;
  tb.querySelectorAll('tbody tr').forEach(tr=>{const ok=(!v.stream||tr.dataset.stream===v.stream)&&(!v.year||tr.dataset.year===v.year)&&(!v.sector||tr.dataset.sector===v.sector)&&(!v.q||tr.textContent.toLowerCase().includes(v.q));tr.style.display=ok?'':'none';if(ok)shown++});
  const c=document.querySelector('[data-count]');if(c)c.textContent=shown};
 sels.forEach(s=>s.addEventListener('input',run));run();}
