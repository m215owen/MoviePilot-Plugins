import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { A as ActorWall } from './ActorWall-54mr42sc.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "AppPage",
  props: {
    api: {},
    config: {},
    pluginId: {},
    nativeSubscribe: { type: Function }
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      return _openBlock(), _createBlock(ActorWall, {
        api: props.api,
        config: props.config,
        "plugin-id": props.pluginId,
        "native-subscribe": props.nativeSubscribe,
        full: ""
      }, null, 8, ["api", "config", "plugin-id", "native-subscribe"]);
    };
  }
});

export { _sfc_main as default };
