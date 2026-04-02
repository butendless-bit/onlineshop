document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const resultEl = document.getElementById('blog-result');
  const empty = document.getElementById('blog-empty');
  const bodyEl = document.getElementById('blog-body');
  const copyBodyBtn = document.getElementById('copy-blog-body-btn');
  const generateBtn = document.getElementById('generate-blog-btn');
  const TASK_NAME = 'blog';

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

  function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      if (!btn) { app.showToast('복사되었습니다.'); return; }
      const original = btn.textContent;
      btn.textContent = '복사됨';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = original; btn.classList.remove('copied'); }, 2000);
    }).catch(() => app.showToast('복사에 실패했습니다.'));
  }

  async function ensureCampaign() {
    const saved = app.getCampaign();
    if (!saved?.id) {
      if (window.self !== window.top) {
        app.showToast('먼저 프로모션 캠페인을 만들어주세요.');
        return null;
      }
      window.location.href = '/promo';
      return null;
    }
    if (saved.products?.length) return saved;
    try {
      return await app.apiFetch(`/api/promo/campaign/${saved.id}`);
    } catch {
      return saved;
    }
  }

  function renderResult(data) {
    const prompt = data?.result?.prompt || data?.prompt || '';
    if (bodyEl) bodyEl.value = prompt;
    resultEl.style.display = 'block';
    empty.style.display = 'none';
    requestAnimationFrame(postFrameHeight);
  }

  async function generateBlogCopy() {
    const campaign = await ensureCampaign();
    if (!campaign) return;

    postTaskStatus('processing', '블로그 프롬프트 생성 중');
    empty.style.display = 'block';
    empty.textContent = '프롬프트를 생성하고 있습니다...';
    resultEl.style.display = 'none';

    const response = await app.apiFetch('/api/promo/generate-blog-copy', {
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

  copyBodyBtn?.addEventListener('click', () => copyText(bodyEl?.value || '', copyBodyBtn));

  generateBtn?.addEventListener('click', async () => {
    try {
      generateBtn.disabled = true;
      generateBtn.textContent = '생성 중...';
      await generateBlogCopy();
      app.showToast('프롬프트가 생성됐습니다! ChatGPT/Gemini에 붙여넣으세요.');
    } catch (error) {
      app.showToast(error.message);
      empty.style.display = 'block';
      empty.textContent = '프롬프트를 불러오지 못했습니다.';
      postTaskStatus('error', '확인 필요');
    } finally {
      generateBtn.disabled = false;
      generateBtn.textContent = '다시 생성하기';
    }
  });

  try {
    await generateBlogCopy();
    requestAnimationFrame(postFrameHeight);
  } catch (error) {
    app.showToast(error.message);
    empty.style.display = 'block';
    empty.textContent = '프롬프트를 불러오지 못했습니다.';
    postTaskStatus('error', '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
