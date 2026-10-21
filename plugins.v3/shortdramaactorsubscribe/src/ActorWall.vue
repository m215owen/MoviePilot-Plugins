<template>
  <!--
    短剧演员 —— 作品墙（照宿主「探索」页的做法重写）。

    与探索页对齐的部分（全部按宿主编译产物逐字核对过）：
      1. 筛选栏：一层 `div.px-3`，里面**一行一个维度** —— 左侧 `div.mr-5` 放 `VLabel`，
         右侧 `VChipGroup` 里是一排 `VChip{filter, tile, value, color: 选中 ? "primary" : ""}`
         （选中项前面的 ✓ 就是 `filter`；选项太多时 VChipGroup 里的 VSlideGroup 自己出
         左右箭头）。**没有「全部」按钮**，再点一次当前项即取消（分组不加 mandatory）。
         容器 / 行 / 标签的类名与探索页完全相同。
      2. 卡片：`VCard.app-hover-lift-card.media-card` + `VImg{aspect-ratio: 2/3, cover}`
         —— 与宿主 MediaCard 同款：左上「短剧」类型徽标（紫）、右上评分徽标，
         悬停时底部浮层（年份 / 标题 / 简介 + 左搜索右订阅两个按钮）+ 上移 4px；
         点卡片进宿主媒体详情页。
      3. 网格：探索页 ProgressiveCardGrid 的默认值 `minItemWidth=144 / gap=16 /
         海报 2:3`，列数按容器宽现算，卡片按 rAF 每帧 6 张渐进补齐。
      4. 无限滚动：与 MediaCardListView 同一套判定 —— 先看 body 有没有滚动条，
         没有就 `while(!hasScrollbar())` 连拉；用
         `[media_source, media_id, type, season]` 去重；本页 0 条或本页签名与上一页
         相同即收尾；有数据后预取 margin 600。

    本插件自己的部分：
      - 行序：版权方 → 类型 → 演员 → 年份 → 排序 → 搜索（用户定的排版）；
        「版权方 / 类型 / 演员」三行选项多（真机 60 / 60 / 95 项），折叠态**只露一排**
        （CSS 高度裁切，渲染全部）+ 行尾「展开」按钮，展开后换行铺全部并可「收起」。
      - 「搜索」行是**演员搜索**：输入的演员名交给短剧百科，回来的演员同样用这套
        卡片渲染（头像作海报）；卡片上的「订阅」= 把该演员加进本插件的演员表。
      - 标题行只放「短剧演员」与统计小字；筛选栏里**没有任何按钮**（探索页同款）：
        加演员走「搜索」行搜人后点卡片上的「订阅」；没有刷新按钮（快照按小时级自动更新）。
  -->
  <div class="sdas" :class="{ 'sdas--full': full }">
    <!-- 标题行：只放标题与统计；筛选栏里不放任何按钮 -->
    <div class="sdas-head">
      <div class="sdas-title">短剧演员</div>
      <div class="sdas-sub">
        <template v-if="loading">正在从短剧百科获取作品…</template>
        <template v-else>
          {{ allTotal }} 部作品 · {{ actorCount }} 位演员
          <template v-if="inLibraryKnown"> · 已入库 {{ inLibraryCount }} 部</template>
          <template v-if="newWorks"> · <span class="sdas-new-dot">{{ newWorks }} 部新作品</span></template>
          <template v-if="filteredOut"> · 筛选出 {{ total }} 部</template>
        </template>
      </div>
    </div>

    <!--
      筛选栏：与探索页同构。
      一行一个维度：`div.flex.justify-start.align-center` > `div.mr-5`(VLabel) + `VChipGroup`，
      里面是 `VChip{filter, tile, value, color: 选中 ? "primary" : ""}`（选中项前面的 ✓
      是 VChip 的 `filter`，再点一次即取消）。
      选项特别多的三行（版权方 / 类型 / 演员）用 **column 模式**（chips 换行排布、
      不出滑动箭头）：折叠态整排渲染但用 `.sdas-clip` 把高度裁到一行，行尾
      「展开 / 收起」按钮切换；按钮必须放在 chip 组**外面** —— 放进组里会被分组当成
      一个可选项，一点就把当前维度的选中态清掉。（滑动模式点展开会「没效果」：新 chips
      都进了滑动区看不见。）
    -->
    <div class="px-3 sdas-filters">
      <!-- 版权方（数据源给出才有这一行） -->
      <div v-if="facets.studios.length" class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>版权方</v-label></div>
        <v-chip-group
          class="sdas-grid-cells"
          column
          :class="{ 'sdas-clip': !isExpanded('studio') }"
          :model-value="studio || undefined"
          @update:model-value="studio = pick($event)"
        >
          <v-chip
            v-for="item in facets.studios"
            :key="item.value"
            :value="item.value"
            :color="studio === item.value ? 'primary' : ''"
            filter
            tile
            :title="item.value"
          >
            {{ item.value }}<span class="sdas-chip-count">{{ item.count }}</span>
          </v-chip>
        </v-chip-group>
        <v-chip
          v-if="facets.studios.length > COLLAPSED_LIMIT"
          class="sdas-row-toggle"
          variant="text"
          :prepend-icon="isExpanded('studio') ? 'mdi-chevron-up' : 'mdi-chevron-down'"
          @click="toggleRow('studio')"
        >
          {{ isExpanded('studio') ? '收起' : '展开' }}
        </v-chip>
      </div>

      <!-- 类型 -->
      <div v-if="facets.genres.length" class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>类型</v-label></div>
        <v-chip-group
          class="sdas-grid-cells"
          column
          :class="{ 'sdas-clip': !isExpanded('genre') }"
          :model-value="genre || undefined"
          @update:model-value="genre = pick($event)"
        >
          <v-chip
            v-for="item in facets.genres"
            :key="item.value"
            :value="item.value"
            :color="genre === item.value ? 'primary' : ''"
            :title="item.value"
            filter
            tile
          >
            {{ item.value }}<span class="sdas-chip-count">{{ item.count }}</span>
          </v-chip>
        </v-chip-group>
        <v-chip
          v-if="facets.genres.length > COLLAPSED_LIMIT"
          class="sdas-row-toggle"
          variant="text"
          :prepend-icon="isExpanded('genre') ? 'mdi-chevron-up' : 'mdi-chevron-down'"
          @click="toggleRow('genre')"
        >
          {{ isExpanded('genre') ? '收起' : '展开' }}
        </v-chip>
      </div>

      <!-- 演员（没有演员时也保留这一行） -->
      <div class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>演员</v-label></div>
        <v-chip-group
          class="sdas-grid-cells"
          column
          :class="{ 'sdas-clip': !isExpanded('actor') }"
          :model-value="actor || undefined"
          @update:model-value="actor = pick($event)"
        >
          <v-chip
            v-for="item in actorFilters"
            :key="item.key"
            :value="item.key"
            :color="actor === item.key ? 'primary' : ''"
            filter
            tile
            :title="actorTitle(item)"
          >
            {{ item.name }}<span class="sdas-chip-count">{{ item.works }}</span>
            <span v-if="item.state === 'waiting'" class="sdas-chip-dot" title="暂时没取到作品，会自动重试">·</span>
          </v-chip>
        </v-chip-group>
        <v-chip
          v-if="actorFilters.length > COLLAPSED_LIMIT"
          class="sdas-row-toggle"
          variant="text"
          :prepend-icon="isExpanded('actor') ? 'mdi-chevron-up' : 'mdi-chevron-down'"
          @click="toggleRow('actor')"
        >
          {{ isExpanded('actor') ? '收起' : '展开' }}
        </v-chip>
      </div>

      <!-- 年份 -->
      <div v-if="facets.years.length" class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>年份</v-label></div>
        <v-chip-group
          :model-value="year || undefined"
          @update:model-value="year = pick($event)"
        >
          <v-chip
            v-for="item in facets.years"
            :key="item.value"
            :value="item.value"
            :color="year === item.value ? 'primary' : ''"
            filter
            tile
          >
            {{ item.value }}<span class="sdas-chip-count">{{ item.count }}</span>
          </v-chip>
        </v-chip-group>
      </div>

      <!-- 排序（作品自带的发布日期 / 热度 / 播放 / 评分） -->
      <div class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>排序</v-label></div>
        <v-chip-group
          :model-value="sort || undefined"
          @update:model-value="sort = pick($event) || 'heat'"
        >
          <v-chip
            v-for="opt in sortOptions"
            :key="opt.value"
            :value="opt.value"
            :color="sort === opt.value ? 'primary' : ''"
            filter
            tile
          >
            {{ opt.title }}
          </v-chip>
        </v-chip-group>
      </div>

      <!-- 媒体库：只在至少查成一条时才给这一行 —— 查库不可用时显示开关，
           会把「没查成」当成「都不在库」（判定与宿主媒体详情页一致） -->
      <div v-if="libraryKnown > 0" class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>媒体库</v-label></div>
        <v-checkbox
          v-model="onlyNotInLibrary"
          label="只看未入库"
          density="compact"
          hide-details
          class="sdas-checkbox"
          title="只显示还没进 MoviePilot 媒体库的作品（判定与媒体详情页一致：身份精确匹配，未命中按片名+年份回退）。已在库的作品卡片右上角有绿色对勾（与探索页一致）"
        />
      </div>

      <!-- 搜索：演员与作品都查（短剧百科同一站，两条检索链路并行） -->
      <div class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>搜索</v-label></div>
        <v-text-field
          v-model="actorQuery"
          class="sdas-search"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          placeholder="搜索演员或作品"
          prepend-inner-icon="mdi-magnify"
        />
        <span v-if="searchActive" class="sdas-search-hint text-body-2 text-medium-emphasis ml-3">
          <template v-if="searchingActors || searchingWorks">正在查短剧百科…</template>
          <template v-else-if="searchSummary">{{ searchSummary }}</template>
          <template v-else>没有找到相关演员或作品</template>
        </span>
        <v-chip
          v-if="filteredOut"
          class="sdas-row-toggle ml-2"
          variant="text"
          prepend-icon="mdi-filter-off-outline"
          @click="resetFilters"
        >
          重置
        </v-chip>
      </div>
    </div>

    <!--
      演员搜索结果：搜索框里有词时独占这一块（作品墙暂时让位）。
      卡片与作品卡**同一套**（VCard.media-card + 2:3 图 + 悬停浮层），
      只是「海报」换成演员头像，「订阅」的含义是把演员加进本插件的演员表。
    -->
    <template v-if="searchActive">
      <!-- 量宽哨兵：演员区 / 作品区两个网格的列宽都从它量（零高，不影响布局） -->
      <div ref="gridRef" class="sdas-measure" aria-hidden="true" />

      <!-- 两个搜索都还没回来时先铺 loading -->
      <div
        v-if="!actorResults.length && !workResults.length && (searchingActors || searchingWorks)"
        class="d-flex flex-column align-center ga-2 py-6"
      >
        <v-progress-circular indeterminate size="28" width="2" />
      </div>

      <template v-else>
        <!-- 演员：交短剧百科 search_actors 找，卡片是「头像 + 悬停浮层」 -->
        <div v-if="actorResults.length" class="mb-6">
          <div class="text-body-2 text-medium-emphasis mb-2">演员 · {{ actorResults.length }}</div>
          <div class="sdas-grid" :style="gridStyle">
            <div v-for="item in actorResults" :key="item.actor_id" class="sdas-item">
              <v-hover v-slot="{ isHovering, props: hoverProps }">
                <div v-bind="hoverProps" class="sdas-hover-area">
                  <v-card
                    :ripple="false"
                    class="app-hover-lift-card outline-none ring-gray-500 media-card sdas-card"
                    :class="{
                      'app-hover-lift-card--hovering': isHovering,
                      'ring-1': isPosterLoaded(actorKey(item)),
                    }"
                    @click="expandActor(item)"
                  >
                    <v-img
                      v-if="item.profile"
                      :src="proxyImage(item.profile)"
                      :aspect-ratio="2 / 3"
                      cover
                      class="object-cover aspect-w-2 aspect-h-3"
                      @load="markPosterLoaded(actorKey(item))"
                      @error="markPosterLoaded(actorKey(item))"
                    >
                      <template #placeholder>
                        <div class="sdas-poster-skeleton" />
                      </template>
                    </v-img>
                    <div v-else class="sdas-poster-empty d-flex align-center justify-center">
                      <v-icon icon="mdi-account-outline" size="56" color="medium-emphasis" />
                    </div>

                    <!-- 悬停浮层：身份行 / 姓名 / 简介 / 按钮排（圆形图标按钮，与作品卡一致） -->
                    <div
                      v-if="isHovering"
                      class="w-full h-full flex flex-col flex-wrap justify-end align-left text-white absolute bottom-0 cursor-pointer pa-2"
                      :style="OVERLAY_STYLE"
                    >
                      <span class="font-semibold text-sm">{{ actorMeta(item) }}</span>
                      <h1 class="sdas-card-title font-bold mb-2 text-white line-clamp-2 overflow-hidden text-ellipsis">
                        {{ item.name }}
                      </h1>
                      <p class="sdas-card-overview line-clamp-3 overflow-hidden text-ellipsis">
                        {{ item.bio || '短剧演员' }}
                      </p>
                      <div class="flex align-center justify-between">
                        <v-btn icon variant="text" title="打开百科演员页" @click.stop="openActorPage(item)">
                          <v-icon size="24" color="white">mdi-open-in-new</v-icon>
                        </v-btn>
                        <v-spacer />
                        <v-btn
                          icon
                          variant="text"
                          size="small"
                          :color="isActorAdded(item) ? 'error' : 'white'"
                          :title="isActorAdded(item) ? '取消订阅（移出关注列表）' : '订阅（加入关注列表）'"
                          :loading="
                            addingActorId === item.actor_id || removingActorId === item.actor_id
                          "
                          @click.stop="isActorAdded(item) ? unsubscribeActor(item) : subscribeActor(item)"
                        >
                          <v-icon
                            size="24"
                            :color="isActorAdded(item) ? 'error' : 'white'"
                          >
                            {{ isActorAdded(item) ? 'mdi-account-remove' : 'mdi-account-plus' }}
                          </v-icon>
                        </v-btn>
                      </div>
                    </div>
                  </v-card>
                </div>
              </v-hover>
            </div>
          </div>
        </div>
        <div v-else-if="!searchingActors" class="sdas-search-miss text-body-2 text-medium-emphasis mb-3">
          没有找到相关演员
        </div>

        <!-- 作品：走宿主搜索同一条链路（run_module("search_medias")），卡片与主墙共用 -->
        <div v-if="workResults.length">
          <div class="text-body-2 text-medium-emphasis mb-2">作品 · {{ workResults.length }}</div>
          <div class="sdas-grid" :style="gridStyle">
            <div v-for="work in workResults" :key="work.key" class="sdas-item">
              <WorkCard
                :work="work"
                :loaded="isPosterLoaded(work.key)"
                :subscribed="subscribed.has(work.media_id)"
                @poster="markPosterLoaded(work.key)"
                @open="openMedia"
                @search="searchWork"
                @subscribe="subscribe"
              />
            </div>
          </div>
        </div>
        <div v-else-if="!searchingWorks && actorResults.length" class="sdas-search-miss text-body-2 text-medium-emphasis">
          没有找到相关作品
        </div>

        <!-- 演员、作品都没搜到 -->
        <div v-if="!actorResults.length && !workResults.length" class="sdas-empty">
          <v-icon size="48" color="grey">mdi-account-search-outline</v-icon>
          <div class="sdas-empty-title">没找到「{{ searchKeyword }}」</div>
          <div class="sdas-empty-hint">换个名字试试 —— 短剧百科只收录站上有的演员和作品</div>
        </div>
      </template>
    </template>

    <template v-else>
      <!-- 展开的演员作品墙：条 + 独立的加载 / 出错 / 空态；作品卡网格与主墙共用 -->
      <div v-if="expandedActor" class="px-3 sdas-expanded-bar">
        <!-- 返回：回到搜索到这位演员的结果页（快照恢复，不重发搜索请求） -->
        <v-btn icon variant="text" title="返回搜索结果" @click="backToSearch">
          <v-icon size="24">mdi-arrow-left</v-icon>
        </v-btn>
        <v-icon icon="mdi-account-outline" size="18" class="mr-2 ml-1" />
        <span class="text-subtitle-1 font-weight-bold">{{ expandedActor.name }} 的作品</span>
        <span v-if="!expandedLoading" class="text-body-2 text-medium-emphasis ml-2">
          共 {{ expandedWorks.length }} 部
        </span>
        <v-spacer />
      </div>

      <!-- 展开：加载中（百科现查，慢一截） -->
      <div v-if="expandedActor && expandedLoading" class="d-flex flex-column align-center ga-2 py-6">
        <v-progress-circular indeterminate size="28" width="2" />
      </div>
      <!-- 展开：出错 -->
      <div v-else-if="expandedActor && expandedError" class="d-flex flex-column align-center ga-2 py-4">
        <span class="text-body-2 text-medium-emphasis">{{ expandedError }}</span>
        <v-btn prepend-icon="mdi-refresh" size="small" variant="tonal" @click="expandActor(expandedActor)">重试</v-btn>
      </div>
      <!-- 展开：百科里没有作品 -->
      <div v-else-if="expandedActor && !expandedWorks.length" class="sdas-empty">
        <v-icon size="48" color="grey">mdi-movie-open-star-outline</v-icon>
        <div class="sdas-empty-title">百科里没有「{{ expandedActor.name }}」的作品记录</div>
      </div>

      <!-- 加载中：有数据前铺 loading（对应探索页的 LoadingBanner 位置） -->
      <div v-else-if="!works.length && !error" class="d-flex flex-column align-center ga-2 py-4">
        <v-progress-circular indeterminate size="28" width="2" />
      </div>

      <!-- 错误态（照探索页的 error 插槽：提示 + 重试） -->
      <div v-else-if="error && !works.length" class="d-flex flex-column align-center ga-2 py-4">
        <span class="text-body-2 text-medium-emphasis">网络错误</span>
        <v-btn prepend-icon="mdi-refresh" size="small" variant="tonal" @click="reload">重试</v-btn>
      </div>

      <!-- 空态（没有作品时才展示） -->
      <div v-else-if="!works.length" class="sdas-empty">
        <v-icon size="48" color="grey">mdi-movie-open-star-outline</v-icon>
        <div class="sdas-empty-title">
          <template v-if="!actorCount">还没有添加演员</template>
          <template v-else>没有符合条件的作品</template>
        </div>
        <div class="sdas-empty-hint">
          <template v-if="!actorCount">在「搜索」里搜一位演员，点卡片上的「订阅」加进来</template>
          <template v-else-if="filteredOut">换个筛选条件试试</template>
          <template v-else-if="emptyHint">{{ emptyHint }}</template>
        </div>
      </div>

      <!--
        作品墙：探索页式海报卡网格。
        列数 = floor((容器宽 + gap) / (minItemWidth + gap))，与 ProgressiveCardGrid 同式；
        行高由 2:3 海报决定（= 列宽 × 1.5）。
        卡片与宿主 MediaCard 同款：左上「短剧」徽标、右上评分徽标，悬停浮层是
        年份 / 标题 / 简介 + 搜索与订阅两个按钮；点卡片进宿主媒体详情页。
      -->
      <div v-else ref="gridRef" class="sdas-grid" :style="gridStyle">
        <div
          v-for="(work, index) in displayWorks"
          :key="work.key"
          class="sdas-item"
          :data-progressive-grid-index="index"
        >
          <WorkCard
            :work="work"
            :loaded="isPosterLoaded(work.key)"
            :subscribed="subscribed.has(work.media_id)"
            @poster="markPosterLoaded(work.key)"
            @open="openMedia"
            @search="searchWork"
            @subscribe="subscribe"
          />
        </div>
      </div>

      <!-- 滚动加载哨兵：常驻渲染，进入视口即拉下一页（展开模式下无分页，不渲染） -->
      <div v-if="!expandedActor" ref="sentinel" class="sdas-sentinel">
        <v-progress-circular v-if="loadingMore" indeterminate size="20" width="2" />
        <span v-else-if="works.length && done">已到末尾 · 共 {{ total }} 部</span>
      </div>
    </template>

    <!-- 自绘提示条：联邦拿不到宿主的全局弹窗服务 -->
    <transition name="sdas-fade">
      <div v-if="tip" class="sdas-toast" :class="`is-${tipType}`">{{ tip }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  addActor,
  fetchActorWorks,
  fetchConfig,
  fetchSubscribedIds,
  fetchWorks,
  mediaPageUrl,
  proxyImage,
  removeActor,
  resourceSearchUrl,
  searchActor,
  searchWorks,
  submitSubscribe,
} from './api'
import WorkCard from './WorkCard.vue'
import type {
  ActorCandidate,
  ActorFilter,
  PluginApi,
  PluginConfig,
  WorkItem,
  WorksFacets,
  WorksPayload,
} from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 插件配置（侧栏场景一般为空，需要时自行拉取） */
  config?: Partial<PluginConfig>
  /** 当前插件实例 ID */
  pluginId?: string
  /** 宿主注入的原生订阅入口：传媒体对象即弹出系统订阅对话框 */
  nativeSubscribe?: (media: Record<string, unknown>) => Promise<any>
  /** 整页留白（侧栏全页场景） */
  full?: boolean
}>()

