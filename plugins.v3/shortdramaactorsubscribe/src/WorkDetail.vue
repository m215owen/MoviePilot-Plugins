<template>
  <!--
    作品详情页（**自绘**，不用宿主自带的媒体详情页）。

    为什么要自己画：宿主详情页（`MoviePilot-Frontend` 的 `MediaDetailView.vue`）里
    右侧信息面板 / 演员阵容 / 推荐 / 分季**全部以 `tmdb_id` 为前提** —— 短剧大多不在
    TMDB 上，那些区块整块不渲染；播放量 / 热度 / 真人·AI 角标更是宿主模型里
    压根没有的字段。这里把百科详情页的字段与作品卡上的字段合起来铺开。

    版式**照宿主「探索」页点进作品详情页的那一页一比一复刻**（逐条对过它的模板与
    scoped 样式，数值直接搬）：

      · 顶栏大图 = **两层绝对定位铺满整宽**（宿主 `.vue-media-back`，24rem `h-96` +
        四向渐变收底）；内容块从**页面顶部**起、叠在大图上 —— 宿主 `.media-page` 那对
        `margin-block-start: -4rem` / `padding-block-start: 4rem` 是穿过它顶栏用的、净效果为 0；
      · 海报（8 / 11 / 13rem 三档 + 双层阴影）+ 标题（**≥1024px 横排**、≥1280px 2.25rem）
        + 属性行「N 分钟 | 题材」+ 操作按钮排（窄屏两列网格、≥640px flex 右对齐）；
      · 左「简介 + 来源 chip」/ 右「信息面板」（首行 10 星 VRating 居中，其余行两端对齐 +
        行间分隔线，末行去线）—— **左栏矮太多时自动改单列**：宿主左栏有长简介 + 导演列表，
        能填满信息面板的高度；短剧简介只有一两行，并排会在左栏下方露一大片空白（夹在
        来源链接与演员阵容中间）。所以按内容高度自动选（见脚本 `syncOverviewStack`）：
        够高 ⇒ 照宿主那道并排（完全一致）；不够 ⇒ 单列（简介 → 来源 → 信息面板 →
        演员阵容），信息面板同时拆成多列网格，免得整宽一行被拉到两端相去很远；
      · **演员阵容横滑人物卡**（宿主 `PersonCardSlideView` → `VirtualSlideView` → `PersonCard`
        同款：9rem 的 2:3 卡 + 圆形头像 100px +「演员」+ 姓名 + 角色两行、标题竖条、
        悬停左右翻页圆钮；**卡片上没有悬停浮层 / 动作按钮**，点卡片与宿主一样「钻进
        这位演员」。宿主那 10 张骨架对应的是「详情已到、credits 未到」的中间态 —— 本插件
        详情与演员出自同一份响应，没有那个中间态，所以不留骨架）；
      · **加载链路与宿主逐条对齐**（`loaded` ≡ `isRefreshed`、`failed` ≡ `detailLoadFailed`）：
        请求在 setup 期发出 ⇒ 首帧即 `LoadingBanner`（4 个跳动圆点），期间不摆任何内容；
        请求完 ⇒ 内容；失败 ⇒ `NoDataFound`（500 + 旋转胶卷盘 + 重试，文案照宿主 i18n
        原话「出错啦！」/「无法获取到媒体信息，请检查网络连接。」）；
      · 玻璃 / 透明主题下**隐藏四向渐变层**、大图改**四边遮罩渐隐**并降不透明度
        （`.media-detail-glass / -transparent .vue-media-back-*` 同款）。

    ⚠️ 两处**必须保留的增量**（宿主那一页没有 / 做不到的）：左上角的返回键（宿主靠顶栏与
    浏览器返回，插件面板没有 ⇒ 做成纯图标浮层，不占排版）；标题右侧那排事实行里的
    热度 / 播放量 / 首次发现（宿主模型里根本没有这些字段）。

    ⚠️ **TMDB 身份照实透出**：百科严格匹配到 TMDB 条目时（如「夏星望野」= 百科 30409 /
    TMDB 326627），来源区多一个 TheMovieDb chip、信息面板多一行 `TMDB ID` —— 地址拼法与
    宿主 `getTheMovieDbLink()` 逐字一致。**TMDB 自己的演职员 / 推荐 / 相似 / 分季不搬**：
    那是 TMDB 的条目，点开回不到本插件的数据面（本页所有卡片都指向百科身份）。

    ⚠️ 宿主那些 `.media-*` / `.vue-media-back*` 类名是**它自己 scoped 的**（选择器带
    data-v 属性），联邦模块的元素匹配不上 ⇒ 版式只能复刻、不能复用。样式一律走自有
    `sdas-*` 类名（联邦 CSS 门禁会丢掉任何含 `.v-` 的选择器）。
    宿主**全局**的 `app-hover-lift-card` / `ring-1` / `text-medium-emphasis` 是全局
    工具类（`src/styles/common.scss`），联邦元素能吃到，照用。
  -->
  <div class="sdas-detail" :class="{ 'is-glass': isGlass, 'is-transparent': isTransparent }">
    <!--
      加载态 —— 与宿主详情页**同构**：宿主那一页是 `v-if="!isRefreshed"` ⇒ 详情没请求完之前
      **整页只有 LoadingBanner**（4 个跳动圆点 + `mt-12`），不摆任何内容、不摆骨架。
      这边的 `!loaded` 就是宿主的 `isRefreshed`，语义与时机逐条对齐（请求在 setup 期就发，
      `loaded` 初始 false ⇒ 首帧即圆点，不会先闪一版内容）。
    -->
    <LoadingBanner v-if="!loaded" class="sdas-detail-loading" />

    <!--
      载入失败 —— 对应宿主的 `v-if="detailLoadFailed"`：文案照宿主 i18n 原话
      （`media.error.title` = 「出错啦！」/ `error.networkError` = 「无法获取到媒体信息，
      请检查网络连接。」），请求异常只进控制台、不上界面（宿主也一样）。
    -->
    <NoDataFound
      v-else-if="failed"
      error-code="500"
      error-title="出错啦！"
      error-description="无法获取到媒体信息，请检查网络连接。"
    >
      <template #button>
        <v-btn prepend-icon="mdi-refresh" variant="tonal" @click="load()">重试</v-btn>
      </template>
    </NoDataFound>

    <template v-else>
      <!--
        顶栏大图：宿主 `.vue-media-back` 同款 —— 两层**绝对定位铺满整宽**（脱离内容排版的
        padding），一层放图、一层放四向渐变收底；内容由 `.sdas-detail-page` 叠在它上面。
      -->
      <div v-if="backdropUrl" class="sdas-detail-back sdas-detail-back-image" aria-hidden="true">
        <v-img class="sdas-detail-back-img" position="top" :src="proxyImage(backdropUrl)" cover />
      </div>
      <div v-if="backdropUrl" class="sdas-detail-back sdas-detail-back-overlay" aria-hidden="true" />

      <div ref="pageRoot" class="sdas-detail-page">
        <!-- 返回键见 `StickyBack`（teleport 到 body 才钉得住）；这里只留未识别提示 -->
        <div v-if="missing" class="sdas-detail-note">
          未识别到媒体信息，下面是作品卡上的信息
        </div>

        <!-- 头部：海报 + 标题 + 属性 + 操作按钮排 -->
        <div class="sdas-detail-header">
          <div class="sdas-detail-poster">
            <v-img
              v-if="view.poster"
              :src="proxyImage(view.poster)"
              cover
              :aspect-ratio="2 / 3"
              class="ring-1 ring-gray-500"
            >
              <template #placeholder>
                <v-skeleton-loader class="sdas-detail-poster-skeleton" />
              </template>
            </v-img>
            <div v-else class="sdas-detail-poster-empty d-flex align-center justify-center">
              <v-icon size="40" color="medium-emphasis">mdi-movie-open-outline</v-icon>
            </div>
          </div>

          <div class="sdas-detail-title">
            <div v-if="inLibrary || view.is_new || view.kind" class="sdas-detail-status">
              <!-- 宿主那枚「已入库」胶囊（green-500/80 + green-500 描边 + green-100 字） -->
              <span v-if="inLibrary" class="sdas-status-pill is-library">已入库</span>
              <span v-if="view.is_new" class="sdas-status-pill is-new">新作品</span>
              <span v-if="view.kind" class="sdas-status-pill is-kind">{{ view.kind }}</span>
            </div>
            <h1 class="sdas-detail-h1">
              <span class="sdas-detail-h1-text">{{ view.title }}</span>
              <span v-if="view.year" class="sdas-detail-year">（{{ view.year }}）</span>
            </h1>
            <span class="sdas-detail-attributes">
              <template v-if="view.episode_minutes">
                {{ view.episode_minutes }} 分钟
              </template>
              <span v-if="view.episode_minutes && view.genres.length" class="mx-1">|</span>
              <!--
                分类可点（2026-10-18 用户口径）：点一下回到卡片墙、按这一类筛选。
                分隔符 ` / ` 由 CSS 的 `::before` 画，条目本体是一枚无底色按钮。
              -->
              <span class="sdas-detail-genres">
                <button
                  v-for="genre in view.genres"
                  :key="genre"
                  type="button"
                  class="sdas-detail-genre"
                  :title="`只看「${genre}」的作品`"
                  @click="emit('filter-genre', genre)"
                >
                  {{ genre }}
                </button>
              </span>
            </span>
          </div>

          <div class="sdas-detail-actions">
            <!-- 与系统详情页同一套：搜索资源 tonal/info、订阅 tonal/warning|error -->
            <v-btn
              class="sdas-detail-action-btn"
              variant="tonal"
              color="info"
              prepend-icon="mdi-magnify"
              @click="emit('search', work)"
            >
              搜索资源
            </v-btn>
            <v-btn
              class="sdas-detail-action-btn"
              variant="tonal"
              :color="subscribed ? 'error' : 'warning'"
              :loading="subscribing"
              :prepend-icon="subscribed ? 'mdi-heart' : 'mdi-heart-outline'"
              :title="subscribed ? '再次点击取消订阅' : '订阅这部剧'"
              @click="emitSubscribe()"
            >
              {{ subscribed ? '已订阅' : '订阅' }}
            </v-btn>
            <!--
              订阅设置（2026-10-22 用户口径）：已订阅的作品给一枚按钮，点开弹窗
              配置 —— 暂停 / 恢复自动搜索、立即搜索一次、看上次搜索结果。
              仅插件自建订阅（引擎 = self）可编辑；宿主订阅请到订阅页管理。
            -->
            <v-btn
              v-if="subscribed"
              class="sdas-detail-action-btn"
              variant="tonal"
              color="grey"
              prepend-icon="mdi-tune"
              title="订阅设置：自动搜索开关、立即搜索"
              @click="subsetOpen = true"
            >
              订阅设置
            </v-btn>
            <!-- 在线播放：系统那枚按钮只在媒体服务器里存在该条目时出现（tonal + mdi-play） -->
            <v-btn
              v-if="inLibrary"
              class="sdas-detail-action-btn"
              variant="tonal"
              :loading="playing"
              prepend-icon="mdi-play"
              @click="playWork()"
            >
              在线播放
            </v-btn>
          </div>
        </div>

        <!--
          左：简介 + 来源；右：信息面板。
          左侧内容明显矮于信息面板时加 `is-stacked` 改单列（宿主那一页的 TMDB 影视简介
          有好几段、还带导演列表，能填满；短剧简介只有一两行，并排会让左栏下方空出一大片，
          正好落在来源链接与演员阵容中间）。判定见脚本里的 `syncOverviewStack`。
        -->
        <div class="sdas-detail-overview" :class="{ 'is-stacked': overviewStacked }">
          <div ref="overviewLeft" class="sdas-detail-overview-left">
            <h2 v-if="view.overview" class="sdas-detail-h2">简介</h2>
            <p v-if="view.overview" class="sdas-detail-text">{{ view.overview }}</p>
            <p v-else class="sdas-detail-text is-dim">百科还没有这部作品的简介。</p>

            <!-- 来源链接 chip（宿主那排 link chip 同款：gray-600 底 + gray-500 描边） -->
            <div class="sdas-detail-links">
              <a v-if="view.url" class="sdas-link-chip" :href="view.url" target="_blank" rel="noopener">
                <v-icon size="16">mdi-link</v-icon>
                <span class="ms-1">短剧百科</span>
              </a>
              <!-- 豆瓣条目 chip：短剧在豆瓣的覆盖率比 TMDB 高，通常这一个才出现 -->
              <a
                v-if="view.douban_url"
                class="sdas-link-chip"
                :href="view.douban_url"
                target="_blank"
                rel="noopener"
                title="在豆瓣打开"
              >
                <v-icon size="16">mdi-link</v-icon>
                <span class="ms-1">豆瓣</span>
              </a>
              <!-- 宿主同款：有 TMDB 身份时给一个 TheMovieDb chip（地址拼法与它逐字一致） -->
              <a
                v-if="view.tmdb_url"
                class="sdas-link-chip"
                :href="view.tmdb_url"
                target="_blank"
                rel="noopener"
                title="在 TheMovieDb 打开"
              >
                <v-icon size="16">mdi-link</v-icon>
                <span class="ms-1">TheMovieDb</span>
              </a>
            </div>
          </div>

          <!-- 信息面板：宿主 .media-facts 同款（首行 10 星评分居中，其余两端对齐 + 分隔线） -->
          <div ref="overviewRight" class="sdas-detail-overview-right">
            <div class="sdas-facts">
              <div v-if="view.vote > 0" class="sdas-ratings">
                <v-rating
                  :model-value="view.vote"
                  :length="10"
                  density="compact"
                  readonly
                  class="ma-2"
                />
              </div>
              <div
                v-for="(fact, index) in facts"
                :key="fact.label"
                class="sdas-fact"
                :class="{ 'is-last': index === facts.length - 1 }"
              >
                <span>{{ fact.label }}</span>
                <span class="sdas-fact-value">
                  <span class="sdas-fact-inner">
                    <!-- 上映日期那一行的云朵图标（宿主原样） -->
                    <svg
                      v-if="fact.icon"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke-width="1.5"
                      stroke="currentColor"
                      aria-hidden="true"
                      class="sdas-fact-icon"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z"
                      />
                    </svg>
                    <button
                      v-if="fact.internal"
                      type="button"
                      class="sdas-fact-link"
                      :class="{ 'ms-1': fact.icon }"
                      :title="`查看原著《${fact.value}》`"
                      @click="openAdapted()"
                    >{{ fact.value }}</button>
                    <a
                      v-else-if="fact.url"
                      class="sdas-fact-link"
                      :class="{ 'ms-1': fact.icon }"
                      :href="fact.url"
                      target="_blank"
                      rel="noopener"
                      :title="`在短剧百科打开：${fact.value}`"
                    >{{ fact.value }}</a>
                    <span v-else :class="{ 'ms-1': fact.icon }" :title="fact.value">{{ fact.value }}</span>
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!--
          演职员阵容：宿主这一块是「横滑人物卡」，本插件**改用与已关注演员同一张卡**
          （`ActorCard`：整卡照片、姓名常显、悬停出信息，右上角爱心可关注）。
          顺序是**导演 → 编剧 → 演员**（用户口径「导演编剧移到演员阵容、优先显示」）：
          这三拨都来自同一份数据 —— 演员来自 `MediaInfo.actors`（带角色名），
          导演 / 编剧来自数据源原始记录的 `people[]`（带 `daoyan:` / `bianju:` 身份与头像），
          所以都能点开各自的人物档案页。滑块仍沿用宿主 `.slider-*` 那套横滑 + 翻页钮。

          2026-10-19 用户口径：**演职员排在豆瓣短评 / 影评之前**（先看人，再看评价）。
        -->
        <div v-if="castRows.length" class="sdas-slider">
          <div class="sdas-slider-header">
            <div class="sdas-slider-title-section">
              <div class="sdas-slider-badge" />
              <h3 class="sdas-slider-title">演职员</h3>
            </div>
          </div>

          <div class="sdas-slider-wrapper">
            <div
              ref="castRail"
              class="sdas-slider-content"
              tabindex="0"
              @scroll.passive="onCastScroll"
            >
              <!--
                演员卡与**已关注演员卡**同一张（2026-10-18 用户口径）：整卡就是照片、
                姓名 + 角色常显、右上角爱心（悬停淡入）。导演 / 编剧排在演员之前，
                他们的卡上第二行是「导演」「编剧」。
              -->
              <div
                v-for="row in castRows"
                :key="castKey(row)"
                class="sdas-slide-item"
              >
                <ActorCard
                  :item="row"
                  :role="row.role"
                  :added="isFollowed(row)"
                  :busy="isBusy(row)"
                  :loaded="loadedCast.has(castKey(row))"
                  @open="openActor(row)"
                  @poster="markCastLoaded(row)"
                  @toggle="emit('toggle-actor', row)"
                />
              </div>
            </div>

            <!-- 左右翻页圆钮（宿主的 nav-button 同款：滚动中或悬停时淡入，触摸端不显示） -->
            <v-btn
              v-show="castNavState !== 0 && castNavState !== 3"
              class="sdas-slider-nav is-left"
              variant="tonal"
              icon
              @click.stop="slideCast(false)"
            >
              <v-icon class="sdas-nav-icon">mdi-chevron-left</v-icon>
            </v-btn>
            <v-btn
              v-show="castNavState !== 2 && castNavState !== 3"
              class="sdas-slider-nav is-right"
              variant="tonal"
              icon
              @click.stop="slideCast(true)"
            >
              <v-icon class="sdas-nav-icon">mdi-chevron-right</v-icon>
            </v-btn>
          </div>
        </div>

        <!--
          豆瓣影评 / 短评（2026-10-18）：系统详情页那两块就是靠 `douban_id` 从宿主
          `/api/v1/douban/*` 取的，这里用**同一批接口、同一份数据**。
          没有豆瓣身份（大多数短剧没有）就整块不渲染；接口失败静默（豆瓣限流是常事）。
        -->
        <!--
          豆瓣短评 / 影评（2026-10-18）：照系统那一页（`MediaCommentView.vue`）复刻 ——
          顶部两个标签（短评 / 影评，带条数）→ 紧凑列表：32px 头像 + 作者 + 五星 +
          正文 / 摘要 + 时间与「有用」数；滚到底「加载更多」。
          数据来自宿主同一批接口（`douban/interests|reviews`），只在有 `douban_id` 时有内容。
        -->
        <div v-if="hasDouban" class="sdas-douban">
          <!--
            两个标签：点击用**容器委托**（`data-douban-tab` + closest）。
            直接在 button 上绑 `@click` 时标签文字那一段常点不动（命中区只覆盖到
            文字所在的那一小块基线），用户反馈「只有数字能点」；改成整块热区后
            文字、条数、左右留白都算同一个靶子。
          -->
          <div class="sdas-douban-tabs" @click="onDoubanTabsClick">
            <button
              type="button"
              class="sdas-douban-tab"
              :class="{ 'is-active': doubanTab === 'interests' }"
              data-douban-tab="interests"
            >
              短评
              <span v-if="doubanTotals.interests" class="sdas-douban-count">
                {{ doubanTotals.interests }}
              </span>
            </button>
            <button
              type="button"
              class="sdas-douban-tab"
              :class="{ 'is-active': doubanTab === 'reviews' }"
              data-douban-tab="reviews"
            >
              影评
              <span v-if="doubanTotals.reviews" class="sdas-douban-count">
                {{ doubanTotals.reviews }}
              </span>
            </button>
          </div>

          <!-- 短评 -->
          <ul v-if="doubanTab === 'interests' && doubanComments.length" class="sdas-douban-list">
            <li v-for="comment in doubanComments" :key="`dc:${comment.id}`" class="sdas-douban-item">
              <div class="sdas-douban-avatar">
                <img v-if="comment.avatar" :src="comment.avatar" alt="" loading="lazy" />
                <span v-else>{{ (comment.author || '?').slice(0, 1) }}</span>
              </div>
              <div class="sdas-douban-body">
                <div class="sdas-douban-author">
                  <span>{{ comment.author }}</span>
                  <v-rating
                    v-if="comment.rating"
                    :model-value="comment.rating"
                    :length="5"
                    density="compact"
                    readonly
                    size="x-small"
                    class="ms-2"
                  />
                </div>
                <div class="sdas-douban-text">{{ comment.comment }}</div>
                <div class="sdas-douban-meta">
                  <span v-if="comment.time">{{ comment.time }}</span>
                  <span v-if="comment.votes">有用 {{ comment.votes }}</span>
                </div>
              </div>
            </li>
          </ul>

          <!-- 影评 -->
          <ul v-else-if="doubanTab === 'reviews' && doubanReviews.length" class="sdas-douban-list">
            <li v-for="review in doubanReviews" :key="`dr:${review.id}`" class="sdas-douban-item">
              <div class="sdas-douban-avatar">
                <img v-if="review.avatar" :src="review.avatar" alt="" loading="lazy" />
                <span v-else>{{ (review.author || '?').slice(0, 1) }}</span>
              </div>
              <div class="sdas-douban-body">
                <button
                  type="button"
                  class="sdas-douban-review-title"
                  :title="review.url ? '在豆瓣打开这篇影评' : review.title"
                  @click="openUrl(review.url)"
                >
                  {{ review.title }}
                </button>
                <div v-if="review.abstract" class="sdas-douban-text">{{ review.abstract }}</div>
                <div class="sdas-douban-meta">
                  <span v-if="review.author">{{ review.author }}</span>
                  <span v-if="review.time">{{ review.time }}</span>
                  <span v-if="review.useful">有用 {{ review.useful }}</span>
                </div>
              </div>
            </li>
          </ul>

          <div class="sdas-douban-foot">
            <v-progress-circular v-if="doubanLoading" indeterminate size="20" width="2" />
            <v-btn
              v-else-if="doubanHasMore"
              variant="text"
              size="small"
              @click="loadMoreDouban()"
            >
              加载更多
            </v-btn>
            <span v-else-if="doubanLoaded && !doubanRows.length" class="sdas-douban-empty">
              没有数据
            </span>
          </div>
        </div>
      </div>
    </template>

    <v-snackbar v-model="snackbar" :timeout="3200" location="bottom">
      {{ snackbarText }}
    </v-snackbar>

    <!--
      订阅设置弹窗：操作按钮排「订阅设置」点开。两行配置（自动搜索开关 /
      立即搜索）+ 一行上次处理结果；不可编辑（宿主订阅）时给指引文案。
    -->
    <v-dialog
      v-model="subsetOpen"
      max-width="470"
      :scrim="true"
      transition="dialog-bottom-transition"
    >
      <v-card v-if="subscription">
        <v-card-title class="d-flex align-center gap-2">
          <v-icon size="18" color="error">mdi-heart</v-icon>
          <span class="text-subtitle-1 font-weight-bold">订阅设置</span>
          <v-spacer />
          <v-chip
            v-if="stateMeta"
            :color="stateMeta.color"
            variant="tonal"
            size="x-small"
            :title="subscription.sub_detail || stateMeta.label"
          >
            <v-icon size="12" class="mr-1">{{ stateMeta.icon }}</v-icon>
            {{ stateMeta.label }}
          </v-chip>
        </v-card-title>
        <v-divider />
        <v-card-text class="sdas-subset-body">
          <!-- 订阅级落点：站点 / 下载器 / 目录，留空即用配置页默认（2026-10-22 用户口径） -->
          <div v-if="subEditable" class="sdas-subset-row">
            <div class="sdas-subset-cell">
              <div class="sdas-subset-label">订阅站点</div>
              <div class="sdas-subset-hint">{{ subSitesHint }}</div>
            </div>
            <v-select
              :model-value="localSites"
              :items="siteOptions"
              item-title="name"
              item-value="id"
              :loading="optionsLoading"
              multiple
              chips
              closable-chips
              clearable
              density="compact"
              hide-details
              variant="outlined"
              class="sdas-subset-input"
              :disabled="savingTargets"
              @update:model-value="onSitesChange"
            />
          </div>

          <div v-if="subEditable" class="sdas-subset-row">
            <div class="sdas-subset-cell">
              <div class="sdas-subset-label">下载器</div>
              <div class="sdas-subset-hint">{{ subDownloaderHint }}</div>
            </div>
            <v-select
              :model-value="localDownloader"
              :items="downloaderOptions"
              item-title="title"
              item-value="value"
              :loading="optionsLoading"
              density="compact"
              hide-details
              variant="outlined"
              class="sdas-subset-input"
              :disabled="savingTargets"
              @update:model-value="onDownloaderChange"
            />
          </div>

          <div v-if="subEditable" class="sdas-subset-row">
            <div class="sdas-subset-cell">
              <div class="sdas-subset-label">保存目录</div>
              <div class="sdas-subset-hint">{{ subSavePathHint }}</div>
            </div>
            <v-select
              :model-value="localSavePath"
              :items="pathOptions"
              item-title="title"
              item-value="value"
              density="compact"
              hide-details
              variant="outlined"
              class="sdas-subset-input"
              :disabled="savingTargets || optionsLoading"
              @update:model-value="onSavePathChange"
            />
          </div>

          <!-- 台账里的种子页面：只给一枚按钮 + 一行种子标题 -->
          <div v-if="subscription.torrent_url" class="sdas-subset-row">
            <div class="sdas-subset-cell">
              <div class="sdas-subset-label">种子</div>
              <div class="sdas-subset-hint sdas-subset-torrent" :title="subscription.torrent_title">
                {{ subscription.torrent_title || '已提交的种子' }}
              </div>
            </div>
            <v-btn
              :href="subscription.torrent_url"
              target="_blank"
              rel="noopener"
              variant="tonal"
              color="info"
              size="small"
              prepend-icon="mdi-open-in-new"
            >
              种子页面
            </v-btn>
          </div>

          <div v-if="subEditable && targetsDirty" class="sdas-subset-row">
            <div class="sdas-subset-cell">
              <div class="sdas-subset-label">保存上面三项</div>
              <div class="sdas-subset-hint">留空的项按配置页的默认值走</div>
            </div>
            <v-btn
              variant="flat"
              color="error"
              size="small"
              prepend-icon="mdi-content-save-outline"
              :loading="savingTargets"
              @click="saveTargets()"
            >
              保存
            </v-btn>
          </div>

          <div v-if="subEditable" class="sdas-subset-row">
            <div class="sdas-subset-cell">
              <div class="sdas-subset-label">立即搜索一次</div>
              <div class="sdas-subset-hint">不等下一轮定时，现在就搜（冷却也一并清掉）</div>
            </div>
            <v-btn
              variant="tonal"
              color="info"
              size="small"
              prepend-icon="mdi-magnify"
              :loading="searchingNow"
              @click="searchNow()"
            >
              立即搜索
            </v-btn>
          </div>

          <div v-if="subscription.sub_detail" class="sdas-subset-note">
            上次处理：{{ subscription.sub_detail }}
            <template v-if="subscription.sub_time">（{{ subscription.sub_time }}）</template>
          </div>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="subsetOpen = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 返回键：钉在视口（宿主面板带 transform + overflow:hidden，sticky 与面板内 fixed 都无效） -->
    <StickyBack :anchor="pageRoot" title="返回" @back="emit('back')" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import LoadingBanner from './LoadingBanner.vue'
