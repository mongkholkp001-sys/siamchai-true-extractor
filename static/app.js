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
  const btnUsersMgmt = document.getElementById('btn-users-mgmt');
  const btnSettings = document.getElementById('btn-settings');
  const btnOpenLicGen = document.getElementById('btn-open-license-gen');

  // Immediately show admin buttons if logged-in user is admin
  if (authUser.toLowerCase() === 'admin') {
    if (btnUsersMgmt) btnUsersMgmt.classList.remove('hidden');
    if (btnSettings) btnSettings.classList.remove('hidden');
    if (btnOpenLicGen) btnOpenLicGen.classList.remove('hidden');
  }

  try {
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    const res = await fetch('/api/auth/me', {
      headers: headers,
      credentials: 'same-origin'
    });
    if (res.ok) {
      const data = await res.json();
      currentUserRole = data.role || (authUser.toLowerCase() === 'admin' ? 'admin' : 'member');
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
      const btnResetAll = document.getElementById('btn-admin-reset-all');
      if (currentUserRole === 'admin') {
        if (btnUsersMgmt) btnUsersMgmt.classList.remove('hidden');
        if (btnSettings) btnSettings.classList.remove('hidden');
        if (btnResetAll) btnResetAll.classList.remove('hidden');
        if (btnOpenLicGen) btnOpenLicGen.classList.remove('hidden');
      } else {
        if (btnUsersMgmt) btnUsersMgmt.classList.add('hidden');
        if (btnSettings) btnSettings.classList.add('hidden');
        if (btnResetAll) btnResetAll.classList.add('hidden');
        if (btnOpenLicGen) btnOpenLicGen.classList.add('hidden');
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
  btnStop.innerHTML = `<span class="inline-block animate-spin mr-1">🛑</span><span>กำลังสั่งหยุดการทำงานทันที...</span>`;
  updateStatusBadge(document.getElementById('badgeJobStatus'), 'stopped');
  try {
    const res = await fetch('/api/stop', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    if (res.ok) {
      btnStop.innerHTML = `<svg class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><span>สั่งหยุดสำเร็จแล้ว</span>`;
      syncServerLogs(['🛑 ส่งคำสั่งหยุดการทำงานเรียบร้อยแล้ว กำลังเซฟผลลัพธ์ล่าสุด...']);
      // Immediately unlock UI locally and poll fresh status
      updateUI({ status: 'stopped', sc_status: 'stopped', tr_status: 'stopped' });
      btnStart.disabled = false;
      btnStop.disabled = true;
      try {
        const sRes = await fetch('/api/status', { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (sRes.ok) updateUI(await sRes.json());
      } catch (_) {}
    }
  } catch (err) {
    console.error(err);
  }
});

const btnForceReset = document.getElementById('btn-force-reset');
if (btnForceReset) {
  btnForceReset.addEventListener('click', async () => {
    btnForceReset.disabled = true;
    btnForceReset.innerHTML = `<span class="inline-block animate-spin mr-1">🔄</span><span>กำลังรีเซ็ต...</span>`;
    try {
      await fetch('/api/force-reset', { method: 'POST' });
      updateUI({ status: 'stopped', sc_status: 'stopped', tr_status: 'stopped', sc_current_index: 0, tr_current_index: 0 });
      btnStart.disabled = false;
      btnStop.disabled = true;
      syncServerLogs(['🔄 สั่งบังคับรีเซ็ตระบบและปลดล็อคหน้าจอเรียบร้อยแล้ว! พร้อมค้นหาใหม่ได้ทันที']);
      try {
        const sRes = await fetch('/api/status', { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (sRes.ok) updateUI(await sRes.json());
      } catch (_) {}
    } catch (e) {
      console.error(e);
    } finally {
      btnForceReset.disabled = false;
      btnForceReset.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg><span>รีเซ็ต</span>`;
    }
  });
}

const btnUserResetActive = document.getElementById('btn-user-reset-active');
if (btnUserResetActive) {
  btnUserResetActive.addEventListener('click', async () => {
    if (!confirm('คุณต้องการรีเซ็ตสถานะงานค้นหาของคุณ เพื่อให้ระบบพร้อมเริ่มค้นหาใหม่ทันทีใช่หรือไม่?')) return;
    btnUserResetActive.disabled = true;
    btnUserResetActive.textContent = 'กำลังรีเซ็ต...';
    try {
      const res = await fetch('/api/job/reset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {})
        },
        body: JSON.stringify({ user: authUser })
      });
      const data = await res.json();
      alert(`🔄 ${data.message || 'รีเซ็ตสถานะงานของคุณเรียบร้อยแล้ว'}`);
      if (typeof pollStatusFallback === 'function') pollStatusFallback();
      if (typeof loadHistoryList === 'function') loadHistoryList();
    } catch (err) {
      alert('เกิดข้อผิดพลาด: ' + err.message);
    } finally {
      btnUserResetActive.disabled = false;
      btnUserResetActive.innerHTML = '<span>🔄 รีเซ็ต</span>';
    }
  });
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
        <th class="py-2.5 px-3">เบอร์ทรูทั้งหมดที่พบ</th>
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
      
      const allPhones = tr.all_phones && tr.all_phones !== '-' ? tr.all_phones : '';
      const activePhones = tr.active_phones && tr.active_phones !== '-' ? tr.active_phones : '';
      let trDisplay = '<span class="text-slate-500">-</span>';
      if (allPhones) {
        trDisplay = `<span class="px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-300 border border-rose-500/30 font-medium font-mono">${allPhones}</span>`;
        if (activePhones && activePhones !== '-') {
          trDisplay += `<span class="ml-1.5 px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" title="Active: ${activePhones}">Active</span>`;
        }
      }

      const coName = sc['ชื่อ-นามสกุลผู้ค้ำ'] ? `${sc['ชื่อ-นามสกุลผู้ค้ำ']} (${sc['เบอร์โทรผู้ค้ำ'] || '-'})` : '-';
      const addr = sc['ที่อยู่ปัจจุบันผู้เช่าซื้อ'] || '-';

      return `
        <tr class="hover:bg-slate-900/40">
          <td class="py-2 px-3 font-mono text-slate-500">${i + 1}</td>
          <td class="py-2 px-3 font-mono font-medium text-white">${r.cid}</td>
          <td class="py-2 px-3 font-medium text-slate-200">${name}</td>
          <td class="py-2 px-3"><span class="px-2 py-0.5 rounded text-[11px] ${scStatus.includes('สำเร็จ') || scStatus.includes('เช่าซื้อ') ? 'bg-indigo-500/15 text-indigo-300' : 'bg-slate-800 text-slate-400'}">${scStatus}</span></td>
          <td class="py-2 px-3 font-mono text-sky-300">${scPhone}</td>
          <td class="py-2 px-3">${trDisplay}</td>
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
        <th class="py-2.5 px-3">สถานะ</th>
        <th class="py-2.5 px-3">จำนวนเบอร์ทั้งหมด</th>
        <th class="py-2.5 px-3">รายการเบอร์โทรศัพท์ทั้งหมด</th>
        <th class="py-2.5 px-3">เบอร์เฉพาะ Active</th>
        <th class="py-2.5 px-3">รายละเอียดทุกเบอร์</th>
      </tr>
    `;

    tableBody.innerHTML = currentResults.map((r, i) => {
      const tr = r.true || {};
      const totalCnt = tr.total_count !== undefined ? tr.total_count : (tr.count || 0);
      const allPh = tr.all_phones || '-';
      const actPh = tr.active_phones || '-';
      const dtPh = tr.phone_details || '-';

      return `
        <tr class="hover:bg-slate-900/40">
          <td class="py-2 px-3 font-mono text-slate-500">${i + 1}</td>
          <td class="py-2 px-3 font-mono font-medium text-white">${r.cid}</td>
          <td class="py-2 px-3"><span class="px-2 py-0.5 rounded text-[11px] ${tr.status && tr.status.includes('สำเร็จ') ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-800 text-slate-400'}">${tr.status || '-'}</span></td>
          <td class="py-2 px-3 font-mono font-bold ${totalCnt > 0 ? 'text-rose-400' : 'text-slate-500'}">${totalCnt}</td>
          <td class="py-2 px-3 font-mono text-rose-300 font-semibold">${allPh !== '-' ? allPh : '<span class="text-slate-500">-</span>'}</td>
          <td class="py-2 px-3 font-mono text-emerald-400">${actPh !== '-' ? actPh : '<span class="text-slate-500">-</span>'}</td>
          <td class="py-2 px-3 font-mono text-slate-400 truncate max-w-xs" title="${dtPh}">${dtPh}</td>
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

function updateStatusBadge(el, status, queuePos) {
  if (!el) return;
  if (status === 'running') {
    el.textContent = 'กำลังค้นหา (RUNNING)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-sky-500/15 text-sky-400 border border-sky-500/30 animate-pulse';
  } else if (status === 'starting') {
    el.textContent = 'กำลังเปิดระบบ... (STARTING)';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30 animate-pulse';
  } else if (status === 'queued') {
    el.textContent = 'กำลังจัดเตรียมระบบ...';
    el.className = 'px-2.5 py-1 rounded-full text-xs font-medium bg-sky-500/15 text-sky-400 border border-sky-500/30 animate-pulse';
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
  const isQueued = (data.status === 'queued');
  const isTerminal = (data.status === 'stopped' || data.status === 'done' || data.status === 'error');
  const isBusy = !isTerminal && (
    data.status === 'running' ||
    data.status === 'starting' ||
    isQueued ||
    data.sc_status === 'running' ||
    data.sc_status === 'starting' ||
    data.tr_status === 'running' ||
    data.tr_status === 'starting'
  );
  isJobRunning = isBusy;

  if (isQueued) {
    btnStart.disabled = true;
    btnStart.innerHTML = `<span class="inline-block animate-spin mr-1">⚡</span><span>กำลังจัดเตรียมระบบและเริ่มค้นหา...</span>`;
    btnStop.disabled = false;
  } else if (isBusy) {
    btnStart.disabled = true;
    btnStart.innerHTML = `<span class="inline-block animate-spin mr-1">⚡</span><span>กำลังค้นหาข้อมูล (ทำงานอัตโนมัติ)...</span>`;
    btnStop.disabled = false;
  } else {
    btnStart.disabled = false;
    btnStart.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><span>เริ่มค้นหาข้อมูล</span>`;
    btnStop.disabled = true;
  }

  // 1. Siamchai Card Update
  const scStatusToRender = isQueued ? 'queued' : ((data.status === 'starting' && data.sc_status === 'idle') ? 'starting' : data.sc_status);
  updateStatusBadge(scStatusPill, scStatusToRender, data.queue_position);
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
  const trStatusToRender = isQueued ? 'queued' : ((data.status === 'starting' && data.tr_status === 'idle') ? 'starting' : data.tr_status);
  updateStatusBadge(trStatusPill, trStatusToRender, data.queue_position);
  trProgressInfo.textContent = `${data.tr_current_index || 0} / ${data.total || 0} รายการ`;
  trProgressPercent.textContent = `${data.tr_percent || 0}%`;
  trProgressBar.style.width = `${data.tr_percent || 0}%`;
  trCurrCid.textContent = `กำลังค้นหา: ${data.tr_current_cid || '-'}`;
  const trFound = data.tr_found_count !== undefined ? data.tr_found_count : (data.tr_count || 0);
  trCountFound.textContent = `พบเบอร์โทรศัพท์: ${trFound} รายการ (ค้นแล้ว ${data.tr_count || 0})`;

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
  usersTableBody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-slate-500">กำลังโหลดข้อมูลผู้ใช้...</td></tr>`;
  try {
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    const res = await fetch('/api/users', {
      headers: headers,
      credentials: 'same-origin'
    });
    if (!res.ok) {
      let errDetail = 'ไม่สามารถโหลดรายชื่อผู้ใช้ได้';
      try {
        const err = await res.json();
        errDetail = err.detail || errDetail;
      } catch (_) {}
      usersTableBody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-rose-400 font-semibold">${errDetail}</td></tr>`;
      return;
    }
    const data = await res.json();
    const users = data.users || [];
    if (!users.length) {
      usersTableBody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-slate-500">ไม่พบข้อมูลผู้ใช้</td></tr>`;
      return;
    }
    usersTableBody.innerHTML = '';
    users.forEach(u => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-900/50 transition-colors';
      const isCurrent = (u.username || '').toLowerCase() === (authUser || '').toLowerCase();
      const roleBadge = u.role === 'admin'
        ? `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Admin</span>`
        : `<span class="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700">Member</span>`;

      // Expiration display
      let expBadge = `<span class="text-slate-500 text-xs">ไม่จำกัด</span>`;
      if (u.expire_date) {
        const todayStr = new Date().toISOString().split('T')[0];
        const isExp = todayStr > u.expire_date;
        if (isExp) {
          expBadge = `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">หมดอายุ (${u.expire_date})</span>`;
        } else {
          expBadge = `<span class="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${u.expire_date}</span>`;
        }
      }

      // Device quota display
      const devCnt = u.devices_count || 0;
      const maxDev = u.max_devices || 2;
      const devBadge = `<span class="px-2 py-0.5 rounded text-[11px] ${devCnt >= maxDev ? 'bg-amber-500/20 text-amber-300 font-semibold' : 'bg-slate-800 text-slate-300'}">${devCnt}/${maxDev} เครื่อง</span>`;

      tr.innerHTML = `
        <td class="p-2.5 font-mono text-white font-medium">${u.username}</td>
        <td class="p-2.5 text-slate-300">${u.name || '-'}</td>
        <td class="p-2.5">${roleBadge}</td>
        <td class="p-2.5 text-center">${expBadge}</td>
        <td class="p-2.5 text-center">${devBadge}</td>
        <td class="p-2.5 text-right space-x-1.5">
          <button class="btn-user-edit px-2 py-1 rounded bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 text-xs border border-indigo-500/30" data-user="${u.username}" data-name="${u.name || ''}" data-expire="${u.expire_date || ''}" data-maxdev="${u.max_devices || 2}" title="แก้ไขโปรโมชั่น / วันหมดอายุ / โควต้าเครื่อง">✏️ แก้ไข</button>
          ${u.role !== 'admin' ? `<button class="btn-user-reset-dev px-2 py-1 rounded bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 text-xs border border-amber-500/30" data-user="${u.username}" title="ล้างประวัติเครื่องเพื่อให้ผูกเครื่องใหม่">💻 ล้างเครื่อง</button>` : ''}
          <button class="btn-user-reset px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700" data-user="${u.username}">🔑 รหัสผ่าน</button>
          ${!isCurrent ? `<button class="btn-user-del px-2 py-1 rounded bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 text-xs border border-rose-500/30" data-user="${u.username}">🗑️ ลบ</button>` : `<span class="text-[11px] text-slate-500 italic pl-1">(บัญชีนี้)</span>`}
        </td>
      `;
      usersTableBody.appendChild(tr);
    });

    document.querySelectorAll('.btn-user-edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const u = e.currentTarget.getAttribute('data-user');
        const name = e.currentTarget.getAttribute('data-name');
        const expire = e.currentTarget.getAttribute('data-expire');
        const maxdev = e.currentTarget.getAttribute('data-maxdev') || '2';

        document.getElementById('edit-user-username').value = u;
        document.getElementById('edit-user-name').value = name;
        document.getElementById('edit-user-expire').value = expire;
        document.getElementById('edit-user-maxdev').value = maxdev;

        const modalEdit = document.getElementById('modal-edit-user');
        if (modalEdit) modalEdit.classList.remove('hidden');
      });
    });

    document.querySelectorAll('.btn-user-reset-dev').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const u = e.currentTarget.getAttribute('data-user');
        if (!confirm(`ต้องการรีเซ็ตประวัติเครื่องที่ผูกไว้ของผู้ใช้ "${u}" ใช่หรือไม่?\n(ผู้ใช้จะสามารถผูกคอมเครื่องใหม่ได้ทันที)`)) return;
        try {
          const r = await fetch(`/api/users/${encodeURIComponent(u)}/reset-devices`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
          });
          const resData = await r.json();
          if (r.ok) {
            alert(`✅ รีเซ็ตเครื่องสำหรับ ${u} เรียบร้อยแล้ว`);
            loadUsersList();
          } else {
            alert(`❌ เกิดข้อผิดพลาด: ${resData.detail || 'ไม่สามารถรีเซ็ตได้'}`);
          }
        } catch (err) {
          alert('เกิดข้อผิดพลาด: ' + err.message);
        }
      });
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
    usersTableBody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-rose-400">เกิดข้อผิดพลาด: ${err.message}</td></tr>`;
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

const btnOpenUsersFromSettings = document.getElementById('btn-open-users-from-settings');
if (btnOpenUsersFromSettings) {
  btnOpenUsersFromSettings.addEventListener('click', () => {
    if (modalSettings) modalSettings.classList.add('hidden');
    if (modalUsers) {
      modalUsers.classList.remove('hidden');
      loadUsersList();
    }
  });
}

if (btnCloseUsers) btnCloseUsers.addEventListener('click', () => modalUsers.classList.add('hidden'));
if (btnDoneUsers) btnDoneUsers.addEventListener('click', () => modalUsers.classList.add('hidden'));
if (btnRefreshUsers) btnRefreshUsers.addEventListener('click', loadUsersList);

// Quick +30 days button
const btnQuick1Month = document.getElementById('btn-quick-1month');
if (btnQuick1Month) {
  btnQuick1Month.addEventListener('click', () => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const inp = document.getElementById('new-user-expire');
    if (inp) inp.value = `${yyyy}-${mm}-${dd}`;
  });
}

if (btnCreateUser) {
  btnCreateUser.addEventListener('click', async () => {
    const uname = document.getElementById('new-user-name').value.trim();
    const upass = document.getElementById('new-user-pass').value.trim();
    const ufullname = document.getElementById('new-user-fullname').value.trim();
    const uexpire = document.getElementById('new-user-expire').value;
    const umaxdev = parseInt(document.getElementById('new-user-maxdev').value || '2', 10);
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
          expire_date: uexpire,
          max_devices: umaxdev,
          role: urole
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(`✅ สร้างผู้ใช้งาน "${uname}" เรียบร้อยแล้ว (โควต้า ${umaxdev} เครื่อง, หมดอายุ: ${uexpire || 'ไม่จำกัด'})`);
        document.getElementById('new-user-name').value = '';
        document.getElementById('new-user-pass').value = '';
        document.getElementById('new-user-fullname').value = '';
        document.getElementById('new-user-expire').value = '';
        loadUsersList();
      } else {
        alert(`❌ ไม่สามารถสร้างผู้ใช้ได้: ${data.detail || 'เกิดข้อผิดพลาด'}`);
      }
    } catch (err) {
      alert('เกิดข้อผิดพลาด: ' + err.message);
    }
  });
}

// ------------------ Edit User Modal Handlers ------------------
const modalEditUser = document.getElementById('modal-edit-user');
const btnCloseEditUser = document.getElementById('btn-close-edit-user');
const btnCancelEditUser = document.getElementById('btn-cancel-edit-user');
const btnSaveEditUser = document.getElementById('btn-save-edit-user');
const btnEditAdd30 = document.getElementById('btn-edit-add-30');
const btnEditAdd60 = document.getElementById('btn-edit-add-60');
const btnEditUnlimited = document.getElementById('btn-edit-unlimited');

function addDaysToDateInput(inpId, days) {
  const inp = document.getElementById(inpId);
  if (!inp) return;
  let baseDate = new Date();
  if (inp.value) {
    const parsed = new Date(inp.value);
    if (!isNaN(parsed.getTime()) && parsed > baseDate) {
      baseDate = parsed;
    }
  }
  baseDate.setDate(baseDate.getDate() + days);
  const yyyy = baseDate.getFullYear();
  const mm = String(baseDate.getMonth() + 1).padStart(2, '0');
  const dd = String(baseDate.getDate()).padStart(2, '0');
  inp.value = `${yyyy}-${mm}-${dd}`;
}

if (btnEditAdd30) btnEditAdd30.addEventListener('click', () => addDaysToDateInput('edit-user-expire', 30));
if (btnEditAdd60) btnEditAdd60.addEventListener('click', () => addDaysToDateInput('edit-user-expire', 60));
if (btnEditUnlimited) btnEditUnlimited.addEventListener('click', () => {
  const inp = document.getElementById('edit-user-expire');
  if (inp) inp.value = '';
});

if (btnCloseEditUser) btnCloseEditUser.addEventListener('click', () => modalEditUser && modalEditUser.classList.add('hidden'));
if (btnCancelEditUser) btnCancelEditUser.addEventListener('click', () => modalEditUser && modalEditUser.classList.add('hidden'));

if (btnSaveEditUser) {
  btnSaveEditUser.addEventListener('click', async () => {
    const u = document.getElementById('edit-user-username').value;
    const name = document.getElementById('edit-user-name').value.trim();
    const expire = document.getElementById('edit-user-expire').value;
    const maxdev = parseInt(document.getElementById('edit-user-maxdev').value, 10) || 2;

    try {
      btnSaveEditUser.disabled = true;
      btnSaveEditUser.textContent = 'กำลังบันทึก...';
      const headers = { 'Content-Type': 'application/json' };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      const res = await fetch(`/api/users/${encodeURIComponent(u)}`, {
        method: 'PUT',
        headers: headers,
        body: JSON.stringify({
          name: name,
          expire_date: expire,
          max_devices: maxdev
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(`✅ อัปเดตข้อมูลผู้ใช้ "${u}" เรียบร้อยแล้ว (โควต้า ${maxdev} เครื่อง, วันหมดอายุ: ${expire || 'ไม่จำกัด'})`);
        if (modalEditUser) modalEditUser.classList.add('hidden');
        loadUsersList();
      } else {
        alert(`❌ เกิดข้อผิดพลาด: ${data.detail || 'ไม่สามารถอัปเดตได้'}`);
      }
    } catch (err) {
      alert('เกิดข้อผิดพลาด: ' + err.message);
    } finally {
      btnSaveEditUser.disabled = false;
      btnSaveEditUser.textContent = '💾 บันทึกการแก้ไข';
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
      else if (j.status === 'starting') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse">กำลังเปิดระบบ</span>';
      else if (j.status === 'queued') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500/20 text-sky-400 border border-sky-500/30 animate-pulse">กำลังจัดเตรียมระบบ</span>';
      else if (j.status === 'stopped') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-400">หยุดแล้ว</span>';
      else if (j.status === 'error') statusBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">ข้อผิดพลาด</span>';

      let modeLabel = 'สยามชัย & ทรู';
      if (j.mode === 'siamchai') modeLabel = 'สยามชัย';
      else if (j.mode === 'true') modeLabel = 'ทรู';

      let dlBtns = [];
      const isJobActive = (j.status === 'running' || j.status === 'starting' || j.status === 'queued');
      const canManage = (currentUserRole === 'admin' || authUser.toLowerCase() === 'admin' || authUser.toLowerCase() === (j.user || '').toLowerCase());

      // If active job: Show stop button
      if (isJobActive && canManage) {
        dlBtns.push(`<button class="btn-row-stop px-2.5 py-1 rounded bg-rose-600/30 hover:bg-rose-600 text-rose-200 hover:text-white text-xs border border-rose-500/40 inline-flex items-center gap-1 font-medium transition-colors" data-jobid="${j.job_id}" data-user="${j.user}" title="สั่งหยุดงานนี้เฉพาะไฟล์นี้">🛑 หยุดงานนี้</button>`);
      }

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

    // Row Stop Specific Job Handler
    document.querySelectorAll('.btn-row-stop').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const jid = e.currentTarget.getAttribute('data-jobid');
        const u = e.currentTarget.getAttribute('data-user');
        if (!confirm(`คุณต้องการสั่งหยุดงานของผู้ใช้ "${u}" (งานนี้เท่านั้น) ใช่หรือไม่?`)) return;
        try {
          btn.disabled = true;
          btn.textContent = 'กำลังหยุด...';
          const headers = { 'Content-Type': 'application/json' };
          if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
          const res = await fetch('/api/stop', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ job_id: jid })
          });
          const data = await res.json();
          alert(`🛑 สั่งหยุดงานของผู้ใช้ "${u}" เรียบร้อยแล้ว`);
          loadHistoryList();
          if (typeof pollStatusFallback === 'function') pollStatusFallback();
        } catch (err) {
          alert('เกิดข้อผิดพลาด: ' + err.message);
        }
      });
    });

    // Row Reset Specific Job Handler
    document.querySelectorAll('.btn-row-reset').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const jid = e.currentTarget.getAttribute('data-jobid');
        const u = e.currentTarget.getAttribute('data-user');
        if (!confirm(`คุณต้องการรีเซ็ตและปลดล็อคงานของผู้ใช้ "${u}" (งานนี้เท่านั้น) เพื่อให้เริ่มใหม่ได้ทันทีใช่หรือไม่?`)) return;
        try {
          btn.disabled = true;
          btn.textContent = 'กำลังรีเซ็ต...';
          const headers = { 'Content-Type': 'application/json' };
          if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
          const res = await fetch('/api/job/reset', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ job_id: jid, user: u })
          });
          const data = await res.json();
          alert(`🔄 รีเซ็ตและปลดล็อคงานของผู้ใช้ "${u}" เรียบร้อยแล้ว`);
          loadHistoryList();
          if (typeof pollStatusFallback === 'function') pollStatusFallback();
        } catch (err) {
          alert('เกิดข้อผิดพลาด: ' + err.message);
        }
      });
    });
  } catch (err) {
    historyTableBody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-rose-400">เกิดข้อผิดพลาด: ${err.message}</td></tr>`;
  }
}

