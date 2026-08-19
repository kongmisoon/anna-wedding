"""
tools/dev_server.py

로컬 개발/검증 전용 서버. (Vercel 배포와는 무관 — api/ 폴더 밖에 있으므로 함수로 배포되지 않는다)

하는 일
  - 정적 파일(index.html, css/, js/, images/)을 서빙한다.
  - POST /api/recommend 요청을 api/recommend.py 의 handler 로 그대로 넘긴다.
  - .env.local 파일이 있으면 읽어서 os.environ 에 주입한다.

실행:
  python tools/dev_server.py           # http://localhost:3000
  python tools/dev_server.py 4000      # 포트 지정
  python tools/dev_server.py --mock    # API 키 없이 UI만 확인 (AI 호출 없이 고정 문구 반환)

--mock 모드는 예산 계산은 실제 로직(api/recommend.py)을 그대로 쓰고,
AI가 만드는 "글" 부분만 고정 문구로 대체한다. UI 렌더링 확인 전용이다.
"""

import importlib.util
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_local():
    """.env.local 을 읽어 환경 변수로 주입한다(이미 설정된 값은 덮어쓰지 않음)."""
    path = os.path.join(ROOT, ".env.local")
    if not os.path.exists(path):
        print("[dev] .env.local 이 없습니다. ANTHROPIC_API_KEY 환경 변수를 직접 설정하세요.")
        return
    with open(path, "r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
    print("[dev] .env.local 로드 완료")


def load_api_module():
    """api/recommend.py 를 모듈로 불러온다."""
    spec = importlib.util.spec_from_file_location(
        "recommend_api", os.path.join(ROOT, "api", "recommend.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


load_env_local()
api_module = load_api_module()
ApiHandler = api_module.handler

MOCK_MODE = "--mock" in sys.argv

MOCK_TEXT = {
    "headline": "[목업] 맞춤 웨딩 패키지",
    "dress": "[목업] 실제 배포 환경에서는 이 자리에 Claude가 생성한 드레스 콘셉트 제안이 표시됩니다.",
    "studio": "[목업] 실제 배포 환경에서는 이 자리에 스튜디오 촬영 콘셉트 제안이 표시됩니다.",
    "makeup": "[목업] 실제 배포 환경에서는 이 자리에 메이크업&헤어 스타일 제안이 표시됩니다.",
    "comment_dress": "[목업] 이 금액대의 드레스 시세 코멘트가 들어갑니다.",
    "comment_studio": "[목업] 이 금액대의 스튜디오 촬영 시세 코멘트가 들어갑니다.",
    "comment_makeup": "[목업] 이 금액대의 메이크업&헤어 시세 코멘트가 들어갑니다.",
    "comment_extra": "[목업] 소품·부케·부모님 한복 등 부대비용 코멘트가 들어갑니다.",
    "comment_reserve": "[목업] 돌발 지출 대비 예비비 활용 코멘트가 들어갑니다.",
    "tip": "[목업] 지역별 진행 팁과 상담 신청 안내 문구가 이 자리에 표시됩니다. "
           "실제 문구는 ANTHROPIC_API_KEY를 설정한 뒤 확인할 수 있습니다.",
}


class DevHandler(SimpleHTTPRequestHandler):
    """정적 파일 + /api/recommend 라우팅을 함께 처리한다."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _handle_mock(self):
        """AI 호출 없이, 실제 예산 로직 + 고정 문구로 응답을 만든다."""
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = {}

        data, error = api_module.validate_payload(payload)
        if error:
            self._write_json(400, {"error": error})
            return

        priority_item = api_module.PRIORITY_TO_ITEM[data["priority"]]
        plan = api_module.build_budget_plan(data["budget"], priority_item)
        warning, recommended = api_module.check_budget_shortage(
            data["region"], data["style"], data["budget"]
        )
        for entry in plan:
            entry["comment"] = MOCK_TEXT[api_module.COMMENT_KEYS[entry["item"]]]

        self._write_json(200, {
            "headline": "[목업] {} {} 웨딩 패키지".format(data["region"], data["style"]),
            "recommendation": {
                "dress": MOCK_TEXT["dress"],
                "studio": MOCK_TEXT["studio"],
                "makeup": MOCK_TEXT["makeup"],
            },
            "budgetPlan": plan,
            "tip": MOCK_TEXT["tip"],
            "budgetWarning": warning,
            "meta": {"mock": True, "recommendedMinBudget": recommended},
        })

    def _write_json(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _delegate_to_api(self, method):
        # ApiHandler 인스턴스를 만들지 않고, 이미 열린 소켓/스트림 위에서 메서드만 빌려 쓴다.
        bound = ApiHandler.__new__(ApiHandler)
        bound.rfile = self.rfile
        bound.wfile = self.wfile
        bound.headers = self.headers
        bound.request_version = self.request_version
        bound.client_address = self.client_address
        bound.command = self.command
        bound.path = self.path
        bound.requestline = self.requestline
        bound.send_response = self.send_response
        bound.send_header = self.send_header
        bound.end_headers = self.end_headers
        bound.address_string = self.address_string
        getattr(bound, method)()

    def do_POST(self):
        if self.path.split("?")[0] == "/api/recommend":
            if MOCK_MODE:
                self._handle_mock()
            else:
                self._delegate_to_api("do_POST")
            return
        self.send_error(404, "Not Found")

    def do_OPTIONS(self):
        if self.path.split("?")[0] == "/api/recommend":
            self._delegate_to_api("do_OPTIONS")
            return
        self.send_error(404, "Not Found")

    def do_GET(self):
        # /api/* 로 온 GET은 Vercel과 동일하게 함수로 넘긴다(405 응답 확인용)
        if self.path.split("?")[0] == "/api/recommend":
            self._delegate_to_api("do_GET")
            return
        super().do_GET()

    def end_headers(self):
        # 개발 중 캐시로 인한 혼란 방지
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    ports = [arg for arg in sys.argv[1:] if arg.isdigit()]
    port = int(ports[0]) if ports else 3000
    if MOCK_MODE:
        print("[dev] MOCK 모드 — AI를 호출하지 않고 고정 문구로 응답합니다.")
    print("[dev] http://localhost:{} 에서 실행 중 (Ctrl+C 로 종료)".format(port))
    ThreadingHTTPServer(("127.0.0.1", port), DevHandler).serve_forever()
