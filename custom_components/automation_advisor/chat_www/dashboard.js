/**
 * Dashboard UI — devices / automations / analysis (logs, thresholds, resend).
 */
(function () {
  const STYLE_ID = "advisor-dashboard-style";

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = `
      .ad-shell {
        --dev: #3db8f5; --auto: #e8b86d; --ok: #3dd68c; --warn: #ff8f6b; --danger: #ff6b7a;
        --panel: #151c25; --panel2: #1b2430; --line: rgba(255,255,255,.1); --muted: #8794a3;
        --term: #0a0f0c; --term-fg: #b7f5c8; --term-dim: #5f8a6c; --term-num: #7dffb3;
        color: #e8eef4;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        min-height: 100%;
        background: radial-gradient(1200px 500px at 10% -10%, #152433 0%, #0c1016 55%);
        font-family: "Instrument Sans", system-ui, sans-serif;
      }
      .ad-shell *, .ad-shell *::before, .ad-shell *::after { box-sizing: border-box; }
      .ad-top {
        position: sticky; top: 0; z-index: 6;
        background: rgba(8,11,15,.96);
        border-bottom: 1px solid var(--line);
      }
      .ad-hdr {
        display:flex; align-items:center; justify-content:space-between; gap:12px;
        padding:14px 18px 8px;
      }
      .ad-brand { font-size:18px; font-weight:750; letter-spacing:-.03em; }
      .ad-sync { display:flex; align-items:center; gap:10px; color:var(--muted); font-size:12px; flex-wrap:wrap; }
      .ad-sync b { color:var(--ok); font-weight:650; }
      .ad-chip {
        display:inline-flex; align-items:center; gap:5px; padding:3px 9px; border-radius:999px;
        font-size:11px; font-weight:650;
      }
      .ad-chip.ok { background:rgba(61,214,140,.12); color:var(--ok); }
      .ad-chip.warn { background:rgba(255,143,107,.14); color:var(--warn); }
      .ad-chip.dev { background:rgba(61,184,245,.14); color:var(--dev); }
      .ad-chip.auto { background:rgba(232,184,109,.14); color:var(--auto); }
      .ad-tabs {
        display:flex !important; gap:4px; padding:4px 14px 12px; background:transparent;
        flex-wrap: wrap;
      }
      .ad-tab {
        appearance:none !important; border:0; cursor:pointer; padding:8px 14px; border-radius:8px;
        font-size:12px !important; font-weight:650; color:#c5d0db !important;
        background:#1b2430 !important; line-height:1.3; min-height:34px;
      }
      .ad-tab:hover { background:#243040 !important; color:#e8eef4 !important; }
      .ad-tab.on { background:#243040 !important; color:#e8eef4 !important; }
      .ad-tab.on[data-kind=dev] { box-shadow:inset 0 -2px 0 var(--dev); }
      .ad-tab.on[data-kind=auto] { box-shadow:inset 0 -2px 0 var(--auto); }
      .ad-tab.on[data-kind=log] { box-shadow:inset 0 -2px 0 #7dffb3; }
      .ad-tab .n {
        margin-left:6px; padding:1px 6px; border-radius:999px;
        background:rgba(255,255,255,.08); font-size:10px;
      }
      .ad-body {
        display: block !important;
        padding:16px 18px 96px;
        min-height: 60vh;
        flex: 1 0 auto;
      }
      .ad-panel { display:none; }
      .ad-panel.on { display:block; }
      .ad-toolbar {
        display:flex; align-items:center; justify-content:space-between; gap:10px;
        margin-bottom:12px; flex-wrap:wrap;
      }
      .ad-title { font-size:14px; font-weight:700; }
      .ad-meta { color:var(--muted); font-size:12px; }
      .ad-room {
        margin:14px 0 8px; font-size:11px; font-weight:750; letter-spacing:.08em;
        text-transform:uppercase; color:var(--muted);
      }
      .ad-room:first-child { margin-top:0; }
      .ad-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
      @media (max-width:820px){ .ad-grid{ grid-template-columns:1fr 1fr; } }
      .ad-card {
        background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px;
      }
      .ad-card.dev { border-left:3px solid var(--dev); }
      .ad-card.auto { border-left:3px solid var(--auto); }
      .ad-card.reason { border-left:3px solid #9b8cff; }
      .ad-cname { font-size:13px; font-weight:700; margin-bottom:4px; }
      .ad-crow { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }
      .ad-dot {
        width:7px; height:7px; border-radius:50%; background:var(--ok);
        display:inline-block; margin-right:4px;
      }
      .ad-dot.off { background:#556270; }
      .ad-dot.warn { background:var(--warn); }
      .ad-list { display:flex; flex-direction:column; gap:8px; }
      .ad-acts { display:flex; gap:6px; margin-top:10px; flex-wrap:wrap; }
      .ad-btn {
        appearance:none; border:0; cursor:pointer; padding:5px 9px; border-radius:6px;
        font-size:11px; font-weight:650; background:#243040; color:#e8eef4;
      }
      .ad-btn.primary { background:rgba(61,184,245,.22); color:var(--dev); }
      .ad-btn.amber { background:rgba(232,184,109,.2); color:var(--auto); }
      .ad-btn.ghost { background:transparent; border:1px solid var(--line); color:var(--muted); }
      .ad-btn.danger { background:rgba(255,107,122,.12); color:var(--danger); }
      .ad-btn.term { background:rgba(125,255,179,.12); color:var(--term-num); }
      .ad-tog { display:inline-flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); }
      .ad-sw {
        width:32px; height:18px; border-radius:999px; background:#2a3542; position:relative;
        cursor:pointer; border:0; padding:0;
      }
      .ad-sw::after {
        content:""; position:absolute; top:2px; left:2px; width:14px; height:14px;
        border-radius:50%; background:#9aa8b5;
      }
      .ad-sw.on { background:rgba(232,184,109,.4); }
      .ad-sw.on::after { left:16px; background:var(--auto); }
      .ad-subnav {
        display:flex; gap:4px; margin-bottom:12px; padding:4px; width:fit-content;
        background:#10161e; border:1px solid var(--line); border-radius:10px;
      }
      .ad-subtab {
        appearance:none; border:0; cursor:pointer; padding:7px 12px; border-radius:7px;
        font-size:12px; font-weight:650; color:var(--muted); background:transparent;
      }
      .ad-subtab.on { background:var(--panel2); color:#e8eef4; }
      .ad-sub { display:none; }
      .ad-sub.on { display:block; }
      .ad-bar { height:8px; border-radius:999px; background:#243040; overflow:hidden; margin-top:8px; }
      .ad-bar > i {
        display:block; height:100%; border-radius:999px;
        background:linear-gradient(90deg,#9b8cff,var(--auto));
      }
      .ad-term {
        background:var(--term); border:1px solid rgba(125,255,179,.18); border-radius:10px; overflow:hidden;
      }
      .ad-term-top {
        display:flex; justify-content:space-between; padding:8px 12px;
        border-bottom:1px solid rgba(125,255,179,.12); background:#0d1410;
        font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
        font-size:11px; color:var(--term-dim);
      }
      .ad-term-top strong { color:var(--term-fg); }
      .ad-term-body {
        height:min(360px,50vh); overflow:auto; position:relative;
        font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
        font-size:12px; line-height:1.55; padding:8px 0;
      }
      .ad-tline {
        display:grid; grid-template-columns:56px 86px 1fr; gap:10px; padding:1px 14px;
        color:var(--term-fg); white-space:nowrap;
      }
      .ad-tline .num { color:var(--term-num); text-align:right; font-variant-numeric:tabular-nums; }
      .ad-tline .ts { color:var(--term-dim); }
      .ad-tline .msg { overflow:hidden; text-overflow:ellipsis; }
      .ad-err { color:var(--danger); font-size:13px; padding:12px; }
      .ad-toasts {
        position:fixed; right:18px; bottom:90px; z-index:40;
        display:flex; flex-direction:column; gap:8px; width:min(320px,calc(100vw - 36px));
        pointer-events:none;
      }
      .ad-toast {
        pointer-events:auto; background:#132018; border:1px solid rgba(125,255,179,.35);
        border-radius:10px; padding:12px 14px; box-shadow:0 12px 40px rgba(0,0,0,.45);
        animation:adIn .22s ease;
      }
      .ad-toast.bad { border-color:rgba(255,107,122,.45); background:#201318; }
      .ad-toast .t { font-size:13px; font-weight:700; color:#eafff1; }
      .ad-toast.bad .t { color:#ffd0d0; }
      .ad-toast .d { font-size:11px; color:var(--term-dim); margin-top:2px; }
      @keyframes adIn { from { opacity:0; transform:translateY(8px);} to { opacity:1; transform:none;} }
    `;
    document.head.appendChild(el);
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function relativeTime(iso) {
    if (!iso) return "—";
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return "—";
    const sec = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (sec < 45) return "방금 전";
    if (sec < 3600) return Math.round(sec / 60) + "분 전";
    if (sec < 86400) return Math.round(sec / 3600) + "시간 전";
    return Math.round(sec / 86400) + "일 전";
  }

  function defaultToken() {
    try {
      const q = new URLSearchParams(location.search || "");
      return q.get("access_token") || q.get("ha_token");
    } catch (_) {
      return null;
    }
  }

  function start(opts) {
    injectStyles();
    const root = (opts && opts.root) || document.getElementById("dash-root");
    if (!root) return;

    const getToken =
      (opts && opts.getAccessToken) ||
      function () {
        return defaultToken();
      };
    const headers =
      (opts && opts.apiHeaders) ||
      function (extra) {
        const h = Object.assign({}, extra || {});
        const token = getToken();
        if (token) h.Authorization = "Bearer " + token;
        return h;
      };

    const state = {
      tab: "devices",
      sub: "logs",
      includeDismissed: false,
      summary: null,
      autos: [],
      logs: null,
      reasons: null,
      poll: null,
    };

    root.innerHTML = `
      <div class="ad-shell">
        <div class="ad-top">
          <div class="ad-hdr">
            <div class="ad-brand">Dashboard</div>
            <div class="ad-sync" id="ad-sync">동기화 <b>—</b></div>
          </div>
          <div class="ad-tabs" role="tablist" aria-label="Dashboard 탭">
            <button type="button" class="ad-tab on" data-kind="dev" data-tab="devices">기기 <span class="n" id="ad-n-dev">0</span></button>
            <button type="button" class="ad-tab" data-kind="auto" data-tab="autos">자동화 <span class="n" id="ad-n-auto">0</span></button>
            <button type="button" class="ad-tab" data-kind="log" data-tab="analysis">분석</button>
          </div>
        </div>
        <div class="ad-body">
          <div class="ad-panel on" id="ad-panel-devices"><div class="ad-meta">기기 불러오는 중…</div></div>
          <div class="ad-panel" id="ad-panel-autos"></div>
          <div class="ad-panel" id="ad-panel-analysis"></div>
        </div>
        <div class="ad-toasts" id="ad-toasts" aria-live="polite"></div>
      </div>
    `;

    const toastBox = root.querySelector("#ad-toasts");

    function toast(title, detail, bad) {
      const el = document.createElement("div");
      el.className = "ad-toast" + (bad ? " bad" : "");
      el.innerHTML = `<div class="t">${esc(title)}</div><div class="d">${esc(detail || "")}</div>`;
      toastBox.appendChild(el);
      setTimeout(() => el.remove(), 2800);
    }

    async function api(path, init) {
      const token = getToken();
      if (!token) {
        throw new Error("HA에 로그인한 상태로 패널을 열어주세요.");
      }
      const res = await fetch(path, Object.assign({ credentials: "same-origin", cache: "no-store" }, init || {}, {
        headers: headers(
          Object.assign(
            { "Content-Type": "application/json" },
            (init && init.headers) || {}
          )
        ),
      }));
      if (res.status === 401) {
        throw new Error("HA에 로그인한 상태로 패널을 열어주세요.");
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok && data && data.error) throw new Error(data.error);
      if (!res.ok) throw new Error("요청 실패 (" + res.status + ")");
      return data;
    }

    async function postAction(kind, suggestionId) {
      return api("/api/automation_advisor/dashboard/action", {
        method: "POST",
        body: JSON.stringify({ kind: kind, suggestion_id: suggestionId || null }),
      });
    }

    function setTab(tab) {
      state.tab = tab;
      root.querySelectorAll(".ad-tab").forEach((b) => {
        b.classList.toggle("on", b.getAttribute("data-tab") === tab);
      });
      root.querySelector("#ad-panel-devices").classList.toggle("on", tab === "devices");
      root.querySelector("#ad-panel-autos").classList.toggle("on", tab === "autos");
      root.querySelector("#ad-panel-analysis").classList.toggle("on", tab === "analysis");
      void refresh();
    }

    root.querySelectorAll(".ad-tab").forEach((btn) => {
      btn.addEventListener("click", () => setTab(btn.getAttribute("data-tab")));
    });

    function renderSync() {
      const s = state.summary;
      const el = root.querySelector("#ad-sync");
      if (!el) return;
      if (!s) {
        el.innerHTML = "동기화 <b>—</b>";
        return;
      }
      const warn =
        s.anomaly_count > 0
          ? `<span class="ad-chip warn">이상 ${s.anomaly_count}</span>`
          : `<span class="ad-chip ok">온라인</span>`;
      el.innerHTML = `${warn}<span>동기화 <b>${esc(relativeTime(s.synced_at))}</b></span><span>·</span><span>기기 ${s.device_count}</span>`;
      const nDev = root.querySelector("#ad-n-dev");
      const nAuto = root.querySelector("#ad-n-auto");
      if (nDev) nDev.textContent = String(s.device_count || 0);
      if (nAuto) {
        nAuto.textContent = String(
          (state.autos && state.autos.length) || s.pending_count || 0
        );
      }
    }

    function renderDevices() {
      const panel = root.querySelector("#ad-panel-devices");
      const devices = (state.summary && state.summary.devices) || [];
      if (!devices.length) {
        panel.innerHTML = `<div class="ad-meta">표시할 기기가 없습니다.</div>`;
        return;
      }
      const byArea = {};
      devices.forEach((d) => {
        const a = d.area || "기타";
        (byArea[a] || (byArea[a] = [])).push(d);
      });
      let html = `
        <div class="ad-toolbar">
          <div><div class="ad-title">연결된 기기</div>
          <div class="ad-meta">방별 목록 · 상태 · 연결된 자동화 수</div></div>
        </div>`;
      Object.keys(byArea)
        .sort()
        .forEach((area) => {
          html += `<div class="ad-room">${esc(area)}</div><div class="ad-grid">`;
          byArea[area].forEach((d) => {
            const dot = d.ok
              ? d.state === "off" || d.state === "closed"
                ? "off"
                : ""
              : "warn";
            html += `<div class="ad-card dev">
              <div class="ad-crow">
                <div class="ad-cname"><span class="ad-dot ${dot}"></span>${esc(d.name)}</div>
                <span class="ad-chip ${d.ok ? "ok" : "warn"}">${esc(d.state)}</span>
              </div>
              <div class="ad-meta">자동화 ${d.automation_count} · 추천 ${d.suggestion_count}</div>
            </div>`;
          });
          html += `</div>`;
        });
      panel.innerHTML = html;
    }

    function renderAutos() {
      const panel = root.querySelector("#ad-panel-autos");
      const items = state.autos || [];
      let html = `
        <div class="ad-toolbar">
          <div><div class="ad-title">자동화</div>
          <div class="ad-meta">추천 · 활성 · 수정/삭제 · 거절 목록</div></div>
          <label class="ad-tog">
            <button type="button" class="ad-sw ${state.includeDismissed ? "on" : ""}" id="ad-reject-sw" aria-pressed="${state.includeDismissed}"></button>
            거절한 자동화 보기
          </label>
        </div>
        <div class="ad-list">`;
      if (!items.length) {
        html += `<div class="ad-meta">표시할 항목이 없습니다.</div>`;
      }
      items.forEach((it) => {
        const pending = it.status === "pending" || it.status === "previewed";
        const chip =
          it.status === "dismissed"
            ? "warn"
            : pending
              ? "auto"
              : "ok";
        const label =
          it.status === "pending"
            ? "추천"
            : it.status === "previewed"
              ? "미리보기"
              : it.status === "dismissed"
                ? "거절"
                : "자동화";
        let acts = "";
        if (it.status === "pending" || it.status === "previewed") {
          acts = `
            <button type="button" class="ad-btn primary" data-act="approve" data-id="${esc(it.id)}">승인</button>
            <button type="button" class="ad-btn ghost" data-act="later" data-id="${esc(it.id)}">나중에</button>
            <button type="button" class="ad-btn danger" data-act="dismiss" data-id="${esc(it.id)}">기각</button>`;
        } else if (it.status === "deployed") {
          acts = `
            <button type="button" class="ad-btn amber" data-act="edit" data-id="${esc(it.id)}">수정</button>
            <button type="button" class="ad-btn danger" data-act="delete" data-id="${esc(it.id)}">삭제</button>`;
        } else {
          acts = `<button type="button" class="ad-btn amber" data-act="resend" data-id="${esc(it.id)}">다시 추천</button>
            <button type="button" class="ad-btn ghost" data-act="delete" data-id="${esc(it.id)}">삭제</button>`;
        }
        html += `<div class="ad-card auto">
          <div class="ad-crow">
            <div>
              <div class="ad-cname">${esc(it.title)}</div>
              <div class="ad-meta">${esc(it.status)} · ${esc(it.explanation || it.source || "")}</div>
            </div>
            <span class="ad-chip ${chip}">${label}</span>
          </div>
          <div class="ad-acts">${acts}</div>
        </div>`;
      });
      html += `</div>`;
      panel.innerHTML = html;
      const sw = panel.querySelector("#ad-reject-sw");
      if (sw) {
        sw.addEventListener("click", () => {
          state.includeDismissed = !state.includeDismissed;
          void refreshAutos();
        });
      }
      panel.querySelectorAll("[data-act]").forEach((btn) => {
        btn.addEventListener("click", () => void onAct(btn.getAttribute("data-act"), btn.getAttribute("data-id")));
      });
    }

    function renderAnalysis() {
      const panel = root.querySelector("#ad-panel-analysis");
      const logs = state.logs;
      const reasons = state.reasons;
      const pending = (state.autos || []).filter(
        (x) => x.status === "pending" || x.status === "previewed"
      );
      panel.innerHTML = `
        <div class="ad-toolbar">
          <div><div class="ad-title">분석</div>
          <div class="ad-meta">로그 · 추천 근거(임계값) · 알림 재전송</div></div>
          <button type="button" class="ad-btn term" id="ad-scan">로그 분석 · 스캔</button>
        </div>
        <div class="ad-subnav">
          <button type="button" class="ad-subtab ${state.sub === "logs" ? "on" : ""}" data-sub="logs">로그</button>
          <button type="button" class="ad-subtab ${state.sub === "reasons" ? "on" : ""}" data-sub="reasons">임계값</button>
          <button type="button" class="ad-subtab ${state.sub === "resend" ? "on" : ""}" data-sub="resend">알림 재전송</button>
        </div>
        <div class="ad-sub ${state.sub === "logs" ? "on" : ""}" id="ad-sub-logs"></div>
        <div class="ad-sub ${state.sub === "reasons" ? "on" : ""}" id="ad-sub-reasons"></div>
        <div class="ad-sub ${state.sub === "resend" ? "on" : ""}" id="ad-sub-resend"></div>
      `;

      const logEl = panel.querySelector("#ad-sub-logs");
      const lines = (logs && logs.lines) || [];
      let term = `
        <div class="ad-term">
          <div class="ad-term-top">
            <span><strong>event_store</strong> · live tail</span>
            <span>수집 ${(logs && logs.total) || 0} · ${(logs && logs.span_days) || 0}d</span>
          </div>
          <div class="ad-term-body">`;
      if (!lines.length) {
        term += `<div class="ad-tline"><span class="num">—</span><span class="ts">--:--:--</span><span class="msg">waiting for events</span></div>`;
      } else {
        lines.forEach((ln) => {
          const ts = (ln.ts || "").slice(11, 19) || "--:--:--";
          term += `<div class="ad-tline"><span class="num">${esc(ln.n)}</span><span class="ts">${esc(ts)}</span><span class="msg">${esc(ln.msg)}</span></div>`;
        });
      }
      term += `</div></div>`;
      logEl.innerHTML = term;

      const reasonEl = panel.querySelector("#ad-sub-reasons");
      const thr = (reasons && reasons.thresholds) || {};
      const items = (reasons && reasons.items) || [];
      let rh = `<div class="ad-meta" style="margin-bottom:8px">임계 confidence ≥ ${esc(thr.min_confidence)} · support ≥ ${esc(thr.min_support)}</div><div class="ad-list">`;
      if (!items.length) rh += `<div class="ad-meta">근거 항목이 없습니다.</div>`;
      items.forEach((it) => {
        const score = typeof it.score === "number" ? it.score : null;
        const pct = score == null ? 0 : Math.round(score * 100);
        rh += `<div class="ad-card reason">
          <div class="ad-crow">
            <div>
              <div class="ad-cname">${esc(it.title)}</div>
              <div class="ad-meta">${esc(it.explanation || "")}</div>
            </div>
            <span class="ad-chip ${it.above_threshold ? "ok" : "warn"}">${score == null ? "—" : score.toFixed(2)}</span>
          </div>
          <div class="ad-bar"><i style="width:${pct}%"></i></div>
        </div>`;
      });
      rh += `</div>`;
      reasonEl.innerHTML = rh;

      const resendEl = panel.querySelector("#ad-sub-resend");
      let sh = `
        <div class="ad-toolbar" style="margin-bottom:8px">
          <div class="ad-meta">대기 중 추천을 Companion / 웹으로 다시 보냄</div>
          <button type="button" class="ad-btn amber" id="ad-resend-all">선택 항목 재전송</button>
        </div>
        <div class="ad-list">`;
      if (!pending.length) sh += `<div class="ad-meta">재전송할 대기 추천이 없습니다.</div>`;
      pending.forEach((it) => {
        sh += `<div class="ad-card auto">
          <div class="ad-crow">
            <div>
              <div class="ad-cname">${esc(it.title)}</div>
              <div class="ad-meta">${esc(it.explanation || it.status)}</div>
            </div>
            <button type="button" class="ad-btn primary" data-act="resend" data-id="${esc(it.id)}">다시 보내기</button>
          </div>
        </div>`;
      });
      sh += `</div>`;
      resendEl.innerHTML = sh;

      panel.querySelectorAll(".ad-subtab").forEach((b) => {
        b.addEventListener("click", () => {
          state.sub = b.getAttribute("data-sub");
          renderAnalysis();
        });
      });
      const scan = panel.querySelector("#ad-scan");
      if (scan) scan.addEventListener("click", () => void onAct("scan"));
      const all = panel.querySelector("#ad-resend-all");
      if (all) all.addEventListener("click", () => void onAct("resend_all"));
      panel.querySelectorAll("[data-act=resend]").forEach((btn) => {
        btn.addEventListener("click", () => void onAct("resend", btn.getAttribute("data-id")));
      });
    }

    async function onAct(kind, id) {
      if (kind === "edit") {
        toast("수정은 챗봇에서", "오른쪽 아래 챗봇에서 자동화 수정을 요청해 주세요.");
        return;
      }
      try {
        const result = await postAction(kind, id);
        if (!result.ok) {
          toast("실패", result.error || "처리할 수 없습니다.", true);
          return;
        }
        if (kind === "resend" || kind === "resend_all") {
          toast("알림 발송 완료", kind === "resend_all"
            ? `대기 추천 ${result.prompted || 0}건을 재전송했습니다.`
            : "추천을 Companion / 웹으로 다시 보냈습니다.");
        } else if (kind === "scan") {
          toast("스캔 완료", `신규 ${result.scanned || 0} · 알림 ${result.prompted || 0}`);
        } else {
          toast("완료", "반영했습니다.");
        }
        await refresh();
      } catch (err) {
        toast("실패", String(err.message || err), true);
      }
    }

    async function refreshAutos() {
      try {
        const data = await api(
          "/api/automation_advisor/dashboard/automations?include_dismissed=" +
            (state.includeDismissed ? "1" : "0")
        );
        state.autos = data.items || [];
        renderSync();
        if (state.tab === "autos") renderAutos();
        if (state.tab === "analysis") renderAnalysis();
      } catch (err) {
        if (state.tab === "autos") {
          root.querySelector("#ad-panel-autos").innerHTML =
            `<div class="ad-err">${esc(err.message || err)}</div>`;
        }
      }
    }

    async function refresh() {
      try {
        state.summary = await api("/api/automation_advisor/dashboard/summary");
        renderSync();
      } catch (err) {
        const panel = root.querySelector("#ad-panel-devices");
        if (panel) {
          panel.innerHTML = `<div class="ad-err">${esc(err.message || err)}</div>`;
        }
        return;
      }

      try {
        if (state.tab === "devices") renderDevices();
      } catch (err) {
        const panel = root.querySelector("#ad-panel-devices");
        if (panel) {
          panel.innerHTML = `<div class="ad-err">${esc(err.message || err)}</div>`;
        }
      }

      try {
        const data = await api(
          "/api/automation_advisor/dashboard/automations?include_dismissed=" +
            (state.includeDismissed ? "1" : "0")
        );
        state.autos = data.items || [];
        renderSync();
      } catch (_) {}

      if (state.tab === "autos") renderAutos();

      if (state.tab === "analysis") {
        try {
          state.logs = await api("/api/automation_advisor/dashboard/logs?limit=100");
          state.reasons = await api("/api/automation_advisor/dashboard/reasons");
        } catch (err) {
          root.querySelector("#ad-panel-analysis").innerHTML =
            `<div class="ad-err">${esc(err.message || err)}</div>`;
          return;
        }
        renderAnalysis();
      }
    }

    clearInterval(state.poll);
    state.poll = setInterval(() => {
      void refresh();
    }, 8000);
    void refresh();
  }

  window.AdvisorDashboard = { start: start };
})();