// Emergency System Reset Handler (Admin Only)
async function handleAdminResetSystem() {
  if (!confirm('⚠️ คำเตือนฉุกเฉิน: คุณต้องการสั่งบังคับหยุดงานค้นหาที่กำลังทำงานอยู่ทั้งหมดของทุกคน และรีเซ็ตระบบใช่หรือไม่?\n\n(ระบบจะปิดบอทที่ค้างทั้งหมด และปลดล็อคให้ทุกคนเริ่มค้นหาใหม่ได้ทันที)')) return;
  try {
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    const res = await fetch('/api/admin/reset-system', {
      method: 'POST',
      headers: headers
    });
    const data = await res.json();
    alert(`✅ ${data.message || 'รีเซ็ตระบบและสั่งปิดงานทั้งหมดเรียบร้อยแล้ว'}`);
    loadHistoryList();
    if (modalSettings) modalSettings.classList.add('hidden');
    if (typeof pollStatusFallback === 'function') pollStatusFallback();
  } catch (err) {
    alert('เกิดข้อผิดพลาด: ' + err.message);
  }
}

const btnAdminResetAll = document.getElementById('btn-admin-reset-all');
if (btnAdminResetAll) btnAdminResetAll.addEventListener('click', handleAdminResetSystem);

const btnSettingsResetSystem = document.getElementById('btn-settings-reset-system');
if (btnSettingsResetSystem) btnSettingsResetSystem.addEventListener('click', handleAdminResetSystem);

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

