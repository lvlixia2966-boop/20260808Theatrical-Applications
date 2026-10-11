/* MediaSession 绑定助手：点播音频接入系统媒体卡片（锁屏/通知栏可控可显示）。
 *
 * 高内聚：MediaSession 元数据与 play/pause/stop 处理器绑定/解绑收敛于此。
 * 低耦合：各音频模块只传 audio 元素与标题信息，停止时调用 clear()；
 *        不支持的浏览器（旧 iOS/桌面）静默跳过，零副作用。
 *
 * 用途（关屏播放方案 2）：Android 上 <audio> 配合 MediaSession 可在锁屏后
 * 继续播放并显示系统播放卡片；iOS 关屏仍会暂停，但锁屏卡片可一键续播。
 */
(function () {
  'use strict';

  var current = null; // 当前接管的 audio 元素，防止多模块互相覆盖媒体卡片

  function bind(audio, meta) {
    if (!('mediaSession' in navigator)) return;
    current = audio;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: (meta && meta.title) || '四川省川剧院',
        artist: (meta && meta.artist) || '四川省川剧院',
        album: (meta && meta.album) || '语音导览',
        artwork: (meta && meta.artwork) || [
          { src: '/assets/mask-red-ai.png', sizes: '512x512', type: 'image/png' },
        ],
      });
      navigator.mediaSession.setActionHandler('play', function () { audio.play().catch(function () {}); });
      navigator.mediaSession.setActionHandler('pause', function () { audio.pause(); });
      navigator.mediaSession.setActionHandler('stop', function () { if (meta && meta.onStop) meta.onStop(); });
    } catch (e) { /* 平台不支持部分 handler，忽略 */ }
  }

  function clear(audio) {
    if (!('mediaSession' in navigator)) return;
    if (audio && current !== audio) return; // 媒体卡片已被其他模块接管
    current = null;
    try {
      navigator.mediaSession.metadata = null;
      navigator.mediaSession.setActionHandler('play', null);
      navigator.mediaSession.setActionHandler('pause', null);
      navigator.mediaSession.setActionHandler('stop', null);
    } catch (e) { /* ignore */ }
  }

  window.MediaHelper = { bind: bind, clear: clear };
})();