import NoDataFound from './NoDataFound.vue'
import ActorCard from './ActorCard.vue'
import StickyBack from './StickyBack.vue'

/** 页面根节点：返回键（`StickyBack`）按它的左上角定位到视口 */
const pageRoot = ref<HTMLElement | null>(null)
import {
  fetchDoubanComments,
  fetchDoubanReviews,
  fetchDownloaderOptions,
  fetchDownloadPaths,
  fetchPlayUrl,
  fetchSearchSites,
  fetchSubscriptions,
  fetchWorkDetail,
  fetchWorkSource,
  pluginSubscribeSearchNow,
  pluginSubscribeUpdate,
  proxyImage,
} from './api'
import type {
  AdaptedInfo,
  DoubanComment,
  DoubanReview,
  WorkSourceRecord,
} from './api'
import type {
  ActorCandidate,
  DownloadClientOption,
  DownloadPathOption,
  PluginApi,
  WorkDetailActor,
  WorkDetailPayload,
  WorkItem,
} from './types'
import type { HostSite } from './api'

/** 作品详情页（作品卡点开进入；返回按钮由父组件负责恢复来源页） */
const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 点开的那张卡片（`fromWork` 的类型兜底与「百科没收录」时的垫底数据） */
  work: WorkItem
  /** 宿主订阅里是否有这部剧（按钮状态） */
  subscribed: boolean
  /** 订阅请求进行中（按钮转圈，防止连点） */
  subscribing?: boolean
  /**
   * 这部剧的订阅行（「已订阅」页 / 订阅端点的同一份数据）：订阅设置块的数据源。
   * 没订阅（或订阅清单还没回来）就是 null，整块不渲染。
   */
  subscription?: {
    sub_state?: string
    sub_detail?: string
    sub_time?: string
    /** 台账记下的种子页面 / 种子标题（下载成功才有） */
    torrent_url?: string
    torrent_title?: string
    /** 订阅级落点覆写（空 = 用配置页默认） */
    sites?: string
    downloader?: string
    save_path?: string
  } | null
  /** 订阅设置可编辑？（引擎 = self 的订阅归插件管；宿主订阅只能去订阅页） */
  subEditable?: boolean
  /**
   * 已在关注列表的**演员身份**集合（`yanyuan:<id>`）。
   *
   * 演职员卡上的爱心要能反映真实状态（与演员墙同一张卡、同一套交互），
   * 所以父组件把关注列表的 id 给它；不传就是全空心。
   */
  followedIds?: Set<string>
  /** 关注 / 取消关注请求进行中的演员身份（卡片上的爱心转圈） */
  busyIds?: Set<string>
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'search', work: WorkItem): void
  (e: 'subscribe', work: WorkItem): void
  /**
   * 点了演员阵容里的卡片：父组件据此打开**演员作品页**（`ActorDetail.vue`）。
   *
   * 与宿主同一套行为 —— 宿主 `PersonCard` 点开的是它的人物详情页（`/person?personid=…`），
   * 本插件的对应物就是演员作品页。
   */
  (e: 'open-actor', actor: ActorCandidate): void
  /** 点了演职员卡上的爱心：父组件负责关注 / 取消关注（与演员墙同一套后端） */
  (e: 'toggle-actor', actor: ActorCandidate): void
  /** 点了「改编自」：父组件切到**原著详情页**（`AdaptedDetail.vue`） */
  (e: 'open-adapted', novel: AdaptedInfo): void
  /** 点了标题行里的分类：父组件回卡片墙并按这一类筛选 */
  (e: 'filter-genre', genre: string): void
  /** 订阅设置里改了什么（暂停 / 恢复 / 立即搜索）：父组件刷新订阅清单 */
  (e: 'sub-updated'): void
}>()

