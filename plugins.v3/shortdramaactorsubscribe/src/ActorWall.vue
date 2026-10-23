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
         **点卡片进本插件自绘的作品详情页**（`WorkDetail.vue`，不再跳宿主详情页）。
      3. 网格：探索页 ProgressiveCardGrid 的默认值 `minItemWidth=144 / gap=16 /
         海报 2:3`，列数按容器宽现算，卡片按 rAF 每帧 6 张渐进补齐。
      4. 无限滚动：**一次只拉一页**，铺完（渐进填充追上）才看哨兵 —— 哨兵还在视口
         600px 内才拉下一页（面板里滚动的是宿主钉的内容容器，见下方「滚动容器」）；
         用 `[media_source, media_id, type, season]` 去重；本页 0 条或本页签名与上一页
         相同即收尾；有数据后预取 margin 600。

    本插件自己的部分（版面自上而下：标题行 → 搜索行 → 视图标签条 → 视图槽位 → 卡片区）：
      - **视图切换是顶部标签条**（「已订阅」/「作品」/「已关注演员 N」/「发现演员」，
        2026-10-22 用户定的顺序），不再往筛选栏里塞一个「演员」chip —— 演员卡与作品
        分类是两种东西，不混在一排里。标签条常驻，与筛选行、卡片区各自固定。
      - **视图槽位**：作品标签页里是作品维度筛选行（版权方 → 类型 → 年份 → 排序 →
        媒体库，用户定的排版）；演员标签页里是演员页自己的工具栏（已关注 N 位 + 刷新）。
        槽位是**内容自适应高度**（用户定的：不留白）—— 演员页工具栏只有一行，槽位就
        只有一行高，卡片区紧跟着往上收，不会为对齐作品页筛选区而空出一段白。
        两页各装各的行，永不混排（演员卡与作品分类是两种东西）。
        「版权方 / 类型」两行选项多（真机 60 / 60 项），折叠态**只露一排**（CSS 高度
        裁切，渲染全部）+ 行尾「展开」按钮，展开后换行铺全部并可「收起」。
      - 「搜索」行常驻在标签条**上面**（两个标签页共用；放槽位里的话演员页就没法搜人）：
        演员与作品都查（短剧百科同一站，两条检索链路并行），有词时搜索结果优先独占主体；
        清空后回到当前标签页那一页。
      - **两个整页视图**（都排在最前面，见下）：点作品卡 → 作品详情页（`WorkDetail.vue`），
        点演员卡 → 演员作品页（`ActorDetail.vue`，版式照宿主的演员详情页）。
        两者都不在面板里 ⇒ 顶栏 / 搜索行 / 标签条 / 槽位整块让位，从顶部铺满；
        换标签、改筛选、或搜索栏里输词都会自动退出（否则会卡在那一页上，点了像没反应）。
      - **演员卡照宿主 `PersonCard` 复刻**（2:3 卡 + 圆形头像 + 姓名 + 身份行），
        悬停浮层里放本插件自己的「百科页 / 关注」两个钮。
      - **已关注演员不分组**：按拼音 A-Z 平铺（非汉字垫底到 `#`），右侧一条「滚动条」式
        字母索引（悬停显示字母、拖动连续跳转）。性别只是槽位里的筛选，不决定顺序。
      - 标题行只放「短剧演员」与统计小字；筛选栏里**没有任何按钮**（探索页同款）：
        加演员走「搜索」行搜人后点卡片上的「订阅」；没有刷新按钮（快照按小时级自动更新）。

    **两个整页视图**（都是全屏：不在 `.sdas` 面板里，顶栏 / 搜索行 / 标签条 / 槽位整块让位）
      ① 作品详情页 —— 点作品卡进入（`WorkDetail.vue`）；
      ② 演员作品页 —— 点演员卡 / 作品详情里的演员阵容卡进入（`ActorDetail.vue`）。
    两者都从面板最顶部铺满，左上返回键回**上一页** —— 与宿主的浏览器历史同构：
    作品详情 → 点演员阵容卡 → 演员作品页 → 返回 ⇒ 回作品详情（而不是直接甩回列表）。
    层层叠放由 `viewLayer` 记最上面那层，`actorOpenedFrom` / `workOpenedFrom` 记来源。

    ⚠️ 排在所有列表之前：两个都是「钻进一个东西」，任何列表分支都得让位。
  -->
  <ActorDetail
    v-if="viewLayer === 'actor' && detailActor"
    :api="props.api"
    :actor="detailActor"
    :subscribed="isActorAdded(detailActor)"
    :busy-follow="isActorBusy(detailActor)"
    :subscribed-ids="subscribed"
    :busy-subscribe-all="subscribingAllKey === actorKey(detailActor)"
    @back="backFromActor()"
    @toggle-actor="toggleActor(detailActor)"
    @subscribe-all="subscribeAllWorks(detailActor)"
    @open-work="openWorkDetail"
    @search="searchWork"
    @subscribe="subscribe"
  />

  <WorkDetail
    v-else-if="viewLayer === 'work' && detailWork"
    :api="props.api"
    :work="detailWork"
    :subscribed="subscribed.has(detailWork.media_id)"
    :subscription="detailSubscription"
        :sub-editable="subEditable"
    :followed-ids="followedActorIds"
    :busy-ids="busyActorIds"
    :subscribing="subscribing"
    @back="backFromWork()"
    @open-actor="openActorFromWork"
    @search="searchWork"
    @subscribe="subscribe"
    @toggle-actor="toggleActorFromWork"
    @open-adapted="openAdaptedFromWork"
    @filter-genre="applyGenreFilter"
    @sub-updated="onDetailSubUpdated"
  />

  <AdaptedDetail
    v-else-if="viewLayer === 'adapted' && detailAdapted"
    :api="props.api"
    :novel="detailAdapted"
    :media-id="detailWork?.media_id || ''"
    :subscribed-ids="subscribed"
    @back="backFromAdapted()"
    @open-work="openWorkDetail"
    @search="searchWork"
    @subscribe="subscribe"
  />

  <div v-else class="sdas" :class="{ 'sdas--full': full }">
    <!-- 标题行：只放标题与统计；筛选栏里不放任何按钮 -->
    <div class="sdas-head">
      <div class="sdas-head-main">
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

    </div>

    <!--
      搜索行：**常驻在标签条上方**（用户定的位置）—— 两个标签页共用这一条搜索，
      换页时它不挪位置；有词时搜索结果优先独占卡片区，清空后回到当前标签页那一页。
      演员与作品都查（短剧百科同一站，两条检索链路并行）。
    -->
    <div class="px-3 sdas-search-row">
      <div class="flex justify-start align-center">
        <div class="mr-5 sdas-row-label"><v-label>搜索</v-label></div>
        <v-text-field
          v-model="actorQuery"
          class="sdas-search"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          placeholder="搜索演员或作品（输入即查本地缓存，回车 / 搜索打站点）"
          prepend-inner-icon="mdi-magnify"
          @keydown.enter="runLookup('site')"
        />
        <!--
          输入即查**本地缓存**（作品墙已加载的行 + 关注列表 + 已加载的演员目录，零请求）；
          这枚按钮（与回车）才去数据源 `/lookup` 打站内搜索（同名多季会列全）。
        -->
        <v-btn
          class="sdas-search-btn ml-2"
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-database-search"
          :loading="searchingActors || searchingWorks"
          @click="runLookup('site')"
        >
          搜索
        </v-btn>
        <span v-if="searchActive" class="sdas-search-hint text-body-2 text-medium-emphasis ml-3">
          <template v-if="searchingActors || searchingWorks">正在查短剧百科…</template>
          <template v-else-if="searchSummary">
            {{ searchSummary }}
            <span v-if="searchMode === 'cache'"> · 本地缓存</span>
            <span v-else-if="searchSource === 'library'"> · 站点无结果，来自数据源库</span>
            <span v-else-if="searchMode === 'site'"> · 站点检索</span>
          </template>
          <template v-else-if="searchMode === 'cache'">缓存里没有，按回车 / 搜索打站点查</template>
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
      视图标签条：「已订阅 / 作品 / 已关注演员 / 发现演员」——视图切换，不是筛选，所以**不跟作品分类混一排**。
      自绘标签条（不依赖宿主的 VTabs：联邦只保证 vue 共享，Vuetify 组件是否全局注册不可控）；
      类名全部自有前缀（不含 `.v-`，联邦 CSS 门禁放行）。

      版式**照宿主探索页顶栏那排来源标签（TheMovieDb / 豆瓣 / Bangumi…）一比一复刻**：
      宿主那份是 `layouts/default/components/HeaderTab.vue`（页面里的 VWindow 只是内容区，
      标签本身由 `useDynamicHeaderTab` 注册到顶栏）—— pill 圆角 20px + 底部 3px 主色指示条
      （宽 70%、`scaleX` 展开）+ 未选中 hover 的 5% 主色底 + 标签溢出时右侧渐隐指示与
      左右 28px 圆形滚动钮（触摸端隐藏，靠手势横滑）。
    -->
    <div class="px-3 sdas-tabs">
      <button
        v-if="showLeftButton"
        type="button"
        class="sdas-tabs-scroll sdas-tabs-scroll-left"
        aria-label="标签向左滚动"
        @click="scrollTabs('left')"
      >
        <v-icon size="small">mdi-chevron-left</v-icon>
      </button>

      <div
        ref="tabsContainerRef"
        class="sdas-tabs-track"
        :class="{ 'show-indicator': showTabsScrollIndicator }"
        role="tablist"
      >
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          role="tab"
          class="sdas-tab"
          :class="{ 'is-active': activeTab === tab.value }"
          :aria-selected="activeTab === tab.value"
          :title="tab.hint"
          @click="activeTab = tab.value"
        >
          {{ tab.title }}
          <span v-if="tab.value === 'actors'" class="sdas-chip-count">{{ followedCount }}</span>
          <span v-else-if="tab.value === 'subs'" class="sdas-chip-count">{{ subItems.length }}</span>
        </button>
      </div>

      <button
        v-if="showRightButton"
        type="button"
        class="sdas-tabs-scroll sdas-tabs-scroll-right"
        aria-label="标签向右滚动"
        @click="scrollTabs('right')"
      >
        <v-icon size="small">mdi-chevron-right</v-icon>
      </button>
    </div>

    <!--
      视图槽位：已订阅页 = 订阅工具栏；作品标签页 = 作品维度筛选行；演员标签页 = 演员页工具栏。
      各页***不共用同一批行***（订阅卡 / 演员卡与作品分类是两种东西），槽位高度随内容自适应
      —— 演员页那一行工具栏不会留出作品页筛选区那么高的空白。
    -->
    <div class="px-3 sdas-slot">
      <!--
        已订阅页槽位：一行工具栏（订阅 N 部 + 在库筛选 + 刷新 + 引擎说明）。
        与演员页工具栏同一套版式。
      -->
      <template v-if="activeTab === 'subs'">
        <div class="flex justify-start align-center sdas-actor-bar">
          <div class="text-body-2 text-medium-emphasis">
            已订阅 · <b>{{ subItems.length }}</b> 部作品
          </div>
          <!-- 在库筛选（2026-10-23 用户口径）：未下载（第一列）/ 全部 / 已入库 / 未入库。
               null（探针不可用 / 还没查到）归进「全部」，不计入两侧 -->
          <v-chip-group
            :model-value="subLibFilter"
            mandatory
            selected-class="text-primary"
            class="ml-3"
            @update:model-value="subLibFilter = $event as SubLibFilter"
          >
            <v-chip
              filter
              tile
              size="small"
              value="undown"
              title="订阅了但还没下成、也不在媒体库的作品（默认视图，空着也停在这页）"
            >
              未下载 {{ subLibCounts.undown }}
            </v-chip>
            <v-chip filter tile size="small" value="all">
              全部 {{ subItems.length }}
            </v-chip>
            <v-chip
              filter
              tile
              size="small"
              value="in"
              :disabled="!subLibCounts.hasIn"
            >
              已入库 {{ subLibCounts.hasIn }}
            </v-chip>
            <v-chip
              filter
              tile
              size="small"
              value="not"
              :disabled="!subLibCounts.hasNot"
            >
              未入库 {{ subLibCounts.hasNot }}
            </v-chip>
          </v-chip-group>
          <v-btn
            icon
            variant="text"
            size="x-small"
            class="ml-1"
            :loading="subsLoading"
            title="刷新订阅与搜索状态"
            @click="loadSubscriptions()"
          >
            <v-icon size="18">mdi-refresh</v-icon>
          </v-btn>
          <!--
            随机订阅 + 立即搜索全部（2026-10-23 用户口径，都在主界面）：
            随机订阅 = 从作品墙全集随机挑 N 部未订阅且未入库的作品；数量输入框
            1~10（默认 1）。立即搜索 = 现在就对全部订阅跑一轮（清冷却；
            已入库 / 已下载 / 历史已有照旧跳过）。
          -->
          <v-text-field
            v-model.number="randomCount"
            type="number"
            min="1"
            max="10"
            density="compact"
            hide-details
            variant="outlined"
            class="sdas-random-count ml-3"
            title="随机订阅数量（1~10）"
          />
          <v-btn
            variant="tonal"
            color="warning"
            size="small"
            prepend-icon="mdi-shuffle-variant"
            :loading="randomSubscribing"
            title="从作品墙全集随机订阅 N 部未入库的作品"
            @click="randomSubscribe()"
          >
            随机订阅
          </v-btn>
          <v-btn
            variant="tonal"
            color="info"
            size="small"
            prepend-icon="mdi-magnify-scan"
            :loading="searchAllRunning"
            title="立即对全部订阅作品执行一轮订阅搜索（已入库 / 已下载的自动跳过）"
            @click="searchAllNow()"
          >
            立即搜索
          </v-btn>
          <span v-if="subEngine" class="text-caption text-medium-emphasis ml-3">
            {{ subEngine === 'self' ? '订阅搜索：插件自建（不进系统订阅页）' : '订阅搜索：走宿主订阅系统' }}
          </span>
        </div>
      </template>

      <template v-else-if="activeTab === 'works'">
        <!--
          筛选行：与探索页同构。
          一行一个维度：`div.flex.justify-start.align-center` > `div.mr-5`(VLabel) + `VChipGroup`，
          里面是 `VChip{filter, tile, value, color: 选中 ? "primary" : ""}`（选中项前面的 ✓
          是 VChip 的 `filter`，再点一次即取消）。
          选项特别多的一行（版权方 / 类型）折叠态整排渲染但用 `.sdas-clip` 把高度裁到一行，
          行尾「展开 / 收起」按钮切换；按钮必须放在 chip 组**外面** —— 放进组里会被分组当成
          一个可选项，一点就把当前维度的选中态清掉。
          ⚠️ 门禁：所有含 `.v-` 的选择器会被 vite 的 CSS 门禁整条丢掉（联邦插件不得发布
          组件库基础样式），所以 chip 组内部的换行 / 等宽格子类规则一律不生效，只保留
          自有类名上的规则。
        -->
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

        <!--
          播放平台（「在哪播」，如 红果短剧 / 河马剧场）
          ⚠️ 当前数据源的**作品卡**不带 platform（平台只写在作品详情页的 meta 文案里）
          ⇒ 这一行恒为空、`v-if` 直接整行隐藏，与「版权方」同一套降级口径：
          数据源哪天在卡片层补上，这里不用改、自动出这一行。
        -->
        <div v-if="facets.platforms.length" class="flex justify-start align-center">
          <div class="mr-5 sdas-row-label"><v-label>播放平台</v-label></div>
          <v-chip-group
            class="sdas-grid-cells"
            column
            :class="{ 'sdas-clip': !isExpanded('platform') }"
            :model-value="platform || undefined"
            @update:model-value="platform = pick($event)"
          >
            <v-chip
              v-for="item in facets.platforms"
              :key="item.value"
              :value="item.value"
              :color="platform === item.value ? 'primary' : ''"
              filter
              tile
              :title="item.value"
            >
              {{ item.value }}<span class="sdas-chip-count">{{ item.count }}</span>
            </v-chip>
          </v-chip-group>
          <v-chip
            v-if="facets.platforms.length > COLLAPSED_LIMIT"
            class="sdas-row-toggle"
            variant="text"
            :prepend-icon="isExpanded('platform') ? 'mdi-chevron-up' : 'mdi-chevron-down'"
            @click="toggleRow('platform')"
          >
            {{ isExpanded('platform') ? '收起' : '展开' }}
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

        <!--
          ⚠️ 这里**没有**「演员」行 —— 视图切换已经挪到上方的标签条。
          演员卡（演员页）与作品分类（这些行）是两种东西，不放在同一排里筛。
        -->

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

        <!--
          媒体库两张卡（2026-10-23 用户口径）：「未入库」「未订阅」—— 点一下即按该
          条件筛，再点取消。热度 / 播放 / 评分三种排序已撤（墙的快照里那些值恒为 0，
          排了也是并列），排序只剩「首播日期」，不再给排序行。
        -->
        <div class="flex justify-start align-center">
          <div class="mr-5 sdas-row-label"><v-label>媒体库</v-label></div>
          <div class="sdas-library-cards">
            <button
              type="button"
              class="sdas-library-card"
              :class="{ 'is-active': onlyNotInLibrary }"
              :disabled="!probeAvailable"
              title="只显示还没进 MoviePilot 媒体库的作品（判定与媒体详情页一致：身份精确匹配，未命中按片名+年份回退）"
              @click="onlyNotInLibrary = !onlyNotInLibrary"
            >
              <v-icon size="16" class="mr-1">mdi-database-off-outline</v-icon>
              <span>未入库</span>
              <span v-if="onlyNotInLibrary && filteredCount" class="sdas-library-count">
                {{ filteredCount }}
              </span>
            </button>
            <button
              type="button"
              class="sdas-library-card"
              :class="{ 'is-active': onlyNotSubscribed }"
              title="只显示还没订阅的作品（订阅清单 = 插件订阅清单 ∪ 宿主 djbaike 订阅，与卡片红心同一份）"
              @click="onlyNotSubscribed = !onlyNotSubscribed"
            >
              <v-icon size="16" class="mr-1">mdi-heart-off-outline</v-icon>
              <span>未订阅</span>
              <span v-if="onlyNotSubscribed && filteredCount" class="sdas-library-count">
                {{ filteredCount }}
              </span>
            </button>
          </div>
        </div>

      </template>

      <!--
        演员页槽位：① 分类行 —— 与作品页「类型」行**同一套**（`VLabel` + `VChipGroup`
        里一排 `VChip{filter, tile}`，带计数角标，再点一次即取消 = 全部）；
        ② 工具栏 —— 「已关注 N 位 + 刷新」。
        槽位随内容自适应高度，卡片区紧跟在这两行下面，不留白。
      -->
      <template v-else-if="activeTab === 'actors'">
        <div class="flex justify-start align-center">
          <div class="mr-5 sdas-row-label"><v-label>分类</v-label></div>
          <v-chip-group
            :model-value="actorGender || undefined"
            @update:model-value="actorGender = pick($event)"
          >
            <v-chip
              v-for="group in actorGroups"
              :key="group.key"
              :value="group.key"
              :color="actorGender === group.key ? 'primary' : ''"
              :title="actorGender === group.key ? '取消分类（看全部）' : `只看${group.title}`"
              filter
              tile
            >
              {{ group.title }}<span class="sdas-chip-count">{{ group.items.length }}</span>
            </v-chip>
          </v-chip-group>
        </div>

        <div class="flex justify-start align-center sdas-actor-bar">
          <div class="text-body-2 text-medium-emphasis">
            已关注 · <b>{{ followedActors.length }}</b> 位演员
          </div>
          <v-btn
            icon
            variant="text"
            size="x-small"
            class="ml-1"
            :loading="followedLoading"
            title="刷新演员列表（会给还没有头像的演员补一次档案）"
            @click="refreshFollowed()"
          >
            <v-icon size="18">mdi-account-sync-outline</v-icon>
          </v-btn>
          <span v-if="followedError" class="text-body-2 text-medium-emphasis ml-3">
            {{ followedError }}
          </span>
        </div>
      </template>

      <!--
        发现页槽位（2026-10-23 用户口径：发现演员 → 发现，导演 / 编剧分类移除）：
        「目录」只留演员一本；同一行右侧接着榜单 chips（热播 / 热搜 / 收藏 / …，
        不再特意标「榜单」两字），点哪本看哪本，点「演员」回到人物目录。
      -->
      <template v-else>
        <div class="flex justify-start align-center">
          <div class="mr-5 sdas-row-label"><v-label>目录</v-label></div>
          <v-chip-group
            :model-value="discoverView"
            @update:model-value="setDiscoverView($event)"
          >
            <v-chip
              value="people"
              :color="discoverView === 'people' ? 'primary' : ''"
              title="翻站点的演员目录"
              filter
              tile
            >
              演员
            </v-chip>
            <v-chip
              v-for="item in rankItems"
              :key="item.key"
              :value="item.key"
              :color="discoverView === item.key ? 'primary' : ''"
              :title="`看站点${item.name}`"
              filter
              tile
            >
              {{ item.name }}
            </v-chip>
          </v-chip-group>
        </div>

        <div class="flex justify-start align-center sdas-actor-bar">
          <div class="text-body-2 text-medium-emphasis">
            <template v-if="discoverView === 'people'">
              <template v-if="peopleLoading">正在取{{ peopleKindLabel }}目录…</template>
              <template v-else-if="peopleRows.length">
                已加载 <b>{{ peopleRows.length }}</b> 位{{ peopleKindLabel }}
              </template>
              <template v-else>{{ peopleMessage || '还没有加载' }}</template>
            </template>
            <template v-else>
              <template v-if="rankLoading">正在取{{ rankName }}…</template>
              <template v-else-if="rankMedias.length">{{ rankName }} · {{ rankMedias.length }} 部</template>
              <template v-else>{{ rankMessage || '还没有加载' }}</template>
            </template>
          </div>
          <!-- 分页改成**滚到底自动续拉**（2026-10-18 用户口径：与作品墙一致） -->
          <span
            v-if="discoverView === 'people' && peopleRows.length && peopleHasMore"
            class="text-caption text-medium-emphasis ml-3"
          >
            继续下滑加载更多
          </span>
          <span
            v-if="discoverView === 'people' && peopleError"
            class="text-body-2 text-medium-emphasis ml-3"
          >
            {{ peopleError }}
          </span>
        </div>
      </template>
    </div>

    <!--
      演员搜索结果：搜索框里有词时独占这一块（作品墙暂时让位）。
      卡片与作品卡**同一套**（VCard.media-card + 2:3 图 + 悬停浮层），
      只是「海报」换成演员头像，「订阅」的含义是把演员加进本插件的演员表。
    -->
    <template v-if="searchActive">
      <!-- 量宽哨兵：演员区 / 作品区两个网格的列宽都从它量（零高，不影响布局） -->
      <div ref="gridRef" class="sdas-measure" aria-hidden="true" />

      <!-- 两个搜索都还没回来时先铺 loading（探索页同款跳动圆点） -->
      <LoadingBanner
        v-if="!actorResults.length && !workResults.length && (searchingActors || searchingWorks)"
        text="正在查短剧百科…"
      />

      <template v-else>
        <!-- 演员：交短剧百科 search_actors 找，卡片是「头像 + 悬停浮层」 -->
        <div v-if="actorResults.length" class="mb-6">
          <div class="text-body-2 text-medium-emphasis mb-2">演员 · {{ actorResults.length }}</div>
          <div class="sdas-grid" :style="gridStyle" :ref="setGridNode">
            <div v-for="item in actorResults" :key="item.actor_id" class="sdas-item">
              <ActorCard
                :item="item"
                :added="isActorAdded(item)"
                :busy="addingActorId === item.actor_id || removingActorId === item.actor_id"
                :loaded="isPosterLoaded(actorKey(item))"
                subscribe-all
                :subscribe-all-busy="subscribingAllKey === actorKey(item)"
                @open="openActorDetail(item)"
                @page="openActorPage(item)"
                @toggle="isActorAdded(item) ? unsubscribeActor(item) : subscribeActor(item)"
                @subscribe-all="subscribeAllWorks(item)"
                @poster="markPosterLoaded(actorKey(item))"
              />
            </div>
          </div>
        </div>
        <div v-else-if="!searchingActors" class="sdas-search-miss text-body-2 text-medium-emphasis mb-3">
          没有找到相关演员
        </div>

        <!-- 作品：走宿主搜索同一条链路（run_module("search_medias")），卡片与主墙共用 -->
        <div v-if="workResults.length">
          <div class="text-body-2 text-medium-emphasis mb-2">作品 · {{ workResults.length }}</div>
          <div class="sdas-grid" :style="gridStyle" :ref="setGridNode">
            <div v-for="work in workResults" :key="work.key" class="sdas-item">
              <WorkCard
                :work="work"
                :loaded="isPosterLoaded(work.key)"
                :subscribed="subscribed.has(work.media_id)"
                :subscribing="subscribingId"
                :searching="searchNowId"
                @poster="markPosterLoaded(work.key)"
                @open="openWorkDetail"
                @search="searchWork"
                @subscribe="subscribe"
                @search-now="searchNow"
              />
            </div>
          </div>
        </div>
        <div v-else-if="!searchingWorks && actorResults.length" class="sdas-search-miss text-body-2 text-medium-emphasis">
          没有找到相关作品
        </div>

        <!-- 演员、作品都没搜到（探索页同款空态：404 + 胶卷盘） -->
        <NoDataFound
          v-if="!actorResults.length && !workResults.length"
          error-code="404"
          :error-title="`没找到「${searchKeyword}」`"
          error-description="换个名字试试 —— 短剧百科只收录站上有的演员和作品"
        />
      </template>
    </template>

    <!--
      演员页：顶部标签条点亮「已关注演员」时独占卡片区（作品墙让位）。
      卡片与搜索结果里的演员卡是**同一个组件**（ActorCard.vue），版式照宿主 `PersonCard`
      复刻（2:3 卡 + 圆形头像 + 姓名 + 身份行），悬停浮层里是「百科页 / 取消关注」两个钮。
      **点卡片进「演员作品页」**（整页，`ActorDetail.vue`，不在卡片区里）。

      卡片区是**一个网格集合铺**（用户要求：卡片不再按性别分块，「集合显示」）——
      没有组标题、没有组间距。性别只作为**分类筛选**留在上面的槽位里
      （选中某一类就只铺那一类，不选则全部；排序统一按拼音 A-Z）。
      已关注的演员全部铺出来（不再折叠 / 分批）。
      关注数与「刷新档案」按钮在上方的视图槽位里（那是演员页自己的工具栏）。
    -->
    <template v-else-if="activeTab === 'actors'">
      <!-- 头一回加载（还没有卡片可铺）：探索页同款跳动圆点 -->
      <LoadingBanner v-if="followedLoading && !followedActors.length" text="正在取演员列表…" />
      <!-- 一位演员都没关注 -->
      <NoDataFound
        v-else-if="!followedActors.length"
        error-code="404"
        error-title="还没有关注的演员"
        error-description="在「搜索」里搜一位演员，点卡片上的「订阅」加进来"
      />
      <!-- 选中的分类里一位都没有（例如刚把最后一位移出关注） -->
      <NoDataFound
        v-else-if="!shownActors.length"
        error-code="404"
        error-title="这一类里还没有关注的演员"
        error-description="点上面的分类标签取消分类，就能看全部演员"
      />
      <!--
        已关注的演员：**不分组**，按拼音 A-Z（非汉字垫底到 `#`）一张网格铺到底
        （2026-10-20 用户口径：不要组标题、不要分组）。

        非虚拟渲染：96 张卡全在 DOM 里，但卡片做了**懒挂载**（见 `observeCell`）：
        每格先占 2:3 占位块撑住高度，滚到 ±600px 内才换真卡，避免一进页就并发 96 个头像请求。

        外层这层 div 同时是右侧「滚动条」的定位锚点（`AlphaIndex` 按它的
        `getBoundingClientRect()` 现算轨道位置）。
      -->
      <div v-else ref="actorGridAnchor" class="sdas-actor-grid">
        <div
          v-for="item in shownActors"
          :key="actorKey(item)"
          class="sdas-actor-cell"
          :data-cell-key="actorKey(item)"
          :ref="(el) => observeCell(el as Element | null, actorKey(item))"
        >
          <ActorCard
            v-if="isCellMounted(actorKey(item))"
            :item="item"
            :state="item.state"
            :added="true"
            :busy="addingActorId === item.actor_id || removingActorId === item.actor_id"
            :loaded="isPosterLoaded(actorKey(item))"
            subscribe-all
            :subscribe-all-busy="subscribingAllKey === actorKey(item)"
            @open="openActorDetail(item)"
            @page="openActorPage(item)"
            @toggle="unsubscribeActor(item)"
            @subscribe-all="subscribeAllWorks(item)"
            @poster="markPosterLoaded(actorKey(item))"
          />
        </div>

        <!-- A-Z 快速滚动：做成**滚动条**（贴内容右边缘的细轨道 + 可拖拇指），悬停/拖动都浮出字母 -->
        <AlphaIndex
          :stops="actorLetterStops"
          :anchor="actorGridAnchor"
          @jump="jumpToActorLetter"
        />
      </div>
    </template>

    <!--
      发现页：人物目录（演员）与站点榜单二选一（上面槽位里的 chips 决定）。
      人物卡与搜索结果里的演员卡是**同一个组件**；点卡片进演员作品页，浮层里是
      「百科页 / 关注」。目录本身是分页的（24 条/页，演员目录上千页），所以底部给
      「加载更多」，不做无限滚动 —— 免得让人以为能一直翻到底。
    -->
    <template v-else-if="activeTab === 'people' && discoverView === 'people'">
      <LoadingBanner
        v-if="peopleLoading && !peopleRows.length"
        :text="`正在取${peopleKindLabel}目录…`"
      />
      <NoDataFound
        v-else-if="!peopleRows.length"
        error-code="404"
        :error-title="peopleMessage ? '人物目录还取不到' : `没有取到${peopleKindLabel}`"
        :error-description="peopleMessage || '数据源这次没有返回内容，过一会儿再试'"
      />
      <ProgressiveCardGrid
        v-else
        :items="peopleRows"
        :min-item-width="MIN_ITEM_WIDTH"
        :item-aspect-ratio="1.5"
        :gap="GRID_GAP"
        :overscan-rows="2"
        :get-item-key="actorKey"
      >
        <template #default="{ item }">
          <ActorCard
            :item="item"
            :added="isActorAdded(item)"
            :busy="addingActorId === item.actor_id || removingActorId === item.actor_id"
            :loaded="isPosterLoaded(actorKey(item))"
            :subscribe-all="peopleKind === 'yanyuan'"
            :subscribe-all-busy="subscribingAllKey === actorKey(item)"
            @open="openActorDetail(item)"
            @page="openActorPage(item)"
            @toggle="isActorAdded(item) ? unsubscribeActor(item) : subscribeActor(item)"
            @subscribe-all="subscribeAllWorks(item)"
            @poster="markPosterLoaded(actorKey(item))"
          />
        </template>
      </ProgressiveCardGrid>

      <!-- 滚动加载哨兵：滚到底自动拉下一页（与作品墙同一个机制） -->
      <div ref="peopleSentinel" class="sdas-sentinel">
        <v-progress-circular
          v-if="peopleLoading && peopleRows.length"
          indeterminate
          size="20"
          width="2"
        />
        <span v-else-if="peopleRows.length && !peopleHasMore">
          已到末尾 · 共 {{ peopleRows.length }} 位{{ peopleKindLabel }}
        </span>
      </div>
    </template>

    <!--
      发现页 · 榜单：**与「演员」目录完全同一套加载方式**（2026-10-23 用户口径）——
      同一个 ProgressiveCardGrid 结构、同一套底部哨兵写法，只是榜单页没有翻页，
      哨兵不做续拉，只在末尾报「已到末尾 · 共 N 部」。
      卡片复用 WorkCard（与作品墙同一套版式与操作：点开进作品详情、可搜索可订阅，
      右上带在库勾、右下带收藏红心）。
    -->
    <template v-else-if="activeTab === 'people' && discoverView !== 'people'">
      <LoadingBanner
        v-if="rankLoading && !rankMedias.length"
        :text="`正在取${rankName}…`"
      />
      <NoDataFound
        v-else-if="!rankMedias.length"
        error-code="404"
        :error-title="rankMessage ? '榜单还取不到' : `没有取到${rankName}`"
        :error-description="rankMessage || '数据源这次没有返回内容，过一会儿再试'"
      />
      <ProgressiveCardGrid
        v-else
        :items="rankWorkItems"
        :min-item-width="MIN_ITEM_WIDTH"
        :item-aspect-ratio="1.5"
        :gap="GRID_GAP"
        :overscan-rows="2"
        :get-item-key="(item: WorkItem) => item.key"
      >
        <template #default="{ item }">
          <WorkCard
            :work="item"
            :loaded="isPosterLoaded(item.key)"
            :subscribed="subscribed.has(item.media_id)"
            :subscribing="subscribingId"
            :searching="searchNowId"
            @poster="markPosterLoaded(item.key)"
            @open="openWorkDetail"
            @search="searchWork"
            @subscribe="subscribe"
            @search-now="searchNow"
          />
        </template>
      </ProgressiveCardGrid>

      <!-- 底部与「演员」目录同款哨兵：滚到底续拉下一页（每页 30 部，与作品页同节奏） -->
      <div v-if="rankMedias.length" ref="rankSentinel" class="sdas-sentinel">
        <v-progress-circular
          v-if="rankLoading"
          indeterminate
          size="20"
          width="2"
        />
        <span v-else-if="rankHasMore" class="text-caption text-medium-emphasis">
          继续下滑加载更多
        </span>
        <span v-else>已到末尾 · 共 {{ rankMedias.length }} 部</span>
      </div>
    </template>

    <!--
      已订阅页：与作品墙**完全同一套卡片**（WorkCard，2026-10-22 用户口径：
      所有卡片风格与点开方式一致）。订阅行映射成 WorkItem 后走同款虚拟网格 ——
      悬停浮层（年份/标题/简介 + 左搜索右订阅）、点卡片进作品详情、点爱心弹
      取消订阅确认，行为与作品墙一比一；左下角多一枚灰色「已暂停」（仅暂停行）。
    -->
    <template v-else-if="activeTab === 'subs'">
      <LoadingBanner v-if="subsLoading && !subWorkItems.length" text="正在取订阅列表…" />
      <NoDataFound
        v-else-if="!subWorkItems.length"
        error-code="404"
        error-title="还没有订阅的作品"
        error-description="在「作品」页找到想追的剧，点卡片上的「订阅」，它就会出现在这里并自动搜索下载"
      />
      <NoDataFound
        v-else-if="!shownSubWorkItems.length"
        error-code="404"
        :error-title="subLibFilter === 'in' ? '没有已入库的订阅' : subLibFilter === 'undown' ? '没有未下载的订阅' : '没有未入库的订阅'"
        error-description="换一个筛选看看，或点工具栏里的「全部」"
      />
      <GlassMediaBackdrop v-else>
        <ProgressiveCardGrid
          :items="shownSubWorkItems"
          :min-item-width="MIN_ITEM_WIDTH"
          :item-aspect-ratio="1.5"
          :gap="GRID_GAP"
          :get-item-key="(item: WorkItem) => item.key"
        >
          <template #default="{ item }">
            <WorkCard
              :work="item"
              :loaded="isPosterLoaded(item.key)"
              :subscribed="subscribed.has(item.media_id)"
              :subscribing="subscribingId"
              :searching="searchNowId"
              @poster="markPosterLoaded(item.key)"
              @open="openWorkDetail"
              @search="searchWork"
              @subscribe="subscribe"
              @search-now="searchNow"
            />
          </template>
        </ProgressiveCardGrid>
      </GlassMediaBackdrop>
    </template>

    <template v-else>
      <!--
        作品墙（2026-10-22：订阅面板已升为「已订阅」标签页，这里恢复纯作品墙）。
      -->
      <LoadingBanner v-if="!works.length && !error" text="正在从短剧百科获取作品…" />

      <!-- 错误态（照探索页的 error 插槽：提示 + 重试） -->
      <div v-else-if="error && !works.length" class="d-flex flex-column align-center ga-2 py-4">
        <span class="text-body-2 text-medium-emphasis">网络错误</span>
        <v-btn prepend-icon="mdi-refresh" size="small" variant="tonal" @click="reload">重试</v-btn>
      </div>

      <!-- 空态（探索页同款：404 + 胶卷盘） -->
      <NoDataFound
        v-else-if="!works.length"
        error-code="404"
        :error-title="!actorCount ? '还没有添加演员' : '没有符合条件的作品'"
        :error-description="
          !actorCount
            ? '在「搜索」里搜一位演员，点卡片上的「订阅」加进来'
            : filteredOut
              ? '换个筛选条件试试'
              : emptyHint
        "
      />

      <!--
        作品墙：探索页式海报卡网格。
        列数 = floor((容器宽 + gap) / (minItemWidth + gap))，与 ProgressiveCardGrid 同式；
        行高由 2:3 海报决定（= 列宽 × 1.5）。
        卡片与宿主 MediaCard 同款：左上「短剧」徽标（探索页电视剧那一档靛蓝）、
        右上评分徽标或已入库勾，悬停浮层是年份 / 标题 / 简介 + 搜索与订阅两个按钮；
        点卡片进本插件自绘的作品详情页。

        外面那层 `GlassMediaBackdrop` 是探索页同款：glass 主题下把这一片卡片的
        背景采样合并成一个层（非 glass 主题自动退化成普通包裹层，零副作用）。
        宿主那边**只有作品列表**有它，演员列表没有 —— 这里同样只包作品网格。
      -->
      <GlassMediaBackdrop v-else>
        <!--
          虚拟滚动网格（宿主 ProgressiveCardGrid 同款复刻）：
          - 整份列表高度由上下 spacer **立即**撑出 ⇒ 第一页一到滚动条就是全长的，
            「滑到哪加载到哪」的节奏和探索页一致；
          - DOM 只挂「视口 ± 4 行」的卡片，滚多深都不会把页面压死。
          列数 / 间距公式与旧 `sdas-grid` 相同（min 144px + 16px 间距）。
        -->
        <ProgressiveCardGrid
          :items="works"
          :min-item-width="MIN_ITEM_WIDTH"
          :item-aspect-ratio="1.5"
          :gap="GRID_GAP"
          :get-item-key="workKey"
        >
          <template #default="{ item }">
            <WorkCard
              :work="item"
              :loaded="isPosterLoaded(item.key)"
              :subscribed="subscribed.has(item.media_id)"
              :subscribing="subscribingId"
              :searching="searchNowId"
              @poster="markPosterLoaded(item.key)"
              @open="openWorkDetail"
              @search="searchWork"
              @subscribe="subscribe"
              @search-now="searchNow"
            />
          </template>
        </ProgressiveCardGrid>
      </GlassMediaBackdrop>

      <!-- 滚动加载哨兵：常驻渲染，进入视口即拉下一页 -->
      <div ref="sentinel" class="sdas-sentinel">
        <v-progress-circular v-if="loadingMore" indeterminate size="20" width="2" />
        <span v-else-if="works.length && done">已到末尾 · 共 {{ total }} 部</span>
      </div>
    </template>

    <!--
      回到顶部：演员两页按「已加载条数 > 30」显，作品墙按滚动距离。
      点击后先把自己藏起来（用户 2026-10-18 口径：点了就该消失），
      再次向下滚出一段距离才重新出现（见 `backTopHiding`）。

      ⚠️ **必须 Teleport 到 body**：宿主面板容器带 `transform`，按钮留在面板里的话
      `position: fixed` 会相对那个容器定位 —— 表现是「按钮跟着页面一起滚」，
      永远停在内容里的某个位置（与提示条 / 确认层同一个坑）。搬到 body 后才真的钉在视口。
    -->
    <Teleport to="body">
      <v-btn
        v-if="showBackTop"
        class="sdas-back-top"
        icon
        color="primary"
        elevation="6"
        title="回到列表顶部"
        @click="scrollToTop()"
      >
        <v-icon size="26">mdi-arrow-up</v-icon>
      </v-btn>
    </Teleport>
  </div>

  <!--
    提示条 / 确认层一律走宿主 Vuetify 的 overlay 组件（`v-snackbar` / `v-dialog`）。

    ⚠️ **不要再自绘 `position: fixed` 覆盖层**：宿主的面板容器带 `transform`（侧栏
    动画），会让后代的 `fixed` 相对**那个容器**定位并跟着内容滚动 —— 表现是
    「弹层不在视口中央、滚一下就跑了」，还会被 `overflow: hidden` 裁掉。
    Vuetify 的 overlay 会 teleport 到 body 的 `v-overlay-container`，不受影响。
  -->
  <v-snackbar
    v-model="tipOpen"
    :timeout="3200"
    location="bottom"
    :color="tipType === 'error' ? 'error' : undefined"
  >
    {{ tip }}
  </v-snackbar>

  <v-dialog v-model="cancelOpen" max-width="380">
    <v-card>
      <v-card-title class="text-subtitle-1">取消订阅</v-card-title>
      <v-card-text class="text-body-2">
        确定取消订阅《{{ cancelTarget?.title }}》吗？取消后系统订阅页里也会一并移除。
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn size="small" variant="text" :disabled="subscribing" @click="cancelOpen = false">
          返回
        </v-btn>
        <v-btn
          size="small"
          variant="tonal"
          color="error"
          :loading="subscribing"
          @click="confirmCancelSubscribe()"
        >
          取消订阅
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!--
    悬浮「最近日志」（2026-10-24 用户口径）：**Teleport 到 body**，位置固定右下角，
    面板怎么滚都不动（宿主容器里有 transform，直接 fixed 会被它当定位祖先、跟着滚）。
    挂在根级 ⇒ 作品墙 / 已订阅 / 演员 / 发现 / 三个详情页都能看见。
    默认只露一个小胶囊，**鼠标悬浮才展开**看日志：展开时胶囊原地不动（所以不闪），
    展开后的日志区可悬停、可滚动、可点选（鼠标移到日志上不会收起）；只有收起态
    不占点击。展开方向跟随位置：拖到页面上半屏就向下展开，下半屏向上展开。
    胶囊可按住拖动，位置**记在本地存储**，下次进来还在原处。**一展开就滚到最新一行**（收起时日志区
    display:none，此时设 scrollTop 无效，所以必须在展开这一刻补滚一次）。
    读 /logs，5 秒轮询一次。
  -->
  <Teleport to="body">
    <div
      class="sdas-logfloat"
      :class="{
        'is-dragging': logDragging,
        'is-down': logExpandDown,
        'is-right': logExpandRight,
      }"
      :style="logStyle"
    >
      <!-- 日志区：默认在胶囊**上方**展开（胶囊不动 ⇒ 不闪）；拖到页面上半屏时改成
           向下展开（`is-down`，胶囊仍然不动）。展开后可滚动、可点选。 -->
      <div
        ref="logsBodyRef"
        class="sdas-logfloat-body"
        @scroll="onLogScroll()"
        @pointerenter="onLogExpand()"
      >
        <div v-for="(line, idx) in logLines" :key="idx" class="sdas-logfloat-line">{{ line }}</div>
        <div v-if="!logLines.length" class="sdas-logfloat-line sdas-logfloat-dim">暂无日志</div>
      </div>
      <div
        ref="logBarRef"
        class="sdas-logfloat-bar"
        title="按住可拖动（可拖到屏幕任意位置）"
        @pointerdown="onLogPointerDown($event)"
        @pointerenter="onLogExpand()"
      >
        <v-icon size="13">mdi-drag-variant</v-icon>
        <span>最近日志</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  addActor,
  fetchActorCards,
  fetchConfig,
  fetchLogs,
  fetchPeople,
  fetchRankWorks,
  fetchRanks,
  fetchSubscriptions,
  fetchWorks,
  lookupSite,
  pluginSubscribe,
  pluginSubscribeRandom,
  pluginSubscribeSearchAll,
  pluginSubscribeSearchNow,
  pluginUnsubscribe,
  removeActor,
  resourceSearchUrl,
  subscribeAllActor,
  type RandomSubscribeWork,
  type SubscriptionRow,
} from './api'
import ActorCard from './ActorCard.vue'
import WorkCard from './WorkCard.vue'
import ActorDetail from './ActorDetail.vue'
import AdaptedDetail from './AdaptedDetail.vue'
import type { AdaptedInfo } from './api'
import WorkDetail from './WorkDetail.vue'
import GlassMediaBackdrop from './GlassMediaBackdrop.vue'
import LoadingBanner from './LoadingBanner.vue'
import NoDataFound from './NoDataFound.vue'
import ProgressiveCardGrid from './ProgressiveCardGrid.vue'
import AlphaIndex from './AlphaIndex.vue'
import { compareByName, initialOf } from './pinyin'
import type {
  ActorCandidate,
  ActorCardItem,
  ActorFilter,
  PeopleRow,
  PluginApi,
  PluginConfig,
  RankItem,
  RankMediaItem,
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
  /** 整页留白（侧栏全页场景） */
  full?: boolean
}>()

