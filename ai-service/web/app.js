/* 蓝珊 · 珊瑚卫士 网页版前端
 * 说明：本页由 AI 服务自己托管（GET / -> web/index.html），调用同一套接口，
 *      因此结果与微信小程序完全一致（同一后端、同一模型）。
 * 接口：GET /health、GET /sample、POST /analyze(multipart: file, lat, lon, year)
 */
const SITES = [
  { lat: 4.4, lon: 118.8, name: '仙本那 · 核心礁区' },
  { lat: 4.2, lon: 118.1, name: '西侧近岸（历史高危）' },
  { lat: 4.9, lon: 119.0, name: '东侧外海（热压力友好）' },
  { lat: 4.8, lon: 118.5, name: '北侧礁区' },
];
const QUICK_YEARS = [2025, 2024, 2023, 2022, 2021];
const GRID = { latMin: 4.025, latMax: 5.025, lonMin: 118.025, lonMax: 119.525 };
const ALL_YEARS = Array.from({ length: 2025 - 1985 + 1 }, (_, i) => 2025 - i);

const API = location.origin;      // 与服务同源（部署到别的域名时也一致）

/* 访问令牌：服务端设了 CORAL_API_TOKEN 时，用 ?token=xxx 打开本页，或先
   localStorage.setItem('coral_token','xxx')。留空则不带（默认部署行为）。 */
const CORAL_TOKEN = (function () {
  try {
    const q = new URLSearchParams(location.search).get('token');
    if (q) { localStorage.setItem('coral_token', q); return q; }
    return localStorage.getItem('coral_token') || '';
  } catch (e) { return ''; }
})();
const AUTH_HEADERS = CORAL_TOKEN ? { 'X-API-Token': CORAL_TOKEN } : {};
const $ = (id) => document.getElementById(id);

const state = {
  file: null,
  lat: SITES[0].lat,
  lon: SITES[0].lon,
  siteIndex: 0,
  year: 2025,
  yearIsQuick: true,
  busy: false,
  years: ALL_YEARS.slice(),
  sampleIndex: 0,
};

/* ---------------- 服务状态 ---------------- */
async function checkHealth() {
  const el = $('svcStatus');
  try {
    const r = await fetch(API + '/health');
    const h = await r.json();
    const ok = h.status === 'ok' && h.segmentation === 'loaded';
    el.textContent = ok ? `服务正常 · ${h.device}` : '服务异常';
    el.className = 'status ' + (ok ? 'ok' : 'bad');
    $('footVer').textContent =
      `模型：分割 ${h.segModel || '-'}｜白化 ${h.segCalibrated ? '已校准' : '未校准'}` +
      `｜计数 ${h.coralCounter || '-'}｜共识第二模型 ${h.bleachAlt || '-'}`;
    if (!ok) showState('AI 服务未就绪：请先在电脑上运行 serve_fusion.py', true);
  } catch (e) {
    el.textContent = '连不上服务';
    el.className = 'status bad';
    showState('连不上 AI 服务。请确认已运行 serve_fusion.py --host 0.0.0.0 --port 8000', true);
  }
}

/* ---------------- 点位 / 年份 ---------------- */
function renderSites() {
  const box = $('siteChips');
  box.innerHTML = '';
  SITES.forEach((s, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip' + (i === state.siteIndex ? ' active' : '');
    b.textContent = s.name;
    b.onclick = () => {
      state.siteIndex = i; state.lat = s.lat; state.lon = s.lon;
      $('siteMsg').textContent = `已选：${s.name}（${s.lat}°N, ${s.lon}°E）`;
      renderSites();
    };
    box.appendChild(b);
  });
}

