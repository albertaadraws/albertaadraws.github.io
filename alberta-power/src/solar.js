// Solar comparison sort/filter and the payback calculator. Client-side only.
(function () {
  var dataEl = document.getElementById("solar-data");
  if (!dataEl) return;
  var D = JSON.parse(dataEl.textContent);
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function money(x) {
    return (x < 0 ? "-" : "") + "$" + Math.abs(x).toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function num(v) {
    var n = parseFloat(v);
    return isNaN(n) ? null : n;
  }

  var table = $("solar-table");
  if (table) {
    var tbody = table.querySelector("tbody");
    function apply() {
      var q = ($("solar-filter") && $("solar-filter").value || "").trim().toLowerCase();
      var showVar = !$("solar-show-var") || $("solar-show-var").checked;
      var showPre = !$("solar-show-pre") || $("solar-show-pre").checked;
      Array.prototype.forEach.call(tbody.querySelectorAll("tr"), function (tr) {
        var kind = tr.getAttribute("data-kind");
        var hideKind = (kind === "variable" && !showVar) || (kind === "presolar" && !showPre);
        var name = tr.getAttribute("data-name") || "";
        tr.hidden = hideKind || (q && name.indexOf(q) === -1);
      });
    }
    function sortBy(field) {
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      rows.sort(function (a, b) {
        var av = num(a.getAttribute("data-" + field));
        var bv = num(b.getAttribute("data-" + field));
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        if (bv !== av) return bv - av;
        var aa = num(a.getAttribute("data-admin"));
        var ba = num(b.getAttribute("data-admin"));
        if (aa == null) return 1;
        if (ba == null) return -1;
        return aa - ba;
      });
      rows.forEach(function (tr) { tbody.appendChild(tr); });
      document.querySelectorAll("#solar-sort button").forEach(function (btn) {
        btn.classList.toggle("on", btn.getAttribute("data-sort") === field);
      });
    }
    document.querySelectorAll("#solar-sort button").forEach(function (btn) {
      btn.addEventListener("click", function () { sortBy(btn.getAttribute("data-sort")); });
    });
    ["solar-filter", "solar-show-var", "solar-show-pre"].forEach(function (id) {
      if (!$(id)) return;
      $(id).addEventListener("input", apply);
      $(id).addEventListener("change", apply);
    });
    sortBy("export");
    apply();
  }

  if (!$("solar-calc")) return;
  var planSel = $("solar-plan");
  D.plans.forEach(function (p) {
    var opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.retailer + " — " + p.plan + " (export " + (p.export_rate == null ? "n/a" : p.export_rate.toFixed(2) + "¢") + ")";
    planSel.appendChild(opt);
  });

  function production(city) {
    var row = (D.production || []).filter(function (r) { return r.city === city; })[0];
    return row || null;
  }
  function selectedPlan() {
    var id = planSel.value;
    if (!id) return null;
    return D.plans.filter(function (p) { return p.id === id; })[0] || null;
  }
  function importRate(plan) {
    if (!plan) return null;
    if ($("solar-import-which") && $("solar-import-which").value === "alt" && plan.import_alt) return plan.import_alt.rate;
    return plan.import_rate;
  }

  function run() {
    var kw = Math.max(0, parseFloat($("solar-kw").value) || 0);
    var city = $("solar-city").value;
    var prod = production(city);
    var share = Math.min(1, Math.max(0, (parseFloat($("solar-share").value) || 0) / 100));
    var perW = Math.max(0, parseFloat($("solar-cpw").value) || 0);
    var plan = selectedPlan();
    var single = Math.max(0, parseFloat($("solar-rate").value) || 0);
    var usePlan = $("solar-mode").value === "plan" && plan && plan.export_rate != null;
    var out = $("solar-out");
    if (!prod || kw <= 0) {
      out.innerHTML = "<p class=\"small muted\">Enter a system size. Annual kWh uses the NRCan figure for the city you pick.</p>";
      return;
    }
    var annual = kw * prod.kwh_per_kw;
    var exported = annual * share;
    var self = annual - exported;
    var exportC = usePlan ? plan.export_rate : single;
    var importC = usePlan ? importRate(plan) : single;
    if (importC == null) importC = single;
    var credit = exported * exportC / 100;
    var avoided = self * importC / 100;
    var value = credit + avoided;
    var cost = kw * 1000 * perW;
    var years = value > 0 ? cost / value : null;
    var bits = [];
    bits.push("<div class=\"result good\"><div class=\"small muted\">Estimate only. Not a quote and not a forecast.</div>");
    bits.push("<div class=\"kpi\"><span class=\"big\">" + (years == null ? "—" : years.toFixed(1) + " years") + "</span><span>simple payback</span></div>");
    bits.push("<p>About <b>" + Math.round(annual).toLocaleString("en-CA") + " kWh/year</b> from " + kw + " kW in " + esc(prod.city_label) + " (" + prod.kwh_per_kw + " kWh per kW, " + esc(prod.orientation) + ", " + esc(prod.period) + ").</p>");
    bits.push("<ul>");
    bits.push("<li>Exported (" + Math.round(share * 100) + "%): " + Math.round(exported).toLocaleString("en-CA") + " kWh × " + exportC.toFixed(2) + "¢ → <b>" + money(credit) + "</b> in bill credits</li>");
    bits.push("<li>Used at home (" + Math.round((1 - share) * 100) + "%): " + Math.round(self).toLocaleString("en-CA") + " kWh × " + importC.toFixed(2) + "¢ → <b>" + money(avoided) + "</b> of electricity you do not buy</li>");
    bits.push("<li>Annual value of those two: <b>" + money(value) + "</b></li>");
    bits.push("<li>Installed cost: " + kw + " kW × " + money(perW) + "/W = <b>" + money(cost) + "</b></li>");
    bits.push("</ul>");
    if (usePlan) {
      bits.push("<p class=\"small\">Plan: <b>" + esc(plan.retailer) + "</b>, " + esc(plan.plan) + ". " + esc(plan.export_text) + " export; " + esc(plan.import_text) + " import." + (plan.indicative ? " This rate is the retailer's recent average and will change." : "") + "</p>");
    } else {
      bits.push("<p class=\"small\">Single rate: every kWh, exported or used at home, is valued at " + single.toFixed(2) + "¢/kWh.</p>");
    }
    bits.push("<p class=\"small muted\">Left out on purpose: delivery and distribution charges, GST, the retailer's monthly admin fee, shading, snow, inverter replacement, and the drop in output as panels age. The export share is an assumption you can edit. A Solar Club HI/LO row prices exports at the HI rate and home use at the LO rate. That is the usual seasonal pattern, not a month-by-month bill. While you are actually on the HI rate, imports that month are at the HI rate too.</p></div>");
    out.innerHTML = bits.join("");
  }

  function syncImportChoice() {
    var plan = selectedPlan();
    var wrap = $("solar-import-wrap");
    if (!wrap) return;
    var show = plan && plan.import_alt && $("solar-mode").value === "plan";
    wrap.hidden = !show;
    if (show) {
      $("solar-import-which").options[1].textContent = plan.import_alt.label;
    }
  }
  ["solar-kw", "solar-city", "solar-share", "solar-cpw", "solar-rate", "solar-mode", "solar-plan", "solar-import-which"].forEach(function (id) {
    if (!$(id)) return;
    $(id).addEventListener("input", function () { syncImportChoice(); run(); });
    $(id).addEventListener("change", function () {
      if (id === "solar-plan" && planSel.value) $("solar-mode").value = "plan";
      syncImportChoice();
      run();
    });
  });
  syncImportChoice();
  run();
})();
