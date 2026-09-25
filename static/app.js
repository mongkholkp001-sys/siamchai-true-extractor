// Customer Data Hub - Unified Extractor Frontend Script (Independent Crawlers)

let currentCids = [];
let currentResults = [];
let activeScreenTab = 'siamchai'; // 'siamchai' or 'true'
let activeTableTab = 'summary'; // 'summary', 'siamchai', 'true'
let isJobRunning = false;
let screenInterval = null;

// Auth Check
const authToken = localStorage.getItem('auth_token') || '';
const authUser = localStorage.getItem('auth_user') || 'admin';
let currentUserRole = 'member';

if (document.getElementById('user-display')) {
  document.getElementById('user-display').textContent = authUser;
}

async function initCurrentUser() {
  try {
    const res = await fetch('/api/auth/me', {
      headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {},
      credentials: 'same-origin'
    });
    if (res.ok) {
      const data = await res.json();
      currentUserRole = data.role || 'member';
      const uDisp = document.getElementById('user-display');
      const rBadge = document.getElementById('role-badge');
      if (uDisp) uDisp.textContent = data.name || data.username || authUser;
      if (rBadge) {
        rBadge.textContent = currentUserRole === 'admin' ? 'Admin' : 'พนักงาน';
        rBadge.className = currentUserRole === 'admin'
          ? 'text-[9px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
          : 'text-[9px] px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30';
      }

      // Show/Hide admin buttons
      const btnUsersMgmt = document.getElementById('btn-users-mgmt');
      const btnSettings = document.getElementById('btn-settings');
      if (btnUsersMgmt) {
        if (currentUserRole === 'admin') btnUsersMgmt.classList.remove('hidden');
        else btnUsersMgmt.classList.add('hidden');
      }
      if (btnSettings) {
        if (currentUserRole === 'admin') btnSettings.classList.remove('hidden');
        else btnSettings.classList.add('hidden');
      }
    }
  } catch (err) {
    console.error('Failed to init user info:', err);
  }
}
initCurrentUser();

// Elements - Inputs & Controls
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const cidBadge = document.getElementById('cid-count-badge');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');

// Combined Download Button
const btnDownloadCombined = document.getElementById('btn-download-combined');

// Siamchai Card Elements
const scStatusPill = document.getElementById('sc-status-pill');
const scProgressInfo = document.getElementById('sc-progress-info');
const scProgressPercent = document.getElementById('sc-progress-percent');
const scProgressBar = document.getElementById('sc-progress-bar');
const scCurrCid = document.getElementById('sc-curr-cid');
const scCountFound = document.getElementById('sc-count-found');
const btnDownloadSc = document.getElementById('btn-download-sc');

// TrueCorp Card Elements
const trStatusPill = document.getElementById('tr-status-pill');
const trProgressInfo = document.getElementById('tr-progress-info');
const trProgressPercent = document.getElementById('tr-progress-percent');
const trProgressBar = document.getElementById('tr-progress-bar');
const trCurrCid = document.getElementById('tr-curr-cid');
const trCountFound = document.getElementById('tr-count-found');
const btnDownloadTr = document.getElementById('btn-download-tr');

// Terminal Log Element
const terminalLogs = document.getElementById('terminal-logs');

// Table Elements
const tableHead = document.getElementById('table-head');
const tableBody = document.getElementById('table-body');
const tableCount = document.getElementById('table-count');
const tabTableSum = document.getElementById('tab-table-sum');
const tabTableSc = document.getElementById('tab-table-sc');
const tabTableTr = document.getElementById('tab-table-tr');

// Checkboxes
const checkSiamchai = document.getElementById('check-siamchai');
const checkTrue = document.getElementById('check-true');

// Direct Textarea
const manualCids = document.getElementById('manual-cids');
if (manualCids) {
  manualCids.addEventListener('input', () => {
    const lines = manualCids.value.split('\n').map(l => l.replace(/\D/g, '').trim()).filter(l => l.length >= 10);
    currentCids = lines;
    if (cidBadge) {
      cidBadge.textContent = `${lines.length} รายการ`;
      cidBadge.className = lines.length > 0
        ? 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30'
        : 'px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700';
    }
  });
}

// ------------------ File Upload & Parsing ------------------
if (dropZone) dropZone.addEventListener('click', () => fileInput.click());

if (dropZone) {
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-sky-500', 'bg-sky-500/10');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('border-sky-500', 'bg-sky-500/10');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-sky-500', 'bg-sky-500/10');
    if (e.dataTransfer.files.length) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });
}

if (fileInput) {
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleFileUpload(e.target.files[0]);
    }
  });
}

