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
 * en zegt `Cache-Control: no-store`; hier leeft hij als blob in het geheugen
 * van deze pagina, zonder download-attribuut, tot de volgende poging of tot de
 * pagina dicht gaat.
 */
if (typeof document !== "undefined") (function () {
  var panel = document.getElementById("reveal");
  if (!panel) return;
  var status = document.getElementById("reveal-pdf-status");
  var current = null;   // de blob-URL van de laatste onthulling

  function forget() {
    if (current) URL.revokeObjectURL(current);
    current = null;
  }

  function say(text, bad, link) {
    status.hidden = false;
    status.textContent = text;
    status.className = bad ? "fout" : "empty";
    if (link) {
      var a = document.createElement("a");
      a.href = link; a.target = "_blank"; a.rel = "noopener";
      a.textContent = "Open de onthulde PDF";
      status.appendChild(document.createTextNode(" "));
      status.appendChild(a);
    }
  }

  function checked(grant) {
    var sel = 'input[name="type"][data-grant="' + CSS.escape(grant) + '"]';
    return Array.prototype.filter
      .call(panel.querySelectorAll(sel), function (b) { return b.checked; })
      .map(function (b) { return b.value; });
  }

  // FastAPI geeft `detail` als tekst, of bij een ongeldig verzoek (422) als
  // lijst van {loc, msg}. Nooit "[object Object]" op het scherm.
  function reason(detail) {
    if (!detail) return "geen reden gegeven";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map(function (d) { return (d && d.msg) || JSON.stringify(d); })
        .join("; ");
    }
    return JSON.stringify(detail);
  }

  function refusal(r) {
    forget();
    return r.json().then(function (body) { return body && body.detail; },
                         function () { return null; })
      .then(function (detail) {
        // Alleen 401/403 is een weigering; 404, 409 en 503 zijn "lukt nu niet".
        var word = (r.status === 401 || r.status === 403) ? "Geweigerd" : "Niet gelukt";
        say(word + " (" + r.status + "): " + reason(detail)
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
    return fetch("/documents/" + panel.getAttribute("data-doc") + "/reveal.pdf", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grant_id: grant, types: types })
    }).then(function (r) {
      btn.disabled = false;
      if (!r.ok) return refusal(r);
      return r.blob().then(function (blob) {
        forget();
        current = URL.createObjectURL(blob);
        // Een poging. Na het renderen is de klik vaak "verbruikt" en houdt een
        // popupblokker dit tegen; de link in de statusregel hieronder is de
        // betrouwbare weg en staat er altijd.
        window.open(current, "_blank", "noopener");
        // De PDF zegt niet welke types de grant werkelijk toestond: wat niet
        // mocht, blijft gelakt. Dus "gevraagd", niet "onthuld"; het spoor
        // noemt wat er werkelijk uitkwam.
        say("PDF gemaakt. Gevraagd: " + types.join(", ") + " · wat de grant "
            + "niet toestaat blijft gelakt · het auditspoor noemt wat er "
            + "onthuld is; herlaad om het te zien.", false, current);
      });
    }).catch(function (err) {
      btn.disabled = false;
      forget();
      say("Verzoek mislukt: " + err, true);
    });
  });
})();
