import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import Config, { p as proxyImage, r as resolveApi, a as recognizeTitle, _ as _export_sfc, f as fetchStatus, b as fetchConfig, s as saveConfig, l as lookupKeyword, c as fetchActor, d as fetchUrls, e as clearUrls, g as fetchCache, h as deleteCacheEntry, i as clearCache, j as fetchCacheEntry } from './__federation_expose_Config-CRW61h5d.js';

function pretty(value) {
  return JSON.stringify(value ?? null, null, 2);
}
function formatCount(value) {
  if (!value) return "";
  if (value >= 1e8) return `${(value / 1e8).toFixed(1)} 亿`;
  if (value >= 1e4) return `${Math.round(value / 1e4)} 万`;
  return String(value);
}
function recordMeta(record, withOrigin = false) {
  if (!record) return "";
  const parts = [];
  const release = String(record.release_date || "").trim();
  const year = String(record.year || "").trim();
  if (record.kind) parts.push(String(record.kind));
  if (release) parts.push(`首播 ${release}`);
  else if (year) parts.push(year);
  if (record.episode_count) parts.push(`共 ${record.episode_count} 集`);
  if (record.duration_minutes) {
    parts.push(
      `全集 ${record.duration_minutes} 分钟` + (record.episode_minutes ? `（单集约 ${record.episode_minutes} 分钟）` : "")
    );
  }
  if (record.studio) parts.push(String(record.studio));
  if (record.rating) parts.push(`评分 ${record.rating}`);
  if (record.heat) parts.push(`热度 ${formatCount(record.heat)}`);
  if (record.play_count) parts.push(`播放 ${formatCount(record.play_count)}`);
  if (record.favorite_count) parts.push(`收藏 ${formatCount(record.favorite_count)}`);
  if (withOrigin) parts.push(`来源 ${record.origin === "detail" ? "详情页" : "检索结果"}`);
  return parts.join(" ｜ ");
}
function castLine(record) {
  const actors = record?.actors || [];
  if (!actors.length) return "";
  return actors.slice(0, 10).map((actor) => actor.character ? `${actor.name}（饰 ${actor.character}）` : actor.name).join("、");
}

const {defineComponent:_defineComponent$2} = await importShared('vue');

const {unref:_unref$2,resolveComponent:_resolveComponent$2,createVNode:_createVNode$2,withCtx:_withCtx$2,toDisplayString:_toDisplayString$2,openBlock:_openBlock$2,createElementBlock:_createElementBlock$2,createCommentVNode:_createCommentVNode$2,createTextVNode:_createTextVNode$2,createElementVNode:_createElementVNode$2,renderList:_renderList$2,Fragment:_Fragment$2,createBlock:_createBlock$2} = await importShared('vue');

const _hoisted_1$2 = {
  class: "d-flex",
  style: { "gap": "12px" }
};
const _hoisted_2$2 = {
  class: "flex-grow-1",
  style: { "min-width": "0" }
};
const _hoisted_3$2 = { class: "text-subtitle-2" };
const _hoisted_4$2 = {
  key: 0,
  class: "text-caption sdbs-dim ml-2"
};
const _hoisted_5$2 = { class: "text-caption sdbs-dim mt-1" };
const _hoisted_6$2 = {
  key: 0,
  class: "text-caption mt-2 sdbs-clamp"
};
const _hoisted_7$2 = {
  key: 0,
  class: "mt-2"
};
const _hoisted_8$2 = {
  class: "d-flex align-center mt-2 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_9$2 = {
  key: 1,
  class: "text-caption sdbs-dim"
};
const _hoisted_10$2 = {
  key: 1,
  class: "sdbs-pre mt-2"
};
const _hoisted_11$2 = { class: "text-subtitle-2 mt-3 mb-2" };
const _hoisted_12$1 = { class: "text-caption sdbs-dim ml-1" };
const _hoisted_13$1 = {
  key: 0,
  class: "text-caption sdbs-dim"
};
const _hoisted_14$1 = {
  class: "d-flex",
  style: { "gap": "8px" }
};
const _hoisted_15$1 = {
  class: "flex-grow-1",
  style: { "min-width": "0" }
};
const _hoisted_16$1 = { class: "text-body-2 sdbs-work-title" };
const _hoisted_17$1 = { class: "text-caption sdbs-dim mt-1" };
const _hoisted_18$1 = {
  key: 0,
  class: "mt-1"
};
const _hoisted_19$1 = { class: "d-flex align-center mt-1" };
const _hoisted_20$1 = {
  key: 0,
  class: "sdbs-pre mt-1"
};
const {computed: computed$2,ref: ref$2,watch: watch$2} = await importShared('vue');
const _sfc_main$2 = /* @__PURE__ */ _defineComponent$2({
  __name: "ActorCard",
  props: {
    profile: {},
    api: {},
    compact: { type: Boolean },
    extra: {}
  },
  setup(__props) {
    const props = __props;
    const actor = computed$2(() => props.profile || {});
    const works = computed$2(() => actor.value.works || []);
    const rawOpen = ref$2(false);
    const openWorks = ref$2(/* @__PURE__ */ new Set());
    const workFull = ref$2({});
    const workLoadingIndex = ref$2(null);
    const meta = computed$2(() => {
      const item = actor.value;
      const parts = [];
      if (item.job_title) parts.push(item.job_title);
      if (item.gender) parts.push(`性别 ${item.gender}`);
      if (item.nationality) parts.push(item.nationality);
      parts.push(`作品 ${item.works_count ?? (item.works || []).length} 部`);
      return parts.join(" ｜ ");
    });
    watch$2(() => props.profile, () => {
      rawOpen.value = false;
      openWorks.value = /* @__PURE__ */ new Set();
      workFull.value = {};
      workLoadingIndex.value = null;
    });
    function workView(index) {
      return workFull.value[index] ?? works.value[index] ?? {};
    }
    function workComplete(index, work) {
      return Boolean(workFull.value[index]) || work?.origin === "detail";
    }
    function workTags(index, work) {
      const tags = (workFull.value[index]?.tags ?? work.tags) || [];
      return workComplete(index, work) ? tags : tags.slice(0, 3);
    }
    async function loadWorkDetail(index) {
      const client = resolveApi({ api: props.api });
      const work = works.value[index];
      if (!client || !work?.media_id || workComplete(index, work)) return;
      workLoadingIndex.value = index;
      try {
        const report = await recognizeTitle(client, { media_id: work.media_id });
        if (report?.success && report.record) {
          workFull.value = { ...workFull.value, [index]: report.record };
        }
      } finally {
        workLoadingIndex.value = null;
      }
    }
    function toggleWorkRaw(index) {
      const next = new Set(openWorks.value);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      openWorks.value = next;
    }
    return (_ctx, _cache) => {
      const _component_v_img = _resolveComponent$2("v-img");
      const _component_v_avatar = _resolveComponent$2("v-avatar");
      const _component_v_chip = _resolveComponent$2("v-chip");
      const _component_v_btn = _resolveComponent$2("v-btn");
      const _component_v_spacer = _resolveComponent$2("v-spacer");
      const _component_v_card = _resolveComponent$2("v-card");
      const _component_v_icon = _resolveComponent$2("v-icon");
      const _component_v_col = _resolveComponent$2("v-col");
      const _component_v_row = _resolveComponent$2("v-row");
      return _openBlock$2(), _createElementBlock$2("div", null, [
        _createVNode$2(_component_v_card, {
          variant: "outlined",
          class: "pa-3"
        }, {
          default: _withCtx$2(() => [
            _createElementVNode$2("div", _hoisted_1$2, [
              _createVNode$2(_component_v_avatar, {
                size: "64",
                rounded: "",
                class: "flex-shrink-0"
              }, {
                default: _withCtx$2(() => [
                  _createVNode$2(_component_v_img, {
                    src: _unref$2(proxyImage)(actor.value.profile),
                    cover: ""
                  }, null, 8, ["src"])
                ]),
                _: 1
              }),
              _createElementVNode$2("div", _hoisted_2$2, [
                _createElementVNode$2("div", _hoisted_3$2, [
                  _createTextVNode$2(_toDisplayString$2(actor.value.name || "（无姓名）") + " ", 1),
                  actor.value.actor_id ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_4$2, "actor:" + _toDisplayString$2(actor.value.actor_id), 1)) : _createCommentVNode$2("", true)
                ]),
                _createElementVNode$2("div", _hoisted_5$2, _toDisplayString$2(meta.value), 1),
                actor.value.bio ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_6$2, _toDisplayString$2(actor.value.bio), 1)) : _createCommentVNode$2("", true)
              ])
            ]),
            actor.value.coactors?.length ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_7$2, [
              _cache[1] || (_cache[1] = _createElementVNode$2("span", { class: "text-caption sdbs-dim mr-1" }, "常合作演员：", -1)),
              (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(actor.value.coactors.slice(0, 12), (co) => {
                return _openBlock$2(), _createBlock$2(_component_v_chip, {
                  key: co.id || co.name,
                  size: "x-small",
                  variant: "tonal",
                  class: "mr-1 mb-1"
                }, {
                  default: _withCtx$2(() => [
                    _createTextVNode$2(_toDisplayString$2(co.name), 1)
                  ]),
                  _: 2
                }, 1024);
              }), 128))
            ])) : _createCommentVNode$2("", true),
            _createElementVNode$2("div", _hoisted_8$2, [
              actor.value.url ? (_openBlock$2(), _createBlock$2(_component_v_btn, {
                key: 0,
                size: "x-small",
                variant: "tonal",
                href: actor.value.url,
                target: "_blank",
                rel: "noopener",
                "prepend-icon": "mdi-open-in-new"
              }, {
                default: _withCtx$2(() => [..._cache[2] || (_cache[2] = [
                  _createTextVNode$2(" 演员页 ", -1)
                ])]),
                _: 1
              }, 8, ["href"])) : _createCommentVNode$2("", true),
              _createVNode$2(_component_v_btn, {
                size: "x-small",
                variant: "text",
                onClick: _cache[0] || (_cache[0] = ($event) => rawOpen.value = !rawOpen.value)
              }, {
                default: _withCtx$2(() => [
                  _createTextVNode$2(_toDisplayString$2(rawOpen.value ? "收起原始数据" : "原始数据"), 1)
                ]),
                _: 1
              }),
              _createVNode$2(_component_v_spacer),
              __props.extra ? (_openBlock$2(), _createElementBlock$2("span", _hoisted_9$2, _toDisplayString$2(__props.extra), 1)) : _createCommentVNode$2("", true)
            ]),
            rawOpen.value ? (_openBlock$2(), _createElementBlock$2("pre", _hoisted_10$2, _toDisplayString$2(_unref$2(pretty)(actor.value)), 1)) : _createCommentVNode$2("", true)
          ]),
          _: 1
        }),
        _createElementVNode$2("div", _hoisted_11$2, [
          _createVNode$2(_component_v_icon, {
            icon: "mdi-movie-open-outline",
            size: "18",
            class: "mr-1"
          }),
          _cache[3] || (_cache[3] = _createTextVNode$2(" 全部作品 ", -1)),
          _createElementVNode$2("span", _hoisted_12$1, "共 " + _toDisplayString$2(works.value.length) + " 部", 1)
        ]),
        !works.value.length ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_13$1, "这位演员在这条记录里没有作品（多半是抓到的页面只有资料）。")) : _createCommentVNode$2("", true),
        _createVNode$2(_component_v_row, { dense: "" }, {
          default: _withCtx$2(() => [
            (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(works.value, (work, index) => {
              return _openBlock$2(), _createBlock$2(_component_v_col, {
                key: work.media_id || index,
                cols: "12",
                sm: __props.compact ? 12 : 6
              }, {
                default: _withCtx$2(() => [
                  _createVNode$2(_component_v_card, {
                    variant: "outlined",
                    class: "pa-2 h-100 d-flex flex-column"
                  }, {
                    default: _withCtx$2(() => [
                      _createElementVNode$2("div", _hoisted_14$1, [
                        _createVNode$2(_component_v_img, {
                          src: _unref$2(proxyImage)(work.poster),
                          width: "60",
                          height: "80",
                          "aspect-ratio": "2/3",
                          cover: "",
                          class: "rounded flex-shrink-0 sdbs-poster"
                        }, null, 8, ["src"]),
                        _createElementVNode$2("div", _hoisted_15$1, [
                          _createElementVNode$2("div", _hoisted_16$1, _toDisplayString$2(work.title || "（无标题）"), 1),
                          _createElementVNode$2("div", _hoisted_17$1, _toDisplayString$2(_unref$2(recordMeta)(workView(index)) || "—"), 1),
                          workTags(index, work).length ? (_openBlock$2(), _createElementBlock$2("div", _hoisted_18$1, [
                            (_openBlock$2(true), _createElementBlock$2(_Fragment$2, null, _renderList$2(workTags(index, work), (tag) => {
                              return _openBlock$2(), _createBlock$2(_component_v_chip, {
                                key: tag,
                                size: "x-small",
                                variant: "tonal",
                                class: "mr-1 mb-1"
                              }, {
                                default: _withCtx$2(() => [
                                  _createTextVNode$2(_toDisplayString$2(tag), 1)
                                ]),
                                _: 2
                              }, 1024);
                            }), 128))
                          ])) : _createCommentVNode$2("", true)
                        ])
                      ]),
                      _createVNode$2(_component_v_spacer),
                      _createElementVNode$2("div", _hoisted_19$1, [
                        work.url ? (_openBlock$2(), _createBlock$2(_component_v_btn, {
                          key: 0,
                          size: "x-small",
                          variant: "text",
                          href: work.url,
                          target: "_blank",
                          rel: "noopener"
                        }, {
                          default: _withCtx$2(() => [..._cache[4] || (_cache[4] = [
                            _createTextVNode$2(" 站点 ", -1)
                          ])]),
                          _: 1
                        }, 8, ["href"])) : _createCommentVNode$2("", true),
                        _createVNode$2(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          loading: workLoadingIndex.value === index,
                          disabled: workComplete(index, work),
                          title: workComplete(index, work) ? "已是作品页那份数据（完整标签 / 首播 / 版权方 / 时长 / 简介 / 剧照）" : "演员页卡片是摘要（标签只印 1~3 个、没有版权方），抓一次详情页补全",
                          onClick: ($event) => loadWorkDetail(index)
                        }, {
                          default: _withCtx$2(() => [
                            _createTextVNode$2(_toDisplayString$2(workComplete(index, work) ? "已补全" : "完整信息"), 1)
                          ]),
                          _: 2
                        }, 1032, ["loading", "disabled", "title", "onClick"]),
                        _createVNode$2(_component_v_spacer),
                        _createVNode$2(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          onClick: ($event) => toggleWorkRaw(index)
                        }, {
                          default: _withCtx$2(() => [
                            _createTextVNode$2(_toDisplayString$2(openWorks.value.has(index) ? "收起" : "原始数据"), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick"])
                      ]),
                      openWorks.value.has(index) ? (_openBlock$2(), _createElementBlock$2("pre", _hoisted_20$1, _toDisplayString$2(_unref$2(pretty)(workView(index))), 1)) : _createCommentVNode$2("", true)
                    ]),
                    _: 2
                  }, 1024)
                ]),
                _: 2
              }, 1032, ["sm"]);
            }), 128))
          ]),
          _: 1
        })
      ]);
    };
  }
});

