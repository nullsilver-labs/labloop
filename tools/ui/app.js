/*
 * labloop's campaign view: one page, routed by its hash, reading /api/state on a cadence.
 *
 * The frame of DesignRefs 77641cfbec32 in Recall's skin (tools/ui/DESIGN.md): a sidebar that folds, then one desk
 * holding Ask (the local model, read-only, a column of its own), the viewer (search fitness four ways, over the
 * hours) and the inspector; the columns and the viewer's split drag. How a candidate was made is a series colour
 * and a shape: improve blue ●, draft ochre ■, crossover rose ◆, the baseline an ink ring, debug faint ▲.
 * Everything a reader might share sits in the hash: the place, the selection, the chart, the list's filter and
 * sort, the inspector's tab.
 */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const OPS = { baseline: 'Baseline', draft: 'Draft', improve: 'Improve', crossover: 'Crossover', debug: 'Debug', failed: 'Failed', deferred: 'Deferred' };
const OP_ORDER = ['baseline', 'draft', 'improve', 'crossover', 'debug'];
const OPC = { baseline: 'var(--color-ink)', draft: 'var(--color-series-2)', improve: 'var(--color-series-1)', crossover: 'var(--color-series-3)', debug: 'var(--color-faint)' };
const FAILED = new Set(['failed', 'killed', 'invalid']);
const H = 3600e3;
// labloop's plate (nullsilver.com/src/lib/marks): the loop's thread, and the gate's two terminals with the way out between
const PLATE = 'M2 3.25A0.25 0.25 0 0 1 1.75 3.5L0.25 3.5A0.25 0.25 0 0 1 0 3.25L0 0.25A0.25 0.25 0 0 1 0.25 0L1.75 0A0.25 0.25 0 0 1 2 0.25ZM6 3.25A0.25 0.25 0 0 1 5.75 3.5L3.25 3.5A0.25 0.25 0 0 1 3 3.25L3 0.25A0.25 0.25 0 0 1 3.25 0L5.75 0A0.25 0.25 0 0 1 6 0.25ZM0.5 5.75A0.25 0.25 0 0 1 0 5.75L0 0.25A0.25 0.25 0 0 1 0.5 0.25ZM0.25 6A0.25 0.25 0 0 1 0.25 5.5L5.75 5.5A0.25 0.25 0 0 1 5.75 6ZM6 5.75A0.25 0.25 0 0 1 5.5 5.75L5.5 0.25A0.25 0.25 0 0 1 6 0.25Z';
const PLATE_MIN = 'M2 3.25A0.25 0.25 0 0 1 1.75 3.5L0.25 3.5A0.25 0.25 0 0 1 0 3.25L0 0.25A0.25 0.25 0 0 1 0.25 0L1.75 0A0.25 0.25 0 0 1 2 0.25ZM6 3.25A0.25 0.25 0 0 1 5.75 3.5L3.25 3.5A0.25 0.25 0 0 1 3 3.25L3 0.25A0.25 0.25 0 0 1 3.25 0L5.75 0A0.25 0.25 0 0 1 6 0.25ZM1 5.75A0.25 0.25 0 0 1 0.75 6L0.25 6A0.25 0.25 0 0 1 0 5.75L0 0.25A0.25 0.25 0 0 1 0.25 0L0.75 0A0.25 0.25 0 0 1 1 0.25ZM6 5.75A0.25 0.25 0 0 1 5.75 6L0.25 6A0.25 0.25 0 0 1 0 5.75L0 5.25A0.25 0.25 0 0 1 0.25 5L5.75 5A0.25 0.25 0 0 1 6 5.25ZM6 5.75A0.25 0.25 0 0 1 5.75 6L5.25 6A0.25 0.25 0 0 1 5 5.75L5 0.25A0.25 0.25 0 0 1 5.25 0L5.75 0A0.25 0.25 0 0 1 6 0.25Z';
const plate = (px) => `<svg class="plate" width="${px}" height="${px}" viewBox="0 0 6 6" fill="currentColor" aria-hidden="true"><path d="${px < 28 ? PLATE_MIN : PLATE}"/></svg>`;
const IC = {
	overview: '<path d="M3 3h4v4H3zM9 3h4v4H9zM3 9h4v4H3zM9 9h4v4H9z"/>',
	candidates: '<path d="M3 4h10M3 8h10M3 12h6"/>',
	docs: '<path d="M4 2.5h5l3 3V13.5H4z M9 2.5v3h3"/>',
	ask: '<path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z"/>',
	read: '<path d="M2.5 4h4.5v8.5H2.5zM9 4h4.5v8.5H9z"/>',
	chip: '<path d="M4.5 4.5h7v7h-7zM6.5 2v2.5M9.5 2v2.5M6.5 11.5V14M9.5 11.5V14M2 6.5h2.5M2 9.5h2.5M11.5 6.5H14M11.5 9.5H14"/>',
	chart: '<path d="M2.5 13.5h11M4 11V7.5M7 11V4M10 11V8.5M13 11V5.5"/>',
	clock: '<path d="M8 2.5a5.5 5.5 0 1 0 0 11a5.5 5.5 0 1 0 0-11M8 5v3.2l2 1.3"/>',
	goal: '<path d="M8 2.5a5.5 5.5 0 1 0 0 11a5.5 5.5 0 1 0 0-11M8 5.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5"/>',
	arrow: '<path d="M4 8h8M9 5l3 3-3 3"/>',
	prev: '<path d="M10 3.5 5.5 8l4.5 4.5"/>',
	next: '<path d="M6 3.5 10.5 8 6 12.5"/>',
	x: '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
	fold: '<path d="M2.5 3h11v10h-11zM6 3v10"/>',
	reset: '<path d="M3 8a5 5 0 1 0 1.5-3.5M3 2.5V5h2.5"/>',
	report: '<path d="M4 2.5h8v11H4zM6 5.5h4M6 8h4M6 10.5h2"/>',
	sun: '<path d="M8 5.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5M8 1.8v1.4M8 12.8v1.4M1.8 8h1.4M12.8 8h1.4M3.6 3.6l1 1M11.4 11.4l1 1M3.6 12.4l1-1M11.4 4.6l1-1"/>',
	moon: '<path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z"/>',
	auto: '<path d="M8 2.5a5.5 5.5 0 1 0 0 11a5.5 5.5 0 1 0 0-11M8 2.5v11"/><path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor"/>',
	up: '<path d="M8 12.5v-9M4.5 7 8 3.5 11.5 7"/>'
};
const ic = (k, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 16 16" aria-hidden="true">${IC[k]}</svg>`;

let S = null, D = null, lastSig = '', lastRoute = '', lastSel = '', pollTimer = null, offline = false;
const ui = { chat: [], asking: false };

/* ------------------------------------------------------------------ the layout: folded sidebar, columns, split */
const LAYOUT_KEY = 'labloop-layout';
const lay = (() => { try { return JSON.parse(localStorage.getItem(LAYOUT_KEY) || '{}'); } catch { return {}; } })();
if (lay.chat == null) lay.chat = innerWidth >= 1800;
const saveLay = () => { try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(lay)); } catch {} };
function applyLayout() {
	document.documentElement.classList.toggle('rail-min', lay.rail === 'min');
	const cols = $('#cols');
	cols.classList.toggle('chat-on', !!lay.chat);
	cols.style.setProperty('--chat-w', `${lay.chatW || 340}px`);
	cols.style.setProperty('--insp-w', `${lay.inspW || 380}px`);
	$('#center').style.setProperty('--top', `${lay.top || (innerHeight < 900 ? 56 : 62)}%`);
	$('#askt')?.setAttribute('aria-pressed', String(!!lay.chat));
}
function dragGutter(ev) {
	const g = ev.target.closest('.gut');
	if (!g || ev.button !== 0) return;
	ev.preventDefault();
	const k = g.dataset.g, x0 = ev.clientX, y0 = ev.clientY, cols = $('#cols').getBoundingClientRect();
	const w0 = k === 'chat' ? lay.chatW || 340 : lay.inspW || 380;
	const cen = $('#center').getBoundingClientRect(), t0 = ((lay.top || 62) / 100) * cen.height;
	const room = (other) => cols.width - other - 2 * 12 - 480; // the centre keeps 480px
	g.classList.add('drag');
	document.body.classList.add('dragging');
	if (k === 'top') document.body.classList.add('dragging--h');
	const move = (e) => {
		if (k === 'chat') lay.chatW = Math.round(Math.max(280, Math.min(560, room(lay.chat ? lay.inspW || 380 : 0), w0 + e.clientX - x0)));
		else if (k === 'insp') lay.inspW = Math.round(Math.max(300, Math.min(640, room(lay.chat ? lay.chatW || 340 : 0), w0 - (e.clientX - x0))));
		else lay.top = Math.round(Math.max(30, Math.min(80, ((t0 + e.clientY - y0) / cen.height) * 100)) * 10) / 10;
		applyLayout();
	};
	const up = () => {
		removeEventListener('pointermove', move);
		removeEventListener('pointerup', up);
		g.classList.remove('drag');
		document.body.classList.remove('dragging', 'dragging--h');
		saveLay();
		drawFigures();
	};
	addEventListener('pointermove', move);
	addEventListener('pointerup', up);
}
document.addEventListener('pointerdown', dragGutter);
document.addEventListener('dblclick', (e) => { const g = e.target.closest('.gut'); if (!g) return; delete lay[{ chat: 'chatW', insp: 'inspW', top: 'top' }[g.dataset.g]]; saveLay(); applyLayout(); drawFigures(); });
function setChat(on) { lay.chat = on; saveLay(); applyLayout(); if (on && !$('#chat .compose')) renderChat(); drawFigures(); }

/* a scroller fades at an edge only while something is hidden past it */
function fadeEdges(el) {
	const t = el.scrollTop, b = el.scrollHeight - el.clientHeight - t;
	el.style.setProperty('--ft', `${Math.min(28, Math.max(0, t))}px`);
	el.style.setProperty('--fb', `${Math.min(28, Math.max(0, b))}px`);
}
document.addEventListener('scroll', (e) => { if (e.target.classList?.contains('fade')) fadeEdges(e.target); }, true);
const fadeAll = () => $$('.fade').forEach(fadeEdges);

