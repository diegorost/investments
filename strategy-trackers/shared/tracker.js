/* Strategy tracker: one script for both pages.  The page sets window.TRACKER_CONFIG
   (strategy key, name, sell rule, the 17 pairs with their enabled flag and first
   tier, seed trades) and data/prices.js sets window.TRACKER_PRICES.  Everything the
   user enters (trades, settings, cash flows, manual price overrides) lives in
   localStorage under one key per strategy and can be exported / imported as JSON.
   Decision support only: nothing here talks to a broker. */
(function () {
  'use strict';
  const CFG = window.TRACKER_CONFIG;
  const STORE_KEY = 'strategy_tracker:' + CFG.key;
  const STEP = 5;              // every rung is 5 percentage points deeper
  const MAX_RUNGS = 16;        // BUY LEVELS!H6:H21 in the workbooks
  const API_BASE = (location.protocol === 'file:' || ['localhost', '127.0.0.1'].includes(location.hostname))
    ? 'http://localhost:8787'
    : 'https://strategy-trackers-api.diegointheworks.workers.dev';

  /* ---------- state ---------- */
  function defaultState() {
    const pairs = {};
    CFG.pairs.forEach(p => { pairs[p.etf] = { enabled: !!p.enabled, tier1: p.tier1, paused: false }; });
    return {
      version: 1,
      settings: { startingCash: 0, referenceLot: 2000, allocationCap: null, rungCount: MAX_RUNGS },
      pairs,
      trades: (CFG.seedTrades || []).map((t, i) => Object.assign({ id: 'seed' + i }, t)),
      cashFlows: [],
      overrides: {},
      ui: { tab: 'start' },
    };
  }
  function load() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (!raw) return defaultState();
      const s = JSON.parse(raw);
      const d = defaultState();
      // tolerate older saves: fill in anything missing, add pairs that are new
      s.settings = Object.assign(d.settings, s.settings || {});
      s.pairs = Object.assign(d.pairs, s.pairs || {});
      s.trades = s.trades || []; s.cashFlows = s.cashFlows || []; s.overrides = s.overrides || {};
      s.ui = Object.assign(d.ui, s.ui || {});
      return s;
    } catch (e) { console.warn('state load failed, starting fresh', e); return defaultState(); }
  }
  let S = load();
  function save() { try { localStorage.setItem(STORE_KEY, JSON.stringify(S)); } catch (e) { toast('Could not save to this browser’s storage: ' + e.message, 'bad'); } }
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

  /* ---------- helpers ---------- */
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = v => { const n = parseFloat(v); return isFinite(n) ? n : null; };
  const fmt$ = v => v == null ? '—' : (v < 0 ? '−$' : '$') + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtP = (v, d) => v == null ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: d == null ? 2 : d, maximumFractionDigits: d == null ? 2 : d });
  const fmtPct = v => v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%';
  const todayISO = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
  function toast(msg, kind) {
    const t = $('#toast'); t.textContent = msg; t.className = 'toast show ' + (kind || '');
    clearTimeout(toast._t); toast._t = setTimeout(() => t.className = 'toast', 3500);
  }

  /* Last completed regular US session, approximate (weekdays only; holidays are
     not known here, so a quote one session older on a holiday week is flagged
     even though it is current).  New York time via Intl. */
  function lastCompletedSession() {
    const now = new Date();
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', weekday: 'short' }).formatToParts(now);
    const g = k => parts.find(p => p.type === k).value;
    let d = new Date(Date.UTC(+g('year'), +g('month') - 1, +g('day')));
    const hour = +g('hour') % 24, min = +g('minute');
    const closed = hour > 16 || (hour === 16 && min >= 0);
    let dow = d.getUTCDay();
    if (!(closed && dow >= 1 && dow <= 5)) d.setUTCDate(d.getUTCDate() - 1);
    while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() - 1);
    return d.toISOString().slice(0, 10);
  }

  /* ---------- market data ---------- */
  function priceRows() {
    const P = window.TRACKER_PRICES;
    const byEtf = {};
    if (P && Array.isArray(P.rows)) P.rows.forEach(r => byEtf[r.etf] = r);
    return byEtf;
  }
  function dataFor(etf) {
    const base = priceRows()[etf] || {};
    const ov = S.overrides[etf] || {};
    const d = Object.assign({}, base);
    let overridden = [];
    ['und_close', 'und_date', 'ath', 'ath_prior', 'prev_month_high', 'etf_close'].forEach(k => {
      if (ov[k] != null && ov[k] !== '') { d[k] = ov[k]; overridden.push(k); }
    });
    d.overridden = overridden;
    return d;
  }

  /* ---------- the model ---------- */
  function rungsFor(etf) {
    const p = S.pairs[etf]; const out = [];
    for (let i = 0; i < (S.settings.rungCount || MAX_RUNGS); i++) {
      const r = p.tier1 + i * STEP; if (r >= 100) break; out.push(r);
    }
    return out;
  }
  function sortedTrades(etf) {
    return S.trades.filter(t => !etf || t.etf === etf)
      .map((t, i) => Object.assign({ _i: i }, t))
      .sort((a, b) => (a.date || '').localeCompare(b.date || '') || a._i - b._i);
  }
  /* Walk one ETF's trades: running shares, cycle number (a sale to zero shares
     starts the next cycle; a new month or a partial sale does not), the rungs
     used in the current cycle, invested cost in the current cycle. */
  function book(etf) {
    let shares = 0, cycle = 1, used = new Set(), invested = 0, cost = 0;
    const rows = [];
    sortedTrades(etf).forEach(t => {
      const sh = num(t.shares) || 0, px = num(t.price) || 0, fee = num(t.fees) || 0;
      const gross = sh * px;
      let cashChange, shareChange;
      if (t.side === 'BUY') { cashChange = -(gross + fee); shareChange = sh; if (t.level != null) used.add(num(t.level)); invested += gross + fee; cost += gross + fee; }
      else { cashChange = gross - fee; shareChange = -sh; invested -= gross - fee; cost = shares > 0 ? cost * Math.max(0, (shares - sh)) / shares : 0; }
      const before = shares; shares += shareChange;
      rows.push(Object.assign({}, t, { cycleKey: etf + '-C' + cycle, cashChange, shareChange, gross, sharesAfter: shares, sharesBefore: before }));
      if (t.side === 'SELL' && shares <= 0) { cycle += 1; used = new Set(); invested = 0; cost = 0; shares = Math.max(0, shares); }
    });
    return { shares, cycle, used, invested, cost, rows };
  }
  function evalPair(etf) {
    const pcfg = CFG.pairs.find(p => p.etf === etf);
    const p = S.pairs[etf], d = dataFor(etf), b = book(etf), rungs = rungsFor(etf);
    const sellRef = CFG.sellRule === 'ath' ? d.ath_prior : d.prev_month_high;
    const valid = d.und_close != null && d.ath != null && d.ath > 0 && sellRef != null && d.etf_close != null;
    const drop = valid ? (d.und_close / d.ath - 1) * 100 : null;
    const depth = drop == null ? null : -drop;
    const reached = rungs.filter(r => depth != null && depth >= r);
    const levelReached = reached.length ? reached[reached.length - 1] : null;
    const unused = rungs.filter(r => !b.used.has(r));
    const lowestUnused = unused.length ? unused[0] : null;
    const newReady = reached.filter(r => !b.used.has(r)).length;
    const inZone = valid && depth >= p.tier1;
    const sellHit = valid && b.shares > 0 && d.und_close >= sellRef;
    const stale = d.und_date && d.und_date < lastCompletedSession();
    let action, why;
    if (!p.enabled) { action = 'WAIT'; why = 'Not enabled in this strategy'; }
    else if (p.paused) { action = 'WAIT'; why = 'Paused in SETTINGS'; }
    else if (!valid) { action = 'CHECK DATA'; why = 'Price data missing or invalid: do not trade from this row'; }
    else if (sellHit) { action = 'SELL ALL'; why = `${d.und_close >= sellRef ? pcfg.und + ' close ' + fmtP(d.und_close) + ' ≥ sell reference ' + fmtP(sellRef) : ''} with ${b.shares} tracked shares`; }
    else if (inZone) { action = 'CONSIDER BUYING'; why = `${pcfg.und} is ${fmtPct(drop)} from ATH, inside the buying zone (starts at ${p.tier1}%)`; }
    else { action = 'WAIT'; why = `${pcfg.und} is ${fmtPct(drop)} from ATH; buying zone starts at −${p.tier1}%`; }
    const cap = S.settings.allocationCap;
    const overCap = cap != null && cap > 0 && (b.invested + (S.settings.referenceLot || 0)) > cap;
    const ladder = rungs.map(r => {
      let st;
      if (!p.enabled) st = 'DISABLED'; else if (p.paused) st = 'PAUSED'; else if (!valid) st = 'NO DATA';
      else if (depth >= r) st = b.used.has(r) ? 'USED' : overCap ? 'OVER CAP' : 'BUY'; else st = 'WAIT';
      return { rung: r, status: st, used: b.used.has(r), reached: depth != null && depth >= r, triggerPrice: d.ath ? d.ath * (1 - r / 100) : null };
    });
    const estValue = b.shares > 0 && d.etf_close != null ? b.shares * d.etf_close : 0;
    return { etf, und: pcfg.und, p, d, b, rungs, sellRef, valid, drop, depth, levelReached, lowestUnused, newReady, inZone, sellHit, stale, action, why, ladder, overCap, estValue, unrealized: b.shares > 0 ? estValue - b.cost : null };
  }
  function evalAll() { return CFG.pairs.map(p => evalPair(p.etf)); }
  function trackedCash() {
    let c = num(S.settings.startingCash) || 0;
    S.cashFlows.forEach(f => c += num(f.amount) || 0);
    S.trades.forEach(t => { const g = (num(t.shares) || 0) * (num(t.price) || 0), f = num(t.fees) || 0; c += t.side === 'BUY' ? -(g + f) : (g - f); });
    return c;
  }
  function entryCheck(t) {
    const miss = [];
    if (!t.date) miss.push('date'); if (!t.etf) miss.push('ticker'); if (!t.side) miss.push('BUY/SELL');
    if (num(t.price) == null || num(t.price) <= 0) miss.push('fill price');
    if (num(t.shares) == null || num(t.shares) <= 0) miss.push('shares');
    if (miss.length) return { ok: false, text: 'MISSING: ' + miss.join(', ') };
    if (t.side === 'BUY' && num(t.level) == null) return { ok: false, text: 'MISSING BUY LEVEL %' };
    if (t.etf && !S.pairs[t.etf]) return { ok: false, text: 'UNKNOWN TICKER' };
    const notes = [];
    if (t.etf && !S.pairs[t.etf].enabled) notes.push('ticker not enabled in this strategy');
    if (t.side === 'SELL' && num(t.level) != null) notes.push('level ignored on a SELL');
    if (t.side === 'BUY' && !rungsFor(t.etf).includes(num(t.level))) notes.push('level is not a configured rung');
    return { ok: true, text: notes.length ? 'OK — ' + notes.join('; ') : 'OK' };
  }

  /* ---------- rendering ---------- */
  const ACTION_CLASS = { 'CONSIDER BUYING': 'buy', 'SELL ALL': 'sell', 'WAIT': 'wait', 'CHECK DATA': 'check' };
  const ACTION_ICON = { 'CONSIDER BUYING': '▲', 'SELL ALL': '▼', 'WAIT': '•', 'CHECK DATA': '!' };
  const pill = a => `<span class="pill ${ACTION_CLASS[a] || 'wait'}"><span class="ico">${ACTION_ICON[a] || ''}</span>${esc(a)}</span>`;
  const LADDER_CLASS = { BUY: 'buy', USED: 'used', WAIT: 'wait', PAUSED: 'off', DISABLED: 'off', 'NO DATA': 'check', 'OVER CAP': 'check' };

  function renderHeader() {
    const P = window.TRACKER_PRICES || {};
    const last = lastCompletedSession();
    const rows = evalAll();
    const dates = rows.map(r => r.d.und_date).filter(Boolean);
    const newest = dates.length ? dates.sort().slice(-1)[0] : null;
    const staleN = rows.filter(r => r.p.enabled && r.stale).length;
    const nodata = !P.rows;
    let cls = 'ok', msg;
    if (nodata) { cls = 'bad'; msg = 'No price data loaded yet. Click Refresh prices above, or check FEED CHECK to enter manual prices meanwhile.'; }
    else if (staleN) { cls = 'warn'; msg = `Quotes dated ${esc(newest)}; the last completed US session is about ${last} (weekday rule, holidays not known). ${staleN} enabled row${staleN > 1 ? 's' : ''} look stale — click Refresh prices before acting.`; }
    else msg = `Quotes dated ${esc(newest)} (last completed session ${last}). Fetched ${esc((P.generated_at || '').replace('T', ' ').slice(0, 19))} UTC.`;
    $('#feedbar').className = 'feedbar ' + cls;
    $('#feedbar').innerHTML = msg;
  }

  function renderStart() {
    const rows = evalAll();
    const enabled = rows.filter(r => r.p.enabled), disabled = rows.filter(r => !r.p.enabled);
    const cash = trackedCash();
    const tr = r => `<tr class="${r.p.enabled ? '' : 'dim'} ${ACTION_CLASS[r.action]}-row">
      <td class="t"><b>${esc(r.etf)}</b></td><td class="t">${esc(r.und)}</td>
      <td class="n">${r.d.und_close != null ? fmtP(r.d.und_close) : '—'}</td>
      <td class="n" title="${CFG.sellRule === 'ath' ? 'ATH before the latest session' : 'Previous completed month (' + esc(r.d.prev_month || '') + ') intraday high'}">${r.sellRef != null ? fmtP(r.sellRef) : '—'}</td>
      <td class="n">${r.b.shares || 0}</td>
      <td class="n">${r.d.etf_close != null ? fmtP(r.d.etf_close) : '—'}</td>
      <td class="action">${pill(r.action)}<div class="why">${esc(r.why)}</div></td>
      <td class="n ${r.drop != null && r.drop <= -r.p.tier1 ? 'deep' : ''}">${fmtPct(r.drop)}</td>
      <td class="n">${r.levelReached != null ? r.levelReached + '%' : '—'}</td>
      <td class="n">${r.lowestUnused != null ? r.lowestUnused + '%' + (r.depth != null && r.depth >= r.lowestUnused ? '' : ' <span class="muted">(not reached)</span>') : '—'}</td>
      <td class="n">${fmt$(r.estValue)}</td>
      <td class="t small">${r.p.enabled ? (r.valid ? (r.d.overridden.length ? 'manual: ' + r.d.overridden.join(', ') : 'feed ' + esc(r.d.status || 'OK')) : 'invalid / missing') : 'disabled'}${r.stale ? ' <span class="warnmark">stale</span>' : ''}</td>
      <td class="t small">${esc(r.d.und_date || '—')}</td>
      <td class="n">${r.newReady}</td>
      <td class="n muted">${fmt$(S.settings.referenceLot)}</td></tr>`;
    $('#start-body').innerHTML = enabled.map(tr).join('') + (disabled.length ? `<tr class="sep"><td colspan="15">Disabled reference rows (belong to ${CFG.key === 'A' ? 'Strategy B' : 'Strategy A'}; not tradable here)</td></tr>` + disabled.map(tr).join('') : '');
    $('#start-cash').textContent = fmt$(cash);
    $('#start-cash').className = cash < 0 ? 'neg' : '';
  }

  function renderDashboard() {
    const rows = evalAll().filter(r => r.p.enabled);
    const cash = trackedCash();
    const held = rows.filter(r => r.b.shares > 0);
    const mv = held.reduce((a, r) => a + r.estValue, 0);
    const cost = held.reduce((a, r) => a + r.b.cost, 0);
    const tiles = [
      ['Tracked cash', fmt$(cash), cash < 0 ? 'negative until allocated cash is recorded' : 'starting cash + flows + trades'],
      ['Positions', String(held.length), held.map(r => r.etf + ' ' + r.b.shares).join(', ') || 'no tracked shares'],
      ['Market value', fmt$(mv), 'tracked shares x ETF close'],
      ['Unrealised P/L', fmt$(mv - cost), 'vs cost incl. fees, open cycle'],
      ['In buying zone', String(rows.filter(r => r.action === 'CONSIDER BUYING').length), 'of ' + rows.length + ' enabled'],
      ['Sell alerts', String(rows.filter(r => r.action === 'SELL ALL').length), 'underlying close ≥ sell reference'],
    ];
    $('#tiles').innerHTML = tiles.map(t => `<div class="tile"><div class="k">${esc(t[0])}</div><div class="v">${esc(t[1])}</div><div class="s">${esc(t[2])}</div></div>`).join('');
    const maxDepth = Math.max(60, ...rows.map(r => Math.max(r.depth || 0, r.rungs[Math.min(5, r.rungs.length - 1)] || 0))) + 5;
    $('#ladders').innerHTML = rows.map(r => {
      const w = v => (Math.min(v, maxDepth) / maxDepth * 100).toFixed(2) + '%';
      const ticks = r.rungs.filter(x => x <= maxDepth).map(x => `<span class="tick ${r.depth != null && r.depth >= x ? (r.b.used.has(x) ? 'used' : 'hit') : ''}" style="left:${w(x)}" title="${x}% rung ${r.b.used.has(x) ? '(used this cycle)' : r.depth != null && r.depth >= x ? '(reached)' : ''}"><i></i><em>${x}</em></span>`).join('');
      const sellPct = r.valid && r.d.ath ? (1 - r.sellRef / r.d.ath) * 100 : null;
      return `<div class="lad">
        <div class="lad-head"><b>${esc(r.etf)}</b> <span class="muted">${esc(r.und)}</span> ${pill(r.action)}
          <span class="lad-nums">${fmtPct(r.drop)} from ATH ${r.d.ath ? '(' + fmtP(r.d.ath) + ' on ' + esc(r.d.ath_date || '') + ')' : ''} · sell ref ${r.sellRef != null ? fmtP(r.sellRef) : '—'}${sellPct != null ? ' (' + fmtPct(-sellPct) + ' from ATH)' : ''} · shares ${r.b.shares}</span></div>
        <div class="bar" title="Underlying drawdown from ATH; ticks are the buying rungs">
          <div class="fill ${r.inZone ? 'zone' : ''}" style="width:${r.depth != null ? w(r.depth) : 0}"></div>
          ${sellPct != null && sellPct > 0 ? `<span class="sellmark" style="left:${w(sellPct)}" title="sell reference ${fmtP(r.sellRef)}"></span>` : ''}
          ${ticks}
        </div></div>`;
    }).join('');
  }

  function renderSettings() {
    const s = S.settings;
    $('#set-startcash').value = s.startingCash; $('#set-lot').value = s.referenceLot;
    $('#set-cap').value = s.allocationCap == null ? '' : s.allocationCap; $('#set-rungs').value = s.rungCount;
    $('#pairs-body').innerHTML = CFG.pairs.map(p => { const st = S.pairs[p.etf]; return `<tr class="${st.enabled ? '' : 'dim'}">
      <td class="t"><b>${esc(p.etf)}</b></td><td class="t">${esc(p.und)}</td>
      <td><input type="checkbox" data-pair="${p.etf}" data-k="enabled" ${st.enabled ? 'checked' : ''}></td>
      <td><input type="checkbox" data-pair="${p.etf}" data-k="paused" ${st.paused ? 'checked' : ''}></td>
      <td><input type="number" class="inp short" data-pair="${p.etf}" data-k="tier1" value="${st.tier1}" min="1" max="95" step="1"> %</td>
      <td class="t small">${rungsFor(p.etf).map(r => r + '%').join(', ')}</td>
      <td class="t small muted">${esc(p.note || '')}</td></tr>`; }).join('');
    $('#flows-body').innerHTML = S.cashFlows.length ? S.cashFlows.map(f => `<tr><td class="t">${esc(f.date)}</td><td class="n">${fmt$(num(f.amount))}</td><td class="t">${esc(f.note)}</td><td><button class="btn tiny danger" data-del-flow="${f.id}">delete</button></td></tr>`).join('') : '<tr><td colspan="4" class="muted">No cash flows recorded. Starting cash is the only allocation.</td></tr>';
  }

  function renderTrades() {
    const sel = $('#tr-etf');
    const cur = sel.value;
    sel.innerHTML = CFG.pairs.map(p => `<option value="${p.etf}" ${S.pairs[p.etf].enabled ? '' : 'class="dim"'}>${p.etf} / ${p.und}${S.pairs[p.etf].enabled ? '' : ' (not enabled here)'}</option>`).join('');
    if (cur && S.pairs[cur]) sel.value = cur; else { const first = CFG.pairs.find(p => S.pairs[p.etf].enabled); if (first) sel.value = first.etf; }
    refreshLevelOptions();
    if (!$('#tr-date').value) $('#tr-date').value = todayISO();
    const all = sortedTrades().map(t => { const b = book(t.etf); const row = b.rows.find(r => r.id === t.id) || {}; return Object.assign({}, t, row); })
      .sort((a, b) => (b.date || '').localeCompare(a.date || '') || b._i - a._i);
    $('#trades-body').innerHTML = all.length ? all.map(t => { const c = entryCheck(t); return `<tr class="${t.side === 'BUY' ? 'buy-row' : 'sell-row'}">
      <td class="t">${esc(t.date)}</td><td class="t"><b>${esc(t.etf)}</b></td><td class="t">${esc(t.side)}</td>
      <td class="t small">${esc(t.cycleKey)}</td><td class="n">${t.side === 'BUY' && num(t.level) != null ? num(t.level) + '%' : ''}</td>
      <td class="n">${fmtP(num(t.price), 4)}</td><td class="n">${esc(t.shares)}</td><td class="n">${fmt$(num(t.fees) || 0)}</td>
      <td class="n ${t.cashChange < 0 ? 'neg' : 'pos'}">${fmt$(t.cashChange)}</td><td class="n">${t.shareChange > 0 ? '+' : ''}${esc(t.shareChange)}</td><td class="n">${fmt$(t.gross)}</td>
      <td class="t small">${esc(t.note)}</td>
      <td class="t small ${c.ok ? 'ok' : 'bad'}">${esc(c.text)}</td>
      <td class="nowrap"><button class="btn tiny" data-edit="${t.id}">edit</button> <button class="btn tiny danger" data-del="${t.id}">delete</button></td></tr>`; }).join('')
      : '<tr><td colspan="14" class="muted">No trades recorded. Only confirmed broker fills belong here.</td></tr>';
    const cash = trackedCash();
    $('#tr-cash').textContent = fmt$(cash); $('#tr-cash').className = cash < 0 ? 'neg' : '';
    $('#tr-held').textContent = CFG.pairs.map(p => ({ e: p.etf, s: book(p.etf).shares })).filter(x => x.s).map(x => x.e + ' ' + x.s).join(', ') || 'none';
  }
  function refreshLevelOptions() {
    const etf = $('#tr-etf').value; const lvl = $('#tr-level'); const side = $('#tr-side').value;
    if (!etf || !S.pairs[etf]) { lvl.innerHTML = ''; return; }
    const r = evalPair(etf); const prev = lvl.value;
    lvl.innerHTML = '<option value="">— (SELL)</option>' + r.rungs.map(x => `<option value="${x}">${x}%${r.depth != null && r.depth >= x ? ' — reached' : ''}${r.b.used.has(x) ? ' (used this cycle, repeat allowed)' : ''}</option>`).join('');
    if (side === 'SELL') lvl.value = ''; else if (prev && r.rungs.includes(num(prev))) lvl.value = prev; else lvl.value = r.levelReached != null ? String(r.levelReached) : '';
    lvl.disabled = side === 'SELL';
    const hint = $('#tr-hint');
    hint.innerHTML = r.valid ? `${esc(r.und)} ${fmtPct(r.drop)} from ATH · level reached ${r.levelReached != null ? r.levelReached + '%' : 'none'} · ${esc(r.etf)} close ${fmtP(r.d.etf_close)} · tracked shares ${r.b.shares} · ${pill(r.action)}` : 'No valid price data for this pair.';
    if (!$('#tr-price').value && r.d.etf_close != null) $('#tr-price').placeholder = 'e.g. ' + fmtP(r.d.etf_close);
  }

  function renderLevels() {
    const rows = evalAll();
    $('#levels-body').innerHTML = rows.map(r => `<div class="lvl ${r.p.enabled ? '' : 'dim'}">
      <div class="lvl-head"><b>${esc(r.etf)}</b> <span class="muted">${esc(r.und)}</span> ${pill(r.action)}
        <span class="muted small">cycle ${r.b.cycle} · used ${r.b.used.size} rung${r.b.used.size === 1 ? '' : 's'} · new levels ready ${r.newReady} · lowest unused ${r.lowestUnused != null ? r.lowestUnused + '%' : '—'}${r.overCap ? ' · over allocation cap' : ''}</span></div>
      <div class="rungs">${r.ladder.map(l => `<div class="rung ${LADDER_CLASS[l.status]}" title="${l.rung}% below ATH${l.triggerPrice ? ' = ' + esc(r.und) + ' ' + fmtP(l.triggerPrice) : ''}"><div class="rp">${l.rung}%</div><div class="rs">${esc(l.status)}</div><div class="rt">${l.triggerPrice ? fmtP(l.triggerPrice) : ''}</div></div>`).join('')}</div></div>`).join('');
  }

  function renderFeed() {
    const P = window.TRACKER_PRICES || {};
    $('#feed-meta').innerHTML = P.rows ? `File written <b>${esc((P.generated_at || '').replace('T', ' '))}</b> · ${esc(P.source || '')} · ${P.rows.length} pairs` : 'No data file loaded (data/prices.js missing or failed to parse).';
    const rows = evalAll();
    $('#feed-body').innerHTML = rows.map(r => { const d = r.d, ov = S.overrides[r.etf] || {}; const inp = (k, step) => `<input type="number" class="inp short" data-ov="${r.etf}" data-k="${k}" step="${step || 'any'}" value="${ov[k] != null ? ov[k] : ''}" placeholder="${(priceRows()[r.etf] || {})[k] != null ? (priceRows()[r.etf] || {})[k] : ''}">`;
      return `<tr class="${r.p.enabled ? '' : 'dim'}"><td class="t"><b>${esc(r.etf)}</b></td><td class="t">${esc(r.und)}</td>
      <td class="t ${d.status === 'OK' ? 'ok' : 'bad'}">${esc(d.status || 'MISSING')}${r.stale ? ' <span class="warnmark">stale</span>' : ''}</td>
      <td class="t small">${esc(d.und_date || '')}</td><td>${inp('und_close')}</td><td>${inp('ath')}</td><td class="t small">${esc(d.ath_date || '')}</td>
      <td>${inp('ath_prior')}</td><td>${inp('prev_month_high')} <span class="muted small">${esc(d.prev_month || '')}</span></td>
      <td>${inp('etf_close')}</td><td class="t small">${esc(d.etf_date || '')}</td><td class="t small">${esc(d.note || '')}</td>
      <td>${r.d.overridden.length ? `<button class="btn tiny" data-clear-ov="${r.etf}">clear manual</button>` : ''}</td></tr>`; }).join('');
  }

  function renderAll() {
    renderHeader();
    const tab = S.ui.tab || 'start';
    $$('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    $$('.panel').forEach(p => p.classList.toggle('show', p.id === 'panel-' + tab));
    ({ start: renderStart, dashboard: renderDashboard, settings: renderSettings, trades: renderTrades, levels: renderLevels, feed: renderFeed, rules: () => {} })[tab]();
  }

  /* ---------- events ---------- */
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-tab]'); if (t) { S.ui.tab = t.dataset.tab; save(); renderAll(); return; }
    const del = e.target.closest('[data-del]');
    if (del) { if (del.dataset.armed) { S.trades = S.trades.filter(x => x.id !== del.dataset.del); save(); renderAll(); toast('Trade deleted'); } else { del.dataset.armed = '1'; del.textContent = 'click again to delete'; setTimeout(() => { delete del.dataset.armed; del.textContent = 'delete'; }, 3000); } return; }
    const ed = e.target.closest('[data-edit]');
    if (ed) { const tr = S.trades.find(x => x.id === ed.dataset.edit); if (!tr) return; $('#tr-id').value = tr.id; $('#tr-date').value = tr.date; $('#tr-etf').value = tr.etf; $('#tr-side').value = tr.side; refreshLevelOptions(); $('#tr-level').value = tr.level == null ? '' : String(tr.level); $('#tr-price').value = tr.price; $('#tr-shares').value = tr.shares; $('#tr-fees').value = tr.fees; $('#tr-note').value = tr.note || ''; $('#tr-submit').textContent = 'Save changes'; $('#tr-cancel').style.display = ''; $('#tr-form').scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
    const df = e.target.closest('[data-del-flow]'); if (df) { S.cashFlows = S.cashFlows.filter(x => x.id !== df.dataset.delFlow); save(); renderAll(); return; }
    const co = e.target.closest('[data-clear-ov]'); if (co) { delete S.overrides[co.dataset.clearOv]; save(); renderAll(); toast('Manual prices cleared for ' + co.dataset.clearOv); return; }
  });
  document.addEventListener('change', e => {
    const el = e.target;
    if (el.dataset.pair) { const p = S.pairs[el.dataset.pair]; if (el.type === 'checkbox') p[el.dataset.k] = el.checked; else { const v = num(el.value); if (v != null && v >= 1 && v < 100) p.tier1 = v; } save(); renderAll(); return; }
    if (el.dataset.ov) { const o = S.overrides[el.dataset.ov] = S.overrides[el.dataset.ov] || {}; const v = num(el.value); if (v == null) delete o[el.dataset.k]; else o[el.dataset.k] = v; if (!Object.keys(o).length) delete S.overrides[el.dataset.ov]; save(); renderAll(); return; }
    if (el.id === 'tr-etf' || el.id === 'tr-side') { refreshLevelOptions(); return; }
  });
  $('#settings-form').addEventListener('change', () => {
    S.settings.startingCash = num($('#set-startcash').value) || 0;
    S.settings.referenceLot = num($('#set-lot').value) || 0;
    const cap = num($('#set-cap').value); S.settings.allocationCap = cap && cap > 0 ? cap : null;
    const rc = num($('#set-rungs').value); S.settings.rungCount = rc ? Math.max(1, Math.min(MAX_RUNGS, Math.round(rc))) : MAX_RUNGS;
    save(); renderAll();
  });
  $('#flow-form').addEventListener('submit', e => {
    e.preventDefault(); const amt = num($('#fl-amount').value); if (amt == null || !$('#fl-date').value) { toast('Date and amount are required', 'bad'); return; }
    S.cashFlows.push({ id: uid(), date: $('#fl-date').value, amount: amt, note: $('#fl-note').value.trim() }); $('#fl-amount').value = ''; $('#fl-note').value = ''; save(); renderAll(); toast('Cash flow recorded');
  });
  function resetTradeForm() { $('#tr-id').value = ''; $('#tr-price').value = ''; $('#tr-shares').value = ''; $('#tr-fees').value = '0'; $('#tr-note').value = ''; $('#tr-submit').textContent = 'Record trade'; $('#tr-cancel').style.display = 'none'; }
  $('#tr-cancel').addEventListener('click', () => { resetTradeForm(); refreshLevelOptions(); });
  $('#tr-form').addEventListener('submit', e => {
    e.preventDefault();
    const t = { id: $('#tr-id').value || uid(), date: $('#tr-date').value, etf: $('#tr-etf').value, side: $('#tr-side').value, level: $('#tr-side').value === 'BUY' ? num($('#tr-level').value) : null, price: num($('#tr-price').value), shares: num($('#tr-shares').value), fees: num($('#tr-fees').value) || 0, note: $('#tr-note').value.trim() };
    const c = entryCheck(t); if (!c.ok) { toast(c.text, 'bad'); return; }
    if (t.side === 'SELL') { const held = book(t.etf).shares; if (t.shares > held + 1e-9) { toast(`SELL of ${t.shares} exceeds ${held} tracked ${t.etf} shares. Record only shares the tracker holds.`, 'bad'); return; } }
    const i = S.trades.findIndex(x => x.id === t.id); if (i >= 0) S.trades[i] = t; else S.trades.push(t);
    save(); resetTradeForm(); renderAll(); toast((i >= 0 ? 'Trade updated: ' : 'Trade recorded: ') + t.side + ' ' + t.shares + ' ' + t.etf + (c.text !== 'OK' ? ' — ' + c.text : ''), c.text === 'OK' ? 'good' : 'warn');
  });
  $('#btn-export').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(S, null, 1)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `strategy_${CFG.key}_tracker_backup_${todayISO()}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  });
  $('#btn-export-xlsx').addEventListener('click', () => {
    if (!window.XLSX) { toast('XLSX library did not load', 'bad'); return; }
    const wb = XLSX.utils.book_new();

    const rows = evalAll();
    const summarySheet = rows.map(r => ({
      ETF: r.etf, Underlying: r.und, Enabled: r.p.enabled, Paused: r.p.paused,
      'Underlying close': r.d.und_close, 'Quote date': r.d.und_date,
      'Sell reference': r.sellRef, 'Tracked shares': r.b.shares, 'ETF close': r.d.etf_close,
      'What to do': r.action, 'Drop from ATH %': r.drop, 'Level reached %': r.levelReached,
      'Lowest unused %': r.lowestUnused, 'Est. sale value': r.estValue,
      'New levels ready': r.newReady, 'Feed status': r.d.status, 'Feed note': r.d.note,
    }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(summarySheet), 'Start here');

    const tradesSheet = sortedTrades().map(t => {
      const b = book(t.etf); const row = b.rows.find(x => x.id === t.id) || {};
      return {
        Date: t.date, ETF: t.etf, Side: t.side, 'Cycle key': row.cycleKey,
        'Buy level %': t.level, 'Fill price': t.price, Shares: t.shares, Fees: t.fees,
        'Cash change': row.cashChange, 'Share change': row.shareChange, Gross: row.gross,
        Note: t.note,
      };
    });
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(tradesSheet), 'Trades');

    const pairsSheet = CFG.pairs.map(p => {
      const st = S.pairs[p.etf];
      return {
        ETF: p.etf, Underlying: p.und, Enabled: st.enabled, Paused: st.paused,
        'First tier %': st.tier1, Ladder: rungsFor(p.etf).join(', '), Note: p.note || '',
      };
    });
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(pairsSheet), 'Pairs');

    const settingsSheet = [{
      'Starting cash': S.settings.startingCash, 'Reference lot': S.settings.referenceLot,
      'Allocation cap': S.settings.allocationCap, 'Rung count': S.settings.rungCount,
      'Tracked cash': trackedCash(),
    }];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(settingsSheet), 'Settings');

    const flowsSheet = S.cashFlows.map(f => ({ Date: f.date, Amount: f.amount, Note: f.note }));
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(flowsSheet.length ? flowsSheet : [{ Date: '', Amount: '', Note: '' }]), 'Cash flows');

    XLSX.writeFile(wb, `strategy_${CFG.key}_tracker_${todayISO()}.xlsx`);
    toast('XLSX exported');
  });
  $('#btn-import').addEventListener('change', e => {
    const f = e.target.files[0]; if (!f) return;
    const rd = new FileReader(); rd.onload = () => { try { const s = JSON.parse(rd.result); if (!s || !Array.isArray(s.trades)) throw new Error('not a tracker backup'); S = Object.assign(defaultState(), s); save(); renderAll(); toast('Backup imported: ' + S.trades.length + ' trades'); } catch (err) { toast('Import failed: ' + err.message, 'bad'); } }; rd.readAsText(f); e.target.value = '';
  });
  $('#btn-reset').addEventListener('click', e => {
    const b = e.currentTarget; if (b.dataset.armed) { S = defaultState(); save(); renderAll(); toast('Reset to the handover’s starting state'); delete b.dataset.armed; b.textContent = 'Reset to handover state'; } else { b.dataset.armed = '1'; b.textContent = 'Click again to erase everything in this browser'; setTimeout(() => { delete b.dataset.armed; b.textContent = 'Reset to handover state'; }, 4000); }
  });
  $('#btn-print').addEventListener('click', () => window.print());

  /* ---------- price feed ---------- */
  function setFeedLoading(loading) {
    const btn = $('#btn-refresh');
    if (!btn) return;
    btn.disabled = loading;
    btn.textContent = loading ? 'Refreshing…' : 'Refresh prices';
  }
  async function loadPrices() {
    setFeedLoading(true);
    try {
      const r = await fetch(API_BASE + '/api/prices');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      window.TRACKER_PRICES = await r.json();
      toast('Prices refreshed');
    } catch (e) {
      toast('Could not fetch prices: ' + e.message, 'bad');
    } finally {
      setFeedLoading(false);
      renderAll();
    }
  }
  const refreshBtn = $('#btn-refresh');
  if (refreshBtn) refreshBtn.addEventListener('click', loadPrices);

  resetTradeForm();
  renderAll();
  loadPrices();
})();