function renderYears() {
  const box = $('yearChips');
  box.innerHTML = '';
  QUICK_YEARS.forEach((y) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip' + (state.yearIsQuick && state.year === y ? ' active' : '');
    b.textContent = String(y);
    b.onclick = () => setYear(y, true);
    box.appendChild(b);
  });
  const pick = document.createElement('button');
  pick.type = 'button';
  const nonQuick = !state.yearIsQuick;
  pick.className = 'chip pick' + (nonQuick ? ' active' : '');
  pick.textContent = nonQuick ? String(state.year) : '其他年份 ▾';
  pick.onclick = () => { $('yearSelect').focus(); $('yearSelect').click(); };
  box.appendChild(pick);

  const sel = $('yearSelect');
  sel.innerHTML = '';
  state.years.forEach((y) => {
    const o = document.createElement('option');
    o.value = String(y); o.textContent = String(y) + ' 年';
    sel.appendChild(o);
  });
  sel.value = String(state.year);
  $('yearMsg').textContent = `可选 ${state.years.length} 年（1985–2025）`;
}

function setYear(y, quick) {
  state.year = y;
  state.yearIsQuick = quick || QUICK_YEARS.includes(y);
  $('yearSelect').value = String(y);
  renderYears();
}

/* ---------------- 图片 ---------------- */
function bindUpload() {
  const zone = $('dropZone'), input = $('fileInput');
  zone.onclick = () => input.click();
  input.onchange = () => input.files[0] && useFile(input.files[0]);
  ['dragenter', 'dragover'].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault(); zone.classList.add('over');
  }));
  ['dragleave', 'drop'].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault(); zone.classList.remove('over');
  }));
  zone.addEventListener('drop', (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) useFile(f);
  });
  $('clearImg').onclick = (e) => {
    e.stopPropagation();
    state.file = null; input.value = '';
    $('previewWrap').classList.add('hidden');
    $('pickWrap').classList.remove('hidden');
  };
  $('sampleBtn').onclick = loadSample;
}

function useFile(file) {
  if (!file.type.startsWith('image/')) return showState('请选择图片文件', true);
  state.file = file;
  const url = URL.createObjectURL(file);
  $('preview').src = url;
  $('previewWrap').classList.remove('hidden');
  $('pickWrap').classList.add('hidden');
  hideState();
}

async function loadSample() {
  $('sampleHint').textContent = '正在取示例图片…';
  try {
    const r = await fetch(`${API}/sample?index=${state.sampleIndex}&set=semporna`);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const blob = await r.blob();
    const f = new File([blob], `sample_${state.sampleIndex}.jpg`, { type: blob.type || 'image/jpeg' });
    useFile(f);
    state.sampleIndex += 1;
    $('sampleHint').textContent = `已载入示例图 #${state.sampleIndex}（可反复点）`;
  } catch (e) {
    $('sampleHint').textContent = '示例图片获取失败：' + e.message;
  }
}

/* ---------------- 地理定位 ---------------- */
function bindGeo() {
  $('geoBtn').onclick = () => {
    if (!navigator.geolocation) return ($('siteMsg').textContent = '此浏览器不支持定位');
    $('siteMsg').textContent = '正在定位…';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const la = pos.coords.latitude, lo = pos.coords.longitude;
        if (la < GRID.latMin || la > GRID.latMax || lo < GRID.lonMin || lo > GRID.lonMax) {
          $('siteMsg').textContent =
            `定位在评估网格外（${la.toFixed(3)}, ${lo.toFixed(3)}）：本项目只覆盖仙本那及周边，` +
            `网格外不给结论，请改选上面的预设点位。`;
          return;
        }
        state.lat = la; state.lon = lo; state.siteIndex = -1;
        $('siteMsg').textContent = `已采用定位：${la.toFixed(3)}°N, ${lo.toFixed(3)}°E`;
        renderSites();
      },
      (err) => { $('siteMsg').textContent = '定位失败：' + (err.message || '未授权'); },
      { timeout: 10000, maximumAge: 60000 }
    );
  };
}

/* ---------------- 评估 ---------------- */
function showState(msg, isErr) {
  const el = $('stateMsg');
  el.textContent = msg;
  el.className = 'state-msg' + (isErr ? ' err' : '');
  el.classList.remove('hidden');
}
function hideState() { $('stateMsg').classList.add('hidden'); }

