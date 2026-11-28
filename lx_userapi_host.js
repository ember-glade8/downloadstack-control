#!/usr/bin/env node
/**
 * LXSRC: local host for lyswhut/lx-music-desktop userApi scripts.
 * Binds 127.0.0.1 only. Reads the user's existing LX Music user_api.json
 * (or a copied snapshot) and never writes back to LX Music files.
 */
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const vm = require('vm');
const http = require('http');
const https = require('https');
const zlib = require('zlib');
const crypto = require('crypto');
const qs = require('querystring');
const { URL } = require('url');

process.on('unhandledRejection', () => {});

function argVal(flag, fallback) {
  const i = process.argv.indexOf(flag);
  if (i >= 0 && process.argv[i + 1]) return process.argv[i + 1];
  return fallback;
}

const PORT = Number(process.env.LX_USERAPI_PORT || argVal('--port', '18562')) || 18562;
const BIND = process.env.LX_USERAPI_BIND || '127.0.0.1';
const DEFAULT_API = process.env.LX_DEFAULT_API || 'user_api_101_1770000001000';

function firstExisting(paths) {
  for (const p of paths) {
    if (p && fs.existsSync(p)) return p;
  }
  return '';
}

const USER_API_JSON = firstExisting([
  process.env.LX_USER_API_JSON,
  path.join(__dirname, 'lx_sources', 'user_api.snapshot.json'),
  path.join(process.env.APPDATA || '', 'lx-music-desktop', 'LxDatas', 'user_api.json'),
  path.join(os.homedir(), 'AppData', 'Roaming', 'lx-music-desktop', 'LxDatas', 'user_api.json'),
]);

const QUALITY_ORDER = [
  'master', 'atmos_plus', 'atmos', 'spatial', 'hires', 'flac24bit', '24bit',
  'flac', '320k', '192k', '128k',
];

const nodeCrypto = {
  aesEncrypt(buf, mode, key, iv) {
    const c = crypto.createCipheriv(mode, key, iv);
    return Buffer.concat([c.update(buf), c.final()]);
  },
  rsaEncrypt(buf, key) {
    const b = Buffer.from(buf);
    const padded = Buffer.concat([Buffer.alloc(Math.max(0, 128 - b.length)), b]);
    return crypto.publicEncrypt({ key, padding: crypto.constants.RSA_NO_PADDING }, padded);
  },
  randomBytes: (n) => crypto.randomBytes(n),
  md5: (s) => crypto.createHash('md5').update(typeof s === 'string' ? s : Buffer.from(s)).digest('hex'),
};

