import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { p as proxyImage, r as retryProxyImage, _ as _export_sfc, e as fetchActorDetail, g as fetchAdaptedDetail, h as fetchAdaptedInfo, i as pluginSubscribeSearchNow, j as pluginSubscribeUpdate, f as fetchSearchSites, b as fetchDownloaderOptions, a as fetchDownloadPaths, k as fetchSubscriptions, l as fetchPlayUrl, m as fetchWorkDetail, n as fetchWorkSource, o as fetchDoubanComments, q as fetchDoubanReviews, t as fetchPeople, u as fetchRankWorks, v as fetchRanks, w as fetchLogs, x as addActor, y as removeActor, z as lookupSite, A as fetchWorks, B as pluginSubscribeRandom, C as pluginSubscribeSearchAll, D as fetchActorCards, E as pluginUnsubscribe, F as pluginSubscribe, G as subscribeAllActor, H as fetchConfig, I as resourceSearchUrl } from './_plugin-vue_export-helper-Clm0RiNn.js';

const {defineComponent:_defineComponent$b} = await importShared('vue');

const {resolveComponent:_resolveComponent$6,openBlock:_openBlock$b,createBlock:_createBlock$7,createCommentVNode:_createCommentVNode$b,createTextVNode:_createTextVNode$6,withCtx:_withCtx$7,createVNode:_createVNode$7,createElementBlock:_createElementBlock$a,toDisplayString:_toDisplayString$8,createElementVNode:_createElementVNode$9,renderList:_renderList$7,Fragment:_Fragment$7,withModifiers:_withModifiers$2,normalizeClass:_normalizeClass$6,mergeProps:_mergeProps$1} = await importShared('vue');

const _hoisted_1$8 = { class: "sdas-person-body" };
const _hoisted_2$7 = {
  key: 1,
  class: "sdas-person-photo sdas-person-photo--empty"
};
const _hoisted_3$7 = { class: "sdas-person-caption" };
const _hoisted_4$7 = { class: "sdas-person-left" };
const _hoisted_5$6 = { class: "sdas-person-name" };
const _hoisted_6$6 = {
  key: 0,
  class: "sdas-person-role"
};
const _hoisted_7$6 = {
  key: 1,
  class: "sdas-person-meta"
};
const _hoisted_8$5 = {
  key: 0,
  class: "sdas-person-more sdas-person-stats"
};
const {computed: computed$9,onBeforeUnmount: onBeforeUnmount$3,ref: ref$a} = await importShared('vue');
const _sfc_main$b = /* @__PURE__ */ _defineComponent$b({
  __name: "ActorCard",
  props: {
    item: {},
    added: { type: Boolean },
    role: {},
    busy: { type: Boolean },
    loaded: { type: Boolean },
    state: {},
    subscribeAll: { type: Boolean },
    subscribeAllBusy: { type: Boolean }
  },
  emits: ["open", "page", "toggle", "poster", "subscribe-all"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const imgFailed = ref$a(false);
    const avatarSrc = computed$9(
      () => props.item.profile ? proxyImage(props.item.profile) : ""
    );
    const retryCount = ref$a(0);
    const retryTimer = ref$a(null);
    const displaySrc = computed$9(() => retryProxyImage(avatarSrc.value, retryCount.value));
    function onAvatarLoad() {
      imgFailed.value = false;
      emit("poster");
    }
    function onAvatarError() {
      if (retryCount.value < 2 && avatarSrc.value) {
        if (retryTimer.value) clearTimeout(retryTimer.value);
        retryTimer.value = setTimeout(() => {
          retryCount.value += 1;
        }, 700);
        return;
      }
      imgFailed.value = true;
      emit("poster");
    }
    onBeforeUnmount$3(() => {
      if (retryTimer.value) clearTimeout(retryTimer.value);
    });
    const worksLine = computed$9(() => {
      const parts = [];
      if (props.item.works_count) parts.push(`${props.item.works_count} 部作品`);
      const job = String(props.item.job_title || "").trim();
      if (job && !["演员", "女演员", "男演员", "男", "女"].includes(job)) parts.push(job);
      if (props.state === "waiting") parts.push("暂未取到作品，会自动重试");
      else if (props.state === "empty") parts.push("短剧百科未收录");
      return parts.join(" · ");
    });
    const statLines = computed$9(() => {
      const lines = [];
      const followers = formatCount(props.item.followers);
      if (followers) lines.push(`粉丝 ${followers}`);
      const likes = formatCount(props.item.likes);
      if (likes) lines.push(`获赞 ${likes}`);
      return lines;
    });
    function formatCount(value) {
      const num = Number(value || 0);
      if (!num) return "";
      if (num >= 1e8) return `${(num / 1e8).toFixed(1)}亿`;
      if (num >= 1e4) return `${(num / 1e4).toFixed(1)}万`;
      return String(num);
    }
    return (_ctx, _cache) => {
      const _component_v_img = _resolveComponent$6("v-img");
      const _component_v_icon = _resolveComponent$6("v-icon");
      const _component_v_btn = _resolveComponent$6("v-btn");
      const _component_v_card = _resolveComponent$6("v-card");
      const _component_v_hover = _resolveComponent$6("v-hover");
      return _openBlock$b(), _createBlock$7(_component_v_hover, null, {
        default: _withCtx$7(({ isHovering, props: hoverProps }) => [
          _createElementVNode$9("div", _mergeProps$1(hoverProps, { class: "sdas-hover-area" }), [
            _createVNode$7(_component_v_card, {
              ripple: false,
              class: _normalizeClass$6(["app-hover-lift-card outline-none sdas-person-card", { "app-hover-lift-card--hovering": isHovering }]),
              onClick: _cache[2] || (_cache[2] = ($event) => emit("open"))
            }, {
              default: _withCtx$7(() => [
                _createElementVNode$9("div", _hoisted_1$8, [
                  __props.item.profile && !imgFailed.value ? (_openBlock$b(), _createBlock$7(_component_v_img, {
                    key: 0,
                    class: "sdas-person-photo",
                    src: displaySrc.value,
                    cover: "",
                    onLoad: onAvatarLoad,
                    onError: onAvatarError
                  }, null, 8, ["src"])) : (_openBlock$b(), _createElementBlock$a("div", _hoisted_2$7, [
                    _createVNode$7(_component_v_icon, {
                      size: "56",
                      color: "medium-emphasis"
                    }, {
                      default: _withCtx$7(() => [..._cache[3] || (_cache[3] = [
                        _createTextVNode$6("mdi-account-outline", -1)
                      ])]),
                      _: 1
                    })
                  ])),
                  _createElementVNode$9("div", _hoisted_3$7, [
                    _createElementVNode$9("div", _hoisted_4$7, [
                      _createElementVNode$9("div", _hoisted_5$6, _toDisplayString$8(__props.item.name), 1),
                      __props.role ? (_openBlock$b(), _createElementBlock$a("div", _hoisted_6$6, _toDisplayString$8(__props.role), 1)) : _createCommentVNode$b("", true),
                      worksLine.value ? (_openBlock$b(), _createElementBlock$a("div", _hoisted_7$6, _toDisplayString$8(worksLine.value), 1)) : _createCommentVNode$b("", true)
                    ]),
                    statLines.value.length ? (_openBlock$b(), _createElementBlock$a("div", _hoisted_8$5, [
                      (_openBlock$b(true), _createElementBlock$a(_Fragment$7, null, _renderList$7(statLines.value, (line) => {
                        return _openBlock$b(), _createElementBlock$a("div", { key: line }, _toDisplayString$8(line), 1);
                      }), 128))
                    ])) : _createCommentVNode$b("", true)
                  ]),
                  __props.subscribeAll ? (_openBlock$b(), _createBlock$7(_component_v_btn, {
                    key: 2,
                    class: "sdas-person-suball",
                    variant: "flat",
                    size: "small",
                    density: "compact",
                    loading: __props.subscribeAllBusy,
                    disabled: __props.subscribeAllBusy,
                    title: "把这名演员的全部作品提交给订阅系统",
                    onClick: _cache[0] || (_cache[0] = _withModifiers$2(($event) => emit("subscribe-all"), ["stop"]))
                  }, {
                    default: _withCtx$7(() => [
                      _createVNode$7(_component_v_icon, {
                        size: "18",
                        start: ""
                      }, {
                        default: _withCtx$7(() => [..._cache[4] || (_cache[4] = [
                          _createTextVNode$6("mdi-playlist-plus", -1)
                        ])]),
                        _: 1
                      }),
                      _cache[5] || (_cache[5] = _createElementVNode$9("span", { class: "sdas-person-suball-text" }, "订阅全部", -1))
                    ]),
                    _: 1
                  }, 8, ["loading", "disabled"])) : _createCommentVNode$b("", true),
                  _createVNode$7(_component_v_btn, {
                    class: "sdas-person-like",
                    icon: "",
                    variant: "text",
                    size: "small",
                    loading: __props.busy,
                    title: __props.added ? "取消关注（移出关注列表）" : "关注（加入关注列表）",
                    onClick: _cache[1] || (_cache[1] = _withModifiers$2(($event) => emit("toggle"), ["stop"]))
                  }, {
                    default: _withCtx$7(() => [
                      _createVNode$7(_component_v_icon, {
                        size: "22",
                        color: __props.added ? "error" : "white"
                      }, {
                        default: _withCtx$7(() => [
                          _createTextVNode$6(_toDisplayString$8(__props.added ? "mdi-heart" : "mdi-heart-outline"), 1)
                        ]),
                        _: 1
                      }, 8, ["color"])
                    ]),
                    _: 1
                  }, 8, ["loading", "title"])
                ])
              ]),
              _: 1
            }, 8, ["class"])
          ], 16)
        ]),
        _: 1
      });
    };
  }
});

const ActorCard = /* @__PURE__ */ _export_sfc(_sfc_main$b, [["__scopeId", "data-v-027225f1"]]);

const {ref: ref$9} = await importShared('vue');

const activeTouchCardId = ref$9(null);
let cardIdSeed = 0;
function nextCardId() {
  cardIdSeed += 1;
  return cardIdSeed;
}
const revealedPosters = /* @__PURE__ */ new Set();

const {defineComponent:_defineComponent$a} = await importShared('vue');

const {resolveComponent:_resolveComponent$5,createVNode:_createVNode$6,createElementVNode:_createElementVNode$8,withCtx:_withCtx$6,openBlock:_openBlock$a,createBlock:_createBlock$6,createCommentVNode:_createCommentVNode$a,createElementBlock:_createElementBlock$9,toDisplayString:_toDisplayString$7,createTextVNode:_createTextVNode$5,vShow:_vShow$1,normalizeClass:_normalizeClass$5,withDirectives:_withDirectives$1,withModifiers:_withModifiers$1,mergeProps:_mergeProps} = await importShared('vue');