/* ------------------------------------------------------------------ formatting */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const ep = (iso) => (iso ? Date.parse(iso) : null);
// figures keep four places so their decimals line up; a literal fixed by hand (a threshold) reads as it was written
const fit = (v) => (v == null ? '—' : Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(4).replace('-', '−'));
const lit = (v) => (v == null ? '—' : (+v.toFixed(4)).toString().replace('-', '−'));
const signed = (v) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '±') + Math.abs(v).toFixed(4));
const num = (v) => (v == null ? '—' : v.toLocaleString('en-GB'));
const money = (v) => (v == null ? '—' : '$' + (v >= 100 ? v.toFixed(0) : v.toFixed(2)));
function dur(sec) {
	if (sec == null || !isFinite(sec)) return '—';
	sec = Math.max(0, sec);
	if (sec < 60) return `${Math.round(sec)} s`;
	if (sec < 3600) return `${Math.round(sec / 60)} min`;
	const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
	if (h < 48) return m ? `${h} h ${m} min` : `${h} h`;
	return `${(sec / 86400).toFixed(1)} days`;
}
const hm = (ms) => new Date(ms).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
const day = (ms) => new Date(ms).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
const when = (ms) => `${day(ms)}, ${hm(ms)}`;
const plural = (n, w, ws = w + 's') => `${num(n)} ${n === 1 ? w : ws}`;
const model = (m) => (m || '').replace(/^claude-/, '').replace(/-\d{8}$/, '').replace(/^([a-z]+)-(\d+)-(\d+)$/, (_, n, a, b) => `${n[0].toUpperCase()}${n.slice(1)} ${a}.${b}`);
const tick = (s) => esc(s).replace(/`([^`]+)`/g, '<code class="code">$1</code>');
// a change in the better direction is right, the other wrong; the figure keeps its own sign
const gainHtml = (delta, gain) => (delta == null ? '<span class="faint">—</span>' : `<span class="${gain > 0 ? 'up' : gain < 0 ? 'down' : 'clay'}">${signed(delta)}</span>`);
// "Built from c0025's code (…) with X" says X; "Crossover: X" says X
function change(t) {
	t = String(t || '');
	const m = t.match(/^Built from (c\d{4,})'s code\s*/);
	if (m) {
		let i = m[0].length;
		if (t[i] === '(') { let d = 0; for (; i < t.length; i++) { if (t[i] === '(') d++; else if (t[i] === ')' && --d === 0) { i++; break; } } }
		const rest = t.slice(i).replace(/^[\s,;:]*(with|and|plus)?\s*/i, '');
		return rest ? rest[0].toUpperCase() + rest.slice(1) : t;
	}
	return t.replace(/^(Crossover|Improve|Draft|Debug)\s*[:—-]\s*/i, '');
}

/* ------------------------------------------------------------------ marks */
function mark(op, x, y, r = 4.5, extra = '') {
	const c = OPC[op] || OPC.debug;
	switch (op) {
		case 'draft': return `<rect x="${x - r * 0.88}" y="${y - r * 0.88}" width="${r * 1.76}" height="${r * 1.76}" rx="1.4" style="fill:${c}" ${extra}/>`;
		case 'crossover': { const d = r * 1.22; return `<path d="M${x},${y - d}L${x + d},${y}L${x},${y + d}L${x - d},${y}Z" style="fill:${c}" ${extra}/>`; }
		case 'baseline': return `<circle cx="${x}" cy="${y}" r="${r - 0.75}" style="fill:var(--pane);stroke:${c};stroke-width:1.5" ${extra}/>`;
		case 'failed': { const d = r * 0.75; return `<path d="M${x - d},${y - d}L${x + d},${y + d}M${x + d},${y - d}L${x - d},${y + d}" style="stroke:var(--color-clay);stroke-width:1.4;stroke-linecap:round;fill:none" ${extra}/>`; }
		case 'deferred': return `<rect x="${x - r * 0.8}" y="${y - r * 0.8}" width="${r * 1.6}" height="${r * 1.6}" rx="1.4" style="fill:none;stroke:var(--color-faint);stroke-width:1;stroke-dasharray:2 1.5" ${extra}/>`;
		case 'debug': return `<path d="M${x},${y - r}L${x + r},${y + r * 0.8}L${x - r},${y + r * 0.8}Z" style="fill:${c}" ${extra}/>`;
		case 'parent': return `<circle cx="${x}" cy="${y}" r="${r - 0.6}" style="fill:var(--pane);stroke:var(--color-clay);stroke-width:1.3" ${extra}/>`;
		default: return `<circle cx="${x}" cy="${y}" r="${r}" style="fill:${c}" ${extra}/>`;
	}
}
const opMark = (op, s = 10) => `<svg viewBox="-6 -6 12 12" width="${s}" height="${s}" aria-hidden="true">${mark(op, 0, 0, 4.6)}</svg>`;
const mk = (op, s = 10) => `<span class="mk">${opMark(op, s)}</span>`;
const opLabel = (op) => `<span class="op">${opMark(op)}${esc(OPS[op] || op)}</span>`;

/* ------------------------------------------------------------------ what the views share */
function derive() {
	const rows = S.rows || [];
	const by = Object.fromEntries(rows.map((r) => [r.id, r]));
	const hib = S.campaign?.higher_is_better !== false;
	const better = (a, b) => (b == null ? true : a == null ? false : hib ? a > b : a < b);
	for (const r of rows) {
		r.seq = parseInt(r.id.slice(1), 10);
		r.deferred = r.status === 'deferred' || r.exec === 'deferred';
		r.bad = FAILED.has(r.exec) || r.status === 'failed';
		const ps = (r.parents || []).map((p) => by[p]).filter((p) => p && p.fitness != null);
		r.ref = r.operator === 'crossover' && ps.length ? ps.reduce((a, b) => (better(a.fitness, b.fitness) ? a : b)) : ps[0] || null;
		// a draft "built from" another's code is not its child in the records, but it is what it set out to beat
		const bm = !r.ref && String(r.title || '').match(/^Built from (c\d{4,})'s code/);
		r.base = bm && by[bm[1]]?.fitness != null ? by[bm[1]] : null;
		const vs = r.ref || r.base;
		r.delta = r.fitness != null && vs ? r.fitness - vs.fitness : null;
		r.gain = r.delta == null ? null : hib ? r.delta : -r.delta;
		r.t0 = ep(r.launched);
		r.t1 = ep(r.ended);
		let o = r;
		while (o.redispatch_of && by[o.redispatch_of]) o = by[o.redispatch_of];
		r.root = o.id;
	}
	const pauses = [];
	let open = null;
	for (const e of S.events || []) {
		if (e.type === 'campaign.paused') open = open ?? ep(e.ts);
		else if (open != null && /resumed after/.test(e.msg || '')) { pauses.push([open, ep(e.ts)]); open = null; }
	}
	if (open != null) pauses.push([open, S.pop?.status === 'waiting_usage' ? Date.now() : open]);
	const waits = [];
	for (const p of pauses.sort((a, b) => a[0] - b[0])) { const l = waits.at(-1); if (l && p[0] - l[1] < 120e3) l[1] = Math.max(l[1], p[1]); else waits.push([...p]); }
	const t0 = ep(S.pop?.started) || Math.min(...rows.map((r) => r.t0 || Infinity));
	const t1 = S.pop?.status === 'finished' ? Math.max(ep(S.pop.finished) || 0, ...rows.map((r) => r.t1 || 0)) : Date.now();
	const scored = rows.filter((r) => r.fitness != null);
	const live = rows.filter((r) => !r.deferred).sort((a, b) => a.seq - b.seq);
	const deferredJobs = new Set(rows.filter((r) => r.deferred).map((r) => r.root));
	return {
		rows, by, hib, better, scored, waits, t0, t1, live, deferredJobs,
		best: by[S.pop?.best] || null,
		baseline: rows.find((r) => r.operator === 'baseline') || null,
		running: rows.filter((r) => r.running),
		cost: rows.reduce((a, r) => a + (r.cost || 0), 0),
		sessions: rows.filter((r) => r.cost != null).length,
		leaders: [...scored].filter((r) => r.operator !== 'baseline').sort((a, b) => (better(a.fitness, b.fitness) ? -1 : 1))
	};
}
function family(id) {
	const out = new Set([id]), stack = [id];
	while (stack.length) { const r = D.by[stack.pop()]; for (const p of [...(r?.parents || []), r?.base?.id].filter(Boolean)) if (!out.has(p)) { out.add(p); stack.push(p); } }
	for (const r of D.rows) if (r.parents?.includes(id) || r.base?.id === id) out.add(r.id);
	return out;
}

/* ------------------------------------------------------------------ the route: a place, a selection, its settings */
function parseRoute() {
	const raw = location.hash.replace(/^#\/?/, '');
	const [path, qs] = raw.split('?');
	const p = decodeURIComponent(path || '').split('/').filter(Boolean);
	const q = new URLSearchParams(qs || '');
	if (!p.length) return { view: 'overview', q };
	if (p[0] === 'c' && p[1]) return { view: 'overview', id: p[1], q };
	if (p[0] === 'candidates') return { view: 'candidates', id: p[1] || null, q };
	if (p[0] === 'docs') return { view: 'docs', name: p.slice(1).join('/') || null, q };
	if (p[0] === 'ask') return { view: 'ask', q };
	return { view: p[0], q };
}
const selId = () => parseRoute().id || null;
const param = (k, d) => parseRoute().q.get(k) ?? d;
// the hash with one setting changed, written without a new history entry or a full render
function setParam(k, v, dflt) {
	const [path, qs] = location.hash.replace(/^#/, '').split('?');
	const q = new URLSearchParams(qs || '');
	if (v == null || v === dflt) q.delete(k); else q.set(k, v);
	const s = q.toString();
	history.replaceState(null, '', `#${path || '/'}${s ? '?' + s : ''}`);
	lastRoute = JSON.stringify(routeKey());
}
const keepQ = (drop = []) => { const q = new URLSearchParams(location.hash.split('?')[1] || ''); for (const k of drop) q.delete(k); const s = q.toString(); return s ? `?${s}` : ''; };
// a candidate's address keeps the place it was chosen from
const candHref = (id) => (parseRoute().view === 'candidates' ? `#/candidates/${id}${keepQ()}` : `#/c/${id}${keepQ()}`);
const closeHref = () => (parseRoute().view === 'candidates' ? `#/candidates${keepQ(['tab'])}` : `#/${keepQ(['tab'])}`);
const routeKey = () => { const r = parseRoute(); return { v: r.view, id: r.id, n: r.name, q: r.q.toString() }; };

/* ------------------------------------------------------------------ markdown */
function inline(s) {
	const codes = [];
	s = s.replace(/`([^`]+)`/g, (_, c) => `\u0000${codes.push(c) - 1}\u0000`);
	s = esc(s);
	s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, u) => (/^(https?:|#)/.test(u) ? `<a href="${u}"${u[0] === '#' ? '' : ' target="_blank" rel="noopener"'}>${t}</a>` : `<span title="${u}">${t}</span>`));
	s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>').replace(/__([^_]+?)__/g, '<strong>$1</strong>');
	s = s.replace(/(^|[\s(])\*(?![\s*])([^*]+?)(?<!\s)\*(?![\w*])/g, '$1<em>$2</em>').replace(/(^|[\s(])_(?![\s_])([^_]+?)(?<!\s)_(?![\w_])/g, '$1<em>$2</em>');
	s = s.replace(/(<a\b[^>]*>.*?<\/a>|<[^>]+>)|\b(c\d{4,})\b/g, (m, tag, cid) => (tag ? tag : D?.by[cid] ? `<a class="cid" href="#/c/${cid}">${cid}</a>` : cid));
	return s.replace(/\u0000(\d+)\u0000/g, (_, i) => {
		const c = codes[+i];
		const m = c.match(/^(?:\/?candidates\/)?(c\d{4,})(?:\/(.*))?$/);
		if (m && D?.by[m[1]]) return `<a class="cid" href="#/c/${m[1]}"><code>${esc(c)}</code></a>`;
		return `<code>${esc(c)}</code>`;
	});
}
const slug = (s) => s.toLowerCase().replace(/<[^>]+>/g, '').replace(/[^\w]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
const KV = /^\s*(?:[-*]\s+)?\**([A-Z][\w /'’()-]{1,38}?)\**\s*:\s+(.+)$/;
function md(src, toc = null) {
	const L = String(src || '').replace(/\r/g, '').split('\n');
	const out = [];
	let i = 0;
	const isBlock = (l) => /^\s*(```|~~~|#{1,6}\s|>|\|)/.test(l) || /^\s*([-*+]|\d+[.)])\s+/.test(l);
	while (i < L.length) {
		const l = L[i];
		let m;
		if (/^\s*$/.test(l)) { i++; continue; }
		if ((m = l.match(/^\s*(```|~~~)/))) {
			const f = m[1], body = [];
			i++;
			while (i < L.length && !L[i].trim().startsWith(f)) body.push(L[i++]);
			i++;
			out.push(`<pre><code>${esc(body.join('\n'))}</code></pre>`);
			continue;
		}
		if ((m = l.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/))) {
			const n = m[1].length, id = slug(m[2]) || `h${i}`;
			if (toc && n >= 2 && n <= 3) toc.push({ n, id, text: m[2].replace(/[*_`]/g, '') });
			out.push(`<h${n} id="${id}">${inline(m[2])}</h${n}>`);
			i++;
			continue;
		}
		if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(l)) { out.push('<hr>'); i++; continue; }
		if (/^\s*>/.test(l)) {
			const body = [];
			while (i < L.length && /^\s*>/.test(L[i])) body.push(L[i++].replace(/^\s*>\s?/, ''));
			out.push(`<blockquote>${md(body.join('\n'))}</blockquote>`);
			continue;
		}
		if (/^\s*\|/.test(l) && i + 1 < L.length && /^\s*\|?\s*:?-{2,}/.test(L[i + 1])) {
			const cellsOf = (row) => row.trim().replace(/^\||\|$/g, '').split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
			const head = cellsOf(l), al = cellsOf(L[i + 1]).map((c) => (/:$/.test(c) ? (/^:/.test(c) ? 'center' : 'right') : ''));
			i += 2;
			const body = [];
			while (i < L.length && /^\s*\|/.test(L[i])) body.push(cellsOf(L[i++]));
			const td = (c, j, t) => `<${t}${al[j] ? ` style="text-align:${al[j]}"` : ''}>${inline(c)}</${t}>`;
			out.push(`<div class="tblwrap"><table>${head.some((c) => c) ? `<thead><tr>${head.map((c, j) => td(c, j, 'th')).join('')}</tr></thead>` : ''}<tbody>${body.map((r) => `<tr>${r.map((c, j) => td(c, j, 'td')).join('')}</tr>`).join('')}</tbody></table></div>`);
			continue;
		}
		if ((m = l.match(/^(\s*)([-*+]|\d+[.)])\s+/))) {
			const base = m[1].length, ordered = /\d/.test(m[2]), items = [];
			while (i < L.length) {
				const x = L[i], mm = x.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
				if (mm && mm[1].length <= base + 1) { items.push([mm[3]]); i++; continue; }
				if (/^\s*$/.test(x)) {
					if (i + 1 < L.length && /^\s+\S/.test(L[i + 1]) && L[i + 1].match(/^\s*/)[0].length > base) { items.at(-1).push(''); i++; continue; }
					break;
				}
				if (x.match(/^\s*/)[0].length > base || !isBlock(x)) { items.at(-1).push(x.replace(new RegExp(`^\\s{0,${base + 4}}`), '')); i++; continue; }
				break;
			}
			const t = ordered ? 'ol' : 'ul';
			out.push(`<${t}>${items.map((it) => `<li>${md(it.join('\n')).replace(/^<p>([\s\S]*?)<\/p>/, '$1')}</li>`).join('')}</${t}>`);
			continue;
		}
		const para = [];
		while (i < L.length && !/^\s*$/.test(L[i]) && !(para.length && isBlock(L[i]))) para.push(L[i++]);
		const k = para.map((p) => p.match(KV));
		if (para.length >= 2 && k.every(Boolean)) out.push(`<dl class="kv2">${k.map((x) => `<dt>${esc(x[1])}</dt><dd>${inline(x[2])}</dd>`).join('')}</dl>`);
		else out.push(`<p>${inline(para.join('\n')).replace(/\n/g, ' ')}</p>`);
	}
	return out.join('\n');
}

/* ------------------------------------------------------------------ the tip */
const tip = $('#tip');
function showTip(html, ev) {
	tip.innerHTML = html;
	tip.classList.add('on');
	const r = tip.getBoundingClientRect();
	let x = ev.clientX + 14, y = ev.clientY + 14;
	if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - 14;
	if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - 14;
	tip.style.left = `${Math.max(8, x)}px`;
	tip.style.top = `${Math.max(8, y)}px`;
}
const hideTip = () => tip.classList.remove('on');
const tipFor = (r) => `<b>${r.id}</b> <span class="c">${esc((OPS[r.operator] || r.operator).toLowerCase())}${r.parents?.length ? ' of ' + r.parents.join(' × ') : r.base ? ` on ${r.base.id}'s code` : ''}</span><br>${r.fitness != null ? `fitness ${fit(r.fitness)}` : r.bad ? esc(r.exec) : r.deferred ? 'deferred by the usage window' : r.running ? esc(r.phase || 'running') : '—'}${r.delta != null ? ` ${gainHtml(r.delta, r.gain)} <span class="c">on ${(r.ref || r.base).id}</span>` : ''}${r.title ? `<br><span class="c">${esc(change(r.title).slice(0, 150))}</span>` : ''}`;

/* ------------------------------------------------------------------ the score's parts: weights recovered from the records */
// Fitness is often a weighted sum of the evaluator's parts (here 0.85 · lang + 0.15 · know). The weights are
// solved from the scored candidates by least squares and used only when they reproduce every fitness.
let partsMemo = null;
function partWeights() {
	if (partsMemo && partsMemo.sig === lastSig) return partsMemo.w;
	const rows = D.scored.filter((r) => r.components && Object.values(r.components).every((v) => typeof v === 'number'));
	const keys = Object.keys(rows[0]?.components || {});
	let w = null;
	if (rows.length >= keys.length + 3 && keys.length) {
		const n = keys.length, A = Array.from({ length: n }, () => new Array(n + 1).fill(0));
		for (const r of rows) for (let i = 0; i < n; i++) { for (let j = 0; j < n; j++) A[i][j] += r.components[keys[i]] * r.components[keys[j]]; A[i][n] += r.components[keys[i]] * r.fitness; }
		let ok = true;
		for (let i = 0; i < n && ok; i++) {
			let p = i; for (let k = i + 1; k < n; k++) if (Math.abs(A[k][i]) > Math.abs(A[p][i])) p = k;
			[A[i], A[p]] = [A[p], A[i]];
			if (Math.abs(A[i][i]) < 1e-12) { ok = false; break; }
			for (let k = 0; k < n; k++) if (k !== i) { const f = A[k][i] / A[i][i]; for (let j = i; j <= n; j++) A[k][j] -= f * A[i][j]; }
		}
		if (ok) {
			const ws = keys.map((_, i) => A[i][n] / A[i][i]);
			if (rows.every((r) => Math.abs(keys.reduce((a, k, i) => a + ws[i] * r.components[k], 0) - r.fitness) < 0.003)) w = Object.fromEntries(keys.map((k, i) => [k, Math.round(ws[i] * 1000) / 1000]));
		}
	}
	partsMemo = { sig: lastSig, w };
	return w;
}

