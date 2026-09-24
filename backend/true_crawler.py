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
from selenium.webdriver.common.action_chains import ActionChains

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
            self.log_callback(msg)
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

        engine, browser_path = self.find_browser()
        if not self.profile_dir or not os.path.exists(self.profile_dir):
            self.profile_dir = tempfile.mkdtemp(prefix="true_hub_profile_")

        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.profile_dir}",
            "--window-size=1920,1080",
            "--disable-blink-features=AutomationControlled",
        ]
        if self.headless or os.name != "nt":
            args.extend(["--headless=new", "--disable-gpu"])

        options = webdriver.ChromeOptions()
        if browser_path:
            options.binary_location = browser_path
        for a in args:
            options.add_argument(a)
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(45)
        self.driver.implicitly_wait(3)

    def handle_popups_and_errors(self) -> bool:
        if not self.driver:
            return False
        handled = False
        # 1. Alert
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
            time.sleep(0.5)
            handled = True
        except Exception:
            pass

        # 2. Modal Popup
        try:
            dialogs = self.driver.find_elements(By.XPATH, "//div[@role='dialog' or contains(@class, 'MuiDialog') or contains(@class, 'swal')]")
            for dlg in dialogs:
                if dlg.is_displayed():
                    btn_xpath = ".//button[contains(text(), 'รีเฟรช') or contains(text(), 'Refresh') or contains(text(), 'ลองใหม่อีกครั้ง') or contains(text(), 'ตกลง') or contains(text(), 'ปิด') or contains(text(), 'OK') or contains(text(), 'รับทราบ')]"
                    buttons = dlg.find_elements(By.XPATH, btn_xpath)
                    if buttons:
                        self.driver.execute_script("arguments[0].click();", buttons[0])
                        time.sleep(0.8)
                        handled = True
                        break
        except Exception:
            pass

        # 3. Refresh button on error text
        try:
            refresh_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Refresh') or contains(text(), 'รีเฟรช') or .//svg[@data-testid='RefreshIcon']]")
            for r_btn in refresh_btns:
                if r_btn.is_displayed():
                    body_sub = self.driver.find_element(By.TAG_NAME, "body").text
                    if any(k in body_sub for k in ["ข้อผิดพลาด", "ไม่สามารถดึงข้อมูล", "โหลดข้อมูลไม่สำเร็จ", "กรุณารองใหม่อีกครั้ง", "error"]):
                        self.driver.execute_script("arguments[0].click();", r_btn)
                        time.sleep(1.5)
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

    def wait_for_verify_detail(self, timeout=18) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            self.handle_popups_and_errors()
            if "verify-detail" in self.driver.current_url:
                break
            time.sleep(0.4)

        if "verify-detail" not in self.driver.current_url:
            return False

        load_start = time.time()
        while time.time() - load_start < 10:
            self.handle_popups_and_errors()
            skeletons = self.driver.find_elements(By.CSS_SELECTOR, ".MuiSkeleton-root, [role='progressbar'], .loading")
            loading = any(s.is_displayed() for s in skeletons)
            has_tr = len(self.driver.find_elements(By.TAG_NAME, "tr")) > 1
            has_arrows = len(self.driver.find_elements(By.CSS_SELECTOR, 'svg[data-testid="KeyboardArrowDownRoundedIcon"]')) > 0
            if not loading and (has_tr or has_arrows):
                time.sleep(0.8)
                return True
            time.sleep(0.4)

        return True

    def click_all_down_arrows(self) -> int:
        click_count = 0
        max_clicks = 25

        while click_count < max_clicks:
            self.handle_popups_and_errors()
            arrows = self.driver.find_elements(
                By.CSS_SELECTOR,
                'svg[data-testid="KeyboardArrowDownRoundedIcon"]:not([data-bot-clicked="true"])'
            )
            if not arrows:
                break

            clicked_any = False
            for target in arrows:
                try:
                    self.driver.execute_script("arguments[0].setAttribute('data-bot-clicked', 'true');", target)
                    self.driver.execute_script("""
                        const svg = arguments[0];
                        const btn = svg.closest('button, [role="button"], td, div') || svg.parentElement;
                        btn.click();
                    """, target)
                    clicked_any = True
                    click_count += 1
                    time.sleep(0.4)
                    break # Re-query fresh elements after each click to handle nested arrows
                except Exception:
                    continue

            if not clicked_any:
                break

        time.sleep(0.6)
        return click_count

    def extract_phone_numbers(self, current_cid: str = "") -> Tuple[List[str], List[str], Dict[str, str]]:
        active_phones = []
        all_phones = []
        phone_status = {}

        # Regex for Thai mobile (06x, 08x, 09x) and landline numbers (02, 03x, etc.)
        # Using negative lookbehind and lookahead to avoid matching substrings of 13-digit CIDs
        phone_pattern = re.compile(r'(?<!\d)(0[689]\d{8}|0[689]\d{1}-\d{3}-\d{4}|0[2-7]\d{7,8}|0[2-7]\d{1}-\d{3}-\d{4})(?!\d)')

        # 1. Scan rows in tables
        rows = self.driver.find_elements(By.TAG_NAME, "tr")
        for r in rows:
            text = r.text
            if not text:
                continue
            matches = phone_pattern.findall(text)
            for ph in matches:
                clean = ph.strip()
                if clean == current_cid or clean.startswith("000"):
                    continue
                if clean not in all_phones:
                    all_phones.append(clean)

                is_active = ("active" in text.lower() or "ใช้งาน" in text) and not any(
                    k in text.lower() for k in ["cancelled", "cancel", "ยกเลิก", "inactive", "suspended"]
                )
                if is_active:
                    phone_status[clean] = "Active"
                    if clean not in active_phones:
                        active_phones.append(clean)
                elif "cancelled" in text.lower() or "cancel" in text.lower() or "ยกเลิก" in text:
                    phone_status[clean] = "Cancelled"
                elif clean not in phone_status:
                    phone_status[clean] = "พบในระบบ"

        # 2. Scan entire page body text
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            matches_body = phone_pattern.findall(body_text)
            for ph in matches_body:
                clean = ph.strip()
                if clean == current_cid or clean.startswith("000"):
                    continue
                if clean not in all_phones:
                    all_phones.append(clean)
                    if clean not in phone_status:
                        phone_status[clean] = "พบในระบบ"
        except Exception:
            pass

        return all_phones, active_phones, phone_status

    def navigate_back_clean(self):
        try:
            self.handle_popups_and_errors()
            if "login" in self.driver.current_url:
                self.perform_login()
                return

            if "verify-detail" in self.driver.current_url:
                back_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'กลับสู่หน้าตรวจสอบ') or contains(text(), 'กลับ')]")
                if back_btns:
                    self.driver.execute_script("arguments[0].click();", back_btns[0])
                    time.sleep(1.2)
                else:
                    self.driver.get(TRUE_PREVERIFY_URL)
                    time.sleep(1.5)
            elif "pre-verify" not in self.driver.current_url:
                self.driver.get(TRUE_PREVERIFY_URL)
                time.sleep(1.5)
        except Exception:
            try:
                self.driver.get(TRUE_PREVERIFY_URL)
                time.sleep(1.5)
            except Exception:
                pass

    def search_one(self, cid: str) -> Dict[str, any]:
        cid_str = str(cid).strip()
        if not cid_str:
            return {"cid": cid_str, "status": "ไม่พบข้อมูล", "active_count": 0, "active_phones": "-", "all_phones": "-", "phone_details": "-"}

        for attempt in range(1, 3):
            try:
                self.navigate_back_clean()
                self.handle_popups_and_errors()

                wait = WebDriverWait(self.driver, 12)
                card_inp = wait.until(EC.presence_of_element_located((By.ID, "input_card_number")))
                
                # Reliable clear and typing
                try:
                    card_inp.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", card_inp)
                card_inp.send_keys(Keys.CONTROL, "a")
                card_inp.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)
                card_inp.send_keys(cid_str)
                time.sleep(0.3)

                # Ensure React state recognizes value change
                self.driver.execute_script("""
                    const input = arguments[0];
                    const val = arguments[1];
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                    if (setter) {
                        setter.call(input, val);
                    } else {
                        input.value = val;
                    }
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                """, card_inp, cid_str)
                time.sleep(0.3)

                submit_btn = self.driver.find_element(By.ID, "button_submit_step")
                
                # If disabled, re-click 'บุคคล' to trigger form validation
                if submit_btn.get_attribute("disabled") is not None:
                    for el in self.driver.find_elements(By.XPATH, "//*[contains(text(), 'บุคคล')]"):
                        try:
                            self.driver.execute_script("arguments[0].click();", el)
                            time.sleep(0.3)
                        except Exception:
                            pass

                # Submit search
                try:
                    submit_btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", submit_btn)

                # Wait for verify-detail page
                ready = self.wait_for_verify_detail(timeout=14)
                self.capture_screen()
                if not ready:
                    continue

                # Expand all collapsed accordions/down arrows
                self.click_all_down_arrows()
                self.capture_screen()

                # Extract phone numbers
                all_ph, active_ph, status_map = self.extract_phone_numbers(current_cid=cid_str)

                count = len(active_ph)
                active_str = ", ".join(active_ph) if count > 0 else "-"
                all_str = ", ".join(all_ph) if all_ph else "-"
                details_str = "; ".join([f"{k} ({v})" for k, v in status_map.items()]) if status_map else "-"

                self.navigate_back_clean()
                return {
                    "cid": cid_str,
                    "status": "สำเร็จ" if count > 0 else ("ไม่พบเบอร์ Active" if all_ph else "ไม่พบข้อมูล"),
                    "active_count": count,
                    "active_phones": active_str,
                    "all_phones": all_str,
                    "phone_details": details_str
                }
            except Exception as e:
                self.log(f"ข้อผิดพลาดทรู (รอบ {attempt}): {e}")
                # If browser crashed, recreate driver
                if "refused" in str(e).lower() or "session" in str(e).lower():
                    try:
                        self.log("กำลังเชื่อมต่อเบราว์เซอร์ TrueCorp ใหม่...")
                        self.login_and_prepare()
                    except Exception:
                        pass
                time.sleep(1)

        self.navigate_back_clean()
        return {
            "cid": cid_str,
            "status": "ไม่พบข้อมูล/ผิดพลาด",
            "active_count": 0,
            "active_phones": "-",
            "all_phones": "-",
            "phone_details": "-"
        }

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
