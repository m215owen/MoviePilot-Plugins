import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { a as siteKey, s as siteInfo, d as fetchStatus, b as setSite, e as ensureSite, g as fetchBaikeExtList, h as fetchBaikeList, i as backfillExtIds, j as deleteBaike, k as clearBaike, l as fetchCacheItems, m as deleteCacheItem, n as clearCache, p as proxyImage, o as fetchNovel, q as fetchPerson, r as lookupRaw, t as envelopeOf } from './site-UXzUndvw.js';

const ENTITY_LABELS = {
  duanju: "短剧（老站）",
  manju: "漫剧",
  hema: "漫剧（河马）",
  huolong: "漫剧（火龙）",
  xiaoshuo: "原著",
  yanyuan: "演员（老站）",
  daoyan: "导演",
  bianju: "编剧",
  drama: "短剧（新站）",
  actor: "演员（新站）",
  douban: "豆瓣作品",
  doubanp: "豆瓣人物"
};
const SITE_ENTITIES = {
  net: ["duanju", "manju", "hema", "huolong", "xiaoshuo", "yanyuan", "daoyan", "bianju", "douban", "doubanp"],
  org: ["drama", "actor", "douban", "doubanp"]
};
const MANJU_ENTITIES = ["manju", "hema", "huolong"];
function entityFiltersFor(site, excludeManju = false) {
  const key = String(site || "").trim().toLowerCase();
  const list = SITE_ENTITIES[key] || SITE_ENTITIES.net;
  return excludeManju ? list.filter((item) => !MANJU_ENTITIES.includes(item)) : [...list];
}
function isKnownEntity(entity) {
  return Object.prototype.hasOwnProperty.call(ENTITY_LABELS, String(entity || "").trim());
}
const REGION_LABELS = {
  "djbaike.detail": "详情",
  "djbaike.person": "人物",
  "djbaike.douban": "豆瓣",
  "djbaike.search": "站内搜索",
  "djbaike.rank": "榜单"
};
function entityLabel(entity) {
  const key = String(entity || "").trim();
  return ENTITY_LABELS[key] || key || "未知";
}
function regionLabel(region) {
  const key = String(region || "").trim();
  return REGION_LABELS[key] || key || "未知";
}
function entityOf(mediaId) {
  const text = String(mediaId || "");
  const at = text.indexOf(":");
  return at > 0 ? text.slice(0, at) : text;
}
const PERSON_ENTITIES = ["yanyuan", "daoyan", "bianju", "actor", "doubanp"];
function isPersonId(mediaId) {
  return PERSON_ENTITIES.includes(entityOf(mediaId));
}
const FACT_LABELS = {
  "extensions.djbaike.heat": "热度",
  "extensions.djbaike.play_count": "播放",
  "extensions.djbaike.favorite_count": "收藏",
  "extensions.djbaike.is_short_drama": "百科收录",
  "extensions.djbaike.kind": "形态"
};
const METRIC_FACTS = [
  "extensions.djbaike.heat",
  "extensions.djbaike.play_count",
  "extensions.djbaike.favorite_count"
];
const FACT_ICONS = {
  "extensions.djbaike.heat": "mdi-fire",
  "extensions.djbaike.play_count": "mdi-play-circle-outline",
  "extensions.djbaike.favorite_count": "mdi-heart-outline"
};
function factLabel(key) {
  const text = String(key || "").trim();
  return FACT_LABELS[text] || text || "未知";
}
function factIcon(key) {
  const text = String(key || "").trim();
  return FACT_ICONS[text] || "mdi-chart-line";
}
function percent(part, whole) {
  const total = Number(whole) || 0;
  if (total <= 0) return "—";
  return `${Math.round(Number(part) / total * 100)}%`;
}

const {defineComponent:_defineComponent$5} = await importShared('vue');

const {toDisplayString:_toDisplayString$4,createTextVNode:_createTextVNode$4,resolveComponent:_resolveComponent$4,withCtx:_withCtx$4,openBlock:_openBlock$5,createBlock:_createBlock$4,createCommentVNode:_createCommentVNode$4,unref:_unref$3,withKeys:_withKeys$1,createVNode:_createVNode$4,createElementVNode:_createElementVNode$5,renderList:_renderList$3,Fragment:_Fragment$3,createElementBlock:_createElementBlock$5,withModifiers:_withModifiers$1} = await importShared('vue');