/** 每页作品数（与后端默认页一致） */
const PAGE_SIZE = 60
/** 网格列宽下限 / 间距（探索页 ProgressiveCardGrid 默认值） */
const MIN_ITEM_WIDTH = 144
const GRID_GAP = 16
/** 渐进填充：每帧补几张（探索页 batchSize 默认值） */
const BATCH_SIZE = 6
/** 超过这么多项的行才有「展开」按钮（折叠态露出几项由 CSS 一行高度决定） */
const COLLAPSED_LIMIT = 12
/** 搜索演员的防抖（站外索引 + 补档案不便宜） */
const LOOKUP_DEBOUNCE = 420
/** 悬停浮层背景（与探索页 MediaCard 逐字相同） */
const OVERLAY_STYLE = {
  background: 'linear-gradient(rgba(45, 55, 72, 40%) 0%, rgba(45, 55, 72, 90%) 100%)',
}

// ── 列表状态（口径对齐 MediaCardListView） ──

/** 已经铺出来的作品（翻页累加、去重后） */
const works = ref<WorkItem[]>([])
/** 当前筛选条件下的作品总数 */
const total = ref(0)
/** 全集作品数（不受筛选影响） */
const allTotal = ref(0)
/** 全集里的新作品数 */
const newWorks = ref(0)
/** 在库状态查成了的作品数（0 = 媒体库判定不可用，隐藏在库相关 UI） */
const libraryKnown = ref(0)
/** 其中明确已在库的作品数 */
const inLibraryCount = ref(0)
const inLibraryKnown = computed(() => libraryKnown.value > 0)
/** 已拉过的页数游标 */
const page = ref(1)
/** 到底了（0 条 或 本页签名与上一页相同） */
const done = ref(false)
/** 网络错误 */
const error = ref(false)
/** 首屏 / 重载中 */
const loading = ref(false)
/** 正在接下一页 */
const loadingMore = ref(false)
/** 去重键集合（`[media_source, media_id, type, season]`） */
const seenKeys = new Set<string>()
/** 每页的签名集合：撞上说明后端已经翻不出新东西了 */
const seenSignatures = new Set<string>()
/** 重载计数器：改筛选/刷新时自增，把在途请求的结果丢掉 */
let epoch = 0