async function handleFileUpload(file) {
  const formData = new FormData();
  formData.append('file', file);

  const statusLabel = dropZone.querySelector('p');
  if (statusLabel) statusLabel.textContent = 'กำลังอ่านไฟล์: ' + file.name + '...';

  try {
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const res = await fetch('/api/upload_excel', {
      method: 'POST',
      headers: headers,
      credentials: 'same-origin',
      body: formData
    });
    const data = await res.json();
    if (res.ok && data.status === 'ok') {
      currentCids = data.cids;
      if (manualCids) manualCids.value = data.cids.join('\n');
      if (cidBadge) {
        cidBadge.textContent = `${data.count} รายการ`;
        cidBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30';
      }
      if (statusLabel) statusLabel.textContent = `✅ โหลดแล้ว: ${file.name} (${data.count} รายการ)`;
      addLog(`📁 โหลดไฟล์สำเร็จ: ${file.name} (${data.count} รายการ)`);
    } else {
      alert(data.detail || 'เกิดข้อผิดพลาดในการอ่านไฟล์');
    }
  } catch (err) {
    alert('เกิดข้อผิดพลาด: ' + err.message);
  }
}

// ------------------ Actions: Start / Stop ------------------
btnStart.addEventListener('click', async () => {
  // Auto-fallback: if currentCids is empty, check manual input textarea
  if (!currentCids.length && manualCids && manualCids.value.trim()) {
    const lines = manualCids.value.split('\n').map(l => l.replace(/\D/g, '').trim()).filter(l => l.length >= 10);
    if (lines.length) {
      currentCids = lines;
      cidBadge.textContent = `${lines.length} รายการ`;
      cidBadge.classList.remove('hidden');
      addLog(`✍️ นำเข้าเลขอัตโนมัติจากช่องพิมพ์: ${lines.length} รายการ`);
    }
  }

  if (!currentCids.length) {
    alert('กรุณาอัปโหลดไฟล์ Excel หรือพิมพ์เลขบัตรประชาชน (13 หลัก) ก่อนกดเริ่มค้นหา');
    return;
  }

  const useSc = checkSiamchai ? checkSiamchai.checked : true;
  const useTr = checkTrue ? checkTrue.checked : true;
  if (!useSc && !useTr) {
    alert('กรุณาเลือกช่องทางในการค้นหาอย่างน้อย 1 ระบบ (สยามชัย หรือ ทรู)');
    return;
  }

  let mode = 'both';
  if (useSc && !useTr) mode = 'siamchai';
  if (!useSc && useTr) mode = 'true';

  const isHeadless = true;

  btnStart.disabled = true;
  btnStart.innerHTML = `<span>⏳ กำลังส่งคำสั่งเริ่มค้นหา...</span>`;
  btnStop.disabled = false;
  btnDownloadCombined.classList.add('hidden');
  btnDownloadSc.classList.add('hidden');
  btnDownloadTr.classList.add('hidden');

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const res = await fetch('/api/start', {
      method: 'POST',
      headers: headers,
      credentials: 'same-origin',
      body: JSON.stringify({
        cids: currentCids,
        mode: mode,
        job_name: 'search_job',
        headless: isHeadless
      })
    });
    const data = await res.json();
    if (res.ok) {
      addLog(`🚀 คำสั่งเริ่มค้นหาสำเร็จ: ${currentCids.length} รายการ (โหมด: ${mode})`);
    } else {
      alert(data.detail || 'ไม่สามารถเริ่มการทำงานได้');
      btnStart.disabled = false;
      btnStart.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><span>เริ่มค้นหา (แยกค้นอิสระ ไม่ต้องรอกัน)</span>`;
      btnStop.disabled = true;
    }
  } catch (err) {
    alert('เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + err.message);
    btnStart.disabled = false;
    btnStart.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><span>เริ่มค้นหา (แยกค้นอิสระ ไม่ต้องรอกัน)</span>`;
    btnStop.disabled = true;
  }
});

