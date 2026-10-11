/* 购物点导览模块：剧院内外购物点介绍（骨架先行，内容待适配）。
 *
 * 高内聚：购物点数据（SPOTS）+ 卡片渲染 + 语言跟随，全部收敛于此。
 * 低耦合：只依赖 #shopping-spots-list 容器与 app:langchange 事件；
 *        UI 文案内置 zh/en 字典（跟随全局语言，未列语言回退英文）。
 *
 * 内容适配方式：往 SPOTS 数组追加条目即可，字段均为 {zh, en} 双语对象：
 *   {
 *     id: 'souvenir',                       // 唯一 ID
 *     name:    { zh: '文创商店', en: 'Souvenir Shop' },
 *     location:{ zh: '剧院一层大堂东侧', en: 'East side of the lobby' },
 *     hours:   { zh: '演出日 18:00-22:00', en: 'Show days 18:00-22:00' },
 *     desc:    { zh: '一句话介绍…', en: 'One-line intro…' },
 *     tags:    [ { zh: '脸谱周边', en: 'Mask merch' }, … ],
 *     image:   './assets/products/xxx.jpg',   // 可选，缺省用图标占位
 *   }
 */
(function () {
  'use strict';

  /* 购物点数据（内容适配后填充；为空时列表区显示「筹备中」空态） */
  var SPOTS = [
    {
      id: 'theatre-shop',
      name: { zh: '剧院文创商店', en: 'Theatre Souvenir Shop' },
      location: { zh: '剧院一层大堂东侧', en: 'East side of the theatre lobby' },
      hours: { zh: '演出日 18:00 - 22:30', en: 'Show days 18:00 - 22:30' },
      desc: { zh: '脸谱挂件、折扇、蜀绣摆件与《皮金滚灯》同款周边，凭竞答九折邀请码享优惠。',
              en: 'Mask pendants, fans, Shu-embroidery pieces and "Rolling Lantern" merch. Quiz discount codes accepted.' },
      tags: [ { zh: '脸谱周边', en: 'Mask merch' }, { zh: '伴手礼', en: 'Gifts' }, { zh: '步行 0 分钟', en: 'In the theatre' } ],
      image: './assets/products/furong_mask_pendant.jpg',
    },
    {
      id: 'hemin-teahouse',
      name: { zh: '鹤鸣茶社', en: 'Heming Teahouse' },
      location: { zh: '人民公园内（地铁 2 号线人民公园站，步行约 8 分钟）', en: 'Inside People’s Park, ~8 min walk from Metro Line 2' },
      hours: { zh: '每日 08:00 - 22:00', en: 'Daily 08:00 - 22:00' },
      desc: { zh: '百年露天茶馆，一碗盖碗茶配采耳与竹琴，感受成都式慢生活，开演前小坐正合适。',
              en: 'A century-old open-air teahouse. Gaiwan tea, ear-cleaning and bamboo fiddle — perfect before a show.' },
      tags: [ { zh: '盖碗茶', en: 'Gaiwan tea' }, { zh: '老成都', en: 'Old Chengdu' }, { zh: '步行 8 分钟', en: '8 min walk' } ],
      image: './assets/products/furong_gaiwan_teaset.jpg',
    },
    {
      id: 'shuxiu-studio',
      name: { zh: '蜀绣非遗工坊', en: 'Shu Embroidery Atelier' },
      location: { zh: '草堂东路蜀绣基地（车程 10 分钟）', en: 'Shu embroidery base, East Caotang Rd (~10 min by car)' },
      hours: { zh: '周二至周日 09:30 - 17:30', en: 'Tue-Sun 09:30 - 17:30' },
      desc: { zh: '国家级非遗蜀绣的工作室与展销空间，可观摩绣娘现场刺绣，芙蓉鲤鱼双面绣值得一看。',
              en: 'Workshop and gallery of Shu embroidery, a national intangible heritage. Watch artisans at work.' },
      tags: [ { zh: '国家非遗', en: 'Heritage craft' }, { zh: '可体验', en: 'Hands-on' }, { zh: '车程 10 分钟', en: '10 min drive' } ],
      image: './assets/products/furong_embroidery_frame.jpg',
    },
    {
      id: 'kuanzhai',
      name: { zh: '宽窄巷子脸谱铺', en: 'Mask Shops in Kuanzhai Alley' },
      location: { zh: '宽窄巷子历史街区（地铁 4 号线宽窄巷子站，步行约 12 分钟）', en: 'Kuanzhai Alleys, ~12 min walk from Metro Line 4' },
      hours: { zh: '每日 10:00 - 22:00', en: 'Daily 10:00 - 22:00' },
      desc: { zh: '清代街巷里的脸谱彩绘小店，可买手绘面具，也能体验 10 分钟脸谱上妆。',
              en: 'Hand-painted mask boutiques in Qing-dao alleys. Buy a mask or get a 10-minute face-painting.' },
      tags: [ { zh: '手绘脸谱', en: 'Painted masks' }, { zh: '街拍打卡', en: 'Photo spots' }, { zh: '步行 12 分钟', en: '12 min walk' } ],
      image: './assets/products/mask_gold_dragon.jpg',
    },
    {
      id: 'wenshufang',
      name: { zh: '文殊坊非遗街区', en: 'Wenshufang Heritage Block' },
      location: { zh: '文殊院历史街区（地铁 1 号线文殊院站，车程 8 分钟）', en: 'Wenshu Monastery block, ~8 min by Metro Line 1' },
      hours: { zh: '每日 10:00 - 21:30', en: 'Daily 10:00 - 21:30' },
      desc: { zh: '禅茶、素斋与非遗小铺聚集的老街区，川剧陶偶与皮影工坊适合带孩子的家庭。',
              en: 'Old block of zen tea, vegetarian food and craft stalls. Opera pottery and shadow-puppet studios for families.' },
      tags: [ { zh: '亲子友好', en: 'Family friendly' }, { zh: '素斋', en: 'Vegetarian' }, { zh: '车程 8 分钟', en: '8 min ride' } ],
      image: './assets/products/furong_opera_pottery.jpg',
    },
    {
      id: 'taikoo-li',
      name: { zh: '春熙路 · 太古里', en: 'Chunxi Rd & Taikoo Li' },
      location: { zh: '春熙路商圈（地铁 2/3 号线春熙路站，车程 10 分钟）', en: 'Chunxi Road area, ~10 min by Metro Line 2/3' },
      hours: { zh: '商铺 Generally 10:00 - 22:30', en: 'Shops generally 10:00 - 22:30' },
      desc: { zh: '成都最热闹的商圈：川剧主题买手店、竹编与折扇老字号，散场后夜宵与夜景一并安排。',
              en: 'Chengdu’s busiest shopping district — opera-themed boutiques, bamboo-fan classics, plus late-night food after the show.' },
      tags: [ { zh: '夜生活', en: 'Night out' }, { zh: '潮牌买手店', en: 'Trendy stores' }, { zh: '车程 10 分钟', en: '10 min drive' } ],
      image: './assets/products/furong_bamboo_fan.jpg',
    },
  ];
    // 更多条目按同字段追加

    // {
    //   id: 'demo',
    //   name: { zh: '文创商店', en: 'Souvenir Shop' },
    //   location: { zh: '剧院一层大堂东侧', en: 'East side of the lobby' },
    //   hours: { zh: '演出日 18:00 - 22:00', en: 'Show days 18:00-22:00' },
    //   desc: { zh: '集见面具、折扇、蜀绣等川剧特色纪念品。',
    //           en: 'Masks, bamboo fans, Shu embroidery and more.' },
    //   tags: [ { zh: '脸谱周边', en: 'Mask merch' }, { zh: '伴手礼', en: 'Gifts' } ],
    //   image: '',
    // },

  /* 模块 UI 文案（跟随全局语言；未列语言回退英文） */
  var UI = {
    zh: {
      preparing: '内容筹备中',
      preparingSub: '购物点信息正在整理，即将上线，敬请期待',
      subtitle: '剧院内外购物点一览：位置、营业时间与特色推荐',
      locationLabel: '位置', hoursLabel: '营业时间',
    },
    en: {
      preparing: 'Coming soon',
      preparingSub: 'Shopping spot details are being prepared and will be available soon',
      subtitle: 'Shopping spots in and around the theatre: location, hours and highlights',
      locationLabel: 'Location', hoursLabel: 'Hours',
    },
  };

  function lang() {
    var l = localStorage.getItem('app_lang') || 'zh';
    return l.indexOf('zh') === 0 ? 'zh' : (UI[l] ? l : 'en');
  }

  function t(key) {
    var d = UI[lang()] || UI.en;
    return d[key] || UI.en[key] || key;
  }

  function pick(obj) {
    if (!obj) return '';
    return obj[lang()] || obj.en || obj.zh || '';
  }

  function cardHtml(spot) {
    var img = spot.image
      ? '<img src="' + spot.image + '" alt="' + escapeHtml(pick(spot.name)) + '" class="w-full aspect-[4/3] object-cover rounded-lg border border-border">'
      : '<div class="w-full aspect-[4/3] rounded-lg border border-border bg-secondary/40 flex items-center justify-center">'
        + '<i data-lucide="store" class="w-10 h-10 text-muted-foreground/50"></i></div>';
    var tags = (spot.tags || []).map(function (tg) {
      return '<span class="text-[11px] px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/25 whitespace-nowrap">'
        + escapeHtml(pick(tg)) + '</span>';
    }).join('');
    return '<div class="card-modern bg-secondary/40 border border-border rounded-xl p-4 space-y-3">'
      + img
      + '<h4 class="font-bold text-sm text-foreground">' + escapeHtml(pick(spot.name)) + '</h4>'
      + '<div class="text-xs text-muted-foreground space-y-1">'
      + '<div class="flex items-start gap-1.5"><i data-lucide="map-pin" class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-primary"></i>'
      + '<span><b class="font-semibold">' + t('locationLabel') + '：</b>' + escapeHtml(pick(spot.location)) + '</span></div>'
      + '<div class="flex items-start gap-1.5"><i data-lucide="clock" class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-primary"></i>'
      + '<span><b class="font-semibold">' + t('hoursLabel') + '：</b>' + escapeHtml(pick(spot.hours)) + '</span></div>'
      + '</div>'
      + (spot.desc ? '<p class="text-xs text-muted-foreground leading-relaxed">' + escapeHtml(pick(spot.desc)) + '</p>' : '')
      + (tags ? '<div class="flex flex-wrap gap-1.5">' + tags + '</div>' : '')
      + '</div>';
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function render() {
    var list = document.getElementById('shopping-spots-list');
    var badge = document.getElementById('shopping-spots-badge');
    var subtitle = document.getElementById('shopping-spots-subtitle');
    if (!list) return;

    if (subtitle) subtitle.textContent = t('subtitle');
    if (badge) {
      badge.textContent = t('preparing');
      badge.style.display = SPOTS.length ? 'none' : '';
    }

    if (!SPOTS.length) {
      list.className = '';
      list.innerHTML = '<div class="w-full text-center py-14 text-muted-foreground text-sm leading-loose">'
        + '<i data-lucide="store" class="w-12 h-12 mx-auto mb-3 opacity-40"></i><br>' + t('preparingSub') + '</div>';
    } else {
      list.className = 'grid grid-cols-1 md:grid-cols-2 gap-5';
      list.innerHTML = SPOTS.map(cardHtml).join('');
    }
    if (window.lucide) lucide.createIcons();
  }

  window.addEventListener('app:langchange', render);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }

  window.ShoppingSpots = { render: render, data: SPOTS };
})();
