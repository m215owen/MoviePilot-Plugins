import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './api-WVyoRzoO.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');

const _hoisted_1 = {
  key: 0,
  class: "das-errors"
};
const {onBeforeUnmount,ref,watch} = await importShared('vue');

const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "ErrorAlerts",
  props: {
    errors: { default: () => [] },
    duration: { default: 5e3 }
  },
  setup(__props) {
    const props = __props;
    const visible = ref(true);
    let timer;
    function clearTimer() {
      if (timer !== void 0) {
        window.clearTimeout(timer);
        timer = void 0;
      }
    }
    function show() {
      clearTimer();
      visible.value = true;
      if (props.duration > 0) {
        timer = window.setTimeout(() => {
          visible.value = false;
        }, props.duration);
      }
    }
    watch(
      () => (props.errors || []).join("\n"),
      () => {
        if (!props.errors || !props.errors.length) {
          clearTimer();
          visible.value = true;
          return;
        }
        show();
      },
      { immediate: true }
    );
    onBeforeUnmount(clearTimer);
    return (_ctx, _cache) => {
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_chip = _resolveComponent("v-chip");
      return __props.errors.length ? (_openBlock(), _createElementBlock("div", _hoisted_1, [
        visible.value ? (_openBlock(true), _createElementBlock(_Fragment, { key: 0 }, _renderList(__props.errors, (item, index) => {
          return _openBlock(), _createBlock(_component_v_alert, {
            key: `${index}-${item}`,
            type: "warning",
            variant: "tonal",
            density: "compact",
            class: "mb-2"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(item), 1)
            ]),
            _: 2
          }, 1024);
        }), 128)) : (_openBlock(), _createBlock(_component_v_chip, {
          key: 1,
          size: "small",
          variant: "tonal",
          color: "warning",
          "prepend-icon": "mdi-alert-outline",
          onClick: show
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(__props.errors.length) + " 项异常（点击查看） ", 1)
          ]),
          _: 1
        }))
      ])) : _createCommentVNode("", true);
    };
  }
});

const ErrorAlerts = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-df55bed5"]]);

export { ErrorAlerts as E };
