import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { P as PLUGIN_ID } from './api-BI6_AAQl.js';
import { _ as _sfc_main$1 } from './PanelTabs.vue_vue_type_script_setup_true_lang-B0xvHErA.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "sdbs-root pa-2" };
const _hoisted_2 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const {computed} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Page",
  props: {
    api: {}
  },
  setup(__props) {
    const props = __props;
    const appHref = computed(() => {
      const base = typeof window === "undefined" ? "" : window.location.href.split("#")[0];
      return `${base}#/plugin-app/${PLUGIN_ID}/main`;
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_icon, {
            icon: "mdi-television-classic",
            class: "mr-1"
          }),
          _cache[2] || (_cache[2] = _createElementVNode("h3", { class: "text-subtitle-1 ma-0" }, "短剧百科刮削源", -1)),
          _createVNode(_component_v_chip, {
            size: "x-small",
            variant: "tonal",
            color: "primary"
          }, {
            default: _withCtx(() => [..._cache[0] || (_cache[0] = [
              _createTextVNode("djbaike", -1)
            ])]),
            _: 1
          }),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_btn, {
            size: "x-small",
            variant: "text",
            "prepend-icon": "mdi-open-in-new",
            href: appHref.value,
            target: "_blank",
            rel: "noreferrer noopener",
            title: "在独立页面打开（书签可存）"
          }, {
            default: _withCtx(() => [..._cache[1] || (_cache[1] = [
              _createTextVNode(" 全页打开 ", -1)
            ])]),
            _: 1
          }, 8, ["href"])
        ]),
        _createVNode(_sfc_main$1, {
          api: props.api
        }, null, 8, ["api"])
      ]);
    };
  }
});

export { _sfc_main as default };