const _hoisted_1$7 = { class: "sdas-poster-skeleton-wrap" };
const _hoisted_2$6 = {
  key: 1,
  class: "sdas-poster-empty d-flex align-center justify-center"
};
const _hoisted_3$6 = { class: "absolute top-0 right-0 p-2 d-flex align-center ga-1" };
const _hoisted_4$6 = {
  key: 0,
  class: "pointer-events-none z-40 flex items-center",
  title: "这部作品已在 MoviePilot 媒体库中（与媒体详情页的判定一致）"
};
const _hoisted_5$5 = {
  key: 1,
  class: "sdas-new",
  title: "新作品（最近上映 / 首次发现）"
};
const _hoisted_6$5 = { class: "font-semibold text-sm" };
const _hoisted_7$5 = { class: "sdas-card-title font-bold mb-2 text-white line-clamp-2 overflow-hidden text-ellipsis" };
const _hoisted_8$4 = { class: "sdas-card-overview line-clamp-3 overflow-hidden text-ellipsis" };
const _hoisted_9$4 = { class: "flex align-center justify-between" };
const {computed: computed$8,onBeforeUnmount: onBeforeUnmount$2,onMounted: onMounted$8,ref: ref$8} = await importShared('vue');
const _sfc_main$a = /* @__PURE__ */ _defineComponent$a({
  __name: "WorkCard",
  props: {
    work: {},
    loaded: { type: Boolean },
    subscribed: { type: Boolean },
    subscribing: {},
    searching: {}
  },
  emits: ["poster", "open", "search", "subscribe", "search-now"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const OVERLAY_STYLE = {
      background: "linear-gradient(rgba(45, 55, 72, 40%) 0%, rgba(45, 55, 72, 90%) 100%)"
    };
    const cardId = nextCardId();
    const isTouchLikePointer = ref$8(
      typeof window !== "undefined" && Boolean(window.matchMedia?.("(hover: none), (pointer: coarse)").matches)
    );
    const imgFailed = ref$8(false);
    const posterSrc = computed$8(() => props.work.poster ? proxyImage(props.work.poster) : "");
    const revisit = ref$8(Boolean(posterSrc.value) && revealedPosters.has(posterSrc.value));
    const retryCount = ref$8(0);
    const retryTimer = ref$8(null);
    const displaySrc = computed$8(() => retryProxyImage(posterSrc.value, retryCount.value));
    const imgRequest = computed$8(() => ({
      key: posterSrc.value,
      eager: revisit.value,
      transition: revisit.value ? { css: false } : "fade-transition"
    }));
    const posterCovered = computed$8(() => Boolean(posterSrc.value) && props.loaded && !imgFailed.value);
    function activeState(isHovering) {
      return activeTouchCardId.value === cardId || !isTouchLikePointer.value && Boolean(isHovering);
    }
    function detailVisible(isHovering) {
      return activeState(isHovering);
    }
    function resetTouchState() {
      if (activeTouchCardId.value === cardId) activeTouchCardId.value = null;
    }
    function handleClick(isHovering) {
      if (isTouchLikePointer.value && !detailVisible(isHovering)) {
        activeTouchCardId.value = cardId;
        return;
      }
      resetTouchState();
      emit("open", props.work);
    }
    function handleDocumentPointerDown(event) {
      if (!isTouchLikePointer.value || activeTouchCardId.value !== cardId) return;
      if (!(event.target instanceof Node)) return;
      if (cardRef.value?.contains(event.target)) return;
      resetTouchState();
    }
    const cardRef = ref$8(null);
    function handleImageLoad() {
      imgFailed.value = false;
      if (posterSrc.value) revealedPosters.add(posterSrc.value);
      emit("poster", props.work.key);
    }
    function handleImageError() {
      if (retryCount.value < 2 && posterSrc.value) {
        if (retryTimer.value) clearTimeout(retryTimer.value);
        retryTimer.value = setTimeout(() => {
          retryCount.value += 1;
        }, 700);
        return;
      }
      imgFailed.value = true;
      emit("poster", props.work.key);
    }
    onMounted$8(() => {
      if (isTouchLikePointer.value) document.addEventListener("pointerdown", handleDocumentPointerDown);
    });
    onBeforeUnmount$2(() => {
      resetTouchState();
      if (retryTimer.value) clearTimeout(retryTimer.value);
      document.removeEventListener("pointerdown", handleDocumentPointerDown);
    });
    const KIND_LABELS = {
      manju: "漫剧",
      huolong: "漫剧",
      duanju: "短剧",
      hema: "短剧"
    };
    const kindLabel = computed$8(() => {
      const raw = String(props.work.media_id || "");
      const kind = raw.includes(":") ? raw.split(":")[0].toLowerCase() : "";
      if (kind && KIND_LABELS[kind]) return KIND_LABELS[kind];
      const source = String(props.work.media_source || "").toLowerCase();
      return KIND_LABELS[source] || "短剧";
    });
    const kindChipClass = computed$8(
      () => kindLabel.value === "漫剧" ? "border-purple-600 bg-purple-600" : "bg-indigo-500 border-indigo-600"
    );
    const badgeIsNew = computed$8(() => Number(props.work.vote) <= 0 && Boolean(props.work.is_new));
    const badge = computed$8(() => {
      const vote = Number(props.work.vote);
      if (vote > 0) return vote.toFixed(1);
      const date = String(props.work.release_date || "").trim();
      if (!date) return "";
      const matched = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
      return matched ? `${matched[2]}-${matched[3]}` : date;
    });
    const badgeTitle = computed$8(
      () => Number(props.work.vote) > 0 ? "评分" : "首播日期（百科还没有这部剧的评分）"
    );
    const SUB_STATES = {
      downloaded: { label: "已提交下载", cls: "bg-green-600 border-green-400", icon: "mdi-check-circle-outline" },
      history: { label: "下载历史已有", cls: "bg-teal-600 border-teal-400", icon: "mdi-content-duplicate" },
      in_library: { label: "已在媒体库", cls: "bg-teal-600 border-teal-400", icon: "mdi-library-outline" },
      noresult: { label: "暂无资源", cls: "bg-grey-darken-1 border-grey", icon: "mdi-magnify-close" },
      failed: { label: "搜索失败", cls: "bg-red-600 border-red-400", icon: "mdi-alert-circle-outline" }
    };
    const subChip = computed$8(() => SUB_STATES[String(props.work.sub_state || "")] || null);
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
      const _component_v_skeleton_loader = _resolveComponent$5("v-skeleton-loader");
      const _component_v_img = _resolveComponent$5("v-img");
      const _component_v_icon = _resolveComponent$5("v-icon");
      const _component_v_chip = _resolveComponent$5("v-chip");
      const _component_v_avatar = _resolveComponent$5("v-avatar");
      const _component_v_btn = _resolveComponent$5("v-btn");
      const _component_v_spacer = _resolveComponent$5("v-spacer");
      const _component_v_card = _resolveComponent$5("v-card");
      const _component_v_hover = _resolveComponent$5("v-hover");
      return _openBlock$a(), _createBlock$6(_component_v_hover, null, {
        default: _withCtx$6(({ isHovering, props: hoverProps }) => [
          _createElementVNode$8("div", _mergeProps({
            ref_key: "cardRef",
            ref: cardRef
          }, hoverProps, { class: "sdas-hover-area" }), [
            _createVNode$6(_component_v_card, {
              ripple: false,
              "data-glass-optical-mode": posterCovered.value ? "excluded" : void 0,
              class: _normalizeClass$5(["app-hover-lift-card outline-none ring-gray-500 media-card sdas-card", {
                "app-hover-lift-card--hovering": activeState(isHovering),
                "ring-1": __props.loaded && !imgFailed.value
              }]),
              onClick: _withModifiers$1(($event) => handleClick(isHovering), ["stop"])
            }, {
              default: _withCtx$6(() => [
                __props.work.poster && !imgFailed.value ? (_openBlock$a(), _createBlock$6(_component_v_img, {
                  key: imgRequest.value.key,
                  src: displaySrc.value,
                  "aspect-ratio": 2 / 3,
                  eager: imgRequest.value.eager,
                  transition: imgRequest.value.transition,
                  cover: "",
                  class: "object-cover aspect-w-2 aspect-h-3",
                  onLoad: handleImageLoad,
                  onError: handleImageError
                }, {
                  placeholder: _withCtx$6(() => [
                    _createElementVNode$8("div", _hoisted_1$7, [
                      _createVNode$6(_component_v_skeleton_loader, { class: "sdas-poster-skeleton" })
                    ])
                  ]),
                  _: 1
                }, 8, ["src", "eager", "transition"])) : (_openBlock$a(), _createElementBlock$9("div", _hoisted_2$6, [
                  _createVNode$6(_component_v_icon, {
                    icon: "mdi-television-classic",
                    size: "64",
                    color: "medium-emphasis"
                  })
                ])),
                _withDirectives$1(_createVNode$6(_component_v_chip, {
                  variant: "elevated",
                  size: "small",
                  class: _normalizeClass$5([kindChipClass.value, "absolute left-2 top-2 bg-opacity-80 text-white font-bold"])
                }, {
                  default: _withCtx$6(() => [
                    _createTextVNode$5(_toDisplayString$7(kindLabel.value), 1)
                  ]),
                  _: 1
                }, 8, ["class"]), [
                  [_vShow$1, __props.loaded]
                ]),
                _withDirectives$1(_createElementVNode$8("div", _hoisted_3$6, [
                  __props.work.in_library === true && !activeState(isHovering) ? (_openBlock$a(), _createElementBlock$9("div", _hoisted_4$6, [..._cache[3] || (_cache[3] = [
                    _createElementVNode$8("div", { class: "relative inline-flex whitespace-nowrap rounded-full border-gray-700 font-semibold leading-5 ring-gray-700" }, [
                      _createElementVNode$8("div", { class: "rounded-full bg-opacity-80 w-5 border p-0 bg-green-500 border-green-400 ring-green-400 text-green-100" }, [
                        _createElementVNode$8("svg", {
                          xmlns: "http://www.w3.org/2000/svg",
                          viewBox: "0 0 20 20",
                          fill: "currentColor",
                          "aria-hidden": "true"
                        }, [
                          _createElementVNode$8("path", {
                            "fill-rule": "evenodd",
                            d: "M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z",
                            "clip-rule": "evenodd"
                          })
                        ])
                      ])
                    ], -1)
                  ])])) : badgeIsNew.value ? (_openBlock$a(), _createElementBlock$9("span", _hoisted_5$5, "NEW")) : badge.value ? (_openBlock$a(), _createBlock$6(_component_v_chip, {
                    key: 2,
                    variant: "elevated",
                    size: "small",
                    class: "bg-opacity-80 text-white font-bold border-purple-600 bg-purple-600",
                    title: badgeTitle.value
                  }, {
                    default: _withCtx$6(() => [
                      _createTextVNode$5(_toDisplayString$7(badge.value), 1)
                    ]),
                    _: 1
                  }, 8, ["title"])) : _createCommentVNode$a("", true)
                ], 512), [
                  [_vShow$1, __props.loaded]
                ]),
                !activeState(isHovering) ? _withDirectives$1((_openBlock$a(), _createBlock$6(_component_v_avatar, {
                  key: 2,
                  size: "24",
                  variant: "plain",
                  density: "compact",
                  tile: "",
                  class: "absolute bottom-1 right-1"
                }, {
                  default: _withCtx$6(() => [
                    _createVNode$6(_component_v_icon, {
                      size: "20",
                      color: "white"
                    }, {
                      default: _withCtx$6(() => [..._cache[4] || (_cache[4] = [
                        _createTextVNode$5("mdi-book-open-page-variant-outline", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 512)), [
                  [_vShow$1, __props.loaded && !imgFailed.value]
                ]) : subChip.value && !activeState(isHovering) ? (_openBlock$a(), _createBlock$6(_component_v_chip, {
                  key: 3,
                  variant: "elevated",
                  size: "x-small",
                  class: _normalizeClass$5(["absolute bottom-1 left-1 bg-opacity-80 text-white", subChip.value.cls]),
                  title: __props.work.sub_detail || subChip.value.label
                }, {
                  default: _withCtx$6(() => [
                    _createVNode$6(_component_v_icon, {
                      size: "12",
                      class: "mr-1"
                    }, {
                      default: _withCtx$6(() => [
                        _createTextVNode$5(_toDisplayString$7(subChip.value.icon), 1)
                      ]),
                      _: 1
                    }),
                    _createTextVNode$5(" " + _toDisplayString$7(subChip.value.label), 1)
                  ]),
                  _: 1
                }, 8, ["class", "title"])) : _createCommentVNode$a("", true),
                detailVisible(isHovering) ? (_openBlock$a(), _createElementBlock$9("div", {
                  key: 4,
                  class: "w-full h-full flex flex-col flex-wrap justify-end align-left text-white absolute bottom-0 cursor-pointer pa-2",
                  style: OVERLAY_STYLE
                }, [
                  _createElementVNode$8("span", _hoisted_6$5, _toDisplayString$7(__props.work.year || "—"), 1),
                  _createElementVNode$8("h1", _hoisted_7$5, _toDisplayString$7(__props.work.title), 1),
                  _createElementVNode$8("p", _hoisted_8$4, _toDisplayString$7(cardSummary(__props.work)), 1),
                  _createElementVNode$8("div", _hoisted_9$4, [
                    _createVNode$6(_component_v_btn, {
                      icon: "",
                      variant: "text",
                      size: "small",
                      title: "搜索资源（电影 + 电视剧全分类）",
                      onClick: _cache[0] || (_cache[0] = _withModifiers$1(($event) => emit("search", __props.work), ["stop"]))
                    }, {
                      default: _withCtx$6(() => [
                        _createVNode$6(_component_v_icon, {
                          size: "24",
                          color: "white"
                        }, {
                          default: _withCtx$6(() => [..._cache[5] || (_cache[5] = [
                            _createTextVNode$5("mdi-magnify", -1)
                          ])]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }),
                    _createVNode$6(_component_v_spacer),
                    _createVNode$6(_component_v_btn, {
                      icon: "",
                      variant: "text",
                      size: "small",
                      loading: props.searching === __props.work.media_id,
                      disabled: Boolean(props.searching),
                      title: "立即搜索一次（与订阅设置里的「立即搜索」同一动作）",
                      onClick: _cache[1] || (_cache[1] = _withModifiers$1(($event) => emit("search-now", __props.work), ["stop"]))
                    }, {
                      default: _withCtx$6(() => [
                        _createVNode$6(_component_v_icon, {
                          size: "24",
                          color: "white"
                        }, {
                          default: _withCtx$6(() => [..._cache[6] || (_cache[6] = [
                            _createTextVNode$5("mdi-download-outline", -1)
                          ])]),
                          _: 1
                        })
                      ]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode$6(_component_v_spacer),
                    _createVNode$6(_component_v_btn, {
                      icon: "",
                      variant: "text",
                      size: "small",
                      loading: props.subscribing === __props.work.media_id,
                      disabled: Boolean(props.subscribing),
                      color: __props.subscribed ? "error" : "white",
                      title: __props.subscribed ? "已订阅（点击取消）" : "加入订阅",
                      onClick: _cache[2] || (_cache[2] = _withModifiers$1(($event) => emit("subscribe", __props.work), ["stop"]))
                    }, {
                      default: _withCtx$6(() => [
                        props.subscribing !== __props.work.media_id ? (_openBlock$a(), _createBlock$6(_component_v_icon, {
                          key: 0,
                          size: "24",
                          color: __props.subscribed ? "error" : "white"
                        }, {
                          default: _withCtx$6(() => [
                            _createTextVNode$5(_toDisplayString$7(__props.subscribed ? "mdi-heart" : "mdi-heart-outline"), 1)
                          ]),
                          _: 1
                        }, 8, ["color"])) : _createCommentVNode$a("", true)
                      ]),
                      _: 1
                    }, 8, ["loading", "disabled", "color", "title"])
                  ])
                ])) : _createCommentVNode$a("", true)
              ]),
              _: 2
            }, 1032, ["data-glass-optical-mode", "class", "onClick"])
          ], 16)
        ]),
        _: 1
      });
    };
  }
});

const WorkCard = /* @__PURE__ */ _export_sfc(_sfc_main$a, [["__scopeId", "data-v-fcdda18f"]]);

const {defineComponent:_defineComponent$9} = await importShared('vue');

const {renderSlot:_renderSlot$3,createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$4,withCtx:_withCtx$5,createVNode:_createVNode$5,normalizeStyle:_normalizeStyle$4,openBlock:_openBlock$9,createBlock:_createBlock$5,createCommentVNode:_createCommentVNode$9,Teleport:_Teleport$2} = await importShared('vue');

const {onBeforeUnmount: onBeforeUnmount$1,onMounted: onMounted$7,ref: ref$7,watch: watch$6} = await importShared('vue');

const TOP_FLOOR = 72;
const _sfc_main$9 = /* @__PURE__ */ _defineComponent$9({
  __name: "StickyBack",
  props: {
    anchor: {},
    title: {}
  },
  emits: ["back"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const posStyle = ref$7({ top: `${TOP_FLOOR}px`, left: "12px" });
    let raf = 0;
    function sync() {
      const el = props.anchor;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      posStyle.value = {
        // 上限跟着面板走（没滚时贴面板左上），下限 TOP_FLOOR 保证不进宿主顶栏
        top: `${Math.max(TOP_FLOOR, Math.round(rect.top + 8))}px`,
        left: `${Math.max(8, Math.round(rect.left + 8))}px`
      };
    }
    function onScroll() {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        sync();
      });
    }
    onMounted$7(() => {
      sync();
      document.addEventListener("scroll", onScroll, true);
      window.addEventListener("resize", onScroll);
    });
    onBeforeUnmount$1(() => {
      document.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    });
    watch$6(() => props.anchor, sync);
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent$4("v-icon");
      const _component_v_btn = _resolveComponent$4("v-btn");
      return _openBlock$9(), _createBlock$5(_Teleport$2, { to: "body" }, [
        __props.anchor ? (_openBlock$9(), _createBlock$5(_component_v_btn, {
          key: 0,
          class: "sdas-sticky-back",
          style: _normalizeStyle$4(posStyle.value),
          icon: "",
          variant: "text",
          title: __props.title,
          onClick: _cache[0] || (_cache[0] = ($event) => emit("back"))
        }, {
          default: _withCtx$5(() => [
            _renderSlot$3(_ctx.$slots, "default", {}, () => [
              _createVNode$5(_component_v_icon, { size: "26" }, {
                default: _withCtx$5(() => [..._cache[1] || (_cache[1] = [
                  _createTextVNode$4("mdi-arrow-left", -1)
                ])]),
                _: 1
              })
            ], true)
          ]),
          _: 3
        }, 8, ["style", "title"])) : _createCommentVNode$9("", true)
      ]);
    };
  }
});

const StickyBack = /* @__PURE__ */ _export_sfc(_sfc_main$9, [["__scopeId", "data-v-06aa9a76"]]);

const {defineComponent:_defineComponent$8} = await importShared('vue');

const {normalizeStyle:_normalizeStyle$3,openBlock:_openBlock$8,createElementBlock:_createElementBlock$8,createCommentVNode:_createCommentVNode$8,renderSlot:_renderSlot$2,normalizeClass:_normalizeClass$4} = await importShared('vue');

const {computed: computed$7,onActivated: onActivated$1,onDeactivated: onDeactivated$1,onMounted: onMounted$6,onUnmounted: onUnmounted$4,ref: ref$6,shallowRef,watch: watch$5} = await importShared('vue');

const _sfc_main$8 = /* @__PURE__ */ _defineComponent$8({
  __name: "GlassMediaBackdrop",
  setup(__props) {
    const root = ref$6(null);
    const backdrop = shallowRef(null);
    const themeName = ref$6("");
    const reducedTransparency = ref$6(false);
    const supported = typeof CSS !== "undefined" && typeof CSS.supports === "function" && CSS.supports("clip-path", 'path("M0 0H1V1Z")') && CSS.supports("backdrop-filter", "blur(1px)");
    const enabled = computed$7(() => supported && themeName.value === "glass" && !reducedTransparency.value);
    const ownedCards = /* @__PURE__ */ new Set();
    let active = false;
    let frame = 0;
    let mutationObserver = null;
    let resizeObserver = null;
    let themeObserver = null;
    let transparencyMedia = null;
    function releaseCards() {
      for (const card of ownedCards) delete card.dataset.glassSharedBackdrop;
      ownedCards.clear();
      backdrop.value = null;
    }
    function isStationary(card, css) {
      if (card.classList.contains("app-hover-lift-card--hovering")) return false;
      if (css.transform === "none" || !css.transform) return true;
      return new DOMMatrixReadOnly(css.transform).isIdentity;
    }
    function cornerRadius(value, width, height) {
      const parts = value.split(" ");
      const parse = (part, size) => part.endsWith("%") ? parseFloat(part) * size / 100 : parseFloat(part);
      return [
        Math.min(width / 2, Math.max(0, parse(parts[0], width) || 0)),
        Math.min(height / 2, Math.max(0, parse(parts[1] ?? parts[0], height) || 0))
      ];
    }
    function update() {
      frame = 0;
      const container = root.value;
      if (!active || !enabled.value || !container || container.closest(".v-overlay__content")) {
        releaseCards();
        return;
      }
      const base = container.getBoundingClientRect();
      if (!base.width || !base.height) {
        releaseCards();
        return;
      }
      const nextCards = /* @__PURE__ */ new Set();
      const rects = [];
      let top = Infinity;
      let bottom = -Infinity;
      for (const card of container.querySelectorAll(".media-card")) {
        if (card.dataset.glassOpticalMode === "excluded") continue;
        const css = getComputedStyle(card);
        if (!isStationary(card, css)) continue;
        const box = card.getBoundingClientRect();
        if (!box.width || !box.height) continue;
        const x = box.left - base.left;
        const y = box.top - base.top;
        rects.push({
          x,
          y,
          w: box.width,
          h: box.height,
          corners: [
            css.borderTopLeftRadius,
            css.borderTopRightRadius,
            css.borderBottomRightRadius,
            css.borderBottomLeftRadius
          ].map((value) => cornerRadius(value, box.width, box.height))
        });
        top = Math.min(top, y);
        bottom = Math.max(bottom, y + box.height);
        nextCards.add(card);
      }
      const paths = rects.map(({ x, y: offsetY, w, h, corners: [tl, tr, br, bl] }) => {
        const y = offsetY - top;
        return `M${x + tl[0]} ${y}H${x + w - tr[0]}A${tr[0]} ${tr[1]} 0 0 1 ${x + w} ${y + tr[1]}V${y + h - br[1]}A${br[0]} ${br[1]} 0 0 1 ${x + w - br[0]} ${y + h}H${x + bl[0]}A${bl[0]} ${bl[1]} 0 0 1 ${x} ${y + h - bl[1]}V${y + tl[1]}A${tl[0]} ${tl[1]} 0 0 1 ${x + tl[0]} ${y}Z`;
      });
      const nextBackdrop = paths.length ? { clipPath: `path("${paths.join(" ")}")`, top: `${top}px`, height: `${bottom - top}px` } : null;
      if (nextBackdrop?.clipPath !== backdrop.value?.clipPath || nextBackdrop?.top !== backdrop.value?.top || nextBackdrop?.height !== backdrop.value?.height)
        backdrop.value = nextBackdrop;
      for (const card of ownedCards) {
        if (!nextCards.has(card)) delete card.dataset.glassSharedBackdrop;
      }
      ownedCards.clear();
      for (const card of nextCards) {
        if (card.dataset.glassSharedBackdrop !== "true") card.dataset.glassSharedBackdrop = "true";
        ownedCards.add(card);
      }
    }
    function schedule() {
      if (active && enabled.value && !frame) frame = requestAnimationFrame(update);
    }
    function stop() {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      mutationObserver?.disconnect();
      resizeObserver?.disconnect();
      themeObserver?.disconnect();
      mutationObserver = null;
      resizeObserver = null;
      themeObserver = null;
      releaseCards();
    }
    function readTheme() {
      if (typeof document === "undefined") return;
      themeName.value = document.documentElement.dataset.theme || "";
    }
    function start() {
      stop();
      if (!active || !enabled.value || !root.value) return;
      mutationObserver = new MutationObserver((records) => {
        if (records.some((record) => {
          if (record.type === "childList")
            return [...record.addedNodes, ...record.removedNodes].some(
              (node) => node instanceof Element && (node.matches(".media-card,[data-progressive-grid-index]") || node.querySelector(".media-card"))
            );
          return record.target instanceof Element && record.target.matches(".media-card,.progressive-card-grid__spacer");
        }))
          schedule();
      });
      mutationObserver.observe(root.value, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: ["data-glass-optical-mode", "class", "style"]
      });
      resizeObserver = new ResizeObserver(schedule);
      resizeObserver.observe(root.value);
      schedule();
    }
    onMounted$6(() => {
      active = true;
      readTheme();
      themeObserver = new MutationObserver(() => {
        readTheme();
        schedule();
      });
      themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-theme-radius"] });
      if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
        transparencyMedia = window.matchMedia("(prefers-reduced-transparency: reduce)");
        reducedTransparency.value = transparencyMedia.matches;
        transparencyMedia.addEventListener("change", (event) => {
          reducedTransparency.value = event.matches;
        });
      }
      start();
    });
    onActivated$1(() => {
      active = true;
      start();
    });
    onDeactivated$1(() => {
      active = false;
      stop();
    });
    onUnmounted$4(() => {
      active = false;
      stop();
    });
    watch$5(enabled, start, { flush: "post" });
    return (_ctx, _cache) => {
      return _openBlock$8(), _createElementBlock$8("div", {
        ref_key: "root",
        ref: root,
        class: _normalizeClass$4(["sdas-glass-backdrop", { "is-active": enabled.value }]),
        onTransitionend: schedule
      }, [
        backdrop.value ? (_openBlock$8(), _createElementBlock$8("div", {
          key: 0,
          class: "sdas-glass-sampling",
          style: _normalizeStyle$3(backdrop.value),
          "aria-hidden": "true",
          "data-glass-optical-mode": "excluded"
        }, null, 4)) : _createCommentVNode$8("", true),
        _renderSlot$2(_ctx.$slots, "default", {}, void 0, true)
      ], 34);
    };
  }
});

const GlassMediaBackdrop = /* @__PURE__ */ _export_sfc(_sfc_main$8, [["__scopeId", "data-v-6ac2ac91"]]);

const {defineComponent:_defineComponent$7} = await importShared('vue');

const {createElementVNode:_createElementVNode$7,toDisplayString:_toDisplayString$6,openBlock:_openBlock$7,createElementBlock:_createElementBlock$7,createCommentVNode:_createCommentVNode$7,createStaticVNode:_createStaticVNode$1} = await importShared('vue');

const _hoisted_1$6 = { class: "sdas-loading" };
const _hoisted_2$5 = { class: "sdas-loading-box" };
const _hoisted_3$5 = { class: "sdas-loading-inner" };
const _hoisted_4$5 = {
  key: 0,
  class: "sdas-loading-text"
};
const _sfc_main$7 = /* @__PURE__ */ _defineComponent$7({
  __name: "LoadingBanner",
  props: {
    text: {}
  },
  setup(__props) {
    return (_ctx, _cache) => {
      return _openBlock$7(), _createElementBlock$7("div", _hoisted_1$6, [
        _createElementVNode$7("div", _hoisted_2$5, [
          _createElementVNode$7("div", _hoisted_3$5, [
            _cache[0] || (_cache[0] = _createStaticVNode$1('<div class="sdas-wave" data-v-fe5657b5><div class="sdas-wave-dot" data-v-fe5657b5></div><div class="sdas-wave-dot" data-v-fe5657b5></div><div class="sdas-wave-dot" data-v-fe5657b5></div><div class="sdas-wave-dot" data-v-fe5657b5></div></div>', 1)),
            __props.text ? (_openBlock$7(), _createElementBlock$7("div", _hoisted_4$5, _toDisplayString$6(__props.text), 1)) : _createCommentVNode$7("", true)
          ])
        ])
      ]);
    };
  }
});

const LoadingBanner = /* @__PURE__ */ _export_sfc(_sfc_main$7, [["__scopeId", "data-v-fe5657b5"]]);

const {defineComponent:_defineComponent$6} = await importShared('vue');

const {createElementVNode:_createElementVNode$6,renderList:_renderList$6,Fragment:_Fragment$6,openBlock:_openBlock$6,createElementBlock:_createElementBlock$6,createCommentVNode:_createCommentVNode$6,toDisplayString:_toDisplayString$5,renderSlot:_renderSlot$1,createStaticVNode:_createStaticVNode} = await importShared('vue');

const _hoisted_1$5 = { class: "sdas-nodata" };
const _hoisted_2$4 = ["aria-label"];
const _hoisted_3$4 = {
  key: 0,
  class: "sdas-reel-holder",
  "aria-hidden": "true"
};
const _hoisted_4$4 = {
  key: 1,
  class: "sdas-code-digit",
  "aria-hidden": "true"
};
const _hoisted_5$4 = { class: "sdas-nodata-title" };
const _hoisted_6$4 = {
  key: 0,
  class: "sdas-nodata-desc"
};
const _hoisted_7$4 = {
  key: 1,
  class: "sdas-nodata-actions"
};
const {computed: computed$6} = await importShared('vue');

const _sfc_main$6 = /* @__PURE__ */ _defineComponent$6({
  __name: "NoDataFound",
  props: {
    errorCode: {},
    errorTitle: {},
    errorDescription: {}
  },
  setup(__props) {
    const props = __props;
    const codeChars = computed$6(() => (props.errorCode || "404").split(""));
    return (_ctx, _cache) => {
      return _openBlock$6(), _createElementBlock$6("div", _hoisted_1$5, [
        _createElementVNode$6("div", {
          class: "sdas-code",
          role: "img",
          "aria-label": __props.errorCode || "404"
        }, [
          _cache[1] || (_cache[1] = _createElementVNode$6("span", {
            class: "sdas-code-glow",
            "aria-hidden": "true"
          }, null, -1)),
          (_openBlock$6(true), _createElementBlock$6(_Fragment$6, null, _renderList$6(codeChars.value, (char, index) => {
            return _openBlock$6(), _createElementBlock$6(_Fragment$6, { key: index }, [
              char === "0" ? (_openBlock$6(), _createElementBlock$6("span", _hoisted_3$4, [..._cache[0] || (_cache[0] = [
                _createStaticVNode('<svg class="sdas-reel" viewBox="0 0 200 200" fill="none" data-v-b5ef75fa><circle cx="100" cy="100" r="88" class="sdas-reel-rim" data-v-b5ef75fa></circle><g class="sdas-reel-holes" data-v-b5ef75fa><circle cx="148" cy="100" r="18" data-v-b5ef75fa></circle><circle cx="124" cy="141.6" r="18" data-v-b5ef75fa></circle><circle cx="76" cy="141.6" r="18" data-v-b5ef75fa></circle><circle cx="52" cy="100" r="18" data-v-b5ef75fa></circle><circle cx="76" cy="58.4" r="18" data-v-b5ef75fa></circle><circle cx="124" cy="58.4" r="18" data-v-b5ef75fa></circle></g><circle cx="100" cy="100" r="11" class="sdas-reel-hub" data-v-b5ef75fa></circle></svg>', 1)
              ])])) : (_openBlock$6(), _createElementBlock$6("span", _hoisted_4$4, _toDisplayString$5(char), 1))
            ], 64);
          }), 128)),
          _cache[2] || (_cache[2] = _createElementVNode$6("span", {
            class: "sdas-film-chip is-a",
            "aria-hidden": "true"
          }, null, -1)),
          _cache[3] || (_cache[3] = _createElementVNode$6("span", {
            class: "sdas-film-chip is-b",
            "aria-hidden": "true"
          }, null, -1)),
          _cache[4] || (_cache[4] = _createElementVNode$6("span", {
            class: "sdas-film-chip is-c",
            "aria-hidden": "true"
          }, null, -1))
        ], 8, _hoisted_2$4),
        _createElementVNode$6("div", _hoisted_5$4, _toDisplayString$5(__props.errorTitle || "没有数据"), 1),
        __props.errorDescription ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_6$4, _toDisplayString$5(__props.errorDescription), 1)) : _createCommentVNode$6("", true),
        _ctx.$slots.button ? (_openBlock$6(), _createElementBlock$6("div", _hoisted_7$4, [
          _renderSlot$1(_ctx.$slots, "button", {}, void 0, true)
        ])) : _createCommentVNode$6("", true)
      ]);
    };
  }
});

const NoDataFound = /* @__PURE__ */ _export_sfc(_sfc_main$6, [["__scopeId", "data-v-b5ef75fa"]]);

const {defineComponent:_defineComponent$5} = await importShared('vue');

const {createElementVNode:_createElementVNode$5,openBlock:_openBlock$5,createElementBlock:_createElementBlock$5,createCommentVNode:_createCommentVNode$5,resolveComponent:_resolveComponent$3,createVNode:_createVNode$4,toDisplayString:_toDisplayString$4,createBlock:_createBlock$4,createTextVNode:_createTextVNode$3,withCtx:_withCtx$4,unref:_unref$2,normalizeClass:_normalizeClass$3,renderList:_renderList$5,Fragment:_Fragment$5} = await importShared('vue');

const _hoisted_1$4 = { class: "sdas-actor-bar" };
const _hoisted_2$3 = {
  key: 0,
  class: "text-body-2 text-medium-emphasis ml-3"
};
const _hoisted_3$3 = {
  key: 1,
  class: "text-body-2 text-medium-emphasis ml-3"
};
const _hoisted_4$3 = {
  key: 2,
  class: "text-body-2 text-medium-emphasis"
};
const _hoisted_5$3 = { class: "sdas-actor-head" };
const _hoisted_6$3 = { class: "sdas-actor-meta" };
const _hoisted_7$3 = { class: "sdas-actor-name" };
const _hoisted_8$3 = { class: "sdas-actor-sub" };
const _hoisted_9$3 = { key: 0 };
const _hoisted_10$3 = { key: 1 };
const _hoisted_11$3 = {
  key: 0,
  class: "sdas-actor-bio"
};
const _hoisted_12$3 = {
  key: 1,
  class: "sdas-actor-facts"
};
const _hoisted_13$3 = { class: "sdas-actor-fact-label" };
const _hoisted_14$3 = { class: "sdas-actor-fact-value" };
const _hoisted_15$3 = {
  key: 2,
  class: "sdas-actor-line"
};
const _hoisted_16$3 = {
  key: 3,
  class: "sdas-actor-line sdas-actor-rep"
};
const _hoisted_17$3 = { class: "sdas-rep-list" };
const _hoisted_18$3 = ["title", "onClick"];
const _hoisted_19$3 = ["title"];
const _hoisted_20$3 = {
  key: 4,
  class: "sdas-actor-line"
};
const _hoisted_21$2 = { class: "sdas-actor-actions" };
const _hoisted_22$2 = { class: "sdas-actor-credits" };
const _hoisted_23$2 = { class: "slider-header sdas-credits-head" };
const _hoisted_24$2 = { class: "slider-title" };
const _hoisted_25$2 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_26$2 = { class: "sdas-credits-grid" };
const _hoisted_27$2 = { key: 1 };
const {computed: computed$5,nextTick: nextTick$2,onMounted: onMounted$5,onUnmounted: onUnmounted$3,reactive: reactive$2,ref: ref$5,watch: watch$4} = await importShared('vue');
const WORKS_PAGE_SIZE = 24;
const _sfc_main$5 = /* @__PURE__ */ _defineComponent$5({
  __name: "ActorDetail",
  props: {
    api: {},
    actor: {},
    subscribed: { type: Boolean },
    busyFollow: { type: Boolean },
    subscribedIds: {},
    busySubscribeAll: { type: Boolean }
  },
  emits: ["back", "search", "subscribe", "open-work", "search-rep", "toggle-actor", "subscribe-all"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const pageRoot = ref$5(null);
    const props = __props;
    const emit = __emit;
    const detail = ref$5(null);
    const loaded = ref$5(false);
    const failed = ref$5(false);
    const hint = ref$5("");
    let hintTimer = null;
    const avatarLoaded = ref$5(false);
    const loadedKeys = reactive$2(/* @__PURE__ */ new Set());
    const fallback = computed$5(() => ({
      found: true,
      actor_id: String(props.actor?.actor_id || ""),
      media_id: String(props.actor?.media_id || ""),
      name: String(props.actor?.name || ""),
      profile: String(props.actor?.profile || ""),
      bio: String(props.actor?.bio || ""),
      job_title: String(props.actor?.job_title || ""),
      gender: String(props.actor?.gender || ""),
      nationality: String(props.actor?.nationality || ""),
      url: String(props.actor?.url || ""),
      works_count: Number(props.actor?.works_count || 0),
      total: 0,
      in_library_count: 0,
      library_known: 0,
      subscribed: Boolean(props.subscribed),
      works: []
    }));
    const view = computed$5(
      () => detail.value?.found ? detail.value : props.actor ? fallback.value : null
    );
    const missing = computed$5(() => Boolean(detail.value) && !detail.value?.found);
    const works = ref$5([]);
    const worksTotal = ref$5(0);
    const worksHasMore = ref$5(false);
    const worksLoading = ref$5(false);
    let worksPage = 0;
    let worksFailures = 0;
    const worksSentinel = ref$5(null);
    let worksObserver = null;
    function observeWorksSentinel() {
      if (!worksObserver) return;
      worksObserver.disconnect();
      if (worksSentinel.value) worksObserver.observe(worksSentinel.value);
    }
    const subLine = computed$5(() => {
      const parts = [];
      const job = String(view.value?.job_title || "").trim();
      const nationality = String(view.value?.nationality || "").trim();
      if (job) parts.push(job);
      if (nationality) parts.push(nationality);
      return parts.join(" | ");
    });
    const facts = computed$5(() => {
      const data = view.value;
      if (!data) return [];
      const rows = [];
      const birth = String(data.birth_date || "").trim() || String(data.birth_year || "").trim();
      if (birth) rows.push({ label: "生日", value: birth });
      if (data.birth_place) rows.push({ label: "出生地", value: data.birth_place });
      if (data.height_cm) rows.push({ label: "身高", value: `${data.height_cm} cm` });
      if (data.weight_kg) rows.push({ label: "体重", value: `${data.weight_kg} kg` });
      if (data.constellation) rows.push({ label: "星座", value: data.constellation });
      if (data.education) rows.push({ label: "院校", value: data.education });
      const followers = formatCount(data.followers);
      if (followers) rows.push({ label: "粉丝", value: followers });
      const likes = formatCount(data.likes);
      if (likes) rows.push({ label: "获赞", value: likes });
      return rows;
    });
    const repWorks = computed$5(() => view.value?.rep_works || []);
    const repLeftover = computed$5(() => {
      const raw = String(view.value?.rep_text || "").trim();
      if (!raw) return "";
      let rest = raw;
      for (const work of repWorks.value) {
        const title = String(work.title || "").trim();
        if (title) rest = rest.replace(title, "");
      }
      return rest.replace(/[\s、,，;；/|]+/g, " ").trim();
    });
    const hobbiesLine = computed$5(() => (view.value?.hobbies || []).join("、"));
    function formatCount(value) {
      const num = Number(value || 0);
      if (!num) return "";
      if (num >= 1e8) return `${(num / 1e8).toFixed(1)} 亿`;
      if (num >= 1e4) return `${(num / 1e4).toFixed(1)} 万`;
      return String(num);
    }
    const creditLine = computed$5(() => {
      const data = view.value;
      if (!data) return "";
      const total = Number(data.works_count || 0) || worksTotal.value;
      if (!total) return "";
      const parts = [`参演 ${total} 部短剧`];
      if (data.library_known > 0) parts.push(`已入库 ${data.in_library_count} 部`);
      return parts.join(" · ");
    });
    const creditSummary = computed$5(() => {
      const data = view.value;
      const total = worksTotal.value || Number(data?.works_count || 0);
      if (!loaded.value && !total) return "正在取作品…";
      const parts = [`共 ${total} 部`];
      if (data && data.library_known > 0) {
        parts.push(`入库 ${data.in_library_count} 部`);
        if (data.library_known < total) parts.push(`判定 ${data.library_known} 部`);
      }
      return parts.join(" · ");
    });
    function markPoster(key) {
      loadedKeys.add(key);
    }
    function toast(text) {
      hint.value = text;
      if (hintTimer) clearTimeout(hintTimer);
      hintTimer = setTimeout(() => {
        hint.value = "";
      }, 4e3);
    }
    function actorIdOf() {
      return String(props.actor?.actor_id || "");
    }
    function actorNameOf() {
      return String(props.actor?.name || "");
    }
    function applyWorksPage(data, append) {
      const pageWorks = data.works || [];
      if (append) {
        const seen = new Set(works.value.map((item) => item.key));
        works.value = [...works.value, ...pageWorks.filter((item) => !seen.has(item.key))];
      } else {
        works.value = pageWorks;
      }
      worksTotal.value = Number(data.works_total ?? data.total ?? works.value.length) || 0;
      worksHasMore.value = typeof data.has_more === "boolean" ? data.has_more : works.value.length < worksTotal.value;
      worksPage = Number(data.works_page || (append ? worksPage : 1)) || 1;
    }
    async function loadMoreWorks() {
      if (worksLoading.value || !worksHasMore.value) return;
      const actorId = actorIdOf();
      const name = actorNameOf();
      if (!actorId && !name) return;
      worksLoading.value = true;
      try {
        const data = await fetchActorDetail(props, actorId, name, worksPage + 1, WORKS_PAGE_SIZE);
        applyWorksPage(data, true);
        worksFailures = 0;
      } catch (err) {
        worksFailures += 1;
        console.error("[ShortDramaActorSubscribe] 续拉作品失败", err);
        if (worksFailures >= 3) worksHasMore.value = false;
      } finally {
        worksLoading.value = false;
        await nextTick$2();
        observeWorksSentinel();
      }
    }
    async function load() {
      const actorId = actorIdOf();
      const name = actorNameOf();
      loaded.value = false;
      failed.value = false;
      worksLoading.value = false;
      worksFailures = 0;
      worksPage = 0;
      works.value = [];
      worksTotal.value = 0;
      worksHasMore.value = false;
      if (!actorId && !name) {
        failed.value = true;
        loaded.value = true;
        return;
      }
      try {
        const data = await fetchActorDetail(props, actorId, name, 1, WORKS_PAGE_SIZE);
        detail.value = data;
        if (data.found) applyWorksPage(data, false);
      } catch (err) {
        console.error("[ShortDramaActorSubscribe] 演员详情加载失败", err);
        detail.value = null;
        failed.value = true;
      } finally {
        loaded.value = true;
        await nextTick$2();
        observeWorksSentinel();
      }
    }
    watch$4(
      () => String(props.actor?.actor_id || props.actor?.name || ""),
      () => {
        detail.value = null;
        loaded.value = false;
        failed.value = false;
        avatarLoaded.value = false;
        loadedKeys.clear();
        works.value = [];
        worksTotal.value = 0;
        worksHasMore.value = false;
        worksPage = 0;
        load();
      },
      { immediate: true }
    );
    onMounted$5(() => {
      if (typeof IntersectionObserver === "undefined") return;
      worksObserver = new IntersectionObserver(
        (entries) => {
          if (!entries.some((entry) => entry.isIntersecting)) return;
          void loadMoreWorks();
        },
        { rootMargin: "800px 0px" }
      );
      observeWorksSentinel();
    });
    onUnmounted$3(() => {
      worksObserver?.disconnect();
      worksObserver = null;
      if (hintTimer) clearTimeout(hintTimer);
    });
    __expose({ toast });
    return (_ctx, _cache) => {
      const _component_v_spacer = _resolveComponent$3("v-spacer");
      const _component_v_btn = _resolveComponent$3("v-btn");
      const _component_v_img = _resolveComponent$3("v-img");
      const _component_v_icon = _resolveComponent$3("v-icon");
      const _component_v_avatar = _resolveComponent$3("v-avatar");
      const _component_v_progress_circular = _resolveComponent$3("v-progress-circular");
      return _openBlock$5(), _createElementBlock$5("div", {
        ref_key: "pageRoot",
        ref: pageRoot,
        class: "sdas-actor"
      }, [
        _createElementVNode$5("div", _hoisted_1$4, [
          _cache[6] || (_cache[6] = _createElementVNode$5("span", { class: "text-body-2 text-medium-emphasis" }, "演员作品", -1)),
          !loaded.value ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_2$3, " 正在从短剧百科取档案与作品… ")) : missing.value ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_3$3, " 百科里没有这位演员的档案 ")) : _createCommentVNode$5("", true),
          _createVNode$4(_component_v_spacer),
          hint.value ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_4$3, _toDisplayString$4(hint.value), 1)) : _createCommentVNode$5("", true)
        ]),
        !loaded.value ? (_openBlock$5(), _createBlock$4(LoadingBanner, { key: 0 })) : failed.value ? (_openBlock$5(), _createBlock$4(NoDataFound, {
          key: 1,
          "error-code": "500",
          "error-title": "出错啦！",
          "error-description": "无法获取到媒体信息，请检查网络连接。"
        }, {
          button: _withCtx$4(() => [
            _createVNode$4(_component_v_btn, {
              "prepend-icon": "mdi-refresh",
              variant: "tonal",
              onClick: _cache[0] || (_cache[0] = ($event) => load())
            }, {
              default: _withCtx$4(() => [..._cache[7] || (_cache[7] = [
                _createTextVNode$3("重试", -1)
              ])]),
              _: 1
            })
          ]),
          _: 1
        })) : !view.value ? (_openBlock$5(), _createBlock$4(NoDataFound, {
          key: 2,
          "error-code": "404",
          "error-title": `百科里没有「${__props.actor.name}」的档案`,
          "error-description": "短剧百科只收录站上有的演员和作品"
        }, null, 8, ["error-title"])) : (_openBlock$5(), _createElementBlock$5(_Fragment$5, { key: 3 }, [
          _createElementVNode$5("div", _hoisted_5$3, [
            _createVNode$4(_component_v_avatar, {
              class: _normalizeClass$3(["sdas-actor-avatar", { "ring-1 ring-gray-700": avatarLoaded.value }]),
              size: "200"
            }, {
              default: _withCtx$4(() => [
                view.value.profile ? (_openBlock$5(), _createBlock$4(_component_v_img, {
                  key: 0,
                  src: _unref$2(proxyImage)(view.value.profile),
                  cover: "",
                  onLoad: _cache[1] || (_cache[1] = ($event) => avatarLoaded.value = true)
                }, null, 8, ["src"])) : (_openBlock$5(), _createBlock$4(_component_v_icon, {
                  key: 1,
                  size: "72",
                  color: "medium-emphasis"
                }, {
                  default: _withCtx$4(() => [..._cache[8] || (_cache[8] = [
                    _createTextVNode$3("mdi-account-outline", -1)
                  ])]),
                  _: 1
                }))
              ]),
              _: 1
            }, 8, ["class"]),
            _createElementVNode$5("div", _hoisted_6$3, [
              _createElementVNode$5("h1", _hoisted_7$3, _toDisplayString$4(view.value.name), 1),
              _createElementVNode$5("div", _hoisted_8$3, [
                subLine.value ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_9$3, _toDisplayString$4(subLine.value), 1)) : _createCommentVNode$5("", true),
                creditLine.value ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_10$3, _toDisplayString$4(creditLine.value), 1)) : _createCommentVNode$5("", true)
              ])
            ])
          ]),
          view.value.bio ? (_openBlock$5(), _createElementBlock$5("p", _hoisted_11$3, _toDisplayString$4(view.value.bio), 1)) : _createCommentVNode$5("", true),
          facts.value.length ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_12$3, [
            (_openBlock$5(true), _createElementBlock$5(_Fragment$5, null, _renderList$5(facts.value, (fact) => {
              return _openBlock$5(), _createElementBlock$5("div", {
                key: fact.label,
                class: "sdas-actor-fact"
              }, [
                _createElementVNode$5("span", _hoisted_13$3, _toDisplayString$4(fact.label), 1),
                _createElementVNode$5("span", _hoisted_14$3, _toDisplayString$4(fact.value), 1)
              ]);
            }), 128))
          ])) : _createCommentVNode$5("", true),
          hobbiesLine.value ? (_openBlock$5(), _createElementBlock$5("p", _hoisted_15$3, [
            _cache[9] || (_cache[9] = _createElementVNode$5("span", { class: "sdas-actor-line-label" }, "爱好", -1)),
            _createTextVNode$3(_toDisplayString$4(hobbiesLine.value), 1)
          ])) : _createCommentVNode$5("", true),
          repWorks.value.length || repLeftover.value ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_16$3, [
            _cache[11] || (_cache[11] = _createElementVNode$5("span", { class: "sdas-actor-line-label" }, "代表作", -1)),
            _createElementVNode$5("span", _hoisted_17$3, [
              (_openBlock$5(true), _createElementBlock$5(_Fragment$5, null, _renderList$5(repWorks.value, (work) => {
                return _openBlock$5(), _createElementBlock$5("button", {
                  key: `rep:${work.key}`,
                  type: "button",
                  class: "sdas-rep-item",
                  title: `打开《${work.title}》的详情`,
                  onClick: ($event) => emit("open-work", work)
                }, _toDisplayString$4(work.title), 9, _hoisted_18$3);
              }), 128)),
              repLeftover.value ? (_openBlock$5(), _createElementBlock$5("button", {
                key: 0,
                type: "button",
                class: "sdas-rep-item sdas-rep-search",
                title: `《${repLeftover.value}》在短剧百科里没有条目（百科把几部剧名连写在一起），点击去资源搜索`,
                onClick: _cache[2] || (_cache[2] = ($event) => emit("search-rep", repLeftover.value))
              }, [
                _createVNode$4(_component_v_icon, {
                  class: "sdas-rep-search-icon",
                  size: "13"
                }, {
                  default: _withCtx$4(() => [..._cache[10] || (_cache[10] = [
                    _createTextVNode$3("mdi-magnify", -1)
                  ])]),
                  _: 1
                }),
                _createTextVNode$3(" " + _toDisplayString$4(repLeftover.value), 1)
              ], 8, _hoisted_19$3)) : _createCommentVNode$5("", true)
            ])
          ])) : view.value.rep_text ? (_openBlock$5(), _createElementBlock$5("p", _hoisted_20$3, [
            _cache[12] || (_cache[12] = _createElementVNode$5("span", { class: "sdas-actor-line-label" }, "代表作", -1)),
            _createTextVNode$3(_toDisplayString$4(view.value.rep_text), 1)
          ])) : _createCommentVNode$5("", true),
          _createElementVNode$5("div", _hoisted_21$2, [
            _createVNode$4(_component_v_btn, {
              class: "sdas-actor-action-btn",
              variant: "tonal",
              color: __props.subscribed ? "error" : "primary",
              "prepend-icon": __props.subscribed ? "mdi-account-remove" : "mdi-account-plus",
              loading: __props.busyFollow,
              onClick: _cache[3] || (_cache[3] = ($event) => emit("toggle-actor"))
            }, {
              default: _withCtx$4(() => [
                _createTextVNode$3(_toDisplayString$4(__props.subscribed ? "取消关注" : "关注该演员"), 1)
              ]),
              _: 1
            }, 8, ["color", "prepend-icon", "loading"]),
            _createVNode$4(_component_v_btn, {
              class: "sdas-actor-action-btn",
              variant: "tonal",
              color: "primary",
              "prepend-icon": "mdi-playlist-plus",
              loading: __props.busySubscribeAll,
              disabled: __props.busySubscribeAll || !worksTotal.value,
              title: "把这名演员的全部作品提交给订阅系统（跳过已订阅与已在库）",
              onClick: _cache[4] || (_cache[4] = ($event) => emit("subscribe-all"))
            }, {
              default: _withCtx$4(() => [..._cache[13] || (_cache[13] = [
                _createTextVNode$3(" 订阅全部作品 ", -1)
              ])]),
              _: 1
            }, 8, ["loading", "disabled"])
          ]),
          _createElementVNode$5("div", _hoisted_22$2, [
            _createElementVNode$5("div", _hoisted_23$2, [
              _createElementVNode$5("span", _hoisted_24$2, [
                _cache[14] || (_cache[14] = _createElementVNode$5("span", null, "参演作品", -1)),
                _createVNode$4(_component_v_icon, {
                  icon: "mdi-arrow-right-circle-outline",
                  size: "18",
                  class: "ms-1"
                })
              ]),
              _createVNode$4(_component_v_spacer),
              _createElementVNode$5("span", _hoisted_25$2, _toDisplayString$4(creditSummary.value), 1)
            ]),
            works.value.length ? (_openBlock$5(), _createBlock$4(GlassMediaBackdrop, { key: 0 }, {
              default: _withCtx$4(() => [
                _createElementVNode$5("div", _hoisted_26$2, [
                  (_openBlock$5(true), _createElementBlock$5(_Fragment$5, null, _renderList$5(works.value, (work) => {
                    return _openBlock$5(), _createBlock$4(WorkCard, {
                      key: work.key,
                      work,
                      loaded: loadedKeys.has(work.key),
                      subscribed: __props.subscribedIds.has(work.media_id),
                      onPoster: ($event) => markPoster(work.key),
                      onOpen: ($event) => emit("open-work", work),
                      onSearch: ($event) => emit("search", work),
                      onSubscribe: ($event) => emit("subscribe", work)
                    }, null, 8, ["work", "loaded", "subscribed", "onPoster", "onOpen", "onSearch", "onSubscribe"]);
                  }), 128))
                ])
              ]),
              _: 1
            })) : (_openBlock$5(), _createBlock$4(NoDataFound, {
              key: 1,
              "error-code": "404",
              "error-title": `百科里没有「${view.value.name}」的作品记录`
            }, null, 8, ["error-title"])),
            _createElementVNode$5("div", {
              ref_key: "worksSentinel",
              ref: worksSentinel,
              class: "sdas-credits-sentinel"
            }, [
              worksLoading.value ? (_openBlock$5(), _createBlock$4(_component_v_progress_circular, {
                key: 0,
                indeterminate: "",
                size: "20",
                width: "2"
              })) : works.value.length && !worksHasMore.value ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_27$2, " 已到末尾 · 共 " + _toDisplayString$4(worksTotal.value) + " 部 ", 1)) : _createCommentVNode$5("", true)
            ], 512)
          ])
        ], 64)),
        _createVNode$4(StickyBack, {
          anchor: pageRoot.value,
          title: "返回",
          onBack: _cache[5] || (_cache[5] = ($event) => emit("back"))
        }, null, 8, ["anchor"])
      ], 512);
    };
  }
});

const ActorDetail = /* @__PURE__ */ _export_sfc(_sfc_main$5, [["__scopeId", "data-v-48e778cf"]]);

const {defineComponent:_defineComponent$4} = await importShared('vue');

const {createElementVNode:_createElementVNode$4,resolveComponent:_resolveComponent$2,createVNode:_createVNode$3,openBlock:_openBlock$4,createElementBlock:_createElementBlock$4,createCommentVNode:_createCommentVNode$4,unref:_unref$1,createBlock:_createBlock$3,createTextVNode:_createTextVNode$2,withCtx:_withCtx$3,toDisplayString:_toDisplayString$3,renderList:_renderList$4,Fragment:_Fragment$4} = await importShared('vue');

const _hoisted_1$3 = { class: "sdas-adapted-bar" };
const _hoisted_2$2 = {
  key: 0,
  class: "sdas-adapted-loading"
};
const _hoisted_3$2 = {
  key: 1,
  class: "sdas-adapted-empty-tip"
};
const _hoisted_4$2 = {
  key: 2,
  class: "sdas-adapted-head"
};
const _hoisted_5$2 = { class: "sdas-adapted-cover" };
const _hoisted_6$2 = {
  key: 1,
  class: "sdas-adapted-cover-empty"
};
const _hoisted_7$2 = { class: "sdas-adapted-meta" };
const _hoisted_8$2 = { class: "sdas-adapted-name" };
const _hoisted_9$2 = { class: "sdas-adapted-sub" };
const _hoisted_10$2 = { key: 0 };
const _hoisted_11$2 = {
  key: 1,
  class: "mx-1"
};
const _hoisted_12$2 = { key: 2 };
const _hoisted_13$2 = {
  key: 0,
  class: "sdas-adapted-genres"
};
const _hoisted_14$2 = { class: "sdas-adapted-text" };
const _hoisted_15$2 = { class: "sdas-adapted-credits" };
const _hoisted_16$2 = { class: "slider-header sdas-adapted-credits-head" };
const _hoisted_17$2 = { class: "slider-title" };
const _hoisted_18$2 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_19$2 = { class: "sdas-adapted-grid" };
const _hoisted_20$2 = {
  key: 1,
  class: "sdas-adapted-empty"
};
const {computed: computed$4,onMounted: onMounted$4,reactive: reactive$1,ref: ref$4} = await importShared('vue');
const _sfc_main$4 = /* @__PURE__ */ _defineComponent$4({
  __name: "AdaptedDetail",
  props: {
    api: {},
    novel: {},
    mediaId: {},
    subscribedIds: {}
  },
  emits: ["back", "open-work", "search", "subscribe"],
  setup(__props, { emit: __emit }) {
    const pageRoot = ref$4(null);
    const props = __props;
    const emit = __emit;
    const EMPTY_INFO = {
      title: "",
      author: "",
      url: "",
      poster: "",
      media_id: "",
      words: 0,
      genres: [],
      summary: "",
      works: []
    };
    const local = ref$4(null);
    const loading = ref$4(false);
    const view = computed$4(() => {
      const base = props.novel || EMPTY_INFO;
      const extra = local.value;
      if (!extra) return base;
      return {
        title: base.title || extra.title,
        author: base.author || extra.author,
        url: base.url || extra.url,
        poster: base.poster || extra.poster,
        media_id: base.media_id || extra.media_id,
        words: base.words || extra.words,
        genres: base.genres?.length ? base.genres : extra.genres,
        summary: base.summary || extra.summary,
        works: base.works?.length ? base.works : extra.works
      };
    });
    onMounted$4(async () => {
      const novelId = String(props.novel?.media_id || "").trim();
      const mediaId = String(props.mediaId || "").trim();
      const needFill = !props.novel?.title || !props.novel?.works?.length;
      if (!needFill) return;
      if (!novelId && !mediaId) return;
      loading.value = true;
      try {
        if (novelId) {
          local.value = await fetchAdaptedDetail({ api: props.api }, novelId);
        } else if (!props.novel?.title) {
          local.value = await fetchAdaptedInfo({ api: props.api }, mediaId);
        }
      } finally {
        loading.value = false;
      }
    });
    const loadedKeys = reactive$1(/* @__PURE__ */ new Set());
    function markPoster(key) {
      loadedKeys.add(key);
    }
    const wordsText = computed$4(() => {
      const words = Number(view.value.words || 0);
      if (!words) return "";
      if (words >= 1e4) return `约 ${(words / 1e4).toFixed(1)} 万字`;
      return `${words} 字`;
    });
    const works = computed$4(
      () => (view.value.works || []).filter((item) => item.title).map((item) => ({
        key: `${item.media_id || item.title}|${item.release_date.slice(0, 4)}`,
        title: item.title,
        year: item.release_date.slice(0, 4),
        type: "电视剧",
        media_source: "djbaike",
        media_id: item.media_id,
        poster: item.poster,
        vote: 0,
        episode_count: item.episodes,
        url: item.url,
        genres: item.genres,
        heat: 0,
        play_count: 0,
        studio: "",
        platform: "",
        kind: "",
        release_date: item.release_date,
        actor: "",
        actor_key: "",
        first_seen: "",
        is_new: false
      }))
    );
    return (_ctx, _cache) => {
      const _component_v_spacer = _resolveComponent$2("v-spacer");
      const _component_v_progress_circular = _resolveComponent$2("v-progress-circular");
      const _component_v_img = _resolveComponent$2("v-img");
      const _component_v_icon = _resolveComponent$2("v-icon");
      return _openBlock$4(), _createElementBlock$4("div", {
        ref_key: "pageRoot",
        ref: pageRoot,
        class: "sdas-adapted"
      }, [
        _createElementVNode$4("div", _hoisted_1$3, [
          _cache[1] || (_cache[1] = _createElementVNode$4("span", { class: "text-body-2 text-medium-emphasis" }, "原著", -1)),
          _createVNode$3(_component_v_spacer)
        ]),
        !view.value.title && loading.value ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_2$2, [
          _createVNode$3(_component_v_progress_circular, {
            indeterminate: "",
            size: "22",
            width: "2"
          }),
          _cache[2] || (_cache[2] = _createElementVNode$4("span", { class: "text-body-2 text-medium-emphasis ml-2" }, "正在取原著信息…", -1))
        ])) : !view.value.title ? (_openBlock$4(), _createElementBlock$4("p", _hoisted_3$2, " 站点没有登记这部剧的原著信息。 ")) : _createCommentVNode$4("", true),
        view.value.title ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_4$2, [
          _createElementVNode$4("div", _hoisted_5$2, [
            view.value.poster ? (_openBlock$4(), _createBlock$3(_component_v_img, {
              key: 0,
              class: "sdas-adapted-cover-img",
              src: _unref$1(proxyImage)(view.value.poster),
              cover: ""
            }, null, 8, ["src"])) : (_openBlock$4(), _createElementBlock$4("div", _hoisted_6$2, [
              _createVNode$3(_component_v_icon, {
                size: "48",
                color: "medium-emphasis"
              }, {
                default: _withCtx$3(() => [..._cache[3] || (_cache[3] = [
                  _createTextVNode$2("mdi-book-open-page-variant-outline", -1)
                ])]),
                _: 1
              })
            ]))
          ]),
          _createElementVNode$4("div", _hoisted_7$2, [
            _createElementVNode$4("h1", _hoisted_8$2, _toDisplayString$3(view.value.title), 1),
            _createElementVNode$4("div", _hoisted_9$2, [
              view.value.author ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_10$2, _toDisplayString$3(view.value.author), 1)) : _createCommentVNode$4("", true),
              view.value.author && wordsText.value ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_11$2, "|")) : _createCommentVNode$4("", true),
              wordsText.value ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_12$2, _toDisplayString$3(wordsText.value), 1)) : _createCommentVNode$4("", true)
            ]),
            view.value.genres.length ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_13$2, [
              (_openBlock$4(true), _createElementBlock$4(_Fragment$4, null, _renderList$4(view.value.genres, (genre) => {
                return _openBlock$4(), _createElementBlock$4("span", {
                  key: genre,
                  class: "sdas-adapted-genre"
                }, _toDisplayString$3(genre), 1);
              }), 128))
            ])) : _createCommentVNode$4("", true)
          ])
        ])) : _createCommentVNode$4("", true),
        view.value.summary ? (_openBlock$4(), _createElementBlock$4(_Fragment$4, { key: 3 }, [
          _cache[4] || (_cache[4] = _createElementVNode$4("h2", { class: "sdas-adapted-h2" }, "简介", -1)),
          _createElementVNode$4("p", _hoisted_14$2, _toDisplayString$3(view.value.summary), 1)
        ], 64)) : _createCommentVNode$4("", true),
        _createElementVNode$4("div", _hoisted_15$2, [
          _createElementVNode$4("div", _hoisted_16$2, [
            _createElementVNode$4("span", _hoisted_17$2, [
              _cache[5] || (_cache[5] = _createElementVNode$4("span", null, "改编作品", -1)),
              _createVNode$3(_component_v_icon, {
                icon: "mdi-arrow-right-circle-outline",
                size: "18",
                class: "ms-1"
              })
            ]),
            _createVNode$3(_component_v_spacer),
            _createElementVNode$4("span", _hoisted_18$2, "共 " + _toDisplayString$3(works.value.length) + " 部", 1)
          ]),
          works.value.length ? (_openBlock$4(), _createBlock$3(GlassMediaBackdrop, { key: 0 }, {
            default: _withCtx$3(() => [
              _createElementVNode$4("div", _hoisted_19$2, [
                (_openBlock$4(true), _createElementBlock$4(_Fragment$4, null, _renderList$4(works.value, (work) => {
                  return _openBlock$4(), _createBlock$3(WorkCard, {
                    key: work.key,
                    work,
                    loaded: loadedKeys.has(work.key),
                    subscribed: __props.subscribedIds.has(work.media_id),
                    onPoster: ($event) => markPoster(work.key),
                    onOpen: ($event) => emit("open-work", work),
                    onSearch: ($event) => emit("search", work),
                    onSubscribe: ($event) => emit("subscribe", work)
                  }, null, 8, ["work", "loaded", "subscribed", "onPoster", "onOpen", "onSearch", "onSubscribe"]);
                }), 128))
              ])
            ]),
            _: 1
          })) : (_openBlock$4(), _createElementBlock$4("p", _hoisted_20$2, "站点没有登记这本书的改编作品。"))
        ]),
        _createVNode$3(StickyBack, {
          anchor: pageRoot.value,
          title: "返回",
          onBack: _cache[0] || (_cache[0] = ($event) => emit("back"))
        }, null, 8, ["anchor"])
      ], 512);
    };
  }
});

