const PLUGIN_ID = "ShortDramaActorSubscribe";
const API_BASE = `plugin/${PLUGIN_ID}`;
const HOST_DOWNLOAD_CLIENTS = "download/clients";
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
function retryProxyImage(url, attempt) {
  if (!url || attempt <= 0) return url;
  return `${url}${url.includes("?") ? "&" : "?"}retry=${attempt}`;
}
function proxyImage(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (!/^https?:\/\//i.test(raw)) return raw;
  if (raw.includes("/system/img/")) return raw;
  return `${apiPrefix()}system/img/0?imgurl=${encodeURIComponent(raw)}&cache=true`;
}
function resourceSearchUrl(work, sites) {
  const query = new URLSearchParams();
  query.set("keyword", work.title);
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
  const rows = unwrapList(await api.get("site/media/tv", { ...SILENT }));
  const sites = rows.filter((site) => site && site.is_active);
  cachedSites = sites;
  return sites;
}
async function fetchDownloaderOptions(props) {
  const api = resolveApi(props);
  if (!api?.get) return [];
  try {
    const rows = unwrapList(
      await api.get(HOST_DOWNLOAD_CLIENTS, { ...SILENT })
    );
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
async function fetchDownloadPaths(props) {
  const api = resolveApi(props);
  if (!api?.get) return [];
  try {
    const rows = unwrapList(
      await api.get("download/paths", { ...SILENT })
    );
    const options = [];
    const seen = /* @__PURE__ */ new Set();
    for (const row of Array.isArray(rows) ? rows : []) {
      const savePath = String(row?.save_path || row?.download_path || "").trim();
      if (!savePath || seen.has(savePath)) continue;
      seen.add(savePath);
      options.push({
        name: String(row?.name || "").trim() || savePath,
        storage: String(row?.storage || "local").trim(),
        download_path: String(row?.download_path || "").trim(),
        save_path: savePath
      });
    }
    return options;
  } catch (err) {
    console.warn(`[${PLUGIN_ID}] 读取下载目录失败`, err);
    return [];
  }
}
async function fetchSubscriptions(props) {
  const api = resolveApi(props);
  if (!api?.get) {
    return { engine: "", items: [], default_sites: "", default_downloader: "", default_save_path: "" };
  }
  try {
    const data = readData(await api.get(`${API_BASE}/subscriptions`, { ...SILENT }));
    return {
      engine: String(data?.engine || ""),
      items: Array.isArray(data?.items) ? data.items : [],
      default_sites: String(data?.default_sites || ""),
      default_downloader: String(data?.default_downloader || ""),
      default_save_path: String(data?.default_save_path || "")
    };
  } catch {
    return { engine: "", items: [], default_sites: "", default_downloader: "", default_save_path: "" };
  }
}
async function pluginSubscribe(props, work) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  return unwrap(
    await api.post(
      `${API_BASE}/subscribe`,
      {
        title: String(work.title || ""),
        year: String(work.year || ""),
        media_source: String(work.media_source || "djbaike"),
        media_id: String(work.media_id || ""),
        actor: String(work.actor || ""),
        poster: String(work.poster || "")
      },
      { ...SILENT }
    )
  );
}
async function pluginUnsubscribe(props, mediaId) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  return unwrap(
    await api.post(`${API_BASE}/unsubscribe`, { media_id: String(mediaId || "") }, { ...SILENT })
  );
}
async function pluginSubscribeUpdate(props, mediaId, targets) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  const payload = { media_id: String(mediaId || "") };
  if (targets) {
    if (targets.sites !== void 0) payload.sites = targets.sites;
    if (targets.downloader !== void 0) payload.downloader = targets.downloader;
    if (targets.save_path !== void 0) payload.save_path = targets.save_path;
  }
  return unwrap(
    await api.post(`${API_BASE}/subscribe/update`, payload, { ...SILENT })
  );
}
async function pluginSubscribeSearchNow(props, mediaId) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  return unwrap(
    await api.post(
      `${API_BASE}/subscribe/search_now`,
      { media_id: String(mediaId || "") },
      { ...SILENT }
    )
  );
}
async function pluginSubscribeRandom(props, count) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  return unwrap(
    await api.post(
      `${API_BASE}/subscribe/random`,
      { count: Math.max(1, Math.min(10, Math.floor(count) || 1)) },
      { ...SILENT }
    )
  );
}
async function pluginSubscribeSearchAll(props) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  return unwrap(
    await api.post(`${API_BASE}/subscribe/search_all`, {}, { ...SILENT })
  );
}
const SILENT = { feedback: "silent" };
function isAxiosResponse(value) {
  if (!value || typeof value !== "object") return false;
  return typeof value.status === "number" && typeof value.statusText === "string" && typeof value.headers === "object" && value.headers !== null && "data" in value;
}
function unwrap(response) {
  if (isAxiosResponse(response)) return response.data;
  return response;
}
function readData(response) {
  const payload = unwrap(response);
  if (payload && typeof payload === "object" && payload.success === false) {
    throw new Error(String(payload.message || "操作失败"));
  }
  return payload?.data ?? null;
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
    studios: normalizeFacetList(raw?.studios),
    platforms: normalizeFacetList(raw?.platforms)
  };
}
function normalizeWork(raw) {
  return {
    ...raw || {},
    genres: Array.isArray(raw?.genres) ? raw.genres.filter((item) => !!item) : [],
    heat: Number(raw?.heat || 0),
    play_count: Number(raw?.play_count || 0),
    studio: String(raw?.studio || ""),
    // 播放平台：作品卡目前不带（平台只在详情页 meta 里），恒空 ⇒ 墙上的平台筛选行自动隐藏。
    // 数据源哪天在卡片层补上，这里不用改，直接就有值。
    platform: String(raw?.platform || ""),
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
  if (params.platform) query.set("platform", params.platform);
  if (params.sort) query.set("sort", params.sort);
  if (params.only_not_in_library) query.set("only_not_in_library", "1");
  if (params.only_not_subscribed) query.set("only_not_subscribed", "1");
  if (params.keyword) query.set("keyword", params.keyword);
  const payload = readData(
    await api.get(`${API_BASE}/works?${query.toString()}`, { ...SILENT })
  );
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
    sort: String(payload?.sort || params.sort || "date"),
    new_window_days: payload?.new_window_days ?? 7,
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
  return readData(await api.get(`${API_BASE}/status`, { ...SILENT }));
}
function normalizeLookupWork(raw, index) {
  const mediaId = String(raw?.media_id || "");
  const release = String(raw?.release_date || "");
  return normalizeWork({
    key: `sw:${mediaId || index}`,
    title: String(raw?.title || ""),
    year: release.slice(0, 4) || String(raw?.year || "").slice(0, 4),
    type: "电视剧",
    media_source: "djbaike",
    media_id: mediaId,
    poster: String(raw?.poster_path || raw?.poster || ""),
    vote: Number(raw?.vote_average || raw?.rating || 0),
    episode_count: Number(raw?.number_of_episodes || raw?.episodes || 0),
    url: String(raw?.detail_link || raw?.url || ""),
    genres: (Array.isArray(raw?.genres) ? raw.genres : []).map((item) => String(item?.name ?? item ?? "").trim()).filter(Boolean),
    heat: 0,
    play_count: 0,
    studio: "",
    platform: "",
    kind: "",
    release_date: release,
    actor: "",
    actor_key: "",
    first_seen: "",
    is_new: false
  });
}
function normalizeLookupActor(raw) {
  const mediaId = String(raw?.media_id || raw?.actor_id || "");
  return {
    name: String(raw?.title || raw?.name || "").trim(),
    actor_id: mediaId,
    media_id: mediaId,
    // 站内搜索的结果未必与输入完全同名（可能是同名不同人），交给卡片让用户判断
    exact: false,
    profile: String(raw?.poster_path || raw?.poster || "").trim() || void 0,
    works_count: 0,
    job_title: void 0,
    gender: void 0,
    nationality: void 0,
    bio: void 0,
    followers: 0,
    likes: 0,
    url: String(raw?.detail_link || raw?.url || "").trim() || void 0
  };
}
async function lookupSite(props, keyword) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const text = String(keyword || "").trim();
  if (!text) return { works: [], actors: [], source: "" };
  const payload = unwrap(
    await api.get(
      `plugin/ShortDramaBaikeScraper/lookup?name=${encodeURIComponent(text)}&remote=1`,
      { ...SILENT, timeout: 6e4 }
    )
  );
  const data = payload?.data;
  const rows = Array.isArray(data) ? data : [];
  const works = [];
  const actors = [];
  for (const raw of rows) {
    const mediaId = String(raw?.media_id || "");
    const entity = mediaId.split(":")[0] || "";
    if (["duanju", "manju", "hema", "huolong"].includes(entity)) {
      works.push(normalizeLookupWork(raw, works.length));
    } else if (["yanyuan", "daoyan", "bianju"].includes(entity)) {
      actors.push(normalizeLookupActor(raw));
    }
  }
  return { works, actors, source: "djbaike" };
}
async function mutateActor(props, action, body, timeout) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  const envelope = unwrap(
    await api.post(`${API_BASE}/actors/${action}`, body, {
      ...SILENT,
      ...timeout ? { timeout } : {}
    })
  );
  const data = envelope?.data || {};
  return {
    message: String(envelope?.message || ""),
    actors: Array.isArray(data.actors) ? data.actors : [],
    need_pick: Boolean(data.need_pick),
    candidates: Array.isArray(data.candidates) ? data.candidates : []
  };
}
async function addActor(props, name, actor_id = "") {
  return mutateActor(props, "add", { name, actor_id }, 18e4);
}
async function removeActor(props, identity) {
  return mutateActor(props, "remove", { ...identity });
}
async function fetchActorList(props) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const data = readData(
    await api.get(`${API_BASE}/actors`, { ...SILENT })
  );
  return Array.isArray(data?.actors) ? data.actors : [];
}
async function fetchActorCards(props, enrich = false) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const query = enrich ? "?enrich=1" : "";
  const data = readData(
    await api.get(`${API_BASE}/actors/cards${query}`, { ...SILENT, timeout: 12e4 })
  );
  return Array.isArray(data?.actors) ? data.actors : [];
}
async function fetchActorDetail(props, actorId, name = "", page = 1, pageSize = 24) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const query = new URLSearchParams();
  if (actorId) query.set("actor_id", actorId);
  if (name) query.set("name", name);
  query.set("works_page", String(page));
  query.set("works_page_size", String(pageSize));
  return readData(
    await api.get(`${API_BASE}/actors/detail?${query.toString()}`, {
      ...SILENT,
      timeout: 18e4
    })
  );
}
function normalizeActorSubscribeAll(raw) {
  const details = Array.isArray(raw?.details) ? raw.details.filter((row) => row && typeof row === "object").map((row) => ({
    time: String(row.time || ""),
    title: String(row.title || ""),
    year: String(row.year || ""),
    media_id: String(row.media_id || ""),
    actor: String(row.actor || ""),
    ok: row.ok === true,
    detail: String(row.detail || "")
  })) : [];
  return {
    name: String(raw?.name || ""),
    total: Number(raw?.total || 0),
    submitted: Number(raw?.submitted || 0),
    skipped_library: Number(raw?.skipped_library || 0),
    skipped_subscribed: Number(raw?.skipped_subscribed || 0),
    failed: Number(raw?.failed || 0),
    capped: raw?.capped === true,
    media_ids: Array.isArray(raw?.media_ids) ? raw.media_ids.map((item) => String(item)).filter(Boolean) : [],
    details
  };
}
async function subscribeAllActor(props, info) {
  const api = resolveApi(props);
  if (!api?.post) throw new Error("缺少可用的 api 实例");
  const res = readData(
    await api.post(
      `${API_BASE}/actors/subscribe_all`,
      {
        actor_id: String(info.actorId || ""),
        name: String(info.name || ""),
        exclude_ids: (info.excludeIds || []).map(String).filter(Boolean)
      },
      { ...SILENT, timeout: 18e4 }
    )
  );
  return normalizeActorSubscribeAll(res);
}
async function fetchRanks(props) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  return readData(await api.get(`${API_BASE}/ranks`, { ...SILENT })) || {
    ranks: [],
    message: ""
  };
}
async function fetchRankWorks(props, rank, page = 1) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const query = new URLSearchParams();
  query.set("rank", rank);
  query.set("page", String(Math.max(1, page)));
  const payload = readData(
    await api.get(`${API_BASE}/ranks/works?${query.toString()}`, {
      ...SILENT,
      timeout: 6e4
    })
  );
  const rows = Array.isArray(payload?.medias) ? payload.medias : [];
  return {
    rank: payload?.rank || rank,
    name: payload?.name || "",
    page: Number(payload?.page) || page,
    has_more: Boolean(payload?.has_more),
    message: payload?.message || "",
    medias: rows
  };
}
async function fetchLogs(props, limit = 80) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  return readData(
    await api.get(`${API_BASE}/logs?limit=${encodeURIComponent(String(limit))}`, {
      ...SILENT,
      timeout: 15e3
    })
  ) || { items: [] };
}
async function fetchPeople(props, kind, page) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const query = new URLSearchParams();
  query.set("kind", kind);
  query.set("page", String(page));
  return readData(
    await api.get(`${API_BASE}/people?${query.toString()}`, {
      ...SILENT,
      timeout: 6e4
    })
  ) || { kind, page, has_more: false, message: "", people: [] };
}
async function fetchWorkDetail(props, work) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  const query = new URLSearchParams();
  query.set("media_id", String(work?.media_id || ""));
  if (work?.title) query.set("title", work.title);
  if (work?.year) query.set("year", work.year);
  const data = readData(
    await api.get(`${API_BASE}/works/detail?${query.toString()}`, {
      ...SILENT,
      timeout: 12e4
    })
  );
  return normalizeWorkDetail(data);
}
function normalizeWorkDetail(raw) {
  return {
    ...raw || {},
    found: raw?.found === true,
    title: String(raw?.title || ""),
    year: String(raw?.year || ""),
    media_source: String(raw?.media_source || "djbaike"),
    media_id: String(raw?.media_id || ""),
    type: String(raw?.type || "电视剧"),
    overview: String(raw?.overview || ""),
    poster: String(raw?.poster || ""),
    backdrop: String(raw?.backdrop || ""),
    vote: Number(raw?.vote || 0),
    release_date: String(raw?.release_date || ""),
    episode_count: Number(raw?.episode_count || 0),
    episode_minutes: Number(raw?.episode_minutes || 0),
    duration_minutes: Number(raw?.duration_minutes || 0),
    genres: Array.isArray(raw?.genres) ? raw.genres.filter((tag) => !!tag) : [],
    studio: String(raw?.studio || ""),
    // 播放平台（「在哪播」）：详情层后端从 MediaInfo 的 networks 收敛出来，
    // 拿不到再拿墙上那一行兜底（merge_detail_row），都取不到就是空串
    platform: String(raw?.platform || ""),
    status: String(raw?.status || ""),
    language: String(raw?.language || ""),
    url: String(raw?.url || ""),
    actors: Array.isArray(raw?.actors) ? raw.actors.filter((row) => row && row.name).map((row) => ({
      actor_id: String(row.actor_id || ""),
      name: String(row.name),
      character: String(row.character || ""),
      profile: String(row.profile || ""),
      kind: String(row.kind || ""),
      url: String(row.url || ""),
      subscribed: row.subscribed === true
    })) : [],
    heat: Number(raw?.heat || 0),
    play_count: Number(raw?.play_count || 0),
    kind: String(raw?.kind || ""),
    first_seen: String(raw?.first_seen || ""),
    is_new: raw?.is_new === true,
    in_library: typeof raw?.in_library === "boolean" ? raw.in_library : null
  };
}
const EMPTY_SOURCE = {
  director: [],
  writer: [],
  cast: [],
  heat_text: "",
  play_count_text: "",
  favorites_text: "",
  status: "",
  duration_minutes: 0,
  duration_text: "",
  studio: "",
  platform: "",
  douban_id: "",
  douban_url: "",
  adapted_title: "",
  adapted_author: "",
  adapted_url: "",
  adapted: null
};
function toNumber(value) {
  const num = Number(String(value ?? "").replace(/[^\d.]/g, ""));
  return Number.isFinite(num) ? num : 0;
}
function personIdFromUrl(url) {
  const hit = String(url || "").match(/\/(yanyuan|daoyan|bianju)\/info-(\d+)\.html/);
  return hit ? `${hit[1]}:${hit[2]}` : "";
}
function parseWordCount(text) {
  const raw = String(text || "").trim();
  const hit = raw.match(/([\d.]+)/);
  if (!hit) return 0;
  const value = Number(hit[1]);
  if (!Number.isFinite(value)) return 0;
  return raw.includes("万") ? Math.round(value * 1e4) : Math.round(value);
}
function novelToAdaptedInfo(novel) {
  const title = String(novel?.name || "").trim();
  if (!title) return null;
  return {
    title,
    author: String(novel?.author || "").trim(),
    url: String(novel?.detail_url || "").trim(),
    poster: String(novel?.poster || "").trim(),
    media_id: String(novel?.media_id || "").trim(),
    words: parseWordCount(novel?.words),
    genres: [],
    summary: String(novel?.overview || "").trim(),
    works: (Array.isArray(novel?.adaptations) ? novel.adaptations : []).filter((item) => String(item?.name || "").trim()).map((item) => {
      const mediaId = String(item.media_id || "").trim();
      const split = mediaId.split(":");
      return {
        media_id: mediaId,
        title: String(item.name).trim(),
        url: split[0] && split[1] ? `https://www.duanjubaike.net/${split[0]}/info-${split[1]}.html` : "",
        poster: String(item.poster || "").trim(),
        release_date: String(item.date || "").trim(),
        episodes: toNumber(item.episodes),
        genres: []
      };
    })
  };
}
async function fetchWorkSource(props, mediaId) {
  const api = resolveApi(props);
  if (!api?.get || !mediaId) return { ...EMPTY_SOURCE };
  try {
    const payload = unwrap(
      await api.get(
        `plugin/ShortDramaBaikeScraper/lookup?media_id=${encodeURIComponent(mediaId)}`,
        { ...SILENT, timeout: 2e4 }
      )
    );
    const info = payload?.data;
    if (!info || typeof info !== "object") return { ...EMPTY_SOURCE };
    const creditRows = (rows, kind, fallbackRole) => (Array.isArray(rows) ? rows : []).filter((item) => String(item?.name || "").trim()).map((item) => ({
      name: String(item.name).trim(),
      media_id: personIdFromUrl(item.url),
      role: String(item.character || item.job || "").trim() || fallbackRole,
      kind,
      // 头像：数据源（MediaCredit）给的是宿主形体 ``profile_path``，同样收
      // ``profile`` / ``poster`` 两种别名 —— 过去这里写死空串，导演/编剧卡
      // 因此永远只能出人形占位（演员走详情端点那一份，同源缺陷在 2026-10-22 一并修）。
      profile: String(
        item.profile_path || item.profile || item.poster || ""
      ).trim()
    }));
    const director = creditRows(info.directors, "daoyan", "导演");
    const writer = [];
    const cast = creditRows(info.actors, "yanyuan", "");
    let adapted = null;
    let adaptedTitle = "";
    let adaptedAuthor = "";
    let adaptedUrl = "";
    try {
      const novelPayload = unwrap(
        await api.get(
          `plugin/ShortDramaBaikeScraper/novel?media_id=${encodeURIComponent(mediaId)}`,
          { ...SILENT, timeout: 2e4 }
        )
      );
      adapted = novelToAdaptedInfo(novelPayload?.data);
      if (adapted) {
        adaptedTitle = adapted.title;
        adaptedAuthor = adapted.author;
        adaptedUrl = adapted.url;
      }
    } catch {
    }
    const doubanId = String(info.douban_id || "").trim();
    const facts = info.classification_facts || {};
    const factText = (key) => String(facts[key] || "").trim();
    const runtimeMinutes = Number(info.runtime);
    const platformName = String((info.networks || [])[0]?.name || "").trim();
    return {
      director,
      writer,
      cast,
      heat_text: factText("extensions.djbaike.heat"),
      play_count_text: factText("extensions.djbaike.play_count"),
      favorites_text: factText("extensions.djbaike.favorite_count"),
      status: String(info.status || "").trim(),
      duration_minutes: Number.isFinite(runtimeMinutes) && runtimeMinutes > 0 ? runtimeMinutes : 0,
      duration_text: "",
      studio: "",
      platform: platformName,
      douban_id: doubanId,
      douban_url: doubanId ? `https://movie.douban.com/subject/${doubanId}/` : "",
      adapted_title: adaptedTitle,
      adapted_author: adaptedAuthor,
      adapted_url: adaptedUrl,
      adapted
    };
  } catch {
    return { ...EMPTY_SOURCE };
  }
}
function doubanTypeName(typeName) {
  return String(typeName || "") === "电影" ? "movie" : "tv";
}
async function fetchDoubanComments(props, doubanId, typeName = "电视剧", start = 0, count = 10) {
  const api = resolveApi(props);
  const id = String(doubanId || "").trim();
  if (!api?.get || !id) return { items: [], total: 0 };
  try {
    const payload = unwrap(
      await api.get(
        `douban/interests/${encodeURIComponent(id)}/${doubanTypeName(typeName)}?start=${start}&count=${count}`,
        { ...SILENT, timeout: 3e4 }
      )
    );
    const data = payload?.data || {};
    const rows = Array.isArray(data.items) ? data.items : [];
    return {
      items: rows.map((row) => ({
        id: String(row?.id || ""),
        comment: String(row?.comment || "").trim(),
        rating: Number(row?.rating || 0),
        votes: Number(row?.vote_count || 0),
        author: String(row?.author?.name || "").trim(),
        author_url: String(row?.author?.url || "").trim(),
        avatar: String(row?.author?.avatar || "").trim(),
        time: String(row?.create_time || "").trim()
      })),
      total: Number(data.total || rows.length) || 0
    };
  } catch {
    return { items: [], total: 0 };
  }
}
async function fetchDoubanReviews(props, doubanId, typeName = "电视剧", start = 0, count = 10) {
  const api = resolveApi(props);
  const id = String(doubanId || "").trim();
  if (!api?.get || !id) return { items: [], total: 0 };
  try {
    const payload = unwrap(
      await api.get(
        `douban/reviews/${encodeURIComponent(id)}/${doubanTypeName(typeName)}?start=${start}&count=${count}`,
        { ...SILENT, timeout: 3e4 }
      )
    );
    const data = payload?.data || {};
    const rows = Array.isArray(data.items) ? data.items : [];
    return {
      items: rows.map((row) => ({
        id: String(row?.id || ""),
        title: String(row?.title || "").trim(),
        abstract: String(row?.abstract || "").trim(),
        rating: Number(row?.rating || 0),
        useful: Number(row?.useful_count || 0),
        author: String(row?.author?.name || "").trim(),
        avatar: String(row?.author?.avatar || "").trim(),
        url: String(row?.url || "").trim(),
        time: String(row?.create_time || "").trim()
      })),
      total: Number(data.total || rows.length) || 0
    };
  } catch {
    return { items: [], total: 0 };
  }
}
async function fetchAdaptedInfo(props, mediaId) {
  if (!String(mediaId || "").trim()) return null;
  try {
    const source = await fetchWorkSource(props, mediaId);
    return source.adapted;
  } catch {
    return null;
  }
}
async function fetchAdaptedDetail(props, mediaId) {
  const id = String(mediaId || "").trim();
  const api = resolveApi(props);
  if (!id || !api?.get) return null;
  try {
    const payload = unwrap(
      await api.get(
        `plugin/ShortDramaBaikeScraper/novel?media_id=${encodeURIComponent(id)}`,
        { ...SILENT, timeout: 2e4 }
      )
    );
    return novelToAdaptedInfo(payload?.data);
  } catch {
    return null;
  }
}
async function fetchPlayUrl(props, info) {
  const api = resolveApi(props);
  if (!api?.get) return "";
  const source = String(info.mediaSource || "").trim();
  const mediaId = String(info.mediaId || "").trim();
  if (!source || !mediaId) return "";
  try {
    const query = new URLSearchParams({
      media_source: source,
      media_id: mediaId,
      title: String(info.title || ""),
      year: String(info.year || ""),
      mtype: String(info.type || "")
    });
    const found = unwrap(
      await api.get(`mediaserver/exists?${query.toString()}`, { ...SILENT, timeout: 3e4 })
    );
    const itemId = String(found?.data?.item?.id || "").trim();
    if (!itemId) return "";
    const played = unwrap(
      await api.get(`mediaserver/play/${encodeURIComponent(itemId)}`, {
        ...SILENT,
        timeout: 3e4
      })
    );
    return String(played?.data?.url || "").trim();
  } catch {
    return "";
  }
}
async function fetchConfig(props) {
  const api = resolveApi(props);
  if (!api?.get) throw new Error("缺少可用的 api 实例");
  return readData(await api.get(`${API_BASE}/config`, { ...SILENT })) || {};
}
async function saveConfig(props, config) {
  const api = resolveApi(props);
  if (!api?.put) throw new Error("缺少可用的 api 实例");
  return readData(await api.put(`${API_BASE}/config`, config, { ...SILENT })) || {};
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { fetchWorks as A, pluginSubscribeRandom as B, pluginSubscribeSearchAll as C, fetchActorCards as D, pluginUnsubscribe as E, pluginSubscribe as F, subscribeAllActor as G, fetchConfig as H, resourceSearchUrl as I, _export_sfc as _, fetchDownloadPaths as a, fetchDownloaderOptions as b, fetchActorList as c, fetchStatus as d, fetchActorDetail as e, fetchSearchSites as f, fetchAdaptedDetail as g, fetchAdaptedInfo as h, pluginSubscribeSearchNow as i, pluginSubscribeUpdate as j, fetchSubscriptions as k, fetchPlayUrl as l, fetchWorkDetail as m, fetchWorkSource as n, fetchDoubanComments as o, proxyImage as p, fetchDoubanReviews as q, retryProxyImage as r, saveConfig as s, fetchPeople as t, fetchRankWorks as u, fetchRanks as v, fetchLogs as w, addActor as x, removeActor as y, lookupSite as z };