// ==========================================================================
// 🔒 LICENSE & ACTIVATION MANAGEMENT SYSTEM (Hardware Machine ID & Expiry)
// ==========================================================================
let cachedLicenseData = null;
let cachedCurrentMachineId = '';

const btnLicenseBadge = document.getElementById('btn-license-badge');
const licenseIndicator = document.getElementById('license-indicator');
const licenseBadgeText = document.getElementById('license-badge-text');

// Activation Modal Elements
const modalLicense = document.getElementById('modal-license');
const btnCloseLicense = document.getElementById('btn-close-license');
const btnDismissLicense = document.getElementById('btn-dismiss-license');
const licStatusBanner = document.getElementById('lic-status-banner');
const licStatusTitle = document.getElementById('lic-status-title');
const licStatusDesc = document.getElementById('lic-status-desc');
const licMachineId = document.getElementById('lic-machine-id');
const btnCopyMachineId = document.getElementById('btn-copy-machine-id');
const btnMailLicense = document.getElementById('btn-mail-license');
const btnCopyLineMsg = document.getElementById('btn-copy-line-msg');
const licKeyInput = document.getElementById('lic-key-input');
const licActionAlert = document.getElementById('lic-action-alert');
const btnSubmitLicense = document.getElementById('btn-submit-license');