const AdaptedDetail = /* @__PURE__ */ _export_sfc(_sfc_main$4, [["__scopeId", "data-v-2c6378b9"]]);

const {defineComponent:_defineComponent$3} = await importShared('vue');

const {openBlock:_openBlock$3,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$3,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$2,createVNode:_createVNode$2,unref:_unref,createElementBlock:_createElementBlock$3,createElementVNode:_createElementVNode$3,toDisplayString:_toDisplayString$2,Fragment:_Fragment$3,renderList:_renderList$3,normalizeClass:_normalizeClass$2,vShow:_vShow,withModifiers:_withModifiers,withDirectives:_withDirectives} = await importShared('vue');

const _hoisted_1$2 = {
  key: 0,
  class: "sdas-detail-back sdas-detail-back-image",
  "aria-hidden": "true"
};
const _hoisted_2$1 = {
  key: 1,
  class: "sdas-detail-back sdas-detail-back-overlay",
  "aria-hidden": "true"
};
const _hoisted_3$1 = {
  key: 0,
  class: "sdas-detail-note"
};
const _hoisted_4$1 = { class: "sdas-detail-header" };
const _hoisted_5$1 = { class: "sdas-detail-poster" };
const _hoisted_6$1 = {
  key: 1,
  class: "sdas-detail-poster-empty d-flex align-center justify-center"
};
const _hoisted_7$1 = { class: "sdas-detail-title" };
const _hoisted_8$1 = {
  key: 0,
  class: "sdas-detail-status"
};
const _hoisted_9$1 = {
  key: 0,
  class: "sdas-status-pill is-library"
};
const _hoisted_10$1 = {
  key: 1,
  class: "sdas-status-pill is-new"
};
const _hoisted_11$1 = {
  key: 2,
  class: "sdas-status-pill is-kind"
};
const _hoisted_12$1 = { class: "sdas-detail-h1" };
const _hoisted_13$1 = { class: "sdas-detail-h1-text" };
const _hoisted_14$1 = {
  key: 0,
  class: "sdas-detail-year"
};
const _hoisted_15$1 = { class: "sdas-detail-attributes" };
const _hoisted_16$1 = {
  key: 1,
  class: "mx-1"
};
const _hoisted_17$1 = { class: "sdas-detail-genres" };
const _hoisted_18$1 = ["title", "onClick"];
const _hoisted_19$1 = { class: "sdas-detail-actions" };
const _hoisted_20$1 = {
  key: 0,
  class: "sdas-detail-h2"
};
const _hoisted_21$1 = {
  key: 1,
  class: "sdas-detail-text"
};
const _hoisted_22$1 = {
  key: 2,
  class: "sdas-detail-text is-dim"
};
const _hoisted_23$1 = { class: "sdas-detail-links" };
const _hoisted_24$1 = ["href"];
const _hoisted_25$1 = ["href"];
const _hoisted_26$1 = ["href"];
const _hoisted_27$1 = { class: "sdas-facts" };
const _hoisted_28$1 = {
  key: 0,
  class: "sdas-ratings"
};
const _hoisted_29$1 = { class: "sdas-fact-value" };
const _hoisted_30$1 = { class: "sdas-fact-inner" };
const _hoisted_31$1 = {
  key: 0,
  xmlns: "http://www.w3.org/2000/svg",
  fill: "none",
  viewBox: "0 0 24 24",
  "stroke-width": "1.5",
  stroke: "currentColor",
  "aria-hidden": "true",
  class: "sdas-fact-icon"
};
const _hoisted_32$1 = ["title"];
const _hoisted_33$1 = ["href", "title"];
const _hoisted_34$1 = ["title"];
const _hoisted_35$1 = {
  key: 1,
  class: "sdas-slider"
};
const _hoisted_36$1 = { class: "sdas-slider-wrapper" };
const _hoisted_37$1 = {
  key: 2,
  class: "sdas-douban"
};
const _hoisted_38$1 = {
  key: 0,
  class: "sdas-douban-count"
};
const _hoisted_39$1 = {
  key: 0,
  class: "sdas-douban-count"
};
const _hoisted_40$1 = {
  key: 0,
  class: "sdas-douban-list"
};
const _hoisted_41$1 = { class: "sdas-douban-avatar" };
const _hoisted_42$1 = ["src"];
const _hoisted_43$1 = { key: 1 };
const _hoisted_44$1 = { class: "sdas-douban-body" };
const _hoisted_45$1 = { class: "sdas-douban-author" };
const _hoisted_46$1 = { class: "sdas-douban-text" };
const _hoisted_47$1 = { class: "sdas-douban-meta" };
const _hoisted_48$1 = { key: 0 };
const _hoisted_49$1 = { key: 1 };
const _hoisted_50$1 = {
  key: 1,
  class: "sdas-douban-list"
};
const _hoisted_51$1 = { class: "sdas-douban-avatar" };
const _hoisted_52$1 = ["src"];
const _hoisted_53$1 = { key: 1 };
const _hoisted_54$1 = { class: "sdas-douban-body" };
const _hoisted_55$1 = ["title", "onClick"];
const _hoisted_56$1 = {
  key: 0,
  class: "sdas-douban-text"
};
const _hoisted_57$1 = { class: "sdas-douban-meta" };
const _hoisted_58$1 = { key: 0 };
const _hoisted_59$1 = { key: 1 };
const _hoisted_60$1 = { key: 2 };
const _hoisted_61$1 = { class: "sdas-douban-foot" };
const _hoisted_62$1 = {
  key: 2,
  class: "sdas-douban-empty"
};
const _hoisted_63 = {
  key: 0,
  class: "sdas-subset-row"
};
const _hoisted_64 = { class: "sdas-subset-cell" };
const _hoisted_65 = { class: "sdas-subset-hint" };
const _hoisted_66 = {
  key: 1,
  class: "sdas-subset-row"
};
const _hoisted_67 = { class: "sdas-subset-cell" };
const _hoisted_68 = { class: "sdas-subset-hint" };
const _hoisted_69 = {
  key: 2,
  class: "sdas-subset-row"
};
const _hoisted_70 = { class: "sdas-subset-cell" };
const _hoisted_71 = { class: "sdas-subset-hint" };
const _hoisted_72 = {
  key: 3,
  class: "sdas-subset-row"
};
const _hoisted_73 = { class: "sdas-subset-cell" };
const _hoisted_74 = ["title"];
const _hoisted_75 = {
  key: 4,
  class: "sdas-subset-row"
};
const _hoisted_76 = {
  key: 5,
  class: "sdas-subset-row"
};
const _hoisted_77 = {
  key: 6,
  class: "sdas-subset-note"
};
const {computed: computed$3,nextTick: nextTick$1,onMounted: onMounted$3,onUnmounted: onUnmounted$2,reactive,ref: ref$3,watch: watch$3} = await importShared('vue');
const DOUBAN_PAGE = 10;
const OVERVIEW_STACK_GAP = 32;
const _sfc_main$3 = /* @__PURE__ */ _defineComponent$3({
  __name: "WorkDetail",
  props: {
    api: {},
    work: {},
    subscribed: { type: Boolean },
    subscribing: { type: Boolean },
    subscription: {},
    subEditable: { type: Boolean },
    followedIds: {},
    busyIds: {}
  },
  emits: ["back", "search", "subscribe", "open-actor", "toggle-actor", "open-adapted", "filter-genre", "sub-updated"],
  setup(__props, { emit: __emit }) {
    const pageRoot = ref$3(null);
    const props = __props;
    const emit = __emit;
    const themeName = ref$3("");
    let themeObserver = null;
    function syncTheme() {
      themeName.value = typeof document === "undefined" ? "" : document.documentElement.dataset.theme || "";
    }
    const isGlass = computed$3(() => themeName.value === "glass");
    const isTransparent = computed$3(() => themeName.value === "transparent");
    const detail = ref$3(null);
    const loaded = ref$3(false);
    const failed = ref$3(false);
    const loadedCast = ref$3(/* @__PURE__ */ new Set());
    function fromWork(work) {
      return {
        found: true,
        media_source: work.media_source,
        media_id: work.media_id,
        title: work.title,
        year: work.year,
        type: work.type,
        overview: work.overview || "",
        poster: work.poster,
        backdrop: "",
        vote: Number(work.vote || 0),
        release_date: work.release_date || "",
        episode_count: Number(work.episode_count || 0),
        episode_minutes: 0,
        duration_minutes: 0,
        genres: work.genres || [],
        studio: work.studio || "",
        // 播放平台：墙上那一行目前恒空（作品卡不带平台），保留字段只为结构完整
        platform: work.platform || "",
        status: "",
        language: "",
        url: work.url || "",
        // 作品卡那一行没有 TMDB 身份（百科的卡片投影里没这个字段）—— 只有详情回来了才有
        tmdb_id: 0,
        tmdb_url: "",
        actors: [],
        kind: work.kind || "",
        first_seen: work.first_seen || "",
        is_new: Boolean(work.is_new),
        in_library: typeof work.in_library === "boolean" ? work.in_library : null
      };
    }
    const view = computed$3(
      () => detail.value?.found ? detail.value : fromWork(props.work)
    );
    const missing = computed$3(() => Boolean(detail.value) && detail.value?.found === false);
    const backdropUrl = computed$3(() => view.value.backdrop || view.value.poster || "");
    const inLibrary = computed$3(() => view.value.in_library === true);
    const source = ref$3(null);
    const doubanTab = ref$3("interests");
    const doubanComments = ref$3([]);
    const doubanReviews = ref$3([]);
    const doubanTotals = reactive({ interests: 0, reviews: 0 });
    const doubanLoading = ref$3(false);
    const doubanLoaded = ref$3(false);
    const hasDouban = computed$3(() => Boolean(view.value?.douban_id));
    const doubanRows = computed$3(
      () => doubanTab.value === "interests" ? doubanComments.value : doubanReviews.value
    );
    const doubanHasMore = computed$3(() => {
      const total = doubanTab.value === "interests" ? doubanTotals.interests : doubanTotals.reviews;
      return total > doubanRows.value.length;
    });
    const castRows = computed$3(() => {
      const rows = [];
      const seen = /* @__PURE__ */ new Set();
      const add = (row) => {
        const key = String(row.actor_id || row.name || "");
        if (!key || seen.has(key)) return;
        seen.add(key);
        rows.push(row);
      };
      const src = source.value;
      for (const person of src?.director || []) {
        add({
          name: person.name,
          actor_id: person.media_id,
          media_id: person.media_id || void 0,
          exact: true,
          profile: person.profile || void 0,
          role: "导演"
        });
      }
      for (const person of src?.writer || []) {
        add({
          name: person.name,
          actor_id: person.media_id,
          media_id: person.media_id || void 0,
          exact: true,
          profile: person.profile || void 0,
          role: "编剧"
        });
      }
      const actors = view.value.actors || [];
      const castSource = actors.length ? actors.map((actor) => ({
        name: actor.name,
        actor_id: actor.actor_id,
        profile: actor.profile,
        character: actor.character,
        subscribed: actor.subscribed
      })) : (src?.cast || []).map((person) => ({
        name: person.name,
        actor_id: person.media_id,
        profile: person.profile,
        character: person.role,
        subscribed: false
      }));
      if (!castSource.length) return rows;
      for (const actor of castSource) {
        add({
          name: actor.name,
          actor_id: actor.actor_id,
          media_id: actor.actor_id || void 0,
          exact: true,
          profile: actor.profile || void 0,
          subscribed: actor.subscribed,
          role: actor.character ? `饰 ${actor.character}` : ""
        });
      }
      return rows;
    });
    const castKey = (row) => row.actor_id || row.name;
    function isFollowed(row) {
      return Boolean(row.actor_id && props.followedIds?.has(row.actor_id));
    }
    function isBusy(row) {
      return Boolean(row.actor_id && props.busyIds?.has(row.actor_id));
    }
    function markCastLoaded(row) {
      if (loadedCast.value.has(castKey(row))) return;
      const next = new Set(loadedCast.value);
      next.add(castKey(row));
      loadedCast.value = next;
    }
    const facts = computed$3(() => {
      const data = view.value;
      const rows = [];
      const push = (label, value, icon = false, url = "", internal = false) => {
        if (value) rows.push({ label, value, icon, url, internal });
      };
      const src = source.value;
      push("ID", data.media_id);
      push("TMDB ID", data.tmdb_id ? String(data.tmdb_id) : "");
      push("豆瓣 ID", data.douban_id || "");
      push("状态", data.status || src?.status || "");
      push("上映日期", data.release_date, true);
      push("集数", data.episode_count ? `${data.episode_count} 集` : "");
      push("单集时长", data.episode_minutes ? `${data.episode_minutes} 分钟` : "");
      push(
        "全集时长",
        data.duration_minutes ? `${data.duration_minutes} 分钟` : src?.duration_minutes ? `${src.duration_minutes} 分钟` : src?.duration_text || ""
      );
      push("原始语言", data.language);
      push("制作公司", data.studio || src?.studio || "");
      push("播出平台", data.platform || src?.platform || "");
      push("热度", src?.heat_text || "");
      push("播放量", src?.play_count_text || "");
      push("收藏", src?.favorites_text || "");
      push(
        "改编自",
        src?.adapted_title ? src.adapted_author ? `《${src.adapted_title}》 / ${src.adapted_author}` : `《${src.adapted_title}》` : "",
        false,
        src?.adapted ? "" : src?.adapted_url || "",
        Boolean(src?.adapted)
      );
      push("首次发现", data.first_seen);
      return rows;
    });
    function emitSubscribe() {
      emit("subscribe", {
        ...props.work,
        episode_count: Number(view.value?.episode_count || props.work.episode_count || 0)
      });
    }
    const subsetOpen = ref$3(false);
    const SUB_STATE_META = {
      downloaded: { label: "已提交下载", color: "green", icon: "mdi-check-circle-outline" },
      history: { label: "下载历史已有", color: "teal", icon: "mdi-content-duplicate" },
      in_library: { label: "已在媒体库", color: "teal", icon: "mdi-library-outline" },
      noresult: { label: "暂无资源", color: "grey", icon: "mdi-magnify-close" },
      failed: { label: "搜索失败", color: "red", icon: "mdi-alert-circle-outline" }
    };
    const stateMeta = computed$3(
      () => SUB_STATE_META[String(props.subscription?.sub_state || "")] || null
    );
    const searchingNow = ref$3(false);
    async function searchNow() {
      if (searchingNow.value) return;
      searchingNow.value = true;
      try {
        const res = await pluginSubscribeSearchNow({ api: props.api }, props.work.media_id);
        toast(String(res?.message || "已开始搜索，结果稍后回填"));
        emit("sub-updated");
        setTimeout(() => emit("sub-updated"), 8e3);
        setTimeout(() => emit("sub-updated"), 2e4);
      } catch (err) {
        toast(`搜索失败：${err instanceof Error ? err.message : err}`);
      } finally {
        searchingNow.value = false;
      }
    }
    const hostSites = ref$3([]);
    const hostDownloaders = ref$3([]);
    const hostPaths = ref$3([]);
    const defaults = ref$3({ sites: "", downloader: "", save_path: "" });
    const optionsLoading = ref$3(false);
    const optionsLoaded = ref$3(false);
    const localSites = ref$3([]);
    const localDownloader = ref$3("");
    const localSavePath = ref$3("");
    const savingTargets = ref$3(false);
    const targetsDirty = ref$3(false);
    const siteOptions = computed$3(() => hostSites.value || []);
    const downloaderOptions = computed$3(() => {
      const def = defaults.value.downloader;
      const names = (hostDownloaders.value || []).map((item) => item.name);
      if (def && !names.includes(def)) names.unshift(def);
      return [
        { title: def ? `默认（${def}）` : "默认（跟随配置页）", value: "" },
        ...names.map((name) => ({ title: name, value: name }))
      ];
    });
    const pathOptions = computed$3(() => {
      const def = defaults.value.save_path;
      const items = (hostPaths.value || []).map((item) => ({
        title: String(item.name || item.save_path || ""),
        value: String(item.save_path || "")
      }));
      const list = items.filter((item) => item.value);
      if (def && !list.some((item) => item.value === def)) list.unshift({ title: def, value: def });
      return [{ title: def ? `默认（${def}）` : "默认（跟随配置页）", value: "" }, ...list];
    });
    const subSitesHint = computed$3(() => {
      if (localSites.value.length) return `已选 ${localSites.value.length} 个站点`;
      const ids = String(defaults.value.sites || "").split(",").map((id) => id.trim()).filter(Boolean);
      if (!ids.length) return "留空 = 配置页里的全部站点";
      const names = ids.map((id) => siteOptions.value.find((site) => String(site.id) === id)?.name || id);
      return `默认：${names.join("、")}`;
    });
    const subDownloaderHint = computed$3(
      () => localDownloader.value ? "只下到这个下载器" : "留空 = 配置页默认下载器"
    );
    const subSavePathHint = computed$3(
      () => localSavePath.value ? "只下到这个目录" : "留空 = 配置页默认目录"
    );
    function syncLocalTargets() {
      localSites.value = String(props.subscription?.sites || "").split(",").map((item) => Number(item.trim())).filter((num) => Number.isFinite(num) && num > 0);
      localDownloader.value = String(props.subscription?.downloader || "");
      localSavePath.value = String(props.subscription?.save_path || "");
      targetsDirty.value = false;
    }
    function onSitesChange(value) {
      const list = Array.isArray(value) ? value : [];
      localSites.value = list.map((item) => Number(item)).filter((num) => Number.isFinite(num) && num > 0);
      targetsDirty.value = true;
    }
    function onDownloaderChange(value) {
      localDownloader.value = String(value || "");
      targetsDirty.value = true;
    }
    function onSavePathChange(value) {
      localSavePath.value = String(value || "");
      targetsDirty.value = true;
    }
    async function saveTargets() {
      if (savingTargets.value) return;
      savingTargets.value = true;
      try {
        const res = await pluginSubscribeUpdate({ api: props.api }, props.work.media_id, {
          sites: localSites.value.join(","),
          downloader: localDownloader.value,
          save_path: localSavePath.value
        });
        toast(String(res?.message || "已保存订阅设置"));
        targetsDirty.value = false;
        emit("sub-updated");
      } catch (err) {
        toast(`保存失败：${err instanceof Error ? err.message : err}`);
      } finally {
        savingTargets.value = false;
      }
    }
    async function loadTargetOptions() {
      if (optionsLoading.value || optionsLoaded.value) return;
      optionsLoading.value = true;
      try {
        const [sites, downloaders, paths, subs] = await Promise.allSettled([
          fetchSearchSites({ api: props.api }),
          fetchDownloaderOptions({ api: props.api }),
          fetchDownloadPaths({ api: props.api }),
          fetchSubscriptions({ api: props.api })
        ]);
        hostSites.value = sites.status === "fulfilled" ? sites.value : [];
        hostDownloaders.value = downloaders.status === "fulfilled" ? downloaders.value : [];
        hostPaths.value = paths.status === "fulfilled" ? paths.value : [];
        if (subs.status === "fulfilled") {
          defaults.value = {
            sites: String(subs.value.default_sites || ""),
            downloader: String(subs.value.default_downloader || ""),
            save_path: String(subs.value.default_save_path || "")
          };
        }
        optionsLoaded.value = true;
      } finally {
        optionsLoading.value = false;
      }
    }
    watch$3(subsetOpen, async (open) => {
      if (!open) return;
      syncLocalTargets();
      await loadTargetOptions();
    });
    watch$3(
      () => props.subscription,
      () => {
        if (subsetOpen.value && !targetsDirty.value) syncLocalTargets();
      }
    );
    const playing = ref$3(false);
    const snackbar = ref$3(false);
    const snackbarText = ref$3("");
    function toast(text) {
      snackbarText.value = String(text || "");
      snackbar.value = Boolean(snackbarText.value);
    }
    async function playWork() {
      if (playing.value) return;
      playing.value = true;
      try {
        const url = await fetchPlayUrl(
          { api: props.api },
          {
            mediaSource: String(view.value.media_source || props.work.media_source || "djbaike"),
            mediaId: String(view.value.media_id || props.work.media_id || ""),
            title: String(view.value.title || props.work.title || ""),
            year: String(view.value.year || props.work.year || ""),
            type: String(view.value.type || "电视剧")
          }
        );
        if (url) {
          window.open(url, "_blank", "noopener");
        } else {
          toast("没有找到可播放的条目：媒体服务器里没有，或未配置媒体服务器");
        }
      } finally {
        playing.value = false;
      }
    }
    function openAdapted() {
      const novel = source.value?.adapted;
      if (novel) emit("open-adapted", novel);
    }
    function openUrl(url) {
      if (!url) return;
      if (typeof window !== "undefined") window.open(url, "_blank", "noopener");
    }
    async function load() {
      loaded.value = false;
      failed.value = false;
      source.value = null;
      doubanReviews.value = [];
      doubanComments.value = [];
      doubanTotals.interests = 0;
      doubanTotals.reviews = 0;
      doubanTab.value = "interests";
      doubanLoaded.value = false;
      try {
        detail.value = await fetchWorkDetail(
          { api: props.api },
          { media_id: props.work.media_id, title: props.work.title, year: props.work.year }
        );
        void fetchWorkSource({ api: props.api }, props.work.media_id).then((value) => {
          source.value = value;
          const data = detail.value;
          if (data && !String(data.douban_id || "").trim() && value.douban_id) {
            detail.value = {
              ...data,
              douban_id: value.douban_id,
              douban_url: value.douban_url || data.douban_url || ""
            };
            if (!doubanComments.value.length && !doubanReviews.value.length) void loadDouban();
          }
        });
        void loadDouban();
      } catch (err) {
        console.error("[ShortDramaActorSubscribe] 作品详情加载失败", err);
        detail.value = null;
        failed.value = true;
      } finally {
        loaded.value = true;
      }
    }
    async function loadDoubanPage(tab, start) {
      const id = String(view.value?.douban_id || "").trim();
      if (!id) return;
      const typeName = String(view.value?.type || "电视剧");
      doubanLoading.value = true;
      try {
        if (tab === "interests") {
          const page = await fetchDoubanComments(
            { api: props.api },
            id,
            typeName,
            start,
            DOUBAN_PAGE
          );
          const seen = new Set(doubanComments.value.map((item) => item.id));
          doubanComments.value.push(...page.items.filter((item) => !seen.has(item.id)));
          doubanTotals.interests = page.total;
        } else {
          const page = await fetchDoubanReviews(
            { api: props.api },
            id,
            typeName,
            start,
            DOUBAN_PAGE
          );
          const seen = new Set(doubanReviews.value.map((item) => item.id));
          doubanReviews.value.push(...page.items.filter((item) => !seen.has(item.id)));
          doubanTotals.reviews = page.total;
        }
      } finally {
        doubanLoading.value = false;
        doubanLoaded.value = true;
      }
    }
    async function loadDouban() {
      if (!view.value?.douban_id) return;
      await loadDoubanPage("interests", 0);
      if (!doubanComments.value.length) {
        await new Promise((resolve) => setTimeout(resolve, 800));
        await loadDoubanPage("interests", 0);
      }
      await loadDoubanPage("reviews", 0);
    }
    function switchDoubanTab(tab) {
      doubanTab.value = tab;
      const loaded2 = tab === "interests" ? doubanComments.value.length : doubanReviews.value.length;
      if (!loaded2) void loadDoubanPage(tab, 0);
    }
    function onDoubanTabsClick(event) {
      const target = event.target;
      const el = target?.closest?.("[data-douban-tab]");
      const tab = el?.getAttribute("data-douban-tab");
      if (tab === "interests" || tab === "reviews") switchDoubanTab(tab);
    }
    function loadMoreDouban() {
      void loadDoubanPage(doubanTab.value, doubanRows.value.length);
    }
    function openActor(row) {
      if (!row.actor_id && !row.name) {
        openUrl(row.url || view.value.url);
        return;
      }
      emit("open-actor", {
        name: row.name,
        actor_id: row.actor_id,
        exact: true,
        subscribed: row.subscribed,
        profile: row.profile,
        url: row.url
      });
    }
    const overviewLeft = ref$3(null);
    const overviewRight = ref$3(null);
    const overviewStacked = ref$3(false);
    let overviewObserver = null;
    function syncOverviewStack() {
      const left = overviewLeft.value;
      const right = overviewRight.value;
      if (!left || !right) {
        overviewStacked.value = false;
        return;
      }
      overviewStacked.value = right.scrollHeight - left.scrollHeight > OVERVIEW_STACK_GAP;
    }
    function watchOverviewSize() {
      overviewObserver?.disconnect();
      overviewObserver = null;
      if (typeof ResizeObserver === "undefined") return;
      overviewObserver = new ResizeObserver(syncOverviewStack);
      if (overviewLeft.value) overviewObserver.observe(overviewLeft.value);
      if (overviewRight.value) overviewObserver.observe(overviewRight.value);
      syncOverviewStack();
    }
    const castRail = ref$3(null);
    const castNavState = ref$3(3);
    let castScrollTimer = null;
    let castResizeObserver = null;
    function syncCastRail() {
      const rail = castRail.value;
      if (!rail) return;
      if (rail.scrollWidth <= rail.clientWidth + 2) castNavState.value = 3;
      else if (rail.scrollLeft <= 2) castNavState.value = 0;
      else if (rail.scrollLeft >= rail.scrollWidth - rail.clientWidth - 2) castNavState.value = 2;
      else castNavState.value = 1;
    }
    function onCastScroll() {
      syncCastRail();
      const rail = castRail.value;
      if (!rail) return;
      rail.classList.add("is-scrolling");
      if (castScrollTimer) clearTimeout(castScrollTimer);
      castScrollTimer = setTimeout(() => castRail.value?.classList.remove("is-scrolling"), 1500);
    }
    function slideCast(next) {
      const rail = castRail.value;
      if (!rail) return;
      const item = rail.querySelector(".sdas-slide-item");
      const step = (item?.offsetWidth || 144) + 16;
      const page = Math.max(1, Math.trunc(rail.clientWidth / step));
      const current = rail.scrollLeft <= 2 ? 0 : Math.trunc((rail.scrollLeft + step / 2) / step);
      const target = next ? Math.min((current + page) * step, rail.scrollWidth - rail.clientWidth) : Math.max((current - page) * step, 0);
      rail.scrollTo({ left: target, top: 0, behavior: "smooth" });
      setTimeout(syncCastRail, 420);
    }
    onMounted$3(() => {
      castResizeObserver = new ResizeObserver(() => syncCastRail());
      if (castRail.value) castResizeObserver.observe(castRail.value);
      nextTick$1(syncCastRail);
      watchOverviewSize();
      syncTheme();
      if (typeof MutationObserver !== "undefined") {
        themeObserver = new MutationObserver(syncTheme);
        themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      }
    });
    onUnmounted$2(() => {
      if (castScrollTimer) clearTimeout(castScrollTimer);
      castResizeObserver?.disconnect();
      castResizeObserver = null;
      overviewObserver?.disconnect();
      overviewObserver = null;
      themeObserver?.disconnect();
      themeObserver = null;
    });
    watch$3(
      () => props.work?.media_id,
      () => {
        loadedCast.value = /* @__PURE__ */ new Set();
        detail.value = null;
        loaded.value = false;
        failed.value = false;
        subsetOpen.value = false;
        load();
      },
      { immediate: true }
    );
    watch$3(castRows, () => nextTick$1(syncCastRail), { flush: "post" });
    watch$3(
      [() => view.value.overview, () => facts.value.length],
      () => nextTick$1(watchOverviewSize),
      { flush: "post" }
    );
    return (_ctx, _cache) => {
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_img = _resolveComponent$1("v-img");
      const _component_v_skeleton_loader = _resolveComponent$1("v-skeleton-loader");
      const _component_v_icon = _resolveComponent$1("v-icon");
      const _component_v_rating = _resolveComponent$1("v-rating");
      const _component_v_progress_circular = _resolveComponent$1("v-progress-circular");
      const _component_v_snackbar = _resolveComponent$1("v-snackbar");
      const _component_v_spacer = _resolveComponent$1("v-spacer");
      const _component_v_chip = _resolveComponent$1("v-chip");
      const _component_v_card_title = _resolveComponent$1("v-card-title");
      const _component_v_divider = _resolveComponent$1("v-divider");
      const _component_v_select = _resolveComponent$1("v-select");
      const _component_v_card_text = _resolveComponent$1("v-card-text");
      const _component_v_card_actions = _resolveComponent$1("v-card-actions");
      const _component_v_card = _resolveComponent$1("v-card");
      const _component_v_dialog = _resolveComponent$1("v-dialog");
      return _openBlock$3(), _createElementBlock$3("div", {
        class: _normalizeClass$2(["sdas-detail", { "is-glass": isGlass.value, "is-transparent": isTransparent.value }])
      }, [
        !loaded.value ? (_openBlock$3(), _createBlock$2(LoadingBanner, {
          key: 0,
          class: "sdas-detail-loading"
        })) : failed.value ? (_openBlock$3(), _createBlock$2(NoDataFound, {
          key: 1,
          "error-code": "500",
          "error-title": "出错啦！",
          "error-description": "无法获取到媒体信息，请检查网络连接。"
        }, {
          button: _withCtx$2(() => [
            _createVNode$2(_component_v_btn, {
              "prepend-icon": "mdi-refresh",
              variant: "tonal",
              onClick: _cache[0] || (_cache[0] = ($event) => load())
            }, {
              default: _withCtx$2(() => [..._cache[15] || (_cache[15] = [
                _createTextVNode$1("重试", -1)
              ])]),
              _: 1
            })
          ]),
          _: 1
        })) : (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 2 }, [
          backdropUrl.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_1$2, [
            _createVNode$2(_component_v_img, {
              class: "sdas-detail-back-img",
              position: "top",
              src: _unref(proxyImage)(backdropUrl.value),
              cover: ""
            }, null, 8, ["src"])
          ])) : _createCommentVNode$3("", true),
          backdropUrl.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_2$1)) : _createCommentVNode$3("", true),
          _createElementVNode$3("div", {
            ref_key: "pageRoot",
            ref: pageRoot,
            class: "sdas-detail-page"
          }, [
            missing.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_3$1, " 未识别到媒体信息，下面是作品卡上的信息 ")) : _createCommentVNode$3("", true),
            _createElementVNode$3("div", _hoisted_4$1, [
              _createElementVNode$3("div", _hoisted_5$1, [
                view.value.poster ? (_openBlock$3(), _createBlock$2(_component_v_img, {
                  key: 0,
                  src: _unref(proxyImage)(view.value.poster),
                  cover: "",
                  "aspect-ratio": 2 / 3,
                  class: "ring-1 ring-gray-500"
                }, {
                  placeholder: _withCtx$2(() => [
                    _createVNode$2(_component_v_skeleton_loader, { class: "sdas-detail-poster-skeleton" })
                  ]),
                  _: 1
                }, 8, ["src"])) : (_openBlock$3(), _createElementBlock$3("div", _hoisted_6$1, [
                  _createVNode$2(_component_v_icon, {
                    size: "40",
                    color: "medium-emphasis"
                  }, {
                    default: _withCtx$2(() => [..._cache[16] || (_cache[16] = [
                      _createTextVNode$1("mdi-movie-open-outline", -1)
                    ])]),
                    _: 1
                  })
                ]))
              ]),
              _createElementVNode$3("div", _hoisted_7$1, [
                inLibrary.value || view.value.is_new || view.value.kind ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_8$1, [
                  inLibrary.value ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_9$1, "已入库")) : _createCommentVNode$3("", true),
                  view.value.is_new ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_10$1, "新作品")) : _createCommentVNode$3("", true),
                  view.value.kind ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_11$1, _toDisplayString$2(view.value.kind), 1)) : _createCommentVNode$3("", true)
                ])) : _createCommentVNode$3("", true),
                _createElementVNode$3("h1", _hoisted_12$1, [
                  _createElementVNode$3("span", _hoisted_13$1, _toDisplayString$2(view.value.title), 1),
                  view.value.year ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_14$1, "（" + _toDisplayString$2(view.value.year) + "）", 1)) : _createCommentVNode$3("", true)
                ]),
                _createElementVNode$3("span", _hoisted_15$1, [
                  view.value.episode_minutes ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
                    _createTextVNode$1(_toDisplayString$2(view.value.episode_minutes) + " 分钟 ", 1)
                  ], 64)) : _createCommentVNode$3("", true),
                  view.value.episode_minutes && view.value.genres.length ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_16$1, "|")) : _createCommentVNode$3("", true),
                  _createElementVNode$3("span", _hoisted_17$1, [
                    (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(view.value.genres, (genre) => {
                      return _openBlock$3(), _createElementBlock$3("button", {
                        key: genre,
                        type: "button",
                        class: "sdas-detail-genre",
                        title: `只看「${genre}」的作品`,
                        onClick: ($event) => emit("filter-genre", genre)
                      }, _toDisplayString$2(genre), 9, _hoisted_18$1);
                    }), 128))
                  ])
                ])
              ]),
              _createElementVNode$3("div", _hoisted_19$1, [
                _createVNode$2(_component_v_btn, {
                  class: "sdas-detail-action-btn",
                  variant: "tonal",
                  color: "info",
                  "prepend-icon": "mdi-magnify",
                  onClick: _cache[1] || (_cache[1] = ($event) => emit("search", __props.work))
                }, {
                  default: _withCtx$2(() => [..._cache[17] || (_cache[17] = [
                    _createTextVNode$1(" 搜索资源 ", -1)
                  ])]),
                  _: 1
                }),
                _createVNode$2(_component_v_btn, {
                  class: "sdas-detail-action-btn",
                  variant: "tonal",
                  color: __props.subscribed ? "error" : "warning",
                  loading: __props.subscribing,
                  "prepend-icon": __props.subscribed ? "mdi-heart" : "mdi-heart-outline",
                  title: __props.subscribed ? "再次点击取消订阅" : "订阅这部剧",
                  onClick: _cache[2] || (_cache[2] = ($event) => emitSubscribe())
                }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$1(_toDisplayString$2(__props.subscribed ? "已订阅" : "订阅"), 1)
                  ]),
                  _: 1
                }, 8, ["color", "loading", "prepend-icon", "title"]),
                __props.subscribed ? (_openBlock$3(), _createBlock$2(_component_v_btn, {
                  key: 0,
                  class: "sdas-detail-action-btn",
                  variant: "tonal",
                  color: "grey",
                  "prepend-icon": "mdi-tune",
                  title: "订阅设置：自动搜索开关、立即搜索",
                  onClick: _cache[3] || (_cache[3] = ($event) => subsetOpen.value = true)
                }, {
                  default: _withCtx$2(() => [..._cache[18] || (_cache[18] = [
                    _createTextVNode$1(" 订阅设置 ", -1)
                  ])]),
                  _: 1
                })) : _createCommentVNode$3("", true),
                inLibrary.value ? (_openBlock$3(), _createBlock$2(_component_v_btn, {
                  key: 1,
                  class: "sdas-detail-action-btn",
                  variant: "tonal",
                  loading: playing.value,
                  "prepend-icon": "mdi-play",
                  onClick: _cache[4] || (_cache[4] = ($event) => playWork())
                }, {
                  default: _withCtx$2(() => [..._cache[19] || (_cache[19] = [
                    _createTextVNode$1(" 在线播放 ", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"])) : _createCommentVNode$3("", true)
              ])
            ]),
            _createElementVNode$3("div", {
              class: _normalizeClass$2(["sdas-detail-overview", { "is-stacked": overviewStacked.value }])
            }, [
              _createElementVNode$3("div", {
                ref_key: "overviewLeft",
                ref: overviewLeft,
                class: "sdas-detail-overview-left"
              }, [
                view.value.overview ? (_openBlock$3(), _createElementBlock$3("h2", _hoisted_20$1, "简介")) : _createCommentVNode$3("", true),
                view.value.overview ? (_openBlock$3(), _createElementBlock$3("p", _hoisted_21$1, _toDisplayString$2(view.value.overview), 1)) : (_openBlock$3(), _createElementBlock$3("p", _hoisted_22$1, "百科还没有这部作品的简介。")),
                _createElementVNode$3("div", _hoisted_23$1, [
                  view.value.url ? (_openBlock$3(), _createElementBlock$3("a", {
                    key: 0,
                    class: "sdas-link-chip",
                    href: view.value.url,
                    target: "_blank",
                    rel: "noopener"
                  }, [
                    _createVNode$2(_component_v_icon, { size: "16" }, {
                      default: _withCtx$2(() => [..._cache[20] || (_cache[20] = [
                        _createTextVNode$1("mdi-link", -1)
                      ])]),
                      _: 1
                    }),
                    _cache[21] || (_cache[21] = _createElementVNode$3("span", { class: "ms-1" }, "短剧百科", -1))
                  ], 8, _hoisted_24$1)) : _createCommentVNode$3("", true),
                  view.value.douban_url ? (_openBlock$3(), _createElementBlock$3("a", {
                    key: 1,
                    class: "sdas-link-chip",
                    href: view.value.douban_url,
                    target: "_blank",
                    rel: "noopener",
                    title: "在豆瓣打开"
                  }, [
                    _createVNode$2(_component_v_icon, { size: "16" }, {
                      default: _withCtx$2(() => [..._cache[22] || (_cache[22] = [
                        _createTextVNode$1("mdi-link", -1)
                      ])]),
                      _: 1
                    }),
                    _cache[23] || (_cache[23] = _createElementVNode$3("span", { class: "ms-1" }, "豆瓣", -1))
                  ], 8, _hoisted_25$1)) : _createCommentVNode$3("", true),
                  view.value.tmdb_url ? (_openBlock$3(), _createElementBlock$3("a", {
                    key: 2,
                    class: "sdas-link-chip",
                    href: view.value.tmdb_url,
                    target: "_blank",
                    rel: "noopener",
                    title: "在 TheMovieDb 打开"
                  }, [
                    _createVNode$2(_component_v_icon, { size: "16" }, {
                      default: _withCtx$2(() => [..._cache[24] || (_cache[24] = [
                        _createTextVNode$1("mdi-link", -1)
                      ])]),
                      _: 1
                    }),
                    _cache[25] || (_cache[25] = _createElementVNode$3("span", { class: "ms-1" }, "TheMovieDb", -1))
                  ], 8, _hoisted_26$1)) : _createCommentVNode$3("", true)
                ])
              ], 512),
              _createElementVNode$3("div", {
                ref_key: "overviewRight",
                ref: overviewRight,
                class: "sdas-detail-overview-right"
              }, [
                _createElementVNode$3("div", _hoisted_27$1, [
                  view.value.vote > 0 ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_28$1, [
                    _createVNode$2(_component_v_rating, {
                      "model-value": view.value.vote,
                      length: 10,
                      density: "compact",
                      readonly: "",
                      class: "ma-2"
                    }, null, 8, ["model-value"])
                  ])) : _createCommentVNode$3("", true),
                  (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(facts.value, (fact, index) => {
                    return _openBlock$3(), _createElementBlock$3("div", {
                      key: fact.label,
                      class: _normalizeClass$2(["sdas-fact", { "is-last": index === facts.value.length - 1 }])
                    }, [
                      _createElementVNode$3("span", null, _toDisplayString$2(fact.label), 1),
                      _createElementVNode$3("span", _hoisted_29$1, [
                        _createElementVNode$3("span", _hoisted_30$1, [
                          fact.icon ? (_openBlock$3(), _createElementBlock$3("svg", _hoisted_31$1, [..._cache[26] || (_cache[26] = [
                            _createElementVNode$3("path", {
                              "stroke-linecap": "round",
                              "stroke-linejoin": "round",
                              d: "M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z"
                            }, null, -1)
                          ])])) : _createCommentVNode$3("", true),
                          fact.internal ? (_openBlock$3(), _createElementBlock$3("button", {
                            key: 1,
                            type: "button",
                            class: _normalizeClass$2(["sdas-fact-link", { "ms-1": fact.icon }]),
                            title: `查看原著《${fact.value}》`,
                            onClick: _cache[5] || (_cache[5] = ($event) => openAdapted())
                          }, _toDisplayString$2(fact.value), 11, _hoisted_32$1)) : fact.url ? (_openBlock$3(), _createElementBlock$3("a", {
                            key: 2,
                            class: _normalizeClass$2(["sdas-fact-link", { "ms-1": fact.icon }]),
                            href: fact.url,
                            target: "_blank",
                            rel: "noopener",
                            title: `在短剧百科打开：${fact.value}`
                          }, _toDisplayString$2(fact.value), 11, _hoisted_33$1)) : (_openBlock$3(), _createElementBlock$3("span", {
                            key: 3,
                            class: _normalizeClass$2({ "ms-1": fact.icon }),
                            title: fact.value
                          }, _toDisplayString$2(fact.value), 11, _hoisted_34$1))
                        ])
                      ])
                    ], 2);
                  }), 128))
                ])
              ], 512)
            ], 2),
            castRows.value.length ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_35$1, [
              _cache[29] || (_cache[29] = _createElementVNode$3("div", { class: "sdas-slider-header" }, [
                _createElementVNode$3("div", { class: "sdas-slider-title-section" }, [
                  _createElementVNode$3("div", { class: "sdas-slider-badge" }),
                  _createElementVNode$3("h3", { class: "sdas-slider-title" }, "演职员")
                ])
              ], -1)),
              _createElementVNode$3("div", _hoisted_36$1, [
                _createElementVNode$3("div", {
                  ref_key: "castRail",
                  ref: castRail,
                  class: "sdas-slider-content",
                  tabindex: "0",
                  onScrollPassive: onCastScroll
                }, [
                  (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(castRows.value, (row) => {
                    return _openBlock$3(), _createElementBlock$3("div", {
                      key: castKey(row),
                      class: "sdas-slide-item"
                    }, [
                      _createVNode$2(ActorCard, {
                        item: row,
                        role: row.role,
                        added: isFollowed(row),
                        busy: isBusy(row),
                        loaded: loadedCast.value.has(castKey(row)),
                        onOpen: ($event) => openActor(row),
                        onPoster: ($event) => markCastLoaded(row),
                        onToggle: ($event) => emit("toggle-actor", row)
                      }, null, 8, ["item", "role", "added", "busy", "loaded", "onOpen", "onPoster", "onToggle"])
                    ]);
                  }), 128))
                ], 544),
                _withDirectives(_createVNode$2(_component_v_btn, {
                  class: "sdas-slider-nav is-left",
                  variant: "tonal",
                  icon: "",
                  onClick: _cache[6] || (_cache[6] = _withModifiers(($event) => slideCast(false), ["stop"]))
                }, {
                  default: _withCtx$2(() => [
                    _createVNode$2(_component_v_icon, { class: "sdas-nav-icon" }, {
                      default: _withCtx$2(() => [..._cache[27] || (_cache[27] = [
                        _createTextVNode$1("mdi-chevron-left", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 512), [
                  [_vShow, castNavState.value !== 0 && castNavState.value !== 3]
                ]),
                _withDirectives(_createVNode$2(_component_v_btn, {
                  class: "sdas-slider-nav is-right",
                  variant: "tonal",
                  icon: "",
                  onClick: _cache[7] || (_cache[7] = _withModifiers(($event) => slideCast(true), ["stop"]))
                }, {
                  default: _withCtx$2(() => [
                    _createVNode$2(_component_v_icon, { class: "sdas-nav-icon" }, {
                      default: _withCtx$2(() => [..._cache[28] || (_cache[28] = [
                        _createTextVNode$1("mdi-chevron-right", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 512), [
                  [_vShow, castNavState.value !== 2 && castNavState.value !== 3]
                ])
              ])
            ])) : _createCommentVNode$3("", true),
            hasDouban.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_37$1, [
              _createElementVNode$3("div", {
                class: "sdas-douban-tabs",
                onClick: onDoubanTabsClick
              }, [
                _createElementVNode$3("button", {
                  type: "button",
                  class: _normalizeClass$2(["sdas-douban-tab", { "is-active": doubanTab.value === "interests" }]),
                  "data-douban-tab": "interests"
                }, [
                  _cache[30] || (_cache[30] = _createTextVNode$1(" 短评 ", -1)),
                  doubanTotals.interests ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_38$1, _toDisplayString$2(doubanTotals.interests), 1)) : _createCommentVNode$3("", true)
                ], 2),
                _createElementVNode$3("button", {
                  type: "button",
                  class: _normalizeClass$2(["sdas-douban-tab", { "is-active": doubanTab.value === "reviews" }]),
                  "data-douban-tab": "reviews"
                }, [
                  _cache[31] || (_cache[31] = _createTextVNode$1(" 影评 ", -1)),
                  doubanTotals.reviews ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_39$1, _toDisplayString$2(doubanTotals.reviews), 1)) : _createCommentVNode$3("", true)
                ], 2)
              ]),
              doubanTab.value === "interests" && doubanComments.value.length ? (_openBlock$3(), _createElementBlock$3("ul", _hoisted_40$1, [
                (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(doubanComments.value, (comment) => {
                  return _openBlock$3(), _createElementBlock$3("li", {
                    key: `dc:${comment.id}`,
                    class: "sdas-douban-item"
                  }, [
                    _createElementVNode$3("div", _hoisted_41$1, [
                      comment.avatar ? (_openBlock$3(), _createElementBlock$3("img", {
                        key: 0,
                        src: comment.avatar,
                        alt: "",
                        loading: "lazy"
                      }, null, 8, _hoisted_42$1)) : (_openBlock$3(), _createElementBlock$3("span", _hoisted_43$1, _toDisplayString$2((comment.author || "?").slice(0, 1)), 1))
                    ]),
                    _createElementVNode$3("div", _hoisted_44$1, [
                      _createElementVNode$3("div", _hoisted_45$1, [
                        _createElementVNode$3("span", null, _toDisplayString$2(comment.author), 1),
                        comment.rating ? (_openBlock$3(), _createBlock$2(_component_v_rating, {
                          key: 0,
                          "model-value": comment.rating,
                          length: 5,
                          density: "compact",
                          readonly: "",
                          size: "x-small",
                          class: "ms-2"
                        }, null, 8, ["model-value"])) : _createCommentVNode$3("", true)
                      ]),
                      _createElementVNode$3("div", _hoisted_46$1, _toDisplayString$2(comment.comment), 1),
                      _createElementVNode$3("div", _hoisted_47$1, [
                        comment.time ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_48$1, _toDisplayString$2(comment.time), 1)) : _createCommentVNode$3("", true),
                        comment.votes ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_49$1, "有用 " + _toDisplayString$2(comment.votes), 1)) : _createCommentVNode$3("", true)
                      ])
                    ])
                  ]);
                }), 128))
              ])) : doubanTab.value === "reviews" && doubanReviews.value.length ? (_openBlock$3(), _createElementBlock$3("ul", _hoisted_50$1, [
                (_openBlock$3(true), _createElementBlock$3(_Fragment$3, null, _renderList$3(doubanReviews.value, (review) => {
                  return _openBlock$3(), _createElementBlock$3("li", {
                    key: `dr:${review.id}`,
                    class: "sdas-douban-item"
                  }, [
                    _createElementVNode$3("div", _hoisted_51$1, [
                      review.avatar ? (_openBlock$3(), _createElementBlock$3("img", {
                        key: 0,
                        src: review.avatar,
                        alt: "",
                        loading: "lazy"
                      }, null, 8, _hoisted_52$1)) : (_openBlock$3(), _createElementBlock$3("span", _hoisted_53$1, _toDisplayString$2((review.author || "?").slice(0, 1)), 1))
                    ]),
                    _createElementVNode$3("div", _hoisted_54$1, [
                      _createElementVNode$3("button", {
                        type: "button",
                        class: "sdas-douban-review-title",
                        title: review.url ? "在豆瓣打开这篇影评" : review.title,
                        onClick: ($event) => openUrl(review.url)
                      }, _toDisplayString$2(review.title), 9, _hoisted_55$1),
                      review.abstract ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_56$1, _toDisplayString$2(review.abstract), 1)) : _createCommentVNode$3("", true),
                      _createElementVNode$3("div", _hoisted_57$1, [
                        review.author ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_58$1, _toDisplayString$2(review.author), 1)) : _createCommentVNode$3("", true),
                        review.time ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_59$1, _toDisplayString$2(review.time), 1)) : _createCommentVNode$3("", true),
                        review.useful ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_60$1, "有用 " + _toDisplayString$2(review.useful), 1)) : _createCommentVNode$3("", true)
                      ])
                    ])
                  ]);
                }), 128))
              ])) : _createCommentVNode$3("", true),
              _createElementVNode$3("div", _hoisted_61$1, [
                doubanLoading.value ? (_openBlock$3(), _createBlock$2(_component_v_progress_circular, {
                  key: 0,
                  indeterminate: "",
                  size: "20",
                  width: "2"
                })) : doubanHasMore.value ? (_openBlock$3(), _createBlock$2(_component_v_btn, {
                  key: 1,
                  variant: "text",
                  size: "small",
                  onClick: _cache[8] || (_cache[8] = ($event) => loadMoreDouban())
                }, {
                  default: _withCtx$2(() => [..._cache[32] || (_cache[32] = [
                    _createTextVNode$1(" 加载更多 ", -1)
                  ])]),
                  _: 1
                })) : doubanLoaded.value && !doubanRows.value.length ? (_openBlock$3(), _createElementBlock$3("span", _hoisted_62$1, " 没有数据 ")) : _createCommentVNode$3("", true)
              ])
            ])) : _createCommentVNode$3("", true)
          ], 512)
        ], 64)),
        _createVNode$2(_component_v_snackbar, {
          modelValue: snackbar.value,
          "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => snackbar.value = $event),
          timeout: 3200,
          location: "bottom"
        }, {
          default: _withCtx$2(() => [
            _createTextVNode$1(_toDisplayString$2(snackbarText.value), 1)
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode$2(_component_v_dialog, {
          modelValue: subsetOpen.value,
          "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => subsetOpen.value = $event),
          "max-width": "470",
          scrim: true,
          transition: "dialog-bottom-transition"
        }, {
          default: _withCtx$2(() => [
            __props.subscription ? (_openBlock$3(), _createBlock$2(_component_v_card, { key: 0 }, {
              default: _withCtx$2(() => [
                _createVNode$2(_component_v_card_title, { class: "d-flex align-center gap-2" }, {
                  default: _withCtx$2(() => [
                    _createVNode$2(_component_v_icon, {
                      size: "18",
                      color: "error"
                    }, {
                      default: _withCtx$2(() => [..._cache[33] || (_cache[33] = [
                        _createTextVNode$1("mdi-heart", -1)
                      ])]),
                      _: 1
                    }),
                    _cache[34] || (_cache[34] = _createElementVNode$3("span", { class: "text-subtitle-1 font-weight-bold" }, "订阅设置", -1)),
                    _createVNode$2(_component_v_spacer),
                    stateMeta.value ? (_openBlock$3(), _createBlock$2(_component_v_chip, {
                      key: 0,
                      color: stateMeta.value.color,
                      variant: "tonal",
                      size: "x-small",
                      title: __props.subscription.sub_detail || stateMeta.value.label
                    }, {
                      default: _withCtx$2(() => [
                        _createVNode$2(_component_v_icon, {
                          size: "12",
                          class: "mr-1"
                        }, {
                          default: _withCtx$2(() => [
                            _createTextVNode$1(_toDisplayString$2(stateMeta.value.icon), 1)
                          ]),
                          _: 1
                        }),
                        _createTextVNode$1(" " + _toDisplayString$2(stateMeta.value.label), 1)
                      ]),
                      _: 1
                    }, 8, ["color", "title"])) : _createCommentVNode$3("", true)
                  ]),
                  _: 1
                }),
                _createVNode$2(_component_v_divider),
                _createVNode$2(_component_v_card_text, { class: "sdas-subset-body" }, {
                  default: _withCtx$2(() => [
                    __props.subEditable ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_63, [
                      _createElementVNode$3("div", _hoisted_64, [
                        _cache[35] || (_cache[35] = _createElementVNode$3("div", { class: "sdas-subset-label" }, "订阅站点", -1)),
                        _createElementVNode$3("div", _hoisted_65, _toDisplayString$2(subSitesHint.value), 1)
                      ]),
                      _createVNode$2(_component_v_select, {
                        "model-value": localSites.value,
                        items: siteOptions.value,
                        "item-title": "name",
                        "item-value": "id",
                        loading: optionsLoading.value,
                        multiple: "",
                        chips: "",
                        "closable-chips": "",
                        clearable: "",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        class: "sdas-subset-input",
                        disabled: savingTargets.value,
                        "onUpdate:modelValue": onSitesChange
                      }, null, 8, ["model-value", "items", "loading", "disabled"])
                    ])) : _createCommentVNode$3("", true),
                    __props.subEditable ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_66, [
                      _createElementVNode$3("div", _hoisted_67, [
                        _cache[36] || (_cache[36] = _createElementVNode$3("div", { class: "sdas-subset-label" }, "下载器", -1)),
                        _createElementVNode$3("div", _hoisted_68, _toDisplayString$2(subDownloaderHint.value), 1)
                      ]),
                      _createVNode$2(_component_v_select, {
                        "model-value": localDownloader.value,
                        items: downloaderOptions.value,
                        "item-title": "title",
                        "item-value": "value",
                        loading: optionsLoading.value,
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        class: "sdas-subset-input",
                        disabled: savingTargets.value,
                        "onUpdate:modelValue": onDownloaderChange
                      }, null, 8, ["model-value", "items", "loading", "disabled"])
                    ])) : _createCommentVNode$3("", true),
                    __props.subEditable ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_69, [
                      _createElementVNode$3("div", _hoisted_70, [
                        _cache[37] || (_cache[37] = _createElementVNode$3("div", { class: "sdas-subset-label" }, "保存目录", -1)),
                        _createElementVNode$3("div", _hoisted_71, _toDisplayString$2(subSavePathHint.value), 1)
                      ]),
                      _createVNode$2(_component_v_select, {
                        "model-value": localSavePath.value,
                        items: pathOptions.value,
                        "item-title": "title",
                        "item-value": "value",
                        density: "compact",
                        "hide-details": "",
                        variant: "outlined",
                        class: "sdas-subset-input",
                        disabled: savingTargets.value || optionsLoading.value,
                        "onUpdate:modelValue": onSavePathChange
                      }, null, 8, ["model-value", "items", "disabled"])
                    ])) : _createCommentVNode$3("", true),
                    __props.subscription.torrent_url ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_72, [
                      _createElementVNode$3("div", _hoisted_73, [
                        _cache[38] || (_cache[38] = _createElementVNode$3("div", { class: "sdas-subset-label" }, "种子", -1)),
                        _createElementVNode$3("div", {
                          class: "sdas-subset-hint sdas-subset-torrent",
                          title: __props.subscription.torrent_title
                        }, _toDisplayString$2(__props.subscription.torrent_title || "已提交的种子"), 9, _hoisted_74)
                      ]),
                      _createVNode$2(_component_v_btn, {
                        href: __props.subscription.torrent_url,
                        target: "_blank",
                        rel: "noopener",
                        variant: "tonal",
                        color: "info",
                        size: "small",
                        "prepend-icon": "mdi-open-in-new"
                      }, {
                        default: _withCtx$2(() => [..._cache[39] || (_cache[39] = [
                          _createTextVNode$1(" 种子页面 ", -1)
                        ])]),
                        _: 1
                      }, 8, ["href"])
                    ])) : _createCommentVNode$3("", true),
                    __props.subEditable && targetsDirty.value ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_75, [
                      _cache[41] || (_cache[41] = _createElementVNode$3("div", { class: "sdas-subset-cell" }, [
                        _createElementVNode$3("div", { class: "sdas-subset-label" }, "保存上面三项"),
                        _createElementVNode$3("div", { class: "sdas-subset-hint" }, "留空的项按配置页的默认值走")
                      ], -1)),
                      _createVNode$2(_component_v_btn, {
                        variant: "flat",
                        color: "error",
                        size: "small",
                        "prepend-icon": "mdi-content-save-outline",
                        loading: savingTargets.value,
                        onClick: _cache[10] || (_cache[10] = ($event) => saveTargets())
                      }, {
                        default: _withCtx$2(() => [..._cache[40] || (_cache[40] = [
                          _createTextVNode$1(" 保存 ", -1)
                        ])]),
                        _: 1
                      }, 8, ["loading"])
                    ])) : _createCommentVNode$3("", true),
                    __props.subEditable ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_76, [
                      _cache[43] || (_cache[43] = _createElementVNode$3("div", { class: "sdas-subset-cell" }, [
                        _createElementVNode$3("div", { class: "sdas-subset-label" }, "立即搜索一次"),
                        _createElementVNode$3("div", { class: "sdas-subset-hint" }, "不等下一轮定时，现在就搜（冷却也一并清掉）")
                      ], -1)),
                      _createVNode$2(_component_v_btn, {
                        variant: "tonal",
                        color: "info",
                        size: "small",
                        "prepend-icon": "mdi-magnify",
                        loading: searchingNow.value,
                        onClick: _cache[11] || (_cache[11] = ($event) => searchNow())
                      }, {
                        default: _withCtx$2(() => [..._cache[42] || (_cache[42] = [
                          _createTextVNode$1(" 立即搜索 ", -1)
                        ])]),
                        _: 1
                      }, 8, ["loading"])
                    ])) : _createCommentVNode$3("", true),
                    __props.subscription.sub_detail ? (_openBlock$3(), _createElementBlock$3("div", _hoisted_77, [
                      _createTextVNode$1(" 上次处理：" + _toDisplayString$2(__props.subscription.sub_detail) + " ", 1),
                      __props.subscription.sub_time ? (_openBlock$3(), _createElementBlock$3(_Fragment$3, { key: 0 }, [
                        _createTextVNode$1("（" + _toDisplayString$2(__props.subscription.sub_time) + "）", 1)
                      ], 64)) : _createCommentVNode$3("", true)
                    ])) : _createCommentVNode$3("", true)
                  ]),
                  _: 1
                }),
                _createVNode$2(_component_v_divider),
                _createVNode$2(_component_v_card_actions, null, {
                  default: _withCtx$2(() => [
                    _createVNode$2(_component_v_spacer),
                    _createVNode$2(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[12] || (_cache[12] = ($event) => subsetOpen.value = false)
                    }, {
                      default: _withCtx$2(() => [..._cache[44] || (_cache[44] = [
                        _createTextVNode$1("关闭", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })) : _createCommentVNode$3("", true)
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode$2(StickyBack, {
          anchor: pageRoot.value,
          title: "返回",
          onBack: _cache[14] || (_cache[14] = ($event) => emit("back"))
        }, null, 8, ["anchor"])
      ], 2);
    };
  }
});

const WorkDetail = /* @__PURE__ */ _export_sfc(_sfc_main$3, [["__scopeId", "data-v-1532979f"]]);

const {defineComponent:_defineComponent$2} = await importShared('vue');

const {normalizeStyle:_normalizeStyle$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,renderSlot:_renderSlot,createElementVNode:_createElementVNode$2} = await importShared('vue');

const _hoisted_1$1 = ["data-progressive-grid-index"];
const {computed: computed$2,onActivated,onDeactivated,onMounted: onMounted$2,onUnmounted: onUnmounted$1,ref: ref$2,watch: watch$2} = await importShared('vue');

const _sfc_main$2 = /* @__PURE__ */ _defineComponent$2({
  __name: "ProgressiveCardGrid",
  props: {
    items: {},
    minItemWidth: { default: 144 },
    itemAspectRatio: { default: 1.5 },
    gap: { default: 16 },
    initialCount: { default: 6 },
    batchSize: { default: 6 },
    overscanRows: { default: 4 },
    getItemKey: { type: Function, default: void 0 }
  },
  setup(__props) {
    const props = __props;
    const containerRef = ref$2(null);
    const trackRef = ref$2(null);
    const layoutWidth = ref$2(0);
    const viewportTop = ref$2(0);
    const viewportBottom = ref$2(0);
    const heightVersion = ref$2(0);
    const frozenVisibleRange = ref$2(null);
    const progressiveStartIndex = ref$2(0);
    const progressiveEndIndex = ref$2(0);
    const itemHeights = /* @__PURE__ */ new Map();
    const observedElements = /* @__PURE__ */ new Map();
    const keyElements = /* @__PURE__ */ new Map();
    const itemRefCallbacks = /* @__PURE__ */ new Map();
    let resizeObserver = null;
    let itemResizeObserver = null;
    let overlayLockObserver = null;
    let scrollTarget = null;
    let layoutFrameId = null;
    let scrollFrameId = null;
    let progressiveFrameId = null;
    let mounted = false;
    let lastMeasuredColumnCount = 0;
    let lastMeasuredColumnWidth = 0;
    let documentOverlayLocked = false;
    const safeGap = computed$2(() => Math.max(0, props.gap));
    const safeInitialCount = computed$2(() => Math.max(1, Math.floor(props.initialCount)));
    const safeBatchSize = computed$2(() => Math.max(1, Math.floor(props.batchSize)));
    const safeMinItemWidth = computed$2(() => Math.max(1, props.minItemWidth));
    const safeOverscanRows = computed$2(() => Math.max(1, props.overscanRows));
    const columnCount = computed$2(() => {
      if (!layoutWidth.value) return 1;
      return Math.max(1, Math.floor((layoutWidth.value + safeGap.value) / (safeMinItemWidth.value + safeGap.value)));
    });
    const columnWidth = computed$2(() => {
      const columns = columnCount.value;
      const width = layoutWidth.value || safeMinItemWidth.value;
      return Math.max(1, (width - safeGap.value * (columns - 1)) / columns);
    });
    const estimatedHeight = computed$2(() => Math.max(1, columnWidth.value * props.itemAspectRatio));
    const itemKeys = computed$2(() => props.items.map((item, index) => getComparableKey(item, index)));
    const keyIndexMap = computed$2(() => {
      const map = /* @__PURE__ */ new Map();
      itemKeys.value.forEach((key, index) => map.set(key, index));
      return map;
    });
    const rowMetrics = computed$2(() => {
      void heightVersion.value;
      const rows = Math.ceil(props.items.length / columnCount.value);
      const heights = [];
      const measuredRows = [];
      const offsets = [0];
      for (let row = 0; row < rows; row += 1) {
        const startIndex = row * columnCount.value;
        const endIndex = Math.min(startIndex + columnCount.value, props.items.length);
        let rowHeight = 0;
        let hasUnmeasuredItem = false;
        for (let index = startIndex; index < endIndex; index += 1) {
          const height = itemHeights.get(itemKeys.value[index]);
          if (height && height > 0) {
            rowHeight = Math.max(rowHeight, height);
          } else {
            hasUnmeasuredItem = true;
          }
        }
        if (hasUnmeasuredItem) rowHeight = Math.max(rowHeight, estimatedHeight.value);
        else rowHeight = Math.max(rowHeight, 1);
        heights.push(rowHeight);
        measuredRows.push(!hasUnmeasuredItem);
        offsets.push(offsets[row] + rowHeight + (row < rows - 1 ? safeGap.value : 0));
      }
      return { heights, measuredRows, offsets, rowCount: rows, totalHeight: offsets[rows] ?? 0 };
    });
    const totalHeight = computed$2(() => rowMetrics.value.totalHeight);
    const calculatedViewportRange = computed$2((previous) => {
      const { offsets, rowCount } = rowMetrics.value;
      if (!props.items.length || rowCount === 0) {
        return { endIndex: 0, endRow: 0, startIndex: 0, startRow: 0 };
      }
      const top = Math.max(0, Math.min(viewportTop.value, totalHeight.value));
      const bottom = Math.max(top, Math.min(viewportBottom.value, totalHeight.value));
      const firstVisibleRow = findFirstRowAtOrAfterOffset(offsets, top);
      const lastVisibleRow = findLastRowAtOrBeforeOffset(offsets, rowCount, bottom);
      const nextRange = {
        endIndex: Math.min(props.items.length, (lastVisibleRow + 1) * columnCount.value),
        endRow: lastVisibleRow,
        startIndex: firstVisibleRow * columnCount.value,
        startRow: firstVisibleRow
      };
      if (previous && previous.startIndex === nextRange.startIndex && previous.endIndex === nextRange.endIndex && previous.startRow === nextRange.startRow && previous.endRow === nextRange.endRow) {
        return previous;
      }
      return nextRange;
    });
    const calculatedVisibleRange = computed$2(() => {
      if (!props.items.length) return calculatedViewportRange.value;
      const viewportRange = calculatedViewportRange.value;
      const rowCount = rowMetrics.value.rowCount;
      const startRow = clamp(viewportRange.startRow - safeOverscanRows.value, 0, rowCount - 1);
      const endRow = clamp(viewportRange.endRow + safeOverscanRows.value, startRow, rowCount - 1);
      return {
        endIndex: Math.min(props.items.length, (endRow + 1) * columnCount.value),
        endRow,
        startIndex: startRow * columnCount.value,
        startRow
      };
    });
    const visibleRange = computed$2(() => frozenVisibleRange.value ?? calculatedVisibleRange.value);
    const renderedVisibleRange = computed$2((previous) => {
      const range = visibleRange.value;
      if (frozenVisibleRange.value || range.endIndex <= range.startIndex) {
        return range;
      }
      const viewportRange = calculatedViewportRange.value;
      const initialEndIndex = Math.min(
        range.endIndex,
        Math.max(
          viewportRange.endIndex,
          Math.ceil((viewportRange.startIndex + safeInitialCount.value) / columnCount.value) * columnCount.value
        )
      );
      const stagedStartIndex = clamp(progressiveStartIndex.value, range.startIndex, viewportRange.startIndex);
      const stagedEndIndex = clamp(
        Math.max(progressiveEndIndex.value, initialEndIndex),
        viewportRange.endIndex,
        range.endIndex
      );
      const startRow = Math.max(range.startRow, Math.floor(stagedStartIndex / columnCount.value));
      const endRow = Math.min(range.endRow, Math.max(range.startRow, Math.ceil(stagedEndIndex / columnCount.value) - 1));
      const nextRange = {
        ...range,
        endIndex: Math.min(range.endIndex, (endRow + 1) * columnCount.value),
        endRow,
        startIndex: startRow * columnCount.value,
        startRow
      };
      if (previous && previous.startIndex === nextRange.startIndex && previous.endIndex === nextRange.endIndex && previous.startRow === nextRange.startRow && previous.endRow === nextRange.endRow) {
        return previous;
      }
      return nextRange;
    });
    const visibleCells = computed$2(() => {
      const cells = [];
      const range = renderedVisibleRange.value;
      for (let index = range.startIndex; index < range.endIndex; index += 1) {
        cells.push({ item: props.items[index], index, key: itemKeys.value[index] });
      }
      return cells;
    });
    const topSpacerHeight = computed$2(() => rowMetrics.value.offsets[renderedVisibleRange.value.startRow] ?? 0);
    const visibleBlockHeight = computed$2(() => {
      const range = renderedVisibleRange.value;
      if (!props.items.length || range.endIndex <= range.startIndex) return 0;
      return Math.max(
        (rowMetrics.value.offsets[range.endRow] ?? 0) + (rowMetrics.value.heights[range.endRow] ?? 0) - (rowMetrics.value.offsets[range.startRow] ?? 0),
        0
      );
    });
    const bottomSpacerHeight = computed$2(
      () => Math.max(totalHeight.value - topSpacerHeight.value - visibleBlockHeight.value, 0)
    );
    const gridStyle = computed$2(() => ({
      columnGap: `${safeGap.value}px`,
      gridTemplateColumns: `repeat(${columnCount.value}, minmax(0, 1fr))`,
      rowGap: `${safeGap.value}px`
    }));
    function clamp(value, min, max) {
      return Math.min(Math.max(value, min), max);
    }
    function getComparableKey(item, index) {
      if (props.getItemKey) return props.getItemKey(item, index);
      return index;
    }
    function getFallbackLayoutWidth() {
      if (typeof window === "undefined") return safeMinItemWidth.value;
      return Math.max(document.documentElement.clientWidth || window.innerWidth || 0, safeMinItemWidth.value);
    }
    function findFirstRowAtOrAfterOffset(offsets, offset) {
      const heights = rowMetrics.value.heights;
      let low = 0;
      let high = heights.length - 1;
      let answer = 0;
      while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        if (offsets[mid] + heights[mid] >= offset) {
          answer = mid;
          high = mid - 1;
        } else {
          low = mid + 1;
        }
      }
      return answer;
    }
    function findLastRowAtOrBeforeOffset(offsets, rowCount, offset) {
      let low = 0;
      let high = rowCount - 1;
      let answer = 0;
      while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        if (offsets[mid] <= offset) {
          answer = mid;
          low = mid + 1;
        } else {
          high = mid - 1;
        }
      }
      return answer;
    }
    function isDocumentOverlayLocked() {
      return typeof document !== "undefined" && document.documentElement.classList.contains("v-overlay-scroll-blocked");
    }
    function shouldPauseVirtualSync() {
      return isDocumentOverlayLocked();
    }
    function freezeVisibleRange() {
      if (frozenVisibleRange.value) return;
      cancelProgressiveRender();
      frozenVisibleRange.value = { ...renderedVisibleRange.value };
    }
    function releaseVisibleRange() {
      frozenVisibleRange.value = null;
      syncProgressiveWindow();
      queueProgressiveRender();
    }
    function handleOverlayLockChange() {
      const nextOverlayLocked = isDocumentOverlayLocked();
      if (nextOverlayLocked === documentOverlayLocked) return;
      documentOverlayLocked = nextOverlayLocked;
      if (shouldPauseVirtualSync()) {
        freezeVisibleRange();
        return;
      }
      invalidateScrollTargetCache();
      releaseVisibleRange();
      queueLayoutSync();
    }
    function getElementFromRef(element) {
      if (!element || typeof HTMLElement === "undefined") return null;
      if (element instanceof HTMLElement) return element;
      if (!("$el" in element)) return null;
      const componentElement = element.$el;
      return componentElement instanceof HTMLElement ? componentElement : null;
    }
    function getRowHeight(row) {
      const startIndex = row * columnCount.value;
      const endIndex = Math.min(startIndex + columnCount.value, props.items.length);
      let rowHeight = 0;
      let hasUnmeasuredItem = false;
      for (let index = startIndex; index < endIndex; index += 1) {
        const height = itemHeights.get(itemKeys.value[index]);
        if (height && height > 0) rowHeight = Math.max(rowHeight, height);
        else hasUnmeasuredItem = true;
      }
      if (hasUnmeasuredItem) return Math.max(rowHeight, estimatedHeight.value);
      return Math.max(rowHeight, 1);
    }
    function ensureItemResizeObserver() {
      if (itemResizeObserver || typeof ResizeObserver === "undefined") return;
      itemResizeObserver = new ResizeObserver((entries) => {
        if (shouldPauseVirtualSync()) {
          freezeVisibleRange();
          return;
        }
        let shouldUpdate = false;
        let scrollAdjustment = 0;
        const currentViewportTop = viewportTop.value;
        const currentOffsets = rowMetrics.value.offsets;
        entries.forEach((entry) => {
          const element = entry.target;
          if (!(element instanceof HTMLElement)) return;
          const key = observedElements.get(element);
          const index = key === void 0 ? void 0 : keyIndexMap.value.get(key);
          if (key === void 0 || index === void 0) return;
          const borderSize = Array.isArray(entry.borderBoxSize) ? entry.borderBoxSize[0] : entry.borderBoxSize;
          const nextHeight = borderSize?.blockSize || entry.contentRect.height;
          const previousHeight = itemHeights.get(key);
          if (!nextHeight || Math.abs((previousHeight ?? 0) - nextHeight) < 0.5) return;
          const row = Math.floor(index / columnCount.value);
          const rowWasFullyMeasured = rowMetrics.value.measuredRows[row];
          const previousRowHeight = getRowHeight(row);
          const previousRowBottom = (currentOffsets[row] ?? 0) + previousRowHeight;
          if (rowWasFullyMeasured && previousHeight !== void 0 && previousHeight < previousRowHeight - 0.5 && nextHeight <= previousRowHeight + 0.5) {
            return;
          }
          itemHeights.set(key, nextHeight);
          const nextRowHeight = getRowHeight(row);
          const delta = nextRowHeight - previousRowHeight;
          if (Math.abs(delta) >= 0.5 && previousRowBottom < currentViewportTop) {
            scrollAdjustment += delta;
          }
          shouldUpdate = true;
        });
        if (!shouldUpdate) return;
        heightVersion.value += 1;
        if (Math.abs(scrollAdjustment) >= 0.5) adjustScrollTop(scrollAdjustment);
        queueViewportSync();
      });
    }
    function setItemRef(element, key) {
      const htmlElement = getElementFromRef(element);
      const previousElement = keyElements.get(key);
      if (!htmlElement) {
        if (previousElement) {
          itemResizeObserver?.unobserve(previousElement);
          observedElements.delete(previousElement);
          keyElements.delete(key);
        }
        return;
      }
      if (previousElement === htmlElement) return;
      ensureItemResizeObserver();
      if (previousElement) {
        itemResizeObserver?.unobserve(previousElement);
        observedElements.delete(previousElement);
      }
      observedElements.set(htmlElement, key);
      keyElements.set(key, htmlElement);
      itemResizeObserver?.observe(htmlElement);
    }
    function getItemRef(key) {
      const existingCallback = itemRefCallbacks.get(key);
      if (existingCallback) return existingCallback;
      const callback = (element) => setItemRef(element, key);
      itemRefCallbacks.set(key, callback);
      return callback;
    }
    let targetCache = /* @__PURE__ */ new WeakMap();
    function invalidateScrollTargetCache() {
      targetCache = /* @__PURE__ */ new WeakMap();
    }
    function isScrollableOverflow(overflowY) {
      return overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay";
    }
    function findNearestScrollTarget(element) {
      if (!element) return window;
      let parent = element.parentElement;
      const visited = [];
      let target = window;
      while (parent && parent !== document.body && parent !== document.documentElement) {
        const cachedTarget = targetCache.get(parent);
        if (cachedTarget) {
          target = cachedTarget;
          break;
        }
        visited.push(parent);
        if (isScrollableOverflow(window.getComputedStyle(parent).overflowY)) {
          target = parent;
          break;
        }
        parent = parent.parentElement;
      }
      visited.forEach((ancestor) => targetCache.set(ancestor, target));
      return target;
    }
    function findScrollTarget() {
      return findNearestScrollTarget(containerRef.value);
    }
    function addScrollListener(target) {
      target.addEventListener("scroll", queueViewportSync, { passive: true });
    }
    function removeScrollListener(target) {
      target?.removeEventListener("scroll", queueViewportSync);
    }
    function refreshScrollTarget() {
      if (!mounted) return;
      const nextTarget = findScrollTarget();
      if (scrollTarget === nextTarget) return;
      removeScrollListener(scrollTarget);
      scrollTarget = nextTarget;
      addScrollListener(scrollTarget);
    }
    function handleWindowResize() {
      invalidateScrollTargetCache();
      queueLayoutSync();
    }
    function syncLayoutWidth() {
      const element = trackRef.value;
      if (!element) {
        if (layoutWidth.value <= 0) layoutWidth.value = getFallbackLayoutWidth();
        return;
      }
      const nextWidth = element.clientWidth;
      if (nextWidth > 0) {
        layoutWidth.value = nextWidth;
        return;
      }
      if (layoutWidth.value <= 0) layoutWidth.value = getFallbackLayoutWidth();
    }
    function syncViewport() {
      const element = trackRef.value;
      if (!element) {
        if (viewportBottom.value <= viewportTop.value) {
          viewportTop.value = 0;
          viewportBottom.value = typeof window === "undefined" ? 0 : window.innerHeight;
        }
        return;
      }
      const trackRect = element.getBoundingClientRect();
      const viewportRect = scrollTarget && scrollTarget !== window ? scrollTarget.getBoundingClientRect() : { bottom: window.innerHeight, top: 0 };
      const nextViewportTop = viewportRect.top - trackRect.top;
      const nextViewportBottom = viewportRect.bottom - trackRect.top;
      if (nextViewportBottom > nextViewportTop) {
        viewportTop.value = nextViewportTop;
        viewportBottom.value = nextViewportBottom;
      }
    }
    function queueLayoutSync() {
      if (typeof window === "undefined" || layoutFrameId !== null) return;
      layoutFrameId = window.requestAnimationFrame(() => {
        layoutFrameId = null;
        if (shouldPauseVirtualSync()) {
          freezeVisibleRange();
          return;
        }
        releaseVisibleRange();
        syncLayoutWidth();
        refreshScrollTarget();
        syncViewport();
      });
    }
    function queueViewportSync() {
      if (typeof window === "undefined" || scrollFrameId !== null) return;
      scrollFrameId = window.requestAnimationFrame(() => {
        scrollFrameId = null;
        if (shouldPauseVirtualSync()) {
          freezeVisibleRange();
          return;
        }
        releaseVisibleRange();
        syncViewport();
      });
    }
    function cancelProgressiveRender() {
      if (progressiveFrameId === null) return;
      window.cancelAnimationFrame(progressiveFrameId);
      progressiveFrameId = null;
    }
    function syncProgressiveWindow() {
      if (frozenVisibleRange.value) return;
      progressiveStartIndex.value = clamp(progressiveStartIndex.value, 0, props.items.length);
      progressiveEndIndex.value = clamp(progressiveEndIndex.value, 0, props.items.length);
      const range = calculatedVisibleRange.value;
      const viewportRange = calculatedViewportRange.value;
      const overlapsViewport = progressiveEndIndex.value > viewportRange.startIndex && progressiveStartIndex.value < viewportRange.endIndex;
      if (!overlapsViewport) {
        progressiveStartIndex.value = viewportRange.startIndex;
        progressiveEndIndex.value = viewportRange.endIndex;
      } else {
        progressiveStartIndex.value = clamp(progressiveStartIndex.value, range.startIndex, viewportRange.startIndex);
        progressiveEndIndex.value = clamp(progressiveEndIndex.value, viewportRange.endIndex, range.endIndex);
      }
      const initialEndIndex = Math.min(
        range.endIndex,
        Math.max(
          viewportRange.endIndex,
          Math.ceil((viewportRange.startIndex + safeInitialCount.value) / columnCount.value) * columnCount.value
        )
      );
      progressiveEndIndex.value = Math.max(progressiveEndIndex.value, initialEndIndex);
    }
    function queueProgressiveRender() {
      if (typeof window === "undefined" || !mounted || progressiveFrameId !== null || frozenVisibleRange.value) {
        return;
      }
      const range = renderedVisibleRange.value;
      const targetRange = visibleRange.value;
      if (range.endIndex >= targetRange.endIndex && range.startIndex <= targetRange.startIndex) {
        return;
      }
      progressiveFrameId = window.requestAnimationFrame(() => {
        progressiveFrameId = null;
        const batchRows = Math.max(1, Math.floor(safeBatchSize.value / columnCount.value));
        const batchItems = batchRows * columnCount.value;
        if (range.endIndex < targetRange.endIndex) {
          progressiveEndIndex.value = Math.min(targetRange.endIndex, range.endIndex + batchItems);
        } else {
          progressiveStartIndex.value = Math.max(targetRange.startIndex, range.startIndex - batchItems);
        }
        queueProgressiveRender();
      });
    }
    function adjustScrollTop(delta) {
      if (!scrollTarget || Math.abs(delta) < 0.5) return;
      if (scrollTarget === window) {
        window.scrollBy({ behavior: "auto", top: delta });
      } else {
        scrollTarget.scrollTop += delta;
      }
    }
    function pruneMeasurements() {
      const keys = new Set(itemKeys.value);
      let changed = false;
      Array.from(itemHeights.keys()).forEach((key) => {
        if (!keys.has(key)) {
          itemHeights.delete(key);
          changed = true;
        }
      });
      Array.from(keyElements.entries()).forEach(([key, element]) => {
        if (!keys.has(key)) {
          itemResizeObserver?.unobserve(element);
          observedElements.delete(element);
          keyElements.delete(key);
        }
      });
      Array.from(itemRefCallbacks.keys()).forEach((key) => {
        if (!keys.has(key)) itemRefCallbacks.delete(key);
      });
      if (changed) heightVersion.value += 1;
    }
    function preservesLeadingKeys(nextKeys, previousKeys = []) {
      if (!previousKeys.length || !nextKeys.length) return false;
      const sharedLength = Math.min(nextKeys.length, previousKeys.length);
      for (let index = 0; index < sharedLength; index += 1) {
        if (nextKeys[index] !== previousKeys[index]) return false;
      }
      return true;
    }
    function hasSameKeySet(nextKeys, previousKeys = []) {
      if (nextKeys.length !== previousKeys.length) return false;
      const previousKeySet = new Set(previousKeys);
      return previousKeySet.size === nextKeys.length && nextKeys.every((key) => previousKeySet.has(key));
    }
    function syncMeasurementsForItems(nextKeys, previousKeys = []) {
      if (!preservesLeadingKeys(nextKeys, previousKeys) && !hasSameKeySet(nextKeys, previousKeys) && itemHeights.size) {
        itemHeights.clear();
        heightVersion.value += 1;
      }
      pruneMeasurements();
    }
    function invalidateMeasurementsForLayoutChange() {
      const nextColumnCount = columnCount.value;
      const nextColumnWidth = columnWidth.value;
      if (lastMeasuredColumnCount === nextColumnCount && Math.abs(lastMeasuredColumnWidth - nextColumnWidth) < 1) {
        return;
      }
      lastMeasuredColumnCount = nextColumnCount;
      lastMeasuredColumnWidth = nextColumnWidth;
      if (!itemHeights.size) return;
      itemHeights.clear();
      heightVersion.value += 1;
    }
    onMounted$2(() => {
      mounted = true;
      documentOverlayLocked = isDocumentOverlayLocked();
      scrollTarget = findScrollTarget();
      addScrollListener(scrollTarget);
      if (trackRef.value?.clientWidth) syncLayoutWidth();
      resizeObserver = new ResizeObserver(queueLayoutSync);
      if (trackRef.value) resizeObserver.observe(trackRef.value);
      if (typeof MutationObserver !== "undefined") {
        overlayLockObserver = new MutationObserver(handleOverlayLockChange);
        overlayLockObserver.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ["class"]
        });
      }
      window.addEventListener("resize", handleWindowResize, { passive: true });
      queueLayoutSync();
      queueProgressiveRender();
    });
    onActivated(() => {
      mounted = true;
      refreshScrollTarget();
      queueLayoutSync();
      queueProgressiveRender();
      requestAnimationFrame(queueLayoutSync);
    });
    onDeactivated(() => {
      mounted = false;
      cancelProgressiveRender();
      removeScrollListener(scrollTarget);
      scrollTarget = null;
    });
    onUnmounted$1(() => {
      mounted = false;
      removeScrollListener(scrollTarget);
      scrollTarget = null;
      window.removeEventListener("resize", handleWindowResize);
      resizeObserver?.disconnect();
      resizeObserver = null;
      itemResizeObserver?.disconnect();
      itemResizeObserver = null;
      overlayLockObserver?.disconnect();
      overlayLockObserver = null;
      if (layoutFrameId !== null) {
        window.cancelAnimationFrame(layoutFrameId);
        layoutFrameId = null;
      }
      if (scrollFrameId !== null) {
        window.cancelAnimationFrame(scrollFrameId);
        scrollFrameId = null;
      }
      cancelProgressiveRender();
    });
    watch$2(
      itemKeys,
      (nextKeys, previousKeys) => {
        if (!preservesLeadingKeys(nextKeys, previousKeys) && !hasSameKeySet(nextKeys, previousKeys)) {
          cancelProgressiveRender();
          progressiveStartIndex.value = 0;
          progressiveEndIndex.value = 0;
        }
        syncMeasurementsForItems(nextKeys, previousKeys);
        syncProgressiveWindow();
        queueLayoutSync();
        queueProgressiveRender();
      },
      { immediate: true }
    );
    watch$2([columnCount, columnWidth], () => {
      cancelProgressiveRender();
      invalidateMeasurementsForLayoutChange();
      syncProgressiveWindow();
      queueViewportSync();
      queueProgressiveRender();
    });
    watch$2([calculatedViewportRange, calculatedVisibleRange], () => {
      cancelProgressiveRender();
      syncProgressiveWindow();
      queueProgressiveRender();
    });
    return (_ctx, _cache) => {
      return _openBlock$2(), _createElementBlock$2("div", {
        ref_key: "containerRef",
        ref: containerRef,
        class: "sdas-pcg"
      }, [
        _createElementVNode$2("div", {
          ref_key: "trackRef",
          ref: trackRef,
          class: "sdas-pcg-track"
        }, [
          topSpacerHeight.value > 0 ? (_openBlock$2(), _createElementBlock$2("div", {
            key: 0,
            class: "sdas-pcg-spacer",
            style: _normalizeStyle$2({ blockSize: `${topSpacerHeight.value}px` }),
            "aria-hidden": "true"
          }, null, 4)) : _createCommentVNode$2("", true),
          visibleCells.value.length > 0 ? (_openBlock$2(), _createElementBlock$2("div", {
            key: 1,
            class: "sdas-pcg-grid",
            style: _normalizeStyle$2(gridStyle.value)
          }, [
            (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(visibleCells.value, (cell) => {
              return _openBlock$2(), _createElementBlock$2("div", {
                key: cell.key,
                ref_for: true,
                ref: getItemRef(cell.key),
                class: "sdas-pcg-item",
                "data-progressive-grid-index": cell.index
              }, [
                _renderSlot(_ctx.$slots, "default", {
                  item: cell.item,
                  index: cell.index
                }, void 0, true)
              ], 8, _hoisted_1$1);
            }), 128))
          ], 4)) : _createCommentVNode$2("", true),
          bottomSpacerHeight.value > 0 ? (_openBlock$2(), _createElementBlock$2("div", {
            key: 2,
            class: "sdas-pcg-spacer",
            style: _normalizeStyle$2({ blockSize: `${bottomSpacerHeight.value}px` }),
            "aria-hidden": "true"
          }, null, 4)) : _createCommentVNode$2("", true)
        ], 512)
      ], 512);
    };
  }
});

