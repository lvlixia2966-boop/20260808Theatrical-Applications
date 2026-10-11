/** 麦克风录音（耳机语音沟通的上行链路）：
 *  MediaRecorder 采集（系统会把输入路由到已连接的蓝牙耳机麦克风）→
 *  停止后产出 Blob，交由调用方 POST /api/v1/companion/asr 识别。 */

let stream = null;
let rec = null;
let chunks = [];

export async function canRecord() {
  try {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  } catch {
    return false;
  }
}

/** 开始录音；需先获权。重复调用返回 false。 */
export async function startRecording() {
  if (rec) return false;
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", ""]
    .find((m) => !m || (window.MediaRecorder && MediaRecorder.isTypeSupported(m)));
  rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  chunks = [];
  rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  rec.start();
  return true;
}

/** 停止录音并返回音频 Blob（audio/webm 或 audio/mp4）。 */
export function stopRecording() {
  return new Promise((resolve) => {
    if (!rec) { resolve(null); return; }
    rec.onstop = () => {
      try { stream.getTracks().forEach((t) => t.stop()); } catch { /* ignore */ }
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      rec = null;
      stream = null;
      resolve(blob);
    };
    try { rec.stop(); } catch { resolve(null); }
  });
}

export function isRecording() { return !!rec; }
