import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { S as SITE_INFO, f as fetchConfig, b as setSite, c as saveConfig } from './site-UXzUndvw.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,toDisplayString:_toDisplayString,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,unref:_unref,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "pa-2" };
const _hoisted_2 = { class: "d-flex align-center mb-2" };
const _hoisted_3 = { class: "d-flex align-center" };
const _hoisted_4 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const {computed,onMounted,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Config",
  props: {
    api: {}
  },
  emits: ["close", "saved"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const local = ref({
      enabled: false,
      site: "net",
      use_baidu_image_proxy: true,
      exclude_manju: true
    });
    const loading = ref(false);
    const saving = ref(false);
    const saved = ref(false);
    const error = ref("");
    const siteItems = [SITE_INFO.net, SITE_INFO.org].map((info) => ({
      title: info.label,
      value: info.key
    }));
    const excludeLabel = computed(
      () => local.value.site === "org" ? "排除 AI 剧" : "排除漫剧"
    );
    const excludeMessages = computed(
      () => local.value.site === "org" ? [
        "新站没有漫剧角标，打开后按卡片标题的「AI短剧」标剔除 AI 剧",
        "识别候选 / 面板检索 / 榜单 / 演员作品都生效"
      ] : [
        "打开：识别候选 / 面板检索 / 榜单都不再出现漫剧",
        "判定只看 kind 这一项 —— kind 为「漫剧」即排除"
      ]
    );
    const imageMessages = computed(
      () => local.value.site === "org" ? [
        "当前是新站：海报直接用页面自带的 cdn.duanjubaike.org 绝对地址",
        "本开关对新站不生效（切换回老站后才会用上）"
      ] : [
        "打开：海报 / 头像走站点原始的百度 gimg 中转（gimg0.baidu.com）",
        "关闭：直连站点自家图床 img.duanjubaike.net"
      ]
    );
    function normalize(config) {
      return {
        enabled: Boolean(config?.enabled),
        // 站点只有 net / org 两个合法值，其它（含 undefined）一律回落 net
        site: config?.site === "org" ? "org" : "net",
        // 后端默认 True；只有显式 false 才关掉（老配置里没有这个键时保持默认）
        use_baidu_image_proxy: config?.use_baidu_image_proxy !== false,
        exclude_manju: config?.exclude_manju !== false
      };
    }
    async function load() {
      loading.value = true;
      error.value = "";
      try {
        local.value = normalize(await fetchConfig(props));
        setSite(local.value.site);
      } catch (err) {
        error.value = `读取配置失败：${err instanceof Error ? err.message : String(err)}`;
      } finally {
        loading.value = false;
      }
    }
    async function save() {
      saving.value = true;
      error.value = "";
      saved.value = false;
      try {
        local.value = normalize(await saveConfig(props, normalize(local.value)));
        setSite(local.value.site);
        saved.value = true;
        emit("saved");
      } catch (err) {
        error.value = `保存失败：${err instanceof Error ? err.message : String(err)}`;
      } finally {
        saving.value = false;
      }
    }
    onMounted(() => {
      void load();
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_card = _resolveComponent("v-card");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-4"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cog-outline",
                size: "20",
                class: "mr-2 text-medium-emphasis"
              }),
              _cache[7] || (_cache[7] = _createElementVNode("h3", { class: "ma-0 text-subtitle-1" }, "短剧百科刮削源 · 设置", -1)),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                icon: "mdi-close",
                variant: "text",
                size: "small",
                title: "关闭",
                onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
              })
            ]),
            _cache[10] || (_cache[10] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-4" }, [
              _createTextVNode(" 把「短剧百科」注册为媒体来源 "),
              _createElementVNode("span", { class: "sdbs-key" }, "djbaike"),
              _createTextVNode("：按片名检索 → 识别 → 订阅 / 刮削。 ")
            ], -1)),
            error.value ? (_openBlock(), _createBlock(_component_v_alert, {
              key: 0,
              type: "error",
              variant: "tonal",
              density: "compact",
              class: "mb-3"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(error.value), 1)
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            _cache[11] || (_cache[11] = _createElementVNode("div", { class: "text-subtitle-2 font-weight-bold" }, "运行", -1)),
            _createVNode(_component_v_divider, { class: "mt-1 mb-2" }),
            _createVNode(_component_v_switch, {
              modelValue: local.value.enabled,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => local.value.enabled = $event),
              label: "启用插件",
              color: "primary",
              density: "compact",
              "hide-details": "",
              class: "mb-3",
              loading: loading.value
            }, null, 8, ["modelValue", "loading"]),
            _cache[12] || (_cache[12] = _createElementVNode("div", { class: "text-subtitle-2 font-weight-bold" }, "数据源", -1)),
            _createVNode(_component_v_divider, { class: "mt-1 mb-2" }),
            _createVNode(_component_v_select, {
              modelValue: local.value.site,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => local.value.site = $event),
              items: _unref(siteItems),
              "item-title": "title",
              "item-value": "value",
              label: "主站",
              density: "compact",
              messages: [
                "只决定检索 / 人物目录 / 榜单走哪个站；详情与图片按身份前缀自动路由",
                "drama: / actor: 恒走新站，duanju: 等恒走老站 —— 换站不会废掉已入库的旧身份"
              ],
              loading: loading.value,
              class: "mb-3"
            }, null, 8, ["modelValue", "items", "loading"]),
            _cache[13] || (_cache[13] = _createElementVNode("div", { class: "text-subtitle-2 font-weight-bold" }, "图片", -1)),
            _createVNode(_component_v_divider, { class: "mt-1 mb-2" }),
            _createVNode(_component_v_switch, {
              modelValue: local.value.use_baidu_image_proxy,
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => local.value.use_baidu_image_proxy = $event),
              label: "保留使用百度图床代理（仅老站生效）",
              color: "primary",
              density: "compact",
              disabled: local.value.site === "org",
              messages: imageMessages.value,
              loading: loading.value
            }, null, 8, ["modelValue", "disabled", "messages", "loading"]),
            _cache[14] || (_cache[14] = _createElementVNode("div", { class: "text-subtitle-2 font-weight-bold mt-2" }, "内容", -1)),
            _createVNode(_component_v_divider, { class: "mt-1 mb-2" }),
            _createVNode(_component_v_switch, {
              modelValue: local.value.exclude_manju,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => local.value.exclude_manju = $event),
              label: excludeLabel.value,
              color: "primary",
              density: "compact",
              messages: excludeMessages.value,
              loading: loading.value
            }, null, 8, ["modelValue", "label", "messages", "loading"]),
            _createVNode(_component_v_divider, { class: "my-3" }),
            _createElementVNode("div", _hoisted_3, [
              saved.value ? (_openBlock(), _createElementBlock("span", _hoisted_4, "已保存")) : _createCommentVNode("", true),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                variant: "text",
                disabled: saving.value,
                onClick: _cache[5] || (_cache[5] = ($event) => emit("close"))
              }, {
                default: _withCtx(() => [..._cache[8] || (_cache[8] = [
                  _createTextVNode("取消", -1)
                ])]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode(_component_v_btn, {
                color: "primary",
                variant: "flat",
                class: "ml-2",
                loading: saving.value,
                disabled: loading.value,
                onClick: _cache[6] || (_cache[6] = ($event) => save())
              }, {
                default: _withCtx(() => [..._cache[9] || (_cache[9] = [
                  _createTextVNode(" 保存 ", -1)
                ])]),
                _: 1
              }, 8, ["loading", "disabled"])
            ])
          ]),
          _: 1
        })
      ]);
    };
  }
});

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const Config = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-0c797046"]]);

export { Config as default };
