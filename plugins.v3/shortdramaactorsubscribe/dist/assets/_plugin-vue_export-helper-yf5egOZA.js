const PLUGIN_ID = "ShortDramaActorSubscribe";
const API_BASE = `plugin/${PLUGIN_ID}`;
const HOST_MEDIA_PAGE = "/media";
const HOST_DOWNLOAD_CLIENTS = "download/clients";
const HOST_SUBSCRIBE = "subscribe/";
let lastApi = null;
let apiBase = "api/v1/";
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
function mediaPageUrl(work) {
  const query = new URLSearchParams();
  query.set("media_source", work.media_source);
  query.set("media_id", work.media_id);
  query.set("title", work.title);
  if (work.year) query.set("year", work.year);
  query.set("type", work.type || "电视剧");
  return `${appBaseUrl()}#${HOST_MEDIA_PAGE}?${query.toString()}`;
}
function resourceSearchUrl(work, sites) {
  const query = new URLSearchParams();
  query.set("media_source", work.media_source);
  query.set("media_id", work.media_id);
  query.set("type", work.type || "电视剧");
  query.set("area", "title");
  query.set("title", work.title);
  if (work.year) query.set("year", work.year);
  if (sites && sites.length) query.set("sites", sites.join(","));
  return `${appBaseUrl()}#/resource?${query.toString()}`;
}
let cachedSites = null;
async function fetchSearchSites(props) {
  if (cachedSites) return cachedSites;
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const payload = unwrap(await api.get("site/media/tv"));
  const rows = unwrapList(payload);
  const sites = rows.filter((site) => site && site.is_active);
  cachedSites = sites;
  return sites;
}
async function fetchDownloaderOptions(props) {
  const api = resolveApi(props);
  if (!api?.get) return [];
  try {
    const rows = unwrapList(await api.get(HOST_DOWNLOAD_CLIENTS));
    const options = [];
    const seen = /* @__PURE__ */ new Set();
    for (const row of Array.isArray(rows) ? rows : []) {
      const name = String(row?.name || "").trim();
      if (!name || seen.has(name)) continue;
      seen.add(name);
      options.push({ name, type: String(row?.type || "").trim() });
    }
    return options;
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载器列表失败`, err);
    return [];
  }
}
function extractErrorMessage(err) {
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
async function submitSubscribe(props, work, downloader) {
  const api = resolveApi(props);
  if (!api?.post) return { ok: false, message: "缺少可用的 api 实例" };
  const payload = {
    name: work.title,
    year: work.year || "",
    media_source: work.media_source,
    media_id: work.media_id,
    type: work.type || "电视剧"
  };
  if (downloader) payload.downloader = downloader;
  try {
    const res = unwrap(
      await api.post(HOST_SUBSCRIBE, payload)
    );
    if (res && res.success === false) {
      return { ok: false, message: String(res.message || "订阅失败") };
    }
    return { ok: true, message: String(res?.message || `已提交订阅：${work.title}`) };
  } catch (err) {
    return { ok: false, message: extractErrorMessage(err) };
  }
}
function unwrap(response) {
  if (!response) return response;
  if (response.data !== void 0 && response.status !== void 0) return response.data;
  return response;
}
function unwrapList(response) {
  const payload = unwrap(response);
  if (!payload) return [];
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.data)) return payload.data;
  return [];
}
function normalizeFacetList(raw) {
  if (!Array.isArray(raw)) return [];
  return raw.filter((item) => item && typeof item === "object").map((item) => ({
    value: String(item.value ?? ""),
    count: Number(item.count ?? 0)
  })).filter((item) => item.value);
}
function normalizeFacets(raw) {
  return {
    genres: normalizeFacetList(raw?.genres),
    years: normalizeFacetList(raw?.years),
    studios: normalizeFacetList(raw?.studios)
  };
}
function normalizeWork(raw) {
  return {
    ...raw || {},
    genres: Array.isArray(raw?.genres) ? raw.genres.filter((item) => !!item) : [],
    heat: Number(raw?.heat || 0),
    play_count: Number(raw?.play_count || 0),
    studio: String(raw?.studio || ""),
    kind: String(raw?.kind || ""),
    year: String(raw?.year || ""),
    release_date: String(raw?.release_date || "")
  };
}
async function fetchWorks(props, params = {}) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const query = new URLSearchParams();
  query.set("page", String(params.page && params.page > 0 ? params.page : 1));
  query.set("page_size", String(params.page_size && params.page_size > 0 ? params.page_size : 60));
  if (params.actor) query.set("actor", params.actor);
  if (params.genre) query.set("genre", params.genre);
  if (params.year) query.set("year", params.year);
  if (params.studio) query.set("studio", params.studio);
  if (params.sort) query.set("sort", params.sort);
  if (params.only_not_in_library) query.set("only_not_in_library", "1");
  if (params.keyword) query.set("keyword", params.keyword);
  const payload = unwrap(await api.get(`${API_BASE}/works?${query.toString()}`));
  const rows = Array.isArray(payload?.works) ? payload.works : [];
  return {
    ...payload || {},
    works: rows.map(normalizeWork),
    actor_filters: Array.isArray(payload?.actor_filters) ? payload.actor_filters : [],
    facets: normalizeFacets(payload?.facets),
    total: Number(payload?.total || 0),
    page: Number(payload?.page || params.page || 1),
    page_size: Number(payload?.page_size || params.page_size || 60),
    has_more: Boolean(payload?.has_more),
    sort: String(payload?.sort || params.sort || "heat"),
    new_window_days: payload?.new_window_days ?? 3,
    summary: payload?.summary ?? {
      total: 0,
      new: 0,
      library_known: 0,
      in_library: 0
    }
  };
}
async function fetchStatus(props) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  return unwrap(await api.get(`${API_BASE}/status`));
}
async function searchActor(props, name, enrich = false) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  const payload = unwrap(
    await api.post(`${API_BASE}/actors/search`, { name, enrich }, { timeout: 9e4 })
  );
  return { ...payload, candidates: Array.isArray(payload?.candidates) ? payload.candidates : [] };
}
function normalizeSearchWork(raw, index) {
  return normalizeWork({
    key: `sw:${raw?.media_source || "duanju"}:${raw?.media_id || index}`,
    title: String(raw?.title || ""),
    year: String(raw?.year || ""),
    type: "电视剧",
    media_source: String(raw?.media_source || "duanju"),
    media_id: String(raw?.media_id || ""),
    poster: String(raw?.poster || ""),
    vote: Number(raw?.vote || 0),
    episode_count: 0,
    url: "",
    genres: [],
    heat: 0,
    play_count: 0,
    studio: "",
    kind: "",
    release_date: "",
    actor: "",
    actor_key: "",
    first_seen: "",
    is_new: false,
    overview: String(raw?.overview || "")
  });
}
async function searchWorks(props, name) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  const payload = unwrap(
    await api.post(`${API_BASE}/works/search`, { name }, { timeout: 9e4 })
  );
  const rows = Array.isArray(payload?.works) ? payload.works : [];
  return { ...payload, works: rows.map(normalizeSearchWork) };
}
async function addActor(props, name, actor_id = "") {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  return unwrap(
    await api.post(`${API_BASE}/actors/add`, { name, actor_id }, { timeout: 18e4 })
  );
}
async function removeActor(props, name) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  return unwrap(await api.post(`${API_BASE}/actors/remove`, { name }));
}
async function fetchActorWorks(props, actorId, name = "") {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const query = new URLSearchParams();
  if (actorId) query.set("actor_id", actorId);
  if (name) query.set("name", name);
  return unwrap(
    await api.get(`${API_BASE}/actors/works?${query.toString()}`, { timeout: 12e4 })
  );
}
async function fetchConfig(props) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const payload = unwrap(await api.get(`${API_BASE}/config`));
  return payload?.config || payload || {};
}
async function saveConfig(props, config) {
  const api = resolveApi(props);
  if (!api?.put) throw new Error("缺少可用的 api 实例");
  return unwrap(await api.put(`${API_BASE}/config`, config));
}
const BAIKE_MEDIA_SOURCES = /* @__PURE__ */ new Set(["duanju", "duanjubaike"]);
async function fetchSubscribedIds(props) {
  const ids = /* @__PURE__ */ new Set();
  const api = resolveApi(props);
  if (!api?.get) return ids;
  try {
    const rows = unwrapList(await api.get("subscribe/?page=1&count=200"));
    for (const row of rows) {
      if (!row) continue;
      if (!BAIKE_MEDIA_SOURCES.has(String(row.media_source || ""))) continue;
      if (row.media_id) ids.add(String(row.media_id));
    }
  } catch {
  }
  return ids;
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, fetchDownloaderOptions as a, fetchStatus as b, addActor as c, fetchActorWorks as d, searchActor as e, fetchSearchSites as f, searchWorks as g, fetchSubscribedIds as h, submitSubscribe as i, fetchConfig as j, resourceSearchUrl as k, fetchWorks as l, mediaPageUrl as m, proxyImage as p, removeActor as r, saveConfig as s };
