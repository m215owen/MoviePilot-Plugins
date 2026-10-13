import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { b as formatTime, e as formatCooldown, g as resourceSearchUrl, r as resolveApi, h as fetchWorks, P as PLUGIN_ID, i as refreshWorks, j as subscribeWork, c as fetchStatus, k as fetchConfig, d as runOnce, o as organizeNow, a as saveConfig, l as removeLedgerEntry, m as clearLedger, n as clearCooldown, _ as _export_sfc } from './_plugin-vue_export-helper-DWQI7QT8.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,unref:_unref,normalizeClass:_normalizeClass} = await importShared('vue');

const _hoisted_1 = {
  class: "d-flex align-center mb-3 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_2 = { class: "text-h6 ma-0" };
const _hoisted_3 = { class: "text-caption sdas-dim" };
const _hoisted_4 = { class: "text-h6" };
const _hoisted_5 = { class: "d-flex align-center pa-3 pb-1" };
const _hoisted_6 = { class: "px-3 pb-3" };
const _hoisted_7 = { class: "text-caption sdas-dim sdas-label" };
const _hoisted_8 = { class: "text-body-2" };
const _hoisted_9 = { class: "d-flex align-center pa-3 pb-1" };
const _hoisted_10 = { class: "text-subtitle-2" };
const _hoisted_11 = { class: "text-caption sdas-dim" };
const _hoisted_12 = { class: "px-3 pb-3" };
const _hoisted_13 = {
  key: 0,
  class: "text-caption sdas-dim"
};
const _hoisted_14 = {
  class: "d-flex flex-wrap",
  style: { "gap": "6px" }
};
const _hoisted_15 = {
  key: 0,
  class: "sdas-dim ml-1"
};
const _hoisted_16 = {
  class: "d-flex align-center pa-3 pb-1 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_17 = { class: "text-subtitle-2" };
const _hoisted_18 = { class: "text-caption sdas-dim" };
const _hoisted_19 = {
  class: "d-flex align-center flex-wrap px-3 pb-2",
  style: { "gap": "8px" }
};
const _hoisted_20 = ["title"];
const _hoisted_21 = { class: "text-caption" };
const _hoisted_22 = { class: "text-caption" };
const _hoisted_23 = { class: "text-caption text-no-wrap" };
const _hoisted_24 = {
  key: 0,
  class: "sdas-dim ml-1"
};
const _hoisted_25 = { class: "text-end text-no-wrap" };
const _hoisted_26 = { key: 0 };
const _hoisted_27 = {
  colspan: "6",
  class: "text-center text-caption sdas-dim py-3"
};
const _hoisted_28 = {
  key: 1,
  class: "pa-2 text-center"
};
const _hoisted_29 = {
  key: 2,
  class: "px-3 pb-2 text-caption sdas-dim"
};
const _hoisted_30 = {
  class: "d-flex align-center pa-3 pb-1 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_31 = { class: "text-subtitle-2" };
const _hoisted_32 = ["title"];
const _hoisted_33 = { class: "text-caption" };
const _hoisted_34 = { class: "text-caption" };
const _hoisted_35 = { class: "text-caption" };
const _hoisted_36 = { class: "text-caption" };
const _hoisted_37 = {
  key: 0,
  class: "text-caption sdas-dim ml-1",
  title: "同剧命中多个资源，已择优"
};
const _hoisted_38 = { class: "text-end text-no-wrap" };
const _hoisted_39 = { key: 0 };
const _hoisted_40 = {
  colspan: "7",
  class: "text-center text-caption sdas-dim py-3"
};
const _hoisted_41 = { class: "d-flex align-center pa-3 pb-1" };
const _hoisted_42 = { class: "text-subtitle-2" };
const _hoisted_43 = { class: "px-3 pb-3" };
const _hoisted_44 = {
  class: "d-flex flex-wrap",
  style: { "gap": "6px" }
};
const _hoisted_45 = { class: "sdas-dim ml-1" };
const _hoisted_46 = { class: "text-subtitle-2 mb-2" };
const _hoisted_47 = { class: "d-flex" };
const _hoisted_48 = { class: "d-flex" };
const {computed,onMounted,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Page",
  props: {
    api: {},
    config: {},
    pluginId: {},
    navKey: {},
    full: { type: Boolean },
    mode: {}
  },
  emits: ["action", "close"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const isMain = computed(() => props.mode !== "status");
    const loading = ref(false);
    const running = ref(false);
    const organizing = ref(false);
    const clearing = ref(false);
    const removing = ref(false);
    const toggling = ref(false);
    const pendingKey = ref("");
    const keyword = ref("");
    const confirmClear = ref(false);
    const removeDialog = ref(false);
    const removeTarget = ref(null);
    const payload = ref(null);
    const searchSites = ref([]);
    const remoteConfig = ref({});
    const siteOptions = ref([]);
    const works = ref({
      items: [],
      summary: { total: 0, pending: 0, cooling: 0, downloaded: 0 },
      refreshed_at: "",
      running: false,
      configured: false,
      actors: [],
      actor_count: 0
    });
    const workKeyword = ref("");
    const workState = ref("all");
    const workActor = ref("all");
    const workLimit = ref(40);
    const refreshingWorks = ref(false);
    const subscribingKey = ref("");
    const workMessage = ref("");
    const worksSummary = computed(() => works.value.summary);
    const stateFilters = [
      { title: "全部状态", value: "all" },
      { title: "待订阅", value: "pending" },
      { title: "冷却中", value: "cooling" },
      { title: "已下载", value: "downloaded" }
    ];
    const actorFilters = computed(() => [
      { title: "全部演员", value: "all" },
      ...Array.from(new Set(works.value.items.map((item) => String(item.actor || "")).filter(Boolean))).map(
        (name) => ({ title: name, value: name })
      )
    ]);
    const filteredWorks = computed(() => {
      const text = workKeyword.value.trim().toLowerCase();
      const state = workState.value;
      const actor = workActor.value;
      return works.value.items.filter((row) => {
        if (state === "downloaded") {
          if (row.state !== "downloaded" && row.state !== "organized") return false;
        } else if (state !== "all" && row.state !== state) {
          return false;
        }
        if (actor !== "all" && String(row.actor || "") !== actor) return false;
        if (text) {
          const haystack = `${row.title || ""} ${row.actor || ""} ${row.year || ""} ${row.alt_title || ""}`;
          if (!haystack.toLowerCase().includes(text)) return false;
        }
        return true;
      });
    });
    const visibleWorks = computed(() => filteredWorks.value.slice(0, workLimit.value));
    const worksEmptyHint = computed(() => {
      if (!works.value.configured) {
        return "还没配置演员与搜索站点：先到配置页填写并保存";
      }
      if (!works.value.items.length) {
        if (works.value.running) return "正在拉取演员作品…";
        return "点右上角「刷新作品」，插件会去 TMDB / 豆瓣 拉取演员的作品清单";
      }
      return "没有匹配的作品，换个筛选条件试试";
    });
    const enabled = computed({
      get: () => payload.value?.enabled ?? props.config?.enabled ?? false,
      set: (value) => {
        if (payload.value) payload.value.enabled = value;
      }
    });
    const summary = computed(() => payload.value?.summary || {});
    const ledger = computed(() => payload.value?.ledger || []);
    const cooldown = computed(() => payload.value?.cooldown || []);
    const cooldownCount = computed(() => cooldown.value.length);
    const lastMessage = computed(() => String(payload.value?.last_result?.message || ""));
    const actorRows = computed(() => {
      const actors = payload.value?.actors || {};
      return Object.keys(actors).map((key) => {
        const record = actors[key];
        return {
          key,
          name: record?.name || key,
          works: record?.works || [],
          errors: record?.errors || [],
          ids: [record?.douban_id ? `豆瓣 ${record.douban_id}` : "", record?.tmdb_id ? `TMDB ${record.tmdb_id}` : ""].filter(Boolean).join("｜")
        };
      });
    });
    const statCards = computed(() => [
      { label: "演员", value: String(summary.value.actor_count || 0), title: "配置并已解析的演员数" },
      {
        label: "候选作品",
        value: String(summary.value.candidate_count || 0),
        title: "上一轮发现层产出的候选剧数（TMDB + 豆瓣并集）"
      },
      { label: "已下载", value: String(summary.value.downloaded_count || 0), title: "账本里的记录数" },
      { label: "已整理", value: String(summary.value.organized_count || 0), title: "已搬进媒体库的剧数" }
    ]);
    function siteName(id) {
      const hit = siteOptions.value.find((item) => Number(item.value) === Number(id));
      return hit?.title || `站点 ${id}`;
    }
    function transferLabel(value) {
      if (value === "copy") return "复制";
      if (value === "move") return "移动";
      return "硬链接";
    }
    function cookieLabel(source) {
      if (source === "manual") return "插件内手填的 Cookie";
      if (source === "cookiecloud") return "宿主 CookieCloud（自动读取）";
      return "未取到（豆瓣匿名搜索额度极低）";
    }
    const configRows = computed(() => {
      const config = { ...props.config || {}, ...remoteConfig.value };
      const sites = config.sites || [];
      return [
        {
          label: "搜索站点",
          value: sites.length ? sites.map((id) => siteName(Number(id))).join("，") : "未配置（无法搜索）"
        },
        {
          label: "搜索范围",
          value: config.prefer_short_drama_category === false ? "全站搜索" : "优先站点「短剧」分类"
        },
        { label: "下载器", value: String(config.downloader || "跟随宿主默认") },
        { label: "下载目录", value: String(config.download_path || "未配置") },
        { label: "媒体库目录", value: String(config.library_path || "未配置") },
        {
          label: "整理方式",
          value: `${transferLabel(config.transfer_type)}${config.organize_enabled === false ? "（整理已关闭）" : ""}`
        },
        {
          label: "运行间隔",
          value: `${config.interval_hours || 6} 小时轮询 / ${config.organize_interval_minutes || 30} 分钟整理`
        },
        { label: "豆瓣登录态", value: cookieLabel(config.douban_cookie_source) }
      ];
    });
    const visibleLedger = computed(() => {
      const text = keyword.value.trim().toLowerCase();
      if (!text) return ledger.value;
      return ledger.value.filter(
        (row) => `${row.title || ""} ${row.actor || ""} ${row.site_name || ""}`.toLowerCase().includes(text)
      );
    });
    function actorTitle(row) {
      const parts = [row.name];
      if (row.ids) parts.push(row.ids);
      parts.push(`${row.works.length} 部作品`);
      if (row.errors.length) parts.push(row.errors.join("；"));
      return parts.join("｜");
    }
    function resourceUrl(row) {
      return resourceSearchUrl(row.title, searchSites.value);
    }
    function stateColor(state) {
      if (state === "organized") return "success";
      if (state === "downloaded") return "info";
      if (state === "cooling") return "warning";
      return "primary";
    }
    function stateLabel(row) {
      if (row.state === "organized") return "已整理";
      if (row.state === "downloaded") return "已下载";
      if (row.state === "cooling") return `冷却 ${row.remaining_minutes || 0} 分`;
      return "待订阅";
    }
    function sourceLabel(source) {
      if (source === "tmdb") return "TMDB";
      if (source === "douban") return "豆瓣";
      return "未知";
    }
    function workResourceUrl(row) {
      return resourceSearchUrl(row.title, searchSites.value);
    }
    function applyWorks(data) {
      works.value = data;
    }
    async function loadWorks() {
      const api = resolveApi(props);
      if (!api) return;
      try {
        const data = await fetchWorks(api);
        if (data) applyWorks(data);
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 读取作品墙失败`, err);
      }
    }
    async function doRefreshWorks() {
      const api = resolveApi(props);
      if (!api) return;
      refreshingWorks.value = true;
      workMessage.value = "";
      try {
        const res = await refreshWorks(api, applyWorks);
        workMessage.value = res.message;
        await load(false);
      } finally {
        refreshingWorks.value = false;
      }
    }
    async function doSubscribe(row) {
      const api = resolveApi(props);
      if (!api) return;
      subscribingKey.value = row.key;
      workMessage.value = "";
      try {
        const res = await subscribeWork(api, { key: row.key, title: row.title, year: row.year });
        workMessage.value = res.message;
        await loadWorks();
        await load(false);
      } finally {
        subscribingKey.value = "";
      }
    }
    function apply(data) {
      payload.value = data;
    }
    async function load(showSpinner = true) {
      const api = resolveApi(props);
      if (!api) return;
      if (showSpinner) loading.value = true;
      try {
        const data = await fetchStatus(api);
        if (data) apply(data);
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 读取运行概览失败`, err);
      } finally {
        loading.value = false;
      }
    }
    async function loadConfig() {
      const api = resolveApi(props);
      if (!api) return;
      try {
        const data = await fetchConfig(api);
        remoteConfig.value = data?.config || {};
        searchSites.value = data?.config?.sites || [];
        siteOptions.value = data?.options?.sites || [];
      } catch (err) {
        console.debug(`[${PLUGIN_ID}] 读取插件配置失败`, err);
      }
    }
    async function doRun() {
      const api = resolveApi(props);
      if (!api) return;
      running.value = true;
      try {
        const before = String(summary.value.last_run || "");
        const res = await runOnce(api, apply, before);
        if (!res.ok) {
          await load(false);
        }
        await load(false);
        emit("action");
      } finally {
        running.value = false;
      }
    }
    async function doOrganize() {
      const api = resolveApi(props);
      if (!api) return;
      organizing.value = true;
      try {
        await organizeNow(api);
        await load(false);
      } finally {
        organizing.value = false;
      }
    }
    async function toggleEnabled(value) {
      const api = resolveApi(props);
      if (!api) return;
      toggling.value = true;
      try {
        await saveConfig(api, { enabled: value });
        await load(false);
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 切换启用状态失败`, err);
      } finally {
        toggling.value = false;
      }
    }
    function askRemove(row) {
      removeTarget.value = row;
      removeDialog.value = true;
    }
    async function doRemove() {
      const api = resolveApi(props);
      const row = removeTarget.value;
      removeDialog.value = false;
      if (!api || !row) return;
      removing.value = true;
      pendingKey.value = row.key;
      try {
        await removeLedgerEntry(api, row.key);
        await load(false);
      } finally {
        removing.value = false;
        pendingKey.value = "";
        removeTarget.value = null;
      }
    }
    async function doClear() {
      const api = resolveApi(props);
      confirmClear.value = false;
      if (!api) return;
      clearing.value = true;
      try {
        await clearLedger(api);
        await load(false);
      } finally {
        clearing.value = false;
      }
    }
    async function doClearCooldown() {
      const api = resolveApi(props);
      if (!api) return;
      await clearCooldown(api);
      await load(false);
    }
    onMounted(() => {
      void load();
      void loadConfig();
      void loadWorks();
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_table = _resolveComponent("v-table");
      const _component_v_dialog = _resolveComponent("v-dialog");
      return _openBlock(), _createElementBlock("div", {
        class: _normalizeClass(["sdas-root", props.full ? "pa-4" : "pa-2"])
      }, [
        _createElementVNode("div", _hoisted_1, [
          _createVNode(_component_v_icon, {
            icon: "mdi-movie-open-star-outline",
            class: "mr-1"
          }),
          _createElementVNode("h2", _hoisted_2, _toDisplayString(isMain.value ? "短剧" : "短剧 · 运行状态"), 1),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal",
            color: enabled.value ? "primary" : "warning"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(enabled.value ? "已启用" : "未启用"), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          payload.value?.running ? (_openBlock(), _createBlock(_component_v_chip, {
            key: 0,
            size: "small",
            variant: "tonal",
            color: "info",
            "prepend-icon": "mdi-progress-clock"
          }, {
            default: _withCtx(() => [..._cache[12] || (_cache[12] = [
              _createTextVNode(" 正在执行 ", -1)
            ])]),
            _: 1
          })) : cooldownCount.value ? (_openBlock(), _createBlock(_component_v_chip, {
            key: 1,
            size: "small",
            variant: "tonal",
            color: "warning",
            "prepend-icon": "mdi-timer-sand",
            title: "搜过但站点暂无资源的剧，24 小时内不重复搜索"
          }, {
            default: _withCtx(() => [
              _createTextVNode(" 冷却 " + _toDisplayString(cooldownCount.value), 1)
            ]),
            _: 1
          })) : _createCommentVNode("", true),
          _createVNode(_component_v_spacer),
          isMain.value ? (_openBlock(), _createBlock(_component_v_switch, {
            key: 2,
            modelValue: enabled.value,
            "onUpdate:modelValue": [
              _cache[0] || (_cache[0] = ($event) => enabled.value = $event),
              toggleEnabled
            ],
            color: "primary",
            "hide-details": "",
            density: "compact",
            loading: toggling.value,
            label: enabled.value ? "已启用" : "已停用",
            class: "sdas-switch"
          }, null, 8, ["modelValue", "loading", "label"])) : _createCommentVNode("", true),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            icon: "mdi-refresh",
            title: "刷新本页数据",
            loading: loading.value,
            onClick: _cache[1] || (_cache[1] = ($event) => load(false))
          }, null, 8, ["loading"]),
          isMain.value ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 3,
            size: "small",
            variant: "tonal",
            icon: "mdi-folder-move-outline",
            title: "立即整理一次（把已下载的搬进媒体库）",
            loading: organizing.value,
            onClick: doOrganize
          }, null, 8, ["loading"])) : _createCommentVNode("", true),
          isMain.value ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 4,
            size: "small",
            color: "primary",
            variant: "tonal",
            "prepend-icon": "mdi-play",
            loading: running.value,
            onClick: doRun
          }, {
            default: _withCtx(() => [..._cache[13] || (_cache[13] = [
              _createTextVNode(" 立即运行 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"])) : _createCommentVNode("", true)
        ]),
        _createVNode(_component_v_row, {
          dense: "",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(statCards.value, (item) => {
              return _openBlock(), _createBlock(_component_v_col, {
                key: item.label,
                cols: "6",
                sm: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "tonal",
                    class: "pa-3",
                    title: item.title
                  }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_3, _toDisplayString(item.label), 1),
                      _createElementVNode("div", _hoisted_4, _toDisplayString(item.value), 1)
                    ]),
                    _: 2
                  }, 1032, ["title"])
                ]),
                _: 2
              }, 1024);
            }), 128))
          ]),
          _: 1
        }),
        !enabled.value ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [..._cache[14] || (_cache[14] = [
            _createTextVNode(" 插件未启用或尚未配置演员/搜索站点，请先到配置页填写后保存。 ", -1)
          ])]),
          _: 1
        })) : _createCommentVNode("", true),
        running.value ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 1,
          type: "info",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [..._cache[15] || (_cache[15] = [
            _createTextVNode(" 正在后台执行（演员多时一轮要跑较久），完成后此页会自动更新… ", -1)
          ])]),
          _: 1
        })) : lastMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 2,
          type: payload.value?.last_result?.success === false ? "warning" : "success",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(lastMessage.value), 1)
          ]),
          _: 1
        }, 8, ["type"])) : _createCommentVNode("", true),
        !isMain.value ? (_openBlock(), _createBlock(_component_v_card, {
          key: 3,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_5, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cog-outline",
                size: "18",
                class: "mr-2"
              }),
              _cache[16] || (_cache[16] = _createElementVNode("span", { class: "text-subtitle-2" }, "运行配置", -1)),
              _createVNode(_component_v_spacer),
              _cache[17] || (_cache[17] = _createElementVNode("span", { class: "text-caption sdas-dim" }, "在插件配置页修改后保存即可生效", -1))
            ]),
            _createElementVNode("div", _hoisted_6, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(configRows.value, (item) => {
                return _openBlock(), _createElementBlock("div", {
                  key: item.label,
                  class: "d-flex align-start py-1"
                }, [
                  _createElementVNode("span", _hoisted_7, _toDisplayString(item.label), 1),
                  _createElementVNode("span", _hoisted_8, _toDisplayString(item.value), 1)
                ]);
              }), 128))
            ])
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_9, [
              _createVNode(_component_v_icon, {
                icon: "mdi-account-multiple-outline",
                size: "18",
                class: "mr-2"
              }),
              _createElementVNode("span", _hoisted_10, "演员（" + _toDisplayString(actorRows.value.length) + "）", 1),
              _createVNode(_component_v_spacer),
              _createElementVNode("span", _hoisted_11, " 上次运行：" + _toDisplayString(_unref(formatTime)(summary.value.last_run)), 1)
            ]),
            _createElementVNode("div", _hoisted_12, [
              !actorRows.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_13, "尚未配置演员")) : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_14, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorRows.value, (row) => {
                  return _openBlock(), _createBlock(_component_v_chip, {
                    key: row.key,
                    size: "small",
                    variant: "tonal",
                    color: row.errors.length ? "warning" : void 0,
                    title: actorTitle(row)
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(row.name) + " ", 1),
                      row.works.length ? (_openBlock(), _createElementBlock("span", _hoisted_15, _toDisplayString(row.works.length), 1)) : _createCommentVNode("", true),
                      row.errors.length ? (_openBlock(), _createBlock(_component_v_icon, {
                        key: 1,
                        icon: "mdi-alert-circle-outline",
                        size: "14",
                        class: "ml-1"
                      })) : _createCommentVNode("", true)
                    ]),
                    _: 2
                  }, 1032, ["color", "title"]);
                }), 128))
              ]),
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorRows.value.filter((item) => item.errors.length), (row) => {
                return _openBlock(), _createElementBlock("div", {
                  key: `err-${row.key}`,
                  class: "text-caption sdas-dim mt-1"
                }, " · " + _toDisplayString(row.name) + "：" + _toDisplayString(row.errors.join("；")), 1);
              }), 128))
            ])
          ]),
          _: 1
        }),
        isMain.value ? (_openBlock(), _createBlock(_component_v_card, {
          key: 4,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_16, [
              _createVNode(_component_v_icon, {
                icon: "mdi-movie-open-star-outline",
                size: "18",
                class: "mr-2"
              }),
              _createElementVNode("span", _hoisted_17, "演员作品（" + _toDisplayString(worksSummary.value.total) + "）", 1),
              _createVNode(_component_v_chip, {
                size: "x-small",
                variant: "tonal",
                color: "primary"
              }, {
                default: _withCtx(() => [
                  _createTextVNode("待订阅 " + _toDisplayString(worksSummary.value.pending), 1)
                ]),
                _: 1
              }),
              worksSummary.value.cooling ? (_openBlock(), _createBlock(_component_v_chip, {
                key: 0,
                size: "x-small",
                variant: "tonal",
                color: "warning"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(" 冷却 " + _toDisplayString(worksSummary.value.cooling), 1)
                ]),
                _: 1
              })) : _createCommentVNode("", true),
              _createVNode(_component_v_chip, {
                size: "x-small",
                variant: "tonal",
                color: "success"
              }, {
                default: _withCtx(() => [
                  _createTextVNode("已下载 " + _toDisplayString(worksSummary.value.downloaded), 1)
                ]),
                _: 1
              }),
              _createVNode(_component_v_spacer),
              _createElementVNode("span", _hoisted_18, " 快照 " + _toDisplayString(works.value.refreshed_at ? _unref(formatTime)(works.value.refreshed_at) : "未刷新"), 1),
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "tonal",
                color: "primary",
                "prepend-icon": "mdi-cloud-refresh-outline",
                loading: refreshingWorks.value,
                title: "只去 TMDB / 豆瓣 拉取演员作品，不触发下载",
                onClick: doRefreshWorks
              }, {
                default: _withCtx(() => [..._cache[18] || (_cache[18] = [
                  _createTextVNode(" 刷新作品 ", -1)
                ])]),
                _: 1
              }, 8, ["loading"])
            ]),
            _createElementVNode("div", _hoisted_19, [
              _createVNode(_component_v_text_field, {
                modelValue: workKeyword.value,
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => workKeyword.value = $event),
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                "prepend-inner-icon": "mdi-magnify",
                placeholder: "筛选剧名 / 演员",
                class: "sdas-filter"
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_select, {
                modelValue: workState.value,
                "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => workState.value = $event),
                items: stateFilters,
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                class: "sdas-state-filter"
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_select, {
                modelValue: workActor.value,
                "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => workActor.value = $event),
                items: actorFilters.value,
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                class: "sdas-state-filter"
              }, null, 8, ["modelValue", "items"])
            ]),
            workMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
              key: 0,
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "mx-3 mb-2"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(workMessage.value) + " ", 1),
                _cache[19] || (_cache[19] = _createElementVNode("div", { class: "text-caption sdas-dim" }, "下载完成后由「整理入库」搬到媒体库，可在下方账本查看。", -1))
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            _createVNode(_component_v_table, {
              density: "compact",
              hover: "",
              class: "sdas-table"
            }, {
              default: _withCtx(() => [
                _cache[21] || (_cache[21] = _createElementVNode("thead", null, [
                  _createElementVNode("tr", null, [
                    _createElementVNode("th", { class: "text-start" }, "剧名"),
                    _createElementVNode("th", { class: "text-start" }, "年份"),
                    _createElementVNode("th", { class: "text-start" }, "演员"),
                    _createElementVNode("th", { class: "text-start" }, "发现"),
                    _createElementVNode("th", { class: "text-start" }, "状态"),
                    _createElementVNode("th", { class: "text-end" }, "操作")
                  ])
                ], -1)),
                _createElementVNode("tbody", null, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleWorks.value, (row) => {
                    return _openBlock(), _createElementBlock("tr", {
                      key: row.key
                    }, [
                      _createElementVNode("td", null, [
                        _createElementVNode("div", {
                          class: "sdas-title",
                          title: row.alt_title || row.title
                        }, _toDisplayString(row.title), 9, _hoisted_20)
                      ]),
                      _createElementVNode("td", _hoisted_21, _toDisplayString(row.year || "—"), 1),
                      _createElementVNode("td", _hoisted_22, _toDisplayString(row.actor || "—"), 1),
                      _createElementVNode("td", _hoisted_23, [
                        _createVNode(_component_v_chip, {
                          size: "x-small",
                          variant: "tonal"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(sourceLabel(row.source)), 1)
                          ]),
                          _: 2
                        }, 1024),
                        row.type ? (_openBlock(), _createElementBlock("span", _hoisted_24, _toDisplayString(row.type), 1)) : _createCommentVNode("", true)
                      ]),
                      _createElementVNode("td", null, [
                        _createVNode(_component_v_chip, {
                          size: "x-small",
                          variant: "tonal",
                          color: stateColor(row.state),
                          title: row.torrent_title || ""
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(stateLabel(row)), 1)
                          ]),
                          _: 2
                        }, 1032, ["color", "title"])
                      ]),
                      _createElementVNode("td", _hoisted_25, [
                        row.state === "pending" || row.state === "cooling" ? (_openBlock(), _createBlock(_component_v_btn, {
                          key: 0,
                          size: "x-small",
                          variant: "tonal",
                          color: "primary",
                          "prepend-icon": "mdi-plus",
                          loading: subscribingKey.value === row.key,
                          onClick: ($event) => doSubscribe(row)
                        }, {
                          default: _withCtx(() => [..._cache[20] || (_cache[20] = [
                            _createTextVNode(" 订阅 ", -1)
                          ])]),
                          _: 1
                        }, 8, ["loading", "onClick"])) : _createCommentVNode("", true),
                        _createVNode(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          icon: "mdi-magnify",
                          title: "到宿主的资源搜索页按剧名搜一遍（人工复核）",
                          href: workResourceUrl(row),
                          target: "_blank"
                        }, null, 8, ["href"])
                      ])
                    ]);
                  }), 128)),
                  !visibleWorks.value.length ? (_openBlock(), _createElementBlock("tr", _hoisted_26, [
                    _createElementVNode("td", _hoisted_27, _toDisplayString(worksEmptyHint.value), 1)
                  ])) : _createCommentVNode("", true)
                ])
              ]),
              _: 1
            }),
            visibleWorks.value.length < filteredWorks.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_28, [
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "text",
                onClick: _cache[5] || (_cache[5] = ($event) => workLimit.value += 50)
              }, {
                default: _withCtx(() => [
                  _createTextVNode(" 显示更多（还有 " + _toDisplayString(filteredWorks.value.length - visibleWorks.value.length) + " 部） ", 1)
                ]),
                _: 1
              })
            ])) : works.value.running ? (_openBlock(), _createElementBlock("div", _hoisted_29, " 后台任务执行中，作品列表随后会自动更新… ")) : _createCommentVNode("", true)
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        isMain.value ? (_openBlock(), _createBlock(_component_v_card, {
          key: 5,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_30, [
              _createVNode(_component_v_icon, {
                icon: "mdi-book-check-outline",
                size: "18",
                class: "mr-2"
              }),
              _createElementVNode("span", _hoisted_31, "已下载账本（" + _toDisplayString(ledger.value.length) + "）", 1),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_text_field, {
                modelValue: keyword.value,
                "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => keyword.value = $event),
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                "prepend-inner-icon": "mdi-magnify",
                placeholder: "筛选剧名 / 演员",
                class: "sdas-filter"
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "text",
                color: "error",
                disabled: !ledger.value.length,
                onClick: _cache[7] || (_cache[7] = ($event) => confirmClear.value = true)
              }, {
                default: _withCtx(() => [..._cache[22] || (_cache[22] = [
                  _createTextVNode(" 清空账本 ", -1)
                ])]),
                _: 1
              }, 8, ["disabled"])
            ]),
            _createVNode(_component_v_table, {
              density: "compact",
              hover: "",
              class: "sdas-table"
            }, {
              default: _withCtx(() => [
                _cache[23] || (_cache[23] = _createElementVNode("thead", null, [
                  _createElementVNode("tr", null, [
                    _createElementVNode("th", { class: "text-start" }, "剧名"),
                    _createElementVNode("th", { class: "text-start" }, "年份"),
                    _createElementVNode("th", { class: "text-start" }, "集数"),
                    _createElementVNode("th", { class: "text-start" }, "站点"),
                    _createElementVNode("th", { class: "text-start" }, "演员"),
                    _createElementVNode("th", { class: "text-start" }, "状态"),
                    _createElementVNode("th", { class: "text-end" }, "操作")
                  ])
                ], -1)),
                _createElementVNode("tbody", null, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleLedger.value, (row) => {
                    return _openBlock(), _createElementBlock("tr", {
                      key: row.key
                    }, [
                      _createElementVNode("td", null, [
                        _createElementVNode("div", {
                          class: "sdas-title",
                          title: row.torrent_title || row.title
                        }, _toDisplayString(row.title), 9, _hoisted_32)
                      ]),
                      _createElementVNode("td", _hoisted_33, _toDisplayString(row.year || "—"), 1),
                      _createElementVNode("td", _hoisted_34, _toDisplayString(row.episodes ? `全${row.episodes}集` : "—"), 1),
                      _createElementVNode("td", _hoisted_35, _toDisplayString(row.site_name || "—"), 1),
                      _createElementVNode("td", _hoisted_36, _toDisplayString(row.actor || "—"), 1),
                      _createElementVNode("td", null, [
                        _createVNode(_component_v_chip, {
                          size: "x-small",
                          variant: "tonal",
                          color: row.organized ? "success" : "info",
                          title: row.organized_path || ""
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(row.organized ? "已整理" : "已下载"), 1)
                          ]),
                          _: 2
                        }, 1032, ["color", "title"]),
                        (row.alternatives || 0) > 1 ? (_openBlock(), _createElementBlock("span", _hoisted_37, _toDisplayString(row.alternatives) + " 选 1 ", 1)) : _createCommentVNode("", true)
                      ]),
                      _createElementVNode("td", _hoisted_38, [
                        _createVNode(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          icon: "mdi-magnify",
                          title: "到宿主的资源搜索页按剧名搜一遍（人工复核）",
                          href: resourceUrl(row),
                          target: "_blank"
                        }, null, 8, ["href"]),
                        _createVNode(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          icon: "mdi-delete-outline",
                          color: "error",
                          title: "从账本移除（下次轮询可重新下载）",
                          loading: pendingKey.value === row.key,
                          onClick: ($event) => askRemove(row)
                        }, null, 8, ["loading", "onClick"])
                      ])
                    ]);
                  }), 128)),
                  !visibleLedger.value.length ? (_openBlock(), _createElementBlock("tr", _hoisted_39, [
                    _createElementVNode("td", _hoisted_40, _toDisplayString(ledger.value.length ? "没有匹配的记录" : "暂无记录，运行一轮后这里会出现已下载的剧"), 1)
                  ])) : _createCommentVNode("", true)
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        isMain.value && cooldown.value.length ? (_openBlock(), _createBlock(_component_v_card, {
          key: 6,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_41, [
              _createVNode(_component_v_icon, {
                icon: "mdi-timer-sand",
                size: "18",
                class: "mr-2"
              }),
              _createElementVNode("span", _hoisted_42, "未命中冷却（" + _toDisplayString(cooldown.value.length) + "）", 1),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "text",
                onClick: doClearCooldown
              }, {
                default: _withCtx(() => [..._cache[24] || (_cache[24] = [
                  _createTextVNode("清空冷却", -1)
                ])]),
                _: 1
              })
            ]),
            _createElementVNode("div", _hoisted_43, [
              _createElementVNode("div", _hoisted_44, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cooldown.value, (row) => {
                  return _openBlock(), _createBlock(_component_v_chip, {
                    key: row.key,
                    size: "small",
                    variant: "tonal",
                    color: "warning",
                    title: `${row.title}${row.year ? "（" + row.year + "）" : ""}｜${_unref(formatCooldown)(row.remaining_minutes)}`
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(row.title) + " ", 1),
                      _createElementVNode("span", _hoisted_45, _toDisplayString(_unref(formatCooldown)(row.remaining_minutes)), 1)
                    ]),
                    _: 2
                  }, 1032, ["title"]);
                }), 128))
              ]),
              _cache[25] || (_cache[25] = _createElementVNode("div", { class: "text-caption sdas-dim mt-2" }, " 这些剧在站点上暂时搜不到资源，24 小时内不再重复搜索（成功下载或手动清空后恢复）。 ", -1))
            ])
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        _createVNode(_component_v_dialog, {
          modelValue: removeDialog.value,
          "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => removeDialog.value = $event),
          "max-width": "420"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, { class: "pa-4" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_46, "从账本移除「" + _toDisplayString(removeTarget.value?.title) + "」？", 1),
                _cache[28] || (_cache[28] = _createElementVNode("div", { class: "text-caption sdas-dim mb-3" }, " 移除后这部剧会在下一轮轮询时重新搜索并下载，已下载的文件不会被删除。 ", -1)),
                _createElementVNode("div", _hoisted_47, [
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    variant: "text",
                    onClick: _cache[8] || (_cache[8] = ($event) => removeDialog.value = false)
                  }, {
                    default: _withCtx(() => [..._cache[26] || (_cache[26] = [
                      _createTextVNode("取消", -1)
                    ])]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    color: "error",
                    variant: "tonal",
                    loading: removing.value,
                    onClick: doRemove
                  }, {
                    default: _withCtx(() => [..._cache[27] || (_cache[27] = [
                      _createTextVNode("移除", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode(_component_v_dialog, {
          modelValue: confirmClear.value,
          "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => confirmClear.value = $event),
          "max-width": "420"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, { class: "pa-4" }, {
              default: _withCtx(() => [
                _cache[31] || (_cache[31] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "清空全部账本记录？", -1)),
                _cache[32] || (_cache[32] = _createElementVNode("div", { class: "text-caption sdas-dim mb-3" }, " 账本用于去重：清空后所有剧都会被当作未下载，下一轮会重新搜索并下载（已下载文件不受影响）。 同时会清空未命中冷却。 ", -1)),
                _createElementVNode("div", _hoisted_48, [
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    variant: "text",
                    onClick: _cache[10] || (_cache[10] = ($event) => confirmClear.value = false)
                  }, {
                    default: _withCtx(() => [..._cache[29] || (_cache[29] = [
                      _createTextVNode("取消", -1)
                    ])]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    color: "error",
                    variant: "tonal",
                    loading: clearing.value,
                    onClick: doClear
                  }, {
                    default: _withCtx(() => [..._cache[30] || (_cache[30] = [
                      _createTextVNode("清空", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"])
      ], 2);
    };
  }
});

const Panel = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-607ddfb7"]]);

export { Panel as default };
