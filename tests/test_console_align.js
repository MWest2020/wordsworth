// De uitlijning uit console.js, getoetst op het echte bestand (console-demo).
// Een fout hier is stil: je ziet de onthulde tekst en gelooft de markering.
const assert = require("assert");
const { wwAlign } = require("../src/wordsworth/static/console.js");

const L = (t) => ({ token: false, text: t });
const T = (t, type) => ({ token: true, text: t, type: type || "PERSON" });

// 1. het gewone geval: een token wordt een waarde
assert.deepStrictEqual(
  wwAlign([L("Aan "), T("[PERSON:aabbccdd]"), L(" te Nijmegen.")],
          "Aan Janine van Dijk te Nijmegen."),
  [{ token: false, text: "Aan " },
   { token: true, text: "Janine van Dijk", revealed: true, type: "PERSON" },
   { token: false, text: " te Nijmegen." }]);

// 2. een token dat NIET onthuld is blijft zichzelf, en heet dan niet onthuld
const same = wwAlign([L("Aan "), T("[PERSON:aabbccdd]"), L(" einde.")],
                     "Aan [PERSON:aabbccdd] einde.");
assert.strictEqual(same[1].revealed, false);

// 3. meerdere tokens, gedeeltelijk onthuld
const mixed = wwAlign(
  [L("bsn "), T("[BSN:11223344]", "BSN"), L(" en naam "), T("[PERSON:aabbccdd]"), L(".")],
  "bsn 123456782 en naam [PERSON:aabbccdd].");
assert.strictEqual(mixed[1].text, "123456782");
assert.strictEqual(mixed[1].revealed, true);
assert.strictEqual(mixed[3].revealed, false);

// 4. een token aan het einde, zonder letterlijke tekst erachter
const tail = wwAlign([L("naam "), T("[PERSON:aabbccdd]")], "naam Janine van Dijk");
assert.strictEqual(tail[1].text, "Janine van Dijk");

// 5. twee tokens tegen elkaar: geen anker, dus geen markering -- NIET raden
assert.strictEqual(
  wwAlign([L("x "), T("[A:11111111]"), L(""), T("[B:22222222]")], "x ab"), null);

// 6. een kort anker mag, zolang er maar één manier is om het te lezen
const kort = wwAlign([L("x "), T("[A:11111111]"), L(", "), T("[B:22222222]"), L(" eind")],
                     "x waarde, ander eind");
assert.deepStrictEqual(kort.filter((p) => p.token).map((p) => p.text),
                       ["waarde", "ander"]);

// 7. letterlijke tekst die niet klopt -> null, geen halve uitlijning
assert.strictEqual(
  wwAlign([L("Aan "), T("[PERSON:aabbccdd]"), L(" te Nijmegen.")],
          "Iets heel anders"), null);

// 8. DE VALKUIL, en tot 18-09 assertte deze test iets dat altijd waar was.
//    De onthulde waarde bevat zelf het anker, dus er zijn twee manieren om de
//    tekst te lezen. Vroeger pakte hij de eerste en markeerde "Piet over
//    123456782" als een BSN -- een onjuiste uitspraak aan de lezer die juist
//    moet beoordelen of de pseudonimisering klopt. Nu: twee lezingen betekent
//    dat wij het niet weten, en dan zeggen we niets.
assert.strictEqual(
  wwAlign([L("a "), T("[X:11111111]"), L(" mid "), T("[Y:22222222]"), L(" z")],
          "a een mid stuk mid twee z"), null);

// 8b. hetzelfde met echte namen, zoals de codereview het reproduceerde
assert.strictEqual(
  wwAlign([L("Aan "), T("[PERSON:aaaaaaaa]"), L(" over "), T("[BSN:bbbbbbbb]"), L(".")],
          "Aan Jan over Piet over 123456782."), null);

// 8c. eenduidig blijft eenduidig: dezelfde vorm, een anker dat maar een keer past
assert.deepStrictEqual(
  wwAlign([L("Aan "), T("[PERSON:aaaaaaaa]"), L(", bsn "), T("[BSN:bbbbbbbb]"), L(".")],
          "Aan Janine van Dijk, bsn 123456782.")
    .filter((p) => p.token).map((p) => p.text),
  ["Janine van Dijk", "123456782"]);

console.log("console.js uitlijning: alle gevallen goed");
