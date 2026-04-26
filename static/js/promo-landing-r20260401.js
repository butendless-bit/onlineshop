/** 캠페인 데이터를 URL 안전 base64로 인코딩 (서버 없이 랜딩 렌더링용) */
function _encodeCampaignData(campaign) {
  const slim = {
    id: campaign.id,
    event_title: campaign.event_title || '',
    store_name: campaign.store_name || '',
    phone: campaign.phone || '',
    kakao_channel_url: campaign.kakao_channel_url || '',
    metadata: campaign.metadata || {},
    products: (campaign.products || []).map((p) => ({
      model_no: p.model_no || '',
      product_name: p.product_name || '',
      product_url: p.product_url || '',
      image_url: p.image_url || '',
      category: p.category || '',
      original_price: p.original_price || 0,
      benefit_price: p.benefit_price || p.sale_price || 0,
      sale_price: p.sale_price || 0,
      spec: p.spec || {},
    })),
  };
  try {
    return btoa(unescape(encodeURIComponent(JSON.stringify(slim))))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  } catch (_) { return ''; }
}

document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const DEFAULT_LANDING_TITLE = '온라인 가성비 특가상품 기획전';
  const qr = document.getElementById('landing-qr');
  const titleInput = document.getElementById('landing-title');
  const introInput = document.getElementById('landing-intro');
  const disclaimerInput = document.getElementById('landing-disclaimer');
  const urlInput = document.getElementById('landing-url');
  const TASK_NAME = 'landing';

  let campaign = null;

  function postTaskStatus(status, message = '') {
    if (window.self !== window.top) {
      window.parent.postMessage({ type: 'promo-task-status', task: TASK_NAME, status, message }, '*');
    }
  }

  function postFrameHeight() {
    if (window.self !== window.top) {
      window.parent.postMessage({ type: 'promo-frame-height', task: TASK_NAME, height: Math.ceil(document.body.scrollHeight) }, '*');
    }
  }

  async function ensureCampaign() {
    const saved = app.getCampaign();
    if (!saved?.id) {
      app.showToast('먼저 프로모션 허브에서 캠페인을 시작해 주세요.');
      if (window.self === window.top) window.location.href = '/promo';
      return null;
    }
    // localStorage에 products가 있으면 API 호출 생략 (Vercel 인스턴스 불일치 대응)
    if (saved.products?.length) {
      campaign = saved;
      return campaign;
    }
    // API 시도, 실패 시 localStorage fallback
    try {
      campaign = await app.apiFetch(`/api/promo/campaign/${saved.id}`);
      app.setCampaign(campaign);
    } catch (_) {
      campaign = saved;
    }
    return campaign;
  }

  async function applyRecommendedCopy(force = false) {
    if (!campaign?.id) return;
    try {
      const result = await app.apiFetch('/api/promo/recommend-landing', {
        method: 'POST',
        body: JSON.stringify({ campaign_id: campaign.id }),
      });
      const recommendation = result.recommendation || {};
      if (force || !titleInput.value.trim()) titleInput.value = recommendation.landing_title || DEFAULT_LANDING_TITLE;
      if (force || !introInput.value.trim()) introInput.value = recommendation.intro_text || '';
    } catch (_) {
      // AI 추천 실패 시 기본값으로 진행 (랜딩 생성은 계속)
      if (force || !titleInput.value.trim()) titleInput.value = DEFAULT_LANDING_TITLE;
    }
  }

  function renderQr(url) {
    try {
      qr.innerHTML = '';
      const holder = document.createElement('div');
      holder.style.display = 'grid';
      holder.style.placeItems = 'center';
      holder.style.minHeight = '220px';
      qr.appendChild(holder);
      if (typeof QRCode !== 'undefined') {
        new QRCode(holder, { text: url, width: 180, height: 180 });
      } else {
        holder.textContent = 'QR 생성 불가 (CDN 로드 실패)';
      }
      requestAnimationFrame(postFrameHeight);
    } catch (_) {
      // QR 생성 실패는 무시 — 랜딩 생성 자체는 계속 진행
    }
  }

  /** ?d= 원본 URL → TinyURL 단축 (5초 타임아웃, 실패 시 원본 반환) */
  async function shortenUrl(longUrl) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      const res = await app.apiFetch('/api/promo/shorten', {
        method: 'POST',
        body: JSON.stringify({ url: longUrl }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      return res?.short_url || longUrl;
    } catch (_) {
      return longUrl;
    }
  }

  /** URL 입력창 + QR 동시 업데이트.
   *  원본 URL 즉시 표시 → 백그라운드에서 단축 후 업데이트 (UI 블로킹 없음) */
  function applyLandingUrl(longUrl) {
    urlInput.dataset.fullUrl = longUrl;
    renderQr(longUrl);          // QR은 항상 원본 ?d= URL
    urlInput.value = longUrl;   // 즉시 원본 URL 표시
    // 백그라운드 단축: 완료되면 조용히 업데이트
    shortenUrl(longUrl).then((short) => {
      if (short && short !== longUrl) urlInput.value = short;
    });
  }

  async function generateLanding() {
    if (!campaign?.id) return;

    postTaskStatus('processing', '랜딩페이지 생성 중');

    const payload = {
      campaign_id: campaign.id,
      landing_title: titleInput.value.trim() || DEFAULT_LANDING_TITLE,
      intro_text: introInput.value.trim(),
      cta_visibility: {
        phone: document.getElementById('show-phone-cta').checked,
        kakao: document.getElementById('show-kakao-cta').checked,
      },
      disclaimer: disclaimerInput.value.trim(),
      // Vercel 인스턴스 불일치 대응: 클라이언트가 갖고 있는 전체 데이터 전송
      products: campaign.products || [],
      store_name: campaign.store_name || '',
      phone: campaign.phone || '',
      kakao_channel_url: campaign.kakao_channel_url || '',
      event_title: campaign.event_title || '',
    };

    const result = await app.apiFetch('/api/promo/generate-landing', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    titleInput.value = result.landing?.landing_title || payload.landing_title;
    introInput.value = result.landing?.intro_text || payload.intro_text;
    disclaimerInput.value = result.landing?.disclaimer || payload.disclaimer;
    app.setLandingResult(result);

    // 캠페인 데이터를 URL에 인코딩 → 서버 DB 불필요, 어디서 열어도 렌더링 가능
    const fullCampaign = {
      ...campaign,
      metadata: { ...(campaign.metadata || {}), landing: result.landing },
    };
    const encoded = _encodeCampaignData(fullCampaign);
    const landingUrl = `${window.location.origin}/promo/${campaign.id}?d=${encoded}`;

    // localStorage 캐시도 병행 저장 (같은 기기 빠른 재사용)
    try {
      localStorage.setItem(`himartLandingCache_${campaign.id}`, JSON.stringify(fullCampaign));
    } catch (_) {}

    applyLandingUrl(landingUrl);   // 즉시 URL 표시, 단축은 백그라운드
    postTaskStatus('done', '완료');
  }

  document.getElementById('generate-landing-btn')?.addEventListener('click', () => {
    generateLanding().catch((error) => {
      const msg = error?.message || String(error);
      app.showToast(msg);
      if (urlInput) urlInput.value = '[오류] ' + msg;
      postTaskStatus('error', '확인 필요');
    });
  });

  document.getElementById('open-landing-btn')?.addEventListener('click', () => {
    const url = urlInput.value.trim();
    if (!url) return app.showToast('먼저 랜딩페이지를 생성해 주세요.');
    window.open(url, '_blank', 'noopener,noreferrer');
  });

  document.getElementById('copy-landing-url-btn')?.addEventListener('click', async () => {
    const url = urlInput.value.trim();
    if (!url) return app.showToast('먼저 랜딩페이지를 생성해 주세요.');
    await navigator.clipboard.writeText(url);
    app.showToast('공유 URL을 복사했습니다.');
  });

  document.getElementById('download-landing-qr-btn')?.addEventListener('click', () => {
    const canvas = qr.querySelector('canvas');
    if (!canvas) return app.showToast('먼저 랜딩페이지를 생성해 주세요.');
    const link = document.createElement('a');
    link.href = canvas.toDataURL('image/png');
    link.download = 'landing_qr.png';
    link.click();
  });

  try {
    const result = await ensureCampaign();
    if (!result) return;

    const saved = app.getLandingResult();
    if (saved?.landing) {
      titleInput.value = saved.landing.landing_title || '';
      introInput.value = saved.landing.intro_text || '';
      disclaimerInput.value = saved.landing.disclaimer || '';
      // ?d= 인코딩 URL 복원 (서버 DB 불필요, 어디서 열어도 렌더링 가능)
      const restoredCampaign = {
        ...campaign,
        metadata: { ...(campaign.metadata || {}), landing: saved.landing },
      };
      const restoredEncoded = _encodeCampaignData(restoredCampaign);
      const restoredUrl = `${window.location.origin}/promo/${campaign.id}?d=${restoredEncoded}`;
      applyLandingUrl(restoredUrl);   // 즉시 표시, 단축은 백그라운드
      postTaskStatus('done', '완료');
      return;
    }

    await applyRecommendedCopy(true);
    await generateLanding();
  } catch (error) {
    const msg = error?.message || String(error);
    app.showToast(msg);
    if (urlInput) urlInput.value = '[오류] ' + msg;
    postTaskStatus('error', '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