btnStop.addEventListener('click', async () => {
  btnStop.disabled = true;
  try {
    await fetch('/api/stop', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
  } catch (err) {
    console.error(err);
  }
});

// ------------------ Table View Tabs ------------------
tabTableSum.addEventListener('click', () => switchTableTab('summary'));
tabTableSc.addEventListener('click', () => switchTableTab('siamchai'));
tabTableTr.addEventListener('click', () => switchTableTab('true'));

function switchTableTab(tab) {
  activeTableTab = tab;
  const tabs = [
    { el: tabTableSum, name: 'summary', activeBg: 'bg-sky-500 text-white' },
    { el: tabTableSc, name: 'siamchai', activeBg: 'bg-indigo-500 text-white' },
    { el: tabTableTr, name: 'true', activeBg: 'bg-rose-500 text-white' }
  ];

  tabs.forEach(t => {
    if (t.name === tab) {
      t.el.className = `px-3 py-1.5 rounded-lg text-xs font-semibold ${t.activeBg} transition-all`;
    } else {
      t.el.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition-all';
    }
  });

  renderTable();
}

function renderTable() {
  if (!currentResults.length) {
    tableBody.innerHTML = `<tr><td colspan="10" class="p-8 text-center text-slate-500">ยังไม่มีข้อมูล (เมื่อเริ่มการค้นหา ผลลัพธ์จะปรากฏที่นี่แบบ Real-time)</td></tr>`;
    return;
  }

  tableCount.textContent = `แสดงผล: ${currentResults.length} รายการ`;

  if (activeTableTab === 'summary') {
    tableHead.innerHTML = `
      <tr>
        <th class="py-2.5 px-3">#</th>
        <th class="py-2.5 px-3">เลขค้นหา</th>
        <th class="py-2.5 px-3">ชื่อ-นามสกุล</th>
        <th class="py-2.5 px-3">สถานะสยามชัย</th>
        <th class="py-2.5 px-3">เบอร์สยามชัย</th>
        <th class="py-2.5 px-3">เบอร์ทรู (Active)</th>
        <th class="py-2.5 px-3">ผู้ค้ำประกัน</th>
        <th class="py-2.5 px-3">ที่อยู่</th>
      </tr>
    `;

    tableBody.innerHTML = currentResults.map((r, i) => {
      const sc = r.siamchai || {};
      const tr = r.true || {};
      const name = sc['ชื่อ-นามสกุล'] || tr.name || '-';
      const scStatus = sc['สถานะ'] || '-';
      const scPhone = sc['เบอร์โทรผู้เช่าซื้อ'] || '-';
      const trActive = tr.active_count > 0 
        ? `<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">${tr.active_phones}</span>` 
        : '<span class="text-slate-500">-</span>';
      const coName = sc['ชื่อ-นามสกุลผู้ค้ำ'] ? `${sc['ชื่อ-นามสกุลผู้ค้ำ']} (${sc['เบอร์โทรผู้ค้ำ'] || '-'})` : '-';
      const addr = sc['ที่อยู่ปัจจุบันผู้เช่าซื้อ'] || '-';

      return `
        <tr class="hover:bg-slate-900/40">
          <td class="py-2 px-3 font-mono text-slate-500">${i + 1}</td>
          <td class="py-2 px-3 font-mono font-medium text-white">${r.cid}</td>
          <td class="py-2 px-3 font-medium text-slate-200">${name}</td>
          <td class="py-2 px-3"><span class="px-2 py-0.5 rounded text-[11px] ${scStatus.includes('สำเร็จ') || scStatus.includes('เช่าซื้อ') ? 'bg-indigo-500/15 text-indigo-300' : 'bg-slate-800 text-slate-400'}">${scStatus}</span></td>
          <td class="py-2 px-3 font-mono text-sky-300">${scPhone}</td>
          <td class="py-2 px-3">${trActive}</td>
          <td class="py-2 px-3 text-slate-300">${coName}</td>
          <td class="py-2 px-3 text-slate-400 truncate max-w-xs" title="${addr}">${addr}</td>
        </tr>
      `;
    }).join('');

  } else if (activeTableTab === 'siamchai') {
    tableHead.innerHTML = `
      <tr>
        <th class="py-2.5 px-3">#</th>
        <th class="py-2.5 px-3">เลขค้นหา</th>
        <th class="py-2.5 px-3">ชื่อ-นามสกุล</th>
        <th class="py-2.5 px-3">สถานะ</th>
        <th class="py-2.5 px-3">เบอร์ผู้เช่าซื้อ</th>
        <th class="py-2.5 px-3">ที่ทำงาน</th>
        <th class="py-2.5 px-3">ชื่อผู้ค้ำ</th>
        <th class="py-2.5 px-3">เบอร์ผู้ค้ำ</th>
      </tr>
    `;

    tableBody.innerHTML = currentResults.map((r, i) => {
      const sc = r.siamchai || {};
      return `
        <tr class="hover:bg-slate-900/40">
          <td class="py-2 px-3 font-mono text-slate-500">${i + 1}</td>
          <td class="py-2 px-3 font-mono font-medium text-white">${r.cid}</td>
          <td class="py-2 px-3 text-slate-200">${sc['ชื่อ-นามสกุล'] || '-'}</td>
          <td class="py-2 px-3">${sc['สถานะ'] || '-'}</td>
          <td class="py-2 px-3 font-mono text-indigo-300">${sc['เบอร์โทรผู้เช่าซื้อ'] || '-'}</td>
          <td class="py-2 px-3 text-slate-300 truncate max-w-xs">${sc['ที่อยู่ที่ทำงานผู้เช่าซื้อ'] || '-'}</td>
          <td class="py-2 px-3 text-slate-300">${sc['ชื่อ-นามสกุลผู้ค้ำ'] || '-'}</td>
          <td class="py-2 px-3 font-mono text-indigo-300">${sc['เบอร์โทรผู้ค้ำ'] || '-'}</td>
        </tr>
      `;
    }).join('');

  } else if (activeTableTab === 'true') {
    tableHead.innerHTML = `
      <tr>
        <th class="py-2.5 px-3">#</th>
        <th class="py-2.5 px-3">เลขค้นหา</th>
        <th class="py-2.5 px-3">สถานะทรู</th>
        <th class="py-2.5 px-3">จำนวนเบอร์ Active</th>
        <th class="py-2.5 px-3">รายการเบอร์ Active</th>
        <th class="py-2.5 px-3">เบอร์ทั้งหมดที่พบ</th>
      </tr>
    `;

    tableBody.innerHTML = currentResults.map((r, i) => {
      const tr = r.true || {};
      return `
        <tr class="hover:bg-slate-900/40">
          <td class="py-2 px-3 font-mono text-slate-500">${i + 1}</td>
          <td class="py-2 px-3 font-mono font-medium text-white">${r.cid}</td>
          <td class="py-2 px-3">${tr.status || '-'}</td>
          <td class="py-2 px-3 font-mono font-bold text-rose-400">${tr.active_count || 0}</td>
          <td class="py-2 px-3 font-mono text-emerald-400">${tr.active_phones || '-'}</td>
          <td class="py-2 px-3 font-mono text-slate-400 truncate max-w-xs">${tr.all_phones || '-'}</td>
        </tr>
      `;
    }).join('');
  }
}

// ------------------ Logs Terminal ------------------
function addLog(msg) {
  const div = document.createElement('div');
  div.textContent = msg;
  if (msg.includes('🟣 [สยามชัย]')) div.className = 'text-indigo-300';
  else if (msg.includes('🔴 [ทรู]')) div.className = 'text-rose-300';
  else if (msg.includes('สำเร็จ') || msg.includes('🎉') || msg.includes('💾')) div.className = 'text-emerald-400 font-medium';
  else if (msg.includes('❌') || msg.includes('ข้อผิดพลาด')) div.className = 'text-rose-400';
  else if (msg.includes('🚀') || msg.includes('⚡')) div.className = 'text-sky-300 font-semibold';
  terminalLogs.appendChild(div);
  terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

document.getElementById('btn-clear-logs').addEventListener('click', () => {
  terminalLogs.innerHTML = '<div class="text-slate-500">// ล้างข้อความเรียบร้อย</div>';
});

// ------------------ WebSocket Status Stream ------------------
let ws = null;
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/status?token=${encodeURIComponent(authToken)}`;
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    document.getElementById('conn-badge').className = 'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
    document.getElementById('conn-text').textContent = 'เชื่อมต่อแล้ว';
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateUI(data);
    } catch (e) {
      console.error("WS error:", e);
    }
  };

  ws.onclose = () => {
    document.getElementById('conn-badge').className = 'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20';
    document.getElementById('conn-text').textContent = 'กำลังเชื่อมต่อใหม่...';
    setTimeout(connectWebSocket, 2000);
  };
}

// ------------------ Dual HTTP Polling Fallback (100% Guaranteed Update) ------------------
let isPolling = false;
async function pollStatusFallback() {
  if (isPolling) return;
  isPolling = true;
  try {
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    const res = await fetch('/api/status', {
      headers: headers,
      credentials: 'same-origin'
    });
    if (res.ok) {
      const data = await res.json();
      updateUI(data);
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        document.getElementById('conn-badge').className = 'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        document.getElementById('conn-text').textContent = 'เชื่อมต่อแล้ว (Live)';
      }
    }
  } catch (e) {
    // Network hiccup
  } finally {
    isPolling = false;
  }
}
setInterval(pollStatusFallback, 1200);

let lastRenderedLogCount = 0;
function syncServerLogs(logs) {
  if (!logs || !logs.length) return;
  if (logs.length === lastRenderedLogCount) return;
  lastRenderedLogCount = logs.length;

  terminalLogs.innerHTML = '';
  logs.forEach(msg => {
    const div = document.createElement('div');
    div.textContent = msg;
    if (msg.includes('🟣 [สยามชัย]')) div.className = 'text-indigo-300';
    else if (msg.includes('🔴 [ทรู]')) div.className = 'text-rose-300';
    else if (msg.includes('สำเร็จ') || msg.includes('🎉') || msg.includes('💾')) div.className = 'text-emerald-400 font-medium';
    else if (msg.includes('❌') || msg.includes('ข้อผิดพลาด')) div.className = 'text-rose-400 font-semibold';
    else if (msg.includes('🚀') || msg.includes('⚡')) div.className = 'text-sky-300 font-semibold';
    terminalLogs.appendChild(div);
  });
  terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

function updateStatusBadge(el, status) {
  if (!el) return;
  if (status === 'running') {
    el.textContent = 'กำลังค้นหา (RUNNING)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-sky-500/15 text-sky-400 border border-sky-500/30 animate-pulse';
  } else if (status === 'starting') {
    el.textContent = 'กำลังเปิดระบบ... (STARTING)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30 animate-pulse';
  } else if (status === 'queued') {
    el.textContent = 'ในคิว (QUEUED)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30';
  } else if (status === 'done') {
    el.textContent = 'เสร็จสิ้น (DONE)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
  } else if (status === 'error') {
    el.textContent = 'ข้อผิดพลาด (ERROR)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30';
  } else if (status === 'stopped') {
    el.textContent = 'หยุดทำงาน';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30';
  } else {
    el.textContent = 'ว่าง (IDLE)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700';
  }
}

function updateUI(data) {
  // Handle Queue Banner
  const queueBanner = document.getElementById('queue-banner');
  const queuePosBadge = document.getElementById('queue-position-badge');
  if (data.status === 'queued') {
    if (queueBanner) {
      queueBanner.classList.remove('hidden');
      if (queuePosBadge) queuePosBadge.textContent = `ลำดับที่ ${data.queue_position || 1}`;
    }
    btnStart.disabled = true;
    btnStart.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span><span>อยู่ในคิวรอประมวลผล (ลำดับที่ ${data.queue_position || 1})...</span>`;
    btnStop.disabled = false;
  } else {
    if (queueBanner) queueBanner.classList.add('hidden');
  }

  const isBusy = (
    data.status === 'running' ||
    data.status === 'starting' ||
    data.status === 'queued' ||
    data.sc_status === 'running' ||
    data.sc_status === 'starting' ||
    data.tr_status === 'running' ||
    data.tr_status === 'starting'
  );
  isJobRunning = isBusy;

  if (isBusy && data.status !== 'queued') {
    btnStart.disabled = true;
    btnStart.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span><span>กำลังค้นหาข้อมูล (แยกค้นอิสระ)...</span>`;
    btnStop.disabled = false;
  } else if (!isBusy) {
    btnStart.disabled = false;
    btnStart.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><span>เริ่มค้นหาข้อมูลทันที (แยกค้นอิสระ)</span>`;
    btnStop.disabled = true;
  }

  // 1. Siamchai Card Update
  updateStatusBadge(scStatusPill, data.sc_status);
  scProgressInfo.textContent = `${data.sc_current_index || 0} / ${data.total || 0} รายการ`;
  scProgressPercent.textContent = `${data.sc_percent || 0}%`;
  scProgressBar.style.width = `${data.sc_percent || 0}%`;
  scCurrCid.textContent = `กำลังค้นหา: ${data.sc_current_cid || '-'}`;
  const scFound = data.sc_found_count !== undefined ? data.sc_found_count : (data.sc_count || 0);
  scCountFound.textContent = `พบข้อมูลสัญญา: ${scFound} รายการ (ค้นแล้ว ${data.sc_count || 0})`;

  const jobIdParam = data.job_id ? `&job_id=${encodeURIComponent(data.job_id)}` : '';

  if (data.has_sc_excel) {
    btnDownloadSc.classList.remove('hidden');
    btnDownloadSc.href = `/api/download/siamchai?token=${authToken}${jobIdParam}`;
  } else {
    btnDownloadSc.classList.add('hidden');
  }

  // 2. TrueCorp Card Update
  updateStatusBadge(trStatusPill, data.tr_status);
  trProgressInfo.textContent = `${data.tr_current_index || 0} / ${data.total || 0} รายการ`;
  trProgressPercent.textContent = `${data.tr_percent || 0}%`;
  trProgressBar.style.width = `${data.tr_percent || 0}%`;
  trCurrCid.textContent = `กำลังค้นหา: ${data.tr_current_cid || '-'}`;
  const trFound = data.tr_found_count !== undefined ? data.tr_found_count : (data.tr_count || 0);
  trCountFound.textContent = `พบเบอร์ Active: ${trFound} รายการ (ค้นแล้ว ${data.tr_count || 0})`;

  if (data.has_tr_excel) {
    btnDownloadTr.classList.remove('hidden');
    btnDownloadTr.href = `/api/download/true?token=${authToken}${jobIdParam}`;
  } else {
    btnDownloadTr.classList.add('hidden');
  }

  // 3. Combined Download Button Update
  if (data.has_combined_excel || data.has_excel) {
    btnDownloadCombined.classList.remove('hidden');
    btnDownloadCombined.href = `/api/download/combined?token=${authToken}${jobIdParam}`;
  } else {
    btnDownloadCombined.classList.add('hidden');
  }

  // 4. Results Table Update
  if (data.results && data.results.length !== currentResults.length) {
    currentResults = data.results;
    renderTable();
  }

  // 5. System Logs Real-time Sync
  if (data.logs && data.logs.length) {
    syncServerLogs(data.logs);
  }
}

