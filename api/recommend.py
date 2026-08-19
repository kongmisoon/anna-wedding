"""
api/recommend.py

Vercel Python Serverless Function — POST /api/recommend

역할
  1. 요청 바디({region, budget, style, weddingMonth, priority})의 필수값을 검증한다.
  2. 총예산을 5개 항목(드레스 / 스튜디오 촬영 / 메이크업&헤어 / 부대비용 / 예비비)으로
     서버에서 직접 계산한다. 금액 계산을 AI에 맡기지 않으므로 합계가 총예산을 넘는 일이 없다.
     (반올림으로 남는 금액은 전부 예비비에서 흡수한다.)
  3. 콘셉트 제안 / 항목별 코멘트 / 진행 팁 등 "글" 부분만 Claude API에 맡기고,
     구조화 출력(output_config.format)으로 JSON 스키마를 강제해 파싱 실패를 방지한다.
  4. 프론트가 그대로 렌더링할 수 있는 JSON을 반환한다.

주의
  - API 키는 환경 변수(ANTHROPIC_API_KEY)에서만 읽는다. 코드에 하드코딩하지 않는다.
"""

import json
import logging
import os
import traceback
from http.server import BaseHTTPRequestHandler

import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

MODEL_ID = "claude-opus-5"
API_TIMEOUT_SECONDS = 25.0

ALLOWED_REGIONS = ("서울", "대전", "충청권", "부산", "전주")
ALLOWED_STYLES = ("로맨틱", "모던 시크", "클래식", "내추럴", "럭셔리")

# 사용자가 고르는 우선순위 값 → 예산 항목명 매핑
PRIORITY_TO_ITEM = {
    "드레스": "드레스",
    "스튜디오촬영": "스튜디오 촬영",
    "메이크업&헤어": "메이크업&헤어",
}

# 예비비 고정 비율(총예산의 8%) — 기획서의 5~10% 범위 안에 들어간다.
RESERVE_RATIO = 0.08

# 예비비를 제외한 4개 항목의 기본 가중치(합계 92)
BASE_WEIGHTS = {
    "드레스": 30.0,
    "스튜디오 촬영": 28.0,
    "메이크업&헤어": 18.0,
    "부대비용": 16.0,
}

# 우선순위로 선택된 항목에 곱하는 가중치
PRIORITY_BOOST = 1.35

# 지역별 최소 권장 예산(만원 단위)
REGION_MIN_BUDGET = {
    "서울": 450,
    "부산": 380,
    "대전": 300,
    "충청권": 280,
    "전주": 280,
}

# 스타일별 최소 권장 예산 배수
STYLE_MULTIPLIER = {
    "럭셔리": 1.35,
    "클래식": 1.10,
    "모던 시크": 1.05,
    "로맨틱": 1.00,
    "내추럴": 0.95,
}

# 항목 순서(응답에서 항상 이 순서를 유지한다)
ITEM_ORDER = ["드레스", "스튜디오 촬영", "메이크업&헤어", "부대비용", "예비비"]

# 스키마 키 ↔ 항목명 매핑 (JSON 스키마는 ASCII 키를 사용한다)
COMMENT_KEYS = {
    "드레스": "comment_dress",
    "스튜디오 촬영": "comment_studio",
    "메이크업&헤어": "comment_makeup",
    "부대비용": "comment_extra",
    "예비비": "comment_reserve",
}

