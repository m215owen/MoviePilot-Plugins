import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { A as ActorWall } from './ActorWall-54mr42sc.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {createVNode:_createVNode,normalizeClass:_normalizeClass,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Page",
  props: {
    api: {},
    config: {},
    pluginId: {},
    nativeSubscribe: { type: Function },
    full: { type: Boolean }
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      return _openBlock(), _createElementBlock("div", {
        class: _normalizeClass(props.full ? "pa-4" : "pa-2")
      }, [
        _createVNode(ActorWall, {
          api: props.api,
          config: props.config,
          "plugin-id": props.pluginId,
          "native-subscribe": props.nativeSubscribe
        }, null, 8, ["api", "config", "plugin-id", "native-subscribe"])
      ], 2);
    };
  }
});

export { _sfc_main as default };
