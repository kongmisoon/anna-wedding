"""
tools/capture_screenshots.py

제출용 스크린샷을 자동으로 캡처한다. (개발/문서화 전용 — 배포와 무관)

사전 준비
  pip install playwright
  python -m playwright install chromium
  python tools/dev_server.py --mock      # 다른 터미널에서 실행

실행
  python tools/capture_screenshots.py                    # 기본 http://localhost:3000
  python tools/capture_screenshots.py http://localhost:3000

결과물은 docs/screenshots/ 에 저장된다.
"""

import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"


def fill_and_submit(page):
    """AI 추천 폼을 채우고 제출한 뒤 결과가 나올 때까지 기다린다."""
    page.select_option("#region", "대전")
    page.fill("#budget", "500")            # range 입력
    page.select_option("#style", "로맨틱")
    page.fill("#weddingMonth", "2026-11")
    # 라디오 input은 칩 UI를 위해 시각적으로 숨겨져 있으므로,
    # 실제 사용자와 동일하게 라벨(칩)을 클릭한다.
    page.click('.radio-chip:has(input[value="스튜디오촬영"]) span')
    page.click("#submitBtn")
    page.wait_for_selector("#resultOutput:not([hidden])", timeout=45000)
    page.wait_for_timeout(1200)            # 바 차트 트랜지션 마무리 대기


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ---------- 1. 데스크톱 전체 화면 ----------
        desktop = browser.new_context(viewport={"width": 1440, "height": 900},
                                      device_scale_factor=2, locale="ko-KR")
        page = desktop.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(OUT_DIR, "01-desktop-full.png"), full_page=True)
        page.screenshot(path=os.path.join(OUT_DIR, "02-desktop-hero.png"))
        print("저장: 01-desktop-full.png / 02-desktop-hero.png (1440x900)")

        # ---------- 2. AI 기능 동작 화면 (데스크톱) ----------
        page.goto(BASE_URL + "/#ai-recommend", wait_until="networkidle")
        page.wait_for_timeout(600)
        fill_and_submit(page)
        page.locator("#ai-recommend").screenshot(
            path=os.path.join(OUT_DIR, "03-ai-result-desktop.png"))
        print("저장: 03-ai-result-desktop.png (AI 추천 결과)")

        # ---------- 3. 실패 처리: 빈 입력 ----------
        # 해시만 다른 URL로 이동하면 리로드가 일어나지 않아 이전 입력값이 남는다.
        # 깨끗한 상태를 보장하기 위해 새 페이지를 연다.
        blank = desktop.new_page()
        blank.goto(BASE_URL, wait_until="networkidle")
        blank.evaluate("document.getElementById('ai-recommend').scrollIntoView()")
        blank.wait_for_timeout(600)
        blank.click("#submitBtn")
        blank.wait_for_selector("#formError:not([hidden])", timeout=5000)
        blank.locator(".ai-layout").screenshot(
            path=os.path.join(OUT_DIR, "04-validation-error.png"))
        print("저장: 04-validation-error.png (빈 입력 검증)")
        desktop.close()

        # ---------- 4. 모바일 ----------
        mobile = browser.new_context(viewport={"width": 375, "height": 812},
                                     device_scale_factor=3, is_mobile=True,
                                     has_touch=True, locale="ko-KR")
        m = mobile.new_page()
        m.goto(BASE_URL, wait_until="networkidle")
        m.wait_for_timeout(1000)
        m.screenshot(path=os.path.join(OUT_DIR, "05-mobile-full.png"), full_page=True)
        m.screenshot(path=os.path.join(OUT_DIR, "06-mobile-hero.png"))

        # 햄버거 메뉴 열린 상태
        m.click("#navToggle")
        m.wait_for_timeout(500)
        m.screenshot(path=os.path.join(OUT_DIR, "07-mobile-menu.png"))
        m.click("#navToggle")
        m.wait_for_timeout(400)
        print("저장: 05-mobile-full.png / 06-mobile-hero.png / 07-mobile-menu.png (375x812)")

        # 모바일 AI 결과
        m.goto(BASE_URL + "/#ai-recommend", wait_until="networkidle")
        m.wait_for_timeout(600)
        fill_and_submit(m)
        m.locator("#ai-recommend").screenshot(
            path=os.path.join(OUT_DIR, "08-ai-result-mobile.png"))
        print("저장: 08-ai-result-mobile.png (모바일 AI 추천 결과)")

        mobile.close()
        browser.close()

    print("\n완료 — {}".format(OUT_DIR))


if __name__ == "__main__":
    main()