/**
 * 宿主主题名（`glass` / `transparent` / 其它）。
 *
 * 宿主详情页在**玻璃 / 透明**主题下会换一套背景处理（`.media-detail-glass .vue-media-back-*`）：
 * 隐藏四向渐变层、把大图换成四边遮罩渐隐、并轻微下调不透明度。这里照它对齐 ——
 * 主题变量挂在 `html[data-theme=…]`（可继承），所以直接读 `documentElement` 即可，
 * 不用去拿 Vuetify 实例。
 */
const themeName = ref('')
let themeObserver: MutationObserver | null = null

function syncTheme(): void {
  themeName.value = typeof document === 'undefined' ? '' : document.documentElement.dataset.theme || ''
}

const isGlass = computed(() => themeName.value === 'glass')
const isTransparent = computed(() => themeName.value === 'transparent')

const detail = ref<WorkDetailPayload | null>(null)
/**
 * 详情是否已请求完毕 —— **对齐宿主的 `isRefreshed`**。
 *
 * false 期间整页只有加载圆点（宿主 `v-if="!isRefreshed"` 就是这个时序）；
 * 请求在 setup 期由下面那个 `watch(..., { immediate: true })` 发出 ⇒ 首帧即 false，
 * 与宿主 `onBeforeMount` 一样是「进去先圆点」，不会先闪一版内容。
 */
const loaded = ref(false)
/**
 * 详情请求是否失败 —— **对齐宿主的 `detailLoadFailed`**。
 *
 * 失败时整块换成 NoDataFound（500 + 固定文案 + 重试），请求异常只进控制台。
 */
const failed = ref(false)
/** 头像已加载完的演员（加载完才画 1px 描边，与宿主的 PersonCard 同一口径） */
const loadedCast = ref<Set<string>>(new Set())

/**
 * 作品卡 → 详情载荷的投影。
 *
 * ⚠️ 它不是「加载中的占位」：加载中整页只有圆点（见模板 `v-if="!loaded"`），内容区
 * 压根不渲染。它只在两处起作用 —— ① 类型兜底（让 `view` 恒不为空，`detail` 为 null 时
 * 也能安全取字段）；② 后端返回 `found=false` 的空壳时，把卡片上现成的海报 / 标题 /
 * 年份 / 题材 / 评分 / 热度垫进去（百科没收录这部剧时页面至少不空）。
 */
function fromWork(work: WorkItem): WorkDetailPayload {
  return {
    found: true,
    media_source: work.media_source,
    media_id: work.media_id,
    title: work.title,
    year: work.year,
    type: work.type,
    overview: work.overview || '',
    poster: work.poster,
    backdrop: '',
    vote: Number(work.vote || 0),
    release_date: work.release_date || '',
    episode_count: Number(work.episode_count || 0),
    episode_minutes: 0,
    duration_minutes: 0,
    genres: work.genres || [],
    studio: work.studio || '',
    // 播放平台：墙上那一行目前恒空（作品卡不带平台），保留字段只为结构完整
    platform: work.platform || '',
    status: '',
    language: '',
    url: work.url || '',
    // 作品卡那一行没有 TMDB 身份（百科的卡片投影里没这个字段）—— 只有详情回来了才有
    tmdb_id: 0,
    tmdb_url: '',
    actors: [],
    kind: work.kind || '',
    first_seen: work.first_seen || '',
    is_new: Boolean(work.is_new),
    in_library: typeof work.in_library === 'boolean' ? work.in_library : null,
  }
}