// Admin Key Generator Modal Elements
const modalLicenseGen = document.getElementById('modal-license-gen');
const btnOpenLicenseGen = document.getElementById('btn-open-license-gen');
const btnCloseLicenseGen = document.getElementById('btn-close-license-gen');
const btnCancelLicenseGen = document.getElementById('btn-cancel-license-gen');
const genLicCustomer = document.getElementById('gen-lic-customer');
const genLicExpire = document.getElementById('gen-lic-expire');
const btnGenAdd30 = document.getElementById('btn-gen-add-30');
const btnGenAdd90 = document.getElementById('btn-gen-add-90');
const btnGenAdd365 = document.getElementById('btn-gen-add-365');
const btnGenUseMyMachine = document.getElementById('btn-gen-use-my-machine');
const genLicMch1 = document.getElementById('gen-lic-mch-1');
const genLicMch2 = document.getElementById('gen-lic-mch-2');
const genLicMch3 = document.getElementById('gen-lic-mch-3');
const btnDoLicenseGen = document.getElementById('btn-do-license-gen');
const genLicResultBox = document.getElementById('gen-lic-result-box');
const genLicOutput = document.getElementById('gen-lic-output');
const btnCopyGenLic = document.getElementById('btn-copy-gen-lic');

async function checkLicenseStatus(autoOpenModalOnInvalid = false) {
  try {
    const res = await fetch('/api/license/status');
    const data = await res.json();
    cachedLicenseData = data;
    cachedCurrentMachineId = data.current_machine || '';

    if (licMachineId) {
      licMachineId.value = cachedCurrentMachineId || 'ไม่สามารถระบุรหัสเครื่องได้';
    }

    // Configure Mailto link
    if (btnMailLicense) {
      const subject = encodeURIComponent(`ขอรหัสเปิดใช้งาน Customer Data Hub [${cachedCurrentMachineId}]`);
      const body = encodeURIComponent(
        `เรียน คุณมงคล,\n\nขอเปิดใช้งานโปรแกรม Customer Data Hub สำหรับเครื่องนี้ครับ\n- รหัสประจำเครื่อง (Machine ID): ${cachedCurrentMachineId}\n- ชื่อลูกค้า/บริษัท: [กรุณาระบุ]\n- เบอร์โทรศัพท์ติดต่อ: [กรุณาระบุ]\n\nขอบคุณครับ`
      );
      btnMailLicense.href = `mailto:${data.contact_email || 'mongkholkp001@gmail.com'}?subject=${subject}&body=${body}`;
    }

    if (data.valid) {
      // Valid License UI
      if (licenseIndicator) {
        licenseIndicator.className = 'w-2 h-2 rounded-full bg-emerald-400';
      }
      if (licenseBadgeText) {
        licenseBadgeText.textContent = `ใบอนุญาต: ${data.customer} (เหลือ ${data.days_left} วัน)`;
      }
      if (btnLicenseBadge) {
        btnLicenseBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 text-xs font-medium border border-emerald-500/30 transition-colors';
        btnLicenseBadge.title = `ใบอนุญาต: ${data.customer}\nหมดอายุ: ${data.expire_date} (อีก ${data.days_left} วัน)\nเครื่องที่ ${data.machine_slot || 1} จากทั้งหมด ${data.max_machines || 3} เครื่อง\nคลิกเพื่อดูรายละเอียด`;
      }

      // Update Modal banner if open
      if (licStatusBanner) {
        licStatusBanner.className = 'p-3.5 rounded-xl border text-xs flex items-start gap-3 bg-emerald-500/10 border-emerald-500/30 text-emerald-200';
      }
      if (licStatusTitle) {
        licStatusTitle.textContent = `✅ ใบอนุญาตใช้งานถูกต้อง (${data.customer})`;
        licStatusTitle.className = 'font-semibold text-emerald-300';
      }
      if (licStatusDesc) {
        licStatusDesc.textContent = `ใช้งานได้ถึง: ${data.expire_date} (เหลือ ${data.days_left} วัน) | อนุมัติเครื่องที่ ${data.machine_slot || 1}/${data.max_machines || 3} เครื่อง`;
      }
    } else {
      // Invalid / Expired / Unauthorized Machine UI
      if (licenseIndicator) {
        licenseIndicator.className = 'w-2 h-2 rounded-full bg-rose-500 animate-pulse';
      }
      if (licenseBadgeText) {
        licenseBadgeText.textContent = data.status === 'EXPIRED' ? '⚠️ ใบอนุญาตหมดอายุ' : '🔒 ยังไม่เปิดใช้งาน';
      }
      if (btnLicenseBadge) {
        btnLicenseBadge.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 text-xs font-semibold border border-rose-500/40 transition-colors animate-pulse';
        btnLicenseBadge.title = `${data.message || 'ใบอนุญาตไม่ถูกต้อง'}\nคลิกเพื่อใส่รหัสเปิดใช้งาน`;
      }

      if (licStatusBanner) {
        licStatusBanner.className = 'p-3.5 rounded-xl border text-xs flex items-start gap-3 bg-rose-500/15 border-rose-500/40 text-rose-200';
      }
      if (licStatusTitle) {
        licStatusTitle.textContent = `⚠️ ${data.message || 'ยังไม่เปิดใช้งานใบอนุญาตบนเครื่องนี้'}`;
        licStatusTitle.className = 'font-semibold text-rose-300';
      }
      if (licStatusDesc) {
        licStatusDesc.textContent = `กรุณาส่งรหัสเครื่องนี้ให้ผู้ดูแลระบบ (mongkholkp001@gmail.com) เพื่อรับรหัสเปิดใช้งาน (License Key)`;
      }

      if (autoOpenModalOnInvalid && modalLicense) {
        modalLicense.classList.remove('hidden');
      }

      // Background listener for online approval from Admin email
      startPollingForApproval();
    }
  } catch (err) {
    console.error('Failed to check license status:', err);
  }
}

