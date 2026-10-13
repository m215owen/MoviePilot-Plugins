import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { r as resolveApi, g as unignoreWork, P as PLUGIN_ID, _ as _export_sfc, w as workKey, p as proxyImage } from './api-WVyoRzoO.js';

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,createVNode:_createVNode$1,createElementVNode:_createElementVNode$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,renderList:_renderList$1,Fragment:_Fragment$1,createBlock:_createBlock$1} = await importShared('vue');

const _hoisted_1$1 = { key: 0 };
const _hoisted_2$1 = {
  key: 0,
  class: "text-medium-emphasis text-body-2 py-4 text-center"
};
const _hoisted_3$1 = ["title"];
const _hoisted_4$1 = {
  key: 0,
  class: "text-caption das-dim mx-2"
};
const {computed,inject,ref} = await importShared('vue');
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "IgnoredManager",
  props: {
    api: {},
    ignored: {},
    count: {}
  },
  emits: ["changed"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const toast = inject("moviepilot:toast", null);
    const open = ref(false);
    const busyKey = ref("");
    const busyAll = ref(false);
    const list = computed(() => props.ignored || []);
    function notify(type, message) {
      const handler = toast && toast[type];
      if (typeof handler === "function") {
        handler.call(toast, message);
        return;
      }
      console[type === "error" ? "warn" : "info"](`[${PLUGIN_ID}] ${message}`);
    }
    async function restore(item) {
      const api = resolveApi(props);
      if (!api) return;
      busyKey.value = item.key;
      try {
        const res = await unignoreWork(api, item.key);
        notify(res.ok ? "success" : "error", res.message);
        if (res.ok) emit("changed");
      } finally {
        busyKey.value = "";
      }
    }
    async function restoreAll() {
      const api = resolveApi(props);
      if (!api) return;
      busyAll.value = true;
      try {
        const res = await unignoreWork(api, "", true);
        notify(res.ok ? "success" : "error", res.message);
        if (res.ok) emit("changed");
      } finally {
        busyAll.value = false;
      }
    }
    return (_ctx, _cache) => {
      const _component_v_chip = _resolveComponent$1("v-chip");
      const _component_v_icon = _resolveComponent$1("v-icon");
      const _component_v_spacer = _resolveComponent$1("v-spacer");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_card_title = _resolveComponent$1("v-card-title");
      const _component_v_divider = _resolveComponent$1("v-divider");
      const _component_v_card_text = _resolveComponent$1("v-card-text");
      const _component_v_card_actions = _resolveComponent$1("v-card-actions");
      const _component_v_card = _resolveComponent$1("v-card");
      const _component_v_dialog = _resolveComponent$1("v-dialog");
      return __props.count ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_1$1, [
        _createVNode$1(_component_v_chip, {
          size: "small",
          variant: "tonal",
          "prepend-icon": "mdi-eye-off-outline",
          title: "查看并恢复被忽略的作品",
          onClick: _cache[0] || (_cache[0] = ($event) => open.value = true)
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(" 已忽略 " + _toDisplayString$1(__props.count) + " 部 ", 1)
          ]),
          _: 1
        }),
        _createVNode$1(_component_v_dialog, {
          modelValue: open.value,
          "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => open.value = $event),
          "max-width": "640"
        }, {
          default: _withCtx$1(() => [
            _createVNode$1(_component_v_card, null, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_v_icon, {
                      icon: "mdi-eye-off-outline",
                      class: "mr-2"
                    }),
                    _cache[4] || (_cache[4] = _createElementVNode$1("span", { class: "text-body-1" }, "已忽略的作品", -1)),
                    _createVNode$1(_component_v_spacer),
                    _createVNode$1(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      onClick: _cache[1] || (_cache[1] = ($event) => open.value = false)
                    }, {
                      default: _withCtx$1(() => [..._cache[3] || (_cache[3] = [
                        _createTextVNode$1("关闭", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_v_divider),
                _createVNode$1(_component_v_card_text, { class: "das-scroll" }, {
                  default: _withCtx$1(() => [
                    !list.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, " 还没有忽略任何作品。 ")) : _createCommentVNode$1("", true),
                    (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(list.value, (item) => {
                      return _openBlock$1(), _createElementBlock$1("div", {
                        key: item.key,
                        class: "d-flex align-center py-1"
                      }, [
                        _createElementVNode$1("span", {
                          class: "text-body-2 das-ellipsis",
                          title: item.title || item.key
                        }, _toDisplayString$1(item.title || item.media_id || item.key), 9, _hoisted_3$1),
                        item.year ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_4$1, _toDisplayString$1(item.year), 1)) : _createCommentVNode$1("", true),
                        item.type ? (_openBlock$1(), _createBlock$1(_component_v_chip, {
                          key: 1,
                          size: "x-small",
                          variant: "tonal",
                          label: "",
                          class: "mr-2"
                        }, {
                          default: _withCtx$1(() => [
                            _createTextVNode$1(_toDisplayString$1(item.type), 1)
                          ]),
                          _: 2
                        }, 1024)) : _createCommentVNode$1("", true),
                        _createVNode$1(_component_v_spacer),
                        _createVNode$1(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          color: "primary",
                          loading: busyKey.value === item.key,
                          disabled: busyAll.value,
                          onClick: ($event) => restore(item)
                        }, {
                          default: _withCtx$1(() => [..._cache[5] || (_cache[5] = [
                            _createTextVNode$1(" 恢复 ", -1)
                          ])]),
                          _: 1
                        }, 8, ["loading", "disabled", "onClick"])
                      ]);
                    }), 128))
                  ]),
                  _: 1
                }),
                _createVNode$1(_component_v_divider),
                _createVNode$1(_component_v_card_actions, null, {
                  default: _withCtx$1(() => [
                    _cache[7] || (_cache[7] = _createElementVNode$1("span", { class: "text-caption das-dim ml-2" }, "恢复后下次刷新即会重新出现", -1)),
                    _createVNode$1(_component_v_spacer),
                    _createVNode$1(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      color: "warning",
                      loading: busyAll.value,
                      disabled: !list.value.length,
                      onClick: restoreAll
                    }, {
                      default: _withCtx$1(() => [..._cache[6] || (_cache[6] = [
                        _createTextVNode$1(" 全部恢复 ", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading", "disabled"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"])
      ])) : _createCommentVNode$1("", true);
    };
  }
});

const IgnoredManager = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-2bf044f5"]]);

const {defineComponent:_defineComponent} = await importShared('vue');

const {toDisplayString:_toDisplayString,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,unref:_unref,resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,withCtx:_withCtx,createTextVNode:_createTextVNode,createBlock:_createBlock} = await importShared('vue');

const _hoisted_1 = {
  key: 0,
  class: "text-medium-emphasis text-body-2 py-4 text-center"
};
const _hoisted_2 = {
  key: 1,
  class: "das-grid"
};
const _hoisted_3 = { class: "das-poster" };
const _hoisted_4 = { class: "das-poster-ph" };
const _hoisted_5 = { class: "das-poster-ph" };
const _hoisted_6 = ["title"];
const _hoisted_7 = { class: "das-meta" };
const _hoisted_8 = {
  key: 0,
  class: "das-dim"
};
const _hoisted_9 = {
  key: 1,
  class: "das-dim das-vote"
};
const _hoisted_10 = ["title"];
const _hoisted_11 = { class: "das-actors-text" };
const _hoisted_12 = {
  key: 1,
  class: "das-dim das-roles"
};
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "WorkGrid",
  props: {
    works: {},
    subscribedKeys: { default: () => [] },
    pendingKey: {},
    busy: { type: Boolean },
    emptyText: {},
    showActors: { type: Boolean, default: true }
  },
  emits: ["subscribe", "ignore"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    function isSubscribed(work) {
      return props.subscribedKeys.includes(workKey(work));
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_img = _resolveComponent("v-img");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card_actions = _resolveComponent("v-card-actions");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createElementBlock("div", null, [
        !__props.works.length ? (_openBlock(), _createElementBlock("div", _hoisted_1, _toDisplayString(__props.emptyText || "暂无作品数据"), 1)) : (_openBlock(), _createElementBlock("div", _hoisted_2, [
          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(__props.works, (work) => {
            return _openBlock(), _createBlock(_component_v_card, {
              key: _unref(workKey)(work),
              variant: "outlined",
              class: "das-card"
            }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_3, [
                  _createVNode(_component_v_img, {
                    src: _unref(proxyImage)(work.poster),
                    "aspect-ratio": 2 / 3,
                    cover: "",
                    class: "das-poster-img"
                  }, {
                    placeholder: _withCtx(() => [
                      _createElementVNode("div", _hoisted_4, [
                        _createVNode(_component_v_icon, {
                          icon: "mdi-image-outline",
                          size: "22"
                        })
                      ])
                    ]),
                    error: _withCtx(() => [
                      _createElementVNode("div", _hoisted_5, [
                        _createVNode(_component_v_icon, {
                          icon: "mdi-movie-open-off-outline",
                          size: "22"
                        })
                      ])
                    ]),
                    _: 1
                  }, 8, ["src"]),
                  work.is_new ? (_openBlock(), _createBlock(_component_v_chip, {
                    key: 0,
                    size: "x-small",
                    color: "error",
                    variant: "flat",
                    class: "das-badge das-badge-left"
                  }, {
                    default: _withCtx(() => [..._cache[0] || (_cache[0] = [
                      _createTextVNode(" 新 ", -1)
                    ])]),
                    _: 1
                  })) : _createCommentVNode("", true),
                  isSubscribed(work) ? (_openBlock(), _createBlock(_component_v_chip, {
                    key: 1,
                    size: "x-small",
                    color: "success",
                    variant: "flat",
                    class: "das-badge das-badge-right"
                  }, {
                    default: _withCtx(() => [..._cache[1] || (_cache[1] = [
                      _createTextVNode(" 已订阅 ", -1)
                    ])]),
                    _: 1
                  })) : _createCommentVNode("", true)
                ]),
                _createVNode(_component_v_card_text, { class: "pa-2 pb-1 das-body" }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", {
                      class: "das-title",
                      title: work.title
                    }, _toDisplayString(work.title), 9, _hoisted_6),
                    _createElementVNode("div", _hoisted_7, [
                      _createVNode(_component_v_chip, {
                        size: "x-small",
                        variant: "tonal",
                        label: ""
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(work.type || "未分类"), 1)
                        ]),
                        _: 2
                      }, 1024),
                      work.year ? (_openBlock(), _createElementBlock("span", _hoisted_8, _toDisplayString(work.year), 1)) : _createCommentVNode("", true),
                      work.vote ? (_openBlock(), _createElementBlock("span", _hoisted_9, [
                        _createVNode(_component_v_icon, {
                          icon: "mdi-star",
                          size: "11",
                          color: "amber"
                        }),
                        _createTextVNode(_toDisplayString(work.vote.toFixed(1)), 1)
                      ])) : _createCommentVNode("", true)
                    ]),
                    __props.showActors && work.actorNames && work.actorNames.length ? (_openBlock(), _createElementBlock("div", {
                      key: 0,
                      class: "das-actors",
                      title: work.actorNames.join(" / ")
                    }, [
                      _createVNode(_component_v_icon, {
                        icon: "mdi-account-outline",
                        size: "11"
                      }),
                      _createElementVNode("span", _hoisted_11, _toDisplayString(work.actorNames.join(" / ")), 1)
                    ], 8, _hoisted_10)) : _createCommentVNode("", true),
                    work.roles && work.roles.length ? (_openBlock(), _createElementBlock("div", _hoisted_12, _toDisplayString(work.roles.join(" / ")), 1)) : _createCommentVNode("", true)
                  ]),
                  _: 2
                }, 1024),
                _createVNode(_component_v_card_actions, { class: "pa-2 pt-0 das-actions" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_btn, {
                      size: "small",
                      class: "das-sub-btn",
                      color: isSubscribed(work) ? "success" : "primary",
                      variant: isSubscribed(work) ? "tonal" : "flat",
                      "prepend-icon": isSubscribed(work) ? "mdi-check" : "mdi-plus",
                      loading: __props.pendingKey === _unref(workKey)(work),
                      disabled: __props.busy,
                      onClick: ($event) => emit("subscribe", work)
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(isSubscribed(work) ? "已订阅" : "订阅"), 1)
                      ]),
                      _: 2
                    }, 1032, ["color", "variant", "prepend-icon", "loading", "disabled", "onClick"]),
                    work.url ? (_openBlock(), _createBlock(_component_v_btn, {
                      key: 0,
                      size: "small",
                      variant: "text",
                      icon: "mdi-open-in-new",
                      title: "打开豆瓣条目",
                      href: work.url,
                      target: "_blank"
                    }, null, 8, ["href"])) : _createCommentVNode("", true),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      icon: "mdi-eye-off-outline",
                      title: "忽略这部作品：不再展示，也不会被自动订阅",
                      disabled: __props.busy,
                      onClick: ($event) => emit("ignore", work)
                    }, null, 8, ["disabled", "onClick"])
                  ]),
                  _: 2
                }, 1024)
              ]),
              _: 2
            }, 1024);
          }), 128))
        ]))
      ]);
    };
  }
});

const WorkGrid = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-3da403a7"]]);

export { IgnoredManager as I, WorkGrid as W };
