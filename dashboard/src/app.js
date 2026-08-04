// ── State ──────────────────────────────────────────────────────────────────
const state = {
  vin:     "YS3FD45Y381234567",   // Your 9-3's VIN — update here
  session: null,
  liveData: null,
};

// ── Stub data (replaced by live backend when J2534 connected) ──────────────
const STUB_ECU_INFO = {
  "VIN":             "YS3FD45Y381234567",
  "PART_NUMBER":     "55564890",
  "ECU_SERIAL":      "T8-2008-B284R",
  "SW_VERSION":      "E87 v1.14",
  "CAL_FINGERPRINT": "Trionic8-StageOEM",
};

const STUB_LIVE = [
  { name:"RPM",           value:850,   unit:"rpm",    warn: v=>v>6500 },
  { name:"BOOST",         value:95.0,  unit:"kPa",    warn: v=>v>200 },
  { name:"IAT",           value:22.5,  unit:"°C",     warn: v=>v>55 },
  { name:"COOLANT",       value:91.0,  unit:"°C",     warn: v=>v>105 },
  { name:"THROTTLE",      value:3.2,   unit:"%",      warn: ()=>false },
  { name:"IGN TIMING",    value:12.5,  unit:"°BTDC",  warn: ()=>false },
  { name:"INJ PW",        value:2.14,  unit:"ms",     warn: ()=>false },
  { name:"LAMBDA",        value:1.00,  unit:"λ",      warn: v=>v<0.85||v>1.15 },
  { name:"KNOCK RETARD",  value:0.0,   unit:"°",      warn: v=>v>5 },
  { name:"WASTEGATE",     value:12.0,  unit:"% duty", warn: ()=>false },
  { name:"HALDEX",        value:0.0,   unit:"%",      warn: ()=>false },
  { name:"BATTERY",       value:14.1,  unit:"V",      warn: v=>v<11.5||v>15.5 },
  { name:"SPEED",         value:0,     unit:"km/h",   warn: ()=>false },
  { name:"MAF",           value:2.8,   unit:"g/s",    warn: ()=>false },
  { name:"FUEL TRIM ST",  value:+1.2,  unit:"%",      warn: v=>Math.abs(v)>10 },
  { name:"FUEL TRIM LT",  value:-0.4,  unit:"%",      warn: v=>Math.abs(v)>15 },
];

const STUB_DTCS = [
  // empty by default — populated when DTCs present
];

// ── Nav ────────────────────────────────────────────────────────────────────
document.querySelectorAll("nav a").forEach(a => {
  a.addEventListener("click", e => {
    e.preventDefault();
    const id = a.dataset.panel;
    document.querySelectorAll("nav a").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
    a.classList.add("active");
    document.getElementById("panel-" + id).classList.add("active");
  });
});

// ── Init ───────────────────────────────────────────────────────────────────
function init() {
  document.getElementById("header-vin").textContent = "VIN: " + state.vin;
  document.getElementById("ov-vin").textContent     = state.vin;
  document.getElementById("ov-ecu-status").textContent = "ONLINE (stub)";
  document.getElementById("ov-j2534").textContent      = "DISCONNECTED";
  document.getElementById("card-j2534").className       = "card warn";
  document.getElementById("ov-dtc-count").textContent   = STUB_DTCS.length;
  document.getElementById("card-dtc").className          = STUB_DTCS.length > 0 ? "card error" : "card ok";
  document.getElementById("ov-session").textContent     = "STUB";
  document.getElementById("ov-last-run").textContent    = new Date().toLocaleString();
  document.getElementById("sb-j2534").innerHTML =
    '<span class="dot dot-warn"></span>J2534: disconnected (stub)';
  document.getElementById("sb-session").textContent = "VIN: " + state.vin;

  renderLive();
  renderECUInfo();
  renderDTCs();
  updateClock();
}

// ── Live data ──────────────────────────────────────────────────────────────
function renderLive() {
  const grid = document.getElementById("live-grid");
  grid.innerHTML = "";
  STUB_LIVE.forEach(item => {
    const isWarn = item.warn(item.value);
    const cell = document.createElement("div");
    cell.className = "live-cell";
    cell.innerHTML = `
      <div class="lc-name">${item.name}</div>
      <div class="lc-value" style="color:${isWarn ? "var(--warn)" : "var(--text)"}">
        ${typeof item.value === "number" && !Number.isInteger(item.value)
          ? item.value.toFixed(1) : item.value}
        <span class="lc-unit">${item.unit}</span>
      </div>`;
    grid.appendChild(cell);
  });
}

function refreshLive() {
  // Jitter stub values slightly to simulate live polling
  STUB_LIVE.forEach(item => {
    if (typeof item.value === "number") {
      item.value = +(item.value * (0.97 + Math.random() * 0.06)).toFixed(
        item.unit === "rpm" || item.unit === "km/h" ? 0 : 1
      );
    }
  });
  renderLive();
}