/* ------------------------------------------------------------------ the figures' shared scale */
// The fitness domain leaves out the baseline (often far below the rest): a value under it is drawn off scale, at a
// break, with its figure, never squashed onto the axis.
function fitDomain(rows, extra = []) {
	const v = rows.filter((r) => r.operator !== 'baseline').map((r) => r.fitness).concat(extra.filter((x) => x != null));
	let lo = Math.min(...v), hi = Math.max(...v);
	if (!isFinite(lo)) { lo = 0; hi = 1; }
	const pad = (hi - lo || 1) * 0.07;
	return [lo - pad, hi + pad];
}
function niceTicks(lo, hi, n = 5) {
	const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw)), e = raw / mag, st = (e >= 5 ? 5 : e >= 2 ? 2 : 1) * mag;
	const dp = Math.max(0, -Math.floor(Math.log10(st) + 1e-9));
	const out = [];
	for (let v = Math.ceil(lo / st - 1e-9) * st; v <= hi + 1e-9; v += st) out.push(+v.toFixed(dp + 2));
	return out.map((v) => [v, v.toFixed(dp).replace('-', '−')]);
}
// the pointer in the figure's own units, through its transform on screen, so a scaled or shifted figure still hits true
function svgPoint(svg, ev) {
	const p = svg.createSVGPoint();
	p.x = ev.clientX;
	p.y = ev.clientY;
	return p.matrixTransform(svg.getScreenCTM().inverse());
}
function hoverable(svg, pts, sel, r = 14) {
	const near = (ev) => {
		const { x, y } = svgPoint(svg, ev);
		let best = null, bd = r * r;
		for (const [px, py, row] of pts) { const d = (px - x) ** 2 + (py - y) ** 2; if (d < bd) { bd = d; best = row; } }
		return best;
	};
	svg.addEventListener('mousemove', (ev) => {
		const row = near(ev);
		svg.style.cursor = row ? 'pointer' : '';
		if (!row) { hideTip(); svg.classList.remove('lit'); return; }
		showTip(tipFor(row), ev);
		const fam = family(row.id);
		svg.classList.add('lit');
		svg.querySelectorAll(sel).forEach((n) => n.classList.toggle('hot', fam.has(n.dataset.id)));
	});
	svg.addEventListener('mouseleave', () => { hideTip(); svg.classList.remove('lit'); });
	svg.addEventListener('click', (ev) => { const row = near(ev); if (row) location.hash = candHref(row.id); });
}
const legendItem = (svg, text) => `<span>${svg}${text}</span>`;
const lgMark = (op) => `<svg viewBox="-6 -5 12 10">${mark(op, 0, 0, 4)}</svg>`;
const lgLine = (cls, style = '') => `<svg viewBox="0 0 14 10"><path d="M0,5H14" class="${cls}" style="${style}"/></svg>`;
function opsLegend(extra = '') {
	const ops = OP_ORDER.filter((o) => o !== 'baseline' && D.live.some((r) => r.operator === o && r.fitness != null));
	return ops.map((o) => legendItem(lgMark(o), OPS[o])).join('') + extra;
}

/* ------------------------------------------------------------------ figure 1: the record ledger, one row a new best */
// Counted in settled jobs, not hours: a campaign that waits on the usage window would otherwise be mostly empty time.
// Each gain is split into what each weighted part of the score gave, so a best won on a noisy part shows as one.
const PART_FILL = ['color-mix(in srgb, var(--color-data) 72%, var(--pane))', 'color-mix(in srgb, var(--color-data) 30%, var(--pane))', 'color-mix(in srgb, var(--color-data) 15%, var(--pane))'];
function records() {
	const pts = D.scored.filter((r) => r.t1).sort((a, b) => a.t1 - b.t1);
	const out = [];
	let cur = D.baseline?.fitness != null ? D.baseline : null, tries = [];
	pts.forEach((r, i) => {
		r.job = i + 1;
		if (r.operator === 'baseline') return;
		if (cur == null || cur.operator === 'baseline' || D.better(r.fitness, cur.fitness)) { out.push({ r, prev: cur, tries }); cur = r; tries = []; }
		else tries.push(r);
	});
	return { recs: out, n: pts.length, since: tries };
}
function figLedger(stage) {
	const sel = selId(), thr = S.campaign?.threshold, fin = S.final, w = partWeights();
	const keys = w ? Object.keys(w).filter((k) => w[k]) : [];
	const { recs, n, since } = records();
	if (!recs.length) { stage.innerHTML = '<div class="empty">No candidate has a score yet.</div>'; return ''; }
	const partsOf = (x) => (keys.length && x.prev?.components && x.r.components ? keys.map((k) => w[k] * (x.r.components[k] - x.prev.components[k])) : [x.prev ? x.r.fitness - x.prev.fitness : 0]);
	for (const x of recs) { x.gain = x.prev ? x.r.fitness - x.prev.fitness : null; x.parts = x.prev ? partsOf(x) : []; }
	// the scale: from the largest fall to the largest rise among steps between candidates; a step off the baseline is cut
	const body = recs.filter((x) => x.prev && x.prev.operator !== 'baseline');
	const neg = Math.min(0, ...body.flatMap((x) => [x.parts.filter((v) => v < 0).reduce((a, v) => a + v, 0)]));
	const pos = Math.max(1e-9, ...body.map((x) => x.parts.filter((v) => v > 0).reduce((a, v) => a + v, 0)));
	const P = (v) => (100 * (v - neg)) / (pos - neg);
	const bar = (x) => {
		if (!x.prev) return '<span class="gbar"></span>';
		let up = 0, dn = 0, segs = '';
		const cut = x.parts.filter((v) => v > 0).reduce((a, v) => a + v, 0) > pos * 1.001;
		x.parts.forEach((v, i) => {
			if (!v) return;
			const a = v > 0 ? up : dn + v, b = v > 0 ? up + v : dn;
			if (v > 0) up += v; else dn += v;
			const l = P(Math.max(neg, a)), rr = P(Math.min(pos, b));
			if (rr - l > 0.05) segs += `<i style="left:${l}%;width:${rr - l}%;background:${PART_FILL[i] || PART_FILL.at(-1)}"></i>`;
		});
		return `<span class="gbar${cut ? ' cut' : ''}"><b style="left:${P(0)}%"></b>${segs}</span>`;
	};
	const partTip = (x) => (keys.length && x.prev?.components ? keys.map((k, i) => `${k} ${signed(x.r.components[k] - x.prev.components[k])} × ${w[k]} = ${signed(x.parts[i])}`).join('\n') : '');
	const from = (r) => (r.parents?.length ? `of ${r.parents.join(' × ')}` : r.base ? `on ${r.base.id}'s code` : 'a fresh draft');
	const toThr = (v) => { if (thr == null) return '—'; const d = v - thr, g = D.hib ? d : -d; return `<span class="${g >= 0 ? 'up' : 'clay'}">${signed(d)}</span>`; };
	const best = (rs) => rs.reduce((a, b) => (a == null || D.better(b.fitness, a.fitness) ? b : a), null);
	const rows = recs.map((x) => {
		const r = x.r, tb = best(x.tries);
		return `<a class="lg-r${r.id === sel ? ' on' : ''}" href="${candHref(r.id)}" data-id="${r.id}">
			<span class="who">${mk(r.operator)}<span><b>${r.id}</b><small>${esc(from(r))}</small></span></span>
			<span class="job">#${r.job}<small>${day(r.t1).replace(/ \w+$/, '')} ${hm(r.t1)}</small></span>
			<span class="n">${fit(r.fitness)}</span>
			<span class="gain" title="${esc(partTip(x))}">${bar(x)}<span class="gv">${x.prev ? `<span class="up">${signed(x.gain)}</span><small>on ${x.prev.operator === 'baseline' ? 'the floor' : x.prev.id}</small>` : ''}</span></span>
			<span class="tries">${x.tries.length ? `${x.tries.length}<small>best ${fit(tb.fitness)}</small>` : '<span class="faint">none</span>'}</span>
			<span class="n">${toThr(r.fitness)}</span></a>`;
	}).join('');
	const last = recs.at(-1).r, fr = fin?.score != null && D.by[fin.candidate] ? D.by[fin.candidate] : null, ok = S.pop?.claim === 'supported';
	const final = fr ? `<a class="lg-r lg-final" href="${candHref(fr.id)}" data-id="${fr.id}">
			<span class="who"><span class="mk"><svg viewBox="-6 -6 12 12" width="10" height="10"><circle r="4" style="fill:none;stroke:${ok ? 'var(--color-right)' : 'var(--color-wrong)'};stroke-width:1.8"/></svg></span><span><b>Final split</b><small>${fr.id}, read once</small></span></span>
			<span class="job">${fin.ended ? `<small>${day(ep(fin.ended)).replace(/ \w+$/, '')} ${hm(ep(fin.ended))}</small>` : ''}</span>
			<span class="n">${fit(fin.score)}</span>
			<span class="gain"><span class="gv wide"><span class="${(D.hib ? fin.score - fr.fitness : fr.fitness - fin.score) >= 0 ? 'up' : 'down'}">${signed(fin.score - fr.fitness)}</span><small>on its search score</small></span></span>
			<span class="tries"></span>
			<span class="n">${toThr(fin.score)}</span></a>` : '';
	const running = D.running.length ? `<div class="lg-r lg-run"><span class="who"><span class="mk"><i class="lamp lamp--now"></i></span><span><b>${plural(D.running.length, 'job')} running</b><small>${D.running.map((r) => r.id).join(', ')}</small></span></span></div>` : '';
	stage.innerHTML = `<div class="ledger fade">
		<p class="lg-cap">${plural(recs.length, 'new best')} in ${n} scored jobs; the last at job ${last.job}, ${since.length ? `${plural(since.length, 'job')} since` : 'nothing since'}.${D.baseline?.fitness != null ? ` The floor is the baseline, ${D.baseline.id}, at ${fit(D.baseline.fitness)}.` : ''}</p>
		<div class="tbl lg-t"><div class="lg-r lg-h"><span>New best</span><span class="job">Job</span><span class="n">Fitness</span><span>Gain on the best before${keys.length ? `, by part` : ''}</span><span class="tries">Tries before</span><span class="n">To ${lit(thr)}</span></div>
		${rows}${final}${running}</div></div>`;
	return keys.length ? keys.map((k, i) => legendItem(`<svg viewBox="0 0 14 10"><rect y="2" width="14" height="6" rx="1.5" style="fill:${PART_FILL[i]}"/></svg>`, `${esc(k)} × ${w[k]}`)).join('') + `<span class="note2">A bar runs left when a part fell. A step off the baseline is cut at the scale's end.</span>` : '';
}

/* ------------------------------------------------------------------ figure 2: which operator pays off */
function figOperators(stage) {
	const sel = selId(), W = stage.clientWidth, Ht = stage.clientHeight;
	if (W < 260 || Ht < 120) return '';
	const ops = OP_ORDER.filter((o) => o !== 'baseline' && D.live.some((r) => r.operator === o && r.fitness != null));
	const thr = S.campaign?.threshold, fin = S.final;
	const cols = W > 640 ? [['median', 64], ['best', 64], ['beat its parent', 104]] : [['best', 64]];
	const cw = cols.reduce((a, c) => a + c[1], 0);
	const m = { l: 116, r: cw + 16, t: 30, b: 34 };
	const pw = W - m.l - m.r, rh = Math.min(132, (Ht - m.t - m.b) / ops.length);
	const [lo, hi] = fitDomain(D.scored, [thr]);
	const X = (v) => m.l + ((v - lo) / (hi - lo)) * pw;
	let g = '', st = '';
	const hit = [];
	const top = m.t, bot = m.t + rh * ops.length;
	for (const [v, s] of niceTicks(lo, hi, Math.max(3, Math.round(pw / 90)))) g += `<line class="grid" x1="${X(v)}" x2="${X(v)}" y1="${top}" y2="${bot}"/><text x="${X(v)}" y="${bot + 18}" text-anchor="middle">${s}</text>`;
	if (thr != null) g += `<line class="thr" x1="${X(thr)}" x2="${X(thr)}" y1="${top - 8}" y2="${bot}"/><text x="${X(thr)}" y="${top - 14}" text-anchor="middle" class="lbl"><tspan class="v">threshold</tspan> ${lit(thr)}</text>`;
	let cx = W - m.r + 16;
	for (const [name, w] of cols) { g += `<text x="${cx + w - 4}" y="${top - 14}" text-anchor="end" class="sm">${name}</text>`; cx += w; }
	ops.forEach((o, i) => {
		const rs = D.live.filter((r) => r.operator === o && r.fitness != null).sort((a, b) => a.fitness - b.fitness);
		const cy = top + rh * (i + 0.5);
		if (i) g += `<line class="grid" x1="0" x2="${W}" y1="${top + rh * i}" y2="${top + rh * i}"/>`;
		g += `<g transform="translate(16,${cy})">${mark(o, 5, -1, 4.6)}<text x="16" y="3" class="ink" style="font-weight:500">${OPS[o]}</text><text x="16" y="19" class="sm">n ${rs.length}</text></g>`;
		// a swarm: each mark takes the nearest free lane to its row's centre
		const lanes = [], r0 = 4.6, lane = 11, maxLane = Math.max(1, Math.floor((rh - 14) / lane / 2));
		for (const r of rs) {
			const x = r.fitness < lo ? m.l - 10 : X(r.fitness);
			let k = 0;
			for (let s = 0; s <= 2 * maxLane; s++) { const kk = s % 2 ? (s + 1) / 2 : -s / 2; if (!lanes.some(([lx, lk]) => lk === kk && Math.abs(lx - x) < r0 * 2.2)) { k = kk; break; } }
			lanes.push([x, k]);
			const y = cy + k * lane;
			st += `<g class="pt" data-id="${r.id}">${mark(o, x, y, r0, 'stroke="var(--pane)" stroke-width="1.3"')}${r.id === sel ? `<circle class="halo" cx="${x}" cy="${y}" r="8.5"/>` : ''}</g>`;
			hit.push([x, y, r]);
		}
		const med = rs[Math.floor((rs.length - 1) / 2)]?.fitness, best = rs.at(D.hib ? -1 : 0);
		if (med != null && rs.length > 2) st += `<line x1="${X(med)}" x2="${X(med)}" y1="${cy - rh / 2 + 8}" y2="${cy + rh / 2 - 8}" style="stroke:var(--color-ink);stroke-width:1.5;opacity:.7"/>`;
		const beat = rs.filter((r) => r.gain != null), up = beat.filter((r) => r.gain > 0).length;
		let x = W - m.r + 16;
		const vals = { median: med != null ? fit(med) : '—', best: best ? fit(best.fitness) : '—', 'beat its parent': beat.length ? `${up} of ${beat.length}` : '—' };
		for (const [name, w] of cols) { g += `<text x="${x + w - 4}" y="${cy + 4}" text-anchor="end" class="ink">${vals[name]}</text>`; x += w; }
		if (best) g += `<text x="${X(best.fitness) - 8}" y="${cy - 12}" text-anchor="end" class="lbl">${best.id}</text>`;
	});
	stage.innerHTML = `<svg class="fig" viewBox="0 0 ${W} ${Ht}" role="img" aria-label="Search fitness of every candidate, by the operator that made it">${g}${st}</svg>`;
	hoverable($('svg', stage), hit, '.pt', 10);
	return legendItem('<svg viewBox="0 0 14 10"><path d="M7,0V10" style="stroke:var(--color-ink);stroke-width:1.5;opacity:.7"/></svg>', 'Median') + legendItem(lgLine('thr'), 'Threshold') + `<span class="note2">A parent is the better one for a crossover, the code's source for a draft built on another</span>`;
}

