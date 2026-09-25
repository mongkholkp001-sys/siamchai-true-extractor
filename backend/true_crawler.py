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

        engine, browser_path = self.find_browser()
        if not self.profile_dir or not os.path.exists(self.profile_dir):
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
        คลิกเปิดลูกศรลงทุกอันที่มีในหน้า (รวมถึงลูกศรย่อยที่โผล่ขึ้นมาใหม่)
        พร้อมระบบ Grace Wait ป้องกันการหลุดรอบเมื่อ Sub-table กำลังโหลด
        """
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
                    time.sleep(0.6)
                    continue
                else:
                    break

            consecutive_empty = 0
            target_arrow = unclicked[0]
            self.driver.execute_script("arguments[0].setAttribute('data-bot-clicked', 'true');", target_arrow)
            click_count += 1
            try:
                ActionChains(self.driver).move_to_element(target_arrow).click().perform()
            except Exception:
                try:
                    self.driver.execute_script("""
                        const el = arguments[0];
                        const btn = el.closest('button, [role="button"], tr, td, div') || el.parentElement || el;
                        btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    """, target_arrow)
                except Exception:
                    pass
            time.sleep(0.4)

    def extract_phone_numbers(self, current_cid: str = "") -> Tuple[List[str], List[str], Dict[str, str]]:
        active_phones = []
        all_phones = []
        phone_status = {}

        # 1. Scan rows in tables
        rows = self.driver.find_elements(By.TAG_NAME, "tr")
        for r in rows:
            text = r.text.strip()
            if not text:
                continue

            matches = re.findall(r'0\d{1,2}-?\d{3}-?\d{4}', text)
            is_active_row = any(k in text for k in ["Active", "active", "ACTIVE", "ใช้งาน"])

            for ph in matches:
                clean = ph.strip()
                # Exclude if it's the CID itself or starts with 000
                if clean == current_cid or clean.replace("-", "") in current_cid or clean.startswith("000"):
                    continue
                if clean not in all_phones:
                    all_phones.append(clean)

                if is_active_row:
                    phone_status[clean] = "Active"
                    if clean not in active_phones:
                        active_phones.append(clean)
                elif any(k in text for k in ["Cancelled", "Cancel", "ยกเลิก", "Inactive", "Suspended"]):
                    if clean not in phone_status:
                        phone_status[clean] = "Cancelled"
                elif clean not in phone_status:
                    phone_status[clean] = "พบในระบบ"

        # 2. Also scan entire page source for any numbers outside tr
        try:
            page_source = self.driver.page_source
            extra_matches = re.findall(r'0\d{1,2}-\d{3}-\d{4}', page_source)
            for ph in extra_matches:
                clean = ph.strip()
                if clean not in all_phones and clean.replace("-", "") not in current_cid and not clean.startswith("000"):
                    all_phones.append(clean)
                    if clean not in phone_status:
                        phone_status[clean] = "Active" if "Active" in page_source else "พบในระบบ"
        except Exception:
            pass

        return all_phones, active_phones, phone_status

    def search_one(self, cid: str) -> Dict[str, any]:
        cid_str = str(cid).strip()
        if not cid_str:
            return {
                "cid": cid_str,
                "status": "ไม่พบข้อมูล",
                "total_count": 0,
                "all_phones": "-",
                "active_count": 0,
                "active_phones": "-",
                "phone_details": "-",
                "count": 0,
                "phones": "-"
            }

        for attempt in range(1, 3):
            try:
                # 1. หากยังอยู่ที่หน้าผลลัพธ์เดิม ให้กดปุ่มย้อนกลับทันที
                if "verify-detail" in self.driver.current_url:
                    try:
                        back_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'กลับสู่หน้าตรวจสอบ')]")
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
                    time.sleep(0.8)

                self.handle_popups_and_errors()

                # 2. รอช่องกรอกเลข
                wait = WebDriverWait(self.driver, 8)
                input_box = wait.until(EC.presence_of_element_located((By.ID, "input_card_number")))
                input_box.clear()
                input_box.send_keys(cid_str)
                time.sleep(0.15)

                # 3. กดปุ่ม ตรวจสอบ
                submit_btn = self.driver.find_element(By.ID, "button_submit_step")
                try:
                    submit_btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", submit_btn)

                # 4. รอหน้าผลลัพธ์โหลด
                WebDriverWait(self.driver, 10).until(
                    lambda d: "verify-detail" in d.current_url or 
                              len(d.find_elements(By.CSS_SELECTOR, 'svg[data-testid="KeyboardArrowDownRoundedIcon"]')) > 0 or
                              len(d.find_elements(By.XPATH, "//button[contains(text(), 'กลับสู่หน้าตรวจสอบ')]")) > 0
                )

                # รอให้ข้อมูลสัญญาหรือลูกศรคลี่ตารางแสดงผลครบถ้วน
                wait_data_start = time.time()
                while time.time() - wait_data_start < 5:
                    self.handle_popups_and_errors()
                    has_arrows = len(self.driver.find_elements(By.CSS_SELECTOR, 'svg[data-testid="KeyboardArrowDownRoundedIcon"]')) > 0
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
                time.sleep(0.5)
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
                    back_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'กลับสู่หน้าตรวจสอบ')]")
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
                if attempt == 2:
                    raise e
                time.sleep(1)

            except Exception as e:
                self.log(f"ข้อผิดพลาดทรู (รอบ {attempt}): {e}")
                time.sleep(0.5)

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
