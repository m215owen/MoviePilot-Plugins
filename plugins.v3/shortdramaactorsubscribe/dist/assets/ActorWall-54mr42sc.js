import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { p as proxyImage, _ as _export_sfc, c as addActor, r as removeActor, d as fetchActorWorks, e as searchActor, g as searchWorks, h as fetchSubscribedIds, i as submitSubscribe, m as mediaPageUrl, j as fetchConfig, k as resourceSearchUrl, l as fetchWorks } from './_plugin-vue_export-helper-yf5egOZA.js';

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {unref:_unref$1,createElementVNode:_createElementVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,createVNode:_createVNode$1,createElementBlock:_createElementBlock$1,createTextVNode:_createTextVNode$1,vShow:_vShow,withDirectives:_withDirectives,toDisplayString:_toDisplayString$1,withModifiers:_withModifiers$1,normalizeClass:_normalizeClass$1,mergeProps:_mergeProps$1} = await importShared('vue');

const _hoisted_1$1 = {
  key: 1,
  class: "sdas-poster-empty d-flex align-center justify-center"
};
const _hoisted_2$1 = { class: "absolute top-0 right-0 p-2" };
const _hoisted_3$1 = {
  key: 0,
  class: "pointer-events-none z-40 flex items-center",
  title: "这部作品已在 MoviePilot 媒体库中（与媒体详情页的判定一致）"
};
const _hoisted_4$1 = { class: "font-semibold text-sm" };
const _hoisted_5$1 = { class: "sdas-card-title font-bold mb-2 text-white line-clamp-2 overflow-hidden text-ellipsis" };
const _hoisted_6$1 = { class: "sdas-card-overview line-clamp-3 overflow-hidden text-ellipsis" };
const _hoisted_7$1 = { class: "flex align-center justify-between" };
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "WorkCard",
  props: {
    work: {},
    loaded: { type: Boolean },
    subscribed: { type: Boolean }
  },
  emits: ["poster", "open", "search", "subscribe"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const OVERLAY_STYLE = {
      background: "linear-gradient(rgba(45, 55, 72, 40%) 0%, rgba(45, 55, 72, 90%) 100%)"
    };
    function cardSummary(work) {
      const parts = [];
      if (work.actor) parts.push(work.actor);
      if (work.episode_count) parts.push(`${work.episode_count} 集`);
      const genres = (work.genres || []).slice(0, 3);
      if (genres.length) parts.push(genres.join(" / "));
      if (!parts.length && work.release_date) parts.push(work.release_date);
      return parts.join(" · ") || props.work.overview || "—";
    }
    return (_ctx, _cache) => {
      const _component_v_img = _resolveComponent$1("v-img");
      const _component_v_icon = _resolveComponent$1("v-icon");
      const _component_v_chip = _resolveComponent$1("v-chip");
      const _component_v_avatar = _resolveComponent$1("v-avatar");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_spacer = _resolveComponent$1("v-spacer");
      const _component_v_card = _resolveComponent$1("v-card");
      const _component_v_hover = _resolveComponent$1("v-hover");
      return _openBlock$1(), _createBlock$1(_component_v_hover, null, {
        default: _withCtx$1(({ isHovering, props: hoverProps }) => [
          _createElementVNode$1("div", _mergeProps$1(hoverProps, { class: "sdas-hover-area" }), [
            _createVNode$1(_component_v_card, {
              ripple: false,
              class: _normalizeClass$1(["app-hover-lift-card outline-none ring-gray-500 media-card sdas-card", {
                "app-hover-lift-card--hovering": isHovering,
                "ring-1": __props.loaded
              }]),
              onClick: _cache[4] || (_cache[4] = ($event) => emit("open", __props.work))
            }, {
              default: _withCtx$1(() => [
                __props.work.poster ? (_openBlock$1(), _createBlock$1(_component_v_img, {
                  key: 0,
                  src: _unref$1(proxyImage)(__props.work.poster),
                  "aspect-ratio": 2 / 3,
                  cover: "",
                  class: "object-cover aspect-w-2 aspect-h-3",
                  onLoad: _cache[0] || (_cache[0] = ($event) => emit("poster", __props.work.key)),
                  onError: _cache[1] || (_cache[1] = ($event) => emit("poster", __props.work.key))
                }, {
                  placeholder: _withCtx$1(() => [..._cache[5] || (_cache[5] = [
                    _createElementVNode$1("div", { class: "sdas-poster-skeleton" }, null, -1)
                  ])]),
                  _: 1
                }, 8, ["src"])) : (_openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
                  _createVNode$1(_component_v_icon, {
                    icon: "mdi-movie-open-outline",
                    size: "56",
                    color: "medium-emphasis"
                  })
                ])),
                _withDirectives(_createVNode$1(_component_v_chip, {
                  variant: "elevated",
                  size: "small",
                  class: "absolute left-2 top-2 bg-opacity-80 text-white font-bold border-purple-600 bg-purple-600"
                }, {
                  default: _withCtx$1(() => [..._cache[6] || (_cache[6] = [
                    _createTextVNode$1(" 短剧 ", -1)
                  ])]),
                  _: 1
                }, 512), [
                  [_vShow, __props.loaded]
                ]),
                _withDirectives(_createElementVNode$1("div", _hoisted_2$1, [
                  __props.work.in_library === true && !isHovering ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_3$1, [..._cache[7] || (_cache[7] = [
                    _createElementVNode$1("div", { class: "relative inline-flex whitespace-nowrap rounded-full border-gray-700 font-semibold leading-5 ring-gray-700" }, [
                      _createElementVNode$1("div", { class: "rounded-full bg-opacity-80 w-5 border p-0 bg-green-500 border-green-400 ring-green-400 text-green-100" }, [
                        _createElementVNode$1("svg", {
                          xmlns: "http://www.w3.org/2000/svg",
                          viewBox: "0 0 20 20",
                          fill: "currentColor",
                          "aria-hidden": "true"
                        }, [
                          _createElementVNode$1("path", {
                            "fill-rule": "evenodd",
                            d: "M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z",
                            "clip-rule": "evenodd"
                          })
                        ])
                      ])
                    ], -1)
                  ])])) : Number(__props.work.vote) > 0 ? (_openBlock$1(), _createBlock$1(_component_v_chip, {
                    key: 1,
                    variant: "elevated",
                    size: "small",
                    class: "bg-opacity-80 text-white font-bold border-purple-600 bg-purple-600"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(Number(__props.work.vote).toFixed(1)), 1)
                    ]),
                    _: 1
                  })) : _createCommentVNode$1("", true)
                ], 512), [
                  [_vShow, __props.loaded]
                ]),
                !isHovering ? _withDirectives((_openBlock$1(), _createBlock$1(_component_v_avatar, {
                  key: 2,
                  size: "24",
                  variant: "plain",
                  density: "compact",
                  tile: "",
                  class: "absolute bottom-1 right-1"
                }, {
                  default: _withCtx$1(() => [
                    _createVNode$1(_component_v_img, {
                      cover: "",
                      src: "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/ShortDramaBaikeSource.png",
                      class: "shadow-lg"
                    })
                  ]),
                  _: 1
                }, 512)), [
                  [_vShow, __props.loaded]
                ]) : _createCommentVNode$1("", true),
                isHovering ? (_openBlock$1(), _createElementBlock$1("div", {
                  key: 3,
                  class: "w-full h-full flex flex-col flex-wrap justify-end align-left text-white absolute bottom-0 cursor-pointer pa-2",
                  style: OVERLAY_STYLE
                }, [
                  _createElementVNode$1("span", _hoisted_4$1, _toDisplayString$1(__props.work.year || "—"), 1),
                  _createElementVNode$1("h1", _hoisted_5$1, _toDisplayString$1(__props.work.title), 1),
                  _createElementVNode$1("p", _hoisted_6$1, _toDisplayString$1(cardSummary(__props.work)), 1),
                  _createElementVNode$1("div", _hoisted_7$1, [
                    _createVNode$1(_component_v_btn, {
                      icon: "",
                      variant: "text",
                      size: "small",
                      title: "搜索资源",
                      onClick: _cache[2] || (_cache[2] = _withModifiers$1(($event) => emit("search", __props.work), ["stop"]))
                    }, {
                      default: _withCtx$1(() => [
                        _createVNode$1(_component_v_icon, {
                          size: "24",
                          color: "white"
                        }, {
                          default: _withCtx$1(() => [..._cache[8] || (_cache[8] = [
                            _createTextVNode$1("mdi-magnify", -1)
                          ])]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode$1(_component_v_spacer),
                    _createVNode$1(_component_v_btn, {
                      icon: "",
                      variant: "text",
                      size: "small",
                      color: __props.subscribed ? "error" : "white",
                      title: __props.subscribed ? "已订阅" : "加入订阅",
                      onClick: _cache[3] || (_cache[3] = _withModifiers$1(($event) => emit("subscribe", __props.work), ["stop"]))
                    }, {
                      default: _withCtx$1(() => [
                        _createVNode$1(_component_v_icon, {
                          size: "24",
                          color: __props.subscribed ? "error" : "white"
                        }, {
                          default: _withCtx$1(() => [
                            _createTextVNode$1(_toDisplayString$1(__props.subscribed ? "mdi-heart" : "mdi-heart-outline"), 1)
                          ]),
                          _: 1
                        }, 8, ["color"])
                      ]),
                      _: 1
                    }, 8, ["color", "title"])
                  ])
                ])) : _createCommentVNode$1("", true)
              ]),
              _: 2
            }, 1032, ["class"])
          ], 16)
        ]),
        _: 1
      });
    };
  }
});