/* ------------------------------------------------------------------ figure 3: did the children beat their parents */
function figParents(stage) {
	const sel = selId(), W = stage.clientWidth;
	const kids = D.live.filter((r) => r.delta != null).sort((a, b) => b.gain - a.gain);
	if (W < 260) return '';
	if (!kids.length) { stage.innerHTML = '<div class="empty">No candidate has a scored parent yet.</div>'; return ''; }
	const thr = S.campaign?.threshold;
	const [lo, hi] = fitDomain(kids.flatMap((k) => [k, k.ref || k.base]), [thr]);
	// an off-scale parent writes its figure beside its id, so that column widens for it
	const rh = Math.max(20, Math.min(24, (stage.clientHeight - 46) / kids.length)), m = { l: kids.some((k) => (k.ref || k.base).fitness < lo) ? 196 : 132, r: 84, t: 34, b: 12 };
	const Ht = m.t + kids.length * rh + m.b, pw = W - m.l - m.r;
	const X = (v) => (v < lo ? m.l - 4 : m.l + ((v - lo) / (hi - lo)) * pw);
	let g = '', st = '';
	const hit = [];
	for (const [v, s] of niceTicks(lo, hi, Math.max(3, Math.round(pw / 90)))) g += `<line class="grid" x1="${X(v)}" x2="${X(v)}" y1="${m.t - 6}" y2="${Ht - m.b}"/><text x="${X(v)}" y="${m.t - 12}" text-anchor="middle">${s}</text>`;
	if (thr != null) g += `<line class="thr" x1="${X(thr)}" x2="${X(thr)}" y1="${m.t - 6}" y2="${Ht - m.b}"/>`;
	g += `<text x="${W - 16}" y="${m.t - 12}" text-anchor="end" class="sm">on its parent</text>`;
	kids.forEach((k, i) => {
		const p = k.ref || k.base, y = m.t + i * rh + rh / 2, x1 = X(p.fitness), x2 = X(k.fitness), up = k.gain > 0;
		st += `<g class="pt" data-id="${k.id}"><rect class="row-hit${k.id === sel ? ' on' : ''}" x="4" y="${y - rh / 2 + 1}" width="${W - 8}" height="${rh - 2}" rx="6"/>`;
		st += `${mark(k.operator, 26, y, 4.2)}<text x="38" y="${y + 4}" class="ink">${k.id}</text><text x="${m.l - 16}" y="${y + 4}" text-anchor="end" class="sm">${p.id}${p.fitness < lo ? ` ${fit(p.fitness)} ←` : ''}</text>`;
		st += `<line x1="${x1}" x2="${x2}" y1="${y}" y2="${y}" style="stroke:${up ? 'var(--color-right)' : 'var(--color-wrong)'};stroke-width:2;opacity:.55"/>`;
		st += `${mark('parent', x1, y, 4.2)}${mark(k.operator, x2, y, 4.4, 'stroke="var(--pane)" stroke-width="1.3"')}`;
		st += `<text x="${W - 16}" y="${y + 4}" text-anchor="end" style="fill:${up ? 'var(--color-right)' : 'var(--color-wrong)'}">${signed(k.delta)}</text></g>`;
		hit.push([x2, y, k]);
	});
	const ups = kids.filter((k) => k.gain > 0).length, ds = kids.map((k) => k.delta).sort((a, b) => a - b), med = ds[Math.floor((ds.length - 1) / 2)];
	stage.innerHTML = `<div class="scroll fade"><svg class="fig" viewBox="0 0 ${W} ${Ht}" width="${W}" height="${Ht}" role="img" aria-label="Each child's search fitness against its parent's">${g}${st}</svg></div>`;
	const svg = $('svg', stage);
	svg.querySelectorAll('.pt').forEach((n) => {
		n.addEventListener('mouseenter', (ev) => showTip(tipFor(D.by[n.dataset.id]), ev));
		n.addEventListener('mousemove', (ev) => showTip(tipFor(D.by[n.dataset.id]), ev));
		n.addEventListener('mouseleave', hideTip);
		n.addEventListener('click', () => { location.hash = candHref(n.dataset.id); });
	});
	return legendItem(`<svg viewBox="-6 -5 12 10">${mark('parent', 0, 0, 4)}</svg>`, 'Parent') + legendItem(lgMark('improve'), 'Child') + legendItem('<svg viewBox="0 0 14 10"><path d="M0,5H14" style="stroke:var(--color-right);stroke-width:2;opacity:.55"/></svg>', 'Better') + legendItem('<svg viewBox="0 0 14 10"><path d="M0,5H14" style="stroke:var(--color-wrong);stroke-width:2;opacity:.55"/></svg>', 'Worse') + `<span class="note2">${ups} of ${kids.length} beat their parent · median ${signed(med)}</span>`;
}

/* ------------------------------------------------------------------ figure 4: the top, and its margin */
function figTop(stage) {
	const sel = selId(), W = stage.clientWidth, H0 = stage.clientHeight;
	if (W < 260) return '';
	const thr = S.campaign?.threshold, fin = S.final;
	const all = D.leaders.filter((r) => !r.deferred);
	const rh = 24, m = { l: 128, r: W > 560 ? 168 : 84, t: 34, b: 12 };
	const fitN = Math.max(8, Math.floor((H0 - m.t - m.b) / rh));
	const top = all.slice(0, fitN);
	const Ht = m.t + all.length * rh + m.b, pw = W - m.l - m.r;
	const [lo, hi] = fitDomain(top, [thr, fin?.score]);
	const X = (v) => m.l + ((v - lo) / (hi - lo)) * pw;
	let g = '', st = '';
	for (const [v, s] of niceTicks(lo, hi, Math.max(3, Math.round(pw / 90)))) g += `<line class="grid" x1="${X(v)}" x2="${X(v)}" y1="${m.t - 6}" y2="${Ht - m.b}"/><text x="${X(v)}" y="${m.t - 12}" text-anchor="middle">${s}</text>`;
	if (thr != null) g += `<line class="thr" x1="${X(thr)}" x2="${X(thr)}" y1="${m.t - 6}" y2="${Ht - m.b}"/>`;
	g += `<text x="${W - 16 - (m.r > 100 ? 84 : 0)}" y="${m.t - 12}" text-anchor="end" class="sm">fitness</text>${m.r > 100 ? `<text x="${W - 16}" y="${m.t - 12}" text-anchor="end" class="sm">to threshold</text>` : ''}`;
	all.forEach((r, i) => {
		const y = m.t + i * rh + rh / 2, off = r.fitness < lo, x = off ? m.l - 4 : X(r.fitness);
		st += `<g class="pt" data-id="${r.id}"><rect class="row-hit${r.id === sel ? ' on' : ''}" x="4" y="${y - rh / 2 + 1}" width="${W - 8}" height="${rh - 2}" rx="6"/>`;
		st += `<text x="16" y="${y + 4}" class="sm" text-anchor="start">${i + 1}</text>${mark(r.operator, 44, y, 4.2)}<text x="56" y="${y + 4}" class="ink">${r.id}</text>`;
		if (!off && thr != null) st += `<line x1="${X(thr)}" x2="${x}" y1="${y}" y2="${y}" style="stroke:${(D.hib ? r.fitness >= thr : r.fitness <= thr) ? 'var(--color-right)' : 'var(--app-edge)'};stroke-width:1.5"/>`;
		st += `${mark(r.operator, x, y, 4.6, 'stroke="var(--pane)" stroke-width="1.3"')}${off ? `<text x="${x + 9}" y="${y + 4}" class="sm">←</text>` : ''}`;
		if (fin?.candidate === r.id && fin.score != null) st += `<circle cx="${X(fin.score)}" cy="${y}" r="5" style="fill:none;stroke:${S.pop?.claim === 'supported' ? 'var(--color-right)' : 'var(--color-wrong)'};stroke-width:1.8"/>`;
		st += `<text x="${W - 16 - (m.r > 100 ? 84 : 0)}" y="${y + 4}" text-anchor="end" class="ink">${fit(r.fitness)}</text>`;
		if (m.r > 100 && thr != null) { const d = r.fitness - thr, gn = D.hib ? d : -d; st += `<text x="${W - 16}" y="${y + 4}" text-anchor="end" style="fill:${gn >= 0 ? 'var(--color-right)' : 'var(--color-clay)'}">${signed(d)}</text>`; }
		st += '</g>';
	});
	stage.innerHTML = `<div class="scroll fade"><svg class="fig" viewBox="0 0 ${W} ${Ht}" width="${W}" height="${Ht}" role="img" aria-label="Candidates ranked by search fitness">${g}${st}</svg></div>`;
	$('svg', stage).querySelectorAll('.pt').forEach((n) => {
		n.addEventListener('mousemove', (ev) => showTip(tipFor(D.by[n.dataset.id]), ev));
		n.addEventListener('mouseleave', hideTip);
		n.addEventListener('click', () => { location.hash = candHref(n.dataset.id); });
	});
	return opsLegend(legendItem(lgLine('thr'), 'Threshold') + (fin?.score != null ? legendItem('<svg viewBox="-6 -5 12 10"><circle r="3.8" style="fill:none;stroke:var(--color-right);stroke-width:1.8"/></svg>', `Final read, ${fit(fin.score)}`) : '') + `<span class="note2">Scale fits the top ${top.length}; ← is below it${D.baseline?.fitness != null ? `, as is the baseline at ${fit(D.baseline.fitness)}` : ''}</span>`);
}

const FIGS = {
	ledger: { name: 'New bests', q: 'What set each new best, by how much, and from what?', draw: figLedger },
	operators: { name: 'By operator', q: 'Which way of making a candidate pays off?', draw: figOperators },
	parents: { name: 'On parent', q: 'Did children beat what they were built from?', draw: figParents },
	top: { name: 'Top', q: 'How far above the threshold is the top, and how close the runners-up?', draw: figTop }
};

/* ------------------------------------------------------------------ the hours: each job a dot in the hour it settled */
function hoursDots(el) {
	const sel = selId();
	const cs = getComputedStyle(el), W = Math.max(260, el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)), avail = el.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
	let bh = H;
	while ((D.t1 - D.t0) / bh > W / 14) bh *= 2;
	const nb = Math.max(1, Math.ceil((D.t1 - D.t0) / bh));
	const pitch = W / nb, gp = 3, CAP = 3;
	let s = Math.max(5, Math.min(10, Math.floor(pitch - 4)));
	const bucket = (t) => Math.min(nb - 1, Math.max(0, Math.floor((t - D.t0) / bh)));
	const up = Array.from({ length: nb }, () => []), down = Array.from({ length: nb }, () => []);
	const seenDef = new Set();
	for (const r of [...D.rows].sort((a, b) => b.seq - a.seq)) {
		if (r.running) up[bucket(Date.now())].push(r);
		else if (r.fitness != null && r.t1) up[bucket(r.t1)].push(r);
		else if (r.bad && (r.t1 || r.t0)) down[bucket(r.t1 || r.t0)].push(r);
		else if (r.deferred && (r.t1 || r.t0) && !seenDef.has(r.root)) { seenDef.add(r.root); down[bucket(r.t1 || r.t0)].push(r); }
	}
	for (const c of up) c.sort((a, b) => (a.running - b.running) || (D.hib ? a.fitness - b.fitness : b.fitness - a.fitness));
	for (const c of down) c.sort((a, b) => b.bad - a.bad);
	const waited = Array.from({ length: nb }, (_, i) => { const a = D.t0 + i * bh, b = a + bh; return D.waits.reduce((w, [x, y]) => w + Math.max(0, Math.min(b, y) - Math.max(a, x)), 0) / bh; });
	const nu = Math.max(3, ...up.map((c) => c.length)), nd = Math.max(1, ...down.map((c) => Math.min(CAP, c.length)));
	if (avail > 60) s = Math.max(5, Math.min(s, Math.floor((avail - 44) / (nu + nd) - gp)));
	const base = 6 + nu * (s + gp), Ht = base + 10 + nd * (s + gp) + 26;
	let out = '';
	const hit = [];
	for (let i = 0; i < nb; i++) {
		const x = i * pitch + (pitch - s) / 2, cx = x + s / 2;
		if (waited[i] > 0.05) out += `<rect class="waitb" x="${i * pitch + 0.5}" y="0" width="${pitch - 1}" height="${base + 8 + nd * (s + gp)}" rx="3" style="opacity:${Math.min(1, waited[i] * 1.2)}"><title>${when(D.t0 + i * bh)}: waiting on usage ${Math.round(waited[i] * 100)}% of the hour</title></rect>`;
		up[i].forEach((r, k) => {
			const y = base - (k + 1) * (s + gp);
			const body = r.running ? `<rect x="${x}" y="${y}" width="${s}" height="${s}" rx="1.5" style="fill:var(--color-signal)"/>` : mark(r.operator, cx, y + s / 2, s / 2);
			out += `<g class="c" data-id="${r.id}">${body}${r.id === D.best?.id || r.id === sel ? `<rect x="${x - 2.5}" y="${y - 2.5}" width="${s + 5}" height="${s + 5}" rx="3" style="fill:none;stroke:var(--color-ink);stroke-width:${r.id === sel ? 1.75 : 1}"/>` : ''}</g>`;
			hit.push([x, y, r]);
		});
		const dn = down[i];
		dn.slice(0, dn.length > CAP ? CAP - 1 : CAP).forEach((r, k) => {
			const y = base + 8 + k * (s + gp);
			out += `<g class="c" data-id="${r.id}">${mark(r.bad ? 'failed' : 'deferred', cx, y + s / 2, s / 2)}</g>`;
			hit.push([x, y, r]);
		});
		if (dn.length > CAP) out += `<text x="${cx}" y="${base + 8 + (CAP - 1) * (s + gp) + s - 1}" text-anchor="middle" class="sm">+${dn.length - CAP + 1}</text>`;
	}
	out += `<line class="axis" x1="0" x2="${W}" y1="${base + 2}" y2="${base + 2}"/>`;
	let lab = '', lastX = -1e9;
	const d0 = new Date(D.t0); d0.setHours(24, 0, 0, 0);
	for (let t = +d0; t < D.t1; t += 24 * H) { const x = ((t - D.t0) / bh) * pitch; if (x - lastX > 30 && x < W - 60) { lab += `<line class="tick" x1="${x}" x2="${x}" y1="${base + 2}" y2="${base + 8}"/><text x="${x + 4}" y="${Ht - 4}">${day(t)}</text>`; lastX = x + 80; } }
	el.innerHTML = `<svg class="fig hours" viewBox="0 0 ${W} ${Ht}" width="${W}" height="${Ht}" role="img" aria-label="Every job as a mark in the hour it settled">${out}${lab}</svg>`;
	const svg = el.firstChild;
	const at = (ev) => { const { x: px, y: py } = svgPoint(svg, ev); return hit.find(([x, y]) => px >= x - 2 && px <= x + s + 2 && py >= y - 2 && py <= y + s + 2)?.[2]; };
	svg.addEventListener('mousemove', (ev) => {
		const r = at(ev);
		if (!r) { hideTip(); svg.classList.remove('lit'); svg.style.cursor = ''; return; }
		svg.style.cursor = 'pointer';
		const retries = r.deferred ? D.rows.filter((x) => x.root === r.root && x.deferred).length : 0;
		showTip(tipFor(r) + (retries > 1 ? `<br><span class="c">deferred ${retries} times</span>` : ''), ev);
		const fam = family(r.id);
		svg.classList.add('lit');
		svg.querySelectorAll('.c').forEach((n) => n.classList.toggle('hot', fam.has(n.dataset.id)));
	});
	svg.addEventListener('mouseleave', () => { hideTip(); svg.classList.remove('lit'); });
	svg.addEventListener('click', (ev) => { const r = at(ev); if (r) location.hash = candHref(r.id); });
}

