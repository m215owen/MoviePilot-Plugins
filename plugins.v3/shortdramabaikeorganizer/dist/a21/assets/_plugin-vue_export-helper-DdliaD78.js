const PLUGIN_ID = "ShortDramaBaikeOrganizer";
const API_ROOT = `plugin/${PLUGIN_ID}`;
function hostApi(props) {
  const injected = props?.api;
  if (injected && typeof injected.get === "function") return injected;
  const globalApi = typeof window !== "undefined" ? window.MoviePilotAPI ?? null : null;
  return globalApi && typeof globalApi.get === "function" ? globalApi : null;
}
function isAxiosResponse(value) {
  if (!value || typeof value !== "object") return false;
  const record = value;
  return typeof record.status === "number" && typeof record.statusText === "string" && !!record.headers && typeof record.headers === "object";
}
function extract(value) {
  const body = isAxiosResponse(value) ? value.data : value;
  if (body && typeof body === "object" && "success" in body) {
    const envelope = body;
    if (envelope.success === false) {
      throw new Error(envelope.message || "后端返回失败");
    }
    return envelope.data;
  }
  return body;
}
async function getJson(api, path, params) {
  const response = await api.get(`${API_ROOT}${path}`, params ? { params } : void 0);
  return extract(response);
}
async function postJson(api, path, params) {
  const response = await api.post(`${API_ROOT}${path}`, void 0, params ? { params } : void 0);
  return extract(response);
}
function pickScan(value, depth = 0) {
  if (!value || typeof value !== "object" || depth > 4) return null;
  const record = value;
  if (typeof record.state === "string" && "total" in record && Array.isArray(record.items)) {
    return record;
  }
  for (const key of ["scan", "data", "result", "payload"]) {
    const found = pickScan(record[key], depth + 1);
    if (found) return found;
  }
  return null;
}
function pickOrganize(value, depth = 0) {
  if (!value || typeof value !== "object" || depth > 4) return null;
  const record = value;
  if (typeof record.state === "string" && "total" in record && Array.isArray(record.details)) {
    return record;
  }
  for (const key of ["organize", "data", "result", "payload"]) {
    const found = pickOrganize(record[key], depth + 1);
    if (found) return found;
  }
  return null;
}
const backend = {
  status: (api) => getJson(api, "/status"),
  scan: (api) => getJson(api, "/scan"),
  scanStart: (api) => postJson(api, "/scan/start"),
  scanStop: (api) => postJson(api, "/scan/stop"),
  /**
   * 整理入口。
   *
   * ⚠️ 不传 `path` 时后端是**后台任务**（立刻返回），真正结果要轮询
   * `organizeProgress`。曾经是同步跑完全部 → 反代超时 → 前端只看到 502。
   */
  organize: (api, params = {}) => postJson(api, "/organize", params),
  /** 整理进度快照（后台整理时轮询） */
  organizeProgress: (api) => getJson(api, "/organize"),
  /** 启动后台整理全部 */
  organizeStart: (api, force = false) => postJson(api, "/organize/start", { force: force ? "1" : "0" }),
  /** 停止后台整理 */
  organizeStop: (api) => postJson(api, "/organize/stop"),
  /** 整理预演：按指定身份/目标库列出将整理哪些文件（media_id 用于从源数据取季号） */
  preview: (api, params) => getJson(api, "/preview", params),
  /**
   * 整理详情：传 `path`/`dest` 拿单剧文件级记录；都不传拿本次整理运行详情。
   */
  details: (api, params = {}) => getJson(api, "/details", params),
  /** 按关键词搜百科候选（人工指定身份用） */
  search: (api, keyword, limit = 10) => getJson(api, "/search", { keyword, limit }),
  /** 记录库：统计 + 全部剧记录（整理中 / 整理完成分开数） */
  store: (api) => getJson(api, "/store"),
  /** 手动标记 / 取消「整理完成」（value=0 取消） */
  storeComplete: (api, path, value = "1") => postJson(api, "/store/complete", { path, value }),
  /** 立即刮削（传源目录 path，或直接传目标目录 dest） */
  scrape: (api, params) => postJson(
    api,
    "/scrape",
    params
  ),
  /** 删除一条记录库记录 */
  storeDelete: (api, path) => postJson(api, "/store/delete", { path }),
  /** 清空记录库 */
  storeClear: (api) => postJson(api, "/store/clear"),
  browse: (api, path = "") => getJson(api, "/dirs/browse", { path }),
  dirOptions: (api) => getJson(api, "/dirs/options")
};

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { _export_sfc as _, pickOrganize as a, backend as b, hostApi as h, pickScan as p };
