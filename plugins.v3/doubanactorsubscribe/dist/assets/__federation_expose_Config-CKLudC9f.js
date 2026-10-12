import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { S as SubscribePrefs } from './SubscribePrefs-Bgn2B3IW.js';
import { r as resolveApi, A as API_BASE, u as unwrap, P as PLUGIN_ID, _ as _export_sfc } from './api-BbaK2SUr.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,withKeys:_withKeys,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createBlock:_createBlock,toDisplayString:_toDisplayString} = await importShared('vue');

const _hoisted_1 = { class: "das-root pa-2" };
const _hoisted_2 = { class: "d-flex align-center mb-3" };
const _hoisted_3 = { class: "text-subtitle-2 mb-2" };
const _hoisted_4 = {
  key: 0,
  class: "text-caption das-dim"
};
const _hoisted_5 = { class: "text-body-2" };
const _hoisted_6 = { class: "text-caption das-dim ml-2" };
const _hoisted_7 = { class: "text-subtitle-2 mb-2" };
const _hoisted_8 = { class: "text-caption das-dim mb-3" };
const _hoisted_9 = { class: "text-subtitle-2 mb-2" };
const _hoisted_10 = { class: "text-subtitle-2 mb-2" };
const _hoisted_11 = { class: "text-subtitle-2 mb-2" };
const _hoisted_12 = { class: "d-flex" };
const {computed,onMounted,reactive,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Config",
  props: {
    initialConfig: {},
    api: {}
  },
  emits: ["save", "close", "switch"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const saving = ref(false);
    const defaults = {
      enabled: false,
      cron: "0 8 * * *",
      actors: "",
      max_works: 10,
      sort_by: "time",
      proxy: false,
      notify: false,
      auto_subscribe: false,
      auto_only_new: true,
      auto_min_vote: 0,
      auto_types: "电影,电视剧",
      auto_max_per_run: 5,
      onlyonce: false,
      subscribe_save_path: "",
      subscribe_sites: [],
      douban_cookie: ""
    };
    const local = reactive({ ...defaults });
    const cookieStatus = computed(() => {
      const initial = props.initialConfig;
      const source = initial?.douban_cookie_source;
      if (source === "manual") return "插件内手填的 Cookie";
      if (source === "cookiecloud") return "宿主 CookieCloud（自动读取，已生效）";
      const hint = initial?.douban_cookie_hint;
      return hint ? `未取到，原因：${String(hint)}` : "尚未取到（刷新一次后会显示）";
    });
    const cronPresets = [
      { label: "每 6 小时", value: "0 */6 * * *" },
      { label: "每 12 小时", value: "0 */12 * * *" },
      { label: "每天 08:00", value: "0 8 * * *" },
      { label: "每天 20:00", value: "0 20 * * *" },
      { label: "每周一 08:00", value: "0 8 * * 1" }
    ];
    const sortOptions = [
      { label: "按时间（最新作品优先）", value: "time" },
      { label: "豆瓣默认（最受关注优先）", value: "collection" }
    ];
    const cronPreset = computed({
      get: () => cronPresets.some((item) => item.value === local.cron) ? local.cron : "",
      set: (value) => {
        if (value) local.cron = value;
      }
    });
    const autoTypes = computed({
      get: () => String(local.auto_types || "").split(/[,，;；]/).map((item) => item.trim()).filter((item) => item === "电影" || item === "电视剧"),
      set: (value) => {
        local.auto_types = (value && value.length ? value : ["电影", "电视剧"]).join(",");
      }
    });
    const searchName = ref("");
    const searching = ref(false);
    const searched = ref(false);
    const candidates = ref([]);
    async function searchActor() {
      const api = resolveApi(props);
      const name = searchName.value.trim();
      if (!api || !name) return;
      searching.value = true;
      try {
        const raw = await api.get(`${API_BASE}/search_actor`, { params: { name } });
        const res = unwrap(raw);
        candidates.value = res?.success ? res.data || [] : [];
        searched.value = true;
      } catch (err) {
        candidates.value = [];
        searched.value = true;
        console.warn(`[${PLUGIN_ID}] 搜索演员失败`, err);
      } finally {
        searching.value = false;
      }
    }
    function appendActor(id) {
      const lines = String(local.actors || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
      if (!lines.includes(id)) lines.push(id);
      local.actors = lines.join("\n");
    }
    function saveConfig() {
      saving.value = true;
      emit("save", JSON.parse(JSON.stringify(local)));
      window.setTimeout(() => {
        saving.value = false;
      }, 600);
    }
    onMounted(() => {
      const initial = props.initialConfig;
      if (initial && typeof initial === "object") {
        Object.keys(defaults).forEach((key) => {
          const value = initial[key];
          if (value !== void 0) {
            local[key] = value;
          }
        });
      }
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_textarea = _resolveComponent("v-textarea");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_img = _resolveComponent("v-img");
      const _component_v_avatar = _resolveComponent("v-avatar");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-4"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cog-outline",
                class: "mr-2"
              }),
              _cache[20] || (_cache[20] = _createElementVNode("h3", { class: "ma-0" }, "豆瓣演员订阅 · 设置", -1)),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                icon: "mdi-close",
                variant: "text",
                size: "small",
                title: "关闭",
                onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
              })
            ]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_switch, {
                      modelValue: local.enabled,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => local.enabled = $event),
                      label: "启用插件",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_switch, {
                      modelValue: local.proxy,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => local.proxy = $event),
                      label: "使用代理服务器",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_switch, {
                      modelValue: local.onlyonce,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => local.onlyonce = $event),
                      label: "保存后立即刷新一次",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_3, [
              _createVNode(_component_v_icon, {
                icon: "mdi-account-multiple-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[21] || (_cache[21] = _createTextVNode(" 订阅的演员 ", -1))
            ]),
            _createVNode(_component_v_textarea, {
              modelValue: local.actors,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => local.actors = $event),
              label: "演员列表",
              placeholder: "支持换行、逗号、顿号、分号分隔：\n刘德华, 吴京, 张译\n也可直接粘贴豆瓣人物主页链接（推荐，最稳）：\nhttps://www.douban.com/personage/37871253/",
              hint: "可用逗号/顿号/分号/换行分隔。填「人物 ID」或直接粘贴人物主页链接可跳过搜索——豆瓣匿名搜索有严格限流，演员多时按名称搜索会失败。",
              "persistent-hint": "",
              rows: "4",
              density: "comfortable",
              "auto-grow": "",
              class: "mb-3"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_text_field, {
              modelValue: searchName.value,
              "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => searchName.value = $event),
              label: "搜索豆瓣演员（辅助填写人物 ID）",
              density: "comfortable",
              "hide-details": "",
              "prepend-inner-icon": "mdi-magnify",
              class: "mb-2",
              onKeyup: _withKeys(searchActor, ["enter"])
            }, {
              append: _withCtx(() => [
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  loading: searching.value,
                  onClick: searchActor
                }, {
                  default: _withCtx(() => [..._cache[22] || (_cache[22] = [
                    _createTextVNode(" 搜索 ", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            }, 8, ["modelValue"]),
            candidates.value.length || searched.value ? (_openBlock(), _createBlock(_component_v_card, {
              key: 0,
              variant: "tonal",
              class: "pa-2 mb-3"
            }, {
              default: _withCtx(() => [
                !candidates.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_4, " 未搜索到匹配的演员，换一个名字或直接填写人物 ID。 ")) : _createCommentVNode("", true),
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(candidates.value, (item) => {
                  return _openBlock(), _createElementBlock("div", {
                    key: item.id,
                    class: "d-flex align-center py-1"
                  }, [
                    _createVNode(_component_v_avatar, {
                      size: "28",
                      class: "mr-2"
                    }, {
                      default: _withCtx(() => [
                        item.avatar ? (_openBlock(), _createBlock(_component_v_img, {
                          key: 0,
                          src: item.avatar
                        }, null, 8, ["src"])) : (_openBlock(), _createBlock(_component_v_icon, {
                          key: 1,
                          icon: "mdi-account-outline",
                          size: "16"
                        }))
                      ]),
                      _: 2
                    }, 1024),
                    _createElementVNode("span", _hoisted_5, _toDisplayString(item.name), 1),
                    _createElementVNode("span", _hoisted_6, "ID " + _toDisplayString(item.id), 1),
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      size: "x-small",
                      variant: "text",
                      color: "primary",
                      onClick: ($event) => appendActor(item.id)
                    }, {
                      default: _withCtx(() => [..._cache[23] || (_cache[23] = [
                        _createTextVNode(" 添加 ID ", -1)
                      ])]),
                      _: 1
                    }, 8, ["onClick"])
                  ]);
                }), 128))
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_7, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cookie-outline",
                size: "18",
                class: "mr-1"
              }),
              _cache[24] || (_cache[24] = _createTextVNode(" 豆瓣 Cookie（提高搜索额度） ", -1))
            ]),
            _createVNode(_component_v_alert, {
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "mb-2"
            }, {
              default: _withCtx(() => [..._cache[25] || (_cache[25] = [
                _createTextVNode(" 默认", -1),
                _createElementVNode("b", null, "自动", -1),
                _createTextVNode("从宿主「系统设置 → CookieCloud」读取豆瓣登录态，这里无需填写。 仅当 CookieCloud 没同步豆瓣、或想临时换一个账号时，才在下面手工粘贴覆盖。 ", -1)
              ])]),
              _: 1
            }),
            _createVNode(_component_v_textarea, {
              modelValue: local.douban_cookie,
              "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => local.douban_cookie = $event),
              label: "豆瓣 Cookie（留空 = 自动用宿主 CookieCloud）",
              placeholder: "bid=xxx; dbcl2=xxx; ck=xxx",
              hint: "浏览器登录豆瓣后按 F12 → 网络 → 任意 douban.com 请求 → 请求头 Cookie 整段复制（务必含 dbcl2）。",
              "persistent-hint": "",
              rows: "2",
              density: "comfortable",
              "auto-grow": "",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createElementVNode("div", _hoisted_8, "当前生效来源：" + _toDisplayString(cookieStatus.value), 1),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_9, [
              _createVNode(_component_v_icon, {
                icon: "mdi-tune-variant",
                size: "18",
                class: "mr-1"
              }),
              _cache[26] || (_cache[26] = _createTextVNode(" 抓取与展示 ", -1))
            ]),
            _createVNode(_component_v_row, { dense: "" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_select, {
                      modelValue: cronPreset.value,
                      "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => cronPreset.value = $event),
                      items: cronPresets,
                      "item-title": "label",
                      "item-value": "value",
                      label: "刷新周期预设",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "6"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.cron,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => local.cron = $event),
                      label: "cron 表达式",
                      hint: "5 段式，例如 0 8 * * * 表示每天 08:00",
                      "persistent-hint": "",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_text_field, {
                      modelValue: local.max_works,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => local.max_works = $event),
                      modelModifiers: { number: true },
                      type: "number",
                      min: "5",
                      max: "10",
                      label: "每位演员展示作品数",
                      hint: "豆瓣作品集接口不支持翻页，最多只能取到 10 部",
                      "persistent-hint": "",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_select, {
                      modelValue: local.sort_by,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => local.sort_by = $event),
                      items: sortOptions,
                      "item-title": "label",
                      "item-value": "value",
                      label: "作品排序",
                      density: "comfortable"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  sm: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_switch, {
                      modelValue: local.notify,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => local.notify = $event),
                      label: "刷新后发送系统通知",
                      color: "primary",
                      "hide-details": "",
                      class: "mt-1"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_10, [
              _createVNode(_component_v_icon, {
                icon: "mdi-auto-fix",
                size: "18",
                class: "mr-1"
              }),
              _cache[27] || (_cache[27] = _createTextVNode(" 自动订阅 ", -1))
            ]),
            _createVNode(_component_v_switch, {
              modelValue: local.auto_subscribe,
              "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => local.auto_subscribe = $event),
              label: "开启自动订阅：把新发现的、满足条件的作品直接提交订阅",
              color: "primary",
              "hide-details": "",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            local.auto_subscribe ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
              _createVNode(_component_v_switch, {
                modelValue: local.auto_only_new,
                "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => local.auto_only_new = $event),
                label: "仅订阅新出现的作品（首次抓取只建立基线，避免一次性订阅全部历史作品）",
                color: "primary",
                "hide-details": "",
                density: "compact",
                class: "mb-3"
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_row, { dense: "" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_col, {
                    cols: "12",
                    sm: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: local.auto_min_vote,
                        "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => local.auto_min_vote = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        step: "0.5",
                        min: "0",
                        max: "10",
                        label: "最低豆瓣评分",
                        hint: "0 表示不限制",
                        "persistent-hint": "",
                        density: "comfortable"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    sm: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_text_field, {
                        modelValue: local.auto_max_per_run,
                        "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => local.auto_max_per_run = $event),
                        modelModifiers: { number: true },
                        type: "number",
                        min: "1",
                        max: "100",
                        label: "单次订阅上限",
                        hint: "防止首次开启时批量误订阅",
                        "persistent-hint": "",
                        density: "comfortable"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    sm: "4"
                  }, {
                    default: _withCtx(() => [
                      _cache[30] || (_cache[30] = _createElementVNode("div", { class: "text-caption mb-1" }, "参与自动订阅的类型", -1)),
                      _createVNode(_component_v_btn_toggle, {
                        modelValue: autoTypes.value,
                        "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => autoTypes.value = $event),
                        multiple: "",
                        density: "compact",
                        variant: "outlined",
                        divided: ""
                      }, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_btn, {
                            size: "small",
                            value: "电影"
                          }, {
                            default: _withCtx(() => [..._cache[28] || (_cache[28] = [
                              _createTextVNode("电影", -1)
                            ])]),
                            _: 1
                          }),
                          _createVNode(_component_v_btn, {
                            size: "small",
                            value: "电视剧"
                          }, {
                            default: _withCtx(() => [..._cache[29] || (_cache[29] = [
                              _createTextVNode("电视剧", -1)
                            ])]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ], 64)) : _createCommentVNode("", true),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_11, [
              _createVNode(_component_v_icon, {
                icon: "mdi-tune-variant",
                size: "18",
                class: "mr-1"
              }),
              _cache[31] || (_cache[31] = _createTextVNode(" 订阅选项 ", -1))
            ]),
            _createVNode(SubscribePrefs, {
              "save-path": local.subscribe_save_path,
              "onUpdate:savePath": _cache[17] || (_cache[17] = ($event) => local.subscribe_save_path = $event),
              sites: local.subscribe_sites,
              "onUpdate:sites": _cache[18] || (_cache[18] = ($event) => local.subscribe_sites = $event),
              api: props.api,
              "show-save": false
            }, null, 8, ["save-path", "sites", "api"]),
            _createVNode(_component_v_alert, {
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "my-3"
            }, {
              default: _withCtx(() => [..._cache[32] || (_cache[32] = [
                _createTextVNode(" 保存由宿主完成：本组件只向宿主抛出 ", -1),
                _createElementVNode("code", null, "save", -1),
                _createTextVNode(" 事件， 宿主会调用 ", -1),
                _createElementVNode("code", null, "api.put('plugin/{id}', cfg)", -1),
                _createTextVNode(" 持久化并重新初始化插件。 ", -1)
              ])]),
              _: 1
            }),
            _createElementVNode("div", _hoisted_12, [
              _createVNode(_component_v_btn, {
                color: "primary",
                loading: saving.value,
                onClick: saveConfig
              }, {
                default: _withCtx(() => [..._cache[33] || (_cache[33] = [
                  _createTextVNode("保存配置", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              _createVNode(_component_v_btn, {
                variant: "text",
                class: "ml-2",
                onClick: _cache[19] || (_cache[19] = ($event) => emit("switch"))
              }, {
                default: _withCtx(() => [..._cache[34] || (_cache[34] = [
                  _createTextVNode("查看详情", -1)
                ])]),
                _: 1
              })
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-4e0f09a2"]]);

export { Config as default };
