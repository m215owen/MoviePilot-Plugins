import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Panel from './__federation_expose_Page-CUpvBUgD.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "AppPage",
  props: {
    api: {},
    config: {},
    pluginId: {},
    navKey: {}
  },
  setup(__props) {
    const props = __props;
    return (_ctx, _cache) => {
      return _openBlock(), _createBlock(Panel, {
        api: props.api,
        config: props.config,
        "plugin-id": props.pluginId,
        "nav-key": props.navKey,
        mode: "main",
        full: ""
      }, null, 8, ["api", "config", "plugin-id", "nav-key"]);
    };
  }
});

export { _sfc_main as default };
