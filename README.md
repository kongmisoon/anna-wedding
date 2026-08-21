# Anna Wedding (애나웨딩)

드레스 · 스튜디오촬영 · 메이크업&헤어 세 축을 중심으로, 서울 · 대전 · 충청권 · 부산 · 전주 지역
예비 신랑신부의 웨딩 준비를 연결하고 디렉팅하는 **웨딩 토탈 디렉팅 웹 서비스**입니다.

핵심 기능은 예산 · 취향 · 지역을 입력하면 AI가 맞춤 웨딩 패키지와 **항목별 예산 플랜**을 제안하는
`AI 맞춤 웨딩 추천`입니다.

- 배포 URL: _(Vercel 배포 후 여기에 기입)_
- 서비스 기획서: [docs/기획서.md](docs/기획서.md)
- 최초 프롬프트 원문: [docs/최초-프롬프트.md](docs/최초-프롬프트.md)

---

## 1. 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| 프론트엔드 | HTML5 / CSS3 / Vanilla JavaScript (프레임워크 미사용) |
| 백엔드 | Vercel Serverless Functions (Python 3.12) |
| AI | Anthropic Claude API (`claude-opus-5`), 구조화 출력(JSON Schema) 사용 |
| 배포 | GitHub → Vercel |

외부 CSS/JS 라이브러리는 사용하지 않았습니다. 예산 플랜 바 차트도 순수 CSS(`width: %`)로 구현했습니다.
웹폰트(Playfair Display, Noto Sans KR)만 Google Fonts에서 불러옵니다.

---

## 2. 폴더 구조

```
anna-wedding/
├── index.html              # 5개 섹션으로 구성된 단일 페이지
├── css/
│   └── style.css           # 전체 스타일 + 반응형 3단계 미디어쿼리
├── js/
│   ├── main.js             # 네비게이션, 탭, 슬라이더, 상담 폼 검증 등 공통 UI
│   └── ai-recommend.js     # AI 추천 폼 → fetch → 결과 렌더링 + 실패 처리
├── images/                 # 이미지 자산 (현재는 CSS/SVG로 대체)
├── api/
│   └── recommend.py        # POST /api/recommend 서버리스 함수
├── tools/
│   ├── dev_server.py       # 로컬 개발 서버 (배포에는 포함되지 않음)
│   └── capture_screenshots.py  # 제출용 스크린샷 자동 캡처
├── docs/
│   ├── 기획서.md            # 서비스 기획서
│   ├── 최초-프롬프트.md      # 개발에 사용한 최초 프롬프트 원문
│   └── screenshots/        # 캡처된 스크린샷
├── requirements.txt        # Python 의존성 (anthropic)
├── vercel.json             # 함수 메모리 / 최대 실행 시간 설정
├── .env.local.example      # 환경 변수 템플릿 (실제 키는 .env.local에)
├── .gitignore
└── README.md
```

---

## 3. 환경 변수 설정 방법

이 프로젝트는 API 키를 **환경 변수로만** 다룹니다. 코드나 문서에 키 값을 절대 적지 마세요.

| 변수명 | 설명 | 발급처 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Claude API 호출용 키 | <https://console.anthropic.com> → API Keys |

### 3-1. 로컬 개발

```bash
cp .env.local.example .env.local
```

생성된 `.env.local` 파일을 열어 발급받은 키를 붙여 넣습니다.

```
ANTHROPIC_API_KEY=<발급받은 키>
```

`.env.local`은 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

### 3-2. Vercel 배포

Vercel 대시보드 → **Project Settings → Environment Variables** 에서 등록합니다.

- Key: `ANTHROPIC_API_KEY`
- Value: 발급받은 키
- Environments: **Production, Preview, Development** 모두 체크

환경 변수를 추가하거나 변경한 뒤에는 **재배포(Redeploy)** 해야 반영됩니다.

---

## 4. 로컬 실행 방법

### 4-1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4-2. 개발 서버 실행

```bash
python tools/dev_server.py
```

<http://localhost:3000> 에서 확인할 수 있습니다.
이 서버는 정적 파일을 서빙하고 `POST /api/recommend` 요청을 `api/recommend.py`로 전달합니다.

### 4-3. API 키 없이 화면만 확인하기

키가 없어도 UI 렌더링을 확인할 수 있는 목(mock) 모드를 제공합니다.
예산 계산은 실제 로직을 그대로 사용하고, AI가 생성하는 문장만 고정 문구로 대체합니다.