/* ------------------------------------------------------------------ the sidebar and the desk's toolbar */
function statusWord() {
	const p = S.pop || {};
	if (S.empty) return ['No campaign yet', false];
	if (p.status === 'finished') return [`Finished ${day(ep(p.finished))}`, false];
	if (p.status === 'waiting_usage') return ['Waiting on usage', true];
	if (p.status === 'stopping') return ['Stopping', true];
	return [`Running · ${plural(D.running.length, 'job')}`, true];
}
function renderRail() {
	const r = parseRoute(), v = r.view;
	const [st, live] = statusWord();
	const hist = param('hist', 'all');
	const ops = OP_ORDER.filter((o) => D.live.some((x) => x.operator === o));
	const want = (e) => hist === 'all' ? true : hist === 'results' ? e.type === 'candidate.done' || e.type.startsWith('campaign.') : e.type === 'candidate.failed';
	const seenDef = new Set();
	const evs = [...(S.events || [])].reverse().filter((e) => {
		if (e.type === 'candidate.launch' || e.type === 'campaign.paused' || /resumed after/.test(e.msg || '') || !want(e)) return false;
		const c = e.candidate && D.by[e.candidate];
		if (c?.deferred) { if (seenDef.has(c.root)) return false; seenDef.add(c.root); }
		return true;
	}).slice(0, 80);
	let h = '', last = '';
	for (const e of evs) {
		const t = ep(e.ts), d = day(t);
		if (d !== last) { h += `<div class="day">${d}</div>`; last = d; }
		const c = e.candidate && D.by[e.candidate];
		const op = e.data?.operator || c?.operator;
		const kind = e.type === 'candidate.failed' ? 'failed' : c?.deferred ? 'deferred' : op && OPC[op] ? op : null;
		const msg = (e.msg || e.type).replace(/^c\d{4,} /, '').replace(/^(draft|improve|crossover|debug|baseline)\s+/i, '');
		const tries = c?.deferred ? D.rows.filter((x) => x.root === c.root && x.deferred).length : 0;
		h += `<${c ? `a href="${candHref(c.id)}" tabindex="-1"` : 'div'} class="item" title="${esc(msg)}"${c && c.id === selId() ? ' aria-current="true"' : ''}>${kind ? mk(kind, 9) : '<span class="mk"><i class="sq" style="background:var(--color-clay)"></i></span>'}<div><div class="it">${c ? `<span class="id">${c.id}</span> ` : ''}${esc(msg)}${tries > 1 ? ` <span class="faint">×${tries}</span>` : ''}</div></div><span class="n">${hm(t)}</span></${c ? 'a' : 'div'}>`;
	}
	const place = (k, n, href, end = '') => `<a class="item" href="${href}" title="${n}"${v === k ? ' aria-current="page"' : ''}>${ic(k)}<div class="it">${n}</div>${end}</a>`;
	$('#rail').innerHTML = `
		<div class="brand">${plate(20)}<span class="name">labloop</span><button class="pill pill--sm pill--round pill--ghost fold" id="fold" aria-label="${lay.rail === 'min' ? 'Unfold the sidebar' : 'Fold the sidebar'}" title="${lay.rail === 'min' ? 'Unfold' : 'Fold'} the sidebar">${ic('fold')}</button></div>
		<div class="camp"><div class="nm">${esc(S.campaign?.id || S.pop?.campaign || 'campaign')}</div><div class="st">${live ? '<i class="lamp lamp--now"></i>' : ''}${esc(st)}</div></div>
		<label class="rsearch">${ic('candidates')}<input id="rq" placeholder="Find a candidate" aria-label="Find a candidate" value="${esc(param('q', ''))}"><span class="kbd">/</span></label>
		<div class="list places">
			${place('overview', 'Overview', '#/')}
			${place('candidates', 'Candidates', '#/candidates', `<span class="n">${D.live.length}</span>`)}
			${place('docs', 'Documents', '#/docs', `<span class="n">${(S.docs || []).length}</span>`)}
		</div>
		<div class="ops"><div class="rh"><span>Operators</span><span>scored</span></div><div class="list">${ops.map((o) => `<div class="item">${mk(o)}<div class="it">${OPS[o]}</div><span class="tag">${D.live.filter((x) => x.operator === o && x.fitness != null).length} of ${D.live.filter((x) => x.operator === o).length}</span></div>`).join('')}</div></div>
		<div class="rh"><span>History</span><span>${plural(evs.length, 'event')}</span></div>
		<div class="seg" id="hseg" role="group" aria-label="Which events">${[['all', 'All'], ['results', 'Results'], ['failures', 'Failures']].map(([k, n]) => `<button aria-pressed="${hist === k}" data-h="${k}">${n}</button>`).join('')}</div>
		<div class="hist fade" id="hist">${h || '<div class="day">Nothing here.</div>'}</div>`;
	const rq = $('#rq');
	rq.addEventListener('keydown', (e) => {
		if (e.key !== 'Enter') return;
		const q = rq.value.trim(), hitId = D.by[q] ? q : null;
		location.hash = hitId ? `#/c/${hitId}` : `#/candidates${q ? `?q=${encodeURIComponent(q)}` : ''}`;
	});
	$('#hseg').addEventListener('click', (e) => { const k = e.target.closest('button')?.dataset.h; if (k) { setParam('hist', k, 'all'); renderRail(); fadeAll(); } });
	$('#fold').addEventListener('click', () => { lay.rail = lay.rail === 'min' ? 'open' : 'min'; saveLay(); applyLayout(); renderRail(); drawFigures(); });
}
function renderDeskbar() {
	const t = document.documentElement.dataset.tone;
	$('#deskbar').innerHTML = `<div class="where">${offline ? `<span class="offline"><i class="lamp" style="color:var(--color-wrong)"></i>Not reaching the server · last read ${hm(offline)}</span>` : ''}</div>
		<div class="end">
			<button class="pill pill--sm" id="askt" aria-pressed="${!!lay.chat}" title="Ask the local model about this campaign">${ic('ask')}Ask</button>
			${S?.docs?.includes('REPORT.md') ? `<a class="pill pill--sm" href="#/docs/REPORT.md">${ic('report')}Report</a>` : ''}
			<button class="pill pill--sm pill--round pill--ghost" id="tidy" aria-label="Reset the layout" title="Reset the panels' sizes">${ic('reset')}</button>
			<div class="seg" id="tones" role="group" aria-label="Tone">${[['system', 'auto', 'Follow the system'], ['day', 'sun', 'Day'], ['night', 'moon', 'Night']].map(([x, i, n]) => `<button aria-pressed="${t === x}" data-t="${x}" aria-label="${n}" title="${n}">${ic(i)}</button>`).join('')}</div>
		</div>`;
	$('#askt').addEventListener('click', () => setChat(!lay.chat));
	$('#tidy').addEventListener('click', () => { for (const k of ['chatW', 'inspW', 'top']) delete lay[k]; saveLay(); applyLayout(); drawFigures(); });
	$('#tones').addEventListener('click', (e) => {
		const x = e.target.closest('button')?.dataset.t;
		if (!x) return;
		document.documentElement.dataset.tone = x;
		try { localStorage.setItem('labloop-tone', x); } catch {}
		renderDeskbar();
		drawFigures();
	});
}

/* ------------------------------------------------------------------ Ask: the local model, read-only */
const SUGGEST = ['Which candidate is best, and what did it change?', 'Why did the failed candidates fail?', 'Which ideas paid off, and which did not?', 'What does the final read mean for the claim?'];
const chatKey = () => `labloop-chat:${S.campaign?.id || S.root}`;
function saveChat() { try { sessionStorage.setItem(chatKey(), JSON.stringify(ui.chat.slice(-20))); } catch {} }
function loadChat() { try { ui.chat = JSON.parse(sessionStorage.getItem(chatKey()) || '[]'); } catch { ui.chat = []; } }
let slm = { up: false };
async function renderChat(prefill) {
	try { slm = await (await fetch('/api/ask/status')).json(); } catch {}
	const el = $('#chat');
	const keep = $('#askq', el)?.value;
	const who = (small) => `<div class="who"><span class="av">${ic('chip')}</span>${esc(slm.model || 'The local model')}<small>${small}</small></div>`;
	const msgs = ui.chat.map((m) => m.role === 'user' ? `<div class="q">${esc(m.text)}</div>` : `<div class="a">${who('read-only')}
		${m.steps?.length ? `<details class="ran"${m.pending ? ' open' : ''}><summary>${ic('read')}Read ${plural(m.steps.filter((s) => !s.refused).length, 'file')}${m.steps.some((s) => s.refused) ? `, ${m.steps.filter((s) => s.refused).length} refused` : ''}</summary><div class="cmds">${m.steps.map((s) => `<div class="cmd${s.refused ? ' x' : ''}"><span>${s.refused ? 'Refused' : s.name === 'read' ? 'Read a file' : s.name === 'grep' ? 'Searched' : s.name === 'ls' ? 'Listed' : s.name === 'find' ? 'Found' : esc(s.name)}</span><code>${esc((s.path || s.pattern || '').replace(/^\/+/, ''))}</code></div>`).join('')}</div></details>` : ''}
		${m.text ? `<div class="prose">${md(m.text)}</div>` : ''}${m.error ? `<div class="note note--wrong">${esc(m.error)}</div>` : ''}
		${m.pending ? `<div class="wait"><i class="lamp lamp--now"></i><span>${m.text ? 'Writing.' : 'Reading the campaign’s files. A small model on the CPU takes a minute or two.'}</span></div>` : ''}${m.seconds ? `<div class="faint" style="font-size:12px">${m.seconds.toFixed(1)} s</div>` : ''}</div>`).join('');
	el.innerHTML = `<div class="ph">${ic('ask')}<span class="t">Ask</span><span class="s">${esc(slm.model || 'the local model')}, ${slm.up ? 'on this machine’s CPU' : 'not running'}</span><span class="end">${ui.chat.length ? '<button class="pill pill--sm pill--ghost" id="clear">Clear</button>' : ''}<button class="pill pill--sm pill--round pill--ghost" id="askclose" aria-label="Close Ask" title="Close (Esc)">${ic('x')}</button></span></div>
		<div class="pb fade"><div class="chatb" id="thread">${msgs || `<p class="intro">I read this campaign's files to answer: the report, the ledger, each candidate's summary and code. I can read only this folder and change nothing. I am small, so take my answer as a pointer to the file that holds it.</p><div class="sugg">${SUGGEST.map((s) => `<button data-s="${esc(s)}" ${slm.up ? '' : 'disabled'}>${ic('arrow')}<span>${esc(s)}</span></button>`).join('')}</div>`}
		${slm.up ? '' : `<div class="note">${slm.installed ? 'The local model is not answering: <code>systemctl --user start nullsilver-slm</code>.' : 'The local model (nullsilver-slm) is not installed on this machine.'}</div>`}</div></div>
		<div class="compose"><form id="askf"><textarea id="askq" rows="2" aria-label="Your question" placeholder="Ask about the campaign, a candidate, a result…" ${slm.up ? '' : 'disabled'}></textarea><div class="row"><span>Read-only · this folder</span><button class="go" disabled aria-label="Ask">${ic('up')}</button></div></form></div>`;
	const ta = $('#askq', el), go = $('.go', el);
	const sync = () => { go.disabled = !(slm.up && !ui.asking && ta.value.trim()); };
	ta.value = prefill ?? keep ?? '';
	sync();
	ta.addEventListener('input', sync);
	ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#askf').requestSubmit(); } });
	$('#askf', el).addEventListener('submit', (e) => { e.preventDefault(); if (slm.up && !ui.asking && ta.value.trim()) { const q = ta.value.trim(); ta.value = ''; ask(q); } });
	$('.sugg', el)?.addEventListener('click', (e) => { const s = e.target.closest('button')?.dataset.s; if (s && slm.up) ask(s); });
	$('#clear', el)?.addEventListener('click', () => { ui.chat = []; saveChat(); renderChat(); });
	$('#askclose', el).addEventListener('click', () => setChat(false));
	const pb = $('.pb', el);
	pb.scrollTop = pb.scrollHeight;
	fadeEdges(pb);
	if (prefill) ta.focus();
}
async function ask(q) {
	const history = ui.chat.filter((m) => !m.pending && !m.error).map((m) => ({ role: m.role, text: m.text }));
	ui.chat.push({ role: 'user', text: q });
	const a = { role: 'assistant', text: '', steps: [], pending: true };
	ui.chat.push(a);
	ui.asking = true;
	renderChat('');
	try {
		const res = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, history }) });
		if (!res.ok) a.error = (await res.json().catch(() => ({}))).error || `HTTP ${res.status}`;
		else {
			const rd = res.body.getReader(), dec = new TextDecoder();
			let buf = '', t = 0;
			for (;;) {
				const { value, done } = await rd.read();
				if (done) break;
				buf += dec.decode(value, { stream: true });
				let k;
				while ((k = buf.indexOf('\n\n')) >= 0) {
					const line = buf.slice(0, k).replace(/^data: ?/, '');
					buf = buf.slice(k + 2);
					let ev; try { ev = JSON.parse(line); } catch { continue; }
					if (ev.type === 'text') a.text += ev.delta || '';
					else if (ev.type === 'tool') a.steps.push(ev);
					else if (ev.type === 'tool_error') a.steps.push({ ...ev, refused: true });
					else if (ev.type === 'done') { a.text = ev.answer || a.text; a.seconds = ev.seconds; }
					else if (ev.type === 'error') a.error = ev.message;
				}
				if (Date.now() - t > 200) { t = Date.now(); renderChat(); }
			}
		}
	} catch (e) { a.error = String(e); }
	a.pending = false;
	ui.asking = false;
	saveChat();
	renderChat();
}

