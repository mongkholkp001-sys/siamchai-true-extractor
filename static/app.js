// Customer Data Hub - Unified Extractor Frontend Script

let currentCids = [];
let currentResults = [];
let activeScreenTab = 'siamchai'; // 'siamchai' or 'true'
let activeTableTab = 'summary'; // 'summary', 'siamchai', 'true'
let isJobRunning = false;
let screenInterval = null;

// Auth Check
const authToken = localStorage.getItem('auth_token');
const authUser = localStorage.getItem('auth_user') || 'admin';
if (document.getElementById('user-display')) {
  document.getElementById('user-display').textContent = authUser;
}

// Elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const cidBadge = document.getElementById('cid-count-badge');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const btnDownload = document.getElementById('btn-download');
const progressBar = document.getElementById('progress-bar');
const progressInfo = document.getElementById('progress-info');
const statusPill = document.getElementById('status-pill');
const currCidDisplay = document.getElementById('curr-cid-display');
const timerDisplay = document.getElementById('timer-display');
const liveImg = document.getElementById('live-img');
const liveOverlay = document.getElementById('live-overlay');
const terminalLogs = document.getElementById('terminal-logs');
const tableHead = document.getElementById('table-head');
const tableBody = document.getElementById('table-body');
const tableCount = document.getElementById('table-count');

// Dual Screen Tabs
const tabScreenSc = document.getElementById('tab-screen-sc');
const tabScreenTr = document.getElementById('tab-screen-tr');

// Table Tabs
const tabTableSum = document.getElementById('tab-table-sum');
const tabTableSc = document.getElementById('tab-table-sc');
const tabTableTr = document.getElementById('tab-table-tr');

// Checkboxes
const checkSiamchai = document.getElementById('check-siamchai');
const checkTrue = document.getElementById('check-true');
const checkHeadless = document.getElementById('check-headless');

// ------------------ File Upload & Parsing ------------------
dropZone.addEventListener('click', () => fileInput.click());

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

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length) {
    handleFileUpload(e.target.files[0]);
  }
});

