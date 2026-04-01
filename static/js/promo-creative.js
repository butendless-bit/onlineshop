document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const preview = document.getElementById('creative-preview');
  const empty = document.getElementById('creative-empty');
  const downloadBtn = document.getElementById('download-creative-btn');
  const TASK_NAME = 'creative';

  let campaignData = null;
  let renderedCards = [];

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

  function escapeHtml(value) {
    return String(value || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  async function ensureCampaign() {
    const campaign = app.getCampaign();
    if (!campaign?.id) {
      app.showToast('먼저 온라인 홍보하기에서 캠페인을 시작해 주세요.');
      if (window.self === window.top) window.location.href = '/promo';
      return null;
    }

    const result = await app.apiFetch(`/api/promo/campaign/${campaign.id}`);
    app.setCampaign(result);
    campaignData = result;
    return result;
  }

  function buildCardHtml(product) {
    const imageSrc = app.getPreferredImage(product);
    const title = escapeHtml(app.getShortProductName(product));
    const price = escapeHtml(app.formatPrice(product, '혜택가'));
    const reason = escapeHtml(product.reason || product.recommendationReason || '매장 추천 상품입니다.');

    return `
      <article class="creative-square creative-square-remade">
        <div class="creative-remade-image-stage">
          ${imageSrc ? `<img src="${imageSrc}" alt="${title}" loading="eager" crossorigin="anonymous">` : `<div class="creative-image-fallback">H</div>`}
        </div>
        <div class="creative-remade-title">${title}</div>
        <div class="creative-remade-price-stage">
          <span class="creative-remade-price-text">${price}</span>
        </div>
        <div style="padding:0 10px 8px; text-align:center; font-size:12px; line-height:1.5; color:#374151;">${reason}</div>
      </article>
    `;
  }

  async function renderPreviews(products) {
    preview.innerHTML = '';
    renderedCards = [];

    for (const product of products || []) {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = buildCardHtml(product);
      const card = wrapper.firstElementChild;
      preview.appendChild(card);
      renderedCards.push(card);
    }

    await Promise.all(renderedCards.map((card) => app.waitForImages(card)));
    empty.style.display = renderedCards.length ? 'none' : 'block';
    preview.style.display = renderedCards.length ? 'grid' : 'none';
    requestAnimationFrame(postFrameHeight);
  }

  async function ensureCutouts(products) {
    for (const product of products || []) {
      if (!product.image_url) continue;
      try {
        const result = await app.apiFetch('/api/image/remove-background', {
          method: 'POST',
          body: JSON.stringify({
            product_id: product.product_id || product.model_no,
            image_url: product.image_url,
            force: false,
          }),
        });
        app.saveCutout(product.product_id || product.model_no, result);
      } catch {
        // Keep original image when cutout fails.
      }
    }
  }

  async function generateCreative() {
    const campaign = await ensureCampaign();
    if (!campaign) return;

    postTaskStatus('processing', '이미지 생성 중');
    empty.textContent = '이미지 시안을 만들고 있습니다...';

    const response = await app.apiFetch('/api/promo/generate-creative', {
      method: 'POST',
      body: JSON.stringify({
        campaign_id: campaign.id,
        style: '행사형',
        tone: '행사 강조',
        price_display: '혜택가',
        layout: '상품별 1장',
      }),
    });

    const products = response?.payload?.products || campaign.products || [];
    await ensureCutouts(products);
    await renderPreviews(products);
    app.setCreativeResult(response);
    postTaskStatus('done', '완료');
  }

  async function downloadPreviews() {
    if (!renderedCards.length) {
      app.showToast('먼저 이미지 시안을 생성해 주세요.');
      return;
    }

    for (let i = 0; i < renderedCards.length; i += 1) {
      const card = renderedCards[i];
      await app.waitForImages(card);
      const canvas = await html2canvas(card, {
        scale: 2,
        backgroundColor: null,
        useCORS: true,
        allowTaint: false,
      });
      const link = document.createElement('a');
      link.href = canvas.toDataURL('image/png');
      link.download = `promo_creative_${i + 1}.png`;
      link.click();
      if (i < renderedCards.length - 1) {
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
    }
  }

  downloadBtn?.addEventListener('click', () => {
    downloadPreviews().catch((error) => app.showToast(error.message));
  });

  try {
    await generateCreative();
  } catch (error) {
    empty.textContent = '이미지 시안을 불러오지 못했습니다.';
    app.showToast(error.message);
    postTaskStatus('error', '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
