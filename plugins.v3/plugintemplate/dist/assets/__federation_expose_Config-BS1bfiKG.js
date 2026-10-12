import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "pt-plugin-root pa-2" };
const _hoisted_2 = { class: "d-flex align-center mb-3" };
const _hoisted_3 = { class: "d-flex" };
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
      cron: "0 */6 * * *",
      notify: false,
      message: "Hello MoviePilot",
      max_records: 50,
      onlyonce: false
    };
    const local = reactive({ ...defaults });
    const cronPresets = [
      { label: "每 30 分钟", value: "*/30 * * * *" },
      { label: "每 1 小时", value: "0 * * * *" },
      { label: "每 6 小时", value: "0 */6 * * *" },
      { label: "每天 03:00", value: "0 3 * * *" },
      { label: "每周一 03:00", value: "0 3 * * 1" },
      { label: "每月 1 日 03:00", value: "0 3 1 * *" }
    ];
    const cronPreset = computed({
      get: () => cronPresets.some((item) => item.value === local.cron) ? local.cron : "",
      set: (value) => {
        if (value) local.cron = value;
      }
    });
    function saveConfig() {
      saving.value = true;
      emit("save", JSON.parse(JSON.stringify(local)));
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
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_checkbox = _resolveComponent("v-checkbox");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-4"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cog-outline",
                class: "mr-2"
              }),
              _cache[9] || (_cache[9] = _createElementVNode("h3", { class: "ma-0" }, "插件开发模板 · 设置", -1)),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                icon: "mdi-close",
                variant: "text",
                size: "small",
                title: "关闭",
                onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
              })
            ]),
            _createVNode(_component_v_switch, {
              modelValue: local.enabled,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => local.enabled = $event),
              label: "启用插件",
              color: "primary",
              "hide-details": "",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_text_field, {
              modelValue: local.message,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => local.message = $event),
              label: "示例文本",
              hint: "业务代码可将其替换为真实配置项",
              "persistent-hint": "",
              density: "comfortable",
              class: "mb-4"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_select, {
                      modelValue: cronPreset.value,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => cronPreset.value = $event),
                      items: cronPresets,
                      "item-title": "label",
                      "item-value": "value",
                      label: "定时周期预设",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  md: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.cron,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => local.cron = $event),
                      label: "cron 表达式",
                      hint: "5 段式，例如 0 */6 * * * 表示每 6 小时",
                      "persistent-hint": "",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_text_field, {
              modelValue: local.max_records,
              "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => local.max_records = $event),
              modelModifiers: { number: true },
              type: "number",
              label: "执行记录保留条数",
              min: "5",
              max: "500",
              density: "comfortable",
              class: "mt-4"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_switch, {
              modelValue: local.notify,
              "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => local.notify = $event),
              label: "任务完成后发送系统通知",
              color: "primary",
              "hide-details": ""
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_checkbox, {
              modelValue: local.onlyonce,
              "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => local.onlyonce = $event),
              label: "保存后立即执行一次",
              "hide-details": "",
              density: "compact",
              class: "mb-3"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_alert, {
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "mb-3"
            }, {
              default: _withCtx(() => [..._cache[10] || (_cache[10] = [
                _createTextVNode(" 保存由宿主完成：本组件只向宿主抛出 ", -1),
                _createElementVNode("code", null, "save", -1),
                _createTextVNode(" 事件， 宿主会调用 ", -1),
                _createElementVNode("code", null, "api.put('plugin/{id}', cfg)", -1),
                _createTextVNode(" 持久化并重新初始化插件。 ", -1)
              ])]),
              _: 1
            }),
            _createElementVNode("div", _hoisted_3, [
              _createVNode(_component_v_btn, {
                color: "primary",
                loading: saving.value,
                onClick: saveConfig
              }, {
                default: _withCtx(() => [..._cache[11] || (_cache[11] = [
                  _createTextVNode("保存配置", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              _createVNode(_component_v_btn, {
                variant: "text",
                class: "ml-2",
                onClick: _cache[8] || (_cache[8] = ($event) => emit("switch"))
              }, {
                default: _withCtx(() => [..._cache[12] || (_cache[12] = [
                  _createTextVNode("查看详情", -1)
                ])]),
                _: 1
              })
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-919b3bb8"]]);

export { Config as default };