connectWebSocket();

// Cancel Queue button
const btnCancelQueue = document.getElementById('btn-cancel-queue');
if (btnCancelQueue) {
  btnCancelQueue.addEventListener('click', async () => {
    if (confirm('คุณต้องการยกเลิกงานค้นหานี้ออกจากคิวใช่หรือไม่?')) {
      try {
        await fetch('/api/stop', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
      } catch (err) {
        console.error(err);
      }
    }
  });
}

// ------------------ Settings Modal ------------------
const modalSettings = document.getElementById('modal-settings');
const btnSettings = document.getElementById('btn-settings');
const btnCloseSettings = document.getElementById('btn-close-settings');
const btnCancelSettings = document.getElementById('btn-cancel-settings');
const btnSaveSettings = document.getElementById('btn-save-settings');

if (btnSettings) {
  btnSettings.addEventListener('click', async () => {
    modalSettings.classList.remove('hidden');
    try {
      const res = await fetch('/api/config', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const cfg = await res.json();
      document.getElementById('cfg-web-user').value = cfg.web_username || '';
      document.getElementById('cfg-sc-user').value = cfg.siamchai_username || '';
      document.getElementById('cfg-tr-user').value = cfg.true_username || '';
    } catch (err) {
      console.error(err);
    }
  });
}

const closeModal = () => modalSettings.classList.add('hidden');
if (btnCloseSettings) btnCloseSettings.addEventListener('click', closeModal);
if (btnCancelSettings) btnCancelSettings.addEventListener('click', closeModal);

if (btnSaveSettings) {
  btnSaveSettings.addEventListener('click', async () => {
    const body = {
      web_username: document.getElementById('cfg-web-user').value.trim(),
      web_password: document.getElementById('cfg-web-pass').value.trim() || undefined,
      siamchai_username: document.getElementById('cfg-sc-user').value.trim(),
      siamchai_password: document.getElementById('cfg-sc-pass').value.trim() || undefined,
      true_username: document.getElementById('cfg-tr-user').value.trim(),
      true_password: document.getElementById('cfg-tr-pass').value.trim() || undefined,
    };

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(body)
      });
      if (res.ok) {
        alert('บันทึกการตั้งค่าเรียบร้อยแล้ว');
        closeModal();
      } else {
        alert('ไม่สามารถบันทึกการตั้งค่าได้');
      }
    } catch (err) {
      alert('เกิดข้อผิดพลาด: ' + err.message);
    }
  });
}

