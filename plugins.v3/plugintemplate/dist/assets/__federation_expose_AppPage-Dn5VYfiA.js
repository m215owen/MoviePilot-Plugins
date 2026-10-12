import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { r as resolveApi, A as API_BASE, u as unwrap } from './api-BKD28MM4.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,createBlock:_createBlock} = await importShared('vue');

const _hoisted_1 = { class: "pt-plugin-root pa-4" };
const _hoisted_2 = { class: "d-flex align-center mb-3" };
const _hoisted_3 = { class: "text-h6" };
const _hoisted_4 = { class: "text-body-2" };
const _hoisted_5 = { class: "text-body-2" };
const _hoisted_6 = {
  key: 0,
  class: "text-medium-emphasis"
};
const _hoisted_7 = { class: "text-body-2" };
const {onMounted,reactive,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "AppPage",
  props: {
    api: {},
    nativeSubscribe: { type: Function },
    navKey: {},
    pluginId: {}
  },
  emits: ["action"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const loading = ref(false);
    const running = ref(false);
    const records = ref([]);
    const config = reactive({
      enabled: false,
      cron: "",
      notify: false,
      message: "",
      max_records: 50
    });
    async function load() {
      const api = resolveApi(props);
      if (!api) return;
      loading.value = true;
      try {
        const [cfgRaw, recRaw] = await Promise.all([
          api.get(`${API_BASE}/config`),
          api.get(`${API_BASE}/records`, { params: { limit: 100 } })
        ]);
        const cfg = unwrap(cfgRaw);
        if (cfg?.success && cfg.data) Object.assign(config, cfg.data);
        const rec = unwrap(recRaw);
        if (rec?.success) records.value = rec.data || [];
      } catch (err) {
        console.warn("[PluginTemplate] 全页加载失败", err);
      } finally {
        loading.value = false;
      }
    }
    async function runNow() {
      const api = resolveApi(props);
      if (!api) return;
      running.value = true;
      try {
        await api.post(`${API_BASE}/run`);
        await load();
        emit("action");
      } finally {
        running.value = false;
      }
    }
    async function clearRecords() {
      const api = resolveApi(props);
      if (!api) return;
      await api.post(`${API_BASE}/clear`);
      await load();
      emit("action");
    }
    onMounted(load);
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_table = _resolveComponent("v-table");
      const _component_v_card_text = _resolveComponent("v-card-text");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_icon, {
            icon: "mdi-puzzle-outline",
            class: "mr-2"
          }),
          _cache[0] || (_cache[0] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "插件开发模板 · 全页视图", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal",
            class: "ml-3"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(__props.pluginId || "PluginTemplate") + " / " + _toDisplayString(__props.navKey || "main"), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            icon: "mdi-refresh",
            loading: loading.value,
            onClick: load
          }, null, 8, ["loading"])
        ]),
        _createVNode(_component_v_row, {
          dense: "",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_col, {
              cols: "12",
              sm: "4"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "tonal",
                  class: "pa-3"
                }, {
                  default: _withCtx(() => [
                    _cache[1] || (_cache[1] = _createElementVNode("div", { class: "text-caption" }, "累计执行", -1)),
                    _createElementVNode("div", _hoisted_3, _toDisplayString(config.run_count ?? records.value.length), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_col, {
              cols: "12",
              sm: "4"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "tonal",
                  class: "pa-3"
                }, {
                  default: _withCtx(() => [
                    _cache[2] || (_cache[2] = _createElementVNode("div", { class: "text-caption" }, "最近执行", -1)),
                    _createElementVNode("div", _hoisted_4, _toDisplayString(records.value[0]?.time || "暂无记录"), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_col, {
              cols: "12",
              sm: "4"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "tonal",
                  class: "pa-3"
                }, {
                  default: _withCtx(() => [
                    _cache[3] || (_cache[3] = _createElementVNode("div", { class: "text-caption" }, "插件状态", -1)),
                    _createElementVNode("div", _hoisted_5, _toDisplayString(config.enabled ? "已启用" : "未启用"), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_card, { variant: "outlined" }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, { class: "d-flex align-center flex-wrap" }, {
              default: _withCtx(() => [
                _cache[6] || (_cache[6] = _createTextVNode(" 执行记录 ", -1)),
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  size: "small",
                  color: "primary",
                  variant: "tonal",
                  "prepend-icon": "mdi-play",
                  loading: running.value,
                  onClick: runNow
                }, {
                  default: _withCtx(() => [..._cache[4] || (_cache[4] = [
                    _createTextVNode(" 立即执行 ", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  class: "ml-2",
                  "prepend-icon": "mdi-delete-outline",
                  onClick: clearRecords
                }, {
                  default: _withCtx(() => [..._cache[5] || (_cache[5] = [
                    _createTextVNode(" 清空 ", -1)
                  ])]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_text, null, {
              default: _withCtx(() => [
                !records.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_6, "暂无执行记录。")) : (_openBlock(), _createBlock(_component_v_table, {
                  key: 1,
                  density: "comfortable"
                }, {
                  default: _withCtx(() => [
                    _cache[7] || (_cache[7] = _createElementVNode("thead", null, [
                      _createElementVNode("tr", null, [
                        _createElementVNode("th", null, "时间"),
                        _createElementVNode("th", null, "触发方式"),
                        _createElementVNode("th", null, "结果"),
                        _createElementVNode("th", null, "耗时"),
                        _createElementVNode("th", null, "说明")
                      ])
                    ], -1)),
                    _createElementVNode("tbody", null, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(records.value, (item, index) => {
                        return _openBlock(), _createElementBlock("tr", { key: index }, [
                          _createElementVNode("td", null, _toDisplayString(item.time), 1),
                          _createElementVNode("td", null, [
                            _createVNode(_component_v_chip, {
                              size: "x-small",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(item.trigger), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _createElementVNode("td", null, [
                            _createVNode(_component_v_icon, {
                              icon: item.success ? "mdi-check-circle" : "mdi-alert-circle",
                              color: item.success ? "success" : "error",
                              size: "18"
                            }, null, 8, ["icon", "color"])
                          ]),
                          _createElementVNode("td", null, _toDisplayString(item.elapsed_ms) + " ms", 1),
                          _createElementVNode("td", _hoisted_7, _toDisplayString(item.detail), 1)
                        ]);
                      }), 128))
                    ])
                  ]),
                  _: 1
                }))
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]);
    };
  }
});

const AppPage = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-371d35a6"]]);

export { AppPage as default };
