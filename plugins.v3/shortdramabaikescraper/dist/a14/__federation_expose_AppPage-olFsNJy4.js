import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _sfc_main$1 } from './PanelTabs.vue_vue_type_script_setup_true_lang-B0xvHErA.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "sdbs-root pa-4" };
const _hoisted_2 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "AppPage",
  props: {
    api: {},
    pluginId: {},
    navKey: {}
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_icon, {
            icon: "mdi-television-classic",
            class: "mr-1"
          }),
          _cache[2] || (_cache[2] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "短剧百科刮削源", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal",
            color: "primary"
          }, {
            default: _withCtx(() => [..._cache[0] || (_cache[0] = [
              _createTextVNode("djbaike", -1)
            ])]),
            _: 1
          }),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal"
          }, {
            default: _withCtx(() => [..._cache[1] || (_cache[1] = [
              _createTextVNode("duanjubaike.net", -1)
            ])]),
            _: 1
          }),
          _createVNode(_component_v_spacer),
          _cache[3] || (_cache[3] = _createElementVNode("span", { class: "text-caption sdbs-dim" }, " ID 库与缓存是来源级全局数据（不按虚拟分身隔离） ", -1))
        ]),
        _createVNode(_sfc_main$1, {
          api: props.api
        }, null, 8, ["api"])
      ]);
    };
  }
});

export { _sfc_main as default };