// ------------------ User Management Modal (Admin) ------------------
const modalUsers = document.getElementById('modal-users');
const btnUsersMgmt = document.getElementById('btn-users-mgmt');
const btnCloseUsers = document.getElementById('btn-close-users');
const btnDoneUsers = document.getElementById('btn-done-users');
const btnRefreshUsers = document.getElementById('btn-refresh-users');
const btnCreateUser = document.getElementById('btn-create-user');
const usersTableBody = document.getElementById('users-table-body');

async function loadUsersList() {
  if (!usersTableBody) return;
  usersTableBody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-slate-500">กำลังโหลดข้อมูลผู้ใช้...</td></tr>`;
  try {
    const res = await fetch('/api/users', {
      headers: { 'Authorization': `Bearer ${authToken}` },
      credentials: 'same-origin'
    });
    if (!res.ok) {
      const err = await res.json();
      usersTableBody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-rose-400 font-semibold">${err.detail || 'ไม่สามารถโหลดรายชื่อผู้ใช้ได้'}</td></tr>`;
      return;
    }
    const data = await res.json();
    const users = data.users || [];
    if (!users.length) {
      usersTableBody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-slate-500">ไม่พบข้อมูลผู้ใช้</td></tr>`;
      return;
    }
    usersTableBody.innerHTML = '';
    users.forEach(u => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-900/50 transition-colors';
      const isCurrent = u.username.toLowerCase() === authUser.toLowerCase();
      const roleBadge = u.role === 'admin'
        ? `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Admin</span>`
        : `<span class="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700">Member</span>`;

      tr.innerHTML = `
        <td class="p-2.5 font-mono text-white font-medium">${u.username}</td>
        <td class="p-2.5 text-slate-300">${u.name || '-'}</td>
        <td class="p-2.5">${roleBadge}</td>
        <td class="p-2.5 text-right space-x-1.5">
          <button class="btn-user-reset px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700" data-user="${u.username}">🔑 รีเซ็ตรหัส</button>
          ${!isCurrent ? `<button class="btn-user-del px-2.5 py-1 rounded bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 text-xs border border-rose-500/30" data-user="${u.username}">🗑️ ลบ</button>` : `<span class="text-[11px] text-slate-500 italic pl-1">(บัญชีนี้)</span>`}
        </td>
      `;
      usersTableBody.appendChild(tr);
    });

    document.querySelectorAll('.btn-user-reset').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const u = e.currentTarget.getAttribute('data-user');
        const newPass = prompt(`ระบุรหัสผ่านใหม่สำหรับผู้ใช้ "${u}":`);
        if (!newPass || !newPass.trim()) return;
        try {
          const r = await fetch(`/api/users/${encodeURIComponent(u)}/password`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ password: newPass.trim() })
          });
          const resData = await r.json();
          if (r.ok) {
            alert(`✅ เปลี่ยนรหัสผ่านสำหรับ ${u} เรียบร้อยแล้ว`);
          } else {
            alert(`❌ เกิดข้อผิดพลาด: ${resData.detail || 'ไม่สามารถเปลี่ยนรหัสได้'}`);
          }
        } catch (err) {
          alert('เกิดข้อผิดพลาด: ' + err.message);
        }
      });
    });

    document.querySelectorAll('.btn-user-del').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const u = e.currentTarget.getAttribute('data-user');
        if (!confirm(`ต้องการลบบัญชีผู้ใช้ "${u}" ใช่หรือไม่?`)) return;
        try {
          const r = await fetch(`/api/users/${encodeURIComponent(u)}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
          });
          const resData = await r.json();
          if (r.ok) {
            alert(`✅ ลบผู้ใช้ ${u} เรียบร้อย`);
            loadUsersList();
          } else {
            alert(`❌ เกิดข้อผิดพลาด: ${resData.detail || 'ไม่สามารถลบได้'}`);
          }
        } catch (err) {
          alert('เกิดข้อผิดพลาด: ' + err.message);
        }
      });
    });

  } catch (err) {
    usersTableBody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-rose-400">เกิดข้อผิดพลาด: ${err.message}</td></tr>`;
  }
}