function exportLive() {
  const data = {};
  STUB_LIVE.forEach(i => { data[i.name] = { value: i.value, unit: i.unit }; });
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `live-data-${state.vin}-${Date.now()}.json`;
  a.click();
}

// ── ECU info ───────────────────────────────────────────────────────────────
function renderECUInfo() {
  const tbl = document.getElementById("ecu-info-table");
  tbl.innerHTML = Object.entries(STUB_ECU_INFO).map(([k, v]) =>
    `<tr><td>${k}</td><td>${v}</td></tr>`
  ).join("");
}

// ── DTCs ───────────────────────────────────────────────────────────────────
function renderDTCs() {
  const tbody = document.getElementById("dtc-tbody");
  if (STUB_DTCS.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="color:var(--ok);text-align:center;padding:20px">
      No active fault codes</td></tr>`;
    return;
  }
  tbody.innerHTML = STUB_DTCS.map(d => `
    <tr>
      <td style="color:var(--accent2)">${d.code}</td>
      <td>${d.desc}</td>
      <td><span class="badge badge-${d.severity}">${d.status}</span></td>
      <td>${d.module}</td>
    </tr>`).join("");
}

function readDTCs() {
  // Stub — would call Python backend over local API when connected
  renderDTCs();
  appendLog("INFO", "DTC read requested (stub mode)");
}

function clearDTCs() {
  STUB_DTCS.length = 0;
  renderDTCs();
  document.getElementById("ov-dtc-count").textContent = "0";
  document.getElementById("card-dtc").className = "card ok";
  appendLog("INFO", "DTCs cleared (stub)");
}

// ── Log viewer ─────────────────────────────────────────────────────────────
const _logLines = [];
function appendLog(level, msg) {
  const ts = new Date().toTimeString().slice(0,8);
  _logLines.push({ ts, level, msg });
  renderLog();
}
function renderLog() {
  const viewer = document.getElementById("log-viewer");
  viewer.innerHTML = _logLines.map(e =>
    `<div class="log-${e.level}">[${e.ts}] [${e.level.padEnd(5)}] ${e.msg}</div>`
  ).join("");
  viewer.scrollTop = viewer.scrollHeight;
}
function loadLog() { renderLog(); }
function clearLogView() { _logLines.length = 0; renderLog(); }

// ── Sessions ───────────────────────────────────────────────────────────────
function loadSessions() {
  const list = document.getElementById("session-list");
  const stubs = [
    { vin: state.vin, ts: "2024-01-15 14:32", prefix: "diag",  errors: 0, dtcs: 0 },
    { vin: state.vin, ts: "2024-01-12 09:18", prefix: "scan",  errors: 0, dtcs: 2 },
    { vin: state.vin, ts: "2024-01-10 17:05", prefix: "diag",  errors: 1, dtcs: 1 },
  ];
  list.innerHTML = stubs.map(s => `
    <div class="session-item">
      <div>
        <div class="si-vin">${s.vin}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:3px">${s.prefix.toUpperCase()} run</div>
      </div>
      <div class="si-meta">
        <div class="si-ts">${s.ts}</div>
        <div style="margin-top:4px">
          <span class="badge ${s.errors>0 ? 'badge-error' : 'badge-ok'}">
            ${s.errors} errors
          </span>
          &nbsp;
          <span class="badge ${s.dtcs>0 ? 'badge-warn' : 'badge-ok'}">
            ${s.dtcs} DTCs
          </span>
        </div>
      </div>
    </div>`).join("");
}

// ── Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  document.getElementById("sb-time").textContent = new Date().toLocaleTimeString();
  setTimeout(updateClock, 1000);
}

// ── CAN Sniffer panel (client-side demo capture — mirrors src.sniffer.engine) ─
const sniffer = {
  frames: [],
  idStats: {},
  capture() {
    const ids = [0x120, 0x1A0, 0x280, 0x7E8];
    for (let i = 0; i < 15; i++) {
      const id = ids[Math.floor(Math.random() * ids.length)];
      const data = Array.from({length: 8}, () => Math.floor(Math.random() * 256));
      const frame = { id, data, ts: Date.now() / 1000 };
      this.frames.push(frame);
      const key = "0x" + id.toString(16).toUpperCase().padStart(3, "0");
      const s = this.idStats[key] || { count: 0, last: null };
      s.count++; s.last = data;
      this.idStats[key] = s;
    }
    this.render();
    appendLog("INFO", `Captured ${this.frames.length} total sniffer frames (demo)`);
  },
  clear() { this.frames = []; this.idStats = {}; this.render(); },
  render() {
    document.getElementById("sniff-total").textContent = this.frames.length;
    document.getElementById("sniff-unique").textContent = Object.keys(this.idStats).length;
    document.getElementById("sniff-bitrate").textContent =
      this.frames.length >= 10 ? "500 kbps (est.)" : "—";
    const tbody = document.getElementById("sniff-tbody");
    tbody.innerHTML = Object.entries(this.idStats).map(([id, s]) => `
      <tr><td style="color:var(--accent2)">${id}</td><td>${s.count}</td><td>${(s.count * 2).toFixed(1)}</td>
      <td>${s.last.map(b => b.toString(16).toUpperCase().padStart(2,"0")).join(" ")}</td></tr>`).join("")
      || `<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:16px">No frames captured</td></tr>`;
  },
  exportJSON() { this._download(JSON.stringify(this.frames, null, 2), "capture.json", "application/json"); },
  exportLog() {
    const text = this.frames.map(f => `(${f.ts.toFixed(6)}) CAN1 ${f.id.toString(16).toUpperCase()}#${f.data.map(b=>b.toString(16).toUpperCase().padStart(2,"0")).join("")}`).join("\n");
    this._download(text, "capture.log", "text/plain");
  },
  exportASC() {
    const text = this.frames.map(f => `${f.ts.toFixed(6)} 1  ${f.id.toString(16).toUpperCase()}  Rx d ${f.data.length} ${f.data.map(b=>b.toString(16).toUpperCase().padStart(2,"0")).join(" ")}`).join("\n");
    this._download(text, "capture.asc", "text/plain");
  },
  _download(content, filename, type) {
    const blob = new Blob([content], { type });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  }
};

