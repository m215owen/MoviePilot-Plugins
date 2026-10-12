import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { w as workKey, _ as _export_sfc } from './_plugin-vue_export-helper-CY9eCSTe.js';

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
const _hoisted_10 = {
  key: 0,
  class: "das-dim das-roles"
};
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "WorkGrid",
  props: {
    works: {},
    subscribedKeys: {},
    pendingKey: {},
    busy: { type: Boolean },
    emptyText: {}
  },
  emits: ["subscribe"],
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
                    src: work.poster,
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
                    work.roles && work.roles.length ? (_openBlock(), _createElementBlock("div", _hoisted_10, _toDisplayString(work.roles.join(" / ")), 1)) : _createCommentVNode("", true)
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
                    }, null, 8, ["href"])) : _createCommentVNode("", true)
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

const WorkGrid = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-17a16a7c"]]);

export { WorkGrid as W };
