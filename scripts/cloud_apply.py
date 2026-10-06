import os
import sys
import json
import time
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="JobPilot Cloud Application Runner")
    parser.add_argument("--url", required=True, help="Job application URL")
    parser.add_argument("--company", default="Target Company", help="Company name")
    parser.add_argument("--role", default="Target Role", help="Job role title")
    parser.add_argument("--mode", choices=["preview", "submit"], default="preview")
    parser.add_argument("--profile", default="data/profile.json", help="Path to profile JSON")
    parser.add_argument("--resume", default="data/resume.pdf", help="Path to resume PDF")
    parser.add_argument("--outdir", default="artifacts/application_run", help="Output directory")
    return parser.parse_args()

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    target_url = normalize_url(args.url)

    # 1. Load Profile
    profile_path = Path(args.profile)
    profile = {}
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

    resume_path = Path(args.resume).resolve()
    has_resume = resume_path.exists()

    print("=" * 60)
    print("🚀 JobPilot Cloud Application Runner (Stealth v2)")
    print(f"Target URL:   {target_url}")
    print(f"Mode:         {args.mode.upper()}")
    print("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] Playwright not installed.")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1366, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US"
        )
        page = context.new_page()

        # Stealth: mask automated browser
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        print(f"\n[1/4] Navigating to: {target_url}...")
        try:
            response = page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            print(f"[INFO] HTTP Response: {response.status if response else 'Loaded'}")
        except Exception as e:
            print(f"[WARN] Navigation notice: {e}")

        # Wait for React / client-side JS to finish rendering
        print("[INFO] Waiting for page components to render...")
        time.sleep(5)

        print(f"[INFO] Page Title: '{page.title()}'")

        # Capture landing screenshot
        initial_shot = outdir / "01_landing.png"
        page.screenshot(path=str(initial_shot), full_page=True)
        print(f"[+] Landing page screenshot saved: {initial_shot}")

        # Check for CAPTCHA
        html_lower = page.content().lower()
        if any(c in html_lower for c in ["g-recaptcha", "h-captcha", "cf-turnstile", "verify you are human"]):
            print("[SAFETY PAUSE] CAPTCHA detected. Human intervention required.")
            page.screenshot(path=str(outdir / "PAUSE_CAPTCHA_DETECTED.png"), full_page=True)
            browser.close()
            return

        # 2. Form Field Filling (Searches page and any embedded iframes)
        print("\n[2/4] Locating and populating form fields...")
        targets = [page] + page.frames

        def fill_first(selectors, value, label):
            if not value:
                return False
            for target in targets:
                for sel in selectors:
                    try:
                        loc = target.locator(sel).first
                        if loc.is_visible(timeout=800):
                            loc.fill(str(value))
                            print(f"  [+] Filled {label}: '{value}'")
                            return True
                    except Exception:
                        continue
            return False

        full_name = profile.get("name", "Mohamed Bhadharudeen")
        first_name = profile.get("first_name", "Mohamed")
        last_name = profile.get("last_name", "Bhadharudeen")

        fill_first(['input[name*="first_name" i]', '#first_name'], first_name, "First Name")
        fill_first(['input[name*="last_name" i]', '#last_name'], last_name, "Last Name")
        fill_first(['input[name*="name" i]:not([name*="first"]):not([name*="last"])', '#name'], full_name, "Full Name")
        fill_first(['input[type="email"]', 'input[name*="email" i]'], profile.get("email"), "Email")
        fill_first(['input[type="tel"]', 'input[name*="phone" i]'], profile.get("phone"), "Phone")
        fill_first(['input[name*="location" i]', 'input[name*="city" i]'], profile.get("location"), "Location")
        fill_first(['input[name*="linkedin" i]'], profile.get("linkedin_url"), "LinkedIn")
        fill_first(['textarea[name*="summary" i]', 'textarea[name*="cover" i]'], profile.get("summary"), "Summary")

        # 3. Resume PDF Attachment
        print("\n[3/4] Attaching resume...")
        if has_resume:
            for target in targets:
                file_input = target.locator('input[type="file"]').first
                if file_input.count() > 0:
                    try:
                        file_input.set_input_files(str(resume_path))
                        print(f"  [+] Attached resume: {resume_path.name}")
                        break
                    except Exception:
                        continue

        time.sleep(2)
        filled_shot = outdir / "02_filled_preview.png"
        page.screenshot(path=str(filled_shot), full_page=True)
        print(f"[+] Filled preview screenshot saved: {filled_shot}")

        # 4. Submission
        if args.mode == "submit":
            for target in targets:
                for s in ['button[type="submit"]', 'button:has-text("Submit")']:
                    try:
                        btn = target.locator(s).first
                        if btn.is_visible(timeout=1000):
                            btn.click()
                            time.sleep(5)
                            break
                    except Exception:
                        continue
            page.screenshot(path=str(outdir / "03_submission_result.png"), full_page=True)

        browser.close()
        print("✅ Run completed successfully!")

if __name__ == "__main__":
    main()
