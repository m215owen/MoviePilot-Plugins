import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { f as fetchSearchSites, a as fetchDownloadPaths, b as fetchDownloaderOptions, c as fetchActorList, s as saveConfig, _ as _export_sfc } from './_plugin-vue_export-helper-Clm0RiNn.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,mergeProps:_mergeProps,createBlock:_createBlock,Fragment:_Fragment} = await importShared('vue');

const _hoisted_1 = { class: "sdas-root pa-2" };
const _hoisted_2 = { class: "d-flex align-center mb-3" };
const _hoisted_3 = { class: "text-subtitle-2 mb-2" };
const _hoisted_4 = { class: "text-caption sdas-dim ml-2" };
const _hoisted_5 = { class: "sdas-block-head" };
const _hoisted_6 = { class: "text-subtitle-2 mb-2" };
const _hoisted_7 = {
  key: 0,
  class: "text-caption text-warning mt-1"
};
const _hoisted_8 = { class: "text-subtitle-2 mb-2" };
const _hoisted_9 = {
  key: 0,
  class: "text-caption sdas-dim ml-2"
};
const _hoisted_10 = {
  key: 0,
  class: "text-caption text-warning mt-1"
};
const _hoisted_11 = {
  key: 1,
  class: "text-caption sdas-dim mt-1"
};
const _hoisted_12 = { class: "sdas-mono" };
const _hoisted_13 = {
  key: 0,
  class: "ml-1"
};
const _hoisted_14 = {
  key: 1,
  class: "ml-1"
};
const _hoisted_15 = { class: "text-subtitle-2 mb-2" };
const _hoisted_16 = {
  class: "d-flex align-center px-4 pb-2",
  style: { "gap": "8px" }
};
const _hoisted_17 = { class: "text-caption sdas-dim" };
const _hoisted_18 = {
  key: 1,
  class: "text-caption sdas-dim"
};
const _hoisted_19 = {
  key: 2,
  class: "text-caption sdas-dim"
};
const _hoisted_20 = { class: "text-subtitle-2 mb-2" };
const _hoisted_21 = { class: "text-subtitle-2 mb-2" };
const _hoisted_22 = { class: "text-subtitle-2 mb-2" };
const _hoisted_23 = { class: "text-subtitle-2 mb-2" };
const _hoisted_24 = { class: "sdas-block-head" };
const _hoisted_25 = { class: "text-subtitle-2 mb-2" };
const _hoisted_26 = { class: "text-subtitle-2 mb-2" };
const _hoisted_27 = {
  class: "d-flex align-center px-4 pb-2",
  style: { "gap": "8px" }
};
const _hoisted_28 = { class: "text-caption sdas-dim" };
const _hoisted_29 = {
  key: 6,
  class: "text-caption sdas-dim"
};
const _hoisted_30 = {
  key: 7,
  class: "text-caption sdas-dim"
};
const _hoisted_31 = {
  class: "d-flex align-center",
  style: { "gap": "8px" }
};
const {computed,onMounted,ref,watch} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Config",
  props: {
    api: {},
    initialConfig: {}
  },
  emits: ["save", "close", "switch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    function defaults() {
      return {
        enabled: false,
        onlyonce: false,
        actors: "",
        interval_hours: 12,
        retry_minutes: 20,
        notify: true,
        sidebar_nav: true,
        search_sites: "",
        subscribe_downloader: "",
        subscribe_sites: "",
        subscribe_save_path: "",
        subscribe_mode: "follow",
        subscribe_prefer: "seeders",
        auto_subscribe: false,
        auto_subscribe_scope: "new",
        auto_subscribe_max_per_run: 5,
        auto_subscribe_skip_library: true,
        subscribe_engine: "host",
        self_interval_hours: 6,
        self_max_per_run: 5,
        self_max_pages: 3
      };
    }
    const scopeOptions = [
      { title: "只订新作品（推荐）", value: "new" },
      { title: "全部作品（含历史）", value: "all" }
    ];
    const engineOptions = [
      { title: "宿主订阅系统（默认）", value: "host" },
      { title: "自建订阅搜索（全分类补搜）", value: "self" }
    ];
    const local = ref(defaults());
    const saving = ref(false);
    const saveError = ref("");
    const siteOptions = ref([]);
    const siteLoadFailed = ref(false);
    const siteLoading = ref(true);
    onMounted(async () => {
      try {
        siteOptions.value = await fetchSearchSites(props);
      } catch {
        siteLoadFailed.value = true;
      } finally {
        siteLoading.value = false;
      }
    });
    const selectedSiteIds = computed(
      () => String(local.value.search_sites || "").split(/[,，;；\s]+/).map((item) => Number(item)).filter((id) => Number.isFinite(id) && id > 0)
    );
    const selectedSiteModels = computed({
      get: () => selectedSiteIds.value,
      set: (ids) => {
        const unique = Array.from(new Set(ids.filter((id) => Number.isFinite(id) && id > 0)));
        local.value.search_sites = unique.join(",");
      }
    });
    const sortedSiteOptions = computed(() => {
      const picked = new Set(selectedSiteIds.value);
      const selected = siteOptions.value.filter((site) => picked.has(site.id));
      const rest = siteOptions.value.filter((site) => !picked.has(site.id));
      return [...selected, ...rest];
    });
    function selectAllSites() {
      local.value.search_sites = siteOptions.value.map((site) => site.id).join(",");
    }
    function parseSiteIds(value) {
      return String(value || "").split(/[,，;；\s]+/).map((item) => Number(item)).filter((id) => Number.isFinite(id) && id > 0);
    }
    const subscribeSiteIds = computed(() => parseSiteIds(local.value.subscribe_sites));
    const subscribeSiteModels = computed({
      get: () => subscribeSiteIds.value,
      set: (ids) => {
        const unique = Array.from(new Set(ids.filter((id) => Number.isFinite(id) && id > 0)));
        local.value.subscribe_sites = unique.join(",");
      }
    });
    const sortedSubscribeSiteOptions = computed(() => {
      const picked = new Set(subscribeSiteIds.value);
      const selected = siteOptions.value.filter((site) => picked.has(site.id));
      const rest = siteOptions.value.filter((site) => !picked.has(site.id));
      return [...selected, ...rest];
    });
    function selectAllSubscribeSites() {
      local.value.subscribe_sites = siteOptions.value.map((site) => site.id).join(",");
    }
    const downloadPaths = ref([]);
    const downloadPathLoading = ref(true);
    const downloadPathItems = computed(
      () => downloadPaths.value.map((item) => ({
        title: item.name || item.download_path || item.save_path,
        subtitle: item.download_path || item.save_path,
        value: item.save_path,
        path: item.download_path || item.save_path,
        storage: item.storage
      }))
    );
    function normalizePath(value) {
      const text = String(value || "").trim().replace(/\\/g, "/");
      if (!text) return "";
      return text.replace(/\/{2,}/g, "/").replace(/\/+$/, "");
    }
    function unwrapPathValue(value) {
      if (value && typeof value === "object") {
        const raw = value;
        return String(raw.value ?? raw.save_path ?? "").trim();
      }
      const text = String(value ?? "").trim();
      return /^\[object [A-Za-z]+\]$/.test(text) ? "" : text;
    }
    const savePathModel = computed({
      get: () => unwrapPathValue(local.value.subscribe_save_path),
      set: (value) => {
        local.value.subscribe_save_path = unwrapPathValue(value);
      }
    });
    const matchedPathOption = computed(() => {
      const key = normalizePath(savePathModel.value);
      if (!key) return null;
      return downloadPathItems.value.find((item) => normalizePath(item.value) === key) || null;
    });
    const savePathInList = computed(() => Boolean(matchedPathOption.value));
    const savePathAligned = computed(() => {
      const option = matchedPathOption.value;
      if (!option) return "";
      const raw = savePathModel.value;
      return option.value && option.value !== raw ? option.value : "";
    });
    const effectiveSavePath = computed(
      () => matchedPathOption.value?.value || savePathModel.value
    );
    function reconcileSavePath() {
      const raw = savePathModel.value;
      if (!raw) return;
      if (matchedPathOption.value) return;
      const byName = downloadPathItems.value.find(
        (item) => item.title && normalizePath(item.title) === normalizePath(raw)
      );
      if (byName && byName.value) local.value.subscribe_save_path = byName.value;
    }
    onMounted(async () => {
      try {
        downloadPaths.value = await fetchDownloadPaths(props);
      } finally {
        downloadPathLoading.value = false;
      }
    });
    let reconciled = false;
    watch(
      [() => downloadPathItems.value.length, () => savePathModel.value],
      () => {
        if (reconciled || !downloadPathItems.value.length) return;
        reconciled = true;
        reconcileSavePath();
      }
    );
    const downloaderOptions = ref([]);
    const downloaderLoading = ref(true);
    const downloaderNames = computed(() => downloaderOptions.value.map((item) => item.name));
    onMounted(async () => {
      try {
        downloaderOptions.value = await fetchDownloaderOptions(props);
      } finally {
        downloaderLoading.value = false;
      }
    });
    onMounted(() => {
      const incoming = props.initialConfig || {};
      local.value = { ...defaults(), ...incoming };
      local.value.subscribe_save_path = unwrapPathValue(local.value.subscribe_save_path);
      fetchActorList(props).then((rows) => {
        actorRows.value = rows;
      }).catch(() => {
      });
    });
    const actorItems = computed(
      () => String(local.value.actors || "").split(/[,，;；\n\r]+/).map((item) => item.trim()).filter(Boolean)
    );
    const actorRows = ref([]);
    const actorIdToName = computed(() => {
      const map = {};
      for (const row of actorRows.value) {
        if (row.key && row.name) map[row.key] = row.name;
      }
      return map;
    });
    const actorNameToIds = computed(() => {
      const map = {};
      for (const row of actorRows.value) {
        if (!row.key || !row.name) continue;
        (map[row.name] ||= []).push(row.key);
      }
      return map;
    });
    const ACTOR_ID_RE = /^(?:yanyuan|daoyan|bianju):\d+$/;
    const actorsDisplay = computed({
      get() {
        const idToName = actorIdToName.value;
        const nameCounts = {};
        for (const row of actorRows.value) {
          if (row.name) nameCounts[row.name] = (nameCounts[row.name] || 0) + 1;
        }
        return actorItems.value.map((item) => {
          const name = idToName[item];
          if (!name) return item;
          return (nameCounts[name] || 0) > 1 ? `${name}｜${item}` : name;
        }).join("，");
      },
      set(value) {
        local.value.actors = String(value || "").split(/[,，;；\n\r]+/).map((line) => {
          const text = line.trim();
          if (!text) return "";
          const mixed = text.match(/^(.*)｜((?:yanyuan|daoyan|bianju):\d+)$/);
          if (mixed) return mixed[2];
          if (ACTOR_ID_RE.test(text)) return text;
          const ids = actorNameToIds.value[text];
          return ids && ids.length === 1 ? ids[0] : text;
        }).filter(Boolean).join(",");
      }
    });
    async function onSave() {
      saving.value = true;
      saveError.value = "";
      try {
        const cleaned = String(local.value.subscribe_downloader || "").trim();
        const cleanedPath = matchedPathOption.value ? matchedPathOption.value.value : unwrapPathValue(local.value.subscribe_save_path);
        const rawMax = Number(local.value.auto_subscribe_max_per_run);
        const maxPerRun = Number.isFinite(rawMax) && rawMax > 0 ? Math.min(50, Math.floor(rawMax)) : 5;
        const rawMode = String(local.value.subscribe_mode || "");
        const mode = rawMode === "normal" || rawMode === "best" ? rawMode : "follow";
        const rawPrefer = String(local.value.subscribe_prefer || "");
        const prefer = rawPrefer === "size_desc" || rawPrefer === "size_asc" ? rawPrefer : "seeders";
        const payload = {
          ...local.value,
          subscribe_downloader: cleaned,
          subscribe_save_path: cleanedPath,
          subscribe_mode: mode,
          subscribe_prefer: prefer,
          auto_subscribe_max_per_run: maxPerRun
        };
        await saveConfig(props, payload);
        emit("save", payload);
      } catch (err) {
        saveError.value = `保存失败：${err instanceof Error ? err.message : err}`;
      } finally {
        saving.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_textarea = _resolveComponent("v-textarea");
      const _component_v_combobox = _resolveComponent("v-combobox");
      const _component_v_list_item = _resolveComponent("v-list-item");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-4"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_icon, {
                icon: "mdi-movie-open-star-outline",
                class: "mr-2"
              }),
              _cache[25] || (_cache[25] = _createElementVNode("h3", { class: "ma-0" }, "短剧演员 · 设置", -1)),
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
              default: _withCtx(() => [..._cache[26] || (_cache[26] = [
                _createTextVNode(" 作品全部来自", -1),
                _createElementVNode("b", null, "短剧百科", -1),
                _createTextVNode("（duanjubaike.net，已作为媒体数据源接入系统）。 在作品墙点「订阅」，走的就是", -1),
                _createElementVNode("b", null, "MoviePilot 自己的订阅系统", -1),
                _createTextVNode(" —— 搜索、下载、整理全部由系统接管。 ", -1)
              ])]),
              _: 1
            }),
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
                      modelValue: local.value.sidebar_nav,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => local.value.sidebar_nav = $event),
                      label: "侧栏显示「短剧演员」入口",
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
                      modelValue: local.value.notify,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => local.value.notify = $event),
                      label: "新作品发系统通知",
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
                      modelValue: local.value.onlyonce,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => local.value.onlyonce = $event),
                      label: "保存后立即刷新一次",
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
            _createElementVNode("div", _hoisted_3, [
              _createVNode(_component_v_icon, {
                icon: "mdi-account-multiple-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[27] || (_cache[27] = _createTextVNode(" 关注的演员 ", -1)),
              _createElementVNode("span", _hoisted_4, "共 " + _toDisplayString(actorItems.value.length) + " 位", 1)
            ]),
            _createVNode(_component_v_textarea, {
              modelValue: actorsDisplay.value,
              "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => actorsDisplay.value = $event),
              variant: "outlined",
              density: "compact",
              rows: "2",
              "auto-grow": "",
              "hide-details": "",
              placeholder: "人名用逗号分隔。例：徐艺真，孙樾，王小亿"
            }, null, 8, ["modelValue"]),
            _cache[63] || (_cache[63] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, " 单个添加也可以在作品墙右上角「添加演员」里填名字（会先在短剧百科里核对）。 ", -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_5, [
              _createVNode(_component_v_icon, {
                icon: "mdi-send-check-outline",
                size: "20",
                class: "mr-1"
              }),
              _cache[28] || (_cache[28] = _createElementVNode("span", { class: "sdas-block-title" }, "订阅", -1)),
              _cache[29] || (_cache[29] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, " 投递 → 方式 → 自动化；作品墙「订阅」、订阅全部作品、自动订阅三处共用 ", -1))
            ]),
            _createElementVNode("div", _hoisted_6, [
              _createVNode(_component_v_icon, {
                icon: "mdi-download-network-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[30] || (_cache[30] = _createTextVNode(" 订阅下载器 ", -1)),
              _cache[31] || (_cache[31] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, "作品墙提交订阅时使用的下载客户端", -1))
            ]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_combobox, {
                      modelValue: local.value.subscribe_downloader,
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => local.value.subscribe_downloader = $event),
                      items: downloaderNames.value,
                      loading: downloaderLoading.value,
                      label: "下载器",
                      variant: "outlined",
                      density: "compact",
                      clearable: "",
                      "hide-details": "",
                      placeholder: "留空 = 跟随系统默认"
                    }, null, 8, ["modelValue", "items", "loading"]),
                    local.value.subscribe_downloader && !downloaderNames.value.includes(local.value.subscribe_downloader) ? (_openBlock(), _createElementBlock("div", _hoisted_7, " 宿主没有名为「" + _toDisplayString(local.value.subscribe_downloader) + "」的下载器，提交时会被忽略 ", 1)) : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[64] || (_cache[64] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, [
              _createTextVNode(" 指定下载器后，作品墙点「订阅」会按此下载器"),
              _createElementVNode("b", null, "直接提交"),
              _createTextVNode("（系统订阅弹窗没有下载器选项，带不上偏好）； 留空则保持原样，弹出系统订阅对话框。下载客户端在宿主「设定 → 下载器」里维护。 ")
            ], -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_8, [
              _createVNode(_component_v_icon, {
                icon: "mdi-folder-download-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[32] || (_cache[32] = _createTextVNode(" 订阅下载目录 ", -1)),
              _cache[33] || (_cache[33] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, "订阅的保存目录（含自动订阅 / 订阅全部作品）", -1))
            ]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "8"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_combobox, {
                      modelValue: savePathModel.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => savePathModel.value = $event),
                      items: downloadPathItems.value,
                      "item-title": "title",
                      "item-value": "value",
                      "return-object": false,
                      loading: downloadPathLoading.value,
                      label: "下载目录",
                      variant: "outlined",
                      density: "compact",
                      clearable: "",
                      "hide-details": "",
                      placeholder: "留空 = 跟随宿主订阅默认"
                    }, {
                      item: _withCtx(({ props: itemProps, item }) => [
                        _createVNode(_component_v_list_item, _mergeProps(itemProps, {
                          subtitle: item.raw.path
                        }), {
                          title: _withCtx(() => [
                            _createElementVNode("span", null, _toDisplayString(item.raw.title), 1),
                            item.raw.storage !== "local" ? (_openBlock(), _createElementBlock("span", _hoisted_9, _toDisplayString(item.raw.storage), 1)) : _createCommentVNode("", true)
                          ]),
                          _: 2
                        }, 1040, ["subtitle"])
                      ]),
                      _: 1
                    }, 8, ["modelValue", "items", "loading"]),
                    savePathModel.value && !savePathInList.value ? (_openBlock(), _createElementBlock("div", _hoisted_10, " 这个路径不是宿主登记的下载目录 —— 宿主保存时会退回默认目录。 请从列表里选一个（或先去宿主「设定 → 目录」把该目录加进下载目录） ")) : savePathInList.value ? (_openBlock(), _createElementBlock("div", _hoisted_11, [
                      _cache[34] || (_cache[34] = _createTextVNode(" 实际提交的路径：", -1)),
                      _createElementVNode("span", _hoisted_12, _toDisplayString(effectiveSavePath.value), 1),
                      savePathAligned.value ? (_openBlock(), _createElementBlock("span", _hoisted_13, "（已按宿主登记值对齐）")) : (_openBlock(), _createElementBlock("span", _hoisted_14, "（与宿主登记值一致）"))
                    ])) : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[65] || (_cache[65] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, " 目录来自宿主「设定 → 目录」里的下载目录。宿主要求保存目录**精确匹配**某个下载目录根 （子目录不算），所以这里只列根目录；留空则跟随宿主订阅默认。下载器是远端存储时， 值可能是 `存储:路径` 形式的 URI，原样提交即可。 ", -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_15, [
              _createVNode(_component_v_icon, {
                icon: "mdi-web-plus",
                size: "18",
                class: "mr-1"
              }),
              _cache[35] || (_cache[35] = _createTextVNode(" 订阅站点 ", -1)),
              _cache[36] || (_cache[36] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, " 自动订阅 / 订阅全部作品只在勾选的站点里搜；不勾 = 走系统默认 ", -1))
            ]),
            siteOptions.value.length ? (_openBlock(), _createBlock(_component_v_select, {
              key: 0,
              modelValue: subscribeSiteModels.value,
              "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => subscribeSiteModels.value = $event),
              items: sortedSubscribeSiteOptions.value,
              "item-title": "name",
              "item-value": "id",
              label: "订阅站点",
              multiple: "",
              chips: "",
              "closable-chips": "",
              variant: "outlined",
              density: "compact",
              "hide-details": "",
              placeholder: "不选 = 走系统默认"
            }, {
              "prepend-item": _withCtx(() => [
                _createElementVNode("div", _hoisted_16, [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "tonal",
                    color: "primary",
                    onClick: selectAllSubscribeSites
                  }, {
                    default: _withCtx(() => [..._cache[37] || (_cache[37] = [
                      _createTextVNode(" 全选 ", -1)
                    ])]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "tonal",
                    onClick: _cache[8] || (_cache[8] = ($event) => subscribeSiteModels.value = [])
                  }, {
                    default: _withCtx(() => [..._cache[38] || (_cache[38] = [
                      _createTextVNode("清空", -1)
                    ])]),
                    _: 1
                  }),
                  _createElementVNode("span", _hoisted_17, " 已选 " + _toDisplayString(subscribeSiteIds.value.length) + " / " + _toDisplayString(siteOptions.value.length), 1)
                ])
              ]),
              _: 1
            }, 8, ["modelValue", "items"])) : siteLoading.value ? (_openBlock(), _createElementBlock("div", _hoisted_18, "正在加载站点列表…")) : (_openBlock(), _createElementBlock("div", _hoisted_19, " 当前没有启用中的站点 —— 订阅会直接走系统默认站点。 ")),
            _cache[66] || (_cache[66] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, [
              _createTextVNode(" 与上面的「资源搜索站点」是两件事：那一项只管作品墙点「搜索」跳转，这一项管"),
              _createElementVNode("b", null, "提交订阅"),
              _createTextVNode(" （自动订阅、订阅全部作品，以及作品墙点「订阅」时的直连提交）。 ")
            ], -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_20, [
              _createVNode(_component_v_icon, {
                icon: "mdi-swap-horizontal-bold",
                size: "18",
                class: "mr-1"
              }),
              _cache[39] || (_cache[39] = _createTextVNode(" 订阅方式 ", -1)),
              _cache[40] || (_cache[40] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, "投递到哪已经定了，这里只决定「有资源就下」还是「洗版」", -1))
            ]),
            _createVNode(_component_v_btn_toggle, {
              modelValue: local.value.subscribe_mode,
              "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => local.value.subscribe_mode = $event),
              mandatory: "",
              divided: "",
              density: "compact",
              variant: "outlined",
              color: "primary"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_btn, {
                  value: "follow",
                  size: "small"
                }, {
                  default: _withCtx(() => [..._cache[41] || (_cache[41] = [
                    _createTextVNode("跟随宿主设置", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  value: "normal",
                  size: "small"
                }, {
                  default: _withCtx(() => [..._cache[42] || (_cache[42] = [
                    _createTextVNode("普通订阅", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  value: "best",
                  size: "small"
                }, {
                  default: _withCtx(() => [..._cache[43] || (_cache[43] = [
                    _createTextVNode("洗版订阅", -1)
                  ])]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["modelValue"]),
            _cache[67] || (_cache[67] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, [
              _createTextVNode(" 宿主订阅的「洗版」开关就是 `Subscribe.best_version`：普通订阅 = 有资源就下； 洗版订阅 = 持续比对画质、遇到更好的版本再替换。 "),
              _createElementVNode("b", null, "跟随宿主设置"),
              _createTextVNode(" = 不传值，按宿主「设定 → 订阅」里电视剧的洗版开关走（默认）； 这里显式选普通 / 洗版会覆盖宿主的默认。作品墙点「订阅」、自动订阅、订阅全部作品三处共用。 ")
            ], -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_21, [
              _createVNode(_component_v_icon, {
                icon: "mdi-sort-descending",
                size: "18",
                class: "mr-1"
              }),
              _cache[44] || (_cache[44] = _createTextVNode(" 优选条件 ", -1)),
              _cache[45] || (_cache[45] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, "同一部剧搜到多条资源时，挑哪条下载", -1))
            ]),
            _createVNode(_component_v_btn_toggle, {
              modelValue: local.value.subscribe_prefer,
              "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => local.value.subscribe_prefer = $event),
              mandatory: "",
              divided: "",
              density: "compact",
              variant: "outlined",
              color: "primary"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_btn, {
                  value: "seeders",
                  size: "small"
                }, {
                  default: _withCtx(() => [..._cache[46] || (_cache[46] = [
                    _createTextVNode("按做种数", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  value: "size_desc",
                  size: "small"
                }, {
                  default: _withCtx(() => [..._cache[47] || (_cache[47] = [
                    _createTextVNode("体积最大", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  value: "size_asc",
                  size: "small"
                }, {
                  default: _withCtx(() => [..._cache[48] || (_cache[48] = [
                    _createTextVNode("体积最小", -1)
                  ])]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["modelValue"]),
            _cache[68] || (_cache[68] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, [
              _createTextVNode(" 默认"),
              _createElementVNode("b", null, "按做种数"),
              _createTextVNode("（越多越稳）；"),
              _createElementVNode("b", null, "体积最大"),
              _createTextVNode(" = 短剧通常是整季合集，更大一般更全； "),
              _createElementVNode("b", null, "体积最小"),
              _createTextVNode(" = 挑最省流量的那条。订阅搜索、订阅全部作品、自动订阅共用。 ")
            ], -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_22, [
              _createVNode(_component_v_icon, {
                icon: "mdi-bell-plus-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[49] || (_cache[49] = _createTextVNode(" 自动订阅演员作品 ", -1)),
              _cache[50] || (_cache[50] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, "发现到符合条件的新作品，直接交给宿主订阅系统", -1))
            ]),
            _createVNode(_component_v_switch, {
              modelValue: local.value.auto_subscribe,
              "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => local.value.auto_subscribe = $event),
              color: "primary",
              density: "compact",
              "hide-details": "",
              inset: "",
              label: "打开自动订阅"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_row, {
              dense: "",
              class: "mt-1"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_select, {
                      modelValue: local.value.auto_subscribe_scope,
                      "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => local.value.auto_subscribe_scope = $event),
                      items: scopeOptions,
                      "item-title": "title",
                      "item-value": "value",
                      label: "订阅范围",
                      variant: "outlined",
                      density: "compact",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.value.auto_subscribe_max_per_run,
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => local.value.auto_subscribe_max_per_run = $event),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      max: "50",
                      label: "单轮最多订阅（部）",
                      variant: "outlined",
                      density: "compact",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_switch, {
              modelValue: local.value.auto_subscribe_skip_library,
              "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => local.value.auto_subscribe_skip_library = $event),
              color: "primary",
              density: "compact",
              "hide-details": "",
              inset: "",
              class: "mt-1",
              label: "已在媒体库的作品跳过"
            }, null, 8, ["modelValue"]),
            _cache[69] || (_cache[69] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, [
              _createTextVNode(" 订阅走宿主订阅系统（与作品墙点「订阅」同一条链路），搜索 / 下载 / 整理都由宿主接手； 集数按作品卡上的集数提交，下载器沿用上面「订阅下载器」。 "),
              _createElementVNode("b", null, "只订新作品"),
              _createTextVNode("：只订最近 7 天内上映（按作品卡上的首播 / 上映日期）的作品，与作品墙的「新作品」同口径； "),
              _createElementVNode("b", null, "全部作品"),
              _createTextVNode("：连历史作品一起补订，按「单轮最多订阅」逐轮推进。 ")
            ], -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_23, [
              _createVNode(_component_v_icon, {
                icon: "mdi-engine-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[51] || (_cache[51] = _createTextVNode(" 订阅引擎 ", -1))
            ]),
            _createVNode(_component_v_select, {
              modelValue: local.value.subscribe_engine,
              "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => local.value.subscribe_engine = $event),
              items: engineOptions,
              "item-title": "title",
              "item-value": "value",
              label: "搜索下载走哪条链路",
              variant: "outlined",
              density: "compact",
              "hide-details": ""
            }, null, 8, ["modelValue"]),
            _cache[70] || (_cache[70] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, [
              _createElementVNode("b", null, "宿主订阅系统"),
              _createTextVNode("：订阅交给宿主，搜索按媒体类型带站点分类参数 —— 个别站点把短剧挂在电影分类时会永远搜不到； "),
              _createElementVNode("b", null, "自建订阅搜索"),
              _createTextVNode("：插件自己就是订阅系统 —— 「订阅」记在插件自己的清单里（作品墙左侧面板可见）， **不提交宿主订阅系统**；搜索时全分类一起搜（电影 + 电视剧 + 短剧），按演员名 / 集数 / 年份消歧后直接提交下载， 下载 / 整理 / 通知仍归宿主。两种引擎自动互斥，只跑选中的那条。 ")
            ], -1)),
            local.value.subscribe_engine === "self" ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
              _createVNode(_component_v_row, {
                dense: "",
                class: "mt-1"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_col, {
                    cols: "12",
                    sm: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: local.value.self_interval_hours,
                        "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => local.value.self_interval_hours = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        min: "1",
                        label: "搜索间隔（小时）",
                        variant: "outlined",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    sm: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: local.value.self_max_per_run,
                        "onUpdate:modelValue": _cache[18] || (_cache[18] = ($event) => local.value.self_max_per_run = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        min: "1",
                        max: "30",
                        label: "单轮最多搜索（部）",
                        variant: "outlined",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    sm: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: local.value.self_max_pages,
                        "onUpdate:modelValue": _cache[19] || (_cache[19] = ($event) => local.value.self_max_pages = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        min: "1",
                        max: "10",
                        label: "每部最多翻页",
                        variant: "outlined",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _cache[52] || (_cache[52] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, " 只搜**已订阅**的作品（卡片订阅 / 订阅全部 / 自动订阅都记进订阅清单）；搜索站点 / 下载器 / 下载目录 沿用上面「订阅」分区的设置；无结果 72 小时、失败 24 小时后自动重试，单轮预算用完的下一轮接着跑（断点在台账里）。 另外，插件每 30 分钟自动拉一次**订阅站点的站点 RSS**（不打搜索接口，避开站点流控），新种子与当前订阅 按剧名消歧后直接下载；RSS 没有的仍由主动搜索兜底。 ", -1))
            ], 64)) : _createCommentVNode("", true),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_24, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cog-outline",
                size: "20",
                class: "mr-1"
              }),
              _cache[53] || (_cache[53] = _createElementVNode("span", { class: "sdas-block-title" }, "运行", -1)),
              _cache[54] || (_cache[54] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, "发现频率，以及作品墙「搜索」用的站点", -1))
            ]),
            _createElementVNode("div", _hoisted_25, [
              _createVNode(_component_v_icon, {
                icon: "mdi-timer-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[55] || (_cache[55] = _createTextVNode(" 刷新节奏 ", -1))
            ]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.value.interval_hours,
                      "onUpdate:modelValue": _cache[20] || (_cache[20] = ($event) => local.value.interval_hours = $event),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "发现间隔（小时）",
                      variant: "outlined",
                      density: "compact",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.value.retry_minutes,
                      "onUpdate:modelValue": _cache[21] || (_cache[21] = ($event) => local.value.retry_minutes = $event),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      label: "解析失败重试（分钟）",
                      variant: "outlined",
                      density: "compact",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[71] || (_cache[71] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, " 每隔「发现间隔」跑一轮发现任务，重抓距上次已超过一个间隔的演员（演员页要真抓网络，不会每轮全量重扫）； 解析失败属于临时故障，按分钟级重试。 ", -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_26, [
              _createVNode(_component_v_icon, {
                icon: "mdi-web-check",
                size: "18",
                class: "mr-1"
              }),
              _cache[56] || (_cache[56] = _createTextVNode(" 资源搜索站点 ", -1)),
              _cache[57] || (_cache[57] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, " 作品墙上点「搜索」时，只在勾选的站点里搜；不勾 = 走系统默认 ", -1))
            ]),
            siteOptions.value.length ? (_openBlock(), _createBlock(_component_v_select, {
              key: 4,
              modelValue: selectedSiteModels.value,
              "onUpdate:modelValue": _cache[23] || (_cache[23] = ($event) => selectedSiteModels.value = $event),
              items: sortedSiteOptions.value,
              "item-title": "name",
              "item-value": "id",
              label: "资源搜索站点",
              multiple: "",
              chips: "",
              "closable-chips": "",
              variant: "outlined",
              density: "compact",
              "hide-details": "",
              placeholder: "不选 = 走系统默认"
            }, {
              "prepend-item": _withCtx(() => [
                _createElementVNode("div", _hoisted_27, [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "tonal",
                    color: "primary",
                    onClick: selectAllSites
                  }, {
                    default: _withCtx(() => [..._cache[58] || (_cache[58] = [
                      _createTextVNode("全选", -1)
                    ])]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "tonal",
                    onClick: _cache[22] || (_cache[22] = ($event) => selectedSiteModels.value = [])
                  }, {
                    default: _withCtx(() => [..._cache[59] || (_cache[59] = [
                      _createTextVNode("清空", -1)
                    ])]),
                    _: 1
                  }),
                  _createElementVNode("span", _hoisted_28, " 已选 " + _toDisplayString(selectedSiteIds.value.length) + " / " + _toDisplayString(siteOptions.value.length), 1)
                ])
              ]),
              _: 1
            }, 8, ["modelValue", "items"])) : siteLoadFailed.value ? (_openBlock(), _createBlock(_component_v_alert, {
              key: 5,
              type: "warning",
              variant: "tonal",
              density: "compact"
            }, {
              default: _withCtx(() => [..._cache[60] || (_cache[60] = [
                _createTextVNode(" 站点列表加载失败，可稍后重新打开本页重试。 ", -1)
              ])]),
              _: 1
            })) : siteLoading.value ? (_openBlock(), _createElementBlock("div", _hoisted_29, "正在加载站点列表…")) : (_openBlock(), _createElementBlock("div", _hoisted_30, " 当前没有启用中的搜索站点 —— 作品墙的「搜索」会直接走系统默认行为。 ")),
            _createVNode(_component_v_divider, { class: "my-3" }),
            saveError.value ? (_openBlock(), _createBlock(_component_v_alert, {
              key: 8,
              type: "error",
              variant: "tonal",
              density: "compact",
              class: "mb-2"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(saveError.value), 1)
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            _createElementVNode("div", _hoisted_31, [
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                variant: "text",
                onClick: _cache[24] || (_cache[24] = ($event) => emit("close"))
              }, {
                default: _withCtx(() => [..._cache[61] || (_cache[61] = [
                  _createTextVNode("取消", -1)
                ])]),
                _: 1
              }),
              _createVNode(_component_v_btn, {
                color: "primary",
                loading: saving.value,
                onClick: onSave
              }, {
                default: _withCtx(() => [..._cache[62] || (_cache[62] = [
                  _createTextVNode("保存", -1)
                ])]),
                _: 1
              }, 8, ["loading"])
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-75b62f1c"]]);

export { Config as default };
