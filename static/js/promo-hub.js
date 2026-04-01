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

    label.textContent = message || (status === 'done' ? '완성' : status === 'error' ? '확인 필요' : '작업 중');
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

  function openWorkspace(campaign) {
    workspace.style.display = 'block';
    workspaceChip.textContent = campaign?.campaign_name || DEFAULT_CAMPAIGN_NAME;
    resetTaskStatuses();
    const campaignId = encodeURIComponent(campaign?.id || '');
    frames.creative.src = `/promo/creative?embed=1&campaign_id=${campaignId}`;
    frames.landing.src = `/promo/landing?embed=1&campaign_id=${campaignId}`;
    frames.instagram.src = `/promo/instagram?embed=1&campaign_id=${campaignId}`;
    frames.blog.src = `/promo/blog?embed=1&campaign_id=${campaignId}`;
    workspace.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
      if (campaign) openWorkspace(campaign);
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