const actorFilters = ref<ActorFilter[]>([])
const facets = ref<WorksFacets>({ genres: [], years: [], studios: [] })

/** 筛选条件 */
const actor = ref('')
const genre = ref('')
const year = ref('')
const studio = ref('')
const sort = ref('heat')
/** 只看未入库（后端只排除明确已在库的；「未知」作品保留） */
const onlyNotInLibrary = ref(false)

/** 折起来的行（键 = 维度名）：真机演员 95 / 类型 60 / 版权方 60 项，默认只铺一行 */
const expandedRows = ref<Record<string, boolean>>({})

/** 搜索框里的关键词：既查演员也查作品 */
const actorQuery = ref('')
const actorResults = ref<ActorCandidate[]>([])
const searchingActors = ref(false)
/** 作品搜索结果（同一关键词，走百科的片名检索） */
const workResults = ref<WorkItem[]>([])
const searchingWorks = ref(false)
/** 正在加入关注列表的演员 ID（按钮转圈用） */
const addingActorId = ref('')
/** 正在移出关注列表的演员 ID（按钮转圈用） */
const removingActorId = ref('')

/** 展开作品墙的演员（点演员卡片进入；null = 主墙） */
const expandedActor = ref<ActorCandidate | null>(null)
/** 进入展开前的搜索结果快照（返回按钮用：查询词 + 候选列表） */
const searchSnapshotQuery = ref('')
const searchSnapshotResults = ref<ActorCandidate[]>([])
/** 同一次搜索里的作品结果快照（返回搜索结果页时一并恢复） */
const searchSnapshotWorks = ref<WorkItem[]>([])
/** 展开演员的作品（百科现查，不进快照） */
const expandedWorks = ref<WorkItem[]>([])
const expandedLoading = ref(false)
const expandedError = ref('')

