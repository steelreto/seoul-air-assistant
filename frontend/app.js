/* 서울 대기질 AI 비서 — 프론트엔드 (바닐라 JS)
 *
 * API 주소는 config.js 의 window.APP_CONFIG.API_BASE_URL 에서 읽는다.
 *  - 비어 있으면 '데모 모드': demo-data.js 의 예시 데이터로 브라우저 안에서만 동작
 *  - Vercel에서는 build.sh 가 환경변수 API_BASE_URL 로 config.js 를 만들어 준다
 */
(() => {
  "use strict";

  const CFG = window.APP_CONFIG || {};
  const API = (CFG.API_BASE_URL || "").trim().replace(/\/+$/, "");
  const DEMO = !API;
  const PAGE_SIZE = 20;
  const UNIT = "㎍/㎥";

  const state = {
    records: [], summary: null, conversations: [],
    convId: null, messages: [], sending: false,
    editingId: null, month: "all", search: "", pageNo: 1,
    range: "all", chart: null, pendingDelete: null,
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (v, d = 1) => (v === null || v === undefined || v === "" || Number.isNaN(v)) ? "-" : Number(v).toFixed(d).replace(/\.0$/, d ? ".0" : "");
  const num = (v) => (v === null || v === undefined || v === "" ? "-" : String(Math.round(Number(v) * 10) / 10));

  // ------------------------------------------------------------ 등급
  const GRADES = [
    { key: "good", label: "좋음", max: 15, range: "0~15" },
    { key: "normal", label: "보통", max: 35, range: "16~35" },
    { key: "bad", label: "나쁨", max: 75, range: "36~75" },
    { key: "worst", label: "매우나쁨", max: Infinity, range: "76 이상" },
  ];
  const gradeOf = (v) => GRADES.find((g) => v <= g.max) || GRADES[3];
  const badge = (v) => {
    if (v === null || v === undefined) return "-";
    const g = gradeOf(v);
    return `<span class="grade g-${g.key}">${g.label}</span>`;
  };

  // ------------------------------------------------------------ 저장소 (localStorage는 편의 기능만)
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* 무시 */ } },
  };

  // ------------------------------------------------------------ 토스트 / 배너
  let toastTimer;
  function toast(msg, isError = false) {
    const el = $("#toast");
    el.textContent = msg;
    el.className = "toast" + (isError ? " error" : "");
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
  }

  function banner(kind, html) {
    const el = $("#banner");
    if (!kind) { el.hidden = true; el.innerHTML = ""; return; }
    el.className = "banner " + kind;
    el.innerHTML = `<div class="wrap">${html}</div>`;
    el.hidden = false;
  }

  function setStatus(stateName, text) {
    $("#statusChip").dataset.state = stateName;
    $("#statusText").textContent = text;
  }

  // ------------------------------------------------------------ HTTP API
  async function http(path, { method = "GET", body, timeout = 20000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(API + path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        let msg = `요청 실패 (${res.status})`;
        if (data && typeof data.detail === "string") msg = data.detail;
        else if (data && Array.isArray(data.detail)) msg = data.detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join(", ");
        throw new Error(msg);
      }
      return data;
    } catch (err) {
      if (err.name === "AbortError") throw new Error("서버 응답이 너무 늦어요. 잠시 후 다시 시도해 주세요.");
      if (err instanceof TypeError) throw new Error("서버에 연결할 수 없어요. 주소나 CORS 설정을 확인하세요.");
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  const httpApi = {
    health: () => http("/health", { timeout: 15000 }),
    listData: () => http("/api/data"),
    summary: () => http("/api/data/summary"),
    createData: (p) => http("/api/data", { method: "POST", body: p }),
    updateData: (id, p) => http(`/api/data/${encodeURIComponent(id)}`, { method: "PUT", body: p }),
    deleteData: (id) => http(`/api/data/${encodeURIComponent(id)}`, { method: "DELETE" }),
    listConvs: () => http("/api/conversations"),
    getConv: (id) => http(`/api/conversations/${encodeURIComponent(id)}`),
    deleteConv: (id) => http(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
    chat: (p) => http("/api/chat", { method: "POST", body: p, timeout: 60000 }),
  };

  // ------------------------------------------------------------ 데모 API (서버 없이 화면 확인용)
  const demoApi = (() => {
    const D = window.DEMO_DATA || { records: [], summary: null };
    let records = D.records.map((r) => ({ ...r, id: r.date }));
    const convs = [];
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const now = () => new Date().toISOString().slice(0, 19) + "+00:00";
    const sorted = () => records.slice().sort((a, b) => a.date.localeCompare(b.date));

    function reply(q) {
      const s = D.summary;
      if (!s) return "데이터가 없어요.";
      const m = s.metrics, w = s.weather_relation;
      const rel = (arr) => arr.map((x) => `${x.label} ${x.pm25_avg}${UNIT}`).join(", ");
      const months = s.monthly.slice().sort((a, b) => b.pm25_avg - a.pm25_avg);
      let body;
      if (/나빴|최악|높았|최고|심했/.test(q)) {
        const d = s.worst_days[0];
        body = `초미세먼지가 가장 높았던 날은 ${d.date}로 ${d.value}${UNIT}(매우나쁨)였어요. 그날 풍속이 ${d.wind}m/s로 약했고 비도 오지 않아 먼지가 쌓이기 쉬운 조건이었어요.`;
      } else if (/좋았|깨끗|낮았|최저/.test(q)) {
        body = `가장 깨끗했던 날은 ${m.min_date}로 ${m.min}${UNIT}였어요. 9~10월은 월평균도 9${UNIT} 안팎으로 1년 중 가장 낮았어요.`;
      } else if (/비 |비가|비오|비 온|강수|우산/.test(q)) {
        body = `비가 1mm 이상 온 날은 평균 ${w.by_rain[1].pm25_avg}${UNIT}, 오지 않은 날은 ${w.by_rain[0].pm25_avg}${UNIT}였어요. 비가 오면 초미세먼지가 낮아지는 경향이 있어요.`;
      } else if (/바람|풍속/.test(q)) {
        body = `풍속별 평균은 ${rel(w.by_wind)}였어요. 바람이 약할수록 농도가 높아지는 경향이 있어요.`;
      } else if (/추운|추울|춥|겨울|기온|더운|더울|여름|날씨/.test(q)) {
        body = `기온대별 평균은 ${rel(w.by_temp)}였어요. 0~10℃ 구간(늦가을·초봄)이 가장 높았고, 한겨울 영하일은 오히려 낮았어요.`;
      } else if (/월|달|계절/.test(q)) {
        body = `월평균이 가장 높았던 달은 ${months[0].month}(${months[0].pm25_avg}${UNIT}), 가장 낮았던 달은 ${months.at(-1).month}(${months.at(-1).pm25_avg}${UNIT})였어요.`;
      } else if (/추세|요즘|최근|이번|오늘|지금/.test(q)) {
        body = `가장 최근 기록은 ${s.latest.date}, ${s.latest.value}${UNIT}(${gradeOf(s.latest.value).label})이에요. 최근 추세는 ${s.trend.text}.`;
      } else {
        body = `${s.period} 기간 ${s.count}일의 초미세먼지 평균은 ${m.average}${UNIT}였고, 좋음 ${s.grade_days["좋음"]}일·보통 ${s.grade_days["보통"]}일·나쁨 ${s.grade_days["나쁨"]}일·매우나쁨 ${s.grade_days["매우나쁨"]}일이었어요.`;
      }
      return `[데모 응답] 서버 연결 전이라 규칙으로 만든 예시 답변이에요.\n\n${body}`;
    }

    const summaryOf = (c) => ({
      id: c.id, title: c.title, message_count: c.messages.length,
      last_message: (c.messages.at(-1) || {}).content?.slice(0, 80) || "",
      created_at: c.created_at, updated_at: c.updated_at,
    });

    return {
      health: async () => ({ status: "ok", db: "demo" }),
      listData: async () => { await wait(120); return sorted(); },
      summary: async () => D.summary,
      async createData(p) {
        await wait(150);
        if (records.some((r) => r.date === p.date)) throw new Error(`${p.date} 데이터가 이미 있어요. 수정을 사용하세요.`);
        const r = { ...p, id: p.date, created_at: now(), updated_at: now() };
        records.push(r); return r;
      },
      async updateData(id, p) {
        await wait(150);
        const r = records.find((x) => x.id === id);
        if (!r) throw new Error("데이터를 찾을 수 없어요.");
        Object.assign(r, p, { updated_at: now() }); return r;
      },
      async deleteData(id) { await wait(120); records = records.filter((x) => x.id !== id); return { id, deleted: true }; },
      listConvs: async () => convs.map(summaryOf).sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
      async getConv(id) { const c = convs.find((x) => x.id === id); if (!c) throw new Error("대화를 찾을 수 없어요."); return { ...summaryOf(c), messages: c.messages }; },
      async deleteConv(id) { const i = convs.findIndex((x) => x.id === id); if (i >= 0) convs.splice(i, 1); return { id, deleted: true }; },
      async chat({ message, conversation_id }) {
        await wait(900);
        const answer = reply(message);
        const msgs = [{ role: "user", content: message, created_at: now() }, { role: "assistant", content: answer, created_at: now() }];
        let c = convs.find((x) => x.id === conversation_id);
        if (!c) {
          c = { id: Math.random().toString(36).slice(2, 12), title: message.slice(0, 30), messages: [], created_at: now() };
          convs.push(c);
        }
        c.messages.push(...msgs); c.updated_at = now();
        return { conversation_id: c.id, title: c.title, reply: answer, model: "demo" };
      },
    };
  })();

  const api = DEMO ? demoApi : httpApi;

  // ------------------------------------------------------------ 라우팅
  const PAGES = ["summary", "chat", "data", "history"];
  function route() {
    const page = PAGES.includes(location.hash.slice(1)) ? location.hash.slice(1) : "summary";
    $$("[data-page]").forEach((s) => { s.hidden = s.dataset.page !== page; });
    $$("[data-nav]").forEach((a) => { if (a.dataset.nav === page) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    if (page === "summary" && state.chart) state.chart.resize();
    if (page === "chat") scrollMessages();
  }

  // ------------------------------------------------------------ 테마
  const THEMES = ["system", "light", "dark"];
  const THEME_LABEL = { system: "시스템", light: "라이트", dark: "다크" };
  function applyTheme(t) {
    if (t === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    $("#themeBtn").textContent = `테마: ${THEME_LABEL[t]}`;
    store.set("theme", t);
    if (state.records.length) renderChart();
  }
  function initTheme() {
    const saved = store.get("theme");
    applyTheme(THEMES.includes(saved) ? saved : "system");
    $("#themeBtn").addEventListener("click", () => {
      const cur = store.get("theme") || "system";
      applyTheme(THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length]);
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => { if (state.records.length) renderChart(); });
  }

  // ------------------------------------------------------------ 요약 화면
  function renderSummary() {
    const s = state.summary;
    if (!s || !s.count) {
      $("#nowBox").innerHTML = `<div class="empty"><b>데이터가 없어요</b>데이터 관리에서 첫 기록을 추가해 보세요.</div>`;
      $("#summaryTable").innerHTML = "";
      $("#ctxStrip").innerHTML = `<span>저장된 데이터가 없어요</span>`;
      return;
    }
    const m = s.metrics, t = s.trend, L = s.latest;
    $("#periodLabel").textContent = `기간 ${s.period} · ${s.count}일`;

    // 최근 기록
    $("#nowDate").textContent = `${L.date} 기준`;
    const pos = Math.min(100, (L.value / 100) * 100);
    $("#nowBox").innerHTML = `
      <div class="now-main">
        <div class="now-date">${esc(L.date)} · 서울 25개 구 평균</div>
        <div class="now-label">초미세먼지 (PM2.5)</div>
        <div class="now-value"><span class="big num">${num(L.value)}</span><span class="unit">${UNIT}</span>${badge(L.value)}</div>
        <div class="now-scale" style="--pos:${pos}%" aria-hidden="true"></div>
        <div class="now-ticks" aria-hidden="true"><span style="left:0">0</span><span style="left:15%">15</span><span style="left:35%">35</span><span style="left:75%">75</span><span style="left:100%">100+</span></div>
      </div>
      <dl class="now-side" style="margin:0">
        <div class="now-item"><dt>미세먼지 PM10</dt><dd class="num">${num(L.pm10)} <small>${UNIT}</small></dd></div>
        <div class="now-item"><dt>평균기온</dt><dd class="num">${num(L.temp_avg)} <small>℃</small></dd></div>
        <div class="now-item"><dt>강수량</dt><dd class="num">${num(L.rain)} <small>mm</small></dd></div>
        <div class="now-item"><dt>평균 풍속</dt><dd class="num">${num(L.wind)} <small>m/s</small></dd></div>
        <div class="now-item"><dt>평균 습도</dt><dd class="num">${num(L.humidity)} <small>%</small></dd></div>
        <div class="now-item"><dt>메모</dt><dd style="font-size:14px">${esc(L.memo) || '<small>없음</small>'}</dd></div>
      </dl>`;

    // 요약 표
    const arrow = { 증가: "▲", 감소: "▼", 유지: "■" }[t.label] || "";
    const tColor = { 증가: "var(--worst)", 감소: "var(--good)", 유지: "var(--muted)" }[t.label] || "inherit";
    $("#summaryTable").innerHTML = `
      <tr><th>데이터 기간</th><td class="num">${esc(s.period)}</td></tr>
      <tr><th>레코드 수</th><td><span class="num">${s.count}</span>개</td></tr>
      <tr><th>평균 / 중앙값</th><td><span class="num">${m.average} / ${m.median}</span> ${UNIT}</td></tr>
      <tr><th>최고</th><td><span class="num">${m.max}</span> ${UNIT} ${badge(m.max)} <span class="muted small num">${esc(m.max_date)}</span></td></tr>
      <tr><th>최저</th><td><span class="num">${m.min}</span> ${UNIT} ${badge(m.min)} <span class="muted small num">${esc(m.min_date)}</span></td></tr>
      <tr><th>최근 추세</th><td><span class="trend" style="color:${tColor}"><span class="trend-arrow">${arrow}</span>${esc(t.label)}</span>
        <div class="muted small">최근 ${t.window_days}일 평균 <span class="num">${t.recent_avg}</span>, 직전 ${t.window_days}일 <span class="num">${t.previous_avg}</span> (${t.change_pct > 0 ? "+" : ""}${t.change_pct}%)</div></td></tr>`;

    // 등급별 일수
    const g = s.grade_days, total = s.count;
    $("#gradeBar").innerHTML = GRADES.map((x) => {
      const n = g[x.label] || 0;
      if (!n) return "";
      const pct = (n / total) * 100;
      return `<span class="s-${x.key}" style="flex:${n}" title="${x.label} ${n}일">${pct >= 7 ? `${Math.round(pct)}%` : ""}</span>`;
    }).join("");
    $("#gradeLegend").innerHTML = GRADES.map((x) => `<span>${badge(x.max === Infinity ? 80 : x.max)} <b class="num">${g[x.label] || 0}</b>일</span>`).join("");
    $("#gradeTable").innerHTML = GRADES.map((x) => `<tr><td>${badge(x.max === Infinity ? 80 : x.max)}</td><td class="r num">${x.range}</td><td class="r num">${g[x.label] || 0}일</td></tr>`).join("");

    // 월별
    $("#monthlyTable").innerHTML = s.monthly.map((r) => `
      <tr><td class="num">${esc(r.month)}</td><td class="r num">${fmt(r.pm25_avg)}</td><td>${badge(r.pm25_avg)}</td>
      <td class="r num hide-sm">${fmt(r.pm10_avg)}</td><td class="r num">${fmt(r.temp_avg)}</td><td class="r num">${fmt(r.rain_total)}</td></tr>`).join("");

    // 기상 조건별
    const wr = s.weather_relation;
    const maxAvg = Math.max(...[...wr.by_temp, ...wr.by_rain, ...wr.by_wind].map((x) => x.pm25_avg), 1);
    const group = (title, items) => `
      <div class="rel"><div class="small" style="font-weight:500">${title}</div>
      ${items.map((x) => `<div class="rel-row"><span>${esc(x.label)} <span class="muted small num">${x.days}일</span></span>
        <span class="rel-track"><span class="rel-fill" style="display:block;width:${(x.pm25_avg / maxAvg) * 100}%"></span></span>
        <span class="rel-val">${x.pm25_avg} ${UNIT}</span></div>`).join("")}</div>`;
    $("#relationBox").innerHTML = group("기온별", wr.by_temp) + group("강수별", wr.by_rain) + group("풍속별", wr.by_wind);

    // 채팅 화면 상단 요약
    $("#ctxStrip").innerHTML = `
      <span><span class="k">AI 참고 데이터</span><b class="num">${esc(s.period)}</b></span>
      <span><span class="k">레코드</span><b class="num">${s.count}개</b></span>
      <span><span class="k">PM2.5 평균</span><b class="num">${m.average}${UNIT}</b></span>
      <span><span class="k">최근 추세</span><b>${esc(t.label)}</b></span>`;
  }

  // ------------------------------------------------------------ 그래프
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function renderChart() {
    const canvas = $("#dailyChart");
    if (!window.Chart || !canvas) return;
    let rows = state.records.slice().sort((a, b) => a.date.localeCompare(b.date));
    if (state.range !== "all") rows = rows.slice(-Number(state.range));

    const primary = css("--primary"), muted = css("--muted"), line = css("--line"),
      bad = css("--bad"), worst = css("--worst"), surface = css("--surface"), text = css("--text");

    const thresholds = {
      id: "thresholds",
      afterDatasetsDraw(chart) {
        const { ctx, chartArea: a, scales: { y } } = chart;
        [[35, "나쁨", bad], [75, "매우나쁨", worst]].forEach(([v, label, color]) => {
          if (v > y.max) return;
          const py = y.getPixelForValue(v);
          ctx.save();
          ctx.strokeStyle = color; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(a.left, py); ctx.lineTo(a.right, py); ctx.stroke();
          ctx.setLineDash([]); ctx.fillStyle = color; ctx.font = "500 11px 'Noto Sans KR', sans-serif";
          ctx.textAlign = "right"; ctx.fillText(label, a.right - 4, py - 4);
          ctx.restore();
        });
      },
    };

    if (state.chart) state.chart.destroy();
    state.chart = new Chart(canvas, {
      type: "line",
      data: {
        labels: rows.map((r) => r.date),
        datasets: [{
          label: "초미세먼지 PM2.5", data: rows.map((r) => r.value),
          borderColor: primary, backgroundColor: primary + "1f", fill: true,
          borderWidth: rows.length > 120 ? 1.5 : 2, pointRadius: rows.length > 60 ? 0 : 2.5,
          pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: surface, pointHoverBackgroundColor: primary,
          tension: 0.2,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: surface, titleColor: text, bodyColor: text, borderColor: line, borderWidth: 1,
            padding: 10, displayColors: false,
            callbacks: {
              title: (items) => items[0].label,
              label: (item) => `PM2.5 ${item.parsed.y}${UNIT} · ${gradeOf(item.parsed.y).label}`,
              afterLabel: (item) => {
                const r = rows[item.dataIndex];
                const out = [`기온 ${num(r.temp_avg)}℃ · 풍속 ${num(r.wind)}m/s · 강수 ${num(r.rain)}mm`];
                if (r.memo) out.push(`메모: ${r.memo}`);
                return out;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false }, border: { color: line },
            ticks: {
              color: muted, maxRotation: 0, autoSkip: true, maxTicksLimit: 12,
              callback(val) { const d = this.getLabelForValue(val); return `${+d.slice(5, 7)}/${+d.slice(8, 10)}`; },
            },
          },
          y: {
            beginAtZero: true, grid: { color: line }, border: { display: false },
            ticks: { color: muted, maxTicksLimit: 6 },
            title: { display: true, text: UNIT, color: muted },
          },
        },
      },
      plugins: [thresholds],
    });
  }

  function initRange() {
    $("#rangeSeg").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-range]");
      if (!b) return;
      state.range = b.dataset.range;
      $$("#rangeSeg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      renderChart();
    });
  }

  // ------------------------------------------------------------ 데이터 관리
  const FIELDS = ["value", "pm10", "temp_avg", "temp_min", "temp_max", "rain", "wind", "humidity"];

  function filteredRecords() {
    let rows = state.records.slice().sort((a, b) => b.date.localeCompare(a.date));
    if (state.month !== "all") rows = rows.filter((r) => r.date.startsWith(state.month));
    if (state.search) rows = rows.filter((r) => (r.memo || "").includes(state.search));
    return rows;
  }

  function renderMonthFilter() {
    const months = [...new Set(state.records.map((r) => r.date.slice(0, 7)))].sort().reverse();
    const sel = $("#monthFilter");
    sel.innerHTML = `<option value="all">전체 기간</option>` + months.map((m) => `<option value="${m}">${m}</option>`).join("");
    sel.value = months.includes(state.month) ? state.month : "all";
  }

  function renderDataTable() {
    const rows = filteredRecords();
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    state.pageNo = Math.min(state.pageNo, pages);
    const slice = rows.slice((state.pageNo - 1) * PAGE_SIZE, state.pageNo * PAGE_SIZE);
    $("#dataCount").textContent = `총 ${state.records.length}건 · 표시 ${rows.length}건`;

    $("#dataTable").innerHTML = slice.length ? slice.map((r) => `
      <tr data-id="${esc(r.id)}" class="${state.editingId === r.id ? "editing" : ""}">
        <td class="num">${esc(r.date)}</td>
        <td class="r num">${num(r.value)}</td>
        <td>${badge(r.value)}</td>
        <td class="r num hide-sm">${num(r.pm10)}</td>
        <td class="r num">${num(r.temp_avg)}</td>
        <td class="r num hide-sm">${num(r.rain)}</td>
        <td class="r num hide-sm">${num(r.wind)}</td>
        <td class="memo hide-sm">${esc(r.memo)}</td>
        <td class="actions">
          <button class="btn btn-sm" type="button" data-act="edit">수정</button>
          <button class="btn btn-sm btn-danger${state.pendingDelete === r.id ? " confirm" : ""}" type="button" data-act="delete">${state.pendingDelete === r.id ? "삭제 확인" : "삭제"}</button>
        </td>
      </tr>`).join("")
      : `<tr><td colspan="9"><div class="empty"><b>조건에 맞는 데이터가 없어요</b>월 선택이나 검색어를 바꿔 보세요.</div></td></tr>`;

    // 페이지네이션 (현재 페이지 앞뒤 2개)
    const pager = $("#pager");
    if (pages <= 1) { pager.innerHTML = ""; return; }
    const btns = [];
    const add = (p, label = p) => btns.push(`<button class="btn btn-sm" type="button" data-page-no="${p}" ${p === state.pageNo ? 'aria-current="page"' : ""}>${label}</button>`);
    if (state.pageNo > 1) add(state.pageNo - 1, "이전");
    for (let p = Math.max(1, state.pageNo - 2); p <= Math.min(pages, state.pageNo + 2); p++) add(p);
    if (state.pageNo < pages) add(state.pageNo + 1, "다음");
    pager.innerHTML = btns.join("") + `<span class="muted small" style="margin-left:6px">${state.pageNo} / ${pages}</span>`;
  }

  function fillForm(r) {
    $("#f-date").value = r ? r.date : "";
    FIELDS.forEach((k) => { $("#f-" + k).value = r && r[k] !== null && r[k] !== undefined ? r[k] : ""; });
    $("#f-memo").value = r ? r.memo || "" : "";
  }

  function setEditing(r) {
    state.editingId = r ? r.id : null;
    fillForm(r);
    $("#f-date").disabled = !!r;
    $("#formTitle").textContent = r ? `데이터 수정 · ${r.date}` : "새 데이터 추가";
    $("#saveBtn").textContent = r ? "수정 저장" : "추가";
    $("#cancelEditBtn").hidden = !r;
    clearFormErrors();
    renderDataTable();
    if (r) { $("#dataForm").scrollIntoView({ behavior: "smooth", block: "start" }); $("#f-value").focus({ preventScroll: true }); }
  }

  function clearFormErrors() {
    ["date", "value", "form"].forEach((k) => { $("#e-" + k).textContent = ""; });
    $$("#dataForm .input").forEach((i) => i.removeAttribute("aria-invalid"));
  }

  function readForm() {
    clearFormErrors();
    let ok = true;
    const fail = (id, msg, errId) => { ok = false; $("#" + id).setAttribute("aria-invalid", "true"); $("#e-" + (errId || "form")).textContent = msg; };

    const date = $("#f-date").value;
    if (!state.editingId && !/^\d{4}-\d{2}-\d{2}$/.test(date)) fail("f-date", "날짜를 선택하세요.", "date");

    const payload = {};
    for (const k of FIELDS) {
      const el = $("#f-" + k);
      const raw = el.value.trim();
      if (raw === "") {
        if (k === "value") fail(el.id, "PM2.5 값을 입력하세요.", "value");
        payload[k] = null;
        continue;
      }
      const v = Number(raw);
      if (Number.isNaN(v) || !el.checkValidity()) {
        const label = el.labels[0].textContent.replace("*", "").trim();
        fail(el.id, `${label}: ${el.min} ~ ${el.max} 사이 숫자를 입력하세요.`, k === "value" ? "value" : "form");
        continue;
      }
      payload[k] = v;
    }
    payload.memo = $("#f-memo").value.trim();
    if (!ok) return null;
    if (!state.editingId) payload.date = date;
    else delete payload.date;
    return payload;
  }

  async function submitForm(e) {
    e.preventDefault();
    const payload = readForm();
    if (!payload) return;
    const btn = $("#saveBtn");
    btn.disabled = true;
    try {
      if (state.editingId) {
        await api.updateData(state.editingId, payload);
        toast(`${state.editingId} 데이터를 수정했어요`);
        setEditing(null);
      } else {
        await api.createData(payload);
        toast(`${payload.date} 데이터를 추가했어요`);
        state.month = payload.date.slice(0, 7);
        fillForm(null);
      }
      await refreshData();
    } catch (err) {
      $("#e-form").textContent = err.message;
    } finally {
      btn.disabled = false;
    }
  }

  async function onTableClick(e) {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const id = b.closest("tr").dataset.id;
    const rec = state.records.find((r) => r.id === id);
    if (b.dataset.act === "edit") { state.pendingDelete = null; setEditing(rec); return; }
    if (state.pendingDelete !== id) {  // 1차 클릭: 확인 단계로 전환 (confirm() 대신)
      state.pendingDelete = id;
      renderDataTable();
      setTimeout(() => { if (state.pendingDelete === id) { state.pendingDelete = null; renderDataTable(); } }, 3500);
      return;
    }
    state.pendingDelete = null;
    try {
      await api.deleteData(id);
      if (state.editingId === id) setEditing(null);
      toast(`${id} 데이터를 삭제했어요`);
      await refreshData();
    } catch (err) { toast(err.message, true); }
  }

  function download(filename, text, type) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportData(kind) {
    const rows = state.records.slice().sort((a, b) => a.date.localeCompare(b.date));
    if (!rows.length) { toast("내보낼 데이터가 없어요", true); return; }
    const cols = ["date", ...FIELDS, "memo"];
    if (kind === "csv") {
      const q = (v) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
      const csv = "﻿" + [cols.join(","), ...rows.map((r) => cols.map((c) => q(r[c])).join(","))].join("\n");
      download("seoul_air.csv", csv, "text/csv;charset=utf-8");
    } else {
      download("seoul_air.json", JSON.stringify(rows.map((r) => Object.fromEntries(cols.map((c) => [c, r[c] ?? null]))), null, 2), "application/json");
    }
    toast(`${rows.length}건을 ${kind.toUpperCase()}로 내보냈어요`);
  }

  function initData() {
    $("#dataForm").addEventListener("submit", submitForm);
    $("#cancelEditBtn").addEventListener("click", () => setEditing(null));
    $("#dataTable").addEventListener("click", onTableClick);
    $("#pager").addEventListener("click", (e) => {
      const b = e.target.closest("[data-page-no]");
      if (b) { state.pageNo = Number(b.dataset.pageNo); renderDataTable(); }
    });
    $("#monthFilter").addEventListener("change", (e) => { state.month = e.target.value; state.pageNo = 1; renderDataTable(); });
    $("#memoSearch").addEventListener("input", (e) => { state.search = e.target.value.trim(); state.pageNo = 1; renderDataTable(); });
    $("#exportCsv").addEventListener("click", () => exportData("csv"));
    $("#exportJson").addEventListener("click", () => exportData("json"));
    $("#dataForm").addEventListener("input", (e) => { if (e.target.matches(".input")) e.target.removeAttribute("aria-invalid"); });
  }

  // ------------------------------------------------------------ 채팅
  const SUGGEST = ["공기가 가장 나빴던 날은 언제야?", "비 오는 날은 미세먼지가 낮아?", "월별로 보면 언제가 제일 나빠?", "최근 추세는 어때?"];

  function scrollMessages() { const box = $("#messages"); box.scrollTop = box.scrollHeight; }

  function renderMessages(loading = false) {
    const box = $("#messages");
    if (!state.messages.length && !loading) {
      const s = state.summary;
      box.innerHTML = `
        <div class="welcome">
          <p><b>무엇이 궁금하세요?</b></p>
          <p class="muted">${s && s.count ? `${esc(s.period)} 동안의 서울 초미세먼지·기상 기록 ${s.count}건을 알고 있어요.` : "데이터를 불러오는 중이에요."} 기록을 근거로 답해 드려요.</p>
          <div class="chips">${SUGGEST.map((q) => `<button class="chip" type="button" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>
        </div>`;
      return;
    }
    box.innerHTML = state.messages.map((m) => `
      <div class="msg ${m.role}${m.error ? " error" : ""}">
        <span class="who">${m.role === "user" ? "나" : "AI 비서"}</span>
        <div class="bubble">${esc(m.content)}</div>
      </div>`).join("") + (loading ? `
      <div class="msg assistant"><span class="who">AI 비서</span>
        <div class="bubble"><span class="typing" aria-label="답변 작성 중"><i></i><i></i><i></i></span> <span class="muted small">데이터를 보고 답변을 쓰는 중이에요</span></div>
      </div>` : "");
    scrollMessages();
  }

  async function send(text) {
    text = text.trim();
    if (!text || state.sending) return;
    state.sending = true;
    $("#sendBtn").disabled = true;
    $("#chatInput").value = "";
    autoGrow();
    state.messages.push({ role: "user", content: text });
    renderMessages(true);
    try {
      const res = await api.chat({ message: text, conversation_id: state.convId });
      state.convId = res.conversation_id;
      state.messages.push({ role: "assistant", content: res.reply });
      renderMessages();
      await refreshConversations();
    } catch (err) {
      state.messages.push({ role: "assistant", content: `답변을 받지 못했어요. ${err.message}`, error: true });
      renderMessages();
      $("#chatInput").value = text;
    } finally {
      state.sending = false;
      $("#sendBtn").disabled = false;
      $("#chatInput").focus();
    }
  }

  function autoGrow() {
    const t = $("#chatInput");
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 140) + "px";
  }

  function newChat() {
    state.convId = null;
    state.messages = [];
    renderMessages();
    renderConversations();
    $("#chatInput").focus();
  }

  async function openConversation(id) {
    try {
      const conv = await api.getConv(id);
      state.convId = conv.id;
      state.messages = conv.messages.map((m) => ({ role: m.role, content: m.content }));
      location.hash = "#chat";
      renderMessages();
      renderConversations();
      toast(`'${conv.title}' 대화를 불러왔어요`);
    } catch (err) { toast(err.message, true); }
  }

  function initChat() {
    $("#chatForm").addEventListener("submit", (e) => { e.preventDefault(); send($("#chatInput").value); });
    $("#chatInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(e.target.value); }
    });
    $("#chatInput").addEventListener("input", autoGrow);
    $("#messages").addEventListener("click", (e) => { const c = e.target.closest("[data-q]"); if (c) send(c.dataset.q); });
    $("#newChatBtn").addEventListener("click", newChat);
    $("#convSide").addEventListener("click", (e) => { const b = e.target.closest("[data-conv]"); if (b) openConversation(b.dataset.conv); });
  }

  // ------------------------------------------------------------ 대화 기록
  const fmtTime = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  };

  function renderConversations() {
    const list = state.conversations;
    $("#convSide").innerHTML = list.length ? list.slice(0, 30).map((c) => `
      <li><button type="button" data-conv="${esc(c.id)}" aria-current="${c.id === state.convId}">
        <span class="t">${esc(c.title)}</span><span class="d num">${fmtTime(c.updated_at)} · ${c.message_count}개</span>
      </button></li>`).join("") : `<li class="empty small">아직 저장된 대화가 없어요</li>`;

    $("#historyCount").textContent = `${list.length}개`;
    $("#historyTable").innerHTML = list.length ? list.map((c) => `
      <tr data-id="${esc(c.id)}">
        <td>${esc(c.title)}${c.id === state.convId ? ' <span class="grade g-good" style="margin-left:4px">열린 대화</span>' : ""}</td>
        <td class="r num">${c.message_count}</td>
        <td class="memo hide-sm">${esc(c.last_message)}</td>
        <td class="num" style="white-space:nowrap">${fmtTime(c.updated_at)}</td>
        <td class="actions">
          <button class="btn btn-sm" type="button" data-act="open">불러오기</button>
          <button class="btn btn-sm btn-danger${state.pendingDelete === "c:" + c.id ? " confirm" : ""}" type="button" data-act="delete">${state.pendingDelete === "c:" + c.id ? "삭제 확인" : "삭제"}</button>
        </td>
      </tr>`).join("")
      : `<tr><td colspan="5"><div class="empty"><b>저장된 대화가 없어요</b>AI 비서에게 질문하면 대화가 자동으로 저장돼요.</div></td></tr>`;
  }

  async function onHistoryClick(e) {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const id = b.closest("tr").dataset.id;
    if (b.dataset.act === "open") { openConversation(id); return; }
    const key = "c:" + id;
    if (state.pendingDelete !== key) {
      state.pendingDelete = key;
      renderConversations();
      setTimeout(() => { if (state.pendingDelete === key) { state.pendingDelete = null; renderConversations(); } }, 3500);
      return;
    }
    state.pendingDelete = null;
    try {
      await api.deleteConv(id);
      if (state.convId === id) newChat();
      toast("대화를 삭제했어요");
      await refreshConversations();
    } catch (err) { toast(err.message, true); }
  }

  // ------------------------------------------------------------ 데이터 불러오기
  async function refreshData() {
    const [records, summary] = await Promise.all([api.listData(), api.summary()]);
    state.records = records;
    state.summary = summary;
    renderSummary();
    renderChart();
    renderMonthFilter();
    renderDataTable();
    if (!state.messages.length) renderMessages();
  }

  async function refreshConversations() {
    state.conversations = await api.listConvs();
    renderConversations();
  }

  async function loadAll() {
    await Promise.all([refreshData(), refreshConversations()]);
  }

  // Render 무료 서버는 한동안 요청이 없으면 잠든다. 첫 요청 전에 /health 로 깨우면서 안내한다.
  async function wakeServer() {
    const slowTimer = setTimeout(() => {
      banner("wake", `<b>서버를 깨우는 중이에요.</b><span>무료 서버라 한동안 쓰지 않으면 잠들어서, 첫 접속은 최대 1분 정도 걸릴 수 있어요.</span>`);
    }, 2500);
    const started = Date.now();
    try {
      while (true) {
        try { await httpApi.health(); return; }
        catch (err) {
          if (Date.now() - started > 90000) throw err;
          await new Promise((r) => setTimeout(r, 3000));
        }
      }
    } finally {
      clearTimeout(slowTimer);
    }
  }

  async function boot() {
    initTheme();
    initRange();
    initData();
    initChat();
    $("#historyTable").addEventListener("click", onHistoryClick);
    $("#refreshHistory").addEventListener("click", () => refreshConversations().then(() => toast("대화 목록을 새로 불러왔어요")).catch((e) => toast(e.message, true)));
    window.addEventListener("hashchange", route);
    route();
    renderMessages();

    if (DEMO) {
      setStatus("demo", "데모 모드");
      banner("demo", `<b>데모 모드</b><span>서버 연결 전이라 브라우저 안의 2025년 예시 데이터로 동작해요. AI 답변은 규칙으로 만든 예시이고, 새로고침하면 변경 내용이 사라져요.</span>`);
    } else {
      setStatus("wait", "서버 연결 중");
    }

    try {
      if (!DEMO) await wakeServer();
      await loadAll();
      if (!DEMO) { banner(null); setStatus("ok", "서버 연결됨"); }
    } catch (err) {
      setStatus("error", "연결 실패");
      banner("error", `<b>서버에 연결하지 못했어요.</b><span>${esc(err.message)}</span> <button class="btn btn-sm" type="button" id="retryBtn">다시 시도</button>`);
      $("#retryBtn")?.addEventListener("click", () => location.reload());
    }
  }

  boot();
})();