async function handleFileUpload(file) {
  const formData = new FormData();
  formData.append('file', file);

  dropZone.querySelector('p').textContent = 'กำลังอ่านไฟล์: ' + file.name + '...';

  try {
    const res = await fetch('/api/upload_excel', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` },
      body: formData
    });
    const data = await res.json();
    if (res.ok && data.status === 'ok') {
      currentCids = data.cids;
      cidBadge.textContent = `${data.count} รายการ`;
      cidBadge.classList.remove('hidden');
      dropZone.querySelector('p').textContent = `✅ โหลดแล้ว: ${file.name} (${data.count} รายการ)`;
      addLog(`📁 โหลดไฟล์สำเร็จ: ${file.name} (${data.count} รายการ)`);
    } else {
      alert(data.detail || 'เกิดข้อผิดพลาดในการอ่านไฟล์');
    }
  } catch (err) {
    alert('เกิดข้อผิดพลาด: ' + err.message);
  }
}

// Manual Input
const toggleManual = document.getElementById('toggle-manual');
const manualBox = document.getElementById('manual-box');
const manualCids = document.getElementById('manual-cids');
const btnApplyManual = document.getElementById('btn-apply-manual');

toggleManual.addEventListener('click', () => manualBox.classList.toggle('hidden'));
btnApplyManual.addEventListener('click', () => {
  const lines = manualCids.value.split('\n').map(l => l.replace(/\D/g, '').trim()).filter(l => l.length >= 10);
  if (lines.length) {
    currentCids = lines;
    cidBadge.textContent = `${lines.length} รายการ`;
    cidBadge.classList.remove('hidden');
    dropZone.querySelector('p').textContent = `✅ ระบุเลขด้วยตนเอง: ${lines.length} รายการ`;
    addLog(`✍️ นำเข้าเลขบัตรด้วยตนเอง: ${lines.length} รายการ`);
    manualBox.classList.add('hidden');
  } else {
    alert('กรุณาระบุเลขบัตรประชาชนอย่างน้อย 1 รายการ');
  }
});

// ------------------ Actions: Start / Stop ------------------
btnStart.addEventListener('click', async () => {
  if (!currentCids.length) {
    alert('กรุณาอัปโหลดไฟล์ Excel หรือระบุเลขค้นหาก่อน');
    return;
  }

  const useSc = checkSiamchai.checked;
  const useTr = checkTrue.checked;
  if (!useSc && !useTr) {
    alert('กรุณาเลือกช่องทางในการค้นหาอย่างน้อย 1 ระบบ (สยามชัย หรือ ทรู)');
    return;
  }

  let mode = 'both';
  if (useSc && !useTr) mode = 'siamchai';
  if (!useSc && useTr) mode = 'true';

  btnStart.disabled = true;
  btnStop.disabled = false;
  btnDownload.classList.add('hidden');

  try {
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        cids: currentCids,
        mode: mode,
        job_name: 'unified_search',
        headless: checkHeadless.checked
      })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || 'ไม่สามารถเริ่มการทำงานได้');
      btnStart.disabled = false;
      btnStop.disabled = true;
    }
  } catch (err) {
    alert('เกิดข้อผิดพลาด: ' + err.message);
    btnStart.disabled = false;
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

// ------------------ Dual Screen Switcher ------------------
tabScreenSc.addEventListener('click', () => {
  activeScreenTab = 'siamchai';
  tabScreenSc.className = 'px-3 py-1 rounded-lg text-xs font-semibold bg-indigo-500 text-white shadow transition-all';
  tabScreenTr.className = 'px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition-all';
  refreshLiveScreenshot();
});

tabScreenTr.addEventListener('click', () => {
  activeScreenTab = 'true';
  tabScreenTr.className = 'px-3 py-1 rounded-lg text-xs font-semibold bg-rose-500 text-white shadow transition-all';
  tabScreenSc.className = 'px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition-all';
  refreshLiveScreenshot();
});

function refreshLiveScreenshot() {
  if (!isJobRunning) return;
  const endpoint = activeScreenTab === 'siamchai' ? '/api/screenshot/siamchai' : '/api/screenshot/true';
  liveImg.src = `${endpoint}?t=${Date.now()}`;
}

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
      const trActive = tr.active_count > 0 ? `<span class="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">${tr.active_phones}</span>` : '<span class="text-slate-500">-</span>';
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
  if (msg.includes('สำเร็จ')) div.className = 'text-emerald-400';
  else if (msg.includes('❌') || msg.includes('ข้อผิดพลาด')) div.className = 'text-rose-400';
  else if (msg.includes('🚀') || msg.includes('✨')) div.className = 'text-sky-300 font-semibold';
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
  ws = new WebSocket(`${protocol}//${window.location.host}/ws/status`);

  ws.onopen = () => {
    document.getElementById('conn-badge').className = 'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
    document.getElementById('conn-text').textContent = 'เชื่อมต่อเซิร์ฟเวอร์แล้ว';
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateUI(data);
  };

  ws.onclose = () => {
    document.getElementById('conn-badge').className = 'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20';
    document.getElementById('conn-text').textContent = 'กำลังเชื่อมต่อใหม่...';
    setTimeout(connectWebSocket, 2000);
  };
}

function updateUI(data) {
  isJobRunning = data.status === 'running';

  // Status pill
  if (data.status === 'running') {
    statusPill.textContent = 'สถานะ: กำลังค้นหาข้อมูล (RUNNING)';
    statusPill.className = 'px-2.5 py-1 rounded-full font-medium bg-sky-500/10 text-sky-400 border border-sky-500/30 animate-pulse';
    btnStart.disabled = true;
    btnStop.disabled = false;
    liveOverlay.classList.add('hidden');
    if (!screenInterval) {
      screenInterval = setInterval(refreshLiveScreenshot, 1000);
    }
  } else {
    statusPill.textContent = data.status === 'done' ? 'สถานะ: เสร็จสิ้น (DONE)' : (data.status === 'error' ? 'สถานะ: เกิดข้อผิดพลาด' : 'สถานะ: ว่าง (IDLE)');
    statusPill.className = data.status === 'done' ? 'px-2.5 py-1 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'px-2.5 py-1 rounded-full font-medium bg-slate-800 text-slate-400 border border-slate-700';
    btnStart.disabled = false;
    btnStop.disabled = true;
    liveOverlay.classList.remove('hidden');
    if (screenInterval) {
      clearInterval(screenInterval);
      screenInterval = null;
    }
  }

  // Progress
  progressBar.style.width = `${data.percent || 0}%`;
  progressInfo.textContent = `${data.current_index || 0} / ${data.total || 0} รายการ (${data.percent || 0}%)`;
  currCidDisplay.textContent = `กำลังทำ: ${data.current_cid || '-'}`;

  const secs = data.elapsed_seconds || 0;
  const m = String(Math.floor(secs / 60)).padStart(2, '0');
  const s = String(secs % 60).padStart(2, '0');
  timerDisplay.textContent = `⏱️ เวลา: ${m}:${s}`;

  // Results
  if (data.recent_results && data.recent_results.length > currentResults.length) {
    currentResults = data.recent_results;
    renderTable();
  }

  // Download button
  if (data.has_excel) {
    btnDownload.classList.remove('hidden');
    btnDownload.href = `/api/download?token=${authToken}`;
  }
}

connectWebSocket();

// ------------------ Settings Modal ------------------
const modalSettings = document.getElementById('modal-settings');
const btnSettings = document.getElementById('btn-settings');
const btnCloseSettings = document.getElementById('btn-close-settings');
const btnCancelSettings = document.getElementById('btn-cancel-settings');
const btnSaveSettings = document.getElementById('btn-save-settings');

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

const closeModal = () => modalSettings.classList.add('hidden');
btnCloseSettings.addEventListener('click', closeModal);
btnCancelSettings.addEventListener('click', closeModal);

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