if (btnUsersMgmt) {
  btnUsersMgmt.addEventListener('click', () => {
    if (modalUsers) {
      modalUsers.classList.remove('hidden');
      loadUsersList();
    }
  });
}

if (btnCloseUsers) btnCloseUsers.addEventListener('click', () => modalUsers.classList.add('hidden'));
if (btnDoneUsers) btnDoneUsers.addEventListener('click', () => modalUsers.classList.add('hidden'));
if (btnRefreshUsers) btnRefreshUsers.addEventListener('click', loadUsersList);

if (btnCreateUser) {
  btnCreateUser.addEventListener('click', async () => {
    const uname = document.getElementById('new-user-name').value.trim();
    const upass = document.getElementById('new-user-pass').value.trim();
    const ufullname = document.getElementById('new-user-fullname').value.trim();
    const urole = document.getElementById('new-user-role').value;

    if (!uname || !upass) {
      alert('กรุณากรอก Username และ Password');
      return;
    }

    try {
      const res = await fetch('/api/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          username: uname,
          password: upass,
          name: ufullname,
          role: urole
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(`✅ สร้างผู้ใช้งาน "${uname}" เรียบร้อยแล้ว`);
        document.getElementById('new-user-name').value = '';
        document.getElementById('new-user-pass').value = '';
        document.getElementById('new-user-fullname').value = '';
        loadUsersList();
      } else {
        alert(`❌ ไม่สามารถสร้างผู้ใช้ได้: ${data.detail || 'เกิดข้อผิดพลาด'}`);
      }
    } catch (err) {
      alert('เกิดข้อผิดพลาด: ' + err.message);
    }
  });
}

