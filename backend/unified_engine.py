import time
import os
import re
import threading
from typing import List, Dict, Optional
from backend.siamchai_crawler import SiamchaiCrawler
from backend.true_crawler import TrueCrawler
from backend.storage import (
    save_combined_results_to_excel,
    save_siamchai_results_to_excel,
    save_true_results_to_excel,
    load_config
)

class UnifiedJobState:
    def __init__(self):
        self.lock = threading.Lock()
        self.job_id: Optional[str] = None
        self.job_name: str = "search_job"
        self.mode: str = "both" # "both", "siamchai", "true"
        self.status: str = "idle" # idle, running, stopped, done, error
        self.total: int = 0
        self.cids: List[str] = []

        # Siamchai Worker State (Runs 100% independently)
        self.sc_status: str = "idle" # idle, running, done, stopped, error
        self.sc_current_index: int = 0
        self.sc_current_cid: str = ""
        self.sc_results: Dict[str, Dict] = {} # cid -> dict
        self.sc_excel_path: Optional[str] = None
        self.sc_error: Optional[str] = None

        # TrueCorp Worker State (Runs 100% independently)
        self.tr_status: str = "idle" # idle, running, done, stopped, error
        self.tr_current_index: int = 0
        self.tr_current_cid: str = ""
        self.tr_results: Dict[str, Dict] = {} # cid -> dict
        self.tr_excel_path: Optional[str] = None
        self.tr_error: Optional[str] = None

        # Combined Excel
        self.combined_excel_path: Optional[str] = None

        self.logs: List[str] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.stop_requested: bool = False

        self.siamchai_crawler: Optional[SiamchaiCrawler] = None
        self.true_crawler: Optional[TrueCrawler] = None

    def add_log(self, msg: str):
        with self.lock:
            ts = time.strftime("%H:%M:%S")
            self.logs.append(f"[{ts}] {msg}")
            if len(self.logs) > 400:
                self.logs.pop(0)

    def to_dict(self):
        with self.lock:
            sc_pct = int((self.sc_current_index / self.total) * 100) if self.total > 0 else 0
            tr_pct = int((self.tr_current_index / self.total) * 100) if self.total > 0 else 0
            
            # Combine current results in order of input CIDs
            combined_rows = []
            for cid in self.cids:
                sc_res = self.sc_results.get(cid)
                tr_res = self.tr_results.get(cid)
                if sc_res is not None or tr_res is not None:
                    combined_rows.append({
                        "cid": cid,
                        "siamchai": sc_res or {},
                        "true": tr_res or {}
                    })

            elapsed = 0
            if self.start_time:
                end = self.end_time or time.time()
                elapsed = int(end - self.start_time)

            return {
                "job_id": self.job_id,
                "job_name": self.job_name,
                "mode": self.mode,
                "status": self.status,
                "total": self.total,
                "elapsed_seconds": elapsed,
                
                # Siamchai details
                "sc_status": self.sc_status,
                "sc_current_index": self.sc_current_index,
                "sc_percent": sc_pct,
                "sc_current_cid": self.sc_current_cid,
                "sc_count": len(self.sc_results),
                "has_sc_excel": bool(self.sc_excel_path and os.path.exists(self.sc_excel_path)),
                "sc_excel_filename": os.path.basename(self.sc_excel_path) if self.sc_excel_path else None,
                "sc_error": self.sc_error,
                
                # True details
                "tr_status": self.tr_status,
                "tr_current_index": self.tr_current_index,
                "tr_percent": tr_pct,
                "tr_current_cid": self.tr_current_cid,
                "tr_count": len(self.tr_results),
                "has_tr_excel": bool(self.tr_excel_path and os.path.exists(self.tr_excel_path)),
                "tr_excel_filename": os.path.basename(self.tr_excel_path) if self.tr_excel_path else None,
                "tr_error": self.tr_error,
                
                # Combined Excel
                "has_combined_excel": bool(self.combined_excel_path and os.path.exists(self.combined_excel_path)),
                "combined_excel_filename": os.path.basename(self.combined_excel_path) if self.combined_excel_path else None,
                
                # Legacy compatibility
                "percent": max(sc_pct, tr_pct),
                "has_excel": bool(self.combined_excel_path and os.path.exists(self.combined_excel_path)),
                "excel_filename": os.path.basename(self.combined_excel_path) if self.combined_excel_path else None,
                
                "results": combined_rows,
                "logs": self.logs[-40:],
                "stop_requested": self.stop_requested
            }

unified_job = UnifiedJobState()

