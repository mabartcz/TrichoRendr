// TrichoRendr window. Ruby pushes the whole state with update(state); buttons call sketchup.<callback>.
// Everything here also goes to %LOCALAPPDATA%/TrichoRendr/logs/plugin.log through Ruby.
const log = msg => { try { sketchup.log(String(msg)); } catch (e) {} };
window.onerror = (msg, src, line, col) => log(`error: ${msg} @${line}:${col}`);
const $ = id => document.getElementById(id);
let S = {}, tab = 'view', inited = false, pinned = null, sentSize = null;
const checked = {}; // scene name -> bool; new scenes default to checked

function fmt(sec) {
  sec = Math.round(sec);
  return sec >= 60 ? `${Math.floor(sec / 60)} min ${String(sec % 60).padStart(2, '0')} s` : `${sec} s`;
}

function radio(name) { return document.querySelector(`input[name=${name}]:checked`).value; }

// {width, height}; height 0 = follow the viewport's shape
function size() {
  const v = $('width').value;
  if (v === 'custom') return { width: +$('cw').value || 3000, height: +$('ch').value || 1300 };
  const [w, h] = v.split('x');
  return { width: +w, height: +(h || 0) };
}

// Look tab, built from this list: [heading] | [key, label, min, max, step, unit] | [key, label, kind, options]
const LOOK_UI = [
  ['Light'],
  ['shadows', 'Sun and shadows', 'check', 'Off = soft overcast light from the sky only. Day uses the sun position from SketchUp (Shadows settings).'],
  ['time', 'Sky', 'seg', [['day', 'Day'], ['sunset', 'Sunset'], ['evening', 'Evening']]],
  ['sun', 'Sun strength', 0, 300, 5, ' %'],
  ['softness', 'Shadow softness', 0, 100, 1, ''],
  ['sky', 'Sky light', 0, 300, 5, ' %'],
  ['haze', 'Haze in the distance', 0, 100, 5, ' %'],
  ['Image'],
  ['style', 'Style', 'select', [['natural', 'Natural'], ['soft', 'Soft (matte, airy)'], ['punchy', 'Punchy'], ['contrast', 'High contrast'],
                                ['vivid', 'Vivid (flat colors, bright)']]],
  ['exposure', 'Brightness', -3, 3, 0.1, ' EV'],
  ['saturation', 'Saturation', 0, 200, 5, ' %'],
  ['warmth', 'Warmth', -100, 100, 5, ''],
  ['glow', 'Glow around bright areas', 0, 100, 5, ' %'],
  ['flare', 'Lens flare (sun in the picture)', 0, 100, 5, ' %'],
  ['background', 'Background', 'seg', [['sky', 'Sky'], ['white', 'White'], ['transparent', 'Transparent']]],
  ['Materials'],
  ['water_tint', 'Water color', 0, 100, 5, ' %'],
  ['waves', 'Water ripples', 0, 200, 5, ' %'],
  ['glass', 'Glass reflections', 0, 200, 5, ' %'],
  ['leaves', 'Sun through leaves', 0, 100, 5, ' %'],
  ['lamps', 'Glowing materials', 0, 500, 10, ' %'],
];
const lookDefaults = () => S.look_defaults || {};
// Look presets, in the style of landscape studio visualisations: each sets every Look setting, light,
// image, background and materials. Built-in ones can't be deleted; her own ones (name + look) are saved with
// the settings.
const MOOD = LOOK_UI.filter(([, label]) => label).map(([key]) => key);
// The tuned everyday look; the other built-in presets change only a few keys of it. (The sliders' defaults are
// neutral: 100 %, 0 EV.)
const BASIC = { shadows: true, time: 'day', sun: 105, softness: 10, sky: 115, haze: 0, style: 'natural', exposure: 0.8,
                saturation: 100, warmth: 90, glow: 0, flare: 0, background: 'sky', water_tint: 50, waves: 50, glass: 100,
                leaves: 20, lamps: 100 };
const PRESETS = {
  basic: ['Basic · balanced everyday light', {}],
  airy: ['Airy day · soft light, hazy distance',
         { style: 'soft', haze: 35, sky: 130, softness: 25, saturation: 95, warmth: 100, glow: 10, exposure: 1.6 }],
  sunset: ['Warm sunset · low sun, glow', { time: 'sunset', style: 'soft', haze: 40, glow: 20, flare: 30, warmth: 100, exposure: 1.4 }],
  evening: ['Blue hour · dusk sky, lamps on', { time: 'evening', lamps: 300, glow: 30, haze: 25, saturation: 90, exposure: 1.4 }],
  plan: ['Soft plan · gentle shadows, calm colors', { style: 'soft', softness: 60, saturation: 85, exposure: 1.6 }],
};
let mine = []; // [{name, look}]

