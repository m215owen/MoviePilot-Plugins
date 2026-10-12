import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { E as ErrorAlerts, W as WorkGrid } from './WorkGrid-D_wUo6oL.js';
import { S as SubscribePrefs } from './SubscribePrefs-Bgn2B3IW.js';
import { m as mergeWorks, s as sortWorks, c as formatTime, w as workKey, r as resolveApi, A as API_BASE, u as unwrap, f as fetchSubscribedKeys, a as waitForRefresh, P as PLUGIN_ID, b as submitSubscribe, _ as _export_sfc } from './api-BbaK2SUr.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,unref:_unref} = await importShared('vue');

const _hoisted_1 = { class: "das-root das-page pa-2" };
const _hoisted_2 = { class: "text-caption" };
const _hoisted_3 = { class: "text-h6" };
const _hoisted_4 = { class: "text-caption das-dim mt-2" };
const _hoisted_5 = { key: 0 };
const _hoisted_6 = { class: "das-chips" };
const _hoisted_7 = { class: "ml-1 das-dim" };
const _hoisted_8 = { class: "d-flex align-center flex-wrap mt-2 das-toolbar" };
const _hoisted_9 = {
  key: 1,
  class: "text-center text-medium-emphasis py-6"
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
    const subscribeSavePath = ref("");
    const subscribeSites = ref([]);
    const actorFilter = ref(ALL_ACTORS);
    const typeFilter = ref("");
    const onlyNew = ref(false);
    const onlyUnsubscribed = ref(false);
    const sortMode = ref("year");
    const keyword = ref("");
    const actors = computed(() => payload.value?.actors || []);
    const unresolvedCount = computed(() => actors.value.filter((actor) => !actor.id).length);
    const statCards = computed(() => {
      const rows = [
        { label: "演员", value: actors.value.length },
        { label: "作品", value: payload.value?.work_count ?? 0 },
        { label: "新作品", value: payload.value?.new_count ?? 0 }
      ];
      if (unresolvedCount.value) {
        rows.push({ label: "未解析演员", value: unresolvedCount.value });
      } else {
        rows.push({ label: "累计刷新", value: payload.value?.run_count ?? 0 });
      }
      return rows;
    });
    const cookieChip = computed(() => {
      const source = payload.value?.douban_cookie_source;
      const hint = payload.value?.douban_cookie_hint || "";
      if (source === "manual") {
        return { text: "Cookie：手填", color: "success", icon: "mdi-cookie", title: "使用插件内手工粘贴的豆瓣 Cookie" };
      }
      if (source === "cookiecloud") {
        return {
          text: "Cookie：CookieCloud",
          color: "success",
          icon: "mdi-cookie",
          title: "已自动从宿主 CookieCloud 读取豆瓣登录态，搜索额度更高"
        };
      }
      return {
        text: "Cookie：未取到",
        color: "warning",
        icon: "mdi-cookie-alert",
        title: hint || "未取到豆瓣登录态，按名称搜索演员会被严格限流；可在配置页手工粘贴 Cookie"
      };
    });
    const cooldownCount = computed(() => payload.value?.search_cooldown_count ?? 0);
    const errorList = computed(() => {
      const items = payload.value?.errors || [];
      return [...items].sort((a, b) => {
        const rank = (text) => text.includes("人物 ID") ? 1 : 0;
        return rank(a) - rank(b);
      });
    });
    function isSubscribed(work) {
      return subscribedKeys.value.includes(workKey(work));
    }
    function actorMatches(actor) {
      return !actorFilter.value || actorFilter.value === ALL_ACTORS ? true : actor.key === actorFilter.value || actor.id === actorFilter.value;
    }
    const visibleWorks = computed(() => {
      const groups = actors.value.filter(actorMatches);
      let works = mergeWorks(groups);
      if (typeFilter.value) works = works.filter((work) => work.type === typeFilter.value);
      if (onlyNew.value) works = works.filter((work) => work.is_new);
      if (onlyUnsubscribed.value) works = works.filter((work) => !isSubscribed(work));
      const kw = keyword.value.trim().toLowerCase();
      if (kw) {
        works = works.filter(
          (work) => String(work.title || "").toLowerCase().includes(kw) || (work.actorNames || []).some((name) => String(name).toLowerCase().includes(kw))
        );
      }
      return sortWorks(works, sortMode.value);
    });
    const pendingTargets = computed(() => visibleWorks.value.filter((work) => !isSubscribed(work)));
    function notify(type, message) {
      const handler = toast && toast[type];
      if (typeof handler === "function") {
        handler.call(toast, message);
        return;
      }
      if (type === "error") console.warn(`[${PLUGIN_ID}] ${message}`);
      else console.info(`[${PLUGIN_ID}] ${message}`);
    }
    function applyPayload(data) {
      payload.value = data;
      subscribeSavePath.value = data.subscribe_save_path || "";
      subscribeSites.value = data.subscribe_sites || [];
    }
    function onPrefsSaved(ok, message) {
      notify(ok ? "success" : "error", message);
    }
    async function load(showSpinner = true) {
      const api = resolveApi(props);
      if (!api) return;
      if (showSpinner) loading.value = true;
      try {
        const raw = await api.get(`${API_BASE}/works`);
        const res = unwrap(raw);
        if (res?.success && res.data) applyPayload(res.data);
        subscribedKeys.value = await fetchSubscribedKeys(api);
        if (payload.value?.pending_refresh || payload.value?.refreshing) {
          waitForRefresh(api, applyPayload);
        }
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
        if (res?.data) applyPayload(res.data);
        if (res?.success) notify("success", res.message || "已开始刷新演员最新作品");
        else notify("error", res?.message || "刷新失败");
        subscribedKeys.value = await fetchSubscribedKeys(api);
        if (payload.value?.refreshing || payload.value?.pending_refresh) {
          waitForRefresh(api, applyPayload);
        }
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
        const res = await submitSubscribe(api, work, {
          savePath: subscribeSavePath.value,
          sites: subscribeSites.value
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
          const res = await submitSubscribe(api, work, {
            savePath: subscribeSavePath.value,
            sites: subscribeSites.value
          });
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
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_chip_group = _resolveComponent("v-chip-group");
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      const _component_v_checkbox = _resolveComponent("v-checkbox");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_progress_linear = _resolveComponent("v-progress-linear");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, { class: "d-flex align-center flex-wrap das-titlebar" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-account-star-outline",
                  class: "mr-1"
                }),
                _cache[15] || (_cache[15] = _createElementVNode("span", null, "豆瓣演员订阅", -1)),
                actors.value.length ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 0,
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(actors.value.length) + " 位演员", 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                visibleWorks.value.length ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 1,
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(visibleWorks.value.length) + " 部作品 ", 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createVNode(_component_v_chip, {
                  size: "small",
                  variant: "tonal",
                  color: cookieChip.value.color,
                  "prepend-icon": cookieChip.value.icon,
                  title: cookieChip.value.title
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(cookieChip.value.text), 1)
                  ]),
                  _: 1
                }, 8, ["color", "prepend-icon", "title"]),
                cooldownCount.value ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 2,
                  size: "small",
                  variant: "tonal",
                  color: "info",
                  "prepend-icon": "mdi-timer-sand",
                  title: `${cooldownCount.value} 位演员在 24 小时内成功搜索过，需等冷却结束后才会重试；直接填人物 ID 可跳过搜索`
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 搜索冷却 " + _toDisplayString(cooldownCount.value), 1)
                  ]),
                  _: 1
                }, 8, ["title"])) : _createCommentVNode("", true),
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  color: "primary",
                  "prepend-icon": "mdi-refresh",
                  loading: refreshing.value || Boolean(payload.value?.refreshing),
                  onClick: refresh
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(payload.value?.refreshing ? "刷新中…" : "刷新作品"), 1)
                  ]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "text",
                  "prepend-icon": "mdi-cog-outline",
                  onClick: _cache[0] || (_cache[0] = ($event) => emit("switch"))
                }, {
                  default: _withCtx(() => [..._cache[12] || (_cache[12] = [
                    _createTextVNode(" 配置插件 ", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "text",
                  "prepend-icon": "mdi-open-in-app",
                  onClick: _cache[1] || (_cache[1] = ($event) => emit("action"))
                }, {
                  default: _withCtx(() => [..._cache[13] || (_cache[13] = [
                    _createTextVNode(" 通知宿主刷新 ", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "text",
                  onClick: _cache[2] || (_cache[2] = ($event) => emit("close"))
                }, {
                  default: _withCtx(() => [..._cache[14] || (_cache[14] = [
                    _createTextVNode("关闭", -1)
                  ])]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_text, { class: "pt-0" }, {
              default: _withCtx(() => [
                !payload.value?.enabled ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2"
                }, {
                  default: _withCtx(() => [..._cache[16] || (_cache[16] = [
                    _createTextVNode(" 插件未启用或尚未配置演员，请先在配置页填写演员并保存。 ", -1)
                  ])]),
                  _: 1
                })) : _createCommentVNode("", true),
                payload.value?.refreshing ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 1,
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2"
                }, {
                  default: _withCtx(() => [..._cache[17] || (_cache[17] = [
                    _createTextVNode(" 正在后台刷新演员作品（演员较多时需要几分钟），完成后此页会自动更新… ", -1)
                  ])]),
                  _: 1
                })) : payload.value?.pending_refresh ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 2,
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2"
                }, {
                  default: _withCtx(() => [..._cache[18] || (_cache[18] = [
                    _createTextVNode(" 演员列表已变更，正在后台刷新作品，稍候会自动更新… ", -1)
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
                _createVNode(ErrorAlerts, {
                  errors: errorList.value,
                  class: "mt-3"
                }, null, 8, ["errors"])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(SubscribePrefs, {
          "save-path": subscribeSavePath.value,
          "onUpdate:savePath": _cache[3] || (_cache[3] = ($event) => subscribeSavePath.value = $event),
          sites: subscribeSites.value,
          "onUpdate:sites": _cache[4] || (_cache[4] = ($event) => subscribeSites.value = $event),
          api: props.api,
          onSaved: onPrefsSaved
        }, null, 8, ["save-path", "sites", "api"]),
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
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => actorFilter.value = $event),
                    mandatory: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_chip, {
                        size: "small",
                        variant: "tonal",
                        value: ALL_ACTORS
                      }, {
                        default: _withCtx(() => [..._cache[19] || (_cache[19] = [
                          _createTextVNode("全部演员", -1)
                        ])]),
                        _: 1
                      }),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actors.value, (actor) => {
                        return _openBlock(), _createBlock(_component_v_chip, {
                          key: actor.key,
                          size: "small",
                          variant: "tonal",
                          value: actor.key,
                          title: actor.error || actor.name
                        }, {
                          default: _withCtx(() => [
                            actor.error ? (_openBlock(), _createBlock(_component_v_icon, {
                              key: 0,
                              icon: "mdi-alert-circle-outline",
                              size: "14",
                              color: "warning",
                              class: "mr-1"
                            })) : _createCommentVNode("", true),
                            _createTextVNode(" " + _toDisplayString(actor.name) + " ", 1),
                            _createElementVNode("span", _hoisted_7, _toDisplayString((actor.works || []).length), 1)
                          ]),
                          _: 2
                        }, 1032, ["value", "title"]);
                      }), 128))
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_8, [
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: typeFilter.value,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => typeFilter.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: ""
                      }, {
                        default: _withCtx(() => [..._cache[20] || (_cache[20] = [
                          _createTextVNode("全部", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电影"
                      }, {
                        default: _withCtx(() => [..._cache[21] || (_cache[21] = [
                          _createTextVNode("电影", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电视剧"
                      }, {
                        default: _withCtx(() => [..._cache[22] || (_cache[22] = [
                          _createTextVNode("电视剧", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _createVNode(_component_v_checkbox, {
                    modelValue: onlyNew.value,
                    "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => onlyNew.value = $event),
                    label: "只看新作品",
                    density: "compact",
                    "hide-details": "",
                    class: "das-checkbox"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_checkbox, {
                    modelValue: onlyUnsubscribed.value,
                    "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => onlyUnsubscribed.value = $event),
                    label: "只看未订阅",
                    density: "compact",
                    "hide-details": "",
                    class: "das-checkbox"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: sortMode.value,
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => sortMode.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "year"
                      }, {
                        default: _withCtx(() => [..._cache[23] || (_cache[23] = [
                          _createTextVNode("最新优先", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "new"
                      }, {
                        default: _withCtx(() => [..._cache[24] || (_cache[24] = [
                          _createTextVNode("新作品优先", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _createVNode(_component_v_text_field, {
                    modelValue: keyword.value,
                    "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => keyword.value = $event),
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
                    onClick: _cache[11] || (_cache[11] = ($event) => subscribeMany(pendingTargets.value))
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
        loading.value || payload.value?.refreshing ? (_openBlock(), _createBlock(_component_v_progress_linear, {
          key: 0,
          indeterminate: "",
          color: "primary",
          class: "mb-3"
        })) : _createCommentVNode("", true),
        !visibleWorks.value.length && !loading.value ? (_openBlock(), _createElementBlock("div", _hoisted_9, " 暂无数据，点击顶部「刷新作品」抓取演员最新作品。 ")) : (_openBlock(), _createBlock(WorkGrid, {
          key: 2,
          works: visibleWorks.value,
          "subscribed-keys": subscribedKeys.value,
          "pending-key": pendingKey.value,
          busy: busy.value,
          "empty-text": "没有符合条件的作品",
          onSubscribe: subscribe
        }, null, 8, ["works", "subscribed-keys", "pending-key", "busy"]))
      ]);
    };
  }
});

const Page = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-53919be1"]]);

export { Page as default };