def siamchai_worker(cids: List[str], headless: bool, cfg: dict):
    """
    Independent worker for Siamchai: searches sequentially through CIDs at its own pace
    without waiting for TrueCorp. Saves Siamchai-specific Excel as soon as it finishes.
    """
    global unified_job
    sc_crawler = None
    try:
        sc_u = cfg.get("siamchai_username", "")
        sc_p = cfg.get("siamchai_password", "")
        if not sc_u or not sc_p:
            raise ValueError("ยังไม่ได้ระบุ Username / Password ของสยามชัย")

        unified_job.add_log("🟣 [สยามชัย] กำลังเปิดเบราว์เซอร์และเข้าสู่ระบบ...")
        sc_crawler = SiamchaiCrawler(
            username=sc_u,
            password=sc_p,
            headless=headless,
            log_callback=lambda m: unified_job.add_log(f"🟣 [สยามชัย] {m}")
        )
        with unified_job.lock:
            unified_job.siamchai_crawler = sc_crawler
            unified_job.sc_status = "running"

        sc_crawler.login_and_prepare()
        unified_job.add_log("🟣 [สยามชัย] เข้าสู่ระบบพร้อมค้นหาข้อมูล!")

        total = len(cids)
        for i, cid in enumerate(cids, 1):
            if unified_job.stop_requested:
                unified_job.add_log("🟣 [สยามชัย] หยุดการค้นหาตามคำสั่ง")
                break

            with unified_job.lock:
                unified_job.sc_current_index = i
                unified_job.sc_current_cid = cid

            try:
                res = sc_crawler.search_one(cid)
            except Exception as e:
                res = {"สถานะ": f"Error: {e}", "ชื่อ-นามสกุล": "-"}

            with unified_job.lock:
                unified_job.sc_results[cid] = res

            name = res.get("ชื่อ-นามสกุล", "-")
            status = res.get("สถานะ", "-")
            unified_job.add_log(f"🟣 [สยามชัย {i}/{total}] เลข {cid}: {name} ({status})")

            # Stable natural pause between queries
            time.sleep(0.5)

    except Exception as e:
        unified_job.add_log(f"🟣 [สยามชัย] ❌ เกิดข้อผิดพลาด: {e}")
        with unified_job.lock:
            unified_job.sc_error = str(e)
            unified_job.sc_status = "error"
    finally:
        with unified_job.lock:
            if unified_job.sc_status != "error":
                unified_job.sc_status = "stopped" if unified_job.stop_requested else "done"

        # Generate Siamchai Excel immediately
        if unified_job.sc_results:
            try:
                rows = []
                for cid in cids:
                    if cid in unified_job.sc_results:
                        rows.append({"cid": cid, "siamchai": unified_job.sc_results[cid]})
                sc_file = save_siamchai_results_to_excel(rows, job_name="siamchai_results")
                with unified_job.lock:
                    unified_job.sc_excel_path = sc_file
                unified_job.add_log(f"🟣 [สยามชัย] 💾 บันทึกไฟล์ Excel สยามชัยเรียบร้อย: {os.path.basename(sc_file)} (พร้อมดาวน์โหลด)")
            except Exception as e:
                unified_job.add_log(f"🟣 [สยามชัย] ❌ สร้าง Excel สยามชัยไม่สำเร็จ: {e}")

        if sc_crawler:
            sc_crawler.close()
        with unified_job.lock:
            unified_job.siamchai_crawler = None


def true_worker(cids: List[str], headless: bool, cfg: dict):
    """
    Independent worker for TrueCorp: searches sequentially through CIDs at its own pace
    without waiting for Siamchai. Saves TrueCorp-specific Excel as soon as it finishes.
    """
    global unified_job
    tr_crawler = None
    try:
        tr_u = cfg.get("true_username", "")
        tr_p = cfg.get("true_password", "")
        if not tr_u or not tr_p:
            raise ValueError("ยังไม่ได้ระบุ Username / Password ของทรู")

        unified_job.add_log("🔴 [ทรู] กำลังเปิดเบราว์เซอร์และเข้าสู่ระบบ...")
        tr_crawler = TrueCrawler(
            username=tr_u,
            password=tr_p,
            headless=headless,
            log_callback=lambda m: unified_job.add_log(f"🔴 [ทรู] {m}")
        )
        with unified_job.lock:
            unified_job.true_crawler = tr_crawler
            unified_job.tr_status = "running"

        tr_crawler.login_and_prepare()
        unified_job.add_log("🔴 [ทรู] เข้าสู่ระบบพร้อมค้นหาข้อมูล!")

        total = len(cids)
        for i, cid in enumerate(cids, 1):
            if unified_job.stop_requested:
                unified_job.add_log("🔴 [ทรู] หยุดการค้นหาตามคำสั่ง")
                break

            with unified_job.lock:
                unified_job.tr_current_index = i
                unified_job.tr_current_cid = cid

            try:
                res = tr_crawler.search_one(cid)
            except Exception as e:
                res = {"status": f"Error: {e}", "active_count": 0, "active_phones": "-"}

            with unified_job.lock:
                unified_job.tr_results[cid] = res

            active_cnt = res.get("active_count", 0)
            active_phones = res.get("active_phones", "-")
            unified_job.add_log(f"🔴 [ทรู {i}/{total}] เลข {cid}: พบ {active_cnt} เบอร์ ({active_phones})")

            # Stable natural pause between queries
            time.sleep(0.5)

    except Exception as e:
        unified_job.add_log(f"🔴 [ทรู] ❌ เกิดข้อผิดพลาด: {e}")
        with unified_job.lock:
            unified_job.tr_error = str(e)
            unified_job.tr_status = "error"
    finally:
        with unified_job.lock:
            if unified_job.tr_status != "error":
                unified_job.tr_status = "stopped" if unified_job.stop_requested else "done"

        # Generate True Excel immediately
        if unified_job.tr_results:
            try:
                rows = []
                for cid in cids:
                    if cid in unified_job.tr_results:
                        rows.append({"cid": cid, "true": unified_job.tr_results[cid]})
                tr_file = save_true_results_to_excel(rows, job_name="true_results")
                with unified_job.lock:
                    unified_job.tr_excel_path = tr_file
                unified_job.add_log(f"🔴 [ทรู] 💾 บันทึกไฟล์ Excel ทรูเรียบร้อย: {os.path.basename(tr_file)} (พร้อมดาวน์โหลด)")
            except Exception as e:
                unified_job.add_log(f"🔴 [ทรู] ❌ สร้าง Excel ทรูไม่สำเร็จ: {e}")

        if tr_crawler:
            tr_crawler.close()
        with unified_job.lock:
            unified_job.true_crawler = None


