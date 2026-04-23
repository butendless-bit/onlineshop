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
    const result = await app.apiFetch('/api/promo/recommend-landing', {
      method: 'POST',
      body: JSON.stringify({ campaign_id: campaign.id }),
    });
    const recommendation = result.recommendation || {};
    if (force || !titleInput.value.trim()) titleInput.value = recommendation.landing_title || DEFAULT_LANDING_TITLE;
    if (force || !introInput.value.trim()) introInput.value = recommendation.intro_text || '';
  }

  function renderQr(url) {
    qr.innerHTML = '';
    const holder = document.createElement('div');
    holder.style.display = 'grid';
    holder.style.placeItems = 'center';
    holder.style.minHeight = '220px';
    qr.appendChild(holder);
    new QRCode(holder, { text: url, width: 180, height: 180 });
    requestAnimationFrame(postFrameHeight);
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

    const landingUrl = `${window.location.origin}/promo/${campaign.id}?source=direct`;
    titleInput.value = result.landing?.landing_title || payload.landing_title;
    introInput.value = result.landing?.intro_text || payload.intro_text;
    disclaimerInput.value = result.landing?.disclaimer || payload.disclaimer;
    urlInput.value = landingUrl;
    renderQr(landingUrl);
    app.setLandingResult(result);

    // localStorage에 전체 캠페인 + 랜딩 데이터 저장
    // → 새 탭으로 열어도 API 없이 바로 렌더링 가능 (Vercel 서버리스 인스턴스 불일치 방지)
    try {
      const cacheKey = `himartLandingCache_${campaign.id}`;
      const cacheData = {
        ...campaign,
        metadata: { ...(campaign.metadata || {}), landing: result.landing },
      };
      localStorage.setItem(cacheKey, JSON.stringify(cacheData));
    } catch (_) {}

    postTaskStatus('done', '완료');
  }

  document.getElementById('generate-landing-btn')?.addEventListener('click', () => {
    generateLanding().catch((error) => {
      app.showToast(error.message);
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
      urlInput.value = `${window.location.origin}/promo/${campaign.id}?source=direct`;
      renderQr(urlInput.value);
      postTaskStatus('done', '완료');
      return;
    }

    await applyRecommendedCopy(true);
    await generateLanding();
  } catch (error) {
    app.showToast(error.message);
    postTaskStatus('error', '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