# Claude에 강제할 응답 스키마
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "패키지 이름. 15자 이내의 한국어 문구."},
        "dress": {"type": "string", "description": "드레스 콘셉트 제안. 2~3문장."},
        "studio": {"type": "string", "description": "스튜디오 촬영 콘셉트 제안. 2~3문장."},
        "makeup": {"type": "string", "description": "메이크업&헤어 스타일 제안. 2~3문장."},
        "comment_dress": {"type": "string", "description": "드레스 예산에 대한 한 줄 시세 코멘트."},
        "comment_studio": {"type": "string", "description": "스튜디오 촬영 예산에 대한 한 줄 시세 코멘트."},
        "comment_makeup": {"type": "string", "description": "메이크업&헤어 예산에 대한 한 줄 시세 코멘트."},
        "comment_extra": {"type": "string", "description": "부대비용(소품·부케·한복 등)에 대한 한 줄 코멘트."},
        "comment_reserve": {"type": "string", "description": "예비비 활용에 대한 한 줄 코멘트."},
        "tip": {"type": "string", "description": "해당 지역·시기 기준 진행 팁과 다음 단계 안내. 3~4문장."},
    },
    "required": [
        "headline", "dress", "studio", "makeup",
        "comment_dress", "comment_studio", "comment_makeup",
        "comment_extra", "comment_reserve", "tip",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "당신은 한국 웨딩 시장을 잘 아는 웨딩 토탈 디렉터입니다. "
    "서울, 대전, 충청권, 부산, 전주 지역의 드레스·스튜디오촬영·메이크업&헤어 시세와 진행 방식에 익숙합니다. "
    "예비 신랑신부에게 정중하고 담백한 존댓말로, 과장 없이 현실적인 조언을 합니다. "
    "금액은 이미 계산되어 주어지므로 새로 계산하거나 다른 숫자를 제시하지 마세요. "
    "주어진 금액을 전제로 그 예산에서 무엇이 가능한지 설명하세요."
)


# ---------------------------------------------------------------------------
# 예산 계산
# ---------------------------------------------------------------------------

