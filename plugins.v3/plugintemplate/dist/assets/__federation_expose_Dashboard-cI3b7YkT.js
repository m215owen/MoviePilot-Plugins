import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { r as resolveApi, A as API_BASE, u as unwrap } from './api-BKD28MM4.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode,Fragment:_Fragment,vShow:_vShow,withDirectives:_withDirectives,mergeProps:_mergeProps} = await importShared('vue');

const _hoisted_1 = { class: "pt-plugin-root" };
const _hoisted_2 = {
  key: 0,
  class: "text-medium-emphasis text-body-2"
};
const _hoisted_3 = { class: "d-flex align-center mb-1" };
const _hoisted_4 = { class: "text-h6" };
const _hoisted_5 = { class: "text-caption" };
const _hoisted_6 = {
  key: 0,
  class: "text-caption text-medium-emphasis mt-1"
};
const _hoisted_7 = { class: "pt-drag-hint" };
const {computed,onMounted,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Dashboard",
  props: {
    config: {},
    allowRefresh: { type: Boolean },
    api: {},
    pluginId: {}
  },
  setup(__props) {
    const props = __props;
    const loading = ref(false);
    const records = ref([]);
    const title = computed(() => "插件开发模板");
    const enabled = computed(() => props.config?.enabled !== false);
    const total = computed(() => props.config?.run_count ?? records.value.length);
    const lastTime = computed(() => records.value[0]?.time || "暂无记录");
    const lastDetail = computed(() => records.value[0]?.detail || "");
    async function load() {
      const api = resolveApi(props);
      if (!api) return;
      loading.value = true;
      try {
        const raw = await api.get(`${API_BASE}/records`, { params: { limit: 5 } });
        const res = unwrap(raw);
        if (res?.success) records.value = res.data || [];
      } catch (err) {
        console.warn("[PluginTemplate] 仪表板加载失败", err);
      } finally {
        loading.value = false;
      }
    }
    onMounted(load);
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_hover = _resolveComponent("v-hover");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_hover, null, {
          default: _withCtx(({ isHovering, props: hoverProps }) => [
            _createVNode(_component_v_card, _mergeProps(hoverProps, { variant: "flat" }), {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, {
                      icon: "mdi-puzzle-outline",
                      size: "20",
                      class: "mr-2"
                    }),
                    _createTextVNode(" " + _toDisplayString(title.value) + " ", 1),
                    _createVNode(_component_v_spacer),
                    __props.allowRefresh ? (_openBlock(), _createBlock(_component_v_btn, {
                      key: 0,
                      icon: "mdi-refresh",
                      variant: "text",
                      size: "x-small",
                      loading: loading.value,
                      onClick: load
                    }, null, 8, ["loading"])) : _createCommentVNode("", true)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    !enabled.value ? (_openBlock(), _createElementBlock("div", _hoisted_2, " 插件未启用。 ")) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _createElementVNode("div", _hoisted_3, [
                        _cache[0] || (_cache[0] = _createElementVNode("span", { class: "text-caption mr-2" }, "累计执行", -1)),
                        _createElementVNode("span", _hoisted_4, _toDisplayString(total.value), 1)
                      ]),
                      _createElementVNode("div", _hoisted_5, "最近执行：" + _toDisplayString(lastTime.value), 1),
                      lastDetail.value ? (_openBlock(), _createElementBlock("div", _hoisted_6, _toDisplayString(lastDetail.value), 1)) : _createCommentVNode("", true)
                    ], 64))
                  ]),
                  _: 1
                }),
                _withDirectives(_createElementVNode("div", _hoisted_7, [
                  _createVNode(_component_v_icon, {
                    icon: "mdi-drag",
                    size: "18"
                  })
                ], 512), [
                  [_vShow, isHovering]
                ])
              ]),
              _: 2
            }, 1040)
          ]),
          _: 1
        })
      ]);
    };
  }
});

const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-2244bbd5"]]);

export { Dashboard as default };
