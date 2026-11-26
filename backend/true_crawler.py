import os
import re
import time
import tempfile
import shutil
import threading
from typing import Dict, List, Optional, Callable, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from backend.siamchai_crawler import GLOBAL_DRIVER_LOCK
from selenium.webdriver.common.action_chains import ActionChains
from backend.browser_factory import create_robust_driver

TRUE_LOGIN_URL = "https://ism-shop.truecorp.co.th/login/"
TRUE_PREVERIFY_URL = "https://ism-shop.truecorp.co.th/pre-verify/"

class TrueCrawler:
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

    def log(self, msg: str):
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass
        else:
            try:
                print(f"[True] {msg}")
            except Exception:
                pass

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

        if not self.profile_dir or not os.path.exists(self.profile_dir):
            self.profile_dir = tempfile.mkdtemp(prefix="true_hub_profile_")

        self.driver, _ = create_robust_driver(
            headless=self.headless,
            profile_dir=self.profile_dir,
            log_fn=self.log
        )

        self.driver.set_page_load_timeout(60)
        self.driver.implicitly_wait(3)

    def handle_popups_and_errors(self) -> bool:
        if not self.driver:
            return False
        handled = False

        # 1. Native Alert
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
            time.sleep(0.4)
            handled = True
        except Exception:
            pass

        # 2. Advanced JavaScript Modal & SweetAlert & Dialog Dismiss
        try:
            dismissed = self.driver.execute_script("""
                let clicked = false;
                // A. SweetAlert2 / Swal confirm buttons
                const swalButtons = document.querySelectorAll('.swal2-confirm, .swal2-actions button, button.swal2-styled');
                for (const b of swalButtons) {
                    if (b.offsetParent !== null || b.offsetHeight > 0) {
                        b.click();
                        return true;
                    }
                }

                // B. Any button with Confirm / OK / ตกลง inside modal or when error popup is visible
                const bodyText = document.body ? (document.body.innerText || '') : '';
                const hasErrorText = bodyText.includes('ขออภัย') || 
                                     bodyText.includes('ไม่สามารถดำเนินการได้') || 
                                     bodyText.includes('กรุณาลองทำรายการใหม่อีกครั้ง') ||
                                     bodyText.includes('เกิดข้อผิดพลาด') ||
                                     bodyText.includes('Error');

                const candidateButtons = Array.from(document.querySelectorAll(
                    'button, [role="button"], a.btn, div.btn, span.btn, .modal button, [class*="dialog"] button, [class*="modal"] button'
                ));

                for (const btn of candidateButtons) {
                    const txt = (btn.innerText || btn.textContent || '').trim();
                    const isConfirmLabel = ['ตกลง', 'OK', 'ok', 'ปิด', 'รับทราบ', 'ลองใหม่อีกครั้ง', 'ยืนยัน', 'Close'].includes(txt);
                    const insideModal = btn.closest('.modal, [role="dialog"], .swal2-popup, .swal2-container, .popup, [class*="modal"], [class*="dialog"]');

                    if (isConfirmLabel && (insideModal || hasErrorText)) {
                        btn.click();
                        btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                        return true;
                    }
                }
                return false;
            """)
            if dismissed:
                time.sleep(0.6)
                handled = True
        except Exception:
            pass

        # 3. XPath fallback for Modal Buttons
        if not handled:
            try:
                confirm_xpath = (
                    "//div[contains(@class, 'modal') or contains(@class, 'dialog') or contains(@role, 'dialog') or contains(@class, 'swal')]"
                    "//*[self::button or self::a or @role='button'][contains(., 'ตกลง') or contains(., 'OK') or contains(., 'ปิด') or contains(., 'รับทราบ') or contains(., 'ลองใหม่อีกครั้ง')]"
                )
                btns = self.driver.find_elements(By.XPATH, confirm_xpath)
                for b in btns:
                    if b.is_displayed():
                        self.driver.execute_script("arguments[0].click();", b)
                        time.sleep(0.6)
                        handled = True
                        break
            except Exception:
                pass

        # 4. Refresh button on error text
        try:
            refresh_btns = self.driver.find_elements(By.XPATH, "//button[contains(., 'Refresh') or contains(., 'รีเฟรช') or .//svg[@data-testid='RefreshIcon']]")
            for r_btn in refresh_btns:
                if r_btn.is_displayed():
                    body_sub = self.driver.find_element(By.TAG_NAME, "body").text
                    if any(k in body_sub for k in ["ข้อผิดพลาด", "ไม่สามารถดึงข้อมูล", "โหลดข้อมูลไม่สำเร็จ", "กรุณารองใหม่อีกครั้ง", "error"]):
                        self.driver.execute_script("arguments[0].click();", r_btn)
                        time.sleep(1.2)
                        handled = True
                        break
        except Exception:
            pass

        return handled

    def perform_login(self) -> bool:
        try:
            self.log(f"เข้าสู่ระบบ TrueCorp ด้วย User: {self.username}...")
            self.driver.get(TRUE_LOGIN_URL)
            time.sleep(2)

            wait = WebDriverWait(self.driver, 15)
            user_inp = wait.until(EC.presence_of_element_located((By.ID, "input_username_login")))
            pass_inp = self.driver.find_element(By.ID, "input_password_login")
            
            user_inp.clear()
            user_inp.send_keys(self.username)
            pass_inp.clear()
            pass_inp.send_keys(self.password)
            time.sleep(0.3)

            submit_div = self.driver.find_element(By.ID, "button_signin_login")
            self.driver.execute_script("arguments[0].click();", submit_div)
            time.sleep(3.5)
            self.capture_screen()

            # Handle branch selection if prompted
            for _ in range(6):
                if "branch" in self.driver.current_url:
                    self.log("กำลังยืนยันเลือกสาขา True...")
                    try:
                        branch_btn = WebDriverWait(self.driver, 8).until(
                            EC.element_to_be_clickable((By.ID, "button_select_branch_0_branchbox"))
                        )
                        self.driver.execute_script("arguments[0].click();", branch_btn)
                        time.sleep(0.8)
                        confirm_btn = self.driver.find_element(By.ID, "button_submit_select_branchbox")
                        self.driver.execute_script("arguments[0].click();", confirm_btn)
                        time.sleep(3)
                        break
                    except Exception:
                        time.sleep(1)
                else:
                    time.sleep(0.5)

            # Navigate to Pre-Verify and confirm input field exists
            self.driver.get(TRUE_PREVERIFY_URL)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "input_card_number"))
            )
            time.sleep(1)
            self.capture_screen()
            self.log("✅ เข้าสู่ระบบและเปิดหน้าตรวจสอบ TrueCorp เรียบร้อยแล้ว")
            return True
        except Exception as e:
            self.log(f"ข้อผิดพลาดขณะล็อกอิน True: {e}")
            return False

    def login_and_prepare(self):
        self.create_driver()
        self.log("กำลังเริ่มต้นเปิดเบราว์เซอร์ TrueCorp...")
        success = self.perform_login()
        if not success:
            raise RuntimeError("ไม่สามารถเข้าสู่ระบบ TrueCorp ได้ กรุณาตรวจสอบ Username / Password หรือการเชื่อมต่อ")

    def recover_driver_session(self):
        self.log("🔄 กำลังรีสตาร์ทเบราว์เซอร์ TrueCorp และเชื่อมต่อระบบใหม่อัตโนมัติ...")
        self.close()
        time.sleep(2)
        self.login_and_prepare()

    def recover_session_if_needed(self) -> bool:
        if not self.driver:
            self.recover_driver_session()
            return True
        try:
            curr_url = self.driver.current_url.lower()
        except Exception:
            self.recover_driver_session()
            return True

        if "login" in curr_url or "signin" in curr_url:
            self.log("⚠️ เซสชันทรูหลุดกลับหน้าล็อกอิน! กำลังเข้าสู่ระบบใหม่อัตโนมัติ...")
            success = self.perform_login()
            if not success:
                self.recover_driver_session()
            return True

        # Check if landed somewhere outside pre-verify and verify-detail
        if "pre-verify" not in curr_url and "verify-detail" not in curr_url:
            try:
                self.driver.get(TRUE_PREVERIFY_URL)
                time.sleep(1)
            except Exception:
                self.recover_driver_session()
                return True

        return False

    def wait_for_verify_detail(self, timeout=8) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            self.handle_popups_and_errors()
            if "verify-detail" in self.driver.current_url:
                break
            time.sleep(0.3)

        if "verify-detail" not in self.driver.current_url:
            return False

        # Fast check: wait until either back button, table, or down arrows appear
        render_start = time.time()
        while time.time() - render_start < 4:
            has_back = len(self.driver.find_elements(By.XPATH, "//button[contains(text(), 'กลับสู่หน้าตรวจสอบ')]")) > 0
            has_tr = len(self.driver.find_elements(By.TAG_NAME, "tr")) > 1
            has_arrows = len(self.driver.find_elements(By.CSS_SELECTOR, 'svg[data-testid="KeyboardArrowDownRoundedIcon"]')) > 0
            if has_back or has_tr or has_arrows:
                time.sleep(0.3)
                return True
            time.sleep(0.3)

        return True

    def click_all_down_arrows(self):
        """
        คลิกเปิดลูกศรทุกรูปแบบที่มีในหน้า (ลูกศรชี้ลง, ชี้ขวา, ExpandMore, Chevron, ปุ่มกางตารางย่อย)
        พร้อมระบบตรวจจับอัตโนมัติและรอข้อมูลโหลด
        """
        max_cycles = 15
        total_clicked = 0

        for cycle in range(max_cycles):
            self.handle_popups_and_errors()

            clicked_in_cycle = self.driver.execute_script("""
                let clicked = 0;
                
                // 1. ตรวจหาปุ่มที่มี aria-expanded="false" (ปุ่มกางตารางย่อย)
                const unexpanded = document.querySelectorAll('button[aria-expanded="false"], [role="button"][aria-expanded="false"]');
                for (const btn of unexpanded) {
                    if (!btn.hasAttribute('data-bot-clicked')) {
                        btn.setAttribute('data-bot-clicked', 'true');
                        btn.click();
                        btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                        clicked++;
                    }
                }
                
                // 2. ตรวจหาลูกศรทุกชนิด (ArrowDown, ArrowRight, ExpandMore, Chevron, ไอคอนลูกศร)
                const arrowSelectors = [
                    'svg[data-testid*="Arrow"]:not([data-bot-clicked="true"])',
                    'svg[data-testid*="Expand"]:not([data-bot-clicked="true"])',
                    'svg[data-testid*="Chevron"]:not([data-bot-clicked="true"])',
                    'table tbody tr td:first-child button:not([data-bot-clicked="true"])',
                    'table tbody tr button:not([data-bot-clicked="true"])',
                    'button[aria-label*="expand"]:not([data-bot-clicked="true"])',
                    'button[aria-label*="detail"]:not([data-bot-clicked="true"])',
                    '[class*="MuiIconButton"]:has(svg):not([data-bot-clicked="true"])',
                    '[class*="expand"]:not([data-bot-clicked="true"])',
                    '[class*="Arrow"]:not([data-bot-clicked="true"])'
                ].join(', ');

                let arrowEls = [];
                try {
                    arrowEls = document.querySelectorAll(arrowSelectors);
                } catch(e) {
                    arrowEls = document.querySelectorAll('svg[data-testid*="Arrow"], svg[data-testid*="Expand"], svg[data-testid*="Chevron"]');
                }

                for (const el of arrowEls) {
                    if (el.getAttribute('data-bot-clicked') === 'true') continue;
                    
                    const parentBtn = el.closest('button, [role="button"], tr, td') || el;
                    if (parentBtn.getAttribute('aria-expanded') === 'true') {
                        el.setAttribute('data-bot-clicked', 'true');
                        continue;
                    }
                    
                    el.setAttribute('data-bot-clicked', 'true');
                    parentBtn.setAttribute('data-bot-clicked', 'true');
                    
                    try {
                        parentBtn.click();
                        parentBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                        clicked++;
                    } catch(err) {}
                }
                
                return clicked;
            """)

            if clicked_in_cycle and clicked_in_cycle > 0:
                total_clicked += clicked_in_cycle
                time.sleep(0.5)
            else:
                if cycle == 0:
                    time.sleep(0.4)
                    continue
                break

        if total_clicked > 0:
            time.sleep(0.6)

    def extract_phone_numbers(self, current_cid: str = "") -> Tuple[List[str], List[str], Dict[str, str]]:
        active_phones = []
        all_phones = []
        phone_status = {}
        clean_cid = str(current_cid).replace("-", "").strip()

        def add_phone(ph_str: str, is_active: bool = False, is_cancel: bool = False):
            digits = re.sub(r'\D', '', str(ph_str))
            if not digits or digits == clean_cid or digits.startswith("000") or len(digits) not in (9, 10):
                return
            if len(digits) == 10 and digits.startswith(('06', '08', '09')):
                formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            elif len(digits) == 9 and digits.startswith(('02', '03', '04', '05', '07')):
                formatted = f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
            else:
                formatted = digits

            if formatted not in all_phones:
                all_phones.append(formatted)
            if is_active:
                phone_status[formatted] = "Active"
                if formatted not in active_phones:
                    active_phones.append(formatted)
            elif is_cancel:
                if formatted not in phone_status:
                    phone_status[formatted] = "Cancelled"
            elif formatted not in phone_status:
                phone_status[formatted] = "พบในระบบ"

        # 1. Scan rows in tables
        rows = self.driver.find_elements(By.TAG_NAME, "tr")
        for r in rows:
            text = r.text.strip()
            if not text:
                continue

            matches = re.findall(r'(?:(?<=\D)|^)(0[2-9]\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}|0[689]\d{8}|0[2-57]\d{7})(?=\D|$)', text)
            is_active_row = any(k in text for k in ["Active", "active", "ACTIVE", "ใช้งาน"])
            is_cancel_row = any(k in text for k in ["Cancelled", "Cancel", "ยกเลิก", "Inactive", "Suspended"])

            for ph in matches:
                add_phone(ph, is_active=is_active_row, is_cancel=is_cancel_row)

        # 2. Also scan entire page text and source for any numbers outside tr
        try:
            body_txt = self.driver.find_element(By.TAG_NAME, "body").text
            extra_matches = re.findall(r'(?:(?<=\D)|^)(0[2-9]\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}|0[689]\d{8}|0[2-57]\d{7})(?=\D|$)', body_txt)
            for ph in extra_matches:
                add_phone(ph, is_active="Active" in body_txt)
        except Exception:
            pass

        return all_phones, active_phones, phone_status

    def search_one(self, cid: str) -> Dict[str, any]:
        cid_str = str(cid).strip()
        if not cid_str or self.stop_requested:
            return {
                "cid": cid_str,
                "status": "หยุดการทำงาน" if self.stop_requested else "ไม่พบข้อมูล",
                "total_count": 0,
                "all_phones": "-",
                "active_count": 0,
                "active_phones": "-",
                "phone_details": "-",
                "count": 0,
                "phones": "-"
            }

        self.recover_session_if_needed()

        for attempt in range(1, 4):
            if self.stop_requested:
                break
            try:
                # 1. หากยังอยู่ที่หน้าผลลัพธ์เดิม ให้กดปุ่มย้อนกลับทันที
                if "verify-detail" in self.driver.current_url:
                    try:
                        back_btns = self.driver.find_elements(By.XPATH, "//button[contains(., 'กลับสู่หน้าตรวจสอบ')]")
                        if back_btns:
                            try:
                                back_btns[0].click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", back_btns[0])
                            time.sleep(0.4)
                    except Exception:
                        pass

                # หากหลุดไปหน้า login หรือยังค้างในหน้าผลลัพธ์
                if "login" in self.driver.current_url:
                    self.perform_login()
                elif "verify-detail" in self.driver.current_url or "pre-verify" not in self.driver.current_url:
                    self.driver.get(TRUE_PREVERIFY_URL)
                    time.sleep(1.0)

                self.handle_popups_and_errors()

                # 2. รอช่องกรอกเลข
                wait = WebDriverWait(self.driver, 12)
                input_box = wait.until(EC.presence_of_element_located((By.ID, "input_card_number")))
                input_box.clear()
                input_box.send_keys(cid_str)
                time.sleep(0.2)

                # 3. กดปุ่ม ตรวจสอบ
                submit_btn = self.driver.find_element(By.ID, "button_submit_step")
                try:
                    submit_btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", submit_btn)

                # 4. รอหน้าผลลัพธ์โหลด พร้อมตรวจจับ Popup ข้อผิดพลาด
                wait_result_start = time.time()
                popup_hit = False
                while time.time() - wait_result_start < 12:
                    if self.stop_requested:
                        break

                    # เช็คว่ามีแจ้งเตือน "ขออภัย" / "ระบบไม่สามารถดำเนินการได้" โผล่ขึ้นมาหรือไม่
                    try:
                        page_txt = self.driver.page_source
                    except Exception:
                        page_txt = ""

                    if any(k in page_txt for k in ["ขออภัย", "ระบบไม่สามารถดำเนินการได้", "กรุณาลองทำรายการใหม่อีกครั้ง"]):
                        self.log(f"⚠️ ตรวจพบแจ้งเตือน 'ระบบไม่สามารถดำเนินการได้' สำหรับเลข {cid_str} - กดปิดแจ้งเตือนและเตรียมค้นหาซ้ำ...")
                        self.handle_popups_and_errors()
                        popup_hit = True
                        break

                    # ตรวจสอบว่ามาถึงหน้าผลลัพธ์แล้ว
                    if "verify-detail" in self.driver.current_url:
                        break
                    if len(self.driver.find_elements(By.XPATH, "//button[contains(., 'กลับสู่หน้าตรวจสอบ')]")) > 0:
                        break
                    if len(self.driver.find_elements(By.CSS_SELECTOR, 'svg[data-testid*="Arrow"], svg[data-testid*="Expand"], svg[data-testid*="Chevron"]')) > 0:
                        break
                    if any(k in page_txt for k in ["ไม่พบข้อมูล", "ไม่พบรายการ", "ไม่มีข้อมูล"]):
                        break

                    time.sleep(0.3)

                if popup_hit:
                    time.sleep(1)
                    # รีเฟรชหน้า pre-verify แล้วลองค้นหาเลขเดิมซ้ำใน attempt ถัดไป
                    self.driver.get(TRUE_PREVERIFY_URL)
                    time.sleep(1.2)
                    self.handle_popups_and_errors()
                    continue

                # รอให้ข้อมูลสัญญาหรือลูกศรคลี่ตารางแสดงผลครบถ้วน
                wait_data_start = time.time()
                while time.time() - wait_data_start < 5:
                    self.handle_popups_and_errors()
                    has_arrows = len(self.driver.find_elements(By.CSS_SELECTOR, 'svg[data-testid*="Arrow"], svg[data-testid*="Expand"], svg[data-testid*="Chevron"], button[aria-expanded="false"]')) > 0
                    has_rows = len(self.driver.find_elements(By.TAG_NAME, "tr")) > 1
                    try:
                        body_txt = self.driver.find_element(By.TAG_NAME, "body").text
                    except Exception:
                        body_txt = ""
                    if has_arrows or has_rows or any(k in body_txt for k in ["ไม่พบข้อมูล", "ไม่พบรายการ", "ไม่มีข้อมูล"]):
                        break
                    time.sleep(0.3)

                time.sleep(0.5)

                # 5. คลิกลูกศรลงทั้งหมดเพื่อกางตารางเบอร์โทรทั้งหมด
                self.click_all_down_arrows()
                time.sleep(0.6)
                self.capture_screen()

                # 6. กวาดหาเบอร์ทั้งหมด และเบอร์ Active
                all_ph, active_ph, status_map = self.extract_phone_numbers(current_cid=cid_str)

                total_count = len(all_ph)
                active_count = len(active_ph)

                all_str = "; ".join(all_ph) if all_ph else "-"
                active_str = "; ".join(active_ph) if active_ph else "-"
                details_str = "; ".join([f"{k} ({v})" for k, v in status_map.items()]) if status_map else "-"

                # เจออะไรก็เอาออกมาให้หมด: ถ้าพบเบอร์ ให้สถานะเป็น "สำเร็จ" ทันที
                status_desc = "สำเร็จ" if total_count > 0 else "ไม่พบข้อมูล"

                # 7. กดกลับสู่หน้าตรวจสอบทันทีสำหรับเลขถัดไป
                try:
                    back_btns = self.driver.find_elements(By.XPATH, "//button[contains(., 'กลับสู่หน้าตรวจสอบ')]")
                    if back_btns:
                        try:
                            back_btns[0].click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", back_btns[0])
                        time.sleep(0.3)
                except Exception:
                    pass

                return {
                    "cid": cid_str,
                    "status": status_desc,
                    "total_count": total_count,
                    "all_phones": all_str,
                    "active_count": active_count,
                    "active_phones": active_str,
                    "phone_details": details_str,
                    # Backward compatibility
                    "count": total_count,
                    "phones": all_str
                }
            except Exception as e:
                self.log(f"⚠️ ข้อผิดพลาดตรวจสอบทรู เลข {cid_str} (รอบ {attempt}): {e}")
                if attempt < 3:
                    try:
                        self.handle_popups_and_errors()
                        self.driver.get(TRUE_PREVERIFY_URL)
                        time.sleep(1.2)
                    except Exception:
                        pass
                else:
                    raise e

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