/** 每页作品数：30（2026-10-20 从 60 收到 30 —— 首屏一次铺 60 张卡明显发沉） */
const PAGE_SIZE = 30
/** 网格列宽下限 / 间距（探索页 ProgressiveCardGrid 默认值） */
const MIN_ITEM_WIDTH = 144
const GRID_GAP = 16
/** 超过这么多项的行才有「展开」按钮（折叠态露出几项由 CSS 一行高度决定） */
const COLLAPSED_LIMIT = 12
/** 搜索演员的防抖（站外索引 + 补档案不便宜） */
const LOOKUP_DEBOUNCE = 420
/**
 * 视图标签条的四页：已订阅页 / 作品页 / 已关注演员页 / 发现演员页。
 *
 * 「发现演员」= 直接翻**站点的人物目录**（演员 / 导演 / 编剧三个分类），
 * 数据源给一页 24 条；卡片上就能关注，不必先知道名字去搜。
 */
type ViewTab = 'subs' | 'works' | 'actors' | 'people'
/** 标签排列（2026-10-22 用户定的顺序）：已订阅 → 作品 → 已关注演员 → 发现演员 */
const tabs: { title: string; value: ViewTab; hint: string }[] = [
  { title: '已订阅', value: 'subs', hint: '已订阅作品的卡片墙（含搜索 / 下载状态）' },
  { title: '作品', value: 'works', hint: '短剧百科的作品海报墙（作品分类筛选在这一页）' },
  { title: '已关注演员', value: 'actors', hint: '看已关注演员的头像卡片墙' },
  { title: '发现', value: 'people', hint: '翻短剧百科的演员目录与站点榜单（热播 / 热搜 / 收藏…），点卡片即关注或订阅' },
]

