import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { W as WorkGrid } from './WorkGrid-8IKiiOmw.js';
import { w as workKey, r as resolveApi, A as API_BASE, u as unwrap, f as fetchSubscribedKeys, P as PLUGIN_ID, s as submitSubscribe, _ as _export_sfc } from './_plugin-vue_export-helper-CY9eCSTe.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');

const _hoisted_1 = { class: "das-root pa-4" };
const _hoisted_2 = {
  class: "d-flex align-center mb-3 flex-wrap",
  style: { "gap": "12px" }
};
const _hoisted_3 = { class: "text-caption" };
const _hoisted_4 = { class: "text-h6" };
const _hoisted_5 = {
  class: "d-flex align-center flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_6 = {
  class: "d-flex align-center flex-wrap mt-2",
  style: { "gap": "12px" }
};
const _hoisted_7 = {
  key: 2,
  class: "text-center text-medium-emphasis py-8"
};
const _hoisted_8 = { class: "das-actor-name" };
const _hoisted_9 = { class: "text-caption das-dim ml-2" };
const {computed,inject,onMounted,ref} = await importShared('vue');
const ALL_ACTORS = "__all__";
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
    const toast = inject("moviepilot:toast", null);
    const loading = ref(false);
    const refreshing = ref(false);
    const busy = ref(false);
    const pendingKey = ref("");
    const payload = ref(null);
    const subscribedKeys = ref([]);
    const actorFilter = ref(ALL_ACTORS);
    const typeFilter = ref("");
    const onlyNew = ref(false);
    const onlyUnsubscribed = ref(false);
    const sortMode = ref("year");
    const keyword = ref("");
    const actors = computed(() => payload.value?.actors || []);
    const statCards = computed(() => [
      { label: "演员", value: payload.value?.actor_count ?? actors.value.length },
      { label: "作品", value: payload.value?.work_count ?? 0 },
      { label: "新作品", value: payload.value?.new_count ?? 0 },
      { label: "累计刷新", value: payload.value?.run_count ?? 0 }
    ]);
    function isSubscribed(work) {
      return subscribedKeys.value.includes(workKey(work));
    }
    function newCount(actor) {
      return (actor.works || []).filter((work) => work.is_new).length;
    }
    function doubanPersonUrl(id) {
      return id ? `https://movie.douban.com/celebrity/${id}/` : "https://movie.douban.com/";
    }
    function matchWork(work) {
      if (typeFilter.value && work.type !== typeFilter.value) return false;
      if (onlyNew.value && !work.is_new) return false;
      if (onlyUnsubscribed.value && isSubscribed(work)) return false;
      return true;
    }
    function matchActor(actor) {
      if (actorFilter.value && actorFilter.value !== ALL_ACTORS) {
        if (actor.key !== actorFilter.value && actor.id !== actorFilter.value) return false;
      }
      const kw = keyword.value.trim().toLowerCase();
      if (!kw) return true;
      return String(actor.name || "").toLowerCase().includes(kw) || (actor.works || []).some((work) => work.title.toLowerCase().includes(kw));
    }
    const visibleActors = computed(() => {
      const kw = keyword.value.trim().toLowerCase();
      const filtering = Boolean(
        actorFilter.value && actorFilter.value !== ALL_ACTORS || typeFilter.value || onlyNew.value || onlyUnsubscribed.value
      );
      const result = [];
      for (const actor of actors.value) {
        if (!matchActor(actor)) continue;
        let works = (actor.works || []).filter((work) => {
          if (!matchWork(work)) return false;
          if (kw && !String(actor.name || "").toLowerCase().includes(kw)) {
            return work.title.toLowerCase().includes(kw);
          }
          return true;
        });
        works = works.sort((a, b) => {
          if (sortMode.value === "new") {
            const flag = Number(Boolean(b.is_new)) - Number(Boolean(a.is_new));
            if (flag) return flag;
          }
          return (Number(b.year) || 0) - (Number(a.year) || 0);
        });
        if (!works.length && filtering) continue;
        result.push({ ...actor, works });
      }
      return result;
    });
    const pendingTargets = computed(
      () => visibleActors.value.flatMap((actor) => (actor.works || []).filter((work) => !isSubscribed(work)))
    );
    function notify(type, message) {
      const handler = toast && toast[type];
      if (typeof handler === "function") {
        handler.call(toast, message);
        return;
      }
      if (type === "error") console.warn(`[${PLUGIN_ID}] ${message}`);
      else console.info(`[${PLUGIN_ID}] ${message}`);
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
        console.warn(`[${PLUGIN_ID}] 全页加载失败`, err);
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
        if (res?.success) notify("success", "已刷新演员最新作品");
        else notify("error", res?.message || "刷新失败");
        subscribedKeys.value = await fetchSubscribedKeys(api);
        emit("action");
      } catch (err) {
        notify("error", "刷新失败，请查看后端日志");
        console.warn(`[${PLUGIN_ID}] 刷新失败`, err);
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
        const res = await submitSubscribe(api, work);
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
    async function subscribeMany(works) {
      const api = resolveApi(props);
      if (!api || !works.length) return;
      busy.value = true;
      let success = 0;
      const failures = [];
      try {
        for (const work of works) {
          const key = workKey(work);
          pendingKey.value = key;
          const res = await submitSubscribe(api, work);
          if (res.ok) {
            success += 1;
            if (!subscribedKeys.value.includes(key)) subscribedKeys.value.push(key);
          } else {
            failures.push(`${work.title}：${res.message}`);
          }
          await new Promise((resolve) => window.setTimeout(resolve, 150));
        }
      } finally {
        pendingKey.value = "";
        busy.value = false;
      }
      if (success) notify("success", `已提交 ${success} 部作品的订阅`);
      if (failures.length) notify("error", `${failures.length} 部订阅失败，例如 ${failures[0]}`);
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
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_chip_group = _resolveComponent("v-chip-group");
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      const _component_v_checkbox = _resolveComponent("v-checkbox");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_progress_linear = _resolveComponent("v-progress-linear");
      const _component_v_img = _resolveComponent("v-img");
      const _component_v_avatar = _resolveComponent("v-avatar");
      const _component_v_card_title = _resolveComponent("v-card-title");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_icon, {
            icon: "mdi-account-star-outline",
            class: "mr-1"
          }),
          _cache[7] || (_cache[7] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "豆瓣演员作品面板", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(__props.pluginId || "DoubanActorSubscribe") + " / " + _toDisplayString(__props.navKey || "main"), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            icon: "mdi-refresh",
            loading: refreshing.value,
            onClick: refresh
          }, null, 8, ["loading"])
        ]),
        _createVNode(_component_v_row, {
          dense: "",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(statCards.value, (item) => {
              return _openBlock(), _createBlock(_component_v_col, {
                key: item.label,
                cols: "6",
                sm: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "tonal",
                    class: "pa-3"
                  }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_3, _toDisplayString(item.label), 1),
                      _createElementVNode("div", _hoisted_4, _toDisplayString(item.value), 1)
                    ]),
                    _: 2
                  }, 1024)
                ]),
                _: 2
              }, 1024);
            }), 128))
          ]),
          _: 1
        }),
        !payload.value?.enabled ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [..._cache[8] || (_cache[8] = [
            _createTextVNode(" 插件未启用或尚未配置演员，请先到配置页填写演员并保存。 ", -1)
          ])]),
          _: 1
        })) : _createCommentVNode("", true),
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_text, { class: "pb-2" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_5, [
                  _createVNode(_component_v_chip_group, {
                    modelValue: actorFilter.value,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => actorFilter.value = $event),
                    mandatory: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_chip, {
                        size: "small",
                        variant: "tonal",
                        value: ALL_ACTORS
                      }, {
                        default: _withCtx(() => [..._cache[9] || (_cache[9] = [
                          _createTextVNode("全部演员", -1)
                        ])]),
                        _: 1
                      }),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actors.value, (actor) => {
                        return _openBlock(), _createBlock(_component_v_chip, {
                          key: actor.key,
                          size: "small",
                          variant: "tonal",
                          value: actor.key
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(actor.name), 1)
                          ]),
                          _: 2
                        }, 1032, ["value"]);
                      }), 128))
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_6, [
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: typeFilter.value,
                    "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => typeFilter.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: ""
                      }, {
                        default: _withCtx(() => [..._cache[10] || (_cache[10] = [
                          _createTextVNode("全部", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电影"
                      }, {
                        default: _withCtx(() => [..._cache[11] || (_cache[11] = [
                          _createTextVNode("电影", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电视剧"
                      }, {
                        default: _withCtx(() => [..._cache[12] || (_cache[12] = [
                          _createTextVNode("电视剧", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _createVNode(_component_v_checkbox, {
                    modelValue: onlyNew.value,
                    "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => onlyNew.value = $event),
                    label: "只看新作品",
                    density: "compact",
                    "hide-details": "",
                    class: "das-narrow"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_checkbox, {
                    modelValue: onlyUnsubscribed.value,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => onlyUnsubscribed.value = $event),
                    label: "只看未订阅",
                    density: "compact",
                    "hide-details": "",
                    class: "das-narrow"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: sortMode.value,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => sortMode.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "year"
                      }, {
                        default: _withCtx(() => [..._cache[13] || (_cache[13] = [
                          _createTextVNode("最新优先", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "new"
                      }, {
                        default: _withCtx(() => [..._cache[14] || (_cache[14] = [
                          _createTextVNode("新作品优先", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _createVNode(_component_v_text_field, {
                    modelValue: keyword.value,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => keyword.value = $event),
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    clearable: "",
                    "prepend-inner-icon": "mdi-magnify",
                    placeholder: "搜索作品名 / 演员名",
                    class: "das-search"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    color: "primary",
                    variant: "tonal",
                    "prepend-icon": "mdi-plus-multiple",
                    disabled: busy.value || !pendingTargets.value.length,
                    onClick: _cache[6] || (_cache[6] = ($event) => subscribeMany(pendingTargets.value))
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 订阅筛选结果（" + _toDisplayString(pendingTargets.value.length) + "） ", 1)
                    ]),
                    _: 1
                  }, 8, ["disabled"])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        loading.value ? (_openBlock(), _createBlock(_component_v_progress_linear, {
          key: 1,
          indeterminate: "",
          color: "primary",
          class: "mb-3"
        })) : _createCommentVNode("", true),
        !visibleActors.value.length && !loading.value ? (_openBlock(), _createElementBlock("div", _hoisted_7, " 没有符合条件的作品。 ")) : _createCommentVNode("", true),
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleActors.value, (actor) => {
          return _openBlock(), _createBlock(_component_v_card, {
            key: actor.key,
            variant: "outlined",
            class: "mb-4"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_card_title, { class: "d-flex align-center flex-wrap" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_avatar, {
                    size: "34",
                    class: "mr-2"
                  }, {
                    default: _withCtx(() => [
                      actor.avatar ? (_openBlock(), _createBlock(_component_v_img, {
                        key: 0,
                        src: actor.avatar
                      }, null, 8, ["src"])) : (_openBlock(), _createBlock(_component_v_icon, {
                        key: 1,
                        icon: "mdi-account-outline",
                        size: "18"
                      }))
                    ]),
                    _: 2
                  }, 1024),
                  _createElementVNode("span", _hoisted_8, _toDisplayString(actor.name), 1),
                  _createElementVNode("span", _hoisted_9, _toDisplayString((actor.works || []).length) + " 部 · 新 " + _toDisplayString(newCount(actor)) + " 部 ", 1),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    variant: "text",
                    color: "primary",
                    href: doubanPersonUrl(actor.id),
                    target: "_blank"
                  }, {
                    default: _withCtx(() => [..._cache[15] || (_cache[15] = [
                      _createTextVNode(" 豆瓣主页 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["href"])
                ]),
                _: 2
              }, 1024),
              _createVNode(_component_v_card_text, null, {
                default: _withCtx(() => [
                  actor.error ? (_openBlock(), _createBlock(_component_v_alert, {
                    key: 0,
                    type: "warning",
                    variant: "tonal",
                    density: "compact",
                    class: "mb-3"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(actor.error), 1)
                    ]),
                    _: 2
                  }, 1024)) : _createCommentVNode("", true),
                  _createVNode(WorkGrid, {
                    works: actor.works || [],
                    "subscribed-keys": subscribedKeys.value,
                    "pending-key": pendingKey.value,
                    busy: busy.value,
                    "empty-text": "该演员暂无符合条件的作品",
                    onSubscribe: subscribe
                  }, null, 8, ["works", "subscribed-keys", "pending-key", "busy"])
                ]),
                _: 2
              }, 1024)
            ]),
            _: 2
          }, 1024);
        }), 128))
      ]);
    };
  }
});

const AppPage = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-ed4230f0"]]);

export { AppPage as default };