function followRequest(url, opts, redirects) {
  return new Promise((resolve) => {
    let u;
    try { u = new URL(url); } catch (e) {
      return resolve({ error: 'bad url' });
    }
    const lib = u.protocol === 'https:' ? https : http;
    const bodyBuf = opts.body ? Buffer.from(opts.body) : null;
    const headers = Object.assign({}, opts.headers || {});
    if (bodyBuf && headers['Content-Length'] == null && headers['content-length'] == null) {
      headers['Content-Length'] = bodyBuf.length;
    }
    const timeout = Math.min(Math.max(Number(opts.timeout) || 15000, 3000), 25000);
    const req = lib.request(url, {
      method: String(opts.method || 'GET').toUpperCase(),
      headers,
      timeout,
    }, (res) => {
      const loc = res.headers.location;
      if (loc && res.statusCode >= 300 && res.statusCode < 400 && (redirects || 0) < 5) {
        res.resume();
        let next = loc;
        try { next = new URL(loc, url).toString(); } catch (e) {}
        return resolve(followRequest(next, Object.assign({}, opts, { method: 'GET', body: null }), (redirects || 0) + 1));
      }
      const chunks = [];
      let stream = res;
      const enc = String(res.headers['content-encoding'] || '').toLowerCase();
      try {
        if (enc === 'gzip') stream = res.pipe(zlib.createGunzip());
        else if (enc === 'deflate') stream = res.pipe(zlib.createInflate());
        else if (enc === 'br') stream = res.pipe(zlib.createBrotliDecompress());
      } catch (e) {}
      stream.on('data', (d) => chunks.push(d));
      const done = () => {
        const raw = Buffer.concat(chunks);
        let body = raw.toString('utf8');
        try { body = JSON.parse(body); } catch (e) {}
        resolve({ statusCode: res.statusCode, headers: res.headers, bytes: raw.length, raw, body });
      };
      stream.on('end', done);
      stream.on('error', (e) => resolve({ error: e.message, statusCode: res.statusCode, headers: res.headers, bytes: 0, body: null }));
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', (e) => resolve({ error: e.message }));
    if (bodyBuf) req.write(bodyBuf);
    req.end();
  });
}

function makeLx(api, script, state) {
  const lx = {
    EVENT_NAMES: { request: 'request', inited: 'inited', updateAlert: 'updateAlert' },
    env: 'desktop',
    version: '2.12.6',
    currentScriptInfo: {
      name: api.name,
      description: api.description || '',
      version: api.version || '1.0.0',
      author: api.author || '',
      homepage: api.homepage || '',
      rawScript: script,
    },
    utils: {
      crypto: nodeCrypto,
      buffer: {
        from: (...a) => Buffer.from(...a),
        bufToString: (b, t) => Buffer.from(b, 'binary').toString(t || 'utf8'),
      },
      zlib: {
        inflate: (b) => new Promise((res, rej) => zlib.inflate(Buffer.from(b), (e, o) => (e ? rej(new Error(e.message)) : res(o)))),
        deflate: (b) => new Promise((res, rej) => zlib.deflate(Buffer.from(b), (e, o) => (e ? rej(new Error(e.message)) : res(o)))),
      },
    },
    request(url, options, cb) {
      const o = options || {};
      let body = o.body;
      let headers = Object.assign({}, o.headers || {});
      if (o.form) {
        body = qs.stringify(o.form);
        if (!headers['Content-Type'] && !headers['content-type']) {
          headers['Content-Type'] = 'application/x-www-form-urlencoded';
        }
      } else if (o.formData) {
        body = typeof o.formData === 'string' ? o.formData : qs.stringify(o.formData);
        if (!headers['Content-Type'] && !headers['content-type']) {
          headers['Content-Type'] = 'application/x-www-form-urlencoded';
        }
      }
      let cancelled = false;
      const p = followRequest(url, { method: o.method, headers, body, timeout: o.timeout }).then((resp) => {
        if (cancelled) return;
        if (typeof cb === 'function') {
          if (resp.error) cb(new Error(resp.error), null, null);
          else cb(null, resp, resp.body);
        }
        return resp;
      });
      if (typeof cb !== 'function') {
        return p.then((resp) => {
          if (resp && resp.error) throw new Error(resp.error);
          return resp;
        });
      }
      return () => { cancelled = true; };
    },
    send(name, data) {
      return new Promise((resolve, reject) => {
        if (name === 'inited' || name === lx.EVENT_NAMES.inited) {
          state.inited = data;
          resolve();
        } else if (name === 'updateAlert' || name === lx.EVENT_NAMES.updateAlert) {
          resolve();
        } else {
          reject(new Error('unsupported event ' + name));
        }
      });
    },
    on(name, fn) {
      if (name === 'request' || name === lx.EVENT_NAMES.request) state.handler = fn;
      return Promise.resolve();
    },
  };
  return lx;
}

function loadApi(api) {
  const script = String(api.script || '');
  const state = {
    id: api.id,
    name: api.name,
    version: api.version || '',
    author: api.author || '',
    description: api.description || '',
    inited: null,
    error: null,
    handler: null,
  };
  const sandbox = {
    console: { log() {}, error() {}, warn() {}, info() {}, debug() {} },
    setTimeout, setInterval, clearTimeout, clearInterval, setImmediate,
    Promise, Buffer, URL, URLSearchParams, atob, btoa, TextEncoder, TextDecoder,
    encodeURIComponent, decodeURIComponent, escape, unescape, queueMicrotask,
    process: { env: {}, version: process.version, platform: process.platform },
  };
  sandbox.global = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.lx = makeLx(api, script, state);
  try {
    vm.runInNewContext(script, vm.createContext(sandbox), { filename: String(api.id || api.name) + '.js', timeout: 12000 });
  } catch (e) {
    state.error = 'load: ' + e.message;
  }
  return state;
}

function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function until(fn, ms) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (fn()) return true;
    await wait(80);
  }
  return fn();
}

