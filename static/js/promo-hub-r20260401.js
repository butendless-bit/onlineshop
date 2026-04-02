document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const DEFAULT_EVENT_TITLE = '온라인 가성비 특가상품 기획전';
  const DEFAULT_CAMPAIGN_NAME = '온라인 가성비 특가상품 캠페인';

  const selectionList = document.getElementById('promo-selection-list');
  const empty = document.getElementById('promo-selection-empty');
  const selectedChip = document.getElementById('promo-selected-chip');
  const createBtn = document.getElementById('create-campaign-btn');
  const eventTitleInput = document.getElementById('event-title');
  const campaignNameInput = document.getElementById('campaign-name');
  const workspace = document.getElementById('promo-workspace');
  const workspaceChip = document.getElementById('workspace-campaign-chip');

  const frames = {
    creative: document.getElementById('promo-frame-creative'),
    landing: document.getElementById('promo-frame-landing'),
    instagram: document.getElementById('promo-frame-instagram'),
    blog: document.getElementById('promo-frame-blog'),
  };

  const taskCards = {
    creative: document.querySelector('[data-task="creative"]'),
    landing: document.querySelector('[data-task="landing"]'),
    instagram: document.querySelector('[data-task="instagram"]'),
    blog: document.querySelector('[data-task="blog"]'),
  };

  const defaultFrameHeights = {
    creative: 560,
    landing: 620,
    instagram: 420,
    blog: 520,
  };

  const loadingOverlay = document.createElement('div');
  loadingOverlay.style.cssText = 'position:fixed;inset:0;z-index:120;background:rgba(7,10,20,.72);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;padding:20px;';
  loadingOverlay.innerHTML = `
    <div style="width:min(100%,420px);padding:28px 24px;border-radius:22px;border:1px solid rgba(255,255,255,.08);background:linear-gradient(180deg,rgba(24,33,56,.96),rgba(18,24,43,.98));box-shadow:0 18px 50px rgba(0,0,0,.28);text-align:center;">
      <div style="width:44px;height:44px;margin:0 auto 16px;border-radius:50%;border:3px solid rgba(255,255,255,.16);border-top-color:#ff5b68;animation:promo-spin .9s linear infinite;"></div>
      <div style="font-size:20px;font-weight:800;color:#fff;">온라인 홍보도우미를 준비하고 있습니다</div>
      <div style="margin-top:10px;font-size:14px;line-height:1.7;color:#98a3bf;">선택 상품을 확인하고 캠페인을 만드는 중입니다. 잠시만 기다려주세요.</div>
    </div>
  `;
  document.body.appendChild(loadingOverlay);

  function showStartLoading() {
    loadingOverlay.style.display = 'flex';
  }

  function hideStartLoading() {
    loadingOverlay.style.display = 'none';
  }

  function applyDefaults(force = false) {
    if (force || !eventTitleInput.value.trim()) eventTitleInput.value = DEFAULT_EVENT_TITLE;
    if (force || !campaignNameInput.value.trim()) campaignNameInput.value = DEFAULT_CAMPAIGN_NAME;
  }

  function setTaskStatus(task, status, message = '') {
    const card = taskCards[task];
    if (!card) return;
    const state = card.querySelector('.promo-task-state');
    const label = card.querySelector('.promo-task-label');
    if (!state || !label) return;

    state.className = 'promo-task-state';
    if (status === 'done') state.classList.add('is-done');
    else if (status === 'error') state.classList.add('is-error');
    else state.classList.add('is-processing');

    const fallback = status === 'done' ? '완성' : status === 'error' ? '확인 필요' : '작업 중';
    const safeMessage = String(message || fallback).trim();
    label.textContent = safeMessage.length > 48 ? `${safeMessage.slice(0, 48)}...` : safeMessage;
  }

  function resetTaskStatuses() {
    ['creative', 'landing', 'instagram', 'blog'].forEach((task) => setTaskStatus(task, 'processing', '작업 준비 중'));
  }

  function setFrameHeight(frame, height) {
    if (!frame) return;
    const safeHeight = Math.max(320, Math.min(Number(height) || 0, 2400));
    frame.style.height = `${safeHeight}px`;
  }

  function initializeFrameHeights() {
    Object.entries(frames).forEach(([key, frame]) => {
      setFrameHeight(frame, defaultFrameHeights[key] || 420);
    });
  }

  function getFrameUrl(task, campaignId) {
    const base = {
      creative: '/promo/creative',
      landing: '/promo/landing',
      instagram: '/promo/instagram',
      blog: '/promo/blog',
    }[task];
    return `${base}?embed=1&campaign_id=${encodeURIComponent(campaignId || '')}`;
  }

  function loadFrame(task, campaign) {
    const frame = frames[task];
    if (!frame || !campaign?.id) return;
    const nextSrc = getFrameUrl(task, campaign.id);
    if (frame.dataset.src === nextSrc) return;
    frame.dataset.src = nextSrc;
    frame.src = nextSrc;
  }

  function openWorkspace(campaign) {
    workspace.style.display = 'block';
    workspaceChip.textContent = campaign?.campaign_name || DEFAULT_CAMPAIGN_NAME;
    resetTaskStatuses();
    workspace.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function loadWorkspaceFrames(campaign, tasks = ['creative', 'landing', 'instagram', 'blog']) {
    tasks.forEach((task) => loadFrame(task, campaign));
  }

  async function refreshSelections() {
    const data = await app.resolveSelections();
    const items = data.items || [];
    selectedChip.textContent = `선택 상품 ${items.length}개`;
    selectionList.innerHTML = '';

    if (!items.length) {
      empty.style.display = 'block';
      selectionList.style.display = 'none';
      return items;
    }

    empty.style.display = 'none';
    selectionList.style.display = 'grid';
    items.forEach((item) => {
      const tile = document.createElement('div');
      tile.className = 'promo-product-tile promo-product-tile-inline';
      tile.innerHTML = `
        <div class="promo-product-thumb promo-product-thumb-inline">${item.image_url ? `<img src="${item.image_url}" alt="">` : ''}</div>
        <div class="promo-product-name promo-product-name-inline">${app.getShortProductName ? app.getShortProductName(item) : (item.product_name || '')}</div>
      `;
      selectionList.appendChild(tile);
    });
    return items;
  }

  async function createCampaign() {
    const items = await refreshSelections();
    if (!items.length) {
      app.showToast('선택한 상품이 없어 온라인 홍보를 시작할 수 없습니다.');
      return null;
    }

    applyDefaults(false);
    const payload = {
      campaign_name: campaignNameInput.value.trim() || DEFAULT_CAMPAIGN_NAME,
      event_title: eventTitleInput.value.trim() || DEFAULT_EVENT_TITLE,
      store_name: document.getElementById('store-name').value.trim(),
      phone: document.getElementById('phone').value.trim(),
      kakao_channel_url: document.getElementById('kakao').value.trim(),
      selected_product_ids: items.map((item) => ({
        model_no: item.model_no,
        _isSubscription: !!item._isSubscription,
        product_name: item.product_name || '',
        model_name: item.model_no || '',
        category: item.category || '',
        product_url: item.product_url || '',
        image_url: item.image_url || '',
        original_price: item.original_price || item.price || 0,
        sale_price: item.sale_price || item.price || 0,
        benefit_price: item.benefit_price || item.benefitPrice || 0,
        subscription_price: item.subscription_price || item.subscriptionPrice || 0,
        cardBenefitText: item.cardBenefitText || '',
        recommendationReason: item.recommendationReason || '',
        featureBullets: item.featureBullets || [],
        productDescription: item.productDescription || '',
        tags: item.tags || [],
        spec: item.specData || item.spec || {},
      })),
    };

    if (!payload.phone) {
      app.showToast('매장 전화번호를 입력해 주세요.');
      return null;
    }
    if (!payload.kakao_channel_url) {
      app.showToast('카카오 채널 URL을 입력해 주세요.');
      return null;
    }

    const result = await app.apiFetch('/api/promo/create-campaign', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    app.setCampaign(result);
    eventTitleInput.value = result.event_title || payload.event_title;
    campaignNameInput.value = result.campaign_name || payload.campaign_name;
    workspaceChip.textContent = result.campaign_name || payload.campaign_name;
    app.showToast('온라인 홍보 도우미를 시작했습니다.');
    return result;
  }

  async function prebuildPromoAssets(campaign) {
    if (!campaign?.id) return;

    try {
      setTaskStatus('creative', 'processing', '이미지 시안 생성 중');
      const creativeResult = await app.apiFetch('/api/promo/generate-creative', {
        method: 'POST',
        body: JSON.stringify({
          campaign_id:       campaign.id,
          style:             '행사형',
          tone:              '행사 강조',
          price_display:     '혜택가',
          layout:            '상품별 1장',
          // Vercel 인스턴스 분리 대응: DB miss 시 payload fallback
          products:          campaign.products || [],
          event_title:       campaign.event_title || '',
          campaign_name:     campaign.campaign_name || '',
          store_name:        campaign.store_name || '',
          phone:             campaign.phone || '',
          kakao_channel_url: campaign.kakao_channel_url || '',
        }),
      });
      app.setCreativeResult(creativeResult);
      setTaskStatus('creative', 'done', '완료');
    } catch (error) {
      setTaskStatus('creative', 'error', error.message || '확인 필요');
    } finally {
      loadWorkspaceFrames(campaign, ['creative']);
    }

    try {
      setTaskStatus('landing', 'processing', '랜딩페이지 생성 중');
      const recommendationResult = await app.apiFetch('/api/promo/recommend-landing', {
        method: 'POST',
        body: JSON.stringify({ campaign_id: campaign.id }),
      });
      const recommendation = recommendationResult.recommendation || {};
      const landingResult = await app.apiFetch('/api/promo/generate-landing', {
        method: 'POST',
        body: JSON.stringify({
          campaign_id: campaign.id,
          landing_title: recommendation.landing_title || DEFAULT_EVENT_TITLE,
          intro_text: recommendation.intro_text || '',
          cta_visibility: { phone: true, kakao: true },
        }),
      });
      app.setLandingResult(landingResult);
      setTaskStatus('landing', 'done', '완료');
    } catch (error) {
      setTaskStatus('landing', 'error', error.message || '확인 필요');
    } finally {
      loadWorkspaceFrames(campaign, ['landing']);
    }

    try {
      setTaskStatus('instagram', 'processing', '인스타 프롬프트 생성 중');
      const instagramResult = await app.apiFetch('/api/promo/generate-instagram-copy', {
        method: 'POST',
        body: JSON.stringify({ campaign_id: campaign.id }),
      });
      app.setInstagramResult(instagramResult);
      setTaskStatus('instagram', 'done', '완료');
    } catch (error) {
      setTaskStatus('instagram', 'error', error.message || '확인 필요');
    } finally {
      loadWorkspaceFrames(campaign, ['instagram']);
    }

    try {
      setTaskStatus('blog', 'processing', '블로그 프롬프트 생성 중');
      const blogResult = await app.apiFetch('/api/promo/generate-blog-copy', {
        method: 'POST',
        body: JSON.stringify({ campaign_id: campaign.id, target_length: 2000 }),
      });
      app.setBlogResult(blogResult);
      setTaskStatus('blog', 'done', '완료');
    } catch (error) {
      setTaskStatus('blog', 'error', error.message || '확인 필요');
    } finally {
      loadWorkspaceFrames(campaign, ['blog']);
    }
  }

  window.addEventListener('message', (event) => {
    const data = event.data || {};
    if (data?.type === 'promo-task-status' && data.task) {
      setTaskStatus(data.task, data.status, data.message || '');
      return;
    }
    if (data?.type === 'promo-frame-height' && data.task) {
      setFrameHeight(frames[data.task], data.height);
    }
  });

  createBtn?.addEventListener('click', async () => {
    try {
      createBtn.disabled = true;
      showStartLoading();
      const campaign = await createCampaign();
      if (campaign) {
        openWorkspace(campaign);
        await prebuildPromoAssets(campaign);
      }
    } catch (error) {
      app.showToast(error.message);
    } finally {
      hideStartLoading();
      createBtn.disabled = false;
    }
  });

  document.getElementById('restore-selection-btn')?.addEventListener('click', async () => {
    try {
      await refreshSelections();
      applyDefaults(true);
      app.showToast('현재 선택 상품을 다시 불러왔습니다.');
    } catch (error) {
      app.showToast(error.message);
    }
  });

  try {
    app.clearPromoSession();
    applyDefaults(true);
    initializeFrameHeights();
    await refreshSelections();
  } catch (error) {
    app.showToast(error.message);
  }
});