// Open modal on click
if (btnLicenseBadge) {
  btnLicenseBadge.addEventListener('click', () => {
    if (modalLicense) {
      modalLicense.classList.remove('hidden');
      if (licActionAlert) licActionAlert.classList.add('hidden');
    }
  });
}

if (btnCloseLicense) {
  btnCloseLicense.addEventListener('click', () => {
    if (modalLicense) modalLicense.classList.add('hidden');
  });
}

if (btnDismissLicense) {
  btnDismissLicense.addEventListener('click', () => {
    if (modalLicense) modalLicense.classList.add('hidden');
  });
}

// Copy Machine ID button
if (btnCopyMachineId) {
  btnCopyMachineId.addEventListener('click', () => {
    if (!cachedCurrentMachineId) return;
    navigator.clipboard.writeText(cachedCurrentMachineId).then(() => {
      btnCopyMachineId.innerHTML = '✅ <span>คัดลอกแล้ว!</span>';
      setTimeout(() => {
        btnCopyMachineId.innerHTML = '📋 <span>คัดลอก</span>';
      }, 2000);
    });
  });
}

// Copy LINE Message button
if (btnCopyLineMsg) {
  btnCopyLineMsg.addEventListener('click', () => {
    if (!cachedCurrentMachineId) return;
    const username = (document.getElementById('req-lic-username')?.value || '').trim();
    const custName = (document.getElementById('req-lic-name')?.value || '').trim();
    const phone = (document.getElementById('req-lic-phone')?.value || '').trim();
    let lineMsg = `เรียน คุณมงคล,\nขอเปิดใช้งานโปรแกรม Customer Data Hub สำหรับเครื่องนี้ครับ\n- ชื่อผู้ใช้ (Username): ${username || '-'}\n- รหัสเครื่อง (Machine ID): ${cachedCurrentMachineId}`;
    if (custName) lineMsg += `\n- ชื่อลูกค้า/บริษัท: ${custName}`;
    if (phone) lineMsg += `\n- เบอร์โทรติดต่อ: ${phone}`;
    lineMsg += `\nขอบคุณครับ`;

    navigator.clipboard.writeText(lineMsg).then(() => {
      btnCopyLineMsg.innerHTML = '✅ <span>คัดลอกข้อความแล้ว!</span>';
      setTimeout(() => {
        btnCopyLineMsg.innerHTML = '💬 <span>คัดลอกส่ง LINE</span>';
      }, 2500);
    });
  });
}

