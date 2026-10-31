// Pure generator logic, shared by the page (app.js) and the CI test
// (site/test/make_zip.mjs). No DOM access here.

// MIRROR: generator/engine.py combination_key — keep in sync.
export function combinationKey(enabled) {
  return [...enabled].sort().join("+") || "base";
}

export function validateName(name, manifest) {
  if (!new RegExp(manifest.name_pattern).test(name)) {
    return "Use lowercase letters, digits and hyphens, starting with a letter.";
  }
  if (name === manifest.placeholder_name) {
    return `Pick a real name; "${name}" is the template placeholder.`;
  }
  if (name.length > manifest.max_name_len) {
    return `Max ${manifest.max_name_len} characters (AWS IAM role names cap at 64). This is ${name.length}.`;
  }
  return null;
}

export function validatePublicKey(key, manifest) {
  if (!key) return null;
  return new RegExp(manifest.public_key_pattern).test(key)
    ? null
    : "64 lowercase hex characters (Developer Portal → General Information → Public Key).";
}

// MIRROR: generator/engine.py apply_name — keep in sync.
export function applyName(files, name, manifest, publicKeyDev = "", publicKeyProd = "") {
  const out = { ...files };
  for (const rel of manifest.name_files) {
    if (rel in out) out[rel] = out[rel].split(manifest.placeholder_name).join(name);
  }
  let config = out["config.env"];
  if (publicKeyDev) config = config.replace(/^DISCORD_PUBLIC_KEY_DEV=.*$/m, `DISCORD_PUBLIC_KEY_DEV=${publicKeyDev}`);
  if (publicKeyProd) config = config.replace(/^DISCORD_PUBLIC_KEY_PROD=.*$/m, `DISCORD_PUBLIC_KEY_PROD=${publicKeyProd}`);
  out["config.env"] = config;
  return out;
}

// ── Zip writer ───────────────────────────────────────────────────────────────
// Minimal ZIP (stored, no compression) — enough for a ~150 KB text starter and
// avoids pulling a third-party library into the page.

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function dosDateTime(date) {
  const time = (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2);
  const day = ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
  return { time, day };
}

/** Build a zip of {path: text} under a top-level `folder/`. Returns a Uint8Array. */
export function buildZip(files, folder, date = new Date()) {
  const encoder = new TextEncoder();
  const { time, day } = dosDateTime(date);
  const locals = [];
  const centrals = [];
  let offset = 0;

  for (const rel of Object.keys(files).sort()) {
    const name = encoder.encode(`${folder}/${rel}`);
    const data = encoder.encode(files[rel]);
    const crc = crc32(data);

    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);  // local file header signature
    local.setUint16(4, 20, true);          // version needed
    local.setUint16(6, 0x0800, true);      // flags: UTF-8 names
    local.setUint16(8, 0, true);           // method: stored
    local.setUint16(10, time, true);
    local.setUint16(12, day, true);
    local.setUint32(14, crc, true);
    local.setUint32(18, data.length, true);
    local.setUint32(22, data.length, true);
    local.setUint16(26, name.length, true);
    local.setUint16(28, 0, true);
    locals.push(new Uint8Array(local.buffer), name, data);

    const central = new DataView(new ArrayBuffer(46));
    central.setUint32(0, 0x02014b50, true); // central directory signature
    central.setUint16(4, 0x031e, true);     // made by: UNIX, spec 3.0
    central.setUint16(6, 20, true);
    central.setUint16(8, 0x0800, true);
    central.setUint16(10, 0, true);
    central.setUint16(12, time, true);
    central.setUint16(14, day, true);
    central.setUint32(16, crc, true);
    central.setUint32(20, data.length, true);
    central.setUint32(24, data.length, true);
    central.setUint16(28, name.length, true);
    central.setUint32(38, (0o100644 << 16) >>> 0, true); // external attrs: regular file, rw-r--r--
    central.setUint32(42, offset, true);
    centrals.push(new Uint8Array(central.buffer), name);

    offset += 30 + name.length + data.length;
  }

  const centralSize = centrals.reduce((n, part) => n + part.length, 0);
  const count = Object.keys(files).length;
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);       // end of central directory signature
  end.setUint16(8, count, true);
  end.setUint16(10, count, true);
  end.setUint32(12, centralSize, true);
  end.setUint32(16, offset, true);

  const parts = [...locals, ...centrals, new Uint8Array(end.buffer)];
  const out = new Uint8Array(parts.reduce((n, part) => n + part.length, 0));
  let pos = 0;
  for (const part of parts) {
    out.set(part, pos);
    pos += part.length;
  }
  return out;
}