async function analyze() {
  if (state.busy) return;
  if (!state.file) return showState('请先选择一张珊瑚照片', true);
  state.busy = true;
  $('goBtn').disabled = true;
  $('goBtn').textContent = '评估中…（首次约 1–3 秒）';
  showState('正在上传并推理…');
  const fd = new FormData();
  fd.append('file', state.file, state.file.name || 'photo.jpg');
  fd.append('lat', String(state.lat));
  fd.append('lon', String(state.lon));
  fd.append('year', String(state.year));
  try {
    const r = await fetch(API + '/analyze',
        { method: 'POST', body: fd, headers: Object.assign({}, AUTH_HEADERS) });
    if (!r.ok) throw new Error('服务返回 HTTP ' + r.status);
    const res = await r.json();
    if (res.success === false) throw new Error(res.error || '评估失败');
    render(res);
    hideState();
    $('results').classList.remove('hidden');
    $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    showState('评估失败：' + e.message, true);
  } finally {
    state.busy = false;
    $('goBtn').disabled = false;
    $('goBtn').textContent = '开始评估';
  }
}

/* ---------------- 渲染 ---------------- */
const pct = (v) => (Math.round((Number(v) || 0) * 1000) / 10);

function render(res) {
  // 质量闸门
  const q = res.captureQuality || {};
  const qb = $('qBadge');
  qb.className = 'badge ' + (q.level === 'good' ? 'good' : q.level === 'warn' ? 'warn' : 'bad');
  qb.textContent = { good: '良好', warn: '一般（建议复核）', poor: '不合格' }[q.level] || '未知';
  $('qMsg').textContent = (q.message || '') + (q.usable === false ? '（该图不建议采信）' : '');

  // 覆盖率
  const c = res.cover || {};
  const rows = [
    ['活珊瑚', c.alivePct, 'alive'], ['白化珊瑚', c.bleachedPct, 'bleached'],
    ['死亡珊瑚', c.deadPct, 'dead'], ['藻类覆盖', c.algaePct, 'algae'],
    ['沙/碎石/底质', c.substratePct, 'substrate'], ['海草', c.seagrassPct, 'seagrass'],
  ];
  $('coverBars').innerHTML = rows.map(([n, v, k]) => `
    <div class="bar-row">
      <span class="bar-name">${n}</span>
      <div class="bar-track"><div class="bar-fill ${k}" style="width:${Math.min(100, pct(v))}%"></div></div>
      <span class="bar-val">${pct(v)}%</span>
    </div>`).join('');
  $('kpiCoral').textContent = pct(c.coralTotalPct) + '%';
  $('kpiBleachShare').textContent = pct(c.bleachingShareOfCoral) + '%';

  // 白化状态 + 共识三档
  const b = res.bleaching || {};
  $('bleachLabel').textContent = b.labelCn || '—';
  const conf = pct(b.confidence);
  $('bleachConf').style.width = Math.min(100, conf) + '%';
  $('bleachConfText').textContent = `主模型置信度 ${conf}%　模型：${b.model || '-'}`;
  const box = $('consensusBox');
  const cs = b.consensus;
  if (cs && cs.severity) {
    const cls = cs.severity === 'review' ? 'review' : cs.severity === 'note' ? 'note' : 'agree';
    const icon = cs.severity === 'review' ? '🔍' : cs.severity === 'note' ? 'ℹ️' : '✓';
    box.innerHTML = `<div class="tip ${cls}">${icon} ${cs.reason || ''}
      <div class="muted">第二模型（${b.altModel || '-'}）判定：${b.altLabelCn || '-'} ${pct(b.altConfidence)}%</div></div>`;
    box.classList.remove('hidden');
  } else {
    box.classList.add('hidden');
  }
  const probs = b.probabilities || {};
  $('bleachProbs').innerHTML = Object.keys(probs)
    .sort((x, y) => probs[y] - probs[x])
    .map((k) => {
      const nm = { bleached: '白化', healthy: '健康', dead: '死亡' }[k.toLowerCase()] || k;
      return `<div class="prob-row"><span>${nm}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.min(100, pct(probs[k]))}%"></div></div>
        <span class="bar-val">${pct(probs[k])}%</span></div>`;
    }).join('');

  // 珊瑚属
  const cr = res.coralRegion || {};
  const top = cr.top || [];
  $('genusTop').textContent = top.length ? top[0].genus : '未识别到珊瑚属';
  $('genusList').innerHTML = top.map((g) =>
    `<div class="list-item"><span>${g.genus}</span><span>${pct(g.confidence)}%</span></div>`).join('');

  // 个体计数
  const cc = res.coralCount || {};
  $('kpiCount').textContent = cc.count != null ? cc.count : '—';
  $('kpiCountMs').textContent = cc.elapsedMs != null ? Math.round(cc.elapsedMs) + ' ms' : '—';

  // 环境数据
  const cl = res.climate || {};
  if (cl.ok) {
    $('kpiBaa').textContent = cl.baaLabel || '—';
    $('kpiDhw').textContent = cl.dhwMax != null ? cl.dhwMax : '—';
    $('climateNote').textContent =
      `评估年份 ${cl.year}，最近 NOAA 5km 格点 ${cl.gridCell ? cl.gridCell.lat + '°N ' + cl.gridCell.lon + '°E' : ''}；` +
      `${cl.verdict || ''}${cl.anomalyNote ? '；' + cl.anomalyNote : ''}（来源：${cl.source || 'NOAA'}）`;
  } else {
    $('kpiBaa').textContent = '无数据';
    $('kpiDhw').textContent = '—';
    $('climateNote').textContent = cl.error || '该坐标不在评估网格内（仅覆盖仙本那及周边），不给结论。';
  }
  if (cl.availableYears && cl.availableYears.length) {
    state.years = cl.availableYears.slice().sort((a, b) => Number(b) - Number(a));
    renderYears();
  }

  // 综合研判
  const r = res.restoration || {};
  const dep = res.deployment || {};
  const sc = [
    ['修复优先级', r.priority], ['恢复潜力', r.recovery && r.recovery.score],
    ['紧迫度', r.urgency && r.urgency.score], ['苗投放适宜度', r.seedlingSuitability],
  ];
  $('restScores').innerHTML = sc.map(([k, v]) =>
    `<div class="score"><div class="score-v">${v != null ? v : '—'}</div><div class="score-k">${k}</div></div>`).join('');
  const adv = (r.deploymentAdvice && r.deploymentAdvice.verdict) || (dep.advice && dep.advice.verdict) ||
    (r.actions && r.actions[0]) || '—';
  $('restAdvice').textContent = `【投放建议】${adv}\n评级：${r.gradeLabel || '—'}` +
    (dep.label ? `\n【历史热压力】${dep.label}；建议避开 ${(dep.avoidMonths || []).join('、')} 月` : '');
  $('reportCn').textContent = r.report || '（无）';
  $('reportEn').textContent = r.reportEn || '（none）';

  $('disclaimer').textContent = res.disclaimer || '';
  $('meta').textContent = `推理耗时 ${res.inferenceMs != null ? Math.round(res.inferenceMs) + ' ms' : '—'}` +
    `；增强预处理：${res.enhanced ? '开启' : '关闭'}；口径：区域尺度（5km 格点 ≠ 礁点）`;
}

/* ---------------- 启动 ---------------- */
window.addEventListener('DOMContentLoaded', () => {
  renderSites(); renderYears(); bindUpload(); bindGeo();
  $('yearSelect').onchange = (e) => setYear(Number(e.target.value), false);
  $('goBtn').onclick = analyze;
  $('siteMsg').textContent = `默认：${SITES[0].name}（${SITES[0].lat}°N, ${SITES[0].lon}°E）`;
  checkHealth();
});
