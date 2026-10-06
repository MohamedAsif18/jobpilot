import os
import sys
import json
import time
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--company", default="Company")
    parser.add_argument("--role", default="Oracle DBA")
    parser.add_argument("--mode", choices=["preview", "submit"], default="preview")
    parser.add_argument("--profile", default="data/profile.json")
    parser.add_argument("--resume", default="data/resume.pdf")
    parser.add_argument("--outdir", default="artifacts/application_run")
    return parser.parse_args()

def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with open(args.profile, "r", encoding="utf-8") as f:
        profile = json.load(f)

    resume_path = Path(args.resume).resolve()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        
        print(f"[1/4] Loading {args.url}...")
        try:
            page.goto(args.url, wait_until="networkidle", timeout=45000)
        except Exception:
            pass
        page.screenshot(path=str(outdir / "01_landing.png"), full_page=True)

        # Policy-safety check for CAPTCHA
        html_lower = page.content().lower()
        if any(c in html_lower for c in ["g-recaptcha", "h-captcha", "cf-turnstile", "verify you are human"]):
            print("[SAFETY PAUSE] CAPTCHA detected. Human intervention required.")
            page.screenshot(path=str(outdir / "PAUSE_CAPTCHA_DETECTED.png"), full_page=True)
            browser.close()
            return

        # Auto-fill standard fields
        print("[2/4] Auto-filling fields...")
        def fill_input(selectors, val):
            for s in selectors:
                try:
                    loc = page.locator(s).first
                    if loc.is_visible(timeout=1000):
                        loc.fill(str(val))
                        return
                except Exception:
                    continue

        first = profile.get("first_name", "Mohamed")
        last = profile.get("last_name", "Bhadharudeen")
        fill_input(['input[name*="first_name" i]', '#first_name'], first)
        fill_input(['input[name*="last_name" i]', '#last_name'], last)
        fill_input(['input[name*="name" i]:not([name*="first"]):not([name*="last"])', '#name'], profile.get("name"))
        fill_input(['input[type="email"]', 'input[name*="email" i]'], profile.get("email"))
        fill_input(['input[type="tel"]', 'input[name*="phone" i]'], profile.get("phone"))
        fill_input(['input[name*="location" i]', 'input[name*="city" i]'], profile.get("location"))
        fill_input(['input[name*="linkedin" i]'], profile.get("linkedin_url"))
        fill_input(['textarea[name*="summary" i]', 'textarea[name*="cover" i]'], profile.get("summary"))

        # Resume file upload
        print("[3/4] Attaching resume...")
        if resume_path.exists():
            file_input = page.locator('input[type="file"]').first
            if file_input.count() > 0:
                file_input.set_input_files(str(resume_path))

        time.sleep(2)
        page.screenshot(path=str(outdir / "02_filled_preview.png"), full_page=True)

        # Submission handling
        print(f"[4/4] Finalizing (Mode: {args.mode})...")
        if args.mode == "submit":
            for s in ['button[type="submit"]', 'button:has-text("Submit")']:
                try:
                    btn = page.locator(s).first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        time.sleep(5)
                        break
                except Exception:
                    continue
            page.screenshot(path=str(outdir / "03_submission_result.png"), full_page=True)

        browser.close()
        print("Done!")

if __name__ == "__main__":
    main()
