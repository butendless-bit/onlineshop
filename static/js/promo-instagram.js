document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const resultEl = document.getElementById('instagram-result');
  const empty = document.getElementById('instagram-empty');
  const captionEl = document.getElementById('instagram-caption');
  const copyBtn = document.getElementById('copy-instagram-caption-btn');
  const generateBtn = document.getElementById('generate-instagram-btn');
  const TASK_NAME = 'instagram';

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
      if (window.self === window.top) window.location.href = '/promo';
      return null;
    }
    if (saved.products?.length) return saved;
    try {
      return await app.apiFetch(`/api/promo/campaign/${saved.id}`);
    } catch {
      return saved;
    }
  }

  function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      if (!btn) { app.showToast('복사되었습니다.'); return; }
      const original = btn.textContent;
      btn.textContent = '복사됨';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = original; btn.classList.remove('copied'); }, 2000);
    }).catch(() => app.showToast('복사에 실패했습니다.'));
  }

  function renderResult(data) {
    const prompt = data?.result?.prompt || data?.prompt || '';
    if (captionEl) captionEl.value = prompt;
    resultEl.style.display = 'block';
    empty.style.display = 'none';
    requestAnimationFrame(postFrameHeight);
  }

  async function generateInstagramCopy() {
    const campaign = await ensureCampaign();
    if (!campaign) return;

    postTaskStatus('processing', '인스타 프롬프트 생성 중');
    empty.textContent = '프롬프트를 생성하고 있습니다...';
    empty.style.display = 'block';
    resultEl.style.display = 'none';

    const response = await app.apiFetch('/api/promo/generate-instagram-copy', {
      method: 'POST',
      body: JSON.stringify({
        campaign_id: campaign.id,
        products: campaign.products,
        event_title: campaign.event_title,
        store_name: campaign.store_name,
        phone: campaign.phone,
        kakao_channel_url: campaign.kakao_channel_url,
      }),
    });

    renderResult(response);
    postTaskStatus('done', '프롬프트 완료');
  }

  copyBtn?.addEventListener('click', () => copyText(captionEl?.value || '', copyBtn));

  generateBtn?.addEventListener('click', async () => {
    try {
      generateBtn.disabled = true;
      generateBtn.textContent = '생성 중...';
      await generateInstagramCopy();
      app.showToast('프롬프트가 생성됐습니다! ChatGPT/Gemini에 붙여넣으세요.');
    } catch (error) {
      app.showToast(error.message);
      empty.textContent = '프롬프트를 불러오지 못했습니다.';
      postTaskStatus('error', '확인 필요');
    } finally {
      generateBtn.disabled = false;
      generateBtn.textContent = '다시 생성하기';
    }
  });

  try {
    await generateInstagramCopy();
    requestAnimationFrame(postFrameHeight);
  } catch (error) {
    app.showToast(error.message);
    empty.textContent = '프롬프트를 불러오지 못했습니다.';
    postTaskStatus('error', '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
