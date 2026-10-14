import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import ConfigPanel from './__federation_expose_Config-CpyU8tD6.js';
import { p as proxyImage, m as mediaPageUrl, c as resourceSearchUrl, _ as _export_sfc, f as formatTime, d as formatCooldown, r as resolveApi, e as fetchWorks, P as PLUGIN_ID, g as refreshWorks, s as subscribeWork, u as unsubscribeWork, h as subscribeWorksBatch, i as unsubscribeWorksBatch, a as fetchStatus, j as fetchConfig, b as runOnce, o as organizeNow, k as saveConfig, l as removeLedgerEntry, n as clearLedger, q as clearCooldown } from './_plugin-vue_export-helper-cVwX3IEQ.js';

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {toDisplayString:_toDisplayString$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createCommentVNode:_createCommentVNode$1,renderList:_renderList$1,Fragment:_Fragment$1,unref:_unref$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,createElementVNode:_createElementVNode$1,withCtx:_withCtx$1,createTextVNode:_createTextVNode$1,createBlock:_createBlock$1,withModifiers:_withModifiers,normalizeClass:_normalizeClass$1} = await importShared('vue');

const _hoisted_1$1 = {
  key: 0,
  class: "text-medium-emphasis text-body-2 py-4 text-center"
};
const _hoisted_2$1 = {
  key: 1,
  class: "sdas-grid"
};
const _hoisted_3$1 = { class: "sdas-poster" };
const _hoisted_4$1 = { class: "sdas-poster-ph" };
const _hoisted_5$1 = { class: "sdas-poster-ph" };
const _hoisted_6$1 = ["title"];
const _hoisted_7$1 = { class: "sdas-meta" };
const _hoisted_8$1 = {
  key: 0,
  class: "sdas-dim"
};
const _hoisted_9$1 = {
  key: 1,
  class: "sdas-dim sdas-vote"
};
const _hoisted_10$1 = ["title"];
const _hoisted_11$1 = { class: "sdas-actors-text" };
const _hoisted_12$1 = ["title"];
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "WorkGrid",
  props: {
    works: {},
    pendingKey: {},
    emptyText: {},
    sites: { default: () => [] },
    selectable: { type: Boolean },
    selectedKeys: { default: () => [] }
  },
  emits: ["subscribe", "unsubscribe", "toggle-select"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    function isSelected(work) {
      return props.selectedKeys.includes(work.key);
    }
    function selectableState(work) {
      return work.state === "pending" || work.state === "cooling" || work.state === "subscribed";
    }
    function onCardClick(work) {
      if (!props.selectable || !selectableState(work)) return;
      emit("toggle-select", work);
    }
    function sourceLabel(source) {
      if (source === "tmdb") return "TMDB";
      if (source === "douban") return "豆瓣";
      if (source === "duanjubaike") return "短剧百科";
      return "未知";
    }
    function actable(work) {
      return work.state === "pending" || work.state === "cooling" || work.state === "subscribed";
    }
    function onAction(work) {
      if (work.state === "subscribed") {
        emit("unsubscribe", work);
        return;
      }
      emit("subscribe", work);
    }
    function statusOf(work) {
      if (work.state === "organized") {
        return {
          text: "已整理",
          action: "已入库",
          color: "success",
          icon: "mdi-folder-check-outline",
          title: work.time ? `已下载并整理入库（${work.time}）` : "已下载并整理入库"
        };
      }
      if (work.state === "downloaded") {
        return {
          text: "已下载",
          action: "已下载",
          color: "info",
          icon: "mdi-download-outline",
          title: work.torrent_title ? `已提交下载：${work.torrent_title}${work.site_name ? ` @ ${work.site_name}` : ""}（等待整理）` : "已提交下载，等待整理入库"
        };
      }
      if (work.state === "subscribed") {
        return {
          text: "订阅中",
          action: "取消订阅",
          color: "secondary",
          icon: "mdi-bookmark-check-outline",
          title: work.remaining_minutes ? `已订阅，但站点暂时没搜到资源（${work.remaining_minutes} 分钟前刚搜过）；插件每轮都会自动重试。点此取消订阅` : "已订阅：插件会按轮询节奏一直重试，直到下载成功。点此取消订阅"
        };
      }
      if (work.state === "cooling") {
        return {
          text: "冷却",
          action: "重试",
          color: "warning",
          icon: "mdi-refresh",
          title: `站点暂时没搜到资源，${work.remaining_minutes || 0} 分钟后可再试（也可现在手动重搜一次）`
        };
      }
      return {
        text: "待订阅",
        action: "订阅",
        color: "primary",
        icon: "mdi-plus",
        title: "订阅这部剧：立即按剧名到站点搜索并择优下载一条；这次没下到会自动重试"
      };
    }
    function detailHref(work) {
      if (!String(work.type || "").trim()) return "";
      return mediaPageUrl(work);
    }
    function resourceHref(work) {
      return resourceSearchUrl(work.title, props.sites);
    }
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$1("v-icon");
      const _component_v_img = _resolveComponent$1("v-img");
      const _component_v_chip = _resolveComponent$1("v-chip");
      const _component_v_checkbox_btn = _resolveComponent$1("v-checkbox-btn");
      const _component_v_card_text = _resolveComponent$1("v-card-text");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_card_actions = _resolveComponent$1("v-card-actions");
      const _component_v_card = _resolveComponent$1("v-card");
      return _openBlock$1(), _createElementBlock$1("div", null, [
        !__props.works.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, _toDisplayString$1(__props.emptyText || "暂无作品数据"), 1)) : (_openBlock$1(), _createElementBlock$1("div", _hoisted_2$1, [
          (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(__props.works, (work) => {
            return _openBlock$1(), _createBlock$1(_component_v_card, {
              key: work.key,
              variant: "outlined",
              class: _normalizeClass$1(["sdas-card", { "sdas-card-picked": __props.selectable && isSelected(work) }]),
              onClick: ($event) => onCardClick(work)
            }, {
              default: _withCtx$1(() => [
                _createElementVNode$1("div", _hoisted_3$1, [
                  _createVNode$1(_component_v_img, {
                    src: _unref$1(proxyImage)(work.poster),
                    "aspect-ratio": 2 / 3,
                    cover: "",
                    class: "sdas-poster-img"
                  }, {
                    placeholder: _withCtx$1(() => [
                      _createElementVNode$1("div", _hoisted_4$1, [
                        _createVNode$1(_component_v_icon, {
                          icon: "mdi-image-outline",
                          size: "22"
                        })
                      ])
                    ]),
                    error: _withCtx$1(() => [
                      _createElementVNode$1("div", _hoisted_5$1, [
                        _createVNode$1(_component_v_icon, {
                          icon: "mdi-movie-open-off-outline",
                          size: "22"
                        })
                      ])
                    ]),
                    _: 1
                  }, 8, ["src"]),
                  _createVNode$1(_component_v_chip, {
                    size: "x-small",
                    color: statusOf(work).color,
                    variant: "flat",
                    class: "sdas-badge sdas-badge-left",
                    title: statusOf(work).title
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(statusOf(work).text), 1)
                    ]),
                    _: 2
                  }, 1032, ["color", "title"]),
                  work.source ? (_openBlock$1(), _createBlock$1(_component_v_chip, {
                    key: 0,
                    size: "x-small",
                    variant: "flat",
                    class: "sdas-badge sdas-badge-right",
                    title: `作品信息来自 ${sourceLabel(work.source)}`
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(sourceLabel(work.source)), 1)
                    ]),
                    _: 2
                  }, 1032, ["title"])) : _createCommentVNode$1("", true),
                  __props.selectable ? (_openBlock$1(), _createBlock$1(_component_v_checkbox_btn, {
                    key: 1,
                    "model-value": isSelected(work),
                    disabled: !selectableState(work),
                    color: "primary",
                    density: "compact",
                    class: "sdas-pick",
                    title: selectableState(work) ? isSelected(work) ? "取消选择" : "选择这部剧" : "已下载/已入库的作品不支持批量订阅",
                    onClick: _cache[0] || (_cache[0] = _withModifiers(() => {
                    }, ["stop"])),
                    "onUpdate:modelValue": ($event) => emit("toggle-select", work)
                  }, null, 8, ["model-value", "disabled", "title", "onUpdate:modelValue"])) : _createCommentVNode$1("", true)
                ]),
                _createVNode$1(_component_v_card_text, { class: "pa-2 pb-1 sdas-body" }, {
                  default: _withCtx$1(() => [
                    _createElementVNode$1("div", {
                      class: "sdas-card-title",
                      title: work.alt_title || work.title
                    }, _toDisplayString$1(work.title), 9, _hoisted_6$1),
                    _createElementVNode$1("div", _hoisted_7$1, [
                      _createVNode$1(_component_v_chip, {
                        size: "x-small",
                        variant: "tonal",
                        label: ""
                      }, {
                        default: _withCtx$1(() => [
                          _createTextVNode$1(_toDisplayString$1(work.type || "未分类"), 1)
                        ]),
                        _: 2
                      }, 1024),
                      work.year ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_8$1, _toDisplayString$1(work.year), 1)) : _createCommentVNode$1("", true),
                      work.vote ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_9$1, [
                        _createVNode$1(_component_v_icon, {
                          icon: "mdi-star",
                          size: "11",
                          color: "amber"
                        }),
                        _createTextVNode$1(_toDisplayString$1(Number(work.vote).toFixed(1)), 1)
                      ])) : _createCommentVNode$1("", true)
                    ]),
                    work.actor ? (_openBlock$1(), _createElementBlock$1("div", {
                      key: 0,
                      class: "sdas-actors",
                      title: work.actor
                    }, [
                      _createVNode$1(_component_v_icon, {
                        icon: "mdi-account-outline",
                        size: "11"
                      }),
                      _createElementVNode$1("span", _hoisted_11$1, _toDisplayString$1(work.actor), 1)
                    ], 8, _hoisted_10$1)) : _createCommentVNode$1("", true),
                    work.torrent_title ? (_openBlock$1(), _createElementBlock$1("div", {
                      key: 1,
                      class: "sdas-dim sdas-source",
                      title: work.torrent_title
                    }, _toDisplayString$1(work.torrent_title), 9, _hoisted_12$1)) : _createCommentVNode$1("", true)
                  ]),
                  _: 2
                }, 1024),
                !__props.selectable ? (_openBlock$1(), _createBlock$1(_component_v_card_actions, {
                  key: 0,
                  class: "pa-2 pt-0 sdas-actions"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_v_btn, {
                      size: "small",
                      class: "sdas-sub-btn",
                      color: statusOf(work).color,
                      variant: actable(work) ? "flat" : "tonal",
                      "prepend-icon": statusOf(work).icon,
                      loading: __props.pendingKey === work.key,
                      disabled: !actable(work),
                      title: statusOf(work).title,
                      onClick: ($event) => onAction(work)
                    }, {
                      default: _withCtx$1(() => [
                        _createTextVNode$1(_toDisplayString$1(statusOf(work).action), 1)
                      ]),
                      _: 2
                    }, 1032, ["color", "variant", "prepend-icon", "loading", "disabled", "title", "onClick"]),
                    detailHref(work) ? (_openBlock$1(), _createBlock$1(_component_v_btn, {
                      key: 0,
                      size: "small",
                      variant: "text",
                      icon: "mdi-open-in-new",
                      title: "在 MoviePilot 中打开媒体详情（新标签页）",
                      href: detailHref(work),
                      target: "_blank",
                      rel: "noopener"
                    }, null, 8, ["href"])) : _createCommentVNode$1("", true),
                    resourceHref(work) ? (_openBlock$1(), _createBlock$1(_component_v_btn, {
                      key: 1,
                      size: "small",
                      variant: "text",
                      icon: "mdi-magnify",
                      title: "到 MoviePilot 的资源搜索页按剧名搜一遍（人工复核）",
                      href: resourceHref(work),
                      target: "_blank",
                      rel: "noopener"
                    }, null, 8, ["href"])) : _createCommentVNode$1("", true)
                  ]),
                  _: 2
                }, 1024)) : _createCommentVNode$1("", true)
              ]),
              _: 2
            }, 1032, ["class", "onClick"]);
          }), 128))
        ]))
      ]);
    };
  }
});