/**
 * 页面呈现的数据：命中就用详情；**没命中（百科没有这部剧）用作品卡垫底**。
 *
 * 后端 `found=false` 的空壳只带 ID / 片名 / 年份，海报、评分、题材、热度这些全在作品卡那
 * 一行上 ⇒ 直接用空壳会把那一页铺空（只留一个标题）。垫上卡片数据才真的「不留白」。
 */
const view = computed<WorkDetailPayload>(() =>
  detail.value?.found ? detail.value : fromWork(props.work),
)

/** 百科里没这部剧（详情回来了但 found=false） */
const missing = computed(() => Boolean(detail.value) && detail.value?.found === false)

const backdropUrl = computed(() => view.value.backdrop || view.value.poster || '')
const inLibrary = computed(() => view.value.in_library === true)

/**
 * 演职员阵容的一行：与**演员候选同构**（同一张 `ActorCard` 渲染），
 * 多一个 `role` —— 演员是「饰 陈天极」，导演 / 编剧是自己的职务。
 */
interface CastRow extends ActorCandidate {
  role?: string
}

/**
 * 数据源**原始记录**（导演 / 编剧 + 站点独有字段）。
 *
 * `MediaInfo` 装不下站点的那几个字段（状态 / 全片时长 / 播放量 / 收藏 / 热度 /
 * 出品方 / 平台 / 改编自），导演与编剧也只在原始记录的 `people[]` 里 —— 所以单独
 * 取一份（数据源公开端点，详情缓存命中）。拿不到就是 `null`，页面退回 `MediaInfo` 那份。
 */
const source = ref<WorkSourceRecord | null>(null)

/**
 * 豆瓣短评 / 影评 —— 与系统那一页（`MediaCommentView.vue`）同一套：
 * 两个标签（短评 / 影评，各带条数）+ `start/count` 分页 + 「加载更多」。
 */
const doubanTab = ref<'interests' | 'reviews'>('interests')
const doubanComments = ref<DoubanComment[]>([])
const doubanReviews = ref<DoubanReview[]>([])
const doubanTotals = reactive({ interests: 0, reviews: 0 })
const doubanLoading = ref(false)
const doubanLoaded = ref(false)
const DOUBAN_PAGE = 10

/** 这部作品有没有豆瓣身份（没有就整块不渲染） */
const hasDouban = computed(() => Boolean(view.value?.douban_id))

/** 当前标签已加载的行（判断「还有没有下一页」「空不空」都用它） */
const doubanRows = computed<{ id: string }[]>(() =>
  doubanTab.value === 'interests' ? doubanComments.value : doubanReviews.value,
)

/** 当前标签是否还有下一页 */
const doubanHasMore = computed(() => {
  const total =
    doubanTab.value === 'interests' ? doubanTotals.interests : doubanTotals.reviews
  return total > doubanRows.value.length
})

/**
 * 演职员阵容：**导演 → 编剧 → 演员**（2026-10-18 用户口径「导演编剧移到演员阵容、
 * 优先显示」）。三拨都按身份去重（同一人兼任导演与编剧时只出一张卡）。
 */
const castRows = computed<CastRow[]>(() => {
  const rows: CastRow[] = []
  const seen = new Set<string>()
  const add = (row: CastRow): void => {
    const key = String(row.actor_id || row.name || '')
    if (!key || seen.has(key)) return
    seen.add(key)
    rows.push(row)
  }
  const src = source.value
  for (const person of src?.director || []) {
    add({
      name: person.name,
      actor_id: person.media_id,
      media_id: person.media_id || undefined,
      exact: true,
      profile: person.profile || undefined,
      role: '导演',
    })
  }
  for (const person of src?.writer || []) {
    add({
      name: person.name,
      actor_id: person.media_id,
      media_id: person.media_id || undefined,
      exact: true,
      profile: person.profile || undefined,
      role: '编剧',
    })
  }
  const actors: WorkDetailActor[] = view.value.actors || []
  const castSource = actors.length
    ? actors.map((actor) => ({
        name: actor.name,
        actor_id: actor.actor_id,
        profile: actor.profile,
        character: actor.character,
        subscribed: actor.subscribed,
      }))
    : (src?.cast || []).map((person) => ({
        name: person.name,
        actor_id: person.media_id,
        profile: person.profile,
        character: person.role,
        subscribed: false,
      }))
  if (!castSource.length) return rows
  for (const actor of castSource) {
    add({
      name: actor.name,
      actor_id: actor.actor_id,
      media_id: actor.actor_id || undefined,
      exact: true,
      profile: actor.profile || undefined,
      subscribed: actor.subscribed,
      role: actor.character ? `饰 ${actor.character}` : '',
    })
  }
  return rows
})

const castKey = (row: { actor_id?: string; name: string }): string => row.actor_id || row.name

/** 这张演职员卡上的人是否已关注（爱心实心 / 空心） */
function isFollowed(row: CastRow): boolean {
  return Boolean(row.actor_id && props.followedIds?.has(row.actor_id))
}

/** 这张演职员卡上的关注请求是否在飞（爱心转圈） */
function isBusy(row: CastRow): boolean {
  return Boolean(row.actor_id && props.busyIds?.has(row.actor_id))
}

function markCastLoaded(row: CastRow): void {
  if (loadedCast.value.has(castKey(row))) return
  const next = new Set(loadedCast.value)
  next.add(castKey(row))
  loadedCast.value = next
}

/** 热度 / 播放量：站点给的是原始大数，按中文习惯折成「万 / 亿」 */
function formatCount(value: number): string {
  const count = Number(value || 0)
  if (!count) return ''
  if (count >= 100000000) return `${(count / 100000000).toFixed(1)} 亿`
  if (count >= 10000) return `${(count / 10000).toFixed(1)} 万`
  return String(Math.round(count))
}

/**
 * 信息面板的行（宿主 `.media-facts` 同款；标签沿用宿主的 i18n 文案）。
 * 空值一律不渲染那一行 —— 短剧的字段缺失很常见，摆一排「—」没有信息量。
 * `ID` 是百科的作品 ID，宿主那一行排第二，位置照搬。
 *
 * `TMDB ID` 紧随其后：宿主那一行**就是** TMDB ID（它的 `ID` 行读 `tmdb_id`），
 * 但本插件的主身份是百科，所以两行分开标清楚 —— 百科有 TMDB 身份时才多出这一行
 * （百科插件按片名 + 首播年严格匹配过才给，见 `tmdb.py`）。
 */
const facts = computed<
  { label: string; value: string; icon?: boolean; url?: string; internal?: boolean }[]
>(() => {
  const data = view.value
  type FactRow = { label: string; value: string; icon?: boolean; url?: string; internal?: boolean }
  const rows: FactRow[] = []
  const push = (
    label: string,
    value: string,
    icon = false,
    url = '',
    internal = false,
  ): void => {
    if (value) rows.push({ label, value, icon, url, internal })
  }
  // 站点原始记录优先补齐 MediaInfo 空着的那些（状态 / 全片时长 / 播放量 / 出品方…）
  const src = source.value
  push('ID', data.media_id)
  push('TMDB ID', data.tmdb_id ? String(data.tmdb_id) : '')
  push('豆瓣 ID', data.douban_id || '')
  push('状态', data.status || src?.status || '')
  push('上映日期', data.release_date, true)
  push('集数', data.episode_count ? `${data.episode_count} 集` : '')
  push('单集时长', data.episode_minutes ? `${data.episode_minutes} 分钟` : '')
  // 全集时长：MediaInfo 常常是 0（站点只印「2小时23分钟」这种原文）⇒ 用原始记录的分钟数 / 原文
  push(
    '全集时长',
    data.duration_minutes
      ? `${data.duration_minutes} 分钟`
      : src?.duration_minutes
        ? `${src.duration_minutes} 分钟`
        : src?.duration_text || '',
  )
  push('原始语言', data.language)
  push('制作公司', data.studio || src?.studio || '')
  // 播放平台：后端详情投影已从 MediaInfo 的 networks 收敛成 data.platform，
  // 数据源原始记录（src）里也有一份 —— 两处任一有值即可，都空则不显示这一行
  push('播出平台', data.platform || src?.platform || '')
  // 只显示站点原文（「380.14万」/「1016万」/「8.86万」）—— 不折算、不兜底数字；
  // 站点没写这一项就是空串，push 会自动跳过该行
  push('热度', src?.heat_text || '')
  push('播放量', src?.play_count_text || '')
  push('收藏', src?.favorites_text || '')
  // 改编自：站点给的是 { title, author, kind }；只写得出名字时不带作者
  // 改编自：有原著数据就进**站内原著详情页**（零额外请求）；没有才退回百科页链接
  push(
    '改编自',
    src?.adapted_title
      ? src.adapted_author
        ? `《${src.adapted_title}》 / ${src.adapted_author}`
        : `《${src.adapted_title}》`
      : '',
    false,
    src?.adapted ? '' : src?.adapted_url || '',
    Boolean(src?.adapted),
  )
  push('首次发现', data.first_seen)
  return rows
})

/**
 * 点「订阅」：把**详情页拿到的集数**一并交出去。
 *
 * 宿主创建电视剧订阅时必须有季集信息（`total_episode`），而卡片上那个数字常常是 0
 * （搜索/剧目目录来的行没带集数）—— 详情页刚从百科拿到的 `episode_count` 才是准的。
 */
function emitSubscribe(): void {
  emit('subscribe', {
    ...props.work,
    episode_count: Number(view.value?.episode_count || props.work.episode_count || 0),
  })
}

// ── 订阅设置（已订阅的作品：暂停 / 恢复自动搜索、立即搜索一次） ──

/** 订阅设置弹窗的开关（操作按钮排「订阅设置」按钮点开） */
const subsetOpen = ref(false)

/** 订阅搜索状态 → 展示（与卡片角标同一套语义；色值用 v-chip 的主题色） */
const SUB_STATE_META: Record<string, { label: string; color: string; icon: string }> = {
  downloaded: { label: '已提交下载', color: 'green', icon: 'mdi-check-circle-outline' },
  history: { label: '下载历史已有', color: 'teal', icon: 'mdi-content-duplicate' },
  in_library: { label: '已在媒体库', color: 'teal', icon: 'mdi-library-outline' },
  noresult: { label: '暂无资源', color: 'grey', icon: 'mdi-magnify-close' },
  failed: { label: '搜索失败', color: 'red', icon: 'mdi-alert-circle-outline' },
}

const stateMeta = computed(
  () => SUB_STATE_META[String(props.subscription?.sub_state || '')] || null,
)

/** 「立即搜索一次」请求中（按钮转圈） */
const searchingNow = ref(false)

async function searchNow(): Promise<void> {
  if (searchingNow.value) return
  searchingNow.value = true
  try {
    const res = await pluginSubscribeSearchNow({ api: props.api }, props.work.media_id)
    toast(String(res?.message || '已开始搜索，结果稍后回填'))
    emit('sub-updated')
    // 后台在跑，过一会儿把订阅行刷回来 —— 状态 chip 就能跟上
    setTimeout(() => emit('sub-updated'), 8000)
    setTimeout(() => emit('sub-updated'), 20000)
  } catch (err) {
    toast(`搜索失败：${err instanceof Error ? err.message : err}`)
  } finally {
    searchingNow.value = false
  }
}

