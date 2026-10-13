import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { r as resolveApi, h as fetchPathOptions, j as fetchDownloaderOptions, k as fetchSiteOptions, A as API_BASE, n as normalizeResult, _ as _export_sfc } from './_plugin-vue_export-helper-DkqlrLa1.js';

const {useModel:_useModel,mergeModels:_mergeModels,defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,createBlock:_createBlock,toDisplayString:_toDisplayString} = await importShared('vue');

const _hoisted_1 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const _hoisted_2 = {
  key: 0,
  class: "text-caption text-warning"
};
const _hoisted_3 = {
  key: 0,
  class: "text-caption text-warning mt-n2"
};
const {computed,onMounted,ref,watch} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "SubscribePrefs",
  props: /* @__PURE__ */ _mergeModels({
    api: {},
    showSave: { type: Boolean, default: true }
  }, {
    "savePath": { default: "" },
    "savePathModifiers": {},
    "downloader": { default: "" },
    "downloaderModifiers": {},
    "sites": { default: () => [] },
    "sitesModifiers": {}
  }),
  emits: /* @__PURE__ */ _mergeModels(["saved"], ["update:savePath", "update:downloader", "update:sites"]),
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const savePath = _useModel(__props, "savePath");
    const downloader = _useModel(__props, "downloader");
    const sites = _useModel(__props, "sites");
    const pathOptions = ref([]);
    const downloaderOptions = ref([]);
    const siteOptions = ref([]);
    const saving = ref(false);
    const loadingOptions = ref(false);
    const loaded = ref(false);
    const pathItems = computed(
      () => pathOptions.value.map((item) => ({
        label: item.name && item.name !== item.path ? `${item.name}（${item.path}）` : item.path,
        path: item.path
      }))
    );
    const downloaderItems = computed(
      () => downloaderOptions.value.map((item) => ({
        label: item.type ? `${item.name}（${item.type}）` : item.name,
        name: item.name
      }))
    );
    const siteItems = computed(
      () => siteOptions.value.map((item) => ({ label: item.name, id: item.id }))
    );
    const downloaderAvailable = computed(() => {
      const current = String(downloader.value || "").trim();
      if (!current) return true;
      if (!downloaderOptions.value.length) return true;
      return downloaderOptions.value.some((item) => item.name === current);
    });
    const pathModel = computed({
      get: () => savePath.value || "",
      set: (value) => {
        if (value && typeof value === "object") savePath.value = String(value.path || "");
        else savePath.value = String(value ?? "").trim();
      }
    });
    const downloaderModel = computed({
      get: () => downloader.value || "",
      set: (value) => {
        if (value && typeof value === "object") downloader.value = String(value.name || "");
        else downloader.value = String(value ?? "").trim();
      }
    });
    const sitesModel = computed({
      get: () => sites.value || [],
      set: (value) => {
        sites.value = Array.isArray(value) ? value.map((item) => Number(item)) : [];
      }
    });
    async function loadOptions() {
      const api = resolveApi(props);
      if (!api) return;
      loadingOptions.value = true;
      try {
        const [paths, downloaders, siteList] = await Promise.all([
          fetchPathOptions(api),
          fetchDownloaderOptions(api),
          fetchSiteOptions(api)
        ]);
        pathOptions.value = paths;
        downloaderOptions.value = downloaders;
        siteOptions.value = siteList;
      } finally {
        loadingOptions.value = false;
        loaded.value = true;
      }
    }
    async function saveAsDefault() {
      const api = resolveApi(props);
      if (!api) {
        emit("saved", false, "宿主 API 未就绪");
        return;
      }
      saving.value = true;
      try {
        const raw = await api.put(`${API_BASE}/config`, {
          subscribe_save_path: savePath.value || "",
          subscribe_downloader: downloader.value || "",
          subscribe_sites: sites.value || []
        });
        const res = normalizeResult(raw);
        emit("saved", res.ok, res.message || (res.ok ? "订阅选项已保存" : "保存失败"));
      } catch (err) {
        console.warn("[DoubanActorSubscribe] 保存订阅选项失败", err);
        emit("saved", false, "保存订阅选项失败");
      } finally {
        saving.value = false;
      }
    }
    onMounted(loadOptions);
    watch(
      () => props.api,
      (next) => {
        if (next && !loaded.value) void loadOptions();
      }
    );
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_combobox = _resolveComponent("v-combobox");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createBlock(_component_v_card, {
        variant: "outlined",
        class: "mb-3"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_v_card_text, { class: "pb-2" }, {
            default: _withCtx(() => [
              _createElementVNode("div", _hoisted_1, [
                _createVNode(_component_v_icon, {
                  icon: "mdi-tune-variant",
                  size: "18"
                }),
                _cache[4] || (_cache[4] = _createElementVNode("span", { class: "text-subtitle-2" }, "订阅选项", -1)),
                _cache[5] || (_cache[5] = _createElementVNode("span", { class: "text-caption das-dim" }, " 提交订阅时一并带上；留空则沿用 MoviePilot 的默认订阅配置 ", -1)),
                _createVNode(_component_v_spacer),
                loaded.value && !pathItems.value.length && !downloaderItems.value.length && !siteItems.value.length ? (_openBlock(), _createElementBlock("span", _hoisted_2, " 未能读取宿主选项 ")) : _createCommentVNode("", true),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "text",
                  icon: "mdi-refresh",
                  loading: loadingOptions.value,
                  title: "重新读取宿主的下载路径、下载器与站点",
                  onClick: loadOptions
                }, null, 8, ["loading"]),
                __props.showSave ? (_openBlock(), _createBlock(_component_v_btn, {
                  key: 1,
                  size: "small",
                  variant: "tonal",
                  color: "primary",
                  "prepend-icon": "mdi-content-save-outline",
                  loading: saving.value,
                  onClick: saveAsDefault
                }, {
                  default: _withCtx(() => [..._cache[3] || (_cache[3] = [
                    _createTextVNode(" 保存为默认 ", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])) : _createCommentVNode("", true)
              ]),
              _createVNode(_component_v_row, { dense: "" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_combobox, {
                        modelValue: pathModel.value,
                        "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => pathModel.value = $event),
                        items: pathItems.value,
                        "item-title": "label",
                        "item-value": "path",
                        loading: loadingOptions.value,
                        label: "下载保存路径",
                        hint: "可从下拉选择，也可直接输入自定义路径；留空表示跟随默认",
                        "persistent-hint": "",
                        density: "comfortable",
                        clearable: "",
                        "prepend-inner-icon": "mdi-folder-outline"
                      }, null, 8, ["modelValue", "items", "loading"])
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_combobox, {
                        modelValue: downloaderModel.value,
                        "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => downloaderModel.value = $event),
                        items: downloaderItems.value,
                        "item-title": "label",
                        "item-value": "name",
                        loading: loadingOptions.value,
                        label: "下载器",
                        hint: "宿主里已配置的下载客户端；留空表示跟随默认",
                        "persistent-hint": "",
                        density: "comfortable",
                        clearable: "",
                        "prepend-inner-icon": "mdi-download-network-outline"
                      }, null, 8, ["modelValue", "items", "loading"]),
                      downloader.value && !downloaderAvailable.value ? (_openBlock(), _createElementBlock("div", _hoisted_3, " 宿主没有名为「" + _toDisplayString(downloader.value) + "」的下载器，提交时会被忽略 ", 1)) : _createCommentVNode("", true)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_col, {
                    cols: "12",
                    md: "4"
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_select, {
                        modelValue: sitesModel.value,
                        "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => sitesModel.value = $event),
                        items: siteItems.value,
                        "item-title": "label",
                        "item-value": "id",
                        loading: loadingOptions.value,
                        label: "订阅站点",
                        hint: "不选表示使用宿主默认订阅站点",
                        "persistent-hint": "",
                        density: "comfortable",
                        multiple: "",
                        chips: "",
                        clearable: "",
                        "prepend-inner-icon": "mdi-web"
                      }, null, 8, ["modelValue", "items", "loading"])
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
      });
    };
  }
});

const SubscribePrefs = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-9f9868c5"]]);

export { SubscribePrefs as S };
