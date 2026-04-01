document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const root = document.getElementById('campaign-landing-root');
  const campaignId = root.dataset.campaignId;
  const params = new URLSearchParams(window.location.search);
  const linkId = params.get('link') || '';
  const source = params.get('source') || params.get('src') || 'direct';

  async function track(eventType) {
    await app.apiFetch(`/api/promo/campaign/${campaignId}/track`, {
      method: 'POST',
      body: JSON.stringify({ event_type: eventType, link_id: linkId, metadata: { source } }),
    });
  }

  try {
    const campaign = await app.apiFetch(`/api/promo/campaign/${campaignId}`);
    const landing = campaign.metadata?.landing || {
      landing_title: campaign.event_title,
      intro_text: '추천 상품을 확인하고 매장으로 문의해 보세요.',
      disclaimer: '행사 및 가격 정보는 생성 시점 기준이며 변동될 수 있습니다.',
      cta_visibility: { phone: true, kakao: true },
    };

    const cardsHtml = (campaign.products || []).map((product) => {
      const shortName = app.getShortProductName(product);
      const specText = app.getProductSpecs(product).join(' · ');
      return `
        <article class="landing-product-card">
          ${app.getPreferredImage(product) ? `<img src="${app.getPreferredImage(product)}" alt="">` : ''}
          <div style="margin-top:12px; font-size:17px; font-weight:900;">${shortName}</div>
          <div style="margin-top:6px; font-size:12px; color:#64748b;">${product.model_no || ''}</div>
          ${specText ? `<div style="margin-top:6px; font-size:12px; color:#475569;">${specText}</div>` : ''}
          <div style="margin-top:8px; font-size:20px; font-weight:900; color:#e60012;">${app.formatPrice(product, '혜택가')}</div>
          <div class="landing-cta-row">
            <a class="promo-btn primary public-call" href="tel:${campaign.phone || ''}">전화하기</a>
            ${campaign.kakao_channel_url ? `<a class="promo-btn kakao public-kakao" href="${campaign.kakao_channel_url}" target="_blank" rel="noopener noreferrer">카카오톡 상담하기</a>` : ''}
          </div>
        </article>
      `;
    }).join('');

    await track('landing_visit');

    root.innerHTML = `
      <div class="landing-mobile-preview" style="margin:0 auto;">
        <div class="landing-header">
          <div style="font-size:12px; opacity:.82;">${campaign.store_name}</div>
          <h2 style="margin:8px 0 0; font-size:26px; line-height:1.2;">${landing.landing_title}</h2>
          <p style="margin:10px 0 0; line-height:1.6; opacity:.92;">${landing.intro_text}</p>
        </div>
        <div class="landing-card-list">${cardsHtml}</div>
        <div class="landing-footer">
          <div style="font-weight:900;">${campaign.store_name}</div>
          <div style="margin-top:6px; color:#475569;">${campaign.phone || '전화번호를 등록해 주세요.'}</div>
          <div style="margin-top:10px;">
            ${campaign.kakao_channel_url ? `<a class="promo-btn kakao public-kakao" href="${campaign.kakao_channel_url}" target="_blank" rel="noopener noreferrer">카카오톡 상담</a>` : ''}
          </div>
          <div style="margin-top:14px; font-size:12px; color:#475569; white-space:pre-wrap;">${landing.disclaimer}</div>
        </div>
      </div>
    `;

    root.querySelectorAll('.public-call').forEach((el) => el.addEventListener('click', () => track('call_click')));
    root.querySelectorAll('.public-kakao').forEach((el) => el.addEventListener('click', () => track('kakao_click')));
  } catch (error) {
    root.innerHTML = `<div class="promo-empty">${error.message}</div>`;
  }
});