// ── 订阅级落点：站点 / 下载器 / 保存目录（留空 = 用配置页默认） ──

/**
 * 可选项全部走**宿主已有接口**（配置页用的是同一批）：
 * 站点 `site/media/tv`、下载器 `download/clients`、目录 `download/paths`；
 * 配置页默认值从 `/subscriptions` 的 `default_*` 拿。插件后端不重复实现一套。
 */
const hostSites = ref<HostSite[]>([])
const hostDownloaders = ref<DownloadClientOption[]>([])
const hostPaths = ref<DownloadPathOption[]>([])
const defaults = ref({ sites: '', downloader: '', save_path: '' })
const optionsLoading = ref(false)
const optionsLoaded = ref(false)
/** 本地编辑态：站点 id 数组、下载器名、保存目录 */
const localSites = ref<number[]>([])
const localDownloader = ref('')
const localSavePath = ref('')
const savingTargets = ref(false)
/** 三项有改动才显示「保存」——避免每开一次弹窗都发请求 */
const targetsDirty = ref(false)

const siteOptions = computed(() => hostSites.value || [])

/** 下载器下拉：第一项固定是「默认（配置页的下载器）」= 空串 */
const downloaderOptions = computed<{ title: string; value: string }[]>(() => {
  const def = defaults.value.downloader
  const names = (hostDownloaders.value || []).map((item) => item.name)
  if (def && !names.includes(def)) names.unshift(def)
  return [
    { title: def ? `默认（${def}）` : '默认（跟随配置页）', value: '' },
    ...names.map((name) => ({ title: name, value: name })),
  ]
})

/** 目录下拉：宿主给的 save_path 选项 + 「默认」空值 */
const pathOptions = computed<{ title: string; value: string }[]>(() => {
  const def = defaults.value.save_path
  const items = (hostPaths.value || []).map((item) => ({
    title: String(item.name || item.save_path || ''),
    value: String(item.save_path || ''),
  }))
  const list = items.filter((item) => item.value)
  if (def && !list.some((item) => item.value === def)) list.unshift({ title: def, value: def })
  return [{ title: def ? `默认（${def}）` : '默认（跟随配置页）', value: '' }, ...list]
})

const subSitesHint = computed(() => {
  if (localSites.value.length) return `已选 ${localSites.value.length} 个站点`
  const ids = String(defaults.value.sites || '')
    .split(',')
    .map((id) => id.trim())
    .filter(Boolean)
  if (!ids.length) return '留空 = 配置页里的全部站点'
  const names = ids.map((id) => siteOptions.value.find((site) => String(site.id) === id)?.name || id)
  return `默认：${names.join('、')}`
})

const subDownloaderHint = computed(() =>
  localDownloader.value ? '只下到这个下载器' : '留空 = 配置页默认下载器',
)

const subSavePathHint = computed(() =>
  localSavePath.value ? '只下到这个目录' : '留空 = 配置页默认目录',
)

/** 把订阅行上的覆写值灌进本地编辑态（打开弹窗 / 行刷新时） */
function syncLocalTargets(): void {
  localSites.value = String(props.subscription?.sites || '')
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((num) => Number.isFinite(num) && num > 0)
  localDownloader.value = String(props.subscription?.downloader || '')
  localSavePath.value = String(props.subscription?.save_path || '')
  targetsDirty.value = false
}

function onSitesChange(value: unknown): void {
  const list = Array.isArray(value) ? value : []
  localSites.value = list
    .map((item) => Number(item))
    .filter((num) => Number.isFinite(num) && num > 0)
  targetsDirty.value = true
}

function onDownloaderChange(value: unknown): void {
  localDownloader.value = String(value || '')
  targetsDirty.value = true
}

function onSavePathChange(value: unknown): void {
  localSavePath.value = String(value || '')
  targetsDirty.value = true
}

/** 保存三项落点（订阅没有暂停位，只改落点） */
async function saveTargets(): Promise<void> {
  if (savingTargets.value) return
  savingTargets.value = true
  try {
    const res = await pluginSubscribeUpdate({ api: props.api }, props.work.media_id, {
      sites: localSites.value.join(','),
      downloader: localDownloader.value,
      save_path: localSavePath.value,
    })
    toast(String(res?.message || '已保存订阅设置'))
    targetsDirty.value = false
    emit('sub-updated')
  } catch (err) {
    toast(`保存失败：${err instanceof Error ? err.message : err}`)
  } finally {
    savingTargets.value = false
  }
}

/** 拉一次可选项（站点 / 下载器 / 目录 / 配置页默认），失败各自降级为空 */
async function loadTargetOptions(): Promise<void> {
  if (optionsLoading.value || optionsLoaded.value) return
  optionsLoading.value = true
  try {
    const [sites, downloaders, paths, subs] = await Promise.allSettled([
      fetchSearchSites({ api: props.api }),
      fetchDownloaderOptions({ api: props.api }),
      fetchDownloadPaths({ api: props.api }),
      fetchSubscriptions({ api: props.api }),
    ])
    hostSites.value = sites.status === 'fulfilled' ? sites.value : []
    hostDownloaders.value = downloaders.status === 'fulfilled' ? downloaders.value : []
    hostPaths.value = paths.status === 'fulfilled' ? paths.value : []
    if (subs.status === 'fulfilled') {
      defaults.value = {
        sites: String(subs.value.default_sites || ''),
        downloader: String(subs.value.default_downloader || ''),
        save_path: String(subs.value.default_save_path || ''),
      }
    }
    optionsLoaded.value = true
  } finally {
    optionsLoading.value = false
  }
}

/** 弹窗打开时才拉可选项，并把覆写值同步进编辑态 */
watch(subsetOpen, async (open) => {
  if (!open) return
  syncLocalTargets()
  await loadTargetOptions()
})

/** 行刷新（订阅清单重拉）后跟上最新的覆写值 */
watch(
  () => props.subscription,
  () => {
    if (subsetOpen.value && !targetsDirty.value) syncLocalTargets()
  },
)

/** 「在线播放」请求中（按钮转圈） */
const playing = ref(false)

/** 轻提示（播放失败等）：本页没有宿主 toast，用一个自己的 snackbar */
const snackbar = ref(false)
const snackbarText = ref('')

function toast(text: string): void {
  snackbarText.value = String(text || '')
  snackbar.value = Boolean(snackbarText.value)
}

/**
 * 在线播放：与系统详情页 `handlePlay()` 同一套 —— 先按身份查媒体库里的条目，
 * 再取播放页地址并新标签打开。没有条目 / 没配媒体服务器时给一句提示。
 */
async function playWork(): Promise<void> {
  if (playing.value) return
  playing.value = true
  try {
    const url = await fetchPlayUrl(
      { api: props.api },
      {
        mediaSource: String(view.value.media_source || props.work.media_source || 'djbaike'),
        mediaId: String(view.value.media_id || props.work.media_id || ''),
        title: String(view.value.title || props.work.title || ''),
        year: String(view.value.year || props.work.year || ''),
        type: String(view.value.type || '电视剧'),
      },
    )
    if (url) {
      window.open(url, '_blank', 'noopener')
    } else {
      toast('没有找到可播放的条目：媒体服务器里没有，或未配置媒体服务器')
    }
  } finally {
    playing.value = false
  }
}

/** 点「改编自」：切到站内原著详情页（数据在打开作品详情时已到手） */
function openAdapted(): void {
  const novel = source.value?.adapted
  if (novel) emit('open-adapted', novel)
}

/** 打开外部地址（百科作品页 / 演员页） */
function openUrl(url: string): void {
  if (!url) return
  if (typeof window !== 'undefined') window.open(url, '_blank', 'noopener')
}

/**
 * 拉详情：百科现查（百科插件侧有 TTL 缓存，重开同一部剧很快）。
 *
 * 三个状态与宿主一一对应：`loaded` ≡ `isRefreshed`、`failed` ≡ `detailLoadFailed`、
 * `detail` ≡ `mediaDetail`。宿主失败时 `mediaDetail` 仍是空对象（赋值前就抛了）⇒ 内容
 * 区不渲染、只出 NoDataFound；这里同样把 `detail` 清成 null（内容区同样不渲染）。
 */
async function load(): Promise<void> {
  loaded.value = false
  failed.value = false
  source.value = null
  doubanReviews.value = []
  doubanComments.value = []
  doubanTotals.interests = 0
  doubanTotals.reviews = 0
  doubanTab.value = 'interests'
  doubanLoaded.value = false
  try {
    detail.value = await fetchWorkDetail(
      { api: props.api },
      { media_id: props.work.media_id, title: props.work.title, year: props.work.year },
    )
    // 原始记录单独取（导演 / 编剧 + 站点独有字段，数据源公开端点；失败静默）
    // —— 不阻塞详情渲染，回来多少补多少
    void fetchWorkSource({ api: props.api }, props.work.media_id).then((value) => {
      source.value = value
      // 2026-10-22 换源：后端经模块 recognize_media 拿到的是宿主 domain 版
      // MediaInfo（转换时丢 douban_id），scraper /lookup 这份有 —— 在这里补回，
      // 豆瓣短评 / 影评与「豆瓣」chip 才有身份可用。
      const data = detail.value
      if (data && !String(data.douban_id || '').trim() && value.douban_id) {
        detail.value = {
          ...data,
          douban_id: value.douban_id,
          douban_url: value.douban_url || data.douban_url || '',
        }
        // 上面那次 loadDouban() 是在**没有豆瓣身份**时发的，必然空转 ——
        // 真机表现就是「短评默认不显示，点一下标签才出来」（2026-10-22）。
        // 身份补回来的这一刻重试一次即可。
        if (!doubanComments.value.length && !doubanReviews.value.length) void loadDouban()
      }
    })
    // 豆瓣影评 / 短评（有 douban_id 才真的发请求）
    void loadDouban()
  } catch (err) {
    // 与宿主一致：异常只进控制台，界面统一用那两句固定文案（不同后端的报错五花八门）
    console.error('[ShortDramaActorSubscribe] 作品详情加载失败', err)
    detail.value = null
    failed.value = true
  } finally {
    loaded.value = true
  }
}

/**
 * 取一页豆瓣短评 / 影评（系统那一页的协议：`start` 偏移 + `count` 条数）。
 *
 * 两个标签各自累加、按 id 去重（豆瓣翻页偶尔会重叠）；失败静默，
 * 只是这一页为空 —— 详情页其余内容不受影响。
 */
async function loadDoubanPage(tab: 'interests' | 'reviews', start: number): Promise<void> {
  const id = String(view.value?.douban_id || '').trim()
  if (!id) return
  const typeName = String(view.value?.type || '电视剧')
  doubanLoading.value = true
  try {
    if (tab === 'interests') {
      const page = await fetchDoubanComments(
        { api: props.api },
        id,
        typeName,
        start,
        DOUBAN_PAGE,
      )
      const seen = new Set(doubanComments.value.map((item) => item.id))
      doubanComments.value.push(...page.items.filter((item) => !seen.has(item.id)))
      doubanTotals.interests = page.total
    } else {
      const page = await fetchDoubanReviews(
        { api: props.api },
        id,
        typeName,
        start,
        DOUBAN_PAGE,
      )
      const seen = new Set(doubanReviews.value.map((item) => item.id))
      doubanReviews.value.push(...page.items.filter((item) => !seen.has(item.id)))
      doubanTotals.reviews = page.total
    }
  } finally {
    doubanLoading.value = false
    doubanLoaded.value = true
  }
}