/**
 * 卡片区当前显示哪一页 —— 由**顶部标签条**切换（视图切换，不是筛选条件）。
 *
 * 「已订阅」= 已订阅作品的海报卡墙（含状态角标）；「作品」= 海报墙 + 作品维度筛选；
 * 「已关注演员」= 已关注演员的卡片墙。
 * 与搜索框互不干扰：搜索框里有词时搜索结果优先（`searchActive` 在前），
 * 清空后回到本标签对应的那一页。
 *
 * ⚠️ 它**不在**筛选栏里 —— 演员卡与作品分类是两种东西，混在一排里会让筛选栏
 * 在切页时整块变形（用户反馈）。切换只换「视图槽位」里的内容与下方卡片区。
 *
 * 默认落「已订阅」（2026-10-22 用户口径：已订阅是第一页）—— 打开面板先看
 * 自己订了什么；数据挂载时就在拉（`loadSubscriptions` 不等切页）。
 */
const activeTab = ref<ViewTab>('subs')

/**
 * 标签条的横向滚动 —— 宿主 `HeaderTab.vue` 那一套原样搬。
 *
 * 标签多了（或面板很窄）时横向可滑：右侧 40px 渐隐指示「还能往右」，
 * 左右各一个 28px 圆形按钮一次滑 200px；触摸端（`(hover: none) and (pointer: coarse)`
 * 或 `maxTouchPoints > 0`）两个都隐藏，靠手势横滑 —— 与宿主的判断逐字一致。
 */
const tabsContainerRef = ref<HTMLElement | null>(null)
const showTabsScrollIndicator = ref(false)
const showLeftButton = ref(false)
const showRightButton = ref(false)

/** 与宿主同一判据：触摸设备不显示滚动控件 */
function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return window.matchMedia('(hover: none) and (pointer: coarse)').matches || navigator.maxTouchPoints > 0
  } catch {
    return false
  }
}

/** 首屏「补满一屏」最多自动接力的页数（见 `requestMoreIfVisible`） */
const FIRST_SCREEN_MAX_PAGES = 3

/** 一次滑 200px（宿主同值） */
function scrollTabs(direction: 'left' | 'right'): void {
  const el = tabsContainerRef.value
  if (!el) return
  const scrollAmount = 200
  const scrollPosition = direction === 'left' ? el.scrollLeft - scrollAmount : el.scrollLeft + scrollAmount
  el.scrollTo({ left: scrollPosition, behavior: 'smooth' })
  // 等滑动动画结束再更新指示（宿主是 300ms 后）
  setTimeout(updateTabsIndicator, 300)
}

function updateTabsIndicator(): void {
  const el = tabsContainerRef.value
  if (!el) return
  const shouldHideScrollControls = isTouchDevice()
  const tolerance = 1
  const hasOverflow = el.scrollWidth > el.clientWidth + tolerance
  const isScrolledToEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - tolerance
  const isScrolledToStart = el.scrollLeft <= tolerance

  showTabsScrollIndicator.value = hasOverflow && !isScrolledToEnd && !shouldHideScrollControls
  showLeftButton.value = hasOverflow && !isScrolledToStart && !shouldHideScrollControls
  showRightButton.value = hasOverflow && !isScrolledToEnd && !shouldHideScrollControls
}

let tabsResizeTimer: ReturnType<typeof setTimeout> | null = null
function handleTabsResize(): void {
  if (tabsResizeTimer) clearTimeout(tabsResizeTimer)
  // 宿主是 150ms 防抖
  tabsResizeTimer = setTimeout(updateTabsIndicator, 150)
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
/** 在库状态查成了的作品数（页模式下只含缓存里已有的结论，冷缓存时为 0） */
const libraryKnown = ref(0)
/** 其中明确已在库的作品数 */
const inLibraryCount = ref(0)
const inLibraryKnown = computed(() => libraryKnown.value > 0)
/** 判定通道可用 —— 「只看未入库」开关的展示依据（页模式下不依赖 library_known） */
const probeAvailable = ref(false)
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
const facets = ref<WorksFacets>({ genres: [], years: [], studios: [], platforms: [] })

// ── 已关注的演员（卡片墙） ──
//
// 数据来自 `/actors/cards`：字段与搜索结果候选同构，前端用**同一个 ActorCard 组件**
// 渲染两处，视觉与交互因此完全一致。头像等档案由后端快照缓存（发现任务每轮顺带补一次），
// 所以默认调用是纯读快照；点标题行的刷新按钮才让后端现抓几位补档案（enrich=1）。
const followedActors = ref<ActorCardItem[]>([])
const followedLoading = ref(false)
const followedError = ref('')

/* ── 「发现」：站点的人物目录（演员一本）+ 站点榜单（2026-10-23 用户口径） ── */

/**
 * 人物目录的分类。导演 / 编剧已移除（2026-10-23 用户口径），只留演员一本；
 * `PeopleKind` 收敛成单值但保留类型与 ref（模板与加载逻辑都用它）。
 */
type PeopleKind = 'yanyuan'
const PEOPLE_TABS: { title: string; value: PeopleKind }[] = [
  { title: '演员', value: 'yanyuan' },
]
const peopleKind = ref<PeopleKind>('yanyuan')
const peopleKindLabel = computed(
  () => PEOPLE_TABS.find((item) => item.value === peopleKind.value)?.title || '演员',
)
const peopleRows = ref<PeopleRow[]>([])
/** 已经加载到第几页（0 = 这一本目录还没拉过） */
const peoplePage = ref(0)
const peopleHasMore = ref(false)
const peopleLoading = ref(false)
const peopleError = ref('')
/** 数据源缺能力 / 取数失败时的说明（后端原样给，不当成请求错误） */
const peopleMessage = ref('')

/**
 * 「发现」页当前看哪本：``'people'`` = 演员目录；其余值 = 榜单 key
 * （``rebo`` / ``reso`` / …，目录来自后端 ``/ranks``，纯静态零网络）。
 */
const discoverView = ref<string>('people')

/** 榜单目录（后端 ``/ranks``；``has_detail`` 为假的整页无详情 id，前端不显示） */
const rankItems = ref<RankItem[]>([])

const rankLoading = ref(false)
/** 当前榜单的原样卡行（数据源按实际页面解析，这里不做归一） */
const rankMedias = ref<RankMediaItem[]>([])
/** 已加载到第几页（0 = 还没拉过；作品页同样口径：每页 30 部） */
const rankPage = ref(0)
/** 是否还有下一页（推荐页按站点分页，其他榜由数据源按 30 部切片） */
const rankHasMore = ref(false)
/** 抓取失败 / 榜单空时的说明（后端原样给，空串 = 正常） */
const rankMessage = ref('')
/** 当前选中的榜单 key（'' = 没在看榜单） */
const rankKey = computed(() => (discoverView.value === 'people' ? '' : discoverView.value))
const rankName = computed(
  () => rankItems.value.find((item) => item.key === rankKey.value)?.name || '榜单',
)

/**
 * 榜单原样卡 → WorkItem：**样式与作品页同一张卡**（WorkCard）。卡行只有必要
 * 字段（title / badge / episodes / date / actors_text，海报与链接已由
 * media_id 现推），没有热度 / 评分 / 题材 —— 只把演员行放进副标题位。
 */
function rankMediaToWork(row: RankMediaItem): WorkItem {
  const source = row.media_id.includes(':')
    ? row.media_id.split(':')[0].toLowerCase()
    : 'djbaike'
  return {
    key: `rank:${row.media_id}`,
    title: row.title,
    year: (row.date || '').slice(0, 4),
    type: row.badge || '短剧',
    media_source: source,
    media_id: row.media_id,
    poster: row.poster,
    vote: 0,
    episode_count: row.episodes || 0,
    url: row.url,
    genres: [],
    heat: 0,
    play_count: 0,
    studio: row.actors_text || '',
    platform: '',
    kind: row.badge || '',
    release_date: row.date || '',
    actor: row.actors_text || '',
    actor_key: '',
    first_seen: '',
    is_new: false,
    // 卡片「入库」图标（与作品页同一套判定）
    in_library: row.in_library ?? null,
  }
}

/** 榜单卡喂给 WorkCard 的列表（原样卡 → WorkItem 映射） */
const rankWorkItems = computed(() => rankMedias.value.map(rankMediaToWork))

/**
 * 取一本榜的一页，**与作品页同一套按需加载**（每页 30 部）：
 * - ``reset = true``：换榜 / 切回发现页，从第 1 页重拉；
 * - ``reset = false``：滚到底续拉下一页（按 media_id 去重合并）。
 */
async function loadRank(key: string, reset = true): Promise<void> {
  if (!key || rankLoading.value) return
  const page = reset ? 1 : rankPage.value + 1
  if (!reset && !rankHasMore.value) return
  rankLoading.value = true
  if (reset) rankMessage.value = ''
  try {
    const payload = await fetchRankWorks(props, key, page)
    const medias = Array.isArray(payload.medias) ? payload.medias : []
    // 拉的期间用户可能已切走：只把当前正看的榜上屏
    if (rankKey.value !== key) return
    if (reset) {
      rankMedias.value = medias
    } else {
      const seen = new Set(rankMedias.value.map((item) => item.media_id))
      rankMedias.value = rankMedias.value.concat(
        medias.filter((item) => !seen.has(item.media_id)),
      )
    }
    if (payload.message) rankMessage.value = payload.message
    rankPage.value = payload.page || page
    rankHasMore.value = Boolean(payload.has_more)
  } catch (err) {
    rankMessage.value = `榜单加载失败：${err instanceof Error ? err.message : err}`
  } finally {
    rankLoading.value = false
    void nextTick(observeRankSentinel)
  }
}

/** 目录 / 榜单 chips 的回调：取消选中没有意义，保持原视图 */
function setDiscoverView(value: unknown): void {
  const key = String(value || '')
  if (!key || key === discoverView.value) return
  if (key === 'people' || rankItems.value.some((item) => item.key === key)) {
    discoverView.value = key
  }
}

watch(discoverView, (view) => {
  if (activeTab.value !== 'people') return
  if (view === 'people') {
    // 回到演员目录：站点目录是活的，总是重新拉第一页（与切标签同一口径）
    void loadPeople(true)
    void nextTick(observePeopleSentinel)
  } else {
    // 换榜：从第 1 页重拉，哨兵重挂（否则滚到底不会续拉下一页）
    void loadRank(view)
    void nextTick(observeRankSentinel)
  }
})

/** 拉一次榜单目录（纯静态，挂载时后台跑一次） */
async function loadRankCatalog(): Promise<void> {
  try {
    const payload = await fetchRanks(props)
    rankItems.value = (payload.ranks || []).filter((item) => item.has_detail !== false)
  } catch {
    // 目录取不到就不显示榜单 chips，演员目录照常
  }
}

// ── 右上「最近日志」（2026-10-23 用户口径：实时滚动） ──

const logLines = ref<string[]>([])
const logsBodyRef = ref<HTMLElement | null>(null)
let logsTimer: ReturnType<typeof setInterval> | null = null

/**
 * 悬浮日志窗的拖动（2026-10-24 用户口径：可拖到屏幕**任意位置**）。
 *
 * 位置记「胶囊左上角」的像素坐标：拖到哪儿就是哪儿，只夹在视口内。
 * 渲染时按展开方向选锚 —— 向上展开钉容器**底边**、向下展开钉容器**顶边**，
 * 另一边显式 `auto`（否则 CSS 里残留的 bottom 会和 inline 的 top 一起生效，
 * 把容器拉成整屏高，胶囊就被顶走了：这正是之前「拖到上面拖不过去」的根因）。
 * 移动/松手监听挂在 window 上，鼠标拖得快、冲出胶囊也不会掉事件。
 * 位置只记在本次会话，不写任何存储。
 */
const logDragging = ref(false)
/**
 * 胶囊位置：垂直用**距顶像素**（上下随便拖），水平用**距右**（胶囊在容器里靠右，
 * 用距右才不会在展开时因为容器变宽而横向跳一下）。null = 还没拖过，停在右下角。
 */
const logPos = ref<{ top: number; left: number } | null>(null)
/** 胶囊本体（量尺寸用：换算展开锚点） */
const logBarRef = ref<HTMLElement | null>(null)
const logBarH = ref(26)
const logBarW = ref(96)
const logViewportH = ref(typeof window === 'undefined' ? 800 : window.innerHeight)
const logViewportW = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)
/** 日志区是否已滚到底（到底才跟着新行自动滚；用户往上翻就不打断） */
const logPinned = ref(true)

