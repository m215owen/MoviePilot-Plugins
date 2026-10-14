import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { S as SubscribePrefs } from './SubscribePrefs-Bumdpnpv.js';
import { e as formatTime, A as API_BASE, g as mediaPageUrl, r as resolveApi, n as normalizeResult, P as PLUGIN_ID, a as waitForRefresh, _ as _export_sfc } from './_plugin-vue_export-helper-WuUIO6Z9.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createBlock:_createBlock,unref:_unref} = await importShared('vue');

const _hoisted_1 = { class: "das-root pa-4" };
const _hoisted_2 = {
  class: "d-flex align-center mb-3 flex-wrap",
  style: { "gap": "12px" }
};
const _hoisted_3 = { class: "text-caption" };
const _hoisted_4 = { class: "text-h6" };
const _hoisted_5 = { class: "text-subtitle-2 mb-3" };
const _hoisted_6 = {
  class: "d-flex flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_7 = { class: "text-caption das-dim" };
const _hoisted_8 = {
  key: 0,
  class: "text-medium-emphasis text-body-2"
};
const _hoisted_9 = { class: "text-caption" };
const _hoisted_10 = { class: "text-caption" };
const _hoisted_11 = ["href", "title"];
const _hoisted_12 = { key: 1 };
const _hoisted_13 = { class: "text-caption das-dim ml-1" };
const _hoisted_14 = { class: "text-caption ml-1" };
const {computed,inject,onMounted,reactive,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "AppPageSettings",
  props: {
    api: {},
    nativeSubscribe: { type: Function },
    navKey: {},
    pluginId: {}
  },
  setup(__props) {
    const props = __props;
    const toast = inject("moviepilot:toast", null);
    const loading = ref(false);
    const saving = ref(false);
    const refreshing = ref(false);
    const clearing = ref(false);
    const confirmClear = ref(false);
    const payload = ref(null);
    const local = reactive({ enabled: false, actors: "", cron: "" });
    const prefs = reactive({
      save_path: "",
      downloader: "",
      sites: []
    });
    function recordHref(row) {
      const mediaId = String(row.media_id || "").trim();
      if (!mediaId) return "";
      if (String(row.type || "").trim()) {
        return mediaPageUrl({
          media_source: row.media_source || "themoviedb",
          media_id: mediaId,
          title: row.title,
          year: row.year,
          type: row.type
        });
      }
      const section = String(row.type || "").includes("电视剧") ? "tv" : "movie";
      return `https://www.themoviedb.org/${section}/${mediaId}`;
    }
    const actorsText = computed({
      get: () => String(local.actors || "").split(/[\r\n,，、;；]+/).map((item) => item.trim()).filter(Boolean).join("，"),
      set: (value) => {
        local.actors = String(value || "");
      }
    });
    const newWindowDays = computed(() => Number(payload.value?.new_window_days || 0));
    const newWindowLabel = computed(
      () => newWindowDays.value > 0 ? `近 ${newWindowDays.value} 天新增` : "近期新增"
    );
    const newActorCount = computed(() => payload.value?.new_actor_count ?? 0);
    const statCards = computed(() => {
      const rows = [
        { label: "演员", value: payload.value?.actor_count ?? 0 },
        { label: "作品", value: payload.value?.work_count ?? 0 },
        {
          label: `${newWindowLabel.value}（演员 / 作品）`,
          value: `${newActorCount.value} / ${payload.value?.new_count ?? 0}`
        }
      ];
      if (payload.value?.library_known) {
        rows.push({ label: "已在媒体库", value: payload.value?.library_count ?? 0 });
      }
      rows.push({ label: "上次刷新", value: formatTime(payload.value?.updated_at) });
      return rows;
    });
    function notify(type, message) {
      const handler = toast && toast[type];
      if (typeof handler === "function") {
        handler.call(toast, message);
        return;
      }
      console.warn(`[${PLUGIN_ID}] ${message}`);
    }
    function onPrefsSaved(ok, message) {
      notify(ok ? "success" : "error", message);
    }
    async function load() {
      const api = resolveApi(props);
      if (!api) {
        notify("error", "宿主 API 未就绪");
        return;
      }
      loading.value = true;
      try {
        const [cfgRaw, worksRaw] = await Promise.all([
          api.get(`${API_BASE}/config`),
          api.get(`${API_BASE}/works`)
        ]);
        const cfg = normalizeResult(cfgRaw);
        if (cfg.ok && cfg.data) {
          local.enabled = Boolean(cfg.data.enabled);
          local.actors = String(cfg.data.actors || "");
          local.cron = String(cfg.data.cron || "");
          prefs.save_path = String(cfg.data.subscribe_save_path || "");
          prefs.downloader = String(cfg.data.subscribe_downloader || "");
          prefs.sites = Array.isArray(cfg.data.subscribe_sites) ? cfg.data.subscribe_sites.map((item) => Number(item)) : [];
        }
        const works = normalizeResult(worksRaw);
        if (works.ok && works.data) payload.value = works.data;
      } catch (err) {
        notify("error", "读取状态失败");
        console.warn(`[${PLUGIN_ID}] 读取状态失败`, err);
      } finally {
        loading.value = false;
      }
    }
    async function save() {
      const api = resolveApi(props);
      if (!api) {
        notify("error", "宿主 API 未就绪");
        return;
      }
      saving.value = true;
      try {
        const raw = await api.put(`${API_BASE}/config`, {
          enabled: local.enabled,
          actors: local.actors,
          cron: local.cron
        });
        const res = normalizeResult(raw);
        if (res.ok) {
          notify("success", "配置已保存");
          await runNow();
        } else {
          notify("error", res.message || "保存失败");
        }
      } catch (err) {
        notify("error", "保存失败");
        console.warn(`[${PLUGIN_ID}] 保存配置失败`, err);
      } finally {
        saving.value = false;
      }
    }
    async function runNow() {
      const api = resolveApi(props);
      if (!api) return;
      refreshing.value = true;
      try {
        const raw = await api.post(`${API_BASE}/run`);
        const res = normalizeResult(raw);
        if (res.data) payload.value = res.data;
        if (res.ok) notify("success", res.message || "已开始刷新演员最新作品");
        else notify("error", res.message || "刷新失败");
        if (payload.value?.refreshing || payload.value?.pending_refresh) {
          waitForRefresh(api, (data) => {
            payload.value = data;
          });
        }
      } catch (err) {
        notify("error", "刷新失败");
        console.warn(`[${PLUGIN_ID}] 刷新失败`, err);
      } finally {
        refreshing.value = false;
      }
    }
    async function clearRecords() {
      const api = resolveApi(props);
      if (!api) return;
      clearing.value = true;
      try {
        const raw = await api.post(`${API_BASE}/clear`);
        const res = normalizeResult(raw);
        if (res.ok) {
          notify("success", res.message || "已清空记录");
          confirmClear.value = false;
          await load();
        } else {
          notify("error", res.message || "清空失败");
        }
      } catch (err) {
        notify("error", "清空失败");
        console.warn(`[${PLUGIN_ID}] 清空失败`, err);
      } finally {
        clearing.value = false;
      }
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
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_textarea = _resolveComponent("v-textarea");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_table = _resolveComponent("v-table");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card_actions = _resolveComponent("v-card-actions");
      const _component_v_dialog = _resolveComponent("v-dialog");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_icon, {
            icon: "mdi-chart-timeline-variant",
            class: "mr-1"
          }),
          _cache[9] || (_cache[9] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "TMDB演员订阅 · 运行状态", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(__props.pluginId || "DoubanActorSubscribe") + " / " + _toDisplayString(__props.navKey || "settings"), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            icon: "mdi-refresh",
            loading: loading.value,
            onClick: load
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
                md: "3"
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
        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(payload.value?.errors || [], (err, index) => {
          return _openBlock(), _createBlock(_component_v_alert, {
            key: index,
            type: "error",
            variant: "tonal",
            density: "compact",
            class: "mb-2"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(err), 1)
            ]),
            _: 2
          }, 1024);
        }), 128)),
        _createVNode(SubscribePrefs, {
          "save-path": prefs.save_path,
          "onUpdate:savePath": _cache[0] || (_cache[0] = ($event) => prefs.save_path = $event),
          downloader: prefs.downloader,
          "onUpdate:downloader": _cache[1] || (_cache[1] = ($event) => prefs.downloader = $event),
          sites: prefs.sites,
          "onUpdate:sites": _cache[2] || (_cache[2] = ($event) => prefs.sites = $event),
          class: "mb-3",
          api: props.api,
          onSaved: onPrefsSaved
        }, null, 8, ["save-path", "downloader", "sites", "api"]),
        _createVNode(_component_v_row, null, {
          default: _withCtx(() => [
            _createVNode(_component_v_col, {
              cols: "12",
              lg: "5"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "outlined",
                  class: "pa-4"
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_5, [
                      _createVNode(_component_v_icon, {
                        icon: "mdi-flash-outline",
                        size: "18",
                        class: "mr-1"
                      }),
                      _cache[10] || (_cache[10] = _createTextVNode(" 快速配置 ", -1))
                    ]),
                    _createVNode(_component_v_alert, {
                      type: "info",
                      variant: "tonal",
                      density: "compact",
                      class: "mb-3"
                    }, {
                      default: _withCtx(() => [
                        _cache[11] || (_cache[11] = _createTextVNode(" 本页通过 ", -1)),
                        _createElementVNode("code", null, "PUT " + _toDisplayString(_unref(API_BASE)) + "/config", 1),
                        _cache[12] || (_cache[12] = _createTextVNode(" 只提交下面三个字段， 其余配置（自动订阅、评分阈值等）保持原样，完整设置请在插件配置弹窗中调整。 ", -1))
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_switch, {
                      modelValue: local.enabled,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => local.enabled = $event),
                      label: "启用插件",
                      color: "primary",
                      "hide-details": "",
                      class: "mb-2"
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_v_textarea, {
                      modelValue: actorsText.value,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => actorsText.value = $event),
                      label: "订阅的演员",
                      placeholder: "多位演员用逗号分隔，例如：刘德华，吴京，张译",
                      hint: "演员名或 TMDB 人物 ID/主页链接均可，用逗号分隔（也支持换行 / 顿号）。填 ID 或链接可跳过搜索，解析结果也更精确。",
                      "persistent-hint": "",
                      rows: "4",
                      "no-resize": "",
                      density: "comfortable",
                      class: "mb-2"
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_v_text_field, {
                      modelValue: local.cron,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => local.cron = $event),
                      label: "刷新周期（cron）",
                      hint: "5 段式，例如 0 8 * * *",
                      "persistent-hint": "",
                      density: "comfortable",
                      class: "mb-3"
                    }, null, 8, ["modelValue"]),
                    _createElementVNode("div", _hoisted_6, [
                      _createVNode(_component_v_btn, {
                        color: "primary",
                        loading: saving.value,
                        onClick: save
                      }, {
                        default: _withCtx(() => [..._cache[13] || (_cache[13] = [
                          _createTextVNode("保存并刷新", -1)
                        ])]),
                        _: 1
                      }, 8, ["loading"]),
                      _createVNode(_component_v_btn, {
                        variant: "tonal",
                        loading: refreshing.value,
                        onClick: runNow
                      }, {
                        default: _withCtx(() => [..._cache[14] || (_cache[14] = [
                          _createTextVNode("立即刷新作品", -1)
                        ])]),
                        _: 1
                      }, 8, ["loading"]),
                      _createVNode(_component_v_btn, {
                        variant: "text",
                        onClick: load
                      }, {
                        default: _withCtx(() => [..._cache[15] || (_cache[15] = [
                          _createTextVNode("放弃修改", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_spacer),
                      _createVNode(_component_v_btn, {
                        variant: "text",
                        color: "error",
                        "prepend-icon": "mdi-delete-outline",
                        onClick: _cache[6] || (_cache[6] = ($event) => confirmClear.value = true)
                      }, {
                        default: _withCtx(() => [..._cache[16] || (_cache[16] = [
                          _createTextVNode(" 清空记录 ", -1)
                        ])]),
                        _: 1
                      })
                    ])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_col, {
              cols: "12",
              lg: "7"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, { variant: "outlined" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
                      default: _withCtx(() => [
                        _cache[17] || (_cache[17] = _createTextVNode(" 自动订阅历史 ", -1)),
                        _createVNode(_component_v_spacer),
                        _createElementVNode("span", _hoisted_7, " 共 " + _toDisplayString((payload.value?.auto_subscribed || []).length) + " 条 ", 1)
                      ]),
                      _: 1
                    }),
                    _createVNode(_component_v_card_text, null, {
                      default: _withCtx(() => [
                        !payload.value?.auto_subscribed?.length ? (_openBlock(), _createElementBlock("div", _hoisted_8, " 暂无自动订阅记录。开启自动订阅后，插件会把新发现且满足条件的作品提交到订阅系统。 ")) : (_openBlock(), _createBlock(_component_v_table, {
                          key: 1,
                          density: "compact"
                        }, {
                          default: _withCtx(() => [
                            _cache[18] || (_cache[18] = _createElementVNode("thead", null, [
                              _createElementVNode("tr", null, [
                                _createElementVNode("th", null, "时间"),
                                _createElementVNode("th", null, "演员"),
                                _createElementVNode("th", null, "作品"),
                                _createElementVNode("th", null, "结果")
                              ])
                            ], -1)),
                            _createElementVNode("tbody", null, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(payload.value.auto_subscribed, (row, index) => {
                                return _openBlock(), _createElementBlock("tr", { key: index }, [
                                  _createElementVNode("td", _hoisted_9, _toDisplayString(row.time), 1),
                                  _createElementVNode("td", _hoisted_10, _toDisplayString(row.actor || "—"), 1),
                                  _createElementVNode("td", null, [
                                    recordHref(row) ? (_openBlock(), _createElementBlock("a", {
                                      key: 0,
                                      href: recordHref(row),
                                      target: "_blank",
                                      rel: "noopener",
                                      title: row.type ? "在 MoviePilot 中打开媒体详情" : "打开 TMDB 条目"
                                    }, _toDisplayString(row.title), 9, _hoisted_11)) : (_openBlock(), _createElementBlock("span", _hoisted_12, _toDisplayString(row.title), 1)),
                                    _createElementVNode("span", _hoisted_13, _toDisplayString(row.year || ""), 1)
                                  ]),
                                  _createElementVNode("td", null, [
                                    _createVNode(_component_v_icon, {
                                      icon: row.success ? "mdi-check-circle" : "mdi-alert-circle",
                                      color: row.success ? "success" : "error",
                                      size: "16"
                                    }, null, 8, ["icon", "color"]),
                                    _createElementVNode("span", _hoisted_14, _toDisplayString(row.detail), 1)
                                  ])
                                ]);
                              }), 128))
                            ])
                          ]),
                          _: 1
                        }))
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_dialog, {
          modelValue: confirmClear.value,
          "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => confirmClear.value = $event),
          "max-width": "420"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, null, {
                  default: _withCtx(() => [..._cache[19] || (_cache[19] = [
                    _createTextVNode("确认清空？", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [..._cache[20] || (_cache[20] = [
                    _createTextVNode(" 将清空已抓取的作品快照与自动订阅记录。已提交到订阅系统的订阅不会被删除。 ", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_card_actions, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[7] || (_cache[7] = ($event) => confirmClear.value = false)
                    }, {
                      default: _withCtx(() => [..._cache[21] || (_cache[21] = [
                        _createTextVNode("取消", -1)
                      ])]),
                      _: 1
                    }),
                    _createVNode(_component_v_btn, {
                      color: "error",
                      loading: clearing.value,
                      onClick: clearRecords
                    }, {
                      default: _withCtx(() => [..._cache[22] || (_cache[22] = [
                        _createTextVNode("确认清空", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"])
      ]);
    };
  }
});

const AppPageSettings = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-be2c0676"]]);

export { AppPageSettings as default };
