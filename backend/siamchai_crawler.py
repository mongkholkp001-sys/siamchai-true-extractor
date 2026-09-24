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
        ]
        if os.name != "nt":
            args.extend(["--no-sandbox", "--disable-setuid-sandbox"])

        if self.headless or os.name != "nt":
            args.extend(["--headless=new", "--disable-gpu"])

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

    def fill_login(self, u, p):
        self.dismiss_popups(1.5)
        wait = WebDriverWait(self.driver, 15)
        u_in = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#user, input#user, input[type="text"]')))
        p_in = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#pass, input#pass, input[type="password"]')))

        u_in.click()
        u_in.send_keys(Keys.CONTROL, "a")
        u_in.send_keys(Keys.BACKSPACE)
        time.sleep(0.05)
        u_in.send_keys(str(u))

        p_in.click()
        p_in.send_keys(Keys.CONTROL, "a")
        p_in.send_keys(Keys.BACKSPACE)
        time.sleep(0.05)
        p_in.send_keys(str(p))

        self.driver.execute_script("""
            arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
            arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
            arguments[1].dispatchEvent(new Event('input', {bubbles:true}));
            arguments[1].dispatchEvent(new Event('change', {bubbles:true}));
            arguments[1].blur();
        """, u_in, p_in)
        time.sleep(0.3)

    def click_login(self):
        try:
            btns = self.driver.find_elements(
                By.XPATH,
                '//span[contains(@class,"label") and normalize-space()="เข้าสู่ระบบ"]/ancestor::a[1] | '
                '//*[self::a or self::button][normalize-space()="เข้าสู่ระบบ"]'
            )
            for b in btns:
                if b.is_displayed():
                    self.js_click(b)
                    return True
        except Exception:
            pass
        try:
            self.driver.switch_to.active_element.send_keys(Keys.ENTER)
            return True
        except Exception:
            return False

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
        self.capture_screen()
        self.dismiss_popups(timeout=2)

        login_success = False
        for attempt in range(1, 4):
            self.log(f"เข้าสู่ระบบสยามชัย (รอบที่ {attempt})...")
            self.fill_login(self.username, self.password)
            self.click_login()
            time.sleep(2.5)
            self.dismiss_popups(timeout=2)
            self.capture_screen()

            try:
                txt = self.driver.find_element(By.ID, "user-panel").text.strip()
                if txt and "กำลังโหลดข้อมูล" not in txt:
                    self.log(f"✅ สยามชัยเข้าสู่ระบบสำเร็จ: {txt}")
                    login_success = True
                    break
            except Exception:
                pass

        self.ensure_inspection_page()
        self.capture_screen()
        self.log("✅ สยามชัยพร้อมค้นหาข้อมูลแล้ว")

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
        wait = WebDriverWait(self.driver, 10)
        inp = wait.until(EC.presence_of_element_located((By.ID, "cus_nation_id")))
        try:
            inp.click()
        except Exception:
            self.js_click(inp)
        inp.send_keys(Keys.CONTROL, "a")
        inp.send_keys(Keys.BACKSPACE)
        time.sleep(0.1)
        inp.send_keys(str(cid))
        time.sleep(0.1)
        inp.send_keys(Keys.ENTER)
        inp.send_keys(Keys.TAB)
        try:
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles:true})); arguments[0].blur();", inp)
        except Exception:
            pass
        time.sleep(0.8)

    def wait_search_result(self, timeout=8):
        end = time.time() + timeout
        self.last_draft_info = ("", "")
        while time.time() < end:
            if self.stop_requested:
                return "STOP"

            # Check draft
            try:
                for el in self.driver.find_elements(By.XPATH, '//*[contains(normalize-space(),"ร่างสัญญา")]'):
                    if el.is_displayed():
                        txt = el.text.strip()
                        id_m = re.search(r"เลขที่บัตรประชาชน\s*(\d+)", txt)
                        nm_m = re.search(r"ชื่อ\s*([^\s]+(?:\s+[^\s]+)*?)\s*ใช่ไหม", txt)
                        self.last_draft_info = (id_m.group(1) if id_m else "", nm_m.group(1) if nm_m else "")
                        break
            except Exception:
                pass

            self.close_dialog_if_open()

            # Check table rows (Real rows found)
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                real_rows = [r for r in rows if r.text.strip() and "ไม่พบข้อมูล" not in r.text and "No data" not in r.text]
                if real_rows:
                    return "FOUND"
            except Exception:
                pass

            # Check not found
            try:
                nf = self.driver.find_elements(By.XPATH, '//*[contains(text(),"ไม่พบข้อมูล") or contains(text(),"No data found") or contains(text(),"ไม่พบรายการ")]')
                if any(n.is_displayed() for n in nf):
                    return "NOT_FOUND"
            except Exception:
                pass

            time.sleep(0.3)

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
                        time.sleep(0.5)
                        return True
            except Exception:
                pass
        return False

    def get_val(self, elem_id):
        try:
            els = self.driver.find_elements(By.ID, elem_id)
            if els:
                return (els[0].get_attribute("value") or els[0].text or "").strip()
        except Exception:
            pass
        return ""

    def clean_join(self, vals):
        clean = []
        for v in vals:
            v_str = str(v or "").strip()
            if v_str and v_str not in ["-", "--", "None", "null", "undefined"]:
                clean.append(v_str)
        return " ".join(clean)

    def extract_details(self, cid: str) -> Dict[str, str]:
        buyer_id = self.get_val("customer.nationid")
        buyer_pre = self.get_val("customer.prename")
        buyer_fn = self.get_val("customer.firstname")
        buyer_ln = self.get_val("customer.lastname")
        buyer_name = self.clean_join([buyer_pre, buyer_fn, buyer_ln])
        buyer_mob = self.get_val("cus_mobile")

        # Address
        card_addr = self.clean_join([self.get_val("addr1"), self.get_val("addr2"), self.get_val("tambon"), self.get_val("amphur"), self.get_val("province"), self.get_val("zipcode")])
        cur_addr = card_addr # default fallback

        # Work
        work_comp = self.get_val("work_company")
        work_tel = self.get_val("tel")
        work_type = self.get_val("work_type")
        work_pos = self.get_val("work_position")
        work_sal = self.get_val("work_salary")
        pos_parts = [p for p in [work_type, work_pos] if p]
        if work_sal:
            pos_parts.append(f"เงินเดือน {work_sal}")
        buyer_pos = " ".join(pos_parts)

        # Guarantor
        co_id = self.get_val("co.nationid")
        co_pre = self.get_val("co.prename")
        co_fn = self.get_val("co.firstname")
        co_ln = self.get_val("co.lastname")
        co_name = self.clean_join([co_pre, co_fn, co_ln])
        co_mob = self.get_val("co.mobile")
        co_rel = self.get_val("co_relation")

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
            "ที่อยู่ที่ทำงานผู้เช่าซื้อ": work_comp,
            "เบอร์โทรที่ทำงาน": work_tel,
            "ตำแหน่ง": buyer_pos,
            "เลขบัตรประชาชนผู้ค้ำ": co_id,
            "ชื่อ-นามสกุลผู้ค้ำ": co_name,
            "เบอร์โทรผู้ค้ำ": co_mob,
            "ความสัมพันธ์": co_rel,
            "ที่อยู่ผู้ค้ำ": "",
            "ที่ทำงานผู้ค้ำ": "",
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
        self.ensure_back_to_search()
        self.enter_search_cid(cid_str)
        res = self.wait_search_result(timeout=7)
        self.capture_screen()

        if res == "FOUND":
            if self.click_first_arrow():
                time.sleep(1.5)
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
        elif res == "DRAFT":
            d_id, d_name = self.last_draft_info
            row = self.make_not_found(cid_str)
            row["ชื่อ-นามสกุล"] = d_name or "ร่างสัญญา"
            row["สถานะ"] = "ร่างสัญญา"
            if d_id:
                row["เลขบัตรประชาชนผู้เช่าซื้อ"] = d_id
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