/**
 * 展开方向跟随位置：胶囊在视口**上半屏**就向下展开，下半屏向上展开
 * （2026-10-24 用户口径：拖到最上面时展开位置要向下）。
 */
const logExpandDown = computed(() => {
  const pos = logPos.value
  if (!pos) return false
  return pos.top + logBarH.value / 2 < logViewportH.value / 2
})

/**
 * 水平展开方向：胶囊在视口**左半屏**就向右展开（日志往右长），右半屏向左展开。
 * 之前水平固定「向右锚、往左长」，胶囊拖到左边时日志就长到屏幕外了
 * （2026-10-24 用户反馈「拖到左边还是会向左展开」）。
 */
const logExpandRight = computed(() => {
  const pos = logPos.value
  if (!pos) return false
  return pos.left + logBarW.value / 2 < logViewportW.value / 2
})

/**
 * 定位：四个方向都给值，避免与 CSS 默认值打架。
 * 向上展开 → 用 `bottom` 锚（胶囊贴容器底，加内容只往上长）；
 * 向下展开 → 用 `top` 锚（胶囊贴容器顶，加内容只往下长）。
 * 两种都不让胶囊位移，所以 hover 不会反复断开（不闪）。
 */
const logStyle = computed<Record<string, string>>(() => {
  const pos = logPos.value
  if (!pos) return { right: '12px', bottom: '12px', top: 'auto', left: 'auto' }
  // 向左展开 → 钉容器右边缘（胶囊靠右，日志往左长）；向右展开 → 钉容器左边缘
  const horizontal = logExpandRight.value
    ? { left: `${pos.left}px`, right: 'auto' }
    : { right: `${Math.max(0, logViewportW.value - pos.left - logBarW.value)}px`, left: 'auto' }
  // 向上展开 → 钉容器下边缘（胶囊靠下，日志往上长）；向下展开 → 钉容器上边缘
  const vertical = logExpandDown.value
    ? { top: `${pos.top}px`, bottom: 'auto' }
    : { bottom: `${Math.max(0, logViewportH.value - pos.top - logBarH.value)}px`, top: 'auto' }
  return { ...horizontal, ...vertical }
})

/**
 * 量胶囊的**收起态**尺寸：hover 展开时胶囊会被 stretch 变宽，
 * 直接用会算出错误的拖动边界（表现为拖不到边上）。临时加 class 强制收起再量。
 */
function measureLogBar(): DOMRect | null {
  const bar = logBarRef.value
  const host = (bar?.closest('.sdas-logfloat') as HTMLElement | null) ?? null
  if (!bar || !host) return null
  host.classList.add('sdas-measuring')
  const rect = bar.getBoundingClientRect()
  host.classList.remove('sdas-measuring')
  if (rect.height > 0) logBarH.value = rect.height
  if (rect.width > 0) logBarW.value = rect.width
  return rect
}

/** 量一次胶囊尺寸与视口尺寸；视口变小后把位置夹回可见范围 */
function updateLogMetrics(): void {
  logViewportH.value = window.innerHeight
  logViewportW.value = window.innerWidth
  measureLogBar()
  clampLogPos()
}

/** 把位置夹回可见范围（窗口变小 / 读回旧位置时用） */
function clampLogPos(): void {
  const pos = logPos.value
  if (!pos) return
  logPos.value = {
    left: logClamp(pos.left, 0, Math.max(0, logViewportW.value - logBarW.value)),
    top: logClamp(pos.top, 0, Math.max(0, logViewportH.value - logBarH.value)),
  }
}

/**
 * 位置持久化（2026-10-24 用户口径：别每次进去都要重新拖）。
 * 存在浏览器本地存储里（按域名隔离），下次打开侧栏 / 刷新页面直接回到上次的位置；
 * 读回来先 clamp 一遍，免得换了个小窗口就跑到屏幕外。展开方向由位置现算，不必存。
 */
const LOG_POS_KEY = 'sdas.logfloat.pos.v1'

function loadLogPos(): void {
  try {
    const raw = window.localStorage.getItem(LOG_POS_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as { top?: unknown; left?: unknown }
    if (typeof parsed?.top === 'number' && typeof parsed?.left === 'number') {
      if (Number.isFinite(parsed.top) && Number.isFinite(parsed.left)) {
        logPos.value = { top: parsed.top, left: parsed.left }
        clampLogPos()
      }
    }
  } catch {
    // 存储被禁用 / 数据坏了：按默认右下角处理，不影响主界面
  }
}

function saveLogPos(): void {
  const pos = logPos.value
  if (!pos) return
  try {
    window.localStorage.setItem(LOG_POS_KEY, JSON.stringify(pos))
  } catch {
    // 存不下就算了：只是下次回到默认位
  }
}

/** 日志区滚动：不在底部就停止自动跟随，让用户能往上翻 */
function onLogScroll(): void {
  const el = logsBodyRef.value
  if (!el) return
  logPinned.value = el.scrollHeight - el.scrollTop - el.clientHeight < 8
}

/**
 * 滚到最新一行（日志按时间正序排列，最新在后 ⇒ 滚到底）。
 * 收起时日志区 `display: none`、没有布局，此时赋值 scrollTop 是无效的，
 * 所以展开那一刻要补滚一次（2026-10-24 用户口径：展开后要显示最新的）。
 */
function scrollLogToEnd(): void {
  const el = logsBodyRef.value
  if (!el || el.clientHeight === 0) return
  el.scrollTop = el.scrollHeight
  // 横向回到行首：上次横着拖到中间、收起再展开时，一上来看到的是半句话
  el.scrollLeft = 0
  logPinned.value = true
}

/** 鼠标进入胶囊 / 日志区 = 展开：这一刻把日志滚到最新 */
function onLogExpand(): void {
  if (logDragging.value) return
  void nextTick(scrollLogToEnd)
}

function logClamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max))
}

/** 拖动状态：起手时的鼠标坐标与胶囊位置（每帧按位移换算，不会累积误差） */
let logDragStart: { px: number; py: number; top: number; left: number } | null = null

function onLogPointerDown(event: PointerEvent): void {
  const bar = event.currentTarget as HTMLElement | null
  if (!bar || logDragStart) return
  updateLogMetrics()
  // 以胶囊当前真实位置为起点（收起态尺寸，避免展开时被 stretch 的尺寸带偏）
  const rect = measureLogBar() ?? bar.getBoundingClientRect()
  const cur = { top: Math.round(rect.top), left: Math.round(rect.left) }
  logPos.value = cur
  logDragStart = { px: event.clientX, py: event.clientY, top: cur.top, left: cur.left }
  logDragging.value = true
  // 移动/松手挂 window（capture）：拖得快、鼠标冲出胶囊也不掉事件
  window.addEventListener('pointermove', onLogPointerMove, true)
  window.addEventListener('pointerup', onLogPointerUp, true)
  window.addEventListener('pointercancel', onLogPointerUp, true)
  event.preventDefault()
}

function onLogPointerMove(event: PointerEvent): void {
  const start = logDragStart
  if (!start) return
  logPos.value = {
    left: logClamp(start.left + (event.clientX - start.px), 0, Math.max(0, logViewportW.value - logBarW.value)),
    top: logClamp(start.top + (event.clientY - start.py), 0, Math.max(0, logViewportH.value - logBarH.value)),
  }
}

function onLogPointerUp(): void {
  if (!logDragStart) return
  logDragStart = null
  logDragging.value = false
  window.removeEventListener('pointermove', onLogPointerMove, true)
  window.removeEventListener('pointerup', onLogPointerUp, true)
  window.removeEventListener('pointercancel', onLogPointerUp, true)
  // 松手才落盘（拖动过程中不写，省得每帧写一次存储）
  saveLogPos()
}

/** 拉一次日志尾部；内容有变化才更新 + 滚到底（新行在后 = 实时滚动） */
async function loadLogs(): Promise<void> {
  try {
    const payload = await fetchLogs(props, 60)
    const items = Array.isArray(payload.items) ? payload.items : []
    if (items.length === logLines.value.length && items.every((line, idx) => line === logLines.value[idx])) {
      return
    }
    logLines.value = items
    void nextTick(() => {
      // 用户往上翻了就不抢滚动条，仍停在原处（logPinned 由 onLogScroll 维护）
      if (logPinned.value) scrollLogToEnd()
    })
  } catch {
    // 日志面板拉不到不影响主界面
  }
}

/**
 * 性别归类：站点字段有时给英文（``Female`` / ``Male``）、有时给中文，认不出来的算「未标注」。
 * 顺序要紧 —— ``female`` 里含 ``male``，先判女再判男。
 */
function genderKey(value?: string): 'female' | 'male' | 'other' {
  const text = String(value || '').trim().toLowerCase()
  if (!text) return 'other'
  if (text === 'female' || text === 'f' || text.includes('女')) return 'female'
  if (text === 'male' || text === 'm' || text.includes('男')) return 'male'
  return 'other'
}

/** 性别分类的取值域（持久化恢复时校验用） */
const GENDER_KEYS = ['female', 'male', 'other']

/**
 * 演员页的**性别归类**（用户要求分三类）：女 → 男 → 未标注，空组不渲染。
 * 顺序固定（不按人数排），免得人数一变组的顺序就换；真机 96 位目前是 54 / 22 / 20。
 * 三个组名同时是槽位里「分类」那三颗 chip 的文案（以及它们角标里的计数）。
 */
const actorGroups = computed(() => {
  const female: ActorCardItem[] = []
  const male: ActorCardItem[] = []
  const other: ActorCardItem[] = []
  for (const item of followedActors.value) {
    const key = genderKey(item.gender)
    if (key === 'female') female.push(item)
    else if (key === 'male') male.push(item)
    else other.push(item)
  }
  return [
    { key: 'female', title: '女演员', items: female },
    { key: 'male', title: '男演员', items: male },
    { key: 'other', title: '未标注', items: other },
  ].filter((group) => group.items.length > 0)
})

/**
 * 演员页槽位里的「分类」筛选（与作品页「类型」行同一套 chip 用法）：
 * 空串 = 不分类（三类合成一串铺）；选中某一类 = 只铺那一类。
 */
const actorGender = ref('')

/**
 * 卡片区实际铺的演员：**一串、不分组**（用户口径：按 A-Z 排序铺卡，不要组标题）。
 * 选了分类就只留那一类；没选则三类合并。
 *
 * 顺序：**拼音 A→Z**（`#` 垫底）。性别只决定「筛哪些人」，不决定「先排谁」——
 * 字母索引只有在字母顺序下才成立（2026-10-20）。
 */
const shownActors = computed(() => {
  const rows = actorGender.value
    ? (actorGroups.value.find((group) => group.key === actorGender.value)?.items ?? [])
    : actorGroups.value.flatMap((group) => group.items)
  return [...rows].sort((a, b) => compareByName(a.name, b.name))
})

/**
 * 首字母停靠点：`[{letter, index, count, ratio}]`。
 *
 * - `index`：该字母第一位演员在 `shownActors` 里的下标（跳转时按它找卡片格子）
 * - `ratio`：`index / 总数`，右侧滚动条把鼠标/手指的纵向位置换算成 `0..1` 后按它找字母；
 *   卡片不等高也不影响，比例只是粗略定位，真正跳转仍以 `index` 为准。
 *
 * 顺序天然是 A→Z（`#` 垫底，`compareByName` 已排最后）。
 */
const actorLetterStops = computed(() => {
  const total = shownActors.value.length || 1
  const stops: Array<{ letter: string; index: number; count: number; ratio: number }> = []
  shownActors.value.forEach((item, index) => {
    const letter = initialOf(item.name)
    const last = stops[stops.length - 1]
    if (last && last.letter === letter) {
      last.count += 1
      return
    }
    stops.push({ letter, index, count: 1, ratio: index / total })
  })
  return stops
})

/** 右侧滚动条的定位锚点（整个卡片网格，不做布局以外的事） */
const actorGridAnchor = ref<HTMLElement | null>(null)

/** 格子节点（按演员 key 存，点字母时用它 `scrollIntoView`） */
const cellElements = new Map<string, HTMLElement>()

/**
 * 点到某个字母：滚到该字母第一位演员的卡片。
 *
 * 用 `scrollIntoView` 而不是自己算 scrollTop —— 真正在滚的可能是 window，也可能是
 * 面板里的某个 overflow 祖先，浏览器会把**所有**滚动祖先一起滚到位，我们不用猜。
 * 顶栏遮挡高度由 `.sdas-actor-cell` 上的 `scroll-margin-block-start` 让出来。
 */
function jumpToActorLetter(letter: string): void {
  const stop = actorLetterStops.value.find((row) => row.letter === letter)
  if (!stop) return
  const target = shownActors.value[stop.index]
  if (!target) return
  const cell = cellElements.get(actorKey(target))
  if (cell?.isConnected) cell.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// ── 非虚拟渲染的「懒挂载」 ──
//
// 演员页不再虚拟滚动（要按 A-Z 顺序铺、要能被字母跳转），96 张卡全进 DOM。
// 卡片本身很轻（2:3 的图 + 两行字），真正的成本是**同时发起 96 张头像请求**，
// 所以布局全铺、卡片只挂「视口 ± 600px」内的：占位块用同样的 2:3 撑住高度，
// 滚到附近再换成真卡 —— 位置不跳、请求不扎堆。

const mountedCells = ref<Set<string>>(new Set())
let cellObserver: IntersectionObserver | null = null
const observedCells = new WeakSet<Element>()

function ensureCellObserver(): IntersectionObserver | null {
  if (cellObserver) return cellObserver
  if (typeof IntersectionObserver === 'undefined') return null
  cellObserver = new IntersectionObserver(
    (entries) => {
      const next = new Set(mountedCells.value)
      let changed = false
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        cellObserver?.unobserve(entry.target)
        const key = (entry.target as HTMLElement).dataset.cellKey || ''
        if (key && !next.has(key)) {
          next.add(key)
          changed = true
        }
      }
      if (changed) mountedCells.value = next
    },
    { rootMargin: '600px 0px' },
  )
  return cellObserver
}

/** 卡片格子的 ref 回调：进视口附近就挂真卡；同时登记节点，供字母跳转使用 */
function observeCell(el: Element | null, key: string): void {
  if (!key) return
  if (!(el instanceof HTMLElement)) {
    // 卸载回调（v-for 换批）不带元素：只在原节点真的脱离文档时清掉登记
    const stale = cellElements.get(key)
    if (stale && !stale.isConnected) cellElements.delete(key)
    return
  }
  cellElements.set(key, el)
  const observer = ensureCellObserver()
  if (!observer) {
    // 老浏览器没有 IntersectionObserver：直接全挂，功能不受影响
    if (!mountedCells.value.has(key)) {
      const next = new Set(mountedCells.value)
      next.add(key)
      mountedCells.value = next
    }
    return
  }
  if (observedCells.has(el)) return
  observedCells.add(el)
  observer.observe(el)
}

function isCellMounted(key: string): boolean {
  return mountedCells.value.has(key)
}

/**
 * 开关上的计数：优先用卡片接口的名单（与卡片墙同源），还没回来时退化成作品接口的名单
 */
const followedCount = computed(() =>
  followedActors.value.length || actorFilters.value.length,
)

// ── 视图槽位（作品维度筛选 / 演员页分类 + 工具栏） ──
//
// 槽位是**内容自适应高度**：作品页铺几行筛选，演员页只有分类行 + 工具栏，卡片区紧跟着
// 往上收 —— 早先为「切标签卡片区起点绝对不动」做过的 slotHeight / ResizeObserver
// 兜底已按用户要求撤掉（代价是切标签时卡片区会有一段位移，换来的是演员页不留白）。

/** 筛选条件 */
const actor = ref('')
const genre = ref('')
const year = ref('')
const studio = ref('')
/** 播放平台（「在哪播」）—— 作品卡目前不带平台，这行筛选项恒为空、整行隐藏 */
const platform = ref('')
/** 排序：**默认发布日期**（用户定的，新剧在前；'heat' 热度 / 'play' 播放 / 'rating' 评分） */
/**
 * 排序只剩首播日期（2026-10-23 用户口径）：热度 / 播放 / 评分在墙的快照里恒为 0，
 * 排出来全是并列 —— 不再给排序入口，固定按 date 查。
 */
const sort = ref('date')
/** 「未订阅」卡：只看还没订阅的作品（后端按订阅清单排除） */
const onlyNotSubscribed = ref(false)
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

/**
 * 当前打开的**演员作品页**（点演员卡进入；null = 列表态）。
 *
 * 它是**整页视图**（与 `detailWork` 一样排在 `.sdas` 面板之外 ⇒ 顶栏 / 搜索行 / 标签条 /
 * 槽位整块让位，从面板顶部铺满）。作品数据由 `ActorDetail.vue` 自己经
 * `GET /actors/detail` 取（百科现查），本组件不再代持 —— 所以这里只存「点的是谁」。
 */
const detailActor = ref<ActorCandidate | null>(null)
/**
 * 当前打开的作品详情（点作品卡进入；null = 列表态）。
 * 它同样是**整页视图**：详情开着时面板整块让位；关掉就回到进来之前那一页。
 */
const detailWork = ref<WorkItem | null>(null)
/**
 * 原著详情页的数据（作品详情里点「改编自」进来）。
 *
 * 不落额外请求：站点在剧集记录的 `adapted_from` 里已经给了整份原著（含全部改编作品），
 * 工作详情页把它原样交给这一层。
 */
const detailAdapted = ref<AdaptedInfo | null>(null)

/**
 * 现在显示的是哪一层整页视图。
 *
 * 两个整页视图**可以层层叠着**（宿主是路由栈：作品详情 → 点演员卡 → 人物详情 → 返回
 * 回到作品详情），所以不能靠「谁非空」来判渲染 —— 用这个字段记最上面那层，返回时退到下一层。
 */
const viewLayer = ref<'' | 'work' | 'actor' | 'adapted'>('')
/** 演员作品页是从哪进来的：`work` = 作品详情页里的演员阵容卡（返回回那一页） */
let actorOpenedFrom: '' | 'work' = ''
/** 作品详情页是从哪进来的：`actor` = 演员作品页里的作品卡（返回回那一页） */
let workOpenedFrom: '' | 'actor' | 'adapted' = ''

/** 进详情前的滚动位置（返回详情时还原） */
let detailScrollY = 0
/** 进演员作品页前的滚动位置（返回时还原；与作品详情各记一份，互不覆盖） */
let actorScrollY = 0

/** 已订阅作品的 media_id（作品卡悬停浮层上爱心按钮的状态） */
const subscribed = ref<Set<string>>(new Set())
/** 图已加载完的卡片 key（工作 / 演员共用一套；探索页也是「图加载完才加 ring」） */
const loadedKeys = ref<Set<string>>(new Set())

/** 提示条 */
const tip = ref('')
const tipType = ref<'info' | 'error'>('info')
let tipTimer: ReturnType<typeof setTimeout> | null = null

/** 提示条的开关（`v-snackbar` 的 v-model；有文案即开） */
const tipOpen = computed({
  get: () => Boolean(tip.value),
  set: (on: boolean) => {
    if (!on) tip.value = ''
  },
})

function toast(text: string, type: 'info' | 'error' = 'info'): void {
  tip.value = text
  tipType.value = type
  if (tipTimer) clearTimeout(tipTimer)
  tipTimer = setTimeout(() => (tip.value = ''), 3200)
}