// ------------------ Job History Modal ------------------
const modalHistory = document.getElementById('modal-history');
const btnJobHistory = document.getElementById('btn-job-history');
const btnCloseHistory = document.getElementById('btn-close-history');
const btnDoneHistory = document.getElementById('btn-done-history');
const btnRefreshHistory = document.getElementById('btn-refresh-history');
const historyTableBody = document.getElementById('history-table-body');

async function loadHistoryList() {
  if (!historyTableBody) return;
  historyTableBody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-500">กำลังโหลดประวัติงาน...</td></tr>`;
  try {
    const res = await fetch('/api/jobs', {
      headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {},
      credentials: 'same-origin'
    });
    if (!res.ok) {
      historyTableBody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-rose-400">ไม่สามารถโหลดประวัติงานได้</td></tr>`;
      return;
    }
    const data = await res.json();
    const jobs = data.jobs || [];
    if (!jobs.length) {
      historyTableBody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-500">ยังไม่มีประวัติงานค้นหา</td></tr>`;
      return;
    }
    historyTableBody.innerHTML = '';
    jobs.forEach(j => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-900/50 transition-colors';

      let statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-400">ว่าง (IDLE)</span>';
      if (j.status === 'done') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">เสร็จสิ้น</span>';
      else if (j.status === 'running') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500/20 text-sky-400 border border-sky-500/30 animate-pulse">กำลังค้นหา</span>';
      else if (j.status === 'queued') statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">ในคิว (${j.queue_position})</span>`;
      else if (j.status === 'stopped') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] bg-amber-500/20 text-amber-400">หยุดแล้ว</span>';
      else if (j.status === 'error') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">ข้อผิดพลาด</span>';

      let modeLabel = 'สยามชัย & ทรู';
      if (j.mode === 'siamchai') modeLabel = 'สยามชัย';
      else if (j.mode === 'true') modeLabel = 'ทรู';

      let dlBtns = [];
      if (j.has_combined_excel) {
        dlBtns.push(`<a href="/api/download/combined?job_id=${encodeURIComponent(j.job_id)}&token=${authToken}" target="_blank" class="px-2.5 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-xs font-semibold border border-emerald-500/40">📊 Excel รวม</a>`);
      }
      if (j.has_sc_excel) {
        dlBtns.push(`<a href="/api/download/siamchai?job_id=${encodeURIComponent(j.job_id)}&token=${authToken}" target="_blank" class="px-2 py-1 rounded bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs border border-indigo-500/40">🟣 สยามชัย</a>`);
      }
      if (j.has_tr_excel) {
        dlBtns.push(`<a href="/api/download/true?job_id=${encodeURIComponent(j.job_id)}&token=${authToken}" target="_blank" class="px-2 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs border border-rose-500/40">🔴 ทรู</a>`);
      }
      if (!dlBtns.length) {
        dlBtns.push(`<span class="text-slate-600 text-xs">-</span>`);
      }

      tr.innerHTML = `
        <td class="p-2.5 text-slate-300 font-mono text-[11px]">${j.created_time_str || '-'}</td>
        <td class="p-2.5 text-white font-medium">${j.user}</td>
        <td class="p-2.5 font-mono text-slate-300">${j.total || 0} รายการ</td>
        <td class="p-2.5 text-slate-300">${modeLabel}</td>
        <td class="p-2.5">${statusBadge}</td>
        <td class="p-2.5 text-center space-x-1.5">${dlBtns.join('')}</td>
      `;
      historyTableBody.appendChild(tr);
    });
  } catch (err) {
    historyTableBody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-rose-400">เกิดข้อผิดพลาด: ${err.message}</td></tr>`;
  }
}

if (btnJobHistory) {
  btnJobHistory.addEventListener('click', () => {
    if (modalHistory) {
      modalHistory.classList.remove('hidden');
      loadHistoryList();
    }
  });
}

if (btnCloseHistory) btnCloseHistory.addEventListener('click', () => modalHistory.classList.add('hidden'));
if (btnDoneHistory) btnDoneHistory.addEventListener('click', () => modalHistory.classList.add('hidden'));
if (btnRefreshHistory) btnRefreshHistory.addEventListener('click', loadHistoryList);

// ------------------ Logout ------------------
document.getElementById('btn-logout').addEventListener('click', async () => {
  if (confirm('คุณต้องการออกจากระบบใช่หรือไม่?')) {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {}
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    window.location.href = '/login';
  }
});
