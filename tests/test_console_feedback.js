// Het feedback-stukje uit console.js, getoetst op het echte bestand
// (deleted-document-answers-410, task 4.1): een weigering wordt getoond en
// niet als gelukt behandeld -- ook niet een 410.
const assert = require("assert");
const path = require("path");
const FILE = path.join(__dirname, "../src/wordsworth/static/console.js");

function page(response) {
  const env = { calls: [], submit: null };
  const melding = { textContent: "", style: {} };
  const select = { value: "PERSON" };
  const mis = {
    querySelector: () => select,
    addEventListener: (ev, fn) => { env.submit = fn; },
  };
  const pre = {
    getAttribute: (a) => (a === "data-doc" ? "doc-1" : null),
    addEventListener: () => {},
  };
  global.document = {
    getElementById: (id) => ({
      reveal: null, doctekst: pre, fbmelding: melding, fbmis: mis,
    })[id] || null,
  };
  global.fetch = (url, opts) => { env.calls.push([url, opts]); return response(); };
  delete require.cache[require.resolve(FILE)];
  require(FILE);
  env.melding = melding;
  return env;
}

const refused = (code, detail) => () => Promise.resolve({
  ok: false, status: code, json: () => Promise.resolve({ detail }),
});
const wacht = () => new Promise((r) => setTimeout(r, 0));

(async () => {
  // Een 410 op een gemiste-waarde melding: getoond, niet verzwegen, niet
  // als gelukt behandeld.
  const env = page(refused(410, "document deleted"));
  env.submit({ preventDefault: () => {} });
  await wacht();
  assert.strictEqual(env.calls.length, 1);
  const [url, opts] = env.calls[0];
  assert.strictEqual(url, "/documents/doc-1/feedback");
  assert.strictEqual(opts.method, "POST");
  assert.deepStrictEqual(JSON.parse(opts.body), { kind: "fn", type: "PERSON" });
  assert.match(env.melding.textContent, /^Niet opgeslagen \(410\): document deleted/);
  assert.strictEqual(env.melding.style.color, "var(--revoked)");

  console.log("console_feedback: 410 getoond, niet als gelukt behandeld");
})().catch((e) => { console.error(e); process.exit(1); });
