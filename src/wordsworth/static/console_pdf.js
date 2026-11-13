/* SPDX-License-Identifier: MIT */
/* Onthullen als PDF, per grant (console-pdf-views).
 *
 * Dezelfde deur als de tekstonthulling in console.js: een POST naar het
 * bestaande API-eindpunt `/documents/{id}/reveal.pdf`, met de cookie van de
 * kijker, de grant van die rij en de aangevinkte types. Hier staat geen regel
 * autorisatie: of het mag, beslist `authorize()` achter dat eindpunt, en een
 * weigering wordt getoond, niet verstopt.
 *
 * De PDF wordt nergens bewaard. Het eindpunt rendert hem bij elke aanroep vers
 * en cachet niets; hier leeft hij als blob in het geheugen van deze pagina,
 * zonder download-attribuut, tot de volgende onthulling of tot de pagina dicht
 * gaat.
 */
if (typeof document !== "undefined") (function () {
  var panel = document.getElementById("reveal");
  if (!panel) return;
  var status = document.getElementById("reveal-pdf-status");
  var current = null;   // de blob-URL van de laatste onthulling

  function say(text, bad, link) {
    status.hidden = false;
    status.textContent = text;
    status.className = bad ? "fout" : "empty";
    if (link) {
      var a = document.createElement("a");
      a.href = link; a.target = "_blank";
      a.textContent = "Open de onthulde PDF";
      status.appendChild(document.createTextNode(" "));
      status.appendChild(a);
    }
  }

  function checked(grant) {
    return Array.prototype.filter
      .call(panel.querySelectorAll('input[name="type"][data-grant="' + grant + '"]'),
            function (b) { return b.checked; })
      .map(function (b) { return b.value; });
  }

  function refusal(r) {
    // Een weigering komt als JSON met een `detail`; lukt dat niet, dan de code.
    return r.json().then(function (body) { return body.detail; },
                         function () { return null; })
      .then(function (detail) {
        say("Geweigerd (" + r.status + "): " + (detail || "geen reden gegeven")
            + " — er is geen PDF gemaakt.", true);
      });
  }

  panel.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-reveal-pdf]");
    if (!btn) return;
    var grant = btn.getAttribute("data-reveal-pdf");
    var types = checked(grant);
    if (!types.length) { say("Geen types aangevinkt.", true); return; }

    btn.disabled = true;
    say("PDF wordt gemaakt…", false);
    fetch("/documents/" + panel.getAttribute("data-doc") + "/reveal.pdf", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grant_id: grant, types: types })
    }).then(function (r) {
      btn.disabled = false;
      if (!r.ok) return refusal(r);
      return r.blob().then(function (blob) {
        if (current) URL.revokeObjectURL(current);
        current = URL.createObjectURL(blob);
        window.open(current, "_blank");
        // De PDF zegt niet welke types de grant werkelijk toestond: wat niet
        // mocht, blijft gelakt. Dus "gevraagd", niet "onthuld"; het spoor
        // noemt wat er werkelijk uitkwam.
        say("PDF gemaakt. Gevraagd: " + types.join(", ") + " · wat de grant "
            + "niet toestaat blijft gelakt · het auditspoor noemt wat er "
            + "onthuld is; herlaad om het te zien.", false, current);
      });
    }).catch(function (err) {
      btn.disabled = false;
      say("Verzoek mislukt: " + err, true);
    });
  });
})();