function compactSources(inited) {
  const sources = (inited && inited.sources) || {};
  const out = {};
  for (const [k, v] of Object.entries(sources)) {
    out[k] = {
      name: (v && v.name) || k,
      type: (v && v.type) || 'music',
      actions: (v && v.actions) || [],
      qualitys: (v && v.qualitys) || [],
    };
  }
  return out;
}

function qualityChain(requested, available) {
  const avail = Array.isArray(available) ? available.slice() : [];
  const req = String(requested || 'flac').toLowerCase();
  const chain = [];
  const push = (q) => { if (q && !chain.includes(q) && (avail.length === 0 || avail.includes(q))) chain.push(q); };
  push(req);
  const start = QUALITY_ORDER.indexOf(req);
  const seq = start >= 0 ? QUALITY_ORDER.slice(start) : QUALITY_ORDER.slice(QUALITY_ORDER.indexOf('flac'));
  for (const q of seq) push(q);
  if (!chain.length) return avail.slice();
  return chain;
}

function asUrl(out) {
  if (typeof out === 'string') return out.trim();
  if (out && typeof out === 'object') {
    return String(out.url || out.uri || out.src || out.musicUrl || '').trim();
  }
  return '';
}

function clipUrl(u) {
  if (!u) return '';
  const s = String(u);
  const bare = s.split('?')[0];
  return bare.length > 160 ? bare.slice(0, 160) + '…' : bare;
}

function race(p, ms, label) {
  return Promise.race([
    Promise.resolve(p),
    new Promise((_, rej) => setTimeout(() => rej(new Error('timeout ' + (label || ''))), ms)),
  ]);
}

async function probeUrl(url) {
  if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) {
    return { ok: false, reason: 'no url' };
  }
  const r = await followRequest(url, {
    method: 'GET',
    headers: {
      Range: 'bytes=0-2047',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
      Accept: '*/*',
    },
    timeout: 10000,
  });
  if (r.error) return { ok: false, reason: r.error };
  const ct = String((r.headers && (r.headers['content-type'] || r.headers['Content-Type'])) || '');
  const ok = (r.statusCode === 200 || r.statusCode === 206) && (r.bytes || 0) > 400;
  return { ok, status: r.statusCode, contentType: ct, bytes: r.bytes || 0, reason: ok ? '' : ('http ' + r.statusCode + '/' + (r.bytes || 0)) };
}

const APIS = [];
const BY_ID = new Map();

function publicApi(st) {
  return {
    id: st.id,
    name: st.name,
    version: st.version,
    author: st.author,
    description: st.description,
    ready: !!(st.inited && typeof st.handler === 'function'),
    error: st.error || null,
    sources: compactSources(st.inited),
    default: st.id === DEFAULT_API,
  };
}

async function boot() {
  if (!USER_API_JSON) {
    console.error(JSON.stringify({ event: 'boot', ok: false, error: 'user_api.json not found' }));
    process.exit(2);
  }
  const raw = fs.readFileSync(USER_API_JSON, 'utf8');
  const data = JSON.parse(raw);
  const list = data.userApis || data || [];
  for (const api of list) {
    const st = loadApi(api);
    await until(() => !!(st.inited || st.error), 10000);
    if (!st.inited && !st.error) st.error = 'no init payload';
    APIS.push(st);
    BY_ID.set(st.id, st);
    console.log(JSON.stringify({
      event: 'loaded',
      id: st.id,
      name: st.name,
      ready: !!(st.inited && st.handler),
      error: st.error || null,
      sources: Object.keys(compactSources(st.inited)),
    }));
  }
}

