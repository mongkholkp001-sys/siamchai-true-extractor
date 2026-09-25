import os
import re
import time
import tempfile
import shutil
import threading
from typing import Dict, List, Optional, Callable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

LOGIN_URL = "https://secure2021-web.siamchai.net/signin/g_8JBhzikdZcuatJaW2QZoKDfmkPszpY#/"
INSPECTION_URL = "https://secure2021-web.siamchai.net/#/installment/inspection"

OUTPUT_COLUMNS = [
    "เลขบัตรที่ใช้ค้นหา", "ชื่อ-นามสกุล", "สถานะ",
    "เลขบัตรประชาชนผู้เช่าซื้อ", "ชื่อ-นามสกุลผู้เช่าซื้อ", "เบอร์โทรผู้เช่าซื้อ",
    "ที่อยู่ตามบัตรประชาชนผู้เช่าซื้อ", "ที่อยู่ปัจจุบันผู้เช่าซื้อ",
    "ที่อยู่ที่ทำงานผู้เช่าซื้อ", "เบอร์โทรที่ทำงาน", "ตำแหน่ง",
    "เลขบัตรประชาชนผู้ค้ำ", "ชื่อ-นามสกุลผู้ค้ำ", "เบอร์โทรผู้ค้ำ",
    "ความสัมพันธ์", "ที่อยู่ผู้ค้ำ", "ที่ทำงานผู้ค้ำ"
]