def run_unified_process(
    cids: List[str],
    mode: str = "both",
    job_name: str = "search_job",
    headless: bool = True
):
    global unified_job
    cfg = load_config()

    with unified_job.lock:
        unified_job.job_id = f"job_{int(time.time())}"
        unified_job.job_name = job_name
        unified_job.mode = mode
        unified_job.status = "running"
        unified_job.total = len(cids)
        unified_job.cids = cids
        unified_job.logs = []
        unified_job.start_time = time.time()
        unified_job.end_time = None
        unified_job.stop_requested = False

        # Reset Siamchai state
        unified_job.sc_status = "starting" if mode in ["both", "siamchai"] else "idle"
        unified_job.sc_current_index = 0
        unified_job.sc_current_cid = ""
        unified_job.sc_results = {}
        unified_job.sc_excel_path = None
        unified_job.sc_error = None

        # Reset True state
        unified_job.tr_status = "starting" if mode in ["both", "true"] else "idle"
        unified_job.tr_current_index = 0
        unified_job.tr_current_cid = ""
        unified_job.tr_results = {}
        unified_job.tr_excel_path = None
        unified_job.tr_error = None

        unified_job.combined_excel_path = None

    unified_job.add_log(f"🚀 เริ่มต้นการค้นหาข้อมูล {len(cids)} รายการ (โหมด: {mode})")
    unified_job.add_log("⚡ ระบบทำงานแยกอิสระ (ของใครของมัน ไม่ต้องรอกัน)")

    threads = []
    if mode in ["both", "siamchai"]:
        t_sc = threading.Thread(target=siamchai_worker, args=(cids, headless, cfg), daemon=True)
        threads.append(t_sc)
        t_sc.start()

    if mode in ["both", "true"]:
        t_tr = threading.Thread(target=true_worker, args=(cids, headless, cfg), daemon=True)
        threads.append(t_tr)
        t_tr.start()

    # Wait for all running workers to finish
    for t in threads:
        t.join()

    # Mark overall job done/stopped
    with unified_job.lock:
        if unified_job.status != "error":
            unified_job.status = "stopped" if unified_job.stop_requested else "done"
        unified_job.end_time = time.time()

    # Create Combined 3-sheet Excel if any results exist
    if unified_job.sc_results or unified_job.tr_results:
        try:
            combined_rows = []
            for cid in cids:
                combined_rows.append({
                    "cid": cid,
                    "siamchai": unified_job.sc_results.get(cid, {}),
                    "true": unified_job.tr_results.get(cid, {})
                })
            cb_file = save_combined_results_to_excel(combined_rows, job_name="combined_results")
            with unified_job.lock:
                unified_job.combined_excel_path = cb_file
            unified_job.add_log(f"📊 💾 รวมผลลัพธ์ลงไฟล์ Excel รวม (3 Sheets) เรียบร้อย: {os.path.basename(cb_file)}")
        except Exception as e:
            unified_job.add_log(f"❌ สร้างไฟล์รวมไม่สำเร็จ: {e}")

    unified_job.add_log("🎉 กระบวนการทั้งหมดเสร็จสิ้น สามารถดาวน์โหลดไฟล์แยกตามระบบหรือไฟล์รวมได้ทันที!")
