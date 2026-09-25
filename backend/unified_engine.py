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
    def __init__(self, user: str = "admin", job_id: Optional[str] = None):
        self.lock = threading.Lock()
        self.job_id: str = job_id or f"job_{int(time.time())}_{user}"
        self.user: str = user
        self.job_name: str = "search_job"
        self.mode: str = "both"  # "both", "siamchai", "true"
        self.status: str = "idle"  # idle, queued, running, stopped, done, error
        self.queue_position: int = 0
        self.total: int = 0
        self.cids: List[str] = []
        self.headless: bool = True

        # Siamchai Worker State (Runs independently)
        self.sc_status: str = "idle"  # idle, starting, running, done, stopped, error
        self.sc_current_index: int = 0
        self.sc_current_cid: str = ""
        self.sc_results: Dict[str, Dict] = {}  # cid -> dict
        self.sc_excel_path: Optional[str] = None
        self.sc_error: Optional[str] = None

        # TrueCorp Worker State (Runs independently)
        self.tr_status: str = "idle"  # idle, starting, running, done, stopped, error
        self.tr_current_index: int = 0
        self.tr_current_cid: str = ""
        self.tr_results: Dict[str, Dict] = {}  # cid -> dict
        self.tr_excel_path: Optional[str] = None
        self.tr_error: Optional[str] = None

        # Combined Excel
        self.combined_excel_path: Optional[str] = None

        self.logs: List[str] = []
        self.created_at: float = time.time()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
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

            sc_found = sum(
                1 for r in self.sc_results.values()
                if r and r.get("สถานะ") not in ["ไม่พบข้อมูล", "Error", None] and r.get("ชื่อ-นามสกุล") not in ["-", "", None]
            )
            tr_found = sum(
                1 for r in self.tr_results.values()
                if r and (
                    r.get("total_count", 0) > 0 
                    or r.get("count", 0) > 0 
                    or r.get("active_count", 0) > 0 
                    or (r.get("all_phones") not in ["-", "", None]) 
                    or r.get("status") in ["สำเร็จ", "พบเบอร์ Active", "พบข้อมูล"]
                )
            )

            created_time_str = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(self.created_at))

            return {
                "job_id": self.job_id,
                "user": self.user,
                "job_name": self.job_name,
                "mode": self.mode,
                "status": self.status,
                "queue_position": self.queue_position,
                "created_at": self.created_at,
                "created_time_str": created_time_str,
                "total": self.total,
                "elapsed_seconds": elapsed,

                # Siamchai details
                "sc_status": self.sc_status,
                "sc_current_index": self.sc_current_index,
                "sc_percent": sc_pct,
                "sc_current_cid": self.sc_current_cid,
                "sc_count": len(self.sc_results),
                "sc_found_count": sc_found,
                "has_sc_excel": bool(self.sc_excel_path and os.path.exists(self.sc_excel_path)),
                "sc_excel_filename": os.path.basename(self.sc_excel_path) if self.sc_excel_path else None,
                "sc_error": self.sc_error,

                # True details
                "tr_status": self.tr_status,
                "tr_current_index": self.tr_current_index,
                "tr_percent": tr_pct,
                "tr_current_cid": self.tr_current_cid,
                "tr_count": len(self.tr_results),
                "tr_found_count": tr_found,
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


def siamchai_worker(job: UnifiedJobState, cids: List[str], headless: bool, cfg: dict):
    sc_crawler = None
    try:
        sc_u = cfg.get("siamchai_username", "")
        sc_p = cfg.get("siamchai_password", "")
        if not sc_u or not sc_p:
            raise ValueError("ยังไม่ได้ระบุ Username / Password ของสยามชัย")

        job.add_log("🟣 [สยามชัย] กำลังเปิดเบราว์เซอร์และเข้าสู่ระบบ...")
        sc_crawler = SiamchaiCrawler(
            username=sc_u,
            password=sc_p,
            headless=headless,
            log_callback=lambda m: job.add_log(f"🟣 [สยามชัย] {m}")
        )
        with job.lock:
            job.siamchai_crawler = sc_crawler
            job.sc_status = "running"

        sc_crawler.login_and_prepare()
        job.add_log("🟣 [สยามชัย] เข้าสู่ระบบพร้อมค้นหาข้อมูล!")

        total = len(cids)
        for i, cid in enumerate(cids, 1):
            if job.stop_requested:
                job.add_log("🟣 [สยามชัย] หยุดการค้นหาตามคำสั่ง")
                break

            with job.lock:
                job.sc_current_index = i
                job.sc_current_cid = cid

            res = None
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                if job.stop_requested:
                    break
                try:
                    # 1. Health check & session recovery before search
                    sc_crawler.recover_session_if_needed()

                    # 2. Search CID
                    res = sc_crawler.search_one(cid)

                    # If status indicates an internal error or dead driver, raise to trigger retry
                    st = str(res.get("สถานะ", ""))
                    if st.startswith("Error") or "invalid session id" in st.lower():
                        raise RuntimeError(st)

                    # Successful search completed
                    break

                except Exception as e:
                    err_msg = str(e)
                    is_fatal_driver_err = any(k in err_msg.lower() for k in [
                        "invalid session id", "no such window", "disconnected",
                        "target window already closed", "connection refused", "maxretryerror"
                    ])
                    if attempt < max_attempts and not job.stop_requested:
                        job.add_log(f"⚠️ [สยามชัย {i}/{total}] เลข {cid} ขัดข้อง ({err_msg[:60]}) -> กำลังรีเช็กใหม่อัตโนมัติ (ครั้งที่ {attempt+1}/{max_attempts})...")
                        if is_fatal_driver_err:
                            try:
                                sc_crawler.recover_driver_session()
                            except Exception as rec_e:
                                job.add_log(f"⚠️ รีสตาร์ทเบราว์เซอร์สยามชัยไม่สำเร็จ: {rec_e}")
                                time.sleep(3)
                        else:
                            try:
                                sc_crawler.ensure_back_to_search()
                            except Exception:
                                sc_crawler.recover_driver_session()
                        time.sleep(1.5)
                    else:
                        job.add_log(f"❌ [สยามชัย {i}/{total}] เลข {cid} ตรวจสอบครบ {max_attempts} ครั้งแล้ว: {err_msg[:80]}")
                        res = {"สถานะ": f"Error: {err_msg}", "ชื่อ-นามสกุล": "-"}

            if not res:
                res = {"สถานะ": "ไม่พบข้อมูล", "ชื่อ-นามสกุล": "-"}

            with job.lock:
                job.sc_results[cid] = res

            name = res.get("ชื่อ-นามสกุล", "-")
            status = res.get("สถานะ", "-")
            job.add_log(f"🟣 [สยามชัย {i}/{total}] เลข {cid}: {name} ({status})")
            time.sleep(0.6)

    except Exception as e:
        job.add_log(f"🟣 [สยามชัย] ❌ เกิดข้อผิดพลาด: {e}")
        with job.lock:
            job.sc_error = str(e)
            job.sc_status = "error"
    finally:
        with job.lock:
            if job.sc_status != "error":
                job.sc_status = "stopped" if job.stop_requested else "done"

        # Generate Siamchai Excel immediately
        if job.sc_results:
            try:
                rows = []
                for cid in cids:
                    if cid in job.sc_results:
                        rows.append({"cid": cid, "siamchai": job.sc_results[cid]})
                sc_file = save_siamchai_results_to_excel(rows, job_name=f"siamchai_{job.user}")
                with job.lock:
                    job.sc_excel_path = sc_file
                job.add_log(f"🟣 [สยามชัย] 💾 บันทึกไฟล์ Excel สยามชัยเรียบร้อย: {os.path.basename(sc_file)} (พร้อมดาวน์โหลด)")
            except Exception as e:
                job.add_log(f"🟣 [สยามชัย] ❌ สร้าง Excel สยามชัยไม่สำเร็จ: {e}")

        if sc_crawler:
            sc_crawler.close()
        with job.lock:
            job.siamchai_crawler = None


def true_worker(job: UnifiedJobState, cids: List[str], headless: bool, cfg: dict):
    tr_crawler = None
    try:
        tr_u = cfg.get("true_username", "")
        tr_p = cfg.get("true_password", "")
        if not tr_u or not tr_p:
            raise ValueError("ยังไม่ได้ระบุ Username / Password ของทรู")

        job.add_log("🔴 [ทรู] กำลังเปิดเบราว์เซอร์และเข้าสู่ระบบ...")
        tr_crawler = TrueCrawler(
            username=tr_u,
            password=tr_p,
            headless=headless,
            log_callback=lambda m: job.add_log(f"🔴 [ทรู] {m}")
        )
        with job.lock:
            job.true_crawler = tr_crawler
            job.tr_status = "running"

        tr_crawler.login_and_prepare()
        job.add_log("🔴 [ทรู] เข้าสู่ระบบพร้อมค้นหาข้อมูล!")

        total = len(cids)
        for i, cid in enumerate(cids, 1):
            if job.stop_requested:
                job.add_log("🔴 [ทรู] หยุดการค้นหาตามคำสั่ง")
                break

            with job.lock:
                job.tr_current_index = i
                job.tr_current_cid = cid

            res = None
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                if job.stop_requested:
                    break
                try:
                    # Health check: if driver dead or None, recover
                    if not tr_crawler.driver:
                        tr_crawler.create_driver()
                        tr_crawler.login_and_prepare()

                    res = tr_crawler.search_one(cid)
                    st = str(res.get("status", ""))
                    if st.startswith("Error") or "invalid session id" in st.lower():
                        raise RuntimeError(st)

                    break

                except Exception as e:
                    err_msg = str(e)
                    is_fatal_driver_err = any(k in err_msg.lower() for k in [
                        "invalid session id", "no such window", "disconnected",
                        "target window already closed", "connection refused", "maxretryerror"
                    ])
                    if attempt < max_attempts and not job.stop_requested:
                        job.add_log(f"⚠️ [ทรู {i}/{total}] เลข {cid} ขัดข้อง ({err_msg[:60]}) -> กำลังรีเช็กใหม่อัตโนมัติ (ครั้งที่ {attempt+1}/{max_attempts})...")
                        if is_fatal_driver_err:
                            try:
                                tr_crawler.create_driver()
                                tr_crawler.login_and_prepare()
                            except Exception as rec_e:
                                job.add_log(f"⚠️ รีสตาร์ทเบราว์เซอร์ทรูไม่สำเร็จ: {rec_e}")
                                time.sleep(3)
                        time.sleep(1.5)
                    else:
                        job.add_log(f"❌ [ทรู {i}/{total}] เลข {cid} ตรวจสอบครบ {max_attempts} ครั้งแล้ว: {err_msg[:80]}")
                        res = {
                            "cid": cid,
                            "name": "-",
                            "status": f"Error: {err_msg}",
                            "total_count": 0,
                            "count": 0,
                            "all_phones": "-",
                            "active_count": 0,
                            "active_phones": "-",
                            "phone_details": "-",
                            "details": []
                        }

            if not res:
                res = {
                    "cid": cid,
                    "name": "-",
                    "status": "ไม่พบข้อมูล",
                    "total_count": 0,
                    "count": 0,
                    "all_phones": "-",
                    "active_count": 0,
                    "active_phones": "-",
                    "phone_details": "-",
                    "details": []
                }

            with job.lock:
                job.tr_results[cid] = res

            total_cnt = res.get("total_count", res.get("count", 0))
            all_phones = res.get("all_phones", "-")
            active_cnt = res.get("active_count", 0)
            job.add_log(f"🔴 [ทรู {i}/{total}] เลข {cid}: พบ {total_cnt} เบอร์ ({all_phones}) [Active: {active_cnt}]")
            time.sleep(0.6)

    except Exception as e:
        job.add_log(f"🔴 [ทรู] ❌ เกิดข้อผิดพลาด: {e}")
        with job.lock:
            job.tr_error = str(e)
            job.tr_status = "error"
    finally:
        with job.lock:
            if job.tr_status != "error":
                job.tr_status = "stopped" if job.stop_requested else "done"

        # Generate True Excel immediately
        if job.tr_results:
            try:
                rows = []
                for cid in cids:
                    if cid in job.tr_results:
                        rows.append({"cid": cid, "true": job.tr_results[cid]})
                tr_file = save_true_results_to_excel(rows, job_name=f"true_{job.user}")
                with job.lock:
                    job.tr_excel_path = tr_file
                job.add_log(f"🔴 [ทรู] 💾 บันทึกไฟล์ Excel ทรูเรียบร้อย: {os.path.basename(tr_file)} (พร้อมดาวน์โหลด)")
            except Exception as e:
                job.add_log(f"🔴 [ทรู] ❌ สร้าง Excel ทรูไม่สำเร็จ: {e}")

        if tr_crawler:
            tr_crawler.close()
        with job.lock:
            job.true_crawler = None


class JobQueueManager:
    """
    Multi-tenant Concurrent Job Manager:
    Allows each user to run their own search jobs independently and simultaneously.
    No waiting in queue across different users.
    Each user runs their own headless browser instances with isolated profiles.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: Dict[str, UnifiedJobState] = {}
        # Track active job ID per user (user_lower -> job_id)
        self.user_active_jobs: Dict[str, str] = {}
        # Track active worker threads per job_id
        self.active_threads: Dict[str, threading.Thread] = {}

    def submit_job(
        self,
        user: str,
        cids: List[str],
        mode: str = "both",
        job_name: str = "search_job",
        headless: bool = True
    ) -> UnifiedJobState:
        with self.lock:
            user_key = user.strip().lower()

            # Prevent double click on the same user account while actively running
            if user_key in self.user_active_jobs:
                existing_id = self.user_active_jobs[user_key]
                existing = self.jobs.get(existing_id)
                if existing and existing.status in ["running", "starting"]:
                    raise ValueError(
                        f"บัญชี '{user}' กำลังมีงานค้นหากำลังทำงานอยู่ ({existing.total} รายการ) "
                        "กรุณารอให้งานเดิมเสร็จสิ้น หรือกดปุ่ม 'หยุดการทำงาน' ก่อนเริ่มงานใหม่"
                    )

            job_id = f"job_{int(time.time())}_{user}"
            job = UnifiedJobState(user=user, job_id=job_id)
            job.job_name = job_name
            job.mode = mode
            job.cids = cids
            job.total = len(cids)
            job.headless = headless
            job.created_at = time.time()
            job.status = "starting"
            job.queue_position = 0

            self.jobs[job_id] = job
            self.user_active_jobs[user_key] = job_id

            job.add_log(f"🚀 เริ่มค้นหาข้อมูล {len(cids)} รายการ (โหมด: {mode}) โดยผู้ใช้: {user}")
            job.add_log("⚡ ระบบประมวลผลแยกอิสระทันที (Concurrent Mode - ไม่ต้องรอคิวใคร)")

            # Launch dedicated worker thread for this job immediately!
            t = threading.Thread(target=self._run_job_wrapper, args=(job,), daemon=True)
            self.active_threads[job_id] = t
            t.start()

            return job

    def _run_job_wrapper(self, job: UnifiedJobState):
        try:
            self._execute_job(job)
        except Exception as e:
            job.add_log(f"❌ เกิดข้อผิดพลาดในการประมวลผลงาน: {e}")
            with job.lock:
                job.status = "error"
        finally:
            with self.lock:
                if job.job_id in self.active_threads:
                    del self.active_threads[job.job_id]

    def get_user_current_job(self, user: str) -> UnifiedJobState:
        with self.lock:
            user_key = user.strip().lower()

            # 1. Currently active or most recent job for this user
            if user_key in self.user_active_jobs:
                act_id = self.user_active_jobs[user_key]
                if act_id in self.jobs:
                    return self.jobs[act_id]

            # 2. Latest job submitted by this user
            user_jobs = [j for j in self.jobs.values() if j.user.strip().lower() == user_key]
            if user_jobs:
                user_jobs.sort(key=lambda j: j.created_at, reverse=True)
                return user_jobs[0]

            # 3. Default idle state
            return UnifiedJobState(user=user)

    def get_job_by_id(self, job_id: str) -> Optional[UnifiedJobState]:
        with self.lock:
            return self.jobs.get(job_id)

    def get_user_jobs_history(self, user: str, limit: int = 40) -> List[Dict]:
        with self.lock:
            if user.strip().lower() == "admin":
                # Admin can see all jobs across all users
                jobs = list(self.jobs.values())
            else:
                jobs = [j for j in self.jobs.values() if j.user.strip().lower() == user.strip().lower()]

            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return [j.to_dict() for j in jobs[:limit]]

    def stop_job(self, user: str, job_id: Optional[str] = None) -> bool:
        with self.lock:
            target_job = None
            if job_id and job_id in self.jobs:
                target_job = self.jobs[job_id]
            else:
                user_key = user.strip().lower()
                if user_key in self.user_active_jobs:
                    act_id = self.user_active_jobs[user_key]
                    if act_id in self.jobs:
                        target_job = self.jobs[act_id]

            if not target_job:
                return False

            # Check permissions: user can stop their own job, admin can stop any
            is_admin = (user.strip().lower() == "admin")
            is_owner = (target_job.user.strip().lower() == user.strip().lower())
            if not is_admin and not is_owner:
                return False

            if target_job.status in ["running", "starting"]:
                target_job.stop_requested = True
                if target_job.siamchai_crawler:
                    target_job.siamchai_crawler.stop_requested = True
                if target_job.true_crawler:
                    target_job.true_crawler.stop_requested = True
                target_job.add_log(f"🛑 ได้รับคำสั่งหยุดการทำงานจาก {user}...")
                return True

            return False

    def _execute_job(self, job: UnifiedJobState):
        cfg = load_config()
        cids = job.cids
        mode = job.mode
        headless = job.headless

        with job.lock:
            job.status = "running"
            job.queue_position = 0
            job.start_time = time.time()
            job.end_time = None
            job.stop_requested = False

            # Reset Siamchai state
            job.sc_status = "starting" if mode in ["both", "siamchai"] else "idle"
            job.sc_current_index = 0
            job.sc_current_cid = ""
            job.sc_results = {}
            job.sc_excel_path = None
            job.sc_error = None

            # Reset True state
            job.tr_status = "starting" if mode in ["both", "true"] else "idle"
            job.tr_current_index = 0
            job.tr_current_cid = ""
            job.tr_results = {}
            job.tr_excel_path = None
            job.tr_error = None

            job.combined_excel_path = None

        job.add_log(f"🚀 เริ่มค้นหาข้อมูล {len(cids)} รายการ (โหมด: {mode}) สำหรับผู้ใช้: {job.user}")
        job.add_log("⚡ ระบบทำงานแยกอิสระ (ของใครของมัน ไม่ต้องรอกัน)")

        threads = []
        if mode in ["both", "siamchai"]:
            t_sc = threading.Thread(target=siamchai_worker, args=(job, cids, headless, cfg), daemon=True)
            threads.append(t_sc)
            t_sc.start()

        if mode in ["both", "true"]:
            t_tr = threading.Thread(target=true_worker, args=(job, cids, headless, cfg), daemon=True)
            threads.append(t_tr)
            t_tr.start()

        # Wait for all running workers to finish
        for t in threads:
            t.join()

        # Mark overall job done/stopped
        with job.lock:
            all_selected_errored = (
                (mode == "both" and job.sc_status == "error" and job.tr_status == "error") or
                (mode == "siamchai" and job.sc_status == "error") or
                (mode == "true" and job.tr_status == "error")
            )
            if all_selected_errored:
                job.status = "error"
                job.add_log("❌ กระบวนการทำงานหยุดลงเนื่องจากเกิดข้อผิดพลาดในการเริ่มต้นระบบ")
            elif job.stop_requested:
                job.status = "stopped"
            else:
                job.status = "done"
            job.end_time = time.time()

        # Create Combined 3-sheet Excel if any results exist
        if job.sc_results or job.tr_results:
            try:
                combined_rows = []
                for cid in cids:
                    combined_rows.append({
                        "cid": cid,
                        "siamchai": job.sc_results.get(cid, {}),
                        "true": job.tr_results.get(cid, {})
                    })
                cb_file = save_combined_results_to_excel(combined_rows, job_name=f"combined_{job.user}")
                with job.lock:
                    job.combined_excel_path = cb_file
                job.add_log(f"📊 💾 รวมผลลัพธ์ลงไฟล์ Excel รวม (3 Sheets) เรียบร้อย: {os.path.basename(cb_file)}")
            except Exception as e:
                job.add_log(f"❌ สร้างไฟล์รวมไม่สำเร็จ: {e}")

        job.add_log("🎉 กระบวนการทั้งหมดเสร็จสิ้น สามารถดาวน์โหลดไฟล์แยกตามระบบหรือไฟล์รวมได้ทันที!")


# Global Job Queue Manager Singleton
job_manager = JobQueueManager()

# Legacy compatibility export
unified_job = UnifiedJobState()