/* ------------------------------------------------------------------ the centre */
function crumbs(parts, end = '') {
	return `<div class="crumbbar">${parts.map(([n, h], i) => (i < parts.length - 1 ? `<a href="${h}">${esc(n)}</a><span class="sep">›</span>` : `<span class="cur">${esc(n)}</span>`)).join('')}${end ? `<span class="end">${end}</span>` : ''}</div>`;
}
function claimChip() {
	const p = S.pop || {}, f = S.final;
	if (p.status !== 'finished') return `<span class="chip pill--sig"><i class="lamp lamp--now"></i><b>${esc((p.status || '').replace('_', ' '))}</b></span>`;
	if (p.claim === 'supported') return `<span class="chip pill--right"><i class="lamp"></i><b>Claim supported${f?.score != null ? ` · ${fit(f.score)}` : ''}</b></span>`;
	if (p.claim === 'not_supported') return `<span class="chip pill--wrong"><i class="lamp"></i><b>Not supported${f?.score != null ? ` · ${fit(f.score)}` : ''}</b></span>`;
	return `<span class="chip"><b>${esc(p.claim || 'finished')}</b></span>`;
}
let figKeep = null;
function centerViewer() {
	const was = $('#stage .ledger, #stage .scroll');
	figKeep = was ? { chart: $('#stage').dataset.chart, top: was.scrollTop } : null;
	const c = S.campaign || {}, p = S.pop || {}, f = S.final;
	const fig = FIGS[param('chart', 'ledger')] ? param('chart', 'ledger') : 'ledger';
	$('#center').className = 'center';
	$('#center').innerHTML = `
		<section class="panel" aria-label="Search fitness"><div class="ph">${ic('chart')}<span class="t">Search fitness</span></div>
			${crumbs([['Campaigns', '#/'], [c.id || '', '#/'], ['Search fitness']], p.updated_at ? `Updated ${hm(ep(p.updated_at))}` : '')}
			<div class="vh">
				<div class="tr"><h2>${num(D.live.length)} candidates, ${plural(D.live.filter((r) => r.fitness != null).length, 'score')}</h2><span class="chip">threshold <b>${lit(c.threshold)}</b></span><span class="chip">best <b>${fit(D.best?.fitness)}</b></span>${f?.score != null ? `<span class="chip ${S.pop?.claim === 'supported' ? 'pill--right' : S.pop?.claim === 'not_supported' ? 'pill--wrong' : ''}">final <b>${fit(f.score)}</b></span>` : ''}</div>
				<div class="bar"><div class="seg" id="vseg" role="group" aria-label="Chart">${Object.entries(FIGS).map(([k, x]) => `<button aria-pressed="${fig === k}" data-v="${k}">${x.name}</button>`).join('')}</div><span class="q2">${FIGS[fig].q}</span></div>
			</div>
			<div class="stage" id="stage"></div><div class="lgd" id="lgd"></div></section>
		<div class="gut gut--h" data-g="top" role="separator" aria-orientation="horizontal" aria-label="Resize"></div>
		<section class="panel hours-p" aria-label="The hours"><div class="ph">${ic('clock')}<span class="t">Each hour of the campaign</span><span class="s">a mark is a job, in the hour it settled</span></div><div class="pb" id="hoursb"></div></section>`;
	$('#vseg').addEventListener('click', (e) => { const v = e.target.closest('button')?.dataset.v; if (v) { setParam('chart', v, 'ledger'); centerViewer(); } });
	renderHours();
	requestAnimationFrame(drawFigures);
}
function drawFigures() {
	const st = $('#stage');
	if (st) {
		const fig = FIGS[param('chart', 'ledger')] || FIGS.ledger;
		hideTip();
		// the legend takes its room under the figure, which can shorten the stage: draw again at the size it settled to
		const w0 = st.clientWidth, h0 = st.clientHeight;
		$('#lgd').innerHTML = fig.draw(st) || '';
		if (st.clientWidth !== w0 || st.clientHeight !== h0) fig.draw(st);
		// a figure that scrolls keeps its place when a row in it is chosen, and shows the chosen row if it is out of view
		const key = FIGS[param('chart', 'ledger')] ? param('chart', 'ledger') : 'ledger', sc = $('.ledger, .scroll', st);
		if (sc && figKeep?.chart === key) sc.scrollTop = figKeep.top;
		st.dataset.chart = key;
		figKeep = null;
		const on = sc && $(':is(.lg-r.on, .row-hit.on)', sc);
		if (on) { const a = on.getBoundingClientRect(), b = sc.getBoundingClientRect(); if (a.top < b.top || a.bottom > b.bottom) sc.scrollTop += a.top - b.top - (b.height - a.height) / 2; }
	}
	const d = $('#dots');
	if (d) hoursDots(d);
	fadeAll();
}
function renderHours() {
	const hb = $('#hoursb');
	if (!hb) return;
	const p = S.pop, c = S.campaign || {}, f = S.final;
	const wall = ((p.status === 'finished' ? ep(p.finished) : Date.now()) - ep(p.started)) / 1000;
	const max = c.max_candidates || D.live.length || 1, nt = 24, per = max / nt;
	const ticks = Array.from({ length: nt }, (_, i) => `<i class="${(i + 1) * per <= (p.settled || 0) ? 'on' : i * per < (p.settled || 0) + D.running.length && i * per >= (p.settled || 0) ? 'cur' : ''}"></i>`).join('');
	const live = p.status !== 'finished';
	const clock = (s) => { s = Math.round(s); return `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; };
	const nDef = D.rows.filter((r) => r.deferred).length, waitS = (S.usage?.waiting_seconds) || D.waits.reduce((a, [x, y]) => a + (y - x) / 1000, 0);
	hb.innerHTML = `
		<div class="hhead"><div class="fcard"><b><i class="lamp${live ? ' lamp--now' : ''}" style="${live ? '' : 'color:var(--color-right)'}"></i>${live ? 'Running' : 'Finished'}</b><small><span>${live ? plural(D.running.length, 'job') + ' in flight' : `${num(p.settled || 0)} settled`}</span>${nDef ? `<span>${plural(D.deferredJobs.size, 'job')} deferred ${nDef}×</span>` : ''}${waitS > 600 ? `<span>waited ${dur(waitS)}</span>` : ''}</small></div>
		<div class="lgd">${opsLegend()}${legendItem(`<svg viewBox="-6 -5 12 10">${mark('failed', 0, 0, 4)}</svg>`, 'Failed')}${nDef ? legendItem(`<svg viewBox="-6 -5 12 10">${mark('deferred', 0, 0, 4.2)}</svg>`, 'Deferred') : ''}${D.waits.length ? legendItem('<svg viewBox="0 0 14 10"><rect width="14" height="10" rx="2" style="fill:var(--color-stock)"/></svg>', 'Waiting on usage') : ''}</div></div>
		<div class="dots" id="dots"></div>
		<div class="goalbar">
			<div class="gr">${ic('goal')}<b>Goal</b><span class="t"><span class="clay">${live ? 'Active' : 'Done'}</span>Beat ${lit(c.threshold)} on the final split, read once at the end</span><span class="e">${ic('clock')}${clock(wall)}</span></div>
			<div class="gr">${ic('candidates')}<b>Now</b><span class="t"><span class="clay">${f?.score != null ? 'Read' : 'Search'}</span>${f?.score != null ? `${f.candidate} read ${fit(f.score)} on the final split` : D.best ? `${D.best.id} leads at ${fit(D.best.fitness)}` : 'waiting for the first score'}</span><span class="e"><span class="ticks" aria-hidden="true">${ticks}</span>${num(p.settled ?? 0)} of ${c.max_candidates ?? '—'}</span></div>
		</div>`;
}
function listRows() {
	const filter = param('f', 'settled'), query = param('q', ''), sort = param('s', 'id'), dir = +param('d', sort === 'id' ? 1 : -1);
	let rows = D.rows.filter((r) => ({ settled: !r.deferred, failed: r.bad, deferred: r.deferred, all: true })[filter] ?? !r.deferred);
	if (query) { const q = query.toLowerCase(); rows = rows.filter((r) => `${r.id} ${r.operator} ${r.title || ''} ${r.fail_reason || ''}`.toLowerCase().includes(q)); }
	const key = { id: (r) => r.seq, fitness: (r) => r.fitness ?? (D.hib ? -Infinity : Infinity), gain: (r) => r.gain ?? -Infinity, lease: (r) => r.lease ?? -1, cost: (r) => r.cost ?? -1 }[sort] || ((r) => r.seq);
	return rows.sort((a, b) => (key(a) - key(b)) * dir);
}
function centerList() {
	const keep = $('#center .pb')?.scrollTop, focused = document.activeElement?.id === 'q';
	const F = { settled: 'Settled', failed: 'Failed', deferred: 'Deferred', all: 'All' };
	const cnt = { settled: D.live.length, failed: D.rows.filter((r) => r.bad).length, deferred: D.rows.filter((r) => r.deferred).length, all: D.rows.length };
	const filter = param('f', 'settled'), query = param('q', ''), sort = param('s', 'id'), dir = +param('d', sort === 'id' ? 1 : -1);
	const rows = listRows(), sel = selId();
	const th = (k, n, cls = '') => `<button class="${cls}" data-s="${k}" aria-pressed="${sort === k}" title="Sort by ${n.toLowerCase()}">${cls === 'n' ? `<span class="ar">${sort === k ? (dir > 0 ? '↑' : '↓') : ''}</span>${n}` : `${n}<span class="ar">${sort === k ? (dir > 0 ? '↑' : '↓') : ''}</span>`}</button>`;
	$('#center').className = 'center one';
	$('#center').innerHTML = `<section class="panel" aria-label="Candidates"><div class="ph">${ic('candidates')}<span class="t">Candidates</span></div>
		${crumbs([['Campaigns', '#/'], [S.campaign?.id || '', '#/'], ['Candidates']], 'every job the loop dispatched, kept whatever became of it')}
		<div class="pb fade"><div class="clist">
		<div class="tools"><div class="seg" id="flt" role="group" aria-label="Which candidates">${Object.entries(F).map(([k, n]) => `<button aria-pressed="${filter === k}" data-f="${k}">${n}<span class="n">${cnt[k]}</span></button>`).join('')}</div><label class="search">${ic('candidates')}<input id="q" aria-label="Filter" placeholder="Filter by id, operator, what changed" value="${esc(query)}"></label></div>
		<div class="tbl"><div class="r rh2 cand-r" id="sorth">${th('id', 'Candidate')}<span>Operator</span><span>What changed</span>${th('fitness', 'Fitness', 'n')}${th('gain', 'On parent', 'n')}${th('lease', 'Lease', 'n')}${th('cost', 'Agent', 'n')}</div>
		${rows.map((r) => `<a class="r cand-r" href="#/candidates/${r.id}${keepQ()}" data-id="${r.id}"${r.id === sel ? ' aria-current="true"' : ''}><span class="id">${r.id}</span><span>${opLabel(r.bad ? 'failed' : r.deferred ? 'deferred' : r.operator)}</span><span class="t" title="${esc(r.title || '')}">${esc(change(r.title) || r.fail_reason || (r.deferred ? 'deferred by the usage window' : ''))}</span><span class="n">${r.fitness != null ? fit(r.fitness) : `<span class="faint">${esc(r.bad ? r.exec : r.deferred ? 'deferred' : '—')}</span>`}</span><span class="n" title="${(r.ref || r.base) ? `against ${(r.ref || r.base).id}` : ''}">${gainHtml(r.delta, r.gain)}</span><span class="n clay">${dur(r.lease)}</span><span class="n clay">${money(r.cost)}</span></a>`).join('')}
		${rows.length ? '' : `<div class="empty">No candidate matches${query ? ` “${esc(query)}”` : ''} among ${F[filter].toLowerCase()}. <button id="clr">Show all</button></div>`}</div>
		</div></div></section>`;
	$('#flt').addEventListener('click', (e) => { const f = e.target.closest('button')?.dataset.f; if (f) { setParam('f', f, 'settled'); centerList(); } });
	$('#sorth').addEventListener('click', (e) => { const s = e.target.closest('button')?.dataset.s; if (!s) return; if (sort === s) setParam('d', String(-dir), String(s === 'id' ? 1 : -1)); else { setParam('s', s, 'id'); setParam('d', null); } centerList(); });
	$('#clr')?.addEventListener('click', () => { setParam('f', 'all', 'settled'); setParam('q', null); centerList(); });
	const q = $('#q');
	q.addEventListener('input', () => { clearTimeout(q._t); q._t = setTimeout(() => { setParam('q', q.value.trim() || null); centerList(); const n = $('#q'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }, 200); });
	const pb = $('#center .pb');
	if (keep != null) pb.scrollTop = keep;
	else if (sel) $('.r[aria-current]', pb)?.scrollIntoView({ block: 'center' });
	if (focused) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
	fadeEdges(pb);
}

async function centerDoc(name) {
	let j;
	try { const res = await fetch(`/api/doc/${encodeURIComponent(name)}`); j = res.ok ? await res.json() : { error: `${name} is not in this campaign.` }; } catch (e) { j = { error: String(e) }; }
	const toc = [];
	const body = j.error ? `<div class="note note--wrong">${esc(j.error)}</div>` : name.endsWith('.md') ? md(j.text || '', toc) : `<pre><code>${esc(j.text || '')}</code></pre>`;
	$('#center').className = 'center one';
	$('#center').innerHTML = `<section class="panel"><div class="ph">${ic('docs')}<span class="t">${esc(name)}</span></div>${crumbs([['Campaigns', '#/'], [S.campaign?.id || '', '#/'], ['Documents', '#/docs'], [name]])}<div class="pb fade"><div class="doc"><article class="prose">${body}</article></div></div></section>`;
	fadeAll();
	return toc;
}

/* ------------------------------------------------------------------ the inspector */
const cell = (k, v, s = '', isVoid = false, sm = false) => `<div class="cell${isVoid ? ' cell--void' : ''}"><dt>${k}</dt><dd${sm ? ' class="sm"' : ''}>${v}</dd>${s ? `<small>${s}</small>` : ''}</div>`;
function headline() {
	const c = S.campaign || {}, f = S.final, b = D.best, p = S.pop;
	if (f?.score != null) return p.claim === 'supported' ? `${f.candidate} cleared ${lit(c.threshold)} on its one final read` : `No candidate cleared ${lit(c.threshold)} on the final read`;
	if (p.status === 'finished') return 'Finished without a final read';
	return b ? `${b.id} leads after ${num(p.settled)} of ${c.max_candidates ?? '—'}` : 'Waiting for the first score';
}
// what a reader needs to judge the headline: the margin, search against final, the runner-up, when the best came, why it stopped
function evidence() {
	const c = S.campaign || {}, f = S.final, p = S.pop || {}, b = D.best, out = [];
	if (f?.score != null && c.threshold != null) out.push(`The final read is <b>${signed(f.score - c.threshold)}</b> from the threshold.`);
	if (f?.score != null && b?.id === f.candidate) { const d = f.score - b.fitness; out.push(`Final against search: <b>${signed(d)}</b>${(D.hib ? d : -d) > 0 ? ', higher than its search score, which is usually optimistic' : ''}.`); }
	const ru = D.leaders.find((r) => r.id !== b?.id);
	if (ru && b) out.push(`The runner-up, <a class="cid" href="${candHref(ru.id)}">${ru.id}</a>, is <b>${signed(ru.fitness - b.fitness)}</b> behind on search and was never read on the final split.`);
	if (p.settled_at_best != null) out.push(`The last new best came at settled job <b>${p.settled_at_best}</b> of ${p.settled}.`);
	if (p.stop_reason) out.push(`It ended ${tick(p.stop_reason)}${D.deferredJobs.size ? `, with ${plural(D.deferredJobs.size, 'job')} still waiting on the usage window` : ''}.`);
	return out.length ? `<ul class="evid">${out.map((x) => `<li><span class="mk"><i class="sq"></i></span><span>${x}</span></li>`).join('')}</ul>` : '';
}
function inspCampaign() {
	const c = S.campaign || {}, p = S.pop || {}, f = S.final, b = D.best;
	const ops = OP_ORDER.filter((o) => o !== 'baseline' && D.rows.some((r) => r.operator === o));
	const lead = D.leaders.slice(0, 8);
	const [lo, hi] = fitDomain(lead, [c.threshold]);
	const P = (v) => `${(100 * (v - lo)) / (hi - lo)}%`;
	const jobs = (o) => { const seen = new Set(); return D.rows.filter((r) => r.operator === o && !seen.has(r.root) && seen.add(r.root)); };
	const maxJobs = Math.max(1, ...ops.map((o) => jobs(o).length));
	const cl = p.claim;
	$('#insp').innerHTML = `<div class="ph">${ic('overview')}<span class="t">Campaign</span></div>
		${crumbs([['Campaigns', '#/'], [c.id || '']], `${esc(model(c.worker_model))} workers`)}
		<div class="pb fade"><div class="ib">
		<div class="ihead"><div class="meta"><span>${num(p.settled ?? 0)} of ${c.max_candidates ?? '—'} settled · ${esc(c.memory || c.kind || '')}</span>${claimChip()}</div><h1>${esc(headline())}</h1><p>${p.finished ? `Finished ${when(ep(p.finished))} after ${dur((ep(p.finished) - ep(p.started)) / 1000)}. ` : `Started ${when(ep(p.started))}. `}Workers ${esc(model(c.worker_model))}${Object.keys(c.models_by_operator || {}).length ? `; ${Object.entries(c.models_by_operator).map(([o, m]) => `${esc(model(m))} for ${o}`).join(', ')}` : ''}. ${c.eval_user ? `Labels hidden by the OS (${esc(c.eval_user)}).` : 'Labels hidden by convention.'}</p></div>
		${evidence()}
		<dl class="cells">
			${cell('Settled', `${num(p.settled ?? 0)}`, `of ${c.max_candidates ?? '—'}${D.deferredJobs.size ? ` · ${D.deferredJobs.size} deferred` : ''}`)}
			${cell('Best on search', b ? fit(b.fitness) : '—', b ? `${b.id}, ${(OPS[b.operator] || '').toLowerCase()}` : 'nothing scored', !b)}
			${cell('Final read', f?.score != null ? fit(f.score) : '—', `threshold ${lit(c.threshold)}`, f?.score == null)}
			${cell('Baseline', D.baseline?.fitness != null ? fit(D.baseline.fitness) : '—', D.baseline ? `${D.baseline.id}, the floor` : '', D.baseline?.fitness == null)}
			${cell('GPU hours', ((p.gpu_seconds || 0) / 3600).toFixed(1), `of ${c.gpu_hours_total ?? '—'} budgeted`)}
			${cell('Agent', money(D.cost), `${D.sessions} sessions`)}
		</dl>
		<div class="blk"><div class="bh"><h3>The leaders</h3><a class="end" href="#/candidates?s=fitness">All ${D.live.length}</a></div><div class="tbl"><div class="r rh2 lead-r"><span>Candidate</span><span title="Each leader's search fitness on a shared scale; the tick is the threshold">Scale <span class="faint">· tick ${lit(c.threshold)}</span></span><span class="n">Fitness</span><span class="n" title="Against its parent; a crossover against the better parent; a draft against the candidate whose code it started from">On parent</span></div>${lead.map((r) => `<a class="r lead-r" href="${candHref(r.id)}" data-id="${r.id}"${r.id === selId() ? ' aria-current="true"' : ''}><span class="id op" title="${esc(OPS[r.operator])}">${opMark(r.operator, 9)}${r.id}</span><span class="trk">${c.threshold != null ? `<i class="tk" style="left:${P(c.threshold)}"></i>` : ''}<svg viewBox="-6 -6 12 12" style="left:${P(r.fitness)}">${mark(r.operator, 0, 0, 4.6)}</svg></span><span class="n">${fit(r.fitness)}</span><span class="n">${gainHtml(r.delta, r.gain)}</span></a>`).join('')}</div></div>
		<div class="blk"><div class="bh"><h3>Where the jobs went</h3><span class="end">jobs, each counted once however often it was deferred</span></div><div class="figsheet"><div class="in">${ops.map((o) => {
			const rs = jobs(o), s1 = rs.filter((r) => D.rows.some((x) => x.root === r.root && x.fitness != null)).length, s2 = rs.filter((r) => D.rows.some((x) => x.root === r.root && x.bad)).length, s4 = rs.filter((r) => D.rows.some((x) => x.root === r.root && x.running)).length, s3 = rs.length - s1 - s2 - s4;
			const w = (n) => `${(100 * n) / maxJobs}%`;
			return `<div class="hb"><span class="op">${opMark(o)}${OPS[o]}</span><div class="stack">${s1 ? `<i style="width:${w(s1)};background:${OPC[o]}"></i>` : ''}${s4 ? `<i style="width:${w(s4)};background:var(--color-signal)"></i>` : ''}${s2 ? `<i style="width:${w(s2)};background:var(--color-clay)"></i>` : ''}${s3 > 0 ? `<i class="hatch" style="width:${w(s3)}"></i>` : ''}</div><span class="n">${s1} of ${rs.length}</span></div>`;
		}).join('')}</div><div class="legend"><span><i class="sq" style="background:var(--color-faint)"></i>Scored, in its operator's colour</span><span><i class="sq" style="background:var(--color-clay)"></i>Failed</span><span><i class="sq hatch"></i>Deferred</span></div></div></div>
		<div class="note ${cl === 'supported' ? 'note--right' : cl === 'not_supported' ? 'note--wrong' : ''}"><b>${cl === 'supported' ? 'The claim holds' : cl === 'not_supported' ? 'The claim does not hold' : cl === 'inconclusive' ? 'The claim is inconclusive' : 'The claim is read at the end'}</b>${f?.score != null ? `${f.candidate} read ${fit(f.score)} on the final split, once, against the ${lit(c.threshold)} fixed in campaign.toml before the run. Search scores are optimistic by construction; only this read supports a claim.` : `The best candidate is read once on the final split when the campaign ends, against the ${lit(c.threshold)} fixed before the run.`}${S.docs?.includes('REPORT.md') ? ' <a href="#/docs/REPORT.md">Read the report</a>.' : ''}</div>
	</div></div>`;
	fadeAll();
}
function partStrips(rec, comps) {
	const w = partWeights();
	return Object.entries(comps).filter(([, v]) => typeof v === 'number').map(([k, v]) => {
		const all = D.scored.map((x) => x.components?.[k]).filter((x) => typeof x === 'number' && isFinite(x)).sort((a, b) => a - b);
		const base = D.baseline?.components?.[k];
		const core = all.filter((x) => x !== base);
		const lo = Math.min(...core, v), hi = Math.max(...core, v), X = (x) => 2 + ((Math.max(lo, Math.min(hi, x)) - lo) / (hi - lo || 1)) * 96;
		const off = w && !w[k];
		return `<div class="part${off ? ' off' : ''}"><span class="k">${esc(k)}<small>${w ? (w[k] ? `× ${w[k]} in fitness` : 'not in fitness') : ''}</small></span><svg viewBox="0 0 100 18" preserveAspectRatio="none"><line x1="0" x2="100" y1="9" y2="9" style="stroke:var(--color-line)" vector-effect="non-scaling-stroke"/>${core.map((x) => `<line x1="${X(x)}" x2="${X(x)}" y1="5" y2="13" style="stroke:var(--color-faint);opacity:.5" vector-effect="non-scaling-stroke"/>`).join('')}${D.best?.components?.[k] != null ? `<line x1="${X(D.best.components[k])}" x2="${X(D.best.components[k])}" y1="2" y2="16" style="stroke:var(--color-ink)" vector-effect="non-scaling-stroke"/>` : ''}<line x1="${X(v)}" x2="${X(v)}" y1="1" y2="17" style="stroke:${OPC[rec.operator] || 'var(--color-ink)'};stroke-width:3" vector-effect="non-scaling-stroke"/></svg><span class="v">${fit(v)}</span></div>`;
	}).join('');
}
async function inspCandidate(id) {
	const r = D.by[id];
	let c;
	try { const res = await fetch(`/api/candidate/${id}`); c = res.ok ? await res.json() : { error: `No candidate ${id} in this campaign.` }; } catch (e) { c = { error: String(e) }; }
	if (selId() !== id) return;
	if (c.error) { $('#insp').innerHTML = `<div class="ph"><span class="t">${esc(id)}</span><span class="end"><a class="pill pill--sm pill--round pill--ghost" href="${closeHref()}" aria-label="Close">${ic('x')}</a></span></div><div class="pb"><div class="ib"><div class="note note--wrong">${esc(c.error)}</div></div></div>`; return; }
	const rec = c.record || {}, fj = c.fitness || {}, fin = fj.final?.score;
	const comps = rec.components || fj.search?.components;
	const parts = comps && typeof comps === 'object' ? partStrips(rec, comps) : '';
	const fam = family(id);
	const famRows = D.rows.filter((x) => fam.has(x.id) && !x.deferred);
	const ftree = [];
	let lastDir = null;
	for (const f of c.files || []) {
		const d = f.path.includes('/') ? f.path.slice(0, f.path.lastIndexOf('/')) : '';
		if (d !== lastDir) { ftree.push(`<div class="dir">${esc(d || 'this candidate')}</div>`); lastDir = d; }
		const kb = f.size < 1024 ? `${f.size} B` : f.size < 1048576 ? `${(f.size / 1024).toFixed(0)} KB` : `${(f.size / 1048576).toFixed(1)} MB`;
		ftree.push(`<button data-f="${esc(f.path)}"><span class="p">${esc(f.path.slice(d ? d.length + 1 : 0))}</span><span class="sz">${kb}</span></button>`);
	}
	const json = (o) => esc(JSON.stringify(o, null, 2));
	const st = r?.running ? `running, ${r.phase || ''}` : r?.bad ? rec.exec : r?.deferred ? 'deferred' : rec.status;
	const order = parseRoute().view === 'candidates' ? listRows() : D.live;
	const i = order.findIndex((x) => x.id === id), prev = order[i - 1], next = order[i + 1];
	const vsIds = [...new Set([...(rec.parents || []), r?.base?.id, D.best && D.best.id !== id ? D.best.id : null].filter((x) => x && D.by[x]))];
	const tabs = [['summary', 'Summary', ''], ...(vsIds.length ? [['diff', 'Diff', '']] : []), ['files', 'Files', (c.files || []).length], ['records', 'Records', '']];
	const ks = tabs.map((t) => t[0]);
	const tab = ks.includes(param('tab')) ? param('tab') : r?.bad ? 'files' : 'summary';
	let vsNow = vsIds.includes(param('vs')) ? param('vs') : vsIds[0];
	const vsName = (x) => (rec.parents?.includes(x) ? 'parent' : x === r?.base?.id ? 'its code' : 'the best');
	const vs = r?.ref || r?.base;
	const sess = rec.session && rec.session.cost_usd != null ? rec.session : null;
	const title = /^#?\s*summary\b/i.test(c.title || '') ? `${OPS[rec.operator] || rec.operator || ''}, ${r?.bad ? rec.exec : r?.deferred ? 'deferred' : rec.status}` : c.title || '', long = title.length > 90;
	const why = r?.bad || r?.deferred ? `<div class="note note--wrong"><b>Why it ${r.bad ? 'failed' : 'was deferred'}</b>${esc(rec.fail_reason || (r.deferred ? 'pushed out by the usage window, then dispatched again' : rec.exec || '')).replace(/(^|\s)(--?[\w-]+)/g, '$1<code class="code">$2</code>')}${rec.exit_code != null ? `. Exit code ${rec.exit_code}` : ''}${rec.launched && rec.ended ? `, after ${dur((ep(rec.ended) - ep(rec.launched)) / 1000)}` : ''}.${(c.files || []).some((f) => /stderr|\.log$/.test(f.path)) ? ' Its log is open under Files.' : ''}</div>` : '';
	$('#insp').innerHTML = `<div class="ph">${mk(r?.bad ? 'failed' : r?.deferred ? 'deferred' : rec.operator, 11)}<span class="t">${id}</span><span class="s">${esc(OPS[rec.operator] || rec.operator || '')}</span><span class="end">
			<a class="pill pill--sm pill--round pill--ghost" ${prev ? `href="${candHref(prev.id)}"` : 'aria-disabled="true" style="opacity:.35;pointer-events:none"'} aria-label="Previous candidate${prev ? `, ${prev.id}` : ''}" title="${prev ? `${prev.id} (k)` : ''}">${ic('prev')}</a>
			<a class="pill pill--sm pill--round pill--ghost" ${next ? `href="${candHref(next.id)}"` : 'aria-disabled="true" style="opacity:.35;pointer-events:none"'} aria-label="Next candidate${next ? `, ${next.id}` : ''}" title="${next ? `${next.id} (j)` : ''}">${ic('next')}</a>
			<a class="pill pill--sm pill--round pill--ghost" href="${closeHref()}" aria-label="Close" title="Close (Esc)">${ic('x')}</a></span></div>
		${crumbs([[S.campaign?.id || '', '#/'], ['Candidates', '#/candidates'], [id]], `${i >= 0 ? `${i + 1} of ${order.length}` : ''}`)}
		<div class="pb fade"><div class="ib">
		<div class="ihead">
			<div class="pills">${opLabel(rec.operator)}${rec.parents?.length ? `<span class="clay">of</span>${rec.parents.map((p) => `<a class="pill pill--sm" href="${candHref(p)}">${p}</a>`).join('')}` : r?.base ? `<span class="clay">on the code of</span><a class="pill pill--sm" href="${candHref(r.base.id)}">${r.base.id}</a>` : ''}<span class="chip">${esc(st || '')}</span>${id === S.pop?.best ? '<span class="chip pill--right"><b>Best on search</b></span>' : ''}</div>
			<h1${long ? ' class="long" id="ttl"' : ''}>${esc(change(title) || id)}</h1>${long ? '<button class="more" id="more">Show all</button>' : ''}
			<div><button class="pill pill--sm" id="askabout">${ic('ask')}Ask about it</button></div>
		</div>
		${why}
		<dl class="cells">
			${cell('Search', rec.fitness != null ? fit(rec.fitness) : 'none', rec.fitness != null ? `n = ${num(rec.n)}` : esc(rec.exec || ''), rec.fitness == null)}
			${cell('On parent', r?.delta != null ? gainHtml(r.delta, r.gain) : '—', vs ? `against ${vs.id}${r.base ? ', its code' : ''}` : rec.operator === 'draft' ? 'a fresh draft' : '', r?.delta == null)}
			${cell('Final', fin != null ? fit(fin) : 'not read', fin != null ? `threshold ${lit(S.campaign?.threshold)}` : 'only the best is read', fin == null)}
			${cell('Lease', dur(r?.lease), (c.config?.train_seconds || r?.train) ? `trained ${dur(c.config?.train_seconds || r?.train)}` : '', r?.lease == null, true)}
			${cell('Agent', sess ? money(sess.cost_usd) : '—', sess ? `${sess.turns ?? '—'} turns, ${esc(model(r?.model))}` : 'no session', !sess, true)}
			${cell('Launched', rec.launched ? hm(ep(rec.launched)) : '—', rec.launched ? `${day(ep(rec.launched))}${rec.gpu != null ? ` · GPU ${rec.gpu}` : ''}` : '', !rec.launched, true)}
		</dl>
		${parts ? `<div class="blk"><div class="bh"><h3>Parts of the score</h3><span class="end">every candidate a tick, the best in ink, this one in colour</span></div><div class="figsheet"><div class="parts">${parts}</div></div></div>` : ''}
		${famRows.length > 1 ? `<div class="blk"><div class="bh"><h3>Its line</h3><span class="end">what it came from, and what came of it</span></div><div class="tbl">${famRows.map((x) => `<a class="r" href="${candHref(x.id)}" style="grid-template-columns:12px 50px minmax(0,1fr) 56px 64px"${x.id === id ? ' aria-current="true"' : ''}>${mk(x.bad ? 'failed' : x.operator)}<span class="id">${x.id}</span><span class="t clay">${esc(change(x.title))}</span><span class="n">${fit(x.fitness)}</span><span class="n">${gainHtml(x.delta, x.gain)}</span></a>`).join('')}</div></div>` : ''}
		<div class="blk"><div class="tabs" id="tabs" role="tablist">${tabs.map(([k, n, x]) => `<button role="tab" aria-selected="${tab === k}" aria-pressed="${tab === k}" data-t="${k}">${n}${x !== '' ? `<span class="n">${x}</span>` : ''}</button>`).join('')}</div>
			<div id="tab-summary"${tab === 'summary' ? '' : ' hidden'}>${c.summary ? `<div class="prose">${md(c.summary)}</div>` : `<p class="clay">No summary yet${r?.running ? ': the worker writes it when its session ends.' : '.'}</p>`}</div>
			${vsIds.length ? `<div id="tab-diff"${tab === 'diff' ? '' : ' hidden'}><div class="dhead"><span class="clay">Against</span><div class="seg" id="vsseg" role="group" aria-label="Compare with">${vsIds.map((x) => `<button aria-pressed="${x === vsNow}" data-vs="${x}">${x}<span class="n">${vsName(x)}</span></button>`).join('')}</div></div><div id="diffb"><div class="e clay">Reading both.</div></div></div>` : ''}
			<div id="tab-files"${tab === 'files' ? '' : ' hidden'}><div class="files" id="files">${ftree.join('') || '<span class="clay">none</span>'}</div><div class="viewer" id="viewer" style="margin-top:8px"><div class="e">Choose a file.</div></div></div>
			<div id="tab-records"${tab === 'records' ? '' : ' hidden'}>${[['fitness.json', c.fitness], ['finding.json', c.finding], ['config.json', c.config], ['job.json', c.job], ['population record', rec]].filter(([, o]) => o).map(([n, o]) => `<details class="rec"><summary><span>${n}</span><span>${Object.keys(o).length} keys</span></summary><pre>${json(o)}</pre></details>`).join('')}</div>
		</div>
	</div></div>`;
	const open = async (path) => {
		$('#files').querySelectorAll('button').forEach((b) => b.toggleAttribute('aria-current', b.dataset.f === path));
		const j = await (await fetch(`/api/candidate/${id}/file?path=${encodeURIComponent(path)}`)).json();
		$('#viewer').innerHTML = j.error ? `<div class="e">${esc(j.error)}</div>` : !j.binary && !j.text ? '<div class="e">An empty file.</div>' : j.binary ? '<div class="e">A binary file. Not shown.</div>' : path.endsWith('.md') ? `<div class="prose" style="padding:12px 14px">${md(j.text)}</div>` : `<pre>${esc(j.text)}</pre>`;
	};
	let diffFor = null;
	const loadDiff = async (vs) => {
		if (diffFor === vs) return;
		diffFor = vs;
		const el = $('#diffb');
		let j;
		try { const res = await fetch(`/api/candidate/${id}/diff?against=${vs}`); j = res.ok ? await res.json() : { error: res.status === 404 ? 'This server predates diffs: restart lab ui.' : `HTTP ${res.status}` }; } catch (e) { j = { error: String(e) }; }
		if (diffFor !== vs || !el.isConnected) return;
		if (j.error) { el.innerHTML = `<div class="note">${esc(j.error)}</div>`; return; }
		const fs = j.files || [], add = fs.reduce((a, f) => a + (f.adds || 0), 0), del = fs.reduce((a, f) => a + (f.dels || 0), 0);
		const line = (l) => `<span class="${l.startsWith('@@') ? 'h' : l[0] === '+' ? 'a' : l[0] === '-' ? 'd' : 'c'}">${esc(l) || ' '}</span>`;
		el.innerHTML = `<p class="dsum">${fs.length ? `${plural(fs.length, 'file')} changed in <code class="code">code/</code>, <span class="up">+${num(add)}</span> <span class="down">−${num(del)}</span>` : 'The same code, file for file.'}${j.same ? `<span class="faint"> · ${plural(j.same, 'file')} unchanged</span>` : ''}</p>
			${fs.map((f, i) => `<details class="dfile"${i < 3 ? ' open' : ''}><summary><span class="p">${esc(f.path)}</span>${f.status !== 'changed' ? `<span class="chip">${f.status}</span>` : ''}${f.binary ? '<span class="faint">binary</span>' : `<span class="up">+${f.adds}</span><span class="down">−${f.dels}</span>`}</summary>${f.binary ? '' : `<pre class="diff">${(f.diff || '').split('\n').map(line).join('')}</pre>`}</details>`).join('')}`;
	};
	const openFirst = () => { const fs = c.files || []; const f = (r?.bad && fs.find((x) => /stderr|\.log$/.test(x.path))) || fs.find((x) => x.path === 'code/run.sh') || fs.find((x) => x.path.startsWith('code/')) || fs[0]; if (f) open(f.path); };
	const pick = (t) => {
		setParam('tab', t, r?.bad ? 'files' : 'summary');
		$('#tabs').querySelectorAll('button').forEach((b) => { b.setAttribute('aria-pressed', b.dataset.t === t); b.setAttribute('aria-selected', b.dataset.t === t); });
		for (const k of ks) $(`#tab-${k}`).hidden = k !== t;
		if (t === 'files' && !$('#files [aria-current]')) openFirst();
		if (t === 'diff') loadDiff(vsNow);
		fadeAll();
	};
	$('#tabs').addEventListener('click', (e) => { const t = e.target.closest('button')?.dataset.t; if (t) pick(t); });
	$('#tabs').addEventListener('keydown', (e) => { if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return; const cur = ks.indexOf(param('tab', r?.bad ? 'files' : 'summary')); const t = ks[(cur + (e.key === 'ArrowRight' ? 1 : ks.length - 1)) % ks.length]; pick(t); $(`#tabs [data-t="${t}"]`).focus(); });
	$('#files').addEventListener('click', (e) => { const f = e.target.closest('button')?.dataset.f; if (f) open(f); });
	$('#askabout').addEventListener('click', () => { setChat(true); renderChat(`What did ${id} try, and what came of it?`); });
	$('#more')?.addEventListener('click', (e) => { const t = $('#ttl'); t.classList.toggle('open'); e.target.textContent = t.classList.contains('open') ? 'Show less' : 'Show all'; });
	$('#vsseg')?.addEventListener('click', (e) => { const x = e.target.closest('button')?.dataset.vs; if (!x) return; vsNow = x; setParam('vs', x, vsIds[0]); $$('#vsseg button').forEach((b) => b.setAttribute('aria-pressed', b.dataset.vs === x)); loadDiff(x); });
	if (tab === 'files') openFirst();
	if (tab === 'diff') loadDiff(vsNow);
	fadeAll();
}