const WorkGrid = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-a5c997bb"]]);

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,unref:_unref,normalizeClass:_normalizeClass} = await importShared('vue');

const _hoisted_1 = {
  class: "d-flex align-center mb-3 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_2 = { class: "text-h6 ma-0" };
const _hoisted_3 = { class: "d-flex align-center pa-3 pb-1" };
const _hoisted_4 = { class: "px-3 pb-3" };
const _hoisted_5 = { class: "text-caption sdas-dim sdas-label" };
const _hoisted_6 = { class: "text-body-2" };
const _hoisted_7 = { class: "d-flex align-start py-1" };
const _hoisted_8 = { class: "text-body-2" };
const _hoisted_9 = {
  key: 0,
  class: "text-caption sdas-dim mt-2"
};
const _hoisted_10 = ["title"];
const _hoisted_11 = { class: "sdas-actor-chips" };
const _hoisted_12 = { class: "ml-1 sdas-dim" };
const _hoisted_13 = {
  key: 0,
  class: "mt-1"
};
const _hoisted_14 = { class: "d-flex align-center flex-wrap mt-2 sdas-toolbar" };
const _hoisted_15 = { class: "text-caption sdas-dim sdas-count" };
const _hoisted_16 = {
  key: 1,
  class: "d-flex align-center flex-wrap mt-2 sdas-pickbar"
};
const _hoisted_17 = { class: "text-caption" };
const _hoisted_18 = { class: "text-caption sdas-dim" };
const _hoisted_19 = {
  key: 2,
  class: "text-caption sdas-dim mt-2"
};
const _hoisted_20 = {
  key: 0,
  class: "text-caption sdas-dim"
};
const _hoisted_21 = {
  key: 1,
  class: "text-caption sdas-dim"
};
const _hoisted_22 = { class: "px-3 pb-3" };
const _hoisted_23 = {
  key: 1,
  class: "d-flex align-center justify-center mt-3 ga-2"
};
const _hoisted_24 = { class: "sdas-page-info" };
const _hoisted_25 = {
  class: "d-flex align-center pa-3 pb-1 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_26 = { class: "text-subtitle-2" };
const _hoisted_27 = ["title"];
const _hoisted_28 = { class: "text-caption" };
const _hoisted_29 = { class: "text-caption" };
const _hoisted_30 = { class: "text-caption" };
const _hoisted_31 = { class: "text-caption" };
const _hoisted_32 = {
  key: 0,
  class: "text-caption sdas-dim ml-1",
  title: "同剧命中多个资源，已择优"
};
const _hoisted_33 = { class: "text-end text-no-wrap" };
const _hoisted_34 = { key: 0 };
const _hoisted_35 = {
  colspan: "7",
  class: "text-center text-caption sdas-dim py-3"
};
const _hoisted_36 = { class: "d-flex align-center pa-3 pb-1" };
const _hoisted_37 = { class: "text-subtitle-2" };
const _hoisted_38 = { class: "px-3 pb-3" };
const _hoisted_39 = {
  class: "d-flex flex-wrap",
  style: { "gap": "6px" }
};
const _hoisted_40 = { class: "sdas-dim ml-1" };
const _hoisted_41 = { class: "text-subtitle-2 mb-2" };
const _hoisted_42 = { class: "d-flex" };
const _hoisted_43 = { class: "d-flex" };
const _hoisted_44 = { class: "sdas-settings" };
const {computed,onMounted,ref,watch} = await importShared('vue');
const WORK_PAGE_SIZE = 20;
const ALL_ACTORS = "all";
const ACTOR_COLLAPSE_LIMIT = 12;
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
      summary: { total: 0, pending: 0, subscribed: 0, cooling: 0, downloaded: 0 },
      refreshed_at: "",
      running: false,
      configured: false,
      actors: [],
      actor_count: 0
    });
    const workKeyword = ref("");
    const workState = ref("all");
    const workActor = ref("all");
    const workPage = ref(1);
    const refreshingWorks = ref(false);
    const subscribingKey = ref("");
    const workMessage = ref("");
    const settingsDialog = ref(false);
    const settingsLoading = ref(false);
    const settingsConfig = ref({});
    const settingsNotice = ref("");
    const actorsExpanded = ref(false);
    const worksSummary = computed(() => works.value.summary);
    const snapshotHours = computed(() => Number(remoteConfig.value?.snapshot_hours) || 24);
    const retryMinutes = computed(() => Number(remoteConfig.value?.retry_minutes) || 20);
    const snapshotHint = computed(
      () => `演员作品快照每 ${snapshotHours.value} 小时整体刷新一次（轮询期间直接用缓存，避免频繁请求豆瓣）；解析失败的演员 ${retryMinutes.value} 分钟后自动重试。点「刷新作品」可立即重新拉取。`
    );
    const actorFilters = computed(
      () => Array.from(new Set(works.value.items.map((item) => String(item.actor || "")).filter(Boolean))).map(
        (name) => ({
          value: name,
          count: works.value.items.filter((item) => String(item.actor || "") === name).length
        })
      )
    );
    const visibleActorFilters = computed(() => {
      const all = actorFilters.value;
      if (actorsExpanded.value || all.length <= ACTOR_COLLAPSE_LIMIT) return all;
      const head = all.slice(0, ACTOR_COLLAPSE_LIMIT);
      const current = all.find((item) => item.value === workActor.value);
      if (current && !head.includes(current)) return [current, ...head];
      return head;
    });
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
        if (actor !== ALL_ACTORS && String(row.actor || "") !== actor) return false;
        if (text) {
          const haystack = `${row.title || ""} ${row.actor || ""} ${row.year || ""} ${row.alt_title || ""}`;
          if (!haystack.toLowerCase().includes(text)) return false;
        }
        return true;
      });
    });
    const workPageCount = computed(
      () => Math.max(1, Math.ceil(filteredWorks.value.length / WORK_PAGE_SIZE))
    );
    const pagedWorks = computed(() => {
      const start = (workPage.value - 1) * WORK_PAGE_SIZE;
      return filteredWorks.value.slice(start, start + WORK_PAGE_SIZE);
    });
    watch([workKeyword, workState, workActor], () => {
      workPage.value = 1;
    });
    const worksEmptyHint = computed(() => {
      if (!works.value.configured) {
        return "还没配置演员与搜索站点：点右上角「设置」填写并保存";
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
          /** 后端归一的状态：''（正常）/ 'waiting'（等自动重试）/ 'empty'（豆瓣确无影视条目） */
          state: record?.state || "",
          ids: [record?.douban_id ? `豆瓣 ${record.douban_id}` : "", record?.tmdb_id ? `TMDB ${record.tmdb_id}` : ""].filter(Boolean).join("｜")
        };
      });
    });
    function isAuthError(message) {
      const text = String(message || "");
      return ["Cookie 已失效", "要求登录", "need_login"].some((marker) => text.includes(marker));
    }
    const waitingActors = computed(() => actorRows.value.filter((row) => row.state === "waiting"));
    const emptyActors = computed(() => actorRows.value.filter((row) => row.state === "empty"));
    const actorsHint = computed(() => {
      const parts = [];
      if (waitingActors.value.length) {
        const expired = waitingActors.value.some((row) => row.errors.some(isAuthError));
        parts.push(
          expired ? `${waitingActors.value.length} 位演员等待豆瓣登录态恢复，将自动重试（重新登录豆瓣并同步 CookieCloud 后恢复）` : `${waitingActors.value.length} 位演员本轮未取到作品，将在下一轮自动重试`
        );
      }
      if (emptyActors.value.length) {
        parts.push(`${emptyActors.value.length} 位演员在豆瓣没有影视作品集`);
      }
      return parts.join("；");
    });
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
    const organizeEnabled = computed(() => {
      const cfg = { ...props.config || {}, ...remoteConfig.value };
      return cfg.organize_enabled === true;
    });
    const configRows = computed(() => {
      const config = { ...props.config || {}, ...remoteConfig.value };
      const sites = config.sites || [];
      const rows = [
        {
          label: "搜索站点",
          value: sites.length ? sites.map((id) => siteName(Number(id))).join("，") : "未配置（无法搜索）"
        },
        {
          label: "搜索范围",
          value: config.prefer_short_drama_category === false ? "全站搜索" : "优先站点「短剧」分类"
        },
        { label: "下载器", value: String(config.downloader || "跟随宿主默认") },
        { label: "下载目录", value: String(config.download_path || "未配置") }
      ];
      if (organizeEnabled.value) {
        rows.push(
          { label: "媒体库目录", value: String(config.library_path || "未配置") },
          { label: "整理方式", value: transferLabel(config.transfer_type) },
          {
            label: "运行间隔",
            value: `${config.interval_hours || 6} 小时轮询 / ${config.organize_interval_minutes || 30} 分钟整理`
          }
        );
      } else {
        rows.push(
          { label: "整理", value: "由外部整理器负责（本插件不参与）" },
          { label: "运行间隔", value: `${config.interval_hours || 6} 小时轮询` }
        );
      }
      rows.push({
        label: "快照刷新",
        value: `${config.snapshot_hours || 24} 小时整体刷新一次，失败 ${config.retry_minutes || 20} 分钟后重试`
      });
      rows.push({ label: "豆瓣登录态", value: cookieLabel(config.douban_cookie_source) });
      return rows;
    });
    const visibleLedger = computed(() => {
      const text = keyword.value.trim().toLowerCase();
      if (!text) return ledger.value;
      return ledger.value.filter(
        (row) => `${row.title || ""} ${row.actor || ""} ${row.site_name || ""}`.toLowerCase().includes(text)
      );
    });
    function actorTitle(name) {
      const row = actorRows.value.find((item) => item.name === name);
      if (!row) return `只看「${name}」的作品`;
      const parts = [`只看「${name}」的作品`];
      if (row.ids) parts.push(row.ids);
      parts.push(`${row.works.length} 部作品`);
      if (row.errors.length) parts.push(row.errors.join("；"));
      return parts.join("｜");
    }
    function resourceUrl(row) {
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
    async function doUnsubscribe(row) {
      const api = resolveApi(props);
      if (!api) return;
      subscribingKey.value = row.key;
      workMessage.value = "";
      try {
        const res = await unsubscribeWork(api, { key: row.key });
        workMessage.value = res.message;
        await loadWorks();
        await load(false);
      } finally {
        subscribingKey.value = "";
      }
    }
    const selectMode = ref(false);
    const selectedKeys = ref([]);
    const batching = ref(false);
    const batchAction = ref("");
    function pickable(row) {
      return row.state === "pending" || row.state === "cooling" || row.state === "subscribed";
    }
    const selectedSubscribable = computed(
      () => selectedWorks.value.filter((row) => row.state === "pending" || row.state === "cooling")
    );
    const selectedSubscribed = computed(
      () => selectedWorks.value.filter((row) => row.state === "subscribed")
    );
    const selectedWorks = computed(() => {
      const wanted = new Set(selectedKeys.value);
      return works.value.items.filter((row) => wanted.has(row.key));
    });
    function toggleSelectMode() {
      selectMode.value = !selectMode.value;
      if (!selectMode.value) selectedKeys.value = [];
    }
    function toggleSelect(row) {
      const index = selectedKeys.value.indexOf(row.key);
      if (index >= 0) selectedKeys.value.splice(index, 1);
      else selectedKeys.value.push(row.key);
    }
    function clearSelection() {
      selectedKeys.value = [];
    }
    function selectAllVisible() {
      const keys = pagedWorks.value.filter(pickable).map((row) => row.key);
      const merged = /* @__PURE__ */ new Set([...selectedKeys.value, ...keys]);
      selectedKeys.value = Array.from(merged);
    }
    async function doBatchSubscribe() {
      const api = resolveApi(props);
      if (!api || !selectedSubscribable.value.length) return;
      batching.value = true;
      batchAction.value = "subscribe";
      workMessage.value = "";
      try {
        const res = await subscribeWorksBatch(api, {
          keys: selectedSubscribable.value.map((row) => row.key)
        });
        workMessage.value = res.message;
        await loadWorks();
        await load(false);
        emit("action");
      } finally {
        batching.value = false;
        batchAction.value = "";
      }
    }
    async function doBatchUnsubscribe() {
      const api = resolveApi(props);
      if (!api || !selectedSubscribed.value.length) return;
      batching.value = true;
      batchAction.value = "unsubscribe";
      workMessage.value = "";
      try {
        const res = await unsubscribeWorksBatch(api, {
          keys: selectedSubscribed.value.map((row) => row.key)
        });
        workMessage.value = res.message;
        await loadWorks();
        await load(false);
        emit("action");
      } finally {
        batching.value = false;
        batchAction.value = "";
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
    async function openSettings() {
      const api = resolveApi(props);
      settingsNotice.value = "";
      settingsLoading.value = true;
      let merged = { ...props.config || {}, ...remoteConfig.value };
      if (api) {
        try {
          const data = await fetchConfig(api);
          if (data?.config) {
            remoteConfig.value = data.config;
            searchSites.value = data.config.sites || [];
            merged = { ...props.config || {}, ...data.config };
          }
        } catch (err) {
          console.debug(`[${PLUGIN_ID}] 打开设置前读取配置失败`, err);
        }
      }
      settingsConfig.value = merged;
      settingsLoading.value = false;
      settingsDialog.value = true;
    }
    async function onConfigSaved(cfg) {
      if (cfg) remoteConfig.value = { ...remoteConfig.value, ...cfg };
      settingsDialog.value = false;
      settingsNotice.value = "设置已保存并生效";
      await loadConfig();
      await load(false);
      await loadWorks();
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
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_progress_linear = _resolveComponent("v-progress-linear");
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
            default: _withCtx(() => [..._cache[18] || (_cache[18] = [
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
          isMain.value ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 2,
            size: "small",
            variant: "tonal",
            color: "primary",
            "prepend-icon": "mdi-cog-outline",
            loading: settingsLoading.value,
            title: "打开插件设置：演员 / 搜索站点 / 下载器与目录 / 整理方式",
            onClick: openSettings
          }, {
            default: _withCtx(() => [..._cache[19] || (_cache[19] = [
              _createTextVNode(" 设置 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"])) : _createCommentVNode("", true),
          isMain.value ? (_openBlock(), _createBlock(_component_v_switch, {
            key: 3,
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
          isMain.value && organizeEnabled.value ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 4,
            size: "small",
            variant: "tonal",
            icon: "mdi-folder-move-outline",
            title: "立即整理一次（把已下载的搬进媒体库）",
            loading: organizing.value,
            onClick: doOrganize
          }, null, 8, ["loading"])) : _createCommentVNode("", true),
          isMain.value ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 5,
            size: "small",
            color: "primary",
            variant: "tonal",
            "prepend-icon": "mdi-play",
            loading: running.value,
            title: "立刻跑一轮：刷新演员作品并重试已订阅的作品（不会下载未订阅的剧）",
            onClick: doRun
          }, {
            default: _withCtx(() => [..._cache[20] || (_cache[20] = [
              _createTextVNode(" 立即运行 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"])) : _createCommentVNode("", true)
        ]),
        !enabled.value ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [..._cache[21] || (_cache[21] = [
            _createTextVNode(" 插件未启用或尚未配置演员/搜索站点，点右上角「设置」即可就地填写并保存。 ", -1)
          ])]),
          _: 1
        })) : _createCommentVNode("", true),
        settingsNotice.value ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 1,
          closable: "",
          type: "success",
          variant: "tonal",
          density: "compact",
          class: "mb-3",
          "onClick:close": _cache[2] || (_cache[2] = ($event) => settingsNotice.value = "")
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(settingsNotice.value), 1)
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        running.value ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 2,
          type: "info",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [..._cache[22] || (_cache[22] = [
            _createTextVNode(" 正在后台执行（演员多时一轮要跑较久），完成后此页会自动更新… ", -1)
          ])]),
          _: 1
        })) : lastMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 3,
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
          key: 4,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_3, [
              _createVNode(_component_v_icon, {
                icon: "mdi-cog-outline",
                size: "18",
                class: "mr-2"
              }),
              _cache[23] || (_cache[23] = _createElementVNode("span", { class: "text-subtitle-2" }, "运行配置", -1)),
              _createVNode(_component_v_spacer),
              _cache[24] || (_cache[24] = _createElementVNode("span", { class: "text-caption sdas-dim" }, "在插件配置页修改后保存即可生效", -1))
            ]),
            _createElementVNode("div", _hoisted_4, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(configRows.value, (item) => {
                return _openBlock(), _createElementBlock("div", {
                  key: item.label,
                  class: "d-flex align-start py-1"
                }, [
                  _createElementVNode("span", _hoisted_5, _toDisplayString(item.label), 1),
                  _createElementVNode("span", _hoisted_6, _toDisplayString(item.value), 1)
                ]);
              }), 128)),
              _createElementVNode("div", _hoisted_7, [
                _cache[25] || (_cache[25] = _createElementVNode("span", { class: "text-caption sdas-dim sdas-label" }, "上次运行", -1)),
                _createElementVNode("span", _hoisted_8, _toDisplayString(_unref(formatTime)(summary.value.last_run)), 1)
              ]),
              actorsHint.value ? (_openBlock(), _createElementBlock("div", _hoisted_9, _toDisplayString(actorsHint.value), 1)) : _createCommentVNode("", true)
            ])
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        isMain.value ? (_openBlock(), _createBlock(_component_v_card, {
          key: 5,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, { class: "d-flex align-center flex-wrap sdas-titlebar" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-movie-open-star-outline",
                  class: "mr-1"
                }),
                _cache[27] || (_cache[27] = _createElementVNode("span", null, "演员作品", -1)),
                _createVNode(_component_v_chip, {
                  size: "small",
                  variant: "tonal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(worksSummary.value.total) + " 部", 1)
                  ]),
                  _: 1
                }),
                worksSummary.value.pending ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 0,
                  size: "small",
                  variant: "tonal",
                  color: "primary"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 待订阅 " + _toDisplayString(worksSummary.value.pending), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                worksSummary.value.subscribed ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 1,
                  size: "small",
                  variant: "tonal",
                  color: "secondary"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 订阅中 " + _toDisplayString(worksSummary.value.subscribed), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                worksSummary.value.cooling ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 2,
                  size: "small",
                  variant: "tonal",
                  color: "warning"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 冷却 " + _toDisplayString(worksSummary.value.cooling), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                worksSummary.value.downloaded ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 3,
                  size: "small",
                  variant: "tonal",
                  color: "info"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 已下载 " + _toDisplayString(worksSummary.value.downloaded), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createVNode(_component_v_spacer),
                _createElementVNode("span", {
                  class: "text-caption sdas-dim",
                  title: snapshotHint.value
                }, " 快照 " + _toDisplayString(works.value.refreshed_at ? _unref(formatTime)(works.value.refreshed_at) : "未刷新"), 9, _hoisted_10),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  color: "primary",
                  "prepend-icon": "mdi-cloud-refresh-outline",
                  loading: refreshingWorks.value,
                  title: "立即重新拉取演员作品（强制重解析，忽略快照缓存；不触发下载）",
                  onClick: doRefreshWorks
                }, {
                  default: _withCtx(() => [..._cache[26] || (_cache[26] = [
                    _createTextVNode(" 刷新作品 ", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_text, { class: "pt-0" }, {
              default: _withCtx(() => [
                _createElementVNode("div", {
                  class: _normalizeClass(["sdas-chips", { "sdas-chips-expanded": actorsExpanded.value }])
                }, [
                  _createElementVNode("div", _hoisted_11, [
                    _createVNode(_component_v_chip, {
                      size: "small",
                      variant: "tonal",
                      color: workActor.value === ALL_ACTORS ? "primary" : void 0,
                      onClick: _cache[3] || (_cache[3] = ($event) => workActor.value = ALL_ACTORS)
                    }, {
                      default: _withCtx(() => [..._cache[28] || (_cache[28] = [
                        _createTextVNode(" 全部演员 ", -1)
                      ])]),
                      _: 1
                    }, 8, ["color"]),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleActorFilters.value, (item) => {
                      return _openBlock(), _createBlock(_component_v_chip, {
                        key: item.value,
                        size: "small",
                        variant: "tonal",
                        color: workActor.value === item.value ? "primary" : void 0,
                        title: actorTitle(item.value),
                        onClick: ($event) => workActor.value = item.value
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.value) + " ", 1),
                          _createElementVNode("span", _hoisted_12, _toDisplayString(item.count), 1)
                        ]),
                        _: 2
                      }, 1032, ["color", "title", "onClick"]);
                    }), 128))
                  ])
                ], 2),
                actorFilters.value.length > ACTOR_COLLAPSE_LIMIT ? (_openBlock(), _createElementBlock("div", _hoisted_13, [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    color: "primary",
                    "append-icon": actorsExpanded.value ? "mdi-chevron-up" : "mdi-chevron-down",
                    onClick: _cache[4] || (_cache[4] = ($event) => actorsExpanded.value = !actorsExpanded.value)
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(actorsExpanded.value ? "收起" : `展开全部（共 ${actorFilters.value.length} 位）`), 1)
                    ]),
                    _: 1
                  }, 8, ["append-icon"])
                ])) : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_14, [
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: workState.value,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => workState.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "all"
                      }, {
                        default: _withCtx(() => [..._cache[29] || (_cache[29] = [
                          _createTextVNode("全部", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "pending"
                      }, {
                        default: _withCtx(() => [..._cache[30] || (_cache[30] = [
                          _createTextVNode("待订阅", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "subscribed"
                      }, {
                        default: _withCtx(() => [..._cache[31] || (_cache[31] = [
                          _createTextVNode("订阅中", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "cooling"
                      }, {
                        default: _withCtx(() => [..._cache[32] || (_cache[32] = [
                          _createTextVNode("冷却中", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "downloaded"
                      }, {
                        default: _withCtx(() => [..._cache[33] || (_cache[33] = [
                          _createTextVNode("已下载", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _createVNode(_component_v_text_field, {
                    modelValue: workKeyword.value,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => workKeyword.value = $event),
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    clearable: "",
                    "prepend-inner-icon": "mdi-magnify",
                    placeholder: "搜索剧名 / 演员",
                    class: "sdas-filter"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_spacer),
                  _createElementVNode("span", _hoisted_15, " 筛出 " + _toDisplayString(filteredWorks.value.length) + " 部 ", 1),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    variant: selectMode.value ? "flat" : "tonal",
                    color: selectMode.value ? "primary" : void 0,
                    "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                    title: selectMode.value ? "退出多选" : "多选：勾选多部作品后一次批量订阅（已下载/已入库的不可选）",
                    onClick: toggleSelectMode
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(selectMode.value ? "退出多选" : "多选"), 1)
                    ]),
                    _: 1
                  }, 8, ["variant", "color", "title"])
                ]),
                selectMode.value ? (_openBlock(), _createElementBlock("div", _hoisted_16, [
                  _createElementVNode("span", _hoisted_17, [
                    _cache[34] || (_cache[34] = _createTextVNode(" 已选 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(selectedKeys.value.length), 1),
                    _cache[35] || (_cache[35] = _createTextVNode(" 部 ", -1))
                  ]),
                  _createElementVNode("span", _hoisted_18, " 待订阅 " + _toDisplayString(selectedSubscribable.value.length) + " ｜ 订阅中 " + _toDisplayString(selectedSubscribed.value.length), 1),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    color: "primary",
                    onClick: selectAllVisible
                  }, {
                    default: _withCtx(() => [..._cache[36] || (_cache[36] = [
                      _createTextVNode(" 选中本页可订阅的 ", -1)
                    ])]),
                    _: 1
                  }),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    disabled: !selectedKeys.value.length,
                    onClick: clearSelection
                  }, {
                    default: _withCtx(() => [..._cache[37] || (_cache[37] = [
                      _createTextVNode(" 清空 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    color: "secondary",
                    variant: "tonal",
                    "prepend-icon": "mdi-bookmark-remove-outline",
                    disabled: !selectedSubscribed.value.length || batching.value,
                    loading: batching.value && batchAction.value === "unsubscribe",
                    onClick: doBatchUnsubscribe
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 批量取消订阅（" + _toDisplayString(selectedSubscribed.value.length) + "） ", 1)
                    ]),
                    _: 1
                  }, 8, ["disabled", "loading"]),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    color: "primary",
                    variant: "flat",
                    "prepend-icon": "mdi-bookmark-plus-outline",
                    disabled: !selectedSubscribable.value.length || batching.value,
                    loading: batching.value && batchAction.value === "subscribe",
                    onClick: doBatchSubscribe
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 批量订阅（" + _toDisplayString(selectedSubscribable.value.length) + "） ", 1)
                    ]),
                    _: 1
                  }, 8, ["disabled", "loading"])
                ])) : _createCommentVNode("", true),
                actorsHint.value ? (_openBlock(), _createElementBlock("div", _hoisted_19, _toDisplayString(actorsHint.value), 1)) : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            workMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
              key: 0,
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "mx-3 mb-2"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(workMessage.value) + " ", 1),
                organizeEnabled.value ? (_openBlock(), _createElementBlock("div", _hoisted_20, " 下载完成后由「整理入库」搬到媒体库，可在下方账本查看。 ")) : (_openBlock(), _createElementBlock("div", _hoisted_21, " 下载完成后由外部整理器入库（本插件不参与整理），可在下方账本查看。 "))
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            _createElementVNode("div", _hoisted_22, [
              works.value.running || refreshingWorks.value ? (_openBlock(), _createBlock(_component_v_progress_linear, {
                key: 0,
                indeterminate: "",
                color: "primary",
                class: "mb-3"
              })) : _createCommentVNode("", true),
              _createVNode(WorkGrid, {
                works: pagedWorks.value,
                "pending-key": subscribingKey.value,
                sites: searchSites.value,
                "empty-text": worksEmptyHint.value,
                selectable: selectMode.value,
                "selected-keys": selectedKeys.value,
                onSubscribe: doSubscribe,
                onUnsubscribe: doUnsubscribe,
                onToggleSelect: toggleSelect
              }, null, 8, ["works", "pending-key", "sites", "empty-text", "selectable", "selected-keys"]),
              workPageCount.value > 1 ? (_openBlock(), _createElementBlock("div", _hoisted_23, [
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  icon: "mdi-chevron-left",
                  disabled: workPage.value <= 1,
                  onClick: _cache[7] || (_cache[7] = ($event) => workPage.value = Math.max(1, workPage.value - 1))
                }, null, 8, ["disabled"]),
                _createElementVNode("span", _hoisted_24, "第 " + _toDisplayString(workPage.value) + " / " + _toDisplayString(workPageCount.value) + " 页", 1),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "tonal",
                  icon: "mdi-chevron-right",
                  disabled: workPage.value >= workPageCount.value,
                  onClick: _cache[8] || (_cache[8] = ($event) => workPage.value = Math.min(workPageCount.value, workPage.value + 1))
                }, null, 8, ["disabled"])
              ])) : _createCommentVNode("", true)
            ])
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        isMain.value ? (_openBlock(), _createBlock(_component_v_card, {
          key: 6,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_25, [
              _createVNode(_component_v_icon, {
                icon: "mdi-book-check-outline",
                size: "18",
                class: "mr-2"
              }),
              _createElementVNode("span", _hoisted_26, "已下载账本（" + _toDisplayString(ledger.value.length) + "）", 1),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_text_field, {
                modelValue: keyword.value,
                "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => keyword.value = $event),
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
                onClick: _cache[10] || (_cache[10] = ($event) => confirmClear.value = true)
              }, {
                default: _withCtx(() => [..._cache[38] || (_cache[38] = [
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
                _cache[39] || (_cache[39] = _createElementVNode("thead", null, [
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
                        }, _toDisplayString(row.title), 9, _hoisted_27)
                      ]),
                      _createElementVNode("td", _hoisted_28, _toDisplayString(row.year || "—"), 1),
                      _createElementVNode("td", _hoisted_29, _toDisplayString(row.episodes ? `全${row.episodes}集` : "—"), 1),
                      _createElementVNode("td", _hoisted_30, _toDisplayString(row.site_name || "—"), 1),
                      _createElementVNode("td", _hoisted_31, _toDisplayString(row.actor || "—"), 1),
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
                        (row.alternatives || 0) > 1 ? (_openBlock(), _createElementBlock("span", _hoisted_32, _toDisplayString(row.alternatives) + " 选 1 ", 1)) : _createCommentVNode("", true)
                      ]),
                      _createElementVNode("td", _hoisted_33, [
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
                  !visibleLedger.value.length ? (_openBlock(), _createElementBlock("tr", _hoisted_34, [
                    _createElementVNode("td", _hoisted_35, _toDisplayString(ledger.value.length ? "没有匹配的记录" : "暂无记录，运行一轮后这里会出现已下载的剧"), 1)
                  ])) : _createCommentVNode("", true)
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        isMain.value && cooldown.value.length ? (_openBlock(), _createBlock(_component_v_card, {
          key: 7,
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_36, [
              _createVNode(_component_v_icon, {
                icon: "mdi-timer-sand",
                size: "18",
                class: "mr-2"
              }),
              _createElementVNode("span", _hoisted_37, "未命中冷却（" + _toDisplayString(cooldown.value.length) + "）", 1),
              _createVNode(_component_v_spacer),
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "text",
                onClick: doClearCooldown
              }, {
                default: _withCtx(() => [..._cache[40] || (_cache[40] = [
                  _createTextVNode("清空冷却", -1)
                ])]),
                _: 1
              })
            ]),
            _createElementVNode("div", _hoisted_38, [
              _createElementVNode("div", _hoisted_39, [
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
                      _createElementVNode("span", _hoisted_40, _toDisplayString(_unref(formatCooldown)(row.remaining_minutes)), 1)
                    ]),
                    _: 2
                  }, 1032, ["title"]);
                }), 128))
              ]),
              _cache[41] || (_cache[41] = _createElementVNode("div", { class: "text-caption sdas-dim mt-2" }, " 这些剧在站点上暂时搜不到资源，24 小时内不再重复搜索（成功下载或手动清空后恢复）。 ", -1))
            ])
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        _createVNode(_component_v_dialog, {
          modelValue: removeDialog.value,
          "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => removeDialog.value = $event),
          "max-width": "420"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, { class: "pa-4" }, {
              default: _withCtx(() => [
                _createElementVNode("div", _hoisted_41, "从账本移除「" + _toDisplayString(removeTarget.value?.title) + "」？", 1),
                _cache[44] || (_cache[44] = _createElementVNode("div", { class: "text-caption sdas-dim mb-3" }, " 移除后这部剧会在下一轮轮询时重新搜索并下载，已下载的文件不会被删除。 ", -1)),
                _createElementVNode("div", _hoisted_42, [
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    variant: "text",
                    onClick: _cache[11] || (_cache[11] = ($event) => removeDialog.value = false)
                  }, {
                    default: _withCtx(() => [..._cache[42] || (_cache[42] = [
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
                    default: _withCtx(() => [..._cache[43] || (_cache[43] = [
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
          "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => confirmClear.value = $event),
          "max-width": "420"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, { class: "pa-4" }, {
              default: _withCtx(() => [
                _cache[47] || (_cache[47] = _createElementVNode("div", { class: "text-subtitle-2 mb-2" }, "清空全部账本记录？", -1)),
                _cache[48] || (_cache[48] = _createElementVNode("div", { class: "text-caption sdas-dim mb-3" }, [
                  _createTextVNode(" 账本用于去重与「已下载」状态：清空后这些剧会回到「待订阅」，"),
                  _createElementVNode("b", null, "不会自动重新下载"),
                  _createTextVNode(" （订阅制下只有你点「订阅」的才会下）。同时会清空未命中冷却。 ")
                ], -1)),
                _createElementVNode("div", _hoisted_43, [
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    variant: "text",
                    onClick: _cache[13] || (_cache[13] = ($event) => confirmClear.value = false)
                  }, {
                    default: _withCtx(() => [..._cache[45] || (_cache[45] = [
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
                    default: _withCtx(() => [..._cache[46] || (_cache[46] = [
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
        }, 8, ["modelValue"]),
        _createVNode(_component_v_dialog, {
          modelValue: settingsDialog.value,
          "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => settingsDialog.value = $event),
          "max-width": "1000"
        }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_44, [
              settingsDialog.value ? (_openBlock(), _createBlock(ConfigPanel, {
                key: 0,
                "initial-config": settingsConfig.value,
                api: props.api,
                onClose: _cache[15] || (_cache[15] = ($event) => settingsDialog.value = false),
                onSave: onConfigSaved,
                onSwitch: _cache[16] || (_cache[16] = ($event) => settingsDialog.value = false)
              }, null, 8, ["initial-config", "api"])) : _createCommentVNode("", true)
            ])
          ]),
          _: 1
        }, 8, ["modelValue"])
      ], 2);
    };
  }
});

const Panel = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-1848ec35"]]);

export { Panel as default };