def build_budget_plan(total_manwon: int, priority_item: str):
    """총예산(만원)을 5개 항목으로 나눈다.

    반환값의 금액 합계는 항상 입력 총예산과 정확히 일치한다.

    계산 순서
      1. 예비비를 총예산의 8%로 먼저 확정한다(1만원 단위 반올림).
         잔돈을 예비비에 몰아넣으면 총예산이 작을 때 예비비 비율이
         기획 범위(5~10%)를 넘어서기 때문에, 예비비를 먼저 고정한다.
      2. 남은 금액을 4개 항목에 가중치대로 나누되 1만원 단위로 내림한다.
      3. 내림으로 남은 잔돈(최대 3만원)은 1순위 항목이 흡수한다.
    """
    total_won = total_manwon * 10_000

    # 1) 예비비 확정
    reserve = int(round(total_won * RESERVE_RATIO / 10_000)) * 10_000
    distributable_won = total_won - reserve

    weights = dict(BASE_WEIGHTS)
    if priority_item in weights:
        weights[priority_item] *= PRIORITY_BOOST
    weight_sum = sum(weights.values())

    # 2) 4개 항목 배분 (1만원 단위 내림)
    plan = []
    allocated = 0
    for name in ITEM_ORDER:
        if name == "예비비":
            continue
        amount = int(distributable_won * weights[name] / weight_sum // 10_000) * 10_000
        allocated += amount
        plan.append({"item": name, "amount": amount})

    # 3) 잔돈은 1순위 항목에 더한다 (합계를 총예산과 정확히 일치시킴)
    leftover = distributable_won - allocated
    if leftover:
        target = next(
            (entry for entry in plan if entry["item"] == priority_item),
            plan[0],
        )
        target["amount"] += leftover

    plan.append({"item": "예비비", "amount": reserve})

    # 실제 금액 기준으로 비율을 다시 계산한다
    for entry in plan:
        entry["percent"] = round(entry["amount"] / total_won * 100, 1)

    return plan


def check_budget_shortage(region: str, style: str, total_manwon: int):
    """지역·스타일 조합의 최소 권장 예산과 비교해 안내 문구를 만든다."""
    base = REGION_MIN_BUDGET.get(region, 300)
    recommended = int(base * STYLE_MULTIPLIER.get(style, 1.0))
    if total_manwon >= recommended:
        return None, recommended
    return (
        "입력하신 예산({input:,}만원)은 {region} · {style} 조합의 최소 권장 예산"
        "({rec:,}만원)보다 낮습니다. 일부 항목은 조정이 필요할 수 있어요. "
        "1순위 항목에 집중하고 나머지는 기본 구성으로 맞추는 방식을 권장드립니다."
    ).format(input=total_manwon, region=region, style=style, rec=recommended), recommended


# ---------------------------------------------------------------------------
# 요청 검증
# ---------------------------------------------------------------------------

def validate_payload(payload):
    """필수값을 검증하고 (정규화된 값, 오류 메시지) 튜플을 돌려준다."""
    if not isinstance(payload, dict):
        return None, "필수 입력값이 누락되었습니다."

    region = (payload.get("region") or "").strip()
    style = (payload.get("style") or "").strip()
    wedding_month = (payload.get("weddingMonth") or "").strip()
    priority = (payload.get("priority") or "").strip()
    budget_raw = payload.get("budget")

    if not region or not style or not wedding_month or not priority or budget_raw in (None, ""):
        return None, "필수 입력값이 누락되었습니다. 지역, 예산, 스타일, 예식 시기, 우선순위를 모두 선택해 주세요."

    if region not in ALLOWED_REGIONS:
        return None, "지원하지 않는 지역입니다. 서울, 대전, 충청권, 부산, 전주 중에서 선택해 주세요."

    if style not in ALLOWED_STYLES:
        return None, "지원하지 않는 웨딩 스타일입니다."

    if priority not in PRIORITY_TO_ITEM:
        return None, "가장 중요한 항목은 드레스, 스튜디오촬영, 메이크업&헤어 중에서 선택해 주세요."

    try:
        budget = int(float(budget_raw))
    except (TypeError, ValueError):
        return None, "총예산은 숫자(만원 단위)로 입력해 주세요."

    if budget < 100 or budget > 5000:
        return None, "총예산은 100만원 이상 5,000만원 이하로 입력해 주세요."

    return {
        "region": region,
        "budget": budget,
        "style": style,
        "weddingMonth": wedding_month,
        "priority": priority,
    }, None


# ---------------------------------------------------------------------------
# Claude 호출
# ---------------------------------------------------------------------------

def build_user_prompt(data, plan, recommended_manwon, shortage_message):
    """계산된 예산 배분을 포함한 사용자 프롬프트를 만든다."""
    lines = [
        "아래 예비부부의 조건에 맞춰 웨딩 패키지 방향을 제안해 주세요.",
        "",
        "[입력 조건]",
        "- 예식 지역: {}".format(data["region"]),
        "- 총예산: {:,}만원".format(data["budget"]),
        "- 웨딩 스타일 취향: {}".format(data["style"]),
        "- 예식 예정 시기: {}".format(data["weddingMonth"]),
        "- 가장 중요한 항목(1순위): {}".format(data["priority"]),
        "- 이 지역·스타일의 최소 권장 예산: 약 {:,}만원".format(recommended_manwon),
        "",
        "[이미 확정된 항목별 예산 — 이 금액을 전제로 설명하세요]",
    ]
    for entry in plan:
        lines.append(
            "- {}: {:,}원 (총예산의 {}%)".format(entry["item"], entry["amount"], entry["percent"])
        )

    if shortage_message:
        lines += [
            "",
            "[참고] 이 예산은 해당 지역·스타일의 최소 권장 예산보다 낮습니다. "
            "무리한 기대를 심어주지 말고, 이 예산 안에서 현실적으로 가능한 선택지를 알려주세요.",
        ]

    lines += [
        "",
        "[작성 지침]",
        "- 1순위 항목에 예산이 더 배정되어 있으므로 그 항목을 조금 더 구체적으로 설명하세요.",
        "- 각 코멘트는 해당 금액으로 무엇이 가능한지 한 문장으로 알려주세요.",
        "- 진행 팁에는 해당 지역의 진행 방식, 예식 시기에 따른 주의점, "
        "그리고 애나웨딩 디렉터 상담을 권하는 자연스러운 마무리를 포함하세요.",
        "- 특정 업체명이나 브랜드명은 언급하지 마세요.",
    ]
    return "\n".join(lines)


def call_claude(system_prompt, user_prompt):
    """Claude에 구조화 출력을 요청하고 파싱된 dict를 돌려준다."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key, timeout=API_TIMEOUT_SECONDS)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=4000,
        system=system_prompt,
        # effort를 낮춰 응답 지연을 줄인다. 스키마 강제는 output_config.format으로 처리.
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
        messages=[{"role": "user", "content": user_prompt}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("모델이 요청을 거절했습니다(stop_reason=refusal).")

    text = next((block.text for block in response.content if block.type == "text"), None)
    if not text:
        raise RuntimeError("모델 응답에 텍스트 블록이 없습니다.")

    return json.loads(text)


# ---------------------------------------------------------------------------
# HTTP 핸들러
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    """Vercel Python 런타임이 사용하는 진입점 클래스."""

    # 기본 로그가 stderr를 어지럽히지 않도록 정리
    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        # 로컬 개발(정적 서버와 API 포트가 다른 경우) 대비 CORS 허용
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        self._send_json(405, {"error": "POST 메서드로 요청해 주세요."})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0

        if length <= 0:
            self._send_json(400, {"error": "필수 입력값이 누락되었습니다."})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, {"error": "요청 형식이 올바르지 않습니다. JSON으로 전송해 주세요."})
            return

        # 1) 필수값 검증
        data, error = validate_payload(payload)
        if error:
            self._send_json(400, {"error": error})
            return

        # 2) 예산 계산 (서버에서 확정)
        priority_item = PRIORITY_TO_ITEM[data["priority"]]
        plan = build_budget_plan(data["budget"], priority_item)
        shortage_message, recommended = check_budget_shortage(
            data["region"], data["style"], data["budget"]
        )

        # 3) Claude 호출
        try:
            ai = call_claude(
                SYSTEM_PROMPT,
                build_user_prompt(data, plan, recommended, shortage_message),
            )
        except RuntimeError as exc:
            logger.error("AI 호출 실패(설정/응답 오류): %s", exc)
            self._send_json(500, {
                "error": "추천 생성 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요."
            })
            return
        except anthropic.APIStatusError as exc:
            logger.error("Claude API 상태 오류 %s: %s", exc.status_code, exc.message)
            self._send_json(500, {
                "error": "추천 서비스가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해 주세요."
            })
            return
        except anthropic.APITimeoutError:
            logger.error("Claude API 타임아웃 (%.0f초 초과)", API_TIMEOUT_SECONDS)
            self._send_json(500, {
                "error": "응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요."
            })
            return
        except anthropic.APIConnectionError as exc:
            logger.error("Claude API 연결 실패: %s", exc)
            self._send_json(500, {
                "error": "네트워크 문제로 추천을 불러오지 못했어요. 잠시 후 다시 시도해 주세요."
            })
            return
        except Exception:  # 예기치 못한 오류도 사용자에게는 친화적으로
            logger.error("예기치 못한 오류:\n%s", traceback.format_exc())
            self._send_json(500, {
                "error": "추천을 불러오는 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요."
            })
            return

        # 4) 프론트가 바로 렌더링할 수 있는 형태로 조립
        for entry in plan:
            entry["comment"] = ai.get(COMMENT_KEYS[entry["item"]], "")

        result = {
            "headline": ai.get("headline", ""),
            "recommendation": {
                "dress": ai.get("dress", ""),
                "studio": ai.get("studio", ""),
                "makeup": ai.get("makeup", ""),
            },
            "budgetPlan": plan,
            "tip": ai.get("tip", ""),
            "budgetWarning": shortage_message,
            "meta": {
                "region": data["region"],
                "budget": data["budget"],
                "style": data["style"],
                "weddingMonth": data["weddingMonth"],
                "priority": data["priority"],
                "recommendedMinBudget": recommended,
                "model": MODEL_ID,
            },
        }
        self._send_json(200, result)
