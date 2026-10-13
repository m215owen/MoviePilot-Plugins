const PLUGIN_ID = "ShortDramaActorSubscribe";
const API_BASE = `plugin/${PLUGIN_ID}`;
const HOST_RESOURCE_PAGE = "/resource";
const HOST_MEDIA_PAGE = "/media";
let lastApi = null;
function resolveApi(props) {
  if (props && props.api) {
    rememberApi(props.api);
    return props.api;
  }
  const globalApi = typeof window !== "undefined" ? window.MoviePilotAPI : null;
  if (globalApi) rememberApi(globalApi);
  return globalApi ?? lastApi;
}
function rememberApi(api) {
  lastApi = api;
  const base = api.defaults?.baseURL;
  if (typeof base === "string" && base) apiBase = normalizeApiBase(base);
}
function normalizeApiBase(base) {
  const marker = "api/v1/";
  const index = base.indexOf(marker);
  return index >= 0 ? base.slice(0, index + marker.length) : base;
}
let apiBase = "api/v1/";
function apiPrefix() {
  const fallback = apiBase.endsWith("/") ? apiBase : `${apiBase}/`;
  try {
    const href = typeof window !== "undefined" ? window.location.href : "http://127.0.0.1/";
    const resolved = new URL(apiBase, href).toString();
    return resolved.endsWith("/") ? resolved : `${resolved}/`;
  } catch {
    return fallback;
  }
}
function appBaseUrl() {
  if (typeof window === "undefined") return "";
  return window.location.href.split("#")[0];
}
function proxyImage(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (!/^https?:\/\//i.test(raw)) return raw;
  if (raw.includes("/system/img/")) return raw;
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`;
}
function resourceSearchUrl(keyword, sites) {
  const text = String(keyword || "").trim();
  if (!text) return "";
  const params = new URLSearchParams();
  params.set("keyword", text);
  params.set("title", text);
  const siteText = normalizeSiteIds(sites);
  if (siteText) params.set("sites", siteText);
  return `${appBaseUrl()}#${HOST_RESOURCE_PAGE}?${params.toString()}`;
}
function mediaPageUrl(work) {
  const mediaId = String(work?.media_id ?? "").trim();
  if (!mediaId) return "";
  const params = new URLSearchParams();
  params.set("media_source", String(work?.source ?? "").trim() || "douban");
  params.set("media_id", mediaId);
  for (const key of ["title", "year", "type"]) {
    const value = String(work?.[key] ?? "").trim();
    if (value) params.set(key, value);
  }
  return `${appBaseUrl()}#${HOST_MEDIA_PAGE}?${params.toString()}`;
}
function normalizeSiteIds(sites) {
  if (sites == null) return "";
  const list = Array.isArray(sites) ? sites : String(sites).split(",");
  const ids = [];
  for (const item of list) {
    const text = String(item ?? "").trim();
    if (!text) continue;
    const value = Number(text);
    if (!Number.isFinite(value)) continue;
    ids.push(String(value));
  }
  return ids.join(",");
}
function unwrap(raw) {
  if (raw && typeof raw === "object" && "success" in raw) {
    return raw;
  }
  const nested = raw?.data;
  return nested ?? raw;
}
function normalizeResult(raw) {
  const value = unwrap(raw);
  if (value && typeof value === "object" && "success" in value) {
    return {
      ok: Boolean(value.success),
      data: value.data,
      message: String(value.message || "")
    };
  }
  return { ok: true, data: value ?? void 0, message: "" };
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
function formatTime(value) {
  if (!value) return "尚未运行";
  const timestamp = Date.parse(String(value).replace(" ", "T"));
  if (Number.isNaN(timestamp)) return String(value);
  const diff = Date.now() - timestamp;
  if (diff < 6e4) return "刚刚";
  if (diff < 36e5) return `${Math.floor(diff / 6e4)} 分钟前`;
  if (diff < 864e5) return `${Math.floor(diff / 36e5)} 小时前`;
  return String(value);
}
function formatCooldown(minutes) {
  const value = Number(minutes) || 0;
  if (value <= 0) return "随时重试";
  if (value < 60) return `冷却 ${value} 分钟`;
  const hours = Math.floor(value / 60);
  const rest = value % 60;
  return rest ? `冷却 ${hours} 小时 ${rest} 分` : `冷却 ${hours} 小时`;
}
async function fetchStatus(api) {
  const res = normalizeResult(await api.get(`${API_BASE}/status`));
  return res.ok && res.data ? res.data : null;
}
async function fetchConfig(api) {
  const res = normalizeResult(
    await api.get(`${API_BASE}/config`)
  );
  return res.ok && res.data ? res.data : null;
}
async function saveConfig(api, config) {
  try {
    const res = normalizeResult(await api.put(`${API_BASE}/config`, config));
    return { ok: res.ok, message: res.message || (res.ok ? "配置已保存" : "保存失败") };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function fetchOptions(api) {
  const res = normalizeResult(await api.get(`${API_BASE}/options`));
  return res.ok && res.data ? res.data : null;
}
async function runOnce(api, apply, beforeRun = "") {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/run`));
    if (!res.ok) return { ok: false, message: res.message || "提交执行失败" };
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
    for (let index = 0; index < 90; index += 1) {
      const payload = await fetchStatus(api);
      if (payload) {
        apply(payload);
        const lastRun = String(payload.summary?.last_run || "");
        if (!payload.running && lastRun && lastRun !== beforeRun) {
          return { ok: true, message: payload.last_result?.message || "执行完成" };
        }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2e3));
    }
    return { ok: true, message: "已提交执行，正在后台运行，可稍后刷新查看" };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function organizeNow(api) {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/organize`));
    return { ok: res.ok, message: res.message || (res.ok ? "已执行整理扫描" : "整理未执行") };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function removeLedgerEntry(api, key) {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/unmatch`, { key }));
    return { ok: res.ok, message: res.message || (res.ok ? "已移除" : "移除失败") };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function clearLedger(api) {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/clear`));
    return { ok: res.ok, message: res.message || (res.ok ? "账本已清空" : "清空失败") };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function clearCooldown(api) {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/miss/clear`));
    return { ok: res.ok, message: res.message || (res.ok ? "冷却已清空" : "清空失败") };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function searchActor(api, name) {
  try {
    const res = normalizeResult(
      await api.get(`${API_BASE}/search_actor`, { params: { name } })
    );
    return { ok: res.ok, message: res.message, data: res.data || [] };
  } catch (err) {
    return { ok: false, message: extractError(err), data: [] };
  }
}
async function fetchWorks(api) {
  const res = normalizeResult(await api.get(`${API_BASE}/works`));
  return res.ok && res.data ? res.data : null;
}
async function subscribeWork(api, payload) {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/works/subscribe`, payload));
    return { ok: res.ok, message: res.message || (res.ok ? "已提交下载" : "订阅失败"), data: res.data };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function refreshWorks(api, apply) {
  try {
    const res = normalizeResult(await api.post(`${API_BASE}/works/refresh`));
    if (!res.ok) return { ok: false, message: res.message || "提交刷新失败" };
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
    for (let index = 0; index < 90; index += 1) {
      const payload = await fetchWorks(api);
      if (payload) {
        apply(payload);
        if (!payload.running) return { ok: true, message: "作品已刷新" };
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2e3));
    }
    return { ok: true, message: "正在后台刷新，稍后刷新页面查看" };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { PLUGIN_ID as P, _export_sfc as _, saveConfig as a, formatTime as b, fetchStatus as c, runOnce as d, resourceSearchUrl as e, fetchOptions as f, formatCooldown as g, fetchWorks as h, refreshWorks as i, subscribeWork as j, fetchConfig as k, removeLedgerEntry as l, mediaPageUrl as m, clearLedger as n, organizeNow as o, proxyImage as p, clearCooldown as q, resolveApi as r, searchActor as s };
