import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, o as resourceSearchUrl, r as resolveApi, q as searchSiteKind, t as fetchSearchSites, v as fetchDefaultSearchSites } from './_plugin-vue_export-helper-qagfV18f.js';

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,withCtx:_withCtx,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,renderList:_renderList,Fragment:_Fragment$1,createBlock:_createBlock$1,createTextVNode:_createTextVNode} = await importShared('vue');

const _hoisted_1 = { class: "text-body-1" };
const _hoisted_2 = { class: "text-caption text-medium-emphasis" };
const _hoisted_3 = {
  key: 0,
  class: "text-caption text-medium-emphasis py-3 text-center"
};
const _hoisted_4 = {
  key: 1,
  class: "text-caption text-medium-emphasis py-3"
};
const _hoisted_5 = {
  key: 2,
  class: "text-caption text-medium-emphasis py-3"
};
const _hoisted_6 = {
  key: 3,
  class: "das-site-list"
};
const _hoisted_7 = {
  key: 4,
  class: "text-caption text-medium-emphasis mt-2"
};
const {computed: computed$1,ref: ref$1,watch} = await importShared('vue');

const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "SitePickDialog",
  props: {
    modelValue: { type: Boolean },
    sites: {},
    selected: { default: () => [] },
    loading: { type: Boolean, default: false },
    title: { default: "选择站点" }
  },
  emits: ["update:modelValue", "confirm"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const picked = ref$1([]);
    const filter = ref$1("");
    const shown = computed$1(() => {
      const keyword = filter.value.trim().toLowerCase();
      if (!keyword) return props.sites;
      return props.sites.filter((site) => {
        const name = String(site.name || "").toLowerCase();
        const domain = String(site.domain || "").toLowerCase();
        return name.includes(keyword) || domain.includes(keyword);
      });
    });
    watch(
      () => props.modelValue,
      (visible) => {
        if (!visible) return;
        filter.value = "";
        const available = new Set(props.sites.map((site) => site.id));
        picked.value = props.selected.filter((id) => available.has(id));
        if (!props.sites.length) picked.value = [...props.selected];
      }
    );
    watch(
      () => props.sites,
      (sites) => {
        if (!props.modelValue || !sites.length) return;
        const available = new Set(sites.map((site) => site.id));
        picked.value = picked.value.filter((id) => available.has(id));
      }
    );
    function toggle(id, value) {
      const next = new Set(picked.value);
      if (value) next.add(id);
      else next.delete(id);
      picked.value = Array.from(next);
    }
    function selectAll() {
      picked.value = props.sites.map((site) => site.id);
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$1("v-icon");
      const _component_v_spacer = _resolveComponent$1("v-spacer");
      const _component_v_card_title = _resolveComponent$1("v-card-title");
      const _component_v_divider = _resolveComponent$1("v-divider");
      const _component_v_text_field = _resolveComponent$1("v-text-field");
      const _component_v_checkbox = _resolveComponent$1("v-checkbox");
      const _component_v_card_text = _resolveComponent$1("v-card-text");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_card_actions = _resolveComponent$1("v-card-actions");
      const _component_v_card = _resolveComponent$1("v-card");
      const _component_v_dialog = _resolveComponent$1("v-dialog");
      return _openBlock$1(), _createBlock$1(_component_v_dialog, {
        "model-value": __props.modelValue,
        "max-width": "520",
        scrollable: "",
        "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => emit("update:modelValue", $event))
      }, {
        default: _withCtx(() => [
          _createVNode$1(_component_v_card, null, {
            default: _withCtx(() => [
              _createVNode$1(_component_v_card_title, { class: "d-flex align-center" }, {
                default: _withCtx(() => [
                  _createVNode$1(_component_v_icon, {
                    icon: "mdi-server-network",
                    size: "20",
                    class: "mr-2"
                  }),
                  _createElementVNode("span", _hoisted_1, _toDisplayString(__props.title || "选择站点"), 1),
                  _createVNode$1(_component_v_spacer),
                  _createElementVNode("span", _hoisted_2, " 已选择 " + _toDisplayString(picked.value.length) + "/" + _toDisplayString(__props.sites.length) + " 个站点 ", 1)
                ]),
                _: 1
              }),
              _createVNode$1(_component_v_divider),
              _createVNode$1(_component_v_card_text, { class: "pb-2" }, {
                default: _withCtx(() => [
                  _createVNode$1(_component_v_text_field, {
                    modelValue: filter.value,
                    "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => filter.value = $event),
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    clearable: "",
                    "prepend-inner-icon": "mdi-magnify",
                    placeholder: "站点搜索",
                    class: "mb-2"
                  }, null, 8, ["modelValue"]),
                  __props.loading ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_3, " 正在读取站点清单… ")) : !__props.sites.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_4, " 宿主没有可用的站点，将按宿主默认搜索站点搜索。 ")) : !shown.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_5, " 没有匹配「" + _toDisplayString(filter.value) + "」的站点。 ", 1)) : (_openBlock$1(), _createElementBlock$1("div", _hoisted_6, [
                    (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList(shown.value, (site) => {
                      return _openBlock$1(), _createBlock$1(_component_v_checkbox, {
                        key: site.id,
                        "model-value": picked.value.includes(site.id),
                        label: site.name,
                        title: site.domain || site.name,
                        density: "compact",
                        "hide-details": "",
                        class: "das-site-item",
                        "onUpdate:modelValue": ($event) => toggle(site.id, $event)
                      }, null, 8, ["model-value", "label", "title", "onUpdate:modelValue"]);
                    }), 128))
                  ])),
                  !__props.loading && __props.sites.length && !picked.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_7, " 未选择任何站点时，按宿主的默认站点搜索全部。 ")) : _createCommentVNode$1("", true)
                ]),
                _: 1
              }),
              _createVNode$1(_component_v_divider),
              _createVNode$1(_component_v_card_actions, null, {
                default: _withCtx(() => [
                  _createVNode$1(_component_v_btn, {
                    size: "small",
                    variant: "text",
                    disabled: !__props.sites.length,
                    onClick: selectAll
                  }, {
                    default: _withCtx(() => [..._cache[5] || (_cache[5] = [
                      _createTextVNode(" 选择全部 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode$1(_component_v_btn, {
                    size: "small",
                    variant: "text",
                    disabled: !picked.value.length,
                    onClick: _cache[1] || (_cache[1] = ($event) => picked.value = [])
                  }, {
                    default: _withCtx(() => [..._cache[6] || (_cache[6] = [
                      _createTextVNode(" 取消全选 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode$1(_component_v_spacer),
                  _createVNode$1(_component_v_btn, {
                    size: "small",
                    variant: "text",
                    onClick: _cache[2] || (_cache[2] = ($event) => emit("update:modelValue", false))
                  }, {
                    default: _withCtx(() => [..._cache[7] || (_cache[7] = [
                      _createTextVNode("取消", -1)
                    ])]),
                    _: 1
                  }),
                  _createVNode$1(_component_v_btn, {
                    size: "small",
                    color: "primary",
                    variant: "flat",
                    disabled: __props.loading,
                    onClick: _cache[3] || (_cache[3] = ($event) => emit("confirm", [...picked.value]))
                  }, {
                    default: _withCtx(() => [..._cache[8] || (_cache[8] = [
                      _createTextVNode(" 确认 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled"])
                ]),
                _: 1
              })
            ]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["model-value"]);
    };
  }
});

const SitePickDialog = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-e2d8e002"]]);

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,Fragment:_Fragment,createElementBlock:_createElementBlock} = await importShared('vue');

const {computed,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "SearchResourceButton",
  props: {
    work: {},
    api: {},
    size: { default: "small" },
    variant: { default: "text" }
  },
  emits: ["error"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const cache = /* @__PURE__ */ new Map();
    const visible = ref(false);
    const loading = ref(false);
    const sites = ref([]);
    const selected = ref([]);
    const searchable = computed(() => Boolean(resourceSearchUrl(props.work)));
    async function open() {
      const api = resolveApi({ api: props.api });
      if (!api) return;
      const kind = searchSiteKind(props.work.type);
      const cached = cache.get(kind);
      if (cached) {
        sites.value = cached.sites;
        selected.value = cached.defaults;
        if (!cached.sites.length) {
          launch([]);
          return;
        }
        visible.value = true;
        return;
      }
      loading.value = true;
      try {
        const [options, defaults] = await Promise.all([
          fetchSearchSites(api, props.work.type),
          fetchDefaultSearchSites(api)
        ]);
        const available = new Set(options.map((site) => site.id));
        let pick = defaults.filter((id) => available.has(id));
        if (options.length && !pick.length) pick = options.map((site) => site.id);
        cache.set(kind, { sites: options, defaults: pick });
        sites.value = options;
        selected.value = pick;
        if (!options.length) {
          launch([]);
          return;
        }
        visible.value = true;
      } finally {
        loading.value = false;
      }
    }
    function confirm(ids) {
      visible.value = false;
      launch(ids);
    }
    function launch(ids) {
      const url = resourceSearchUrl(props.work, ids);
      if (!url) {
        emit("error", "这部作品没有可用的检索条件");
        return;
      }
      window.open(url, "_blank", "noopener");
    }
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent("v-btn");
      return _openBlock(), _createElementBlock(_Fragment, null, [
        searchable.value ? (_openBlock(), _createBlock(_component_v_btn, {
          key: 0,
          size: __props.size,
          variant: __props.variant,
          icon: "mdi-magnify",
          loading: loading.value,
          title: "搜索这部作品的资源：先选站点，再在 MoviePilot 资源搜索页打开（新标签页）",
          onClick: open
        }, null, 8, ["size", "variant", "loading"])) : _createCommentVNode("", true),
        _createVNode(SitePickDialog, {
          modelValue: visible.value,
          "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => visible.value = $event),
          sites: sites.value,
          selected: selected.value,
          loading: loading.value,
          title: "选择搜索站点",
          onConfirm: confirm
        }, null, 8, ["modelValue", "sites", "selected", "loading"])
      ], 64);
    };
  }
});

export { _sfc_main as _ };