const ProgressiveCardGrid = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-430b3e33"]]);

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,toDisplayString:_toDisplayString$1,normalizeClass:_normalizeClass$1,createElementVNode:_createElementVNode$1,normalizeStyle:_normalizeStyle$1,createCommentVNode:_createCommentVNode$1,Transition:_Transition,withCtx:_withCtx$1,createVNode:_createVNode$1,Teleport:_Teleport$1,createBlock:_createBlock$1} = await importShared('vue');

const {computed: computed$1,onBeforeUnmount,onMounted: onMounted$1,ref: ref$1,watch: watch$1} = await importShared('vue');

const HOT_ZONE = 18;
const KEEP_ZONE = 54;
const VERTICAL_SLACK = 28;
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "AlphaIndex",
  props: {
    stops: {},
    anchor: { default: null }
  },
  emits: ["jump"],
  setup(__props, { emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const railStyle = ref$1({ top: "0px", height: "0px", right: "0px" });
    const hintStyle = ref$1({ top: "0px" });
    const trackTop = ref$1(0);
    const current = ref$1("");
    const visible = ref$1(false);
    const active = ref$1(false);
    const hint = ref$1("");
    const trackHeight = ref$1(0);
    let hovering = false;
    let dragging = false;
    let lastJumped = "";
    const hasStops = computed$1(() => props.stops.length > 1);
    function clamp(value, min, max) {
      if (!Number.isFinite(value)) return min;
      return Math.min(max, Math.max(min, value));
    }
    function ratioAt(clientY) {
      if (trackHeight.value <= 0) return 0;
      return clamp((clientY - trackTop.value) / trackHeight.value, 0, 1);
    }
    function letterAtRatio(ratio) {
      const list = props.stops;
      if (!list.length) return "";
      let hit = list[0].letter;
      for (const stop of list) {
        if (stop.ratio <= ratio + 1e-6) hit = stop.letter;
        else break;
      }
      return hit;
    }
    function letterAtPointer(clientY) {
      const list = props.stops;
      if (!list.length) return { letter: "", ratio: 0 };
      const ratio = ratioAt(clientY);
      const index = clamp(Math.floor(ratio * list.length), 0, list.length - 1);
      return { letter: list[index].letter, ratio: (index + 0.5) / list.length };
    }
    function placeHint(ratio) {
      const y = clamp(ratio * trackHeight.value, 0, trackHeight.value);
      hintStyle.value = { top: `${Math.round(y)}px` };
    }
    function hide() {
      visible.value = false;
      active.value = false;
      hovering = false;
      hint.value = "";
    }
    function sync() {
      const el = props.anchor;
      if (!el || typeof window === "undefined") {
        hide();
        return;
      }
      const rect = el.getBoundingClientRect();
      const viewportHeight = window.innerHeight || 0;
      if (!hasStops.value || rect.bottom < 160 || rect.top > viewportHeight - 80 || rect.width < 200) {
        hide();
        return;
      }
      const top = Math.max(rect.top + 8, 76);
      const bottom = Math.min(rect.bottom - 8, viewportHeight - 16);
      const height = Math.max(96, bottom - top);
      const contentHeight = Math.max(rect.height, el.offsetHeight, 1);
      const viewportSpan = Math.max(160, viewportHeight - 76 - 16);
      if (contentHeight <= viewportSpan + 80) {
        hide();
        return;
      }
      trackHeight.value = height;
      trackTop.value = top;
      railStyle.value = {
        top: `${Math.round(top)}px`,
        height: `${Math.round(height)}px`,
        right: "0px"
      };
      const scrolled = Math.max(0, 76 - rect.top);
      const progressValue = clamp(scrolled / Math.max(1, contentHeight - viewportSpan), 0, 1);
      current.value = letterAtRatio(progressValue);
      visible.value = true;
    }
    let raf = 0;
    function queueSync() {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        sync();
      });
    }
    function showHintAt(clientY) {
      const hit = letterAtPointer(clientY);
      hint.value = hit.letter;
      placeHint(hit.ratio);
      return hit.letter;
    }
    function jump(letter) {
      if (!letter || letter === lastJumped) return;
      lastJumped = letter;
      emit("jump", letter);
    }
    function onPointerDown(event) {
      if (!hasStops.value) return;
      dragging = true;
      active.value = true;
      lastJumped = "";
      event.preventDefault();
      event.currentTarget?.setPointerCapture?.(event.pointerId);
      jump(showHintAt(event.clientY));
    }
    function onPointerMove(event) {
      if (!dragging) return;
      jump(showHintAt(event.clientY));
    }
    function edgeGap(clientX) {
      const width = document.documentElement?.clientWidth || window.innerWidth || 0;
      return width - clientX;
    }
    function applyPointer(clientX, clientY) {
      if (!visible.value || dragging || !hasStops.value) return;
      const gap = edgeGap(clientX);
      const withinVertical = clientY >= trackTop.value - VERTICAL_SLACK && clientY <= trackTop.value + trackHeight.value + VERTICAL_SLACK;
      if (!active.value) {
        if (gap < -2 || gap > HOT_ZONE || !withinVertical) return;
        hovering = true;
        active.value = true;
        lastJumped = "";
        showHintAt(clientY);
        return;
      }
      if (gap < -2 || gap > KEEP_ZONE || !withinVertical) {
        hovering = false;
        active.value = false;
        hint.value = "";
        return;
      }
      showHintAt(clientY);
    }
    let moveRaf = 0;
    function onGlobalPointerMove(event) {
      if (event.pointerType !== "mouse") return;
      if (!visible.value || dragging) return;
      const x = event.clientX;
      const y = event.clientY;
      if (moveRaf) return;
      moveRaf = requestAnimationFrame(() => {
        moveRaf = 0;
        applyPointer(x, y);
      });
    }
    function stopDrag() {
      if (!dragging) return;
      dragging = false;
      active.value = hovering;
      if (!hovering) hint.value = "";
      lastJumped = "";
    }
    onMounted$1(() => {
      document.addEventListener("scroll", queueSync, true);
      document.addEventListener("pointermove", onGlobalPointerMove, true);
      window.addEventListener("resize", queueSync);
      window.addEventListener("pointerup", stopDrag);
      window.addEventListener("pointercancel", stopDrag);
      sync();
    });
    onBeforeUnmount(() => {
      document.removeEventListener("scroll", queueSync, true);
      document.removeEventListener("pointermove", onGlobalPointerMove, true);
      window.removeEventListener("resize", queueSync);
      window.removeEventListener("pointerup", stopDrag);
      window.removeEventListener("pointercancel", stopDrag);
      if (raf) cancelAnimationFrame(raf);
      if (moveRaf) cancelAnimationFrame(moveRaf);
    });
    watch$1(() => [props.anchor, props.stops.length], () => queueSync());
    return (_ctx, _cache) => {
      return _openBlock$1(), _createBlock$1(_Teleport$1, { to: "body" }, [
        visible.value ? (_openBlock$1(), _createElementBlock$1("div", {
          key: 0,
          class: _normalizeClass$1(["sdas-scroll", { "sdas-scroll--active": active.value }]),
          style: _normalizeStyle$1(railStyle.value),
          role: "scrollbar",
          "aria-label": "按首字母快速定位",
          "aria-valuenow": "0"
        }, [
          _createElementVNode$1("div", {
            class: "sdas-scroll-letters",
            onPointerdown: onPointerDown,
            onPointermove: onPointerMove
          }, [
            (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(__props.stops, (stop) => {
              return _openBlock$1(), _createElementBlock$1("span", {
                key: stop.letter,
                class: _normalizeClass$1(["sdas-scroll-letter", {
                  "is-current": stop.letter === current.value,
                  "is-active": stop.letter === hint.value
                }])
              }, _toDisplayString$1(stop.letter), 3);
            }), 128))
          ], 32),
          _createVNode$1(_Transition, { name: "sdas-alpha-fade" }, {
            default: _withCtx$1(() => [
              hint.value ? (_openBlock$1(), _createElementBlock$1("span", {
                key: 0,
                class: "sdas-scroll-hint",
                style: _normalizeStyle$1(hintStyle.value)
              }, _toDisplayString$1(hint.value), 5)) : _createCommentVNode$1("", true)
            ]),
            _: 1
          })
        ], 6)) : _createCommentVNode$1("", true)
      ]);
    };
  }
});

