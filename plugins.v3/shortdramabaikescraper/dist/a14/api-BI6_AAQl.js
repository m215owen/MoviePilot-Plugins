const PLUGIN_ID = "ShortDramaBaikeScraper";
const API_BASE = `plugin/${PLUGIN_ID}`;
let lastApi = null;
function resolveApi(props) {
  if (props && props.api) {
    lastApi = props.api;
    return props.api;
  }
  const globalApi = typeof window !== "undefined" ? window.MoviePilotAPI : null;
  if (globalApi) lastApi = globalApi;
  if (lastApi) return lastApi;
  throw new Error("宿主未注入 API 实例：面板需在 MoviePilot 插件页面内打开");
}
function unwrap(payload) {
  return envelopeOf(payload).data;
}
function isEnvelope(value) {
  return Boolean(
    value && typeof value === "object" && !Array.isArray(value) && "success" in value && "data" in value
  );
}
function envelopeOf(body) {
  if (isEnvelope(body)) {
    return body;
  }
  return { success: void 0, message: void 0, data: body };
}
async function getRaw(props, path, params) {
  const api = resolveApi(props);
  if (!api.get) throw new Error("宿主 API 缺少 get 方法");
  const response = await api.get(`${API_BASE}${path}`, { params, feedback: "silent" });
  if (isEnvelope(response)) return response;
  return response?.data ?? response;
}
async function get(props, path, params) {
  return unwrap(await getRaw(props, path, params));
}
async function post(props, path, params) {
  const api = resolveApi(props);
  if (!api.post) throw new Error("宿主 API 缺少 post 方法");
  const response = await api.post(`${API_BASE}${path}`, void 0, { params, feedback: "silent" });
  return unwrap(response?.data ?? response);
}
async function del(props, path, params) {
  const api = resolveApi(props);
  if (!api.delete) throw new Error("宿主 API 缺少 delete 方法");
  const response = await api.delete(`${API_BASE}${path}`, { params, feedback: "silent" });
  return unwrap(response?.data ?? response);
}
async function put(props, path, payload) {
  const api = resolveApi(props);
  if (!api.put) throw new Error("宿主 API 缺少 put 方法");
  const response = await api.put(`${API_BASE}${path}`, payload);
  if (isEnvelope(response)) return unwrap(response);
  return unwrap(response?.data ?? response);
}
async function fetchStatus(props) {
  return await get(props, "/status");
}
async function fetchBaikeList(props, params = {}) {
  return await get(props, "/baike/list", params);
}
async function deleteBaike(props, mediaId) {
  return await del(props, "/baike/del", { media_id: mediaId });
}
async function clearBaike(props) {
  return await post(props, "/baike/clear");
}
async function fetchCacheItems(props, region, limit = 100, search = "") {
  return await get(props, "/cache/items", { region, limit, search });
}
async function deleteCacheItem(props, region, key) {
  return await del(props, "/cache/del", { region, key });
}
async function clearCache(props) {
  return await post(props, "/cache/clear");
}
async function lookupRaw(props, params) {
  return getRaw(props, "/lookup", params);
}
async function fetchPerson(props, mediaId) {
  const body = await getRaw(props, "/person", { media_id: mediaId });
  const payload = envelopeOf(body);
  const data = payload.data;
  return {
    person: data && typeof data === "object" ? data : null,
    message: String(payload.message || "")
  };
}
async function fetchNovel(props, mediaId) {
  const body = await getRaw(props, "/novel", { media_id: mediaId });
  const payload = envelopeOf(body);
  const data = payload.data;
  return {
    novel: data && typeof data === "object" ? data : null,
    message: String(payload.message || "")
  };
}
function proxyImage(url) {
  const text = String(url || "").trim();
  if (!text || text.startsWith("/") || text.startsWith("data:")) return text;
  let host = "";
  try {
    host = new URL(text).hostname.toLowerCase();
  } catch {
    return text;
  }
  if (host === "doubanio.com" || host.endsWith(".doubanio.com")) {
    return `/api/v1/system/img/0?imgurl=${encodeURIComponent(text)}&cache=1`;
  }
  return text;
}
async function fetchConfig(props) {
  return await get(props, "/config");
}
async function saveConfig(props, payload) {
  return await put(props, "/config", payload);
}

export { PLUGIN_ID as P, fetchBaikeList as a, fetchCacheItems as b, clearBaike as c, deleteBaike as d, fetchStatus as e, fetchConfig as f, deleteCacheItem as g, clearCache as h, fetchNovel as i, fetchPerson as j, envelopeOf as k, lookupRaw as l, proxyImage as p, saveConfig as s };