// Preset id -> its look values: 'airy' etc. or 'my:<index>'.
function presetLook(id) {
  const p = id.startsWith('my:') ? mine[+id.slice(3)]?.look : PRESETS[id]?.[1];
  if (!p) return null;
  return Object.fromEntries(MOOD.map(k => [k, id.startsWith('my:') ? p[k] : (k in p ? p[k] : BASIC[k])]));
}

function buildMoods() {
  const sel = $('mood'), group = (label, items) => {
    const g = document.createElement('optgroup');
    g.label = label;
    items.forEach(([v, t]) => g.append(new Option(t, v)));
    return g;
  };
  sel.replaceChildren(new Option('Custom settings', ''),
                      group('Presets', Object.entries(PRESETS).map(([id, [label]]) => [id, label])));
  if (mine.length) sel.append(group('My presets', mine.map((p, i) => [`my:${i}`, p.name])));
}

// The preset list shows which preset the current settings are (her own first), or "Custom settings".
function moodSync() {
  const v = lookValues(), ids = [...mine.map((_, i) => `my:${i}`), ...Object.keys(PRESETS)];
  $('mood').value = ids.find(id => { const p = presetLook(id); return MOOD.every(k => p[k] === v[k]); }) || '';
  $('mood-delete').hidden = !$('mood').value.startsWith('my:');
}

function buildLook() {
  const root = $('look');
  LOOK_UI.forEach(([key, label, a, b, step, unit]) => {
    if (!label) {
      const f = document.createElement('fieldset'), l = document.createElement('legend');
      l.textContent = key;
      f.append(l);
      root.append(f);
      return;
    }
    const row = document.createElement('div'), name = document.createElement('span');
    row.className = 'ctl';
    row.id = `ctl-${key}`;
    name.textContent = label;
    if (a === 'check') {
      row.innerHTML = `<label class="check"><input type="checkbox" id="look-${key}"><span>${label}</span></label>`;
      row.title = b;
    } else if (a === 'select') {
      const input = document.createElement('select');
      input.id = `look-${key}`;
      b.forEach(([v, t]) => input.add(new Option(t, v)));
      row.append(name, input);
    } else if (a === 'seg') {
      const input = document.createElement('div');
      input.className = 'seg';
      input.innerHTML = b.map(([v, t]) =>
        `<label><input type="radio" name="look-${key}" value="${v}"><span>${t}</span></label>`).join('');
      row.append(name, input);
    } else {
      const input = Object.assign(document.createElement('input'), { type: 'range', min: a, max: b, step });
      const out = document.createElement('output');
      input.id = `look-${key}`;
      input.oninput = () => { out.textContent = `${(+input.value).toFixed(step < 1 ? 1 : 0)}${unit}`; lookSync(); };
      input.ondblclick = () => { if (!S.busy) { input.value = lookDefaults()[key]; input.oninput(); saveSettings(); } };
      row.append(name, out, input);
    }
    root.lastChild.append(row);
  });
}

function lookValues() {
  const v = {};
  LOOK_UI.forEach(([key, label, a]) => {
    if (!label) return;
    if (a === 'check') v[key] = $(`look-${key}`).checked;
    else if (a === 'seg') v[key] = document.querySelector(`input[name=look-${key}]:checked`)?.value;
    else if (a === 'select') v[key] = $(`look-${key}`).value;
    else v[key] = +$(`look-${key}`).value;
  });
  return v;
}

function setLook(v) {
  LOOK_UI.forEach(([key, label, a]) => {
    if (!label || !(key in v)) return;
    if (a === 'check') $(`look-${key}`).checked = v[key];
    else if (a === 'seg') {
      const r = document.querySelector(`input[name=look-${key}][value="${v[key]}"]`);
      if (r) r.checked = true;
    } else { $(`look-${key}`).value = v[key]; $(`look-${key}`).oninput?.(); }
  });
  lookSync();
}

// Marks settings that differ from the default with a dot; dims the sun sliders when there is no sun.
function lookSync() {
  const v = lookValues(), d = lookDefaults();
  Object.keys(v).forEach(k => $(`ctl-${k}`).classList.toggle('changed', k in d && v[k] !== d[k]));
  ['sun', 'softness'].forEach(k => $(`ctl-${k}`).classList.toggle('off', !v.shadows || v.time === 'evening'));
  moodSync();
}

