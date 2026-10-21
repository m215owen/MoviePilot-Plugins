import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { f as fetchSearchSites, a as fetchDownloaderOptions, s as saveConfig, _ as _export_sfc } from './_plugin-vue_export-helper-yf5egOZA.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "sdas-root pa-2" };
const _hoisted_2 = { class: "d-flex align-center mb-3" };
const _hoisted_3 = { class: "text-subtitle-2 mb-2" };
const _hoisted_4 = { class: "text-caption sdas-dim ml-2" };
const _hoisted_5 = { class: "text-subtitle-2 mb-2" };
const _hoisted_6 = { class: "text-subtitle-2 mb-2" };
const _hoisted_7 = {
  class: "d-flex align-center px-4 pb-2",
  style: { "gap": "8px" }
};
const _hoisted_8 = { class: "text-caption sdas-dim" };
const _hoisted_9 = {
  key: 2,
  class: "text-caption sdas-dim"
};
const _hoisted_10 = {
  key: 3,
  class: "text-caption sdas-dim"
};
const _hoisted_11 = { class: "text-subtitle-2 mb-2" };
const _hoisted_12 = {
  key: 0,
  class: "text-caption text-warning mt-1"
};
const _hoisted_13 = {
  class: "d-flex align-center",
  style: { "gap": "8px" }
};
const {computed,onMounted,ref} = await importShared('vue');
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
        subscribe_downloader: ""
      };
    }
    const local = ref(defaults());
    const saving = ref(false);
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
    });
    const actorItems = computed(
      () => String(local.value.actors || "").split(/[,，;；\n\r]+/).map((item) => item.trim()).filter(Boolean)
    );
    async function onSave() {
      saving.value = true;
      try {
        const cleaned = String(local.value.subscribe_downloader || "").trim();
        await saveConfig(props, { ...local.value, subscribe_downloader: cleaned });
        emit("save", { ...local.value, subscribe_downloader: cleaned });
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
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_combobox = _resolveComponent("v-combobox");
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
              _cache[12] || (_cache[12] = _createElementVNode("h3", { class: "ma-0" }, "短剧演员 · 设置", -1)),
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
              default: _withCtx(() => [..._cache[13] || (_cache[13] = [
                _createTextVNode(" 作品全部来自", -1),
                _createElementVNode("b", null, "短剧百科", -1),
                _createTextVNode("（duanjubaike.org，已作为媒体数据源接入系统）。 在作品墙点「订阅」，走的就是", -1),
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
              _cache[14] || (_cache[14] = _createTextVNode(" 关注的演员 ", -1)),
              _createElementVNode("span", _hoisted_4, "共 " + _toDisplayString(actorItems.value.length) + " 位", 1)
            ]),
            _createVNode(_component_v_textarea, {
              modelValue: local.value.actors,
              "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => local.value.actors = $event),
              variant: "outlined",
              density: "compact",
              rows: "4",
              "auto-grow": "",
              "hide-details": "",
              placeholder: "一行一位，或用逗号分隔。例：\n徐艺真\n孙樾"
            }, null, 8, ["modelValue"]),
            _cache[25] || (_cache[25] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, " 单个添加也可以在作品墙右上角「添加演员」里填名字（会先在短剧百科里核对）。 ", -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_5, [
              _createVNode(_component_v_icon, {
                icon: "mdi-timer-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[15] || (_cache[15] = _createTextVNode(" 刷新节奏 ", -1))
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
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => local.value.interval_hours = $event),
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
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => local.value.retry_minutes = $event),
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
            _cache[26] || (_cache[26] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, " 每隔「发现间隔」跑一轮发现任务，重抓距上次已超过一个间隔的演员（演员页要真抓网络，不会每轮全量重扫）； 解析失败属于临时故障，按分钟级重试。 ", -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_6, [
              _createVNode(_component_v_icon, {
                icon: "mdi-web-check",
                size: "18",
                class: "mr-1"
              }),
              _cache[16] || (_cache[16] = _createTextVNode(" 资源搜索站点 ", -1)),
              _cache[17] || (_cache[17] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, " 作品墙上点「搜索」时，只在勾选的站点里搜；不勾 = 走系统默认 ", -1))
            ]),
            siteOptions.value.length ? (_openBlock(), _createBlock(_component_v_select, {
              key: 0,
              modelValue: selectedSiteModels.value,
              "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => selectedSiteModels.value = $event),
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
                _createElementVNode("div", _hoisted_7, [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "tonal",
                    color: "primary",
                    onClick: selectAllSites
                  }, {
                    default: _withCtx(() => [..._cache[18] || (_cache[18] = [
                      _createTextVNode("全选", -1)
                    ])]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "tonal",
                    onClick: _cache[8] || (_cache[8] = ($event) => selectedSiteModels.value = [])
                  }, {
                    default: _withCtx(() => [..._cache[19] || (_cache[19] = [
                      _createTextVNode("清空", -1)
                    ])]),
                    _: 1
                  }),
                  _createElementVNode("span", _hoisted_8, " 已选 " + _toDisplayString(selectedSiteIds.value.length) + " / " + _toDisplayString(siteOptions.value.length), 1)
                ])
              ]),
              _: 1
            }, 8, ["modelValue", "items"])) : siteLoadFailed.value ? (_openBlock(), _createBlock(_component_v_alert, {
              key: 1,
              type: "warning",
              variant: "tonal",
              density: "compact"
            }, {
              default: _withCtx(() => [..._cache[20] || (_cache[20] = [
                _createTextVNode(" 站点列表加载失败，可稍后重新打开本页重试。 ", -1)
              ])]),
              _: 1
            })) : siteLoading.value ? (_openBlock(), _createElementBlock("div", _hoisted_9, "正在加载站点列表…")) : (_openBlock(), _createElementBlock("div", _hoisted_10, " 当前没有启用中的搜索站点 —— 作品墙的「搜索」会直接走系统默认行为。 ")),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_11, [
              _createVNode(_component_v_icon, {
                icon: "mdi-download-network-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[21] || (_cache[21] = _createTextVNode(" 订阅下载器 ", -1)),
              _cache[22] || (_cache[22] = _createElementVNode("span", { class: "text-caption sdas-dim ml-2" }, "作品墙提交订阅时使用的下载客户端", -1))
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
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => local.value.subscribe_downloader = $event),
                      items: downloaderNames.value,
                      loading: downloaderLoading.value,
                      label: "下载器",
                      variant: "outlined",
                      density: "compact",
                      clearable: "",
                      "hide-details": "",
                      placeholder: "留空 = 跟随系统默认"
                    }, null, 8, ["modelValue", "items", "loading"]),
                    local.value.subscribe_downloader && !downloaderNames.value.includes(local.value.subscribe_downloader) ? (_openBlock(), _createElementBlock("div", _hoisted_12, " 宿主没有名为「" + _toDisplayString(local.value.subscribe_downloader) + "」的下载器，提交时会被忽略 ", 1)) : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _cache[27] || (_cache[27] = _createElementVNode("div", { class: "text-caption sdas-dim mt-1" }, [
              _createTextVNode(" 指定下载器后，作品墙点「订阅」会按此下载器"),
              _createElementVNode("b", null, "直接提交"),
              _createTextVNode("（系统订阅弹窗没有下载器选项，带不上偏好）； 留空则保持原样，弹出系统订阅对话框。下载客户端在宿主「设定 → 下载器」里维护。 ")
            ], -1)),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_13, [
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                variant: "text",
                onClick: _cache[11] || (_cache[11] = ($event) => emit("close"))
              }, {
                default: _withCtx(() => [..._cache[23] || (_cache[23] = [
                  _createTextVNode("取消", -1)
                ])]),
                _: 1
              }),
              _createVNode(_component_v_btn, {
                color: "primary",
                loading: saving.value,
                onClick: onSave
              }, {
                default: _withCtx(() => [..._cache[24] || (_cache[24] = [
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

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-6de28871"]]);

export { Config as default };