// ------------------ Polling for 1-Click Email Approval ------------------
let approvalPollInterval = null;
function startPollingForApproval() {
  if (approvalPollInterval) clearInterval(approvalPollInterval);
  approvalPollInterval = setInterval(async () => {
    if (!cachedCurrentMachineId) return;
    try {
      const res = await fetch(`/api/license/check-online?mch=${encodeURIComponent(cachedCurrentMachineId)}`);
      const data = await res.json();
      if (data.approved) {
        clearInterval(approvalPollInterval);
        approvalPollInterval = null;
        if (data.auth_token) {
          localStorage.setItem('auth_token', data.auth_token);
          localStorage.setItem('auth_user', data.username || data.customer || 'member');
        }
        if (licActionAlert) {
          licActionAlert.className = 'p-3 rounded-xl text-xs bg-emerald-500/20 border border-emerald-500/40 text-emerald-300';
          licActionAlert.innerHTML = `🎉 <b>ผู้ดูแลระบบกดอนุมัติเรียบร้อยแล้ว!</b><br>บัญชีผู้ใช้: <b>${data.username || data.customer}</b> (สิทธิ์: ผู้ใช้ทั่วไป)<br>เครื่องที่ ${data.machine_slot || 1}/${data.max_machines || 3} เครื่อง (หมดอายุ: ${data.expire_date} - เหลือ ${data.days_left} วัน)<br>ระบบกำลังเข้าสู่โปรแกรมอัตโนมัติ...`;
          licActionAlert.classList.remove('hidden');
        }
        await checkLicenseStatus(false);
        // Refresh session to apply member role and hide admin controls
        await checkAuthMe();
        setTimeout(() => {
          if (modalLicense) modalLicense.classList.add('hidden');
        }, 1500);
      }
    } catch (e) {
      console.warn('Poll approval err:', e);
    }
  }, 4000);
}

