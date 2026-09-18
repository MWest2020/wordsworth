// SPDX-License-Identifier: MIT
//
// De onthulknop op de documentpagina (console-demo).
//
// Dit bestand bevat GEEN autorisatie. Het stuurt een verzoek naar het bestaande
// reveal-eindpunt met het cookie dat je al hebt; wie wat mag, beslist de server
// met dezelfde authorize() en hetzelfde auditrecord als voor elke andere beller.
// Een weigering wordt getoond, niet weggewerkt.

// Zoek per token de onthulde waarde door te verankeren op de letterlijke tekst
// eromheen, die immers niet verandert. Zuiver en zonder DOM, zodat hij in node
// te toetsen is -- de uitlijning is het enige hier waar een fout stil is.
//
// Lukt het niet sluitend, dan geeft hij null terug: liever geen markering dan
// een verkeerde. De sluitcontrole onderaan is wat dat waarmaakt -- verankeren op
// een kort of herhaald stuk tekst kan er net naast zitten, en dan klopt het
// terugbouwen niet meer.
function wwAlign(segments, revealed) {
  var gevonden = [];
  zoek(segments, revealed, 0, 0, [], gevonden);
  // Precies één manier om dit te lezen, of we zeggen niets. Twee uitlijningen
  // betekent dat wij niet weten welke waarde bij welk type hoort, en een
  // verkeerde markering is erger dan geen: de lezer moet juist beoordelen of de
  // pseudonimisering klopt.
  return gevonden.length === 1 ? gevonden[0] : null;
}

// Alle volledige uitlijningen, tot er twee zijn -- meer hoeven we niet te weten.
function zoek(segments, revealed, i, pos, tot_nu, uit) {
  if (uit.length > 1) return;
  if (i === segments.length) {
    if (pos === revealed.length) uit.push(tot_nu.slice());
    return;
  }
  var s = segments[i];
  if (!s.token) {
    if (revealed.substr(pos, s.text.length) !== s.text) return;
    tot_nu.push({ token: false, text: s.text });
    zoek(segments, revealed, i + 1, pos + s.text.length, tot_nu, uit);
    tot_nu.pop();
    return;
  }
  // Staan er hierachter geen tokens meer, dan ligt de staart vast en is het
  // einde exact te berekenen -- geen zoeken, geen gok.
  var staart = 0, alleen_letterlijk = true;
  for (var j = i + 1; j < segments.length; j++) {
    if (segments[j].token) { alleen_letterlijk = false; break; }
    staart += segments[j].text.length;
  }
  var kandidaten = [];
  if (alleen_letterlijk) {
    var eind = revealed.length - staart;
    if (eind >= pos) kandidaten.push(eind);
  } else {
    // Elke plek waar het volgende letterlijke stuk staat is een mogelijkheid.
    // De eerste pakken is precies de gok die "Piet over 123456782" als een
    // BSN markeerde.
    var volgend = segments[i + 1].text;
    if (volgend === "") return;                 // twee tokens tegen elkaar
    for (var k = revealed.indexOf(volgend, pos); k >= 0;
         k = revealed.indexOf(volgend, k + 1)) {
      kandidaten.push(k);
    }
  }
  for (var c = 0; c < kandidaten.length && uit.length < 2; c++) {
    var waarde = revealed.slice(pos, kandidaten[c]);
    tot_nu.push({ token: true, text: waarde, revealed: waarde !== s.text,
                  type: s.type });
    zoek(segments, revealed, i + 1, kandidaten[c], tot_nu, uit);
    tot_nu.pop();
  }
}

if (typeof module !== "undefined" && module.exports) { module.exports = { wwAlign: wwAlign }; }

if (typeof document !== "undefined") (function () {

  var panel = document.getElementById("reveal");
  if (!panel) return;
  var pre = document.querySelector("pre.doc");
  var status = document.getElementById("reveal-status");
  var TOKEN = /\[[A-Z0-9_]+:[0-9a-f]{8}\]/g;

  // De oorspronkelijke opbouw: afwisselend letterlijke tekst en tokens, in de
  // volgorde waarin de server ze rendert.
  var segments = [];
  if (pre) {
    Array.prototype.forEach.call(pre.childNodes, function (n) {
      var token = n.nodeType === 1 && n.classList.contains("tok");
      segments.push({ token: token, text: n.textContent, type: token ? n.title : null });
    });
  }

  function say(text, bad) {
    status.hidden = false;
    status.textContent = text;
    status.className = bad ? "fout" : "empty";
  }

  function render(revealed) {
    var parts = wwAlign(segments, revealed);
    pre.textContent = "";
    if (!parts) {
      // Terugval: nog steeds de echte onthulde tekst, alleen zonder markering
      // per waarde. De overgebleven tokens krijgen hun stijl terug.
      var last = 0, m;
      TOKEN.lastIndex = 0;
      while ((m = TOKEN.exec(revealed)) !== null) {
        pre.appendChild(document.createTextNode(revealed.slice(last, m.index)));
        var t = document.createElement("span");
        t.className = "tok"; t.textContent = m[0];
        pre.appendChild(t); last = m.index + m[0].length;
      }
      pre.appendChild(document.createTextNode(revealed.slice(last)));
      return false;
    }
    parts.forEach(function (p) {
      if (!p.token) { pre.appendChild(document.createTextNode(p.text)); return; }
      var span = document.createElement("span");
      span.className = p.revealed ? "tok revealed" : "tok";
      if (p.type) span.title = p.type;
      span.textContent = p.text;
      pre.appendChild(span);
    });
    return true;
  }

  panel.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-reveal]");
    if (!btn) return;
    var grant = btn.getAttribute("data-reveal");
    var types = Array.prototype.filter
      .call(panel.querySelectorAll('input[name="type"][data-grant="' + grant + '"]'),
            function (b) { return b.checked; })
      .map(function (b) { return b.value; });
    if (!types.length) { say("Geen types aangevinkt.", true); return; }

    btn.disabled = true;
    say("Bezig…", false);
    fetch("/documents/" + panel.getAttribute("data-doc") + "/reveal", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grant_id: grant, types: types })
    }).then(function (r) {
      return r.json().then(function (body) { return { ok: r.ok, code: r.status, body: body }; });
    }).then(function (res) {
      btn.disabled = false;
      if (!res.ok) {
        say("Geweigerd (" + res.code + "): " + (res.body.detail || "geen reden gegeven")
            + " — de tekst blijft gepseudonimiseerd.", true);
        return;
      }
      var marked = render(res.body.revealed_text);
      var msg = "Onthuld: " + (res.body.revealed_types.join(", ") || "niets");
      if (res.body.withheld_types && res.body.withheld_types.length) {
        msg += " · geweigerd: " + res.body.withheld_types.join(", ");
      }
      if (!marked) msg += " · waarden niet apart te markeren, tekst is wel de onthulde";
      msg += " · staat in het auditspoor; herlaad om het te zien.";
      say(msg, false);
    }).catch(function (err) {
      btn.disabled = false;
      say("Verzoek mislukt: " + err, true);
    });
  });
})();
