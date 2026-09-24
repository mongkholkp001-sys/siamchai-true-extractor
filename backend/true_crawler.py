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
            print(f"[True] {msg}")

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
        engine, browser_path = self.find_browser()
        self.profile_dir = tempfile.mkdtemp(prefix="true_hub_profile_")

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
        if self.headless:
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
                        time.sleep(1)
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
            if "login" in self.driver.current_url:
                self.log(f"เข้าสู่ระบบ TrueCorp ด้วย User: {self.username}...")
                user_inp = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "input_username_login"))
                )
                pass_inp = self.driver.find_element(By.ID, "input_password_login")
                user_inp.clear()
                user_inp.send_keys(self.username)
                pass_inp.clear()
                pass_inp.send_keys(self.password)
                time.sleep(0.3)

                submit_div = self.driver.find_element(By.ID, "button_signin_login")
                self.driver.execute_script("arguments[0].click();", submit_div)
                time.sleep(3)
                self.capture_screen()

            if "branch" in self.driver.current_url:
                self.log("กำลังเลือกสาขา True...")
                try:
                    branch_btn = WebDriverWait(self.driver, 6).until(
                        EC.element_to_be_clickable((By.ID, "button_select_branch_0_branchbox"))
                    )
                    self.driver.execute_script("arguments[0].click();", branch_btn)
                    time.sleep(0.8)
                    confirm_btn = self.driver.find_element(By.ID, "button_submit_select_branchbox")
                    self.driver.execute_script("arguments[0].click();", confirm_btn)
                    time.sleep(2.5)
                except Exception as e:
                    self.log(f"หมายเหตุการเลือกสาขา: {e}")

            if "pre-verify" not in self.driver.current_url:
                self.driver.get(TRUE_PREVERIFY_URL)
                time.sleep(2)
            self.capture_screen()
            return True
        except Exception as e:
            self.log(f"ข้อผิดพลาดขณะล็อกอิน True: {e}")
            return False

    def login_and_prepare(self):
        self.create_driver()
        self.log("กำลังเปิดหน้า True Pre-Verify...")
        self.driver.get(TRUE_PREVERIFY_URL)
        time.sleep(2.5)
        self.capture_screen()
        self.perform_login()
        self.log("✅ TrueCorp พร้อมตรวจสอบข้อมูลแล้ว")

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
                time.sleep(1)
                return True
            time.sleep(0.5)

        return True

    def click_all_down_arrows(self) -> int:
        click_count = 0
        max_clicks = 30
        consecutive_empty = 0

        while click_count < max_clicks:
            self.handle_popups_and_errors()
            unclicked = self.driver.find_elements(
                By.CSS_SELECTOR,
                'svg[data-testid="KeyboardArrowDownRoundedIcon"]:not([data-bot-clicked="true"])'
            )
            if not unclicked:
                consecutive_empty += 1
                if consecutive_empty < 2:
                    time.sleep(1.2)
                    continue
                else:
                    break

            consecutive_empty = 0
            target = unclicked[0]
            self.driver.execute_script("arguments[0].setAttribute('data-bot-clicked', 'true');", target)
            click_count += 1
            try:
                ActionChains(self.driver).move_to_element(target).click().perform()
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", target)
                except Exception:
                    pass
            time.sleep(0.7)

        return click_count

    def extract_phone_numbers(self) -> Tuple[List[str], List[str], Dict[str, str]]:
        active_phones = []
        all_phones = []
        phone_status = {}

        rows = self.driver.find_elements(By.TAG_NAME, "tr")
        for r in rows:
            text = r.text
            matches = re.findall(r'0\d{1,2}-?\d{3}-?\d{4}', text)
            for ph in matches:
                clean = ph.strip()
                if clean not in all_phones:
                    all_phones.append(clean)
                if "Active" in text:
                    phone_status[clean] = "Active"
                    if clean not in active_phones:
                        active_phones.append(clean)
                elif "Cancelled" in text or "Cancel" in text:
                    phone_status[clean] = "Cancelled"
                elif clean not in phone_status:
                    phone_status[clean] = "Found"

        src = self.driver.page_source
        extra = re.findall(r'0\d{2}-\d{3}-\d{4}', src)
        for ph in extra:
            clean = ph.strip()
            if clean not in all_phones and not clean.startswith("000"):
                all_phones.append(clean)
                if clean not in phone_status:
                    phone_status[clean] = "Active" if "Active" in src else "Found"

        return all_phones, active_phones, phone_status

    def navigate_back_clean(self):
        try:
            self.handle_popups_and_errors()
            if "verify-detail" in self.driver.current_url:
                back_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'กลับสู่หน้าตรวจสอบ')]")
                if back_btns:
                    self.driver.execute_script("arguments[0].click();", back_btns[0])
                    time.sleep(1)
                else:
                    self.driver.get(TRUE_PREVERIFY_URL)
                    time.sleep(1.5)
            elif "pre-verify" not in self.driver.current_url:
                self.driver.get(TRUE_PREVERIFY_URL)
                time.sleep(1.5)
        except Exception:
            self.driver.get(TRUE_PREVERIFY_URL)
            time.sleep(1.5)

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
                card_inp.clear()
                self.driver.execute_script("""
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, card_inp, cid_str)
                time.sleep(0.4)

                submit_btn = self.driver.find_element(By.ID, "button_submit_step")
                self.driver.execute_script("arguments[0].click();", submit_btn)

                ready = self.wait_for_verify_detail(timeout=16)
                self.capture_screen()
                if not ready:
                    continue

                self.click_all_down_arrows()
                self.capture_screen()
                all_ph, active_ph, status_map = self.extract_phone_numbers()

                count = len(active_ph)
                active_str = ", ".join(active_ph) if count > 0 else "-"
                all_str = ", ".join(all_ph) if all_ph else "-"
                details_str = "; ".join([f"{k} ({v})" for k, v in status_map.items()]) if status_map else "-"

                self.navigate_back_clean()
                return {
                    "cid": cid_str,
                    "status": "สำเร็จ" if count > 0 else "ไม่พบเบอร์ Active",
                    "active_count": count,
                    "active_phones": active_str,
                    "all_phones": all_str,
                    "phone_details": details_str
                }
            except Exception as e:
                self.log(f"ข้อผิดพลาดทรู (รอบ {attempt}): {e}")
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