const WorkCard = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-6ee01f0f"]]);

const {defineComponent:_defineComponent} = await importShared('vue');

const {createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,toDisplayString:_toDisplayString,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,renderList:_renderList,createBlock:_createBlock,normalizeClass:_normalizeClass,unref:_unref,withModifiers:_withModifiers,mergeProps:_mergeProps,normalizeStyle:_normalizeStyle,Transition:_Transition} = await importShared('vue');

const _hoisted_1 = { class: "sdas-head" };
const _hoisted_2 = { class: "sdas-sub" };
const _hoisted_3 = { class: "sdas-new-dot" };
const _hoisted_4 = { class: "px-3 sdas-filters" };
const _hoisted_5 = {
  key: 0,
  class: "flex justify-start align-center"
};
const _hoisted_6 = { class: "mr-5 sdas-row-label" };
const _hoisted_7 = { class: "sdas-chip-count" };
const _hoisted_8 = {
  key: 1,
  class: "flex justify-start align-center"
};
const _hoisted_9 = { class: "mr-5 sdas-row-label" };
const _hoisted_10 = { class: "sdas-chip-count" };
const _hoisted_11 = { class: "flex justify-start align-center" };
const _hoisted_12 = { class: "mr-5 sdas-row-label" };
const _hoisted_13 = { class: "sdas-chip-count" };
const _hoisted_14 = {
  key: 0,
  class: "sdas-chip-dot",
  title: "暂时没取到作品，会自动重试"
};
const _hoisted_15 = {
  key: 2,
  class: "flex justify-start align-center"
};
const _hoisted_16 = { class: "mr-5 sdas-row-label" };
const _hoisted_17 = { class: "sdas-chip-count" };
const _hoisted_18 = { class: "flex justify-start align-center" };
const _hoisted_19 = { class: "mr-5 sdas-row-label" };
const _hoisted_20 = {
  key: 3,
  class: "flex justify-start align-center"
};
const _hoisted_21 = { class: "mr-5 sdas-row-label" };
const _hoisted_22 = { class: "flex justify-start align-center" };
const _hoisted_23 = { class: "mr-5 sdas-row-label" };
const _hoisted_24 = {
  key: 0,
  class: "sdas-search-hint text-body-2 text-medium-emphasis ml-3"
};
const _hoisted_25 = {
  key: 0,
  class: "d-flex flex-column align-center ga-2 py-6"
};
const _hoisted_26 = {
  key: 0,
  class: "mb-6"
};
const _hoisted_27 = { class: "text-body-2 text-medium-emphasis mb-2" };
const _hoisted_28 = {
  key: 1,
  class: "sdas-poster-empty d-flex align-center justify-center"
};
const _hoisted_29 = { class: "font-semibold text-sm" };
const _hoisted_30 = { class: "sdas-card-title font-bold mb-2 text-white line-clamp-2 overflow-hidden text-ellipsis" };
const _hoisted_31 = { class: "sdas-card-overview line-clamp-3 overflow-hidden text-ellipsis" };
const _hoisted_32 = { class: "flex align-center justify-between" };
const _hoisted_33 = {
  key: 1,
  class: "sdas-search-miss text-body-2 text-medium-emphasis mb-3"
};
const _hoisted_34 = { key: 2 };
const _hoisted_35 = { class: "text-body-2 text-medium-emphasis mb-2" };
const _hoisted_36 = {
  key: 3,
  class: "sdas-search-miss text-body-2 text-medium-emphasis"
};
const _hoisted_37 = {
  key: 4,
  class: "sdas-empty"
};
const _hoisted_38 = { class: "sdas-empty-title" };
const _hoisted_39 = {
  key: 0,
  class: "px-3 sdas-expanded-bar"
};
const _hoisted_40 = { class: "text-subtitle-1 font-weight-bold" };
const _hoisted_41 = {
  key: 0,
  class: "text-body-2 text-medium-emphasis ml-2"
};
const _hoisted_42 = {
  key: 1,
  class: "d-flex flex-column align-center ga-2 py-6"
};
const _hoisted_43 = {
  key: 2,
  class: "d-flex flex-column align-center ga-2 py-4"
};
const _hoisted_44 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_45 = {
  key: 3,
  class: "sdas-empty"
};
const _hoisted_46 = { class: "sdas-empty-title" };
const _hoisted_47 = {
  key: 4,
  class: "d-flex flex-column align-center ga-2 py-4"
};
const _hoisted_48 = {
  key: 5,
  class: "d-flex flex-column align-center ga-2 py-4"
};
const _hoisted_49 = {
  key: 6,
  class: "sdas-empty"
};
const _hoisted_50 = { class: "sdas-empty-title" };
const _hoisted_51 = { class: "sdas-empty-hint" };
const _hoisted_52 = ["data-progressive-grid-index"];
const _hoisted_53 = { key: 1 };
const {computed,nextTick,onMounted,onUnmounted,ref,watch} = await importShared('vue');
const PAGE_SIZE = 60;
const MIN_ITEM_WIDTH = 144;
const GRID_GAP = 16;
const BATCH_SIZE = 6;
const COLLAPSED_LIMIT = 12;
const LOOKUP_DEBOUNCE = 420;
const FILTER_STORAGE_KEY = "ShortDramaActorSubscribe.filters.v1";
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "ActorWall",
  props: {
    api: {},
    config: {},
    pluginId: {},
    nativeSubscribe: { type: Function },
    full: { type: Boolean }
  },
  setup(__props) {
    const props = __props;
    const OVERLAY_STYLE = {
      background: "linear-gradient(rgba(45, 55, 72, 40%) 0%, rgba(45, 55, 72, 90%) 100%)"
    };
    const works = ref([]);
    const total = ref(0);
    const allTotal = ref(0);
    const newWorks = ref(0);
    const libraryKnown = ref(0);
    const inLibraryCount = ref(0);
    const inLibraryKnown = computed(() => libraryKnown.value > 0);
    const page = ref(1);
    const done = ref(false);
    const error = ref(false);
    const loading = ref(false);
    const loadingMore = ref(false);
    const seenKeys = /* @__PURE__ */ new Set();
    const seenSignatures = /* @__PURE__ */ new Set();
    let epoch = 0;
    const actorFilters = ref([]);
    const facets = ref({ genres: [], years: [], studios: [] });
    const actor = ref("");
    const genre = ref("");
    const year = ref("");
    const studio = ref("");
    const sort = ref("heat");
    const onlyNotInLibrary = ref(false);
    const expandedRows = ref({});
    const actorQuery = ref("");
    const actorResults = ref([]);
    const searchingActors = ref(false);
    const workResults = ref([]);
    const searchingWorks = ref(false);
    const addingActorId = ref("");
    const removingActorId = ref("");
    const expandedActor = ref(null);
    const searchSnapshotQuery = ref("");
    const searchSnapshotResults = ref([]);
    const searchSnapshotWorks = ref([]);
    const expandedWorks = ref([]);
    const expandedLoading = ref(false);
    const expandedError = ref("");
    const subscribed = ref(/* @__PURE__ */ new Set());
    const loadedKeys = ref(/* @__PURE__ */ new Set());
    const tip = ref("");
    const tipType = ref("info");
    let tipTimer = null;
    function toast(text, type = "info") {
      tip.value = text;
      tipType.value = type;
      if (tipTimer) clearTimeout(tipTimer);
      tipTimer = setTimeout(() => tip.value = "", 3200);
    }
    const sortOptions = [
      { title: "发布日期", value: "date" },
      { title: "热度", value: "heat" },
      { title: "播放", value: "play" },
      { title: "评分", value: "rating" }
    ];
    const filteredOut = computed(
      () => Boolean(
        actor.value || genre.value || year.value || studio.value || onlyNotInLibrary.value
      )
    );
    function resetFilters() {
      actor.value = "";
      genre.value = "";
      year.value = "";
      studio.value = "";
      onlyNotInLibrary.value = false;
    }
    let savedPages = 0;
    let savedScroll = 0;
    let lastScrollY = 0;
    function restoreViewState() {
      try {
        const raw = sessionStorage.getItem(FILTER_STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw);
        actor.value = typeof saved.actor === "string" ? saved.actor : "";
        genre.value = typeof saved.genre === "string" ? saved.genre : "";
        year.value = typeof saved.year === "string" ? saved.year : "";
        studio.value = typeof saved.studio === "string" ? saved.studio : "";
        onlyNotInLibrary.value = saved.only_not_in_library === true;
        if (typeof saved.sort === "string" && sortOptions.some((opt) => opt.value === saved.sort)) {
          sort.value = saved.sort;
        }
        savedPages = typeof saved.pages === "number" && saved.pages > 0 ? Math.floor(saved.pages) : 0;
        savedScroll = typeof saved.scroll === "number" && saved.scroll > 0 ? Math.floor(saved.scroll) : 0;
      } catch {
        try {
          sessionStorage.removeItem(FILTER_STORAGE_KEY);
        } catch {
        }
      }
    }
    function persistFilters() {
      writeViewState({ pages: 0, scroll: 0 });
    }
    function writeViewState(view) {
      try {
        sessionStorage.setItem(
          FILTER_STORAGE_KEY,
          JSON.stringify({
            actor: actor.value,
            genre: genre.value,
            year: year.value,
            studio: studio.value,
            sort: sort.value,
            only_not_in_library: onlyNotInLibrary.value,
            ...view
          })
        );
      } catch {
      }
    }
    restoreViewState();
    const searchKeyword = computed(() => String(actorQuery.value || "").trim());
    const searchActive = computed(() => searchKeyword.value.length > 0);
    const searchSummary = computed(() => {
      const parts = [];
      if (actorResults.value.length) parts.push(`${actorResults.value.length} 位演员`);
      if (workResults.value.length) parts.push(`${workResults.value.length} 部作品`);
      return parts.join(" · ");
    });
    function isExpanded(row) {
      return Boolean(expandedRows.value[row]);
    }
    function toggleRow(row) {
      expandedRows.value = { ...expandedRows.value, [row]: !expandedRows.value[row] };
    }
    function pick(value) {
      return typeof value === "string" ? value : "";
    }
    function query() {
      return {
        actor: actor.value,
        genre: genre.value,
        year: year.value,
        studio: studio.value,
        sort: sort.value,
        only_not_in_library: onlyNotInLibrary.value,
        page_size: PAGE_SIZE
      };
    }
    const actorCount = computed(() => actorFilters.value.length);
    const emptyHint = computed(() => {
      const waiting = actorFilters.value.filter((item) => item.state === "waiting");
      const empty = actorFilters.value.filter((item) => item.state === "empty");
      if (!works.value.length && empty.length) {
        return `短剧百科未收录：${empty.map((item) => item.name).join("、")}`;
      }
      if (!works.value.length && waiting.length) {
        return "百科暂时没返回作品，插件会自动重试";
      }
      return "";
    });
    function actorTitle(item) {
      if (item.state === "empty") return "短剧百科未收录该演员";
      if (item.state === "waiting") return "暂时没取到作品，会自动重试";
      return `${item.works} 部作品`;
    }
    function markPosterLoaded(key) {
      loadedKeys.value.add(key);
    }
    function isPosterLoaded(key) {
      if (!key) return true;
      return loadedKeys.value.has(key);
    }
    function actorKey(item) {
      return `actor:${item.actor_id}`;
    }
    function actorMeta(item) {
      const parts = [];
      if (item.works_count) parts.push(`${item.works_count} 部作品`);
      if (item.job_title) parts.push(item.job_title);
      if (item.gender) parts.push(item.gender);
      if (item.nationality) parts.push(item.nationality);
      if (!parts.length) parts.push("短剧演员");
      return parts.join(" · ");
    }
    function isActorAdded(item) {
      if (item.subscribed) return true;
      return actorFilters.value.some((row) => row.name === item.name);
    }
    function openActorPage(item) {
      if (!item.url) {
        toast("这条候选没有百科链接");
        return;
      }
      if (typeof window !== "undefined") window.open(item.url, "_blank", "noopener");
    }
    async function subscribeActor(item) {
      if (isActorAdded(item)) {
        toast(`「${item.name}」已经在关注列表里`);
        return;
      }
      addingActorId.value = item.actor_id;
      try {
        const result = await addActor(props, item.name, item.actor_id);
        if (result?.success === false) {
          toast(String(result.message || "添加失败"), "error");
          return;
        }
        item.subscribed = true;
        toast(String(result?.message || `已添加「${item.name}」`));
        await reload();
      } catch (err) {
        toast(`添加失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        addingActorId.value = "";
      }
    }
    async function unsubscribeActor(item) {
      if (!isActorAdded(item)) {
        toast(`「${item.name}」不在关注列表里`);
        return;
      }
      removingActorId.value = item.actor_id;
      try {
        const result = await removeActor(props, item.name);
        if (result?.success === false) {
          toast(String(result.message || "移除失败"), "error");
          return;
        }
        item.subscribed = false;
        if (expandedActor.value?.actor_id === item.actor_id) collapseActor();
        toast(String(result?.message || `已移除「${item.name}」`));
        await reload();
      } catch (err) {
        toast(`移除失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        removingActorId.value = "";
      }
    }
    async function expandActor(item) {
      if (searchActive.value) {
        searchSnapshotQuery.value = searchKeyword.value;
        searchSnapshotResults.value = actorResults.value;
        searchSnapshotWorks.value = workResults.value;
      }
      actorQuery.value = "";
      expandedActor.value = item;
      expandedWorks.value = [];
      expandedError.value = "";
      expandedLoading.value = true;
      try {
        const payload = await fetchActorWorks(props, item.actor_id, item.name);
        if (expandedActor.value?.actor_id !== item.actor_id) return;
        if (payload?.success === false) {
          expandedError.value = String(payload.message || "取作品失败");
          return;
        }
        expandedWorks.value = payload.works || [];
      } catch (err) {
        if (expandedActor.value?.actor_id !== item.actor_id) return;
        expandedError.value = err instanceof Error ? err.message : String(err);
      } finally {
        if (expandedActor.value?.actor_id === item.actor_id) expandedLoading.value = false;
      }
    }
    function collapseActor() {
      expandedActor.value = null;
      expandedWorks.value = [];
      expandedError.value = "";
      expandedLoading.value = false;
    }
    async function backToSearch() {
      const query2 = searchSnapshotQuery.value;
      const results = searchSnapshotResults.value;
      const works2 = searchSnapshotWorks.value;
      collapseActor();
      if (!query2) return;
      actorResults.value = results;
      workResults.value = works2;
      searchingActors.value = false;
      searchingWorks.value = false;
      actorQuery.value = query2;
      await nextTick();
      if (lookupTimer) clearTimeout(lookupTimer);
      searchSnapshotQuery.value = "";
      searchSnapshotResults.value = [];
      searchSnapshotWorks.value = [];
    }
    let lookupEpoch = 0;
    async function runLookup() {
      const name = searchKeyword.value;
      const stamp = ++lookupEpoch;
      if (!name) {
        actorResults.value = [];
        workResults.value = [];
        searchingActors.value = false;
        searchingWorks.value = false;
        return;
      }
      searchingActors.value = true;
      searchingWorks.value = true;
      const actorTask = searchActor(props, name, true).then((payload) => {
        if (stamp !== lookupEpoch) return;
        actorResults.value = payload.candidates || [];
      }).catch((err) => {
        if (stamp !== lookupEpoch) return;
        actorResults.value = [];
        toast(`搜索演员失败：${err instanceof Error ? err.message : err}`, "error");
      }).finally(() => {
        if (stamp === lookupEpoch) searchingActors.value = false;
      });
      const workTask = searchWorks(props, name).then((payload) => {
        if (stamp !== lookupEpoch) return;
        workResults.value = payload.works || [];
      }).catch((err) => {
        if (stamp !== lookupEpoch) return;
        workResults.value = [];
        toast(`搜索作品失败：${err instanceof Error ? err.message : err}`, "error");
      }).finally(() => {
        if (stamp === lookupEpoch) searchingWorks.value = false;
      });
      await Promise.allSettled([actorTask, workTask]);
    }
    const gridRef = ref(null);
    const gridWidth = ref(0);
    let gridObserver = null;
    const columns = computed(() => {
      const width = gridWidth.value || MIN_ITEM_WIDTH;
      return Math.max(1, Math.floor((width + GRID_GAP) / (MIN_ITEM_WIDTH + GRID_GAP)));
    });
    const gridStyle = computed(() => ({
      columnGap: `${GRID_GAP}px`,
      rowGap: `${GRID_GAP}px`,
      gridTemplateColumns: `repeat(${columns.value}, minmax(0, 1fr))`
    }));
    function measureGrid() {
      const node = gridRef.value;
      if (!node) return;
      const width = node.clientWidth;
      if (width && width !== gridWidth.value) gridWidth.value = width;
    }
    function watchGrid() {
      gridObserver?.disconnect();
      gridObserver = null;
      const node = gridRef.value;
      if (!node) return;
      measureGrid();
      if (typeof ResizeObserver === "function") {
        gridObserver = new ResizeObserver(() => measureGrid());
        gridObserver.observe(node);
      }
    }
    const visibleCount = ref(0);
    let fillFrame = null;
    const visibleWorks = computed(() => works.value.slice(0, visibleCount.value));
    const displayWorks = computed(
      () => expandedActor.value ? expandedWorks.value : visibleWorks.value
    );
    function stepFill() {
      fillFrame = null;
      if (visibleCount.value >= works.value.length) {
        ensureFilled();
        return;
      }
      visibleCount.value = Math.min(works.value.length, visibleCount.value + BATCH_SIZE);
      if (visibleCount.value >= works.value.length) {
        ensureFilled();
        return;
      }
      if (typeof requestAnimationFrame === "function") {
        fillFrame = requestAnimationFrame(stepFill);
      } else {
        fillFrame = setTimeout(stepFill, 16);
      }
    }
    function scheduleFill() {
      if (fillFrame !== null) return;
      if (typeof requestAnimationFrame === "function") {
        fillFrame = requestAnimationFrame(stepFill);
      } else {
        fillFrame = setTimeout(stepFill, 16);
      }
    }
    function cancelFill() {
      if (fillFrame === null) return;
      if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(fillFrame);
      else clearTimeout(fillFrame);
      fillFrame = null;
    }
    function dedupeKey(work) {
      return JSON.stringify(["media", work.media_source, String(work.media_id ?? ""), work.type ?? null, null]);
    }
    function hasScrollbar() {
      const body = document.body;
      const viewport = window.innerHeight || document.documentElement.clientHeight;
      return body.scrollHeight - viewport > 2;
    }
    function applyMeta(payload) {
      total.value = payload.total;
      actorFilters.value = payload.actor_filters || [];
      facets.value = payload.facets;
      allTotal.value = payload.summary?.total ?? payload.total;
      newWorks.value = payload.summary?.new ?? 0;
      libraryKnown.value = Number(payload.summary?.library_known ?? 0);
      inLibraryCount.value = Number(payload.summary?.in_library ?? 0);
    }
    async function fetchPage() {
      const payload = await fetchWorks(props, { ...query(), page: page.value, page_size: PAGE_SIZE });
      page.value += 1;
      applyMeta(payload);
      const rows = payload.works || [];
      const signature = [...new Set(rows.map(dedupeKey))].sort().join("\n");
      const terminal = rows.length === 0 || seenSignatures.has(signature);
      if (!terminal) seenSignatures.add(signature);
      if (terminal) return { terminal: true, rows: [] };
      const fresh = rows.filter((row) => {
        const key = dedupeKey(row);
        if (seenKeys.has(key)) return false;
        seenKeys.add(key);
        return true;
      });
      return { terminal: false, rows: fresh };
    }
    function append(rows) {
      if (!rows.length) return;
      works.value = works.value.concat(rows);
      scheduleFill();
    }
    async function loadMore() {
      if (loadingMore.value || done.value) return;
      const stamp = epoch;
      loadingMore.value = true;
      error.value = false;
      try {
        if (hasScrollbar()) {
          const { terminal, rows } = await fetchPage();
          if (stamp !== epoch) return;
          if (terminal) {
            done.value = true;
            return;
          }
          append(rows);
        } else {
          while (!hasScrollbar()) {
            const { terminal, rows } = await fetchPage();
            if (stamp !== epoch) return;
            if (terminal) {
              done.value = true;
              return;
            }
            append(rows);
            await nextTick();
          }
        }
      } catch (err) {
        if (stamp !== epoch) return;
        error.value = true;
        toast(`加载作品失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        if (stamp === epoch) {
          loadingMore.value = false;
          await nextTick();
          ensureFilled();
        }
      }
    }
    function ensureFilled() {
      const node = sentinel.value;
      if (!node || done.value || loadingMore.value || loading.value) return;
      if (visibleCount.value < works.value.length) return;
      const viewport = window.innerHeight || document.documentElement.clientHeight;
      if (node.getBoundingClientRect().top <= viewport + 600) loadMore();
    }
    async function reload() {
      epoch += 1;
      cancelFill();
      loading.value = true;
      error.value = false;
      done.value = false;
      page.value = 1;
      seenKeys.clear();
      seenSignatures.clear();
      works.value = [];
      visibleCount.value = 0;
      loadingMore.value = false;
      await nextTick();
      try {
        await loadMore();
      } finally {
        loading.value = false;
      }
    }
    async function loadSubscribed() {
      subscribed.value = await fetchSubscribedIds(props);
    }
    const sentinel = ref(null);
    let observer = null;
    onMounted(async () => {
      if (typeof IntersectionObserver === "function") {
        observer = new IntersectionObserver(
          (entries) => {
            if (entries.some((entry) => entry.isIntersecting)) loadMore();
          },
          { rootMargin: "600px 0px" }
        );
        if (sentinel.value) observer.observe(sentinel.value);
      }
      window.addEventListener("scroll", onScroll, { passive: true });
      await Promise.all([reload(), loadSubscribed()]);
      await restorePaging();
      await nextTick();
      watchGrid();
    });
    function onScroll() {
      lastScrollY = window.scrollY || 0;
    }
    async function restorePaging() {
      if (savedPages <= 1) return;
      const stamp = epoch;
      for (let target = 2; target <= savedPages; target += 1) {
        if (stamp !== epoch) return;
        try {
          const { terminal, rows } = await fetchPage();
          if (stamp !== epoch) return;
          if (terminal) return;
          append(rows);
          await nextTick();
        } catch {
          return;
        }
      }
      visibleCount.value = works.value.length;
      await nextTick();
      window.scrollTo({ top: savedScroll });
    }
    onUnmounted(() => {
      writeViewState({ pages: Math.max(1, page.value - 1), scroll: lastScrollY });
      window.removeEventListener("scroll", onScroll);
      observer?.disconnect();
      observer = null;
      gridObserver?.disconnect();
      gridObserver = null;
      cancelFill();
      if (tipTimer) clearTimeout(tipTimer);
      if (lookupTimer) clearTimeout(lookupTimer);
    });
    watch(searchActive, async () => {
      await nextTick();
      watchGrid();
    });
    watch(
      () => works.value.length,
      async (count, previous) => {
        if (count && !previous) {
          await nextTick();
          watchGrid();
        }
      }
    );
    let lookupTimer = null;
    watch([actor, genre, year, studio, sort, onlyNotInLibrary], () => {
      persistFilters();
      reload();
    });
    watch(actorQuery, () => {
      if (lookupTimer) clearTimeout(lookupTimer);
      lookupTimer = setTimeout(runLookup, LOOKUP_DEBOUNCE);
    });
    async function subscribe(work) {
      if (subscribed.value.has(work.media_id)) {
        toast("这部剧已经在订阅里了");
        return;
      }
      await ensureConfig();
      const downloader = String(configData.value.subscribe_downloader || "").trim();
      if (downloader) {
        const res = await submitSubscribe(props, work, downloader);
        if (res.ok) {
          const next = new Set(subscribed.value);
          next.add(work.media_id);
          subscribed.value = next;
          setTimeout(loadSubscribed, 3e3);
        }
        toast(res.ok ? res.message : `订阅失败：${res.message}`, res.ok ? "info" : "error");
        return;
      }
      if (typeof props.nativeSubscribe !== "function") {
        toast("当前宿主没有提供系统订阅入口，请从「详情」页订阅", "error");
        return;
      }
      try {
        const result = await props.nativeSubscribe({
          media_source: work.media_source,
          media_id: work.media_id,
          title: work.title,
          year: work.year || "",
          type: work.type || "电视剧",
          poster_path: work.poster || "",
          vote_average: work.vote || 0
        });
        if (result && result.success === false) {
          toast(String(result.message || "订阅失败"), "error");
          return;
        }
        setTimeout(loadSubscribed, 3e3);
      } catch (err) {
        toast(`订阅失败：${err instanceof Error ? err.message : err}`, "error");
      }
    }
    function openMedia(work) {
      const url = mediaPageUrl(work);
      if (typeof window !== "undefined" && window.location) {
        window.location.href = url;
      }
    }
    const configData = ref({});
    let configLoaded = false;
    async function ensureConfig() {
      if (configLoaded) return;
      configLoaded = true;
      try {
        configData.value = { ...await fetchConfig(props), ...configData.value };
      } catch {
        configLoaded = false;
      }
    }
    async function searchWork(work) {
      if (typeof window === "undefined" || !window.location) return;
      await ensureConfig();
      const siteIds = String(configData.value.search_sites || "").split(/[,，;；\s]+/).filter((id) => id && /^\d+$/.test(id));
      window.location.href = resourceSearchUrl(work, siteIds.length ? siteIds.map(Number) : void 0);
    }
    return (_ctx, _cache) => {
      const _component_v_label = _resolveComponent("v-label");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_chip_group = _resolveComponent("v-chip-group");
      const _component_v_checkbox = _resolveComponent("v-checkbox");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_progress_circular = _resolveComponent("v-progress-circular");
      const _component_v_img = _resolveComponent("v-img");
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_hover = _resolveComponent("v-hover");
      return _openBlock(), _createElementBlock("div", {
        class: _normalizeClass(["sdas", { "sdas--full": __props.full }])
      }, [
        _createElementVNode("div", _hoisted_1, [
          _cache[12] || (_cache[12] = _createElementVNode("div", { class: "sdas-title" }, "短剧演员", -1)),
          _createElementVNode("div", _hoisted_2, [
            loading.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
              _createTextVNode("正在从短剧百科获取作品…")
            ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
              _createTextVNode(_toDisplayString(allTotal.value) + " 部作品 · " + _toDisplayString(actorCount.value) + " 位演员 ", 1),
              inLibraryKnown.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                _createTextVNode(" · 已入库 " + _toDisplayString(inLibraryCount.value) + " 部", 1)
              ], 64)) : _createCommentVNode("", true),
              newWorks.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _cache[11] || (_cache[11] = _createTextVNode(" · ", -1)),
                _createElementVNode("span", _hoisted_3, _toDisplayString(newWorks.value) + " 部新作品", 1)
              ], 64)) : _createCommentVNode("", true),
              filteredOut.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                _createTextVNode(" · 筛选出 " + _toDisplayString(total.value) + " 部", 1)
              ], 64)) : _createCommentVNode("", true)
            ], 64))
          ])
        ]),
        _createElementVNode("div", _hoisted_4, [
          facets.value.studios.length ? (_openBlock(), _createElementBlock("div", _hoisted_5, [
            _createElementVNode("div", _hoisted_6, [
              _createVNode(_component_v_label, null, {
                default: _withCtx(() => [..._cache[13] || (_cache[13] = [
                  _createTextVNode("版权方", -1)
                ])]),
                _: 1
              })
            ]),
            _createVNode(_component_v_chip_group, {
              class: _normalizeClass(["sdas-grid-cells", { "sdas-clip": !isExpanded("studio") }]),
              column: "",
              "model-value": studio.value || void 0,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => studio.value = pick($event))
            }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(facets.value.studios, (item) => {
                  return _openBlock(), _createBlock(_component_v_chip, {
                    key: item.value,
                    value: item.value,
                    color: studio.value === item.value ? "primary" : "",
                    filter: "",
                    tile: "",
                    title: item.value
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(item.value), 1),
                      _createElementVNode("span", _hoisted_7, _toDisplayString(item.count), 1)
                    ]),
                    _: 2
                  }, 1032, ["value", "color", "title"]);
                }), 128))
              ]),
              _: 1
            }, 8, ["class", "model-value"]),
            facets.value.studios.length > COLLAPSED_LIMIT ? (_openBlock(), _createBlock(_component_v_chip, {
              key: 0,
              class: "sdas-row-toggle",
              variant: "text",
              "prepend-icon": isExpanded("studio") ? "mdi-chevron-up" : "mdi-chevron-down",
              onClick: _cache[1] || (_cache[1] = ($event) => toggleRow("studio"))
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(isExpanded("studio") ? "收起" : "展开"), 1)
              ]),
              _: 1
            }, 8, ["prepend-icon"])) : _createCommentVNode("", true)
          ])) : _createCommentVNode("", true),
          facets.value.genres.length ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
            _createElementVNode("div", _hoisted_9, [
              _createVNode(_component_v_label, null, {
                default: _withCtx(() => [..._cache[14] || (_cache[14] = [
                  _createTextVNode("类型", -1)
                ])]),
                _: 1
              })
            ]),
            _createVNode(_component_v_chip_group, {
              class: _normalizeClass(["sdas-grid-cells", { "sdas-clip": !isExpanded("genre") }]),
              column: "",
              "model-value": genre.value || void 0,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => genre.value = pick($event))
            }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(facets.value.genres, (item) => {
                  return _openBlock(), _createBlock(_component_v_chip, {
                    key: item.value,
                    value: item.value,
                    color: genre.value === item.value ? "primary" : "",
                    title: item.value,
                    filter: "",
                    tile: ""
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(item.value), 1),
                      _createElementVNode("span", _hoisted_10, _toDisplayString(item.count), 1)
                    ]),
                    _: 2
                  }, 1032, ["value", "color", "title"]);
                }), 128))
              ]),
              _: 1
            }, 8, ["class", "model-value"]),
            facets.value.genres.length > COLLAPSED_LIMIT ? (_openBlock(), _createBlock(_component_v_chip, {
              key: 0,
              class: "sdas-row-toggle",
              variant: "text",
              "prepend-icon": isExpanded("genre") ? "mdi-chevron-up" : "mdi-chevron-down",
              onClick: _cache[3] || (_cache[3] = ($event) => toggleRow("genre"))
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(isExpanded("genre") ? "收起" : "展开"), 1)
              ]),
              _: 1
            }, 8, ["prepend-icon"])) : _createCommentVNode("", true)
          ])) : _createCommentVNode("", true),
          _createElementVNode("div", _hoisted_11, [
            _createElementVNode("div", _hoisted_12, [
              _createVNode(_component_v_label, null, {
                default: _withCtx(() => [..._cache[15] || (_cache[15] = [
                  _createTextVNode("演员", -1)
                ])]),
                _: 1
              })
            ]),
            _createVNode(_component_v_chip_group, {
              class: _normalizeClass(["sdas-grid-cells", { "sdas-clip": !isExpanded("actor") }]),
              column: "",
              "model-value": actor.value || void 0,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => actor.value = pick($event))
            }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorFilters.value, (item) => {
                  return _openBlock(), _createBlock(_component_v_chip, {
                    key: item.key,
                    value: item.key,
                    color: actor.value === item.key ? "primary" : "",
                    filter: "",
                    tile: "",
                    title: actorTitle(item)
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(item.name), 1),
                      _createElementVNode("span", _hoisted_13, _toDisplayString(item.works), 1),
                      item.state === "waiting" ? (_openBlock(), _createElementBlock("span", _hoisted_14, "·")) : _createCommentVNode("", true)
                    ]),
                    _: 2
                  }, 1032, ["value", "color", "title"]);
                }), 128))
              ]),
              _: 1
            }, 8, ["class", "model-value"]),
            actorFilters.value.length > COLLAPSED_LIMIT ? (_openBlock(), _createBlock(_component_v_chip, {
              key: 0,
              class: "sdas-row-toggle",
              variant: "text",
              "prepend-icon": isExpanded("actor") ? "mdi-chevron-up" : "mdi-chevron-down",
              onClick: _cache[5] || (_cache[5] = ($event) => toggleRow("actor"))
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(isExpanded("actor") ? "收起" : "展开"), 1)
              ]),
              _: 1
            }, 8, ["prepend-icon"])) : _createCommentVNode("", true)
          ]),
          facets.value.years.length ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
            _createElementVNode("div", _hoisted_16, [
              _createVNode(_component_v_label, null, {
                default: _withCtx(() => [..._cache[16] || (_cache[16] = [
                  _createTextVNode("年份", -1)
                ])]),
                _: 1
              })
            ]),
            _createVNode(_component_v_chip_group, {
              "model-value": year.value || void 0,
              "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => year.value = pick($event))
            }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(facets.value.years, (item) => {
                  return _openBlock(), _createBlock(_component_v_chip, {
                    key: item.value,
                    value: item.value,
                    color: year.value === item.value ? "primary" : "",
                    filter: "",
                    tile: ""
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(item.value), 1),
                      _createElementVNode("span", _hoisted_17, _toDisplayString(item.count), 1)
                    ]),
                    _: 2
                  }, 1032, ["value", "color"]);
                }), 128))
              ]),
              _: 1
            }, 8, ["model-value"])
          ])) : _createCommentVNode("", true),
          _createElementVNode("div", _hoisted_18, [
            _createElementVNode("div", _hoisted_19, [
              _createVNode(_component_v_label, null, {
                default: _withCtx(() => [..._cache[17] || (_cache[17] = [
                  _createTextVNode("排序", -1)
                ])]),
                _: 1
              })
            ]),
            _createVNode(_component_v_chip_group, {
              "model-value": sort.value || void 0,
              "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => sort.value = pick($event) || "heat")
            }, {
              default: _withCtx(() => [
                (_openBlock(), _createElementBlock(_Fragment, null, _renderList(sortOptions, (opt) => {
                  return _createVNode(_component_v_chip, {
                    key: opt.value,
                    value: opt.value,
                    color: sort.value === opt.value ? "primary" : "",
                    filter: "",
                    tile: ""
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(opt.title), 1)
                    ]),
                    _: 2
                  }, 1032, ["value", "color"]);
                }), 64))
              ]),
              _: 1
            }, 8, ["model-value"])
          ]),
          libraryKnown.value > 0 ? (_openBlock(), _createElementBlock("div", _hoisted_20, [
            _createElementVNode("div", _hoisted_21, [
              _createVNode(_component_v_label, null, {
                default: _withCtx(() => [..._cache[18] || (_cache[18] = [
                  _createTextVNode("媒体库", -1)
                ])]),
                _: 1
              })
            ]),
            _createVNode(_component_v_checkbox, {
              modelValue: onlyNotInLibrary.value,
              "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => onlyNotInLibrary.value = $event),
              label: "只看未入库",
              density: "compact",
              "hide-details": "",
              class: "sdas-checkbox",
              title: "只显示还没进 MoviePilot 媒体库的作品（判定与媒体详情页一致：身份精确匹配，未命中按片名+年份回退）。已在库的作品卡片右上角有绿色对勾（与探索页一致）"
            }, null, 8, ["modelValue"])
          ])) : _createCommentVNode("", true),
          _createElementVNode("div", _hoisted_22, [
            _createElementVNode("div", _hoisted_23, [
              _createVNode(_component_v_label, null, {
                default: _withCtx(() => [..._cache[19] || (_cache[19] = [
                  _createTextVNode("搜索", -1)
                ])]),
                _: 1
              })
            ]),
            _createVNode(_component_v_text_field, {
              modelValue: actorQuery.value,
              "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => actorQuery.value = $event),
              class: "sdas-search",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              clearable: "",
              placeholder: "搜索演员或作品",
              "prepend-inner-icon": "mdi-magnify"
            }, null, 8, ["modelValue"]),
            searchActive.value ? (_openBlock(), _createElementBlock("span", _hoisted_24, [
              searchingActors.value || searchingWorks.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                _createTextVNode("正在查短剧百科…")
              ], 64)) : searchSummary.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _createTextVNode(_toDisplayString(searchSummary.value), 1)
              ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                _createTextVNode("没有找到相关演员或作品")
              ], 64))
            ])) : _createCommentVNode("", true),
            filteredOut.value ? (_openBlock(), _createBlock(_component_v_chip, {
              key: 1,
              class: "sdas-row-toggle ml-2",
              variant: "text",
              "prepend-icon": "mdi-filter-off-outline",
              onClick: resetFilters
            }, {
              default: _withCtx(() => [..._cache[20] || (_cache[20] = [
                _createTextVNode(" 重置 ", -1)
              ])]),
              _: 1
            })) : _createCommentVNode("", true)
          ])
        ]),
        searchActive.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
          _createElementVNode("div", {
            ref_key: "gridRef",
            ref: gridRef,
            class: "sdas-measure",
            "aria-hidden": "true"
          }, null, 512),
          !actorResults.value.length && !workResults.value.length && (searchingActors.value || searchingWorks.value) ? (_openBlock(), _createElementBlock("div", _hoisted_25, [
            _createVNode(_component_v_progress_circular, {
              indeterminate: "",
              size: "28",
              width: "2"
            })
          ])) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
            actorResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_26, [
              _createElementVNode("div", _hoisted_27, "演员 · " + _toDisplayString(actorResults.value.length), 1),
              _createElementVNode("div", {
                class: "sdas-grid",
                style: _normalizeStyle(gridStyle.value)
              }, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorResults.value, (item) => {
                  return _openBlock(), _createElementBlock("div", {
                    key: item.actor_id,
                    class: "sdas-item"
                  }, [
                    _createVNode(_component_v_hover, null, {
                      default: _withCtx(({ isHovering, props: hoverProps }) => [
                        _createElementVNode("div", _mergeProps({ ref_for: true }, hoverProps, { class: "sdas-hover-area" }), [
                          _createVNode(_component_v_card, {
                            ripple: false,
                            class: _normalizeClass(["app-hover-lift-card outline-none ring-gray-500 media-card sdas-card", {
                              "app-hover-lift-card--hovering": isHovering,
                              "ring-1": isPosterLoaded(actorKey(item))
                            }]),
                            onClick: ($event) => expandActor(item)
                          }, {
                            default: _withCtx(() => [
                              item.profile ? (_openBlock(), _createBlock(_component_v_img, {
                                key: 0,
                                src: _unref(proxyImage)(item.profile),
                                "aspect-ratio": 2 / 3,
                                cover: "",
                                class: "object-cover aspect-w-2 aspect-h-3",
                                onLoad: ($event) => markPosterLoaded(actorKey(item)),
                                onError: ($event) => markPosterLoaded(actorKey(item))
                              }, {
                                placeholder: _withCtx(() => [..._cache[21] || (_cache[21] = [
                                  _createElementVNode("div", { class: "sdas-poster-skeleton" }, null, -1)
                                ])]),
                                _: 1
                              }, 8, ["src", "onLoad", "onError"])) : (_openBlock(), _createElementBlock("div", _hoisted_28, [
                                _createVNode(_component_v_icon, {
                                  icon: "mdi-account-outline",
                                  size: "56",
                                  color: "medium-emphasis"
                                })
                              ])),
                              isHovering ? (_openBlock(), _createElementBlock("div", {
                                key: 2,
                                class: "w-full h-full flex flex-col flex-wrap justify-end align-left text-white absolute bottom-0 cursor-pointer pa-2",
                                style: OVERLAY_STYLE
                              }, [
                                _createElementVNode("span", _hoisted_29, _toDisplayString(actorMeta(item)), 1),
                                _createElementVNode("h1", _hoisted_30, _toDisplayString(item.name), 1),
                                _createElementVNode("p", _hoisted_31, _toDisplayString(item.bio || "短剧演员"), 1),
                                _createElementVNode("div", _hoisted_32, [
                                  _createVNode(_component_v_btn, {
                                    icon: "",
                                    variant: "text",
                                    title: "打开百科演员页",
                                    onClick: _withModifiers(($event) => openActorPage(item), ["stop"])
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_icon, {
                                        size: "24",
                                        color: "white"
                                      }, {
                                        default: _withCtx(() => [..._cache[22] || (_cache[22] = [
                                          _createTextVNode("mdi-open-in-new", -1)
                                        ])]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }, 8, ["onClick"]),
                                  _createVNode(_component_v_spacer),
                                  _createVNode(_component_v_btn, {
                                    icon: "",
                                    variant: "text",
                                    size: "small",
                                    color: isActorAdded(item) ? "error" : "white",
                                    title: isActorAdded(item) ? "取消订阅（移出关注列表）" : "订阅（加入关注列表）",
                                    loading: addingActorId.value === item.actor_id || removingActorId.value === item.actor_id,
                                    onClick: _withModifiers(($event) => isActorAdded(item) ? unsubscribeActor(item) : subscribeActor(item), ["stop"])
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_icon, {
                                        size: "24",
                                        color: isActorAdded(item) ? "error" : "white"
                                      }, {
                                        default: _withCtx(() => [
                                          _createTextVNode(_toDisplayString(isActorAdded(item) ? "mdi-account-remove" : "mdi-account-plus"), 1)
                                        ]),
                                        _: 2
                                      }, 1032, ["color"])
                                    ]),
                                    _: 2
                                  }, 1032, ["color", "title", "loading", "onClick"])
                                ])
                              ])) : _createCommentVNode("", true)
                            ]),
                            _: 2
                          }, 1032, ["class", "onClick"])
                        ], 16)
                      ]),
                      _: 2
                    }, 1024)
                  ]);
                }), 128))
              ], 4)
            ])) : !searchingActors.value ? (_openBlock(), _createElementBlock("div", _hoisted_33, " 没有找到相关演员 ")) : _createCommentVNode("", true),
            workResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_34, [
              _createElementVNode("div", _hoisted_35, "作品 · " + _toDisplayString(workResults.value.length), 1),
              _createElementVNode("div", {
                class: "sdas-grid",
                style: _normalizeStyle(gridStyle.value)
              }, [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(workResults.value, (work) => {
                  return _openBlock(), _createElementBlock("div", {
                    key: work.key,
                    class: "sdas-item"
                  }, [
                    _createVNode(WorkCard, {
                      work,
                      loaded: isPosterLoaded(work.key),
                      subscribed: subscribed.value.has(work.media_id),
                      onPoster: ($event) => markPosterLoaded(work.key),
                      onOpen: openMedia,
                      onSearch: searchWork,
                      onSubscribe: subscribe
                    }, null, 8, ["work", "loaded", "subscribed", "onPoster"])
                  ]);
                }), 128))
              ], 4)
            ])) : !searchingWorks.value && actorResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_36, " 没有找到相关作品 ")) : _createCommentVNode("", true),
            !actorResults.value.length && !workResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_37, [
              _createVNode(_component_v_icon, {
                size: "48",
                color: "grey"
              }, {
                default: _withCtx(() => [..._cache[23] || (_cache[23] = [
                  _createTextVNode("mdi-account-search-outline", -1)
                ])]),
                _: 1
              }),
              _createElementVNode("div", _hoisted_38, "没找到「" + _toDisplayString(searchKeyword.value) + "」", 1),
              _cache[24] || (_cache[24] = _createElementVNode("div", { class: "sdas-empty-hint" }, "换个名字试试 —— 短剧百科只收录站上有的演员和作品", -1))
            ])) : _createCommentVNode("", true)
          ], 64))
        ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
          expandedActor.value ? (_openBlock(), _createElementBlock("div", _hoisted_39, [
            _createVNode(_component_v_btn, {
              icon: "",
              variant: "text",
              title: "返回搜索结果",
              onClick: backToSearch
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { size: "24" }, {
                  default: _withCtx(() => [..._cache[25] || (_cache[25] = [
                    _createTextVNode("mdi-arrow-left", -1)
                  ])]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_icon, {
              icon: "mdi-account-outline",
              size: "18",
              class: "mr-2 ml-1"
            }),
            _createElementVNode("span", _hoisted_40, _toDisplayString(expandedActor.value.name) + " 的作品", 1),
            !expandedLoading.value ? (_openBlock(), _createElementBlock("span", _hoisted_41, " 共 " + _toDisplayString(expandedWorks.value.length) + " 部 ", 1)) : _createCommentVNode("", true),
            _createVNode(_component_v_spacer)
          ])) : _createCommentVNode("", true),
          expandedActor.value && expandedLoading.value ? (_openBlock(), _createElementBlock("div", _hoisted_42, [
            _createVNode(_component_v_progress_circular, {
              indeterminate: "",
              size: "28",
              width: "2"
            })
          ])) : expandedActor.value && expandedError.value ? (_openBlock(), _createElementBlock("div", _hoisted_43, [
            _createElementVNode("span", _hoisted_44, _toDisplayString(expandedError.value), 1),
            _createVNode(_component_v_btn, {
              "prepend-icon": "mdi-refresh",
              size: "small",
              variant: "tonal",
              onClick: _cache[10] || (_cache[10] = ($event) => expandActor(expandedActor.value))
            }, {
              default: _withCtx(() => [..._cache[26] || (_cache[26] = [
                _createTextVNode("重试", -1)
              ])]),
              _: 1
            })
          ])) : expandedActor.value && !expandedWorks.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_45, [
            _createVNode(_component_v_icon, {
              size: "48",
              color: "grey"
            }, {
              default: _withCtx(() => [..._cache[27] || (_cache[27] = [
                _createTextVNode("mdi-movie-open-star-outline", -1)
              ])]),
              _: 1
            }),
            _createElementVNode("div", _hoisted_46, "百科里没有「" + _toDisplayString(expandedActor.value.name) + "」的作品记录", 1)
          ])) : !works.value.length && !error.value ? (_openBlock(), _createElementBlock("div", _hoisted_47, [
            _createVNode(_component_v_progress_circular, {
              indeterminate: "",
              size: "28",
              width: "2"
            })
          ])) : error.value && !works.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_48, [
            _cache[29] || (_cache[29] = _createElementVNode("span", { class: "text-body-2 text-medium-emphasis" }, "网络错误", -1)),
            _createVNode(_component_v_btn, {
              "prepend-icon": "mdi-refresh",
              size: "small",
              variant: "tonal",
              onClick: reload
            }, {
              default: _withCtx(() => [..._cache[28] || (_cache[28] = [
                _createTextVNode("重试", -1)
              ])]),
              _: 1
            })
          ])) : !works.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_49, [
            _createVNode(_component_v_icon, {
              size: "48",
              color: "grey"
            }, {
              default: _withCtx(() => [..._cache[30] || (_cache[30] = [
                _createTextVNode("mdi-movie-open-star-outline", -1)
              ])]),
              _: 1
            }),
            _createElementVNode("div", _hoisted_50, [
              !actorCount.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                _createTextVNode("还没有添加演员")
              ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _createTextVNode("没有符合条件的作品")
              ], 64))
            ]),
            _createElementVNode("div", _hoisted_51, [
              !actorCount.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                _createTextVNode("在「搜索」里搜一位演员，点卡片上的「订阅」加进来")
              ], 64)) : filteredOut.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                _createTextVNode("换个筛选条件试试")
              ], 64)) : emptyHint.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                _createTextVNode(_toDisplayString(emptyHint.value), 1)
              ], 64)) : _createCommentVNode("", true)
            ])
          ])) : (_openBlock(), _createElementBlock("div", {
            key: 7,
            ref_key: "gridRef",
            ref: gridRef,
            class: "sdas-grid",
            style: _normalizeStyle(gridStyle.value)
          }, [
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(displayWorks.value, (work, index) => {
              return _openBlock(), _createElementBlock("div", {
                key: work.key,
                class: "sdas-item",
                "data-progressive-grid-index": index
              }, [
                _createVNode(WorkCard, {
                  work,
                  loaded: isPosterLoaded(work.key),
                  subscribed: subscribed.value.has(work.media_id),
                  onPoster: ($event) => markPosterLoaded(work.key),
                  onOpen: openMedia,
                  onSearch: searchWork,
                  onSubscribe: subscribe
                }, null, 8, ["work", "loaded", "subscribed", "onPoster"])
              ], 8, _hoisted_52);
            }), 128))
          ], 4)),
          !expandedActor.value ? (_openBlock(), _createElementBlock("div", {
            key: 8,
            ref_key: "sentinel",
            ref: sentinel,
            class: "sdas-sentinel"
          }, [
            loadingMore.value ? (_openBlock(), _createBlock(_component_v_progress_circular, {
              key: 0,
              indeterminate: "",
              size: "20",
              width: "2"
            })) : works.value.length && done.value ? (_openBlock(), _createElementBlock("span", _hoisted_53, "已到末尾 · 共 " + _toDisplayString(total.value) + " 部", 1)) : _createCommentVNode("", true)
          ], 512)) : _createCommentVNode("", true)
        ], 64)),
        _createVNode(_Transition, { name: "sdas-fade" }, {
          default: _withCtx(() => [
            tip.value ? (_openBlock(), _createElementBlock("div", {
              key: 0,
              class: _normalizeClass(["sdas-toast", `is-${tipType.value}`])
            }, _toDisplayString(tip.value), 3)) : _createCommentVNode("", true)
          ]),
          _: 1
        })
      ], 2);
    };
  }
});

const ActorWall = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-6c26e0f7"]]);

export { ActorWall as A };
