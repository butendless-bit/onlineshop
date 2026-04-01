document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const resultEl = document.getElementById('blog-result');
  const empty = document.getElementById('blog-empty');
  const promptEl = document.getElementById('blog-single-prompt');
  const copyBtn = document.getElementById('copy-blog-prompt-btn');
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
      if (!btn) {
        app.showToast('복사되었습니다.');
        return;
      }
      const original = btn.textContent;
      btn.textContent = '복사됨';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = original;
        btn.classList.remove('copied');
      }, 2000);
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
    return app.apiFetch(`/api/promo/campaign/${saved.id}`);
  }

  function renderResult(payload) {
    const result = payload?.result || {};
    const promptPackage = result?.prompt_package || {};
    promptEl.value = promptPackage.single_prompt || promptPackage.combined_prompt || '';
    resultEl.style.display = 'block';
    empty.style.display = 'none';
    requestAnimationFrame(postFrameHeight);
  }

  async function generatePrompt() {
    const campaign = await ensureCampaign();
    if (!campaign) return;

    postTaskStatus('processing', '블로그 프롬프트 생성 중');
    empty.style.display = 'block';
    empty.textContent = '블로그용 단일 프롬프트를 준비하는 중입니다...';
    resultEl.style.display = 'none';

    const payload = await app.apiFetch('/api/promo/generate-blog-copy', {
      method: 'POST',
      body: JSON.stringify({
        campaign_id: campaign.id,
        products: campaign.products,
        event_title: campaign.event_title,
        store_name: campaign.store_name,
        phone: campaign.phone,
        kakao_channel_url: campaign.kakao_channel_url,
        target_length: 2000,
      }),
    });

    app.setBlogResult?.(payload);
    renderResult(payload);
    postTaskStatus('done', '블로그 프롬프트 준비 완료');
  }

  copyBtn?.addEventListener('click', () => copyText(promptEl.value || '', copyBtn));

  generateBtn?.addEventListener('click', async () => {
    try {
      generateBtn.disabled = true;
      generateBtn.textContent = '생성 중...';
      await generatePrompt();
      app.showToast('블로그 프롬프트를 만들었습니다.');
    } catch (error) {
      app.showToast(error.message);
      empty.style.display = 'block';
      empty.textContent = '프롬프트를 불러오지 못했습니다.';
      postTaskStatus('error', error.message || '확인 필요');
    } finally {
      generateBtn.disabled = false;
      generateBtn.textContent = '프롬프트 다시 만들기';
    }
  });

  try {
    const cached = app.getBlogResult?.();
    if (cached?.result) {
      renderResult(cached);
      postTaskStatus('done', '블로그 프롬프트 준비 완료');
    } else {
      await generatePrompt();
    }
    requestAnimationFrame(postFrameHeight);
  } catch (error) {
    app.showToast(error.message);
    empty.style.display = 'block';
    empty.textContent = '프롬프트를 불러오지 못했습니다.';
    postTaskStatus('error', error.message || '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
