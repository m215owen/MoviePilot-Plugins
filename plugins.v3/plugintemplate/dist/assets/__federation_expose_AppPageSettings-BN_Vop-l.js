import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { A as API_BASE, r as resolveApi, u as unwrap } from './api-BKD28MM4.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,unref:_unref,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "pt-plugin-root pa-4" };
const _hoisted_2 = { class: "d-flex align-center mb-3" };
const _hoisted_3 = { class: "d-flex mt-3" };
const {inject,onMounted,reactive,ref} = await importShared('vue');
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
    const defaults = {
      enabled: false,
      cron: "0 */6 * * *",
      notify: false,
      message: "Hello MoviePilot",
      max_records: 50
    };
    const local = reactive({ ...defaults });
    async function load() {
      const api = resolveApi(props);
      if (!api) {
        toast?.error("宿主 API 未就绪");
        return;
      }
      loading.value = true;
      try {
        const raw = await api.get(`${API_BASE}/config`);
        const res = unwrap(raw);
        if (res?.success && res.data) Object.assign(local, res.data);
      } catch (err) {
        toast?.error("读取配置失败");
        console.warn("[PluginTemplate] 读取配置失败", err);
      } finally {
        loading.value = false;
      }
    }
    async function save() {
      const api = resolveApi(props);
      if (!api) {
        toast?.error("宿主 API 未就绪");
        return;
      }
      saving.value = true;
      try {
        const raw = await api.put(`${API_BASE}/config`, { ...local });
        const res = unwrap(raw);
        if (res?.success) {
          if (res.data) Object.assign(local, res.data);
          toast?.success("配置已保存");
        } else {
          toast?.error(res?.message || "保存失败");
        }
      } catch (err) {
        toast?.error("保存失败");
        console.warn("[PluginTemplate] 保存配置失败", err);
      } finally {
        saving.value = false;
      }
    }
    onMounted(load);
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_icon, {
            icon: "mdi-cog-outline",
            class: "mr-2"
          }),
          _cache[5] || (_cache[5] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "插件开发模板 · 设置全页", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal",
            class: "ml-3"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(__props.pluginId || "PluginTemplate") + " / " + _toDisplayString(__props.navKey || "settings"), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            icon: "mdi-refresh",
            loading: loading.value,
            onClick: load
          }, null, 8, ["loading"])
        ]),
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-4",
          "max-width": "820"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_alert, {
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "mb-3"
            }, {
              default: _withCtx(() => [
                _cache[6] || (_cache[6] = _createTextVNode(" 本页演示「多 nav_key 全页」与「组件内直接调用插件 API」： 保存通过 ", -1)),
                _createElementVNode("code", null, "PUT " + _toDisplayString(_unref(API_BASE)) + "/config", 1),
                _cache[7] || (_cache[7] = _createTextVNode(" 完成。 ", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_v_switch, {
              modelValue: local.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => local.enabled = $event),
              label: "启用插件",
              color: "primary",
              "hide-details": "",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_text_field, {
              modelValue: local.message,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => local.message = $event),
              label: "示例文本",
              density: "comfortable",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_text_field, {
              modelValue: local.cron,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => local.cron = $event),
              label: "cron 表达式",
              hint: "5 段式，例如 0 */6 * * *",
              "persistent-hint": "",
              density: "comfortable",
              class: "mb-3"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_text_field, {
              modelValue: local.max_records,
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => local.max_records = $event),
              modelModifiers: { number: true },
              type: "number",
              label: "执行记录保留条数",
              min: "5",
              max: "500",
              density: "comfortable",
              class: "mb-2"
            }, null, 8, ["modelValue"]),
            _createVNode(_component_v_switch, {
              modelValue: local.notify,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => local.notify = $event),
              label: "任务完成后发送系统通知",
              color: "primary",
              "hide-details": ""
            }, null, 8, ["modelValue"]),
            _createElementVNode("div", _hoisted_3, [
              _createVNode(_component_v_btn, {
                color: "primary",
                loading: saving.value,
                onClick: save
              }, {
                default: _withCtx(() => [..._cache[8] || (_cache[8] = [
                  _createTextVNode("保存配置", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              _createVNode(_component_v_btn, {
                variant: "text",
                class: "ml-2",
                onClick: load
              }, {
                default: _withCtx(() => [..._cache[9] || (_cache[9] = [
                  _createTextVNode("放弃修改", -1)
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

const AppPageSettings = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-382ecf69"]]);

export { AppPageSettings as default };