/**
 * 首屏取豆瓣两块的第一页。
 *
 * **串行**：豆瓣对并发请求很不客气 —— 两页一起发常常双双返回空，真机表现就是
 * 「进页面短评空白，点一下短评标签才出来」（2026-10-22 用户反馈）。先拉当前可见的
 * 短评，再拉影评；短评第一次空了隔 0.8 秒补一次，仍空才算真没有。
 */
async function loadDouban(): Promise<void> {
  if (!view.value?.douban_id) return
  await loadDoubanPage('interests', 0)
  if (!doubanComments.value.length) {
    await new Promise((resolve) => setTimeout(resolve, 800))
    await loadDoubanPage('interests', 0)
  }
  await loadDoubanPage('reviews', 0)
}

/** 切标签：没加载过就补第一页（两页其实都已拉过，这里只是兜底） */
function switchDoubanTab(tab: 'interests' | 'reviews'): void {
  doubanTab.value = tab
  const loaded = tab === 'interests' ? doubanComments.value.length : doubanReviews.value.length
  if (!loaded) void loadDoubanPage(tab, 0)
}

/**
 * 标签点击的容器委托。
 *
 * 两个标签是原生 `<button>`，原来只在文字那一小段落上有点击热区，用户反馈
 * 「只有后面的条数点得动」。这里统一在容器上监听，命中 `[data-douban-tab]`
 * 就切换 —— 文字 / 数字 / 内边距一律等效。
 */
function onDoubanTabsClick(event: MouseEvent): void {
  const target = event.target as HTMLElement | null
  const el = target?.closest?.('[data-douban-tab]') as HTMLElement | null
  const tab = el?.getAttribute('data-douban-tab')
  if (tab === 'interests' || tab === 'reviews') switchDoubanTab(tab)
}

/** 「加载更多」：按当前标签已加载条数作为偏移 */
function loadMoreDouban(): void {
  void loadDoubanPage(doubanTab.value, doubanRows.value.length)
}

/**
 * 点演员阵容里的卡片 —— 与宿主一样「钻进这位演员」。
 *
 * 宿主 `PersonCard` 的 `goPersonDetail()` 是 `router.push('/person?personid=…')`；
 * 本插件没有宿主那一页，对应物是**演员作品页**（`ActorDetail.vue`），由父组件经
 * `open-actor` 切过去。
 *
 * 数据源（.net）的作品详情里，演职员只带**名字与角色**，站点演员 ID 不在宿主
 * `MediaCredit` 里 —— 所以这一跳按**名字**打开（后端 `/actors/detail?name=…`
 * 会到数据源里按名字精确匹配）。连名字都没有时（理论上不会有）才退化成
 * 打开外部页面。
 */
function openActor(row: CastRow): void {
  if (!row.actor_id && !row.name) {
    openUrl(row.url || view.value.url)
    return
  }
  emit('open-actor', {
    name: row.name,
    actor_id: row.actor_id,
    exact: true,
    subscribed: row.subscribed,
    profile: row.profile,
    url: row.url,
  })
}

/**
 * 「简介 + 来源」与「信息面板」这一行：左栏明显矮时改单列。
 *
 * 宿主那一页（`.media-overview`）是**左右并排**，行高由更高的那一侧决定；它的左栏有
 * TMDB 简介（常常好几段）加导演列表，能填满，所以看不出问题。短剧的简介只有一两行，
 * 而信息面板有 7~10 行 ⇒ 并排时左栏下方空出一大片，正好夹在来源链接与演员阵容中间。
 *
 * 这里按**内容高度**自动选：够高就并排（与宿主那一页完全一致），会露空白就按窄屏那样
 * 单列（样式里的 `.is-stacked`）。用 `scrollHeight` 而不是盒子高度 —— 并排时左栏被
 * `align-items: stretch` 拉到与右栏同高，量盒子高度永远是 0 差值。
 */
const overviewLeft = ref<HTMLElement | null>(null)
const overviewRight = ref<HTMLElement | null>(null)
const overviewStacked = ref(false)
let overviewObserver: ResizeObserver | null = null

/** 差得不多就不折腾（并排更省纵向空间，也更接近宿主那一页） */
const OVERVIEW_STACK_GAP = 32

function syncOverviewStack(): void {
  const left = overviewLeft.value
  const right = overviewRight.value
  if (!left || !right) {
    overviewStacked.value = false
    return
  }
  overviewStacked.value = right.scrollHeight - left.scrollHeight > OVERVIEW_STACK_GAP
}

/** 重新挂观察器：`v-if` 分支切换后元素会换，所以要重新 observe 一次 */
function watchOverviewSize(): void {
  overviewObserver?.disconnect()
  overviewObserver = null
  if (typeof ResizeObserver === 'undefined') return
  overviewObserver = new ResizeObserver(syncOverviewStack)
  if (overviewLeft.value) overviewObserver.observe(overviewLeft.value)
  if (overviewRight.value) overviewObserver.observe(overviewRight.value)
  syncOverviewStack()
}

// ── 演员阵容横滑（宿主的 VirtualSlideView 那套只取外观：滚动 + 翻页钮状态） ──
const castRail = ref<HTMLElement | null>(null)
/** 0 在最左 / 1 在中间 / 2 在最右 / 3 没有可滚动的（与宿主的 disabled 语义一致） */
const castNavState = ref(3)
let castScrollTimer: ReturnType<typeof setTimeout> | null = null
let castResizeObserver: ResizeObserver | null = null

function syncCastRail(): void {
  const rail = castRail.value
  if (!rail) return
  if (rail.scrollWidth <= rail.clientWidth + 2) castNavState.value = 3
  else if (rail.scrollLeft <= 2) castNavState.value = 0
  else if (rail.scrollLeft >= rail.scrollWidth - rail.clientWidth - 2) castNavState.value = 2
  else castNavState.value = 1
}

/** 用户滚动时让翻页钮常显一会儿（宿主的 is-scrolling 同款）；量宽时不触发 */
function onCastScroll(): void {
  syncCastRail()
  const rail = castRail.value
  if (!rail) return
  rail.classList.add('is-scrolling')
  if (castScrollTimer) clearTimeout(castScrollTimer)
  castScrollTimer = setTimeout(() => castRail.value?.classList.remove('is-scrolling'), 1500)
}

/** 翻一屏（宿主按「可视卡片数 × 步长」算，这里同样按步长走） */
function slideCast(next: boolean): void {
  const rail = castRail.value
  if (!rail) return
  const item = rail.querySelector<HTMLElement>('.sdas-slide-item')
  const step = (item?.offsetWidth || 144) + 16
  const page = Math.max(1, Math.trunc(rail.clientWidth / step))
  const current = rail.scrollLeft <= 2 ? 0 : Math.trunc((rail.scrollLeft + step / 2) / step)
  const target = next
    ? Math.min((current + page) * step, rail.scrollWidth - rail.clientWidth)
    : Math.max((current - page) * step, 0)
  rail.scrollTo({ left: target, top: 0, behavior: 'smooth' })
  setTimeout(syncCastRail, 420)
}

onMounted(() => {
  castResizeObserver = new ResizeObserver(() => syncCastRail())
  if (castRail.value) castResizeObserver.observe(castRail.value)
  nextTick(syncCastRail)

  // 简介 / 信息面板的高度一变就重新判一次并排还是单列
  watchOverviewSize()

  // 主题跟着宿主实时变（用户在设置里切玻璃 / 透明主题时不用重开面板）
  syncTheme()
  if (typeof MutationObserver !== 'undefined') {
    themeObserver = new MutationObserver(syncTheme)
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  }
})

onUnmounted(() => {
  if (castScrollTimer) clearTimeout(castScrollTimer)
  castResizeObserver?.disconnect()
  castResizeObserver = null
  overviewObserver?.disconnect()
  overviewObserver = null
  themeObserver?.disconnect()
  themeObserver = null
})

// 换一部作品就重拉（点开另一张卡时组件不一定重建，只换 work）
watch(
  () => props.work?.media_id,
  () => {
    loadedCast.value = new Set()
    // 与宿主一致：**换一部剧 = 全新一页**（宿主是路由跳转 ⇒ 新实例 ⇒ 状态从零开始）。
    // 不清掉的话，同一实例内换剧会先渲染上一部的详情（宿主绝不会这样）。
    detail.value = null
    loaded.value = false
    failed.value = false
    subsetOpen.value = false
    load()
  },
  { immediate: true },
)

// 演员表铺出来之后才有可滚动内容：量一次才决定翻页钮显不显示
watch(castRows, () => nextTick(syncCastRail), { flush: 'post' })

// 简介 / 信息面板的内容变了（换作品、详情回来）也要重新判一次并排还是单列 ——
// 只靠 ResizeObserver 会漏掉「内容变了但被拉伸后的盒子尺寸没变」的情形
watch(
  [() => view.value.overview, () => facts.value.length],
  () => nextTick(watchOverviewSize),
  { flush: 'post' },
)
</script>

<style scoped>
/*
  页面根 —— 宿主那一页是 `.max-w-8xl.mx-auto.px-4` 里的块：**限宽类在宿主 CSS 里
  根本没生成**（`style.css` 里只有 `max-w-32 / 40 / 6xl`），所以两边都是满宽 + 1rem 内边距。
  这里把 padding 交给内容块，大图 / 渐变层用绝对定位挂在根上、铺满整宽。
*/
.sdas-detail {
  position: relative;
}

/* 加载态：宿主给 LoadingBanner 加了 `mt-12`（3rem） */
.sdas-detail-loading {
  margin-block-start: 3rem;
}

/* 「未识别到媒体信息」提示行：留在正文第一行（返回键已移到视口，见 StickyBack） */
.sdas-detail-note {
  padding: 4px 0;
  font-size: 0.8125rem;
  opacity: 0.75;
}