// Send Direct Email Request (Direct to mongkholkp001@gmail.com with 1-Click Approval Links)
const btnSendEmailRequest = document.getElementById('btn-send-email-request');
if (btnSendEmailRequest) {
  btnSendEmailRequest.addEventListener('click', async () => {
    const reqLicUser = document.getElementById('req-lic-username');
    const reqLicPass = document.getElementById('req-lic-password');
    const reqLicName = document.getElementById('req-lic-name');
    const reqLicPhone = document.getElementById('req-lic-phone');

    const username = (reqLicUser ? reqLicUser.value : '').trim();
    const password = (reqLicPass ? reqLicPass.value : '').trim();
    const custName = (reqLicName ? reqLicName.value : '').trim();
    const phone = (reqLicPhone ? reqLicPhone.value : '').trim();

    if (!username || username.length < 3) {
      alert('กรุณาระบุชื่อผู้ใช้ (Username) อย่างน้อย 3 ตัวอักษร (ภาษาอังกฤษหรือตัวเลข)');
      if (reqLicUser) reqLicUser.focus();
      return;
    }
    if (!password || password.length < 4) {
      alert('กรุณากำหนดรหัสผ่าน (Password) อย่างน้อย 4 ตัวอักษร สำหรับเข้าใช้งานเครื่องนี้');
      if (reqLicPass) reqLicPass.focus();
      return;
    }

    try {
      btnSendEmailRequest.disabled = true;
      btnSendEmailRequest.innerHTML = '<span>กำลังส่งข้อมูลเข้าอีเมล Admin...</span>';

      const res = await fetch('/api/license/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: username,
          password: password,
          customer_name: custName || username,
          phone: phone,
          machine_id: cachedCurrentMachineId
        })
      });
      const data = await res.json();
      if (res.ok) {
        if (licActionAlert) {
          licActionAlert.className = 'p-3 rounded-xl text-xs bg-emerald-500/20 border border-emerald-500/40 text-emerald-300';
          licActionAlert.innerHTML = `✅ <b>ส่งคำขอและสร้างบัญชีสำเร็จเรียบร้อย!</b><br>ระบบได้ส่งคำขอของผู้ใช้ <b>${username}</b> ไปยังอีเมล <b>mongkholkp001@gmail.com</b> เรียบร้อยแล้ว<br><div class="mt-2 text-amber-300 flex items-center gap-1.5"><span class="animate-spin text-sm">⏳</span> <span>กำลังรอผู้ดูแลระบบกดอนุมัติในอีเมล... (เมื่ออนุมัติแล้ว ระบบจะปลดล็อคเข้าใช้งานเป็น User ทันที)</span></div>`;
          licActionAlert.classList.remove('hidden');
        }
        btnSendEmailRequest.innerHTML = '⏳ <span>รอผู้ดูแลระบบกดอนุมัติในอีเมล...</span>';
        startPollingForApproval();
      } else {
        alert('ส่งคำขอไม่สำเร็จ: ' + (data.detail || 'เกิดข้อผิดพลาด'));
        btnSendEmailRequest.innerHTML = '✉️ <span>ส่งคำขอเปิดใช้งานและสร้างบัญชีทันที</span>';
      }
    } catch (err) {
      alert('เกิดข้อผิดพลาดในการส่ง: ' + err.message);
      btnSendEmailRequest.innerHTML = '✉️ <span>ส่งคำขอเปิดใช้งานและสร้างบัญชีทันที</span>';
    } finally {
      btnSendEmailRequest.disabled = false;
    }
  });
}