const ActorCard = /* @__PURE__ */ _export_sfc(_sfc_main$2, [["__scopeId", "data-v-2dddb087"]]);

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {unref:_unref$1,resolveComponent:_resolveComponent$1,createVNode:_createVNode$1,toDisplayString:_toDisplayString$1,createElementVNode:_createElementVNode$1,renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$1,createElementBlock:_createElementBlock$1,createTextVNode:_createTextVNode$1,withCtx:_withCtx$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1} = await importShared('vue');

const _hoisted_1$1 = {
  class: "d-flex",
  style: { "gap": "12px" }
};
const _hoisted_2$1 = {
  class: "flex-grow-1",
  style: { "min-width": "0" }
};
const _hoisted_3$1 = { class: "text-subtitle-2" };
const _hoisted_4$1 = { class: "text-caption sdbs-dim mt-1" };
const _hoisted_5$1 = {
  key: 0,
  class: "mt-1"
};
const _hoisted_6$1 = {
  key: 1,
  class: "text-caption mt-2 sdbs-clamp"
};
const _hoisted_7$1 = {
  key: 2,
  class: "text-caption sdbs-dim mt-2"
};
const _hoisted_8$1 = {
  key: 3,
  class: "mt-2"
};
const _hoisted_9$1 = {
  class: "d-flex align-center mt-2 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_10$1 = {
  key: 1,
  class: "text-caption sdbs-dim"
};
const _hoisted_11$1 = {
  key: 0,
  class: "sdbs-pre mt-2"
};
const {computed: computed$1,ref: ref$1,watch: watch$1} = await importShared('vue');
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "RecordCard",
  props: {
    record: {},
    extra: {}
  },
  setup(__props) {
    const props = __props;
    const item = computed$1(() => props.record || {});
    const rawOpen = ref$1(false);
    const meta = computed$1(() => recordMeta(item.value, true));
    const cast = computed$1(() => castLine(item.value));
    watch$1(() => props.record, () => {
      rawOpen.value = false;
    });
    return (_ctx, _cache) => {
      const _component_v_img = _resolveComponent$1("v-img");
      const _component_v_chip = _resolveComponent$1("v-chip");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_spacer = _resolveComponent$1("v-spacer");
      const _component_v_card = _resolveComponent$1("v-card");
      return _openBlock$1(), _createBlock$1(_component_v_card, {
        variant: "outlined",
        class: "pa-3"
      }, {
        default: _withCtx$1(() => [
          _createElementVNode$1("div", _hoisted_1$1, [
            _createVNode$1(_component_v_img, {
              src: _unref$1(proxyImage)(item.value.poster),
              width: "92",
              height: "123",
              "aspect-ratio": "2/3",
              cover: "",
              class: "rounded flex-shrink-0 sdbs-poster"
            }, null, 8, ["src"]),
            _createElementVNode$1("div", _hoisted_2$1, [
              _createElementVNode$1("div", _hoisted_3$1, _toDisplayString$1(item.value.title || "（无标题）"), 1),
              _createElementVNode$1("div", _hoisted_4$1, _toDisplayString$1(meta.value), 1),
              item.value.tags?.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_5$1, [
                (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(item.value.tags, (tag) => {
                  return _openBlock$1(), _createBlock$1(_component_v_chip, {
                    key: tag,
                    size: "x-small",
                    variant: "tonal",
                    class: "mr-1 mb-1"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(tag), 1)
                    ]),
                    _: 2
                  }, 1024);
                }), 128))
              ])) : _createCommentVNode$1("", true),
              item.value.overview ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_6$1, _toDisplayString$1(item.value.overview), 1)) : _createCommentVNode$1("", true),
              cast.value ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_7$1, "主演：" + _toDisplayString$1(cast.value), 1)) : _createCommentVNode$1("", true),
              item.value.related?.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_8$1, [
                _cache[1] || (_cache[1] = _createElementVNode$1("span", { class: "text-caption sdbs-dim mr-1" }, "同页推荐：", -1)),
                (_openBlock$1(true), _createElementBlock$1(_Fragment$1, null, _renderList$1(item.value.related.slice(0, 8), (rel) => {
                  return _openBlock$1(), _createBlock$1(_component_v_chip, {
                    key: rel.media_id || rel.title,
                    size: "x-small",
                    variant: "tonal",
                    class: "mr-1 mb-1",
                    href: rel.url,
                    target: "_blank",
                    rel: "noopener"
                  }, {
                    default: _withCtx$1(() => [
                      _createTextVNode$1(_toDisplayString$1(rel.title), 1)
                    ]),
                    _: 2
                  }, 1032, ["href"]);
                }), 128))
              ])) : _createCommentVNode$1("", true)
            ])
          ]),
          _createElementVNode$1("div", _hoisted_9$1, [
            item.value.url ? (_openBlock$1(), _createBlock$1(_component_v_btn, {
              key: 0,
              size: "x-small",
              variant: "tonal",
              href: item.value.url,
              target: "_blank",
              rel: "noopener",
              "prepend-icon": "mdi-open-in-new"
            }, {
              default: _withCtx$1(() => [..._cache[2] || (_cache[2] = [
                _createTextVNode$1(" 站点页面 ", -1)
              ])]),
              _: 1
            }, 8, ["href"])) : _createCommentVNode$1("", true),
            _createVNode$1(_component_v_btn, {
              size: "x-small",
              variant: "text",
              onClick: _cache[0] || (_cache[0] = ($event) => rawOpen.value = !rawOpen.value)
            }, {
              default: _withCtx$1(() => [
                _createTextVNode$1(_toDisplayString$1(rawOpen.value ? "收起原始数据" : "原始数据"), 1)
              ]),
              _: 1
            }),
            _createVNode$1(_component_v_spacer),
            __props.extra ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_10$1, _toDisplayString$1(__props.extra), 1)) : _createCommentVNode$1("", true)
          ]),
          rawOpen.value ? (_openBlock$1(), _createElementBlock$1("pre", _hoisted_11$1, _toDisplayString$1(_unref$1(pretty)(item.value)), 1)) : _createCommentVNode$1("", true)
        ]),
        _: 1
      });
    };
  }
});

