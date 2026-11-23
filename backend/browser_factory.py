"""
Browser Factory: Robust multi-tier WebDriver initialization for Chrome, Edge, and Brave.
Supports Windows Registry discovery, ChromeDriverManager, Selenium Manager, and automatic Edge fallback.
"""

import os
import sys
import shutil
import time
import tempfile
import threading
from typing import Optional, Callable, Tuple, List
from selenium import webdriver

GLOBAL_DRIVER_LOCK = threading.Lock()

def get_installed_browsers() -> List[Tuple[str, str]]:
    """
    Returns a list of (engine_name, executable_path) found on the system.
    Engine names: 'chrome', 'edge', 'brave'
    """
    found = []
    seen_paths = set()

    def add_if_exists(engine: str, p: Optional[str]):
        if p and p not in seen_paths and os.path.exists(p):
            seen_paths.add(p)
            found.append((engine, p))

    if os.name == "nt":
        import winreg
        # 1. Check Windows Registry (App Paths) - most accurate on Windows
        for engine, reg_name in [("chrome", "chrome.exe"), ("edge", "msedge.exe"), ("brave", "brave.exe")]:
            for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root_key, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{reg_name}") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            add_if_exists(engine, val)
                except Exception:
                    pass

        # 2. Check Standard Windows paths
        candidates = [
            ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            ("chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            ("chrome", os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")),
            ("chrome", os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe")),
            ("edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            ("edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            ("edge", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")),
            ("brave", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ("brave", r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        for engine, path in candidates:
            add_if_exists(engine, path)

    else:
        # Linux (Render, Docker, VPS, Ubuntu)
        render_chrome = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
        add_if_exists("chrome", render_chrome)

        for binary in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
            p = shutil.which(binary)
            if p:
                add_if_exists("chrome", p)
        for p in ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser"]:
            add_if_exists("chrome", p)

    return found


def _build_common_args(profile_dir: Optional[str], headless: bool) -> List[str]:
    args = [
        "--disable-notifications",
        "--disable-popup-blocking",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-dev-shm-usage",
        "--remote-allow-origins=*",
        "--window-size=1920,1080",
        "--disable-blink-features=AutomationControlled",
        "--blink-settings=imagesEnabled=false",
        "--disable-extensions",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disk-cache-size=10485760",
        "--media-cache-size=10485760",
        "--js-flags=--max-old-space-size=512",
    ]
    if profile_dir:
        args.append(f"--user-data-dir={profile_dir}")

    if os.name != "nt":
        args.extend(["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])

    if headless or os.name != "nt":
        args.extend(["--headless=new"])

    return args


def create_robust_driver(
    headless: bool = True,
    profile_dir: Optional[str] = None,
    log_fn: Optional[Callable[[str], None]] = None,
) -> Tuple[webdriver.Remote, str]:
    """
    Creates and returns a working WebDriver (Chrome or Edge) with automatic fallback.
    Returns: (driver_instance, engine_name)
    """
    def log(msg: str):
        if log_fn:
            try:
                log_fn(msg)
            except Exception:
                pass

    browsers = get_installed_browsers()
    args = _build_common_args(profile_dir, headless)

    # Reorder browsers: Chrome first, then Edge, then Brave
    chrome_candidates = [b for b in browsers if b[0] in ("chrome", "brave")]
    edge_candidates = [b for b in browsers if b[0] == "edge"]

    # If no specific browser found on Windows, still try default Chrome then default Edge
    if not chrome_candidates and not edge_candidates:
        chrome_candidates = [("chrome", None)]
        edge_candidates = [("edge", None)]

    errors = []

    with GLOBAL_DRIVER_LOCK:
        # ---------------- Tier 1: Try Chrome / Brave ----------------
        for engine, browser_path in chrome_candidates:
            try:
                log(f"กำลังเปิดเบราว์เซอร์ Google Chrome ({browser_path or 'ค่าเริ่มต้น'})...")
                options = webdriver.ChromeOptions()
                if browser_path:
                    options.binary_location = browser_path
                for a in args:
                    options.add_argument(a)

                # Method 1.1: Local or system chromedriver
                local_driver = (
                    shutil.which("chromedriver")
                    or ("/usr/bin/chromedriver" if os.path.exists("/usr/bin/chromedriver") else None)
                    or (os.path.join(getattr(sys, "_MEIPASS", ""), "chromedriver.exe") if getattr(sys, "frozen", False) else None)
                )

                if local_driver and os.path.exists(local_driver):
                    try:
                        from selenium.webdriver.chrome.service import Service
                        driver = webdriver.Chrome(service=Service(local_driver), options=options)
                        return driver, engine
                    except Exception as e:
                        errors.append(f"Local chromedriver failed: {e}")

                # Method 1.2: ChromeDriverManager (downloads or uses cached driver)
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    from selenium.webdriver.chrome.service import Service
                    driver_exec = ChromeDriverManager().install()
                    if driver_exec:
                        driver = webdriver.Chrome(service=Service(driver_exec), options=options)
                        return driver, engine
                except Exception as e:
                    errors.append(f"ChromeDriverManager failed: {e}")

                # Method 1.3: Selenium 4 built-in Selenium Manager
                try:
                    driver = webdriver.Chrome(options=options)
                    return driver, engine
                except Exception as e:
                    errors.append(f"Selenium Manager Chrome failed: {e}")

            except Exception as e:
                errors.append(f"Chrome attempt failed: {e}")

        # ---------------- Tier 2: Automatic Fallback to Microsoft Edge ----------------
        # Almost every Windows machine has Edge pre-installed
        if os.name == "nt":
            for engine, browser_path in (edge_candidates or [("edge", None)]):
                try:
                    log("⚠️ กำลังสลับไปใช้ Microsoft Edge อัตโนมัติ...")
                    options = webdriver.EdgeOptions()
                    if browser_path:
                        options.binary_location = browser_path
                    for a in args:
                        options.add_argument(a)

                    # Method 2.1: Selenium Manager Edge
                    try:
                        driver = webdriver.Edge(options=options)
                        log("✅ เปิดใช้งานผ่าน Microsoft Edge สำเร็จ")
                        return driver, "edge"
                    except Exception as e:
                        errors.append(f"Selenium Manager Edge failed: {e}")

                    # Method 2.2: EdgeChromiumDriverManager
                    try:
                        from webdriver_manager.microsoft import EdgeChromiumDriverManager
                        from selenium.webdriver.edge.service import Service
                        driver_exec = EdgeChromiumDriverManager().install()
                        if driver_exec:
                            driver = webdriver.Edge(service=Service(driver_exec), options=options)
                            log("✅ เปิดใช้งานผ่าน Microsoft Edge สำเร็จ")
                            return driver, "edge"
                    except Exception as e:
                        errors.append(f"EdgeChromiumDriverManager failed: {e}")

                except Exception as e:
                    errors.append(f"Edge attempt failed: {e}")

    # ---------------- If All Failed ----------------
    detailed_err = " | ".join(errors[-2:]) if errors else "No compatible browser found"
    err_msg = (
        "❌ ไม่สามารถเปิดเบราว์เซอร์ได้: เครื่องนี้อาจยังไม่ได้ติดตั้ง Google Chrome หรือเบราว์เซอร์ถูกบล็อก "
        "กรุณาดาวน์โหลดและติดตั้ง Google Chrome (ฟรีที่ https://www.google.com/chrome) แล้วลองใหม่อีกครั้ง"
    )
    log(err_msg)
    raise RuntimeError(f"{err_msg} (รายละเอียด: {detailed_err})")