// Materials tab: word lists per kind, comma separated in the text boxes.
const WORD_KINDS = ['water', 'glass', 'glow'];
const wordValues = () => Object.fromEntries(WORD_KINDS.map(k =>
  [k, $(`words-${k}`).value.split(/[,;\n]/).map(w => w.trim().toLowerCase()).filter(Boolean)]));
const setWords = v => WORD_KINDS.forEach(k => { if (v[k]) $(`words-${k}`).value = v[k].join(', '); });

function settings() {
  const preset = $('preset').value;
  return {
    mode: radio('mode'), ...size(),
    samples: preset === 'custom' ? +$('samples').value : +preset,
    scenes: (S.pages || []).filter(n => checked[n]), folder: S.folder, look: lookValues(), words: wordValues(), presets: mine,
  };
}

function sync() {
  const s = settings(), a = S.aspect || 16 / 9, scenes = s.mode === 'scenes';
  $('custom-size').hidden = $('width').value !== 'custom';
  const k = `${s.width}x${s.height}`; // the viewport preview takes the render's shape
  if (inited && k !== sentSize) { sentSize = k; sketchup.frame(JSON.stringify(size())); }
  $('size').textContent = !s.height ? `${s.width} × ${Math.round(s.width / a)} px (viewport shape)`
    : 'The Viewport tab shows this frame.';
  $('custom').hidden = $('preset').value !== 'custom';
  const pane = radio('pane');
  $('pane-output').hidden = pane !== 'output';
  $('pane-look').hidden = pane !== 'look';
  $('pane-materials').hidden = pane !== 'materials';
  $('scenes').hidden = !scenes;
  $('output').hidden = !scenes;
  $('start').textContent = !scenes ? 'Start render'
    : s.scenes.length ? `Render ${s.scenes.length} scene${s.scenes.length > 1 ? 's' : ''}` : 'Pick scenes to render';
  $('start').disabled = scenes && !s.scenes.length;
  const n = s.scenes.length, total = (S.pages || []).length;
  $('all').checked = n === total && total > 0;
  $('all').indeterminate = n > 0 && n < total;
  $('count').textContent = `${n} / ${total}`;
}

let lastSceneKey = '';

// Scene checklist; during and after a batch each row shows its queue status.
function renderScenes(force) {
  const pages = S.pages || [], list = $('scene-list');
  const key = JSON.stringify([pages, S.current_page, S.busy, S.batch]);
  if (!force && key === lastSceneKey) return;
  lastSceneKey = key;
  const items = {};
  (S.batch?.items || []).forEach(it => items[it.name] = it);
  pages.forEach(n => { if (!(n in checked)) checked[n] = true; });
  $('no-scenes').hidden = pages.length > 0;
  list.hidden = !pages.length;
  list.replaceChildren(...pages.map(n => {
    const li = document.createElement('li'), it = items[n];
    li.classList.toggle('current', n === S.current_page);
    li.classList.toggle('active', it?.status === 'active' && S.batch?.running);
    const label = document.createElement('label'), box = document.createElement('input'), name = document.createElement('span');
    box.type = 'checkbox';
    box.checked = !!checked[n];
    box.disabled = !!S.busy;
    box.onchange = () => { checked[n] = box.checked; sync(); };
    name.className = 'name';
    name.textContent = n;
    label.append(box, name);
    const badge = document.createElement('span');
    badge.className = 'badge';
    if (it) {
      const st = it.status;
      badge.classList.add(st);
      badge.textContent = st === 'done' ? '✓ view' : st === 'active' ? (it.pct != null ? `${Math.round(it.pct)} %` : '…')
        : st === 'waiting' ? 'waiting' : st === 'failed' ? '✕ failed' : st;
      if (st === 'failed' && it.error) badge.title = it.error;
      if (st === 'done') badge.onclick = () => { pinned = it.file; tab = 'render'; show(); };
    }
    li.append(label, badge);
    return li;
  }));
}

// Stats tab: totals from Ruby (S.usage), counted on this PC after every finished render.
const big = n => n >= 1e6
  ? new Intl.NumberFormat('en', { notation: 'compact', compactDisplay: 'long', maximumFractionDigits: 1 }).format(n)
  : Math.round(n).toLocaleString('en');
const hours = sec => sec >= 3600 ? `${(sec / 3600).toFixed(1)} h` : fmt(sec);
const A4_300DPI = 2480 * 3508;