async function callMusicUrl(st, source, quality, musicInfo, timeoutMs) {
  if (!st || typeof st.handler !== 'function') throw new Error('handler missing');
  const sources = compactSources(st.inited);
  if (source && sources[source] && !(sources[source].actions || []).includes('musicUrl')) {
    throw new Error('api does not support musicUrl on ' + source);
  }
  const out = await race(st.handler({
    source,
    action: 'musicUrl',
    info: { type: quality, musicInfo: musicInfo || {} },
  }), timeoutMs || 14000, (st.name || st.id) + ' ' + source + quality);
  const url = asUrl(out);
  if (!url) throw new Error('empty url');
  if (!/^https?:\/\//i.test(url)) throw new Error('non-http url');
  return url;
}

async function handleMusicUrl(body) {
  const source = String(body.source || body.platform || '').trim();
  const quality = String(body.quality || 'flac').trim() || 'flac';
  const musicInfo = body.musicInfo || body.music_info || {};
  const wantProbe = body.probe !== false;
  let apiId = String(body.apiId || body.api_id || 'auto').trim() || 'auto';
  if (!source) return { ok: false, error: 'missing source' };

  const selected = apiId !== 'auto' ? APIS.filter((s) => s.id === apiId) : [];
  const preferred = APIS.filter((s) => s.id === DEFAULT_API);
  const rest = APIS.filter((s) => s.id !== DEFAULT_API);
  const queue = (selected.length ? selected : preferred.concat(rest)).filter((st) => {
    if (!(st.inited && typeof st.handler === 'function')) return false;
    const srcs = compactSources(st.inited);
    const meta = srcs[source];
    return !!(meta && (meta.actions || []).includes('musicUrl'));
  });
  if (!queue.length) {
    return { ok: false, error: 'no installed 音源 supports ' + source, apiId };
  }

  const tried = [];
  if (apiId !== 'auto' && queue.length === 1) {
    const st = queue[0];
    const quals = qualityChain(quality, (compactSources(st.inited)[source] || {}).qualitys);
    for (const q of quals) {
      try {
        const url = await callMusicUrl(st, source, q, musicInfo, 14000);
        const pr = wantProbe ? await probeUrl(url) : { ok: true };
        tried.push({ apiId: st.id, apiName: st.name, quality: q, url: clipUrl(url), ok: !!pr.ok, reason: pr.reason || '' });
        if (pr.ok) {
          return { ok: true, apiId: st.id, apiName: st.name, source, quality: q, url, contentType: pr.contentType || '', tried };
        }
      } catch (e) {
        tried.push({ apiId: st.id, apiName: st.name, quality: q, ok: false, reason: e.message });
      }
    }
    return { ok: false, error: 'selected 音源 failed', apiId, source, tried };
  }

  // auto: try requested quality across all APIs in parallel, then fall back
  const rounds = [quality];
  for (const q of qualityChain(quality, QUALITY_ORDER)) {
    if (!rounds.includes(q)) rounds.push(q);
    if (rounds.length >= 3) break;
  }
  for (const q of rounds) {
    const hit = await new Promise((resolve) => {
      let pending = queue.length;
      let settled = false;
      if (!pending) return resolve(null);
      for (const st of queue) {
        const avail = (compactSources(st.inited)[source] || {}).qualitys || [];
        const useQ = avail.includes(q) ? q : (qualityChain(q, avail)[0] || q);
        Promise.resolve().then(async () => {
          try {
            const url = await callMusicUrl(st, source, useQ, musicInfo, 14000);
            const pr = wantProbe ? await probeUrl(url) : { ok: true };
            tried.push({ apiId: st.id, apiName: st.name, quality: useQ, url: clipUrl(url), ok: !!(pr && pr.ok), reason: (pr && pr.reason) || '' });
            if (!settled && url && pr && pr.ok) { settled = true; resolve({ st, q: useQ, url, pr }); }
          } catch (e) {
            tried.push({ apiId: st.id, apiName: st.name, quality: useQ, ok: false, reason: e.message });
          } finally {
            pending -= 1;
            if (pending <= 0 && !settled) resolve(null);
          }
        });
      }
    });
    if (hit) {
      return {
        ok: true, apiId: hit.st.id, apiName: hit.st.name, source, quality: hit.q,
        url: hit.url, contentType: hit.pr.contentType || '', tried,
      };
    }
  }
  return { ok: false, error: 'all LX 音源 failed for ' + source, source, tried };
}

async function handleSearch(body) {
  const apiId = String(body.apiId || body.api_id || '').trim();
  const source = String(body.source || '').trim();
  const keyword = String(body.keyword || body.query || body.text || '').trim();
  if (!keyword) return { ok: false, error: 'missing keyword' };
  const cands = (apiId ? APIS.filter((s) => s.id === apiId) : APIS).filter((st) => {
    if (!(st.inited && typeof st.handler === 'function')) return false;
    const meta = compactSources(st.inited)[source];
    const actions = (meta && meta.actions) || [];
    return actions.includes('search') || actions.includes('musicSearch');
  });
  if (!cands.length) return { ok: false, error: 'no 音源 supports search on ' + (source || '?') };
  const st = cands[0];
  const meta = compactSources(st.inited)[source] || {};
  const action = (meta.actions || []).includes('musicSearch') ? 'musicSearch' : 'search';
  try {
    const out = await race(st.handler({
      source,
      action,
      info: {
        keyword, text: keyword, query: keyword,
        type: body.type || 'music',
        page: Number(body.page || 1) || 1,
        limit: Number(body.limit || 20) || 20,
      },
    }), 14000, 'search');
    return { ok: true, apiId: st.id, apiName: st.name, source, action, result: out };
  } catch (e) {
    return { ok: false, error: e.message, apiId: st.id, apiName: st.name };
  }
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let n = 0;
    req.on('data', (c) => {
      n += c.length;
      if (n > 2 * 1024 * 1024) {
        reject(new Error('body too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8') || '{}';
      try { resolve(JSON.parse(raw)); } catch (e) { reject(new Error('bad json')); }
    });
    req.on('error', reject);
  });
}

function send(res, code, obj) {
  const raw = Buffer.from(JSON.stringify(obj), 'utf8');
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': raw.length,
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': 'http://127.0.0.1',
  });
  res.end(raw);
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': 'http://127.0.0.1',
      'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    return res.end();
  }
  const u = new URL(req.url, 'http://127.0.0.1');
  try {
    if (req.method === 'GET' && (u.pathname === '/health' || u.pathname === '/')) {
      return send(res, 200, {
        ok: true, service: 'lx-userapi-host', port: PORT,
        userApiJson: USER_API_JSON, apis: APIS.map(publicApi),
      });
    }
    if (req.method === 'GET' && (u.pathname === '/apis' || u.pathname === '/sources')) {
      return send(res, 200, { ok: true, defaultApi: DEFAULT_API, apis: APIS.map(publicApi) });
    }
    if (req.method === 'POST' && (u.pathname === '/musicUrl' || u.pathname === '/music_url')) {
      const body = await readJson(req);
      const out = await handleMusicUrl(body);
      return send(res, out.ok ? 200 : 422, out);
    }
    if (req.method === 'POST' && u.pathname === '/search') {
      const body = await readJson(req);
      const out = await handleSearch(body);
      return send(res, out.ok ? 200 : 422, out);
    }
    send(res, 404, { ok: false, error: 'not found' });
  } catch (e) {
    send(res, 500, { ok: false, error: e.message });
  }
});

(async () => {
  await boot();
  server.listen(PORT, BIND, () => {
    console.log(JSON.stringify({
      event: 'listen', ok: true, bind: BIND, port: PORT,
      apis: APIS.length, ready: APIS.filter((s) => s.inited && s.handler).length,
      userApiJson: USER_API_JSON,
    }));
  });
})().catch((e) => {
  console.error(JSON.stringify({ event: 'fatal', error: e.message }));
  process.exit(1);
});
