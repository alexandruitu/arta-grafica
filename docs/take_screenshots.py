"""Take screenshots of each tab using pyppeteer (headless Chrome)."""
import asyncio
import os
from pyppeteer import launch

BASE_URL = "http://localhost:5173"
OUT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")

TABS = [
    ("dashboard", "Dashboard"),
    ("gantt", "Gantt"),
    ("board", "Board Masini"),
    ("comenzi", "Comenzi"),
    ("planificare", "Planificare"),
    ("stoc", "Stoc Materiale"),
]

async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    browser = await launch(
        headless=True,
        executablePath='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
    )
    page = await browser.newPage()
    await page.setViewport({'width': 1400, 'height': 900})

    for i, (tab_id, tab_name) in enumerate(TABS):
        print(f"Capturing {tab_name}...")
        await page.goto(BASE_URL, {'waitUntil': 'networkidle0', 'timeout': 15000})
        await asyncio.sleep(1)

        # Click the tab button
        buttons = await page.querySelectorAll('button')
        for btn in buttons:
            text = await page.evaluate('(el) => el.textContent', btn)
            if text and tab_name in text:
                await btn.click()
                break

        await asyncio.sleep(2)  # Wait for content to load

        path = os.path.join(OUT_DIR, f"{i+1}_{tab_id}.png")
        await page.screenshot({'path': path, 'fullPage': False})
        print(f"  Saved: {path}")

    await browser.close()
    print("Done!")

asyncio.get_event_loop().run_until_complete(main())
