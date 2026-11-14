// "Onthul als PDF" uit console_pdf.js, getoetst op het echte bestand
// (console-pdf-views): wat het verstuurt, wat het toont, wat het opruimt.
// Een minimale nep-DOM; de klikhandler geeft zijn fetch-belofte terug.
const assert = require("assert");
const path = require("path");
const FILE = path.join(__dirname, "../src/wordsworth/static/console_pdf.js");

function page(checks, response) {
  const env = { calls: [], opened: [], made: [], revoked: [], handler: null };
  const status = { hidden: true, textContent: "", className: "", children: [],
                   appendChild(n) { this.children.push(n); } };
  const boxes = checks.map(([grant, value, on]) => ({ grant, value, checked: on }));
  const panel = {
    getAttribute: (a) => (a === "data-doc" ? "doc-1" : null),
    addEventListener: (ev, fn) => { env.handler = fn; },
    querySelectorAll(sel) {
      const m = /data-grant="([^"]*)"/.exec(sel);
      return boxes.filter((b) => b.grant === m[1]);
    },
  };
  global.document = {
    getElementById: (id) => ({ reveal: panel, "reveal-pdf-status": status })[id] || null,
    createElement: () => ({}),
    createTextNode: (t) => ({ text: t }),
  };
  global.CSS = { escape: (s) => s.replace(/"/g, '\\"') };
  global.window = { open: (u, t, f) => { env.opened.push([u, t, f]); return null; } };
  let n = 0;
  global.URL = {
    createObjectURL: () => { const u = "blob:x/" + (++n); env.made.push(u); return u; },
    revokeObjectURL: (u) => env.revoked.push(u),
  };
  global.fetch = (url, opts) => { env.calls.push([url, opts]); return response(); };
  delete require.cache[require.resolve(FILE)];
  require(FILE);
  env.status = status;
  env.click = (grant) => {
    const btn = { disabled: false, getAttribute: () => grant };
    return Promise.resolve(env.handler({ target: { closest: () => btn } }));
  };
  return env;
}

const ok = () => Promise.resolve({ ok: true, status: 200,
  blob: () => Promise.resolve("PDF") });
const refused = (code, detail) => () => Promise.resolve({ ok: false, status: code,
  json: () => Promise.resolve({ detail }) });

(async () => {
  // 1. post grant_id en de aangevinkte types, met de cookie (same-origin)
  let p = page([["g1", "PERSON", true], ["g1", "BSN", false], ["g2", "EMAIL", true]], ok);
  await p.click("g1");
  assert.strictEqual(p.calls.length, 1);
  const [url, opts] = p.calls[0];
  assert.strictEqual(url, "/documents/doc-1/reveal.pdf");
  assert.strictEqual(opts.method, "POST");
  assert.strictEqual(opts.credentials, "same-origin");
  assert.deepStrictEqual(JSON.parse(opts.body), { grant_id: "g1", types: ["PERSON"] });
  assert.deepStrictEqual(p.opened, [["blob:x/1", "_blank", "noopener"]]);
  assert.strictEqual(p.status.children[1].href, "blob:x/1");   // de betrouwbare link

  // 2. een tweede onthulling ruimt de vorige blob op
  await p.click("g1");
  assert.deepStrictEqual(p.revoked, ["blob:x/1"]);

  // 3. geen types aangevinkt: geen verzoek
  p = page([["g1", "PERSON", false]], ok);
  await p.click("g1");
  assert.strictEqual(p.calls.length, 0);
  assert.match(p.status.textContent, /Geen types aangevinkt/);

  // 4. een 403 wordt getoond als weigering, en de oude blob gaat weg
  let answer = ok;
  p = page([["g1", "PERSON", true]], () => answer());
  await p.click("g1");
  answer = refused(403, "grant not applicable");
  await p.click("g1");
  assert.match(p.status.textContent, /^Geweigerd \(403\): grant not applicable/);
  assert.strictEqual(p.status.className, "fout");
  assert.deepStrictEqual(p.revoked, ["blob:x/1"]);

  // 5. een 503 is geen weigering; een 422-lijst wordt leesbaar
  p = page([["g1", "PERSON", true]], refused(503, "key service unavailable"));
  await p.click("g1");
  assert.match(p.status.textContent, /^Niet gelukt \(503\): key service unavailable/);
  p = page([["g1", "PERSON", true]], refused(422, [{ loc: ["body"], msg: "field required" }]));
  await p.click("g1");
  assert.match(p.status.textContent, /field required/);
  assert.ok(!/object Object/.test(p.status.textContent));

  // 6. een netwerkfout ruimt de blob ook op
  answer = ok;
  p = page([["g1", "PERSON", true]], () => answer());
  await p.click("g1");
  answer = () => Promise.reject(new Error("weg"));
  await p.click("g1");
  assert.match(p.status.textContent, /Verzoek mislukt/);
  assert.deepStrictEqual(p.revoked, ["blob:x/1"]);

  console.log("console_pdf: alle gevallen goed");
})().catch((e) => { console.error(e); process.exit(1); });
