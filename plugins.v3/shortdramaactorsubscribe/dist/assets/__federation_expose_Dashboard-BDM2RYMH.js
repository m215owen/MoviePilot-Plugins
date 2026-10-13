import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { f as formatTime, r as resolveApi, a as fetchStatus, P as PLUGIN_ID, b as runOnce, _ as _export_sfc } from './_plugin-vue_export-helper-BPSYN_be.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass,unref:_unref,withCtx:_withCtx} = await importShared('vue');

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
  class: "text-caption sdas-dim"
};
const _hoisted_10 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_11 = ["title"];
const _hoisted_12 = { class: "text-caption sdas-dim ml-2" };
const _hoisted_13 = { class: "text-caption sdas-dim" };
const _hoisted_14 = { class: "text-caption sdas-dim mt-2" };
const {computed,onMounted,ref} = await importShared('vue');
const LIMIT = 4;
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
    const running = ref(false);
    const payload = ref(null);
    const enabled = computed(() => payload.value?.enabled ?? props.config?.enabled ?? false);
    const summary = computed(() => payload.value?.summary || {});
    const latest = computed(() => (payload.value?.ledger || []).slice(0, LIMIT));
    function apply(data) {
      payload.value = data;
    }
    async function load() {
      const api = resolveApi(props);
      if (!api) return;
      try {
        const data = await fetchStatus(api);
        if (data) apply(data);
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 仪表板加载失败`, err);
      }
    }
    async function doRun() {
      const api = resolveApi(props);
      if (!api) return;
      running.value = true;
      try {
        const before = String(summary.value.last_run || "");
        await runOnce(api, apply, before);
        await load();
      } finally {
        running.value = false;
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
                icon: "mdi-movie-star-outline",
                size: "20",
                class: "mr-2"
              }),
              _cache[0] || (_cache[0] = _createElementVNode("span", { class: "text-body-1" }, "短剧演员订阅", -1)),
              _createVNode(_component_v_spacer),
              props.allowRefresh !== false ? (_openBlock(), _createBlock(_component_v_btn, {
                key: 0,
                icon: "mdi-refresh",
                variant: "text",
                size: "x-small",
                loading: running.value,
                title: "立即运行一轮",
                onClick: doRun
              }, null, 8, ["loading"])) : _createCommentVNode("", true)
            ]),
            _createElementVNode("div", _hoisted_3, [
              !enabled.value ? (_openBlock(), _createElementBlock("div", _hoisted_4, " 插件未启用或尚未配置演员 / 搜索站点。 ")) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _createElementVNode("div", _hoisted_5, [
                  _createElementVNode("span", _hoisted_6, [
                    _cache[1] || (_cache[1] = _createTextVNode("演员 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(summary.value.actor_count || 0), 1)
                  ]),
                  _createElementVNode("span", _hoisted_7, [
                    _cache[2] || (_cache[2] = _createTextVNode("已下载 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(summary.value.downloaded_count || 0), 1)
                  ]),
                  _createElementVNode("span", _hoisted_8, [
                    _cache[3] || (_cache[3] = _createTextVNode("已整理 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(summary.value.organized_count || 0), 1)
                  ]),
                  summary.value.cooldown_count ? (_openBlock(), _createElementBlock("span", _hoisted_9, " 冷却 " + _toDisplayString(summary.value.cooldown_count), 1)) : _createCommentVNode("", true)
                ]),
                !latest.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_10, " 还没有下载记录，点右上角运行一轮。 ")) : _createCommentVNode("", true),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(latest.value, (row) => {
                  return _openBlock(), _createElementBlock("div", {
                    key: row.key,
                    class: "d-flex align-center py-1"
                  }, [
                    _createElementVNode("span", {
                      class: _normalizeClass(["sdas-dot", row.organized ? "sdas-dot-done" : ""])
                    }, null, 2),
                    _createElementVNode("span", {
                      class: "sdas-name",
                      title: row.torrent_title || row.title
                    }, _toDisplayString(row.title), 9, _hoisted_11),
                    _createElementVNode("span", _hoisted_12, _toDisplayString(row.year || "—"), 1),
                    _createVNode(_component_v_spacer),
                    _createElementVNode("span", _hoisted_13, _toDisplayString(row.organized ? "已整理" : "已下载"), 1)
                  ]);
                }), 128)),
                _createElementVNode("div", _hoisted_14, _toDisplayString(summary.value.actor_count || 0) + " 位演员｜" + _toDisplayString(_unref(formatTime)(summary.value.last_run)), 1)
              ], 64))
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-d4bc753a"]]);

export { Dashboard as default };
