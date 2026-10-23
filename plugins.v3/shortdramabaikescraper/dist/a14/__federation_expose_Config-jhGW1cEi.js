import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { f as fetchConfig, s as saveConfig } from './api-BI6_AAQl.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "sdbs-root pa-2" };
const _hoisted_2 = { class: "d-flex align-center mb-2" };
const _hoisted_3 = {
  class: "d-flex align-center mt-5",
  style: { "gap": "8px" }
};
const _hoisted_4 = {
  key: 0,
  class: "text-caption sdbs-dim"
};
const {onMounted,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Config",
  props: {
    api: {}
  },
  emits: ["close", "saved"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const local = ref({ enabled: false });
    const loading = ref(false);
    const saving = ref(false);
    const saved = ref(false);
    const error = ref("");
    async function load() {
      loading.value = true;
      error.value = "";
      try {
        const config = await fetchConfig(props);
        local.value = {
          enabled: Boolean(config?.enabled)
        };
      } catch (err) {
        error.value = `读取配置失败：${err instanceof Error ? err.message : String(err)}`;
      } finally {
        loading.value = false;
      }
    }
    async function save() {
      saving.value = true;
      error.value = "";
      saved.value = false;
      try {
        const result = await saveConfig(props, {
          enabled: Boolean(local.value.enabled)
        });
        local.value = {
          enabled: Boolean(result?.enabled)
        };
        saved.value = true;
        emit("saved");
      } catch (err) {
        error.value = `保存失败：${err instanceof Error ? err.message : String(err)}`;
      } finally {
        saving.value = false;
      }
    }
    onMounted(() => {
      void load();
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_switch = _resolveComponent("v-switch");
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
              _cache[4] || (_cache[4] = _createElementVNode("h3", { class: "ma-0 text-subtitle-1" }, "短剧百科刮削源 · 设置", -1)),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                icon: "mdi-close",
                variant: "text",
                size: "small",
                title: "关闭",
                onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
              })
            ]),
            _cache[7] || (_cache[7] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-4" }, [
              _createTextVNode(" 把「短剧百科」(www.duanjubaike.net) 注册为媒体来源 "),
              _createElementVNode("span", { class: "sdbs-key" }, "djbaike"),
              _createTextVNode("：按片名检索 → 识别 → 订阅 / 刮削。 ")
            ], -1)),
            error.value ? (_openBlock(), _createBlock(_component_v_alert, {
              key: 0,
              type: "error",
              variant: "tonal",
              density: "compact",
              class: "mb-3"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(error.value), 1)
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            _cache[8] || (_cache[8] = _createElementVNode("div", { class: "text-subtitle-2 font-weight-bold" }, "运行", -1)),
            _createVNode(_component_v_divider, { class: "mt-1 mb-3" }),
            _createVNode(_component_v_switch, {
              modelValue: local.value.enabled,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => local.value.enabled = $event),
              label: "启用插件",
              color: "primary",
              density: "compact",
              "hide-details": "",
              loading: loading.value
            }, null, 8, ["modelValue", "loading"]),
            _createElementVNode("div", _hoisted_3, [
              saved.value ? (_openBlock(), _createElementBlock("span", _hoisted_4, "已保存")) : _createCommentVNode("", true),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                variant: "text",
                disabled: saving.value,
                onClick: _cache[2] || (_cache[2] = ($event) => emit("close"))
              }, {
                default: _withCtx(() => [..._cache[5] || (_cache[5] = [
                  _createTextVNode("取消", -1)
                ])]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode(_component_v_btn, {
                color: "primary",
                variant: "flat",
                loading: saving.value,
                disabled: loading.value,
                onClick: _cache[3] || (_cache[3] = ($event) => save())
              }, {
                default: _withCtx(() => [..._cache[6] || (_cache[6] = [
                  _createTextVNode(" 保存 ", -1)
                ])]),
                _: 1
              }, 8, ["loading", "disabled"])
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

export { _sfc_main as default };
