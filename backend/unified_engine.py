import time
import os
import threading
from typing import List, Dict, Optional
from backend.siamchai_crawler import SiamchaiCrawler
from backend.true_crawler import TrueCrawler
from backend.storage import save_combined_results_to_excel, load_config

class UnifiedJobState:
    def __init__(self):
        self.lock = threading.Lock()
        self.job_id: Optional[str] = None
        self.job_name: str = "unified_extract"
        self.mode: str = "both" # "both", "siamchai", "true"
        self.status: str = "idle" # idle, running, stopped, done, error
        self.current_index: int = 0
        self.total: int = 0
        self.current_cid: str = ""
        self.results: List[Dict] = []
        self.logs: List[str] = []
        self.excel_path: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.error_message: Optional[str] = None
        self.stop_requested: bool = False

        self.siamchai_crawler: Optional[SiamchaiCrawler] = None
        self.true_crawler: Optional[TrueCrawler] = None

    def add_log(self, msg: str):
        with self.lock:
            ts = time.strftime("%H:%M:%S")
            self.logs.append(f"[{ts}] {msg}")
            if len(self.logs) > 300:
                self.logs.pop(0)

    def to_dict(self):
        with self.lock:
            percent = 0
            if self.total > 0:
                percent = int((self.current_index / self.total) * 100)
            elapsed = 0
            if self.start_time:
                end = self.end_time or time.time()
                elapsed = int(end - self.start_time)

            return {
                "job_id": self.job_id,
                "job_name": self.job_name,
                "mode": self.mode,
                "status": self.status,
                "current_index": self.current_index,
                "total": self.total,
                "percent": percent,
                "current_cid": self.current_cid,
                "results_count": len(self.results),
                "recent_results": self.results[-15:],
                "logs": self.logs[-40:],
                "has_excel": bool(self.excel_path and os.path.exists(self.excel_path)),
                "excel_filename": os.path.basename(self.excel_path) if self.excel_path else None,
                "elapsed_seconds": elapsed,
                "error_message": self.error_message,
            }

unified_job = UnifiedJobState()

def run_unified_process(
    cids: List[str],
    mode: str = "both",
    job_name: str = "unified_search",
    headless: bool = True
):
    global unified_job
    cfg = load_config()

    with unified_job.lock:
        unified_job.job_id = f"job_{int(time.time())}"
        unified_job.job_name = job_name
        unified_job.mode = mode
        unified_job.status = "running"
        unified_job.current_index = 0
        unified_job.total = len(cids)
        unified_job.current_cid = ""
        unified_job.results = []
        unified_job.logs = []
        unified_job.excel_path = None
        unified_job.start_time = time.time()
        unified_job.end_time = None
        unified_job.error_message = None
        unified_job.stop_requested = False

    unified_job.add_log(f"🚀 เริ่มกระบวนการค้นหาข้อมูล {len(cids)} รายการ (โหมด: {mode})")

    # 1. Initialize Crawlers
    sc_crawler = None
    tr_crawler = None

    try:
        if mode in ["both", "siamchai"]:
            sc_u = cfg.get("siamchai_username", "")
            sc_p = cfg.get("siamchai_password", "")
            if not sc_u or not sc_p:
                raise ValueError("ยังไม่ได้กำหนด Username / Password ของสยามชัย")
            sc_crawler = SiamchaiCrawler(
                username=sc_u,
                password=sc_p,
                headless=headless,
                log_callback=unified_job.add_log
            )
            unified_job.siamchai_crawler = sc_crawler
            sc_crawler.login_and_prepare()

        if mode in ["both", "true"]:
            tr_u = cfg.get("true_username", "")
            tr_p = cfg.get("true_password", "")
            if not tr_u or not tr_p:
                raise ValueError("ยังไม่ได้กำหนด Username / Password ของทรู")
            tr_crawler = TrueCrawler(
                username=tr_u,
                password=tr_p,
                headless=headless,
                log_callback=unified_job.add_log
            )
            unified_job.true_crawler = tr_crawler
            tr_crawler.login_and_prepare()

        unified_job.add_log("✨ ทุกระบบเชื่อมต่อพร้อมทำงานแล้ว เริ่มค้นหาข้อมูล...")

        # 2. Iterate CIDs
        total = len(cids)
        for i, cid in enumerate(cids, 1):
            if unified_job.stop_requested:
                unified_job.add_log("🛑 การทำงานถูกหยุดโดยผู้ใช้")
                break

            cid_str = str(cid).strip()
            if not cid_str:
                continue

            with unified_job.lock:
                unified_job.current_index = i
                unified_job.current_cid = cid_str

            unified_job.add_log(f"[{i}/{total}] ค้นหาเลขบัตร: {cid_str}...")

            row_data = {
                "cid": cid_str,
                "siamchai": {},
                "true": {}
            }

            # Helper functions to run single search
            def do_sc():
                if sc_crawler:
                    try:
                        row_data["siamchai"] = sc_crawler.search_one(cid_str)
                    except Exception as e:
                        row_data["siamchai"] = {"สถานะ": f"Error: {e}", "ชื่อ-นามสกุล": "-"}

            def do_tr():
                if tr_crawler:
                    try:
                        row_data["true"] = tr_crawler.search_one(cid_str)
                    except Exception as e:
                        row_data["true"] = {"status": f"Error: {e}", "active_count": 0, "active_phones": "-"}

            # Concurrency: Run both simultaneously if mode is "both"
            if mode == "both":
                t1 = threading.Thread(target=do_sc)
                t2 = threading.Thread(target=do_tr)
                t1.start()
                t2.start()
                t1.join()
                t2.join()
            elif mode == "siamchai":
                do_sc()
            elif mode == "true":
                do_tr()

            # Summary log
            sc_res = row_data["siamchai"]
            tr_res = row_data["true"]
            summary_parts = []
            if sc_crawler:
                summary_parts.append(f"สยามชัย: {sc_res.get('ชื่อ-นามสกุล', '-')} ({sc_res.get('สถานะ', '-')})")
            if tr_crawler:
                summary_parts.append(f"ทรู: {tr_res.get('active_count', 0)} เบอร์")

            unified_job.add_log(f"[{i}/{total}] ผลลัพธ์: {' | '.join(summary_parts)}")

            with unified_job.lock:
                unified_job.results.append(row_data)

            time.sleep(0.5)

        # 3. Save to Excel
        if unified_job.results:
            unified_job.add_log("📊 กำลังสร้างไฟล์ Excel รวมทุกระบบ (3 Sheets)...")
            filepath = save_combined_results_to_excel(unified_job.results, job_name=unified_job.job_name)
            with unified_job.lock:
                unified_job.excel_path = filepath
            unified_job.add_log(f"🎉 เสร็จสมบูรณ์! บันทึกไฟล์ที่: {os.path.basename(filepath)}")

    except Exception as e:
        unified_job.add_log(f"❌ เกิดข้อผิดพลาดร้ายแรง: {e}")
        with unified_job.lock:
            unified_job.error_message = str(e)
            unified_job.status = "error"
    finally:
        with unified_job.lock:
            if unified_job.status != "error":
                unified_job.status = "stopped" if unified_job.stop_requested else "done"
            unified_job.end_time = time.time()

        if sc_crawler:
            sc_crawler.close()
        if tr_crawler:
            tr_crawler.close()

        with unified_job.lock:
            unified_job.siamchai_crawler = None
            unified_job.true_crawler = None