const RecordCard = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["__scopeId", "data-v-785a1084"]]);

const {defineComponent:_defineComponent} = await importShared('vue');

const {resolveComponent:_resolveComponent,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock,withKeys:_withKeys,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass,unref:_unref} = await importShared('vue');

const _hoisted_1 = {
  class: "d-flex align-center mb-3 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_2 = { class: "sdbs-duo" };
const _hoisted_3 = {
  class: "d-flex align-center flex-wrap pa-3 pb-2",
  style: { "gap": "8px" }
};
const _hoisted_4 = {
  key: 1,
  class: "text-caption sdbs-dim"
};
const _hoisted_5 = { class: "pa-3 pt-2 d-flex flex-column flex-grow-1" };
const _hoisted_6 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const _hoisted_7 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const _hoisted_8 = { class: "sdbs-scroll" };
const _hoisted_9 = { class: "d-flex align-center py-1" };
const _hoisted_10 = ["title", "onClick"];
const _hoisted_11 = { class: "text-caption sdbs-dim ml-1" };
const _hoisted_12 = {
  key: 0,
  class: "text-caption sdbs-dim mr-2",
  title: "「命中词」＝搜这个词时发现的它；键／标题／命中词任何一个都能把它查回来"
};
const _hoisted_13 = {
  key: 0,
  class: "sdbs-expand mb-2"
};
const _hoisted_14 = { class: "text-caption sdbs-dim mb-1" };
const _hoisted_15 = {
  key: 0,
  class: "d-flex align-center py-2"
};
const _hoisted_16 = {
  class: "d-flex align-center flex-wrap pa-3 pb-2",
  style: { "gap": "8px" }
};
const _hoisted_17 = {
  key: 1,
  class: "text-caption sdbs-dim"
};
const _hoisted_18 = { class: "pa-3 pt-2 d-flex flex-column flex-grow-1" };
const _hoisted_19 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const _hoisted_20 = { class: "text-caption sdbs-dim mb-2" };
const _hoisted_21 = {
  key: 2,
  class: "text-caption sdbs-dim mb-2"
};
const _hoisted_22 = {
  class: "d-flex align-center flex-wrap mb-2",
  style: { "gap": "8px" }
};
const _hoisted_23 = { class: "sdbs-scroll" };
const _hoisted_24 = ["title", "onClick"];
const _hoisted_25 = {
  key: 1,
  class: "text-caption sdbs-dim mr-2"
};
const _hoisted_26 = { class: "text-caption sdbs-dim mr-2" };
const _hoisted_27 = {
  key: 0,
  class: "sdbs-expand mb-2"
};
const _hoisted_28 = { class: "text-caption sdbs-dim mb-1" };
const _hoisted_29 = {
  key: 0,
  class: "d-flex align-center py-2"
};
const _hoisted_30 = {
  key: 0,
  class: "text-caption sdbs-dim mb-2"
};
const _hoisted_31 = {
  class: "d-flex align-center mb-1 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_32 = {
  key: 3,
  class: "sdbs-pre"
};
const _hoisted_33 = {
  key: 5,
  class: "text-caption sdbs-dim mt-1"
};
const _hoisted_34 = {
  class: "d-flex align-center mt-2 flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_35 = {
  key: 0,
  class: "text-caption sdbs-dim"
};
const _hoisted_36 = { class: "d-flex align-center mb-2" };
const _hoisted_37 = { class: "text-caption sdbs-dim mb-1" };
const _hoisted_38 = { class: "text-body-2 flex-grow-1" };
const _hoisted_39 = {
  key: 1,
  class: "mt-3"
};
const _hoisted_40 = { class: "d-flex align-center mb-2" };
const _hoisted_41 = { class: "text-caption sdbs-dim mb-1" };
const _hoisted_42 = { class: "text-body-2 flex-grow-1" };
const _hoisted_43 = { class: "text-caption sdbs-dim mr-2" };
const _hoisted_44 = {
  key: 1,
  class: "mt-3"
};
const {computed,ref,watch} = await importShared('vue');
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
    const titleLoadingId = ref("");
    const actorCandidates = ref([]);
    const actorProfile = ref(null);
    const actorMessage = ref("");
    const actorLoadingId = ref("");
    const libraryLoading = ref(false);
    const libraryKeyword = ref("");
    const libraryKind = ref("all");
    const libraryRecords = ref([]);
    const libraryStats = ref("");
    const libraryStatsRaw = ref({});
    const libraryNotice = ref("");
    const libraryClearOpen = ref(false);
    const libraryClearing = ref(false);
    const libraryEmptyText = ref("库里还没有记录 —— 先在上面的搜索框搜一次片名或演员名。");
    const cacheLoading = ref(false);
    const cacheKeyword = ref("");
    const cacheKind = ref("all");
    const cacheEntries = ref([]);
    const cacheStatus = ref(null);
    const cacheNotice = ref("");
    const cacheClearOpen = ref(false);
    const cacheClearing = ref(false);
    const cacheDeleting = ref("");
    const cacheEmptyText = ref("缓存还是空的 —— 搜一次片名或演员名就会写入。");
    const cacheShown = ref(0);
    const cacheOpenKey = ref("");
    const cacheOpenData = ref({});
    const cacheOpenLoading = ref("");
    const cacheRawOpen = ref(false);
    const libraryOpenKey = ref("");
    const libraryOpenData = ref({});
    const libraryOpenLoading = ref("");
    const cacheChip = computed(() => {
      const cache = status.value?.cache;
      if (!cache) return "";
      return `${cache.count ?? cache.detail ?? 0} 条`;
    });
    const storeChip = computed(() => {
      const store = status.value?.store;
      if (!store?.total) return "";
      return `${store.total} 条`;
    });
    const hasTitlePanel = computed(
      () => Boolean(titleCandidates.value.length || titleRecord.value || titleMessage.value)
    );
    const hasActorPanel = computed(
      () => Boolean(actorCandidates.value.length || actorProfile.value || actorMessage.value)
    );
    const hasResult = computed(() => hasTitlePanel.value || hasActorPanel.value);
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
      titleLoadingId.value = "";
    }
    function resetActor() {
      actorCandidates.value = [];
      actorProfile.value = null;
      actorMessage.value = "";
      actorLoadingId.value = "";
    }
    async function pickActor(candidate) {
      const api = resolveApi(props);
      if (!api || !candidate.actor_id) return;
      actorLoadingId.value = candidate.actor_id;
      actorMessage.value = "";
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
    async function loadLibrary() {
      const api = resolveApi(props);
      if (!api) return;
      libraryLoading.value = true;
      libraryNotice.value = "";
      try {
        const query = libraryKeyword.value.trim();
        const report = await fetchUrls(api, {
          keyword: query,
          kind: libraryKind.value === "all" ? "" : libraryKind.value
        });
        if (!report?.success) {
          libraryRecords.value = [];
          libraryStats.value = "";
          libraryStatsRaw.value = {};
          libraryEmptyText.value = report?.message || "URL 库暂时读不出来（插件数据库未就绪？）";
          return;
        }
        libraryRecords.value = report.records || [];
        libraryOpenKey.value = "";
        libraryOpenData.value = {};
        libraryOpenLoading.value = "";
        const stats = report.stats || {};
        libraryStatsRaw.value = stats;
        libraryStats.value = `作品 ${stats.work ?? 0} / 演员 ${stats.actor ?? 0}｜关键词 ${stats.keywords ?? 0} 个`;
        libraryEmptyText.value = query ? `库里没有「${query}」——换个完整片名或演员全名，或先在上面的搜索框搜一次。` : "库里还没有记录 —— 先在上面的搜索框搜一次片名或演员名。";
      } finally {
        libraryLoading.value = false;
      }
    }
    function rowKeyInfo(row) {
      const key = String(row.keyword || "");
      const name = String(row.label || "");
      const trigger = String(row.display || "");
      const parts = [];
      if (key && key !== name) parts.push(`键 ${key}`);
      if (trigger && trigger !== key && trigger !== name) parts.push(`命中词 ${trigger}`);
      return parts.join("｜");
    }
    const libraryClearScope = computed(() => {
      const query = libraryKeyword.value.trim();
      const stats = libraryStatsRaw.value || {};
      if (query) return `「${query}」相关的记录`;
      if (libraryKind.value === "actor") return `全部 ${stats.actor ?? 0} 条演员记录`;
      if (libraryKind.value === "work") return `全部 ${stats.work ?? 0} 条作品记录`;
      return `整库 ${stats.total ?? 0} 条记录`;
    });
    async function clearLibrary() {
      const api = resolveApi(props);
      if (!api) return;
      libraryClearing.value = true;
      try {
        const report = await clearUrls(api, {
          keyword: libraryKeyword.value.trim(),
          kind: libraryKind.value === "all" ? "" : libraryKind.value
        });
        libraryClearOpen.value = false;
        if (!report?.success) {
          libraryEmptyText.value = report?.message || "清库失败（后端没有响应）";
          return;
        }
        await loadLibrary();
        libraryNotice.value = `${report.message || "已清空"}；再搜一次就会重新发现。`;
      } finally {
        libraryClearing.value = false;
      }
    }
    watch(libraryKind, () => {
      void loadLibrary();
    });
    const cacheWhere = computed(() => cacheStatus.value || status.value?.cache || {});
    const cacheSummary = computed(() => {
      const where = cacheWhere.value;
      const kinds = where.kinds || {};
      const total = where.count ?? 0;
      if (!total) return "";
      const parts = [`作品 ${kinds.detail ?? 0}`, `演员 ${kinds.actor ?? 0}`];
      if (kinds.tmdb) parts.push(`TMDB ${kinds.tmdb}`);
      return parts.join(" / ");
    });
    const cacheTotal = computed(() => Number(cacheWhere.value.count ?? 0));
    const cacheMoreText = computed(() => {
      const total = cacheTotal.value;
      const shown = cacheShown.value;
      if (!total || !shown || shown >= total) return "";
      return `列表按写入时间倒序显示 ${shown} 条（共 ${total} 条）—— 用上面的框按片名 / 演员名 / 站点 ID 过滤。`;
    });
    const cacheTtlText = computed(() => {
      const ttl = Number(cacheWhere.value.ttl || 0);
      if (!ttl) return "未生效";
      if (ttl < 3600) return `${ttl} 秒`;
      const hours = ttl / 3600;
      return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} 小时`;
    });
    const cacheTtlSource = computed(() => {
      const where = cacheWhere.value;
      if (where.disabled) return `插件配置关闭（cache_ttl = ${where.override_ttl ?? -1}）`;
      const meta = Number(where.system?.meta_expire_hours || 0);
      if (where.ttl_source === "plugin") return `插件配置覆盖（${where.override_ttl ?? 0} 秒）`;
      if (where.ttl_source === "system") return `系统设置「缓存有效期」= ${meta} 小时`;
      return "系统自动（未设有效期：普通 24 小时 / 大内存 72 小时）";
    });
    const cacheClearScope = computed(() => {
      if (!cacheWhere.value.blocked && cacheKind.value !== "all") {
        const label = cacheWhere.value.kind_labels?.[cacheKind.value] || cacheKind.value;
        return `全部「${label}」缓存`;
      }
      return `本插件的全部缓存（${cacheWhere.value.count ?? 0} 条）`;
    });
    function cacheKindColor(kind) {
      if (kind === "actor") return "purple";
      if (kind === "tmdb") return "teal";
      return "primary";
    }
    function cacheTime(ts) {
      if (!ts) return "";
      const date = new Date(ts * 1e3);
      if (Number.isNaN(date.getTime())) return "";
      const pad = (value) => String(value).padStart(2, "0");
      return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }
    async function loadCache() {
      const api = resolveApi(props);
      if (!api) return;
      cacheLoading.value = true;
      cacheNotice.value = "";
      try {
        const query = cacheKeyword.value.trim();
        const report = await fetchCache(api, {
          keyword: query,
          kind: cacheKind.value === "all" ? "" : cacheKind.value
        });
        if (!report?.success) {
          cacheEntries.value = [];
          cacheShown.value = 0;
          cacheEmptyText.value = report?.message || "缓存读不出来（宿主缓存后端未就绪？）";
          return;
        }
        cacheEntries.value = report.data || [];
        cacheShown.value = Number(report.returned ?? cacheEntries.value.length);
        cacheOpenKey.value = "";
        cacheOpenData.value = {};
        cacheOpenLoading.value = "";
        cacheStatus.value = report.cache || null;
        cacheEmptyText.value = query ? `缓存里没有「${query}」——换个完整片名 / 演员名，或站点 ID 试试。` : "缓存还是空的 —— 搜一次片名或演员名就会写入。";
      } finally {
        cacheLoading.value = false;
      }
    }
    async function deleteCacheRow(key) {
      if (!key) return;
      const api = resolveApi(props);
      if (!api) return;
      cacheDeleting.value = key;
      try {
        const report = await deleteCacheEntry(api, key);
        if (!report?.success) {
          cacheNotice.value = report?.message || "删除失败（后端没有响应）";
          return;
        }
        await loadCache();
        cacheNotice.value = report.message || "已删除";
        void load();
      } finally {
        cacheDeleting.value = "";
      }
    }
    async function clearCacheAll() {
      const api = resolveApi(props);
      if (!api) return;
      cacheClearing.value = true;
      try {
        const report = await clearCache(api, cacheKind.value === "all" ? "" : cacheKind.value);
        cacheClearOpen.value = false;
        if (!report?.success) {
          cacheEmptyText.value = report?.message || "清空失败（后端没有响应）";
          return;
        }
        await loadCache();
        cacheNotice.value = report.message || "已清空";
        void load();
      } finally {
        cacheClearing.value = false;
      }
    }
    function rowsOf(row) {
      return [row, ...row.attached || []];
    }
    function rowId(row) {
      return `${row.kind || ""}:${row.native_id || row.url || ""}`;
    }
    const cacheExpanded = computed(() => {
      const key = cacheOpenKey.value;
      if (!key) return null;
      const payload = cacheOpenData.value[key] || null;
      return {
        key,
        loading: cacheOpenLoading.value === key,
        payload,
        record: payload?.record || null,
        actor: payload?.actor || null,
        message: payload && payload.success === false ? payload.message || "这条缓存读不出来" : ""
      };
    });
    const libraryExpanded = computed(() => {
      const id = libraryOpenKey.value;
      if (!id) return null;
      const data = libraryOpenData.value[id];
      return {
        id,
        loading: libraryOpenLoading.value === id,
        record: data?.record || null,
        actor: data?.actor || null,
        message: data?.error || ""
      };
    });
    async function toggleCacheRow(row) {
      const key = String(row.key || "");
      if (!key) return;
      if (cacheOpenKey.value === key) {
        cacheOpenKey.value = "";
        return;
      }
      cacheOpenKey.value = key;
      cacheRawOpen.value = false;
      if (cacheOpenData.value[key]) return;
      const api = resolveApi(props);
      if (!api) return;
      cacheOpenLoading.value = key;
      try {
        const report = await fetchCacheEntry(api, key);
        cacheOpenData.value = {
          ...cacheOpenData.value,
          [key]: report || { success: false, message: "读不出这条缓存（接口没有响应）" }
        };
      } finally {
        cacheOpenLoading.value = "";
      }
    }
    async function toggleLibraryRow(row) {
      const id = rowId(row);
      if (libraryOpenKey.value === id) {
        libraryOpenKey.value = "";
        return;
      }
      libraryOpenKey.value = id;
      if (libraryOpenData.value[id]) return;
      const api = resolveApi(props);
      if (!api) return;
      const nativeId = String(row.native_id || "");
      if (!nativeId) {
        libraryOpenData.value = {
          ...libraryOpenData.value,
          [id]: { error: "这条记录没有站点 ID（老记录，或页面标题里没带），只能点「打开」去站点看。" }
        };
        return;
      }
      libraryOpenLoading.value = id;
      try {
        if (row.kind === "actor") {
          const report = await fetchActor(api, { actor_id: nativeId });
          libraryOpenData.value = {
            ...libraryOpenData.value,
            [id]: report?.success && report.actor ? { actor: report.actor } : { error: report?.message || "抓演员页失败（多半是站点风控，稍后再试）" }
          };
        } else {
          const report = await recognizeTitle(api, { media_id: nativeId });
          libraryOpenData.value = {
            ...libraryOpenData.value,
            [id]: report?.success && report.record ? { record: report.record } : { error: report?.message || "抓作品页失败（多半是站点风控，稍后再试）" }
          };
        }
      } finally {
        libraryOpenLoading.value = "";
      }
    }
    function libraryMetaLine(row) {
      const parts = [];
      if (row.keyword && row.label && row.keyword !== row.label) parts.push(`键 ${row.keyword}`);
      const origin = row.origin === "page" ? "页面顺带发现" : "引擎发现";
      parts.push(row.backend ? `${origin}（${row.backend}）` : origin);
      if (row.native_id) parts.push(`${row.kind === "actor" ? "actor" : "work"}:${row.native_id}`);
      if (row.hits && row.hits > 1) parts.push(`用过 ${row.hits} 次`);
      const seen = cacheTime(row.last_used_at || row.first_seen_at);
      if (seen) parts.push(`最近 ${seen}`);
      return parts.join(" ｜ ");
    }
    function cacheMetaLine(row) {
      const parts = [String(row.key || "")];
      const at = cacheTime(row.cached_at);
      if (at) parts.push(`写入 ${at}`);
      if (row.kind_label || row.kind) parts.push(String(row.kind_label || row.kind));
      return parts.join(" ｜ ");
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
    void loadLibrary();
    void loadCache();
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_switch = _resolveComponent("v-switch");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_progress_circular = _resolveComponent("v-progress-circular");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_card_actions = _resolveComponent("v-card-actions");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_dialog = _resolveComponent("v-dialog");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      return _openBlock(), _createElementBlock("div", {
        class: _normalizeClass(["sdbs-root", props.full ? "pa-4" : "pa-2"])
      }, [
        _createElementVNode("div", _hoisted_1, [
          _createVNode(_component_v_icon, {
            icon: "mdi-television-classic",
            class: "mr-1"
          }),
          _cache[27] || (_cache[27] = _createElementVNode("h2", { class: "text-h6 ma-0" }, "短剧百科数据源", -1)),
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
          _createVNode(_component_v_spacer),
          props.full ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 0,
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
            default: _withCtx(() => [..._cache[26] || (_cache[26] = [
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
          default: _withCtx(() => [..._cache[28] || (_cache[28] = [
            _createTextVNode(" 短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器建不起媒体身份 —— 本插件补的就是这一段。 搜索框", -1),
            _createElementVNode("b", null, "片名与演员名都收", -1),
            _createTextVNode("：一次检索同时给出「作品」与「演员」两块结果，哪边命中就显示哪边 （两边都命中就并排显示）。搜到的页面 URL 会存进", -1),
            _createElementVNode("b", null, "插件自有数据库", -1),
            _createTextVNode("（URL 库），下次同一个词 直接查库、零引擎请求；卡片上的「原始数据」可以看到插件解析出的完整字段。 ", -1)
          ])]),
          _: 1
        }),
        _createElementVNode("div", _hoisted_2, [
          _createVNode(_component_v_card, {
            variant: "outlined",
            class: "sdbs-panel sdbs-col"
          }, {
            default: _withCtx(() => [
              _createElementVNode("div", _hoisted_3, [
                _createVNode(_component_v_icon, {
                  icon: "mdi-database-outline",
                  size: "18"
                }),
                _cache[29] || (_cache[29] = _createElementVNode("span", { class: "text-subtitle-2" }, "URL 库", -1)),
                storeChip.value ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 0,
                  size: "x-small",
                  variant: "tonal",
                  color: "teal"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(storeChip.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createVNode(_component_v_spacer),
                libraryStats.value ? (_openBlock(), _createElementBlock("span", _hoisted_4, _toDisplayString(libraryStats.value), 1)) : _createCommentVNode("", true)
              ]),
              _createVNode(_component_v_divider),
              _createElementVNode("div", _hoisted_5, [
                _createElementVNode("div", _hoisted_6, [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    loading: libraryLoading.value,
                    "prepend-icon": "mdi-refresh",
                    onClick: _cache[3] || (_cache[3] = ($event) => loadLibrary())
                  }, {
                    default: _withCtx(() => [..._cache[30] || (_cache[30] = [
                      _createTextVNode(" 刷新 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    color: "error",
                    "prepend-icon": "mdi-delete-sweep-outline",
                    disabled: libraryLoading.value || libraryClearing.value,
                    onClick: _cache[4] || (_cache[4] = ($event) => libraryClearOpen.value = true)
                  }, {
                    default: _withCtx(() => [..._cache[31] || (_cache[31] = [
                      _createTextVNode(" 清空库 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: libraryKind.value,
                    "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => libraryKind.value = $event),
                    density: "compact",
                    variant: "outlined",
                    divided: "",
                    mandatory: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "all"
                      }, {
                        default: _withCtx(() => [..._cache[32] || (_cache[32] = [
                          _createTextVNode("全部", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "work"
                      }, {
                        default: _withCtx(() => [..._cache[33] || (_cache[33] = [
                          _createTextVNode("作品", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "actor"
                      }, {
                        default: _withCtx(() => [..._cache[34] || (_cache[34] = [
                          _createTextVNode("演员", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _cache[38] || (_cache[38] = _createElementVNode("div", { class: "text-caption sdbs-dim mb-2" }, [
                  _createTextVNode(" 库里只存「页面 URL」：命中就直接抓页面（"),
                  _createElementVNode("b", null, "零引擎请求"),
                  _createTextVNode("），解析结果不落库 —— 站点内容随时在变，页面永远实时解析。"),
                  _createElementVNode("b", null, "一个页面只占一条记录"),
                  _createTextVNode("（同一个 ID 走了两条 发现路径被写成多行时会自动合并），每条按"),
                  _createElementVNode("b", null, "它自己的名字"),
                  _createTextVNode("建档；右边标出「命中词」， 告诉你它是搜哪个词时被带出来的。解析作品页时顺带把演员链接写进库，所以搜过一部剧， 之后再搜它里面的演员名也能命中。 ")
                ], -1)),
                libraryNotice.value ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 0,
                  type: "success",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(libraryNotice.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_7, [
                  _createVNode(_component_v_text_field, {
                    modelValue: libraryKeyword.value,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => libraryKeyword.value = $event),
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    clearable: "",
                    "prepend-inner-icon": "mdi-magnify",
                    placeholder: "按关键词精确查（留空＝最近入库）",
                    class: "sdbs-lib-search",
                    onKeyup: _cache[7] || (_cache[7] = _withKeys(($event) => loadLibrary(), ["enter"]))
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    variant: "tonal",
                    color: "primary",
                    loading: libraryLoading.value,
                    onClick: _cache[8] || (_cache[8] = ($event) => loadLibrary())
                  }, {
                    default: _withCtx(() => [..._cache[35] || (_cache[35] = [
                      _createTextVNode(" 查询 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"])
                ]),
                !libraryRecords.value.length ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 1,
                  type: "info",
                  variant: "tonal",
                  density: "compact"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(libraryEmptyText.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_8, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(libraryRecords.value, (row) => {
                    return _openBlock(), _createElementBlock("div", {
                      key: `${row.kind}:${row.url}`
                    }, [
                      _createElementVNode("div", _hoisted_9, [
                        _createVNode(_component_v_chip, {
                          size: "x-small",
                          variant: "tonal",
                          color: row.kind === "actor" ? "purple" : "primary",
                          class: "mr-2"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(row.kind === "actor" ? "演员" : "作品"), 1)
                          ]),
                          _: 2
                        }, 1032, ["color"]),
                        _createElementVNode("span", {
                          class: "text-body-2 flex-grow-1 sdbs-lib-text sdbs-clickable",
                          title: `点一下在下方展开${row.kind === "actor" ? "这位演员" : "这部作品"}的内容`,
                          onClick: ($event) => toggleLibraryRow(row)
                        }, [
                          _createTextVNode(_toDisplayString(row.label || row.keyword || row.display) + " ", 1),
                          _createElementVNode("span", _hoisted_11, _toDisplayString(row.origin === "page" ? "页面顺带" : "引擎"), 1)
                        ], 8, _hoisted_10),
                        rowKeyInfo(row) ? (_openBlock(), _createElementBlock("span", _hoisted_12, _toDisplayString(rowKeyInfo(row)), 1)) : _createCommentVNode("", true),
                        row.url ? (_openBlock(), _createBlock(_component_v_btn, {
                          key: 1,
                          size: "x-small",
                          variant: "text",
                          href: row.url,
                          target: "_blank",
                          rel: "noopener"
                        }, {
                          default: _withCtx(() => [..._cache[36] || (_cache[36] = [
                            _createTextVNode(" 打开 ", -1)
                          ])]),
                          _: 1
                        }, 8, ["href"])) : _createCommentVNode("", true),
                        _createVNode(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          icon: libraryOpenKey.value === rowId(row) ? "mdi-chevron-up" : "mdi-chevron-down",
                          title: libraryOpenKey.value === rowId(row) ? "收起" : "展开这条记录的内容",
                          onClick: ($event) => toggleLibraryRow(row)
                        }, null, 8, ["icon", "title", "onClick"])
                      ]),
                      libraryExpanded.value && libraryExpanded.value.id === rowId(row) ? (_openBlock(), _createElementBlock("div", _hoisted_13, [
                        _createElementVNode("div", _hoisted_14, _toDisplayString(libraryMetaLine(row)), 1),
                        libraryExpanded.value.loading ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
                          _createVNode(_component_v_progress_circular, {
                            size: "16",
                            width: "2",
                            indeterminate: "",
                            class: "mr-2"
                          }),
                          _cache[37] || (_cache[37] = _createElementVNode("span", { class: "text-caption sdbs-dim" }, "正在抓页面（首次约 1~3 秒，抓到即进缓存）…", -1))
                        ])) : libraryExpanded.value.record ? (_openBlock(), _createBlock(RecordCard, {
                          key: 1,
                          record: libraryExpanded.value.record,
                          api: props.api,
                          extra: `URL 库 · ${row.origin === "page" ? "页面顺带" : "引擎"}`
                        }, null, 8, ["record", "api", "extra"])) : libraryExpanded.value.actor ? (_openBlock(), _createBlock(ActorCard, {
                          key: 2,
                          profile: libraryExpanded.value.actor,
                          api: props.api,
                          compact: ""
                        }, null, 8, ["profile", "api"])) : libraryExpanded.value.message ? (_openBlock(), _createBlock(_component_v_alert, {
                          key: 3,
                          type: "warning",
                          variant: "tonal",
                          density: "compact"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(libraryExpanded.value.message), 1)
                          ]),
                          _: 1
                        })) : _createCommentVNode("", true)
                      ])) : _createCommentVNode("", true)
                    ]);
                  }), 128))
                ])
              ]),
              _createVNode(_component_v_dialog, {
                modelValue: libraryClearOpen.value,
                "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => libraryClearOpen.value = $event),
                "max-width": "440"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, null, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_card_title, { class: "text-subtitle-2 pt-3" }, {
                        default: _withCtx(() => [..._cache[39] || (_cache[39] = [
                          _createTextVNode("清空 URL 库", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_card_text, { class: "text-body-2" }, {
                        default: _withCtx(() => [
                          _cache[40] || (_cache[40] = _createTextVNode(" 将要删除：", -1)),
                          _createElementVNode("b", null, _toDisplayString(libraryClearScope.value), 1),
                          _cache[41] || (_cache[41] = _createTextVNode("。 ", -1)),
                          _cache[42] || (_cache[42] = _createElementVNode("br", null, null, -1)),
                          _cache[43] || (_cache[43] = _createTextVNode(" 库里只存「页面 URL」，清掉之后下次搜索会重新问一遍搜索引擎 —— 引擎有最小间隔、召回也不稳，认得出的词会更少。确认要清吗？ ", -1))
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_card_actions, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_spacer),
                          _createVNode(_component_v_btn, {
                            size: "small",
                            variant: "text",
                            onClick: _cache[9] || (_cache[9] = ($event) => libraryClearOpen.value = false)
                          }, {
                            default: _withCtx(() => [..._cache[44] || (_cache[44] = [
                              _createTextVNode("取消", -1)
                            ])]),
                            _: 1
                          }),
                          _createVNode(_component_v_btn, {
                            size: "small",
                            variant: "tonal",
                            color: "error",
                            loading: libraryClearing.value,
                            onClick: _cache[10] || (_cache[10] = ($event) => clearLibrary())
                          }, {
                            default: _withCtx(() => [..._cache[45] || (_cache[45] = [
                              _createTextVNode(" 确认清空 ", -1)
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
              }, 8, ["modelValue"])
            ]),
            _: 1
          }),
          _createVNode(_component_v_card, {
            variant: "outlined",
            class: "sdbs-panel sdbs-col"
          }, {
            default: _withCtx(() => [
              _createElementVNode("div", _hoisted_16, [
                _createVNode(_component_v_icon, {
                  icon: "mdi-cached",
                  size: "18"
                }),
                _cache[46] || (_cache[46] = _createElementVNode("span", { class: "text-subtitle-2" }, "缓存管理", -1)),
                cacheChip.value ? (_openBlock(), _createBlock(_component_v_chip, {
                  key: 0,
                  size: "x-small",
                  variant: "tonal",
                  color: "secondary"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(cacheChip.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createVNode(_component_v_spacer),
                cacheSummary.value ? (_openBlock(), _createElementBlock("span", _hoisted_17, _toDisplayString(cacheSummary.value), 1)) : _createCommentVNode("", true)
              ]),
              _createVNode(_component_v_divider),
              _createElementVNode("div", _hoisted_18, [
                _createElementVNode("div", _hoisted_19, [
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    loading: cacheLoading.value,
                    "prepend-icon": "mdi-refresh",
                    onClick: _cache[12] || (_cache[12] = ($event) => loadCache())
                  }, {
                    default: _withCtx(() => [..._cache[47] || (_cache[47] = [
                      _createTextVNode(" 刷新 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"]),
                  _createVNode(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    color: "error",
                    "prepend-icon": "mdi-delete-sweep-outline",
                    disabled: cacheLoading.value || cacheClearing.value || !cacheTotal.value,
                    onClick: _cache[13] || (_cache[13] = ($event) => cacheClearOpen.value = true)
                  }, {
                    default: _withCtx(() => [..._cache[48] || (_cache[48] = [
                      _createTextVNode(" 清空缓存 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled"]),
                  _createVNode(_component_v_spacer),
                  _createVNode(_component_v_btn_toggle, {
                    modelValue: cacheKind.value,
                    "onUpdate:modelValue": [
                      _cache[14] || (_cache[14] = ($event) => cacheKind.value = $event),
                      _cache[15] || (_cache[15] = ($event) => loadCache())
                    ],
                    density: "compact",
                    variant: "outlined",
                    divided: "",
                    mandatory: ""
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "all"
                      }, {
                        default: _withCtx(() => [..._cache[49] || (_cache[49] = [
                          _createTextVNode("全部", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "detail"
                      }, {
                        default: _withCtx(() => [..._cache[50] || (_cache[50] = [
                          _createTextVNode("作品详情", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "actor"
                      }, {
                        default: _withCtx(() => [..._cache[51] || (_cache[51] = [
                          _createTextVNode("演员档案", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_btn, {
                        size: "small",
                        value: "tmdb"
                      }, {
                        default: _withCtx(() => [..._cache[52] || (_cache[52] = [
                          _createTextVNode("TMDB 身份", -1)
                        ])]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }, 8, ["modelValue"])
                ]),
                _createElementVNode("div", _hoisted_20, [
                  _cache[53] || (_cache[53] = _createTextVNode(" 解析结果的缓存：", -1)),
                  _cache[54] || (_cache[54] = _createElementVNode("b", null, "作品详情", -1)),
                  _cache[55] || (_cache[55] = _createTextVNode("、", -1)),
                  _cache[56] || (_cache[56] = _createElementVNode("b", null, "演员档案", -1)),
                  _cache[57] || (_cache[57] = _createTextVNode("与 ", -1)),
                  _cache[58] || (_cache[58] = _createElementVNode("b", null, "TMDB 身份", -1)),
                  _cache[59] || (_cache[59] = _createTextVNode("各一条。 缓存的后端与有效期", -1)),
                  _cache[60] || (_cache[60] = _createElementVNode("b", null, "跟着宿主走", -1)),
                  _cache[61] || (_cache[61] = _createTextVNode("（系统设置 → 缓存）—— 启用 Redis 时与宿主共用同一个实例（本插件独占 ", -1)),
                  _createElementVNode("code", null, _toDisplayString(cacheWhere.value.region), 1),
                  _cache[62] || (_cache[62] = _createTextVNode(" 区），否则落在进程内内存。 ", -1))
                ]),
                cacheWhere.value.blocked ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2"
                }, {
                  default: _withCtx(() => [
                    _cache[63] || (_cache[63] = _createTextVNode(" 站点命中系统「不缓存站点」配置（", -1)),
                    _createElementVNode("code", null, _toDisplayString(cacheWhere.value.system?.no_cache_site_key), 1),
                    _cache[64] || (_cache[64] = _createTextVNode("） —— 本插件已按系统口径", -1)),
                    _cache[65] || (_cache[65] = _createElementVNode("b", null, "停用缓存", -1)),
                    _cache[66] || (_cache[66] = _createTextVNode("，每次解析都会重新抓页面。 ", -1))
                  ]),
                  _: 1
                })) : cacheWhere.value.disabled ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 1,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2"
                }, {
                  default: _withCtx(() => [
                    _cache[67] || (_cache[67] = _createTextVNode(" 插件配置里把缓存有效期设成了 ", -1)),
                    _createElementVNode("b", null, _toDisplayString(cacheWhere.value.override_ttl), 1),
                    _cache[68] || (_cache[68] = _createTextVNode("（负数即", -1)),
                    _cache[69] || (_cache[69] = _createElementVNode("b", null, "关闭插件缓存", -1)),
                    _cache[70] || (_cache[70] = _createTextVNode("） —— 每次解析都会重新抓页面。想恢复跟随系统，把「设置 → 站点与请求 → 缓存覆盖」改回 0。 ", -1))
                  ]),
                  _: 1
                })) : (_openBlock(), _createElementBlock("div", _hoisted_21, [
                  _cache[71] || (_cache[71] = _createTextVNode(" 当前：后端 ", -1)),
                  _createElementVNode("b", null, _toDisplayString(cacheWhere.value.backend), 1),
                  _cache[72] || (_cache[72] = _createTextVNode("｜有效期 ", -1)),
                  _createElementVNode("b", null, _toDisplayString(cacheTtlText.value), 1),
                  _createTextVNode(" （" + _toDisplayString(cacheTtlSource.value) + "）｜图片缓存 ", 1),
                  _createElementVNode("b", null, _toDisplayString(cacheWhere.value.system?.image_cache ? "开" : "关"), 1),
                  _createTextVNode(" （系统「全局图片缓存」" + _toDisplayString(cacheWhere.value.system?.image_cache_days ?? 7) + " 天） ", 1)
                ])),
                cacheNotice.value ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 3,
                  type: "success",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-2"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(cacheNotice.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_22, [
                  _createVNode(_component_v_text_field, {
                    modelValue: cacheKeyword.value,
                    "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => cacheKeyword.value = $event),
                    density: "compact",
                    variant: "outlined",
                    "hide-details": "",
                    clearable: "",
                    "prepend-inner-icon": "mdi-magnify",
                    placeholder: "按片名 / 演员名 / 站点 ID 过滤",
                    class: "sdbs-lib-search",
                    onKeyup: _cache[17] || (_cache[17] = _withKeys(($event) => loadCache(), ["enter"]))
                  }, null, 8, ["modelValue"]),
                  _createVNode(_component_v_btn, {
                    size: "small",
                    variant: "tonal",
                    color: "primary",
                    loading: cacheLoading.value,
                    onClick: _cache[18] || (_cache[18] = ($event) => loadCache())
                  }, {
                    default: _withCtx(() => [..._cache[73] || (_cache[73] = [
                      _createTextVNode(" 查询 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["loading"])
                ]),
                !cacheEntries.value.length ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 4,
                  type: "info",
                  variant: "tonal",
                  density: "compact"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(cacheEmptyText.value), 1)
                  ]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_23, [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cacheEntries.value, (row) => {
                    return _openBlock(), _createElementBlock("div", {
                      key: row.key
                    }, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(rowsOf(row), (item, position) => {
                        return _openBlock(), _createElementBlock("div", {
                          key: item.key
                        }, [
                          _createElementVNode("div", {
                            class: _normalizeClass(["d-flex align-center py-1", { "sdbs-attached": position > 0 }])
                          }, [
                            position > 0 ? (_openBlock(), _createBlock(_component_v_icon, {
                              key: 0,
                              icon: "mdi-subdirectory-arrow-right",
                              size: "14",
                              class: "mr-1 sdbs-dim"
                            })) : _createCommentVNode("", true),
                            _createVNode(_component_v_chip, {
                              size: "x-small",
                              variant: "tonal",
                              color: cacheKindColor(item.kind),
                              class: "mr-2"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(item.kind_label || item.kind), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"]),
                            _createElementVNode("span", {
                              class: "text-body-2 flex-grow-1 sdbs-lib-text sdbs-clickable",
                              title: item.key,
                              onClick: ($event) => toggleCacheRow(item)
                            }, _toDisplayString(item.label || item.key), 9, _hoisted_24),
                            item.ref ? (_openBlock(), _createElementBlock("span", _hoisted_25, _toDisplayString(item.ref), 1)) : _createCommentVNode("", true),
                            _createElementVNode("span", _hoisted_26, _toDisplayString(cacheTime(item.cached_at)), 1),
                            _createVNode(_component_v_btn, {
                              size: "x-small",
                              variant: "text",
                              color: "error",
                              loading: cacheDeleting.value === item.key,
                              onClick: ($event) => deleteCacheRow(item.key || "")
                            }, {
                              default: _withCtx(() => [..._cache[74] || (_cache[74] = [
                                _createTextVNode(" 删除 ", -1)
                              ])]),
                              _: 1
                            }, 8, ["loading", "onClick"]),
                            _createVNode(_component_v_btn, {
                              size: "x-small",
                              variant: "text",
                              icon: cacheOpenKey.value === item.key ? "mdi-chevron-up" : "mdi-chevron-down",
                              title: cacheOpenKey.value === item.key ? "收起" : "展开这条缓存里的内容",
                              onClick: ($event) => toggleCacheRow(item)
                            }, null, 8, ["icon", "title", "onClick"])
                          ], 2),
                          cacheExpanded.value && cacheExpanded.value.key === item.key ? (_openBlock(), _createElementBlock("div", _hoisted_27, [
                            _createElementVNode("div", _hoisted_28, _toDisplayString(cacheMetaLine(item)), 1),
                            cacheExpanded.value.loading ? (_openBlock(), _createElementBlock("div", _hoisted_29, [
                              _createVNode(_component_v_progress_circular, {
                                size: "16",
                                width: "2",
                                indeterminate: "",
                                class: "mr-2"
                              }),
                              _cache[75] || (_cache[75] = _createElementVNode("span", { class: "text-caption sdbs-dim" }, "正在读取缓存内容…", -1))
                            ])) : cacheExpanded.value.payload ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                              cacheExpanded.value.message ? (_openBlock(), _createBlock(_component_v_alert, {
                                key: 0,
                                type: "warning",
                                variant: "tonal",
                                density: "compact"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(cacheExpanded.value.message), 1)
                                ]),
                                _: 1
                              })) : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                cacheExpanded.value.payload.summary ? (_openBlock(), _createElementBlock("div", _hoisted_30, _toDisplayString(cacheExpanded.value.payload.summary), 1)) : _createCommentVNode("", true),
                                cacheExpanded.value.record ? (_openBlock(), _createBlock(RecordCard, {
                                  key: 1,
                                  record: cacheExpanded.value.record,
                                  api: props.api
                                }, null, 8, ["record", "api"])) : cacheExpanded.value.actor ? (_openBlock(), _createBlock(ActorCard, {
                                  key: 2,
                                  profile: cacheExpanded.value.actor,
                                  api: props.api,
                                  compact: ""
                                }, null, 8, ["profile", "api"])) : _createCommentVNode("", true),
                                _createElementVNode("div", _hoisted_31, [
                                  _createVNode(_component_v_btn, {
                                    size: "x-small",
                                    variant: "text",
                                    onClick: _cache[19] || (_cache[19] = ($event) => cacheRawOpen.value = !cacheRawOpen.value)
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(cacheRawOpen.value ? "收起缓存原文" : "缓存原文"), 1)
                                    ]),
                                    _: 1
                                  }),
                                  _cache[76] || (_cache[76] = _createElementVNode("span", { class: "text-caption sdbs-dim" }, " 缓存里那份未投影的解析结果（含 tmdb_identity / stills 等内部字段） ", -1))
                                ]),
                                cacheRawOpen.value ? (_openBlock(), _createElementBlock("pre", _hoisted_32, _toDisplayString(_unref(pretty)(cacheExpanded.value.payload.data)), 1)) : _createCommentVNode("", true)
                              ], 64))
                            ], 64)) : _createCommentVNode("", true)
                          ])) : _createCommentVNode("", true)
                        ]);
                      }), 128))
                    ]);
                  }), 128))
                ]),
                cacheMoreText.value ? (_openBlock(), _createElementBlock("div", _hoisted_33, _toDisplayString(cacheMoreText.value), 1)) : _createCommentVNode("", true)
              ]),
              _createVNode(_component_v_dialog, {
                modelValue: cacheClearOpen.value,
                "onUpdate:modelValue": _cache[22] || (_cache[22] = ($event) => cacheClearOpen.value = $event),
                "max-width": "440"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, null, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_card_title, { class: "text-subtitle-2 pt-3" }, {
                        default: _withCtx(() => [..._cache[77] || (_cache[77] = [
                          _createTextVNode("清空缓存", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode(_component_v_card_text, { class: "text-body-2" }, {
                        default: _withCtx(() => [
                          _cache[78] || (_cache[78] = _createTextVNode(" 将要删除：", -1)),
                          _createElementVNode("b", null, _toDisplayString(cacheClearScope.value), 1),
                          _cache[79] || (_cache[79] = _createTextVNode("。 ", -1)),
                          _cache[80] || (_cache[80] = _createElementVNode("br", null, null, -1)),
                          _cache[81] || (_cache[81] = _createTextVNode(" 缓存只是「省一次抓页面」，", -1)),
                          _cache[82] || (_cache[82] = _createElementVNode("b", null, "删掉不会丢任何数据", -1)),
                          _cache[83] || (_cache[83] = _createTextVNode(" —— 下次识别 / 搜索会重新解析一遍 （站点有风控，短时间大量重建可能触发限流）。只清本插件自己的缓存区，不动宿主与其它插件。 ", -1))
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_card_actions, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_spacer),
                          _createVNode(_component_v_btn, {
                            size: "small",
                            variant: "text",
                            onClick: _cache[20] || (_cache[20] = ($event) => cacheClearOpen.value = false)
                          }, {
                            default: _withCtx(() => [..._cache[84] || (_cache[84] = [
                              _createTextVNode("取消", -1)
                            ])]),
                            _: 1
                          }),
                          _createVNode(_component_v_btn, {
                            size: "small",
                            variant: "tonal",
                            color: "error",
                            loading: cacheClearing.value,
                            onClick: _cache[21] || (_cache[21] = ($event) => clearCacheAll())
                          }, {
                            default: _withCtx(() => [..._cache[85] || (_cache[85] = [
                              _createTextVNode(" 确认清空 ", -1)
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
              }, 8, ["modelValue"])
            ]),
            _: 1
          })
        ]),
        _createVNode(_component_v_card, {
          variant: "outlined",
          class: "pa-3 sdbs-panel"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_text_field, {
              modelValue: keyword.value,
              "onUpdate:modelValue": _cache[23] || (_cache[23] = ($event) => keyword.value = $event),
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              clearable: "",
              "prepend-inner-icon": "mdi-magnify",
              placeholder: "输入短剧片名或演员姓名，例如：女足替补的滚烫夏天 / 魏依珂",
              onKeyup: _withKeys(doLookup, ["enter"])
            }, null, 8, ["modelValue"]),
            _createElementVNode("div", _hoisted_34, [
              _createVNode(_component_v_btn, {
                size: "small",
                color: "primary",
                variant: "tonal",
                loading: searching.value,
                disabled: !keyword.value.trim(),
                onClick: doLookup
              }, {
                default: _withCtx(() => [..._cache[86] || (_cache[86] = [
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
                default: _withCtx(() => [..._cache[87] || (_cache[87] = [
                  _createTextVNode("清空", -1)
                ])]),
                _: 1
              }, 8, ["disabled"]),
              _createVNode(_component_v_spacer),
              hint.value ? (_openBlock(), _createElementBlock("span", _hoisted_35, _toDisplayString(hint.value), 1)) : _createCommentVNode("", true)
            ])
          ]),
          _: 1
        }),
        _createVNode(_component_v_row, { dense: "" }, {
          default: _withCtx(() => [
            hasTitlePanel.value ? (_openBlock(), _createBlock(_component_v_col, {
              key: 0,
              cols: "12",
              md: hasActorPanel.value ? 6 : 12
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "outlined",
                  class: "pa-3 sdbs-panel"
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_36, [
                      _createVNode(_component_v_icon, {
                        icon: "mdi-movie-search-outline",
                        size: "18",
                        class: "mr-1"
                      }),
                      _cache[88] || (_cache[88] = _createElementVNode("span", { class: "text-subtitle-2" }, "作品", -1)),
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
                        _createElementVNode("div", _hoisted_37, " 命中 " + _toDisplayString(titleCandidates.value.length) + " 条候选，点「识别」看完整详情（按匹配分排序）： ", 1),
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
                            candidate.from ? (_openBlock(), _createBlock(_component_v_chip, {
                              key: 0,
                              size: "x-small",
                              variant: "text",
                              color: candidate.from === "store" ? "teal" : "grey",
                              class: "mr-2",
                              title: candidate.from === "store" ? "URL 库里已有这条，本次零引擎请求" : "本次刚从搜索引擎发现，已写进 URL 库"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(candidate.from === "store" ? "库" : "引擎"), 1)
                              ]),
                              _: 2
                            }, 1032, ["color", "title"])) : _createCommentVNode("", true),
                            _createElementVNode("span", _hoisted_38, _toDisplayString(candidate.title), 1),
                            candidate.same_title && candidate.same_title > 1 ? (_openBlock(), _createBlock(_component_v_chip, {
                              key: 1,
                              size: "x-small",
                              variant: "text",
                              color: "orange-darken-2",
                              class: "ml-1",
                              title: "站点给这部剧建了多条记录（实测真人版 / AI 版标题一字不差），\r\n                  这条只是其中之一 —— 逐条点「识别」比一比，数据全的那条通常有演员与集数"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(" 同名 " + _toDisplayString(candidate.same_title) + " 版 ", 1)
                              ]),
                              _: 2
                            }, 1024)) : _createCommentVNode("", true),
                            candidate.url ? (_openBlock(), _createBlock(_component_v_btn, {
                              key: 2,
                              size: "x-small",
                              variant: "text",
                              icon: "mdi-open-in-new",
                              href: candidate.url,
                              target: "_blank",
                              rel: "noopener",
                              title: "打开站点页面"
                            }, null, 8, ["href"])) : _createCommentVNode("", true),
                            _createVNode(_component_v_btn, {
                              size: "x-small",
                              variant: "tonal",
                              color: "primary",
                              loading: titleLoadingId.value === candidate.media_id,
                              onClick: ($event) => pickTitle(candidate)
                            }, {
                              default: _withCtx(() => [..._cache[89] || (_cache[89] = [
                                _createTextVNode(" 识别 ", -1)
                              ])]),
                              _: 1
                            }, 8, ["loading", "onClick"])
                          ]);
                        }), 128))
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true),
                    titleRecord.value ? (_openBlock(), _createElementBlock("div", _hoisted_39, [
                      _createVNode(RecordCard, {
                        record: titleRecord.value,
                        api: props.api
                      }, null, 8, ["record", "api"])
                    ])) : titleMessage.value ? (_openBlock(), _createBlock(_component_v_alert, {
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
            }, 8, ["md"])) : _createCommentVNode("", true),
            hasActorPanel.value ? (_openBlock(), _createBlock(_component_v_col, {
              key: 1,
              cols: "12",
              md: hasTitlePanel.value ? 6 : 12
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card, {
                  variant: "outlined",
                  class: "pa-3 sdbs-panel"
                }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_40, [
                      _createVNode(_component_v_icon, {
                        icon: "mdi-account-search-outline",
                        size: "18",
                        class: "mr-1"
                      }),
                      _cache[90] || (_cache[90] = _createElementVNode("span", { class: "text-subtitle-2" }, "演员", -1)),
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
                        _createElementVNode("div", _hoisted_41, " 命中 " + _toDisplayString(actorCandidates.value.length) + " 位，点「看作品」拉取档案与全部作品： ", 1),
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
                            candidate.from ? (_openBlock(), _createBlock(_component_v_chip, {
                              key: 0,
                              size: "x-small",
                              variant: "text",
                              color: candidate.from === "store" ? "teal" : "grey",
                              class: "mr-2",
                              title: candidate.from === "store" ? "URL 库里已有这条，本次零引擎请求" : "本次刚从搜索引擎发现，已写进 URL 库"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(candidate.from === "store" ? "库" : "引擎"), 1)
                              ]),
                              _: 2
                            }, 1032, ["color", "title"])) : _createCommentVNode("", true),
                            _createElementVNode("span", _hoisted_42, _toDisplayString(candidate.name), 1),
                            candidate.url ? (_openBlock(), _createBlock(_component_v_btn, {
                              key: 1,
                              size: "x-small",
                              variant: "text",
                              icon: "mdi-open-in-new",
                              href: candidate.url,
                              target: "_blank",
                              rel: "noopener",
                              title: "打开演员页"
                            }, null, 8, ["href"])) : _createCommentVNode("", true),
                            _createElementVNode("span", _hoisted_43, "actor:" + _toDisplayString(candidate.actor_id), 1),
                            _createVNode(_component_v_btn, {
                              size: "x-small",
                              variant: "tonal",
                              color: "primary",
                              loading: actorLoadingId.value === candidate.actor_id,
                              onClick: ($event) => pickActor(candidate)
                            }, {
                              default: _withCtx(() => [..._cache[91] || (_cache[91] = [
                                _createTextVNode(" 看作品 ", -1)
                              ])]),
                              _: 1
                            }, 8, ["loading", "onClick"])
                          ]);
                        }), 128))
                      ]),
                      _: 1
                    })) : _createCommentVNode("", true),
                    actorProfile.value ? (_openBlock(), _createElementBlock("div", _hoisted_44, [
                      _createVNode(ActorCard, {
                        profile: actorProfile.value,
                        api: props.api
                      }, null, 8, ["profile", "api"])
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
            }, 8, ["md"])) : _createCommentVNode("", true)
          ]),
          _: 1
        }),
        _createVNode(_component_v_dialog, {
          modelValue: settingsOpen.value,
          "onUpdate:modelValue": _cache[25] || (_cache[25] = ($event) => settingsOpen.value = $event),
          "max-width": "1080",
          scrollable: ""
        }, {
          default: _withCtx(() => [
            settingsOpen.value ? (_openBlock(), _createBlock(Config, {
              key: 0,
              api: props.api,
              "initial-config": remoteConfig.value,
              onClose: _cache[24] || (_cache[24] = ($event) => settingsOpen.value = false),
              onSave: onConfigSaved
            }, null, 8, ["api", "initial-config"])) : _createCommentVNode("", true)
          ]),
          _: 1
        }, 8, ["modelValue"])
      ], 2);
    };
  }
});

const Page = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-8bf25fe6"]]);

export { Page as default };