/** 是否处于筛选状态（决定要不要显示「重置」与「筛选出 N 部」） */
const filteredOut = computed(() =>
  Boolean(
    actor.value ||
      genre.value ||
      year.value ||
      studio.value ||
      platform.value ||
      onlyNotInLibrary.value ||
      onlyNotSubscribed.value,
  ),
)

function resetFilters(): void {
  actor.value = ''
  genre.value = ''
  year.value = ''
  studio.value = ''
  platform.value = ''
  onlyNotInLibrary.value = false
  onlyNotSubscribed.value = false
}

/**
 * 视图状态持久化（2026-10-22 用户口径：**sessionStorage 完全去除**）。
 *
 * 早先把「筛选/排序 + 已加载页数 + 滚动位置」存进 sessionStorage，切走再回来时
 * 恢复进度、跳回原位置；现按用户要求整段拆除 —— 每次打开都是全新状态（第一页、
 * 顶部、「全部」筛选），不会停留在上次的位置。
 *
 * 仍然保留的（与持久化无关）：`lastScrollY` 由 scroll 监听持续记录，
 * 只服务「回到顶部」按钮的显隐（`scrolledFar` / `backTopHiding`），不落任何存储。
 *
 * 背景（为什么早先需要它，现仅存档）：插件页路由没有 keepAlive，宿主按 fullPath
 * 重挂组件，点进详情再回来所有 ref 归零 —— 探索页不丢状态是因为宿主给它加了
 * `<KeepAlive>`，插件改不了自己的路由 meta。
 */
/** 最近一次滚动位置（scroll 监听里持续记录；只用于回到顶部按钮的显隐判断） */
let lastScrollY = 0

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
    platform: platform.value,
    sort: sort.value,
    only_not_in_library: onlyNotInLibrary.value,
    only_not_subscribed: onlyNotSubscribed.value,
    page_size: PAGE_SIZE,
  }
}

const actorCount = computed(() => actorFilters.value.length)

/** 当前筛选出来的部数（两张卡激活时显示它） */
const filteredCount = computed(() => total.value)

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

// ── 演员卡片墙（演员页与搜索结果共用 ActorCard 组件） ──

// ── 演员搜索卡片 ──

/**
 * 这位演员是否已经在关注列表里。
 *
 * 2026-10-20 起按 **actor_id** 比对（ID 是唯一身份）：同名的另一位是不同的人，
 * 按名字比会把同名的另一位误标成已关注。候选没带 ID（极端情况）才退回名字。
 */
function isActorAdded(item: ActorCandidate): boolean {
  if (item.subscribed) return true
  if (item.actor_id) {
    return actorFilters.value.some((row) => row.key === item.actor_id)
  }
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
    if (result.need_pick) {
      // 只给名字、且百科里没有同名精确命中：拿候选让用户挑（后端按 API 专题 §3.3
      // 用 200 + data.need_pick 表达，不当成接口失败）
      toast(result.message || '百科里没有完全同名的演员，请从候选里挑一位', 'error')
      return
    }
    // 先在卡片上标出来（不用等整轮重载回来）
    item.subscribed = true
    toast(result.message || `已添加「${item.name}」`)
    await reload()
    await loadFollowed()  // 关注列表变了：卡片墙同步（新演员立刻出现在「已关注」里）
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
    // ID 是唯一身份：优先按 actor_id 移除（同名另一位不受影响），name 只作后端兜底
    const result = await removeActor(props, { actor_id: item.actor_id, name: item.name })
    item.subscribed = false
    // 演员作品页开着这位演员时**不关**：那一页的数据是百科现查的（与关注状态无关），
    // 用户多半还要继续看他的作品；关注列表里他会立刻消失
    toast(result.message || `已移除「${item.name}」`)
    await reload()
    await loadFollowed()  // 关注列表变了：卡片墙同步（移出的演员立刻消失）
  } catch (err) {
    toast(`移除失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    removingActorId.value = ''
  }
}

/**
 * 点演员卡：打开**演员作品页**（整页视图，`ActorDetail.vue`）。
 *
 * 进来先清空搜索框 —— 搜索结果分支排在整页视图**前面**，留着词会把这一页盖住。
 * 档案与作品由子组件经 ``GET /actors/detail`` 现查（短剧百科），本组件只负责切页与
 * 还原滚动位置。出口：页面左上返回键；换顶部标签、改筛选、或在搜索栏里输个词都会
 * 自动退出（见下方 watch）—— 否则会卡在整页视图上，点了像没反应。
 *
 * 这是**列表入口**：底下那层（作品详情）要清掉，返回就是回列表。
 */
function openActorDetail(item: ActorCandidate): void {
  // 详情开着时点演员卡（搜索结果里那排）：先退出作品详情，整页视图才看得见
  exitViews(false)
  actorQuery.value = ''
  actorScrollY = currentScrollY()
  detailActor.value = item
  viewLayer.value = 'actor'
  scrollToPosition(0)
}

/**
 * 作品详情里点了标题行的分类：回到卡片墙并只看这一类。
 *
 * 清掉年份 / 版权方（它们都是单选的，留着很容易把结果筛成空），演员筛选保留 ——
 * 「这位演员 + 这个分类」是有意义的组合。搜索词也清掉，否则搜索结果会盖住墙。
 *
 * ⚠️ 值没变时 `watch` 不会触发（同一分类再点一次），那种情况手动退视图 + 重拉一次。
 */
function applyGenreFilter(value: string): void {
  const target = String(value || '').trim()
  if (!target) return
  const same = genre.value === target
  const cleared = Boolean(year.value || studio.value || platform.value)
  const hadKeyword = Boolean(actorQuery.value)
  actorQuery.value = ''
  year.value = ''
  studio.value = ''
  platform.value = ''
  genre.value = target
  if (same && !cleared && !hadKeyword) {
    exitViews()
    void reload()
  }
}

/**
 * 作品详情里点「改编自」：进**原著详情页**（叠在作品详情之上，返回回那一页）。
 */
function openAdaptedFromWork(novel: AdaptedInfo): void {
  detailAdapted.value = novel
  viewLayer.value = 'adapted'
  scrollToPosition(0)
}

/** 原著详情页的返回键：回作品详情（那是入口），没有作品页时回列表 */
function backFromAdapted(): void {
  if (detailWork.value) {
    viewLayer.value = 'work'
    void nextTick(() => scrollToPosition(detailScrollY))
    return
  }
  exitViews()
}

/** 演员作品页的返回键：有下一层就退一层，没有就回列表 */
function backFromActor(): void {
  if (actorOpenedFrom === 'work' && detailWork.value) {
    actorOpenedFrom = ''
    viewLayer.value = 'work'
    void nextTick(() => scrollToPosition(detailScrollY))
    return
  }
  exitViews()
}

/** 作品详情页的返回键：从演员作品页点进来的就退回演员页，否则回列表 */
function backFromWork(): void {
  if (workOpenedFrom === 'actor' && detailActor.value) {
    workOpenedFrom = ''
    viewLayer.value = 'actor'
    void nextTick(() => scrollToPosition(0))
    return
  }
  // 从原著页的改编作品点进来：退回原著页（再退一步才是列表）
  if (workOpenedFrom === 'adapted' && detailAdapted.value) {
    workOpenedFrom = ''
    viewLayer.value = 'adapted'
    void nextTick(() => scrollToPosition(0))
    return
  }
  exitViews()
}

/**
 * 关掉所有整页视图，回卡片墙。
 *
 * `restoreScroll` = 是否还原「进来之前列表的滚动位置」—— 列表入口自己切页时不需要
 * （那时候接着会走自己的滚动），槽位上那些「我要看卡片墙」的操作需要。
 */
function exitViews(restoreScroll = true): void {
  const hadWork = Boolean(detailWork.value)
  const hadActor = Boolean(detailActor.value)
  const hadAdapted = Boolean(detailAdapted.value)
  detailWork.value = null
  detailActor.value = null
  detailAdapted.value = null
  actorOpenedFrom = ''
  workOpenedFrom = ''
  viewLayer.value = ''
  if ((!hadWork && !hadActor && !hadAdapted) || !restoreScroll) return
  const top = hadActor ? actorScrollY : detailScrollY
  void nextTick(() => scrollToPosition(top))
}

/**
 * 走「回列表」这一步（两个整页视图都退出）。
 *
 * 演员页槽位上的操作（点分类 / 点刷新）都意味着「我要看演员卡片墙」：整页视图开着时
 * 主体是那一页，这时只改分类 `actorGender` 卡片墙压根不会出现 —— 用户点了「男演员」
 * 像没反应（实机反馈）。所以这类操作先把整页视图退掉，再让分类生效。
 * 作品详情页同理（槽位操作要先让列表回来）。
 */
function toActorWall(): void {
  exitViews()
}

/** 演员页工具栏的刷新：也先退出整页视图（那时点它，要看的显然是演员卡片墙） */
function refreshFollowed(): void {
  toActorWall()
  loadFollowed(true)
}

/** 已关注演员的身份集合（作品详情的演职员卡据此点亮爱心） */
const followedActorIds = computed(
  () =>
    new Set(
      followedActors.value.map((item) => String(item.actor_id || '')).filter(Boolean),
    ),
)

/** 关注 / 取消关注请求在飞的演员身份（爱心转圈，与卡片墙共用同一对变量） */
const busyActorIds = computed(
  () => new Set([addingActorId.value, removingActorId.value].filter(Boolean)),
)

/**
 * 作品详情里点了演职员卡上的爱心 —— 与演员墙完全同一套：已在关注就取消，否则关注。
 * 完成后 `reload()` / `loadFollowed()` 会刷新集合，几处的爱心一起变。
 */
function toggleActorFromWork(row: ActorCandidate): void {
  if (isActorAdded(row)) void unsubscribeActor(row)
  else void subscribeActor(row)
}

/**
 * 演员页槽位上「关注 / 取消关注」的忙态判据（整页视图里那个关注按钮转圈用）。
 *
 * 搜索结果、已关注列表、演员作品页三处用的是同一对忙态变量（`addingActorId` /
 * `removingActorId`），所以哪一处发起请求，三处的按钮都会一起转圈。
 */
function isActorBusy(item: ActorCandidate | null): boolean {
  if (!item) return false
  return addingActorId.value === item.actor_id || removingActorId.value === item.actor_id
}

/**
 * 演员作品页里的「关注 / 取消关注」：复用关注列表那一套（`subscribeActor` /
 * `unsubscribeActor`），只把 toast 与状态刷新交给它们 —— 不另写一份关注逻辑。
 *
 * ⚠️ 页面**不关**：关注只是给这位演员加个标记，用户还要继续看他的作品。
 */
async function toggleActor(item: ActorCandidate | null): Promise<void> {
  if (!item) return
  if (isActorAdded(item)) {
    await unsubscribeActor(item)
  } else {
    await subscribeActor(item)
  }
}

/** 搜索：**用数据源自己那条检索**（站点优先、库兜底），失败才退回本插件的两条链路 */
let lookupEpoch = 0

/** 这次结果来自哪：`site` 站点命中 / `library` 站点 0 条退库 / 空串未知（提示行用） */
const searchSource = ref('')

/** 这次结果是怎么来的：`cache` 打字时的本地缓存 / `site` 回车或点「搜索」打站点 */
const searchMode = ref<'' | 'cache' | 'site'>('')

/**
 * 搜索：**两种来源**（2026-10-18 用户口径）。
 *
 * * `'cache'` —— 打字时用（防抖 300ms）：只翻**本地已有的数据**（作品墙已加载的行 +
 *   关注列表 + 已加载的演员目录），零请求、零等待，边打边出；
 * * `'site'` —— 回车或点「搜索」时用：走数据源 `/lookup` 打站内搜索（站点优先、
 *   库兜底，同名多季会列全），与在数据源面板里检索得到的结果一致。
 *
 * 站点检索不可用（数据源没装 / 停用 / 旧版本）时**直接报错**，不退回本插件自己的
 * 两条链路 —— 那两条口径不同（片名精确匹配、同名多季不全），拿它顶替会让人以为搜到了。
 */
async function runLookup(mode: 'cache' | 'site' = 'cache'): Promise<void> {
  const name = searchKeyword.value
  const stamp = ++lookupEpoch
  if (!name) {
    actorResults.value = []
    workResults.value = []
    searchingActors.value = false
    searchingWorks.value = false
    searchSource.value = ''
    searchMode.value = ''
    return
  }

  if (mode === 'cache') {
    // ── 本地缓存：同步完成，不发任何请求 ──
    searchMode.value = 'cache'
    searchSource.value = ''
    const needle = name.toLowerCase()
    const hit = (text: unknown): boolean =>
      String(text || '').toLowerCase().includes(needle)
    workResults.value = works.value
      .filter(
        (item) =>
          hit(item.title) ||
          hit(item.actor) ||
          hit(item.studio) ||
          hit(item.platform) ||
          (item.genres || []).some((genre) => hit(genre)),
      )
      .slice(0, 30)
    const actorPool: ActorCandidate[] = [
      ...followedActors.value,
      ...peopleRows.value.map((row) => row as unknown as ActorCandidate),
    ]
    const seen = new Set<string>()
    actorResults.value = actorPool
      .filter((row) => {
        if (!hit(row.name)) return false
        const key = String(row.actor_id || row.name)
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
      .slice(0, 30)
    searchingActors.value = false
    searchingWorks.value = false
    return
  }

  // ── 站点检索（数据源 /lookup） ──
  searchMode.value = 'site'
  searchingActors.value = true
  searchingWorks.value = true
  searchSource.value = ''
  try {
    const result = await lookupSite(props, name)
    if (stamp !== lookupEpoch) return
    actorResults.value = result.actors
    workResults.value = result.works
    searchSource.value = result.source
  } catch (err) {
    // 数据源检索不可用就明说（2026-10-18 用户口径：**不兜底**）——
    // 本插件自己那两条链路口径不同（片名精确匹配、同名多季不全），拿它顶替只会
    // 让人以为"搜到了"，实际少了结果。
    if (stamp !== lookupEpoch) return
    actorResults.value = []
    workResults.value = []
    toast(`检索不可用：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    if (stamp === lookupEpoch) {
      searchingActors.value = false
      searchingWorks.value = false
    }
  }
}


// ── 网格几何 + 渐进填充 ──

const gridRef = ref<HTMLElement | null>(null)
const gridWidth = ref(0)
let gridObserver: ResizeObserver | null = null

/**
 * 几处网格**共用同一个测量源**：它们都在同一根容器里、宽度一致（搜索结果上下两块、
 * 作品墙 / 展开的作品墙），量谁都是同一个数。
 *
 * 用函数 ref 而不是 `ref="gridRef"`：搜索结果里可能同时有两个网格在 DOM 里，
 * 字符串 ref 会被后一个覆盖（Vue 也会告警）。
 */
function setGridNode(el: unknown): void {
  const node = (
    el && typeof el === 'object' && '$el' in el ? (el as { $el?: unknown }).$el : el
  ) as HTMLElement | null
  if (node) gridRef.value = node
}

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

/**
 * 网格元素是**条件渲染**的：loading / 空态 / 错误态下它压根不在 DOM 里。
 * 从 loading 切到网格那一拍如果没人再量一次，`gridWidth` 会停在 0
 * （或上一次那个容器的宽度）—— 列数 `floor((0+16)/160)` 就塌成 **1 列**，
 * 卡片一根根竖着排，看起来跟作品页完全不是一个版式。
 * 最典型的就是点演员卡展开作品墙：展开那一刻还在 loading，量不到元素，
 * 百科数据回来网格才出现 —— 而那时没人再量。
 * 所以这里盯住模板 ref 本身：节点一挂上就重量一遍并重挂尺寸观察。
 */
watch(gridRef, (node) => { if (node) watchGrid() }, { flush: 'post' })

/** 作品墙网格的业务键（稳定键：列表追加时已挂载卡片不会被重建） */
function workKey(work: WorkItem): string {
  return work.key
}

/*
 * 早先这里有一整套「渐进填充」：`visibleCount` 游标 + 每帧补 BATCH_SIZE 张 + rAF
 * 后台兜底 + 铺完再 `ensureFilled` 看哨兵 —— 全部**已删除**，渲染职责整体移交给了
 * `ProgressiveCardGrid`（虚拟滚动网格，复刻宿主同款）：
 * - 整份列表高度由 spacer 立即撑出，不再需要「铺出来才有高度」；
 * - DOM 只挂视口 ± 4 行，「页面卡死」的根源（DOM 随页数无上限增长）随之消失；
 * - 加载链回归探索页语义：一次 intersect 拉一页，哨兵离视口 600px 内才续拉。
 */

// ── 数据：拉页 / 去重 / 收尾 ──

/** 去重键：与 MediaCardListView 的口径一致 */
function dedupeKey(work: WorkItem): string {
  return JSON.stringify(['media', work.media_source, String(work.media_id ?? ''), work.type ?? null, null])
}

/*
  ── 滚动容器 ──

  ⚠️ 插件面板里**会滚的不是 window / body**：宿主的 style.css 里有
  `.page-content-container > :first-child { max-block-size: 100%; overflow-y: auto }`
  —— 页面内容的第一层子元素被钉成固定高 + 自带纵向滚动，插件根节点就长在它里面。
  早先「满没满一屏」判在 `document.body` 上 ⇒ 在面板里恒判「没满屏」；再加上判定的
  时机在渐进填充铺满之前 ⇒ 哨兵永远在「视口 600px 内」⇒ loadMore 一页接一页把全集
  拉完铺完（用户看到的「一次性加载、页面卡死」）。

  所以这里从网格往上找最近的可滚祖先，找不到再退回 document / window，
  供哨兵续拉判定与滚动位置记录 / 恢复使用（`ProgressiveCardGrid` 内部也做了同一套
  探测 —— 它管自己的虚拟窗口，这里管整页的滚动位置）。
  缓存起来：scroll 事件里每次都遍历 DOM 太贵。
*/
let scrollHostEl: HTMLElement | null = null

/** 从某个节点往上找最近的可滚祖先（找不到返回 null） */
function findScrollHost(from: HTMLElement | null): HTMLElement | null {
  if (typeof window === 'undefined') return null
  let node: HTMLElement | null = from
  while (node) {
    const style = window.getComputedStyle(node)
    if (
      (style.overflowY === 'auto' || style.overflowY === 'scroll') &&
      node.scrollHeight > node.clientHeight + 2
    ) {
      return node
    }
    node = node.parentElement
  }
  return null
}

/** 重新探测（挂载 / 主体分支切换 / 尺寸变化后节点会换，缓存要失效） */
function resolveScrollHost(): HTMLElement | null {
  scrollHostEl = findScrollHost(gridRef.value ?? sentinel.value ?? null)
  return scrollHostEl
}

/*
  ── 原生滚动条 ──

  「已关注演员」这一页右侧已经有自绘的 A-Z 滚动条（AlphaIndex），宿主那根原生滚动条
  摆在更靠右的位置、两条并存就是冗余（2026-10-20 用户口径：原有的进度条去除）。

  做法：给**真正在滚的那个宿主容器**挂一个自有类名（样式见文件末尾的 `:global()`），
  切走 / 卸载立刻摘掉 —— 不去动宿主自己的样式表，也不影响别的页面。

  类名必须自有：联邦 CSS 门禁会把含 `.v-` / `.mdi-` 的选择器整条丢掉。
*/
const NATIVE_SCROLL_MUTED = 'sdas-native-scroll-muted'
let mutedScrollEl: HTMLElement | null = null
/** 静音前宿主容器**内联**的 padding-right（恢复时要还原成原值，不是空串） */
let mutedPrevPadRight = ''
let mutedPadApplied = false