const _hoisted_1$5 = { class: "sdbs-page" };
const _hoisted_2$5 = { class: "sdbs-filter-row" };
const _hoisted_3$4 = { class: "sdbs-actions" };
const _hoisted_4$4 = {
  key: 0,
  class: "sdbs-dim"
};
const _hoisted_5$4 = {
  key: 0,
  class: "sdbs-dim"
};
const _hoisted_6$4 = {
  key: 0,
  class: "sdbs-dim"
};
const _hoisted_7$4 = { class: "sdbs-meta" };
const _hoisted_8$4 = { class: "sdbs-meta-item" };
const _hoisted_9$4 = { class: "sdbs-meta-value" };
const _hoisted_10$3 = { class: "sdbs-meta-item" };
const _hoisted_11$3 = { class: "sdbs-meta-value sdbs-num" };
const _hoisted_12$3 = {
  key: 2,
  class: "sdbs-list"
};
const _hoisted_13$3 = { class: "sdbs-row-top" };
const _hoisted_14$3 = ["onClick"];
const _hoisted_15$3 = { class: "sdbs-row-main" };
const _hoisted_16$3 = { class: "sdbs-row-title" };
const _hoisted_17$3 = { class: "sdbs-tag" };
const _hoisted_18$3 = ["title"];
const _hoisted_19$3 = { class: "sdbs-key" };
const _hoisted_20$3 = { key: 0 };
const _hoisted_21$3 = {
  key: 0,
  class: "sdbs-expand"
};
const _hoisted_22$2 = {
  class: "sdbs-key",
  style: { "width": "120px" }
};
const _hoisted_23$2 = {
  key: 0,
  class: "sdbs-key"
};
const _hoisted_24$2 = {
  key: 1,
  class: "sdbs-dim"
};
const _hoisted_25$2 = { class: "sdbs-actions" };
const _hoisted_26$2 = { class: "sdbs-raw" };
const _hoisted_27$1 = {
  key: 3,
  class: "sdbs-list"
};
const _hoisted_28$1 = { class: "sdbs-row-top" };
const _hoisted_29$1 = ["onClick"];
const _hoisted_30$1 = { class: "sdbs-row-main" };
const _hoisted_31$1 = { class: "sdbs-row-title" };
const _hoisted_32$1 = { class: "sdbs-tag" };
const _hoisted_33$1 = ["title"];
const _hoisted_34$1 = { class: "sdbs-key" };
const _hoisted_35$1 = {
  key: 0,
  class: "sdbs-gap sdbs-dim"
};
const _hoisted_36$1 = {
  key: 0,
  class: "sdbs-expand"
};
const _hoisted_37$1 = {
  class: "sdbs-key",
  style: { "width": "120px" }
};
const _hoisted_38$1 = {
  key: 0,
  class: "sdbs-key"
};
const _hoisted_39$1 = {
  key: 1,
  class: "sdbs-dim"
};
const _hoisted_40$1 = { class: "sdbs-actions" };
const _hoisted_41$1 = { class: "sdbs-raw" };
const _hoisted_42$1 = {
  key: 4,
  class: "sdbs-empty"
};
const {computed: computed$4,onBeforeUnmount,onMounted: onMounted$3,ref: ref$4,watch: watch$1} = await importShared('vue');
const EXT_DOUBAN = "__ext_douban__";
const EXT_TMDB = "__ext_tmdb__";
const _sfc_main$5 = /* @__PURE__ */ _defineComponent$5({
  __name: "BaikePanel",
  props: {
    api: {}
  },
  emits: ["lookup"],
  setup(__props, { expose: __expose, emit: __emit }) {
    const props = __props;
    const emit = __emit;
    const LIMITS = [25, 50, 100, 200];
    const EXT_SOURCES = {
      [EXT_DOUBAN]: "douban",
      [EXT_TMDB]: "tmdb"
    };
    const SITE_COLUMNS = [
      { key: "media_id", label: "media_id" },
      { key: "name", label: "name" }
    ];
    const EXT_COLUMNS = [
      { key: "name", label: "name" },
      { key: "douban", label: "douban" },
      { key: "tmdb", label: "tmdb" }
    ];
    const loading = ref$4(false);
    const loaded = ref$4(false);
    const items = ref$4([]);
    const extItems = ref$4([]);
    const total = ref$4(0);
    const offset = ref$4(0);
    const limit = ref$4(50);
    const error = ref$4("");
    const keyword = ref$4("");
    const submitted = ref$4("");
    const entity = ref$4("");
    const opened = ref$4("");
    const pending = ref$4(null);
    const confirmOpen = ref$4(false);
    const purging = ref$4(false);
    const counts = ref$4({});
    const extDouban = ref$4(0);
    const extTmdb = ref$4(0);
    const extMode = computed$4(() => Boolean(EXT_SOURCES[entity.value]));
    const extSource = computed$4(() => EXT_SOURCES[entity.value] || "");
    const extLabel = computed$4(
      () => extSource.value === "douban" ? "豆瓣 id" : extSource.value === "tmdb" ? "TMDB id" : ""
    );
    const excludeManju = ref$4(true);
    const backfilling = ref$4(false);
    const backfillTip = ref$4("");
    const cursor = ref$4("");
    const chips = computed$4(() => {
      const own = entityFiltersFor(siteKey.value, excludeManju.value);
      const extra = Object.keys(counts.value).filter(
        (key) => isKnownEntity(key) && !own.includes(key) && countOf(key) > 0 && !(excludeManju.value && MANJU_ENTITIES.includes(key))
      ).sort();
      return [...own, ...extra];
    });
    function countOf(entity2) {
      return Number(counts.value[String(entity2 || "")] || 0);
    }
    async function loadStatus() {
      try {
        const status = await fetchStatus(props);
        counts.value = status?.by_entity || {};
        extDouban.value = Number(status?.ext_douban || 0);
        extTmdb.value = Number(status?.ext_tmdb || 0);
        excludeManju.value = status?.exclude_manju !== false;
        setSite(status?.site);
      } catch {
        await ensureSite(props.api);
      }
      syncEntity();
    }
    function syncEntity() {
      if (!entity.value || extMode.value) return;
      if (chips.value.includes(entity.value)) return;
      entity.value = "";
      search();
    }
    let token = 0;
    const filtered = computed$4(() => Boolean(submitted.value || entity.value));
    const rowCount = computed$4(
      () => extMode.value ? extItems.value.length : items.value.length
    );
    const rangeText = computed$4(() => {
      if (!rowCount.value) return "0";
      return `${offset.value + 1}–${offset.value + rowCount.value}`;
    });
    const emptyIcon = computed$4(() => {
      if (loading.value) return "mdi-progress-clock";
      return filtered.value ? "mdi-magnify-close" : "mdi-database-off-outline";
    });
    const confirmText = computed$4(() => {
      if (pending.value) {
        return `从 ID 库删掉这一行？

media_id：${pending.value.media_id}
name：${pending.value.name || "（空）"}

会联动删除它的详情缓存与人物缓存；下次识别到它会重新入库。`;
      }
      return `清空站点 ID 库的 ${total.value} 条记录？

只删「baike」表里的站点行，**外部 id（baike_ext 里的豆瓣 / TMDB）保留**；**缓存也不动**（缓存请到「缓存」分区单独清）。站点行清空后要靠后续识别 / 检索重新生长。`;
    });
    function subTitle(row) {
      const parts = [row.media_id];
      parts.push(entityLabel(entityOf(row.media_id)));
      return parts.join(" · ");
    }
    function extValueOf(row) {
      if (extSource.value === "douban") return row.douban;
      if (extSource.value === "tmdb") return row.tmdb;
      return "";
    }
    function otherExtOf(row) {
      if (extSource.value === "douban" && row.tmdb) return `TMDB ${row.tmdb}`;
      if (extSource.value === "tmdb" && row.douban) return `豆瓣 ${row.douban}`;
      return "";
    }
    function extSubTitle(row) {
      const parts = [row.name, `${extLabel.value || "外部 id"} ${extValueOf(row) || "（空）"}`];
      if (row.douban && extSource.value !== "douban") parts.push(`豆瓣 ${row.douban}`);
      if (row.tmdb && extSource.value !== "tmdb") parts.push(`TMDB ${row.tmdb}`);
      return parts.join(" · ");
    }
    function canLookup(row) {
      const id = String(row.media_id || "");
      return id.includes(":") && id.split(":")[1].length > 0;
    }
    function toggle(key) {
      opened.value = opened.value === key ? "" : key;
    }
    async function copy(text) {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        error.value = "复制失败：浏览器拒绝了剪贴板权限";
      }
    }
    function search() {
      submitted.value = String(keyword.value || "").trim();
      offset.value = 0;
      opened.value = "";
      cursor.value = "";
      backfillTip.value = "";
      void load();
    }
    function step(direction) {
      const next = offset.value + direction * limit.value;
      if (next < 0) return;
      offset.value = next;
      opened.value = "";
      void load();
    }
    async function load() {
      const seq = ++token;
      const wantExt = extMode.value;
      loading.value = true;
      error.value = "";
      try {
        let got = 0;
        if (wantExt) {
          const data = await fetchBaikeExtList(props, {
            q: submitted.value,
            offset: offset.value,
            limit: limit.value,
            source: extSource.value
          });
          if (seq !== token) return;
          extItems.value = data?.items || [];
          items.value = [];
          got = extItems.value.length;
          total.value = Number(data?.total ?? got);
        } else {
          const data = await fetchBaikeList(props, {
            q: submitted.value,
            entity: entity.value,
            offset: offset.value,
            limit: limit.value
          });
          if (seq !== token) return;
          items.value = data?.items || [];
          extItems.value = [];
          got = items.value.length;
          total.value = Number(data?.total ?? got);
        }
        if (!got && total.value > 0 && offset.value > 0) {
          offset.value = Math.max(0, Math.floor((total.value - 1) / limit.value) * limit.value);
        }
      } catch (err) {
        if (seq !== token) return;
        error.value = `读取 ${wantExt ? `外部 id 表（${extLabel.value}）` : "站点 ID 库"}失败：${err instanceof Error ? err.message : String(err)}`;
        items.value = [];
        extItems.value = [];
        total.value = 0;
      } finally {
        if (seq === token) {
          loading.value = false;
          loaded.value = true;
        }
      }
    }
    async function backfill() {
      if (backfilling.value) return;
      backfilling.value = true;
      backfillTip.value = "";
      error.value = "";
      const personScope = PERSON_ENTITIES.includes(entity.value);
      const BATCH = personScope ? 15 : 30;
      const ROUNDS = personScope ? 2 : 5;
      let scanned = 0;
      let douban = 0;
      let tmdb = 0;
      let remaining = 0;
      let throttled = false;
      try {
        for (let round = 0; round < ROUNDS; round += 1) {
          const result = await backfillExtIds(props, {
            entity: entity.value,
            limit: BATCH,
            after: cursor.value
          });
          scanned += result?.scanned || 0;
          douban += result?.douban || 0;
          tmdb += result?.tmdb || 0;
          remaining = result?.remaining || 0;
          const next = result?.cursor || "";
          const moved = next !== cursor.value;
          cursor.value = next;
          if (result?.throttled) {
            throttled = true;
            break;
          }
          if (!moved) break;
        }
        const parts = personScope ? [`扫了 ${scanned} 个演员/人物`, `补豆瓣 ${douban}`, `补 TMDB ${tmdb}`, `剩余待补 ${remaining}`] : [`扫了 ${scanned} 条`, `补豆瓣 ${douban}`, `补 TMDB ${tmdb}`, `剩余待补 ${remaining}`];
        backfillTip.value = parts.join(" · ") + (throttled ? "（豆瓣风控，等 10 分钟以上再点）" : remaining > 0 ? "（再点一次继续往后扫）" : "");
        await load();
        await loadStatus();
      } catch (err) {
        error.value = `批量补 id 失败：${err instanceof Error ? err.message : String(err)}`;
      } finally {
        backfilling.value = false;
      }
    }
    function askDelete(row) {
      pending.value = row;
      confirmOpen.value = true;
    }
    function askClear() {
      pending.value = null;
      confirmOpen.value = true;
    }
    function closeConfirm() {
      if (purging.value) return;
      confirmOpen.value = false;
      pending.value = null;
    }
    async function confirmPurge() {
      const target = pending.value;
      purging.value = true;
      error.value = "";
      try {
        if (target) {
          const result = await deleteBaike(props, target.media_id);
          if (!result?.ok) error.value = `删除未生效：${result?.detail || "该 media_id 不存在"}`;
        } else {
          const result = await clearBaike(props);
          if (!result?.ok) error.value = "清空未生效：后端未确认";
          offset.value = 0;
        }
        confirmOpen.value = false;
        pending.value = null;
        opened.value = "";
        await loadStatus();
        await load();
      } catch (err) {
        error.value = `操作失败：${err instanceof Error ? err.message : String(err)}`;
      } finally {
        purging.value = false;
      }
    }
    async function refresh() {
      await loadStatus();
      await load();
    }
    __expose({ reload: refresh });
    let timer;
    watch$1(
      () => keyword.value,
      (value) => {
        window.clearTimeout(timer);
        const text = String(value || "").trim();
        if (!text) {
          search();
          return;
        }
        timer = window.setTimeout(() => {
          submitted.value = text;
          offset.value = 0;
          opened.value = "";
          void load();
        }, 350);
      }
    );
    onMounted$3(() => {
      void loadStatus();
      void load();
    });
    onBeforeUnmount(() => {
      window.clearTimeout(timer);
    });
    return (_ctx, _cache) => {
      const _component_v_alert = _resolveComponent$4("v-alert");
      const _component_v_text_field = _resolveComponent$4("v-text-field");
      const _component_v_btn = _resolveComponent$4("v-btn");
      const _component_v_btn_toggle = _resolveComponent$4("v-btn-toggle");
      const _component_v_spacer = _resolveComponent$4("v-spacer");
      const _component_v_icon = _resolveComponent$4("v-icon");
      const _component_v_select = _resolveComponent$4("v-select");
      const _component_v_table = _resolveComponent$4("v-table");
      const _component_v_card_title = _resolveComponent$4("v-card-title");
      const _component_v_card_text = _resolveComponent$4("v-card-text");
      const _component_v_card_actions = _resolveComponent$4("v-card-actions");
      const _component_v_card = _resolveComponent$4("v-card");
      const _component_v_dialog = _resolveComponent$4("v-dialog");
      return _openBlock$5(), _createElementBlock$5("div", _hoisted_1$5, [
        error.value ? (_openBlock$5(), _createBlock$4(_component_v_alert, {
          key: 0,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-2"
        }, {
          default: _withCtx$4(() => [
            _createTextVNode$4(_toDisplayString$4(error.value), 1)
          ]),
          _: 1
        })) : _createCommentVNode$4("", true),
        _createElementVNode$5("div", _hoisted_2$5, [
          _createVNode$4(_component_v_text_field, {
            modelValue: keyword.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => keyword.value = $event),
            class: "sdbs-filter",
            variant: "outlined",
            density: "compact",
            "hide-details": "",
            clearable: "",
            "prepend-inner-icon": "mdi-magnify",
            placeholder: extMode.value ? `按名字 / ${extLabel.value} 模糊过滤（例如：马倩倩 / ${extSource.value === "douban" ? "38500395" : "298016"}）` : `按 media_id 或 name 模糊过滤（例如：以爱为家 / ${_unref$3(siteInfo).sampleId}）`,
            onKeydown: _cache[1] || (_cache[1] = _withKeys$1(($event) => search(), ["enter"]))
          }, null, 8, ["modelValue", "placeholder"]),
          _createVNode$4(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            loading: loading.value,
            onClick: _cache[2] || (_cache[2] = ($event) => search())
          }, {
            default: _withCtx$4(() => [..._cache[15] || (_cache[15] = [
              _createTextVNode$4(" 查询 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"])
        ]),
        _createElementVNode$5("div", _hoisted_3$4, [
          _createVNode$4(_component_v_btn_toggle, {
            modelValue: entity.value,
            "onUpdate:modelValue": [
              _cache[3] || (_cache[3] = ($event) => entity.value = $event),
              _cache[4] || (_cache[4] = ($event) => search())
            ],
            class: "sdbs-toggle",
            density: "compact",
            variant: "text",
            divided: "",
            mandatory: ""
          }, {
            default: _withCtx$4(() => [
              _createVNode$4(_component_v_btn, {
                size: "x-small",
                value: ""
              }, {
                default: _withCtx$4(() => [..._cache[16] || (_cache[16] = [
                  _createTextVNode$4("全部", -1)
                ])]),
                _: 1
              }),
              (_openBlock$5(true), _createElementBlock$5(_Fragment$3, null, _renderList$3(chips.value, (key) => {
                return _openBlock$5(), _createBlock$4(_component_v_btn, {
                  key,
                  size: "x-small",
                  value: key,
                  title: `${_unref$3(entityLabel)(key)} · 库里 ${countOf(key)} 条`
                }, {
                  default: _withCtx$4(() => [
                    _createTextVNode$4(_toDisplayString$4(_unref$3(entityLabel)(key)) + " ", 1),
                    countOf(key) ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_4$4, _toDisplayString$4(countOf(key)), 1)) : _createCommentVNode$4("", true)
                  ]),
                  _: 2
                }, 1032, ["value", "title"]);
              }), 128)),
              _createVNode$4(_component_v_btn, {
                size: "x-small",
                value: EXT_DOUBAN,
                title: `外部 id 表（baike_ext）里有豆瓣 id 的记录：名字 + 豆瓣 id，共 ${extDouban.value} 条；与站点行无关，清空站点库也不受影响`
              }, {
                default: _withCtx$4(() => [
                  _cache[17] || (_cache[17] = _createTextVNode$4(" 豆瓣 id ", -1)),
                  extDouban.value ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_5$4, _toDisplayString$4(extDouban.value), 1)) : _createCommentVNode$4("", true)
                ]),
                _: 1
              }, 8, ["title"]),
              _createVNode$4(_component_v_btn, {
                size: "x-small",
                value: EXT_TMDB,
                title: `外部 id 表（baike_ext）里有 TMDB id 的记录：名字 + TMDB id，共 ${extTmdb.value} 条；与站点行无关，清空站点库也不受影响`
              }, {
                default: _withCtx$4(() => [
                  _cache[18] || (_cache[18] = _createTextVNode$4(" TMDB id ", -1)),
                  extTmdb.value ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_6$4, _toDisplayString$4(extTmdb.value), 1)) : _createCommentVNode$4("", true)
                ]),
                _: 1
              }, 8, ["title"])
            ]),
            _: 1
          }, 8, ["modelValue"]),
          _createVNode$4(_component_v_spacer),
          _createVNode$4(_component_v_btn, {
            size: "x-small",
            variant: "text",
            "prepend-icon": "mdi-refresh",
            title: "按当前条件重查（数据库查询本来就实时，这里只是重发条件）",
            loading: loading.value,
            onClick: _cache[5] || (_cache[5] = ($event) => load())
          }, {
            default: _withCtx$4(() => [..._cache[19] || (_cache[19] = [
              _createTextVNode$4(" 刷新 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"]),
          _createVNode$4(_component_v_btn, {
            size: "x-small",
            variant: "text",
            "prepend-icon": "mdi-link-variant-plus",
            title: _unref$3(PERSON_ENTITIES).includes(entity.value) ? "按豆瓣演职员表给人物补影人 id（同片同名即同一人；一批 20 部作品，可反复点）" : "给库里 douban / tmdb 两列全空的行按名补一次外部 id（豆瓣精确匹配；一批 20 条，可反复点；豆瓣限流时会自动停）",
            loading: backfilling.value,
            disabled: extMode.value || !loaded.value || !total.value || backfilling.value,
            onClick: _cache[6] || (_cache[6] = ($event) => backfill())
          }, {
            default: _withCtx$4(() => [..._cache[20] || (_cache[20] = [
              _createTextVNode$4(" 补 id ", -1)
            ])]),
            _: 1
          }, 8, ["title", "loading", "disabled"]),
          _createVNode$4(_component_v_btn, {
            size: "x-small",
            variant: "text",
            color: "error",
            "prepend-icon": "mdi-delete-sweep-outline",
            title: "清空站点 ID 库（外部 id 与缓存都不动）",
            disabled: extMode.value || !loaded.value || !total.value,
            onClick: _cache[7] || (_cache[7] = ($event) => askClear())
          }, {
            default: _withCtx$4(() => [..._cache[21] || (_cache[21] = [
              _createTextVNode$4(" 清空 ", -1)
            ])]),
            _: 1
          }, 8, ["disabled"])
        ]),
        _createElementVNode$5("div", _hoisted_7$4, [
          _createElementVNode$5("span", _hoisted_8$4, [
            _createVNode$4(_component_v_icon, {
              size: "14",
              icon: "mdi-format-list-numbered"
            }),
            _cache[22] || (_cache[22] = _createTextVNode$4(" 共 ", -1)),
            _createElementVNode$5("span", _hoisted_9$4, _toDisplayString$4(loaded.value ? total.value : "—"), 1),
            _cache[23] || (_cache[23] = _createTextVNode$4(" 条 ", -1))
          ]),
          _createElementVNode$5("span", _hoisted_10$3, [
            _cache[24] || (_cache[24] = _createTextVNode$4(" 显示 ", -1)),
            _createElementVNode$5("span", _hoisted_11$3, _toDisplayString$4(rangeText.value), 1)
          ]),
          _createVNode$4(_component_v_spacer),
          _createVNode$4(_component_v_btn, {
            size: "x-small",
            variant: "text",
            icon: "mdi-chevron-left",
            title: "上一页",
            disabled: offset.value <= 0 || loading.value,
            onClick: _cache[8] || (_cache[8] = ($event) => step(-1))
          }, null, 8, ["disabled"]),
          _createVNode$4(_component_v_btn, {
            size: "x-small",
            variant: "text",
            icon: "mdi-chevron-right",
            title: "下一页",
            disabled: offset.value + limit.value >= total.value || loading.value,
            onClick: _cache[9] || (_cache[9] = ($event) => step(1))
          }, null, 8, ["disabled"]),
          _createVNode$4(_component_v_select, {
            modelValue: limit.value,
            "onUpdate:modelValue": [
              _cache[10] || (_cache[10] = ($event) => limit.value = $event),
              _cache[11] || (_cache[11] = ($event) => search())
            ],
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            items: LIMITS,
            style: { "max-width": "96px" }
          }, null, 8, ["modelValue"])
        ]),
        backfillTip.value ? (_openBlock$5(), _createBlock$4(_component_v_alert, {
          key: 1,
          type: "info",
          variant: "tonal",
          density: "compact",
          class: "mb-2"
        }, {
          default: _withCtx$4(() => [
            _createTextVNode$4(_toDisplayString$4(backfillTip.value), 1)
          ]),
          _: 1
        })) : _createCommentVNode$4("", true),
        !extMode.value && items.value.length ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_12$3, [
          (_openBlock$5(true), _createElementBlock$5(_Fragment$3, null, _renderList$3(items.value, (row) => {
            return _openBlock$5(), _createElementBlock$5("div", {
              key: row.media_id,
              class: "sdbs-row"
            }, [
              _createElementVNode$5("div", _hoisted_13$3, [
                _createElementVNode$5("button", {
                  type: "button",
                  class: "sdbs-row-head",
                  onClick: ($event) => toggle(row.media_id)
                }, [
                  _createVNode$4(_component_v_icon, {
                    size: "14",
                    icon: opened.value === row.media_id ? "mdi-chevron-down" : "mdi-chevron-right"
                  }, null, 8, ["icon"]),
                  _createElementVNode$5("span", _hoisted_15$3, [
                    _createElementVNode$5("span", _hoisted_16$3, _toDisplayString$4(row.name || "（未记录名字）"), 1),
                    _createElementVNode$5("span", _hoisted_17$3, _toDisplayString$4(_unref$3(entityLabel)(_unref$3(entityOf)(row.media_id))), 1)
                  ])
                ], 8, _hoisted_14$3),
                _createVNode$4(_component_v_btn, {
                  class: "sdbs-row-del",
                  size: "x-small",
                  variant: "text",
                  color: "error",
                  icon: "mdi-delete-outline",
                  title: `从库里删掉 ${row.media_id}（会联动删它的详情 / 人物缓存）`,
                  onClick: _withModifiers$1(($event) => askDelete(row), ["stop"])
                }, null, 8, ["title", "onClick"])
              ]),
              _createElementVNode$5("div", {
                class: "sdbs-row-sub",
                title: subTitle(row)
              }, [
                _createElementVNode$5("span", _hoisted_19$3, _toDisplayString$4(row.media_id), 1),
                !row.name ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_20$3, " · 无名字（不可按名检索）")) : _createCommentVNode$4("", true)
              ], 8, _hoisted_18$3),
              opened.value === row.media_id ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_21$3, [
                _createVNode$4(_component_v_table, {
                  density: "compact",
                  class: "mb-1"
                }, {
                  default: _withCtx$4(() => [
                    _createElementVNode$5("tbody", null, [
                      (_openBlock$5(), _createElementBlock$5(_Fragment$3, null, _renderList$3(SITE_COLUMNS, (col) => {
                        return _createElementVNode$5("tr", {
                          key: col.key
                        }, [
                          _createElementVNode$5("td", _hoisted_22$2, _toDisplayString$4(col.key), 1),
                          _createElementVNode$5("td", null, [
                            row[col.key] ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_23$2, _toDisplayString$4(row[col.key]), 1)) : (_openBlock$5(), _createElementBlock$5("span", _hoisted_24$2, "（空）"))
                          ])
                        ]);
                      }), 64))
                    ])
                  ]),
                  _: 2
                }, 1024),
                _createElementVNode$5("div", _hoisted_25$2, [
                  _createVNode$4(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    "prepend-icon": "mdi-content-duplicate",
                    onClick: ($event) => copy(JSON.stringify(row, null, 2))
                  }, {
                    default: _withCtx$4(() => [..._cache[25] || (_cache[25] = [
                      _createTextVNode$4(" 复制这一行 JSON ", -1)
                    ])]),
                    _: 1
                  }, 8, ["onClick"]),
                  _createVNode$4(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    color: "primary",
                    "prepend-icon": "mdi-open-in-new",
                    disabled: !canLookup(row),
                    title: "按 media_id 查这条的详情（会出网，命中缓存则零请求）",
                    onClick: ($event) => emit("lookup", row.media_id)
                  }, {
                    default: _withCtx$4(() => [..._cache[26] || (_cache[26] = [
                      _createTextVNode$4(" 查详情 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["disabled", "onClick"])
                ]),
                _createElementVNode$5("pre", _hoisted_26$2, _toDisplayString$4(JSON.stringify(row, null, 2)), 1)
              ])) : _createCommentVNode$4("", true)
            ]);
          }), 128))
        ])) : extMode.value && extItems.value.length ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_27$1, [
          (_openBlock$5(true), _createElementBlock$5(_Fragment$3, null, _renderList$3(extItems.value, (row) => {
            return _openBlock$5(), _createElementBlock$5("div", {
              key: row.name,
              class: "sdbs-row"
            }, [
              _createElementVNode$5("div", _hoisted_28$1, [
                _createElementVNode$5("button", {
                  type: "button",
                  class: "sdbs-row-head",
                  onClick: ($event) => toggle(row.name)
                }, [
                  _createVNode$4(_component_v_icon, {
                    size: "14",
                    icon: opened.value === row.name ? "mdi-chevron-down" : "mdi-chevron-right"
                  }, null, 8, ["icon"]),
                  _createElementVNode$5("span", _hoisted_30$1, [
                    _createElementVNode$5("span", _hoisted_31$1, _toDisplayString$4(row.name), 1),
                    _createElementVNode$5("span", _hoisted_32$1, _toDisplayString$4(extLabel.value), 1)
                  ])
                ], 8, _hoisted_29$1)
              ]),
              _createElementVNode$5("div", {
                class: "sdbs-row-sub",
                title: extSubTitle(row)
              }, [
                _createElementVNode$5("span", null, [
                  _createTextVNode$4(_toDisplayString$4(extLabel.value) + " ", 1),
                  _createElementVNode$5("span", _hoisted_34$1, _toDisplayString$4(extValueOf(row) || "（空）"), 1)
                ]),
                otherExtOf(row) ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_35$1, "· 另有 " + _toDisplayString$4(otherExtOf(row)), 1)) : _createCommentVNode$4("", true)
              ], 8, _hoisted_33$1),
              opened.value === row.name ? (_openBlock$5(), _createElementBlock$5("div", _hoisted_36$1, [
                _createVNode$4(_component_v_table, {
                  density: "compact",
                  class: "mb-1"
                }, {
                  default: _withCtx$4(() => [
                    _createElementVNode$5("tbody", null, [
                      (_openBlock$5(), _createElementBlock$5(_Fragment$3, null, _renderList$3(EXT_COLUMNS, (col) => {
                        return _createElementVNode$5("tr", {
                          key: col.key
                        }, [
                          _createElementVNode$5("td", _hoisted_37$1, _toDisplayString$4(col.key), 1),
                          _createElementVNode$5("td", null, [
                            row[col.key] ? (_openBlock$5(), _createElementBlock$5("span", _hoisted_38$1, _toDisplayString$4(row[col.key]), 1)) : (_openBlock$5(), _createElementBlock$5("span", _hoisted_39$1, "（空）"))
                          ])
                        ]);
                      }), 64))
                    ])
                  ]),
                  _: 2
                }, 1024),
                _createElementVNode$5("div", _hoisted_40$1, [
                  _createVNode$4(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    "prepend-icon": "mdi-content-duplicate",
                    onClick: ($event) => copy(JSON.stringify(row, null, 2))
                  }, {
                    default: _withCtx$4(() => [..._cache[27] || (_cache[27] = [
                      _createTextVNode$4(" 复制这一行 JSON ", -1)
                    ])]),
                    _: 1
                  }, 8, ["onClick"])
                ]),
                _createElementVNode$5("pre", _hoisted_41$1, _toDisplayString$4(JSON.stringify(row, null, 2)), 1)
              ])) : _createCommentVNode$4("", true)
            ]);
          }), 128))
        ])) : (_openBlock$5(), _createElementBlock$5("div", _hoisted_42$1, [
          _createVNode$4(_component_v_icon, {
            size: "26",
            icon: emptyIcon.value
          }, null, 8, ["icon"]),
          _createElementVNode$5("span", null, _toDisplayString$4(loading.value ? "读取中…" : extMode.value ? submitted.value ? `外部 id 表里没有匹配「${submitted.value}」的 ${extLabel.value}` : `${extLabel.value}还是空的：补过一次 id 就会有记录` : filtered.value ? "站点库里没有匹配的记录" : "站点库里还没有记录：识别 / 检索过一次就会有"), 1)
        ])),
        _createVNode$4(_component_v_dialog, {
          modelValue: confirmOpen.value,
          "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => confirmOpen.value = $event),
          "max-width": "460"
        }, {
          default: _withCtx$4(() => [
            _createVNode$4(_component_v_card, null, {
              default: _withCtx$4(() => [
                _createVNode$4(_component_v_card_title, { class: "text-body-1" }, {
                  default: _withCtx$4(() => [
                    _createTextVNode$4(_toDisplayString$4(pending.value ? "删除这一条 ID" : "清空整个 ID 库"), 1)
                  ]),
                  _: 1
                }),
                _createVNode$4(_component_v_card_text, {
                  class: "text-body-2",
                  style: { "white-space": "pre-line" }
                }, {
                  default: _withCtx$4(() => [
                    _createTextVNode$4(_toDisplayString$4(confirmText.value), 1)
                  ]),
                  _: 1
                }),
                _createVNode$4(_component_v_card_actions, null, {
                  default: _withCtx$4(() => [
                    _createVNode$4(_component_v_spacer),
                    _createVNode$4(_component_v_btn, {
                      variant: "text",
                      disabled: purging.value,
                      onClick: _cache[12] || (_cache[12] = ($event) => closeConfirm())
                    }, {
                      default: _withCtx$4(() => [..._cache[28] || (_cache[28] = [
                        _createTextVNode$4("取消", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode$4(_component_v_btn, {
                      color: "error",
                      variant: "flat",
                      loading: purging.value,
                      onClick: _cache[13] || (_cache[13] = ($event) => confirmPurge())
                    }, {
                      default: _withCtx$4(() => [
                        _createTextVNode$4(_toDisplayString$4(pending.value ? "删除" : "清空"), 1)
                      ]),
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
      ]);
    };
  }
});

const {defineComponent:_defineComponent$4} = await importShared('vue');

const {toDisplayString:_toDisplayString$3,createTextVNode:_createTextVNode$3,resolveComponent:_resolveComponent$3,withCtx:_withCtx$3,openBlock:_openBlock$4,createBlock:_createBlock$3,createCommentVNode:_createCommentVNode$3,renderList:_renderList$2,Fragment:_Fragment$2,createElementBlock:_createElementBlock$4,unref:_unref$2,createVNode:_createVNode$3,createElementVNode:_createElementVNode$4,withModifiers:_withModifiers} = await importShared('vue');

const _hoisted_1$4 = { class: "sdbs-page" };
const _hoisted_2$4 = { class: "sdbs-actions" };
const _hoisted_3$3 = { class: "sdbs-meta" };
const _hoisted_4$3 = { class: "sdbs-meta-item" };
const _hoisted_5$3 = { class: "sdbs-key" };
const _hoisted_6$3 = { class: "sdbs-meta-item" };
const _hoisted_7$3 = { class: "sdbs-meta-value" };
const _hoisted_8$3 = {
  key: 1,
  class: "sdbs-list"
};
const _hoisted_9$3 = { class: "sdbs-row-top" };
const _hoisted_10$2 = ["onClick"];
const _hoisted_11$2 = { class: "sdbs-row-main" };
const _hoisted_12$2 = { class: "sdbs-row-title" };
const _hoisted_13$2 = {
  key: 0,
  class: "sdbs-tag"
};
const _hoisted_14$2 = {
  key: 1,
  class: "sdbs-tag"
};
const _hoisted_15$2 = ["title"];
const _hoisted_16$2 = { class: "sdbs-key" };
const _hoisted_17$2 = {
  key: 0,
  class: "sdbs-tag"
};
const _hoisted_18$2 = {
  key: 0,
  class: "sdbs-expand"
};
const _hoisted_19$2 = { class: "sdbs-actions" };
const _hoisted_20$2 = { class: "sdbs-raw" };
const _hoisted_21$2 = {
  key: 2,
  class: "sdbs-empty"
};
const {computed: computed$3,onMounted: onMounted$2,ref: ref$3} = await importShared('vue');
const _sfc_main$4 = /* @__PURE__ */ _defineComponent$4({
  __name: "CachePanel",
  props: {
    api: {}
  },
  setup(__props, { expose: __expose }) {
    const props = __props;
    const LIMITS = [50, 100, 200, 500];
    const FALLBACK_REGIONS = Object.keys(REGION_LABELS);
    const regions = ref$3(FALLBACK_REGIONS);
    const region = ref$3("djbaike.detail");
    const limit = ref$3(100);
    const loading = ref$3(false);
    const loaded = ref$3(false);
    const items = ref$3([]);
    const q = ref$3("");
    let searchTimer = null;
    const error = ref$3("");
    const opened = ref$3("");
    const pending = ref$3(null);
    const confirmOpen = ref$3(false);
    const purging = ref$3(false);
    let token = 0;
    const confirmText = computed$3(() => {
      if (pending.value) {
        const realKey = pending.value.parent || pending.value.key;
        return `删掉 ${region.value} 里的这一条？

键：${realKey}${pending.value.parent ? "（整份数组缓存，一次删掉整条）" : ""}

只删这一份缓存，ID 库不动；下次用到它会重新抓页。`;
      }
      return `清空本插件的**全部缓存分区**（detail / person / douban / search / rank）？

ID 库不动。清空后首次识别会重新出网抓页，换来的是「全部按当下页面重刮」。`;
    });
    function isPlainObject(value) {
      return Object.prototype.toString.call(value) === "[object Object]";
    }
    function summary(item) {
      if (item.label) return item.label;
      const value = item.value;
      if (typeof value === "string") return value.slice(0, 80) || "（空字符串）";
      if (Array.isArray(value)) return `数组 · ${value.length} 项`;
      if (isPlainObject(value)) {
        const title = value.title || value.name || value.media_id;
        if (title) return String(title);
        const keys = Object.keys(value);
        return keys.length ? `{ ${keys.slice(0, 4).join(", ")}${keys.length > 4 ? " …" : ""} }` : "（空对象）";
      }
      if (value === null || value === void 0) return "（null）";
      return String(value);
    }
    function kindTag(item) {
      const value = item.value;
      if (!isPlainObject(value)) return "";
      return String(value.kind || value.type || value.media_source || "");
    }
    function entityTag(item) {
      const entity = entityOf(item.parent || item.key);
      return isKnownEntity(entity) ? entityLabel(entity) : "";
    }
    function rawJson(item) {
      try {
        return JSON.stringify(item.value, null, 2) ?? String(item.value);
      } catch {
        return String(item.value);
      }
    }
    async function copy(text) {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        error.value = "复制失败：浏览器拒绝了剪贴板权限";
      }
    }
    function toggle(item) {
      opened.value = opened.value === item.key ? "" : item.key;
    }
    const emptyHint = computed$3(() => {
      if (q.value.trim()) return `这个分区里没有匹配「${q.value.trim()}」的条目`;
      if (region.value === "djbaike.rank") {
        return "榜单区为空：打开面板里任一榜单后才会写入（一本榜一条缓存，值是该榜全部卡行）";
      }
      return "这个分区现在是空的（没抓过页，或已过 TTL）";
    });
    function search() {
      opened.value = "";
      void load();
    }
    function scheduleSearch() {
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(() => search(), 300);
    }
    async function load() {
      const seq = ++token;
      loading.value = true;
      error.value = "";
      try {
        const data = await fetchCacheItems(props, region.value, limit.value, q.value.trim());
        if (seq !== token) return;
        items.value = data?.items || [];
      } catch (err) {
        if (seq !== token) return;
        error.value = `读取缓存失败：${err instanceof Error ? err.message : String(err)}`;
        items.value = [];
      } finally {
        if (seq === token) {
          loading.value = false;
          loaded.value = true;
        }
      }
    }
    async function loadRegions() {
      try {
        const status = await fetchStatus(props);
        const list = status?.regions || [];
        if (list.length) {
          regions.value = list;
          if (!list.includes(region.value)) region.value = list[0];
        }
      } catch {
      }
    }
    function askDelete(item) {
      pending.value = item;
      confirmOpen.value = true;
    }
    function askClear() {
      pending.value = null;
      confirmOpen.value = true;
    }
    function closeConfirm() {
      if (purging.value) return;
      confirmOpen.value = false;
      pending.value = null;
    }
    async function confirmPurge() {
      const target = pending.value;
      purging.value = true;
      error.value = "";
      try {
        if (target) {
          const result = await deleteCacheItem(props, region.value, target.parent || target.key);
          if (!result?.ok) error.value = `删除未生效：${result?.detail || "键不存在或已过期"}`;
        } else {
          const result = await clearCache(props);
          if (!result?.ok) error.value = "清空未生效：后端未确认";
        }
        confirmOpen.value = false;
        pending.value = null;
        opened.value = "";
        await load();
      } catch (err) {
        error.value = `操作失败：${err instanceof Error ? err.message : String(err)}`;
      } finally {
        purging.value = false;
      }
    }
    __expose({ reload: load });
    onMounted$2(async () => {
      await loadRegions();
      await load();
    });
    return (_ctx, _cache) => {
      const _component_v_alert = _resolveComponent$3("v-alert");
      const _component_v_btn = _resolveComponent$3("v-btn");
      const _component_v_btn_toggle = _resolveComponent$3("v-btn-toggle");
      const _component_v_icon = _resolveComponent$3("v-icon");
      const _component_v_spacer = _resolveComponent$3("v-spacer");
      const _component_v_text_field = _resolveComponent$3("v-text-field");
      const _component_v_select = _resolveComponent$3("v-select");
      const _component_v_card_title = _resolveComponent$3("v-card-title");
      const _component_v_card_text = _resolveComponent$3("v-card-text");
      const _component_v_card_actions = _resolveComponent$3("v-card-actions");
      const _component_v_card = _resolveComponent$3("v-card");
      const _component_v_dialog = _resolveComponent$3("v-dialog");
      return _openBlock$4(), _createElementBlock$4("div", _hoisted_1$4, [
        error.value ? (_openBlock$4(), _createBlock$3(_component_v_alert, {
          key: 0,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-2"
        }, {
          default: _withCtx$3(() => [
            _createTextVNode$3(_toDisplayString$3(error.value), 1)
          ]),
          _: 1
        })) : _createCommentVNode$3("", true),
        _createElementVNode$4("div", _hoisted_2$4, [
          _createVNode$3(_component_v_btn_toggle, {
            modelValue: region.value,
            "onUpdate:modelValue": [
              _cache[0] || (_cache[0] = ($event) => region.value = $event),
              _cache[1] || (_cache[1] = ($event) => search())
            ],
            class: "sdbs-toggle",
            density: "compact",
            variant: "text",
            divided: "",
            mandatory: ""
          }, {
            default: _withCtx$3(() => [
              (_openBlock$4(true), _createElementBlock$4(_Fragment$2, null, _renderList$2(regions.value, (key) => {
                return _openBlock$4(), _createBlock$3(_component_v_btn, {
                  key,
                  size: "x-small",
                  value: key
                }, {
                  default: _withCtx$3(() => [
                    _createTextVNode$3(_toDisplayString$3(_unref$2(regionLabel)(key)), 1)
                  ]),
                  _: 2
                }, 1032, ["value"]);
              }), 128))
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]),
        _createElementVNode$4("div", _hoisted_3$3, [
          _createElementVNode$4("span", _hoisted_4$3, [
            _createVNode$3(_component_v_icon, {
              size: "14",
              icon: "mdi-database-outline"
            }),
            _createElementVNode$4("span", _hoisted_5$3, _toDisplayString$3(region.value || "—"), 1)
          ]),
          _createElementVNode$4("span", _hoisted_6$3, [
            _cache[11] || (_cache[11] = _createTextVNode$3(" 枚举 ", -1)),
            _createElementVNode$4("span", _hoisted_7$3, _toDisplayString$3(loaded.value ? items.value.length : "—"), 1),
            _cache[12] || (_cache[12] = _createTextVNode$3(" 条 ", -1))
          ]),
          _createVNode$3(_component_v_spacer),
          _createVNode$3(_component_v_text_field, {
            modelValue: q.value,
            "onUpdate:modelValue": [
              _cache[2] || (_cache[2] = ($event) => q.value = $event),
              _cache[3] || (_cache[3] = ($event) => scheduleSearch())
            ],
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            clearable: "",
            "prepend-inner-icon": "mdi-magnify",
            placeholder: "搜键 / 内容",
            style: { "max-width": "180px" },
            class: "mr-2"
          }, null, 8, ["modelValue"]),
          _createVNode$3(_component_v_select, {
            modelValue: limit.value,
            "onUpdate:modelValue": [
              _cache[4] || (_cache[4] = ($event) => limit.value = $event),
              _cache[5] || (_cache[5] = ($event) => search())
            ],
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            items: LIMITS,
            style: { "max-width": "96px" }
          }, null, 8, ["modelValue"]),
          _createVNode$3(_component_v_btn, {
            size: "x-small",
            variant: "text",
            "prepend-icon": "mdi-refresh",
            title: "重新枚举（缓存会自己过 TTL，这里只是重读一遍）",
            loading: loading.value,
            onClick: _cache[6] || (_cache[6] = ($event) => load())
          }, {
            default: _withCtx$3(() => [..._cache[13] || (_cache[13] = [
              _createTextVNode$3(" 刷新 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"]),
          _createVNode$3(_component_v_btn, {
            size: "x-small",
            variant: "text",
            color: "error",
            "prepend-icon": "mdi-delete-sweep-outline",
            title: "清空本插件全部缓存分区（ID 库不动）",
            onClick: _cache[7] || (_cache[7] = ($event) => askClear())
          }, {
            default: _withCtx$3(() => [..._cache[14] || (_cache[14] = [
              _createTextVNode$3(" 清空全部 ", -1)
            ])]),
            _: 1
          })
        ]),
        items.value.length ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_8$3, [
          (_openBlock$4(true), _createElementBlock$4(_Fragment$2, null, _renderList$2(items.value, (item) => {
            return _openBlock$4(), _createElementBlock$4("div", {
              key: item.key,
              class: "sdbs-row"
            }, [
              _createElementVNode$4("div", _hoisted_9$3, [
                _createElementVNode$4("button", {
                  type: "button",
                  class: "sdbs-row-head",
                  onClick: ($event) => toggle(item)
                }, [
                  _createVNode$3(_component_v_icon, {
                    size: "14",
                    icon: opened.value === item.key ? "mdi-chevron-down" : "mdi-chevron-right"
                  }, null, 8, ["icon"]),
                  _createElementVNode$4("span", _hoisted_11$2, [
                    _createElementVNode$4("span", _hoisted_12$2, _toDisplayString$3(summary(item)), 1),
                    entityTag(item) ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_13$2, _toDisplayString$3(entityTag(item)), 1)) : _createCommentVNode$3("", true),
                    kindTag(item) ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_14$2, _toDisplayString$3(kindTag(item)), 1)) : _createCommentVNode$3("", true)
                  ])
                ], 8, _hoisted_10$2),
                _createVNode$3(_component_v_btn, {
                  class: "sdbs-row-del",
                  size: "x-small",
                  variant: "text",
                  color: "error",
                  icon: "mdi-delete-outline",
                  title: `删掉 ${region.value} 里的这一条`,
                  onClick: _withModifiers(($event) => askDelete(item), ["stop"])
                }, null, 8, ["title", "onClick"])
              ]),
              _createElementVNode$4("div", {
                class: "sdbs-row-sub",
                title: `${region.value} · ${item.parent || item.key}`
              }, [
                _createElementVNode$4("span", _hoisted_16$2, _toDisplayString$3(item.key), 1),
                item.parent ? (_openBlock$4(), _createElementBlock$4("span", _hoisted_17$2, _toDisplayString$3(item.parent), 1)) : _createCommentVNode$3("", true)
              ], 8, _hoisted_15$2),
              opened.value === item.key ? (_openBlock$4(), _createElementBlock$4("div", _hoisted_18$2, [
                _createElementVNode$4("div", _hoisted_19$2, [
                  _createVNode$3(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    "prepend-icon": "mdi-content-duplicate",
                    onClick: ($event) => copy(rawJson(item))
                  }, {
                    default: _withCtx$3(() => [..._cache[15] || (_cache[15] = [
                      _createTextVNode$3(" 复制原始 JSON ", -1)
                    ])]),
                    _: 1
                  }, 8, ["onClick"]),
                  _createVNode$3(_component_v_btn, {
                    size: "x-small",
                    variant: "text",
                    "prepend-icon": "mdi-identifier",
                    onClick: ($event) => copy(item.key)
                  }, {
                    default: _withCtx$3(() => [..._cache[16] || (_cache[16] = [
                      _createTextVNode$3(" 复制键 ", -1)
                    ])]),
                    _: 1
                  }, 8, ["onClick"])
                ]),
                _createElementVNode$4("pre", _hoisted_20$2, _toDisplayString$3(rawJson(item)), 1)
              ])) : _createCommentVNode$3("", true)
            ]);
          }), 128))
        ])) : (_openBlock$4(), _createElementBlock$4("div", _hoisted_21$2, [
          _createVNode$3(_component_v_icon, {
            size: "26",
            icon: loading.value ? "mdi-progress-clock" : "mdi-database-off-outline"
          }, null, 8, ["icon"]),
          _createElementVNode$4("span", null, _toDisplayString$3(loading.value ? "读取中…" : emptyHint.value), 1)
        ])),
        _createVNode$3(_component_v_dialog, {
          modelValue: confirmOpen.value,
          "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => confirmOpen.value = $event),
          "max-width": "460"
        }, {
          default: _withCtx$3(() => [
            _createVNode$3(_component_v_card, null, {
              default: _withCtx$3(() => [
                _createVNode$3(_component_v_card_title, { class: "text-body-1" }, {
                  default: _withCtx$3(() => [
                    _createTextVNode$3(_toDisplayString$3(pending.value ? "删除这条缓存" : "清空全部缓存"), 1)
                  ]),
                  _: 1
                }),
                _createVNode$3(_component_v_card_text, {
                  class: "text-body-2",
                  style: { "white-space": "pre-line" }
                }, {
                  default: _withCtx$3(() => [
                    _createTextVNode$3(_toDisplayString$3(confirmText.value), 1)
                  ]),
                  _: 1
                }),
                _createVNode$3(_component_v_card_actions, null, {
                  default: _withCtx$3(() => [
                    _createVNode$3(_component_v_spacer),
                    _createVNode$3(_component_v_btn, {
                      variant: "text",
                      disabled: purging.value,
                      onClick: _cache[8] || (_cache[8] = ($event) => closeConfirm())
                    }, {
                      default: _withCtx$3(() => [..._cache[17] || (_cache[17] = [
                        _createTextVNode$3("取消", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode$3(_component_v_btn, {
                      color: "error",
                      variant: "flat",
                      loading: purging.value,
                      onClick: _cache[9] || (_cache[9] = ($event) => confirmPurge())
                    }, {
                      default: _withCtx$3(() => [
                        _createTextVNode$3(_toDisplayString$3(pending.value ? "删除" : "清空"), 1)
                      ]),
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
      ]);
    };
  }
});

const {defineComponent:_defineComponent$3} = await importShared('vue');

const {createElementVNode:_createElementVNode$3,renderList:_renderList$1,Fragment:_Fragment$1,openBlock:_openBlock$3,createElementBlock:_createElementBlock$3,toDisplayString:_toDisplayString$2,normalizeStyle:_normalizeStyle$1} = await importShared('vue');

const _hoisted_1$3 = { class: "sdbs-donut-wrap" };
const _hoisted_2$3 = ["aria-label"];
const _hoisted_3$2 = ["stroke", "stroke-dasharray", "stroke-dashoffset"];
const _hoisted_4$2 = {
  x: "70",
  y: "66",
  "text-anchor": "middle",
  class: "sdbs-donut-total"
};
const _hoisted_5$2 = {
  x: "70",
  y: "82",
  "text-anchor": "middle",
  class: "sdbs-donut-caption"
};
const _hoisted_6$2 = { class: "sdbs-legend" };
const _hoisted_7$2 = { class: "sdbs-legend-name" };
const _hoisted_8$2 = { class: "sdbs-legend-value" };
const _hoisted_9$2 = { class: "sdbs-legend-ratio" };
const {computed: computed$2} = await importShared('vue');
const RADIUS = 52;
const THICKNESS = 18;
const _sfc_main$3 = /* @__PURE__ */ _defineComponent$3({
  __name: "DonutChart",
  props: {
    rows: {},
    unit: { default: "条" },
    name: {},
    title: { default: "分布" }
  },
  setup(__props) {
    const props = __props;
    const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
    const PALETTE = [
      "#5B8FF9",
      "#61DDAA",
      "#F6BD16",
      "#7262FD",
      "#78D3F8",
      "#F6903D",
      "#9661BC",
      "#008685",
      "#F08BB4",
      "#65789B"
    ];
    const total = computed$2(
      () => props.rows.reduce((sum, row) => sum + Math.max(0, Number(row.count) || 0), 0)
    );
    const slices = computed$2(() => {
      const rows = props.rows.map((row) => ({ key: row.key, count: Math.max(0, Number(row.count) || 0) })).filter((row) => row.count > 0);
      const sum = rows.reduce((acc, row) => acc + row.count, 0);
      if (!sum) return [];
      let accumulated = 0;
      return rows.map((row, index) => {
        const length = row.count / sum * CIRCUMFERENCE;
        const offset = -(accumulated / sum) * CIRCUMFERENCE;
        accumulated += row.count;
        return {
          ...row,
          color: PALETTE[index % PALETTE.length],
          dash: `${length} ${CIRCUMFERENCE}`,
          offset,
          ratio: percent(row.count, sum)
        };
      });
    });
    return (_ctx, _cache) => {
      return _openBlock$3(), _createElementBlock$3("div", _hoisted_1$3, [
        (_openBlock$3(), _createElementBlock$3("svg", {
          class: "sdbs-donut",
          viewBox: "0 0 140 140",
          role: "img",
          "aria-label": `${__props.title}饼图`
        }, [
          _createElementVNode$3("circle", {
            cx: "70",
            cy: "70",
            r: RADIUS,
            fill: "none",
            stroke: "rgba(var(--v-theme-on-surface), 0.08)",
            "stroke-width": THICKNESS
          }),
          (_openBlock$3(true), _createElementBlock$3(_Fragment$1, null, _renderList$1(slices.value, (slice) => {
            return _openBlock$3(), _createElementBlock$3("circle", {
              key: slice.key,
              cx: "70",
              cy: "70",
              r: RADIUS,
              fill: "none",
              stroke: slice.color,
              "stroke-width": THICKNESS,
              "stroke-dasharray": slice.dash,
              "stroke-dashoffset": slice.offset,
              "stroke-linecap": "butt",
              transform: "rotate(-90 70 70)"
            }, [
              _createElementVNode$3("title", null, _toDisplayString$2(__props.name(slice.key)) + " " + _toDisplayString$2(slice.count) + " " + _toDisplayString$2(__props.unit) + "（" + _toDisplayString$2(slice.ratio) + "）", 1)
            ], 8, _hoisted_3$2);
          }), 128)),
          _createElementVNode$3("text", _hoisted_4$2, _toDisplayString$2(total.value), 1),
          _createElementVNode$3("text", _hoisted_5$2, _toDisplayString$2(__props.unit), 1)
        ], 8, _hoisted_2$3)),
        _createElementVNode$3("div", _hoisted_6$2, [
          (_openBlock$3(true), _createElementBlock$3(_Fragment$1, null, _renderList$1(slices.value, (slice) => {
            return _openBlock$3(), _createElementBlock$3("div", {
              key: slice.key,
              class: "sdbs-legend-row"
            }, [
              _createElementVNode$3("span", {
                class: "sdbs-swatch",
                style: _normalizeStyle$1({ backgroundColor: slice.color })
              }, null, 4),
              _createElementVNode$3("span", _hoisted_7$2, _toDisplayString$2(__props.name(slice.key)), 1),
              _createElementVNode$3("span", _hoisted_8$2, _toDisplayString$2(slice.count), 1),
              _createElementVNode$3("span", _hoisted_9$2, _toDisplayString$2(slice.ratio), 1)
            ]);
          }), 128))
        ])
      ]);
    };
  }
});

const {defineComponent:_defineComponent$2} = await importShared('vue');

const {toDisplayString:_toDisplayString$1,createTextVNode:_createTextVNode$2,resolveComponent:_resolveComponent$2,withCtx:_withCtx$2,openBlock:_openBlock$2,createBlock:_createBlock$2,createCommentVNode:_createCommentVNode$2,createElementVNode:_createElementVNode$2,unref:_unref$1,createVNode:_createVNode$2,createElementBlock:_createElementBlock$2} = await importShared('vue');

const _hoisted_1$2 = { class: "sdbs-page" };
const _hoisted_2$2 = { class: "sdbs-stats" };
const _hoisted_3$1 = { class: "sdbs-stat" };
const _hoisted_4$1 = { class: "sdbs-stat-value" };
const _hoisted_5$1 = { class: "sdbs-stat" };
const _hoisted_6$1 = { class: "sdbs-stat-value" };
const _hoisted_7$1 = { class: "sdbs-stat-hint" };
const _hoisted_8$1 = { class: "sdbs-stat" };
const _hoisted_9$1 = { class: "sdbs-stat-value" };
const _hoisted_10$1 = { class: "sdbs-stat" };
const _hoisted_11$1 = { class: "sdbs-stat-value" };
const _hoisted_12$1 = { class: "sdbs-stat-hint" };
const _hoisted_13$1 = { class: "sdbs-section" };
const _hoisted_14$1 = {
  key: 3,
  class: "sdbs-empty",
  style: { "padding": "12px" }
};
const _hoisted_15$1 = { class: "sdbs-section" };
const _hoisted_16$1 = {
  key: 5,
  class: "sdbs-empty",
  style: { "padding": "12px" }
};
const _hoisted_17$1 = { class: "sdbs-meta" };
const _hoisted_18$1 = { class: "sdbs-meta-item" };
const _hoisted_19$1 = { class: "sdbs-meta-value" };
const _hoisted_20$1 = { class: "sdbs-meta-item" };
const _hoisted_21$1 = { class: "sdbs-meta-value sdbs-key" };
const _hoisted_22$1 = { class: "sdbs-meta-item" };
const _hoisted_23$1 = ["href"];
const _hoisted_24$1 = { class: "sdbs-dim" };
const _hoisted_25$1 = { class: "sdbs-meta-item" };
const _hoisted_26$1 = { class: "sdbs-meta-value" };
const {computed: computed$1,onMounted: onMounted$1,ref: ref$2} = await importShared('vue');
const _sfc_main$2 = /* @__PURE__ */ _defineComponent$2({
  __name: "OverviewPanel",
  props: {
    api: {}
  },
  setup(__props, { expose: __expose }) {
    const props = __props;
    const loading = ref$2(false);
    const loaded = ref$2(false);
    const status = ref$2(null);
    const error = ref$2("");
    const doubanTotal = computed$1(() => {
      const counts = status.value?.by_entity || {};
      return Number(counts.douban || 0) + Number(counts.doubanp || 0);
    });
    const entityRows = computed$1(() => {
      const counts = status.value?.by_entity || {};
      const excludeManju = status.value?.exclude_manju !== false;
      const own = entityFiltersFor(siteKey.value, excludeManju);
      const known = own.map((key) => ({ key, count: Number(counts[key] || 0) }));
      const extra = Object.keys(counts).filter(
        (key) => !own.includes(key) && Number(counts[key] || 0) > 0 && !(excludeManju && MANJU_ENTITIES.includes(key))
      ).sort().map((key) => ({ key, count: Number(counts[key] || 0) }));
      return [...known, ...extra];
    });
    const cacheRows = computed$1(() => {
      const counts = status.value?.by_region || {};
      const known = Object.keys(REGION_LABELS);
      const declared = status.value?.regions || [];
      const extra = [...declared, ...Object.keys(counts)].filter((key) => !known.includes(key));
      return [...known, ...extra].map((key) => ({ key, count: Number(counts[key] || 0) }));
    });
    const cacheTotal = computed$1(() => cacheRows.value.reduce((sum, row) => sum + row.count, 0));
    const cachedRegions = computed$1(() => cacheRows.value.filter((row) => row.count > 0).length);
    const entityTotal = computed$1(() => entityRows.value.reduce((sum, row) => sum + row.count, 0));
    async function load() {
      loading.value = true;
      error.value = "";
      try {
        status.value = await fetchStatus(props);
        setSite(status.value?.site);
      } catch (err) {
        error.value = `读取状态失败：${err instanceof Error ? err.message : String(err)}`;
        status.value = null;
      } finally {
        loading.value = false;
        loaded.value = true;
      }
    }
    __expose({ reload: load });
    onMounted$1(() => {
      void load();
    });
    return (_ctx, _cache) => {
      const _component_v_alert = _resolveComponent$2("v-alert");
      const _component_v_icon = _resolveComponent$2("v-icon");
      const _component_v_spacer = _resolveComponent$2("v-spacer");
      const _component_v_divider = _resolveComponent$2("v-divider");
      const _component_v_btn = _resolveComponent$2("v-btn");
      return _openBlock$2(), _createElementBlock$2("div", _hoisted_1$2, [
        error.value ? (_openBlock$2(), _createBlock$2(_component_v_alert, {
          key: 0,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx$2(() => [
            _createTextVNode$2(_toDisplayString$1(error.value), 1)
          ]),
          _: 1
        })) : _createCommentVNode$2("", true),
        status.value?.enabled === false ? (_openBlock$2(), _createBlock$2(_component_v_alert, {
          key: 1,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx$2(() => [..._cache[1] || (_cache[1] = [
            _createTextVNode$2(" 插件当前未启用：识别、检索与探索页都不会生效（面板的管理操作仍可用）。 ", -1)
          ])]),
          _: 1
        })) : _createCommentVNode$2("", true),
        _createElementVNode$2("div", _hoisted_2$2, [
          _createElementVNode$2("div", _hoisted_3$1, [
            _cache[2] || (_cache[2] = _createElementVNode$2("div", { class: "sdbs-stat-label" }, "ID 库总条数", -1)),
            _createElementVNode$2("div", _hoisted_4$1, _toDisplayString$1(loaded.value ? status.value?.total ?? 0 : "—"), 1),
            _cache[3] || (_cache[3] = _createElementVNode$2("div", { class: "sdbs-stat-hint" }, "表内真实行数", -1))
          ]),
          _createElementVNode$2("div", _hoisted_5$1, [
            _cache[4] || (_cache[4] = _createElementVNode$2("div", { class: "sdbs-stat-label" }, "可检索条数", -1)),
            _createElementVNode$2("div", _hoisted_6$1, _toDisplayString$1(loaded.value ? status.value?.searchable ?? 0 : "—"), 1),
            _createElementVNode$2("div", _hoisted_7$1, _toDisplayString$1(status.value ? `占 ${_unref$1(percent)(status.value.searchable, status.value.total)}（name 非空）` : "name 非空的行"), 1)
          ]),
          _createElementVNode$2("div", _hoisted_8$1, [
            _cache[5] || (_cache[5] = _createElementVNode$2("div", { class: "sdbs-stat-label" }, "豆瓣兜底", -1)),
            _createElementVNode$2("div", _hoisted_9$1, _toDisplayString$1(loaded.value ? doubanTotal.value : "—"), 1),
            _cache[6] || (_cache[6] = _createElementVNode$2("div", { class: "sdbs-stat-hint" }, "百科未收录、走豆瓣出条", -1))
          ]),
          _createElementVNode$2("div", _hoisted_10$1, [
            _cache[7] || (_cache[7] = _createElementVNode$2("div", { class: "sdbs-stat-label" }, "缓存条数", -1)),
            _createElementVNode$2("div", _hoisted_11$1, _toDisplayString$1(loaded.value ? cacheTotal.value : "—"), 1),
            _createElementVNode$2("div", _hoisted_12$1, _toDisplayString$1(loaded.value ? `分布在 ${cachedRegions.value} / ${status.value?.regions?.length ?? 0} 个分区` : "各缓存 region 行数之和"), 1)
          ])
        ]),
        _createElementVNode$2("div", _hoisted_13$1, [
          _createVNode$2(_component_v_icon, {
            icon: "mdi-chart-donut",
            size: "16"
          }),
          _cache[8] || (_cache[8] = _createElementVNode$2("span", null, "实体分布", -1)),
          _createVNode$2(_component_v_spacer),
          _cache[9] || (_cache[9] = _createElementVNode$2("span", { class: "text-caption sdbs-dim" }, "按 media_id 前缀统计", -1))
        ]),
        entityTotal.value ? (_openBlock$2(), _createBlock$2(_sfc_main$3, {
          key: 2,
          rows: entityRows.value,
          unit: "条",
          name: _unref$1(entityLabel),
          title: "实体分布"
        }, null, 8, ["rows", "name"])) : (_openBlock$2(), _createElementBlock$2("div", _hoisted_14$1, [
          _createVNode$2(_component_v_icon, {
            size: "24",
            icon: "mdi-database-off-outline"
          }),
          _cache[10] || (_cache[10] = _createElementVNode$2("span", null, "还没有任何记录", -1))
        ])),
        _createElementVNode$2("div", _hoisted_15$1, [
          _createVNode$2(_component_v_icon, {
            icon: "mdi-chart-pie",
            size: "16"
          }),
          _cache[11] || (_cache[11] = _createElementVNode$2("span", null, "缓存分布", -1)),
          _createVNode$2(_component_v_spacer),
          _cache[12] || (_cache[12] = _createElementVNode$2("span", { class: "text-caption sdbs-dim" }, "按缓存 region 统计（会随 TTL 过期）", -1))
        ]),
        cacheTotal.value ? (_openBlock$2(), _createBlock$2(_sfc_main$3, {
          key: 4,
          rows: cacheRows.value,
          unit: "条",
          name: _unref$1(regionLabel),
          title: "缓存分布"
        }, null, 8, ["rows", "name"])) : (_openBlock$2(), _createElementBlock$2("div", _hoisted_16$1, [
          _createVNode$2(_component_v_icon, {
            size: "24",
            icon: "mdi-cached"
          }),
          _cache[13] || (_cache[13] = _createElementVNode$2("span", null, "缓存现在是空的（没抓过页，或已过 TTL）", -1))
        ])),
        _createVNode$2(_component_v_divider, { class: "my-3" }),
        _createElementVNode$2("div", _hoisted_17$1, [
          _createElementVNode$2("span", _hoisted_18$1, [
            _createVNode$2(_component_v_icon, {
              size: "14",
              icon: "mdi-tag-outline"
            }),
            _cache[14] || (_cache[14] = _createTextVNode$2(" 版本 ", -1)),
            _createElementVNode$2("span", _hoisted_19$1, _toDisplayString$1(status.value?.version || "—"), 1)
          ]),
          _createElementVNode$2("span", _hoisted_20$1, [
            _createVNode$2(_component_v_icon, {
              size: "14",
              icon: "mdi-database-search-outline"
            }),
            _cache[15] || (_cache[15] = _createTextVNode$2(" 来源标识 ", -1)),
            _createElementVNode$2("span", _hoisted_21$1, _toDisplayString$1(status.value?.media_source || "—"), 1)
          ]),
          _createElementVNode$2("span", _hoisted_22$1, [
            _createVNode$2(_component_v_icon, {
              size: "14",
              icon: "mdi-web"
            }),
            _cache[16] || (_cache[16] = _createTextVNode$2(" 站点 ", -1)),
            _createElementVNode$2("a", {
              class: "sdbs-key",
              href: _unref$1(siteInfo).base,
              target: "_blank",
              rel: "noreferrer noopener"
            }, _toDisplayString$1(_unref$1(siteInfo).host), 9, _hoisted_23$1),
            _createElementVNode$2("span", _hoisted_24$1, _toDisplayString$1(_unref$1(siteKey) === "org" ? "新站" : "老站"), 1)
          ]),
          _createElementVNode$2("span", _hoisted_25$1, [
            _createVNode$2(_component_v_icon, {
              size: "14",
              icon: "mdi-filter-remove-outline"
            }),
            _cache[17] || (_cache[17] = _createTextVNode$2(" 排除 ", -1)),
            _createElementVNode$2("span", _hoisted_26$1, _toDisplayString$1(status.value?.exclude_manju === false ? "未开启" : _unref$1(siteInfo).excludeName), 1)
          ]),
          _createVNode$2(_component_v_spacer),
          _createVNode$2(_component_v_btn, {
            size: "x-small",
            variant: "text",
            "prepend-icon": "mdi-refresh",
            loading: loading.value,
            onClick: _cache[0] || (_cache[0] = ($event) => load())
          }, {
            default: _withCtx$2(() => [..._cache[18] || (_cache[18] = [
              _createTextVNode$2(" 刷新 ", -1)
            ])]),
            _: 1
          }, 8, ["loading"])
        ])
      ]);
    };
  }
});

const {defineComponent:_defineComponent$1} = await importShared('vue');

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode$1,resolveComponent:_resolveComponent$1,withCtx:_withCtx$1,openBlock:_openBlock$1,createBlock:_createBlock$1,createCommentVNode:_createCommentVNode$1,unref:_unref,withKeys:_withKeys,createVNode:_createVNode$1,createElementVNode:_createElementVNode$1,Fragment:_Fragment,createElementBlock:_createElementBlock$1,normalizeStyle:_normalizeStyle,renderList:_renderList,normalizeClass:_normalizeClass} = await importShared('vue');

const _hoisted_1$1 = { class: "sdbs-page" };
const _hoisted_2$1 = { class: "sdbs-searchbox" };
const _hoisted_3 = { class: "sdbs-actions mt-2" };
const _hoisted_4 = { class: "text-caption sdbs-dim" };
const _hoisted_5 = {
  key: 1,
  class: "sdbs-actions mb-2 mt-2"
};
const _hoisted_6 = { class: "text-caption sdbs-dim" };
const _hoisted_7 = { class: "sdbs-section" };
const _hoisted_8 = {
  class: "d-flex",
  style: { "gap": "12px" }
};
const _hoisted_9 = { style: { "flex": "1 1 auto", "min-width": "0" } };
const _hoisted_10 = {
  class: "text-subtitle-1 d-flex align-center flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_11 = { class: "sdbs-tag" };
const _hoisted_12 = { class: "text-caption sdbs-dim" };
const _hoisted_13 = ["title"];
const _hoisted_14 = { class: "sdbs-key" };
const _hoisted_15 = {
  key: 0,
  class: "sdbs-key"
};
const _hoisted_16 = {
  key: 1,
  class: "sdbs-key"
};
const _hoisted_17 = {
  key: 0,
  class: "text-caption sdbs-dim mt-1",
  style: { "padding-inline-start": "0" }
};
const _hoisted_18 = {
  key: 1,
  class: "text-body-2 sdbs-clamp mt-2 sdbs-pre"
};
const _hoisted_19 = { class: "sdbs-section mt-3" };
const _hoisted_20 = { class: "sdbs-count" };
const _hoisted_21 = { class: "sdbs-grid" };
const _hoisted_22 = ["title", "onClick"];
const _hoisted_23 = {
  key: 0,
  class: "sdbs-mark"
};
const _hoisted_24 = {
  key: 1,
  class: "sdbs-mark"
};
const _hoisted_25 = { class: "sdbs-card-title" };
const _hoisted_26 = { class: "sdbs-card-sub" };
const _hoisted_27 = {
  key: 0,
  class: "sdbs-badge-douban"
};
const _hoisted_28 = { class: "sdbs-card-meta" };
const _hoisted_29 = { class: "sdbs-section" };
const _hoisted_30 = {
  class: "d-flex",
  style: { "gap": "12px" }
};
const _hoisted_31 = { style: { "flex": "1 1 auto", "min-width": "0" } };
const _hoisted_32 = {
  class: "text-subtitle-1 d-flex align-center flex-wrap",
  style: { "gap": "8px" }
};
const _hoisted_33 = { class: "sdbs-tag" };
const _hoisted_34 = ["title"];
const _hoisted_35 = { class: "sdbs-key" };
const _hoisted_36 = { key: 0 };
const _hoisted_37 = { key: 1 };
const _hoisted_38 = {
  key: 0,
  class: "text-caption sdbs-dim mt-1",
  style: { "padding-inline-start": "0" }
};
const _hoisted_39 = {
  key: 1,
  class: "text-body-2 sdbs-clamp mt-2 sdbs-pre"
};
const _hoisted_40 = { class: "sdbs-section mt-3" };
const _hoisted_41 = { class: "sdbs-count" };
const _hoisted_42 = { class: "sdbs-grid" };
const _hoisted_43 = ["title", "onClick"];
const _hoisted_44 = {
  key: 0,
  class: "sdbs-mark"
};
const _hoisted_45 = { class: "sdbs-card-title" };
const _hoisted_46 = { class: "sdbs-card-sub" };
const _hoisted_47 = { class: "sdbs-card-meta" };
const _hoisted_48 = { class: "sdbs-section" };
const _hoisted_49 = {
  class: "d-flex",
  style: { "gap": "12px" }
};
const _hoisted_50 = {
  key: 0,
  class: "sdbs-mark"
};
const _hoisted_51 = { style: { "flex": "1 1 auto", "min-width": "0" } };
const _hoisted_52 = { class: "text-subtitle-1" };
const _hoisted_53 = {
  class: "sdbs-meta",
  style: { "margin": "4px 0 6px" }
};
const _hoisted_54 = {
  key: 0,
  class: "sdbs-meta-item"
};
const _hoisted_55 = {
  key: 1,
  class: "sdbs-meta-item"
};
const _hoisted_56 = {
  key: 2,
  class: "sdbs-meta-item"
};
const _hoisted_57 = ["title"];
const _hoisted_58 = { class: "sdbs-key" };
const _hoisted_59 = { key: 0 };
const _hoisted_60 = { key: 1 };
const _hoisted_61 = {
  key: 0,
  class: "sdbs-chips mt-1"
};
const _hoisted_62 = ["title"];
const _hoisted_63 = {
  key: 1,
  class: "sdbs-chips mt-2"
};
const _hoisted_64 = {
  key: 2,
  class: "text-body-2 sdbs-clamp mt-2 sdbs-pre"
};
const _hoisted_65 = {
  key: 3,
  class: "sdbs-credit-row"
};
const _hoisted_66 = ["title", "onClick"];
const _hoisted_67 = {
  key: 4,
  class: "sdbs-credit-row"
};
const _hoisted_68 = ["title", "onClick"];
const _hoisted_69 = { class: "sdbs-section" };
const _hoisted_70 = { class: "sdbs-count" };
const _hoisted_71 = { class: "sdbs-grid" };
const _hoisted_72 = ["title", "onClick"];
const _hoisted_73 = {
  key: 0,
  class: "sdbs-mark"
};
const _hoisted_74 = { class: "sdbs-card-title" };
const _hoisted_75 = { class: "sdbs-card-sub" };
const _hoisted_76 = { class: "sdbs-card-meta" };
const _hoisted_77 = {
  key: 6,
  class: "sdbs-empty"
};
const _hoisted_78 = { class: "text-caption sdbs-dim" };
const _hoisted_79 = {
  key: 7,
  class: "sdbs-empty"
};
const _hoisted_80 = { class: "sdbs-actions" };
const _hoisted_81 = { class: "sdbs-raw" };
const {computed,ref: ref$1} = await importShared('vue');
const _sfc_main$1 = /* @__PURE__ */ _defineComponent$1({
  __name: "QueryPanel",
  props: {
    api: {}
  },
  setup(__props, { expose: __expose }) {
    const props = __props;
    const keyword = ref$1("");
    const activeId = ref$1("");
    const loading = ref$1(false);
    const error = ref$1("");
    const hasResult = ref$1(false);
    const remote = ref$1(true);
    const type = ref$1("");
    const single = ref$1(null);
    const list = ref$1([]);
    const person = ref$1(null);
    const novel = ref$1(null);
    const novelOfSingle = ref$1(null);
    const novelLoading = ref$1(false);
    const navStack = ref$1([]);
    const rawPayload = ref$1(null);
    const byId = computed(() => {
      if (activeId.value) return true;
      const text = keyword.value.trim();
      if (!text) return false;
      return text.includes(":") || /^\d+$/.test(text);
    });
    const canSubmit = computed(() => Boolean(keyword.value.trim()) && !loading.value);
    function genreNames(items) {
      const seen = /* @__PURE__ */ new Set();
      const out = [];
      for (const item of items || []) {
        const name = typeof item === "string" ? item.trim() : String(item?.name || "").trim();
        if (!name || seen.has(name)) continue;
        seen.add(name);
        out.push(name);
      }
      return out;
    }
    const genreList = computed(() => genreNames(single.value?.genres));
    const metricList = computed(() => {
      const facts = single.value?.classification_facts || {};
      const out = [];
      for (const key of METRIC_FACTS) {
        const raw = facts[key];
        const text = typeof raw === "string" ? raw.trim() : raw === null || raw === void 0 ? "" : String(raw);
        if (!text) continue;
        out.push({ key, label: factLabel(key), value: text, icon: factIcon(key) });
      }
      return out;
    });
    function personIdFromUrl(url) {
      const text = String(url || "");
      const douban = /douban\.com\/(?:celebrity|personage)\/(\d+)/.exec(text);
      if (douban) return `doubanp:${douban[1]}`;
      const org = /duanjubaike\.org\/[^/]+\/(actor)\/(\d+)/.exec(text);
      if (org) return `${org[1]}:${org[2]}`;
      const net = /[/](yanyuan|daoyan|bianju)\/info-(\d+)\.html/.exec(text);
      return net ? `${net[1]}:${net[2]}` : "";
    }
    function creditChips(items, withRole = false, limit = 0) {
      const list2 = items || [];
      const picked = limit > 0 ? list2.slice(0, limit) : list2;
      return picked.map((item) => {
        if (!item) return null;
        if (typeof item === "string") {
          const label = item.trim();
          return label ? { label, mediaId: "" } : null;
        }
        const name = String(item.name || "").trim();
        if (!name) return null;
        const role = String(item.character || "").trim();
        return {
          label: withRole && role ? `${name}（${role}）` : name,
          mediaId: personIdFromUrl(String(item.url || ""))
        };
      }).filter((chip) => Boolean(chip && chip.label));
    }
    const directorLinks = computed(() => creditChips(single.value?.directors));
    const actorLinks = computed(() => creditChips(single.value?.actors, true, 12));
    function currentEntry() {
      if (person.value)
        return { kind: "person", id: person.value.media_id, name: person.value.name, payload: person.value };
      if (novel.value)
        return { kind: "novel", id: novel.value.media_id, name: novel.value.name, payload: novel.value };
      if (single.value?.media_id) {
        return {
          kind: "work",
          id: String(single.value.media_id),
          name: String(single.value.title || ""),
          payload: single.value
        };
      }
      return null;
    }
    function pushNav() {
      const entry = currentEntry();
      if (!entry?.id) return;
      const top = navStack.value[navStack.value.length - 1];
      if (top && top.id === entry.id) return;
      navStack.value.push(entry);
    }
    function goBack() {
      const entry = navStack.value.pop();
      if (!entry) return;
      error.value = "";
      activeId.value = entry.id;
      keyword.value = entry.name || entry.id;
      if (entry.kind === "person") {
        if (entry.payload) {
          person.value = entry.payload;
          single.value = null;
          novel.value = null;
          novelOfSingle.value = null;
          list.value = [];
          rawPayload.value = null;
          hasResult.value = true;
        } else {
          void loadPerson(entry.id);
        }
        return;
      }
      if (entry.kind === "novel") {
        if (entry.payload) {
          novel.value = entry.payload;
          person.value = null;
          single.value = null;
          novelOfSingle.value = null;
          list.value = [];
          rawPayload.value = null;
          hasResult.value = true;
        } else {
          void loadNovel(entry.id);
        }
        return;
      }
      if (entry.payload) {
        single.value = entry.payload;
        person.value = null;
        novel.value = null;
        novelOfSingle.value = null;
        list.value = [];
        rawPayload.value = null;
        hasResult.value = true;
        if (single.value?.media_id) void probeNovel(single.value.media_id);
      } else {
        void run();
      }
    }
    function openPerson(mediaId) {
      if (!mediaId) return;
      pushNav();
      activeId.value = mediaId;
      void loadPerson(mediaId);
    }
    const rawText = computed(() => {
      try {
        return JSON.stringify(rawPayload.value, null, 2);
      } catch {
        return String(rawPayload.value);
      }
    });
    const rawSize = computed(() => `${rawText.value.length} 字符`);
    const rawSummary = computed(() => {
      const body = rawPayload.value;
      if (body === null || body === void 0) return "无响应";
      if (Array.isArray(body)) return `数组 ${body.length} 条（已解包）`;
      if (typeof body === "object") {
        const record = body;
        if ("success" in record && "data" in record) {
          const data = record.data;
          const size = Array.isArray(data) ? `${data.length} 条` : data === null ? "null" : typeof data;
          return `信封 success=${String(record.success)} data=${size}`;
        }
        return `对象（键：${Object.keys(record).slice(0, 4).join(",") || "空"}）`;
      }
      return `原始值 ${String(body)}`;
    });
    const detailHref = computed(() => {
      const item = single.value;
      if (!item?.media_id) return "";
      const query = new URLSearchParams();
      query.set("media_source", "djbaike");
      query.set("media_id", item.media_id);
      query.set("type", "电视剧");
      query.set("title", item.title || "");
      const base = typeof window === "undefined" ? "" : window.location.href.split("#")[0];
      return `${base}#/media?${query.toString()}`;
    });
    async function copy(text) {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        error.value = "复制失败：浏览器拒绝了剪贴板权限";
      }
    }
    function submitSearch() {
      activeId.value = "";
      navStack.value = [];
      void run();
    }
    function pick(item) {
      const id = String(item.media_id || "");
      if (!id) return;
      const name = String(item.title || "").trim();
      if (isPersonId(id)) {
        pushNav();
        activeId.value = id;
        keyword.value = name || id;
        void loadPerson(id);
        return;
      }
      pushNav();
      activeId.value = id;
      keyword.value = name || id;
      void run();
    }
    function openWork(work) {
      if (!work.media_id) return;
      pushNav();
      person.value = null;
      novel.value = null;
      activeId.value = work.media_id;
      keyword.value = String(work.name || "").trim() || work.media_id;
      void run();
    }
    function openAdaptation(work) {
      if (!work.media_id) return;
      pushNav();
      person.value = null;
      novel.value = null;
      activeId.value = work.media_id;
      keyword.value = String(work.name || "").trim() || work.media_id;
      void run();
    }
    async function loadNovel(mediaId) {
      loading.value = true;
      error.value = "";
      novel.value = null;
      person.value = null;
      single.value = null;
      novelOfSingle.value = null;
      list.value = [];
      rawPayload.value = null;
      try {
        const result = await fetchNovel(props, mediaId);
        if (result.novel) {
          novel.value = result.novel;
          keyword.value = String(result.novel.name || "").trim() || mediaId;
          activeId.value = mediaId;
        } else {
          error.value = `原著档案加载失败：${mediaId}`;
        }
        hasResult.value = true;
      } catch (err) {
        error.value = `查询失败：${err instanceof Error ? err.message : String(err)}`;
        hasResult.value = true;
      } finally {
        loading.value = false;
      }
    }
    function openNovelOfSingle() {
      const target = novelOfSingle.value;
      if (!target) return;
      pushNav();
      novel.value = target;
      person.value = null;
      single.value = null;
      rawPayload.value = null;
      keyword.value = String(target.name || "").trim() || target.media_id;
      activeId.value = target.media_id;
      hasResult.value = true;
    }
    async function probeNovel(mediaId) {
      novelLoading.value = true;
      try {
        const result = await fetchNovel(props, mediaId);
        if (single.value?.media_id === mediaId) {
          novelOfSingle.value = result.novel;
        }
      } catch {
      } finally {
        novelLoading.value = false;
      }
    }
    async function loadPerson(mediaId) {
      loading.value = true;
      error.value = "";
      person.value = null;
      novel.value = null;
      novelOfSingle.value = null;
      single.value = null;
      list.value = [];
      rawPayload.value = null;
      try {
        const result = await fetchPerson(props, mediaId);
        if (result.person) {
          person.value = result.person;
          keyword.value = String(result.person.name || "").trim() || mediaId;
          activeId.value = mediaId;
        } else {
          error.value = result.message || `取不到人物档案：${mediaId}`;
        }
        hasResult.value = true;
      } catch (err) {
        error.value = `人物档案读取失败：${err instanceof Error ? err.message : String(err)}`;
        hasResult.value = true;
      } finally {
        loading.value = false;
      }
    }
    async function run() {
      const text = (activeId.value || keyword.value).trim();
      if (!text) return;
      if (isPersonId(text)) {
        await loadPerson(text);
        return;
      }
      loading.value = true;
      error.value = "";
      single.value = null;
      list.value = [];
      person.value = null;
      novel.value = null;
      novelOfSingle.value = null;
      try {
        if (byId.value) {
          const body = await lookupRaw(props, { media_id: text });
          rawPayload.value = body;
          const payload = envelopeOf(body);
          const data = payload.data;
          if (Array.isArray(data)) {
            single.value = data[0] ?? null;
          } else {
            single.value = data && typeof data === "object" ? data : null;
          }
          if (!single.value && payload.success === false) {
            error.value = String(payload.message || "查询失败");
          }
          if (single.value?.media_id) {
            void probeNovel(single.value.media_id);
          }
        } else {
          const body = await lookupRaw(props, {
            name: text,
            remote: remote.value ? 1 : 0,
            type: type.value
          });
          rawPayload.value = body;
          const payload = envelopeOf(body);
          const data = payload.data;
          const rows = Array.isArray(data) ? data : [];
          list.value = rows;
          if (!rows.length && payload.success === false) {
            error.value = String(payload.message || "查询失败");
          }
          if (!rows.length && data && !Array.isArray(data) && typeof data === "object") {
            single.value = data;
          }
        }
        hasResult.value = true;
      } catch (err) {
        error.value = `查询失败：${err instanceof Error ? err.message : String(err)}`;
        hasResult.value = true;
      } finally {
        loading.value = false;
      }
    }
    __expose({
      query(mediaId) {
        keyword.value = mediaId;
        activeId.value = "";
        navStack.value = [];
        void run();
      }
    });
    return (_ctx, _cache) => {
      const _component_v_alert = _resolveComponent$1("v-alert");
      const _component_v_text_field = _resolveComponent$1("v-text-field");
      const _component_v_btn = _resolveComponent$1("v-btn");
      const _component_v_switch = _resolveComponent$1("v-switch");
      const _component_v_btn_toggle = _resolveComponent$1("v-btn-toggle");
      const _component_v_spacer = _resolveComponent$1("v-spacer");
      const _component_v_icon = _resolveComponent$1("v-icon");
      const _component_v_card = _resolveComponent$1("v-card");
      const _component_v_expansion_panel_title = _resolveComponent$1("v-expansion-panel-title");
      const _component_v_expansion_panel_text = _resolveComponent$1("v-expansion-panel-text");
      const _component_v_expansion_panel = _resolveComponent$1("v-expansion-panel");
      const _component_v_expansion_panels = _resolveComponent$1("v-expansion-panels");
      return _openBlock$1(), _createElementBlock$1("div", _hoisted_1$1, [
        error.value ? (_openBlock$1(), _createBlock$1(_component_v_alert, {
          key: 0,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-2"
        }, {
          default: _withCtx$1(() => [
            _createTextVNode$1(_toDisplayString(error.value), 1)
          ]),
          _: 1
        })) : _createCommentVNode$1("", true),
        _createElementVNode$1("div", _hoisted_2$1, [
          _createVNode$1(_component_v_text_field, {
            modelValue: keyword.value,
            "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => keyword.value = $event),
            class: "sdbs-search",
            variant: "outlined",
            density: "compact",
            "hide-details": "",
            clearable: "",
            "prepend-inner-icon": "mdi-magnify",
            placeholder: `media_id（${_unref(siteInfo).sampleId}）或剧名 / 演员名，例如：以爱为家`,
            onKeydown: _cache[1] || (_cache[1] = _withKeys(($event) => submitSearch(), ["enter"]))
          }, null, 8, ["modelValue", "placeholder"]),
          _createVNode$1(_component_v_btn, {
            class: "sdbs-search-btn",
            size: "small",
            color: "primary",
            variant: "tonal",
            loading: loading.value,
            disabled: !canSubmit.value,
            onClick: _cache[2] || (_cache[2] = ($event) => submitSearch())
          }, {
            default: _withCtx$1(() => [..._cache[13] || (_cache[13] = [
              _createTextVNode$1(" 查询 ", -1)
            ])]),
            _: 1
          }, 8, ["loading", "disabled"])
        ]),
        _createElementVNode$1("div", _hoisted_3, [
          _createVNode$1(_component_v_switch, {
            modelValue: remote.value,
            "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => remote.value = $event),
            class: "sdbs-switch",
            color: "primary",
            density: "compact",
            "hide-details": "",
            label: "联网补全",
            disabled: byId.value,
            title: byId.value ? "按 media_id 直查本来就会按需抓页，这个开关只影响按名搜索" : "勾上才走站内搜索 / 豆瓣（会出网）"
          }, null, 8, ["modelValue", "disabled", "title"]),
          _createVNode$1(_component_v_btn_toggle, {
            modelValue: type.value,
            "onUpdate:modelValue": [
              _cache[4] || (_cache[4] = ($event) => type.value = $event),
              _cache[5] || (_cache[5] = ($event) => hasResult.value && run())
            ],
            class: "sdbs-toggle",
            density: "compact",
            variant: "text",
            divided: "",
            mandatory: "",
            disabled: byId.value
          }, {
            default: _withCtx$1(() => [
              _createVNode$1(_component_v_btn, {
                size: "x-small",
                value: ""
              }, {
                default: _withCtx$1(() => [..._cache[14] || (_cache[14] = [
                  _createTextVNode$1("全部", -1)
                ])]),
                _: 1
              }),
              _createVNode$1(_component_v_btn, {
                size: "x-small",
                value: "work"
              }, {
                default: _withCtx$1(() => [..._cache[15] || (_cache[15] = [
                  _createTextVNode$1("作品", -1)
                ])]),
                _: 1
              }),
              _createVNode$1(_component_v_btn, {
                size: "x-small",
                value: "person"
              }, {
                default: _withCtx$1(() => [..._cache[16] || (_cache[16] = [
                  _createTextVNode$1("人物", -1)
                ])]),
                _: 1
              })
            ]),
            _: 1
          }, 8, ["modelValue", "disabled"]),
          _createVNode$1(_component_v_spacer),
          _createElementVNode$1("span", _hoisted_4, _toDisplayString(byId.value ? "按 id 直查（命中缓存则零请求）" : "按名字搜索候选"), 1)
        ]),
        navStack.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_5, [
          _createVNode$1(_component_v_btn, {
            size: "small",
            variant: "tonal",
            color: "primary",
            "prepend-icon": "mdi-arrow-left",
            onClick: _cache[6] || (_cache[6] = ($event) => goBack())
          }, {
            default: _withCtx$1(() => [
              _createTextVNode$1(" 返回「" + _toDisplayString(navStack.value[navStack.value.length - 1].name || navStack.value[navStack.value.length - 1].id) + "」 ", 1)
            ]),
            _: 1
          }),
          _createElementVNode$1("span", _hoisted_6, [
            _createTextVNode$1(_toDisplayString(person.value ? "正在看人物档案" : novel.value ? "正在看原著档案" : "正在看作品详情") + " ", 1),
            navStack.value.length > 1 ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 0 }, [
              _createTextVNode$1("· 还有 " + _toDisplayString(navStack.value.length - 1) + " 层可返回", 1)
            ], 64)) : _createCommentVNode$1("", true)
          ])
        ])) : _createCommentVNode$1("", true),
        person.value ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 2 }, [
          _createElementVNode$1("div", _hoisted_7, [
            _createVNode$1(_component_v_icon, {
              icon: "mdi-account-star-outline",
              size: "16"
            }),
            _cache[19] || (_cache[19] = _createElementVNode$1("span", null, "人物档案", -1)),
            _createVNode$1(_component_v_spacer),
            _createVNode$1(_component_v_btn, {
              size: "x-small",
              variant: "text",
              "prepend-icon": "mdi-content-duplicate",
              onClick: _cache[7] || (_cache[7] = ($event) => copy(JSON.stringify(person.value, null, 2)))
            }, {
              default: _withCtx$1(() => [..._cache[17] || (_cache[17] = [
                _createTextVNode$1(" 复制 JSON ", -1)
              ])]),
              _: 1
            }),
            _createVNode$1(_component_v_btn, {
              size: "x-small",
              variant: "text",
              color: "primary",
              "prepend-icon": "mdi-open-in-new",
              href: person.value.detail_url || void 0,
              target: "_blank",
              rel: "noreferrer noopener",
              disabled: !person.value.detail_url
            }, {
              default: _withCtx$1(() => [..._cache[18] || (_cache[18] = [
                _createTextVNode$1(" 站点页面 ", -1)
              ])]),
              _: 1
            }, 8, ["href", "disabled"])
          ]),
          _createVNode$1(_component_v_card, {
            variant: "outlined",
            class: "pa-3"
          }, {
            default: _withCtx$1(() => [
              _createElementVNode$1("div", _hoisted_8, [
                _createElementVNode$1("div", {
                  class: "sdbs-avatar-box",
                  style: _normalizeStyle(person.value.avatar ? { backgroundImage: `url(${_unref(proxyImage)(person.value.avatar)})` } : void 0)
                }, null, 4),
                _createElementVNode$1("div", _hoisted_9, [
                  _createElementVNode$1("div", _hoisted_10, [
                    _createElementVNode$1("span", null, _toDisplayString(person.value.name), 1),
                    _createElementVNode$1("span", _hoisted_11, _toDisplayString(person.value.role), 1),
                    _createElementVNode$1("span", _hoisted_12, "作品 " + _toDisplayString(person.value.work_count) + " 部", 1)
                  ]),
                  _createElementVNode$1("div", {
                    class: "sdbs-row-sub mt-1",
                    style: { "padding-inline-start": "0" },
                    title: person.value.media_id
                  }, [
                    _createElementVNode$1("span", _hoisted_14, _toDisplayString(person.value.media_id), 1),
                    person.value.douban_id ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_15, "· " + _toDisplayString(person.value.douban_id), 1)) : _createCommentVNode$1("", true),
                    person.value.tmdb_id ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_16, "· " + _toDisplayString(person.value.tmdb_id), 1)) : _createCommentVNode$1("", true)
                  ], 8, _hoisted_13),
                  person.value.douban_info?.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_17, _toDisplayString(person.value.douban_info.join("　")), 1)) : _createCommentVNode$1("", true),
                  person.value.intro ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_18, _toDisplayString(person.value.intro), 1)) : _createCommentVNode$1("", true)
                ])
              ])
            ]),
            _: 1
          }),
          person.value.works?.length ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 0 }, [
            _createElementVNode$1("div", _hoisted_19, [
              _createVNode$1(_component_v_icon, {
                icon: "mdi-movie-multiple-outline",
                size: "16"
              }),
              _cache[20] || (_cache[20] = _createElementVNode$1("span", null, "作品", -1)),
              _createElementVNode$1("span", _hoisted_20, _toDisplayString(person.value.works.length), 1),
              _createVNode$1(_component_v_spacer),
              _cache[21] || (_cache[21] = _createElementVNode$1("span", { class: "text-caption sdbs-dim" }, "点海报查这部片的详情 · 含豆瓣合并来源（角标「豆瓣」）", -1))
            ]),
            _createElementVNode$1("div", _hoisted_21, [
              (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(person.value.works, (work) => {
                return _openBlock$1(), _createElementBlock$1("div", {
                  key: work.media_id,
                  class: "sdbs-item sdbs-card",
                  title: `${work.name || work.media_id}${work.date ? " · " + work.date : work.year ? " · " + work.year : ""}${work.episodes ? " · " + work.episodes + " 集" : ""}`,
                  onClick: ($event) => openWork(work)
                }, [
                  _createElementVNode$1("div", {
                    class: "sdbs-poster",
                    style: _normalizeStyle(work.poster ? { backgroundImage: `url(${_unref(proxyImage)(work.poster)})` } : void 0)
                  }, [
                    work.episodes ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_23, _toDisplayString(work.episodes) + " 集", 1)) : work.rating ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_24, _toDisplayString(Number(work.rating).toFixed(1)), 1)) : _createCommentVNode$1("", true)
                  ], 4),
                  _createElementVNode$1("div", _hoisted_25, _toDisplayString(work.name || work.media_id), 1),
                  _createElementVNode$1("div", _hoisted_26, [
                    work.origin === "douban" ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_27, "豆瓣")) : _createCommentVNode$1("", true),
                    _createTextVNode$1(" " + _toDisplayString(work.date || work.year || work.kind || "—"), 1)
                  ]),
                  _createElementVNode$1("div", _hoisted_28, _toDisplayString((work.tags || []).slice(0, 2).join(" / ") || " "), 1)
                ], 8, _hoisted_22);
              }), 128))
            ])
          ], 64)) : _createCommentVNode$1("", true)
        ], 64)) : novel.value ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 3 }, [
          _createElementVNode$1("div", _hoisted_29, [
            _createVNode$1(_component_v_icon, {
              icon: "mdi-book-open-variant",
              size: "16"
            }),
            _cache[24] || (_cache[24] = _createElementVNode$1("span", null, "原著档案", -1)),
            _createVNode$1(_component_v_spacer),
            _createVNode$1(_component_v_btn, {
              size: "x-small",
              variant: "text",
              "prepend-icon": "mdi-content-duplicate",
              onClick: _cache[8] || (_cache[8] = ($event) => copy(JSON.stringify(novel.value, null, 2)))
            }, {
              default: _withCtx$1(() => [..._cache[22] || (_cache[22] = [
                _createTextVNode$1(" 复制 JSON ", -1)
              ])]),
              _: 1
            }),
            _createVNode$1(_component_v_btn, {
              size: "x-small",
              variant: "text",
              color: "primary",
              "prepend-icon": "mdi-open-in-new",
              href: novel.value.detail_url || void 0,
              target: "_blank",
              rel: "noreferrer noopener",
              disabled: !novel.value.detail_url
            }, {
              default: _withCtx$1(() => [..._cache[23] || (_cache[23] = [
                _createTextVNode$1(" 站点页面 ", -1)
              ])]),
              _: 1
            }, 8, ["href", "disabled"])
          ]),
          _createVNode$1(_component_v_card, {
            variant: "outlined",
            class: "pa-3"
          }, {
            default: _withCtx$1(() => [
              _createElementVNode$1("div", _hoisted_30, [
                _createElementVNode$1("div", {
                  class: "sdbs-avatar-box",
                  style: _normalizeStyle(novel.value.poster ? { backgroundImage: `url(${_unref(proxyImage)(novel.value.poster)})` } : void 0)
                }, null, 4),
                _createElementVNode$1("div", _hoisted_31, [
                  _createElementVNode$1("div", _hoisted_32, [
                    _createElementVNode$1("span", null, "《" + _toDisplayString(novel.value.name) + "》", 1),
                    _createElementVNode$1("span", _hoisted_33, _toDisplayString(novel.value.kind), 1)
                  ]),
                  _createElementVNode$1("div", {
                    class: "sdbs-row-sub mt-1",
                    style: { "padding-inline-start": "0" },
                    title: novel.value.media_id
                  }, [
                    _createElementVNode$1("span", _hoisted_35, _toDisplayString(novel.value.media_id), 1),
                    novel.value.author ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_36, " · 作者：" + _toDisplayString(novel.value.author), 1)) : _createCommentVNode$1("", true),
                    novel.value.words ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_37, " · " + _toDisplayString(novel.value.words), 1)) : _createCommentVNode$1("", true)
                  ], 8, _hoisted_34),
                  novel.value.aka ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_38, " 又名：《" + _toDisplayString(novel.value.aka) + "》 ", 1)) : _createCommentVNode$1("", true),
                  novel.value.overview ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_39, _toDisplayString(novel.value.overview), 1)) : _createCommentVNode$1("", true)
                ])
              ])
            ]),
            _: 1
          }),
          novel.value.adaptations?.length ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 0 }, [
            _createElementVNode$1("div", _hoisted_40, [
              _createVNode$1(_component_v_icon, {
                icon: "mdi-movie-multiple-outline",
                size: "16"
              }),
              _cache[25] || (_cache[25] = _createElementVNode$1("span", null, "改编作品", -1)),
              _createElementVNode$1("span", _hoisted_41, _toDisplayString(novel.value.adaptation_count || novel.value.adaptations.length), 1),
              _createVNode$1(_component_v_spacer),
              _cache[26] || (_cache[26] = _createElementVNode$1("span", { class: "text-caption sdbs-dim" }, "改编自本原著的剧，点海报看详情", -1))
            ]),
            _createElementVNode$1("div", _hoisted_42, [
              (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(novel.value.adaptations, (work) => {
                return _openBlock$1(), _createElementBlock$1("div", {
                  key: work.media_id,
                  class: "sdbs-item sdbs-card",
                  title: `${work.name || work.media_id}${work.date ? " · " + work.date : ""}${work.episodes ? " · " + work.episodes + " 集" : ""}`,
                  onClick: ($event) => openAdaptation(work)
                }, [
                  _createElementVNode$1("div", {
                    class: "sdbs-poster",
                    style: _normalizeStyle(work.poster ? { backgroundImage: `url(${_unref(proxyImage)(work.poster)})` } : void 0)
                  }, [
                    work.episodes ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_44, _toDisplayString(work.episodes) + " 集", 1)) : _createCommentVNode$1("", true)
                  ], 4),
                  _createElementVNode$1("div", _hoisted_45, _toDisplayString(work.name || work.media_id), 1),
                  _createElementVNode$1("div", _hoisted_46, _toDisplayString(work.date || work.kind || "—"), 1),
                  _createElementVNode$1("div", _hoisted_47, _toDisplayString(work.kind || " "), 1)
                ], 8, _hoisted_43);
              }), 128))
            ])
          ], 64)) : _createCommentVNode$1("", true)
        ], 64)) : single.value ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 4 }, [
          _createElementVNode$1("div", _hoisted_48, [
            _createVNode$1(_component_v_icon, {
              icon: "mdi-movie-open-outline",
              size: "16"
            }),
            _cache[30] || (_cache[30] = _createElementVNode$1("span", null, "详情", -1)),
            _createVNode$1(_component_v_spacer),
            _createVNode$1(_component_v_btn, {
              size: "x-small",
              variant: "text",
              "prepend-icon": "mdi-content-duplicate",
              onClick: _cache[9] || (_cache[9] = ($event) => copy(JSON.stringify(single.value, null, 2)))
            }, {
              default: _withCtx$1(() => [..._cache[27] || (_cache[27] = [
                _createTextVNode$1(" 复制 JSON ", -1)
              ])]),
              _: 1
            }),
            _createVNode$1(_component_v_btn, {
              size: "x-small",
              variant: "text",
              color: "primary",
              "prepend-icon": "mdi-open-in-new",
              disabled: !detailHref.value,
              title: "在宿主的媒体详情页打开（新标签）",
              href: detailHref.value || void 0,
              target: "_blank",
              rel: "noreferrer noopener"
            }, {
              default: _withCtx$1(() => [..._cache[28] || (_cache[28] = [
                _createTextVNode$1(" 宿主详情页 ", -1)
              ])]),
              _: 1
            }, 8, ["disabled", "href"]),
            novelOfSingle.value ? (_openBlock$1(), _createBlock$1(_component_v_btn, {
              key: 0,
              size: "x-small",
              variant: "tonal",
              color: "primary",
              "prepend-icon": "mdi-book-open-variant",
              loading: novelLoading.value,
              onClick: _cache[10] || (_cache[10] = ($event) => openNovelOfSingle())
            }, {
              default: _withCtx$1(() => [..._cache[29] || (_cache[29] = [
                _createTextVNode$1(" 改编档案 ", -1)
              ])]),
              _: 1
            }, 8, ["loading"])) : _createCommentVNode$1("", true)
          ]),
          _createVNode$1(_component_v_card, {
            variant: "outlined",
            class: "pa-3"
          }, {
            default: _withCtx$1(() => [
              _createElementVNode$1("div", _hoisted_49, [
                _createElementVNode$1("div", {
                  class: "sdbs-poster",
                  style: _normalizeStyle([{ "flex": "0 0 auto", "width": "104px" }, single.value.poster_path ? { backgroundImage: `url(${_unref(proxyImage)(single.value.poster_path)})` } : void 0])
                }, [
                  single.value.vote_average ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_50, _toDisplayString(Number(single.value.vote_average).toFixed(1)), 1)) : _createCommentVNode$1("", true)
                ], 4),
                _createElementVNode$1("div", _hoisted_51, [
                  _createElementVNode$1("div", _hoisted_52, _toDisplayString(single.value.title || "（无标题）"), 1),
                  _createElementVNode$1("div", _hoisted_53, [
                    single.value.year ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_54, [
                      _createVNode$1(_component_v_icon, {
                        size: "14",
                        icon: "mdi-calendar"
                      }),
                      _createTextVNode$1(_toDisplayString(single.value.year), 1)
                    ])) : _createCommentVNode$1("", true),
                    single.value.number_of_episodes ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_55, [
                      _createVNode$1(_component_v_icon, {
                        size: "14",
                        icon: "mdi-playlist-play"
                      }),
                      _createTextVNode$1(_toDisplayString(single.value.number_of_episodes) + " 集 ", 1)
                    ])) : _createCommentVNode$1("", true),
                    single.value.type ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_56, [
                      _createVNode$1(_component_v_icon, {
                        size: "14",
                        icon: "mdi-tag-outline"
                      }),
                      _createTextVNode$1(_toDisplayString(single.value.type), 1)
                    ])) : _createCommentVNode$1("", true)
                  ]),
                  _createElementVNode$1("div", {
                    class: "sdbs-row-sub",
                    style: { "padding-inline-start": "0" },
                    title: single.value.media_id || ""
                  }, [
                    _createElementVNode$1("span", _hoisted_58, _toDisplayString(single.value.media_id || "—"), 1),
                    single.value.douban_id ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_59, " · 豆瓣 " + _toDisplayString(single.value.douban_id), 1)) : _createCommentVNode$1("", true),
                    single.value.tmdb_id ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_60, " · TMDB " + _toDisplayString(single.value.tmdb_id), 1)) : _createCommentVNode$1("", true)
                  ], 8, _hoisted_57),
                  metricList.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_61, [
                    (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(metricList.value, (metric) => {
                      return _openBlock$1(), _createElementBlock$1("span", {
                        key: metric.key,
                        class: "sdbs-metric",
                        title: metric.key
                      }, [
                        _createVNode$1(_component_v_icon, {
                          size: "12",
                          icon: metric.icon
                        }, null, 8, ["icon"]),
                        _createTextVNode$1(_toDisplayString(metric.label) + " " + _toDisplayString(metric.value), 1)
                      ], 8, _hoisted_62);
                    }), 128))
                  ])) : _createCommentVNode$1("", true),
                  genreList.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_63, [
                    (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(genreList.value, (genre) => {
                      return _openBlock$1(), _createElementBlock$1("span", {
                        key: genre,
                        class: "sdbs-tag"
                      }, _toDisplayString(genre), 1);
                    }), 128))
                  ])) : _createCommentVNode$1("", true),
                  single.value.overview ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_64, _toDisplayString(single.value.overview), 1)) : _createCommentVNode$1("", true),
                  directorLinks.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_65, [
                    _cache[31] || (_cache[31] = _createElementVNode$1("span", { class: "sdbs-credit-label" }, "导演", -1)),
                    (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(directorLinks.value, (credit, index) => {
                      return _openBlock$1(), _createElementBlock$1("span", {
                        key: `director-${index}-${credit.label}`,
                        class: _normalizeClass(["sdbs-credit", { "sdbs-credit-click": credit.mediaId }]),
                        title: credit.mediaId || "站点未给出人物页链接",
                        onClick: ($event) => openPerson(credit.mediaId)
                      }, _toDisplayString(credit.label), 11, _hoisted_66);
                    }), 128))
                  ])) : _createCommentVNode$1("", true),
                  actorLinks.value.length ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_67, [
                    _cache[32] || (_cache[32] = _createElementVNode$1("span", { class: "sdbs-credit-label" }, "演员", -1)),
                    (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(actorLinks.value, (credit, index) => {
                      return _openBlock$1(), _createElementBlock$1("span", {
                        key: `actor-${index}-${credit.label}`,
                        class: _normalizeClass(["sdbs-credit", { "sdbs-credit-click": credit.mediaId }]),
                        title: credit.mediaId || "站点未给出人物页链接",
                        onClick: ($event) => openPerson(credit.mediaId)
                      }, _toDisplayString(credit.label), 11, _hoisted_68);
                    }), 128))
                  ])) : _createCommentVNode$1("", true)
                ])
              ])
            ]),
            _: 1
          })
        ], 64)) : list.value.length ? (_openBlock$1(), _createElementBlock$1(_Fragment, { key: 5 }, [
          _createElementVNode$1("div", _hoisted_69, [
            _createVNode$1(_component_v_icon, {
              icon: "mdi-format-list-bulleted",
              size: "16"
            }),
            _cache[33] || (_cache[33] = _createElementVNode$1("span", null, "候选", -1)),
            _createElementVNode$1("span", _hoisted_70, _toDisplayString(list.value.length), 1),
            _createVNode$1(_component_v_spacer),
            _cache[34] || (_cache[34] = _createElementVNode$1("span", { class: "text-caption sdbs-dim" }, "同名多条原样列出，识别时才按规则收敛", -1))
          ]),
          _createElementVNode$1("div", _hoisted_71, [
            (_openBlock$1(true), _createElementBlock$1(_Fragment, null, _renderList(list.value, (item) => {
              return _openBlock$1(), _createElementBlock$1("div", {
                key: item.media_id || item.title,
                class: "sdbs-item",
                style: { "cursor": "pointer" },
                title: item.media_id || "",
                onClick: ($event) => pick(item)
              }, [
                _createElementVNode$1("div", {
                  class: "sdbs-poster",
                  style: _normalizeStyle(item.poster_path ? { backgroundImage: `url(${_unref(proxyImage)(item.poster_path)})` } : void 0)
                }, [
                  item.vote_average ? (_openBlock$1(), _createElementBlock$1("span", _hoisted_73, _toDisplayString(Number(item.vote_average).toFixed(1)), 1)) : _createCommentVNode$1("", true)
                ], 4),
                _createElementVNode$1("div", _hoisted_74, _toDisplayString(item.title || "（无标题）"), 1),
                _createElementVNode$1("div", _hoisted_75, _toDisplayString([item.year, item.number_of_episodes ? `${item.number_of_episodes} 集` : ""].filter(Boolean).join(" · ") || "—"), 1),
                _createElementVNode$1("div", _hoisted_76, _toDisplayString(item.media_id || ""), 1)
              ], 8, _hoisted_72);
            }), 128))
          ])
        ], 64)) : hasResult.value && !loading.value ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_77, [
          _createVNode$1(_component_v_icon, {
            size: "26",
            icon: "mdi-magnify-close"
          }),
          _createElementVNode$1("span", null, " 没有结果。按名搜索时：" + _toDisplayString(remote.value ? "本地 → 站内搜索 → 豆瓣都没命中" : "只查了本地库，把「联网补全」打开可再试站内搜索"), 1),
          _createElementVNode$1("span", _hoisted_78, "接口返回：" + _toDisplayString(rawSummary.value), 1)
        ])) : !hasResult.value ? (_openBlock$1(), _createElementBlock$1("div", _hoisted_79, [
          _createVNode$1(_component_v_icon, {
            size: "26",
            icon: "mdi-magnify"
          }),
          _cache[35] || (_cache[35] = _createElementVNode$1("span", null, "输入 media_id 查单条详情，或输入剧名 / 演员名出候选", -1))
        ])) : _createCommentVNode$1("", true),
        rawPayload.value ? (_openBlock$1(), _createBlock$1(_component_v_expansion_panels, {
          key: 8,
          variant: "accordion",
          class: "mt-3"
        }, {
          default: _withCtx$1(() => [
            _createVNode$1(_component_v_expansion_panel, null, {
              default: _withCtx$1(() => [
                _createVNode$1(_component_v_expansion_panel_title, { class: "text-caption" }, {
                  default: _withCtx$1(() => [..._cache[36] || (_cache[36] = [
                    _createTextVNode$1(" 原始响应（含 success / message 信封） ", -1)
                  ])]),
                  _: 1
                }),
                _createVNode$1(_component_v_expansion_panel_text, null, {
                  default: _withCtx$1(() => [
                    _createElementVNode$1("div", _hoisted_80, [
                      _createVNode$1(_component_v_btn, {
                        size: "x-small",
                        variant: "text",
                        "prepend-icon": "mdi-content-duplicate",
                        onClick: _cache[11] || (_cache[11] = ($event) => copy(rawText.value))
                      }, {
                        default: _withCtx$1(() => [..._cache[37] || (_cache[37] = [
                          _createTextVNode$1(" 复制全文 ", -1)
                        ])]),
                        _: 1
                      }),
                      _createVNode$1(_component_v_btn, {
                        size: "x-small",
                        variant: "text",
                        "prepend-icon": "mdi-code-json",
                        onClick: _cache[12] || (_cache[12] = ($event) => copy(rawText.value))
                      }, {
                        default: _withCtx$1(() => [
                          _createTextVNode$1(_toDisplayString(rawSize.value), 1)
                        ]),
                        _: 1
                      })
                    ]),
                    _createElementVNode$1("pre", _hoisted_81, _toDisplayString(rawText.value), 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })) : _createCommentVNode$1("", true)
      ]);
    };
  }
});

const {defineComponent:_defineComponent} = await importShared('vue');

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,vShow:_vShow,withDirectives:_withDirectives,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,createElementBlock:_createElementBlock} = await importShared('vue');

const _hoisted_1 = { class: "sdbs-tabs" };
const _hoisted_2 = { class: "pa-3" };
const {nextTick,onMounted,onUnmounted,ref,watch} = await importShared('vue');
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "PanelTabs",
  props: {
    api: {}
  },
  setup(__props) {
    const props = __props;
    const active = ref("overview");
    const visited = ref(/* @__PURE__ */ new Set(["overview"]));
    const queryRef = ref(null);
    watch(active, (tab) => {
      const next = new Set(visited.value);
      next.add(tab);
      visited.value = next;
    });
    async function openLookup(mediaId) {
      active.value = "query";
      await nextTick();
      queryRef.value?.query(mediaId);
    }
    function syncSite() {
      void ensureSite(props.api, true);
    }
    onMounted(() => {
      syncSite();
      if (typeof window !== "undefined") window.addEventListener("focus", syncSite);
    });
    onUnmounted(() => {
      if (typeof window !== "undefined") window.removeEventListener("focus", syncSite);
    });
    return (_ctx, _cache) => {
      const _component_v_tab = _resolveComponent("v-tab");
      const _component_v_tabs = _resolveComponent("v-tabs");
      const _component_v_divider = _resolveComponent("v-divider");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_tabs, {
          modelValue: active.value,
          "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => active.value = $event),
          density: "compact",
          color: "primary",
          "show-arrows": ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_tab, {
              value: "overview",
              "prepend-icon": "mdi-view-dashboard-outline"
            }, {
              default: _withCtx(() => [..._cache[1] || (_cache[1] = [
                _createTextVNode("概览", -1)
              ])]),
              _: 1
            }),
            _createVNode(_component_v_tab, {
              value: "baike",
              "prepend-icon": "mdi-database-outline"
            }, {
              default: _withCtx(() => [..._cache[2] || (_cache[2] = [
                _createTextVNode("ID 库", -1)
              ])]),
              _: 1
            }),
            _createVNode(_component_v_tab, {
              value: "cache",
              "prepend-icon": "mdi-cached"
            }, {
              default: _withCtx(() => [..._cache[3] || (_cache[3] = [
                _createTextVNode("缓存", -1)
              ])]),
              _: 1
            }),
            _createVNode(_component_v_tab, {
              value: "query",
              "prepend-icon": "mdi-magnify"
            }, {
              default: _withCtx(() => [..._cache[4] || (_cache[4] = [
                _createTextVNode("查询", -1)
              ])]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode(_component_v_divider),
        _createElementVNode("div", _hoisted_2, [
          visited.value.has("overview") ? _withDirectives((_openBlock(), _createBlock(_sfc_main$2, {
            key: 0,
            api: props.api
          }, null, 8, ["api"])), [
            [_vShow, active.value === "overview"]
          ]) : _createCommentVNode("", true),
          visited.value.has("baike") ? _withDirectives((_openBlock(), _createBlock(_sfc_main$5, {
            key: 1,
            api: props.api,
            onLookup: openLookup
          }, null, 8, ["api"])), [
            [_vShow, active.value === "baike"]
          ]) : _createCommentVNode("", true),
          visited.value.has("cache") ? _withDirectives((_openBlock(), _createBlock(_sfc_main$4, {
            key: 2,
            api: props.api
          }, null, 8, ["api"])), [
            [_vShow, active.value === "cache"]
          ]) : _createCommentVNode("", true),
          visited.value.has("query") ? _withDirectives((_openBlock(), _createBlock(_sfc_main$1, {
            key: 3,
            ref_key: "queryRef",
            ref: queryRef,
            api: props.api
          }, null, 8, ["api"])), [
            [_vShow, active.value === "query"]
          ]) : _createCommentVNode("", true)
        ])
      ]);
    };
  }
});

export { _sfc_main as _ };