const AlphaIndex = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-332d033d"]]);

const GROUP_CHARS = {
  A: "俺傲凹哀哎唉啊嗄嗌嗳嗷坳埃埯奥媪嫒安岙岸庵廒懊拗按挨捱揞敖昂暗暧案桉氨澳熬爱犴獒瑷癌皑盎矮砹碍翱聱肮胺艾蔼螯袄谙遨鏊鏖铵锕锿阿隘霭鞍骜鳌鹌黯",
  B: "不丙亳伯伴佰便保俾倍傍傧八兵冫冰别剥办勃勹包匕北匾半卑博卜卞卟变叭吡吧呗哔哺啵嘣坂坌坝埠堡壁备奔妣婊婢嬖孛孢宝宾岜崩巴币布帛帮并庇庳弁弊弼彪彬彼必忭怖悖悲惫愎憋扁扒扮扳把报抱拌拔拜拨捌捕捭掰搏搬摆摈摒播擘敝斌斑晡暴本杓杯板柄柏标梆棒榜槟檗步殡比毕毖毙汴波泵浜渤滗滨濒濞灞灬炳焙煲煸爆爸版狈狴玢玻班璧瓣瓿甏甭畀畚疤病痹瘢瘪瘭癍白百砭碑碚碥碧磅礴禀秉秕稗窆笆笔笨笾筚箅箔篦簸簿粑绊绑绷缏编缤罢耙背胞脖膀膊膑膘臂舨般舭舶芭苄苞苯茇荜荸菝菠萆葆蒡蓓蓖蔽薄薜蚌蝙补表被裨裱褊褒褓褙襞谤豳豹贝败贬贲趵跋跛跸踣蹦蹩辈辨辩辫边迸逋逼遍避邦邴邶部鄙醭鐾钚钡钣钯钵钸钹铂铋锛镑镔镖镳闭阪陂陛雹霸靶鞭鞴颁飑飙飚饱饼饽驳骠髀髌髟鬓魃鲅鲍鳊鳔鳖鸨鹁鹎鼻龅",
  C: "丑丛丞串乘亍产仇从仓传伥伧伺侈侧侪促俦倡偿储催傺充冁册冲凑出刍创初刺匆厂厕厝厨参叉叱吃吵吹呈呲哧唇唱啐啜啻喘嗔嗤嘈嘬嘲噌嚓囱场坻坼垂城埕塍墀处姹娼婵媸嫦存孱宠宸察寸尘尝尺层屮岑岔崇崔嵯巛川巢差帱常幢床廛弛彩彳彻徂徜忏忖忡忱怅怆怊怵恻悴惆惝惨惩惭愁慈憧憷成戳才扯承抄抻抽拆持挫捶掣措掺插揣搀搋搐搓搽摧撑撤撮撺操擦敕敞斥昌春昶晁晟晨曹曾朝杈材村杵枞枨查柴柽棰椎椽椿楚楮榇榱槌槎槽樗橙橱檫次此殂残毳氅氚汆汊池沉沧测涔淙淬淳滁漕潮潺澄澈澶灿炊炒炽焯爨猖猜猝猹琛琮璀璁璨瓷畅畜畴疮疵痤痴瘁瘛瘥瘳皴眵睬瞅瞠矗矬砗础碜碴磁磋礤祠禅秤称程稠穿窗窜笞策筹篡篪簇粗粲粹糍糙纯绌绰绸缠羼翅翠耖耻聪肠脆脞腠膪臣臭舂舛舡舱船艚艟艹苁苌苍茈茌茨茬茶茺草莼菖菜萃葱蒇蔟蔡藏虫虿蚕蚩蛏蜍蝉蝽螬螭蟾蠢衩衬裁裎褚褫觇触词诚诧谄谌谗谶豺财赐赤趁超踌踔踟踩踹蹉蹙蹭蹰蹴蹿躇躔车辍辏辞辰辶迟逞遄郴酢酬酲醇醋采钏钗钞铖铲铳锄锉错锤锸镡镩镲闯阊阐陈除陲雌雏雠颤餐饬馇馋驰骋骖骢骣鬯魑鲳鸱鹑鹚鹾黜黪齿龀龊",
  D: "丁东丢丹仃代佃但低侗倒傣儋兑党兜典冬冻凋凳凼刀刁刂到剁动单叠叨叮叼吊吨呆呔咄咚哆哒哚啖啶喋嗒嗲嘀嘟噔囤地坫垌垛垤垫埭堆堕堞堤堵墩多大夺奠妒妲娣嫡宕定对导岛岱岽峒嶝巅帝带底店度弟弹当待得德忉怛怠怼恫悼惦惮惰憝懂戥戴打抖抵担挡捣掂掇掉掸揲搭敌敦斗断旦朵杜柁柢栋档棣椟椴歹殆殚段殿毒氐氘氡氮沌沓洞涤淀淡渎渡滇滴澹灯炖点焘煅爹牍牒犊狄独玎玳玷瓞甙电甸疔疸痘瘅瘩癜癫登的盗盯盹盾眈睇督睹瞪短砀砘砥硐碇碉碓碘碟碡碲磴礅祷稻窦端笃笛笪第等答箪篼簖簟簦籴纛绐缍缎缔羝翟耋耵耷耽聃肚胆胨胴腚舵芏荡荻菪萏董蒂蔸蚪蛋蝶蠹袋裆裰褡觌订诋诞读调谍谛谠豆貂贷赌赕趸跌跺踮踱蹀蹈蹬蹲躲达迨迪迭递逗逮遁道邓邸郸都酊钉钓钝钿铎铛铞铤铥铫锝锭锻镀镝镦镫队阽陡雕靛靼鞑顶顿颠骀骶髑鲷鲽鸫黛黩鼎",
  E: "二佴俄儿厄呃噩垩娥婀尔屙峨恩恶愕扼摁洱珥而耳腭苊莪萼蒽蛾讹诶谔贰轭迩遏鄂铒锇锷阏颚额饵饿鲕鳄鸸鹅鹗",
  F: "丰乏付份仿伏伐佛俘俯俸偾傅冯凡凤凫分副匐匚匪反发吠否吩呋咐唪啡坊坟垡复夫奉奋妃妇妨孚孵富封峰帆幅幞幡府废弗忿怫悱愤房扉扶抚拂拊放敷斐斧方服枋枫桴梵棼榧樊氛氟汾沣沸法泛浮涪淝滏瀵烦烽焚燔父犯狒珐甫畈番疯痱矾砜砝砩祓福稃符筏篚粉粪繁纷纺绂绋绯缚缝缶罘罚翡翻肤肥肪肺腐腑腓腹舫艴芙芬芳芾苻范茯莩菔菲葑蕃藩蘩蚨蜂蜉蜚蝠蝮袱覆讣讽访诽负贩费赋赙赴趺跗蹯辅辐返逢邡郛酆酚釜钒钫锋镄阀阜阝防附霏非风飞饭馥驸鲂鲋鲱鲼鳆麸黻黼鼢",
  G: "丐丨个乖亘仡估伽佝供倌傀光公共关冈冠刚刮刽刿剐割功勾匦卦古各告呙呱呷咕咣咯哏哥哽哿嗝嘎嘏噶固国圪圭坩垓垢埂埚塥够妫姑媾孤宄官宫寡尕尜尬尴岗岣崞崮工巩帼干广庋庚廾弓彀归怪恭惯感戆戈戤拐拱挂掴掼搁搞搿擀改攻故敢旮旰晷更杆杠杲构果枸柑柜栝根格桂桄桧梏梗棍棺椁概槁槔橄歌毂汞汩沟沽泔涫淦港溉滚澉灌炔牯牿犷狗猓珙瑰瓜甘疙疳痼癸皈皋盖盥睾瞽矸硅硌磙秆稿竿笱筻箍管篙篝簋糕纥纲绀给绠绲缑缟缸罐罟罡羔羹耕耿聒肛肝股肱胍胱胳膈膏臌舸艮苟苷茛莞菇菰葛藁虢虼蚣蛄蛊蜾蝈衮袼裹褂观规觏觚觥诂诖诟诡该诰谷贡购贯贵赅赓赣赶跟跪躬轨轱辊辜过逛遘郜郭酐酤钆钙钢钩钴铬锅锆锢镉镐闺阁陔隔雇革鞲顾馆馘骨骼高鬲鬼鲑鲠鲧鲴鳏鳜鸪鸹鸽鹄鹘鹳鼓龚龟",
  H: "乎互亥亨伙会何侯候冱凰函划劐劾化卉华厚号合后含吼呵呼和咴哄哈哕哗哼唤唬唿喉喊喙喝嗥嗨嗬嘿嚆嚎嚯回囫圜坏堠壑壕壶夥夯奂好婚孩宏宦害寒寰岵幌幻弘弧彗很徊後徨徽忽怀怙恍恒恚恢恨悍悔患惑惚惠惶慌慧憨憾或户戽扈护挥捍换撖撼擐攉斛旱昊昏晃晖晗晦曷杭核桁桓桦槐槲横欢毁毫氦汇汉汗沆沪河泓洄洪洹活浍浑浒浣浩海涣涵涸淮混湖湟溷滑滹漶潢濠瀚灏火灰烀烘烩焊焓焕煌煳狐狠猢猴猾獾环珩珲琥瑚璜瓠画痕痪瘊癀皇皓盍盒砉磺祜祸禾秽笏篁篌簧糇糊红绗绘缋缓缳罕翮翰耗耠肓胡胲航花茴荒荟荤荭荷获菏菡萑葫蒿蕙蕻薅薨藿蘅虍虎虹虺蚝蚵蚶蛔蛤蝗蝴蟥蟪蠖衡褐觳訇讧讳诃诙话诨诲谎豁豢豪貉货贺贿赫踝轰轷辉还逅逭遑邗邯郇郝酣醐醢钬铧铪锪锾镬闳阂阍阖阚隍隳霍韩顸颃颌颔颢馄骅骇骸骺鬟魂鲎鲩鳇鸿鹕鹤鹱麾黄黉黑鼾",
  J: "丌举久九乩井亟交京仅今介件价伎佳佶佼侥俊俭俱倔借倦倨假偈健僦僬僭僵儆兢具兼冀冂军决净减几击刭剂剑剞剧剪剿劂加劫劲匠卩即卷卺厥厩及句叫叽吉君咀咎咭哜唧啾喈嗟嘉噍噘噤噱嚼囝圾均坚基堇境墼夹奖奸妓妗姐姜姣姬娇娟婕婧嫁嫉孑孓季家寂寄将尖就尽局居届屐屦岌岬峤峻崛嵇嵴巨己巾廑建弪彐径徼忌急恝悸惊惧憬戋戒戛戟戢截戬扃技抉拒拘拣拮挢挤捃捐捡据捷掎掘接掬揪揭搅搛撅攫救教敫敬斤旌既旧晋景晶暨机杰极枧架枷柩柬桀桊桔桕桨桷检棘椐椒楗楫榉榘槿橘橛歼殛毽江汲沮泾洁洎洚津浃浆浇济浚浸涓涧渐湔湫溅激灸炅炬炯烬焦煎爝爵牮犄犋犍犟狙狡狷獍獗玑玖珈珏琚瑾甲界畸畿疆疖疚疥疽疾痂痉瘕瘠皆皎皲监眷睑睛睫矍矜矩矫矶硷碣碱礁礓祭禁积秸稷稼稽究窖窘窭竞竟竣竭笄笈笕笳笺筋简箕箭籍粳精糨紧纠级纪经结绛绝绞绢继绩缄缉缙缣缰缴羁羯翦耩聚肌肩肼胛胫胶脊脚腈腱臼舅舰艰艽节芥芨芰苣苴茄茎茧茭茳荆荐荚荠荩莒菁菅菊菌菹葭蒋蒹蒺蓟蕉蕨蕺藉虮蚧蛟蛱蠲街衿袈袷裥裾襟见觉觊觐角觖解謇警计讥讦记讲讵诀诘诫谏谨谫谲豇贱贾赆赍赳趄趼跏距跤践跻跽踞踺踽蹇蹶轿较辑近进迥迦迳迹遽郊郏郡鄄酒酱酵醮醵金鉴钅钜钧钾铗铰锏锔锦锩键锯镌镓镜镢间阄阱阶际降隽集雎霁靓靖静靳鞠鞫鞯韭颈颉颊飓饥饯饺馑驹驾骄骏骥骱髻鬏鲒鲚鲛鲣鲫鲸鸠鸡鹃鹣鹪鹫麂麇齑龃",
  K: "亏亢伉佧侃侉侩倥克况凯刊刳刻剀勘匡匮卡口叩可吭咔咖咳哐哙哭啃喀喟喹喾嗑困圹坎坑块坤坷垦垮垲堀堪壳夔夸夼奎孔客宽寇尻岢岿崆库康廓开快忾恐恪恳恺悃悝愦愧慨慷戡扛扣扩抗抠括拷挎捆控揆揩旷昆暌枯柯栲框棵楷槛款氪渴溃溘炕烤犒狂狯珂琨疴盔看眍眶睽瞌瞰矿砍磕科稞空窟窠窥筐筘筷箜篑糠纩绔缂考聩肯胩胯脍芤苛苦莰葵蒈蒉蒯蔻蛞蝌蝰裉裤诓诳课贶跨跬轲逵邝郐酷醌钪钶铐铠铿锎锞锟锴闶阃阔隗靠颏颗馈馗骒骷髁髋髡魁鲲龈龛",
  L: "两临丽乐乱了亮仂仑令伦伶佬例侣俐俚俩俪倮偻傈僚儡六兰冷冽凉凌凛列刘利剌力劣励劳勒卢卤卵历厉厘另叻吏吕吝呖呤咙咧哩唠唳啉啦啷喇喱喽嘞嘹噜囵囹坜垃垄垅垆垒埒塄墚奁姥娄娈娌婪嫘嫠孪寥寮尥屡履岚岭峦崂崃嵝嶙帘庐廉廊廖廪录律徕怜恋愣懒懔戮戾抡拉拎拢拦挛捋捞捩掠掳揽搂摞撂撩撸擂敛斓料旅旒旯晾朗李来林枥柃柳栊栌栎栏栗栳栾梁梨棂棱椋椤楝楞楼榄榈榔榴橹檑檩殓氇氯沥沦泐泠泪泷泸泺洌洛流浏浪涝涞涟淋渌溜溧滤滥滦漉漏漓漤漯潋潞潦澜澧濂濑灵炉炼烂烈烙熘燎牢犁狸狼猁猎猡獠率玲珑珞琅理琉琏琳璃璐瓴留略疗疠疬痢痨瘌瘘瘤瘰癃癞睐瞵砬砺砻砾硫碌磊磷礼禄离稂稆窿立笠笼箩篓篥篮篱簏籁类粒粝粮粱粼累纶练络绫绺绿缆缕缡缧缭罗罱罹羚羸翎老耒耢耧聆聊聋联肋胧胪脔脶脸腊膂膦臁舻良芦苈苓茏荔荦莅莉莨莱莲菱萝落蒌蒗蓝蓠蓼蔹蔺蕾藜虏虑蛉蛎蜊蜡蝼螂螺蠃蠊蠡裂裢裣裸褛褴览詈论诔谅谰赁赂赉赖趔跞路踉躏躐轮轳轹辂辆辘辚辣辽连逦逯逻遛遴邋邻郎郦酃酪酹醪醴里量銮鎏钌铃铑铝铹铼链锂锊锍锒锣镂镏镙镣镥镧镭镰闾阆阑陆陇陋陵隆隶雒雳零雷霖露颅领馏驴骆骊骝骡髅鬣魉鲁鲈鲡鲢鲤鲮鳓鳞鳢鸬鸾鹂鹨鹩鹭鹿麓麟黎黧龄龙",
  M: "么乜买亩仫们侔免冒冕冖冥劢勉勐募卖卯名吗命咩咪哞唛喵嘛嘧坶埋墁墓墨妈妙妹姆娩媒媚嫫嬷孟宀宓密寐寞岷峁嵋帽幂幔幕庙弥弭忙悯愍慕慢懋懑懵扪抹抿拇描摩摸摹敉敏旄明昧昴暝暮曼朦木末杩杪枚某梅梦棉楣模檬殁母每毛毪民氓汨沐沔没沫泌泖泯浼淼渑渺湄湎溟满漠漫漭灭焖煤熳牟牡牦牧犸猕猛猫猸玛玫珉瑁甍瘼皿盟目盲眄眇眉眠眯眸睦瞀瞄瞑瞒瞢矛码硭磨礞祢秒秘秣穆篾米糜糸縻绵缅缈缗缦缪美耄耱脉脒腼膜艋艨芈芒苗苜苠茂茅茆茉茗茫荬莓莫莽萌蒙蓦蔑蔓藐蘑蘼虻蚂蛑蛮蜜蜢蝥螟螨蟆蟊蟒蠓蠛袂袤觅谋谜谟谧谩谬貊貌貘贸迈迷邈邙酩酶醚鍪钔钼铆铭锚锰镁镅镆镘门闵闷闽陌霉霾靡面鞔颟馍馒马骂髦魅魔鳗鳘鸣鹋鹛麋麦麻麽默黾",
  N: "乃伲佞你侬倪傩内农凝努匿南呐呢呶咛哝哪啮喃喏嗫嗯囊囔囡坭垴埝奈女奴奶妞妮娘娜嫩嬲孥孬孽宁尼尿年廿弄弩念忸怒怩恁恧恼您懦扭拈拟拧拿挠挪捏捺捻搦撵攮旎昵暖曩柠柰楠氖泞泥浓涅淖溺牛狃狞猊猱瑙甯男疒疟睨硇碾糯纳纽耐耨聂聍肭胬能脑脓脲腩腻臬艿茑萘蔫蘖虐蛲蝻衄衲袅讷诺赧蹑辇辗逆那酿钕钠钮铌铙锘镊镍镎闹陧难霓颞馁馕驽鲇鲵鲶鸟黏鼐",
  O: "偶呕哦喔噢怄欧殴沤瓯耦藕讴鸥",
  P: "丕丿乒乓仆仳佩俜俳偏僻凭判刨剖剽劈匍匏匹叛叵呸咆品哌啤啪喷嘌嘭噗噼圃圮坡坪坯埔埤培堋姘娉婆媲嫔嫖屁屏帔帕平庀庖庞彭彷徘怕怦扑批抛抨披拍拚拼捧掊排撇擗攀攴攵旁旆普曝朋朴杷枇枰棚榀殍毗氆氕沛泊泡泮泼派浦淠湃湓溥滂漂潘澎濮瀑炮烹爬爿片牌牝犏狍珀琵琶璞瓢瓶甓畔疋疱疲痞癖皤皮盆盘盼睥瞟瞥砒砰破硼碰磐票笸筢篇篷粕纰缥罴翩耪聘胖胚胼脬脯脾膨芘苤苹莆菩萍葡葩蒎蒲蓬蚍蜱螃螵蟛蟠袍袢裒裴襻譬评谝谱貔贫赔趴跑蹁蹒蹼辔辟迫逄邳郫鄱配醅钋钷铍铺锫镤镨陪陴霈霹颇频颦飘骈骗魄鲆鹏鼙",
  Q: "七且丘丬乔乞乾亓亲仟企佥侨侵俅俏俟倩倾全其凄凵切券前劁劝劬勤区千却卿去取吣启呛嗪嘁噙器囚圈圊圻堑墙奇契妻妾娶嫱寝屈屺岂岍岐岖峭崎嵌巧巯庆弃强怯恰悄悛悫悭情惬愀愆慊憔憩戕戗戚扦抢拳挈掐掮揿搴撬擎擒敲旗晴曲朐期权杞枪柒栖桤桥棋椠楸榷槭樯樵橇檎檠欠欺歉歧氍气氢氰求汔汽沁沏泅泉泣洽浅淇清渠溱漆潜炝牵犬犭犰球琦琪琴琼璩畎畦痊瘸癯瞧瞿砌硗确碛磬磲祁祈祛祺禽秋秦穷穹窃窍筇筌签箐箝箧糗綦綮绮绻缱缲缺罄羌羟群翘耆肷脐腔芊芎芑芡芩芪芹苘茕茜荃荞萁萋葜葺蔷蕖蕲蘧虔虬蚯蛆蛐蛩蛴蜞蜣蜷蜻蝤螓蠼衢衾裘裙褰襁觑謦讫诎诠诮请谦谯谴赇起趋趣跄跫跷蹊躯轻辁迁迄逑逡遒遣邛邱郄酋醛銎钎钤钦钱钳铅铨锓锖锲锵锹镪阒阕阙阡雀青鞒鞘顷颀颧驱骐骑骞髂鬈鲭鳅鳍鸲鹊麒麴黔黢黥鼽齐龋",
  R: "乳人亻仁仍仞任偌儒入冉冗刃嚅嚷壤壬如妊娆孺容嵘弱忍惹戎扔扰揉攘日朊枘染柔桡榕汝洳润溶溽濡热然熔燃狨瑞瓤睿禳稔穰箬糅纫绒绕缛肉肜芮苒若茸茹荏荛荣葚蓉蓐蕊蕤薷蚋蚺蝾融蠕衽褥襦认让蹂轫软辱铷锐闰阮鞣韧颥饪饶髯",
  S: "三上世丝丧书事什仕仨伞伤伸似佘使侍俗倏傻僧僳兕兽凇删刷刹剡剩劭势勺匙十卅升厍厦厮厶叁双叔受叟史司吮呻咝哂哨唆唢售唰唼商啥啬善嗉嗍嗓嗖嗜嗣嗦嗽嗾嘶噬噻四圣垧埏埘埽塑塞塾墅墒士声夙失奢妁始姒姗姝娑娠婶嫂嬗孀孙孰守宋实审室宿寺寿射少尚尸屎属山岁崧嵊嵩巳市帅师庶式弑彡忪怂思恃恕悚愫慎慑戍所扇手扌扫抒拭拴拾挲捎损授搔搜搠搡摄摅摔撒撕擅擞收散数斯施时是晌晒暑曙朔术杀杉束松枢柿树栓桑桫梢梭梳森椹榫槊歃歙死殇殊殳毵毹氏水氵汕汜沈沙沭泗洒涉涑涩涮淑淞深渖渗湿溯溲滠漱潲潸澌澍濉炻烁烧煞煽熟熵燧爽牲狩狮狲狻猞珊琐瑟甚生甥甩申畲疏疝痧瘙瘦盛省眚眭睃睡睢瞍瞬矢矧石砂砷硕碎磉示礻社祀神祟私秫稍税稣穑穗竖竦笋笙笥筛筮筲算簌粟糁素索纟纱纾绅绍绥绱绳绶缌缩缫缮署羧耍耜耸肃肆肾胂胜脎腧腮膳膻臊舌舍舐舒舜舢艄艏艘色芍芟苏苕苫荪荽莎莘莳菘菽萨蒜蒴蓍蓑蔌蔬薮薯虱虽蚀蛇蛳蛸蜀蜃螋螫蟀蟮衫衰裟裳视觞觫誓讪讼设识诉试诗诜说诵谁谂谇谡谥豉豕贳赊赎赏赛赡赦跚身轼输述送适逝速遂邃邵鄯酥酸酾释钐铄铈铩铯锁锶锼闩闪陕隋随隧隼霎霜韶顺颂颡飒飕食飧饣饰饲馊馓首驶驷骚骟髓鲥鲨鲺鳃鳋鳝鸶麝黍鼠",
  T: "乇亠亭他仝体佗佟佻倘倜停偷傥僮兔凸剃剔厅台叹同吐吞听唐唾啕啼嗵嚏团图土坍坛坦坨堂堍塌塔塘填天太头套她妥婷它屉屠屯帑帖庭庹廷彖彤徒忐忑忒忝态恬恸悌惕慝托投抟抬拓拖挑挞挺捅掏探推掭提搪摊昙暾替条柝桃桐桶梃梯棠椭榻樘橐檀殄毯氽汀汤汰沱沲泰洮涂涕涛淌淘添湍溏溻滔滕滩潭潼炭炱烃烫煺特獭瑭甜田町畋疃疼痛痰瘫眺瞳砣砼碳祧秃突窕童笤筒箨粜糖统绦绨缇羰耥肽胎脱腆腾腿膛臀舔艇苔茼荑荼莛菟萄萜葶薹藤蜓蜕蜩螗螳袒裼褪覃誊讨谈谭豚贪贴趟趿跆跎跳踏踢蹄蹋躺迢退逃透途逖通遢邰郯酞酡酮酴醍醣钍钛钭钽铁铊铜铴铽锑锬镗闼阗陀陶霆韬颓题餮饕饧饨驮驼骰髫鲐鲦鳎鸵鹈鼍鼗龆",
  W: "万丸为乌五亡仵伍伟伪位佤侮倭偎兀刎剜务勿午卧卫危吴吻吾呒呜味哇唔唯喂嗡囗围圩圬坞外妄妩委威娃娓娲婉婺完宛寤尉尾屋崴嵬巍巫帏帷幄庑弯往微忘忤怃悟惋惘惟慰戊我挖挝挽捂握文斡无旺晚晤望未杌枉桅梧武歪毋污汪汶沃沩洧洼浯涠涡渥温渭湾潍炜烷焐煨物牾猥猬王玟玩玮琬璺瓦瓮畏畹痦痿瘟皖硪碗稳窝紊纨纬纹维绾网罔翁肟胃脘腕腽舞艉芄芜芴苇莴菀萎葳蓊蔚蕹薇蚊蛙蜈蜗蜿袜诬误诿谓豌軎辋迕违逶邬鋈钨问闱闻阌阢隈雯雾韦韪顽骛魍魏鲔鹉鹜鼯龌",
  X: "下习乡些享亵仙休侠信修偕像僖儇兄先兮兴写冼凶刑削勋勖勰匈匣协卸厢县叙吁向吓吸咸咻响哓哮唏啸喜喧嗅嘘嘻嚣囟型埙墟夏夕奚姓娴婿媳嫌嬉孝学宣宪宵寻小屑屣岘岫峋峡崤巡巷巽希席幸序庠庥廨弦形徇徐徙循心忄忻性恂恤息悉悬悻惜想惺懈戌戏挟掀揎携撷擤效斜新旋旬旭昔昕星显晓晰暄暇暹曛曦朽杏析枭枵柙校栩械楔楦榍榭樨橡檄欣欷歆歇殉氙汐汛汹泄泫泶泻洗洫洵浔浠消涎淅淆渫渲湘溆溪溴漩潇瀣炫烯煊煦熄熊熏熙熹燮燹牺犀狎狭猃猩献獬獯玄现玺瑕璇痃痫癣皙盱相眩瞎矽硎硒硖硝碹祆祥禊禧秀稀穴穸窨笑筅筱箫箱籼粞糈系絮纤线绁细绚绡绣绪续缃缬罅羞羡羲翔翕肖胁胥胸腥腺膝舄舷舾芗芯苋荀荇荥荨莶菥萧萱葙葸蓄蓰蓿蕈薛薤薪薰藓虚虾蚬蜥蝎螅蟋蟓蟹血衅行衔袖袭襄西觋训讯许询详诩谐谑谖谢象貅贤跣跹踅躞轩辖辛迅选逊逍遐邂邢邪郗酗酰醑醒醯醺鑫铉铣销锈锌锡锨镟镶闲阋陉限险陷隙隰雄雪需霄霞霰靴鞋项须顼飨饩饷馅馐香馨驯骁骧髹魈鲜鲞鲟鳕鸺鹇黠鼷",
  Y: "一与业严丫义乙也予于云亚亦亿以仪仰伊优伛伢佑余佚佣佯佾侑依俑俞俣俨倚偃允元兖养冤冶刈刖劓勇匀医卣印压厌原厣又友右叶吆吖吟吲呀呓员呦咏咦咬咽咿哑哟唁唷喁喑喻嘤噎噫因园囿圄圆圉圯垠垣垭垸域埸堙堰塬墉壅壹夜夤夭央夷奄奕妍妖妤妪姚姨姻娅娱婴媛媵嫣嬴孕宇宜宥宴寅寓尢尤尧尹屹屿岈岩岳峄峪崖崦崾嵛嶷已幺幼幽应庸庾廴延异弈弋引彝彦影役徉御徭忆忧怏怡怨怿恙恹恽恿悒悠悦愈愉意愚愠愿慵懿扬抑押拥挹掖掩掾揄揖揠援揶摇撄攸於旖昀易映昱晏晔晕曜曰曳月有杨杳柚样桠椅椰楹榆樱樾橼檐欤欲欹殃殒殪殷毅毓氤氧氩氲永沂沅油沿泱泳洇洋浴涌涯液淤淫淹渊渔渝游湮源溢滟滢演漪漾潆瀛瀹炀炎烊烟烨焉焰焱煜熠熨燕燠爰爷爻牖牙犹狁狱狳狺猗猷猿玉珧琊琰瑗瑛瑜瑶璎用甬由疑疡疣疫痈痍痒痖瘀瘐瘗瘾瘿癔盂盈益盐眙眢眼睚矣砑研砚硬禹禺秧移窈窑窬窳竽筠筵箢粤繇纡约纭绎缘缢缨罂罨羊羽羿翊翌翳翼耀耘耶聿肀肄育肴胤胭胰腋腌腰腴膺臃臆臾舀舁舆舣艳艺芋芫芸芽苑苡英茔茚茵荧荫药莜莠莸莹莺菸萤营萦萸蓣蓥蕴薏虞蚁蚓蚜蚰蚴蛘蛹蜒蜮蜴蝇蝓蝣螈衍衙衣衤袁裔裕要觎言誉讠议讶译诒诣语诱谀谊谒谕谚谣谳豫贻赝赢越跃踊轧轶轺辕迂迎运迓远迤逸逾遇遗遥邀邑邕邮邺郁郓郢郧郾鄞鄢酉酏酝酽釉野钇钥钰钺铀铕铘铟铱银镒镛镱闫阅阈阉阎阳阴院陨隅隐雁雅雍雨雩霪靥鞅韫音韵页预颍颐颖颜餍饔饫饮饴馀驭驿验鬻魇鱼鱿鳐鳙鸢鸦鸭鸯鸳鹆鹞鹦鹬鹰黝黟鼋鼬鼹龉龠",
  Z: "丈专中丶主之乍争仄仉仔仗仲众伫住佐作侄侏侦俎倬债值做偬兆兹再冢准凿则制助匝卒卓占卮只召吒吱周咂咋咒咤咨咫咱哉哲哳唑唣啁啄啧啭喳嘱嘴噪在圳址坐坠埴增壮夂奏奘妆妯姊姿嫜子字孜孳宅宗宙宰寨尊展峙峥崭崽嵫嶂州左帐帙帚帜帧帻幛庄座张彘彰征徵志忠忮怍怎怔总恣惴憎战扎执找抓折拄拙招择拯拶拽指挚挣振捉掌掷揍揸搌摘摭摺撙撞撰擢攒攥支政整斋斟斩斫旃族旨早昃昝昨昭昼智暂最朕札朱杂杖杼枕枝枣枳柘柞柱栀栅栈栉株栽桌桎桢桩梓棕棹植楂楱榛榨槠樟樽橥止正殖毡汁治沼沾注泽洙洲浈浊浙浞涨涿淄渍渚渣湛滋滓滞漳潴澡濯灶灼灾炙炷炸烛照煮燥爪状狰猪獐珍珠琢璋瓒甄甑甾畛疰疹痄症痔痣瘃瘴瘵皂皱盅盏直真眦眨着睁瞩瞻知砖砟砦砧砸磔祉祖祗祚祝祯禚种租秩秭稚稹窀窄窒站章竹竺笊笫笮筑筝箦箴箸篆簪籀籽粘粢粥粽糌糟紫絷纂纣纵纸组织终绉综绽缀缁缒缜缯缵罩罪置罾翥者耔职肇肘肢肫肿胀胄胗胙胝脂脏腙膣臧自至致臻舟舯舳舴芝芷苎茁茱荮著葬蒸蓁蔗蕞藻蘸蚤蚱蛀蛛蛭蛰蜇蜘螽蟑衷装褶觜觯訾詹证诅诈诊诌诏诛诤诸诹诼谆谘谪谮谵豸贞责账质贮贼贽赀赃资赈赘赚赜赞赠赭走赵趑趱足趾跖踪踬踯踵躁躅躜转轴轵轸载轾辄辎辙这迮追逐造遭遮遵邹邾郅郑鄣鄹酌酎酯醉重錾针钊钟钲钻铡铢铮铸锃锗锥锱锺镇镞镯长闸阵阻阼陟陬障隹雉震颛馔驵驺驻骓骘骤髭鬃鲰鲻鳟鸩鸷鹧麈黹齄龇"
};
const CHAR_LETTER = (() => {
  const map = /* @__PURE__ */ new Map();
  for (const letter of Object.keys(GROUP_CHARS)) {
    for (const char of GROUP_CHARS[letter]) map.set(char, letter);
  }
  return map;
})();
const SURNAME_LETTER = {
  曾: "Z",
  单: "S",
  解: "X",
  仇: "Q",
  查: "Z",
  区: "O",
  朴: "P",
  盖: "G",
  乐: "Y",
  覃: "Q",
  翟: "Z",
  尉: "Y",
  折: "S",
  种: "C",
  过: "G",
  秘: "B",
  员: "Y",
  燕: "Y",
  长: "C",
  重: "C"
};
const LETTER_ORDER = [
  "A",
  "B",
  "C",
  "D",
  "E",
  "F",
  "G",
  "H",
  "I",
  "J",
  "K",
  "L",
  "M",
  "N",
  "O",
  "P",
  "Q",
  "R",
  "S",
  "T",
  "U",
  "V",
  "W",
  "X",
  "Y",
  "Z",
  "#"
];
function letterRank(letter) {
  const index = LETTER_ORDER.indexOf(letter);
  return index < 0 ? LETTER_ORDER.length : index;
}
function initialOf(rawName) {
  const name = String(rawName || "").trim();
  if (!name) return "#";
  const first = Array.from(name)[0];
  if (!first) return "#";
  if (/[A-Za-z]/.test(first)) return first.toUpperCase();
  if (first in SURNAME_LETTER) return SURNAME_LETTER[first];
  return CHAR_LETTER.get(first) || "#";
}
const collator = (() => {
  try {
    return new Intl.Collator("zh-Hans-CN", { sensitivity: "base" });
  } catch {
    return null;
  }
})();
function compareByName(a, b) {
  const rankDiff = letterRank(initialOf(a)) - letterRank(initialOf(b));
  if (rankDiff !== 0) return rankDiff;
  if (collator) {
    const result = collator.compare(String(a || ""), String(b || ""));
    if (result !== 0) return result;
  }
  return String(a || "").localeCompare(String(b || ""));
}