/** 已订阅作品的 media_id（作品卡悬停浮层上爱心按钮的状态） */
const subscribed = ref<Set<string>>(new Set())
/** 图已加载完的卡片 key（工作 / 演员共用一套；探索页也是「图加载完才加 ring」） */
const loadedKeys = ref<Set<string>>(new Set())

/** 提示条 */
const tip = ref('')
const tipType = ref<'info' | 'error'>('info')
let tipTimer: ReturnType<typeof setTimeout> | null = null

function toast(text: string, type: 'info' | 'error' = 'info'): void {
  tip.value = text
  tipType.value = type
  if (tipTimer) clearTimeout(tipTimer)
  tipTimer = setTimeout(() => (tip.value = ''), 3200)
}

/** 排序维度（排的全是作品自带的真实数据；发布日期放首位，默认排序仍是热度） */
const sortOptions = [
  { title: '发布日期', value: 'date' },
  { title: '热度', value: 'heat' },
  { title: '播放', value: 'play' },
  { title: '评分', value: 'rating' },
]

/** 是否处于筛选状态（决定要不要显示「重置」与「筛选出 N 部」） */
const filteredOut = computed(() =>
  Boolean(
    actor.value ||
      genre.value ||
      year.value ||
      studio.value ||
      onlyNotInLibrary.value,
  ),
)

function resetFilters(): void {
  actor.value = ''
  genre.value = ''
  year.value = ''
  studio.value = ''
  onlyNotInLibrary.value = false
}

/**
 * 筛选/视图状态持久化（sessionStorage，按标签页隔离）。
 *
 * 点进媒体详情会离开插件页、返回时组件**重新挂载**——所有 ref 都回到默认值。
 * 探索页 TMDB 不丢状态是因为宿主给 `/discover` 路由加了 `meta.keepAlive`，
 * 组件被 `<KeepAlive>` 缓存、从不销毁；而插件页路由 `/plugin-app/...` 没有
 * keepAlive（宿主按 fullPath 重挂），插件也改不了自己的路由 meta ⇒
 * 只能做到「销毁后把状态还原」：筛选/排序变化即写、已加载页数与滚动位置在
 * 离开页面前写，回来时先恢复再拉数据，并补齐之前加载过的页、跳回原滚动位置。
 * ⚠️ restoreViewState() 必须在下方 watch 注册**之前**调用：注册后改值会立即触发 reload。
 */
const FILTER_STORAGE_KEY = 'ShortDramaActorSubscribe.filters.v1'

/** 离开页面时的视图状态（已加载页数 / 滚动位置），非响应式 */
let savedPages = 0
let savedScroll = 0
/** 最近一次滚动位置（scroll 监听里持续记录，卸载时写入存储） */
let lastScrollY = 0

function restoreViewState(): void {
  try {
    const raw = sessionStorage.getItem(FILTER_STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as Record<string, unknown>
    actor.value = typeof saved.actor === 'string' ? saved.actor : ''
    genre.value = typeof saved.genre === 'string' ? saved.genre : ''
    year.value = typeof saved.year === 'string' ? saved.year : ''
    studio.value = typeof saved.studio === 'string' ? saved.studio : ''
    onlyNotInLibrary.value = saved.only_not_in_library === true
    if (typeof saved.sort === 'string' && sortOptions.some((opt) => opt.value === saved.sort)) {
      sort.value = saved.sort
    }
    savedPages = typeof saved.pages === 'number' && saved.pages > 0 ? Math.floor(saved.pages) : 0
    savedScroll = typeof saved.scroll === 'number' && saved.scroll > 0 ? Math.floor(saved.scroll) : 0
  } catch {
    // 存的内容坏了就清掉，回到默认
    try {
      sessionStorage.removeItem(FILTER_STORAGE_KEY)
    } catch {
      /* 忽略 */
    }
  }
}

/** 筛选一变就写（此刻还不知道会加载到第几页，页数/滚动留到卸载时补全） */
function persistFilters(): void {
  writeViewState({ pages: 0, scroll: 0 })
}

function writeViewState(view: { pages: number; scroll: number }): void {
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
        ...view,
      }),
    )
  } catch {
    /* sessionStorage 不可用（隐私模式等）就退化为不记忆 */
  }
}