```bash
python tools/dev_server.py --mock
```

### 4-4. Vercel CLI로 실행 (선택)

실제 배포 환경과 동일하게 확인하려면 Vercel CLI를 사용할 수 있습니다.

```bash
npm i -g vercel
vercel dev
```

---

## 5. 배포 방법

1. GitHub에 저장소를 생성하고 코드를 푸시합니다.
2. [Vercel](https://vercel.com) → **Add New → Project** → 해당 저장소를 Import 합니다.
3. Framework Preset은 **Other**, Root Directory는 `anna-wedding` 폴더를 지정합니다.
   (저장소 루트에 프로젝트를 두었다면 그대로 두면 됩니다.)
4. **Environment Variables**에 `ANTHROPIC_API_KEY`를 등록합니다. (3-2 참고)
5. **Deploy**를 누릅니다. `api/recommend.py`는 자동으로 서버리스 함수로 배포됩니다.

`vercel.json`에서 함수 메모리 1024MB, 최대 실행 시간 60초로 설정해 두었습니다.

---

## 6. API 명세

### `POST /api/recommend`

**요청 바디**

```json
{
  "region": "대전",
  "budget": 500,
  "style": "로맨틱",
  "weddingMonth": "2026-11",
  "priority": "스튜디오촬영"
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `region` | string | `서울` / `대전` / `충청권` / `부산` / `전주` |
| `budget` | number | 총예산 (만원 단위, 100~5000) |
| `style` | string | `로맨틱` / `모던 시크` / `클래식` / `내추럴` / `럭셔리` |
| `weddingMonth` | string | 예식 예정 시기 (`YYYY-MM`) |
| `priority` | string | `드레스` / `스튜디오촬영` / `메이크업&헤어` |

**성공 응답 (200)**

```json
{
  "headline": "대전 로맨틱 웨딩 패키지",
  "recommendation": {
    "dress": "...",
    "studio": "...",
    "makeup": "..."
  },
  "budgetPlan": [
    { "item": "드레스",       "amount": 1350000, "percent": 27.0, "comment": "..." },
    { "item": "스튜디오 촬영",  "amount": 1720000, "percent": 34.4, "comment": "..." },
    { "item": "메이크업&헤어",  "amount": 810000,  "percent": 16.2, "comment": "..." },
    { "item": "부대비용",      "amount": 720000,  "percent": 14.4, "comment": "..." },
    { "item": "예비비",        "amount": 400000,  "percent": 8.0,  "comment": "..." }
  ],
  "tip": "...",
  "budgetWarning": null,
  "meta": { "...": "입력값 및 모델 정보" }
}
```

**오류 응답**

| 상태 코드 | 상황 | 응답 |
| --- | --- | --- |
| 400 | 필수값 누락 / 허용되지 않은 값 | `{ "error": "필수 입력값이 누락되었습니다. ..." }` |
| 405 | POST가 아닌 메서드 | `{ "error": "POST 메서드로 요청해 주세요." }` |
| 500 | AI 호출 실패 · 키 미설정 · 타임아웃 | `{ "error": "추천 생성 중 문제가 발생했어요. ..." }` |

500 응답은 사용자에게 친화적인 문구만 반환하고, 상세 원인은 서버 로그에만 기록합니다.

---

## 7. 예산 플랜 계산 방식

**금액 계산은 AI가 아니라 서버(Python)가 직접 수행합니다.** AI에게 금액을 맡기면 합계가
총예산을 넘거나 계산이 틀릴 수 있기 때문에, 서버는 금액을 확정하고 AI는 "글"만 생성합니다.

1. **예비비를 먼저 확정** — 총예산의 8%를 1만원 단위로 반올림합니다.
   (잔돈을 예비비에 몰아넣으면 총예산이 작을 때 예비비 비율이 기획 범위 5~10%를 벗어납니다.)
2. **나머지 92%를 4개 항목에 가중치대로 배분** — 기본 가중치는
   드레스 30 / 스튜디오 촬영 28 / 메이크업&헤어 18 / 부대비용 16이며,
   사용자가 고른 1순위 항목에 **1.35배** 가중치를 적용한 뒤 정규화합니다.
3. **1만원 단위로 내림**하고, 내림으로 남은 잔돈(최대 3만원)은 **1순위 항목이 흡수**합니다.

이 방식으로 **5개 항목 금액의 합계는 항상 입력한 총예산과 정확히 일치**합니다.
100만원~5,000만원 × 3개 우선순위 = 1,473개 조합을 검증했으며,
합계 불일치 0건, 예비비 비율은 7.69%~8.33% 범위에 들어옵니다.

또한 지역·스타일 조합의 최소 권장 예산보다 입력 예산이 낮으면
`budgetWarning` 필드로 현실적인 안내 문구를 함께 내려줍니다.

---

## 8. 실패 처리

| 상황 | 동작 |
| --- | --- |
| **빈 입력 / 필수값 누락** | 클라이언트에서 먼저 검증해 폼 하단에 구체적 안내를 띄우고, **API를 호출하지 않습니다.** 해당 입력 필드에 오류 스타일이 적용됩니다. |
| **API 오류 (4xx)** | "입력 정보를 다시 확인해 주세요" + 서버가 내려준 사유를 표시합니다. |
| **API 오류 (5xx / 네트워크)** | "추천을 불러오는 중 문제가 발생했어요" 카드와 **재시도 버튼**을 표시합니다. |
| **응답 지연** | 로딩 상태를 즉시 표시하고, 9초 후 안내 문구를 강화, **15초 후** "응답이 지연되고 있어요"로 전환합니다. |
| **타임아웃** | **30초** 초과 시 `AbortController`로 요청을 취소하고 재시도 버튼을 표시합니다. 서버 측에서도 Claude 호출에 25초 타임아웃을 겁니다. |

---

## 9. 테스트 시나리오

로컬에서 다음을 확인할 수 있습니다.

| 시나리오 | 방법 | 기대 결과 |
| --- | --- | --- |
| 정상 입력 | 대전 / 500만원 / 로맨틱 / 2026-11 / 스튜디오촬영 | 추천 3항목 + 예산 플랜 5항목 표시, 합계 5,000,000원 |
| 빈 입력 | 아무것도 선택하지 않고 제출 | "예식 지역을 선택해 주세요." 표시, 네트워크 요청 없음 |
| 예산 부족 | 서울 / 300만원 / 럭셔리 | 최소 권장 예산 안내 문구 노출 |
| 오류 유도 | `ANTHROPIC_API_KEY`를 잘못된 값으로 변경 후 호출 | 오류 카드 + 재시도 버튼 |
| 지연 상황 | DevTools → Network → Throttling (Slow 3G) | 로딩 → 15초 후 지연 안내 → 30초 후 타임아웃 안내 |

---

## 10. 스크린샷

`docs/screenshots/` 에 저장되어 있습니다.

| 파일 | 내용 |
| --- | --- |
| `01-desktop-full.png` | 데스크톱 전체 페이지 (1440px) |
| `02-desktop-hero.png` | 데스크톱 메인 화면 |
| `03-ai-result-desktop.png` | **AI 추천 기능 동작 화면** (입력 → 결과 + 예산 플랜) |
| `04-validation-error.png` | 빈 입력 검증 (실패 처리) |
| `05-mobile-full.png` | 모바일 전체 페이지 (375px) |
| `06-mobile-hero.png` | 모바일 메인 화면 |
| `07-mobile-menu.png` | 모바일 햄버거 메뉴 열림 |
| `08-ai-result-mobile.png` | 모바일 AI 추천 결과 |

재캡처하려면:

```bash
pip install playwright
python -m playwright install chromium
python tools/dev_server.py --mock          # 터미널 1
python tools/capture_screenshots.py        # 터미널 2
```

---

## 11. 접근성 / 기타

- 시맨틱 태그(`header`, `nav`, `main`, `section`, `footer`)와 `aria-*` 속성을 적용했습니다.
- 지역 탭은 좌우 방향키로 이동할 수 있습니다.
- `prefers-reduced-motion` 설정 시 애니메이션을 최소화합니다.
- 모든 이미지/그리드는 `max-width: 100%` 기준이며, 가로 스크롤이 발생하지 않습니다.

---

## 12. 주의사항

- 이 프로젝트는 **학습용 데모**입니다. 표시되는 시세와 파트너 정보는 예시입니다.
- 상담 문의 폼은 실제 전송 없이 클라이언트에서 접수 완료 상태만 표시합니다.
- API 키는 절대 커밋하지 마세요. 실수로 커밋했다면 즉시 키를 폐기하고 재발급하세요.
