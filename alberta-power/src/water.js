// Monthly water estimate. Uses only the rates embedded from the public pages. Nothing is sent anywhere.
(function () {
  var el = document.getElementById("water-data");
  if (!el || !document.getElementById("water-calc")) return;
  var D = JSON.parse(el.textContent);
  var $ = function (id) { return document.getElementById(id); };
  var DAYS = 365 / 12;
  function money(x) {
    return (x < 0 ? "-" : "") + "$" + Math.abs(x).toFixed(2);
  }
  function tierCost(m3, tiers) {
    var cost = 0, prev = 0;
    tiers.forEach(function (t) {
      var up = t.up_to == null ? m3 : t.up_to;
      var slice = Math.max(0, Math.min(m3, up) - prev);
      cost += slice * t.rate;
      prev = up;
    });
    return cost;
  }
  function line(label, amount) {
    return "<tr><td>" + label + "</td><td class=\"num\">" + money(amount) + "</td></tr>";
  }
  function run() {
    var city = $("w-city").value;
    var m3 = Math.max(0, parseFloat($("w-m3").value) || 0);
    var edmonton = city === "edmonton";
    if ($("w-meter-wrap")) $("w-meter-wrap").hidden = !edmonton;
    if ($("w-waste-wrap")) $("w-waste-wrap").hidden = !edmonton;
    var rows = [];
    var note = "";
    if (city === "edmonton" && D.edmonton) {
      var E = D.edmonton;
      var mm = $("w-meter").value;
      var meter = (E.meters_daily || {})[mm];
      if (!meter) {
        $("w-out").innerHTML = "<p>No published daily charge for that meter size.</p>";
        return;
      }
      var waterUse = tierCost(m3, E.water_tiers_m3);
      var fixedDay = (meter.water_fixed || 0) + (meter.fire_protection || 0) + (meter.sanitary_fixed || 0) + (E.wastewater_treatment_daily || 0);
      var fixed = fixedDay * DAYS;
      var ww = m3 * E.wastewater_treatment_per_m3;
      var san = m3 * E.sanitary_per_m3;
      rows.push(line("Water use (" + m3 + " m³, tiered)", waterUse));
      rows.push(line("Water fixed + fire protection + sanitary fixed + wastewater fixed (" + mm + " mm, × " + DAYS.toFixed(2) + " days)", fixed));
      rows.push(line("Wastewater treatment (" + E.wastewater_treatment_per_m3.toFixed(4) + "/m³)", ww));
      rows.push(line("Sanitary collection (" + E.sanitary_per_m3.toFixed(5) + "/m³)", san));
      var total = waterUse + fixed + ww + san;
      var cart = $("w-waste").value;
      if (cart && D.edmonton_waste) {
        var item = (D.edmonton_waste.curbside || []).filter(function (c) { return c.id === cart; })[0];
        var add = cart === "apartment" ? D.edmonton_waste.apartment_monthly : (item ? item.monthly : 0);
        if (add) {
          rows.push(line("Waste services (flat, City of Edmonton)", add));
          total += add;
        }
      }
      rows.push("<tr><td><b>Estimated total</b></td><td class=\"num\"><b>" + money(total) + "</b></td></tr>");
      note = "Edmonton fixed charges are daily, so this uses a " + DAYS.toFixed(2) + "-day month (365 ÷ 12). A real bill uses the number of days in the period. Stormwater is not included: EPCOR charges property area × intensity × runoff coefficient × $" + E.stormwater.daily_rate.toFixed(5) + " per day, and the page does not give one residential runoff coefficient. GST is not added.";
    } else if (city === "calgary" && D.calgary) {
      var C = D.calgary;
      var water = m3 * C.water_per_m3 + C.water_fixed_per_30_days;
      var ww = m3 * C.wastewater_return_factor * C.wastewater_per_m3 + C.wastewater_fixed_per_30_days;
      var storm = C.stormwater_per_30_days;
      rows.push(line("Water (" + m3 + " m³ × $" + C.water_per_m3.toFixed(4) + " + $" + C.water_fixed_per_30_days.toFixed(2) + " / 30 days)", water));
      rows.push(line("Wastewater (" + m3 + " × " + C.wastewater_return_factor + " × $" + C.wastewater_per_m3.toFixed(4) + " + $" + C.wastewater_fixed_per_30_days.toFixed(2) + ")", ww));
      rows.push(line("Stormwater (flat per 30 days)", storm));
      var totalC = water + ww + storm;
      rows.push("<tr><td><b>Estimated 30-day total</b></td><td class=\"num\"><b>" + money(totalC) + "</b></td></tr>");
      if (m3 === C.example_m3) {
        note = "At " + C.example_m3 + " m³ the City's own 2026 illustration is $" + C.water_example_bill.toFixed(2) + " water + $" + C.wastewater_example_bill.toFixed(2) + " wastewater + $" + C.stormwater_per_30_days.toFixed(2) + " stormwater. This estimate should match those figures. GST is not added. A billing period other than 30 days changes the fixed charges.";
      } else {
        note = "Fixed charges are the City's per-30-days amounts. Wastewater volume is water use × " + C.wastewater_return_factor + ", which is the factor the City uses year-round. GST is not added.";
      }
    } else {
      $("w-out").innerHTML = "<p>No rates are loaded for that city.</p>";
      return;
    }
    $("w-out").innerHTML = "<div class=\"table-wrap\"><table><tbody>" + rows.join("") + "</tbody></table></div><p class=\"small muted\">" + note + "</p>";
  }
  ["w-city", "w-m3", "w-meter", "w-waste"].forEach(function (id) {
    if (!$(id)) return;
    $(id).addEventListener("input", run);
    $(id).addEventListener("change", run);
  });
  run();
})();