/** 摘掉静音类并把补偿的留白还原 */
function unmuteScrollHost(): void {
  if (!mutedScrollEl) return
  mutedScrollEl.classList.remove(NATIVE_SCROLL_MUTED)
  if (mutedPadApplied) {
    mutedScrollEl.style.paddingRight = mutedPrevPadRight
    mutedPadApplied = false
  }
  mutedPrevPadRight = ''
  mutedScrollEl = null
}

function muteNativeScrollBar(on: boolean): void {
  if (typeof document === 'undefined') return
  if (!on) {
    unmuteScrollHost()
    return
  }
  // 演员页没有作品网格（gridRef 为空），从演员网格本身往上找同一个可滚容器
  const host =
    findScrollHost(actorGridAnchor.value) ?? scrollHostEl ?? resolveScrollHost() ?? null
  if (!host) return
  if (host === mutedScrollEl) return
  unmuteScrollHost()

  /*
    2026-10-20 用户口径：「右侧还有一个可以拉动的区域」—— 那是上一版**只把原生滚动条
    涂成透明**留下的：看不见但还占位、还能拖。现在彻底隐藏它。

    `scrollbar-width: none` 会把滚动条占的宽度一起收掉（Windows 约 15px），内容区
    跟着变宽 ⇒ 卡片重排（用户对布局变化极度敏感）。所以隐藏前先量出它占多宽
    （`offsetWidth - clientWidth`），把这点宽度补进容器的 padding-right，
    内容可用宽度分毫不差；量到 0（macOS 覆盖式滚动条 / 触摸屏）就直接隐藏不补偿。
  */
  const barWidth = Math.max(0, host.offsetWidth - host.clientWidth)
  mutedPrevPadRight = host.style.paddingRight
  if (barWidth > 0) {
    const base = window.getComputedStyle(host).paddingRight || '0px'
    host.style.paddingRight = `calc(${base} + ${barWidth}px)`
    mutedPadApplied = true
  }
  // 自绘 A-Z 条 = 原生滚动条
  host.classList.add(NATIVE_SCROLL_MUTED)
  mutedScrollEl = host
}

function scrollHost(): HTMLElement | null {
  return scrollHostEl ?? resolveScrollHost()
}

/** 滚动视口的底边（容器内滚动时是容器底边，否则是 window 视口） */
function viewportBottom(): number {
  const host = scrollHost()
  if (host) return host.getBoundingClientRect().bottom
  return window.innerHeight || document.documentElement.clientHeight
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
  probeAvailable.value =
    payload.summary?.probe_available === true || libraryKnown.value > 0
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
}

/**
 * 接下一页（滚动触发 / 首屏补满）—— **一次只拉一页**（与探索页 VInfiniteScroll 同语义）。
 *
 * 追加后网格的 spacer **立即**把整页高度撑出来（虚拟滚动），所以这一页进列，
 * 哨兵就往下退了约一屏多；是否继续由 finally 里的 `requestMoreIfVisible()` 按
 * 「哨兵离视口 600px 内」重新判定 —— 探索页 VInfiniteScroll 在 items 变化后也是
 * 这么重算距离的。首屏不满一屏时天然形成「连拉到出现滚动条为止」，滚动一出现就停。
 */
