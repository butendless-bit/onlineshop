document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const resultEl = document.getElementById('instagram-result');
  const empty = document.getElementById('instagram-empty');
  const promptEl = document.getElementById('instagram-single-prompt');
  const copyBtn = document.getElementById('copy-instagram-prompt-btn');
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
    return app.apiFetch(`/api/promo/campaign/${saved.id}`);
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

  function renderResult(result) {
    const promptPackage = result?.prompt_package || {};
    promptEl.value = promptPackage.single_prompt || promptPackage.combined_prompt || '';
    resultEl.style.display = 'block';
    empty.style.display = 'none';
    requestAnimationFrame(postFrameHeight);
  }

  async function generateInstagramPrompt() {
    const campaign = await ensureCampaign();
    if (!campaign) return;

    postTaskStatus('processing', '인스타 프롬프트 생성 중');
    empty.textContent = '인스타그램용 단일 프롬프트를 준비하는 중입니다...';
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

    renderResult(response.result || {});
    postTaskStatus('done', '인스타 프롬프트 준비 완료');
  }

  copyBtn?.addEventListener('click', () => copyText(promptEl.value || '', copyBtn));

  generateBtn?.addEventListener('click', async () => {
    try {
      generateBtn.disabled = true;
      generateBtn.textContent = '생성 중...';
      await generateInstagramPrompt();
      app.showToast('인스타 프롬프트를 만들었습니다.');
    } catch (error) {
      app.showToast(error.message);
      empty.textContent = '프롬프트를 불러오지 못했습니다.';
      postTaskStatus('error', '확인 필요');
    } finally {
      generateBtn.disabled = false;
      generateBtn.textContent = '프롬프트 다시 만들기';
    }
  });

  try {
    await generateInstagramPrompt();
    requestAnimationFrame(postFrameHeight);
  } catch (error) {
    app.showToast(error.message);
    empty.textContent = '프롬프트를 불러오지 못했습니다.';
    postTaskStatus('error', '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