// ── Flash-Safe checklist panel ────────────────────────────────────────────
const flashsafe = {
  lastResults: [],
  evaluate() {
    // Mirrors src.flashsafe.checklist.FlashSafeChecklist against demo telemetry.
    this.lastResults = [
      { name: "battery_voltage", status: "PASS", detail: "13.10 V (minimum 12.4 V)" },
      { name: "ignition_state", status: "PASS", detail: "ON" },
      { name: "can_bus_stability", status: "PASS", detail: "Stable" },
      { name: "j2534_buffer", status: "PASS", detail: "OK" },
      { name: "programming_session", status: "PASS", detail: "Active" },
      { name: "blocking_dtcs", status: "PASS", detail: "No blocking DTCs" },
      { name: "calibration_file", status: "PASS", detail: "Verified against calibration catalog" },
    ];
    this.render();
  },
  render() {
    const tbody = document.getElementById("flashsafe-tbody");
    tbody.innerHTML = this.lastResults.map(r => `
      <tr><td>${r.name}</td>
      <td><span class="badge badge-${r.status === "PASS" ? "ok" : r.status === "FAIL" ? "error" : "warn"}">${r.status}</span></td>
      <td>${r.detail}</td></tr>`).join("");
    const allClear = this.lastResults.length > 0 && this.lastResults.every(r => r.status === "PASS");
    document.getElementById("flashsafe-summary").textContent = allClear ? "YES" : "NO";
    document.getElementById("flashsafe-summary-card").className = "card " + (allClear ? "ok" : "error");
  }
};

// ── ECU flashing panel ────────────────────────────────────────────────────
const flashing = {
  start() {
    if (!flashsafe.lastResults.length) flashsafe.evaluate();
    const allClear = flashsafe.lastResults.every(r => r.status === "PASS");
    const log = document.getElementById("flash-log");
    const emit = (msg) => { const d = document.createElement("div"); d.className = "log-INFO";
      d.textContent = `[${new Date().toTimeString().slice(0,8)}] ${msg}`; log.appendChild(d); log.scrollTop = log.scrollHeight; };
    if (!allClear) {
      document.getElementById("flash-state").textContent = "FAILED";
      emit("Flash-safe checklist not clear — aborting (see Flash-Safe Mode panel)");
      return;
    }
    document.getElementById("flash-security").textContent = "No licensed provider configured";
    emit("Requesting programming-level security access...");
    emit("No licensed SeedKeyProvider configured — refusing real programming access.");
    emit("(This demo panel stops here by design — see docs/security-access-disclaimer.md)");
    document.getElementById("flash-state").textContent = "FAILED";
    document.getElementById("flash-progress").textContent = "0%";
  }
};

