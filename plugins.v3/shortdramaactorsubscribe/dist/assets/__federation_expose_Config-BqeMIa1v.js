import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { r as resolveApi, s as searchActor, f as fetchOptions, a as saveConfig, _ as _export_sfc } from './_plugin-vue_export-helper-CgyRQy_e.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,withKeys:_withKeys,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createBlock:_createBlock} = await importShared('vue');

const _hoisted_1 = { class: "sdas-root pa-2" };
const _hoisted_2 = { class: "d-flex align-center mb-3" };
const _hoisted_3 = { class: "text-subtitle-2 mb-2" };
const _hoisted_4 = { class: "text-caption sdas-dim ml-2" };
const _hoisted_5 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const _hoisted_6 = {
  key: 0,
  class: "d-flex align-center text-caption sdas-dim",
  style: { "gap": "8px" }
};
const _hoisted_7 = { class: "text-body-2" };
const _hoisted_8 = {
  key: 0,
  class: "text-caption sdas-dim ml-2"
};
const _hoisted_9 = { class: "text-caption sdas-dim ml-2" };
const _hoisted_10 = { class: "text-subtitle-2 mb-2" };
const _hoisted_11 = {
  class: "d-flex align-center mb-2 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_12 = { class: "text-subtitle-2" };
const _hoisted_13 = { class: "text-subtitle-2 mb-2" };
const _hoisted_14 = { class: "text-caption sdas-dim mb-1" };
const _hoisted_15 = {
  class: "d-flex align-center flex-wrap",
  style: { "gap": "8px" }
};
const {computed,onMounted,reactive,ref} = await importShared('vue');
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
    const saving = ref(false);
    const defaults = {
      enabled: false,
      onlyonce: false,
      actors: "",
      sites: [],
      prefer_short_drama_category: true,
      downloader: "",
      download_path: "",
      library_path: "",
      transfer_type: "link",
      interval_hours: 6,
      organize_enabled: true,
      organize_interval_minutes: 30,
      notify: true,
      douban_cookie: "",
      proxy: false,
      max_works: 10,
      sidebar_nav: true
    };
    const local = reactive({ ...defaults });
    const options = reactive({
      sites: [],
      downloaders: [],
      transfer_types: [
        { title: "硬链接（推荐，省空间）", value: "link" },
        { title: "复制", value: "copy" },
        { title: "移动", value: "move" }
      ],
      directories: [],
      defaults: {
        downloader: "",
        directory: "",
        library_path: "",
        directory_name: ""
      }
    });
    const downloaderItems = computed(
      () => options.downloaders.map((item) => ({
        title: item.default ? `${item.title}（系统默认）` : item.title,
        value: item.value
      }))
    );
    const downloaderHint = computed(() => {
      const prefer = options.defaults.downloader;
      return prefer ? `留空则跟随宿主默认（${prefer}）` : "留空则跟随宿主默认下载器";
    });
    const directoryItems = computed(
      () => options.directories.filter((item) => item.download_path).map((item) => ({
        title: item.is_short_drama ? `★ ${item.title}` : item.title,
        value: item.download_path
      }))
    );
    const libraryItems = computed(
      () => Array.from(
        new Set(options.directories.map((item) => item.library_path).filter((item) => !!item))
      )
    );
    const directoryHint = computed(() => {
      const count = options.directories.length;
      if (!count) return "未从系统读到目录配置，可直接手工填写路径";
      return `共 ${count} 个系统目录，可下拉选择或直接输入；既用于提交下载，也作为整理扫描目录`;
    });
    const shortDramaDirectory = computed(
      () => options.directories.find((item) => item.is_short_drama) || null
    );
    function onPickDirectory(value) {
      const path = String(value || "").trim();
      if (!path) return;
      const hit = options.directories.find((item) => item.download_path === path);
      if (!hit) return;
      const current = String(local.library_path || "").trim();
      const autoFilled = options.directories.some(
        (item) => item.library_path && item.library_path === current
      );
      if (!current || autoFilled) {
        local.library_path = hit.library_path || "";
      }
    }
    function applySystemDefaults() {
      const defaults2 = options.defaults;
      if (!defaults2) return;
      if (defaults2.directory) local.download_path = defaults2.directory;
      if (defaults2.library_path) local.library_path = defaults2.library_path;
      if (defaults2.downloader && !String(local.downloader || "").trim()) {
        local.downloader = defaults2.downloader;
      }
    }
    const cookieStatus = computed(() => {
      const source = String(
        props.initialConfig?.douban_cookie_source || ""
      );
      if (source === "manual") return "插件内手填的 Cookie";
      if (source === "cookiecloud") return "宿主 CookieCloud（自动读取，已生效）";
      if (source) return "未取到登录态（豆瓣匿名搜索额度极低）";
      return "读取中…";
    });
    function chipColor(source) {
      return source === "tmdb" ? "teal" : "green";
    }
    const actorItems = computed(
      () => String(local.actors || "").split(/[\r\n,，、;；]+/).map((item) => item.trim()).filter(Boolean)
    );
    const actorDraft = ref("");
    function commitActorItems(items) {
      const seen = /* @__PURE__ */ new Set();
      const next = [];
      for (const item of items) {
        const value = String(item || "").trim();
        if (!value || seen.has(value)) continue;
        seen.add(value);
        next.push(value);
      }
      local.actors = next.join("，");
    }
    function addActorDraft() {
      const parts = String(actorDraft.value || "").split(/[\r\n,，、;；]+/).map((item) => item.trim()).filter(Boolean);
      if (!parts.length) return;
      commitActorItems([...actorItems.value, ...parts]);
      actorDraft.value = "";
    }
    const searchName = ref("");
    const searching = ref(false);
    const searchMessage = ref("");
    const candidates = ref([]);
    async function doSearchActor() {
      const api = resolveApi(props);
      const name = searchName.value.trim();
      if (!api || !name) return;
      searching.value = true;
      try {
        const res = await searchActor(api, name);
        candidates.value = res.data;
        searchMessage.value = candidates.value.length ? "" : res.message || "未找到匹配的演员，换一个名字或直接填写人物 ID。";
      } finally {
        searching.value = false;
      }
    }
    function clearSearch() {
      candidates.value = [];
      searchMessage.value = "";
    }
    function appendActor(id) {
      commitActorItems([...actorItems.value, id]);
    }
    async function loadOptions() {
      const api = resolveApi(props);
      if (!api) return;
      try {
        const data = await fetchOptions(api);
        if (!data) return;
        options.sites = data.sites || [];
        options.downloaders = data.downloaders || [];
        options.directories = data.directories || [];
        if (data.defaults) options.defaults = data.defaults;
        if (data.transfer_types?.length) options.transfer_types = data.transfer_types;
        if (!String(local.download_path || "").trim() && options.defaults.directory) {
          local.download_path = options.defaults.directory;
          if (!String(local.library_path || "").trim()) {
            local.library_path = options.defaults.library_path;
          }
        }
        if (!String(local.downloader || "").trim() && options.defaults.downloader) {
          local.downloader = options.defaults.downloader;
        }
      } catch (err) {
        console.warn("[ShortDramaActorSubscribe] 读取下拉候选失败", err);
      }
    }
    async function saveConfig$1() {
      saving.value = true;
      const payload = JSON.parse(JSON.stringify(local));
      emit("save", payload);
      const api = resolveApi(props);
      if (api) {
        const res = await saveConfig(api, payload);
        if (!res.ok) console.warn("[ShortDramaActorSubscribe] 保存配置失败：", res.message);
      }
      window.setTimeout(() => {
        saving.value = false;
      }, 600);
    }
    onMounted(() => {
      const initial = props.initialConfig;
      if (initial && typeof initial === "object") {
        Object.keys(defaults).forEach((key) => {
          const value = initial[key];
          if (value !== void 0) {
            local[key] = value;
          }
        });
      }
      void loadOptions();
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_textarea = _resolveComponent("v-textarea");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_combobox = _resolveComponent("v-combobox");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-4"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_icon, {
                icon: "mdi-movie-star-outline",
                class: "mr-2"
              }),
              _cache[19] || (_cache[19] = _createElementVNode("h3", { class: "ma-0" }, "短剧演员订阅 · 设置", -1)),
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
              default: _withCtx(() => [..._cache[20] || (_cache[20] = [
                _createTextVNode(" 本插件", -1),
                _createElementVNode("b", null, "不走宿主订阅系统", -1),
                _createTextVNode("：短剧在 TMDB / 豆瓣 大量没有条目，宿主识别器建不起媒体身份。 这里改为「剧名 → 站点搜索」直达资源：发现源合并 TMDB 与豆瓣，同名以年份消歧 （年份缺失放行），同剧多资源按 做种数 → 体积 → 分辨率 择优下一条。 ", -1)
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
                      modelValue: local.enabled,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => local.enabled = $event),
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
                      modelValue: local.sidebar_nav,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => local.sidebar_nav = $event),
                      label: "侧栏「订阅」组里显示「短剧」入口",
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
                      modelValue: local.notify,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => local.notify = $event),
                      label: "发送系统通知",
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
                      modelValue: local.proxy,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => local.proxy = $event),
                      label: "使用宿主代理",
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
              _cache[21] || (_cache[21] = _createTextVNode(" 订阅的演员 ", -1)),
              _createElementVNode("span", _hoisted_4, "共 " + _toDisplayString(actorItems.value.length) + " 位", 1)
            ]),
            _createElementVNode("div", _hoisted_5, [
              _createVNode(_component_v_text_field, {
                modelValue: actorDraft.value,
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => actorDraft.value = $event),
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                "prepend-inner-icon": "mdi-account-plus-outline",
                placeholder: "输入演员名 / 豆瓣ID / TMDB ID / 主页链接后回车添加（可一次粘贴多个）",
                class: "sdas-actor-input",
                onKeyup: _withKeys(addActorDraft, ["enter"])
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "tonal",
                color: "primary",
                disabled: !actorDraft.value.trim(),
                onClick: addActorDraft
              }, {
                default: _withCtx(() => [..._cache[22] || (_cache[22] = [
                  _createTextVNode(" 添加 ", -1)
                ])]),
                _: 1
              }, 8, ["disabled"])
            ]),
            _createVNode(_component_v_textarea, {
              modelValue: local.actors,
              "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => local.actors = $event),
              density: "comfortable",
              variant: "outlined",
              "hide-details": "",
              rows: "4",
              "no-resize": "",
              placeholder: "多位演员用逗号分隔，例如：马秋元，王格格，申浩男",
              class: "sdas-actor-textarea mb-2"
            }, null, 8, ["modelValue"]),
            _cache[35] || (_cache[35] = _createElementVNode("div", { class: "text-caption sdas-dim mb-3" }, " 填「人物 ID」可跳过按名称搜索（豆瓣搜索额度很紧，演员多时优先填 ID）。 发现源同时查 TMDB 与豆瓣，两边结果按剧名 + 年份并集。 ", -1)),
            _createVNode(_component_v_text_field, {
              modelValue: searchName.value,
              "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => searchName.value = $event),
              label: "搜索演员（辅助填写人物 ID）",
              density: "comfortable",
              "hide-details": "",
              "prepend-inner-icon": "mdi-magnify",
              class: "mb-2",
              onKeyup: _withKeys(doSearchActor, ["enter"])
            }, {
              append: _withCtx(() => [
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  loading: searching.value,
                  onClick: doSearchActor
                }, {
                  default: _withCtx(() => [..._cache[23] || (_cache[23] = [
                    _createTextVNode(" 搜索 ", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            }, 8, ["modelValue"]),
            candidates.value.length || searchMessage.value ? (_openBlock(), _createBlock(_component_v_card, {
              key: 0,
              variant: "tonal",
              class: "pa-2 mb-3"
            }, {
              default: _withCtx(() => [
                !candidates.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
                  _createElementVNode("span", null, _toDisplayString(searchMessage.value), 1),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    icon: "mdi-close",
                    title: "关闭",
                    onClick: clearSearch
                  })
                ])) : _createCommentVNode("", true),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(candidates.value, (item) => {
                  return _openBlock(), _createElementBlock("div", {
                    key: `${item.source}:${item.id}`,
                    class: "d-flex align-center py-1"
                  }, [
                    _createVNode(_component_v_chip, {
                      size: "x-small",
                      variant: "tonal",
                      class: "mr-2",
                      color: chipColor(item.source)
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(item.source === "tmdb" ? "TMDB" : "豆瓣"), 1)
                      ]),
                      _: 2
                    }, 1032, ["color"]),
                    _createElementVNode("span", _hoisted_7, _toDisplayString(item.name), 1),
                    item.original_name && item.original_name !== item.name ? (_openBlock(), _createElementBlock("span", _hoisted_8, _toDisplayString(item.original_name), 1)) : _createCommentVNode("", true),
                    _createElementVNode("span", _hoisted_9, "ID " + _toDisplayString(item.id), 1),
                    _createVNode(_component_v_btn, {
                      size: "x-small",
                      variant: "tonal",
                      color: "primary",
                      density: "compact",
                      class: "ml-2",
                      onClick: ($event) => appendActor(item.id)
                    }, {
                      default: _withCtx(() => [..._cache[24] || (_cache[24] = [
                        _createTextVNode(" 添加 ID ", -1)
                      ])]),
                      _: 1
                    }, 8, ["onClick"])
                  ]);
                }), 128))
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_10, [
              _createVNode(_component_v_icon, {
                icon: "mdi-magnify-scan",
                size: "18",
                class: "mr-1"
              }),
              _cache[25] || (_cache[25] = _createTextVNode(" 搜索范围与下载 ", -1))
            ]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_select, {
                      modelValue: local.sites,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => local.sites = $event),
                      items: options.sites,
                      label: "搜索站点",
                      multiple: "",
                      chips: "",
                      "closable-chips": "",
                      density: "comfortable",
                      hint: "不选则无法搜索；建议只选确有短剧资源的站点",
                      "persistent-hint": ""
                    }, null, 8, ["modelValue", "items"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_select, {
                      modelValue: local.downloader,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => local.downloader = $event),
                      items: downloaderItems.value,
                      label: "下载器",
                      clearable: "",
                      density: "comfortable",
                      hint: downloaderHint.value,
                      "persistent-hint": ""
                    }, null, 8, ["modelValue", "items", "hint"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, { cols: "12" }, {
                  default: _withCtx(() => [..._cache[26] || (_cache[26] = [
                    _createElementVNode("div", { class: "text-caption sdas-dim" }, " 下载器与下载路径的候选来自宿主「系统设置 → 下载器 / 目录管理」， 默认值已按系统配置预填，无需手抄路径。 ", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_col, { cols: "12" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_switch, {
                      modelValue: local.prefer_short_drama_category,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => local.prefer_short_drama_category = $event),
                      label: "优先在站点「短剧」分类内搜索（可显著降低同名误命中；站点没有该分类时自动退化为全站搜索）",
                      color: "primary",
                      "hide-details": "",
                      density: "compact"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_11, [
              _createElementVNode("span", _hoisted_12, [
                _createVNode(_component_v_icon, {
                  icon: "mdi-folder-move-outline",
                  size: "18",
                  class: "mr-1"
                }),
                _cache[27] || (_cache[27] = _createTextVNode(" 整理入库 ", -1))
              ]),
              shortDramaDirectory.value ? (_openBlock(), _createBlock(_component_v_chip, {
                key: 0,
                size: "x-small",
                variant: "tonal",
                color: "primary"
              }, {
                default: _withCtx(() => [..._cache[28] || (_cache[28] = [
                  _createTextVNode(" 检测到系统「短剧」目录 ", -1)
                ])]),
                _: 1
              })) : _createCommentVNode("", true),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "text",
                color: "primary",
                disabled: !options.defaults.directory,
                onClick: applySystemDefaults
              }, {
                default: _withCtx(() => [..._cache[29] || (_cache[29] = [
                  _createTextVNode(" 采用系统推荐路径 ", -1)
                ])]),
                _: 1
              }, 8, ["disabled"])
            ]),
            _createVNode(_component_v_switch, {
              modelValue: local.organize_enabled,
              "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => local.organize_enabled = $event),
              label: "启用整理入库",
              color: "primary",
              "hide-details": "",
              density: "compact",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_combobox, {
                      modelValue: local.download_path,
                      "onUpdate:modelValue": [
                        _cache[12] || (_cache[12] = ($event) => local.download_path = $event),
                        onPickDirectory
                      ],
                      items: directoryItems.value,
                      "item-title": "title",
                      "item-value": "value",
                      label: "下载目录（下载器保存路径）",
                      density: "comfortable",
                      hint: directoryHint.value,
                      "persistent-hint": ""
                    }, null, 8, ["modelValue", "items", "hint"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_combobox, {
                      modelValue: local.library_path,
                      "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => local.library_path = $event),
                      items: libraryItems.value,
                      label: "媒体库根目录",
                      density: "comfortable",
                      hint: "与下载目录成对，来自宿主「目录管理」；整理后放到 <该目录>/剧名 (年份)/",
                      "persistent-hint": ""
                    }, null, 8, ["modelValue", "items"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_select, {
                      modelValue: local.transfer_type,
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => local.transfer_type = $event),
                      items: options.transfer_types,
                      label: "整理方式",
                      density: "comfortable"
                    }, null, 8, ["modelValue", "items"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "6",
                  sm: "3",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.interval_hours,
                      "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => local.interval_hours = $event),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "1",
                      max: "168",
                      label: "订阅轮询间隔（小时）",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "6",
                  sm: "3",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.organize_interval_minutes,
                      "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => local.organize_interval_minutes = $event),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "5",
                      max: "1440",
                      label: "整理扫描间隔（分钟）",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_13, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cookie-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[30] || (_cache[30] = _createTextVNode(" 豆瓣 Cookie（提高搜索额度） ", -1))
            ]),
            _createVNode(_component_v_alert, {
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "mb-2"
            }, {
              default: _withCtx(() => [..._cache[31] || (_cache[31] = [
                _createTextVNode(" 默认", -1),
                _createElementVNode("b", null, "自动", -1),
                _createTextVNode("从宿主「系统设置 → CookieCloud」读取豆瓣登录态，这里无需填写。 仅当 CookieCloud 没同步豆瓣、或想临时换账号时才手工粘贴覆盖。 ", -1)
              ])]),
              _: 1
            }),
            _createVNode(_component_v_textarea, {
              modelValue: local.douban_cookie,
              "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => local.douban_cookie = $event),
              label: "豆瓣 Cookie（留空 = 自动用宿主 CookieCloud）",
              placeholder: "bid=xxx; dbcl2=xxx; ck=xxx",
              rows: "2",
              density: "comfortable",
              "auto-grow": "",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createElementVNode("div", _hoisted_14, " 当前生效来源：" + _toDisplayString(cookieStatus.value), 1),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_15, [
              _createVNode(_component_v_btn, {
                color: "primary",
                loading: saving.value,
                onClick: saveConfig$1
              }, {
                default: _withCtx(() => [..._cache[32] || (_cache[32] = [
                  _createTextVNode("保存配置", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              _createVNode(_component_v_btn, {
                variant: "text",
                onClick: _cache[18] || (_cache[18] = ($event) => emit("switch"))
              }, {
                default: _withCtx(() => [..._cache[33] || (_cache[33] = [
                  _createTextVNode("查看详情", -1)
                ])]),
                _: 1
              }),
              _createVNode(_component_v_spacer),
              _cache[34] || (_cache[34] = _createElementVNode("span", { class: "text-caption sdas-dim" }, "保存后立即生效（后台会重新初始化插件）", -1))
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-966a881d"]]);

export { Config as default };