restoreViewState()

/** 搜索状态：搜索框里有词时，这一块显示演员搜索结果 */
/**
 * 搜索框关键词（null 安全版）。
 * ⚠️ Vuetify 的 clearable 点 ✕ 时把模型设成 **null** 而不是空串 —— 直接
 * ``actorQuery.trim()`` 会在 null 上抛 TypeError，渲染中断，页面卡在搜索结果
 * 回不到作品墙。所有读关键词的地方一律走这个 computed。
 */
const searchKeyword = computed(() => String(actorQuery.value || '').trim())
const searchActive = computed(() => searchKeyword.value.length > 0)

/** 搜索结果摘要（「3 位演员 · 2 部作品」；两个都空时给空串走兜底文案） */
const searchSummary = computed(() => {
  const parts: string[] = []
  if (actorResults.value.length) parts.push(`${actorResults.value.length} 位演员`)
  if (workResults.value.length) parts.push(`${workResults.value.length} 部作品`)
  return parts.join(' · ')
})

// ── 可展开的筛选行 ──

function isExpanded(row: string): boolean {
  return Boolean(expandedRows.value[row])
}

function toggleRow(row: string): void {
  expandedRows.value = { ...expandedRows.value, [row]: !expandedRows.value[row] }
}

/**
 * VChipGroup 在「再点一次」时会把 modelValue 置成 undefined/null ——
 * 这里统一收敛成字符串，空串即「这一维不筛」。
 */
