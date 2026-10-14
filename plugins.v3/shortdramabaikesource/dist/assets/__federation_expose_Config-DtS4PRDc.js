import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const PLUGIN_ID = "ShortDramaBaikeSource";
const API_BASE = `plugin/${PLUGIN_ID}`;
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
function unwrap(response) {
  const value = response;
  if (value && typeof value === "object" && "data" in value) {
    const inner = value.data;
    if (inner && typeof inner === "object") return inner;
  }
  return response;
}
async function getJson(api, path, params) {
  try {
    const response = await api.get(`${API_BASE}${path}`, { params });
    return unwrap(response);
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] ${path} 调用失败`, error);
    return null;
  }
}
function fetchStatus(api) {
  return getJson(api, "/status");
}
function lookupKeyword(api, keyword, year) {
  return getJson(api, "/lookup", { keyword, year: void 0 });
}
function recognizeTitle(api, options) {
  return getJson(
    api,
    "/recognize",
    options
  );
}
function fetchActor(api, options) {
  return getJson(api, "/actor", options);
}
function fetchUrls(api, options = {}) {
  return getJson(api, "/urls", {
    keyword: options.keyword || void 0,
    kind: options.kind || void 0,
    limit: options.limit ?? 50
  });
}
async function clearUrls(api, options = {}) {
  try {
    const response = await api.post(`${API_BASE}/urls/clear`, {
      keyword: options.keyword || "",
      kind: options.kind || ""
    });
    return unwrap(response);
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] 清空 URL 库失败`, error);
    return null;
  }
}
function fetchConfig(api) {
  return getJson(api, "/config");
}
async function saveConfig(api, config) {
  try {
    const response = await api.put(`${API_BASE}/config`, config);
    return unwrap(response);
  } catch (error) {
    console.warn(`[${PLUGIN_ID}] 保存配置失败`, error);
    return null;
  }
}

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "d-flex align-center mb-3" };
const _hoisted_2 = { class: "text-subtitle-2 mb-2" };
const _hoisted_3 = { class: "text-subtitle-2 mb-2" };
const _hoisted_4 = { class: "text-subtitle-2 mb-2" };
const _hoisted_5 = {
  key: 1,
  class: "text-caption sdbs-dim mb-2"
};
const _hoisted_6 = {
  class: "d-flex align-center flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_7 = { class: "text-caption sdbs-dim" };
const {onMounted,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Config",
  props: {
    initialConfig: {},
    api: {}
  },
  emits: ["save", "close", "switch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const DEFAULTS = {
      enabled: false,
      domain: "https://duanjubaike.org",
      search_in_global: true,
      timeout: 15,
      cache_ttl: 604800,
      web_index_search: true,
      web_index_backend: "auto",
      proxy: false,
      detail_facts: false,
      follow_links: true
    };
    const FALLBACK_BACKENDS = ["auto", "duckduckgo", "yandex", "google", "brave", "mojeek"];
    const local = ref({ ...DEFAULTS, ...props.initialConfig || {} });
    const loaded = ref({ ...local.value });
    const backendOptions = ref(FALLBACK_BACKENDS);
    const loading = ref(false);
    const saving = ref(false);
    const hint = ref("");
    const statusText = ref("");
    onMounted(() => {
      void loadConfig();
    });
    async function loadConfig() {
      const api = resolveApi(props);
      if (!api) return;
      loading.value = true;
      try {
        const report = await fetchConfig(api);
        if (report?.config) {
          local.value = { ...DEFAULTS, ...report.config };
          loaded.value = { ...local.value };
        }
        const options = report?.options;
        if (options?.web_index_backends?.length) backendOptions.value = options.web_index_backends;
        await loadStatus();
      } catch (error) {
        hint.value = "读取配置失败，当前显示的是默认值";
        console.warn("[ShortDramaBaikeSource] 读取配置失败", error);
      } finally {
        loading.value = false;
      }
    }
    async function loadStatus() {
      const api = resolveApi(props);
      if (!api) return;
      try {
        const report = await fetchStatus(api);
        if (!report) {
          statusText.value = "";
          return;
        }
        const index = report.web_index || {};
        const indexText = index.available ? index.enabled ? `站外索引 开（后端 ${index.backend || "auto"}）` : "站外索引 关" : "站外索引 不可用（依赖缺失）";
        const store = report.store || {};
        statusText.value = [
          `运行状态：${report.enabled ? "已启用" : "未启用"}`,
          indexText,
          `URL 库 ${store.total ?? 0} 条（作品 ${store.work ?? 0} / 演员 ${store.actor ?? 0}）`,
          `缓存 详情 ${report.cache?.detail ?? 0} 条 / 演员 ${report.cache?.actor ?? 0} 条`
        ].join("　｜　");
      } catch (error) {
        statusText.value = "";
        console.warn("[ShortDramaBaikeSource] 读取运行状态失败", error);
      }
    }
    function resetToLoaded() {
      local.value = { ...loaded.value };
      hint.value = "已还原为服务端当前配置";
    }
    async function doSave() {
      const api = resolveApi(props);
      if (!api) {
        hint.value = "拿不到宿主接口实例，无法保存";
        return;
      }
      saving.value = true;
      hint.value = "";
      try {
        const payload = {
          ...local.value,
          domain: String(local.value.domain || "").trim()
        };
        const report = await saveConfig(api, payload);
        if (report?.success) {
          if (report.config) {
            local.value = { ...DEFAULTS, ...report.config };
            loaded.value = { ...local.value };
          }
          hint.value = report.message || "配置已保存";
          await loadStatus();
          emit("save", local.value);
        } else {
          hint.value = report?.message || "保存失败";
        }
      } catch (error) {
        hint.value = "保存失败（请看宿主日志）";
        console.warn("[ShortDramaBaikeSource] 保存配置失败", error);
      } finally {
        saving.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_progress_linear = _resolveComponent("v-progress-linear");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createBlock(_component_v_card, {
        variant: "outlined",
        class: "pa-4"
      }, {
        default: _withCtx(() => [
          _createElementVNode("div", _hoisted_1, [
            _createVNode(_component_v_icon, {
              icon: "mdi-television-classic",
              class: "mr-2"
            }),
            _cache[11] || (_cache[11] = _createElementVNode("h3", { class: "ma-0" }, "短剧百科数据源 · 设置", -1)),
            _createVNode(_component_v_spacer),
            _createVNode(_component_v_btn, {
              icon: "mdi-close",
              variant: "text",
              size: "small",
              title: "关闭",
              onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
            })
          ]),
          _createVNode(_component_v_alert, {
            type: "info",
            variant: "tonal",
            density: "compact",
            class: "mb-3"
          }, {
            default: _withCtx(() => [..._cache[12] || (_cache[12] = [
              _createTextVNode(" 本插件把 ", -1),
              _createElementVNode("b", null, "duanjubaike.org", -1),
              _createTextVNode(" 注册成 MoviePilot 的一等媒体数据源（与 TMDB / 豆瓣同级）， 补齐 TMDB、豆瓣上没有条目的短剧。站内检索被 Cloudflare 挡住、目录页已弃用， 片名与演员名 → ID 都走", -1),
              _createElementVNode("b", null, "站外索引", -1),
              _createTextVNode("（搜索引擎的 ", -1),
              _createElementVNode("code", null, "site:", -1),
              _createTextVNode(" 限定检索）， 因此这里没有「抓取配额」类配置 —— 正常使用不会触发站点风控。 ", -1)
            ])]),
            _: 1
          }),
          loading.value ? (_openBlock(), _createBlock(_component_v_progress_linear, {
            key: 0,
            indeterminate: "",
            color: "primary",
            class: "mb-3"
          })) : _createCommentVNode("", true),
          _createVNode(_component_v_row, { dense: "" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: local.value.enabled,
                    "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => local.value.enabled = $event),
                    label: "启用插件",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: local.value.search_in_global,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => local.value.search_in_global = $event),
                    label: "参与宿主全局检索",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: local.value.web_index_search,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => local.value.web_index_search = $event),
                    label: "站外索引检索",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: local.value.detail_facts,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => local.value.detail_facts = $event),
                    label: "详情页摘要行",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode(_component_v_divider, { class: "my-3" }),
          _createElementVNode("div", _hoisted_2, [
            _createVNode(_component_v_icon, {
              icon: "mdi-earth",
              size: "18",
              class: "mr-1"
            }),
            _cache[13] || (_cache[13] = _createTextVNode(" 站点与请求 ", -1))
          ]),
          _createVNode(_component_v_row, { dense: "" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "12",
                md: "6"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_text_field, {
                    modelValue: local.value.domain,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => local.value.domain = $event),
                    label: "站点域名",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    placeholder: "https://duanjubaike.org"
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_text_field, {
                    modelValue: local.value.timeout,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => local.value.timeout = $event),
                    modelModifiers: { number: true },
                    label: "请求超时",
                    suffix: "秒",
                    type: "number",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_text_field, {
                    modelValue: local.value.cache_ttl,
                    "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => local.value.cache_ttl = $event),
                    modelModifiers: { number: true },
                    label: "详情缓存",
                    suffix: "秒",
                    type: "number",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _cache[18] || (_cache[18] = _createElementVNode("div", { class: "text-caption sdbs-dim mt-1" }, [
            _createTextVNode(" 详情页内容基本不变，缓存默认 7 天。插件"),
            _createElementVNode("b", null, "没有后台任务"),
            _createTextVNode("：缓存只在被查询时按需重建。 ")
          ], -1)),
          _createVNode(_component_v_divider, { class: "my-3" }),
          _createElementVNode("div", _hoisted_3, [
            _createVNode(_component_v_icon, {
              icon: "mdi-web-search",
              size: "18",
              class: "mr-1"
            }),
            _cache[14] || (_cache[14] = _createTextVNode(" 站外索引（片名 / 演员名 → 站点 ID 的唯一通道） ", -1))
          ]),
          _createVNode(_component_v_row, { dense: "" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_select, {
                    modelValue: local.value.web_index_backend,
                    "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => local.value.web_index_backend = $event),
                    items: backendOptions.value,
                    label: "检索后端",
                    density: "compact",
                    variant: "outlined",
                    "hide-details": ""
                  }, null, 8, ["modelValue", "items"])
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: local.value.proxy,
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => local.value.proxy = $event),
                    label: "使用系统代理",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _cache[19] || (_cache[19] = _createElementVNode("div", { class: "text-caption sdbs-dim mt-1" }, [
            _createTextVNode(" 实测 "),
            _createElementVNode("code", null, "auto"),
            _createTextVNode(" 与 "),
            _createElementVNode("code", null, "yandex"),
            _createTextVNode(" 有结果；单次检索约 10 秒，相邻两次至少隔 3 秒。 关掉它之后面板搜索框会直接不可用（没有第二条发现通道），按姓名找演员也一样。 ")
          ], -1)),
          _createVNode(_component_v_divider, { class: "my-3" }),
          _createElementVNode("div", _hoisted_4, [
            _createVNode(_component_v_icon, {
              icon: "mdi-database-outline",
              size: "18",
              class: "mr-1"
            }),
            _cache[15] || (_cache[15] = _createTextVNode(" URL 库（插件自有数据库） ", -1))
          ]),
          _createVNode(_component_v_row, { dense: "" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "12",
                sm: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_switch, {
                    modelValue: local.value.follow_links,
                    "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => local.value.follow_links = $event),
                    label: "顺带沉淀页面里的链接",
                    color: "primary",
                    "hide-details": ""
                  }, null, 8, ["modelValue"])
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _cache[20] || (_cache[20] = _createElementVNode("div", { class: "text-caption sdbs-dim mt-1" }, [
            _createTextVNode(" 库里只存「关键词 → 页面 URL」，"),
            _createElementVNode("b", null, "不存解析结果"),
            _createTextVNode("：站点内容随时在变，页面永远实时解析。 取数优先查库（命中即零引擎请求），库里没有才检索一次并把作品与演员两类 URL 一起入库。 开启本项后，解析作品页时顺带把演员链接写进库、解析演员页时顺带把作品链接写进库 —— 所以搜过一部剧，之后再搜它里面的演员名也是零引擎请求。 PostgreSQL 实例下这些表落在宿主库的独立 schema，SQLite 实例下落在插件数据目录的 "),
            _createElementVNode("code", null, "plugin.db"),
            _createTextVNode("，两种情况下都跟着宿主一起备份。 ")
          ], -1)),
          _createVNode(_component_v_divider, { class: "my-3" }),
          statusText.value ? (_openBlock(), _createElementBlock("div", _hoisted_5, [
            _createVNode(_component_v_icon, {
              icon: "mdi-information-outline",
              size: "14",
              class: "mr-1"
            }),
            _createTextVNode(_toDisplayString(statusText.value), 1)
          ])) : _createCommentVNode("", true),
          _createElementVNode("div", _hoisted_6, [
            _createVNode(_component_v_btn, {
              color: "primary",
              variant: "tonal",
              loading: saving.value,
              "prepend-icon": "mdi-content-save-outline",
              onClick: doSave
            }, {
              default: _withCtx(() => [..._cache[16] || (_cache[16] = [
                _createTextVNode(" 保存 ", -1)
              ])]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_v_btn, {
              variant: "text",
              disabled: saving.value,
              onClick: resetToLoaded
            }, {
              default: _withCtx(() => [..._cache[17] || (_cache[17] = [
                _createTextVNode("还原", -1)
              ])]),
              _: 1
            }, 8, ["disabled"]),
            _createVNode(_component_v_spacer),
            _createElementVNode("span", _hoisted_7, _toDisplayString(hint.value), 1)
          ])
        ]),
        _: 1
      });
    };
  }
});

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-332c2ac0"]]);

export { _export_sfc as _, fetchConfig as a, recognizeTitle as b, fetchActor as c, fetchUrls as d, Config as default, clearUrls as e, fetchStatus as f, lookupKeyword as l, proxyImage as p, resolveApi as r, saveConfig as s };