class SiamchaiCrawler:
    def __init__(
        self,
        username: str,
        password: str,
        headless: bool = True,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int, int, Dict], None]] = None,
    ):
        self.username = username
        self.password = password
        self.headless = headless
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.driver: Optional[webdriver.Chrome] = None
        self.profile_dir: Optional[str] = None
        self.is_running = False
        self.stop_requested = False
        self.last_screenshot_bytes: Optional[bytes] = None
        self.lock = threading.Lock()
        self.last_draft_info = ("", "")

    def log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(f"[Siamchai] {msg}")

    def capture_screen(self):
        if not self.driver:
            return
        try:
            png = self.driver.get_screenshot_as_png()
            with self.lock:
                self.last_screenshot_bytes = png
        except Exception:
            pass

    def get_screenshot_bytes(self) -> Optional[bytes]:
        with self.lock:
            return self.last_screenshot_bytes

    def find_browser(self):
        # 1. Linux candidates (Render, Docker, VPS)
        if os.name != "nt":
            render_chrome = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
            if os.path.exists(render_chrome):
                return "chrome", render_chrome

            for binary in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
                p = shutil.which(binary)
                if p:
                    return "chrome", p
            for p in ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser"]:
                if os.path.exists(p):
                    return "chrome", p

        # 2. Windows candidates
        candidates = [
            ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            ("chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            ("chrome", os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
            ("brave", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ("edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            ("edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        ]
        for name, p in candidates:
            if os.path.exists(p):
                return name, p
        return "chrome", None

    def create_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        if self.profile_dir and os.path.exists(self.profile_dir):
            try:
                shutil.rmtree(self.profile_dir, ignore_errors=True)
            except Exception:
                pass
            self.profile_dir = None

        engine, browser_path = self.find_browser()
        self.profile_dir = tempfile.mkdtemp(prefix="siamchai_hub_profile_")

        args = [
            "--disable-notifications",
            "--disable-popup-blocking",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-dev-shm-usage",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.profile_dir}",
            "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled",
            "--blink-settings=imagesEnabled=false",
            "--disable-extensions",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        if os.name != "nt":
            args.extend(["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])

        if self.headless or os.name != "nt":
            args.extend(["--headless=new"])

        if engine == "edge":
            options = webdriver.EdgeOptions()
            if browser_path:
                options.binary_location = browser_path
            for a in args:
                options.add_argument(a)
            self.driver = webdriver.Edge(options=options)
        else:
            options = webdriver.ChromeOptions()
            if browser_path:
                options.binary_location = browser_path
            for a in args:
                options.add_argument(a)

            driver_path = shutil.which("chromedriver") or ("/usr/bin/chromedriver" if os.path.exists("/usr/bin/chromedriver") else None)
            if driver_path:
                from selenium.webdriver.chrome.service import Service
                self.driver = webdriver.Chrome(service=Service(driver_path), options=options)
            else:
                self.driver = webdriver.Chrome(options=options)

        self.driver.set_page_load_timeout(45)
        self.driver.implicitly_wait(2)

    def is_loading_overlay_active(self) -> bool:
        if not self.driver:
            return False
        loader_selectors = [
            ".k-loading-mask",
            ".k-loading-image",
            ".k-loading-color",
            ".loading-spinner",
            ".spinner-border",
            ".blockOverlay",
            "div.loading",
            "div.spinner",
            "#loading-img",
            "#loading-spinner",
        ]
        for sel in loader_selectors:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        sz = el.size
                        if sz.get("width", 0) > 8 and sz.get("height", 0) > 8:
                            return True
            except Exception:
                pass
        return False

    def recover_driver_session(self):
        self.log("🔄 กำลังรีสตาร์ทเบราว์เซอร์สยามชัยและเชื่อมต่อระบบใหม่อัตโนมัติ...")
        self.close()
        time.sleep(2)
        self.login_and_prepare()

    def recover_session_if_needed(self) -> bool:
        if not self.driver:
            self.recover_driver_session()
            return True
        try:
            _ = self.driver.current_url
        except Exception:
            self.recover_driver_session()
            return True

        # 1) Check for session timeout popup
        timeout_detected = False
        try:
            popups = self.driver.find_elements(
                By.XPATH,
                '//*[contains(text(),"ขาดการติดต่อ") or contains(text(),"หมดอายุ") or contains(text(),"Session Timeout")]'
            )
            if any(p.is_displayed() for p in popups):
                timeout_detected = True
                self.log("⚠️ ตรวจพบแจ้งเตือนเซสชันขาดการติดต่อ! กำลังล็อกอินใหม่อัตโนมัติ...")
        except Exception:
            pass

        if timeout_detected:
            self.dismiss_popups(timeout=2)
            time.sleep(1)
            self.ensure_login_and_inspection()
            return True

        # 2) Check if redirected back to signin page
        try:
            curr_url = self.driver.current_url.lower()
            if "signin" in curr_url or "login" in curr_url:
                self.log("⚠️ ตรวจพบหลุดกลับหน้าล็อกอิน! กำลังเข้าสู่ระบบใหม่อัตโนมัติ...")
                self.ensure_login_and_inspection()
                return True
        except Exception:
            pass

        return False

    def ensure_login_and_inspection(self):
        try:
            if not self.driver:
                self.login_and_prepare()
                return True
            curr = self.driver.current_url.lower()
            if "signin" in curr or "login" in curr:
                self.perform_login_step()
                time.sleep(3)
                self.dismiss_popups(timeout=2)
            self.ensure_inspection_page()
            return True
        except Exception as e:
            self.log(f"พยายามล็อกอินใหม่อัตโนมัติ: {e} -> ทำการรีสตาร์ทเบราว์เซอร์ใหม่")
            self.recover_driver_session()
            return True

    def clear_search_input(self):
        try:
            inputs = self.driver.find_elements(By.ID, "cus_nation_id")
            if inputs:
                inp = inputs[0]
                inp.click()
                inp.send_keys(Keys.CONTROL, "a")
                inp.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)
                inp.send_keys(Keys.TAB)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles:true})); arguments[0].blur();", inp)
        except Exception:
            pass
        time.sleep(0.3)

    def js_click(self, el):
        try:
            self.driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False

    def close_dialog_if_open(self):
        try:
            candidates = self.driver.find_elements(
                By.CSS_SELECTOR,
                '.dialog-screen.show .flaticon-close47, .dialog .close, .dialog a.flex-button, span.flaticon-close47, .flaticon-close47'
            )
            for c in candidates:
                if c.is_displayed():
                    self.js_click(c)
                    time.sleep(0.3)
                    return True
        except Exception:
            pass

        try:
            for el in self.driver.find_elements(By.XPATH, '//*[normalize-space()="ปิด"]'):
                if el.is_displayed():
                    self.js_click(el)
                    time.sleep(0.3)
                    return True
        except Exception:
            pass
        return False

    def dismiss_popups(self, timeout=3):
        end = time.time() + timeout
        while time.time() < end:
            try:
                candidates = self.driver.find_elements(
                    By.XPATH,
                    '//span[contains(@class,"label") and (contains(text(),"รับทราบ") or contains(text(),"ตกลง") or contains(text(),"ปิด"))]/ancestor::a[1] | '
                    '//*[self::a or self::button][.//*[contains(text(),"รับทราบ") or contains(text(),"ตกลง") or contains(text(),"ปิด")] or contains(text(),"รับทราบ") or contains(text(),"ตกลง") or contains(text(),"ปิด")]'
                )
                for c in candidates:
                    if c.is_displayed():
                        self.js_click(c)
                        time.sleep(0.8)
                        self.capture_screen()
                        return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def perform_login_step(self):
        self.dismiss_popups(1.0)
        wait = WebDriverWait(self.driver, 12)
        u_in = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#user, input#user, input[type="text"]')))
        p_in = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#pass, input#pass, input[type="password"]')))

        u_in.click()
        u_in.clear()
        u_in.send_keys(str(self.username))
        time.sleep(0.15)

        p_in.click()
        p_in.clear()
        p_in.send_keys(str(self.password))
        time.sleep(0.2)
        p_in.send_keys(Keys.ENTER)  # Validates and activates the button in React
        time.sleep(0.5)

        btns = self.driver.find_elements(
            By.XPATH,
            '//span[normalize-space()="เข้าสู่ระบบ"]/ancestor::a[1] | '
            '//*[self::a or self::button][normalize-space()="เข้าสู่ระบบ"]'
        )
        if btns:
            try:
                ActionChains(self.driver).move_to_element(btns[0]).click().perform()
            except Exception:
                self.js_click(btns[0])

    def ensure_inspection_page(self):
        try:
            el = self.driver.find_element(By.ID, "cus_nation_id")
            if el.is_displayed():
                return True
        except Exception:
            pass

        # 1. Open favorite/module icon
        for sel in ["div.icon.flaticon-favorite22", ".flaticon-favorite22", "#module-panel .icon"]:
            for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    self.js_click(el)
                    time.sleep(1.2)
                    break

        # 2. Click 'เงินผ่อน'
        for el in self.driver.find_elements(By.XPATH, '//*[normalize-space()="เงินผ่อน"]'):
            if el.is_displayed():
                self.js_click(el)
                time.sleep(1.5)
                break

        # 3. Click 'ตรวจสอบประวัติ'
        for el in self.driver.find_elements(By.XPATH, '//*[normalize-space()="ตรวจสอบประวัติ"]'):
            if el.is_displayed():
                self.js_click(el)
                time.sleep(2)
                break

        # 4. Wait for cus_nation_id
        try:
            WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.ID, "cus_nation_id")))
            return True
        except Exception:
            pass

        # Direct navigation fallback
        try:
            self.driver.get(INSPECTION_URL)
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "cus_nation_id")))
            return True
        except Exception:
            return False

    def login_and_prepare(self):
        self.create_driver()
        self.log("กำลังเปิดหน้า Login สยามชัย...")
        self.driver.get(LOGIN_URL)
        time.sleep(2)
        self.dismiss_popups(timeout=2)

        # Round 1
        self.log(f"เข้าสู่ระบบสยามชัยด้วยรหัส {self.username}...")
        self.perform_login_step()
        time.sleep(3.5)

        # Handle session timeout popup ("ขาดการติดต่อนานเกินไป กรุณาเข้าสู่ระบบใหม่อีกครั้ง")
        if "signin" not in self.driver.current_url:
            self.dismiss_popups(timeout=2)
            time.sleep(1.5)

        # If redirected back to signin (due to previous session invalidation)
        if "signin" in self.driver.current_url:
            self.log("กำลังเชื่อมต่อเซสชันสยามชัยรอบที่ 2...")
            self.perform_login_step()
            time.sleep(3.5)

        self.ensure_inspection_page()
        self.capture_screen()
        self.log("✅ สยามชัยเข้าสู่ระบบและพร้อมค้นหาข้อมูลแล้ว")

    def ensure_back_to_search(self):
        try:
            inputs = self.driver.find_elements(By.ID, "cus_nation_id")
            if inputs and inputs[0].is_displayed():
                self.close_dialog_if_open()
                return True
        except Exception:
            pass

        for sel in ["div.act-back", ".act-back", '//*[normalize-space()="ย้อนกลับ"]']:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        self.js_click(el)
                        time.sleep(0.8)
                        break
            except Exception:
                pass

        for el in self.driver.find_elements(By.XPATH, '//*[self::a or self::span or self::div][normalize-space()="ตรวจสอบประวัติ"]'):
            try:
                if el.is_displayed():
                    self.js_click(el)
                    time.sleep(0.8)
                    break
            except Exception:
                pass

        self.close_dialog_if_open()
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "cus_nation_id")))
            return True
        except Exception:
            pass

        try:
            self.driver.get(INSPECTION_URL)
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "cus_nation_id")))
            return True
        except Exception:
            return False

    def enter_search_cid(self, cid: str):
        wait = WebDriverWait(self.driver, 12)
        inp = wait.until(EC.presence_of_element_located((By.ID, "cus_nation_id")))
        try:
            inp.click()
        except Exception:
            self.js_click(inp)
        inp.send_keys(Keys.CONTROL, "a")
        inp.send_keys(Keys.BACKSPACE)
        time.sleep(0.1)
        inp.send_keys(str(cid))
        time.sleep(0.15)
        inp.send_keys(Keys.ENTER)
        inp.send_keys(Keys.TAB)
        try:
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true})); arguments[0].dispatchEvent(new Event('change', {bubbles:true})); arguments[0].blur();", inp)
        except Exception:
            pass
        time.sleep(0.6)

    def wait_search_result(self, timeout=12):
        start_time = time.time()
        end_time = start_time + timeout
        empty_since = None
        loader_seen = False
        self.last_draft_info = ("", "")

        while time.time() < end_time:
            if self.stop_requested:
                return "STOP"

            self.recover_session_if_needed()

            # Check loading spinner / overlay
            if self.is_loading_overlay_active():
                loader_seen = True
                empty_since = None
                time.sleep(0.2)
                continue

            # 1. Check draft popup
            try:
                for el in self.driver.find_elements(By.XPATH, '//*[contains(normalize-space(),"ร่างสัญญา")]'):
                    if el.is_displayed():
                        txt = el.text.strip()
                        id_m = re.search(r"เลขที่บัตรประชาชน\s*(\d+)", txt)
                        nm_m = re.search(r"ชื่อ\s*([^\s]+(?:\s+[^\s]+)*?)\s*ใช่ไหม", txt)
                        self.last_draft_info = (id_m.group(1) if id_m else "", nm_m.group(1) if nm_m else "")
                        return "DRAFT"
            except Exception:
                pass

            # Close any unwanted dialog
            self.close_dialog_if_open()

            # 2. Check table rows (Real rows found)
            real_rows = []
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                for r in rows:
                    rtxt = r.text.strip()
                    if rtxt and "ไม่พบข้อมูล" not in rtxt and "No data" not in rtxt and "กำลังโหลด" not in rtxt:
                        real_rows.append(r)
                if real_rows:
                    return "FOUND"
            except Exception:
                real_rows = []

            # 3. Check not found message
            not_found_displayed = False
            try:
                nf = self.driver.find_elements(By.XPATH, '//*[contains(text(),"ไม่พบข้อมูล") or contains(text(),"No data found") or contains(text(),"ไม่พบรายการ")]')
                if any(n.is_displayed() for n in nf):
                    not_found_displayed = True
            except Exception:
                pass

            now = time.time()
            if not real_rows:
                if empty_since is None:
                    empty_since = now
                else:
                    required_wait = 1.5 if (loader_seen or not_found_displayed) else 2.5
                    if (now - empty_since >= required_wait) and (now - start_time >= 1.5):
                        return "NOT_FOUND"
            else:
                empty_since = None

            time.sleep(0.2)

        if self.last_draft_info[1]:
            return "DRAFT"
        return "NOT_FOUND"

    def click_first_arrow(self):
        selectors = [
            "span.flaticon-right244, .flaticon-right244",
            "table tbody tr a.flex-icon",
            "table tbody tr td:last-child a"
        ]
        for sel in selectors:
            try:
                arrows = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for a in arrows:
                    if a.is_displayed():
                        self.js_click(a)
                        time.sleep(0.6)
                        return True
            except Exception:
                pass
        return False

    def get_val_at_index(self, elem_id: str, idx: int = 0) -> str:
        try:
            els = self.driver.find_elements(By.ID, elem_id)
            if len(els) > idx:
                return (els[idx].get_attribute("value") or els[idx].text or "").strip()
        except Exception:
            pass
        return ""

    def get_val(self, elem_id: str) -> str:
        return self.get_val_at_index(elem_id, 0)

    def clean_join(self, vals):
        clean = []
        for v in vals:
            v_str = str(v or "").strip()
            if v_str and v_str not in ["-", "--", "None", "null", "undefined", "nan"]:
                clean.append(v_str)
        return " ".join(clean)

    def extract_details(self, cid: str) -> Dict[str, str]:
        buyer_id = self.get_val_at_index("customer.nationid", 0)
        buyer_pre = self.get_val_at_index("customer.prename", 0)
        buyer_fn = self.get_val_at_index("customer.firstname", 0)
        buyer_ln = self.get_val_at_index("customer.lastname", 0)
        buyer_name = self.clean_join([buyer_pre, buyer_fn, buyer_ln])
        buyer_mob = self.get_val_at_index("cus_mobile", 0)

        # Address buyer
        card_addr = self.clean_join([
            self.get_val_at_index("addr1", 0), self.get_val_at_index("addr2", 0),
            self.get_val_at_index("tambon", 0), self.get_val_at_index("amphur", 0),
            self.get_val_at_index("province", 0), self.get_val_at_index("zipcode", 0)
        ])
        cur_addr = self.clean_join([
            self.get_val_at_index("addr1", 1), self.get_val_at_index("addr2", 1),
            self.get_val_at_index("tambon", 1), self.get_val_at_index("amphur", 1),
            self.get_val_at_index("province", 1), self.get_val_at_index("zipcode", 1)
        ]) or card_addr

        # Work buyer
        work_comp = self.get_val_at_index("work_company", 0)
        work_addr = self.clean_join([
            work_comp,
            self.get_val_at_index("addr1", 2), self.get_val_at_index("addr2", 2),
            self.get_val_at_index("tambon", 2), self.get_val_at_index("amphur", 2),
            self.get_val_at_index("province", 2), self.get_val_at_index("zipcode", 2)
        ])
        work_tel = self.get_val_at_index("tel", 0)
        work_type = self.get_val_at_index("work_type", 0)
        work_pos = self.get_val_at_index("work_position", 0)
        work_sal = self.get_val_at_index("work_salary", 0)
        pos_parts = [p for p in [work_type, work_pos] if p]
        if work_sal:
            pos_parts.append(f"เงินเดือน {work_sal}")
        buyer_pos = " ".join(pos_parts)

        # Guarantor
        co_id = self.get_val_at_index("co.nationid", 0)
        co_pre = self.get_val_at_index("co.prename", 0)
        co_fn = self.get_val_at_index("co.firstname", 0)
        co_ln = self.get_val_at_index("co.lastname", 0)
        co_name = self.clean_join([co_pre, co_fn, co_ln])
        co_mob = self.get_val_at_index("co.mobile", 0)
        co_rel = self.get_val_at_index("co_relation", 0)

        co_addr = self.clean_join([
            self.get_val_at_index("addr1", 3), self.get_val_at_index("addr2", 3),
            self.get_val_at_index("tambon", 3), self.get_val_at_index("amphur", 3),
            self.get_val_at_index("province", 3), self.get_val_at_index("zipcode", 3)
        ])

        co_comp = self.get_val_at_index("co_work_company", 0)
        co_work = self.clean_join([
            co_comp,
            self.get_val_at_index("addr1", 5), self.get_val_at_index("addr2", 5),
            self.get_val_at_index("tambon", 5), self.get_val_at_index("amphur", 5),
            self.get_val_at_index("province", 5), self.get_val_at_index("zipcode", 5)
        ])

        status = "ผู้เช่าซื้อ"
        clean_cid = re.sub(r"\D", "", str(cid))
        if clean_cid and co_id and clean_cid in re.sub(r"\D", "", co_id):
            status = "ผู้ค้ำประกัน"

        return {
            "เลขบัตรที่ใช้ค้นหา": str(cid),
            "ชื่อ-นามสกุล": co_name if status == "ผู้ค้ำประกัน" else buyer_name,
            "สถานะ": status,
            "เลขบัตรประชาชนผู้เช่าซื้อ": buyer_id,
            "ชื่อ-นามสกุลผู้เช่าซื้อ": buyer_name,
            "เบอร์โทรผู้เช่าซื้อ": buyer_mob,
            "ที่อยู่ตามบัตรประชาชนผู้เช่าซื้อ": card_addr,
            "ที่อยู่ปัจจุบันผู้เช่าซื้อ": cur_addr,
            "ที่อยู่ที่ทำงานผู้เช่าซื้อ": work_addr,
            "เบอร์โทรที่ทำงาน": work_tel,
            "ตำแหน่ง": buyer_pos,
            "เลขบัตรประชาชนผู้ค้ำ": co_id,
            "ชื่อ-นามสกุลผู้ค้ำ": co_name,
            "เบอร์โทรผู้ค้ำ": co_mob,
            "ความสัมพันธ์": co_rel,
            "ที่อยู่ผู้ค้ำ": co_addr,
            "ที่ทำงานผู้ค้ำ": co_work,
        }

    def make_not_found(self, cid: str) -> Dict[str, str]:
        row = {col: "" for col in OUTPUT_COLUMNS}
        row["เลขบัตรที่ใช้ค้นหา"] = str(cid)
        row["ชื่อ-นามสกุล"] = "ไม่พบข้อมูล"
        row["สถานะ"] = "ไม่พบข้อมูล"
        return row

    def search_one(self, cid: str) -> Dict[str, str]:
        cid_str = str(cid).strip()
        if not cid_str:
            return self.make_not_found(cid)

        self.recover_session_if_needed()
        self.ensure_back_to_search()
        self.clear_search_input()
        self.enter_search_cid(cid_str)
        res = self.wait_search_result(timeout=12)
        self.capture_screen()

        if res == "FOUND":
            if self.click_first_arrow():
                time.sleep(1.2)
                self.close_dialog_if_open()
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="customer.nationid"] | //*[@id="cus_mobile"]'))
                    )
                except Exception:
                    time.sleep(1)
                self.close_dialog_if_open()
                row = self.extract_details(cid_str)
                self.capture_screen()
                self.ensure_back_to_search()
                return row
            else:
                self.ensure_back_to_search()
                return self.make_not_found(cid_str)
        elif res == "DRAFT":
            d_id, d_name = self.last_draft_info
            row = self.make_not_found(cid_str)
            row["ชื่อ-นามสกุล"] = d_name or "ร่างสัญญา"
            row["สถานะ"] = "ร่างสัญญา"
            if d_id:
                row["เลขบัตรประชาชนผู้เช่าซื้อ"] = d_id
            self.close_dialog_if_open()
            self.ensure_back_to_search()
            return row

        self.ensure_back_to_search()
        return self.make_not_found(cid_str)

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        if self.profile_dir and os.path.exists(self.profile_dir):
            try:
                shutil.rmtree(self.profile_dir, ignore_errors=True)
            except Exception:
                pass
            self.profile_dir = None
