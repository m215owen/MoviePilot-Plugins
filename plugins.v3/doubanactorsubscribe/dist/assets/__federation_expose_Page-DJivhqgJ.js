import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { W as WorkGrid } from './WorkGrid-8IKiiOmw.js';
import { a as formatTime, r as resolveApi, A as API_BASE, u as unwrap, f as fetchSubscribedKeys, P as PLUGIN_ID, w as workKey, s as submitSubscribe, _ as _export_sfc } from './_plugin-vue_export-helper-CY9eCSTe.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,unref:_unref} = await importShared('vue');

const _hoisted_1 = { class: "das-root das-page pa-2" };
const _hoisted_2 = { class: "text-caption" };
const _hoisted_3 = { class: "text-h6" };
const _hoisted_4 = { class: "text-caption das-dim mt-2" };
const _hoisted_5 = { key: 0 };
const _hoisted_6 = {
  class: "d-flex align-center flex-wrap",
  style: { "gap": "12px" }
};
const _hoisted_7 = { class: "ml-1 das-dim" };
const _hoisted_8 = {
  class: "d-flex align-center flex-wrap mt-2",
  style: { "gap": "12px" }
};
const _hoisted_9 = {
  key: 1,
  class: "text-center text-medium-emphasis py-6"
};
const _hoisted_10 = { class: "das-actor-name" };
const _hoisted_11 = { class: "das-dim text-caption ml-2" };
const _hoisted_12 = {
  key: 1,
  class: "text-caption das-dim mb-3"
};
const _hoisted_13 = {
  class: "d-flex mt-3 flex-wrap",
  style: { "gap": "4px" }
};
const {computed,inject,onMounted,ref} = await importShared('vue');
const ALL_ACTORS = "__all__";
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Page",
  props: {
    api: {},
    nativeSubscribe: { type: Function },
    pluginId: {}
  },
  emits: ["action", "switch", "close"],
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
    const keyword = ref("");
    const actors = computed(() => payload.value?.actors || []);
    const statCards = computed(() => [
      { label: "演员", value: payload.value?.actor_count ?? actors.value.length },
      { label: "作品", value: payload.value?.work_count ?? 0 },
      { label: "新作品", value: payload.value?.new_count ?? 0 },
      { label: "累计刷新", value: payload.value?.run_count ?? 0 }
    ]);
    const visibleActors = computed(() => {
      const kw = keyword.value.trim().toLowerCase();
      const filtering = Boolean(
        actorFilter.value && actorFilter.value !== ALL_ACTORS || typeFilter.value || onlyNew.value || kw
      );
      const result = [];
      for (const actor of actors.value) {
        if (actorFilter.value && actorFilter.value !== ALL_ACTORS) {
          if (actor.key !== actorFilter.value && actor.id !== actorFilter.value) continue;
        }
        const works = (actor.works || []).filter((work) => {
          if (typeFilter.value && work.type !== typeFilter.value) return false;
          if (onlyNew.value && !work.is_new) return false;
          if (kw && !work.title.toLowerCase().includes(kw)) return false;
          return true;
        });
        if (!works.length && filtering) continue;
        result.push({ ...actor, works });
      }
      return result;
    });
    function isSubscribed(work) {
      return subscribedKeys.value.includes(workKey(work));
    }
    function newCount(actor) {
      return (actor.works || []).filter((work) => work.is_new).length;
    }
    function unsubscribed(actor) {
      return (actor.works || []).filter((work) => !isSubscribed(work));
    }
    function notify(type, message) {
      const handler = toast && toast[type];
      if (typeof handler === "function") {
        handler.call(toast, message);
        return;
      }
      if (type === "error") console.warn(`[${PLUGIN_ID}] ${message}`);
      else console.info(`[${PLUGIN_ID}] ${message}`);
    }
    async function load(showSpinner = true) {
      const api = resolveApi(props);
      if (!api) return;
      if (showSpinner) loading.value = true;
      try {
        const raw = await api.get(`${API_BASE}/works`);
        const res = unwrap(raw);
        if (res?.success && res.data) payload.value = res.data;
        subscribedKeys.value = await fetchSubscribedKeys(api);
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 加载作品失败`, err);
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
    onMounted(() => load());
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_chip_group = _resolveComponent("v-chip-group");
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      const _component_v_checkbox = _resolveComponent("v-checkbox");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_progress_linear = _resolveComponent("v-progress-linear");
      const _component_v_img = _resolveComponent("v-img");
      const _component_v_avatar = _resolveComponent("v-avatar");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, { class: "d-flex align-center flex-wrap" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-account-star-outline",
                  class: "mr-2"
                }),
                _cache[8] || (_cache[8] = _createElementVNode("span", null, "豆瓣演员订阅", -1)),
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  color: "primary",
                  "prepend-icon": "mdi-refresh",
                  loading: refreshing.value,
                  onClick: refresh
                }, {
                  default: _withCtx(() => [..._cache[7] || (_cache[7] = [
                    _createTextVNode(" 刷新作品 ", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_text, null, {
              default: _withCtx(() => [
                !payload.value?.enabled ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  default: _withCtx(() => [..._cache[9] || (_cache[9] = [
                    _createTextVNode(" 插件未启用或尚未配置演员，请先在配置页填写演员并保存。 ", -1)
                  ])]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createVNode(_component_v_row, { dense: "" }, {
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
                              _createElementVNode("div", _hoisted_2, _toDisplayString(item.label), 1),
                              _createElementVNode("div", _hoisted_3, _toDisplayString(item.value), 1)
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
                _createElementVNode("div", _hoisted_4, [
                  _createTextVNode(" 上次刷新：" + _toDisplayString(_unref(formatTime)(payload.value?.updated_at)) + " ", 1),
                  payload.value?.auto_subscribe ? (_openBlock(), _createElementBlock("span", _hoisted_5, " ｜自动订阅：" + _toDisplayString(payload.value?.auto_only_new ? "仅新作品" : "含存量作品") + " ・评分 ≥ " + _toDisplayString(payload.value?.auto_min_vote || 0) + " ・" + _toDisplayString((payload.value?.auto_types || []).join("/") || "全部类型"), 1)) : _createCommentVNode("", true)
                ]),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(payload.value?.errors || [], (err, index) => {
                  return _openBlock(), _createBlock(_component_v_alert, {
                    key: index,
                    type: "error",
                    variant: "tonal",
                    density: "compact",
                    class: "mt-2"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(err), 1)
                    ]),
                    _: 2
                  }, 1024);
                }), 128))
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_text, { class: "pb-2" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_6, [
                  _createVNode(_component_v_chip_group, {
                    modelValue: actorFilter.value,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => actorFilter.value = $event),
                    mandatory: "",
                    class: "das-chips"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_chip, {
                        size: "small",
                        variant: "tonal",
                        value: ALL_ACTORS
                      }, {
                        default: _withCtx(() => [..._cache[10] || (_cache[10] = [
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
                            _createTextVNode(_toDisplayString(actor.name) + " ", 1),
                            _createElementVNode("span", _hoisted_7, "（" + _toDisplayString((actor.works || []).length) + "）", 1)
                          ]),
                          _: 2
                        }, 1032, ["value"]);
                      }), 128))
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_8, [
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
                        default: _withCtx(() => [..._cache[11] || (_cache[11] = [
                          _createTextVNode("全部", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电影"
                      }, {
                        default: _withCtx(() => [..._cache[12] || (_cache[12] = [
                          _createTextVNode("电影", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电视剧"
                      }, {
                        default: _withCtx(() => [..._cache[13] || (_cache[13] = [
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
                    class: "das-checkbox"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_text_field, {
                    modelValue: keyword.value,
                    "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => keyword.value = $event),
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    clearable: "",
                    "prepend-inner-icon": "mdi-magnify",
                    placeholder: "搜索作品名",
                    class: "das-search"
                  }, null, 8, ["modelValue"])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        loading.value ? (_openBlock(), _createBlock(_component_v_progress_linear, {
          key: 0,
          indeterminate: "",
          color: "primary",
          class: "mb-3"
        })) : _createCommentVNode("", true),
        !visibleActors.value.length && !loading.value ? (_openBlock(), _createElementBlock("div", _hoisted_9, " 暂无数据，点击「刷新作品」抓取演员最新作品。 ")) : _createCommentVNode("", true),
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleActors.value, (actor) => {
          return _openBlock(), _createBlock(_component_v_card, {
            key: actor.key,
            variant: "outlined",
            class: "mb-3"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_card_title, { class: "d-flex align-center flex-wrap" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_avatar, {
                    size: "36",
                    class: "mr-2"
                  }, {
                    default: _withCtx(() => [
                      actor.avatar ? (_openBlock(), _createBlock(_component_v_img, {
                        key: 0,
                        src: actor.avatar
                      }, null, 8, ["src"])) : (_openBlock(), _createBlock(_component_v_icon, {
                        key: 1,
                        icon: "mdi-account-outline"
                      }))
                    ]),
                    _: 2
                  }, 1024),
                  _createElementVNode("div", _hoisted_10, [
                    _createTextVNode(_toDisplayString(actor.name) + " ", 1),
                    _createElementVNode("span", _hoisted_11, " 共 " + _toDisplayString((actor.works || []).length) + " 部 · 新 " + _toDisplayString(newCount(actor)) + " 部 ", 1)
                  ]),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    variant: "tonal",
                    color: "primary",
                    "prepend-icon": "mdi-plus-multiple",
                    disabled: busy.value || !unsubscribed(actor).length,
                    onClick: ($event) => subscribeMany(unsubscribed(actor))
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 订阅全部未订阅（" + _toDisplayString(unsubscribed(actor).length) + "） ", 1)
                    ]),
                    _: 2
                  }, 1032, ["disabled", "onClick"])
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
                  actor.biography ? (_openBlock(), _createElementBlock("div", _hoisted_12, _toDisplayString(actor.biography), 1)) : _createCommentVNode("", true),
                  _createVNode(WorkGrid, {
                    works: actor.works || [],
                    "subscribed-keys": subscribedKeys.value,
                    "pending-key": pendingKey.value,
                    busy: busy.value,
                    "empty-text": "该演员暂无匹配的作品",
                    onSubscribe: subscribe
                  }, null, 8, ["works", "subscribed-keys", "pending-key", "busy"])
                ]),
                _: 2
              }, 1024)
            ]),
            _: 2
          }, 1024);
        }), 128)),
        _createElementVNode("div", _hoisted_13, [
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            "prepend-icon": "mdi-cog-outline",
            onClick: _cache[4] || (_cache[4] = ($event) => emit("switch"))
          }, {
            default: _withCtx(() => [..._cache[14] || (_cache[14] = [
              _createTextVNode(" 配置插件 ", -1)
            ])]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            "prepend-icon": "mdi-refresh",
            onClick: _cache[5] || (_cache[5] = ($event) => emit("action"))
          }, {
            default: _withCtx(() => [..._cache[15] || (_cache[15] = [
              _createTextVNode(" 通知宿主刷新 ", -1)
            ])]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            onClick: _cache[6] || (_cache[6] = ($event) => emit("close"))
          }, {
            default: _withCtx(() => [..._cache[16] || (_cache[16] = [
              _createTextVNode("关闭", -1)
            ])]),
            _: 1
          })
        ])
      ]);
    };
  }
});

const Page = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-b6b841d1"]]);

export { Page as default };
