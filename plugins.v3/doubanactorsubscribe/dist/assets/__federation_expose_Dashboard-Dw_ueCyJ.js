import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _sfc_main$1 } from './SearchResourceButton.vue_vue_type_script_setup_true_lang-BvAsOj-z.js';
import { m as mergeWorks, s as sortWorks, w as workKey, e as formatTime, r as resolveApi, A as API_BASE, u as unwrap, f as fetchSubscribedKeys, P as PLUGIN_ID, a as waitForRefresh, b as submitSubscribe, c as unsubscribeWork, i as ignoreWork, _ as _export_sfc } from './_plugin-vue_export-helper-DpVJBdwh.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,withCtx:_withCtx,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,renderList:_renderList,Fragment:_Fragment,unref:_unref,normalizeClass:_normalizeClass,vShow:_vShow,withDirectives:_withDirectives,mergeProps:_mergeProps} = await importShared('vue');

const _hoisted_1 = { class: "das-root das-dash" };
const _hoisted_2 = {
  key: 0,
  class: "text-medium-emphasis text-body-2"
};
const _hoisted_3 = {
  class: "d-flex align-center mb-2",
  style: { "gap": "12px" }
};
const _hoisted_4 = { class: "text-caption" };
const _hoisted_5 = { class: "text-caption" };
const _hoisted_6 = { class: "text-caption" };
const _hoisted_7 = { class: "das-new" };
const _hoisted_8 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_9 = ["title"];
const _hoisted_10 = { class: "text-caption das-dim ml-2" };
const _hoisted_11 = { class: "text-caption das-dim mt-2" };
const _hoisted_12 = { class: "das-drag-hint" };
const {computed,inject,onMounted,ref} = await importShared('vue');
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
    const toast = inject("moviepilot:toast", null);
    const loading = ref(false);
    const refreshing = ref(false);
    const pendingKey = ref("");
    const payload = ref(null);
    const subscribedKeys = ref([]);
    const enabled = computed(() => payload.value?.enabled ?? props.config?.enabled !== false);
    const stats = computed(() => ({
      actor_count: payload.value?.actor_count ?? 0,
      work_count: payload.value?.work_count ?? 0,
      new_count: payload.value?.new_count ?? 0,
      updated_at: payload.value?.updated_at || ""
    }));
    const flattened = computed(() => {
      const works = mergeWorks(payload.value?.actors || []);
      return sortWorks(works, "new").map((work) => ({
        actor: (work.actorNames || [])[0] || "—",
        work
      }));
    });
    const latest = computed(() => flattened.value.slice(0, LIMIT));
    const item0 = computed(() => ({ actor: latest.value[0]?.actor || "未配置演员" }));
    function isSubscribed(work) {
      return subscribedKeys.value.includes(workKey(work));
    }
    function notify(type, message) {
      const handler = toast && toast[type];
      if (typeof handler === "function") {
        handler.call(toast, message);
        return;
      }
      console.warn(`[${PLUGIN_ID}] ${message}`);
    }
    async function load() {
      const api = resolveApi(props);
      if (!api) return;
      loading.value = true;
      try {
        const raw = await api.get(`${API_BASE}/works`);
        const res = unwrap(raw);
        if (res?.success && res.data) payload.value = res.data;
        subscribedKeys.value = await fetchSubscribedKeys(api);
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 仪表板加载失败`, err);
      } finally {
        loading.value = false;
      }
    }
    async function refresh() {
      const api = resolveApi(props);
      if (!api) return;
      refreshing.value = true;
      try {
        const raw = await api.post(`${API_BASE}/run`);
        const res = unwrap(raw);
        if (res?.data) payload.value = res.data;
        subscribedKeys.value = await fetchSubscribedKeys(api);
        if (payload.value?.refreshing || payload.value?.pending_refresh) {
          waitForRefresh(api, (data) => {
            payload.value = data;
          });
        }
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 仪表板刷新失败`, err);
      } finally {
        refreshing.value = false;
      }
    }
    async function subscribe(work) {
      const api = resolveApi(props);
      if (!api) return;
      const key = workKey(work);
      pendingKey.value = key;
      try {
        const res = await submitSubscribe(api, work, {
          savePath: payload.value?.subscribe_save_path || props.config?.subscribe_save_path || "",
          downloader: payload.value?.subscribe_downloader || props.config?.subscribe_downloader || "",
          sites: payload.value?.subscribe_sites || props.config?.subscribe_sites || []
        });
        if (res.ok) {
          if (!subscribedKeys.value.includes(key)) subscribedKeys.value.push(key);
          notify("success", res.message);
        } else {
          notify("error", `${work.title} 订阅失败：${res.message}`);
        }
      } finally {
        pendingKey.value = "";
      }
    }
    async function unsubscribe(work) {
      const api = resolveApi(props);
      if (!api) return;
      const key = workKey(work);
      pendingKey.value = key;
      try {
        const res = await unsubscribeWork(api, work);
        if (res.ok) {
          subscribedKeys.value = subscribedKeys.value.filter((item) => item !== key);
          notify("success", res.message);
        } else {
          notify("error", `${work.title} 取消订阅失败：${res.message}`);
        }
      } finally {
        pendingKey.value = "";
      }
    }
    async function ignore(work) {
      const api = resolveApi(props);
      if (!api) return;
      const res = await ignoreWork(api, work);
      notify(res.ok ? "success" : "error", res.message);
      if (res.ok) await load();
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
            _createVNode(_component_v_card, _mergeProps(hoverProps, {
              variant: "flat",
              class: "das-dash-card"
            }), {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, {
                      icon: "mdi-account-star-outline",
                      size: "20",
                      class: "mr-2"
                    }),
                    _cache[0] || (_cache[0] = _createElementVNode("span", { class: "text-body-1" }, "豆瓣演员订阅", -1)),
                    _createVNode(_component_v_spacer),
                    __props.allowRefresh ? (_openBlock(), _createBlock(_component_v_btn, {
                      key: 0,
                      icon: "mdi-refresh",
                      variant: "text",
                      size: "x-small",
                      loading: refreshing.value,
                      onClick: refresh
                    }, null, 8, ["loading"])) : _createCommentVNode("", true)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    !enabled.value ? (_openBlock(), _createElementBlock("div", _hoisted_2, " 插件未启用或尚未配置演员。 ")) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _createElementVNode("div", _hoisted_3, [
                        _createElementVNode("span", _hoisted_4, [
                          _cache[1] || (_cache[1] = _createTextVNode("演员 ", -1)),
                          _createElementVNode("b", null, _toDisplayString(stats.value.actor_count), 1)
                        ]),
                        _createElementVNode("span", _hoisted_5, [
                          _cache[2] || (_cache[2] = _createTextVNode("作品 ", -1)),
                          _createElementVNode("b", null, _toDisplayString(stats.value.work_count), 1)
                        ]),
                        _createElementVNode("span", _hoisted_6, [
                          _cache[3] || (_cache[3] = _createTextVNode(" 新作品 ", -1)),
                          _createElementVNode("b", _hoisted_7, _toDisplayString(stats.value.new_count), 1)
                        ])
                      ]),
                      !latest.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_8, " 暂无作品数据，点击右上角刷新。 ")) : _createCommentVNode("", true),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(latest.value, (item) => {
                        return _openBlock(), _createElementBlock("div", {
                          key: _unref(workKey)(item.work),
                          class: "d-flex align-center py-1"
                        }, [
                          _createElementVNode("span", {
                            class: _normalizeClass(["das-dot", item.work.is_new ? "das-dot-new" : ""])
                          }, null, 2),
                          _createElementVNode("span", {
                            class: "das-name",
                            title: item.work.title
                          }, _toDisplayString(item.work.title), 9, _hoisted_9),
                          _createElementVNode("span", _hoisted_10, _toDisplayString(item.work.year || "—"), 1),
                          _createVNode(_component_v_spacer),
                          _createVNode(_component_v_btn, {
                            size: "x-small",
                            variant: "text",
                            icon: isSubscribed(item.work) ? "mdi-close" : "mdi-plus",
                            color: isSubscribed(item.work) ? "error" : "primary",
                            loading: pendingKey.value === _unref(workKey)(item.work),
                            title: isSubscribed(item.work) ? "取消订阅" : "订阅",
                            onClick: ($event) => isSubscribed(item.work) ? unsubscribe(item.work) : subscribe(item.work)
                          }, null, 8, ["icon", "color", "loading", "title", "onClick"]),
                          _createVNode(_sfc_main$1, {
                            api: __props.api,
                            work: item.work,
                            size: "x-small",
                            variant: "text"
                          }, null, 8, ["api", "work"]),
                          _createVNode(_component_v_btn, {
                            size: "x-small",
                            variant: "text",
                            icon: "mdi-eye-off-outline",
                            title: "忽略这部作品：不再展示，也不会被自动订阅",
                            onClick: ($event) => ignore(item.work)
                          }, null, 8, ["onClick"])
                        ]);
                      }), 128)),
                      _createElementVNode("div", _hoisted_11, _toDisplayString(item0.value.actor) + " 等 " + _toDisplayString(stats.value.actor_count) + " 位演员｜" + _toDisplayString(_unref(formatTime)(stats.value.updated_at)), 1)
                    ], 64))
                  ]),
                  _: 1
                }),
                _withDirectives(_createElementVNode("div", _hoisted_12, [
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

const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-06b0071f"]]);

export { Dashboard as default };