const {defineComponent:_defineComponent} = await importShared('vue');

const {openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,Fragment:_Fragment,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,withKeys:_withKeys,renderList:_renderList,normalizeClass:_normalizeClass,normalizeStyle:_normalizeStyle,Teleport:_Teleport} = await importShared('vue');

const _hoisted_1 = { class: "sdas-head" };
const _hoisted_2 = { class: "sdas-head-main" };
const _hoisted_3 = { class: "sdas-sub" };
const _hoisted_4 = { class: "sdas-new-dot" };
const _hoisted_5 = { class: "px-3 sdas-search-row" };
const _hoisted_6 = { class: "flex justify-start align-center" };
const _hoisted_7 = { class: "mr-5 sdas-row-label" };
const _hoisted_8 = {
  key: 0,
  class: "sdas-search-hint text-body-2 text-medium-emphasis ml-3"
};
const _hoisted_9 = { key: 0 };
const _hoisted_10 = { key: 1 };
const _hoisted_11 = { key: 2 };
const _hoisted_12 = { class: "px-3 sdas-tabs" };
const _hoisted_13 = ["aria-selected", "title", "onClick"];
const _hoisted_14 = {
  key: 0,
  class: "sdas-chip-count"
};
const _hoisted_15 = {
  key: 1,
  class: "sdas-chip-count"
};
const _hoisted_16 = { class: "px-3 sdas-slot" };
const _hoisted_17 = {
  key: 0,
  class: "flex justify-start align-center sdas-actor-bar"
};
const _hoisted_18 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_19 = {
  key: 0,
  class: "text-caption text-medium-emphasis ml-3"
};
const _hoisted_20 = {
  key: 0,
  class: "flex justify-start align-center"
};
const _hoisted_21 = { class: "mr-5 sdas-row-label" };
const _hoisted_22 = { class: "sdas-chip-count" };
const _hoisted_23 = {
  key: 1,
  class: "flex justify-start align-center"
};
const _hoisted_24 = { class: "mr-5 sdas-row-label" };
const _hoisted_25 = { class: "sdas-chip-count" };
const _hoisted_26 = {
  key: 2,
  class: "flex justify-start align-center"
};
const _hoisted_27 = { class: "mr-5 sdas-row-label" };
const _hoisted_28 = { class: "sdas-chip-count" };
const _hoisted_29 = {
  key: 3,
  class: "flex justify-start align-center"
};
const _hoisted_30 = { class: "mr-5 sdas-row-label" };
const _hoisted_31 = { class: "sdas-chip-count" };
const _hoisted_32 = { class: "flex justify-start align-center" };
const _hoisted_33 = { class: "mr-5 sdas-row-label" };
const _hoisted_34 = { class: "sdas-library-cards" };
const _hoisted_35 = ["disabled"];
const _hoisted_36 = {
  key: 0,
  class: "sdas-library-count"
};
const _hoisted_37 = {
  key: 0,
  class: "sdas-library-count"
};
const _hoisted_38 = { class: "flex justify-start align-center" };
const _hoisted_39 = { class: "mr-5 sdas-row-label" };
const _hoisted_40 = { class: "sdas-chip-count" };
const _hoisted_41 = { class: "flex justify-start align-center sdas-actor-bar" };
const _hoisted_42 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_43 = {
  key: 0,
  class: "text-body-2 text-medium-emphasis ml-3"
};
const _hoisted_44 = { class: "flex justify-start align-center" };
const _hoisted_45 = { class: "mr-5 sdas-row-label" };
const _hoisted_46 = { class: "flex justify-start align-center sdas-actor-bar" };
const _hoisted_47 = { class: "text-body-2 text-medium-emphasis" };
const _hoisted_48 = {
  key: 0,
  class: "text-caption text-medium-emphasis ml-3"
};
const _hoisted_49 = {
  key: 1,
  class: "text-body-2 text-medium-emphasis ml-3"
};
const _hoisted_50 = {
  key: 0,
  class: "mb-6"
};
const _hoisted_51 = { class: "text-body-2 text-medium-emphasis mb-2" };
const _hoisted_52 = {
  key: 1,
  class: "sdas-search-miss text-body-2 text-medium-emphasis mb-3"
};
const _hoisted_53 = { key: 2 };
const _hoisted_54 = { class: "text-body-2 text-medium-emphasis mb-2" };
const _hoisted_55 = {
  key: 3,
  class: "sdas-search-miss text-body-2 text-medium-emphasis"
};
const _hoisted_56 = ["data-cell-key"];
const _hoisted_57 = { key: 1 };
const _hoisted_58 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_59 = { key: 2 };
const _hoisted_60 = {
  key: 1,
  class: "d-flex flex-column align-center ga-2 py-4"
};
const _hoisted_61 = { key: 1 };
const _hoisted_62 = {
  key: 0,
  class: "sdas-logfloat-line sdas-logfloat-dim"
};
const {computed,nextTick,onMounted,onUnmounted,ref,watch} = await importShared('vue');
const PAGE_SIZE = 30;
const MIN_ITEM_WIDTH = 144;
const GRID_GAP = 16;
const COLLAPSED_LIMIT = 12;
const LOOKUP_DEBOUNCE = 420;
const FIRST_SCREEN_MAX_PAGES = 3;
const LOG_POS_KEY = "sdas.logfloat.pos.v1";
const NATIVE_SCROLL_MUTED = "sdas-native-scroll-muted";
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "ActorWall",
  props: {
    api: {},
    config: {},
    pluginId: {},
    full: { type: Boolean }
  },
  setup(__props) {
    const props = __props;
    const tabs = [
      { title: "已订阅", value: "subs", hint: "已订阅作品的卡片墙（含搜索 / 下载状态）" },
      { title: "作品", value: "works", hint: "短剧百科的作品海报墙（作品分类筛选在这一页）" },
      { title: "已关注演员", value: "actors", hint: "看已关注演员的头像卡片墙" },
      { title: "发现", value: "people", hint: "翻短剧百科的演员目录与站点榜单（热播 / 热搜 / 收藏…），点卡片即关注或订阅" }
    ];
    const activeTab = ref("subs");
    const tabsContainerRef = ref(null);
    const showTabsScrollIndicator = ref(false);
    const showLeftButton = ref(false);
    const showRightButton = ref(false);
    function isTouchDevice() {
      if (typeof window === "undefined") return false;
      try {
        return window.matchMedia("(hover: none) and (pointer: coarse)").matches || navigator.maxTouchPoints > 0;
      } catch {
        return false;
      }
    }
    function scrollTabs(direction) {
      const el = tabsContainerRef.value;
      if (!el) return;
      const scrollAmount = 200;
      const scrollPosition = direction === "left" ? el.scrollLeft - scrollAmount : el.scrollLeft + scrollAmount;
      el.scrollTo({ left: scrollPosition, behavior: "smooth" });
      setTimeout(updateTabsIndicator, 300);
    }
    function updateTabsIndicator() {
      const el = tabsContainerRef.value;
      if (!el) return;
      const shouldHideScrollControls = isTouchDevice();
      const tolerance = 1;
      const hasOverflow = el.scrollWidth > el.clientWidth + tolerance;
      const isScrolledToEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - tolerance;
      const isScrolledToStart = el.scrollLeft <= tolerance;
      showTabsScrollIndicator.value = hasOverflow && !isScrolledToEnd && !shouldHideScrollControls;
      showLeftButton.value = hasOverflow && !isScrolledToStart && !shouldHideScrollControls;
      showRightButton.value = hasOverflow && !isScrolledToEnd && !shouldHideScrollControls;
    }
    let tabsResizeTimer = null;
    function handleTabsResize() {
      if (tabsResizeTimer) clearTimeout(tabsResizeTimer);
      tabsResizeTimer = setTimeout(updateTabsIndicator, 150);
    }
    const works = ref([]);
    const total = ref(0);
    const allTotal = ref(0);
    const newWorks = ref(0);
    const libraryKnown = ref(0);
    const inLibraryCount = ref(0);
    const inLibraryKnown = computed(() => libraryKnown.value > 0);
    const probeAvailable = ref(false);
    const page = ref(1);
    const done = ref(false);
    const error = ref(false);
    const loading = ref(false);
    const loadingMore = ref(false);
    const seenKeys = /* @__PURE__ */ new Set();
    const seenSignatures = /* @__PURE__ */ new Set();
    let epoch = 0;
    const actorFilters = ref([]);
    const facets = ref({ genres: [], years: [], studios: [], platforms: [] });
    const followedActors = ref([]);
    const followedLoading = ref(false);
    const followedError = ref("");
    const PEOPLE_TABS = [
      { title: "演员", value: "yanyuan" }
    ];
    const peopleKind = ref("yanyuan");
    const peopleKindLabel = computed(
      () => PEOPLE_TABS.find((item) => item.value === peopleKind.value)?.title || "演员"
    );
    const peopleRows = ref([]);
    const peoplePage = ref(0);
    const peopleHasMore = ref(false);
    const peopleLoading = ref(false);
    const peopleError = ref("");
    const peopleMessage = ref("");
    const discoverView = ref("people");
    const rankItems = ref([]);
    const rankLoading = ref(false);
    const rankMedias = ref([]);
    const rankPage = ref(0);
    const rankHasMore = ref(false);
    const rankMessage = ref("");
    const rankKey = computed(() => discoverView.value === "people" ? "" : discoverView.value);
    const rankName = computed(
      () => rankItems.value.find((item) => item.key === rankKey.value)?.name || "榜单"
    );
    function rankMediaToWork(row) {
      const source = row.media_id.includes(":") ? row.media_id.split(":")[0].toLowerCase() : "djbaike";
      return {
        key: `rank:${row.media_id}`,
        title: row.title,
        year: (row.date || "").slice(0, 4),
        type: row.badge || "短剧",
        media_source: source,
        media_id: row.media_id,
        poster: row.poster,
        vote: 0,
        episode_count: row.episodes || 0,
        url: row.url,
        genres: [],
        heat: 0,
        play_count: 0,
        studio: row.actors_text || "",
        platform: "",
        kind: row.badge || "",
        release_date: row.date || "",
        actor: row.actors_text || "",
        actor_key: "",
        first_seen: "",
        is_new: false,
        // 卡片「入库」图标（与作品页同一套判定）
        in_library: row.in_library ?? null
      };
    }
    const rankWorkItems = computed(() => rankMedias.value.map(rankMediaToWork));
    async function loadRank(key, reset = true) {
      if (!key || rankLoading.value) return;
      const page2 = reset ? 1 : rankPage.value + 1;
      if (!reset && !rankHasMore.value) return;
      rankLoading.value = true;
      if (reset) rankMessage.value = "";
      try {
        const payload = await fetchRankWorks(props, key, page2);
        const medias = Array.isArray(payload.medias) ? payload.medias : [];
        if (rankKey.value !== key) return;
        if (reset) {
          rankMedias.value = medias;
        } else {
          const seen = new Set(rankMedias.value.map((item) => item.media_id));
          rankMedias.value = rankMedias.value.concat(
            medias.filter((item) => !seen.has(item.media_id))
          );
        }
        if (payload.message) rankMessage.value = payload.message;
        rankPage.value = payload.page || page2;
        rankHasMore.value = Boolean(payload.has_more);
      } catch (err) {
        rankMessage.value = `榜单加载失败：${err instanceof Error ? err.message : err}`;
      } finally {
        rankLoading.value = false;
        void nextTick(observeRankSentinel);
      }
    }
    function setDiscoverView(value) {
      const key = String(value || "");
      if (!key || key === discoverView.value) return;
      if (key === "people" || rankItems.value.some((item) => item.key === key)) {
        discoverView.value = key;
      }
    }
    watch(discoverView, (view) => {
      if (activeTab.value !== "people") return;
      if (view === "people") {
        void loadPeople(true);
        void nextTick(observePeopleSentinel);
      } else {
        void loadRank(view);
        void nextTick(observeRankSentinel);
      }
    });
    async function loadRankCatalog() {
      try {
        const payload = await fetchRanks(props);
        rankItems.value = (payload.ranks || []).filter((item) => item.has_detail !== false);
      } catch {
      }
    }
    const logLines = ref([]);
    const logsBodyRef = ref(null);
    let logsTimer = null;
    const logDragging = ref(false);
    const logPos = ref(null);
    const logBarRef = ref(null);
    const logBarH = ref(26);
    const logBarW = ref(96);
    const logViewportH = ref(typeof window === "undefined" ? 800 : window.innerHeight);
    const logViewportW = ref(typeof window === "undefined" ? 1280 : window.innerWidth);
    const logPinned = ref(true);
    const logExpandDown = computed(() => {
      const pos = logPos.value;
      if (!pos) return false;
      return pos.top + logBarH.value / 2 < logViewportH.value / 2;
    });
    const logExpandRight = computed(() => {
      const pos = logPos.value;
      if (!pos) return false;
      return pos.left + logBarW.value / 2 < logViewportW.value / 2;
    });
    const logStyle = computed(() => {
      const pos = logPos.value;
      if (!pos) return { right: "12px", bottom: "12px", top: "auto", left: "auto" };
      const horizontal = logExpandRight.value ? { left: `${pos.left}px`, right: "auto" } : { right: `${Math.max(0, logViewportW.value - pos.left - logBarW.value)}px`, left: "auto" };
      const vertical = logExpandDown.value ? { top: `${pos.top}px`, bottom: "auto" } : { bottom: `${Math.max(0, logViewportH.value - pos.top - logBarH.value)}px`, top: "auto" };
      return { ...horizontal, ...vertical };
    });
    function measureLogBar() {
      const bar = logBarRef.value;
      const host = bar?.closest(".sdas-logfloat") ?? null;
      if (!bar || !host) return null;
      host.classList.add("sdas-measuring");
      const rect = bar.getBoundingClientRect();
      host.classList.remove("sdas-measuring");
      if (rect.height > 0) logBarH.value = rect.height;
      if (rect.width > 0) logBarW.value = rect.width;
      return rect;
    }
    function updateLogMetrics() {
      logViewportH.value = window.innerHeight;
      logViewportW.value = window.innerWidth;
      measureLogBar();
      clampLogPos();
    }
    function clampLogPos() {
      const pos = logPos.value;
      if (!pos) return;
      logPos.value = {
        left: logClamp(pos.left, 0, Math.max(0, logViewportW.value - logBarW.value)),
        top: logClamp(pos.top, 0, Math.max(0, logViewportH.value - logBarH.value))
      };
    }
    function loadLogPos() {
      try {
        const raw = window.localStorage.getItem(LOG_POS_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (typeof parsed?.top === "number" && typeof parsed?.left === "number") {
          if (Number.isFinite(parsed.top) && Number.isFinite(parsed.left)) {
            logPos.value = { top: parsed.top, left: parsed.left };
            clampLogPos();
          }
        }
      } catch {
      }
    }
    function saveLogPos() {
      const pos = logPos.value;
      if (!pos) return;
      try {
        window.localStorage.setItem(LOG_POS_KEY, JSON.stringify(pos));
      } catch {
      }
    }
    function onLogScroll() {
      const el = logsBodyRef.value;
      if (!el) return;
      logPinned.value = el.scrollHeight - el.scrollTop - el.clientHeight < 8;
    }
    function scrollLogToEnd() {
      const el = logsBodyRef.value;
      if (!el || el.clientHeight === 0) return;
      el.scrollTop = el.scrollHeight;
      el.scrollLeft = 0;
      logPinned.value = true;
    }
    function onLogExpand() {
      if (logDragging.value) return;
      void nextTick(scrollLogToEnd);
    }
    function logClamp(value, min, max) {
      return Math.min(Math.max(value, min), Math.max(min, max));
    }
    let logDragStart = null;
    function onLogPointerDown(event) {
      const bar = event.currentTarget;
      if (!bar || logDragStart) return;
      updateLogMetrics();
      const rect = measureLogBar() ?? bar.getBoundingClientRect();
      const cur = { top: Math.round(rect.top), left: Math.round(rect.left) };
      logPos.value = cur;
      logDragStart = { px: event.clientX, py: event.clientY, top: cur.top, left: cur.left };
      logDragging.value = true;
      window.addEventListener("pointermove", onLogPointerMove, true);
      window.addEventListener("pointerup", onLogPointerUp, true);
      window.addEventListener("pointercancel", onLogPointerUp, true);
      event.preventDefault();
    }
    function onLogPointerMove(event) {
      const start = logDragStart;
      if (!start) return;
      logPos.value = {
        left: logClamp(start.left + (event.clientX - start.px), 0, Math.max(0, logViewportW.value - logBarW.value)),
        top: logClamp(start.top + (event.clientY - start.py), 0, Math.max(0, logViewportH.value - logBarH.value))
      };
    }
    function onLogPointerUp() {
      if (!logDragStart) return;
      logDragStart = null;
      logDragging.value = false;
      window.removeEventListener("pointermove", onLogPointerMove, true);
      window.removeEventListener("pointerup", onLogPointerUp, true);
      window.removeEventListener("pointercancel", onLogPointerUp, true);
      saveLogPos();
    }
    async function loadLogs() {
      try {
        const payload = await fetchLogs(props, 60);
        const items = Array.isArray(payload.items) ? payload.items : [];
        if (items.length === logLines.value.length && items.every((line, idx) => line === logLines.value[idx])) {
          return;
        }
        logLines.value = items;
        void nextTick(() => {
          if (logPinned.value) scrollLogToEnd();
        });
      } catch {
      }
    }
    function genderKey(value) {
      const text = String(value || "").trim().toLowerCase();
      if (!text) return "other";
      if (text === "female" || text === "f" || text.includes("女")) return "female";
      if (text === "male" || text === "m" || text.includes("男")) return "male";
      return "other";
    }
    const actorGroups = computed(() => {
      const female = [];
      const male = [];
      const other = [];
      for (const item of followedActors.value) {
        const key = genderKey(item.gender);
        if (key === "female") female.push(item);
        else if (key === "male") male.push(item);
        else other.push(item);
      }
      return [
        { key: "female", title: "女演员", items: female },
        { key: "male", title: "男演员", items: male },
        { key: "other", title: "未标注", items: other }
      ].filter((group) => group.items.length > 0);
    });
    const actorGender = ref("");
    const shownActors = computed(() => {
      const rows = actorGender.value ? actorGroups.value.find((group) => group.key === actorGender.value)?.items ?? [] : actorGroups.value.flatMap((group) => group.items);
      return [...rows].sort((a, b) => compareByName(a.name, b.name));
    });
    const actorLetterStops = computed(() => {
      const total2 = shownActors.value.length || 1;
      const stops = [];
      shownActors.value.forEach((item, index) => {
        const letter = initialOf(item.name);
        const last = stops[stops.length - 1];
        if (last && last.letter === letter) {
          last.count += 1;
          return;
        }
        stops.push({ letter, index, count: 1, ratio: index / total2 });
      });
      return stops;
    });
    const actorGridAnchor = ref(null);
    const cellElements = /* @__PURE__ */ new Map();
    function jumpToActorLetter(letter) {
      const stop = actorLetterStops.value.find((row) => row.letter === letter);
      if (!stop) return;
      const target = shownActors.value[stop.index];
      if (!target) return;
      const cell = cellElements.get(actorKey(target));
      if (cell?.isConnected) cell.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    const mountedCells = ref(/* @__PURE__ */ new Set());
    let cellObserver = null;
    const observedCells = /* @__PURE__ */ new WeakSet();
    function ensureCellObserver() {
      if (cellObserver) return cellObserver;
      if (typeof IntersectionObserver === "undefined") return null;
      cellObserver = new IntersectionObserver(
        (entries) => {
          const next = new Set(mountedCells.value);
          let changed = false;
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            cellObserver?.unobserve(entry.target);
            const key = entry.target.dataset.cellKey || "";
            if (key && !next.has(key)) {
              next.add(key);
              changed = true;
            }
          }
          if (changed) mountedCells.value = next;
        },
        { rootMargin: "600px 0px" }
      );
      return cellObserver;
    }
    function observeCell(el, key) {
      if (!key) return;
      if (!(el instanceof HTMLElement)) {
        const stale = cellElements.get(key);
        if (stale && !stale.isConnected) cellElements.delete(key);
        return;
      }
      cellElements.set(key, el);
      const observer2 = ensureCellObserver();
      if (!observer2) {
        if (!mountedCells.value.has(key)) {
          const next = new Set(mountedCells.value);
          next.add(key);
          mountedCells.value = next;
        }
        return;
      }
      if (observedCells.has(el)) return;
      observedCells.add(el);
      observer2.observe(el);
    }
    function isCellMounted(key) {
      return mountedCells.value.has(key);
    }
    const followedCount = computed(
      () => followedActors.value.length || actorFilters.value.length
    );
    const actor = ref("");
    const genre = ref("");
    const year = ref("");
    const studio = ref("");
    const platform = ref("");
    const sort = ref("date");
    const onlyNotSubscribed = ref(false);
    const onlyNotInLibrary = ref(false);
    const expandedRows = ref({});
    const actorQuery = ref("");
    const actorResults = ref([]);
    const searchingActors = ref(false);
    const workResults = ref([]);
    const searchingWorks = ref(false);
    const addingActorId = ref("");
    const removingActorId = ref("");
    const detailActor = ref(null);
    const detailWork = ref(null);
    const detailAdapted = ref(null);
    const viewLayer = ref("");
    let actorOpenedFrom = "";
    let workOpenedFrom = "";
    let detailScrollY = 0;
    let actorScrollY = 0;
    const subscribed = ref(/* @__PURE__ */ new Set());
    const loadedKeys = ref(/* @__PURE__ */ new Set());
    const tip = ref("");
    const tipType = ref("info");
    let tipTimer = null;
    const tipOpen = computed({
      get: () => Boolean(tip.value),
      set: (on) => {
        if (!on) tip.value = "";
      }
    });
    function toast(text, type = "info") {
      tip.value = text;
      tipType.value = type;
      if (tipTimer) clearTimeout(tipTimer);
      tipTimer = setTimeout(() => tip.value = "", 3200);
    }
    const filteredOut = computed(
      () => Boolean(
        actor.value || genre.value || year.value || studio.value || platform.value || onlyNotInLibrary.value || onlyNotSubscribed.value
      )
    );
    function resetFilters() {
      actor.value = "";
      genre.value = "";
      year.value = "";
      studio.value = "";
      platform.value = "";
      onlyNotInLibrary.value = false;
      onlyNotSubscribed.value = false;
    }
    let lastScrollY = 0;
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
        platform: platform.value,
        sort: sort.value,
        only_not_in_library: onlyNotInLibrary.value,
        only_not_subscribed: onlyNotSubscribed.value,
        page_size: PAGE_SIZE
      };
    }
    const actorCount = computed(() => actorFilters.value.length);
    const filteredCount = computed(() => total.value);
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
    function isActorAdded(item) {
      if (item.subscribed) return true;
      if (item.actor_id) {
        return actorFilters.value.some((row) => row.key === item.actor_id);
      }
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
        if (result.need_pick) {
          toast(result.message || "百科里没有完全同名的演员，请从候选里挑一位", "error");
          return;
        }
        item.subscribed = true;
        toast(result.message || `已添加「${item.name}」`);
        await reload();
        await loadFollowed();
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
        const result = await removeActor(props, { actor_id: item.actor_id, name: item.name });
        item.subscribed = false;
        toast(result.message || `已移除「${item.name}」`);
        await reload();
        await loadFollowed();
      } catch (err) {
        toast(`移除失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        removingActorId.value = "";
      }
    }
    function openActorDetail(item) {
      exitViews(false);
      actorQuery.value = "";
      actorScrollY = currentScrollY();
      detailActor.value = item;
      viewLayer.value = "actor";
      scrollToPosition(0);
    }
    function applyGenreFilter(value) {
      const target = String(value || "").trim();
      if (!target) return;
      const same = genre.value === target;
      const cleared = Boolean(year.value || studio.value || platform.value);
      const hadKeyword = Boolean(actorQuery.value);
      actorQuery.value = "";
      year.value = "";
      studio.value = "";
      platform.value = "";
      genre.value = target;
      if (same && !cleared && !hadKeyword) {
        exitViews();
        void reload();
      }
    }
    function openAdaptedFromWork(novel) {
      detailAdapted.value = novel;
      viewLayer.value = "adapted";
      scrollToPosition(0);
    }
    function backFromAdapted() {
      if (detailWork.value) {
        viewLayer.value = "work";
        void nextTick(() => scrollToPosition(detailScrollY));
        return;
      }
      exitViews();
    }
    function backFromActor() {
      if (actorOpenedFrom === "work" && detailWork.value) {
        actorOpenedFrom = "";
        viewLayer.value = "work";
        void nextTick(() => scrollToPosition(detailScrollY));
        return;
      }
      exitViews();
    }
    function backFromWork() {
      if (workOpenedFrom === "actor" && detailActor.value) {
        workOpenedFrom = "";
        viewLayer.value = "actor";
        void nextTick(() => scrollToPosition(0));
        return;
      }
      if (workOpenedFrom === "adapted" && detailAdapted.value) {
        workOpenedFrom = "";
        viewLayer.value = "adapted";
        void nextTick(() => scrollToPosition(0));
        return;
      }
      exitViews();
    }
    function exitViews(restoreScroll = true) {
      const hadWork = Boolean(detailWork.value);
      const hadActor = Boolean(detailActor.value);
      const hadAdapted = Boolean(detailAdapted.value);
      detailWork.value = null;
      detailActor.value = null;
      detailAdapted.value = null;
      actorOpenedFrom = "";
      workOpenedFrom = "";
      viewLayer.value = "";
      if (!hadWork && !hadActor && !hadAdapted || !restoreScroll) return;
      const top = hadActor ? actorScrollY : detailScrollY;
      void nextTick(() => scrollToPosition(top));
    }
    function toActorWall() {
      exitViews();
    }
    function refreshFollowed() {
      toActorWall();
      loadFollowed(true);
    }
    const followedActorIds = computed(
      () => new Set(
        followedActors.value.map((item) => String(item.actor_id || "")).filter(Boolean)
      )
    );
    const busyActorIds = computed(
      () => new Set([addingActorId.value, removingActorId.value].filter(Boolean))
    );
    function toggleActorFromWork(row) {
      if (isActorAdded(row)) void unsubscribeActor(row);
      else void subscribeActor(row);
    }
    function isActorBusy(item) {
      if (!item) return false;
      return addingActorId.value === item.actor_id || removingActorId.value === item.actor_id;
    }
    async function toggleActor(item) {
      if (!item) return;
      if (isActorAdded(item)) {
        await unsubscribeActor(item);
      } else {
        await subscribeActor(item);
      }
    }
    let lookupEpoch = 0;
    const searchSource = ref("");
    const searchMode = ref("");
    async function runLookup(mode = "cache") {
      const name = searchKeyword.value;
      const stamp = ++lookupEpoch;
      if (!name) {
        actorResults.value = [];
        workResults.value = [];
        searchingActors.value = false;
        searchingWorks.value = false;
        searchSource.value = "";
        searchMode.value = "";
        return;
      }
      if (mode === "cache") {
        searchMode.value = "cache";
        searchSource.value = "";
        const needle = name.toLowerCase();
        const hit = (text) => String(text || "").toLowerCase().includes(needle);
        workResults.value = works.value.filter(
          (item) => hit(item.title) || hit(item.actor) || hit(item.studio) || hit(item.platform) || (item.genres || []).some((genre2) => hit(genre2))
        ).slice(0, 30);
        const actorPool = [
          ...followedActors.value,
          ...peopleRows.value.map((row) => row)
        ];
        const seen = /* @__PURE__ */ new Set();
        actorResults.value = actorPool.filter((row) => {
          if (!hit(row.name)) return false;
          const key = String(row.actor_id || row.name);
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        }).slice(0, 30);
        searchingActors.value = false;
        searchingWorks.value = false;
        return;
      }
      searchMode.value = "site";
      searchingActors.value = true;
      searchingWorks.value = true;
      searchSource.value = "";
      try {
        const result = await lookupSite(props, name);
        if (stamp !== lookupEpoch) return;
        actorResults.value = result.actors;
        workResults.value = result.works;
        searchSource.value = result.source;
      } catch (err) {
        if (stamp !== lookupEpoch) return;
        actorResults.value = [];
        workResults.value = [];
        toast(`检索不可用：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        if (stamp === lookupEpoch) {
          searchingActors.value = false;
          searchingWorks.value = false;
        }
      }
    }
    const gridRef = ref(null);
    const gridWidth = ref(0);
    let gridObserver = null;
    function setGridNode(el) {
      const node = el && typeof el === "object" && "$el" in el ? el.$el : el;
      if (node) gridRef.value = node;
    }
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
    watch(gridRef, (node) => {
      if (node) watchGrid();
    }, { flush: "post" });
    function workKey(work) {
      return work.key;
    }
    function dedupeKey(work) {
      return JSON.stringify(["media", work.media_source, String(work.media_id ?? ""), work.type ?? null, null]);
    }
    let scrollHostEl = null;
    function findScrollHost(from) {
      if (typeof window === "undefined") return null;
      let node = from;
      while (node) {
        const style = window.getComputedStyle(node);
        if ((style.overflowY === "auto" || style.overflowY === "scroll") && node.scrollHeight > node.clientHeight + 2) {
          return node;
        }
        node = node.parentElement;
      }
      return null;
    }
    function resolveScrollHost() {
      scrollHostEl = findScrollHost(gridRef.value ?? sentinel.value ?? null);
      return scrollHostEl;
    }
    let mutedScrollEl = null;
    let mutedPrevPadRight = "";
    let mutedPadApplied = false;
    function unmuteScrollHost() {
      if (!mutedScrollEl) return;
      mutedScrollEl.classList.remove(NATIVE_SCROLL_MUTED);
      if (mutedPadApplied) {
        mutedScrollEl.style.paddingRight = mutedPrevPadRight;
        mutedPadApplied = false;
      }
      mutedPrevPadRight = "";
      mutedScrollEl = null;
    }
    function muteNativeScrollBar(on) {
      if (typeof document === "undefined") return;
      if (!on) {
        unmuteScrollHost();
        return;
      }
      const host = findScrollHost(actorGridAnchor.value) ?? scrollHostEl ?? resolveScrollHost() ?? null;
      if (!host) return;
      if (host === mutedScrollEl) return;
      unmuteScrollHost();
      const barWidth = Math.max(0, host.offsetWidth - host.clientWidth);
      mutedPrevPadRight = host.style.paddingRight;
      if (barWidth > 0) {
        const base = window.getComputedStyle(host).paddingRight || "0px";
        host.style.paddingRight = `calc(${base} + ${barWidth}px)`;
        mutedPadApplied = true;
      }
      host.classList.add(NATIVE_SCROLL_MUTED);
      mutedScrollEl = host;
    }
    function scrollHost() {
      return scrollHostEl ?? resolveScrollHost();
    }
    function viewportBottom() {
      const host = scrollHost();
      if (host) return host.getBoundingClientRect().bottom;
      return window.innerHeight || document.documentElement.clientHeight;
    }
    function applyMeta(payload) {
      total.value = payload.total;
      actorFilters.value = payload.actor_filters || [];
      facets.value = payload.facets;
      allTotal.value = payload.summary?.total ?? payload.total;
      newWorks.value = payload.summary?.new ?? 0;
      libraryKnown.value = Number(payload.summary?.library_known ?? 0);
      inLibraryCount.value = Number(payload.summary?.in_library ?? 0);
      probeAvailable.value = payload.summary?.probe_available === true || libraryKnown.value > 0;
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
    }
    async function loadMore(chain = false) {
      if (loadingMore.value || done.value) return;
      const stamp = epoch;
      loadingMore.value = true;
      error.value = false;
      try {
        const { terminal, rows } = await fetchPage();
        if (stamp !== epoch) return;
        if (terminal) {
          done.value = true;
          return;
        }
        append(rows);
        if (total.value > 0 && works.value.length >= total.value) done.value = true;
      } catch (err) {
        if (stamp !== epoch) return;
        error.value = true;
        toast(`加载作品失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        if (stamp === epoch) {
          loadingMore.value = false;
          await nextTick();
          resolveScrollHost();
          if (chain) requestMoreIfVisible();
        }
      }
    }
    function requestMoreIfVisible() {
      const node = sentinel.value;
      if (!node || done.value || loadingMore.value || loading.value) return;
      if (page.value > FIRST_SCREEN_MAX_PAGES + 1) return;
      if (node.getBoundingClientRect().top <= viewportBottom() + 600) void loadMore(true);
    }
    async function reload() {
      epoch += 1;
      loading.value = true;
      error.value = false;
      done.value = false;
      page.value = 1;
      seenKeys.clear();
      seenSignatures.clear();
      works.value = [];
      loadedKeys.value.clear();
      loadingMore.value = false;
      backTopHiding.value = false;
      await nextTick();
      try {
        await loadMore(true);
      } finally {
        loading.value = false;
      }
    }
    let librarySummaryBusy = false;
    async function refreshLibrarySummary() {
      if (librarySummaryBusy || !probeAvailable.value) return;
      librarySummaryBusy = true;
      try {
        const payload = await fetchWorks(props, {
          only_not_in_library: true,
          page: 1,
          page_size: 1
        });
        const summary = payload.summary;
        if (summary) {
          libraryKnown.value = Number(summary.library_known || 0);
          inLibraryCount.value = Number(summary.in_library || 0);
        }
      } catch {
      } finally {
        librarySummaryBusy = false;
      }
    }
    async function loadSubscribed() {
      await loadSubscriptions();
    }
    const subItems = ref([]);
    const subEngine = ref("");
    const subsLoading = ref(false);
    const isSelfEngine = computed(() => {
      const engine = String(subEngine.value || configData.value.subscribe_engine || "self");
      return engine !== "host";
    });
    const subEditable = computed(() => isSelfEngine.value);
    function subRowToWork(row) {
      const source = row.media_id.includes(":") ? row.media_id.split(":")[0].toLowerCase() : "djbaike";
      return {
        key: `sub:${row.media_id}`,
        title: row.title,
        year: row.year || "",
        type: "电视剧",
        media_source: source,
        media_id: row.media_id,
        poster: row.poster || "",
        vote: 0,
        episode_count: 0,
        url: "",
        genres: [],
        heat: 0,
        play_count: 0,
        studio: "",
        platform: "",
        kind: "",
        release_date: "",
        actor: row.actor || "",
        actor_key: "",
        first_seen: "",
        is_new: false,
        sub_state: row.sub_state,
        sub_detail: row.sub_detail,
        sub_time: row.sub_time,
        in_library: typeof row.in_library === "boolean" ? row.in_library : null
      };
    }
    const subWorkItems = computed(() => subItems.value.map(subRowToWork));
    function isSubDone(row) {
      if (row.in_library === true) return true;
      return ["downloaded", "history", "in_library"].includes(String(row.sub_state || ""));
    }
    const subLibFilter = ref("undown");
    const subLibCounts = computed(() => {
      let undown = 0;
      let hasIn = 0;
      let hasNot = 0;
      for (const row of subItems.value) {
        if (row.in_library === true) hasIn += 1;
        else if (row.in_library === false) hasNot += 1;
        if (!isSubDone(row)) undown += 1;
      }
      return { undown, hasIn, hasNot };
    });
    const shownSubWorkItems = computed(() => {
      if (subLibFilter.value === "undown") {
        return subWorkItems.value.filter((work) => !isSubDone(work));
      }
      if (subLibFilter.value === "in") {
        return subWorkItems.value.filter((work) => work.in_library === true);
      }
      if (subLibFilter.value === "not") {
        return subWorkItems.value.filter((work) => work.in_library === false);
      }
      return subWorkItems.value;
    });
    const detailSubscription = computed(() => {
      const mid = detailWork.value?.media_id;
      if (!mid) return null;
      return subItems.value.find((row) => row.media_id === mid) || null;
    });
    function onDetailSubUpdated() {
      void loadSubscriptions();
    }
    async function loadSubscriptions() {
      subsLoading.value = true;
      try {
        const res = await fetchSubscriptions(props);
        subItems.value = res.items;
        if (res.engine) subEngine.value = res.engine;
        subscribed.value = new Set(res.items.map((row) => String(row.media_id || "")).filter(Boolean));
      } catch {
      } finally {
        subsLoading.value = false;
      }
    }
    const randomCount = ref(1);
    const randomSubscribing = ref(false);
    async function randomSubscribe() {
      if (randomSubscribing.value) return;
      randomSubscribing.value = true;
      try {
        const res = await pluginSubscribeRandom(props, randomCount.value);
        const picked = res?.data?.items || [];
        if (res?.success && picked.length) {
          const names = picked.map((item) => `《${item.title}》`).join("、");
          toast(`已随机订阅 ${picked.length} 部：${names}，订阅搜索稍后自动找资源`);
          void loadSubscriptions();
          scheduleSubscribedReload();
        } else {
          toast(String(res?.message || "没有可随机订阅的作品"), "error");
        }
      } catch (err) {
        toast(`随机订阅失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        randomSubscribing.value = false;
      }
    }
    const searchAllRunning = ref(false);
    async function searchAllNow() {
      if (searchAllRunning.value) return;
      searchAllRunning.value = true;
      try {
        const res = await pluginSubscribeSearchAll(props);
        if (res?.success) {
          toast(String(res?.message || "已开始订阅搜索（全部订阅）"));
          for (const delay of [8e3, 2e4, 45e3]) {
            setTimeout(() => void loadSubscriptions(), delay);
          }
        } else {
          toast(String(res?.message || "订阅搜索没能启动"), "error");
        }
      } catch (err) {
        toast(`订阅搜索启动失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        searchAllRunning.value = false;
      }
    }
    async function backfillFollowedProfiles() {
      const need = followedActors.value.filter(
        (item) => item.actor_id && !item.followers && !item.likes
      ).length;
      if (!need) return;
      try {
        const rows = await fetchActorCards(props, true);
        if (rows.length) followedActors.value = rows;
      } catch {
      }
    }
    async function loadFollowed(enrich = false) {
      followedLoading.value = true;
      followedError.value = "";
      try {
        followedActors.value = await fetchActorCards(props, enrich);
      } catch (err) {
        followedError.value = `演员列表加载失败：${err instanceof Error ? err.message : err}`;
      } finally {
        followedLoading.value = false;
      }
    }
    async function loadPeople(reset = false) {
      if (peopleLoading.value) return;
      if (!reset && (!peopleHasMore.value || !peopleRows.value.length)) return;
      const page2 = reset ? 1 : peoplePage.value + 1;
      peopleLoading.value = true;
      peopleError.value = "";
      try {
        const payload = await fetchPeople(props, peopleKind.value, page2);
        peopleMessage.value = payload.message || "";
        const merged = reset ? payload.people : [...peopleRows.value, ...payload.people];
        const seen = /* @__PURE__ */ new Set();
        peopleRows.value = merged.filter((row) => {
          const key = row.actor_id || row.name;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
        peoplePage.value = payload.page || page2;
        peopleHasMore.value = Boolean(payload.has_more);
      } catch (err) {
        peopleError.value = `人物目录加载失败：${err instanceof Error ? err.message : err}`;
      } finally {
        peopleLoading.value = false;
        void nextTick(observePeopleSentinel);
      }
    }
    watch(peopleKind, () => {
      if (activeTab.value === "people") void loadPeople(true);
    });
    watch(activeTab, (tab) => {
      if (tab === "people") {
        if (discoverView.value === "people") {
          void loadPeople(true);
          void nextTick(observePeopleSentinel);
        } else {
          void loadRank(discoverView.value);
          void nextTick(observeRankSentinel);
        }
      }
      void nextTick(() => muteNativeScrollBar(tab === "actors" || tab === "subs"));
      backTopHiding.value = false;
    });
    const subscribeReloadTimers = [];
    function scheduleSubscribedReload() {
      const timer = setTimeout(() => {
        const index = subscribeReloadTimers.indexOf(timer);
        if (index >= 0) subscribeReloadTimers.splice(index, 1);
        void loadSubscribed();
      }, 3e3);
      subscribeReloadTimers.push(timer);
    }
    const sentinel = ref(null);
    let observer = null;
    const peopleSentinel = ref(null);
    let peopleObserver = null;
    const rankSentinel = ref(null);
    let rankObserver = null;
    function observePeopleSentinel() {
      if (!peopleObserver) return;
      resolveScrollHost();
      peopleObserver.disconnect();
      if (peopleSentinel.value) peopleObserver.observe(peopleSentinel.value);
    }
    function observeRankSentinel() {
      if (!rankObserver) return;
      resolveScrollHost();
      rankObserver.disconnect();
      if (rankSentinel.value) rankObserver.observe(rankSentinel.value);
    }
    function observeSentinel() {
      if (!observer) return;
      resolveScrollHost();
      observer.disconnect();
      if (sentinel.value) observer.observe(sentinel.value);
    }
    onMounted(async () => {
      if (typeof IntersectionObserver === "function") {
        observer = new IntersectionObserver(
          (entries) => {
            if (entries.some((entry) => entry.isIntersecting)) loadMore();
          },
          { rootMargin: "300px 0px" }
        );
        if (sentinel.value) observer.observe(sentinel.value);
        peopleObserver = new IntersectionObserver(
          (entries) => {
            if (!entries.some((entry) => entry.isIntersecting)) return;
            if (activeTab.value !== "people") return;
            if (peopleHasMore.value && !peopleLoading.value && peopleRows.value.length) {
              void loadPeople();
            }
          },
          { rootMargin: "300px 0px" }
        );
        if (peopleSentinel.value) peopleObserver.observe(peopleSentinel.value);
        rankObserver = new IntersectionObserver(
          (entries) => {
            if (!entries.some((entry) => entry.isIntersecting)) return;
            if (activeTab.value !== "people" || discoverView.value === "people") return;
            if (rankHasMore.value && !rankLoading.value && rankMedias.value.length) {
              void loadRank(discoverView.value, false);
            }
          },
          { rootMargin: "300px 0px" }
        );
        if (rankSentinel.value) rankObserver.observe(rankSentinel.value);
      }
      window.addEventListener("scroll", onScroll, { passive: true, capture: true });
      window.addEventListener("resize", handleTabsResize);
      window.addEventListener("resize", updateLogMetrics);
      tabsContainerRef.value?.addEventListener("scroll", updateTabsIndicator);
      void loadSubscribed();
      void loadRankCatalog();
      void loadLogs();
      logsTimer = setInterval(() => void loadLogs(), 5e3);
      await Promise.all([reload(), loadFollowed()]);
      void backfillFollowedProfiles();
      void refreshLibrarySummary();
      await nextTick();
      updateLogMetrics();
      loadLogPos();
      onScroll();
      watchGrid();
      updateTabsIndicator();
      muteNativeScrollBar(activeTab.value === "actors" || activeTab.value === "subs");
    });
    const scrolledFar = ref(false);
    const backTopHiding = ref(false);
    const showBackTop = computed(() => {
      if (viewLayer.value) return false;
      if (backTopHiding.value) return false;
      if (activeTab.value === "actors") return shownActors.value.length > 30;
      if (activeTab.value === "people") return peopleRows.value.length > 30;
      return scrolledFar.value;
    });
    function currentScrollTop(event) {
      const host = scrollHost();
      const target = event?.target || null;
      const fromTarget = target && target !== document ? Number(target.scrollTop || 0) : Number(document.scrollingElement?.scrollTop || 0);
      return Math.max(
        host ? Number(host.scrollTop || 0) : 0,
        Number(window.scrollY || 0),
        fromTarget || 0
      );
    }
    function onScroll(event) {
      lastScrollY = currentScrollTop(event);
      scrolledFar.value = lastScrollY > 300;
      if (backTopHiding.value && lastScrollY > 300) backTopHiding.value = false;
    }
    function scrollToTop() {
      const host = scrollHost();
      if (host) host.scrollTo({ top: 0, behavior: "smooth" });
      else window.scrollTo({ top: 0, behavior: "smooth" });
      lastScrollY = 0;
      scrolledFar.value = false;
      backTopHiding.value = true;
    }
    function scrollToPosition(position) {
      const host = scrollHost();
      if (host) host.scrollTo({ top: position });
      else window.scrollTo({ top: position });
    }
    function currentScrollY() {
      const host = scrollHost();
      return host ? host.scrollTop : window.scrollY || 0;
    }
    onUnmounted(() => {
      muteNativeScrollBar(false);
      if (logsTimer) {
        clearInterval(logsTimer);
        logsTimer = null;
      }
      window.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("resize", updateLogMetrics);
      onLogPointerUp();
      window.removeEventListener("resize", handleTabsResize);
      tabsContainerRef.value?.removeEventListener("scroll", updateTabsIndicator);
      if (tabsResizeTimer) {
        clearTimeout(tabsResizeTimer);
        tabsResizeTimer = null;
      }
      observer?.disconnect();
      observer = null;
      gridObserver?.disconnect();
      gridObserver = null;
      cellObserver?.disconnect();
      cellObserver = null;
      cellElements.clear();
      if (tipTimer) clearTimeout(tipTimer);
      if (lookupTimer) clearTimeout(lookupTimer);
      while (subscribeReloadTimers.length) {
        const pending = subscribeReloadTimers.pop();
        if (pending) clearTimeout(pending);
      }
    });
    watch([searchActive, activeTab, detailActor, detailWork, viewLayer], async () => {
      await nextTick();
      observeSentinel();
      watchGrid();
    });
    watch(
      () => shownActors.value.length,
      async (count) => {
        if (activeTab.value !== "actors" || !count) return;
        await nextTick();
        muteNativeScrollBar(true);
      }
    );
    watch(
      () => shownSubWorkItems.value.length,
      async (count) => {
        if (activeTab.value !== "subs" || !count) return;
        await nextTick();
        muteNativeScrollBar(true);
      }
    );
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
    watch([actor, genre, year, studio, platform, sort, onlyNotInLibrary, onlyNotSubscribed], () => {
      exitViews();
      reload();
    });
    watch(actorGender, () => {
      toActorWall();
    });
    watch(actorQuery, () => {
      if (searchKeyword.value) exitViews();
      if (lookupTimer) clearTimeout(lookupTimer);
      lookupTimer = setTimeout(() => void runLookup("cache"), LOOKUP_DEBOUNCE);
    });
    watch(activeTab, () => {
      exitViews();
    });
    const subscribing = ref(false);
    const subscribingId = ref("");
    const subscribingAllKey = ref("");
    const cancelTarget = ref(null);
    const cancelOpen = computed({
      get: () => cancelTarget.value !== null,
      set: (on) => {
        if (!on) cancelTarget.value = null;
      }
    });
    function askCancelSubscribe(work) {
      if (subscribing.value) return;
      cancelTarget.value = work;
    }
    async function confirmCancelSubscribe() {
      const work = cancelTarget.value;
      if (!work) return;
      subscribing.value = true;
      subscribingId.value = work.media_id;
      try {
        const res = await pluginUnsubscribe(props, work.media_id);
        if (res && res.success === false) {
          toast(String(res.message || "取消订阅失败"), "error");
          return;
        }
        const next = new Set(subscribed.value);
        next.delete(work.media_id);
        subscribed.value = next;
        toast(`已取消订阅：${work.title}`);
        void loadSubscriptions();
      } catch (err) {
        toast(`取消失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        subscribing.value = false;
        subscribingId.value = "";
        cancelTarget.value = null;
      }
    }
    const searchNowId = ref("");
    async function searchNow(work) {
      if (searchNowId.value) return;
      searchNowId.value = work.media_id;
      try {
        await ensureConfig();
        if (!subscribed.value.has(work.media_id)) {
          const sub = await pluginSubscribe(props, work);
          if (sub && sub.success === false) {
            toast(String(sub.message || "订阅失败"), "error");
            return;
          }
          const next = new Set(subscribed.value);
          next.add(work.media_id);
          subscribed.value = next;
        }
        const result = await pluginSubscribeSearchNow(props, work.media_id);
        toast(result?.message || `已开始搜索《${work.title}》，结果稍后回填`);
        scheduleSubscribedReload();
      } catch (err) {
        toast(`立即搜索失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        searchNowId.value = "";
      }
    }
    async function subscribe(work) {
      if (subscribed.value.has(work.media_id)) {
        askCancelSubscribe(work);
        return;
      }
      if (subscribing.value) return;
      subscribing.value = true;
      subscribingId.value = work.media_id;
      try {
        await ensureConfig();
        const res = await pluginSubscribe(props, work);
        if (res && res.success === false) {
          toast(String(res.message || "订阅失败"), "error");
          return;
        }
        const next = new Set(subscribed.value);
        next.add(work.media_id);
        subscribed.value = next;
        toast(res?.message || `已订阅：${work.title}`);
        void loadSubscriptions();
      } catch (err) {
        toast(`订阅失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        subscribing.value = false;
        subscribingId.value = "";
      }
    }
    function describeSubscribeAll(res) {
      const parts = [`提交 ${res.submitted} 部`];
      if (res.skipped_library) parts.push(`已在库 ${res.skipped_library} 部`);
      if (res.skipped_subscribed) parts.push(`已订阅 ${res.skipped_subscribed} 部`);
      if (res.failed) parts.push(`失败 ${res.failed} 部`);
      if (res.capped) parts.push("超出单次上限，可再点一次继续");
      return parts.join(" · ");
    }
    async function subscribeAllWorks(item) {
      if (!item || subscribingAllKey.value) return;
      const key = actorKey(item);
      subscribingAllKey.value = key;
      try {
        const res = await subscribeAllActor(props, {
          actorId: String(item.actor_id || ""),
          name: String(item.name || ""),
          excludeIds: Array.from(subscribed.value)
        });
        if (res.media_ids.length) {
          const next = new Set(subscribed.value);
          for (const mediaId of res.media_ids) next.add(mediaId);
          subscribed.value = next;
          scheduleSubscribedReload();
        }
        toast(`${item.name}：${describeSubscribeAll(res)}`, res.failed ? "error" : "info");
      } catch (err) {
        toast(`订阅全部失败：${err instanceof Error ? err.message : err}`, "error");
      } finally {
        subscribingAllKey.value = "";
      }
    }
    function openWorkDetail(work) {
      if (viewLayer.value === "adapted") {
        workOpenedFrom = "adapted";
        actorOpenedFrom = "";
      } else if (viewLayer.value === "actor") {
        workOpenedFrom = "actor";
        actorOpenedFrom = "";
      } else {
        workOpenedFrom = "";
        detailScrollY = currentScrollY();
      }
      detailWork.value = work;
      viewLayer.value = "work";
      scrollToPosition(0);
    }
    function openActorFromWork(item) {
      actorQuery.value = "";
      actorOpenedFrom = "work";
      detailActor.value = item;
      viewLayer.value = "actor";
      scrollToPosition(0);
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
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip_group = _resolveComponent("v-chip-group");
      const _component_v_progress_circular = _resolveComponent("v-progress-circular");
      const _component_v_snackbar = _resolveComponent("v-snackbar");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_card_actions = _resolveComponent("v-card-actions");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_dialog = _resolveComponent("v-dialog");
      return _openBlock(), _createElementBlock(_Fragment, null, [
        viewLayer.value === "actor" && detailActor.value ? (_openBlock(), _createBlock(ActorDetail, {
          key: 0,
          api: props.api,
          actor: detailActor.value,
          subscribed: isActorAdded(detailActor.value),
          "busy-follow": isActorBusy(detailActor.value),
          "subscribed-ids": subscribed.value,
          "busy-subscribe-all": subscribingAllKey.value === actorKey(detailActor.value),
          onBack: _cache[0] || (_cache[0] = ($event) => backFromActor()),
          onToggleActor: _cache[1] || (_cache[1] = ($event) => toggleActor(detailActor.value)),
          onSubscribeAll: _cache[2] || (_cache[2] = ($event) => subscribeAllWorks(detailActor.value)),
          onOpenWork: openWorkDetail,
          onSearch: searchWork,
          onSubscribe: subscribe
        }, null, 8, ["api", "actor", "subscribed", "busy-follow", "subscribed-ids", "busy-subscribe-all"])) : viewLayer.value === "work" && detailWork.value ? (_openBlock(), _createBlock(WorkDetail, {
          key: 1,
          api: props.api,
          work: detailWork.value,
          subscribed: subscribed.value.has(detailWork.value.media_id),
          subscription: detailSubscription.value,
          "sub-editable": subEditable.value,
          "followed-ids": followedActorIds.value,
          "busy-ids": busyActorIds.value,
          subscribing: subscribing.value,
          onBack: _cache[3] || (_cache[3] = ($event) => backFromWork()),
          onOpenActor: openActorFromWork,
          onSearch: searchWork,
          onSubscribe: subscribe,
          onToggleActor: toggleActorFromWork,
          onOpenAdapted: openAdaptedFromWork,
          onFilterGenre: applyGenreFilter,
          onSubUpdated: onDetailSubUpdated
        }, null, 8, ["api", "work", "subscribed", "subscription", "sub-editable", "followed-ids", "busy-ids", "subscribing"])) : viewLayer.value === "adapted" && detailAdapted.value ? (_openBlock(), _createBlock(AdaptedDetail, {
          key: 2,
          api: props.api,
          novel: detailAdapted.value,
          "media-id": detailWork.value?.media_id || "",
          "subscribed-ids": subscribed.value,
          onBack: _cache[4] || (_cache[4] = ($event) => backFromAdapted()),
          onOpenWork: openWorkDetail,
          onSearch: searchWork,
          onSubscribe: subscribe
        }, null, 8, ["api", "novel", "media-id", "subscribed-ids"])) : (_openBlock(), _createElementBlock("div", {
          key: 3,
          class: _normalizeClass(["sdas", { "sdas--full": __props.full }])
        }, [
          _createElementVNode("div", _hoisted_1, [
            _createElementVNode("div", _hoisted_2, [
              _cache[37] || (_cache[37] = _createElementVNode("div", { class: "sdas-title" }, "短剧演员", -1)),
              _createElementVNode("div", _hoisted_3, [
                loading.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                  _createTextVNode("正在从短剧百科获取作品…")
                ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  _createTextVNode(_toDisplayString(allTotal.value) + " 部作品 · " + _toDisplayString(actorCount.value) + " 位演员 ", 1),
                  inLibraryKnown.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    _createTextVNode(" · 已入库 " + _toDisplayString(inLibraryCount.value) + " 部", 1)
                  ], 64)) : _createCommentVNode("", true),
                  newWorks.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                    _cache[36] || (_cache[36] = _createTextVNode(" · ", -1)),
                    _createElementVNode("span", _hoisted_4, _toDisplayString(newWorks.value) + " 部新作品", 1)
                  ], 64)) : _createCommentVNode("", true),
                  filteredOut.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                    _createTextVNode(" · 筛选出 " + _toDisplayString(total.value) + " 部", 1)
                  ], 64)) : _createCommentVNode("", true)
                ], 64))
              ])
            ])
          ]),
          _createElementVNode("div", _hoisted_5, [
            _createElementVNode("div", _hoisted_6, [
              _createElementVNode("div", _hoisted_7, [
                _createVNode(_component_v_label, null, {
                  default: _withCtx(() => [..._cache[38] || (_cache[38] = [
                    _createTextVNode("搜索", -1)
                  ])]),
                  _: 1
                })
              ]),
              _createVNode(_component_v_text_field, {
                modelValue: actorQuery.value,
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => actorQuery.value = $event),
                class: "sdas-search",
                density: "compact",
                variant: "outlined",
                "hide-details": "",
                clearable: "",
                placeholder: "搜索演员或作品（输入即查本地缓存，回车 / 搜索打站点）",
                "prepend-inner-icon": "mdi-magnify",
                onKeydown: _cache[6] || (_cache[6] = _withKeys(($event) => runLookup("site"), ["enter"]))
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_btn, {
                class: "sdas-search-btn ml-2",
                size: "small",
                variant: "tonal",
                color: "primary",
                "prepend-icon": "mdi-database-search",
                loading: searchingActors.value || searchingWorks.value,
                onClick: _cache[7] || (_cache[7] = ($event) => runLookup("site"))
              }, {
                default: _withCtx(() => [..._cache[39] || (_cache[39] = [
                  _createTextVNode(" 搜索 ", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              searchActive.value ? (_openBlock(), _createElementBlock("span", _hoisted_8, [
                searchingActors.value || searchingWorks.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                  _createTextVNode("正在查短剧百科…")
                ], 64)) : searchSummary.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                  _createTextVNode(_toDisplayString(searchSummary.value) + " ", 1),
                  searchMode.value === "cache" ? (_openBlock(), _createElementBlock("span", _hoisted_9, " · 本地缓存")) : searchSource.value === "library" ? (_openBlock(), _createElementBlock("span", _hoisted_10, " · 站点无结果，来自数据源库")) : searchMode.value === "site" ? (_openBlock(), _createElementBlock("span", _hoisted_11, " · 站点检索")) : _createCommentVNode("", true)
                ], 64)) : searchMode.value === "cache" ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                  _createTextVNode("缓存里没有，按回车 / 搜索打站点查")
                ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
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
                default: _withCtx(() => [..._cache[40] || (_cache[40] = [
                  _createTextVNode(" 重置 ", -1)
                ])]),
                _: 1
              })) : _createCommentVNode("", true)
            ])
          ]),
          _createElementVNode("div", _hoisted_12, [
            showLeftButton.value ? (_openBlock(), _createElementBlock("button", {
              key: 0,
              type: "button",
              class: "sdas-tabs-scroll sdas-tabs-scroll-left",
              "aria-label": "标签向左滚动",
              onClick: _cache[8] || (_cache[8] = ($event) => scrollTabs("left"))
            }, [
              _createVNode(_component_v_icon, { size: "small" }, {
                default: _withCtx(() => [..._cache[41] || (_cache[41] = [
                  _createTextVNode("mdi-chevron-left", -1)
                ])]),
                _: 1
              })
            ])) : _createCommentVNode("", true),
            _createElementVNode("div", {
              ref_key: "tabsContainerRef",
              ref: tabsContainerRef,
              class: _normalizeClass(["sdas-tabs-track", { "show-indicator": showTabsScrollIndicator.value }]),
              role: "tablist"
            }, [
              (_openBlock(), _createElementBlock(_Fragment, null, _renderList(tabs, (tab) => {
                return _createElementVNode("button", {
                  key: tab.value,
                  type: "button",
                  role: "tab",
                  class: _normalizeClass(["sdas-tab", { "is-active": activeTab.value === tab.value }]),
                  "aria-selected": activeTab.value === tab.value,
                  title: tab.hint,
                  onClick: ($event) => activeTab.value = tab.value
                }, [
                  _createTextVNode(_toDisplayString(tab.title) + " ", 1),
                  tab.value === "actors" ? (_openBlock(), _createElementBlock("span", _hoisted_14, _toDisplayString(followedCount.value), 1)) : tab.value === "subs" ? (_openBlock(), _createElementBlock("span", _hoisted_15, _toDisplayString(subItems.value.length), 1)) : _createCommentVNode("", true)
                ], 10, _hoisted_13);
              }), 64))
            ], 2),
            showRightButton.value ? (_openBlock(), _createElementBlock("button", {
              key: 1,
              type: "button",
              class: "sdas-tabs-scroll sdas-tabs-scroll-right",
              "aria-label": "标签向右滚动",
              onClick: _cache[9] || (_cache[9] = ($event) => scrollTabs("right"))
            }, [
              _createVNode(_component_v_icon, { size: "small" }, {
                default: _withCtx(() => [..._cache[42] || (_cache[42] = [
                  _createTextVNode("mdi-chevron-right", -1)
                ])]),
                _: 1
              })
            ])) : _createCommentVNode("", true)
          ]),
          _createElementVNode("div", _hoisted_16, [
            activeTab.value === "subs" ? (_openBlock(), _createElementBlock("div", _hoisted_17, [
              _createElementVNode("div", _hoisted_18, [
                _cache[43] || (_cache[43] = _createTextVNode(" 已订阅 · ", -1)),
                _createElementVNode("b", null, _toDisplayString(subItems.value.length), 1),
                _cache[44] || (_cache[44] = _createTextVNode(" 部作品 ", -1))
              ]),
              _createVNode(_component_v_chip_group, {
                "model-value": subLibFilter.value,
                mandatory: "",
                "selected-class": "text-primary",
                class: "ml-3",
                "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => subLibFilter.value = $event)
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_chip, {
                    filter: "",
                    tile: "",
                    size: "small",
                    value: "undown",
                    title: "订阅了但还没下成、也不在媒体库的作品（默认视图，空着也停在这页）"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 未下载 " + _toDisplayString(subLibCounts.value.undown), 1)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_chip, {
                    filter: "",
                    tile: "",
                    size: "small",
                    value: "all"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 全部 " + _toDisplayString(subItems.value.length), 1)
                    ]),
                    _: 1
                  }),
                  _createVNode(_component_v_chip, {
                    filter: "",
                    tile: "",
                    size: "small",
                    value: "in",
                    disabled: !subLibCounts.value.hasIn
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 已入库 " + _toDisplayString(subLibCounts.value.hasIn), 1)
                    ]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_v_chip, {
                    filter: "",
                    tile: "",
                    size: "small",
                    value: "not",
                    disabled: !subLibCounts.value.hasNot
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(" 未入库 " + _toDisplayString(subLibCounts.value.hasNot), 1)
                    ]),
                    _: 1
                  }, 8, ["disabled"])
                ]),
                _: 1
              }, 8, ["model-value"]),
              _createVNode(_component_v_btn, {
                icon: "",
                variant: "text",
                size: "x-small",
                class: "ml-1",
                loading: subsLoading.value,
                title: "刷新订阅与搜索状态",
                onClick: _cache[11] || (_cache[11] = ($event) => loadSubscriptions())
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_icon, { size: "18" }, {
                    default: _withCtx(() => [..._cache[45] || (_cache[45] = [
                      _createTextVNode("mdi-refresh", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _: 1
              }, 8, ["loading"]),
              _createVNode(_component_v_text_field, {
                modelValue: randomCount.value,
                "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => randomCount.value = $event),
                modelModifiers: { number: true },
                type: "number",
                min: "1",
                max: "10",
                density: "compact",
                "hide-details": "",
                variant: "outlined",
                class: "sdas-random-count ml-3",
                title: "随机订阅数量（1~10）"
              }, null, 8, ["modelValue"]),
              _createVNode(_component_v_btn, {
                variant: "tonal",
                color: "warning",
                size: "small",
                "prepend-icon": "mdi-shuffle-variant",
                loading: randomSubscribing.value,
                title: "从作品墙全集随机订阅 N 部未入库的作品",
                onClick: _cache[13] || (_cache[13] = ($event) => randomSubscribe())
              }, {
                default: _withCtx(() => [..._cache[46] || (_cache[46] = [
                  _createTextVNode(" 随机订阅 ", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              _createVNode(_component_v_btn, {
                variant: "tonal",
                color: "info",
                size: "small",
                "prepend-icon": "mdi-magnify-scan",
                loading: searchAllRunning.value,
                title: "立即对全部订阅作品执行一轮订阅搜索（已入库 / 已下载的自动跳过）",
                onClick: _cache[14] || (_cache[14] = ($event) => searchAllNow())
              }, {
                default: _withCtx(() => [..._cache[47] || (_cache[47] = [
                  _createTextVNode(" 立即搜索 ", -1)
                ])]),
                _: 1
              }, 8, ["loading"]),
              subEngine.value ? (_openBlock(), _createElementBlock("span", _hoisted_19, _toDisplayString(subEngine.value === "self" ? "订阅搜索：插件自建（不进系统订阅页）" : "订阅搜索：走宿主订阅系统"), 1)) : _createCommentVNode("", true)
            ])) : activeTab.value === "works" ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
              facets.value.studios.length ? (_openBlock(), _createElementBlock("div", _hoisted_20, [
                _createElementVNode("div", _hoisted_21, [
                  _createVNode(_component_v_label, null, {
                    default: _withCtx(() => [..._cache[48] || (_cache[48] = [
                      _createTextVNode("版权方", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _createVNode(_component_v_chip_group, {
                  class: _normalizeClass(["sdas-grid-cells", { "sdas-clip": !isExpanded("studio") }]),
                  column: "",
                  "model-value": studio.value || void 0,
                  "onUpdate:modelValue": _cache[15] || (_cache[15] = ($event) => studio.value = pick($event))
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
                          _createElementVNode("span", _hoisted_22, _toDisplayString(item.count), 1)
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
                  onClick: _cache[16] || (_cache[16] = ($event) => toggleRow("studio"))
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(isExpanded("studio") ? "收起" : "展开"), 1)
                  ]),
                  _: 1
                }, 8, ["prepend-icon"])) : _createCommentVNode("", true)
              ])) : _createCommentVNode("", true),
              facets.value.platforms.length ? (_openBlock(), _createElementBlock("div", _hoisted_23, [
                _createElementVNode("div", _hoisted_24, [
                  _createVNode(_component_v_label, null, {
                    default: _withCtx(() => [..._cache[49] || (_cache[49] = [
                      _createTextVNode("播放平台", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _createVNode(_component_v_chip_group, {
                  class: _normalizeClass(["sdas-grid-cells", { "sdas-clip": !isExpanded("platform") }]),
                  column: "",
                  "model-value": platform.value || void 0,
                  "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => platform.value = pick($event))
                }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(facets.value.platforms, (item) => {
                      return _openBlock(), _createBlock(_component_v_chip, {
                        key: item.value,
                        value: item.value,
                        color: platform.value === item.value ? "primary" : "",
                        filter: "",
                        tile: "",
                        title: item.value
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.value), 1),
                          _createElementVNode("span", _hoisted_25, _toDisplayString(item.count), 1)
                        ]),
                        _: 2
                      }, 1032, ["value", "color", "title"]);
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["class", "model-value"]),
                facets.value.platforms.length > COLLAPSED_LIMIT ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 0,
                  class: "sdas-row-toggle",
                  variant: "text",
                  "prepend-icon": isExpanded("platform") ? "mdi-chevron-up" : "mdi-chevron-down",
                  onClick: _cache[18] || (_cache[18] = ($event) => toggleRow("platform"))
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(isExpanded("platform") ? "收起" : "展开"), 1)
                  ]),
                  _: 1
                }, 8, ["prepend-icon"])) : _createCommentVNode("", true)
              ])) : _createCommentVNode("", true),
              facets.value.genres.length ? (_openBlock(), _createElementBlock("div", _hoisted_26, [
                _createElementVNode("div", _hoisted_27, [
                  _createVNode(_component_v_label, null, {
                    default: _withCtx(() => [..._cache[50] || (_cache[50] = [
                      _createTextVNode("类型", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _createVNode(_component_v_chip_group, {
                  class: _normalizeClass(["sdas-grid-cells", { "sdas-clip": !isExpanded("genre") }]),
                  column: "",
                  "model-value": genre.value || void 0,
                  "onUpdate:modelValue": _cache[19] || (_cache[19] = ($event) => genre.value = pick($event))
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
                          _createElementVNode("span", _hoisted_28, _toDisplayString(item.count), 1)
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
                  onClick: _cache[20] || (_cache[20] = ($event) => toggleRow("genre"))
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(isExpanded("genre") ? "收起" : "展开"), 1)
                  ]),
                  _: 1
                }, 8, ["prepend-icon"])) : _createCommentVNode("", true)
              ])) : _createCommentVNode("", true),
              facets.value.years.length ? (_openBlock(), _createElementBlock("div", _hoisted_29, [
                _createElementVNode("div", _hoisted_30, [
                  _createVNode(_component_v_label, null, {
                    default: _withCtx(() => [..._cache[51] || (_cache[51] = [
                      _createTextVNode("年份", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _createVNode(_component_v_chip_group, {
                  "model-value": year.value || void 0,
                  "onUpdate:modelValue": _cache[21] || (_cache[21] = ($event) => year.value = pick($event))
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
                          _createElementVNode("span", _hoisted_31, _toDisplayString(item.count), 1)
                        ]),
                        _: 2
                      }, 1032, ["value", "color"]);
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["model-value"])
              ])) : _createCommentVNode("", true),
              _createElementVNode("div", _hoisted_32, [
                _createElementVNode("div", _hoisted_33, [
                  _createVNode(_component_v_label, null, {
                    default: _withCtx(() => [..._cache[52] || (_cache[52] = [
                      _createTextVNode("媒体库", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _createElementVNode("div", _hoisted_34, [
                  _createElementVNode("button", {
                    type: "button",
                    class: _normalizeClass(["sdas-library-card", { "is-active": onlyNotInLibrary.value }]),
                    disabled: !probeAvailable.value,
                    title: "只显示还没进 MoviePilot 媒体库的作品（判定与媒体详情页一致：身份精确匹配，未命中按片名+年份回退）",
                    onClick: _cache[22] || (_cache[22] = ($event) => onlyNotInLibrary.value = !onlyNotInLibrary.value)
                  }, [
                    _createVNode(_component_v_icon, {
                      size: "16",
                      class: "mr-1"
                    }, {
                      default: _withCtx(() => [..._cache[53] || (_cache[53] = [
                        _createTextVNode("mdi-database-off-outline", -1)
                      ])]),
                      _: 1
                    }),
                    _cache[54] || (_cache[54] = _createElementVNode("span", null, "未入库", -1)),
                    onlyNotInLibrary.value && filteredCount.value ? (_openBlock(), _createElementBlock("span", _hoisted_36, _toDisplayString(filteredCount.value), 1)) : _createCommentVNode("", true)
                  ], 10, _hoisted_35),
                  _createElementVNode("button", {
                    type: "button",
                    class: _normalizeClass(["sdas-library-card", { "is-active": onlyNotSubscribed.value }]),
                    title: "只显示还没订阅的作品（订阅清单 = 插件订阅清单 ∪ 宿主 djbaike 订阅，与卡片红心同一份）",
                    onClick: _cache[23] || (_cache[23] = ($event) => onlyNotSubscribed.value = !onlyNotSubscribed.value)
                  }, [
                    _createVNode(_component_v_icon, {
                      size: "16",
                      class: "mr-1"
                    }, {
                      default: _withCtx(() => [..._cache[55] || (_cache[55] = [
                        _createTextVNode("mdi-heart-off-outline", -1)
                      ])]),
                      _: 1
                    }),
                    _cache[56] || (_cache[56] = _createElementVNode("span", null, "未订阅", -1)),
                    onlyNotSubscribed.value && filteredCount.value ? (_openBlock(), _createElementBlock("span", _hoisted_37, _toDisplayString(filteredCount.value), 1)) : _createCommentVNode("", true)
                  ], 2)
                ])
              ])
            ], 64)) : activeTab.value === "actors" ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
              _createElementVNode("div", _hoisted_38, [
                _createElementVNode("div", _hoisted_39, [
                  _createVNode(_component_v_label, null, {
                    default: _withCtx(() => [..._cache[57] || (_cache[57] = [
                      _createTextVNode("分类", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _createVNode(_component_v_chip_group, {
                  "model-value": actorGender.value || void 0,
                  "onUpdate:modelValue": _cache[24] || (_cache[24] = ($event) => actorGender.value = pick($event))
                }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorGroups.value, (group) => {
                      return _openBlock(), _createBlock(_component_v_chip, {
                        key: group.key,
                        value: group.key,
                        color: actorGender.value === group.key ? "primary" : "",
                        title: actorGender.value === group.key ? "取消分类（看全部）" : `只看${group.title}`,
                        filter: "",
                        tile: ""
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(group.title), 1),
                          _createElementVNode("span", _hoisted_40, _toDisplayString(group.items.length), 1)
                        ]),
                        _: 2
                      }, 1032, ["value", "color", "title"]);
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["model-value"])
              ]),
              _createElementVNode("div", _hoisted_41, [
                _createElementVNode("div", _hoisted_42, [
                  _cache[58] || (_cache[58] = _createTextVNode(" 已关注 · ", -1)),
                  _createElementVNode("b", null, _toDisplayString(followedActors.value.length), 1),
                  _cache[59] || (_cache[59] = _createTextVNode(" 位演员 ", -1))
                ]),
                _createVNode(_component_v_btn, {
                  icon: "",
                  variant: "text",
                  size: "x-small",
                  class: "ml-1",
                  loading: followedLoading.value,
                  title: "刷新演员列表（会给还没有头像的演员补一次档案）",
                  onClick: _cache[25] || (_cache[25] = ($event) => refreshFollowed())
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, { size: "18" }, {
                      default: _withCtx(() => [..._cache[60] || (_cache[60] = [
                        _createTextVNode("mdi-account-sync-outline", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 8, ["loading"]),
                followedError.value ? (_openBlock(), _createElementBlock("span", _hoisted_43, _toDisplayString(followedError.value), 1)) : _createCommentVNode("", true)
              ])
            ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
              _createElementVNode("div", _hoisted_44, [
                _createElementVNode("div", _hoisted_45, [
                  _createVNode(_component_v_label, null, {
                    default: _withCtx(() => [..._cache[61] || (_cache[61] = [
                      _createTextVNode("目录", -1)
                    ])]),
                    _: 1
                  })
                ]),
                _createVNode(_component_v_chip_group, {
                  "model-value": discoverView.value,
                  "onUpdate:modelValue": _cache[26] || (_cache[26] = ($event) => setDiscoverView($event))
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_chip, {
                      value: "people",
                      color: discoverView.value === "people" ? "primary" : "",
                      title: "翻站点的演员目录",
                      filter: "",
                      tile: ""
                    }, {
                      default: _withCtx(() => [..._cache[62] || (_cache[62] = [
                        _createTextVNode(" 演员 ", -1)
                      ])]),
                      _: 1
                    }, 8, ["color"]),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(rankItems.value, (item) => {
                      return _openBlock(), _createBlock(_component_v_chip, {
                        key: item.key,
                        value: item.key,
                        color: discoverView.value === item.key ? "primary" : "",
                        title: `看站点${item.name}`,
                        filter: "",
                        tile: ""
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode(_toDisplayString(item.name), 1)
                        ]),
                        _: 2
                      }, 1032, ["value", "color", "title"]);
                    }), 128))
                  ]),
                  _: 1
                }, 8, ["model-value"])
              ]),
              _createElementVNode("div", _hoisted_46, [
                _createElementVNode("div", _hoisted_47, [
                  discoverView.value === "people" ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                    peopleLoading.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _createTextVNode("正在取" + _toDisplayString(peopleKindLabel.value) + "目录…", 1)
                    ], 64)) : peopleRows.value.length ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _cache[63] || (_cache[63] = _createTextVNode(" 已加载 ", -1)),
                      _createElementVNode("b", null, _toDisplayString(peopleRows.value.length), 1),
                      _createTextVNode(" 位" + _toDisplayString(peopleKindLabel.value), 1)
                    ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                      _createTextVNode(_toDisplayString(peopleMessage.value || "还没有加载"), 1)
                    ], 64))
                  ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                    rankLoading.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                      _createTextVNode("正在取" + _toDisplayString(rankName.value) + "…", 1)
                    ], 64)) : rankMedias.value.length ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _createTextVNode(_toDisplayString(rankName.value) + " · " + _toDisplayString(rankMedias.value.length) + " 部", 1)
                    ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                      _createTextVNode(_toDisplayString(rankMessage.value || "还没有加载"), 1)
                    ], 64))
                  ], 64))
                ]),
                discoverView.value === "people" && peopleRows.value.length && peopleHasMore.value ? (_openBlock(), _createElementBlock("span", _hoisted_48, " 继续下滑加载更多 ")) : _createCommentVNode("", true),
                discoverView.value === "people" && peopleError.value ? (_openBlock(), _createElementBlock("span", _hoisted_49, _toDisplayString(peopleError.value), 1)) : _createCommentVNode("", true)
              ])
            ], 64))
          ]),
          searchActive.value ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
            _createElementVNode("div", {
              ref_key: "gridRef",
              ref: gridRef,
              class: "sdas-measure",
              "aria-hidden": "true"
            }, null, 512),
            !actorResults.value.length && !workResults.value.length && (searchingActors.value || searchingWorks.value) ? (_openBlock(), _createBlock(LoadingBanner, {
              key: 0,
              text: "正在查短剧百科…"
            })) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
              actorResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_50, [
                _createElementVNode("div", _hoisted_51, "演员 · " + _toDisplayString(actorResults.value.length), 1),
                _createElementVNode("div", {
                  class: "sdas-grid",
                  style: _normalizeStyle(gridStyle.value),
                  ref: setGridNode
                }, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(actorResults.value, (item) => {
                    return _openBlock(), _createElementBlock("div", {
                      key: item.actor_id,
                      class: "sdas-item"
                    }, [
                      _createVNode(ActorCard, {
                        item,
                        added: isActorAdded(item),
                        busy: addingActorId.value === item.actor_id || removingActorId.value === item.actor_id,
                        loaded: isPosterLoaded(actorKey(item)),
                        "subscribe-all": "",
                        "subscribe-all-busy": subscribingAllKey.value === actorKey(item),
                        onOpen: ($event) => openActorDetail(item),
                        onPage: ($event) => openActorPage(item),
                        onToggle: ($event) => isActorAdded(item) ? unsubscribeActor(item) : subscribeActor(item),
                        onSubscribeAll: ($event) => subscribeAllWorks(item),
                        onPoster: ($event) => markPosterLoaded(actorKey(item))
                      }, null, 8, ["item", "added", "busy", "loaded", "subscribe-all-busy", "onOpen", "onPage", "onToggle", "onSubscribeAll", "onPoster"])
                    ]);
                  }), 128))
                ], 4)
              ])) : !searchingActors.value ? (_openBlock(), _createElementBlock("div", _hoisted_52, " 没有找到相关演员 ")) : _createCommentVNode("", true),
              workResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_53, [
                _createElementVNode("div", _hoisted_54, "作品 · " + _toDisplayString(workResults.value.length), 1),
                _createElementVNode("div", {
                  class: "sdas-grid",
                  style: _normalizeStyle(gridStyle.value),
                  ref: setGridNode
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
                        subscribing: subscribingId.value,
                        searching: searchNowId.value,
                        onPoster: ($event) => markPosterLoaded(work.key),
                        onOpen: openWorkDetail,
                        onSearch: searchWork,
                        onSubscribe: subscribe,
                        onSearchNow: searchNow
                      }, null, 8, ["work", "loaded", "subscribed", "subscribing", "searching", "onPoster"])
                    ]);
                  }), 128))
                ], 4)
              ])) : !searchingWorks.value && actorResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_55, " 没有找到相关作品 ")) : _createCommentVNode("", true),
              !actorResults.value.length && !workResults.value.length ? (_openBlock(), _createBlock(NoDataFound, {
                key: 4,
                "error-code": "404",
                "error-title": `没找到「${searchKeyword.value}」`,
                "error-description": "换个名字试试 —— 短剧百科只收录站上有的演员和作品"
              }, null, 8, ["error-title"])) : _createCommentVNode("", true)
            ], 64))
          ], 64)) : activeTab.value === "actors" ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
            followedLoading.value && !followedActors.value.length ? (_openBlock(), _createBlock(LoadingBanner, {
              key: 0,
              text: "正在取演员列表…"
            })) : !followedActors.value.length ? (_openBlock(), _createBlock(NoDataFound, {
              key: 1,
              "error-code": "404",
              "error-title": "还没有关注的演员",
              "error-description": "在「搜索」里搜一位演员，点卡片上的「订阅」加进来"
            })) : !shownActors.value.length ? (_openBlock(), _createBlock(NoDataFound, {
              key: 2,
              "error-code": "404",
              "error-title": "这一类里还没有关注的演员",
              "error-description": "点上面的分类标签取消分类，就能看全部演员"
            })) : (_openBlock(), _createElementBlock("div", {
              key: 3,
              ref_key: "actorGridAnchor",
              ref: actorGridAnchor,
              class: "sdas-actor-grid"
            }, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(shownActors.value, (item) => {
                return _openBlock(), _createElementBlock("div", {
                  key: actorKey(item),
                  class: "sdas-actor-cell",
                  "data-cell-key": actorKey(item),
                  ref_for: true,
                  ref: (el) => observeCell(el, actorKey(item))
                }, [
                  isCellMounted(actorKey(item)) ? (_openBlock(), _createBlock(ActorCard, {
                    key: 0,
                    item,
                    state: item.state,
                    added: true,
                    busy: addingActorId.value === item.actor_id || removingActorId.value === item.actor_id,
                    loaded: isPosterLoaded(actorKey(item)),
                    "subscribe-all": "",
                    "subscribe-all-busy": subscribingAllKey.value === actorKey(item),
                    onOpen: ($event) => openActorDetail(item),
                    onPage: ($event) => openActorPage(item),
                    onToggle: ($event) => unsubscribeActor(item),
                    onSubscribeAll: ($event) => subscribeAllWorks(item),
                    onPoster: ($event) => markPosterLoaded(actorKey(item))
                  }, null, 8, ["item", "state", "busy", "loaded", "subscribe-all-busy", "onOpen", "onPage", "onToggle", "onSubscribeAll", "onPoster"])) : _createCommentVNode("", true)
                ], 8, _hoisted_56);
              }), 128)),
              _createVNode(AlphaIndex, {
                stops: actorLetterStops.value,
                anchor: actorGridAnchor.value,
                onJump: jumpToActorLetter
              }, null, 8, ["stops", "anchor"])
            ], 512))
          ], 64)) : activeTab.value === "people" && discoverView.value === "people" ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
            peopleLoading.value && !peopleRows.value.length ? (_openBlock(), _createBlock(LoadingBanner, {
              key: 0,
              text: `正在取${peopleKindLabel.value}目录…`
            }, null, 8, ["text"])) : !peopleRows.value.length ? (_openBlock(), _createBlock(NoDataFound, {
              key: 1,
              "error-code": "404",
              "error-title": peopleMessage.value ? "人物目录还取不到" : `没有取到${peopleKindLabel.value}`,
              "error-description": peopleMessage.value || "数据源这次没有返回内容，过一会儿再试"
            }, null, 8, ["error-title", "error-description"])) : (_openBlock(), _createBlock(ProgressiveCardGrid, {
              key: 2,
              items: peopleRows.value,
              "min-item-width": MIN_ITEM_WIDTH,
              "item-aspect-ratio": 1.5,
              gap: GRID_GAP,
              "overscan-rows": 2,
              "get-item-key": actorKey
            }, {
              default: _withCtx(({ item }) => [
                _createVNode(ActorCard, {
                  item,
                  added: isActorAdded(item),
                  busy: addingActorId.value === item.actor_id || removingActorId.value === item.actor_id,
                  loaded: isPosterLoaded(actorKey(item)),
                  "subscribe-all": peopleKind.value === "yanyuan",
                  "subscribe-all-busy": subscribingAllKey.value === actorKey(item),
                  onOpen: ($event) => openActorDetail(item),
                  onPage: ($event) => openActorPage(item),
                  onToggle: ($event) => isActorAdded(item) ? unsubscribeActor(item) : subscribeActor(item),
                  onSubscribeAll: ($event) => subscribeAllWorks(item),
                  onPoster: ($event) => markPosterLoaded(actorKey(item))
                }, null, 8, ["item", "added", "busy", "loaded", "subscribe-all", "subscribe-all-busy", "onOpen", "onPage", "onToggle", "onSubscribeAll", "onPoster"])
              ]),
              _: 1
            }, 8, ["items"])),
            _createElementVNode("div", {
              ref_key: "peopleSentinel",
              ref: peopleSentinel,
              class: "sdas-sentinel"
            }, [
              peopleLoading.value && peopleRows.value.length ? (_openBlock(), _createBlock(_component_v_progress_circular, {
                key: 0,
                indeterminate: "",
                size: "20",
                width: "2"
              })) : peopleRows.value.length && !peopleHasMore.value ? (_openBlock(), _createElementBlock("span", _hoisted_57, " 已到末尾 · 共 " + _toDisplayString(peopleRows.value.length) + " 位" + _toDisplayString(peopleKindLabel.value), 1)) : _createCommentVNode("", true)
            ], 512)
          ], 64)) : activeTab.value === "people" && discoverView.value !== "people" ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
            rankLoading.value && !rankMedias.value.length ? (_openBlock(), _createBlock(LoadingBanner, {
              key: 0,
              text: `正在取${rankName.value}…`
            }, null, 8, ["text"])) : !rankMedias.value.length ? (_openBlock(), _createBlock(NoDataFound, {
              key: 1,
              "error-code": "404",
              "error-title": rankMessage.value ? "榜单还取不到" : `没有取到${rankName.value}`,
              "error-description": rankMessage.value || "数据源这次没有返回内容，过一会儿再试"
            }, null, 8, ["error-title", "error-description"])) : (_openBlock(), _createBlock(ProgressiveCardGrid, {
              key: 2,
              items: rankWorkItems.value,
              "min-item-width": MIN_ITEM_WIDTH,
              "item-aspect-ratio": 1.5,
              gap: GRID_GAP,
              "overscan-rows": 2,
              "get-item-key": (item) => item.key
            }, {
              default: _withCtx(({ item }) => [
                _createVNode(WorkCard, {
                  work: item,
                  loaded: isPosterLoaded(item.key),
                  subscribed: subscribed.value.has(item.media_id),
                  subscribing: subscribingId.value,
                  searching: searchNowId.value,
                  onPoster: ($event) => markPosterLoaded(item.key),
                  onOpen: openWorkDetail,
                  onSearch: searchWork,
                  onSubscribe: subscribe,
                  onSearchNow: searchNow
                }, null, 8, ["work", "loaded", "subscribed", "subscribing", "searching", "onPoster"])
              ]),
              _: 1
            }, 8, ["items", "get-item-key"])),
            rankMedias.value.length ? (_openBlock(), _createElementBlock("div", {
              key: 3,
              ref_key: "rankSentinel",
              ref: rankSentinel,
              class: "sdas-sentinel"
            }, [
              rankLoading.value ? (_openBlock(), _createBlock(_component_v_progress_circular, {
                key: 0,
                indeterminate: "",
                size: "20",
                width: "2"
              })) : rankHasMore.value ? (_openBlock(), _createElementBlock("span", _hoisted_58, " 继续下滑加载更多 ")) : (_openBlock(), _createElementBlock("span", _hoisted_59, "已到末尾 · 共 " + _toDisplayString(rankMedias.value.length) + " 部", 1))
            ], 512)) : _createCommentVNode("", true)
          ], 64)) : activeTab.value === "subs" ? (_openBlock(), _createElementBlock(_Fragment, { key: 4 }, [
            subsLoading.value && !subWorkItems.value.length ? (_openBlock(), _createBlock(LoadingBanner, {
              key: 0,
              text: "正在取订阅列表…"
            })) : !subWorkItems.value.length ? (_openBlock(), _createBlock(NoDataFound, {
              key: 1,
              "error-code": "404",
              "error-title": "还没有订阅的作品",
              "error-description": "在「作品」页找到想追的剧，点卡片上的「订阅」，它就会出现在这里并自动搜索下载"
            })) : !shownSubWorkItems.value.length ? (_openBlock(), _createBlock(NoDataFound, {
              key: 2,
              "error-code": "404",
              "error-title": subLibFilter.value === "in" ? "没有已入库的订阅" : subLibFilter.value === "undown" ? "没有未下载的订阅" : "没有未入库的订阅",
              "error-description": "换一个筛选看看，或点工具栏里的「全部」"
            }, null, 8, ["error-title"])) : (_openBlock(), _createBlock(GlassMediaBackdrop, { key: 3 }, {
              default: _withCtx(() => [
                _createVNode(ProgressiveCardGrid, {
                  items: shownSubWorkItems.value,
                  "min-item-width": MIN_ITEM_WIDTH,
                  "item-aspect-ratio": 1.5,
                  gap: GRID_GAP,
                  "get-item-key": (item) => item.key
                }, {
                  default: _withCtx(({ item }) => [
                    _createVNode(WorkCard, {
                      work: item,
                      loaded: isPosterLoaded(item.key),
                      subscribed: subscribed.value.has(item.media_id),
                      subscribing: subscribingId.value,
                      searching: searchNowId.value,
                      onPoster: ($event) => markPosterLoaded(item.key),
                      onOpen: openWorkDetail,
                      onSearch: searchWork,
                      onSubscribe: subscribe,
                      onSearchNow: searchNow
                    }, null, 8, ["work", "loaded", "subscribed", "subscribing", "searching", "onPoster"])
                  ]),
                  _: 1
                }, 8, ["items", "get-item-key"])
              ]),
              _: 1
            }))
          ], 64)) : (_openBlock(), _createElementBlock(_Fragment, { key: 5 }, [
            !works.value.length && !error.value ? (_openBlock(), _createBlock(LoadingBanner, {
              key: 0,
              text: "正在从短剧百科获取作品…"
            })) : error.value && !works.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_60, [
              _cache[65] || (_cache[65] = _createElementVNode("span", { class: "text-body-2 text-medium-emphasis" }, "网络错误", -1)),
              _createVNode(_component_v_btn, {
                "prepend-icon": "mdi-refresh",
                size: "small",
                variant: "tonal",
                onClick: reload
              }, {
                default: _withCtx(() => [..._cache[64] || (_cache[64] = [
                  _createTextVNode("重试", -1)
                ])]),
                _: 1
              })
            ])) : !works.value.length ? (_openBlock(), _createBlock(NoDataFound, {
              key: 2,
              "error-code": "404",
              "error-title": !actorCount.value ? "还没有添加演员" : "没有符合条件的作品",
              "error-description": !actorCount.value ? "在「搜索」里搜一位演员，点卡片上的「订阅」加进来" : filteredOut.value ? "换个筛选条件试试" : emptyHint.value
            }, null, 8, ["error-title", "error-description"])) : (_openBlock(), _createBlock(GlassMediaBackdrop, { key: 3 }, {
              default: _withCtx(() => [
                _createVNode(ProgressiveCardGrid, {
                  items: works.value,
                  "min-item-width": MIN_ITEM_WIDTH,
                  "item-aspect-ratio": 1.5,
                  gap: GRID_GAP,
                  "get-item-key": workKey
                }, {
                  default: _withCtx(({ item }) => [
                    _createVNode(WorkCard, {
                      work: item,
                      loaded: isPosterLoaded(item.key),
                      subscribed: subscribed.value.has(item.media_id),
                      subscribing: subscribingId.value,
                      searching: searchNowId.value,
                      onPoster: ($event) => markPosterLoaded(item.key),
                      onOpen: openWorkDetail,
                      onSearch: searchWork,
                      onSubscribe: subscribe,
                      onSearchNow: searchNow
                    }, null, 8, ["work", "loaded", "subscribed", "subscribing", "searching", "onPoster"])
                  ]),
                  _: 1
                }, 8, ["items"])
              ]),
              _: 1
            })),
            _createElementVNode("div", {
              ref_key: "sentinel",
              ref: sentinel,
              class: "sdas-sentinel"
            }, [
              loadingMore.value ? (_openBlock(), _createBlock(_component_v_progress_circular, {
                key: 0,
                indeterminate: "",
                size: "20",
                width: "2"
              })) : works.value.length && done.value ? (_openBlock(), _createElementBlock("span", _hoisted_61, "已到末尾 · 共 " + _toDisplayString(total.value) + " 部", 1)) : _createCommentVNode("", true)
            ], 512)
          ], 64)),
          (_openBlock(), _createBlock(_Teleport, { to: "body" }, [
            showBackTop.value ? (_openBlock(), _createBlock(_component_v_btn, {
              key: 0,
              class: "sdas-back-top",
              icon: "",
              color: "primary",
              elevation: "6",
              title: "回到列表顶部",
              onClick: _cache[27] || (_cache[27] = ($event) => scrollToTop())
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, { size: "26" }, {
                  default: _withCtx(() => [..._cache[66] || (_cache[66] = [
                    _createTextVNode("mdi-arrow-up", -1)
                  ])]),
                  _: 1
                })
              ]),
              _: 1
            })) : _createCommentVNode("", true)
          ]))
        ], 2)),
        _createVNode(_component_v_snackbar, {
          modelValue: tipOpen.value,
          "onUpdate:modelValue": _cache[28] || (_cache[28] = ($event) => tipOpen.value = $event),
          timeout: 3200,
          location: "bottom",
          color: tipType.value === "error" ? "error" : void 0
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(tip.value), 1)
          ]),
          _: 1
        }, 8, ["modelValue", "color"]),
        _createVNode(_component_v_dialog, {
          modelValue: cancelOpen.value,
          "onUpdate:modelValue": _cache[31] || (_cache[31] = ($event) => cancelOpen.value = $event),
          "max-width": "380"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, { class: "text-subtitle-1" }, {
                  default: _withCtx(() => [..._cache[67] || (_cache[67] = [
                    _createTextVNode("取消订阅", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, { class: "text-body-2" }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 确定取消订阅《" + _toDisplayString(cancelTarget.value?.title) + "》吗？取消后系统订阅页里也会一并移除。 ", 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_actions, null, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "text",
                      disabled: subscribing.value,
                      onClick: _cache[29] || (_cache[29] = ($event) => cancelOpen.value = false)
                    }, {
                      default: _withCtx(() => [..._cache[68] || (_cache[68] = [
                        _createTextVNode(" 返回 ", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode(_component_v_btn, {
                      size: "small",
                      variant: "tonal",
                      color: "error",
                      loading: subscribing.value,
                      onClick: _cache[30] || (_cache[30] = ($event) => confirmCancelSubscribe())
                    }, {
                      default: _withCtx(() => [..._cache[69] || (_cache[69] = [
                        _createTextVNode(" 取消订阅 ", -1)
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
        (_openBlock(), _createBlock(_Teleport, { to: "body" }, [
          _createElementVNode("div", {
            class: _normalizeClass(["sdas-logfloat", {
              "is-dragging": logDragging.value,
              "is-down": logExpandDown.value,
              "is-right": logExpandRight.value
            }]),
            style: _normalizeStyle(logStyle.value)
          }, [
            _createElementVNode("div", {
              ref_key: "logsBodyRef",
              ref: logsBodyRef,
              class: "sdas-logfloat-body",
              onScroll: _cache[32] || (_cache[32] = ($event) => onLogScroll()),
              onPointerenter: _cache[33] || (_cache[33] = ($event) => onLogExpand())
            }, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(logLines.value, (line, idx) => {
                return _openBlock(), _createElementBlock("div", {
                  key: idx,
                  class: "sdas-logfloat-line"
                }, _toDisplayString(line), 1);
              }), 128)),
              !logLines.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_62, "暂无日志")) : _createCommentVNode("", true)
            ], 544),
            _createElementVNode("div", {
              ref_key: "logBarRef",
              ref: logBarRef,
              class: "sdas-logfloat-bar",
              title: "按住可拖动（可拖到屏幕任意位置）",
              onPointerdown: _cache[34] || (_cache[34] = ($event) => onLogPointerDown($event)),
              onPointerenter: _cache[35] || (_cache[35] = ($event) => onLogExpand())
            }, [
              _createVNode(_component_v_icon, { size: "13" }, {
                default: _withCtx(() => [..._cache[70] || (_cache[70] = [
                  _createTextVNode("mdi-drag-variant", -1)
                ])]),
                _: 1
              }),
              _cache[71] || (_cache[71] = _createElementVNode("span", null, "最近日志", -1))
            ], 544)
          ], 6)
        ]))
      ], 64);
    };
  }
});

const ActorWall = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-9ec46fe0"]]);

export { ActorWall as A };
