(function () {
  const STORAGE_KEY = 'himartPromoSelection';
  const CAMPAIGN_KEY = 'himartPromoCampaign';
  const CREATIVE_KEY = 'himartPromoCreativeResult';
  const CUTOUT_KEY = 'himartPromoCutoutMap';
  const LANDING_KEY = 'himartPromoLanding';
  const INSTAGRAM_KEY = 'himartPromoInstagramResult';
  const BLOG_KEY = 'himartPromoBlogResult';

  function readStorage(key, fallback = null) {
    try {
      const sessionValue = sessionStorage.getItem(key);
      if (sessionValue !== null) return sessionValue;
    } catch {}
    try {
      const localValue = localStorage.getItem(key);
      if (localValue !== null) return localValue;
    } catch {}
    return fallback;
  }

  function writeStorage(key, value) {
    try { sessionStorage.setItem(key, value); } catch {}
    try { localStorage.setItem(key, value); } catch {}
  }

  function removeStorage(key) {
    try { sessionStorage.removeItem(key); } catch {}
    try { localStorage.removeItem(key); } catch {}
  }

  function getSelectionsFromQuery() {
    try {
      const modelsParam = new URLSearchParams(window.location.search).get('models');
      if (!modelsParam) return [];
      return modelsParam
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean)
        .map((modelNo) => ({ model_no: decodeURIComponent(modelNo), _isSubscription: false }));
    } catch {
      return [];
    }
  }

  function showToast(message, duration = 2800) {
    const el = document.getElementById('promo-toast');
    if (!el) return;
    el.textContent = message;
    el.classList.add('show');
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(() => el.classList.remove('show'), duration);
  }

  async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || '요청 처리 중 오류가 발생했습니다.');
    }
    return data;
  }

  function getSelections() {
    try {
      const parsed = JSON.parse(readStorage(STORAGE_KEY, '[]') || '[]');
      if (Array.isArray(parsed) && parsed.length) return parsed;
      return getSelectionsFromQuery();
    } catch {
      return getSelectionsFromQuery();
    }
  }

  function setSelections(items) {
    writeStorage(STORAGE_KEY, JSON.stringify(items || []));
  }

  function getCampaign() {
    try {
      const stored = JSON.parse(readStorage(CAMPAIGN_KEY, 'null') || 'null');
      if (stored?.id) return stored;
      const campaignId = new URLSearchParams(window.location.search).get('campaign_id');
      return campaignId ? { id: campaignId } : null;
    } catch {
      const campaignId = new URLSearchParams(window.location.search).get('campaign_id');
      return campaignId ? { id: campaignId } : null;
    }
  }

  function setCampaign(data) {
    writeStorage(CAMPAIGN_KEY, JSON.stringify(data));
  }

  function clearPromoSession() {
    removeStorage(CAMPAIGN_KEY);
    removeStorage(CREATIVE_KEY);
    removeStorage(CUTOUT_KEY);
    removeStorage(LANDING_KEY);
    removeStorage(INSTAGRAM_KEY);
    removeStorage(BLOG_KEY);
  }

  function setCreativeResult(data) {
    writeStorage(CREATIVE_KEY, JSON.stringify(data));
  }

  function getCreativeResult() {
    try {
      return JSON.parse(readStorage(CREATIVE_KEY, 'null') || 'null');
    } catch {
      return null;
    }
  }

  function setLandingResult(data) {
    writeStorage(LANDING_KEY, JSON.stringify(data));
  }

  function getLandingResult() {
    try {
      return JSON.parse(readStorage(LANDING_KEY, 'null') || 'null');
    } catch {
      return null;
    }
  }

  function setInstagramResult(data) {
    writeStorage(INSTAGRAM_KEY, JSON.stringify(data));
  }

  function getInstagramResult() {
    try {
      return JSON.parse(readStorage(INSTAGRAM_KEY, 'null') || 'null');
    } catch {
      return null;
    }
  }

  function setBlogResult(data) {
    writeStorage(BLOG_KEY, JSON.stringify(data));
  }

  function getBlogResult() {
    try {
      return JSON.parse(readStorage(BLOG_KEY, 'null') || 'null');
    } catch {
      return null;
    }
  }

  function getCutoutMap() {
    try {
      return JSON.parse(readStorage(CUTOUT_KEY, '{}') || '{}');
    } catch {
      return {};
    }
  }

  function saveCutout(productId, data) {
    const current = getCutoutMap();
    current[productId] = data;
    writeStorage(CUTOUT_KEY, JSON.stringify(current));
  }

  async function resolveSelections() {
    const selections = getSelections();
    if (!selections.length) return { items: [], store_info: null };
    return apiFetch('/api/promo/selection/resolve', {
      method: 'POST',
      body: JSON.stringify({ selections }),
    });
  }

  function formatPrice(product, mode) {
    const original = Number(product.original_price || product.price || 0);
    const benefit = Number(product.benefit_price || product.benefitPrice || 0);
    const sale = Number(product.sale_price || product.price || 0);
    const monthly = Number(product.monthly_fee || product.subscriptionPrice || 0);
    let value = benefit || sale || original;
    if (mode === '기본가') value = original || sale || benefit;
    if (mode === '카드혜택 포함') value = benefit || sale || original;
    if (mode === '구독가 포함' && monthly) return `월 ${monthly.toLocaleString('ko-KR')}원`;
    return value ? `${value.toLocaleString('ko-KR')}원` : '가격 문의';
  }

  function getPreferredImage(product) {
    const cutouts = getCutoutMap();
    const key = product.product_id || product.model_no;
    const cutout = key ? cutouts[key] : null;
    return cutout?.processed_url || cutout?.transparent_png_url || product.image_url || '';
  }

  const _BRAND_PATTERN = /^(LG|삼성|Samsung|SAMSUNG|위니아|캐리어|Carrier|대우|코웨이|쿠쿠|Apple|애플|SK|하이얼|Haier|다이슨|Dyson)/i;
  const _CAT_KO = {
    tv: 'TV', refrigerator: '냉장고', washer: '세탁기', dryer: '건조기',
    kimchi: '김치냉장고', aircon: '에어컨', airpurifier: '공기청정기',
    vacuum: '청소기', dishwasher: '식기세척기', range: '전기레인지',
    laptop: '노트북', tablet: '태블릿',
  };

  function getShortProductName(product) {
    const name = String(product.product_name || '');
    const brandM = name.match(_BRAND_PATTERN);
    const brand = brandM ? brandM[1] : (String(product.brand || '').trim() || '');
    const catKo = _CAT_KO[product.category || ''] || '';

    let spec = {};
    try { const s = product.spec; spec = (s && typeof s === 'object') ? s : JSON.parse(s || '{}'); } catch {}

    const inchM   = name.match(/(\d{2,3})\s*(?:인치|형|")/);
    const literM  = name.match(/(\d{2,4})\s*[Ll](?!\w)/);
    const kgM     = name.match(/(\d+(?:\.\d+)?)\s*[Kk][Gg]/);
    const pyeongM = name.match(/(\d+)\s*평/);

    let size = '', feature = '';
    switch (product.category) {
      case 'tv':
        if (inchM) size = `${inchM[1]}인치`;
        feature = (spec.tv_type && spec.tv_type !== 'LED') ? spec.tv_type : '';
        break;
      case 'refrigerator':
        if (literM) size = `${literM[1]}L`;
        feature = (spec.fridge_type && spec.fridge_type !== '일반형') ? spec.fridge_type : '';
        break;
      case 'washer':
        if (kgM) size = `${parseFloat(kgM[1])}kg`;
        feature = spec.washer_type || '';
        break;
      case 'dryer':
        if (kgM) size = `${parseFloat(kgM[1])}kg`;
        feature = spec.dryer_type === '히트펌프' ? '히트펌프' : (spec.dryer_type ? '전기' : '');
        break;
      case 'kimchi':
        if (literM) size = `${literM[1]}L`;
        feature = spec.kimchi_type || '';
        break;
      case 'aircon':
        if (pyeongM) size = `${pyeongM[1]}평`;
        feature = spec.aircon_type || '';
        break;
      case 'airpurifier':
        if (pyeongM) size = `${pyeongM[1]}평`;
        break;
      case 'vacuum':
        feature = spec.vacuum_type || '';
        break;
      case 'dishwasher':
        feature = spec.dish_type || '';
        break;
      case 'range':
        feature = spec.range_type || '';
        break;
      case 'laptop': case 'tablet':
        if (inchM) size = `${inchM[1]}인치`;
        break;
    }

    const join = (...parts) => parts.filter(Boolean).join(' ');
    const LIMIT = 15;
    // 순서: 브랜드 → 용량/크기 → 유형 → 품목
    for (const combo of [
      join(brand, size, feature, catKo),
      join(brand, size, catKo),
      join(brand, feature, catKo),
      join(brand, catKo),
      join(brand, size),
      catKo ? join(brand || '하이마트', catKo) : brand,
    ]) {
      if (combo && combo.length <= LIMIT) return combo;
    }
    return join(brand || '하이마트', catKo).slice(0, LIMIT) || '추천상품';
  }

  function getProductSpecs(product) {
    const name = String(product.product_name || '');
    const spec = [];
    const liters = (name.match(/(\d{2,4})\s*L/i) || [])[1];
    const kg = (name.match(/(\d{1,2}(?:\.\d)?)\s*KG/i) || [])[1];
    const inches = (name.match(/(\d{2,3})\s*(인치|")/i) || [])[1];
    if (liters) spec.push(`${liters}L`);
    if (kg) spec.push(`${kg}KG`);
    if (inches) spec.push(`${inches}인치`);
    if (/4도어/.test(name)) spec.push('4도어');
    if (/양문형/.test(name)) spec.push('양문형');
    if (/뚜껑형/.test(name)) spec.push('뚜껑형');
    if (/스탠드/.test(name)) spec.push('스탠드');
    if (/드럼/.test(name)) spec.push('드럼');
    if (/통돌이/.test(name)) spec.push('통돌이');
    if (/일체형/.test(name)) spec.push('일체형');
    if (/히트펌프/i.test(name)) spec.push('히트펌프');
    if (/OLED/i.test(name)) spec.push('OLED');
    if (/QLED/i.test(name)) spec.push('QLED');
    if (/QNED/i.test(name)) spec.push('QNED');
    if (/2in1/i.test(name)) spec.push('2in1');
    return spec.slice(0, 3);
  }

  async function getRenderableImageSrc(url) {
    if (!url) return '';
    if (url.startsWith('data:')) return url;
    try {
      const result = await apiFetch(`/proxy/image?url=${encodeURIComponent(url)}`, { method: 'GET', headers: {} });
      return result.data || url;
    } catch {
      return url;
    }
  }

  async function waitForImages(root) {
    const images = Array.from(root.querySelectorAll('img'));
    await Promise.all(images.map((img) => {
      if (img.complete && img.naturalWidth > 0) return Promise.resolve();
      return new Promise((resolve) => {
        const done = () => resolve();
        img.addEventListener('load', done, { once: true });
        img.addEventListener('error', done, { once: true });
      });
    }));
  }

  window.promoApp = {
    STORAGE_KEY,
    showToast,
    apiFetch,
    getSelections,
    setSelections,
    resolveSelections,
    getCampaign,
    setCampaign,
    clearPromoSession,
    setCreativeResult,
    getCreativeResult,
    setLandingResult,
    getLandingResult,
    setInstagramResult,
    getInstagramResult,
    setBlogResult,
    getBlogResult,
    formatPrice,
    getPreferredImage,
    getShortProductName,
    getProductSpecs,
    saveCutout,
    getCutoutMap,
    getRenderableImageSrc,
    waitForImages,
  };
})();
