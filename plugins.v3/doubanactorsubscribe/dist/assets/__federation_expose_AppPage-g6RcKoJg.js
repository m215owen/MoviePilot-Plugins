import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { I as IgnoredManager, W as WorkGrid } from './WorkGrid-3_kT3Ydi.js';
import { m as mergeWorks, s as sortWorks, w as workKey, r as resolveApi, i as ignoreWork, A as API_BASE, n as normalizeResult, P as PLUGIN_ID, u as unwrap, f as fetchSubscribedKeys, a as waitForRefresh, b as submitSubscribe, c as unsubscribeWork, d as removeActor, _ as _export_sfc } from './_plugin-vue_export-helper-Bu1j1gfm.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,normalizeClass:_normalizeClass} = await importShared('vue');

const _hoisted_1 = { class: "das-root pa-4" };
const _hoisted_2 = { class: "d-flex align-center mb-3 flex-wrap das-titlebar" };
const _hoisted_3 = { class: "text-caption" };
const _hoisted_4 = { class: "text-h6" };
const _hoisted_5 = { class: "das-actor-chips" };
const _hoisted_6 = {
  key: 2,
  class: "das-chip-new",
  title: "最近加入的演员"
};
const _hoisted_7 = { class: "ml-1 das-dim" };
const _hoisted_8 = {
  key: 0,
  class: "mt-1"
};
const _hoisted_9 = { class: "d-flex align-center flex-wrap mt-2 das-toolbar" };
const _hoisted_10 = {
  key: 3,
  class: "text-center text-medium-emphasis py-8"
};
const _hoisted_11 = {
  key: 5,
  class: "d-flex align-center justify-center mt-3 ga-2"
};
const _hoisted_12 = { class: "das-page-info" };
const {computed,inject,onMounted,ref,watch} = await importShared('vue');
const ALL_ACTORS = "__all__";
const ACTOR_COLLAPSE_LIMIT = 12;
const PAGE_SIZE = 20;
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "AppPage",
  props: {
    api: {},
    nativeSubscribe: { type: Function },
    navKey: {},
    pluginId: {}
  },
  emits: ["action"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const toast = inject("moviepilot:toast", null);
    const loading = ref(false);
    const refreshing = ref(false);
    const busy = ref(false);
    const pendingKey = ref("");
    const payload = ref(null);
    const subscribedKeys = ref([]);
    const enabled = ref(false);
    const toggling = ref(false);
    const subscribeSavePath = ref("");
    const subscribeDownloader = ref("");
    const subscribeSites = ref([]);
    const actorFilter = ref(ALL_ACTORS);
    const typeFilter = ref("");
    const onlyNew = ref(false);
    const onlyUnsubscribed = ref(false);
    const onlyNotInLibrary = ref(false);
    const sortMode = ref("year");
    const keyword = ref("");
    watch(
      [actorFilter, typeFilter, onlyNew, onlyUnsubscribed, onlyNotInLibrary, sortMode, keyword],
      resetPage
    );
    const actors = computed(() => payload.value?.actors || []);
    const actorsExpanded = ref(false);
    const visibleActors = computed(() => {
      const all = actors.value;
      if (actorsExpanded.value || all.length <= ACTOR_COLLAPSE_LIMIT) return all;
      const head = all.slice(0, ACTOR_COLLAPSE_LIMIT);
      const current = all.find(
        (actor) => actor.key === actorFilter.value || actor.id === actorFilter.value
      );
      if (current && !head.includes(current)) return [current, ...head];
      return head;
    });
    const newWindowDays = computed(() => Number(payload.value?.new_window_days || 0));
    const newWindowLabel = computed(
      () => newWindowDays.value > 0 ? `近 ${newWindowDays.value} 天新增` : "近期新增"
    );
    const newActorCount = computed(
      () => payload.value?.new_actor_count ?? actors.value.filter((actor) => actor.is_new).length
    );
    const libraryKnown = computed(() => Boolean(payload.value?.library_known));
    const statCards = computed(() => {
      const rows = [
        { label: "演员", value: payload.value?.actor_count ?? actors.value.length, title: "" },
        { label: "作品", value: payload.value?.work_count ?? 0, title: "" },
        {
          label: `${newWindowLabel.value}（演员 / 作品）`,
          value: `${newActorCount.value} / ${payload.value?.new_count ?? 0}`,
          title: `新演员 = 最近 ${newWindowDays.value} 天加入订阅列表的演员（chip 上标「新」）；新作品 = 首次出现在该演员加入之后的作品。刚加入的演员过去的老作品属于基线，不会逐张标「新」，只有之后刷新才冒出来的作品才带「新」。`
        }
      ];
      if (libraryKnown.value) {
        rows.push({
          label: "已在媒体库",
          value: payload.value?.library_count ?? 0,
          title: "已在媒体库中的作品数（判定与媒体详情页的「是否在媒体库」一致：先按豆瓣/TMDB 身份匹配，未命中时按片名 + 类型 + 年份回退匹配）。卡片角上标「已入库」；自动订阅会跳过这些作品。"
        });
      }
      rows.push({ label: "累计刷新", value: payload.value?.run_count ?? 0, title: "" });
      return rows;
    });
    const cookieChip = computed(() => {
      const source = payload.value?.douban_cookie_source;
      const hint = payload.value?.douban_cookie_hint || "";
      if (source === "manual") {
        return { text: "Cookie：手填", color: "success", icon: "mdi-cookie", title: "使用插件内手工粘贴的豆瓣 Cookie" };
      }
      if (source === "cookiecloud") {
        return {
          text: "Cookie：CookieCloud",
          color: "success",
          icon: "mdi-cookie",
          title: "已自动从宿主 CookieCloud 读取豆瓣登录态，搜索额度更高"
        };
      }
      return {
        text: "Cookie：未取到",
        color: "warning",
        icon: "mdi-cookie-alert",
        title: hint || "未取到豆瓣登录态，按名称搜索演员会被严格限流；可在配置页手工粘贴 Cookie"
      };
    });
    const unresolvedCount = computed(
      () => payload.value?.unresolved_count ?? actors.value.filter((actor) => !actor.id).length
    );
    const cooldownCount = computed(() => payload.value?.search_cooldown_count ?? 0);
    const unresolvedHint = computed(
      () => `还有 ${unresolvedCount.value} 位演员没解析出人物 ID（共 ${actors.value.length} 位）：` + (cooldownCount.value ? `其中 ${cooldownCount.value} 位在 24 小时搜索冷却内，需等冷却结束后才会重试；` : `下次刷新会继续按名称搜索；`) + `直接填人物 ID 或主页链接可完全跳过搜索`
    );
    function isSubscribed(work) {
      return subscribedKeys.value.includes(workKey(work));
    }
    function actorMatches(actor) {
      return !actorFilter.value || actorFilter.value === ALL_ACTORS ? true : actor.key === actorFilter.value || actor.id === actorFilter.value;
    }
    function isActorActive(actor) {
      return actorFilter.value === actor.key || actorFilter.value === actor.id;
    }
    function isFuzzyActor(actor) {
      return Boolean(actor.fuzzy) && Boolean(actor.name) && actor.name !== actor.key;
    }
    function actorTitle(actor) {
      const suffix = "（点右侧 × 可从订阅演员中移除）";
      const prefix = actor.is_new && actor.joined_at ? `最近加入（${actor.joined_at}）｜` : "";
      if (actor.error) return `${prefix}${actor.error}${suffix}`;
      if (isFuzzyActor(actor)) {
        const candidates = (actor.candidates || []).filter(Boolean);
        return `${prefix}配置的「${actor.key}」在豆瓣没有同名演员，已按最接近的结果「${actor.name}」解析` + (candidates.length ? `（候选：${candidates.join(" / ")}）` : "") + `。请核对，或把配置项改成人物 ID 精确指定。${suffix}`;
      }
      return `${prefix}${actor.name}${suffix}`;
    }
    const visibleWorks = computed(() => {
      const groups = actors.value.filter(actorMatches);
      let works = mergeWorks(groups);
      if (typeFilter.value) works = works.filter((work) => work.type === typeFilter.value);
      if (onlyNew.value) works = works.filter((work) => work.is_new);
      if (onlyUnsubscribed.value) works = works.filter((work) => !isSubscribed(work));
      if (onlyNotInLibrary.value) works = works.filter((work) => work.in_library !== true);
      const kw = keyword.value.trim().toLowerCase();
      if (kw) {
        works = works.filter(
          (work) => String(work.title || "").toLowerCase().includes(kw) || (work.actorNames || []).some((name) => String(name).toLowerCase().includes(kw))
        );
      }
      return sortWorks(works, sortMode.value);
    });
    const pendingTargets = computed(
      () => visibleWorks.value.filter((work) => !isSubscribed(work))
    );
    const page = ref(1);
    const pageCount = computed(() => Math.max(1, Math.ceil(visibleWorks.value.length / PAGE_SIZE)));
    const pagedWorks = computed(() => {
      const start = (page.value - 1) * PAGE_SIZE;
      return visibleWorks.value.slice(start, start + PAGE_SIZE);
    });
    function resetPage() {
      page.value = 1;
    }
    function notify(type, message) {
      const handler = toast && toast[type];
      if (typeof handler === "function") {
        handler.call(toast, message);
        return;
      }
      if (type === "error") console.warn(`[${PLUGIN_ID}] ${message}`);
      else console.info(`[${PLUGIN_ID}] ${message}`);
    }
    function applyPayload(data) {
      payload.value = data;
      enabled.value = Boolean(data.enabled);
      subscribeSavePath.value = data.subscribe_save_path || "";
      subscribeDownloader.value = data.subscribe_downloader || "";
      subscribeSites.value = data.subscribe_sites || [];
    }
    async function ignore(work) {
      const api = resolveApi(props);
      if (!api) return;
      const res = await ignoreWork(api, work);
      notify(res.ok ? "success" : "error", res.message);
      if (res.ok) await load(false);
    }
    async function toggleEnabled(value) {
      const api = resolveApi(props);
      if (!api) {
        notify("error", "宿主 API 未就绪");
        return;
      }
      const next = Boolean(value);
      toggling.value = true;
      try {
        const raw = await api.put(`${API_BASE}/config`, { enabled: next });
        const res = normalizeResult(raw);
        if (!res.ok) {
          enabled.value = !next;
          notify("error", res.message || "切换状态失败");
          return;
        }
        notify("success", next ? "插件已启用" : "插件已停用");
        await load(false);
        if (next) await refresh();
      } catch (err) {
        enabled.value = !next;
        notify("error", "切换状态失败");
        console.warn(`[${PLUGIN_ID}] 切换启用状态失败`, err);
      } finally {
        toggling.value = false;
      }
    }
    async function load(showSpinner = true) {
      const api = resolveApi(props);
      if (!api) return;
      if (showSpinner) loading.value = true;
      try {
        const raw = await api.get(`${API_BASE}/works`);
        const res = unwrap(raw);
        if (res?.success && res.data) applyPayload(res.data);
        subscribedKeys.value = await fetchSubscribedKeys(api);
        if (payload.value?.pending_refresh || payload.value?.refreshing) {
          waitForRefresh(api, applyPayload);
        }
      } catch (err) {
        console.warn(`[${PLUGIN_ID}] 全页加载失败`, err);
      } finally {
        loading.value = false;
      }
    }
    async function refresh() {
      const api = resolveApi(props);
      if (!api) return;
      refreshing.value = true;
      try {
        const raw = await api.post(`${API_BASE}/run`);
        const res = unwrap(raw);
        if (res?.data) applyPayload(res.data);
        if (res?.success) notify("success", res.message || "已开始刷新演员最新作品");
        else notify("error", res?.message || "刷新失败");
        subscribedKeys.value = await fetchSubscribedKeys(api);
        if (payload.value?.refreshing || payload.value?.pending_refresh) {
          waitForRefresh(api, applyPayload);
        }
        emit("action");
      } catch (err) {
        notify("error", "刷新失败，请查看后端日志");
        console.warn(`[${PLUGIN_ID}] 刷新失败`, err);
      } finally {
        refreshing.value = false;
      }
    }
    async function subscribe(work) {
      const api = resolveApi(props);
      if (!api) return;
      const key = workKey(work);
      pendingKey.value = key;
      try {
        const res = await submitSubscribe(api, work, {
          savePath: subscribeSavePath.value,
          downloader: subscribeDownloader.value,
          sites: subscribeSites.value
        });
        if (res.ok) {
          if (!subscribedKeys.value.includes(key)) subscribedKeys.value.push(key);
          notify("success", res.message);
        } else {
          notify("error", `${work.title} 订阅失败：${res.message}`);
        }
      } finally {
        pendingKey.value = "";
      }
    }
    async function unsubscribe(work) {
      const api = resolveApi(props);
      if (!api) return;
      const key = workKey(work);
      pendingKey.value = key;
      try {
        const res = await unsubscribeWork(api, work);
        if (res.ok) {
          subscribedKeys.value = subscribedKeys.value.filter((item) => item !== key);
          notify("success", res.message);
        } else {
          notify("error", `${work.title} 取消订阅失败：${res.message}`);
        }
      } finally {
        pendingKey.value = "";
      }
    }
    const confirmDialog = ref(false);
    const removeTarget = ref(null);
    const removeDialog = ref(false);
    const removing = ref(false);
    function askRemoveActor(actor) {
      removeTarget.value = actor;
      removeDialog.value = true;
    }
    async function doRemoveActor() {
      const actor = removeTarget.value;
      removeDialog.value = false;
      if (!actor) return;
      const api = resolveApi(props);
      if (!api) return;
      removing.value = true;
      try {
        const res = await removeActor(api, actor);
        notify(res.ok ? "success" : "error", res.message);
        if (res.ok) {
          if (actorFilter.value === actor.key || actorFilter.value === actor.id) {
            actorFilter.value = ALL_ACTORS;
          }
          await load(false);
        }
      } finally {
        removing.value = false;
        removeTarget.value = null;
      }
    }
    function confirmSubscribeMany() {
      if (!pendingTargets.value.length) return;
      confirmDialog.value = true;
    }
    async function doSubscribeMany() {
      confirmDialog.value = false;
      await subscribeMany(pendingTargets.value);
    }
    async function subscribeMany(works) {
      const api = resolveApi(props);
      if (!api || !works.length) return;
      busy.value = true;
      let success = 0;
      const failures = [];
      try {
        for (const work of works) {
          const key = workKey(work);
          pendingKey.value = key;
          const res = await submitSubscribe(api, work, {
            savePath: subscribeSavePath.value,
            downloader: subscribeDownloader.value,
            sites: subscribeSites.value
          });
          if (res.ok) {
            success += 1;
            if (!subscribedKeys.value.includes(key)) subscribedKeys.value.push(key);
          } else {
            failures.push(`${work.title}：${res.message}`);
          }
          await new Promise((resolve) => window.setTimeout(resolve, 150));
        }
      } finally {
        pendingKey.value = "";
        busy.value = false;
      }
      if (success) notify("success", `已提交 ${success} 部作品的订阅`);
      if (failures.length) notify("error", `${failures.length} 部订阅失败，例如 ${failures[0]}`);
    }
    watch(
      () => payload.value?.enabled,
      (value) => {
        if (typeof value === "boolean") enabled.value = value;
      }
    );
    onMounted(() => load());
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
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      const _component_v_checkbox = _resolveComponent("v-checkbox");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_card_actions = _resolveComponent("v-card-actions");
      const _component_v_dialog = _resolveComponent("v-dialog");
      const _component_v_progress_linear = _resolveComponent("v-progress-linear");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_icon, {
            icon: "mdi-account-star-outline",
            class: "mr-1"
          }),
          _cache[16] || (_cache[16] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "豆瓣演员作品面板", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(__props.pluginId || "DoubanActorSubscribe") + " / " + _toDisplayString(__props.navKey || "main"), 1)
            ]),
            _: 1
          }),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal",
            class: "ml-1",
            color: cookieChip.value.color,
            "prepend-icon": cookieChip.value.icon,
            title: cookieChip.value.title
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(cookieChip.value.text), 1)
            ]),
            _: 1
          }, 8, ["color", "prepend-icon", "title"]),
          unresolvedCount.value ? (_openBlock(), _createBlock(_component_v_chip, {
            key: 0,
            size: "small",
            variant: "tonal",
            color: "warning",
            class: "ml-1",
            "prepend-icon": "mdi-timer-sand",
            title: unresolvedHint.value
          }, {
            default: _withCtx(() => [
              _createTextVNode(" 待解析 " + _toDisplayString(unresolvedCount.value), 1)
            ]),
            _: 1
          }, 8, ["title"])) : _createCommentVNode("", true),
          _createVNode(IgnoredManager, {
            class: "ml-1",
            api: props.api,
            ignored: payload.value?.ignored || [],
            count: payload.value?.ignored_count || 0,
            onChanged: _cache[0] || (_cache[0] = ($event) => load(false))
          }, null, 8, ["api", "ignored", "count"]),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_switch, {
            modelValue: enabled.value,
            "onUpdate:modelValue": [
              _cache[1] || (_cache[1] = ($event) => enabled.value = $event),
              toggleEnabled
            ],
            color: "primary",
            "hide-details": "",
            density: "compact",
            loading: toggling.value,
            label: enabled.value ? "已启用" : "已停用",
            class: "das-switch"
          }, null, 8, ["modelValue", "loading", "label"]),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            icon: "mdi-refresh",
            loading: refreshing.value || Boolean(payload.value?.refreshing),
            onClick: refresh
          }, null, 8, ["loading"])
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
        !payload.value?.enabled ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [..._cache[17] || (_cache[17] = [
            _createTextVNode(" 插件未启用或尚未配置演员，请先到配置页填写演员并保存。 ", -1)
          ])]),
          _: 1
        })) : _createCommentVNode("", true),
        payload.value?.refreshing || payload.value?.pending_refresh ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 1,
          type: "info",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(payload.value?.refreshing ? "正在后台刷新演员作品（演员较多时需要几分钟），完成后此页会自动更新…" : "演员列表已变更，正在后台刷新作品，稍候会自动更新…"), 1)
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_text, { class: "pb-2" }, {
              default: _withCtx(() => [
                _createElementVNode("div", {
                  class: _normalizeClass(["das-chips", { "das-chips-expanded": actorsExpanded.value }])
                }, [
                  _createElementVNode("div", _hoisted_5, [
                    _createVNode(_component_v_chip, {
                      size: "small",
                      variant: "tonal",
                      color: actorFilter.value === ALL_ACTORS ? "primary" : void 0,
                      onClick: _cache[2] || (_cache[2] = ($event) => actorFilter.value = ALL_ACTORS)
                    }, {
                      default: _withCtx(() => [..._cache[18] || (_cache[18] = [
                        _createTextVNode(" 全部演员 ", -1)
                      ])]),
                      _: 1
                    }, 8, ["color"]),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(visibleActors.value, (actor) => {
                      return _openBlock(), _createBlock(_component_v_chip, {
                        key: actor.key,
                        size: "small",
                        variant: "tonal",
                        color: isActorActive(actor) ? "primary" : void 0,
                        closable: "",
                        "close-icon": "mdi-close",
                        title: actorTitle(actor),
                        onClick: ($event) => actorFilter.value = actor.key,
                        "onClick:close": ($event) => askRemoveActor(actor)
                      }, {
                        default: _withCtx(() => [
                          actor.error ? (_openBlock(), _createBlock(_component_v_icon, {
                            key: 0,
                            icon: "mdi-alert-circle-outline",
                            size: "14",
                            color: "warning",
                            class: "mr-1"
                          })) : isFuzzyActor(actor) ? (_openBlock(), _createBlock(_component_v_icon, {
                            key: 1,
                            icon: "mdi-help-circle-outline",
                            size: "14",
                            color: "warning",
                            class: "mr-1"
                          })) : _createCommentVNode("", true),
                          actor.is_new ? (_openBlock(), _createElementBlock("span", _hoisted_6, "新")) : _createCommentVNode("", true),
                          isFuzzyActor(actor) ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                            _createTextVNode(_toDisplayString(actor.key) + " ", 1),
                            _cache[19] || (_cache[19] = _createElementVNode("span", { class: "das-dim mx-1" }, "→", -1)),
                            _createTextVNode(" " + _toDisplayString(actor.name), 1)
                          ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
                            _createTextVNode(_toDisplayString(actor.name), 1)
                          ], 64)),
                          _createElementVNode("span", _hoisted_7, _toDisplayString((actor.works || []).length), 1)
                        ]),
                        _: 2
                      }, 1032, ["color", "title", "onClick", "onClick:close"]);
                    }), 128))
                  ])
                ], 2),
                actors.value.length > ACTOR_COLLAPSE_LIMIT ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    color: "primary",
                    "append-icon": actorsExpanded.value ? "mdi-chevron-up" : "mdi-chevron-down",
                    onClick: _cache[3] || (_cache[3] = ($event) => actorsExpanded.value = !actorsExpanded.value)
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(actorsExpanded.value ? "收起" : `展开全部（共 ${actors.value.length} 位）`), 1)
                    ]),
                    _: 1
                  }, 8, ["append-icon"])
                ])) : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_9, [
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: typeFilter.value,
                    "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => typeFilter.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: ""
                      }, {
                        default: _withCtx(() => [..._cache[20] || (_cache[20] = [
                          _createTextVNode("全部", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电影"
                      }, {
                        default: _withCtx(() => [..._cache[21] || (_cache[21] = [
                          _createTextVNode("电影", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "电视剧"
                      }, {
                        default: _withCtx(() => [..._cache[22] || (_cache[22] = [
                          _createTextVNode("电视剧", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _createVNode(_component_v_checkbox, {
                    modelValue: onlyNew.value,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => onlyNew.value = $event),
                    label: "只看新作品",
                    density: "compact",
                    "hide-details": "",
                    class: "das-checkbox",
                    title: "只显示在你订阅的演员加入之后才出现的作品；刚加入演员的历史作品属于基线，不算新。想看新加的演员，请点上方的「新」chip"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_checkbox, {
                    modelValue: onlyUnsubscribed.value,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => onlyUnsubscribed.value = $event),
                    label: "只看未订阅",
                    density: "compact",
                    "hide-details": "",
                    class: "das-checkbox"
                  }, null, 8, ["modelValue"]),
                  libraryKnown.value ? (_openBlock(), _createBlock(_component_v_checkbox, {
                    key: 0,
                    modelValue: onlyNotInLibrary.value,
                    "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => onlyNotInLibrary.value = $event),
                    label: "只看未入库",
                    density: "compact",
                    "hide-details": "",
                    class: "das-checkbox",
                    title: "只显示还没进媒体库的作品（判定与媒体详情页一致）。已在库的作品卡片角上会标「已入库」，自动订阅也会跳过它们"
                  }, null, 8, ["modelValue"])) : _createCommentVNode("", true),
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: sortMode.value,
                    "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => sortMode.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "year"
                      }, {
                        default: _withCtx(() => [..._cache[23] || (_cache[23] = [
                          _createTextVNode("最新优先", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "new"
                      }, {
                        default: _withCtx(() => [..._cache[24] || (_cache[24] = [
                          _createTextVNode("新作品优先", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"]),
                  _createVNode(_component_v_text_field, {
                    modelValue: keyword.value,
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => keyword.value = $event),
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    clearable: "",
                    "prepend-inner-icon": "mdi-magnify",
                    placeholder: "搜索作品名 / 演员名",
                    class: "das-search"
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    color: "primary",
                    variant: "tonal",
                    "prepend-icon": "mdi-plus-multiple",
                    disabled: busy.value || !pendingTargets.value.length,
                    onClick: confirmSubscribeMany
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 订阅筛选结果（" + _toDisplayString(pendingTargets.value.length) + "） ", 1)
                    ]),
                    _: 1
                  }, 8, ["disabled"])
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_dialog, {
          modelValue: confirmDialog.value,
          "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => confirmDialog.value = $event),
          "max-width": "460"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, null, {
                  default: _withCtx(() => [..._cache[25] || (_cache[25] = [
                    _createTextVNode("确认批量订阅？", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    _cache[26] || (_cache[26] = _createTextVNode(" 将把当前筛选结果里的 ", -1)),
                    _createElementVNode("strong", null, _toDisplayString(pendingTargets.value.length), 1),
                    _cache[27] || (_cache[27] = _createTextVNode(" 部未订阅作品 一次性提交到订阅系统（按豆瓣 ID 精确订阅）。 ", -1)),
                    pendingTargets.value.length > 20 ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _createTextVNode(" 数量较多，确认后请耐心等待逐条提交完成。 ")
                    ], 64)) : _createCommentVNode("", true)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_actions, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[10] || (_cache[10] = ($event) => confirmDialog.value = false)
                    }, {
                      default: _withCtx(() => [..._cache[28] || (_cache[28] = [
                        _createTextVNode("取消", -1)
                      ])]),
                      _: 1
                    }),
                    _createVNode(_component_v_btn, {
                      color: "primary",
                      onClick: doSubscribeMany
                    }, {
                      default: _withCtx(() => [..._cache[29] || (_cache[29] = [
                        _createTextVNode("确认订阅", -1)
                      ])]),
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
        }, 8, ["modelValue"]),
        _createVNode(_component_v_dialog, {
          modelValue: removeDialog.value,
          "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => removeDialog.value = $event),
          "max-width": "460"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, null, {
                  default: _withCtx(() => [..._cache[30] || (_cache[30] = [
                    _createTextVNode("从订阅演员中移除？", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    _cache[31] || (_cache[31] = _createTextVNode(" 将移除演员 ", -1)),
                    _createElementVNode("strong", null, _toDisplayString(removeTarget.value?.name || removeTarget.value?.key), 1),
                    _cache[32] || (_cache[32] = _createTextVNode("， 并", -1)),
                    _cache[33] || (_cache[33] = _createElementVNode("strong", null, "同步删除配置页里的同名条目", -1)),
                    _cache[34] || (_cache[34] = _createTextVNode("、清理它的作品数据。 以后不会再抓取这位演员的作品；已经提交的订阅不受影响。 ", -1))
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_actions, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[12] || (_cache[12] = ($event) => removeDialog.value = false)
                    }, {
                      default: _withCtx(() => [..._cache[35] || (_cache[35] = [
                        _createTextVNode("取消", -1)
                      ])]),
                      _: 1
                    }),
                    _createVNode(_component_v_btn, {
                      color: "error",
                      variant: "tonal",
                      loading: removing.value,
                      onClick: doRemoveActor
                    }, {
                      default: _withCtx(() => [..._cache[36] || (_cache[36] = [
                        _createTextVNode(" 确认移除 ", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        loading.value || payload.value?.refreshing ? (_openBlock(), _createBlock(_component_v_progress_linear, {
          key: 2,
          indeterminate: "",
          color: "primary",
          class: "mb-3"
        })) : _createCommentVNode("", true),
        !visibleWorks.value.length && !loading.value ? (_openBlock(), _createElementBlock("div", _hoisted_10, " 没有符合条件的作品。 ")) : (_openBlock(), _createBlock(WorkGrid, {
          key: 4,
          works: pagedWorks.value,
          "subscribed-keys": subscribedKeys.value,
          "pending-key": pendingKey.value,
          busy: busy.value,
          "empty-text": "没有符合条件的作品",
          onSubscribe: subscribe,
          onUnsubscribe: unsubscribe,
          onIgnore: ignore
        }, null, 8, ["works", "subscribed-keys", "pending-key", "busy"])),
        pageCount.value > 1 ? (_openBlock(), _createElementBlock("div", _hoisted_11, [
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            icon: "mdi-chevron-left",
            disabled: page.value <= 1,
            onClick: _cache[14] || (_cache[14] = ($event) => page.value = Math.max(1, page.value - 1))
          }, null, 8, ["disabled"]),
          _createElementVNode("span", _hoisted_12, "第 " + _toDisplayString(page.value) + " / " + _toDisplayString(pageCount.value) + " 页", 1),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            icon: "mdi-chevron-right",
            disabled: page.value >= pageCount.value,
            onClick: _cache[15] || (_cache[15] = ($event) => page.value = Math.min(pageCount.value, page.value + 1))
          }, null, 8, ["disabled"])
        ])) : _createCommentVNode("", true)
      ]);
    };
  }
});

const AppPage = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-7038df51"]]);

export { AppPage as default };