function renderStats() {
  const u = S.usage || {}, n = u.done || 0;
  if (!n) {
    $('stats').innerHTML = '<p class="hint">No finished renders yet. Your numbers appear here after the first one.</p>';
    return;
  }
  const card = (value, label, note) => `<div class="card"><b>${value}</b><span>${label}</span><small>${note}</small></div>`;
  const since = new Date(`${u.since}T12:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const days = u.days || 1, failed = u.failed || 0, prints = Math.floor((u.pixels || 0) / A4_300DPI);
  $('stats').innerHTML = `
    <div class="cards">
      ${card(big(n), n === 1 ? 'render finished' : 'renders finished', `since ${since} · on ${days} day${days > 1 ? 's' : ''}`)}
      ${card(hours(u.seconds || 0), 'spent rendering', `average ${fmt((u.seconds || 0) / n)} · longest ${fmt(u.longest || 0)}`)}
      ${card(`${big((u.pixels || 0) / 1e6)} MP`, 'megapixels rendered',
             prints ? `as much as ${prints} A4 print${prints > 1 ? 's' : ''} at 300 dpi` : 'not yet one A4 print at 300 dpi')}
      ${card(big(u.paths || 0), 'light paths traced', 'pixels × samples')}
      ${card(big(u.triangles || 0), 'triangles rendered', `biggest model ${big(u.biggest || 0)}`)}
      ${card(big(u.faceme || 0), 'trees and people', 'face-me components turned to the camera')}
      ${card(big(u.scenes || 0), 'scenes from batches', 'rendered while you did something else')}
      ${card(`${Math.round(100 * n / (n + failed))} %`, 'finished without error', `${failed} failed · ${u.cancelled || 0} cancelled`)}
    </div>
    <p class="hint">Counted on this PC only; nothing is sent anywhere.
      <span class="links">Logs of the last renders: <a class="open-logs">Open logs folder</a></span></p>`;
}

function show() {
  const render = pinned || S.render;
  const src = tab === 'render' ? render : S.view;
  $('tab-view').classList.toggle('on', tab === 'view');
  $('tab-render').classList.toggle('on', tab === 'render');
  $('tab-stats').classList.toggle('on', tab === 'stats');
  $('view').hidden = tab === 'stats';
  $('stats').hidden = tab !== 'stats';
  if (tab === 'stats') renderStats();
  $('tab-render').disabled = !render && !S.busy;
  $('refresh').hidden = !S.view_stale || tab !== 'view' || !!S.busy;
  if (!S.view_stale) $('refresh').textContent = 'Refresh preview';
  if (src && $('img').dataset.src !== src) {
    log(`img: loading ${tab} ${src}`);
    $('img').dataset.src = src;
    $('img').src = src;
  }
  $('img').hidden = !src;
  $('empty').hidden = !!src;
  $('empty').textContent = tab === 'view' ? 'Loading viewport…'
    : S.busy ? 'Rendering… the first preview appears here when Blender has built the scene.' : 'No render yet.';
}

// Called from Ruby with the whole state:
// {status, pct, eta, view, render, error, busy, settings, aspect, pages, current_page, folder, batch}
function update(s) {
  const prev = S;
  S = s;
  if (!inited) log(`update: first state view=${s.view} busy=${s.busy} pages=${(s.pages || []).length}`);
  if (!inited && s.settings) {
    inited = true;
    const st = s.settings;
    document.querySelector(`input[name=mode][value="${st.mode || 'view'}"]`).checked = true;
    const key = st.height ? `${st.width}x${st.height}` : String(st.width);
    $('width').value = [...$('width').options].some(o => o.value === key) ? key : 'custom';
    $('cw').value = st.width;
    $('ch').value = st.height || Math.round(st.width / (s.aspect || 16 / 9));
    sentSize = `${st.width}x${st.height || 0}`; // Ruby already snapshots with the saved size
    const preset = [...$('preset').options].find(o => +o.value === st.samples);
    $('preset').value = preset ? preset.value : 'custom';
    $('samples').value = st.samples;
    setLook(st.look || s.look_defaults || {});
    setWords(st.words || s.words_defaults || {});
    mine = st.presets || [];
    buildMoods();
    moodSync();
  }
  if (!s.batch) pinned = null; // pinned images come from batch results (gone after opening another model)
  if (!s.render && !pinned && !s.busy && tab === 'render') tab = 'view';
  if (s.render && s.render !== prev.render) { tab = 'render'; pinned = null; }
  else if (s.view && s.view !== prev.view && !s.busy && tab !== 'stats') tab = 'view';

  $('version').textContent = s.version ? `v${s.version}` : '';
  $('text').textContent = s.status || '';
  $('text').title = s.status || '';
  $('eta').textContent = s.eta != null ? `~${fmt(s.eta)} left` : '';
  const known = s.pct != null;
  $('bar').classList.toggle('busy', !!s.busy);
  $('bar').classList.toggle('known', known);
  $('fill').style.width = known ? `${s.pct}%` : (s.busy ? '' : '0');
  $('err').hidden = !s.error; // {what, todo, details}
  $('err-what').textContent = s.error?.what || '';
  $('err-todo').textContent = s.error?.todo || '';
  $('err-details').textContent = s.error?.details || '';
  $('folder').textContent = s.folder || '';
  $('folder').title = s.folder || '';
  $('start').hidden = !!s.busy;
  $('cancel').hidden = !s.busy;
  $('cancel').textContent = s.batch?.running ? 'Cancel batch' : 'Cancel';
  $('save').disabled = !(pinned || s.render);
  if (!!s.busy !== !!prev.busy || !prev.settings) {
    document.querySelectorAll('aside select, aside input, aside textarea, #pick').forEach(e => e.disabled = !!s.busy);
  }
  renderScenes();
  sync();
  show();
}

$('img').onload = () => log(`img: loaded ${$('img').naturalWidth}x${$('img').naturalHeight} ${$('img').src}`);
$('img').onerror = () => log(`img: FAILED ${$('img').src}`);
$('tab-view').onclick = () => { tab = 'view'; show(); };
$('tab-render').onclick = () => { tab = 'render'; show(); };
$('tab-stats').onclick = () => { tab = 'stats'; show(); };
buildMoods();
buildLook();
const saveSettings = () => { if (inited && !S.busy) sketchup.save_settings?.(JSON.stringify(settings())); };
document.querySelectorAll('aside select, aside input, aside textarea').forEach(e => e.onchange = () => { sync(); lookSync(); saveSettings(); });
$('look-reset').onclick = () => { if (!S.busy) { setLook(lookDefaults()); saveSettings(); } };
$('mood').onchange = () => {
  const p = presetLook($('mood').value);
  if (p && !S.busy) { setLook(p); saveSettings(); } else moodSync();
};
const nameRow = show => { $('mood-new').hidden = !show; if (show) { $('mood-name').value = ''; $('mood-name').focus(); } };
$('mood-save').onclick = () => { if (!S.busy) nameRow($('mood-new').hidden); };
$('mood-ok').onclick = () => {
  const name = $('mood-name').value.trim().slice(0, 40);
  if (!name) return;
  const look = Object.fromEntries(MOOD.map(k => [k, lookValues()[k]]));
  const i = mine.findIndex(p => p.name === name); // same name: replace
  if (i >= 0) mine[i] = { name, look }; else mine.push({ name, look });
  nameRow(false);
  buildMoods();
  moodSync();
  saveSettings();
};
$('mood-name').onkeydown = e => { if (e.key === 'Enter') $('mood-ok').onclick(); if (e.key === 'Escape') nameRow(false); };
$('mood-delete').onclick = () => {
  const v = $('mood').value;
  if (S.busy || !v.startsWith('my:')) return;
  mine.splice(+v.slice(3), 1);
  buildMoods();
  moodSync();
  saveSettings();
};
$('words-reset').onclick = () => { if (!S.busy) { setWords(S.words_defaults || {}); saveSettings(); } };
$('all').onchange = () => { (S.pages || []).forEach(n => checked[n] = $('all').checked); renderScenes(true); sync(); };
$('pick').onclick = () => sketchup.pick_folder();
$('refresh').onclick = () => { $('refresh').textContent = 'Updating…'; setTimeout(() => sketchup.refresh(), 30); };
$('open').onclick = () => sketchup.open_folder();
$('start').onclick = () => sketchup.start(JSON.stringify(settings()));
$('cancel').onclick = () => sketchup.cancel();
$('save').onclick = () => sketchup.save(pinned || '');
// Both "Open logs folder" links; the Stats one is rebuilt with the tab, so listen on the document.
document.addEventListener('click', e => { if (e.target.classList.contains('open-logs')) sketchup.open_logs(); });
$('err-more').onclick = () => {
  $('err-details').hidden = !$('err-details').hidden;
  $('err-more').textContent = $('err-details').hidden ? 'Show details' : 'Hide details';
};
// execCommand: the async clipboard API may be refused in SketchUp's dialog; a hidden textarea always works.
$('err-copy').onclick = () => {
  const t = Object.assign(document.createElement('textarea'), { value: S.error?.details || '' });
  t.style.cssText = 'position:fixed;opacity:0';
  document.body.append(t);
  t.select();
  const ok = document.execCommand('copy');
  t.remove();
  $('err-copy').textContent = ok ? 'Copied' : 'Could not copy: open the details and press Ctrl+C';
  setTimeout(() => { $('err-copy').textContent = 'Copy details'; }, 2500);
};
log(`page: ${location.href} ua=${navigator.userAgent}`);
sketchup.ready();
