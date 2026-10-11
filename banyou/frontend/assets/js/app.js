/** 应用入口：单页 = AI 伴游纯对话。
 *  准入（ble.js）→ 对话页（companion）。知识库与定位在对话之下工作，
 *  好物与设置经标题栏按钮以浮层打开，不再有独立页面。 */

import { render as companion } from "./views/companion.js";
import { initShop } from "./shop.js";
import "./ble.js";   // 耳机准入：连接专用耳机后才能使用（?demo=1 旁路）
import { refreshIcons } from "./ui.js";

const viewEl = document.getElementById("view");

initShop();

companion(null, viewEl).catch((err) => {
  console.error(err);
  viewEl.innerHTML = `
    <div style="text-align:center;padding:80px 24px;color:#71806f;font-size:14px">
      <div style="font-size:44px">🏔️</div>
      <p>${err && err.message ? err.message : "加载失败"}</p>
      <button class="btn" onclick="location.reload()">重新加载</button>
    </div>`;
});
refreshIcons();