function pick(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/** 当前查询条件（不含分页） */
function query(): Record<string, unknown> {
  return {
    actor: actor.value,
    genre: genre.value,
    year: year.value,
    studio: studio.value,
    sort: sort.value,
    only_not_in_library: onlyNotInLibrary.value,
    page_size: PAGE_SIZE,
  }
}

const actorCount = computed(() => actorFilters.value.length)

/** 演员名后第一个失败/未收录原因，作为空态提示 */
const emptyHint = computed(() => {
  const waiting = actorFilters.value.filter((item) => item.state === 'waiting')
  const empty = actorFilters.value.filter((item) => item.state === 'empty')
  if (!works.value.length && empty.length) {
    return `短剧百科未收录：${empty.map((item) => item.name).join('、')}`
  }
  if (!works.value.length && waiting.length) {
    return '百科暂时没返回作品，插件会自动重试'
  }
  return ''
})

function actorTitle(item: ActorFilter): string {
  if (item.state === 'empty') return '短剧百科未收录该演员'
  if (item.state === 'waiting') return '暂时没取到作品，会自动重试'
  return `${item.works} 部作品`
}

// ── 海报与卡片 ──

/**
 * 图加载完（含错误）后把 key 记下来。
 *
 * 作品卡与演员卡共用这套标记：探索页也是「图加载完才给卡片加 ring-1」。
 */
function markPosterLoaded(key: string): void {
  loadedKeys.value.add(key)
}

function isPosterLoaded(key: string | undefined): boolean {
  if (!key) return true
  return loadedKeys.value.has(key)
}

/** 演员卡在加载集合里的键（与作品卡共用一个 Set，前缀避免撞车） */
function actorKey(item: ActorCandidate): string {
  return `actor:${item.actor_id}`
}

// ── 演员搜索卡片 ──

/** 演员卡浮层的身份行：作品数 / 身份 / 性别 / 国籍 */
function actorMeta(item: ActorCandidate): string {
  const parts: string[] = []
  if (item.works_count) parts.push(`${item.works_count} 部作品`)
  if (item.job_title) parts.push(item.job_title)
  if (item.gender) parts.push(item.gender)
  if (item.nationality) parts.push(item.nationality)
  if (!parts.length) parts.push('短剧演员')
  return parts.join(' · ')
}

/** 这位演员是否已经在关注列表里（后端标过，或刚在本地加过） */
function isActorAdded(item: ActorCandidate): boolean {
  if (item.subscribed) return true
  return actorFilters.value.some((row) => row.name === item.name)
}

/** 打开百科的演员页 */
function openActorPage(item: ActorCandidate): void {
  if (!item.url) {
    toast('这条候选没有百科链接')
    return
  }
  if (typeof window !== 'undefined') window.open(item.url, '_blank', 'noopener')
}

/** 「订阅」演员 = 把它加进本插件的演员表（不是宿主的剧集订阅） */
async function subscribeActor(item: ActorCandidate): Promise<void> {
  if (isActorAdded(item)) {
    toast(`「${item.name}」已经在关注列表里`)
    return
  }
  addingActorId.value = item.actor_id
  try {
    const result = await addActor(props, item.name, item.actor_id)
    if (result?.success === false) {
      toast(String(result.message || '添加失败'), 'error')
      return
    }
    // 先在卡片上标出来（不用等整轮重载回来）
    item.subscribed = true
    toast(String(result?.message || `已添加「${item.name}」`))
    await reload()
  } catch (err) {
    toast(`添加失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    addingActorId.value = ''
  }
}

/** 「取消订阅」演员 = 把它移出关注列表（连同快照一起删，后端负责） */
async function unsubscribeActor(item: ActorCandidate): Promise<void> {
  if (!isActorAdded(item)) {
    toast(`「${item.name}」不在关注列表里`)
    return
  }
  removingActorId.value = item.actor_id
  try {
    const result = await removeActor(props, item.name)
    if (result?.success === false) {
      toast(String(result.message || '移除失败'), 'error')
      return
    }
    item.subscribed = false
    // 正展开这位演员的作品墙就一并收起（主墙里已经没有他了）
    if (expandedActor.value?.actor_id === item.actor_id) collapseActor()
    toast(String(result?.message || `已移除「${item.name}」`))
    await reload()
  } catch (err) {
    toast(`移除失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    removingActorId.value = ''
  }
}

/**
 * 点演员卡片：展开这位演员的作品墙（百科实时取，关注与否均可）。
 *
 * 会先退出搜索结果视图（作品墙让回来），作品在新端点 `/actors/works` 现查 ——
 * 每条都已补成作品页记录，字段与主墙的 WorkItem 一致，卡片渲染完全复用。
 */
async function expandActor(item: ActorCandidate): Promise<void> {
  // 从搜索结果页进入：快照查询词与结果，返回时原样恢复（不重发搜索请求）
  if (searchActive.value) {
    searchSnapshotQuery.value = searchKeyword.value
    searchSnapshotResults.value = actorResults.value
    searchSnapshotWorks.value = workResults.value
  }
  actorQuery.value = ''
  expandedActor.value = item
  expandedWorks.value = []
  expandedError.value = ''
  expandedLoading.value = true
  try {
    const payload = await fetchActorWorks(props, item.actor_id, item.name)
    if (expandedActor.value?.actor_id !== item.actor_id) return // 用户已换人 / 收起
    if (payload?.success === false) {
      expandedError.value = String(payload.message || '取作品失败')
      return
    }
    expandedWorks.value = payload.works || []
  } catch (err) {
    if (expandedActor.value?.actor_id !== item.actor_id) return
    expandedError.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (expandedActor.value?.actor_id === item.actor_id) expandedLoading.value = false
  }
}

/** 收起展开的演员作品墙，回到主墙 */
function collapseActor(): void {
  expandedActor.value = null
  expandedWorks.value = []
  expandedError.value = ''
  expandedLoading.value = false
}

/**
 * 返回按钮：回到搜索到这位演员的结果页。
 *
 * 直接恢复快照（查询词 + 候选列表），不重发搜索请求 —— 恢复查询词会触发
 * watch 里的防抖搜索，恢复后下一拍把它取消掉。
 */
async function backToSearch(): Promise<void> {
  const query = searchSnapshotQuery.value
  const results = searchSnapshotResults.value
  const works = searchSnapshotWorks.value
  collapseActor()
  if (!query) return // 没有快照（异常路径），留在主墙
  actorResults.value = results
  workResults.value = works
  searchingActors.value = false
  searchingWorks.value = false
  actorQuery.value = query
  await nextTick()
  if (lookupTimer) clearTimeout(lookupTimer)
  searchSnapshotQuery.value = ''
  searchSnapshotResults.value = []
  searchSnapshotWorks.value = []
}

/** 搜索：走短剧百科，演员（带头像 / 作品数）与作品（片名检索）并行 */
let lookupEpoch = 0

async function runLookup(): Promise<void> {
  const name = searchKeyword.value
  const stamp = ++lookupEpoch
  if (!name) {
    actorResults.value = []
    workResults.value = []
    searchingActors.value = false
    searchingWorks.value = false
    return
  }
  searchingActors.value = true
  searchingWorks.value = true
  const actorTask = searchActor(props, name, true)
    .then((payload) => {
      if (stamp !== lookupEpoch) return
      actorResults.value = payload.candidates || []
    })
    .catch((err) => {
      if (stamp !== lookupEpoch) return
      actorResults.value = []
      toast(`搜索演员失败：${err instanceof Error ? err.message : err}`, 'error')
    })
    .finally(() => {
      if (stamp === lookupEpoch) searchingActors.value = false
    })
  const workTask = searchWorks(props, name)
    .then((payload) => {
      if (stamp !== lookupEpoch) return
      workResults.value = payload.works || []
    })
    .catch((err) => {
      if (stamp !== lookupEpoch) return
      workResults.value = []
      toast(`搜索作品失败：${err instanceof Error ? err.message : err}`, 'error')
    })
    .finally(() => {
      if (stamp === lookupEpoch) searchingWorks.value = false
    })
  await Promise.allSettled([actorTask, workTask])
  // 头像 / 作品数 / 简介由后端搜索时统一补档（enrich=true，经 run_module("actor_profile")
  // 分发给百科插件），前端不再直调百科 HTTP 接口。
}

// ── 网格几何 + 渐进填充 ──

const gridRef = ref<HTMLElement | null>(null)
const gridWidth = ref(0)
let gridObserver: ResizeObserver | null = null

/** 列数：与 ProgressiveCardGrid 同一个公式 */
const columns = computed(() => {
  const width = gridWidth.value || MIN_ITEM_WIDTH
  return Math.max(1, Math.floor((width + GRID_GAP) / (MIN_ITEM_WIDTH + GRID_GAP)))
})

const gridStyle = computed(() => ({
  columnGap: `${GRID_GAP}px`,
  rowGap: `${GRID_GAP}px`,
  gridTemplateColumns: `repeat(${columns.value}, minmax(0, 1fr))`,
}))

function measureGrid(): void {
  const node = gridRef.value
  if (!node) return
  const width = node.clientWidth
  if (width && width !== gridWidth.value) gridWidth.value = width
}

/** 挂上/重挂容器的尺寸观察（网格只在有作品时才存在） */
function watchGrid(): void {
  gridObserver?.disconnect()
  gridObserver = null
  const node = gridRef.value
  if (!node) return
  measureGrid()
  if (typeof ResizeObserver === 'function') {
    gridObserver = new ResizeObserver(() => measureGrid())
    gridObserver.observe(node)
  }
}

/** 已铺出来的张数（渐进填充的游标） */
const visibleCount = ref(0)
let fillFrame: number | null = null

const visibleWorks = computed(() => works.value.slice(0, visibleCount.value))

/** 网格真正渲染的列表：展开演员时是他/她的作品全集（无分页，直接铺满） */
const displayWorks = computed(() =>
  expandedActor.value ? expandedWorks.value : visibleWorks.value,
)

/** 每帧补 BATCH_SIZE 张，补完再检查哨兵（与探索页的渐进填充同节奏） */
function stepFill(): void {
  fillFrame = null
  if (visibleCount.value >= works.value.length) {
    ensureFilled()
    return
  }
  visibleCount.value = Math.min(works.value.length, visibleCount.value + BATCH_SIZE)
  if (visibleCount.value >= works.value.length) {
    ensureFilled()
    return
  }
  if (typeof requestAnimationFrame === 'function') {
    fillFrame = requestAnimationFrame(stepFill)
  } else {
    fillFrame = setTimeout(stepFill, 16) as unknown as number
  }
}

function scheduleFill(): void {
  if (fillFrame !== null) return
  if (typeof requestAnimationFrame === 'function') {
    fillFrame = requestAnimationFrame(stepFill)
  } else {
    fillFrame = setTimeout(stepFill, 16) as unknown as number
  }
}

function cancelFill(): void {
  if (fillFrame === null) return
  if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(fillFrame)
  else clearTimeout(fillFrame)
  fillFrame = null
}

// ── 数据：拉页 / 去重 / 收尾 ──

/** 去重键：与 MediaCardListView 的口径一致 */
function dedupeKey(work: WorkItem): string {
  return JSON.stringify(['media', work.media_source, String(work.media_id ?? ''), work.type ?? null, null])
}

/** body 有没有滚动条（探索页用它决定「先连拉几页」） */
function hasScrollbar(): boolean {
  const body = document.body
  const viewport = window.innerHeight || document.documentElement.clientHeight
  return body.scrollHeight - viewport > 2
}

/** 分面 / 统计（同一筛选条件下每页都一样，随便哪页都能刷新） */
function applyMeta(payload: WorksPayload): void {
  total.value = payload.total
  actorFilters.value = payload.actor_filters || []
  facets.value = payload.facets
  allTotal.value = payload.summary?.total ?? payload.total
  newWorks.value = payload.summary?.new ?? 0
  libraryKnown.value = Number(payload.summary?.library_known ?? 0)
  inLibraryCount.value = Number(payload.summary?.in_library ?? 0)
}

/** 拉一页，返回「是否已到底 + 本页新增的条目」 */
async function fetchPage(): Promise<{ terminal: boolean; rows: WorkItem[] }> {
  const payload = await fetchWorks(props, { ...query(), page: page.value, page_size: PAGE_SIZE })
  page.value += 1
  applyMeta(payload)
  const rows = payload.works || []
  const signature = [...new Set(rows.map(dedupeKey))].sort().join('\n')
  const terminal = rows.length === 0 || seenSignatures.has(signature)
  if (!terminal) seenSignatures.add(signature)
  if (terminal) return { terminal: true, rows: [] }
  const fresh = rows.filter((row) => {
    const key = dedupeKey(row)
    if (seenKeys.has(key)) return false
    seenKeys.add(key)
    return true
  })
  return { terminal: false, rows: fresh }
}

function append(rows: WorkItem[]): void {
  if (!rows.length) return
  works.value = works.value.concat(rows)
  scheduleFill()
}

/** 接下一页（滚动到底 / 首屏不满一屏时触发） */
async function loadMore(): Promise<void> {
  if (loadingMore.value || done.value) return
  const stamp = epoch
  loadingMore.value = true
  error.value = false
  try {
    if (hasScrollbar()) {
      const { terminal, rows } = await fetchPage()
      if (stamp !== epoch) return
      if (terminal) {
        done.value = true
        return
      }
      append(rows)
    } else {
      // 首屏 / 内容不足一屏：哨兵不会移位，observer 不会再回调 ⇒ 主动连拉
      while (!hasScrollbar()) {
        const { terminal, rows } = await fetchPage()
        if (stamp !== epoch) return
        if (terminal) {
          done.value = true
          return
        }
        append(rows)
        await nextTick()
      }
    }
  } catch (err) {
    if (stamp !== epoch) return
    error.value = true
    toast(`加载作品失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    if (stamp === epoch) {
      loadingMore.value = false
      await nextTick()
      ensureFilled()
    }
  }
}

/**
 * 页面太短、或哨兵本来就在视口里时，IntersectionObserver 不会再回调 ——
 * 每次加载 / 填充完之后主动补一次，直到填满或到底。
 * （等价于探索页 VInfiniteScroll 在 items 变化时重算距离的行为。）
 */
function ensureFilled(): void {
  const node = sentinel.value
  if (!node || done.value || loadingMore.value || loading.value) return
  if (visibleCount.value < works.value.length) return
  const viewport = window.innerHeight || document.documentElement.clientHeight
  if (node.getBoundingClientRect().top <= viewport + 600) loadMore()
}

/** 重置列表并拉第一页（改筛选、刷新、首屏都走这里 —— 等价于探索页的「key 自增重挂载」） */
async function reload(): Promise<void> {
  epoch += 1
  cancelFill()
  loading.value = true
  error.value = false
  done.value = false
  page.value = 1
  seenKeys.clear()
  seenSignatures.clear()
  works.value = []
  visibleCount.value = 0
  loadingMore.value = false
  await nextTick()
  try {
    await loadMore()
  } finally {
    loading.value = false
  }
}

async function loadSubscribed(): Promise<void> {
  subscribed.value = await fetchSubscribedIds(props)
}

// ── 滚动加载 ──

const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

onMounted(async () => {
  if (typeof IntersectionObserver === 'function') {
    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore()
      },
      { rootMargin: '600px 0px' },
    )
    if (sentinel.value) observer.observe(sentinel.value)
  }
  window.addEventListener('scroll', onScroll, { passive: true })
  await Promise.all([reload(), loadSubscribed()])
  await restorePaging()
  await nextTick()
  watchGrid()
})

/** 持续记录滚动位置：卸载时写入存储，返回时才能跳回原处 */
function onScroll(): void {
  lastScrollY = window.scrollY || 0
}

/**
 * 恢复离开前的进度：把之前加载过的页一页页补齐，再跳回原滚动位置。
 * （探索页是宿主 KeepAlive 连 DOM 一起保住，这里只能重拉 —— 数据源有缓存，代价可控。）
 */
async function restorePaging(): Promise<void> {
  if (savedPages <= 1) return
  const stamp = epoch
  for (let target = 2; target <= savedPages; target += 1) {
    if (stamp !== epoch) return
    try {
      const { terminal, rows } = await fetchPage()
      if (stamp !== epoch) return
      if (terminal) return
      append(rows)
      await nextTick()
    } catch {
      return // 恢复失败就停在已加载的部分，不打扰用户
    }
  }
  // 渐进填充是按帧补的，跳滚动位置前一次性把卡片全铺出来，否则页面高度不够、跳不到位
  visibleCount.value = works.value.length
  await nextTick()
  window.scrollTo({ top: savedScroll })
}

onUnmounted(() => {
  // 离开页面（点进详情等）前把「加载到第几页 + 滚动到哪」记下来，回来时恢复。
  // 用监听器记下的 lastScrollY 而不是现读 window.scrollY：宿主 scrollBehavior
  // 复位滚动发生在组件卸载前后，时序不可靠，监听器里的一定是离开前的位置。
  writeViewState({ pages: Math.max(1, page.value - 1), scroll: lastScrollY })
  window.removeEventListener('scroll', onScroll)
  observer?.disconnect()
  observer = null
  gridObserver?.disconnect()
  gridObserver = null
  cancelFill()
  if (tipTimer) clearTimeout(tipTimer)
  if (lookupTimer) clearTimeout(lookupTimer)
})

// 网格节点挂在两个互斥分支里（演员结果 / 作品墙），切换时要重新量一次
watch(searchActive, async () => {
  await nextTick()
  watchGrid()
})

// 网格节点是 v-else 分支：作品数从 0 变 1 时才出现，出现后重新量一次
watch(
  () => works.value.length,
  async (count, previous) => {
    if (count && !previous) {
      await nextTick()
      watchGrid()
    }
  },
)

// 筛选条件一变就持久化 + 重新拉第一页；搜索演员做防抖，避免每敲一个字都去查百科
let lookupTimer: ReturnType<typeof setTimeout> | null = null
watch([actor, genre, year, studio, sort, onlyNotInLibrary], () => {
  persistFilters()
  reload()
})
watch(actorQuery, () => {
  if (lookupTimer) clearTimeout(lookupTimer)
  lookupTimer = setTimeout(runLookup, LOOKUP_DEBOUNCE)
})

// ── 动作 ──

/** 订阅：配置页指定了下载器 → 直接向宿主提交（弹窗没有下载器选项，带不上偏好）；
 * 没指定 → 弹系统订阅对话框，走宿主默认 */
async function subscribe(work: WorkItem): Promise<void> {
  if (subscribed.value.has(work.media_id)) {
    toast('这部剧已经在订阅里了')
    return
  }
  await ensureConfig()
  const downloader = String(configData.value.subscribe_downloader || '').trim()
  if (downloader) {
    const res = await submitSubscribe(props, work, downloader)
    if (res.ok) {
      const next = new Set(subscribed.value)
      next.add(work.media_id)
      subscribed.value = next
      // 宿主入库稍有延迟，稍后回查一次对齐真实状态
      setTimeout(loadSubscribed, 3000)
    }
    toast(res.ok ? res.message : `订阅失败：${res.message}`, res.ok ? 'info' : 'error')
    return
  }
  if (typeof props.nativeSubscribe !== 'function') {
    toast('当前宿主没有提供系统订阅入口，请从「详情」页订阅', 'error')
    return
  }
  try {
    const result = await props.nativeSubscribe({
      media_source: work.media_source,
      media_id: work.media_id,
      title: work.title,
      year: work.year || '',
      type: work.type || '电视剧',
      poster_path: work.poster || '',
      vote_average: work.vote || 0,
    })
    if (result && result.success === false) {
      toast(String(result.message || '订阅失败'), 'error')
      return
    }
    // 弹窗里用户还要确认，等一会儿再回查一次订阅表（只是为了把「已订阅」标出来）
    setTimeout(loadSubscribed, 3000)
  } catch (err) {
    toast(`订阅失败：${err instanceof Error ? err.message : err}`, 'error')
  }
}

/** 打开宿主的媒体详情页：短剧百科已是系统媒体源，详情页由系统渲染 */
function openMedia(work: WorkItem): void {
  const url = mediaPageUrl(work)
  if (typeof window !== 'undefined' && window.location) {
    window.location.href = url
  }
}

/** 配置缓存：站点跳转与订阅提交共用（首次用时拉一次，之后复用） */
const configData = ref<Partial<PluginConfig>>({})
let configLoaded = false

/** 懒加载插件配置（失败则下次再试） */
async function ensureConfig(): Promise<void> {
  if (configLoaded) return
  configLoaded = true
  try {
    configData.value = { ...(await fetchConfig(props)), ...configData.value }
  } catch {
    configLoaded = false
  }
}

/** 卡片上的搜索：按配置页选定的站点跳宿主资源搜索页（不带弹窗） */
async function searchWork(work: WorkItem): Promise<void> {
  if (typeof window === 'undefined' || !window.location) return
  await ensureConfig()
  // 配置的站点 ID 串（空 = 不限定，走宿主默认行为）
  const siteIds = String(configData.value.search_sites || '')
    .split(/[,，;；\s]+/)
    .filter((id) => id && /^\d+$/.test(id))
  window.location.href = resourceSearchUrl(work, siteIds.length ? siteIds.map(Number) : undefined)
}
</script>

<style scoped>
.sdas {
  --sdas-fg: rgb(var(--v-theme-on-surface));
  --sdas-fg-dim: rgba(var(--v-theme-on-surface), 0.62);
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0 12px;
  color: var(--sdas-fg);
}

.sdas--full {
  padding: 12px 16px 24px;
}

/* 标题行：标题 + 统计小字，竖排 */
.sdas-head {
  padding: 0 12px;
}

.sdas-title {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.2;
}

.sdas-sub {
  margin-top: 4px;
  font-size: 13px;
  color: var(--sdas-fg-dim);
}

.sdas-new-dot {
  color: #e53935;
}

/*
  筛选栏：行结构（flex / justify-start / align-center / mr-5）与标签（VLabel）的类名
  全部沿用探索页；这里只补行间距与 chip 上的计数角标。
*/
.sdas-filters {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* 展开的演员作品墙顶条（与筛选栏同宽度节奏） */
.sdas-expanded-bar {
  display: flex;
  align-items: center;
  min-height: 40px;
  margin-bottom: 2px;
}

/*
  可展开的三行（版权方 / 类型 / 演员）用 column 模式的 chip 组：chips 换行排布，
  没有滑动箭头。组要占满行内剩余宽度，chips 才会按容器宽换行。
*/
.sdas-filters .v-chip-group--column {
  flex: 1 1 auto;
  min-width: 0;
}

/* 筛选栏内非网格行的 chip（年份 / 排序）统一边距，起点与网格行一致 */
.sdas-filters .v-chip-group .v-chip {
  margin: 4px 8px 4px 0;
}

/* 标签列定宽：「版权方」3 个字、其余 2 个字 —— 定宽后各行 chips 的起点才竖向对齐 */
.sdas-row-label {
  flex: 0 0 3.5em;
}

/* 「只看未入库」开关：贴齐 chip 行高，别把筛选区撑高 */
.sdas-filters .sdas-checkbox {
  flex: none;
  margin-top: -2px;
}

/*
  「版权方 / 类型 / 演员」三行用**等宽格子**铺 chip：一行 N 个等宽格子、整齐换行；
  长名字在格内省略，完整名走 chip 的 title 悬停提示。格子间距 8px：
  行高 = 32(chip) + 8(gap) = 40px，与折叠态的裁切线（.sdas-clip）正好咬合。
*/
.sdas-filters .v-chip-group.sdas-grid-cells {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));
  gap: 8px;
  align-items: center;
}

.sdas-filters .v-chip-group.sdas-grid-cells .v-chip {
  margin: 0;
  min-width: 0;
  max-width: 100%;
  justify-content: flex-start;
}

/* 格内省略：VChip 的内容包一层 .v-chip__content（宿主产物里已证实存在） */
.sdas-filters .v-chip-group.sdas-grid-cells .v-chip__content {
  display: block;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 折叠态：整排渲染但高度裁到一行（第二排正好从 40px 起，被裁掉）；展开后摘掉裁切 */
.sdas-filters .sdas-clip {
  max-height: 40px;
  overflow: hidden;
}

.sdas-chip-count {
  margin-left: 5px;
  font-size: 11px;
  opacity: 0.6;
  letter-spacing: 0;
}

.sdas-chip-dot {
  margin-left: 4px;
  color: #fb8c00;
  font-weight: 700;
}

.sdas-search {
  width: 14rem;
  flex: 0 0 auto;
}

/* 行尾的「展开 / 收起」按钮：必须留在 chip 组外面，且不被挤压 */
.sdas-row-toggle {
  flex: 0 0 auto;
  margin-left: 4px;
}

.sdas-search-hint {
  flex: 0 1 auto;
  white-space: nowrap;
}

/* 卡片网格：列数 / 间距由 gridStyle 现算（与 ProgressiveCardGrid 同式） */
.sdas-grid {
  display: grid;
}

.sdas-item {
  min-width: 0;
}

.sdas-hover-area {
  inline-size: 100%;
}

.sdas-card {
  cursor: pointer;
}

/* 海报骨架：与宿主 .media-card-placeholder 同一口径 */
.sdas-poster-skeleton {
  inline-size: 100%;
  block-size: 100%;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.sdas-poster-empty {
  aspect-ratio: 2 / 3;
  inline-size: 100%;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

/* 悬停浮层里的文字（对应宿主 .media-card-title / .media-card-overview） */
.sdas-card-title {
  font-size: 1.125rem;
  line-height: 1.25rem;
}

.sdas-card-overview {
  font-size: 0.875rem;
  line-height: 1.125rem;
  opacity: 0.92;
}

/* 滚动加载哨兵 */
.sdas-sentinel {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  font-size: 12px;
  color: var(--sdas-fg-dim);
}

/* 空态 */
.sdas-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 56px 16px;
  color: var(--sdas-fg-dim);
  text-align: center;
}

.sdas-empty-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--sdas-fg);
}

.sdas-empty-hint {
  font-size: 13px;
  max-width: 460px;
}

/* 自绘提示条 */
.sdas-toast {
  position: fixed;
  left: 50%;
  bottom: 48px;
  transform: translateX(-50%);
  z-index: 3000;
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 13px;
  color: #fff;
  background: rgba(0, 0, 0, 0.82);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}

.sdas-toast.is-error {
  background: #c62828;
}

.sdas-fade-enter-active,
.sdas-fade-leave-active {
  transition: opacity 0.2s ease;
}

.sdas-fade-enter-from,
.sdas-fade-leave-to {
  opacity: 0;
}

/* 搜索页的量宽哨兵：零高占满一行，两个结果网格的列宽都从它量 */
.sdas-measure {
  inline-size: 100%;
  block-size: 0;
}

/* 搜索页里某一类结果为空的小提示（另一类有结果时才单独露出来） */
.sdas-search-miss {
  opacity: 0.8;
}
</style>
