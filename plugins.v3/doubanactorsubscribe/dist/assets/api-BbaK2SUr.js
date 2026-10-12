const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const PLUGIN_ID = "DoubanActorSubscribe";
const API_BASE = `plugin/${PLUGIN_ID}`;
const HOST_SUBSCRIBE = "subscribe/";
const HOST_SITES = "site/rss";
const HOST_DOWNLOAD_PATHS = "download/paths";
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
  if (extras.sites && extras.sites.length) payload.sites = extras.sites;
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
function mergeWorks(actors) {
  const merged = /* @__PURE__ */ new Map();
  for (const actor of actors) {
    for (const work of actor.works || []) {
      const key = workKey(work);
      const existing = merged.get(key);
      if (!existing) {
        merged.set(key, {
          ...work,
          roles: [...work.roles || []],
          actorNames: actor.name ? [actor.name] : []
        });
        continue;
      }
      if (actor.name && !(existing.actorNames || []).includes(actor.name)) {
        existing.actorNames = [...existing.actorNames || [], actor.name];
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

export { API_BASE as A, PLUGIN_ID as P, _export_sfc as _, waitForRefresh as a, submitSubscribe as b, formatTime as c, fetchPathOptions as d, fetchSiteOptions as e, fetchSubscribedKeys as f, mergeWorks as m, normalizeResult as n, proxyImage as p, resolveApi as r, sortWorks as s, unwrap as u, workKey as w };
