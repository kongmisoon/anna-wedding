/*
  js/main.js
  공통 UI 로직 담당 파일.
  - 모바일 햄버거 메뉴 토글
  - 스크롤에 따른 헤더 그림자 / 현재 섹션 네비 하이라이트
  - 지역별 안내 탭 전환
  - 예산 슬라이더 값 표시
  - 상담 문의 폼 클라이언트 유효성 검사
*/
(function () {
  'use strict';

  /* ---------- 1. 모바일 햄버거 메뉴 ---------- */
  var navToggle = document.getElementById('navToggle');
  var primaryNav = document.getElementById('primaryNav');

  function closeNav() {
    primaryNav.classList.remove('is-open');
    navToggle.classList.remove('is-open');
    navToggle.setAttribute('aria-expanded', 'false');
    navToggle.setAttribute('aria-label', '메뉴 열기');
  }

  if (navToggle && primaryNav) {
    navToggle.addEventListener('click', function () {
      var willOpen = !primaryNav.classList.contains('is-open');
      primaryNav.classList.toggle('is-open', willOpen);
      navToggle.classList.toggle('is-open', willOpen);
      navToggle.setAttribute('aria-expanded', String(willOpen));
      navToggle.setAttribute('aria-label', willOpen ? '메뉴 닫기' : '메뉴 열기');
    });

    // 메뉴 안의 링크를 누르면 자동으로 닫는다 (모바일 UX)
    primaryNav.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeNav();
    });

    // 데스크톱 폭으로 돌아가면 열린 상태를 초기화
    window.addEventListener('resize', function () {
      if (window.innerWidth > 1024) closeNav();
    });
  }

  /* ---------- 2. 헤더 그림자 + 현재 섹션 하이라이트 ---------- */
  var header = document.getElementById('siteHeader');
  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-link'));
  var sections = navLinks
    .map(function (link) { return document.querySelector(link.getAttribute('href')); })
    .filter(Boolean);

  function onScroll() {
    if (header) header.classList.toggle('is-scrolled', window.scrollY > 8);

    // 화면 상단에서 가장 가까운 섹션을 현재 섹션으로 판단
    var offset = window.scrollY + (header ? header.offsetHeight : 0) + 24;
    var currentIndex = 0;
    sections.forEach(function (section, i) {
      if (section.offsetTop <= offset) currentIndex = i;
    });
    navLinks.forEach(function (link, i) {
      link.classList.toggle('is-active', i === currentIndex);
    });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---------- 3. 지역별 안내 탭 ---------- */
  var tabWrap = document.getElementById('regionTabs');
  if (tabWrap) {
    var tabs = Array.prototype.slice.call(tabWrap.querySelectorAll('.tab'));
    var panels = Array.prototype.slice.call(tabWrap.querySelectorAll('.tab-panel'));

    function activateTab(index) {
      tabs.forEach(function (tab, i) {
        var selected = i === index;
        tab.classList.toggle('is-active', selected);
        tab.setAttribute('aria-selected', String(selected));
      });
      panels.forEach(function (panel, i) {
        var selected = i === index;
        panel.classList.toggle('is-active', selected);
        panel.hidden = !selected;
      });
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { activateTab(i); });
      // 좌우 방향키로 탭 이동 (키보드 접근성)
      tab.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        e.preventDefault();
        var next = e.key === 'ArrowRight'
          ? (i + 1) % tabs.length
          : (i - 1 + tabs.length) % tabs.length;
        activateTab(next);
        tabs[next].focus();
      });
    });
  }

  /* ---------- 4. 예산 슬라이더 값 표시 ---------- */
  var budgetInput = document.getElementById('budget');
  var budgetOutput = document.getElementById('budgetOutput');

  function renderBudget() {
    if (!budgetInput || !budgetOutput) return;
    budgetOutput.textContent = Number(budgetInput.value).toLocaleString('ko-KR') + '만원';
  }

  if (budgetInput) {
    budgetInput.addEventListener('input', renderBudget);
    renderBudget();
  }

  /* ---------- 5. 예식 예정 시기 기본값(다음 달 이후만 선택 가능) ---------- */
  var monthInput = document.getElementById('weddingMonth');
  if (monthInput) {
    var now = new Date();
    var min = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    var pad = function (n) { return String(n).padStart(2, '0'); };
    monthInput.min = min.getFullYear() + '-' + pad(min.getMonth() + 1);
  }

  /* ---------- 6. 상담 문의 폼 유효성 검사 ---------- */
  var contactForm = document.getElementById('contactForm');
  var contactError = document.getElementById('contactError');
  var contactSuccess = document.getElementById('contactSuccess');

  function showContactError(message, fieldId) {
    contactError.textContent = message;
    contactError.hidden = false;
    contactSuccess.hidden = true;
    var el = document.getElementById(fieldId);
    if (el) {
      el.closest('.field').classList.add('has-error');
      el.focus();
    }
  }

  if (contactForm) {
    // 입력을 수정하면 해당 필드의 오류 표시를 해제
    contactForm.addEventListener('input', function (e) {
      var field = e.target.closest('.field');
      if (field) field.classList.remove('has-error');
    });

    contactForm.addEventListener('submit', function (e) {
      e.preventDefault();
      contactError.hidden = true;
      contactSuccess.hidden = true;
      Array.prototype.forEach.call(contactForm.querySelectorAll('.field'), function (f) {
        f.classList.remove('has-error');
      });

      var name = document.getElementById('name').value.trim();
      var phone = document.getElementById('phone').value.trim();
      var region = document.getElementById('contactRegion').value;
      var message = document.getElementById('message').value.trim();

      if (!name) return showContactError('이름을 입력해 주세요.', 'name');
      if (!phone) return showContactError('연락처를 입력해 주세요.', 'phone');
      // 숫자 9~11자리(하이픈 제외)를 연락처로 인정
      if (!/^[0-9]{9,11}$/.test(phone.replace(/[^0-9]/g, ''))) {
        return showContactError('연락처 형식을 확인해 주세요. 예: 010-1234-5678', 'phone');
      }
      if (!region) return showContactError('희망 지역을 선택해 주세요.', 'contactRegion');
      if (!message) return showContactError('문의 내용을 입력해 주세요.', 'message');

      // 데모 프로젝트이므로 실제 전송 없이 접수 완료 상태만 표시한다.
      contactSuccess.hidden = false;
      contactForm.reset();
      contactSuccess.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }
})();