// Submit License Key Activation
if (btnSubmitLicense) {
  btnSubmitLicense.addEventListener('click', async () => {
    const key = (licKeyInput ? licKeyInput.value : '').trim();
    if (!key) {
      if (licActionAlert) {
        licActionAlert.className = 'p-3 rounded-xl text-xs bg-rose-500/20 border border-rose-500/40 text-rose-300';
        licActionAlert.textContent = 'กรุณาวางรหัส License Key ก่อนกดเปิดใช้งาน';
        licActionAlert.classList.remove('hidden');
      }
      return;
    }

    try {
      btnSubmitLicense.disabled = true;
      btnSubmitLicense.innerHTML = '<span>กำลังตรวจสอบและเปิดใช้งาน...</span>';

      const res = await fetch('/api/license/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ license_key: key })
      });
      const data = await res.json();

      if (res.ok && data.valid) {
        if (licActionAlert) {
          licActionAlert.className = 'p-3 rounded-xl text-xs bg-emerald-500/20 border border-emerald-500/40 text-emerald-300';
          licActionAlert.textContent = `🎉 เปิดใช้งานสำเร็จ! ยินดีต้อนรับคุณ ${data.customer} (ใช้งานได้ถึง ${data.expire_date})`;
          licActionAlert.classList.remove('hidden');
        }
        if (licKeyInput) licKeyInput.value = '';
        await checkLicenseStatus(false);
        setTimeout(() => {
          if (modalLicense) modalLicense.classList.add('hidden');
        }, 1800);
      } else {
        if (licActionAlert) {
          licActionAlert.className = 'p-3 rounded-xl text-xs bg-rose-500/20 border border-rose-500/40 text-rose-300';
          licActionAlert.textContent = `❌ ${data.detail || data.message || 'รหัสเปิดใช้งานไม่ถูกต้อง'}`;
          licActionAlert.classList.remove('hidden');
        }
      }
    } catch (err) {
      if (licActionAlert) {
        licActionAlert.className = 'p-3 rounded-xl text-xs bg-rose-500/20 border border-rose-500/40 text-rose-300';
        licActionAlert.textContent = `เกิดข้อผิดพลาดในการเชื่อมต่อ: ${err.message}`;
        licActionAlert.classList.remove('hidden');
      }
    } finally {
      btnSubmitLicense.disabled = false;
      btnSubmitLicense.innerHTML = '🚀 <span>เปิดใช้งานระบบ (Activate)</span>';
    }
  });
}

// ------------------ Admin License Key Generator Handlers ------------------
if (btnOpenLicenseGen) {
  btnOpenLicenseGen.addEventListener('click', () => {
    if (modalLicenseGen) {
      modalLicenseGen.classList.remove('hidden');
      if (genLicResultBox) genLicResultBox.classList.add('hidden');
      // Default to 30 days
      const d = new Date();
      d.setDate(d.getDate() + 30);
      if (genLicExpire) genLicExpire.value = d.toISOString().split('T')[0];
    }
  });
}

if (btnCloseLicenseGen) btnCloseLicenseGen.addEventListener('click', () => modalLicenseGen.classList.add('hidden'));
if (btnCancelLicenseGen) btnCancelLicenseGen.addEventListener('click', () => modalLicenseGen.classList.add('hidden'));

function setGenExpireDays(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  if (genLicExpire) genLicExpire.value = d.toISOString().split('T')[0];
}

if (btnGenAdd30) btnGenAdd30.addEventListener('click', () => setGenExpireDays(30));
if (btnGenAdd90) btnGenAdd90.addEventListener('click', () => setGenExpireDays(90));
if (btnGenAdd365) btnGenAdd365.addEventListener('click', () => setGenExpireDays(365));

if (btnGenUseMyMachine) {
  btnGenUseMyMachine.addEventListener('click', () => {
    if (cachedCurrentMachineId && genLicMch1) {
      genLicMch1.value = cachedCurrentMachineId;
    }
  });
}

if (btnDoLicenseGen) {
  btnDoLicenseGen.addEventListener('click', async () => {
    const cust = (genLicCustomer ? genLicCustomer.value : '').trim();
    const exp = (genLicExpire ? genLicExpire.value : '').trim();
    if (!cust) {
      alert('กรุณาระบุชื่อลูกค้า / บริษัท');
      return;
    }
    if (!exp) {
      alert('กรุณาระบุวันหมดอายุ');
      return;
    }

    const machines = [];
    if (genLicMch1 && genLicMch1.value.trim()) machines.push(genLicMch1.value.trim().toUpperCase());
    if (genLicMch2 && genLicMch2.value.trim()) machines.push(genLicMch2.value.trim().toUpperCase());
    if (genLicMch3 && genLicMch3.value.trim()) machines.push(genLicMch3.value.trim().toUpperCase());

    if (machines.length === 0) {
      if (!confirm('คุณไม่ได้ระบุรหัสเครื่องใดๆ เลย ต้องการใส่รหัสเครื่องนี้เป็นค่าเริ่มต้นหรือไม่?')) {
        return;
      }
      if (cachedCurrentMachineId) machines.push(cachedCurrentMachineId);
    }

    try {
      btnDoLicenseGen.disabled = true;
      btnDoLicenseGen.textContent = 'กำลังสร้างรหัส...';

      const headers = { 'Content-Type': 'application/json' };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch('/api/license/generate', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          customer: cust,
          expire_date: exp,
          machines: machines,
          max_machines: 3
        })
      });
      const data = await res.json();

      if (res.ok && data.license_key) {
        if (genLicOutput) genLicOutput.value = data.license_key;
        if (genLicResultBox) genLicResultBox.classList.remove('hidden');
        alert(`🎉 สร้าง License Key สำหรับคุณ "${cust}" สำเร็จเรียบร้อยแล้ว!\nสามารถกดปุ่มคัดลอกรหัสเพื่อส่งให้ลูกค้าได้ทันที`);
      } else {
        alert('สร้างรหัสไม่สำเร็จ: ' + (data.detail || 'เกิดข้อผิดพลาด'));
      }
    } catch (err) {
      alert('เกิดข้อผิดพลาด: ' + err.message);
    } finally {
      btnDoLicenseGen.disabled = false;
      btnDoLicenseGen.textContent = '⚡ สร้างรหัสเปิดใช้งาน';
    }
  });
}

if (btnCopyGenLic) {
  btnCopyGenLic.addEventListener('click', () => {
    if (genLicOutput && genLicOutput.value) {
      navigator.clipboard.writeText(genLicOutput.value).then(() => {
        btnCopyGenLic.innerHTML = '✅ <span>คัดลอกเรียบร้อยแล้ว!</span>';
        setTimeout(() => {
          btnCopyGenLic.innerHTML = '📋 <span>คัดลอกรหัส</span>';
        }, 2000);
      });
    }
  });
}

// Initial License check on app load (prompt modal if not activated)
checkLicenseStatus(true);