async function loadMore(chain = false): Promise<void> {
  if (loadingMore.value || done.value) return
  const stamp = epoch
  loadingMore.value = true
  error.value = false
  try {
    const { terminal, rows } = await fetchPage()
    if (stamp !== epoch) return
    if (terminal) {
      done.value = true
      return
    }
    append(rows)
    // 取满就收工：不用等越界页返回空数组（后端 total 是准的）
    if (total.value > 0 && works.value.length >= total.value) done.value = true
  } catch (err) {
    if (stamp !== epoch) return
    error.value = true
    toast(`加载作品失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    if (stamp === epoch) {
      loadingMore.value = false
      await nextTick()
      resolveScrollHost()
      // **只有首屏补满才接力**：滚动触发的一律一页，拉完等下一次 intersect。
      // 早先这里无条件接力，于是一次滚动就把几千部一路拉到底（滚动条越滚越细）。
      if (chain) requestMoreIfVisible()
    }
  }
}

/**
 * 哨兵还在视口 600px 内（首屏太短 / 刚追加完一页仍不够）就再拉一页。
 * 只在这里判定，`loadMore` 自身有 in-flight 守卫，链式续拉天然被「每页多一屏高度」
 * 的几何事实终止 —— 探索页那边由 VInfiniteScroll 做同一件事。
 */
function requestMoreIfVisible(): void {
  const node = sentinel.value
  if (!node || done.value || loadingMore.value || loading.value) return
  // 首屏补满最多 3 页：容器高度报 0 之类的几何异常时也不会一路拉飞
  if (page.value > FIRST_SCREEN_MAX_PAGES + 1) return
  if (node.getBoundingClientRect().top <= viewportBottom() + 600) void loadMore(true)
}

/** 重置列表并拉第一页（改筛选、刷新、首屏都走这里 —— 等价于探索页的「key 自增重挂载」） */
async function reload(): Promise<void> {
  epoch += 1
  loading.value = true
  error.value = false
  done.value = false
  page.value = 1
  seenKeys.clear()
  seenSignatures.clear()
  works.value = []
  // 海报淡入记录的 key 只增不减，切筛选/刷新时一并丢掉（同一批 key 也不会再复现）
  loadedKeys.value.clear()
  loadingMore.value = false
  // 刷新列表后回顶按钮重新按新列表的条数/滚动判，先清掉「点了回顶先藏住」的标记
  backTopHiding.value = false
  await nextTick()
  try {
    // 首屏 / 换筛选：允许接力补满一屏（最多 `FIRST_SCREEN_MAX_PAGES` 页）
    await loadMore(true)
  } finally {
    loading.value = false
  }
}

/**
 * 后台补一次**全集判库**的统计（「已入库 N 部」）。
 *
 * 页模式的 summary 只报探针缓存里已有的结论，冷缓存时就是 0 —— 后端在每次
 * ``/works`` 后都会起预热线程，这里主动拉一次 ``only_not_in_library=1``（后端
 * 因此做全量判定并把探针焐热），拿全量 summary 回填统计；预热后只要 0.2 秒。
 */
let librarySummaryBusy = false
async function refreshLibrarySummary(): Promise<void> {
  if (librarySummaryBusy || !probeAvailable.value) return
  librarySummaryBusy = true
  try {
    const payload = await fetchWorks(props, {
      only_not_in_library: true,
      page: 1,
      page_size: 1,
    })
    const summary = payload.summary
    if (summary) {
      libraryKnown.value = Number(summary.library_known || 0)
      inLibraryCount.value = Number(summary.in_library || 0)
    }
  } catch {
    // 统计补不齐不影响主界面；预热线程反正会跑，下次进来就准了
  } finally {
    librarySummaryBusy = false
  }
}

/**
 * 订阅状态集合 = **订阅清单**（`/subscriptions`：插件订阅清单 ∪ 宿主 djbaike 订阅）。
 *
 * 老实现只读宿主订阅表，自建订阅（引擎 = self 之后默认路径）根本不在里面 ——
 * 表现为「订阅了但红心不亮 / 取消点了没反应」。现在只认这一份真相，
 * 作品墙、搜索结果、演员作品页、改编页拿的都是同一个 Set。
 */
async function loadSubscribed(): Promise<void> {
  await loadSubscriptions()
}

/** 订阅清单（「已订阅」标签页；插件订阅清单 ∪ 宿主 djbaike 订阅） */
const subItems = ref<SubscriptionRow[]>([])
const subEngine = ref('')
const subsLoading = ref(false)

/**
 * 自建订阅模式？（订阅记插件清单、不进宿主订阅系统）
 *
 * 取**运行时真相**：`/subscriptions` 回的 `subEngine` → 配置页缓存 → 未知按 self。
 * 只看配置页那份会把插件订阅误判成宿主订阅 —— 取消时走错分支，红心点了没反应
 * （2026-10-22 真机）。
 */
const isSelfEngine = computed(() => {
  const engine = String(subEngine.value || configData.value.subscribe_engine || 'self')
  return engine !== 'host'
})

/**
 * 详情页「订阅设置」能不能编辑整块（暂停 / 站点 / 下载器 / 目录）。
 *
 * 判据优先用**后端 `/subscriptions` 回的 engine**（运行时真相），配置页那份只是
 * 本地缓存 —— 配置还没拉回来 / 字段缺失时，只认配置会把整块设置藏起来
 * （2026-10-22 真机：弹窗里三行落点全不见）。
 */
/** 订阅设置整块是否可编辑：与 `isSelfEngine` 同一口径（未知按 self） */
const subEditable = computed(() => isSelfEngine.value)

/**
 * 订阅行 → WorkItem（「已订阅」页复用作品墙 WorkCard 的映射）。
 *
 * 订阅端点给的行只有身份 + 海报 + 状态，WorkCard 需要的其它字段（评分 / 集数 /
 * 题材 / 简介）这里没有 —— 全部落默认值：卡片上不显示这些角标，悬停浮层的简介
 * 行退化为「演员（有则显示）· —」。想看全量信息点卡片进作品详情（`/works/detail`
 * 现查百科，与作品墙同一条路）。
 *
 * `key` 用 `sub:` 前缀 + media_id：海报加载登记表与作品墙共用一个 Set，前缀避免
 * 「同一部剧在两页各拉一次海报登记」互相干扰（其实同键也无害，前缀只是语义更清楚）。
 */
function subRowToWork(row: SubscriptionRow): WorkItem {
  const source = row.media_id.includes(':') ? row.media_id.split(':')[0].toLowerCase() : 'djbaike'
  return {
    key: `sub:${row.media_id}`,
    title: row.title,
    year: row.year || '',
    type: '电视剧',
    media_source: source,
    media_id: row.media_id,
    poster: row.poster || '',
    vote: 0,
    episode_count: 0,
    url: '',
    genres: [],
    heat: 0,
    play_count: 0,
    studio: '',
    platform: '',
    kind: '',
    release_date: '',
    actor: row.actor || '',
    actor_key: '',
    first_seen: '',
    is_new: false,
    sub_state: row.sub_state,
    sub_detail: row.sub_detail,
    sub_time: row.sub_time,
    in_library: typeof row.in_library === 'boolean' ? row.in_library : null,
  }
}

/** 「已订阅」页喂给 WorkCard 的列表（subItems 的映射视图，订阅增删自动跟随） */
const subWorkItems = computed(() => subItems.value.map(subRowToWork))

/**
 * 「已订阅」页的筛选（2026-10-23 用户口径）：未下载 / 全部 / 已入库 / 未入库。
 * 「未下载」= 订阅了但还没下成、也不在媒体库（台账没有成功记录 + 探针确认不在库）。
 * 本地状态，不落任何存储（sessionStorage 已全拆）；null（探针不可用 / 未查到）
 * 只归「全部」。
 */
type SubLibFilter = 'undown' | 'all' | 'in' | 'not'

/** 订阅行的「已完成」判定：台账成功态（downloaded / history / in_library）或探针确认在库 */
function isSubDone(row: { sub_state?: string; in_library?: boolean | null }): boolean {
  if (row.in_library === true) return true
  return ['downloaded', 'history', 'in_library'].includes(String(row.sub_state || ''))
}

const subLibFilter = ref<SubLibFilter>('undown')

const subLibCounts = computed(() => {
  let undown = 0
  let hasIn = 0
  let hasNot = 0
  for (const row of subItems.value) {
    if (row.in_library === true) hasIn += 1
    else if (row.in_library === false) hasNot += 1
    if (!isSubDone(row)) undown += 1
  }
  return { undown, hasIn, hasNot }
})

/** 筛选后的订阅卡列表（「全部」= 原样，含 null 未知的行） */
const shownSubWorkItems = computed(() => {
  if (subLibFilter.value === 'undown') {
    return subWorkItems.value.filter((work) => !isSubDone(work))
  }
  if (subLibFilter.value === 'in') {
    return subWorkItems.value.filter((work) => work.in_library === true)
  }
  if (subLibFilter.value === 'not') {
    return subWorkItems.value.filter((work) => work.in_library === false)
  }
  return subWorkItems.value
})

/**
 * 当前打开的作品详情对应的订阅行（详情页「订阅设置」弹窗的数据源）。
 * 没订阅 / 订阅清单还没回来就是 null —— 弹窗与按钮整块不渲染。
 */
const detailSubscription = computed<SubscriptionRow | null>(() => {
  const mid = detailWork.value?.media_id
  if (!mid) return null
  return subItems.value.find((row) => row.media_id === mid) || null
})

/** 详情页订阅设置里改了什么（暂停 / 恢复 / 立即搜索）：刷新订阅清单与角标 */
function onDetailSubUpdated(): void {
  void loadSubscriptions()
}

async function loadSubscriptions(): Promise<void> {
  subsLoading.value = true
  try {
    const res = await fetchSubscriptions(props)
    subItems.value = res.items
    if (res.engine) subEngine.value = res.engine
    // 订阅状态集合跟订阅清单一起刷新（唯一真相源，见 loadSubscribed 的说明）
    subscribed.value = new Set(res.items.map((row) => String(row.media_id || '')).filter(Boolean))
  } catch {
    // 面板数据拉不到就算了，不影响墙
  } finally {
    subsLoading.value = false
  }
}

// ── 随机订阅 + 立即搜索全部（主界面按钮，2026-10-23 用户口径） ──

/** 随机订阅数量（1~10，后端同样钳制） */
const randomCount = ref(1)
const randomSubscribing = ref(false)

async function randomSubscribe(): Promise<void> {
  if (randomSubscribing.value) return
  randomSubscribing.value = true
  try {
    const res = await pluginSubscribeRandom(props, randomCount.value)
    const picked: RandomSubscribeWork[] = res?.data?.items || []
    if (res?.success && picked.length) {
      const names = picked.map((item) => `《${item.title}》`).join('、')
      toast(`已随机订阅 ${picked.length} 部：${names}，订阅搜索稍后自动找资源`)
      void loadSubscriptions()
      scheduleSubscribedReload()
    } else {
      toast(String(res?.message || '没有可随机订阅的作品'), 'error')
    }
  } catch (err) {
    toast(`随机订阅失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    randomSubscribing.value = false
  }
}

const searchAllRunning = ref(false)

async function searchAllNow(): Promise<void> {
  if (searchAllRunning.value) return
  searchAllRunning.value = true
  try {
    const res = await pluginSubscribeSearchAll(props)
    if (res?.success) {
      toast(String(res?.message || '已开始订阅搜索（全部订阅）'))
      // 后台在跑：分几次把订阅行刷回来，状态角标跟着走
      for (const delay of [8000, 20000, 45000]) {
        setTimeout(() => void loadSubscriptions(), delay)
      }
    } else {
      toast(String(res?.message || '订阅搜索没能启动'), 'error')
    }
  } catch (err) {
    toast(`订阅搜索启动失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    searchAllRunning.value = false
  }
}

/**
 * 拉「已关注的演员」卡片数据（面板顶部的卡片墙）。
 *
 * 档案（头像 / 简介）优先来自后端快照 —— 发现任务每轮顺带补一次，所以默认调用很快；
 * `enrich=true`（卡片墙标题行的刷新按钮）会让后端现抓几位还没有档案的演员页，
 * 稍慢一点但能立刻把头像补上。
 */
/**
 * 首屏画完之后在后台补一次演员档案。
 *
 * 头像能按身份现拼，但**粉丝 / 获赞只存在于人物页**，必须真取一次档案；
 * 档案是进程内缓存（插件重载即空），所以打开面板时先出卡、随后静默补齐，
 * 补完直接覆盖列表 —— 用户不用手动点「刷新档案」。
 */
async function backfillFollowedProfiles(): Promise<void> {
  const need = followedActors.value.filter(
    (item) => item.actor_id && !item.followers && !item.likes,
  ).length
  if (!need) return
  try {
    const rows = await fetchActorCards(props, true)
    if (rows.length) followedActors.value = rows
  } catch {
    // 补档是锦上添花：失败就等下一轮发现任务，不打扰用户
  }
}

async function loadFollowed(enrich = false): Promise<void> {
  followedLoading.value = true
  followedError.value = ''
  try {
    followedActors.value = await fetchActorCards(props, enrich)
  } catch (err) {
    followedError.value = `演员列表加载失败：${err instanceof Error ? err.message : err}`
  } finally {
    followedLoading.value = false
  }
}

/**
 * 拉人物目录的一页。
 *
 * ``reset`` = 从第一页重来（首次进「发现演员」、切人物分类）；否则续下一页
 * （「加载更多」）。同一时刻只允许一个请求在飞 —— 连点「加载更多」不会把同一页
 * 拉两遍（分页接口没幂等保证，重复追加只能靠去重兜）。
 *
 * 数据源还没提供 ``list_people`` 时后端回「空列表 + message」，这里只把 message
 * 显示出来，**不弹错误**：那是能力缺失，不是这次请求失败。
 */
async function loadPeople(reset = false): Promise<void> {
  if (peopleLoading.value) return
  if (!reset && (!peopleHasMore.value || !peopleRows.value.length)) return
  const page = reset ? 1 : peoplePage.value + 1
  peopleLoading.value = true
  peopleError.value = ''
  try {
    const payload = await fetchPeople(props, peopleKind.value, page)
    peopleMessage.value = payload.message || ''
    const merged = reset ? payload.people : [...peopleRows.value, ...payload.people]
    const seen = new Set<string>()
    peopleRows.value = merged.filter((row) => {
      const key = row.actor_id || row.name
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    peoplePage.value = payload.page || page
    peopleHasMore.value = Boolean(payload.has_more)
  } catch (err) {
    peopleError.value = `人物目录加载失败：${err instanceof Error ? err.message : err}`
  } finally {
    peopleLoading.value = false
    // 哨兵随列表一起重排：重挂一次，若还在视口内会立刻续拉下一页
    void nextTick(observePeopleSentinel)
  }
}

/** 换人物分类 = 换一本目录，回到第一页（只在正看这一页时才请求） */
watch(peopleKind, () => {
  if (activeTab.value === 'people') void loadPeople(true)
})

/** 第一次点进「发现」才去拉：不给首屏加一次无关请求 */
watch(activeTab, (tab) => {
  // 切到「发现」**总是**重新拉（2026-10-18 用户口径：从别处切过来要刷新）：
  // 站点目录 / 榜单是活的，留着上次的旧页没意义；加载中则跳过（内部防重入）。
  if (tab === 'people') {
    if (discoverView.value === 'people') {
      void loadPeople(true)
      void nextTick(observePeopleSentinel)
    } else {
      void loadRank(discoverView.value)
      void nextTick(observeRankSentinel)
    }
  }
  // 演员 / 已订阅两页藏掉宿主原生滚动条（2026-10-22 用户口径：已订阅与已关注演员
  // 的滚动条一致）；其余页要还回去
  void nextTick(() => muteNativeScrollBar(tab === 'actors' || tab === 'subs'))
  // 换了列表，回顶按钮的显隐重新按新列表判
  backTopHiding.value = false
})

/**
 * 订阅后延迟 3 秒回查订阅表（宿主入库稍有延迟），只为把「已订阅」标出来。
 *
 * 定时器句柄统一收在这里：组件卸载（点进详情页等）时全部清掉，别让回调往已经
 * 卸载的组件写状态。
 */
const subscribeReloadTimers: ReturnType<typeof setTimeout>[] = []

function scheduleSubscribedReload(): void {
  const timer = setTimeout(() => {
    const index = subscribeReloadTimers.indexOf(timer)
    if (index >= 0) subscribeReloadTimers.splice(index, 1)
    void loadSubscribed()
  }, 3000)
  subscribeReloadTimers.push(timer)
}

// ── 滚动加载 ──

const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

// 发现演员页的哨兵（分页接口 24 条/页，滚到底自动续拉）
const peopleSentinel = ref<HTMLElement | null>(null)
let peopleObserver: IntersectionObserver | null = null

// 榜单页的哨兵（每页 30 部，与作品页同一套：滚到底续拉下一页）
const rankSentinel = ref<HTMLElement | null>(null)
let rankObserver: IntersectionObserver | null = null

/**
 * 重挂演员目录的滚动哨兵。
 *
 * 哨兵只活在「发现演员」分支里（空态 / 加载态 / 加载更多失败时都不在），
 * 分支一换就是新节点 —— 观察器不会自己跟过去，不重挂就是「滑到底也不再加载」。
 */
function observePeopleSentinel(): void {
  if (!peopleObserver) return
  resolveScrollHost()
  peopleObserver.disconnect()
  if (peopleSentinel.value) peopleObserver.observe(peopleSentinel.value)
}

/** 重挂榜单哨兵（切榜会换节点；不重挂就等于「滑到底不再加载」） */
function observeRankSentinel(): void {
  if (!rankObserver) return
  resolveScrollHost()
  rankObserver.disconnect()
  if (rankSentinel.value) rankObserver.observe(rankSentinel.value)
}

/**
 * 把滚动哨兵挂到观察器上。
 *
 * 哨兵只活在作品墙分支里 —— 跳到搜索结果 / 演员页 / 展开视图都会把它连同节点一起
 * 卸载，回到作品墙时是**新节点**；观察器不会自己跟过去，不重挂就等于「滚动加载失效、
 * 卡在第一页」。所以每次主体分支切换后都要重挂一次。
 */
function observeSentinel(): void {
  if (!observer) return
  // 节点换了 ⇒ 滚动容器可能也换了，缓存要重新探测
  resolveScrollHost()
  observer.disconnect()
  if (sentinel.value) observer.observe(sentinel.value)
}

onMounted(async () => {
  if (typeof IntersectionObserver === 'function') {
    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore()
      },
      { rootMargin: '300px 0px' },
    )
    if (sentinel.value) observer.observe(sentinel.value)
    peopleObserver = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return
        if (activeTab.value !== 'people') return
        if (peopleHasMore.value && !peopleLoading.value && peopleRows.value.length) {
          void loadPeople()
        }
      },
      { rootMargin: '300px 0px' },
    )
    if (peopleSentinel.value) peopleObserver.observe(peopleSentinel.value)
    rankObserver = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return
        if (activeTab.value !== 'people' || discoverView.value === 'people') return
        if (rankHasMore.value && !rankLoading.value && rankMedias.value.length) {
          void loadRank(discoverView.value, false)
        }
      },
      { rootMargin: '300px 0px' },
    )
    if (rankSentinel.value) rankObserver.observe(rankSentinel.value)
  }
  // capture：容器滚动的 scroll 事件不冒泡，捕获阶段才能收到
  window.addEventListener('scroll', onScroll, { passive: true, capture: true })
  // 标签条：与宿主 HeaderTab 一样 —— 监听 resize / scroll 决定渐隐指示与左右滚动钮
  window.addEventListener('resize', handleTabsResize)
  // 悬浮日志：量一次胶囊尺寸，窗口尺寸变化时重算（决定向上/向下展开）
  window.addEventListener('resize', updateLogMetrics)
  tabsContainerRef.value?.addEventListener('scroll', updateTabsIndicator)
  // 订阅名单不阻塞首屏（只影响卡片上的「已订阅」角标），跟着后台跑
  void loadSubscribed()
  // 榜单目录纯静态零网络；日志轮询 5 秒一次（固定窗口，始终在拉）
  void loadRankCatalog()
  void loadLogs()
  logsTimer = setInterval(() => void loadLogs(), 5000)
  await Promise.all([reload(), loadFollowed()])
  // 首屏之后静默补档（粉丝 / 获赞 / 简介），不阻塞卡片先出来
  void backfillFollowedProfiles()
  // 冷缓存时首屏「已入库 0 部」（页模式只报探针缓存里的局部结论）——
  // 后台补一次全量判库的 summary（后端会顺带预热），几秒后数字自己变准
  void refreshLibrarySummary()
  await nextTick()
  // 先量尺寸/视口，再读回上次位置并夹回可见范围（顺序反了会夹到错误边界）
  updateLogMetrics()
  loadLogPos()
  onScroll()
  watchGrid()
  updateTabsIndicator()
  // 挂载完成后再判一次原生滚动条（此刻视图已定型）
  muteNativeScrollBar(activeTab.value === 'actors' || activeTab.value === 'subs')
})

/**
 * 持续记录滚动位置：只服务「回到顶部」按钮的显隐（scrolledFar / backTopHiding），
 * 不写任何存储（2026-10-22 用户口径：sessionStorage 完全去除）。
 *
 * ⚠️ 滚的是「页面内容那层容器」（见 `scrollHost`）而不是 window ⇒ 读它的 `scrollTop`；
 * 早先读 `window.scrollY` 在面板里恒为 0，等于「返回时永远跳到顶」。
 * 监听用 capture：scroll 事件不冒泡，但捕获阶段会从 window 一路传到真正的滚动节点。
 */
/** 滚得够远了（作品墙用这个判据；演员页改用条数，见 `showBackTop`） */
const scrolledFar = ref(false)

/**
 * 点过「回到顶部」后先藏起来（2026-10-18 用户口径：点了就该消失，别赖在原地）。
 * 用户再次向下滚（离开顶部超过 300px）时才重新亮出来；切标签 / 重载时一并复位。
 */
const backTopHiding = ref(false)

/**
 * 回到顶部按钮的显隐。
 *
 * 演员两页（已关注 / 发现）**按加载条数**判：超过 30 位就一直显示 —— 这两页一屏
 * 放不下 30 张卡，用户不需要先滚一段才等到按钮（2026-10-18 用户口径）。
 * 作品墙仍按滚动距离（300px）。
 */
const showBackTop = computed(() => {
  // 整页视图（作品详情 / 演员作品页 / 原著页）里不显示：返回键已钉在视口左下，
  // 再放一个「回到列表顶部」会把详情页本身滚回顶部。
  if (viewLayer.value) return false
  // 刚点过回顶：藏住，等再往下滚才回来
  if (backTopHiding.value) return false
  if (activeTab.value === 'actors') return shownActors.value.length > 30
  if (activeTab.value === 'people') return peopleRows.value.length > 30
  return scrolledFar.value
})

/**
 * 记录滚动位置。**三个来源取最大值**：
 *
 * 面板里滚的可能是宿主钉的内容容器、也可能就是 window（不同布局模式不一样，
 * 插件里拿到的 `scrollHost()` 偶尔探测不到）。早先只读 `scrollHost()`，
 * 探测失败就恒为 0 —— 表现正是「页数再多也永远滚不过一屏、回顶按钮不出现」。
 * 所以这里同时看：探测到的容器、window、以及**滚动事件的目标元素**（最可靠）。
 */
function currentScrollTop(event?: Event): number {
  const host = scrollHost()
  const target = (event?.target || null) as HTMLElement | null
  const fromTarget =
    target && target !== (document as unknown as HTMLElement)
      ? Number(target.scrollTop || 0)
      : Number(document.scrollingElement?.scrollTop || 0)
  return Math.max(
    host ? Number(host.scrollTop || 0) : 0,
    Number(window.scrollY || 0),
    fromTarget || 0,
  )
}

function onScroll(event?: Event): void {
  lastScrollY = currentScrollTop(event)
  // 阈值 300：滚过小半屏就该能一键回顶（600 在窄面板里往往已经接近底部了）
  scrolledFar.value = lastScrollY > 300
  // 点过回顶后再次向下滚出一段距离 → 重新亮出按钮
  if (backTopHiding.value && lastScrollY > 300) backTopHiding.value = false
}

/** 回到列表顶部（滚的是宿主钉的那个内容容器，不是 window） */
function scrollToTop(): void {
  const host = scrollHost()
  if (host) host.scrollTo({ top: 0, behavior: 'smooth' })
  else window.scrollTo({ top: 0, behavior: 'smooth' })
  lastScrollY = 0
  scrolledFar.value = false
  // 按钮先藏起来，再次向下滚才重新出现
  backTopHiding.value = true
}

/** 跳到记录的位置（容器滚动 ⇒ 滚容器，否则滚 window） */
function scrollToPosition(position: number): void {
  const host = scrollHost()
  if (host) host.scrollTo({ top: position })
  else window.scrollTo({ top: position })
}

/** 当前的滚动位置（容器滚动 ⇒ 容器的 scrollTop，否则 window.scrollY） */
function currentScrollY(): number {
  const host = scrollHost()
  return host ? host.scrollTop : window.scrollY || 0
}

onUnmounted(() => {
  // 离开页面前把宿主原生滚动条还原（类是临时挂上去的）
  muteNativeScrollBar(false)
  if (logsTimer) {
    clearInterval(logsTimer)
    logsTimer = null
  }
  window.removeEventListener('scroll', onScroll, { capture: true })
  window.removeEventListener('resize', updateLogMetrics)
  // 拖动中途卸载：摘掉挂在 window 上的 pointer 监听，避免泄漏
  onLogPointerUp()
  window.removeEventListener('resize', handleTabsResize)
  tabsContainerRef.value?.removeEventListener('scroll', updateTabsIndicator)
  if (tabsResizeTimer) {
    clearTimeout(tabsResizeTimer)
    tabsResizeTimer = null
  }
  observer?.disconnect()
  observer = null
  gridObserver?.disconnect()
  gridObserver = null
  cellObserver?.disconnect()
  cellObserver = null
  cellElements.clear()
  if (tipTimer) clearTimeout(tipTimer)
  if (lookupTimer) clearTimeout(lookupTimer)
  while (subscribeReloadTimers.length) {
    const pending = subscribeReloadTimers.pop()
    if (pending) clearTimeout(pending)
  }
})

// 网格节点与滚动哨兵挂在下述几个互斥分支里（作品详情 / 搜索结果 / 演员页 / 作品墙 /
// 展开视图），切换时节点会重建 —— 一律重新量一次宽度（列数）并重挂哨兵观察
// 网格节点与滚动哨兵挂在下述几个互斥分支里（作品详情 / 搜索结果 / 演员页 / 作品墙 /
// 展开视图），切换时节点会重建 —— 一律重新量一次宽度（列数）并重挂哨兵观察。
// `viewLayer` 也要看：两个整页视图之间层层退回时节点同样会重建。
watch([searchActive, activeTab, detailActor, detailWork, viewLayer], async () => {
  await nextTick()
  observeSentinel()
  watchGrid()
})

/*
 * 演员卡片铺满一屏之前，宿主容器还没有可滚的内容（`scrollHeight === clientHeight`），
 * 这时探不到「真正在滚的那个节点」。所以条数一变就重试一次藏原生滚动条。
 */
watch(
  () => shownActors.value.length,
  async (count) => {
    if (activeTab.value !== 'actors' || !count) return
    await nextTick()
    muteNativeScrollBar(true)
  },
)

/*
 * 「已订阅」同理：数据是切到该页之后才回来的，回来那一刻容器可能还没有可滚内容
 * （探不到真正在滚的节点）—— 条数一变就补一次藏滚动条。
 */
watch(
  () => shownSubWorkItems.value.length,
  async (count) => {
    if (activeTab.value !== 'subs' || !count) return
    await nextTick()
    muteNativeScrollBar(true)
  },
)

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

// 筛选条件一变就重新拉第一页；搜索演员做防抖，避免每敲一个字都去查百科
let lookupTimer: ReturnType<typeof setTimeout> | null = null
watch([actor, genre, year, studio, platform, sort, onlyNotInLibrary, onlyNotSubscribed], () => {
  // 槽位上的筛选行在整页视图旁边仍然可见：改筛选 = 要看列表，先把整页视图退掉
  exitViews()
  reload()
})

// 演员页的分类只是本地过滤（不必重拉作品）。
// 但整页视图开着时点分类 = 想回卡片墙看这一类，所以要连带退出（toActorWall）。
watch(actorGender, () => {
  toActorWall()
})
watch(actorQuery, () => {
  // 整页视图开着时只要搜索栏里有词（新一次搜索），就退出去让搜索结果占主体 ——
  // 否则那一页会把结果盖住，用户敲了词像没反应。
  // 进整页视图时清空搜索框那一拍 next 是空串，不会误退。
  if (searchKeyword.value) exitViews()
  if (lookupTimer) clearTimeout(lookupTimer)
  // 打字只查本地缓存（零请求）；要站点结果得按回车 / 点「搜索」
  lookupTimer = setTimeout(() => void runLookup('cache'), LOOKUP_DEBOUNCE)
})

// 标签切换：只退整页视图，不写盘（2026-10-22 用户口径：sessionStorage 已完全去除）。
// （节点重建后的量宽 / 哨兵重挂由上面那个分支 watch 统一负责。）
watch(activeTab, () => {
  // 换标签 = 换页：整页视图是「钻进某个东西」，换页就退出来 ——
  // 否则会把列表盖住（点了标签像没反应）。
  exitViews()
})

// ── 动作 ──

/** 订阅：配置页指定了下载器 → 直接向宿主提交（弹窗没有下载器选项，带不上偏好）；
 * 没指定 → 弹系统订阅对话框，走宿主默认 */
/** 订阅请求进行中（详情页的订阅按钮转圈，避免连点） */
const subscribing = ref(false)
/** 正在处理的那部剧（卡片爱心据此转圈；空串 = 空闲） */
const subscribingId = ref('')

/** 正在「订阅全部作品」的演员键（演员卡 / 详情页按钮据此转圈；空串 = 空闲） */
const subscribingAllKey = ref('')

/** 待确认取消订阅的作品（非空 = 确认层打开） */
const cancelTarget = ref<WorkItem | null>(null)

/** 确认层的开关（`v-dialog` 的 v-model；关掉即放弃取消） */
const cancelOpen = computed({
  get: () => cancelTarget.value !== null,
  set: (on: boolean) => {
    if (!on) cancelTarget.value = null
  },
})

/** 点「已订阅」：先问一句，不直接删 */
function askCancelSubscribe(work: WorkItem): void {
  if (subscribing.value) return
  cancelTarget.value = work
}

/**
 * 确认取消订阅 —— 只调插件接口清**插件订阅清单**。
 *
 * 2026-10-23 用户口径：宿主订阅链路整套去除，不再调宿主的
 * `DELETE subscribe/media/{media_id}`，也不再 `cancelSubscribe`。
 */
async function confirmCancelSubscribe(): Promise<void> {
  const work = cancelTarget.value
  if (!work) return
  subscribing.value = true
  subscribingId.value = work.media_id
  try {
    const res = await pluginUnsubscribe(props, work.media_id)
    if (res && res.success === false) {
      toast(String(res.message || '取消订阅失败'), 'error')
      return
    }
    const next = new Set(subscribed.value)
    next.delete(work.media_id)
    subscribed.value = next
    toast(`已取消订阅：${work.title}`)
    void loadSubscriptions()
  } catch (err) {
    toast(`取消失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    subscribing.value = false
    subscribingId.value = ''
    cancelTarget.value = null
  }
}

/**
 * 订阅一部剧。
 *
 * 现在**优先直连宿主订阅接口**：带上 `season` / `start_episode` / `total_episode`，
 * 宿主就不会再去做「补充识别」（那一步对插件来源必然失败 —— 识别结果里没有 seasons，
 * 直接报「媒体信息中没有季集信息」，这就是之前「点了没反应」的根因）。
 *
 * 直连失败且宿主注入了 `nativeSubscribe` 时，交回宿主的订阅弹窗（能选季 / 下载器）；
 * 两条路都走不通也一定给一句 toast —— 不再出现「点了什么都没有」。
 */
/** 正在「立即搜索」的那部作品（空串 = 空闲；只有那张卡的按钮转圈） */
const searchNowId = ref('')

/**
 * 卡片底部「立即搜索」：动作与订阅设置里的「立即搜索一次」完全一样
 * —— 后端清掉冷却后开后台线程跑一轮（``/subscribe/search_now``）。
 *
 * 后端的 search_now 只认**订阅清单里的作品**，所以未订阅时先订阅再搜：
 * 点一下就是「订阅 + 现在就搜一次」。
 */
async function searchNow(work: WorkItem): Promise<void> {
  if (searchNowId.value) return
  searchNowId.value = work.media_id
  try {
    await ensureConfig()
    if (!subscribed.value.has(work.media_id)) {
      const sub = await pluginSubscribe(props, work)
      if (sub && sub.success === false) {
        toast(String(sub.message || '订阅失败'), 'error')
        return
      }
      const next = new Set(subscribed.value)
      next.add(work.media_id)
      subscribed.value = next
    }
    const result = await pluginSubscribeSearchNow(props, work.media_id)
    toast(result?.message || `已开始搜索《${work.title}》，结果稍后回填`)
    scheduleSubscribedReload()
  } catch (err) {
    toast(`立即搜索失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    searchNowId.value = ''
  }
}

async function subscribe(work: WorkItem): Promise<void> {
  if (subscribed.value.has(work.media_id)) {
    // 已订阅 ⇒ 再点一次是**取消订阅**（与系统详情页一致：那里点「已订阅」= 取消）。
    // 先弹确认层，避免误触把订阅删掉。
    askCancelSubscribe(work)
    return
  }
  if (subscribing.value) return
  subscribing.value = true
  subscribingId.value = work.media_id
  try {
    await ensureConfig()
    // 2026-10-23 用户口径：宿主订阅链路整套去除 —— 订阅只记进**插件订阅清单**
    // （「已订阅」标签页可见），由订阅搜索任务全分类搜索、命中即下。
    const res = await pluginSubscribe(props, work)
    if (res && res.success === false) {
      toast(String(res.message || '订阅失败'), 'error')
      return
    }
    const next = new Set(subscribed.value)
    next.add(work.media_id)
    subscribed.value = next
    toast(res?.message || `已订阅：${work.title}`)
    void loadSubscriptions()
  } catch (err) {
    toast(`订阅失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    subscribing.value = false
    subscribingId.value = ''
  }
}

/**
 * 把配置里的「逗号分隔站点 ID 串」解析成数字数组（宿主订阅接口的 `sites` 是 int 列表）。
 * 与配置页同一个容错口径：中文逗号 / 分号 / 空白都算分隔符，非法项直接丢弃。
 */
function parseSiteIds(value: string | undefined): number[] {
  return String(value || '')
    .split(/[,，;；\s]+/)
    .map((item) => Number(item))
    .filter((id) => Number.isFinite(id) && id > 0)
}

/** 「订阅全部作品」结果的一句话摘要（提交 / 已在库 / 已订阅 / 失败） */
function describeSubscribeAll(res: {
  submitted: number
  skipped_library: number
  skipped_subscribed: number
  failed: number
  capped: boolean
}): string {
  const parts = [`提交 ${res.submitted} 部`]
  if (res.skipped_library) parts.push(`已在库 ${res.skipped_library} 部`)
  if (res.skipped_subscribed) parts.push(`已订阅 ${res.skipped_subscribed} 部`)
  if (res.failed) parts.push(`失败 ${res.failed} 部`)
  if (res.capped) parts.push('超出单次上限，可再点一次继续')
  return parts.join(' · ')
}

/**
 * 订阅一位演员的**全部作品**（演员卡 / 演员详情页的按钮）。
 *
 * 走插件后端批量接口（`/actors/subscribe_all`）：作品由后端现取，不受演员详情页
 * 滚动加载的分页影响；前端已知已订阅的（`subscribed` 集合）作为 `exclude_ids` 传过去，
 * 已在库的由后端按配置跳过。成功的作品顺手把爱心点亮点（不必等回查）。
 */
async function subscribeAllWorks(
  item: ActorCandidate | ActorCardItem | null | undefined,
): Promise<void> {
  if (!item || subscribingAllKey.value) return
  const key = actorKey(item)
  subscribingAllKey.value = key
  try {
    const res = await subscribeAllActor(props, {
      actorId: String(item.actor_id || ''),
      name: String(item.name || ''),
      excludeIds: Array.from(subscribed.value),
    })
    if (res.media_ids.length) {
      const next = new Set(subscribed.value)
      for (const mediaId of res.media_ids) next.add(mediaId)
      subscribed.value = next
      scheduleSubscribedReload()
    }
    toast(`${item.name}：${describeSubscribeAll(res)}`, res.failed ? 'error' : 'info')
  } catch (err) {
    toast(`订阅全部失败：${err instanceof Error ? err.message : err}`, 'error')
  } finally {
    subscribingAllKey.value = ''
  }
}

/**
 * 打开**本插件自绘的作品详情页**（不再跳宿主媒体详情页）。
 *
 * 宿主详情页对短剧基本是空的：它的信息面板 / 演职员 / 推荐 / 分季全都以 `tmdb_id`
 * 为前提，而短剧大多不在 TMDB 上；播放量 / 热度 / 真人·AI 角标更是宿主模型里没有的字段。
 * 自绘详情页把这些一起铺开（数据走 `/works/detail`，见 WorkDetail.vue）。
 *
 * 详情是**卡片区**的内容，不切标签也不清搜索词 ⇒ 返回能原样回到来源页。
 */
function openWorkDetail(work: WorkItem): void {
  if (viewLayer.value === 'adapted') {
    // 原著页的「改编作品」卡点进来：原著页留着（返回退回去）
    workOpenedFrom = 'adapted'
    actorOpenedFrom = ''
  } else if (viewLayer.value === 'actor') {
    // 演员作品页的卡片点进来：演员页留着（返回能回去）。演员页下面若还压着别的作品页，
    // 这一步会把它盖掉 ⇒ 连带把演员页的返回目标降级成列表，免得退回去看到的不是原来那部。
    workOpenedFrom = 'actor'
    actorOpenedFrom = ''
  } else {
    workOpenedFrom = ''
    detailScrollY = currentScrollY()
  }
  detailWork.value = work
  viewLayer.value = 'work'
  scrollToPosition(0)
}

/**
 * 作品详情页的演员阵容卡点开：与宿主同构（作品详情 → 人物详情 → 返回回作品详情）。
 *
 * 与 `openActorDetail`（列表入口）的区别只有一个：**不动 `detailWork`** —— 演员页叠在
 * 作品详情之上，返回时退回去还是那一页（滚动位置也照原样还原）。
 */
function openActorFromWork(item: ActorCandidate): void {
  actorQuery.value = ''
  actorOpenedFrom = 'work'
  detailActor.value = item
  viewLayer.value = 'actor'
  scrollToPosition(0)
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

/**
 * 卡片上的搜索：按配置页选定的站点跳宿主资源搜索页（不带弹窗）。
 *
 * 走的是**全分类标题搜索**（不带媒体身份 / 不带 type），因为短剧在各站的分类
 * 极不统一 —— PTS 就把《为所欲为（80集）…SKIT》放在「电影」分类，按电视剧搜
 * 站点侧会直接过滤掉。详见 `api.ts` 里 `resourceSearchUrl` 的注释。
 */
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
  /* 日志窗绝对定位到右上，**不参与行高** —— 否则 100px 高的小窗会把标题行撑高，
     标题与「搜索」行之间就空出一大块（2026-10-24 用户反馈） */
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  min-height: 46px;
  padding: 0 12px;
}

.sdas-head-main {
  min-width: 0;
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
  悬浮「最近日志」：默认钉在右下角（Teleport 到 body，不随页面滚动），可拖动。
  默认只露胶囊；悬浮展开日志区（在胶囊**上方**，胶囊位置不动 ⇒ 不闪）。
  只有胶囊吃鼠标（拖动 / hover），日志区 `pointer-events: none` 点击穿透。
  自有类名（不含 `.v-`），联邦 CSS 门禁放行；配色只吃主题变量。
*/
.sdas-logfloat {
  /* 位置**只由内联样式**给（四个方向都给值）：若这里再写 right/bottom，
     向下展开时内联的 top 会和它一起生效，把容器拉成整屏高、胶囊被顶走
     —— 这就是之前「拖到屏幕上方拖不过去」的根因（2026-10-24）。 */
  position: fixed;
  z-index: 2100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  pointer-events: none;
}

/* 向右展开（胶囊在左半屏）：换成贴容器左边缘，日志才有地方往右长 */
.sdas-logfloat.is-right {
  align-items: flex-start;
}

/* 量尺寸专用：强制收起态再量，避免 hover 展开时量到被 stretch 的尺寸 */
.sdas-logfloat.sdas-measuring .sdas-logfloat-body {
  display: none !important;
}

.sdas-logfloat.sdas-measuring .sdas-logfloat-bar {
  align-self: flex-end;
}

.sdas-logfloat.is-right.sdas-measuring .sdas-logfloat-bar {
  align-self: flex-start;
}

.sdas-logfloat-bar {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 999px;
  background: rgba(var(--v-theme-surface), 0.9);
  backdrop-filter: blur(4px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.16);
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.4;
  pointer-events: auto;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.sdas-logfloat.is-dragging .sdas-logfloat-bar {
  cursor: grabbing;
}

/* 展开态：日志区与胶囊拼成一张卡（胶囊圆角改成下圆角，日志区上圆角） */
.sdas-logfloat:hover .sdas-logfloat-bar {
  border-top-color: transparent;
  border-radius: 0 0 8px 8px;
  align-self: stretch;
  justify-content: flex-start;
}

.sdas-logfloat-body {
  display: none;
  width: min(46vw, 380px);
  max-height: 96px;
  /* 竖向 + **横向**都能滚：日志行往往比面板宽，以前只能看到被截断的半句
     （2026-10-24 用户口径）。细滚动条，不喧宾夺主。 */
  overflow: auto;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
  padding: 6px 10px 4px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: rgba(var(--v-theme-surface), 0.92);
  backdrop-filter: blur(4px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.16);
  /* 展开后可悬停 / 滚动 / 选文字：鼠标进到日志上也保持在 hover 里，不会收起 */
  pointer-events: auto;
  cursor: auto;
}

.sdas-logfloat:hover .sdas-logfloat-body {
  display: block;
}

/* 向下展开：胶囊在上、日志在下（拖到页面上半屏时） */
.sdas-logfloat.is-down {
  flex-direction: column-reverse;
}

.sdas-logfloat.is-down .sdas-logfloat-body {
  border-top: none;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 0 0 8px 8px;
}

.sdas-logfloat.is-down:hover .sdas-logfloat-bar {
  border-top-color: rgba(var(--v-theme-on-surface), 0.12);
  border-bottom-color: transparent;
  border-radius: 8px 8px 0 0;
}

/* 拖动期间不展开，避免边拖边弹 */
.sdas-logfloat.is-dragging .sdas-logfloat-body {
  display: none;
}

.sdas-logfloat-line {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  line-height: 1.55;
  /* `pre` 保留原始空格缩进、不换行；行宽由内容决定 ⇒ 超出面板就横向滚，
     不再用 ellipsis 把后半句吃掉（选文字复制也能拿到整行）。 */
  white-space: pre;
  width: max-content;
  min-width: 100%;
  color: rgba(var(--v-theme-on-surface), 0.82);
}

.sdas-logfloat-dim {
  color: rgba(var(--v-theme-on-surface), 0.45);
}

/*
  视图标签条：「已订阅 / 作品 / 已关注演员 / 发现演员」。**自绘**（不用宿主的 VTabs —— 联邦只保证 vue 共享，
  Vuetify 组件是否全局注册不可控），类名全自有前缀，不触发联邦 CSS 门禁。
  标签条 / 视图槽位 / 卡片区各自独立成块 ⇒ 切页只换槽位内容与卡片区，版面不重排。

  版式**照宿主探索页顶栏那排来源标签（TheMovieDb / 豆瓣 / Bangumi…）逐条复刻** ——
  宿主那份是 `src/layouts/default/components/HeaderTab.vue`（scoped，联邦匹配不上 ⇒
  数值照搬、类名自有）。它**没有**整条下边框（选中态自带 3px 指示条），所以这里
  原先那条 `border-bottom` 一并去掉。颜色变量宿主用的是 `on-background`，这里换
  `on-surface`（标签条画在插件面板的 surface 底上，另两个状态值 0.7 / 1 照抄）。
*/
.sdas-tabs {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: all 0.3s ease;
}

/*
  标签轨道：横向可滑、滚动条隐藏、右侧 95% 处起渐隐（与宿主同款的 mask），
  再叠一个 40px 的渐隐指示块（只在「还能往右滑」时淡入）。
*/
.sdas-tabs-track {
  position: relative;
  display: flex;
  flex-grow: 1;
  gap: 12px;
  min-inline-size: 0;
  overflow-x: auto;
  padding-block: 4px;
  padding-inline-end: 20px;
  scrollbar-width: none;
  -webkit-mask-image: linear-gradient(to right, black 95%, transparent 100%);
  mask-image: linear-gradient(to right, black 95%, transparent 100%);
}

.sdas-tabs-track::-webkit-scrollbar {
  display: none;
}

.sdas-tabs-track::after {
  position: absolute;
  z-index: 1;
  background: linear-gradient(to left, rgba(var(--v-theme-surface), 1) 30%, transparent);
  content: '';
  inline-size: 40px;
  inset-block: 0;
  inset-inline-end: 0;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease-in-out;
}

.sdas-tabs-track.show-indicator::after {
  opacity: 1;
}

/* 左右滚动钮：28px 圆形，一次滑 200px（触摸端交给手势，见下方媒体查询） */
.sdas-tabs-scroll {
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border: 0;
  border-radius: 50%;
  block-size: 28px;
  inline-size: 28px;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.6);
  cursor: pointer;
  outline: none;
  transition: background-color 0.2s ease;
}

.sdas-tabs-scroll:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.06);
}

.sdas-tabs-scroll-left {
  margin-inline-end: 6px;
}

.sdas-tabs-scroll-right {
  margin-inline-start: 6px;
}

.sdas-tab {
  position: relative;
  display: flex;
  align-items: center;
  border: 0;
  border-radius: 20px;
  background-color: transparent;
  padding-block: 6px;
  padding-inline: 14px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.3;
  color: rgba(var(--v-theme-on-surface), 0.7);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 10%);
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s ease;
}

/* 选中指示条：3px 主色、宽 70%、居中展开（宿主 scaleX(0) → scaleX(1)） */
.sdas-tab::after {
  position: absolute;
  border-radius: 3px;
  background-color: rgb(var(--v-theme-primary));
  block-size: 3px;
  content: '';
  inline-size: 70%;
  inset-block-end: -4px;
  inset-inline-start: 50%;
  transform: translateX(-50%) scaleX(0);
  transition: transform 0.2s ease;
}

.sdas-tab.is-active {
  color: rgb(var(--v-theme-primary));
  text-shadow: 0 1px 3px rgba(0, 0, 0, 15%);
}

.sdas-tab.is-active::after {
  transform: translateX(-50%) scaleX(1);
}

/* 未选中 hover：5% 主色底 + 文字提到全不透明（宿主同款） */
.sdas-tab:hover:not(.is-active) {
  background-color: rgba(var(--v-theme-primary), 0.05);
  color: rgba(var(--v-theme-on-surface), 1);
}

/* 触摸端支持手势横滑，滚动钮与渐隐指示块都不需要 —— 与宿主同一条媒体查询 */
@media (hover: none) and (pointer: coarse) {
  .sdas-tabs-scroll {
    display: none !important;
  }

  .sdas-tabs-track::after {
    display: none !important;
  }
}

/*
  视图槽位：作品标签页装作品维度筛选行，演员标签页装演员页工具栏。
  高度**随内容自适应**（用户要求：不留白）—— 演员页只有一行工具栏，槽位就只有一行高，
  卡片区紧跟着往上收；早先那条按作品页筛选区实测高度补的 min-height 已撤掉。
  行结构（flex / justify-start / align-center / mr-5）与标签（VLabel）的类名沿用探索页。
*/
.sdas-slot {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* 演员页工具栏：贴齐筛选行的行高，垂直方向与作品页第一行对齐 */
.sdas-actor-bar {
  min-height: 40px;
}

/* 搜索行：常驻在标签条**上方**，两个标签页共用同一条搜索 */
.sdas-search-row {
  display: flex;
  align-items: center;
}

/*
  ⚠️ 凡是选择器里带 `.v-*`（宿主 Vuetify 组件类）的规则**一律不要写**：
  `vite.config.ts` 的 postcss 门禁会把整条规则丢掉（联邦插件不得发布组件库基础样式，
  主指南 §8.3 第 5 条）。早先这里针对 `.v-chip-group` / `.v-chip__content` 的几条排版规则
  从未生效过，2026-10-20 已删除；要调 chip 的排版只能靠自有类名（如 `.sdas-grid-cells`）
  挂在组件外层元素上，或者用 `:deep()` 之外的其他手段。
*/

/* 标签列定宽：「版权方」3 个字、其余 2 个字 —— 定宽后各行 chips 的起点才竖向对齐 */
/* 媒体库两张卡（未入库 / 未订阅）：点一下即筛，再点取消 */
.sdas-library-cards {
  display: flex;
  gap: 8px;
}

.sdas-library-card {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.18);
  border-radius: 999px;
  font-size: 0.8125rem;
  line-height: 1.2rem;
  background: transparent;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.sdas-library-card:hover:not(:disabled) {
  background: rgb(var(--v-theme-on-surface), 0.06);
}

.sdas-library-card:disabled {
  opacity: 0.45;
  cursor: default;
}

.sdas-library-card.is-active {
  border-color: rgb(var(--v-theme-primary));
  background: rgb(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}

.sdas-library-count {
  margin-inline-start: 6px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgb(var(--v-theme-primary), 0.18);
  font-size: 0.6875rem;
}

.sdas-row-label {
  flex: 0 0 3.5em;
}

/* 「只看未入库」开关：贴齐 chip 行高，别把筛选区撑高 */
.sdas-slot .sdas-checkbox {
  flex: none;
  margin-top: -2px;
}

/* 折叠态：整排渲染但高度裁到一行（第二排正好从 40px 起，被裁掉）；展开后摘掉裁切 */
.sdas-slot .sdas-clip {
  max-height: 40px;
  overflow: hidden;
}

.sdas-chip-count {
  margin-left: 5px;
  font-size: 11px;
  opacity: 0.6;
  letter-spacing: 0;
}

/* 标签条里的计数（「已关注演员 N」）：宿主那排标签没有计数，间距取它图标那 6px；
   选中态跟着提亮一点，免得主色文字后面挂一个灰数字 */
.sdas-tab .sdas-chip-count {
  margin-left: 6px;
  opacity: 0.7;
}

.sdas-tab.is-active .sdas-chip-count {
  opacity: 0.9;
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

/* 演员页的卡片区是**一个网格集合**（用户要求：不再按性别分块），没有组标题与组间距；
   顺序按拼音 A-Z（见 `shownActors` / `actorLetterStops`），网格样式见 `.sdas-actor-grid`。 */

.sdas-item {
  min-width: 0;
}

/* 演员卡的样式（.sdas-card / .sdas-poster-* / .sdas-card-title 等）随卡片一起搬到了
   ActorCard.vue —— 搜索结果与「已关注」两处共用同一个组件，这里不再保留副本。 */

/* 回到顶部（Teleport 到 body 后钉在视口右下）。
   2026-10-18 用户口径：**放大**（52px、图标 26）且**不贴边**（离边 40px），
   别缩成一颗小点。层级取 1500：高于面板内容（< 10），低于 Vuetify 弹窗（~2400）——
   弹窗打开时不该还能点它。 */
.sdas-back-top {
  position: fixed;
  inset-inline-end: 40px;
  inset-block-end: 40px;
  width: 52px !important;
  height: 52px !important;
  z-index: 1500;
}

.sdas-sentinel {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  font-size: 12px;
  color: var(--sdas-fg-dim);
}


/* 空态（探索页同款）见 NoDataFound.vue —— 旧的 sdas-empty 三条样式已随替换删掉 */

/* 自绘提示条 */
/* 搜索页的量宽哨兵：零高占满一行，两个结果网格的列宽都从它量 */
.sdas-measure {
  inline-size: 100%;
  block-size: 0;
}

/* 搜索页里某一类结果为空的小提示（另一类有结果时才单独露出来） */
.sdas-search-miss {
  opacity: 0.8;
}

/*
 * ── 已关注演员：A-Z 平铺网格（非虚拟渲染，不分组） ──
 *
 * 列宽口径与虚拟网格一致（144px 起、16px 间距），换成实体网格后视觉不变。
 * 2026-10-20 用户口径：卡片直接按 A-Z 铺，不插组标题；右侧只留一条「滚动条」式索引。
 *
 * **不给滚动条留专用带**（2026-10-20 用户口径）：卡片铺满整行，滚动条整体挪到
 * 视口最右侧、也就是宿主原生滚动条原来待的那个位置（见 AlphaIndex 的 `right: 2px`）。
 */
.sdas-actor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(144px, 1fr));
  gap: 16px;
}

/* 每个格子先按 2:3 占位（与演员卡等高），懒挂载前后位置不跳。
   **不能加 `overflow: hidden`**：卡片悬停会 `translateY(-4px)` 抬起来（宿主的
   `app-hover-lift-card`），裁掉就看不见了 —— 圆角只用来修饰占位块。 */
.sdas-actor-cell {
  position: relative;
  aspect-ratio: 2 / 3;
  border-radius: 12px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  /* 点字母跳过来时给宿主顶栏（搜索栏）让出高度，目标卡不被盖住 */
  scroll-margin-block-start: 84px;
}

.sdas-actor-cell > :deep(*) {
  block-size: 100%;
  inline-size: 100%;
}

/*
 * ── 演员页：把宿主原生滚动条**彻底隐藏** ──
 *
 * 上一版只把轨道和拇指涂成全透明，结果右侧留下一条「看不见但能拖」的区域
 * （2026-10-20 用户口径：「右侧为什么还有一个可以拉动的区域」）。现在直接收掉。
 *
 * ⚠️ 单纯 `scrollbar-width: none` 会把滚动条**占的宽度一起收掉**（Windows 上约 15px），
 * 滚动容器内容区随之变宽，作品墙卡片重新换行、列数变化（用户口径：作品墙恢复成以前
 * 的布局，只动滚动条）。所以宽度不能白丢 —— `muteNativeScrollBar()` 在加这个类**之前**
 * 量出滚动条宽度，等量补进容器的 padding-right，内容可用宽度分毫不差。
 *
 * 类名由 `muteNativeScrollBar()` 动态加到真正在滚的祖先上（宿主把页面内容第一层
 * 钉成固定高 + overflow-y:auto），所以只能用 `:global()` —— scoped 会给选择器补
 * `[data-v-xxx]`，而那是宿主节点、没有这个属性。类名是自有前缀，CSS 门禁不删。
 */
:global(.sdas-native-scroll-muted) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

:global(.sdas-native-scroll-muted::-webkit-scrollbar) {
  inline-size: 0;
  block-size: 0;
  display: none;
}

/* 随机订阅数量输入框：窄一格，别把工具栏撑开 */
.sdas-random-count {
  inline-size: 96px;
  flex: 0 0 96px;
}

/* 窄屏：工具栏允许换行，按钮不挤成一团 */
@media (width < 900px) {
  .sdas-actor-bar {
    flex-wrap: wrap;
    row-gap: 4px;
  }
}
</style>