.sdas-detail-note {
  overflow: hidden;
  padding: 2px 8px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
  background: rgb(8 18 28 / 42%);
  color: #fff;
  font-size: 0.8125rem;
  line-height: 1.5;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/*
  ── 顶栏大图（宿主 `.vue-media-back` 同款）──
  两层绝对定位铺满整宽、`h-96`（24rem）：一层放图、一层放四向渐变把边缘收到页面底色。
  内容块 `.sdas-detail-page` 叠在它们上面（z-index 1）。
*/
.sdas-detail-back {
  position: absolute;
  z-index: 0;
  inset-block-start: 0;
  inset-inline: 0;
  block-size: 24rem;
  pointer-events: none;
}

.sdas-detail-back-image {
  overflow: hidden;
}

.sdas-detail-back-img {
  block-size: 24rem;
  inline-size: 100%;
}

.sdas-detail-back-overlay {
  background-image:
    linear-gradient(
      180deg,
      rgba(var(--v-theme-background), 0) 50%,
      rgba(var(--v-theme-background), 1) 100%
    ),
    linear-gradient(
      0deg,
      rgba(var(--v-theme-background), 0) 80%,
      rgba(var(--v-theme-background), 1) 100%
    ),
    linear-gradient(
      90deg,
      rgba(var(--v-theme-background), 0) 50%,
      rgba(var(--v-theme-background), 1) 100%
    ),
    linear-gradient(
      270deg,
      rgba(var(--v-theme-background), 0) 50%,
      rgba(var(--v-theme-background), 1) 100%
    );
}

/*
  玻璃 / 透明主题：宿主会**隐藏四向渐变层**、把大图换成四边遮罩渐隐并轻微下调不透明度
  （`MediaDetailView.vue` 的 `.media-detail-glass .vue-media-back-*`，数值照搬）。
*/
.sdas-detail.is-glass .sdas-detail-back-overlay,
.sdas-detail.is-transparent .sdas-detail-back-overlay {
  display: none;
}

.sdas-detail.is-glass .sdas-detail-back-img,
.sdas-detail.is-transparent .sdas-detail-back-img {
  mask-image:
    linear-gradient(to bottom, transparent 0%, #000 16%, #000 58%, transparent 100%),
    linear-gradient(to right, transparent 0%, #000 10%, #000 90%, transparent 100%);
  mask-composite: intersect;
  -webkit-mask-image:
    linear-gradient(to bottom, transparent 0%, #000 16%, #000 58%, transparent 100%),
    linear-gradient(to right, transparent 0%, #000 10%, #000 90%, transparent 100%);
  -webkit-mask-composite: source-in;
}

.sdas-detail.is-transparent .sdas-detail-back-img {
  opacity: 0.78;
}

.sdas-detail.is-glass .sdas-detail-back-img {
  opacity: 0.88;
}

/*
  内容块（宿主 `.media-page`）：宿主那两条 `margin-block-start: -4rem` + `padding-block-start: 4rem`
  是**用来穿过宿主顶栏的、净效果为 0** —— 内容从页面顶部开始，大图在它下面铺 24rem。
  这里没有宿主顶栏，所以直接让内容从顶部起（`z-index: 1` 叠在大图上）。
*/
.sdas-detail-page {
  position: relative;
  z-index: 1;
  padding-inline: 1rem;
}

/* ── 头部：海报 + 标题 + 操作按钮（宿主 .media-header 同构） ── */
.sdas-detail-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-block-start: 1rem;
}

@media (width >= 1280px) {
  .sdas-detail-header {
    flex-direction: row;
    align-items: flex-end;
  }
}

.sdas-detail-poster {
  overflow: hidden;
  border-radius: var(--app-surface-radius, 8px);
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
  inline-size: 8rem;
}

@media (width >= 768px) {
  .sdas-detail-poster {
    inline-size: 11rem;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  }
}

@media (width >= 1280px) {
  .sdas-detail-poster {
    inline-size: 13rem;
    margin-inline-end: 1rem;
  }
}

/* 海报骨架：用宿主同款 VSkeletonLoader（CSS 由宿主提供），铺满 2:3 海报位 */
.sdas-detail-poster-skeleton {
  position: absolute;
  inset: 0;
  block-size: 100%;
  inline-size: 100%;
}

.sdas-detail-poster-empty {
  aspect-ratio: 2 / 3;
  inline-size: 100%;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.sdas-detail-title {
  display: flex;
  flex: 1 1 0%;
  flex-direction: column;
  margin-block-start: 1rem;
  min-inline-size: 0;
  text-align: center;
}

@media (width >= 1280px) {
  .sdas-detail-title {
    margin-block: 0;
    margin-inline: 0 1rem;
    text-align: start;
  }
}

/* 状态胶囊：宿主 .media-status（+ 它那枚 rounded-full 绿色胶囊） */
.sdas-detail-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  justify-content: center;
  margin-block-end: 0.5rem;
}

@media (width >= 1280px) {
  .sdas-detail-status {
    justify-content: flex-start;
  }
}

.sdas-status-pill {
  display: inline-flex;
  align-items: center;
  padding-inline: 0.5rem;
  border: 1px solid transparent;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.25rem;
  white-space: nowrap;
}

.sdas-status-pill.is-library {
  border-color: #22c55e;
  background-color: rgb(34 197 94 / 80%);
  color: #dcfce7;
}

.sdas-status-pill.is-new {
  border-color: #e53935;
  background-color: rgb(229 57 53 / 80%);
  color: #ffebee;
}

.sdas-status-pill.is-kind {
  border-color: #7e57c2;
  background-color: rgb(126 87 194 / 80%);
  color: #ede7f6;
}

/*
  标题行 —— 宿主 `<h1 class="d-flex flex-column flex-lg-row align-baseline
  justify-center justify-lg-start">` + 子块 `align-self-center align-self-lg-end`：
  **横排的断点是 lg（1024px）**，字号断点在 1280px（`.media-title > h1`）。两处照抄。
*/
.sdas-detail-h1 {
  display: flex;
  flex-direction: column;
  align-items: baseline;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 2rem;
}

.sdas-detail-h1-text {
  align-self: center;
  min-inline-size: 0;
  word-break: break-word;
}

.sdas-detail-year {
  align-self: center;
  font-size: 1.125rem;
}

@media (width >= 1024px) {
  .sdas-detail-h1 {
    flex-direction: row;
    justify-content: flex-start;
  }

  .sdas-detail-h1-text,
  .sdas-detail-year {
    align-self: flex-end;
  }
}

@media (width >= 1280px) {
  .sdas-detail-h1 {
    font-size: 2.25rem;
    line-height: 2.5rem;
  }
}

/* 属性行：宿主 .media-attributes */
.sdas-detail-attributes {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  margin-block-start: 0.25rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
}

@media (width >= 640px) {
  .sdas-detail-attributes {
    font-size: 0.875rem;
    line-height: 1.25rem;
  }
}

@media (width >= 1280px) {
  .sdas-detail-attributes {
    justify-content: flex-start;
    margin-block-start: 0;
    font-size: 1rem;
    line-height: 1.5rem;
  }
}

/* 操作按钮排：宿主 .media-actions（窄屏两列网格，≥640px 起变一行右对齐） */
/* 分类条目：与标题行同字号同色，悬停下划线（不抢标题的视觉） */
.sdas-detail-genres {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
}

.sdas-detail-genre {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

/* 条目之间的分隔符（原来是一整串「A / B」，现在由 CSS 画，DOM 里只留剧名本身） */
.sdas-detail-genre + .sdas-detail-genre::before {
  content: ' / ';
  opacity: 0.6;
  white-space: pre;
}

.sdas-detail-genre:hover {
  text-decoration: underline;
}

.sdas-detail-genre:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
  border-radius: 3px;
}

.sdas-detail-actions {
  --sdas-action-gap: 0.75rem;

  display: grid;
  flex-shrink: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sdas-action-gap);
  inline-size: min(100%, 22rem);
  justify-content: center;
  margin-block-start: 1rem;
}

.sdas-detail-action-btn {
  inline-size: 100%;
  min-inline-size: 0;
}

.sdas-detail-actions > .sdas-detail-action-btn:only-child,
.sdas-detail-actions
  > .sdas-detail-action-btn:last-child:nth-child(odd):not(:first-child) {
  grid-column: 1 / -1;
  inline-size: calc((100% - var(--sdas-action-gap)) / 2);
  justify-self: center;
}

@media (width >= 640px) {
  /* 分类条目：与标题行同字号同色，悬停下划线（不抢标题的视觉） */
.sdas-detail-genres {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
}

.sdas-detail-genre {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

/* 条目之间的分隔符（原来是一整串「A / B」，现在由 CSS 画，DOM 里只留剧名本身） */
.sdas-detail-genre + .sdas-detail-genre::before {
  content: ' / ';
  opacity: 0.6;
  white-space: pre;
}

.sdas-detail-genre:hover {
  text-decoration: underline;
}

.sdas-detail-genre:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
  border-radius: 3px;
}

.sdas-detail-actions {
    display: flex;
    gap: 0.5rem;
    inline-size: auto;
    justify-content: flex-end;
  }

  .sdas-detail-action-btn,
  .sdas-detail-actions > .sdas-detail-action-btn:only-child,
  .sdas-detail-actions
    > .sdas-detail-action-btn:last-child:nth-child(odd):not(:first-child) {
    inline-size: auto;
  }
}

@media (width >= 1280px) {
  /* 分类条目：与标题行同字号同色，悬停下划线（不抢标题的视觉） */
.sdas-detail-genres {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
}

.sdas-detail-genre {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

/* 条目之间的分隔符（原来是一整串「A / B」，现在由 CSS 画，DOM 里只留剧名本身） */
.sdas-detail-genre + .sdas-detail-genre::before {
  content: ' / ';
  opacity: 0.6;
  white-space: pre;
}

.sdas-detail-genre:hover {
  text-decoration: underline;
}

.sdas-detail-genre:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
  border-radius: 3px;
}

.sdas-detail-actions {
    margin-block-start: 0;
  }
}

/* ── 简介（左） + 信息面板（右）：宿主 .media-overview 同构 ── */
.sdas-detail-overview {
  display: flex;
  flex-direction: column;
  padding-block: 2rem 1rem;
}

@media (width >= 1024px) {
  .sdas-detail-overview {
    flex-direction: row;
  }
}

.sdas-detail-overview-left {
  flex: 1 1 0%;
  min-inline-size: 0;
}

@media (width >= 1024px) {
  .sdas-detail-overview-left {
    margin-inline-end: 2rem;
  }
}

.sdas-detail-overview-right {
  inline-size: 100%;
  margin-block-start: 2rem;
}

@media (width >= 1024px) {
  .sdas-detail-overview-right {
    inline-size: 20rem;
    margin-block-start: 0;
  }
}

/*
  ── 左栏矮太多时改单列（脚本判定，见 `syncOverviewStack`）──
  宿主那一页的左栏有长简介 + 导演列表，能填满信息面板的高度；短剧简介只有一两行，
  并排就会在左栏下方露一大片空白（夹在来源链接与演员阵容中间）。够高时上面那套并排
  规则照旧（与宿主那一页完全一致），不够高才走这里。
*/
@media (width >= 1024px) {
  .sdas-detail-overview.is-stacked {
    flex-direction: column;
  }

  .sdas-detail-overview.is-stacked .sdas-detail-overview-left {
    margin-inline-end: 0;
  }

  .sdas-detail-overview.is-stacked .sdas-detail-overview-right {
    inline-size: 100%;
    margin-block-start: 2rem;
  }

  /*
    信息面板整宽后一行会被拉到两端相去很远 ⇒ 拆成多列网格，每列 17rem 起（与宿主那
    20rem 竖栏差不多宽，行内仍是「标签左 / 值右」）。网格线只画每格的**上边** + 容器的
    **下边**：同行并排的格子线落在同一条水平线上、最后一行没填满也不会缺角，
    也不会与容器边框叠成双线。
  */
  .sdas-detail-overview.is-stacked .sdas-facts {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
    border-width: 0 0 1px;
    border-radius: 0;
  }

  .sdas-detail-overview.is-stacked .sdas-facts > * {
    border-block-start: 1px solid var(--sdas-facts-border);
    border-block-end-width: 0;
  }

  /* 评分行整行居中（它跨满所有列） */
  .sdas-detail-overview.is-stacked .sdas-ratings {
    grid-column: 1 / -1;
  }
}

.sdas-detail-h2 {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.75rem;
}

@media (width >= 640px) {
  .sdas-detail-h2 {
    font-size: 1.5rem;
    line-height: 2rem;
  }
}

/* 简介正文：宿主 `.media-overview p` 没有专门规则（走宿主默认 1rem / 1.5），这里不另设字号 */
.sdas-detail-text {
  white-space: pre-wrap;
}

.sdas-detail-text.is-dim {
  opacity: 0.7;
}

/* ── 信息面板：宿主 .media-facts / .media-ratings / .media-fact ── */
.sdas-facts {
  border: 1px solid var(--sdas-facts-border);
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 700;
  line-height: 1.25rem;

  /* 宿主的 .media-facts 用 Tailwind gray-700 做分隔线（主题无关，原样搬） */
  --sdas-facts-border: #374151;
}

.sdas-ratings {
  display: flex;
  align-items: center;
  justify-content: center;
  border-block-end: 1px solid var(--sdas-facts-border);
  font-weight: 500;
  padding-block: 0.5rem;
  padding-inline: 1rem;
}

.sdas-fact {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border-block-end: 1px solid var(--sdas-facts-border);
  padding-block: 0.5rem;
  padding-inline: 1rem;
}

.sdas-fact.is-last {
  border-block-end-width: 0;
}

.sdas-fact-value {
  display: flex;
  justify-content: flex-end;
  min-inline-size: 0;
  text-align: end;
}

.sdas-fact-inner {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.sdas-fact-icon {
  block-size: 1rem;
  inline-size: 1rem;
  flex: 0 0 auto;
}

/* 来源链接 chip（宿主 .media-source-link-chip 同款：gray-600 底 + gray-500 描边） */
.sdas-detail-links {
  margin-block-start: 1.5rem;
}

.sdas-link-chip {
  display: inline-flex;
  align-items: center;
  margin-block-end: 0.5rem;
  margin-inline-end: 0.5rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid #6b7280;
  border-radius: 9999px;
  background-color: #4b5563;
  color: #e5e7eb;
  font-size: 0.875rem;
  line-height: 1.25rem;
  text-decoration: none;
  transition: background-color 0.15s ease;
}

.sdas-link-chip:hover {
  background-color: #374151;
}

/* 玻璃主题下宿主会把来源 chip 一起玻璃化（`.media-detail-glass .media-source-link-chip` 同款） */
.sdas-detail.is-glass .sdas-link-chip {
  border: 1px solid var(--glass-border);
  -webkit-backdrop-filter: var(--glass-chip-backdrop-filter);
  backdrop-filter: var(--glass-chip-backdrop-filter);
  background-color: var(--glass-button-surface);
  background-image: var(--glass-chip-sheen);
  box-shadow: var(--glass-control-shadow);
  color: rgb(var(--v-theme-on-surface));
}

.sdas-detail.is-glass .sdas-link-chip:hover {
  border-color: var(--glass-border-hover);
  background-color: var(--glass-button-surface-hover);
  box-shadow: var(--glass-control-shadow-hover);
}

/* ── 演员阵容：横滑人物卡（宿主 .slider-* + PersonCard 同款） ── */
.sdas-slider {
  position: relative;
  isolation: isolate;
  margin-block-end: 8px;

  --sdas-slider-bleed-start: 28px;
  --sdas-slider-bleed-end: 56px;
}

.sdas-slider-header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-block-end: 12px;
  padding-inline: 8px;
}

.sdas-slider-title-section {
  display: flex;
  align-items: center;
  flex-grow: 1;
  min-inline-size: 0;
}

/* 标题前的竖条（宿主 .title-badge） */
.sdas-slider-badge {
  flex: 0 0 auto;
  margin-inline-end: 8px;
  border-radius: 2px;
  background-color: rgb(var(--v-theme-primary));
  block-size: 16px;
  inline-size: 3px;
}

.sdas-slider-title {
  margin: 0;
  color: rgba(var(--v-theme-on-background), 0.95);
  font-size: 1.2rem;
  font-weight: 600;
  line-height: 1.5rem;
}

.sdas-slider-wrapper {
  position: relative;
  z-index: 1;
  inline-size: 100%;
}

.sdas-slider-content {
  display: flex;
  gap: 16px;
  margin-block: calc(var(--sdas-slider-bleed-start) * -1) calc(var(--sdas-slider-bleed-end) * -1);
  padding-block: var(--sdas-slider-bleed-start) var(--sdas-slider-bleed-end);
  padding-inline: 12px;
  overflow: auto hidden;
  overscroll-behavior-x: contain;
  scroll-behavior: smooth;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.sdas-slider-content::-webkit-scrollbar {
  display: none;
}

/*
 * 滑轨里的一格 = **演员墙那张卡**（`ActorCard`，2:3 整图）。
 * 宽度取 9.75rem（156px，演员墙卡宽 144 略宽一点）：导演 / 编剧卡上第二行要放得下
 * 「导演」「编剧」，比宿主原来 9rem 的圆头像卡宽一档。
 */
.sdas-slide-item {
  flex: 0 0 auto;
  inline-size: 9.75rem;
  padding-block-end: 12px;
}

/* 信息面板里可点的值（目前只有「改编自」）：与正文同色，悬停下划线 */
.sdas-fact-link {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-decoration: none;
  overflow-wrap: anywhere;
  cursor: pointer;
  text-align: start;
}

.sdas-fact-link:hover {
  text-decoration: underline;
}

.sdas-fact-link:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
  border-radius: 3px;
}

/* ── 豆瓣短评 / 影评（照系统 MediaCommentView：标签页 + 紧凑列表） ── */
.sdas-douban {
  margin-top: 1.5rem;
  padding-inline: 16px;
}

.sdas-douban-tabs {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  /* 抵消下面标签的左右内边距，视觉位置与文案对齐不变 */
  margin-inline: -8px;
  border-block-end: 1px solid rgba(var(--v-border-color), 0.24);
}

/* 标签：整块可点（热区 = 内边距 + 文字 + 条数），不再只有文字那一小段 */
.sdas-douban-tab {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-block-size: 36px;
  margin-block-end: -1px;
  padding: 6px 8px 8px;
  border: 0;
  border-block-end: 2px solid transparent;
  background: none;
  color: rgba(var(--v-theme-on-surface), 0.72);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.sdas-douban-tab:hover {
  color: rgba(var(--v-theme-on-surface), 0.92);
}

.sdas-douban-tab.is-active {
  border-block-end-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-primary));
}

.sdas-douban-count {
  margin-inline-start: 4px;
  font-size: 0.75rem;
  opacity: 0.6;
}

.sdas-douban-list {
  display: flex;
  flex-direction: column;
  padding: 4px 0 0;
  margin: 0;
  list-style: none;
}

.sdas-douban-item {
  display: flex;
  gap: 10px;
  padding: 9px 0;
}

.sdas-douban-item + .sdas-douban-item {
  border-block-start: 1px solid rgba(var(--v-border-color), 0.14);
}

.sdas-douban-avatar {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  inline-size: 32px;
  block-size: 32px;
  overflow: hidden;
  border-radius: 50%;
  background: rgba(var(--v-theme-on-surface), 0.1);
  font-size: 0.75rem;
  font-weight: 600;
}

.sdas-douban-avatar > img {
  inline-size: 100%;
  block-size: 100%;
  object-fit: cover;
}

.sdas-douban-body {
  min-inline-size: 0;
  flex: 1 1 auto;
}

.sdas-douban-author {
  display: flex;
  align-items: center;
  font-size: 0.875rem;
  line-height: 1.25rem;
  opacity: 0.9;
}

.sdas-douban-text {
  margin-top: 2px;
  font-size: 0.875rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.sdas-douban-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 3px;
  font-size: 0.75rem;
  line-height: 1.25rem;
  opacity: 0.6;
}

/* 影评标题：可点（去豆瓣原文），与系统那行标题同位置同字号 */
.sdas-douban-review-title {
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 500;
  line-height: 1.35rem;
  text-align: start;
  overflow-wrap: anywhere;
  cursor: pointer;
}

.sdas-douban-review-title:hover {
  text-decoration: underline;
}

.sdas-douban-foot {
  display: flex;
  align-items: center;
  justify-content: center;
  min-block-size: 40px;
  padding-block: 6px;
}

.sdas-douban-empty {
  font-size: 0.875rem;
  opacity: 0.6;
}

/* 翻页圆钮（宿主 .nav-button 同款：悬停或滚动中淡入，触摸端不显示） */
.sdas-slider-nav {
  position: absolute;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  inset-block-start: 50%;
  border: 1px solid rgb(255 255 255 / 14%);
  border-radius: 50%;
  backdrop-filter: blur(8px);
  background: rgb(8 18 28 / 52%) !important;
  block-size: 40px;
  box-shadow: 0 8px 22px rgb(0 0 0 / 22%);
  color: #fff;
  inline-size: 40px;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-50%);
  transition:
    opacity 0.3s ease,
    transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1),
    background-color 0.3s ease,
    box-shadow 0.3s ease,
    border-color 0.3s ease;
}

