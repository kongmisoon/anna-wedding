/*
  js/ai-recommend.js
  AI 맞춤 웨딩 추천 기능 담당 파일.
  흐름: 입력값 검증 → POST /api/recommend → 상태별 UI(빈 상태 / 로딩 / 오류 / 결과) 렌더링.

  실패 처리 3종:
   (1) 빈 입력   : 필수값 누락 시 폼 근처에 구체적 안내를 띄우고 API 호출 자체를 막는다.
   (2) API 오류  : 4xx/5xx 응답이면 오류 카드 + 재시도 버튼을 노출한다.
   (3) 지연/타임아웃 : 9초/15초 시점에 로딩 문구를 단계적으로 바꾸고,
                      30초를 넘기면 AbortController로 요청을 취소한 뒤 안내 문구를 띄운다.
*/
(function () {
  'use strict';

  var API_ENDPOINT = '/api/recommend';
  var SLOW_NOTICE_MS = 9000;    // 이 시점부터 "준비 중" 안내를 강화
  var DELAY_NOTICE_MS = 15000;  // 이 시점부터 "응답 지연" 안내로 전환
  var TIMEOUT_MS = 30000;       // 이 시점에 요청을 강제 취소

  /* ---------- DOM 참조 ---------- */
  var form = document.getElementById('recommendForm');
  if (!form) return;

  var submitBtn = document.getElementById('submitBtn');
  var formError = document.getElementById('formError');

  var elEmpty = document.getElementById('resultEmpty');
  var elLoading = document.getElementById('resultLoading');
  var elError = document.getElementById('resultError');
  var elOutput = document.getElementById('resultOutput');

  var loadingTitle = document.getElementById('loadingTitle');
  var loadingDesc = document.getElementById('loadingDesc');
  var errorTitle = document.getElementById('errorTitle');
  var errorDesc = document.getElementById('errorDesc');

  var retryBtn = document.getElementById('retryBtn');
  var againBtn = document.getElementById('againBtn');
  var toContactBtn = document.getElementById('toContactBtn');

  var lastPayload = null;   // 재시도용으로 마지막 요청 본문을 보관
  var timers = [];          // 로딩 단계 전환 타이머

  /* ---------- 상태 전환 ---------- */
  function showState(state) {
    elEmpty.hidden = state !== 'empty';
    elLoading.hidden = state !== 'loading';
    elError.hidden = state !== 'error';
    elOutput.hidden = state !== 'result';
  }

  function clearTimers() {
    timers.forEach(clearTimeout);
    timers = [];
  }

  function showFormError(message, fieldId) {
    formError.textContent = message;
    formError.hidden = false;
    var el = document.getElementById(fieldId);
    var field = el ? el.closest('.field') : null;
    if (field) field.classList.add('has-error');
    if (el && typeof el.focus === 'function') el.focus();
  }

  function clearFormError() {
    formError.hidden = true;
    formError.textContent = '';
    Array.prototype.forEach.call(form.querySelectorAll('.field'), function (f) {
      f.classList.remove('has-error');
    });
  }

  form.addEventListener('input', function (e) {
    var field = e.target.closest('.field');
    if (field) field.classList.remove('has-error');
  });

  /* ---------- 입력값 수집 & 검증 (실패 처리 1) ---------- */
  function collectInput() {
    var priorityEl = form.querySelector('input[name="priority"]:checked');
    return {
      region: document.getElementById('region').value,
      budget: Number(document.getElementById('budget').value),
      style: document.getElementById('style').value,
      weddingMonth: document.getElementById('weddingMonth').value,
      priority: priorityEl ? priorityEl.value : ''
    };
  }

  function validate(data) {
    if (!data.region) return { message: '예식 지역을 선택해 주세요.', field: 'region' };
    if (!data.budget || data.budget < 100) return { message: '총예산을 100만원 이상으로 설정해 주세요.', field: 'budget' };
    if (!data.style) return { message: '웨딩 스타일 취향을 선택해 주세요.', field: 'style' };
    if (!data.weddingMonth) return { message: '예식 예정 시기를 선택해 주세요.', field: 'weddingMonth' };
    if (!data.priority) return { message: '가장 중요하게 생각하는 항목을 하나 선택해 주세요.', field: 'region' };
    return null;
  }

  /* ---------- 숫자 포맷 ---------- */
  function formatWon(value) {
    return Number(value).toLocaleString('ko-KR') + '원';
  }

  /* ---------- 결과 렌더링 ---------- */
  function renderResult(data, input) {
    var rec = data.recommendation || {};
    document.getElementById('recDress').textContent = rec.dress || '-';
    document.getElementById('recStudio').textContent = rec.studio || '-';
    document.getElementById('recMakeup').textContent = rec.makeup || '-';

    document.getElementById('resultBadge').textContent =
      input.region + ' · ' + input.style + ' · ' + input.priority + ' 우선';
    document.getElementById('resultHeadline').textContent =
      data.headline || (input.region + ' ' + input.style + ' 맞춤 웨딩 패키지');

    var plan = Array.isArray(data.budgetPlan) ? data.budgetPlan : [];
    var total = plan.reduce(function (sum, item) { return sum + Number(item.amount || 0); }, 0);

    document.getElementById('budgetTotal').textContent =
      '입력하신 총예산 ' + Number(input.budget).toLocaleString('ko-KR') + '만원 기준으로 배분했습니다.';

    // 바 차트 (순수 CSS: width 퍼센트만 사용)
    var listEl = document.getElementById('budgetList');
    listEl.innerHTML = '';
    plan.forEach(function (item) {
      var wrap = document.createElement('div');
      wrap.className = 'budget-item';

      var head = document.createElement('div');
      head.className = 'budget-item-head';

      var name = document.createElement('span');
      name.className = 'budget-item-name';
      name.textContent = item.item;

      var amount = document.createElement('span');
      amount.className = 'budget-item-amount';
      amount.textContent = formatWon(item.amount);

      head.appendChild(name);
      head.appendChild(amount);

      var track = document.createElement('div');
      track.className = 'budget-bar-track';
      var bar = document.createElement('div');
      bar.className = 'budget-bar';
      bar.style.width = '0%';
      track.appendChild(bar);

      var percent = document.createElement('p');
      percent.className = 'budget-item-percent';
      percent.textContent = '총예산의 ' + item.percent + '%';

      var comment = document.createElement('p');
      comment.className = 'budget-item-comment';
      comment.textContent = item.comment || '';

      wrap.appendChild(head);
      wrap.appendChild(track);
      wrap.appendChild(percent);
      wrap.appendChild(comment);
      listEl.appendChild(wrap);

      // 렌더 직후 폭을 넣어 CSS transition 애니메이션이 동작하게 한다.
      // rAF는 비활성 탭에서 멈추므로, 실행되지 않은 경우를 대비해 타이머 폴백을 둔다.
      var fill = function () { bar.style.width = item.percent + '%'; };
      requestAnimationFrame(fill);
      setTimeout(fill, 120);
    });

    // 표
    var tbody = document.getElementById('budgetTableBody');
    tbody.innerHTML = '';
    plan.forEach(function (item) {
      var tr = document.createElement('tr');
      var th = document.createElement('th');
      th.scope = 'row';
      th.textContent = item.item;
      var tdAmount = document.createElement('td');
      tdAmount.textContent = formatWon(item.amount);
      var tdPercent = document.createElement('td');
      tdPercent.textContent = item.percent + '%';
      tr.appendChild(th);
      tr.appendChild(tdAmount);
      tr.appendChild(tdPercent);
      tbody.appendChild(tr);
    });

    document.getElementById('budgetSum').textContent = formatWon(total);
    document.getElementById('budgetSumPercent').textContent =
      plan.reduce(function (sum, item) { return sum + Number(item.percent || 0); }, 0) + '%';

    // 예산 부족 안내 (엣지 케이스)
    var warnEl = document.getElementById('budgetWarning');
    if (data.budgetWarning) {
      warnEl.textContent = data.budgetWarning;
      warnEl.hidden = false;
    } else {
      warnEl.hidden = true;
    }

    document.getElementById('recTip').textContent = data.tip || '';

    showState('result');
  }

  /* ---------- API 호출 ---------- */
  function requestRecommendation(payload) {
    lastPayload = payload;
    clearTimers();
    clearFormError();
    showState('loading');
    submitBtn.disabled = true;
    submitBtn.textContent = '추천 생성 중…';

    loadingTitle.textContent = 'AI가 추천을 준비 중입니다…';
    loadingDesc.textContent = '예산과 지역 시세를 함께 계산하고 있어요. 잠시만 기다려 주세요.';

    // 실패 처리 3: 지연 단계별 안내
    timers.push(setTimeout(function () {
      loadingDesc.textContent = '조금만 더 기다려 주세요. 항목별 예산 플랜을 구성하고 있어요.';
    }, SLOW_NOTICE_MS));

    timers.push(setTimeout(function () {
      loadingTitle.textContent = '응답이 지연되고 있어요';
      loadingDesc.textContent = '네트워크 상태에 따라 시간이 더 걸릴 수 있습니다. 잠시 후 다시 시도해 주세요.';
    }, DELAY_NOTICE_MS));

    var controller = new AbortController();
    var timeoutId = setTimeout(function () { controller.abort(); }, TIMEOUT_MS);
    timers.push(timeoutId);

    fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    })
      .then(function (res) {
        return res.json()
          .catch(function () { return {}; })
          .then(function (body) {
            if (!res.ok) {
              var err = new Error(body.error || 'API 오류가 발생했습니다.');
              err.status = res.status;
              throw err;
            }
            return body;
          });
      })
      .then(function (body) {
        clearTimers();
        renderResult(body, payload);
        elOutput.scrollIntoView({ behavior: 'smooth', block: 'start' });
      })
      .catch(function (err) {
        clearTimers();
        if (err.name === 'AbortError') {
          // 실패 처리 3: 타임아웃
          errorTitle.textContent = '응답이 지연되고 있어요';
          errorDesc.textContent = '요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.';
        } else if (err.status && err.status >= 400 && err.status < 500) {
          // 실패 처리 2: 4xx
          errorTitle.textContent = '입력 정보를 다시 확인해 주세요';
          errorDesc.textContent = err.message;
        } else {
          // 실패 처리 2: 5xx / 네트워크 오류
          errorTitle.textContent = '추천을 불러오는 중 문제가 발생했어요';
          errorDesc.textContent = err.message || '잠시 후 다시 시도해 주세요.';
        }
        showState('error');
      })
      .then(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = 'AI 추천 받기';
      });
  }

  /* ---------- 이벤트 바인딩 ---------- */
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearFormError();

    var data = collectInput();
    var invalid = validate(data);
    if (invalid) {
      // 실패 처리 1: 필수값 누락 → API를 호출하지 않고 폼 근처에 안내
      showFormError(invalid.message, invalid.field);
      return;
    }
    requestRecommendation(data);
  });

  retryBtn.addEventListener('click', function () {
    if (lastPayload) requestRecommendation(lastPayload);
    else showState('empty');
  });

  againBtn.addEventListener('click', function () {
    showState('empty');
    form.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  toContactBtn.addEventListener('click', function () {
    // 추천 결과를 상담 폼 문의 내용에 자동으로 채워 넣는다
    if (lastPayload) {
      var messageEl = document.getElementById('message');
      var regionEl = document.getElementById('contactRegion');
      var headline = document.getElementById('resultHeadline').textContent;

      if (regionEl) regionEl.value = lastPayload.region;
      if (messageEl && !messageEl.value.trim()) {
        messageEl.value =
          '[AI 추천 결과로 상담 신청]\n' +
          '- 지역: ' + lastPayload.region + '\n' +
          '- 총예산: ' + Number(lastPayload.budget).toLocaleString('ko-KR') + '만원\n' +
          '- 스타일: ' + lastPayload.style + '\n' +
          '- 예식 시기: ' + lastPayload.weddingMonth + '\n' +
          '- 1순위 항목: ' + lastPayload.priority + '\n' +
          '- 추천 패키지: ' + headline + '\n\n' +
          '위 결과를 기준으로 상담받고 싶습니다.';
      }
    }
    document.getElementById('contact').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
})();
