// "What would I pay" calculator. Client-side only, no tracking. Ranks strictly by cost.
(function(){
  var D = JSON.parse(document.getElementById('rate-data').textContent);
  var $ = function(id){return document.getElementById(id)};
  var PRESETS = D.presets;
  function money(x){return (x<0?'-':'')+'$'+Math.abs(x).toFixed(2)}
  function cost(p, use){ return (p.fuel==='electricity' ? use*p.rate/100 : use*p.rate) + p.admin_monthly }
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function bench(fuel, city){ return fuel==='electricity' ? D.defaults['rolr_'+city] : D.defaults.gas_default }
  function rank(fuel, use, opts){
    return D.plans.filter(function(p){
      if(p.fuel!==fuel) return false;
      if(!opts.variable && p.type==='variable') return false;
      if(!opts.conditional && p.conditions) return false;
      return true;
    }).map(function(p){return {p:p, c:cost(p,use)}}).sort(function(a,b){return a.c-b.c});
  }
  function table(fuel, use, city, opts){
    var b = bench(fuel, city); if(!b) return '';
    var bc = cost(b, use), rows = rank(fuel, use, opts).slice(0, 8);
    var unit = fuel==='electricity' ? '¢/kWh' : '$/GJ';
    var h = '<div class="table-wrap"><table><thead><tr><th>#</th><th>Retailer and plan</th><th class="num">Rate</th><th class="num">Est. per month</th><th class="num">vs default</th></tr></thead><tbody>';
    h += '<tr class="bench"><td>–</td><td><b>'+esc(b.retailer)+'</b> <span class="tag def">Default</span><br><span class="small muted">'+esc(b.plan)+'</span></td><td class="num">'+(fuel==='electricity'?b.rate.toFixed(2):b.rate.toFixed(3))+' '+unit+'</td><td class="num"><b>'+money(bc)+'</b></td><td class="num">–</td></tr>';
    rows.forEach(function(r,i){
      var d = bc - r.c, p = r.p;
      h += '<tr><td class="rank">'+(i+1)+'</td><td><b>'+esc(p.retailer)+'</b> '+(p.type==='variable'?'<span class="tag var">Variable</span>':'')+(p.conditions?'<span class="tag cond" title="'+esc(p.conditions)+'">Conditions</span>':'')+'<br><span class="small muted">'+esc(p.plan)+(p.term_label?' · '+esc(p.term_label):'')+'</span></td><td class="num">'+(fuel==='electricity'?p.rate.toFixed(2):p.rate.toFixed(2))+' '+unit+'</td><td class="num"><b>'+money(r.c)+'</b></td><td class="num '+(d>=0?'save':'more')+'">'+(d>=0?'save '+money(d):money(-d)+' more')+'</td></tr>';
    });
    return h + '</tbody></table></div>';
  }
  function run(){
    var kwh = Math.max(0, parseFloat($('kwh').value)||0), gj = Math.max(0, parseFloat($('gj').value)||0);
    var city = $('city').value, opts = {variable: $('incl-var').checked, conditional: $('incl-cond').checked};
    var out = '', tot = 0, totB = 0, parts = [];
    if(kwh>0){
      var be = rank('electricity', kwh, opts)[0], bb = bench('electricity', city);
      if(be && bb){ tot += be.c; totB += cost(bb,kwh); parts.push('electricity: <b>'+esc(be.p.retailer)+'</b> '+esc(be.p.plan)); }
      out += '<h3 style="margin-top:18px">Electricity at '+kwh+' kWh/month</h3>' + table('electricity', kwh, city, opts);
    }
    if(gj>0){
      var bg = rank('gas', gj, opts)[0], gb = bench('gas', city);
      if(bg && gb){ tot += bg.c; totB += cost(gb,gj); parts.push('gas: <b>'+esc(bg.p.retailer)+'</b> '+esc(bg.p.plan)); }
      out += '<h3 style="margin-top:18px">Natural gas at '+gj+' GJ/month</h3>' + table('gas', gj, city, opts);
      var g = D.defaults.gas_default;
      if(g && g.avg12) out += '<p class="small muted">The default gas rate changes every month. This month it is $'+g.rate.toFixed(3)+'/GJ; its 12-month average ('+esc(g.avg12_range)+') was $'+g.avg12.toFixed(3)+'/GJ, and winter months usually run higher. At that average the default would cost about '+money(gj*g.avg12+g.admin_monthly)+'/month.</p>';
    }
    var sum = '';
    if(parts.length){
      var d = totB - tot;
      sum = '<div class="result '+(d>=0?'good':'mid')+'"><div class="small muted">Cheapest combination for you ('+parts.join(', ')+')</div><div class="kpi"><span class="big">'+money(tot)+'/month</span><span class="'+(d>=0?'save':'more')+'">'+(d>=0?'saves about '+money(d)+'/month ('+money(d*12)+'/year)':'costs '+money(-d)+'/month more')+' vs. the default rates</span></div><div class="small muted">Energy charges plus retailer admin fees only. Delivery, local access fees and GST are the same whichever retailer you choose, so they are left out.</div></div>';
    }
    $('calc-out').innerHTML = sum + out;
  }
  document.querySelectorAll('.presets button').forEach(function(b){
    b.addEventListener('click', function(){
      var p = PRESETS[b.dataset.p]; $('kwh').value = p.kwh; $('gj').value = p.gj;
      document.querySelectorAll('.presets button').forEach(function(x){x.classList.toggle('on', x===b)}); run();
    });
  });
  ['kwh','gj','city','incl-var','incl-cond'].forEach(function(id){ $(id).addEventListener('input', run); $(id).addEventListener('change', run); });
  $('calc-form').addEventListener('submit', function(e){ e.preventDefault(); run(); });
  run();
})();
