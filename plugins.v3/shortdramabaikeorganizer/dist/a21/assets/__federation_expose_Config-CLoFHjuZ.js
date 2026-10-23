import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { b as backend, h as hostApi, _ as _export_sfc } from './_plugin-vue_export-helper-DdliaD78.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,createVNode:_createVNode,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "sdbo-dir-line" };
const _hoisted_2 = { class: "sdbo-dir-line mt-2" };
const _hoisted_3 = { class: "sdbo-dir-line" };
const _hoisted_4 = { class: "sdbo-dir-line" };
const _hoisted_5 = {
  key: 3,
  class: "text-caption text-medium-emphasis mt-3"
};
const _hoisted_6 = { class: "text-caption text-medium-emphasis mt-3" };
const {onErrorCaptured,onMounted,reactive,ref} = await importShared('vue');
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
      source_dirs: [],
      library_dir: "",
      scan_depth: 1,
      transfer_type: "softlink",
      episode_width: 2,
      auto_rename_episode: true,
      scrape_enabled: true,
      force_transfer: false,
      notify: true,
      monitor_enabled: false,
      monitor_mode: "watch",
      monitor_interval: 60,
      force_reorganize: false
    };
    const transferItems = [
      { title: "移动（move）", value: "move" },
      { title: "复制（copy）", value: "copy" },
      { title: "硬链接（link）", value: "link" },
      { title: "软链接（softlink）", value: "softlink" }
    ];
    const monitorModeItems = [
      { title: "事件监听（推荐）", value: "watch" },
      { title: "轮询（回退）", value: "poll" }
    ];
    function toList(value) {
      const raw = typeof value === "string" ? value.split(/\r?\n/) : Array.isArray(value) ? value : [];
      const result = [];
      for (const item of raw) {
        const text = typeof item === "string" ? item : item && typeof item === "object" ? String(item.value ?? item.title ?? "") : "";
        const trimmed = text.trim();
        if (trimmed && result.indexOf(trimmed) < 0) result.push(trimmed);
      }
      return result;
    }
    function toOne(value) {
      if (typeof value === "string") return value.trim();
      if (value && typeof value === "object") {
        const record = value;
        return String(record.value ?? record.title ?? "").trim();
      }
      return "";
    }
    const incoming = props.initialConfig || {};
    const conf = reactive({
      ...DEFAULTS,
      ...incoming,
      source_dirs: toList(incoming.source_dirs),
      library_dir: toOne(incoming.library_dir)
    });
    const errorText = ref("");
    const saving = ref(false);
    const manualPath = ref("");
    const sourceItems = ref([]);
    const libraryItems = ref([]);
    const browseOpen = ref(false);
    const browseTarget = ref("source");
    const browseLoading = ref(false);
    const browseMessage = ref("");
    const browseEntries = ref([]);
    const currentPath = ref("");
    const parentPath = ref("");
    const pathInput = ref("");
    onErrorCaptured((err) => {
      errorText.value = `渲染异常：${err?.message || String(err)}`;
      return false;
    });
    function apiOrNull() {
      return hostApi({ api: props.api });
    }
    async function loadDirOptions() {
      const api = apiOrNull();
      if (!api) return;
      try {
        const data = await backend.dirOptions(api);
        sourceItems.value = data?.sources || [];
        libraryItems.value = data?.libraries || [];
      } catch (err) {
        errorText.value = `读取系统目录失败：${err?.message || String(err)}`;
      }
    }
    function openBrowse(target) {
      browseTarget.value = target;
      browseOpen.value = true;
      browseMessage.value = "";
      const start = target === "library" ? toOne(conf.library_dir) : toList(conf.source_dirs)[0] || "";
      const fallback = (target === "library" ? libraryItems.value[0] : sourceItems.value[0])?.value || "/";
      void goPath(start || fallback);
    }
    async function goPath(path) {
      const api = apiOrNull();
      if (!api) {
        browseMessage.value = "宿主 api 实例不可用，请刷新页面重试";
        return;
      }
      browseLoading.value = true;
      browseMessage.value = "";
      try {
        const data = await backend.browse(api, path || "");
        currentPath.value = data?.path || "";
        parentPath.value = data?.parent || "";
        pathInput.value = data?.path || "";
        browseEntries.value = data?.entries || [];
      } catch (err) {
        browseMessage.value = `读取目录失败：${err?.message || String(err)}`;
      } finally {
        browseLoading.value = false;
      }
    }
    function confirmBrowse() {
      if (!currentPath.value) return;
      if (browseTarget.value === "library") {
        conf.library_dir = currentPath.value;
        ensureOption(libraryItems, currentPath.value);
      } else {
        const list = toList(conf.source_dirs);
        if (list.indexOf(currentPath.value) < 0) list.push(currentPath.value);
        conf.source_dirs = list;
        ensureOption(sourceItems, currentPath.value);
      }
      browseOpen.value = false;
    }
    function addManual() {
      const path = manualPath.value.trim();
      if (!path) return;
      const list = toList(conf.source_dirs);
      if (list.indexOf(path) < 0) list.push(path);
      conf.source_dirs = list;
      ensureOption(sourceItems, path);
      manualPath.value = "";
    }
    function ensureOption(items, path) {
      if (!path) return;
      if (items.value.some((item) => item.value === path)) return;
      items.value = [...items.value, { title: path, value: path }];
    }
    function saveConfig() {
      saving.value = true;
      errorText.value = "";
      emit("save", {
        ...conf,
        source_dirs: toList(conf.source_dirs),
        library_dir: toOne(conf.library_dir)
      });
      window.setTimeout(() => {
        saving.value = false;
      }, 400);
    }
    function closeDialog() {
      emit("close");
    }
    onMounted(() => {
      void loadDirOptions();
    });
    return (_ctx, _cache) => {
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_card_actions = _resolveComponent("v-card-actions");
      const _component_v_progress_linear = _resolveComponent("v-progress-linear");
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_list_item_title = _resolveComponent("v-list-item-title");
      const _component_v_list_item = _resolveComponent("v-list-item");
      const _component_v_list = _resolveComponent("v-list");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_dialog = _resolveComponent("v-dialog");
      return _openBlock(), _createBlock(_component_v_card, {
        class: "sdbo-config",
        variant: "flat"
      }, {
        default: _withCtx(() => [
          errorText.value ? (_openBlock(), _createBlock(_component_v_alert, {
            key: 0,
            type: "error",
            variant: "tonal",
            density: "compact",
            class: "ma-3 mb-0"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(errorText.value), 1)
            ]),
            _: 1
          })) : _createCommentVNode("", true),
          _createVNode(_component_v_card_title, { class: "text-body-1 pb-1" }, {
            default: _withCtx(() => [..._cache[23] || (_cache[23] = [
              _createTextVNode(" 短剧百科整理 · 配置 ", -1),
              _createElementVNode("span", { class: "text-caption text-medium-emphasis" }, "（前端 build a9）", -1)
            ])]),
            _: 1
          }),
          _createVNode(_component_v_card_text, null, {
            default: _withCtx(() => [
              _createVNode(_component_v_row, { dense: "" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "3"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_switch, {
                        modelValue: conf.enabled,
                        "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => conf.enabled = $event),
                        label: "启用插件",
                        color: "primary",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "3"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_switch, {
                        modelValue: conf.notify,
                        "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => conf.notify = $event),
                        label: "发送通知",
                        color: "primary",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "3"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_switch, {
                        modelValue: conf.scrape_enabled,
                        "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => conf.scrape_enabled = $event),
                        label: "自动刮削",
                        color: "primary",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "3"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_switch, {
                        modelValue: conf.force_transfer,
                        "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => conf.force_transfer = $event),
                        label: "强制整理历史",
                        color: "primary",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "3"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_switch, {
                        modelValue: conf.monitor_enabled,
                        "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => conf.monitor_enabled = $event),
                        label: "目录监控",
                        color: "primary",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _cache[27] || (_cache[27] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-3" }, "扫描目录（待整理短剧的上一层根目录，可多选）", -1)),
              _createElementVNode("div", _hoisted_1, [
                _createVNode(_component_v_select, {
                  modelValue: conf.source_dirs,
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => conf.source_dirs = $event),
                  items: sourceItems.value,
                  multiple: "",
                  chips: "",
                  density: "compact",
                  "hide-details": "",
                  class: "sdbo-grow"
                }, null, 8, ["modelValue", "items"]),
                _createVNode(_component_v_btn, {
                  variant: "tonal",
                  color: "primary",
                  "prepend-icon": "mdi-folder-search",
                  onClick: _cache[6] || (_cache[6] = ($event) => openBrowse("source"))
                }, {
                  default: _withCtx(() => [..._cache[24] || (_cache[24] = [
                    _createTextVNode("浏览目录", -1)
                  ])]),
                  _: 1
                })
              ]),
              _createElementVNode("div", _hoisted_2, [
                _createVNode(_component_v_text_field, {
                  modelValue: manualPath.value,
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => manualPath.value = $event),
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  placeholder: "系统配置里没有的目录？粘贴绝对路径后点右侧按钮加入",
                  class: "sdbo-grow",
                  onKeyup: _withKeys(addManual, ["enter"])
                }, null, 8, ["modelValue"]),
                _createVNode(_component_v_btn, {
                  variant: "text",
                  onClick: addManual
                }, {
                  default: _withCtx(() => [..._cache[25] || (_cache[25] = [
                    _createTextVNode("加入扫描目录", -1)
                  ])]),
                  _: 1
                })
              ]),
              _cache[28] || (_cache[28] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-3" }, "目标库目录（短剧媒体库根）", -1)),
              _createElementVNode("div", _hoisted_3, [
                _createVNode(_component_v_select, {
                  modelValue: conf.library_dir,
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => conf.library_dir = $event),
                  items: libraryItems.value,
                  density: "compact",
                  "hide-details": "",
                  clearable: "",
                  class: "sdbo-grow"
                }, null, 8, ["modelValue", "items"]),
                _createVNode(_component_v_btn, {
                  variant: "tonal",
                  color: "primary",
                  "prepend-icon": "mdi-folder-search",
                  onClick: _cache[9] || (_cache[9] = ($event) => openBrowse("library"))
                }, {
                  default: _withCtx(() => [..._cache[26] || (_cache[26] = [
                    _createTextVNode("浏览目录", -1)
                  ])]),
                  _: 1
                })
              ]),
              _createVNode(_component_v_row, {
                dense: "",
                class: "mt-3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: conf.scan_depth,
                        "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => conf.scan_depth = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        min: "1",
                        label: "扫描深度",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_select, {
                        modelValue: conf.transfer_type,
                        "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => conf.transfer_type = $event),
                        items: transferItems,
                        label: "搬运方式",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: conf.episode_width,
                        "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => conf.episode_width = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        min: "1",
                        max: "4",
                        label: "集号补零位数",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_select, {
                        modelValue: conf.monitor_mode,
                        "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => conf.monitor_mode = $event),
                        items: monitorModeItems,
                        label: "监控模式",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: conf.monitor_interval,
                        "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => conf.monitor_interval = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        min: "10",
                        label: "轮询间隔(秒)（仅轮询模式）",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_switch, {
                        modelValue: conf.auto_rename_episode,
                        "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => conf.auto_rename_episode = $event),
                        label: "集号缺失自动补齐",
                        color: "primary",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_switch, {
                        modelValue: conf.force_reorganize,
                        "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => conf.force_reorganize = $event),
                        label: "强制重整理",
                        color: "warning",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode(_component_v_card_actions, null, {
            default: _withCtx(() => [
              _cache[31] || (_cache[31] = _createElementVNode("span", { class: "text-caption text-medium-emphasis" }, "识别源 djbaike ｜ 插件自包含搬运 ｜ 历史写系统整理历史", -1)),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                variant: "text",
                onClick: closeDialog
              }, {
                default: _withCtx(() => [..._cache[29] || (_cache[29] = [
                  _createTextVNode("取消", -1)
                ])]),
                _: 1
              }),
              _createVNode(_component_v_btn, {
                color: "primary",
                variant: "flat",
                "prepend-icon": "mdi-content-save",
                loading: saving.value,
                onClick: saveConfig
              }, {
                default: _withCtx(() => [..._cache[30] || (_cache[30] = [
                  _createTextVNode("保存", -1)
                ])]),
                _: 1
              }, 8, ["loading"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_dialog, {
            modelValue: browseOpen.value,
            "onUpdate:modelValue": _cache[22] || (_cache[22] = ($event) => browseOpen.value = $event),
            "max-width": "680",
            scrollable: ""
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_card, null, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card_title, { class: "text-body-2" }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 浏览目录 · " + _toDisplayString(browseTarget.value === "library" ? "目标库目录" : "扫描目录"), 1)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_card_text, { style: { "min-height": "300px" } }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_4, [
                        _createVNode(_component_v_btn, {
                          variant: "text",
                          size: "small",
                          "prepend-icon": "mdi-arrow-up",
                          disabled: !parentPath.value || browseLoading.value,
                          onClick: _cache[17] || (_cache[17] = ($event) => goPath(parentPath.value))
                        }, {
                          default: _withCtx(() => [..._cache[32] || (_cache[32] = [
                            _createTextVNode("上级", -1)
                          ])]),
                          _: 1
                        }, 8, ["disabled"]),
                        _createVNode(_component_v_text_field, {
                          modelValue: pathInput.value,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = ($event) => pathInput.value = $event),
                          density: "compact",
                          variant: "outlined",
                          "hide-details": "",
                          placeholder: "输入绝对路径后回车",
                          class: "sdbo-grow",
                          onKeyup: _cache[19] || (_cache[19] = _withKeys(($event) => goPath(pathInput.value), ["enter"]))
                        }, null, 8, ["modelValue"]),
                        _createVNode(_component_v_btn, {
                          variant: "text",
                          size: "small",
                          disabled: browseLoading.value,
                          onClick: _cache[20] || (_cache[20] = ($event) => goPath(pathInput.value))
                        }, {
                          default: _withCtx(() => [..._cache[33] || (_cache[33] = [
                            _createTextVNode("前往", -1)
                          ])]),
                          _: 1
                        }, 8, ["disabled"])
                      ]),
                      browseLoading.value ? (_openBlock(), _createBlock(_component_v_progress_linear, {
                        key: 0,
                        indeterminate: "",
                        color: "primary",
                        class: "mt-2"
                      })) : _createCommentVNode("", true),
                      browseMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
                        key: 1,
                        type: "info",
                        variant: "tonal",
                        density: "compact",
                        class: "mt-2"
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(browseMessage.value), 1)
                        ]),
                        _: 1
                      })) : _createCommentVNode("", true),
                      browseEntries.value.length ? (_openBlock(), _createBlock(_component_v_list, {
                        key: 2,
                        density: "compact",
                        class: "mt-2 sdbo-browse-list"
                      }, {
                        default: _withCtx(() => [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(browseEntries.value, (entry) => {
                            return _openBlock(), _createBlock(_component_v_list_item, {
                              key: entry.value,
                              onClick: ($event) => goPath(entry.value)
                            }, {
                              prepend: _withCtx(() => [
                                _createVNode(_component_v_icon, {
                                  icon: "mdi-folder",
                                  size: "18",
                                  class: "mr-2"
                                })
                              ]),
                              default: _withCtx(() => [
                                _createVNode(_component_v_list_item_title, { class: "text-body-2" }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(entry.title), 1)
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _: 2
                            }, 1032, ["onClick"]);
                          }), 128))
                        ]),
                        _: 1
                      })) : !browseLoading.value && !browseMessage.value ? (_openBlock(), _createElementBlock("div", _hoisted_5, " 该目录下没有子目录，可直接选它，或输入更深的路径。 ")) : _createCommentVNode("", true),
                      _createElementVNode("div", _hoisted_6, "当前：" + _toDisplayString(currentPath.value || "（未进入）"), 1)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_card_actions, null, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        variant: "text",
                        onClick: _cache[21] || (_cache[21] = ($event) => browseOpen.value = false)
                      }, {
                        default: _withCtx(() => [..._cache[34] || (_cache[34] = [
                          _createTextVNode("取消", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_spacer),
                      _createVNode(_component_v_btn, {
                        color: "primary",
                        variant: "flat",
                        disabled: !currentPath.value || browseLoading.value,
                        onClick: confirmBrowse
                      }, {
                        default: _withCtx(() => [..._cache[35] || (_cache[35] = [
                          _createTextVNode("选定此目录", -1)
                        ])]),
                        _: 1
                      }, 8, ["disabled"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _: 1
      });
    };
  }
});

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-6ca6c23a"]]);

export { Config as default };