// ── Tech2/MDI emulator panel ──────────────────────────────────────────────
const emulator = {
  capabilities: {
    ENGINE: { name: "Engine Control Module", dtcs: 0, rpm: 850, coolant: 91 },
    TRANS:  { name: "Transmission Control Module", dtcs: 0, gear: "P" },
    ABS:    { name: "ABS/Brake Control Module", dtcs: 0, wheelSpeed: 0 },
    BCM:    { name: "Body Control Module", dtcs: 1 },
  },
  menu: ["Read Diagnostic Trouble Codes", "Display Live Data", "Actuator Tests / Special Functions",
         "SPS Programming Passthrough", "Snapshot Viewer", "Safe CAN Injection (bench only)"],
  render(module) {
    const cap = this.capabilities[module];
    const grid = document.getElementById("emulator-grid");
    grid.innerHTML = Object.entries(cap).filter(([k]) => k !== "name").map(([k, v]) => `
      <div class="card ${k === 'dtcs' && v > 0 ? 'error' : 'ok'}"><div class="card-label">${k.toUpperCase()}</div><div class="card-value">${v}</div></div>`).join("");
    document.getElementById("emulator-menu").innerHTML = this.menu.map((m, i) => `
      <div class="session-item"><div>${i+1}. ${m}</div><div class="si-meta">${cap.name}</div></div>`).join("");
  }
};

// ── Cloud history panel (mirrors src.cloud.sync.OfflineCache) ────────────
const cloud = {
  pending: 3,
  lastSync: null,
  entries: [
    { type: "vin_profiles", vin: state.vin, recorded: "2024-01-15 14:32" },
    { type: "dtc_history", vin: state.vin, recorded: "2024-01-15 14:33" },
    { type: "flash_history", vin: state.vin, recorded: "2024-01-10 09:00" },
  ],
  sync() {
    this.pending = 0;
    this.lastSync = new Date().toLocaleString();
    this.render();
    appendLog("INFO", "Cloud sync queue flushed (demo — see backend/app/routes_sync.py for the real endpoint)");
  },
  render() {
    document.getElementById("cloud-pending").textContent = this.pending;
    document.getElementById("cloud-last-sync").textContent = this.lastSync || "Never";
    document.getElementById("cloud-tbody").innerHTML = this.entries.map(e => `
      <tr><td>${e.type}</td><td style="color:var(--accent2)">${e.vin}</td><td>${e.recorded}</td></tr>`).join("");
  }
};

// ── Remote diagnostics panel ──────────────────────────────────────────────
const remote = {
  connected: false,
  connect() {
    this.connected = true;
    document.getElementById("remote-status").textContent = "Connected (demo session)";
    document.getElementById("remote-status-card").className = "card ok";
    appendLog("INFO", "Remote diagnostics session opened (see backend/app/websocket_remote.py)");
  },
  sendChat() {
    const input = document.getElementById("remote-chat-input");
    if (!input.value.trim()) return;
    const chat = document.getElementById("remote-chat");
    const d = document.createElement("div"); d.className = "log-DATA";
    d.textContent = `[${new Date().toTimeString().slice(0,8)}] technician: ${input.value}`;
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
    input.value = "";
  }
};

// ── Calibration catalog + plugin manager (static demo data) ──────────────
function renderCalibrationCatalog() {
  const rows = [
    { cal_id: "CAL0001", calibration_id: "Trionic8-StageOEM", os_id: "E87-BASE", cvn: "4F2A9B10", applicability: "YS3FD45Y3" },
    { cal_id: "CAL0002", calibration_id: "Trionic8-StageOEM-r2", os_id: "E87-BASE", cvn: "7C1D3E44", applicability: "YS3FD45Y3" },
  ];
  document.getElementById("calibration-tbody").innerHTML = rows.map(r => `
    <tr><td style="color:var(--accent2)">${r.cal_id}</td><td>${r.calibration_id}</td><td>${r.os_id}</td><td>${r.cvn}</td><td>${r.applicability}</td></tr>`).join("");
}

function renderPluginManager() {
  const rows = [
    { oem: "gm", protocols: "ISO15765, GMLAN, KWP2000", years: "1996–2026", services: "haldex_relearn, epb_service_mode" },
    { oem: "ford", protocols: "ISO15765, ISO9141", years: "1998–2026", services: "read_as_built_data" },
  ];
  document.getElementById("plugins-tbody").innerHTML = rows.map(r => `
    <tr><td style="color:var(--accent2)">${r.oem}</td><td>${r.protocols}</td><td>${r.years}</td><td>${r.services}</td></tr>`).join("");
}

// ── Startup log entries ────────────────────────────────────────────────────
appendLog("INFO", "SAAB-SUITE Dashboard initialised");
appendLog("INFO", `VIN: ${state.vin}`);
appendLog("INFO", "ECU: Trionic T8 / B284R");
appendLog("WARN", "J2534 interface not connected — stub mode active");
appendLog("DATA", "Platform: Win7-SAAB VM / Mongoose Pro GM II");

loadSessions();
init();
sniffer.render();
flashsafe.evaluate();
emulator.render("ENGINE");
cloud.render();
renderCalibrationCatalog();
renderPluginManager();
