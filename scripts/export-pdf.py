#!/usr/bin/env python3
"""
Slides-to-Web → PDF エクスポーター
"""

import os, sys, base64, glob
from pathlib import Path
from playwright.sync_api import sync_playwright

SLIDES_DIR = Path(__file__).parent.parent / "slides"
OUTPUT_PDF = SLIDES_DIR / "exports" / "presentation.pdf"
WIDTH = 1920
HEIGHT = 1080

CHROME_PATHS = glob.glob("/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome")
CHROME = CHROME_PATHS[0] if CHROME_PATHS else None

def main():
    if not CHROME:
        print("Chromium not found. Run: playwright install chromium")
        sys.exit(1)

    os.makedirs(OUTPUT_PDF.parent, exist_ok=True)

    # Read HTML and CSS, inline everything to avoid external requests
    html_path = SLIDES_DIR / "index.html"
    css_path = SLIDES_DIR / "themes" / "default.css"
    engine_path = SLIDES_DIR / "engine.js"

    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    engine_js = engine_path.read_text(encoding="utf-8")

    # Remove external font links and script/css references, inline them
    import re
    html = re.sub(r'<link[^>]*fonts\.googleapis[^>]*>', '', html)
    html = re.sub(r'<link[^>]*fonts\.gstatic[^>]*>', '', html)
    html = re.sub(r'<link[^>]*rel="preconnect"[^>]*>', '', html)
    html = re.sub(r'<link[^>]*href="themes/default\.css"[^>]*>', f'<style>{css}</style>', html)
    html = re.sub(r'<script[^>]*src="engine\.js"[^>]*></script>', f'<script>{engine_js}</script>', html)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(html, wait_until="domcontentloaded")
        page.wait_for_timeout(500)

        total = page.evaluate("document.querySelectorAll('.slide').length")
        print(f"Found {total} slides")

        screenshots = []
        for i in range(total):
            page.evaluate(f"""() => {{
                document.querySelectorAll('.slide').forEach((s, j) => {{
                    s.classList.toggle('active', j === {i});
                }});
            }}""")
            page.wait_for_timeout(400)

            path = f"/tmp/slide-{i:03d}.png"
            page.screenshot(path=path)
            screenshots.append(path)
            print(f"  Slide {i+1}/{total} captured")

        # Build PDF
        img_tags = ""
        for s in screenshots:
            with open(s, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            img_tags += (
                f'<div style="width:{WIDTH}px;height:{HEIGHT}px;page-break-after:always;">'
                f'<img src="data:image/png;base64,{b64}" style="width:100%;height:100%;">'
                f'</div>'
            )

        pdf_page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        pdf_page.set_content(
            f'<!DOCTYPE html><html><body style="margin:0;padding:0;">{img_tags}</body></html>',
            wait_until="domcontentloaded",
        )
        pdf_page.wait_for_timeout(500)
        pdf_page.pdf(
            path=str(OUTPUT_PDF),
            width=f"{WIDTH}px",
            height=f"{HEIGHT}px",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )

        browser.close()

        for s in screenshots:
            os.unlink(s)

    print(f"\nPDF exported: {OUTPUT_PDF}")

if __name__ == "__main__":
    main()