function inspDocs(name, toc) {
	const docs = S.docs || [];
	$('#insp').innerHTML = `<div class="ph">${ic('docs')}<span class="t">Documents</span><span class="s">${docs.length}</span></div>
		${crumbs([[S.campaign?.id || '', '#/'], ['Documents']])}
		<div class="pb fade"><div class="ib">
		<div class="blk"><div class="tbl">${docs.map((d) => `<a class="r" href="#/docs/${d}" style="grid-template-columns:16px minmax(0,1fr)"${d === name ? ' aria-current="true"' : ''}>${ic('docs')}<span>${esc(d)}</span></a>`).join('')}</div></div>
		${toc.length ? `<div class="blk"><div class="bh"><h3>In ${esc(name)}</h3><span class="end">${plural(toc.length, 'section')}</span></div><nav class="toc">${toc.map((t) => `<a class="l${t.n}" href="#" data-to="${t.id}">${esc(t.text)}</a>`).join('')}</nav></div>` : ''}
	</div></div>`;
	$('#insp .toc')?.addEventListener('click', (e) => { const a = e.target.closest('a'); if (!a) return; e.preventDefault(); document.getElementById(a.dataset.to)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
	fadeAll();
}

/* ------------------------------------------------------------------ rendering and the cadence */
const sig = () => [S.pop?.updated_at, S.rows?.length, S.events?.length, D.running.map((r) => r.id + r.phase).join(','), S.pop?.status].join('|');
const selSig = (id) => { const r = id && D.by[id]; return r ? [r.status, r.exec, r.phase, r.fitness].join('|') : ''; };

async function renderAll(force = false) {
	if (!S) return;
	const r = parseRoute(), key = JSON.stringify(routeKey()), changed = key !== lastRoute, s = sig();
	const selChanged = r.id && selSig(r.id) !== lastSel;
	if (!force && !changed && s === lastSig) return;
	const dataOnly = !changed && !force;
	lastSig = s;
	lastRoute = key;
	lastSel = selSig(r.id);
	hideTip();
	const ins = $('#insp');
	if (ins.classList.contains('sk')) { ins.classList.remove('sk'); ins.removeAttribute('aria-busy'); }
	applyLayout();
	renderDeskbar();
	renderRail();
	if (lay.chat && (!$('#chat .compose') || force)) renderChat();
	if (S.empty) { $('#center').className = 'center one'; $('#center').innerHTML = `<section class="panel"><div class="load">No population.json in ${esc(S.root)} yet: <code class="code">lab run</code> writes it when the campaign starts, and this page fills in on its own.</div></section>`; $('#insp').innerHTML = ''; fadeAll(); return; }
	if (r.view === 'ask') { setChat(true); location.hash = '#/'; return; }
	if (r.id && !D.by[r.id]) { $('#insp').innerHTML = `<div class="ph"><span class="t">${esc(r.id)}</span><span class="end"><a class="pill pill--sm pill--round pill--ghost" href="${closeHref()}" aria-label="Close">${ic('x')}</a></span></div><div class="pb"><div class="ib"><div class="note">No candidate ${esc(r.id)} in this campaign.</div></div></div>`; }
	if (r.view === 'overview') { centerViewer(); if (!r.id) inspCampaign(); else if (D.by[r.id] && (!dataOnly || selChanged)) await inspCandidate(r.id); }
	else if (r.view === 'candidates') { centerList(); if (!r.id) inspCampaign(); else if (D.by[r.id] && (!dataOnly || selChanged)) await inspCandidate(r.id); }
	else if (r.view === 'docs') { if (dataOnly) return; const name = r.name || (S.docs?.includes('REPORT.md') ? 'REPORT.md' : S.docs?.[0]); if (!name) return; const toc = await centerDoc(name); inspDocs(name, toc); }
	else location.hash = '#/';
	document.title = `${r.id ? r.id + ' · ' : ''}${S.campaign?.id || 'labloop'} · labloop`;
	fadeAll();
}

async function poll() {
	clearTimeout(pollTimer);
	try {
		const res = await fetch('/api/state');
		if (!res.ok) throw new Error(`HTTP ${res.status}`);
		S = await res.json();
		D = derive();
		if (offline) { offline = false; renderDeskbar(); }
		if (!ui.chat.length) loadChat();
		await renderAll();
	} catch (e) {
		console.error(e);
		if (!offline) { offline = Date.now(); if (S) renderDeskbar(); }
		const ld = $('#load');
		if (ld && !S) { ld.classList.add('bad'); ld.innerHTML = `<i class="lamp"></i><span>Not reaching the server. Trying again.</span>`; }
	}
	// before the first read, try again soon; after it, as often as the campaign changes
	const live = ['running', 'waiting_usage', 'stopping'].includes(S?.pop?.status) || S?.empty;
	pollTimer = setTimeout(poll, !S ? 3000 : document.hidden ? 60000 : live ? 5000 : 60000);
}

addEventListener('hashchange', () => renderAll());
document.addEventListener('keydown', (e) => {
	if (e.metaKey || e.ctrlKey || e.altKey) return;
	const typing = /^(input|textarea|select)$/i.test(document.activeElement?.tagName || '');
	if (e.key === 'Escape') {
		if (typing) { document.activeElement.blur(); return; }
		if (lay.chat && $('#chat').contains(document.activeElement)) { setChat(false); return; }
		if (selId()) { location.hash = closeHref(); return; }
		if (lay.chat) setChat(false);
		return;
	}
	if (typing) return;
	if (e.key === '/') { e.preventDefault(); if (lay.rail === 'min') { lay.rail = 'open'; saveLay(); applyLayout(); renderRail(); } $('#rq')?.focus(); return; }
	if (e.key === 'j' || e.key === 'k') {
		const r = parseRoute(), order = r.view === 'candidates' ? listRows() : D.live;
		if (!order.length) return;
		const i = order.findIndex((x) => x.id === r.id), n = order[Math.max(0, Math.min(order.length - 1, i < 0 ? 0 : i + (e.key === 'j' ? 1 : -1)))];
		if (n) location.hash = candHref(n.id);
		return;
	}
	if (e.key === '[' || e.key === ']') { const bs = $$('#tabs button'); bs[(bs.findIndex((b) => b.getAttribute('aria-pressed') === 'true') + (e.key === ']' ? 1 : bs.length - 1)) % bs.length]?.click(); }
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
let rz;
addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(drawFigures, 150); });
applyLayout();
setTimeout(() => { const ld = $('#load'); if (ld && !S && !ld.classList.contains('bad')) ld.lastElementChild.textContent = 'Still reading: a long campaign takes a few seconds'; }, 4000);
poll();
