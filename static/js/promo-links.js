document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  let campaign = null;

  async function ensureCampaign() {
    const saved = app.getCampaign();
    if (!saved) {
      window.location.href = '/promo';
      return null;
    }
    campaign = await app.apiFetch(`/api/promo/campaign/${saved.id}`);
    return campaign;
  }

  function renderQr(url) {
    const root = document.getElementById('track-link-qr');
    root.innerHTML = '';
    const holder = document.createElement('div');
    holder.style.display = 'grid';
    holder.style.placeItems = 'center';
    holder.style.minHeight = '220px';
    root.appendChild(holder);
    new QRCode(holder, { text: url, width: 180, height: 180 });
  }

  document.getElementById('generate-link-btn')?.addEventListener('click', async () => {
    try {
      const data = await ensureCampaign();
      if (!data) return;
      const result = await app.apiFetch('/api/promo/generate-track-link', {
        method: 'POST',
        body: JSON.stringify({ campaign_id: data.id, source: document.getElementById('link-source').value }),
      });
      document.getElementById('track-link-url').value = result.url || '';
      document.getElementById('track-link-short').value = result.short_url || '';
      renderQr(result.url || result.short_url);
    } catch (error) {
      app.showToast(error.message);
    }
  });

  document.getElementById('copy-link-btn')?.addEventListener('click', async () => {
    const value = document.getElementById('track-link-url').value;
    if (!value) return app.showToast('먼저 추적 링크를 생성해 주세요.');
    await navigator.clipboard.writeText(value);
    app.showToast('추적 링크를 복사했습니다.');
  });
});
