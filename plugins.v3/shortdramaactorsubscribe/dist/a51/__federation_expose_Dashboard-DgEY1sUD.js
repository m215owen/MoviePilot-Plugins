import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { d as fetchStatus, _ as _export_sfc } from './_plugin-vue_export-helper-Clm0RiNn.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,Fragment:_Fragment,withCtx:_withCtx} = await importShared('vue');

const _hoisted_1 = { class: "sdas-root sdas-dash" };
const _hoisted_2 = { class: "d-flex align-center pa-3 pb-1" };
const _hoisted_3 = { class: "px-3 pb-3" };
const _hoisted_4 = {
  key: 0,
  class: "text-medium-emphasis text-body-2"
};
const _hoisted_5 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "12px" }
};
const _hoisted_6 = { class: "text-caption" };
const _hoisted_7 = { class: "text-caption" };
const _hoisted_8 = { class: "text-caption" };
const _hoisted_9 = {
  key: 0,
  class: "text-caption"
};
const _hoisted_10 = {
  key: 0,
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "12px" }
};
const _hoisted_11 = {
  class: "text-caption",
  title: "自建订阅搜索：全分类补搜 + 择优下载"
};
const _hoisted_12 = {
  key: 1,
  class: "text-caption sdas-dim"
};
const _hoisted_13 = {
  key: 2,
  class: "text-caption sdas-dim"
};
const {onMounted,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Dashboard",
  props: {
    api: {}
  },
  setup(__props) {
    const props = __props;
    const status = ref({});
    const loading = ref(false);
    const error = ref("");
    async function load() {
      loading.value = true;
      error.value = "";
      try {
        status.value = await fetchStatus(props) || {};
      } catch (err) {
        error.value = `加载失败：${err instanceof Error ? err.message : err}`;
      } finally {
        loading.value = false;
      }
    }
    onMounted(load);
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "flat",
          class: "sdas-dash-card"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_icon, {
                icon: "mdi-movie-open-star-outline",
                size: "20",
                class: "mr-2"
              }),
              _cache[0] || (_cache[0] = _createElementVNode("span", { class: "text-body-1" }, "短剧演员", -1)),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                icon: "mdi-refresh",
                variant: "text",
                size: "x-small",
                loading: loading.value,
                title: "刷新",
                onClick: load
              }, null, 8, ["loading"])
            ]),
            _createElementVNode("div", _hoisted_3, [
              error.value ? (_openBlock(), _createElementBlock("div", _hoisted_4, _toDisplayString(error.value), 1)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _createElementVNode("div", _hoisted_5, [
                  _createElementVNode("span", _hoisted_6, [
                    _cache[1] || (_cache[1] = _createTextVNode("演员 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(status.value.actors || 0), 1)
                  ]),
                  _createElementVNode("span", _hoisted_7, [
                    _cache[2] || (_cache[2] = _createTextVNode("作品 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(status.value.works || 0), 1)
                  ]),
                  _createElementVNode("span", _hoisted_8, [
                    _cache[3] || (_cache[3] = _createTextVNode("新作品 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(status.value.new_works || 0), 1)
                  ]),
                  status.value.auto_subscribe ? (_openBlock(), _createElementBlock("span", _hoisted_9, [
                    _cache[4] || (_cache[4] = _createTextVNode(" 已自动订阅 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(status.value.auto_subscribed || 0), 1)
                  ])) : _createCommentVNode("", true)
                ]),
                status.value.sub_engine === "self" ? (_openBlock(), _createElementBlock("div", _hoisted_10, [
                  _createElementVNode("span", _hoisted_11, [
                    _cache[8] || (_cache[8] = _createTextVNode(" 自建订阅 已下 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(status.value.sub_downloaded || 0), 1),
                    status.value.sub_noresult ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _cache[5] || (_cache[5] = _createTextVNode(" · 暂无 ", -1)),
                      _createElementVNode("b", null, _toDisplayString(status.value.sub_noresult), 1)
                    ], 64)) : _createCommentVNode("", true),
                    status.value.sub_failed ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _cache[6] || (_cache[6] = _createTextVNode(" · 失败 ", -1)),
                      _createElementVNode("b", null, _toDisplayString(status.value.sub_failed), 1)
                    ], 64)) : _createCommentVNode("", true),
                    status.value.sub_skipped ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                      _cache[7] || (_cache[7] = _createTextVNode(" · 跳过 ", -1)),
                      _createElementVNode("b", null, _toDisplayString(status.value.sub_skipped), 1)
                    ], 64)) : _createCommentVNode("", true),
                    _cache[9] || (_cache[9] = _createTextVNode(" · 待搜 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(status.value.sub_pending || 0), 1)
                  ])
                ])) : _createCommentVNode("", true),
                status.value.last_refresh ? (_openBlock(), _createElementBlock("div", _hoisted_12, " 上次刷新：" + _toDisplayString(status.value.last_refresh), 1)) : (_openBlock(), _createElementBlock("div", _hoisted_13, " 还没刷新过（可在插件设置里勾「保存后立即刷新一次」） "))
              ], 64))
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-529b4ad6"]]);

export { Dashboard as default };
