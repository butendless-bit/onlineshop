document.addEventListener('DOMContentLoaded', async () => {
  const app = window.promoApp;
  const resultEl = document.getElementById('blog-result');
  const empty = document.getElementById('blog-empty');
  const titlesEl = document.getElementById('blog-titles');
  const bodyEl = document.getElementById('blog-body');
  const ctaEl = document.getElementById('blog-cta');
  const copyBodyBtn = document.getElementById('copy-blog-body-btn');
  const copyAllBtn = document.getElementById('copy-blog-all-btn');
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
    return app.apiFetch(`/api/promo/campaign/${saved.id}`);
  }

  function renderResult(payload) {
    const result = payload?.result || payload || {};
    // result = {titles: [...], body: "...", cta: "..."} from claude_service
    const titles = result?.titles || [];
    const body = result?.body || '';
    const cta = result?.cta || '';

    if (titlesEl) {
      titlesEl.innerHTML = titles.map((t, i) =>
        `<div class="blog-title-option"><span class="blog-title-num">${i + 1}</span><span class="blog-title-text">${t}</span></div>`
      ).join('');
    }
    if (bodyEl) bodyEl.value = body;
    if (ctaEl) ctaEl.value = cta;

    resultEl.style.display = 'block';
    empty.style.display = 'none';
    requestAnimationFrame(postFrameHeight);
  }

  async function generateBlogCopy() {
    const campaign = await ensureCampaign();
    if (!campaign) return;

    postTaskStatus('processing', '블로그 글 생성 중');
    empty.style.display = 'block';
    empty.textContent = 'AI가 블로그 글을 작성하고 있습니다... (약 15~30초 소요)';
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

    renderResult(payload);
    postTaskStatus('done', '블로그 글 완료');
  }

  copyBodyBtn?.addEventListener('click', () => copyText(bodyEl?.value || '', copyBodyBtn));
  copyAllBtn?.addEventListener('click', () => {
    const titles = Array.from(document.querySelectorAll('.blog-title-text')).map(el => el.textContent).join('\n');
    const body = bodyEl?.value || '';
    const cta = ctaEl?.value || '';
    const titleSection = titles ? `📌 제목 후보:\n${titles}\n\n` : '';
    const ctaSection = cta ? `\n\n[상담 유도]\n${cta}` : '';
    copyText(titleSection + body + ctaSection, copyAllBtn);
  });

  generateBtn?.addEventListener('click', async () => {
    try {
      generateBtn.disabled = true;
      generateBtn.textContent = '생성 중...';
      await generateBlogCopy();
      app.showToast('블로그 글을 만들었습니다!');
    } catch (error) {
      app.showToast(error.message);
      empty.style.display = 'block';
      empty.textContent = '블로그 글을 불러오지 못했습니다.';
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
    empty.textContent = '블로그 글을 불러오지 못했습니다.';
    postTaskStatus('error', '확인 필요');
  }

  window.addEventListener('load', postFrameHeight);
  window.addEventListener('resize', postFrameHeight);
});