/* 图标走自有类名（门禁会丢含 `.v-` 的选择器，所以不用 :deep(.v-icon)） */
.sdas-nav-icon {
  color: #fff;
  font-size: 28px;
  filter: drop-shadow(0 1px 2px rgb(0 0 0 / 55%));
  transition: transform 0.3s ease;
}

.sdas-slider-nav.is-left {
  inset-inline-start: 8px;
}

.sdas-slider-nav.is-right {
  inset-inline-end: 8px;
}

.sdas-slider-nav:hover {
  border-color: rgb(255 255 255 / 28%);
  background: rgb(8 18 28 / 68%) !important;
  box-shadow: 0 10px 26px rgb(0 0 0 / 28%);
  transform: translateY(-50%) scale(1.05);
}

.sdas-slider-nav:hover .sdas-nav-icon {
  transform: scale(1.08);
}

.sdas-slider-content.is-scrolling ~ .sdas-slider-nav {
  opacity: 1;
  pointer-events: auto;
}

@media (hover: hover) {
  .sdas-slider-wrapper:hover .sdas-slider-nav {
    opacity: 1;
    pointer-events: auto;
  }
}

/* 搬运端（宿主用 `display.mobile`，600px 阈值）不显示翻页钮 —— 手指直接滑 */
@media (width < 600px) {
  .sdas-slider-nav {
    display: none !important;
  }
}

/* ── 订阅设置弹窗（操作按钮排「订阅设置」点开） ── */
.sdas-subset-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-block: 14px;
  /* 行数变多（暂停 / 站点 / 下载器 / 目录 / 种子 / 立即搜索），小屏必须能滚，
     否则后半截设置会被卡片高度切掉，看着像「没有这一项」 */
  max-block-size: 68vh;
  overflow-y: auto;
}

.sdas-subset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sdas-subset-cell {
  min-inline-size: 0;
}

.sdas-subset-label {
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.25rem;
}

.sdas-subset-hint {
  margin-block-start: 2px;
  font-size: 0.75rem;
  line-height: 1.1rem;
  opacity: 0.7;
}

/* 订阅设置里的下拉 / 输入框：宽度收到右侧一列，长名字自己省略 */
.sdas-subset-input {
  max-inline-size: 190px;
  min-inline-size: 130px;
  flex: 0 0 auto;
}

/* 种子标题：一行省略，完整标题挂在 title 提示上 */
.sdas-subset-torrent {
  max-inline-size: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sdas-subset-note {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  font-size: 0.75rem;
  line-height: 1.2rem;
  opacity: 0.85;
  overflow-wrap: anywhere;
}
</style>
