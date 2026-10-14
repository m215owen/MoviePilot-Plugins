const PLUGIN_ID = "DoubanActorSubscribe";
const API_BASE = `plugin/${PLUGIN_ID}`;
const HOST_SUBSCRIBE = "subscribe/";
const HOST_SITES = "site/rss";
const HOST_DOWNLOAD_PATHS = "download/paths";
const HOST_DOWNLOAD_CLIENTS = "download/clients";
const HOST_MEDIA_PAGE = "/media";
const SUBSCRIBE_PAGE_SIZE = 100;
const SUBSCRIBE_MAX_PAGES = 20;
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
function proxyImage(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (!/^https?:\/\//i.test(raw)) return raw;
  if (raw.includes("/system/img/")) return raw;
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`;
}
function mediaPageUrl(work) {
  const mediaId = String(work?.media_id ?? "").trim();
  if (!mediaId) return "";
  const params = new URLSearchParams();
  params.set("media_source", String(work?.media_source || "").trim() || "themoviedb");
  params.set("media_id", mediaId);
  for (const key of ["title", "year", "type"]) {
    const value = String(work?.[key] ?? "").trim();
    if (value) params.set(key, value);
  }
  return `${appBaseUrl()}#${HOST_MEDIA_PAGE}?${params.toString()}`;
}
function appBaseUrl() {
  if (typeof window === "undefined") return "";
  return window.location.href.split("#")[0];
}
function unwrap(raw) {
  if (raw && typeof raw === "object" && "success" in raw) {
    return raw;
  }
  const nested = raw?.data;
  return nested ?? raw;
}
function unwrapList(raw) {
  const value = raw;
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") {
    const inner = value.data;
    if (Array.isArray(inner)) return inner;
    const deeper = inner?.data;
    if (Array.isArray(deeper)) return deeper;
  }
  return [];
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
const MISSING_INFO_HINTS = [
  "季集信息",
  "季的信息",
  "总集数",
  "集数信息",
  "未识别到媒体信息",
  "媒体信息识别失败"
];
function isMissingInfoMessage(message) {
  const text = String(message || "");
  if (MISSING_INFO_HINTS.some((hint) => text.includes(hint))) return true;
  return text.includes("季") && text.includes("集");
}
async function submitSubscribe(api, work, extras = {}) {
  const payload = {
    name: work.title,
    year: work.year || "",
    media_source: work.media_source,
    media_id: work.media_id
  };
  if (work.type) payload.type = work.type;
  const savePath = String(extras.savePath || "").trim();
  if (savePath) payload.save_path = savePath;
  const downloader = String(extras.downloader || "").trim();
  if (downloader) payload.downloader = downloader;
  if (extras.sites && extras.sites.length) payload.sites = extras.sites;
  try {
    const raw = await api.post(HOST_SUBSCRIBE, payload);
    const res = unwrap(raw);
    if (res && res.success === false) {
      const failure = res.message || "订阅失败";
      if (isMissingInfoMessage(failure)) {
        const reserved = await reserveWork(api, work, extras);
        if (reserved.ok) return reserved;
        return { ok: false, message: `${failure}（转为预订也失败：${reserved.message}）` };
      }
      return { ok: false, message: failure };
    }
    return { ok: true, message: res?.message || `已提交订阅：${work.title}` };
  } catch (err) {
    const message = extractError(err);
    if (isMissingInfoMessage(message)) {
      const reserved = await reserveWork(api, work, extras);
      if (reserved.ok) return reserved;
    }
    return { ok: false, message };
  }
}
async function reserveWork(api, work, extras = {}) {
  try {
    const raw = await api.post(`${API_BASE}/reserve`, {
      title: work.title,
      year: work.year || "",
      type: work.type || "",
      media_source: work.media_source,
      media_id: work.media_id,
      poster: work.poster || "",
      subtitle: work.subtitle || "",
      vote: work.vote || 0,
      save_path: String(extras.savePath || "").trim(),
      downloader: String(extras.downloader || "").trim(),
      sites: extras.sites || []
    });
    const res = unwrap(raw);
    if (res && res.success === false) {
      return { ok: false, message: res.message || "转为预订失败" };
    }
    return { ok: true, message: res?.message || `已按「预订」提交：${work.title}` };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function unsubscribeWork(api, work) {
  try {
    const raw = await api.post(`${API_BASE}/unsubscribe`, {
      media_source: work.media_source,
      media_id: work.media_id,
      title: work.title
    });
    const res = unwrap(raw);
    if (res && res.success === false) {
      return { ok: false, message: res.message || "取消订阅失败" };
    }
    return { ok: true, message: res?.message || `已取消订阅「${work.title}」` };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function ignoreWork(api, work) {
  try {
    const raw = await api.post(`${API_BASE}/ignore`, {
      media_source: work.media_source,
      media_id: work.media_id,
      title: work.title,
      year: work.year,
      type: work.type
    });
    const res = unwrap(raw);
    if (res && res.success === false) {
      return { ok: false, message: res.message || "忽略失败" };
    }
    return { ok: true, message: res?.message || `已忽略「${work.title}」` };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function unignoreWork(api, key = "", all = false) {
  try {
    const raw = await api.post(`${API_BASE}/unignore`, all ? { all: true } : { key });
    const res = unwrap(raw);
    if (res && res.success === false) {
      return { ok: false, message: res.message || "恢复失败" };
    }
    return { ok: true, message: res?.message || "已恢复" };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function removeActor(api, actor) {
  try {
    const raw = await api.post(`${API_BASE}/actor/remove`, {
      actor: actor.key,
      actor_id: actor.id || "",
      name: actor.name || ""
    });
    const res = unwrap(raw);
    if (res && res.success === false) {
      return { ok: false, message: res.message || "移除失败" };
    }
    const display = actor.name || actor.key;
    return { ok: true, message: res?.message || `已移除演员「${display}」` };
  } catch (err) {
    return { ok: false, message: extractError(err) };
  }
}
async function fetchSubscribedKeys(api) {
  const keys = [];
  try {
    for (let page = 1; page <= SUBSCRIBE_MAX_PAGES; page += 1) {
      const raw = await api.get(HOST_SUBSCRIBE, {
        params: { page, count: SUBSCRIBE_PAGE_SIZE }
      });
      const list = unwrapList(raw);
      if (!list.length) break;
      for (const item of list) {
        const row = item;
        if (row?.media_source && row?.media_id) {
          keys.push(`${row.media_source}:${row.media_id}`);
        }
      }
      if (list.length < SUBSCRIBE_PAGE_SIZE) break;
    }
    return keys;
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取已有订阅失败，已按 ${keys.length} 条处理`, err);
    return keys;
  }
}
async function fetchSiteOptions(api) {
  try {
    const raw = await api.get(HOST_SITES);
    const list = unwrapList(raw);
    if (!list.length) return [];
    const options = [];
    for (const row of list) {
      if (row?.id == null) continue;
      if (row.is_active === false) continue;
      options.push({ id: Number(row.id), name: String(row.name || `站点 ${row.id}`) });
    }
    return options;
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取站点列表失败`, err);
    return [];
  }
}
async function fetchPathOptions(api) {
  try {
    const raw = await api.get(HOST_DOWNLOAD_PATHS);
    const list = unwrapList(raw);
    if (!list.length) return [];
    const options = [];
    const seen = /* @__PURE__ */ new Set();
    for (const row of list) {
      const path = String(row.save_path || row.download_path || "").trim();
      if (!path || seen.has(path)) continue;
      seen.add(path);
      const name = String(row.name || "").trim();
      options.push({ name, path });
    }
    return options;
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载目录失败`, err);
    return [];
  }
}
async function fetchDownloaderOptions(api) {
  try {
    const raw = await api.get(HOST_DOWNLOAD_CLIENTS);
    const list = unwrapList(raw);
    if (!list.length) return [];
    const options = [];
    const seen = /* @__PURE__ */ new Set();
    for (const row of list) {
      const name = String(row.name || "").trim();
      if (!name || seen.has(name)) continue;
      seen.add(name);
      options.push({ name, type: String(row.type || "").trim() });
    }
    return options;
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载器列表失败`, err);
    return [];
  }
}
function mergeWorks(actors) {
  const merged = /* @__PURE__ */ new Map();
  for (const actor of actors) {
    const names = actorDisplayNames(actor);
    for (const work of actor.works || []) {
      const key = workKey(work);
      const existing = merged.get(key);
      if (!existing) {
        merged.set(key, {
          ...work,
          roles: [...work.roles || []],
          actorNames: [...names]
        });
        continue;
      }
      const missing = names.filter((name) => !(existing.actorNames || []).includes(name));
      if (missing.length) {
        existing.actorNames = [...existing.actorNames || [], ...missing];
      }
      if (work.is_new) existing.is_new = true;
      const extraRoles = (work.roles || []).filter(
        (item) => !(existing.roles || []).includes(item)
      );
      if (extraRoles.length) existing.roles = [...existing.roles || [], ...extraRoles];
    }
  }
  return Array.from(merged.values());
}
function actorDisplayNames(actor) {
  const name = String(actor.name || "").trim();
  const key = String(actor.key || "").trim();
  const names = name ? [name] : [];
  if (key && key !== name) names.push(key);
  return names;
}
function sortWorks(works, mode = "year") {
  return [...works].sort((a, b) => {
    if (mode === "new") {
      const flag = Number(Boolean(b.is_new)) - Number(Boolean(a.is_new));
      if (flag) return flag;
    }
    return (Number(b.year) || 0) - (Number(a.year) || 0);
  });
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
function waitForRefresh(api, apply, tries = 72, intervalMs = 2500) {
  const tick = async () => {
    for (let index = 0; index < tries; index += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
      try {
        const res = unwrap(await api.get(`${API_BASE}/works`));
        if (res?.success && res.data) {
          apply(res.data);
          if (!res.data.pending_refresh && !res.data.refreshing) return;
        }
      } catch (err) {
        console.debug(`[${PLUGIN_ID}] 等待刷新完成时读取失败`, err);
      }
    }
  };
  void tick();
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { API_BASE as A, PLUGIN_ID as P, _export_sfc as _, waitForRefresh as a, submitSubscribe as b, unsubscribeWork as c, removeActor as d, formatTime as e, fetchSubscribedKeys as f, mediaPageUrl as g, fetchPathOptions as h, ignoreWork as i, fetchDownloaderOptions as j, fetchSiteOptions as k, unignoreWork as l, mergeWorks as m, normalizeResult as n, proxyImage as p, resolveApi as r, sortWorks as s, unwrap as u, workKey as w };
