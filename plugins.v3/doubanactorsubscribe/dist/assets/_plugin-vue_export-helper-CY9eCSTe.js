const PLUGIN_ID = "DoubanActorSubscribe";
const API_BASE = `plugin/${PLUGIN_ID}`;
const HOST_SUBSCRIBE = "subscribe/";
function resolveApi(props) {
  if (props && props.api) return props.api;
  const globalApi = typeof window !== "undefined" ? window.MoviePilotAPI : null;
  return globalApi ?? null;
}
function unwrap(raw) {
  if (raw && typeof raw === "object" && "success" in raw) {
    return raw;
  }
  const nested = raw?.data;
  return nested ?? raw;
}
function workKey(work) {
  return `${work.media_source}:${work.media_id}`;
}
function extractError(err) {
  const anyErr = err;
  const data = anyErr?.response?.data;
  if (data) {
    if (typeof data.detail === "string" && data.detail) return data.detail;
    if (Array.isArray(data.detail) && data.detail.length) {
      const first = data.detail[0];
      if (first?.msg) return String(first.msg);
    }
    if (typeof data.message === "string" && data.message) return data.message;
  }
  return anyErr?.message || "请求失败";
}
async function submitSubscribe(api, work) {
  const payload = {
    name: work.title,
    year: work.year || "",
    media_source: work.media_source,
    media_id: work.media_id
  };
  if (work.type) payload.type = work.type;
  try {
    const raw = await api.post(HOST_SUBSCRIBE, payload);
    const res = unwrap(raw);
    if (res && res.success === false) {
      return { ok: false, message: res.message || "订阅失败" };
    }
    return { ok: true, message: res?.message || `已提交订阅：${work.title}` };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function fetchSubscribedKeys(api) {
  try {
    const raw = await api.get(HOST_SUBSCRIBE, { params: { page: 1, count: 500 } });
    const list = unwrap(raw);
    const keys = [];
    if (Array.isArray(list)) {
      for (const item of list) {
        const row = item;
        if (row?.media_source && row?.media_id) {
          keys.push(`${row.media_source}:${row.media_id}`);
        }
      }
    }
    return keys;
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取已有订阅失败`, err);
    return [];
  }
}
function formatTime(value) {
  if (!value) return "尚未刷新";
  const timestamp = Date.parse(value.replace(" ", "T"));
  if (Number.isNaN(timestamp)) return value;
  const diff = Date.now() - timestamp;
  if (diff < 6e4) return "刚刚";
  if (diff < 36e5) return `${Math.floor(diff / 6e4)} 分钟前`;
  if (diff < 864e5) return `${Math.floor(diff / 36e5)} 小时前`;
  return value;
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { API_BASE as A, PLUGIN_ID as P, _export_sfc as _, formatTime as a, fetchSubscribedKeys as f, resolveApi as r, submitSubscribe as s, unwrap as u, workKey as w };
