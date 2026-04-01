document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const table = document.getElementById('saved-table');
  const tbody = table.querySelector('tbody');
  const empty = document.getElementById('saved-empty');

  async function loadCampaigns() {
    const result = await app.apiFetch('/api/promo/campaigns');
    const items = result.items || [];
    tbody.innerHTML = '';
    if (!items.length) {
      empty.style.display = 'block';
      table.style.display = 'none';
      return;
    }
    empty.style.display = 'none';
    table.style.display = 'table';
    items.forEach((item) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${item.campaign_name}</td>
        <td>${item.event_title}</td>
        <td>${String(item.created_at || '').slice(0, 16).replace('T', ' ')}</td>
        <td>방문 ${item.summary.landing_visit_count} / 전화 ${item.summary.call_click_count} / 카카오 ${item.summary.kakao_click_count}</td>
        <td>
          <button class="promo-btn ghost" data-open="${item.id}">열기</button>
          <button class="promo-btn ghost" data-delete="${item.id}">삭제</button>
        </td>
      `;
      tbody.appendChild(row);
    });

    tbody.querySelectorAll('[data-open]').forEach((button) => {
      button.addEventListener('click', async () => {
        const campaign = await app.apiFetch(`/api/promo/campaign/${button.dataset.open}`);
        app.setCampaign(campaign);
        window.location.href = '/promo';
      });
    });
    tbody.querySelectorAll('[data-delete]').forEach((button) => {
      button.addEventListener('click', async () => {
        await app.apiFetch(`/api/promo/campaign/${button.dataset.delete}`, { method: 'DELETE' });
        app.showToast('홍보 패키지를 삭제했습니다.');
        await loadCampaigns();
      });
    });
  }

  loadCampaigns().catch((error) => app.showToast(error.message));
});
