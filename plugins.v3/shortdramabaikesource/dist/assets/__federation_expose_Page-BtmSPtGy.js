import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config, { p as proxyImage, r as resolveApi, f as fetchStatus, a as fetchConfig, s as saveConfig, l as lookupKeyword, b as recognizeTitle, c as fetchActor, _ as _export_sfc } from './__federation_expose_Config-Cyya1UBK.js';

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,withKeys:_withKeys,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,unref:_unref,normalizeClass:_normalizeClass} = await importShared('vue');

const _hoisted_1 = {
  class: "d-flex align-center mb-3 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_2 = {
  class: "d-flex align-center mt-2 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_3 = {
  key: 0,
  class: "text-caption sdbs-dim"
};
const _hoisted_4 = { class: "d-flex align-center mb-2" };
const _hoisted_5 = { class: "text-caption sdbs-dim mb-1" };
const _hoisted_6 = { class: "text-body-2 flex-grow-1" };
const _hoisted_7 = {
  key: 0,
  class: "text-caption sdbs-dim mr-2"
};
const _hoisted_8 = {
  class: "d-flex",
  style: { "gap": "12px" }
};
const _hoisted_9 = {
  class: "flex-grow-1",
  style: { "min-width": "0" }
};
const _hoisted_10 = { class: "text-subtitle-2" };
const _hoisted_11 = { class: "text-caption sdbs-dim mt-1" };
const _hoisted_12 = {
  key: 0,
  class: "mt-1"
};
const _hoisted_13 = {
  key: 1,
  class: "text-caption mt-2 sdbs-clamp"
};
const _hoisted_14 = {
  key: 2,
  class: "text-caption sdbs-dim mt-2"
};
const _hoisted_15 = {
  class: "d-flex align-center mt-2 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_16 = {
  key: 0,
  class: "sdbs-pre mt-2"
};
const _hoisted_17 = { class: "d-flex align-center mb-2" };
const _hoisted_18 = { class: "text-caption sdbs-dim mb-1" };
const _hoisted_19 = { class: "text-body-2 flex-grow-1" };
const _hoisted_20 = { class: "text-caption sdbs-dim mr-2" };
const _hoisted_21 = {
  key: 1,
  class: "mt-3"
};
const _hoisted_22 = {
  class: "d-flex",
  style: { "gap": "12px" }
};
const _hoisted_23 = {
  class: "flex-grow-1",
  style: { "min-width": "0" }
};
const _hoisted_24 = { class: "text-subtitle-2" };
const _hoisted_25 = { class: "text-caption sdbs-dim ml-2" };
const _hoisted_26 = { class: "text-caption sdbs-dim mt-1" };
const _hoisted_27 = {
  key: 0,
  class: "text-caption mt-2 sdbs-clamp"
};
const _hoisted_28 = {
  key: 0,
  class: "mt-2"
};
const _hoisted_29 = {
  class: "d-flex align-center mt-2 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_30 = {
  key: 1,
  class: "sdbs-pre mt-2"
};
const _hoisted_31 = { class: "text-subtitle-2 mt-3 mb-2" };
const _hoisted_32 = { class: "text-caption sdbs-dim ml-1" };
const _hoisted_33 = {
  class: "d-flex",
  style: { "gap": "8px" }
};
const _hoisted_34 = {
  class: "flex-grow-1",
  style: { "min-width": "0" }
};
const _hoisted_35 = { class: "text-body-2 sdbs-work-title" };
const _hoisted_36 = { class: "text-caption sdbs-dim mt-1" };
const _hoisted_37 = {
  key: 0,
  class: "mt-1"
};
const _hoisted_38 = { class: "d-flex align-center mt-1" };
const _hoisted_39 = {
  key: 0,
  class: "sdbs-pre mt-1"
};
const {computed,ref} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "Page",
  props: {
    api: {},
    config: {},
    pluginId: {},
    navKey: {},
    full: { type: Boolean }
  },
  emits: ["action", "close"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const enabled = ref(Boolean(props.config?.enabled));
    const toggling = ref(false);
    const loading = ref(false);
    const configLoading = ref(false);
    const settingsOpen = ref(false);
    const remoteConfig = ref({});
    const status = ref(null);
    const keyword = ref("");
    const searching = ref(false);
    const hint = ref("");
    const titleCandidates = ref([]);
    const titleRecord = ref(null);
    const titleMessage = ref("");
    const titleRawOpen = ref(false);
    const titleLoadingId = ref("");
    const actorCandidates = ref([]);
    const actorProfile = ref(null);
    const actorMessage = ref("");
    const actorRawOpen = ref(false);
    const actorLoadingId = ref("");
    const openWorks = ref(/* @__PURE__ */ new Set());
    const pretty = (value) => JSON.stringify(value ?? null, null, 2);
    const cacheChip = computed(() => {
      const cache = status.value?.cache;
      if (!cache) return "";
      return `详情 ${cache.detail ?? 0} ｜ 演员 ${cache.actor ?? 0}`;
    });
    const titleMeta = computed(() => {
      const record = titleRecord.value;
      if (!record) return "";
      const parts = [];
      if (record.year) parts.push(record.year);
      if (record.episode_count) parts.push(`共 ${record.episode_count} 集`);
      if (record.duration_minutes) parts.push(`单集 ${record.duration_minutes} 分钟`);
      if (record.kind) parts.push(record.kind);
      if (record.rating) parts.push(`评分 ${record.rating}`);
      parts.push(`来源 ${record.origin === "detail" ? "详情页" : "检索结果"}`);
      return parts.join(" ｜ ");
    });
    const titleCast = computed(() => {
      const actors = titleRecord.value?.actors || [];
      if (!actors.length) return "";
      return actors.slice(0, 10).map((actor) => actor.character ? `${actor.name}（饰 ${actor.character}）` : actor.name).join("、");
    });
    const actorMeta = computed(() => {
      const actor = actorProfile.value;
      if (!actor) return "";
      const parts = [];
      if (actor.job_title) parts.push(actor.job_title);
      if (actor.gender) parts.push(`性别 ${actor.gender}`);
      if (actor.nationality) parts.push(actor.nationality);
      parts.push(`作品 ${actor.works_count ?? (actor.works || []).length} 部`);
      return parts.join(" ｜ ");
    });
    const hasTitlePanel = computed(
      () => Boolean(titleCandidates.value.length || titleRecord.value || titleMessage.value)
    );
    const hasActorPanel = computed(
      () => Boolean(actorCandidates.value.length || actorProfile.value || actorMessage.value)
    );
    const hasResult = computed(() => hasTitlePanel.value || hasActorPanel.value);
    function workMeta(work) {
      const parts = [];
      if (work.kind) parts.push(work.kind);
      if (work.episode_count) parts.push(`${work.episode_count} 集`);
      if (work.rating) parts.push(`评分 ${work.rating}`);
      if (work.heat) parts.push(`热度 ${Math.round(work.heat / 1e4)} 万`);
      return parts.join(" ｜ ") || "—";
    }
    async function load() {
      const api = resolveApi(props);
      if (!api) return;
      loading.value = true;
      try {
        const payload = await fetchStatus(api);
        if (payload) {
          status.value = payload;
          enabled.value = Boolean(payload.enabled);
        }
      } finally {
        loading.value = false;
      }
    }
    async function toggleEnabled(value) {
      const api = resolveApi(props);
      if (!api) return;
      toggling.value = true;
      try {
        const current = await fetchConfig(api);
        const merged = { ...current?.config || remoteConfig.value };
        merged.enabled = Boolean(value);
        const report = await saveConfig(api, merged);
        if (!report?.success) {
          enabled.value = !value;
          titleMessage.value = report?.message || "切换启用状态失败";
          return;
        }
        remoteConfig.value = report.config || merged;
        await load();
      } finally {
        toggling.value = false;
      }
    }
    async function doLookup() {
      const api = resolveApi(props);
      const query = keyword.value.trim();
      if (!api || !query) return;
      searching.value = true;
      hint.value = "";
      resetTitle();
      resetActor();
      try {
        const report = await lookupKeyword(api, query);
        const titles = report?.titles || [];
        const actors = report?.actors || [];
        titleCandidates.value = titles;
        actorCandidates.value = actors;
        if (!titles.length && !actors.length) {
          hint.value = report?.message || `没搜到「${query}」。`;
          return;
        }
        const parts = [];
        if (titles.length) parts.push(`作品 ${titles.length} 条候选`);
        if (actors.length) parts.push(`演员 ${actors.length} 位候选`);
        hint.value = parts.join(" ｜ ");
        if (titles.length === 1) await pickTitle(titles[0]);
        if (actors.length === 1) await pickActor(actors[0]);
      } finally {
        searching.value = false;
      }
    }
    async function pickTitle(candidate) {
      const api = resolveApi(props);
      if (!api || !candidate.media_id) return;
      titleLoadingId.value = candidate.media_id;
      titleMessage.value = "";
      titleRawOpen.value = false;
      try {
        const report = await recognizeTitle(api, { media_id: candidate.media_id });
        if (report?.success && report.record) {
          titleRecord.value = report.record;
        } else {
          titleMessage.value = report?.message || "取详情失败（多半是站点风控，稍后再试）";
        }
      } finally {
        titleLoadingId.value = "";
      }
    }
    function resetTitle() {
      titleCandidates.value = [];
      titleRecord.value = null;
      titleMessage.value = "";
      titleRawOpen.value = false;
      titleLoadingId.value = "";
    }
    function resetActor() {
      actorCandidates.value = [];
      actorProfile.value = null;
      actorMessage.value = "";
      actorRawOpen.value = false;
      actorLoadingId.value = "";
      openWorks.value = /* @__PURE__ */ new Set();
    }
    async function pickActor(candidate) {
      const api = resolveApi(props);
      if (!api || !candidate.actor_id) return;
      actorLoadingId.value = candidate.actor_id;
      actorMessage.value = "";
      actorRawOpen.value = false;
      openWorks.value = /* @__PURE__ */ new Set();
      try {
        const report = await fetchActor(api, { actor_id: candidate.actor_id });
        if (report?.success && report.actor) {
          actorProfile.value = report.actor;
        } else {
          actorMessage.value = report?.message || "拉演员页失败（多半是站点风控，稍后再试）";
        }
      } finally {
        actorLoadingId.value = "";
      }
    }
    function clearAll() {
      keyword.value = "";
      hint.value = "";
      resetTitle();
      resetActor();
    }
    function toggleWorkRaw(index) {
      const next = new Set(openWorks.value);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      openWorks.value = next;
    }
    async function openSettings() {
      const api = resolveApi(props);
      configLoading.value = true;
      try {
        if (api) {
          const report = await fetchConfig(api);
          if (report?.config) remoteConfig.value = report.config;
        }
      } finally {
        configLoading.value = false;
      }
      settingsOpen.value = true;
    }
    async function onConfigSaved(config) {
      if (config) remoteConfig.value = config;
      settingsOpen.value = false;
      await load();
    }
    load();
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_progress_circular = _resolveComponent("v-progress-circular");
      const _component_v_img = _resolveComponent("v-img");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_avatar = _resolveComponent("v-avatar");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_dialog = _resolveComponent("v-dialog");
      return _openBlock(), _createElementBlock("div", {
        class: _normalizeClass(["sdbs-root", props.full ? "pa-4" : "pa-2"])
      }, [
        _createElementVNode("div", _hoisted_1, [
          _createVNode(_component_v_icon, {
            icon: "mdi-television-classic",
            class: "mr-1"
          }),
          _cache[9] || (_cache[9] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "短剧百科数据源", -1)),
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
          cacheChip.value ? (_openBlock(), _createBlock(_component_v_chip, {
            key: 0,
            size: "small",
            variant: "tonal",
            color: "secondary",
            title: "内存里已缓存的作品详情与演员档案数量（插件重启后重新累积）"
          }, {
            default: _withCtx(() => [
              _createTextVNode(" 缓存 " + _toDisplayString(cacheChip.value), 1)
            ]),
            _: 1
          })) : _createCommentVNode("", true),
          _createVNode(_component_v_spacer),
          props.full ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 1,
            size: "small",
            variant: "text",
            icon: "mdi-close",
            title: "关闭",
            onClick: _cache[0] || (_cache[0] = ($event) => emit("close"))
          })) : _createCommentVNode("", true),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            "prepend-icon": "mdi-cog-outline",
            loading: configLoading.value,
            title: "打开配置：站点域名 / 站外索引 / 缓存 / 详情页摘要",
            onClick: openSettings
          }, {
            default: _withCtx(() => [..._cache[8] || (_cache[8] = [
              _createTextVNode(" 设置 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"]),
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
            class: "sdbs-switch"
          }, null, 8, ["modelValue", "loading", "label"]),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            icon: "mdi-refresh",
            title: "刷新本页状态",
            loading: loading.value,
            onClick: _cache[2] || (_cache[2] = ($event) => load())
          }, null, 8, ["loading"])
        ]),
        _createVNode(_component_v_alert, {
          type: "info",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [..._cache[10] || (_cache[10] = [
            _createTextVNode(" 短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器建不起媒体身份 —— 本插件补的就是这一段。 搜索框", -1),
            _createElementVNode("b", null, "片名与演员名都收", -1),
            _createTextVNode("：一次检索同时给出「作品」与「演员」两块结果，哪边命中就显示哪边 （两边都命中就并排显示）。卡片上的「原始数据」可以直接看到插件处理后的完整字段。 ", -1)
          ])]),
          _: 1
        }),
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-3 sdbs-panel"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_text_field, {
              modelValue: keyword.value,
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => keyword.value = $event),
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              clearable: "",
              "prepend-inner-icon": "mdi-magnify",
              placeholder: "输入短剧片名或演员姓名，例如：女足替补的滚烫夏天 / 魏依珂",
              onKeyup: _withKeys(doLookup, ["enter"])
            }, null, 8, ["modelValue"]),
            _createElementVNode("div", _hoisted_2, [
              _createVNode(_component_v_btn, {
                size: "small",
                color: "primary",
                variant: "tonal",
                loading: searching.value,
                disabled: !keyword.value.trim(),
                onClick: doLookup
              }, {
                default: _withCtx(() => [..._cache[11] || (_cache[11] = [
                  _createTextVNode(" 搜索 ", -1)
                ])]),
                _: 1
              }, 8, ["loading", "disabled"]),
              _createVNode(_component_v_btn, {
                size: "small",
                variant: "text",
                disabled: !hasResult.value,
                onClick: clearAll
              }, {
                default: _withCtx(() => [..._cache[12] || (_cache[12] = [
                  _createTextVNode("清空", -1)
                ])]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode(_component_v_spacer),
              hint.value ? (_openBlock(), _createElementBlock("span", _hoisted_3, _toDisplayString(hint.value), 1)) : _createCommentVNode("", true)
            ])
          ]),
          _: 1
        }),
        _createVNode(_component_v_row, { dense: "" }, {
          default: _withCtx(() => [
            hasTitlePanel.value ? (_openBlock(), _createBlock(_component_v_col, {
              key: 0,
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "outlined",
                  class: "pa-3 sdbs-panel"
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_4, [
                      _createVNode(_component_v_icon, {
                        icon: "mdi-movie-search-outline",
                        size: "18",
                        class: "mr-1"
                      }),
                      _cache[13] || (_cache[13] = _createElementVNode("span", { class: "text-subtitle-2" }, "作品", -1)),
                      _createVNode(_component_v_spacer),
                      titleLoadingId.value ? (_openBlock(), _createBlock(_component_v_progress_circular, {
                        key: 0,
                        size: "16",
                        width: "2",
                        indeterminate: ""
                      })) : _createCommentVNode("", true)
                    ]),
                    titleCandidates.value.length ? (_openBlock(), _createBlock(_component_v_card, {
                      key: 0,
                      variant: "tonal",
                      class: "pa-2 mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_5, " 命中 " + _toDisplayString(titleCandidates.value.length) + " 条候选，点「识别」看完整详情（按匹配分排序）： ", 1),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(titleCandidates.value, (candidate) => {
                          return _openBlock(), _createElementBlock("div", {
                            key: candidate.media_id || candidate.title,
                            class: "d-flex align-center py-1"
                          }, [
                            _createVNode(_component_v_chip, {
                              size: "x-small",
                              variant: "tonal",
                              class: "mr-2",
                              title: `匹配分 ${candidate.score}`
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(candidate.score), 1)
                              ]),
                              _: 2
                            }, 1032, ["title"]),
                            _createElementVNode("span", _hoisted_6, _toDisplayString(candidate.title), 1),
                            candidate.episode_count ? (_openBlock(), _createElementBlock("span", _hoisted_7, _toDisplayString(candidate.episode_count) + " 集 ", 1)) : _createCommentVNode("", true),
                            _createVNode(_component_v_btn, {
                              size: "x-small",
                              variant: "tonal",
                              color: "primary",
                              loading: titleLoadingId.value === candidate.media_id,
                              onClick: ($event) => pickTitle(candidate)
                            }, {
                              default: _withCtx(() => [..._cache[14] || (_cache[14] = [
                                _createTextVNode(" 识别 ", -1)
                              ])]),
                              _: 1
                            }, 8, ["loading", "onClick"])
                          ]);
                        }), 128))
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true),
                    titleRecord.value ? (_openBlock(), _createBlock(_component_v_card, {
                      key: 1,
                      variant: "outlined",
                      class: "pa-3 mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_8, [
                          _createVNode(_component_v_img, {
                            src: _unref(proxyImage)(titleRecord.value.poster),
                            width: "92",
                            height: "123",
                            "aspect-ratio": "2/3",
                            cover: "",
                            class: "rounded flex-shrink-0 sdbs-poster"
                          }, null, 8, ["src"]),
                          _createElementVNode("div", _hoisted_9, [
                            _createElementVNode("div", _hoisted_10, _toDisplayString(titleRecord.value.title || "（无标题）"), 1),
                            _createElementVNode("div", _hoisted_11, _toDisplayString(titleMeta.value), 1),
                            titleRecord.value.tags?.length ? (_openBlock(), _createElementBlock("div", _hoisted_12, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(titleRecord.value.tags, (tag) => {
                                return _openBlock(), _createBlock(_component_v_chip, {
                                  key: tag,
                                  size: "x-small",
                                  variant: "tonal",
                                  class: "mr-1 mb-1"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(tag), 1)
                                  ]),
                                  _: 2
                                }, 1024);
                              }), 128))
                            ])) : _createCommentVNode("", true),
                            titleRecord.value.overview ? (_openBlock(), _createElementBlock("div", _hoisted_13, _toDisplayString(titleRecord.value.overview), 1)) : _createCommentVNode("", true),
                            titleCast.value ? (_openBlock(), _createElementBlock("div", _hoisted_14, "主演：" + _toDisplayString(titleCast.value), 1)) : _createCommentVNode("", true)
                          ])
                        ]),
                        _createElementVNode("div", _hoisted_15, [
                          titleRecord.value.url ? (_openBlock(), _createBlock(_component_v_btn, {
                            key: 0,
                            size: "x-small",
                            variant: "tonal",
                            href: titleRecord.value.url,
                            target: "_blank",
                            rel: "noopener",
                            "prepend-icon": "mdi-open-in-new"
                          }, {
                            default: _withCtx(() => [..._cache[15] || (_cache[15] = [
                              _createTextVNode(" 站点页面 ", -1)
                            ])]),
                            _: 1
                          }, 8, ["href"])) : _createCommentVNode("", true),
                          _createVNode(_component_v_btn, {
                            size: "x-small",
                            variant: "text",
                            onClick: _cache[4] || (_cache[4] = ($event) => titleRawOpen.value = !titleRawOpen.value)
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(titleRawOpen.value ? "收起原始数据" : "原始数据"), 1)
                            ]),
                            _: 1
                          })
                        ]),
                        titleRawOpen.value ? (_openBlock(), _createElementBlock("pre", _hoisted_16, _toDisplayString(pretty(titleRecord.value)), 1)) : _createCommentVNode("", true)
                      ]),
                      _: 1
                    })) : titleMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
                      key: 2,
                      type: "warning",
                      variant: "tonal",
                      density: "compact",
                      class: "mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(titleMessage.value), 1)
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })) : _createCommentVNode("", true),
            hasActorPanel.value ? (_openBlock(), _createBlock(_component_v_col, {
              key: 1,
              cols: "12",
              md: "6"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "outlined",
                  class: "pa-3 sdbs-panel"
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_17, [
                      _createVNode(_component_v_icon, {
                        icon: "mdi-account-search-outline",
                        size: "18",
                        class: "mr-1"
                      }),
                      _cache[16] || (_cache[16] = _createElementVNode("span", { class: "text-subtitle-2" }, "演员", -1)),
                      _createVNode(_component_v_spacer),
                      actorLoadingId.value ? (_openBlock(), _createBlock(_component_v_progress_circular, {
                        key: 0,
                        size: "16",
                        width: "2",
                        indeterminate: ""
                      })) : _createCommentVNode("", true)
                    ]),
                    actorCandidates.value.length ? (_openBlock(), _createBlock(_component_v_card, {
                      key: 0,
                      variant: "tonal",
                      class: "pa-2 mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("div", _hoisted_18, " 命中 " + _toDisplayString(actorCandidates.value.length) + " 位，点「看作品」拉取档案与全部作品： ", 1),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorCandidates.value, (candidate) => {
                          return _openBlock(), _createElementBlock("div", {
                            key: candidate.actor_id || candidate.name,
                            class: "d-flex align-center py-1"
                          }, [
                            _createVNode(_component_v_chip, {
                              size: "x-small",
                              variant: "tonal",
                              class: "mr-2",
                              title: `匹配分 ${candidate.score}`
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(candidate.score), 1)
                              ]),
                              _: 2
                            }, 1032, ["title"]),
                            _createElementVNode("span", _hoisted_19, _toDisplayString(candidate.name), 1),
                            _createElementVNode("span", _hoisted_20, "actor:" + _toDisplayString(candidate.actor_id), 1),
                            _createVNode(_component_v_btn, {
                              size: "x-small",
                              variant: "tonal",
                              color: "primary",
                              loading: actorLoadingId.value === candidate.actor_id,
                              onClick: ($event) => pickActor(candidate)
                            }, {
                              default: _withCtx(() => [..._cache[17] || (_cache[17] = [
                                _createTextVNode(" 看作品 ", -1)
                              ])]),
                              _: 1
                            }, 8, ["loading", "onClick"])
                          ]);
                        }), 128))
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true),
                    actorProfile.value ? (_openBlock(), _createElementBlock("div", _hoisted_21, [
                      _createVNode(_component_v_card, {
                        variant: "outlined",
                        class: "pa-3"
                      }, {
                        default: _withCtx(() => [
                          _createElementVNode("div", _hoisted_22, [
                            _createVNode(_component_v_avatar, {
                              size: "64",
                              rounded: "",
                              class: "flex-shrink-0"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_v_img, {
                                  src: _unref(proxyImage)(actorProfile.value.profile),
                                  cover: ""
                                }, null, 8, ["src"])
                              ]),
                              _: 1
                            }),
                            _createElementVNode("div", _hoisted_23, [
                              _createElementVNode("div", _hoisted_24, [
                                _createTextVNode(_toDisplayString(actorProfile.value.name || "（无姓名）") + " ", 1),
                                _createElementVNode("span", _hoisted_25, "actor:" + _toDisplayString(actorProfile.value.actor_id), 1)
                              ]),
                              _createElementVNode("div", _hoisted_26, _toDisplayString(actorMeta.value), 1),
                              actorProfile.value.bio ? (_openBlock(), _createElementBlock("div", _hoisted_27, _toDisplayString(actorProfile.value.bio), 1)) : _createCommentVNode("", true)
                            ])
                          ]),
                          actorProfile.value.coactors?.length ? (_openBlock(), _createElementBlock("div", _hoisted_28, [
                            _cache[18] || (_cache[18] = _createElementVNode("span", { class: "text-caption sdbs-dim mr-1" }, "常合作演员：", -1)),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorProfile.value.coactors.slice(0, 12), (co) => {
                              return _openBlock(), _createBlock(_component_v_chip, {
                                key: co.id || co.name,
                                size: "x-small",
                                variant: "tonal",
                                class: "mr-1 mb-1"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(co.name), 1)
                                ]),
                                _: 2
                              }, 1024);
                            }), 128))
                          ])) : _createCommentVNode("", true),
                          _createElementVNode("div", _hoisted_29, [
                            actorProfile.value.url ? (_openBlock(), _createBlock(_component_v_btn, {
                              key: 0,
                              size: "x-small",
                              variant: "tonal",
                              href: actorProfile.value.url,
                              target: "_blank",
                              rel: "noopener",
                              "prepend-icon": "mdi-open-in-new"
                            }, {
                              default: _withCtx(() => [..._cache[19] || (_cache[19] = [
                                _createTextVNode(" 演员页 ", -1)
                              ])]),
                              _: 1
                            }, 8, ["href"])) : _createCommentVNode("", true),
                            _createVNode(_component_v_btn, {
                              size: "x-small",
                              variant: "text",
                              onClick: _cache[5] || (_cache[5] = ($event) => actorRawOpen.value = !actorRawOpen.value)
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(actorRawOpen.value ? "收起原始数据" : "原始数据"), 1)
                              ]),
                              _: 1
                            })
                          ]),
                          actorRawOpen.value ? (_openBlock(), _createElementBlock("pre", _hoisted_30, _toDisplayString(pretty(actorProfile.value)), 1)) : _createCommentVNode("", true)
                        ]),
                        _: 1
                      }),
                      _createElementVNode("div", _hoisted_31, [
                        _createVNode(_component_v_icon, {
                          icon: "mdi-movie-open-outline",
                          size: "18",
                          class: "mr-1"
                        }),
                        _cache[20] || (_cache[20] = _createTextVNode(" 全部作品 ", -1)),
                        _createElementVNode("span", _hoisted_32, "共 " + _toDisplayString(actorProfile.value.works?.length || 0) + " 部", 1)
                      ]),
                      _createVNode(_component_v_row, { dense: "" }, {
                        default: _withCtx(() => [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorProfile.value.works || [], (work, index) => {
                            return _openBlock(), _createBlock(_component_v_col, {
                              key: work.media_id || index,
                              cols: "12",
                              sm: "6"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_v_card, {
                                  variant: "outlined",
                                  class: "pa-2 h-100 d-flex flex-column"
                                }, {
                                  default: _withCtx(() => [
                                    _createElementVNode("div", _hoisted_33, [
                                      _createVNode(_component_v_img, {
                                        src: _unref(proxyImage)(work.poster),
                                        width: "60",
                                        height: "80",
                                        "aspect-ratio": "2/3",
                                        cover: "",
                                        class: "rounded flex-shrink-0 sdbs-poster"
                                      }, null, 8, ["src"]),
                                      _createElementVNode("div", _hoisted_34, [
                                        _createElementVNode("div", _hoisted_35, _toDisplayString(work.title || "（无标题）"), 1),
                                        _createElementVNode("div", _hoisted_36, _toDisplayString(workMeta(work)), 1),
                                        work.tags?.length ? (_openBlock(), _createElementBlock("div", _hoisted_37, [
                                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(work.tags.slice(0, 3), (tag) => {
                                            return _openBlock(), _createBlock(_component_v_chip, {
                                              key: tag,
                                              size: "x-small",
                                              variant: "tonal",
                                              class: "mr-1 mb-1"
                                            }, {
                                              default: _withCtx(() => [
                                                _createTextVNode(_toDisplayString(tag), 1)
                                              ]),
                                              _: 2
                                            }, 1024);
                                          }), 128))
                                        ])) : _createCommentVNode("", true)
                                      ])
                                    ]),
                                    _createVNode(_component_v_spacer),
                                    _createElementVNode("div", _hoisted_38, [
                                      work.url ? (_openBlock(), _createBlock(_component_v_btn, {
                                        key: 0,
                                        size: "x-small",
                                        variant: "text",
                                        href: work.url,
                                        target: "_blank",
                                        rel: "noopener"
                                      }, {
                                        default: _withCtx(() => [..._cache[21] || (_cache[21] = [
                                          _createTextVNode(" 站点 ", -1)
                                        ])]),
                                        _: 1
                                      }, 8, ["href"])) : _createCommentVNode("", true),
                                      _createVNode(_component_v_spacer),
                                      _createVNode(_component_v_btn, {
                                        size: "x-small",
                                        variant: "text",
                                        onClick: ($event) => toggleWorkRaw(index)
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(openWorks.value.has(index) ? "收起" : "原始数据"), 1)
                                        ]),
                                        _: 2
                                      }, 1032, ["onClick"])
                                    ]),
                                    openWorks.value.has(index) ? (_openBlock(), _createElementBlock("pre", _hoisted_39, _toDisplayString(pretty(work)), 1)) : _createCommentVNode("", true)
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _: 2
                            }, 1024);
                          }), 128))
                        ]),
                        _: 1
                      })
                    ])) : actorMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
                      key: 2,
                      type: "warning",
                      variant: "tonal",
                      density: "compact",
                      class: "mt-3"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(actorMessage.value), 1)
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })) : _createCommentVNode("", true)
          ]),
          _: 1
        }),
        _createVNode(_component_v_dialog, {
          modelValue: settingsOpen.value,
          "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => settingsOpen.value = $event),
          "max-width": "1080",
          scrollable: ""
        }, {
          default: _withCtx(() => [
            settingsOpen.value ? (_openBlock(), _createBlock(Config, {
              key: 0,
              api: props.api,
              "initial-config": remoteConfig.value,
              onClose: _cache[6] || (_cache[6] = ($event) => settingsOpen.value = false),
              onSave: onConfigSaved
            }, null, 8, ["api", "initial-config"])) : _createCommentVNode("", true)
          ]),
          _: 1
        }, 8, ["modelValue"])
      ], 2);
    };
  }
});

const Page = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-41719cfb"]]);

export { Page as default };
