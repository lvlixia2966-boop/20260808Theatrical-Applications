/* 收银台模块：渠道选择 → 创建订单 → 拉起支付 → 轮询结果。
 *
 * 高内聚：收银台 UI、渠道拉取、订单创建、支付结果轮询全部收敛于此。
 * 低耦合：
 *  - 商城结算：Cart 抽屉调用 window.Checkout.open(items)；
 *  - 支付渠道细节（PayPal 沙盒 SDK / 模拟收银台 iframe）由后端 /api/payments/channels 决定。
 *
 * 支付成功后清空购物车并派发 window 事件 'app:order:paid'（detail: order）。
 */
(function () {
  'use strict';

  const I18N = {
    zh: {
      title: '收银台', chooseChannel: '选择支付方式', pay: '支付', close: '关闭',
      waiting: '等待支付结果…', success: '支付成功！', fail: '支付未完成，可稍后在订单中重试。',
      sandbox: '沙盒演示', amount: '应付金额', retry: '重试', loadingErr: '支付服务暂不可用，请稍后重试',
    },
    en: {
      title: 'Checkout', chooseChannel: 'Choose a payment method', pay: 'Pay', close: 'Close',
      waiting: 'Waiting for payment…', success: 'Payment successful!', fail: 'Payment not completed. You can retry later.',
      sandbox: 'Sandbox', amount: 'Amount due', retry: 'Retry', loadingErr: 'Payment service unavailable, try later',
    },
  };
  const lang = () => (localStorage.getItem('app_lang') || 'zh').startsWith('zh') ? 'zh' : 'en';
  const t = (k) => (I18N[lang()] && I18N[lang()][k]) || I18N.zh[k] || k;

  const MAX_POLL_MS = 60000; // 支付轮询上限 60s
  const CHANNEL_ICON = { paypal: '🅿️', wechat: '💬', alipay: '💙' };

  let pollTimer = null;
  let paypalSdkLoaded = false;

  /* ── UI 骨架（懒构建，样式自包含） ─────────────────────── */
  const CSS = `
  #checkout-mask{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:300;display:none;
    align-items:center;justify-content:center;padding:16px}
  #checkout-mask.open{display:flex}
  #checkout-card{width:100%;max-width:420px;background:#fff;border-radius:18px;overflow:hidden;
    box-shadow:0 16px 48px rgba(0,0,0,.2);max-height:92vh;overflow-y:auto}
  .ck-head{padding:16px 20px;border-bottom:1px solid #eee;display:flex;align-items:center}
  .ck-head b{font-size:16px}
  .ck-close{margin-left:auto;border:none;background:none;font-size:18px;color:#999;cursor:pointer;line-height:1}
  .ck-body{padding:20px}
  .ck-amount{text-align:center;margin-bottom:18px}
  .ck-amount .lbl{font-size:12px;color:#999}
  .ck-amount .val{font-size:32px;font-weight:800;color:#111}
  .ck-channels{display:flex;flex-direction:column;gap:10px}
  .ck-channel{display:flex;align-items:center;gap:12px;padding:14px 16px;border:1.5px solid #e5e5e5;
    border-radius:12px;cursor:pointer;transition:border .15s;background:#fff;width:100%;text-align:left}
  .ck-channel:hover{border-color:#059669}
  .ck-channel .ico{font-size:22px}
  .ck-channel .nm{font-size:14px;font-weight:700;color:#222}
  .ck-channel .tag{margin-left:auto;font-size:10px;color:#b45309;background:#fef3c7;padding:2px 8px;border-radius:999px}
  .ck-status{text-align:center;padding:28px 0;font-size:14px;color:#555}
  .ck-status .spin{display:block;width:34px;height:34px;margin:0 auto 14px;border:3px solid #e5e5e5;
    border-top-color:#059669;border-radius:50%;animation:ckspin .8s linear infinite}
  @keyframes ckspin{to{transform:rotate(360deg)}}
  .ck-success{text-align:center;padding:24px 0}
  .ck-success .ok{width:56px;height:56px;margin:0 auto 12px;border-radius:50%;background:#e8f7ee;color:#059669;
    font-size:28px;display:flex;align-items:center;justify-content:center}
  .ck-success .msg{font-size:15px;font-weight:700;color:#059669}
  .ck-iframe-wrap{width:100%;height:420px;border:1px solid #eee;border-radius:12px;overflow:hidden}
  .ck-iframe-wrap iframe{width:100%;height:100%;border:none}
  .ck-err{background:#fdecec;color:#d93025;font-size:13px;border-radius:10px;padding:10px 12px;margin-bottom:12px}
  #paypal-btn-box{min-height:46px}
  `;

  function ensureUI() {
    if (document.getElementById('checkout-mask')) return;
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);
    const mask = document.createElement('div');
    mask.id = 'checkout-mask';
    mask.innerHTML = `
      <div id="checkout-card">
        <div class="ck-head"><b data-ck="title"></b>
          <button class="ck-close" data-ck="close">✕</button></div>
        <div class="ck-body" data-ck="body"></div>
      </div>`;
    document.body.appendChild(mask);
    mask.querySelector('[data-ck="close"]').addEventListener('click', close);
    mask.addEventListener('click', (e) => { if (e.target === mask) close(); });
  }

  function setBody(html) {
    document.querySelector('#checkout-mask [data-ck="body"]').innerHTML = html;
  }
  function setTitle(text) {
    document.querySelector('#checkout-mask [data-ck="title"]').textContent = text;
  }

  async function api(path, opts) {
    const resp = await fetch(path, opts);
    const body = await resp.json().catch(() => ({ code: -1, message: 'bad response' }));
    if (!resp.ok || body.code !== 0) throw new Error(body.message || `HTTP ${resp.status}`);
    return body.data;
  }

  /* ── 主流程 ───────────────────────────────────────────── */
  async function open(items) {
    ensureUI();
    document.getElementById('checkout-mask').classList.add('open');
    setTitle(`💳 ${t('title')}`);
    const totalCents = items.reduce((s, i) => s + i.price_cents * i.qty, 0);
    setBody(`
      <div class="ck-amount">
        <div class="lbl">${t('amount')}</div>
        <div class="val">¥${(totalCents / 100).toFixed(2)}</div>
      </div>
      <div data-ck="err"></div>
      <div data-ck="area"></div>
    `);
    const area = document.querySelector('#checkout-mask [data-ck="area"]');
    area.innerHTML = `<div class="ck-status"><span class="spin"></span>${t('chooseChannel')}…</div>`;

    try {
      const data = await api('/api/payments/channels');
      renderChannels(area, data, items);
    } catch (e) {
      area.innerHTML = `<div class="ck-status">${t('loadingErr')}</div>`;
    }
  }

  function renderChannels(area, data, items) {
    area.innerHTML = `
      <div class="ck-channels">
        ${data.channels.map(ch => `
          <button class="ck-channel" data-channel="${ch.channel}">
            <span class="ico">${CHANNEL_ICON[ch.channel] || '💳'}</span>
            <span class="nm">${ch.name}</span>
            ${ch.mode === 'mock' ? `<span class="tag">${t('sandbox')}</span>` : ''}
          </button>`).join('')}
      </div>`;
    area.querySelectorAll('.ck-channel').forEach(btn => {
      btn.addEventListener('click', () => createOrder(btn.dataset.channel, data, items));
    });
  }

  async function createOrder(channel, channelsData, items) {
    const area = document.querySelector('#checkout-mask [data-ck="area"]');
    area.innerHTML = `<div class="ck-status"><span class="spin"></span>${t('waiting')}</div>`;
    let order;
    try {
      const data = await api('/api/payments/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene: 'mall', channel, items }),
      });
      order = data.order; // 后端包装为 {order: PaymentOrderOut}
    } catch (e) {
      showFail(area, e.message);
      return;
    }
    launchPayment(order, channelsData);
  }

  function launchPayment(order, channelsData) {
    const area = document.querySelector('#checkout-mask [data-ck="area"]');
    const usePaypalSdk = order.channel === 'paypal' && channelsData.paypal_client_id;

    if (usePaypalSdk) {
      area.innerHTML = `<div id="paypal-btn-box"></div><div data-ck="err"></div>`;
      loadPaypalSdk(channelsData.paypal_client_id).then(() => {
        window.paypal.Buttons({
          style: { layout: 'vertical' },
          createOrder: () => order.gateway_order_id, // 后端已创建 PayPal 沙盒订单
          onApprove: async (data2) => {
            try {
              const done = await api(`/api/payments/orders/${order.order_no}/paypal-capture`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: data2.orderID }),
              });
              onPaid(done.order);
            } catch (e) { showFail(area, e.message); }
          },
          onCancel: () => showFail(area, t('fail')),
          onError: () => showFail(area, t('fail')),
        }).render('#paypal-btn-box');
      }).catch(() => {
        // SDK 加载失败（如无外网）：降级模拟收银台
        startPolling(order);
        area.innerHTML = iframeHtml(order.pay_url);
      });
      return;
    }

    // 模拟收银台（iframe 内完成"支付"，主窗口轮询订单状态）
    startPolling(order);
    area.innerHTML = iframeHtml(order.pay_url);
  }

  function iframeHtml(url) {
    return `<div class="ck-iframe-wrap"><iframe src="${url}" allow="payment"></iframe></div>`;
  }

  function loadPaypalSdk(clientId) {
    if (paypalSdkLoaded && window.paypal) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=CNY`;
      s.onload = () => { paypalSdkLoaded = true; resolve(); };
      s.onerror = () => reject(new Error('paypal sdk load failed'));
      document.head.appendChild(s);
    });
  }

  function startPolling(order) {
    stopPolling();
    pollTimer = setInterval(async () => {
      try {
        const data = await api(`/api/payments/orders/${order.order_no}`);
        if (data.status === 'paid') { stopPolling(); onPaid(data); }
      } catch { /* 网络抖动忽略，下轮重试 */ }
    }, 2000);
  }
  function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

  function onPaid(order) {
    setBody(`
      <div class="ck-success">
        <div class="ok">✓</div>
        <div class="msg">${t('success')}</div>
        <div style="font-size:12px;color:#999;margin-top:6px">${order.order_no}</div>
      </div>`);
    if (window.Cart) window.Cart.clear();
    window.dispatchEvent(new CustomEvent('app:order:paid', { detail: { order } }));
  }

  function showFail(area, message) {
    area.innerHTML = `
      <div class="ck-err">${message || t('fail')}</div>
      <div class="ck-status">${t('fail')}</div>`;
  }

  function close() {
    stopPolling();
    const mask = document.getElementById('checkout-mask');
    if (mask) mask.classList.remove('open');
  }

  window.Checkout = { open, close };
})();
