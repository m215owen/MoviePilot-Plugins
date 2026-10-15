<template>
  <div class="sdbs-root" :class="props.full ? 'pa-4' : 'pa-2'">
    <!-- ── 标题栏 ─────────────────────────────────────────────── -->
    <div class="d-flex align-center mb-3 flex-wrap" style="gap: 8px">
      <v-icon icon="mdi-television-classic" class="mr-1" />
      <h2 class="text-h6 ma-0">短剧百科数据源</h2>
      <v-chip size="small" variant="tonal" :color="enabled ? 'primary' : 'warning'">
        {{ enabled ? '已启用' : '未启用' }}
      </v-chip>
      <v-spacer />
      <v-btn
        v-if="props.full"
        size="small"
        variant="text"
        icon="mdi-close"
        title="关闭"
        @click="emit('close')"
      />
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-cog-outline"
        :loading="configLoading"
        title="打开配置：站点域名 / 站外索引 / 缓存 / 详情页摘要"
        @click="openSettings"
      >
        设置
      </v-btn>
      <v-switch
        v-model="enabled"
        color="primary"
        hide-details
        density="compact"
        :loading="toggling"
        :label="enabled ? '已启用' : '已停用'"
        class="sdbs-switch"
        @update:model-value="toggleEnabled"
      />
      <v-btn
        size="small"
        variant="tonal"
        color="primary"
        icon="mdi-refresh"
        title="刷新本页状态"
        :loading="loading"
        @click="load()"
      />
    </div>

    <v-alert type="info" variant="tonal" density="compact" class="mb-3">
      短剧在 TMDB / 豆瓣上大量没有条目，宿主识别器建不起媒体身份 —— 本插件补的就是这一段。
      搜索框<b>片名与演员名都收</b>：一次检索同时给出「作品」与「演员」两块结果，哪边命中就显示哪边
      （两边都命中就并排显示）。搜到的页面 URL 会存进<b>插件自有数据库</b>（URL 库），下次同一个词
      直接查库、零引擎请求；卡片上的「原始数据」可以看到插件解析出的完整字段。
    </v-alert>

    <!-- ── 缓存 与 URL 库：并排各占一半（点标题展开 / 收起） ─── -->
    <div class="sdbs-duo">
      <!-- ── URL 库（插件自有数据库；库里只存 URL，不存解析结果） ── -->
      <v-card variant="outlined" class="sdbs-panel">
        <!-- 卡片头（整行可点）：收起时也只占一行，与右边那张等高 -->
        <div
          class="d-flex align-center pa-3 sdbs-fold"
          style="gap: 8px"
          @click="toggleLibrary"
        >
          <v-icon icon="mdi-database-outline" size="18" />
          <span class="text-subtitle-2">URL 库</span>
          <v-chip v-if="storeChip" size="x-small" variant="tonal" color="teal">{{ storeChip }}</v-chip>
          <v-spacer />
          <span class="text-caption sdbs-dim">{{ libraryOpen ? '收起' : '展开' }}</span>
          <v-icon :icon="libraryOpen ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="20" />
        </div>
        <template v-if="libraryOpen">
          <v-divider />
          <div class="pa-3 pt-2">
            <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
              <v-btn
                size="x-small"
                variant="text"
                :loading="libraryLoading"
                prepend-icon="mdi-refresh"
                @click="loadLibrary()"
              >
                刷新
              </v-btn>
              <v-btn
                size="x-small"
                variant="text"
                color="error"
                prepend-icon="mdi-delete-sweep-outline"
                :disabled="libraryLoading || libraryClearing"
                @click="libraryClearOpen = true"
              >
                清空库
              </v-btn>
              <v-spacer />
              <span v-if="libraryStats" class="text-caption sdbs-dim">{{ libraryStats }}</span>
            </div>
            <div class="text-caption sdbs-dim mb-2">
              库里只存「页面 URL」：命中就直接抓页面（<b>零引擎请求</b>），解析结果不落库 ——
              站点内容随时在变，页面永远实时解析。<b>一个页面只占一条记录</b>（同一个 ID 走了两条
              发现路径被写成多行时会自动合并），每条按<b>它自己的名字</b>建档；右边标出「命中词」，
              告诉你它是搜哪个词时被带出来的。解析作品页时顺带把演员链接写进库，所以搜过一部剧，
              之后再搜它里面的演员名也能命中。
            </div>
            <v-alert v-if="libraryNotice" type="success" variant="tonal" density="compact" class="mb-2">
              {{ libraryNotice }}
            </v-alert>
            <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
              <v-text-field
                v-model="libraryKeyword"
                density="compact"
                variant="outlined"
                hide-details
                clearable
                prepend-inner-icon="mdi-magnify"
                placeholder="按关键词精确查（留空＝最近入库）"
                class="sdbs-lib-search"
                @keyup.enter="loadLibrary()"
              />
              <v-btn size="small" variant="tonal" color="primary" :loading="libraryLoading" @click="loadLibrary()">
                查询
              </v-btn>
              <v-btn-toggle v-model="libraryKind" density="compact" variant="outlined" divided mandatory>
                <v-btn size="small" value="all">全部</v-btn>
                <v-btn size="small" value="work">作品</v-btn>
                <v-btn size="small" value="actor">演员</v-btn>
              </v-btn-toggle>
            </div>
            <v-alert v-if="!libraryRecords.length" type="info" variant="tonal" density="compact">
              {{ libraryEmptyText }}
            </v-alert>
            <div
              v-for="row in libraryRecords"
              :key="`${row.kind}:${row.url}`"
              class="d-flex align-center py-1"
            >
              <v-chip
                size="x-small"
                variant="tonal"
                :color="row.kind === 'actor' ? 'purple' : 'primary'"
                class="mr-2"
              >
                {{ row.kind === 'actor' ? '演员' : '作品' }}
              </v-chip>
              <span class="text-body-2 flex-grow-1 sdbs-lib-text">
                {{ row.label || row.keyword || row.display }}
                <span class="text-caption sdbs-dim ml-1">{{ row.origin === 'page' ? '页面顺带' : '引擎' }}</span>
              </span>
              <span
                v-if="rowKeyInfo(row)"
                class="text-caption sdbs-dim mr-2"
                title="「命中词」＝搜这个词时发现的它；键／标题／命中词任何一个都能把它查回来"
              >
                {{ rowKeyInfo(row) }}
              </span>
              <v-btn
                v-if="row.url"
                size="x-small"
                variant="text"
                :href="row.url"
                target="_blank"
                rel="noopener"
              >
                打开
              </v-btn>
            </div>

            <v-dialog v-model="libraryClearOpen" max-width="440">
              <v-card>
                <v-card-title class="text-subtitle-2 pt-3">清空 URL 库</v-card-title>
                <v-card-text class="text-body-2">
                  将要删除：<b>{{ libraryClearScope }}</b>。
                  <br />
                  库里只存「页面 URL」，清掉之后下次搜索会重新问一遍搜索引擎 ——
                  引擎有最小间隔、召回也不稳，认得出的词会更少。确认要清吗？
                </v-card-text>
                <v-card-actions>
                  <v-spacer />
                  <v-btn size="small" variant="text" @click="libraryClearOpen = false">取消</v-btn>
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="error"
                    :loading="libraryClearing"
                    @click="clearLibrary()"
                  >
                    确认清空
                  </v-btn>
                </v-card-actions>
              </v-card>
            </v-dialog>
          </div>
        </template>
      </v-card>

      <!-- ── 缓存管理（后端与有效期跟随宿主，但不进宿主的缓存管理页） ── -->
      <v-card variant="outlined" class="sdbs-panel">
        <!-- 卡片头（整行可点）：收回时只剩一行，与左边那张等高 -->
        <div
          class="d-flex align-center pa-3 sdbs-fold"
          style="gap: 8px"
          @click="toggleCache"
        >
          <v-icon icon="mdi-cached" size="18" />
          <span class="text-subtitle-2">缓存管理</span>
          <v-chip v-if="cacheChip" size="x-small" variant="tonal" color="secondary">{{ cacheChip }}</v-chip>
          <v-spacer />
          <span class="text-caption sdbs-dim">{{ cacheOpen ? '收起' : '展开' }}</span>
          <v-icon :icon="cacheOpen ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="20" />
        </div>
        <template v-if="cacheOpen">
          <v-divider />
          <div class="pa-3 pt-2">
            <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
              <v-btn
                size="x-small"
                variant="text"
                :loading="cacheLoading"
                prepend-icon="mdi-refresh"
                @click="loadCache()"
              >
                刷新
              </v-btn>
              <v-btn
                size="x-small"
                variant="text"
                color="error"
                prepend-icon="mdi-delete-sweep-outline"
                :disabled="cacheLoading || cacheClearing || !cacheEntries.length"
                @click="cacheClearOpen = true"
              >
                清空缓存
              </v-btn>
              <v-spacer />
              <span v-if="cacheSummary" class="text-caption sdbs-dim">{{ cacheSummary }}</span>
            </div>
            <div class="text-caption sdbs-dim mb-2">
              解析结果的缓存：<b>作品详情</b>、<b>演员档案</b>与 <b>TMDB 身份</b>各一条。
              缓存的后端与有效期<b>跟着宿主走</b>（系统设置 → 缓存）——
              启用 Redis 时与宿主共用同一个实例（本插件独占
              <code>{{ cacheWhere.region }}</code> 区），否则落在进程内内存。
            </div>
            <v-alert
              v-if="cacheWhere.blocked"
              type="warning"
              variant="tonal"
              density="compact"
              class="mb-2"
            >
              站点命中系统「不缓存站点」配置（<code>{{ cacheWhere.system?.no_cache_site_key }}</code>）
              —— 本插件已按系统口径<b>停用缓存</b>，每次解析都会重新抓页面。
            </v-alert>
            <v-alert v-else-if="cacheWhere.disabled" type="warning" variant="tonal" density="compact" class="mb-2">
              插件配置里把缓存有效期设成了 <b>{{ cacheWhere.override_ttl }}</b>（负数即<b>关闭插件缓存</b>）
              —— 每次解析都会重新抓页面。想恢复跟随系统，把「设置 → 站点与请求 → 缓存覆盖」改回 0。
            </v-alert>
            <div v-else class="text-caption sdbs-dim mb-2">
              当前：后端 <b>{{ cacheWhere.backend }}</b>｜有效期 <b>{{ cacheTtlText }}</b>
              （{{ cacheTtlSource }}）｜图片缓存
              <b>{{ cacheWhere.system?.image_cache ? '开' : '关' }}</b>
              （系统「全局图片缓存」{{ cacheWhere.system?.image_cache_days ?? 7 }} 天）
            </div>
            <v-alert v-if="cacheNotice" type="success" variant="tonal" density="compact" class="mb-2">
              {{ cacheNotice }}
            </v-alert>
            <div class="d-flex align-center flex-wrap mb-2" style="gap: 8px">
              <v-text-field
                v-model="cacheKeyword"
                density="compact"
                variant="outlined"
                hide-details
                clearable
                prepend-inner-icon="mdi-magnify"
                placeholder="按片名 / 演员名 / 站点 ID 过滤"
                class="sdbs-lib-search"
                @keyup.enter="loadCache()"
              />
              <v-btn size="small" variant="tonal" color="primary" :loading="cacheLoading" @click="loadCache()">
                查询
              </v-btn>
              <v-btn-toggle
                v-model="cacheKind"
                density="compact"
                variant="outlined"
                divided
                mandatory
                @update:model-value="loadCache()"
              >
                <v-btn size="small" value="all">全部</v-btn>
                <v-btn size="small" value="detail">作品详情</v-btn>
                <v-btn size="small" value="actor">演员档案</v-btn>
                <v-btn size="small" value="tmdb">TMDB 身份</v-btn>
              </v-btn-toggle>
            </div>
            <v-alert v-if="!cacheEntries.length" type="info" variant="tonal" density="compact">
              {{ cacheEmptyText }}
            </v-alert>
            <div v-for="row in cacheEntries" :key="row.key" class="d-flex align-center py-1">
              <v-chip
                size="x-small"
                variant="tonal"
                :color="cacheKindColor(row.kind)"
                class="mr-2"
              >
                {{ row.kind_label || row.kind }}
              </v-chip>
              <span class="text-body-2 flex-grow-1 sdbs-lib-text" :title="row.key">
                {{ row.label || row.key }}
              </span>
              <span v-if="row.ref" class="text-caption sdbs-dim mr-2">{{ row.ref }}</span>
              <span class="text-caption sdbs-dim mr-2">{{ cacheTime(row.cached_at) }}</span>
              <v-btn
                size="x-small"
                variant="text"
                color="error"
                :loading="cacheDeleting === row.key"
                @click="deleteCacheRow(row.key || '')"
              >
                删除
              </v-btn>
            </div>

            <v-dialog v-model="cacheClearOpen" max-width="440">
              <v-card>
                <v-card-title class="text-subtitle-2 pt-3">清空缓存</v-card-title>
                <v-card-text class="text-body-2">
                  将要删除：<b>{{ cacheClearScope }}</b>。
                  <br />
                  缓存只是「省一次抓页面」，<b>删掉不会丢任何数据</b> —— 下次识别 / 搜索会重新解析一遍
                  （站点有风控，短时间大量重建可能触发限流）。只清本插件自己的缓存区，不动宿主与其它插件。
                </v-card-text>
                <v-card-actions>
                  <v-spacer />
                  <v-btn size="small" variant="text" @click="cacheClearOpen = false">取消</v-btn>
                  <v-btn
                    size="small"
                    variant="tonal"
                    color="error"
                    :loading="cacheClearing"
                    @click="clearCacheAll()"
                  >
                    确认清空
                  </v-btn>
                </v-card-actions>
              </v-card>
            </v-dialog>
          </div>
        </template>
      </v-card>
    </div>

    <!-- ── 唯一的搜索框：片名与演员名都收 ─────────────────────── -->
    <v-card variant="outlined" class="pa-3 sdbs-panel">
      <v-text-field
        v-model="keyword"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        prepend-inner-icon="mdi-magnify"
        placeholder="输入短剧片名或演员姓名，例如：女足替补的滚烫夏天 / 魏依珂"
        @keyup.enter="doLookup"
      />
      <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
        <v-btn
          size="small"
          color="primary"
          variant="tonal"
          :loading="searching"
          :disabled="!keyword.trim()"
          @click="doLookup"
        >
          搜索
        </v-btn>
        <v-btn size="small" variant="text" :disabled="!hasResult" @click="clearAll">清空</v-btn>
        <v-spacer />
        <span v-if="hint" class="text-caption sdbs-dim">{{ hint }}</span>
      </div>
    </v-card>

    <v-row dense>
      <!-- ── 作品结果 ─────────────────────────────────────────── -->
      <v-col v-if="hasTitlePanel" cols="12" md="6">
        <v-card variant="outlined" class="pa-3 sdbs-panel">
          <div class="d-flex align-center mb-2">
            <v-icon icon="mdi-movie-search-outline" size="18" class="mr-1" />
            <span class="text-subtitle-2">作品</span>
            <v-spacer />
            <v-progress-circular v-if="titleLoadingId" size="16" width="2" indeterminate />
          </div>

          <!-- 候选列表 -->
          <v-card v-if="titleCandidates.length" variant="tonal" class="pa-2 mt-3">
            <div class="text-caption sdbs-dim mb-1">
              命中 {{ titleCandidates.length }} 条候选，点「识别」看完整详情（按匹配分排序）：
            </div>
            <div
              v-for="candidate in titleCandidates"
              :key="candidate.media_id || candidate.title"
              class="d-flex align-center py-1"
            >
              <v-chip size="x-small" variant="tonal" class="mr-2" :title="`匹配分 ${candidate.score}`">
                {{ candidate.score }}
              </v-chip>
              <v-chip
                v-if="candidate.from"
                size="x-small"
                variant="text"
                :color="candidate.from === 'store' ? 'teal' : 'grey'"
                class="mr-2"
                :title="
                  candidate.from === 'store'
                    ? 'URL 库里已有这条，本次零引擎请求'
                    : '本次刚从搜索引擎发现，已写进 URL 库'
                "
              >
                {{ candidate.from === 'store' ? '库' : '引擎' }}
              </v-chip>
              <span class="text-body-2 flex-grow-1">{{ candidate.title }}</span>
              <v-chip
                v-if="candidate.same_title && candidate.same_title > 1"
                size="x-small"
                variant="text"
                color="orange-darken-2"
                class="ml-1"
                title="站点给这部剧建了多条记录（实测真人版 / AI 版标题一字不差），
                  这条只是其中之一 —— 逐条点「识别」比一比，数据全的那条通常有演员与集数"
              >
                同名 {{ candidate.same_title }} 版
              </v-chip>
              <v-btn
                v-if="candidate.url"
                size="x-small"
                variant="text"
                icon="mdi-open-in-new"
                :href="candidate.url"
                target="_blank"
                rel="noopener"
                title="打开站点页面"
              />
              <v-btn
                size="x-small"
                variant="tonal"
                color="primary"
                :loading="titleLoadingId === candidate.media_id"
                @click="pickTitle(candidate)"
              >
                识别
              </v-btn>
            </div>
          </v-card>

          <!-- 作品卡片 -->
          <v-card v-if="titleRecord" variant="outlined" class="pa-3 mt-3">
            <div class="d-flex" style="gap: 12px">
              <v-img
                :src="proxyImage(titleRecord.poster)"
                width="92"
                height="123"
                aspect-ratio="2/3"
                cover
                class="rounded flex-shrink-0 sdbs-poster"
              />
              <div class="flex-grow-1" style="min-width: 0">
                <div class="text-subtitle-2">{{ titleRecord.title || '（无标题）' }}</div>
                <div class="text-caption sdbs-dim mt-1">{{ titleMeta }}</div>
                <div v-if="titleRecord.tags?.length" class="mt-1">
                  <v-chip
                    v-for="tag in titleRecord.tags"
                    :key="tag"
                    size="x-small"
                    variant="tonal"
                    class="mr-1 mb-1"
                  >
                    {{ tag }}
                  </v-chip>
                </div>
                <div v-if="titleRecord.overview" class="text-caption mt-2 sdbs-clamp">
                  {{ titleRecord.overview }}
                </div>
                <div v-if="titleCast" class="text-caption sdbs-dim mt-2">主演：{{ titleCast }}</div>
                <!-- 同页「推荐短剧」：站点自己给的关联作品，也一并解析出来了 -->
                <div v-if="titleRecord.related?.length" class="mt-2">
                  <span class="text-caption sdbs-dim mr-1">同页推荐：</span>
                  <v-chip
                    v-for="rel in titleRecord.related.slice(0, 8)"
                    :key="rel.media_id || rel.title"
                    size="x-small"
                    variant="tonal"
                    class="mr-1 mb-1"
                    :href="rel.url"
                    target="_blank"
                    rel="noopener"
                  >
                    {{ rel.title }}
                  </v-chip>
                </div>
              </div>
            </div>
            <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
              <v-btn
                v-if="titleRecord.url"
                size="x-small"
                variant="tonal"
                :href="titleRecord.url"
                target="_blank"
                rel="noopener"
                prepend-icon="mdi-open-in-new"
              >
                站点页面
              </v-btn>
              <v-btn size="x-small" variant="text" @click="titleRawOpen = !titleRawOpen">
                {{ titleRawOpen ? '收起原始数据' : '原始数据' }}
              </v-btn>
            </div>
            <pre v-if="titleRawOpen" class="sdbs-pre mt-2">{{ pretty(titleRecord) }}</pre>
          </v-card>

          <v-alert
            v-else-if="titleMessage"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            {{ titleMessage }}
          </v-alert>
        </v-card>
      </v-col>

      <!-- ── 演员结果 ─────────────────────────────────────────── -->
      <v-col v-if="hasActorPanel" cols="12" md="6">
        <v-card variant="outlined" class="pa-3 sdbs-panel">
          <div class="d-flex align-center mb-2">
            <v-icon icon="mdi-account-search-outline" size="18" class="mr-1" />
            <span class="text-subtitle-2">演员</span>
            <v-spacer />
            <v-progress-circular v-if="actorLoadingId" size="16" width="2" indeterminate />
          </div>

          <!-- 候选演员 -->
          <v-card v-if="actorCandidates.length" variant="tonal" class="pa-2 mt-3">
            <div class="text-caption sdbs-dim mb-1">
              命中 {{ actorCandidates.length }} 位，点「看作品」拉取档案与全部作品：
            </div>
            <div
              v-for="candidate in actorCandidates"
              :key="candidate.actor_id || candidate.name"
              class="d-flex align-center py-1"
            >
              <v-chip size="x-small" variant="tonal" class="mr-2" :title="`匹配分 ${candidate.score}`">
                {{ candidate.score }}
              </v-chip>
              <v-chip
                v-if="candidate.from"
                size="x-small"
                variant="text"
                :color="candidate.from === 'store' ? 'teal' : 'grey'"
                class="mr-2"
                :title="
                  candidate.from === 'store'
                    ? 'URL 库里已有这条，本次零引擎请求'
                    : '本次刚从搜索引擎发现，已写进 URL 库'
                "
              >
                {{ candidate.from === 'store' ? '库' : '引擎' }}
              </v-chip>
              <span class="text-body-2 flex-grow-1">{{ candidate.name }}</span>
              <v-btn
                v-if="candidate.url"
                size="x-small"
                variant="text"
                icon="mdi-open-in-new"
                :href="candidate.url"
                target="_blank"
                rel="noopener"
                title="打开演员页"
              />
              <span class="text-caption sdbs-dim mr-2">actor:{{ candidate.actor_id }}</span>
              <v-btn
                size="x-small"
                variant="tonal"
                color="primary"
                :loading="actorLoadingId === candidate.actor_id"
                @click="pickActor(candidate)"
              >
                看作品
              </v-btn>
            </div>
          </v-card>

          <!-- 演员档案 + 作品墙 -->
          <div v-if="actorProfile" class="mt-3">
            <v-card variant="outlined" class="pa-3">
              <div class="d-flex" style="gap: 12px">
                <v-avatar size="64" rounded class="flex-shrink-0">
                  <v-img :src="proxyImage(actorProfile.profile)" cover />
                </v-avatar>
                <div class="flex-grow-1" style="min-width: 0">
                  <div class="text-subtitle-2">
                    {{ actorProfile.name || '（无姓名）' }}
                    <span class="text-caption sdbs-dim ml-2">actor:{{ actorProfile.actor_id }}</span>
                  </div>
                  <div class="text-caption sdbs-dim mt-1">{{ actorMeta }}</div>
                  <div v-if="actorProfile.bio" class="text-caption mt-2 sdbs-clamp">
                    {{ actorProfile.bio }}
                  </div>
                </div>
              </div>
              <div v-if="actorProfile.coactors?.length" class="mt-2">
                <span class="text-caption sdbs-dim mr-1">常合作演员：</span>
                <v-chip
                  v-for="co in actorProfile.coactors.slice(0, 12)"
                  :key="co.id || co.name"
                  size="x-small"
                  variant="tonal"
                  class="mr-1 mb-1"
                >
                  {{ co.name }}
                </v-chip>
              </div>
              <div class="d-flex align-center mt-2 flex-wrap" style="gap: 8px">
                <v-btn
                  v-if="actorProfile.url"
                  size="x-small"
                  variant="tonal"
                  :href="actorProfile.url"
                  target="_blank"
                  rel="noopener"
                  prepend-icon="mdi-open-in-new"
                >
                  演员页
                </v-btn>
                <v-btn size="x-small" variant="text" @click="actorRawOpen = !actorRawOpen">
                  {{ actorRawOpen ? '收起原始数据' : '原始数据' }}
                </v-btn>
              </div>
              <pre v-if="actorRawOpen" class="sdbs-pre mt-2">{{ pretty(actorProfile) }}</pre>
            </v-card>

            <!-- 作品墙 -->
            <div class="text-subtitle-2 mt-3 mb-2">
              <v-icon icon="mdi-movie-open-outline" size="18" class="mr-1" />
              全部作品
              <span class="text-caption sdbs-dim ml-1">共 {{ actorProfile.works?.length || 0 }} 部</span>
            </div>
            <v-row dense>
              <v-col
                v-for="(work, index) in actorProfile.works || []"
                :key="work.media_id || index"
                cols="12" sm="6"
              >
                <v-card variant="outlined" class="pa-2 h-100 d-flex flex-column">
                  <div class="d-flex" style="gap: 8px">
                    <v-img
                      :src="proxyImage(work.poster)"
                      width="60"
                      height="80"
                      aspect-ratio="2/3"
                      cover
                      class="rounded flex-shrink-0 sdbs-poster"
                    />
                    <div class="flex-grow-1" style="min-width: 0">
                      <div class="text-body-2 sdbs-work-title">{{ work.title || '（无标题）' }}</div>
                      <div class="text-caption sdbs-dim mt-1">{{ workMeta(workView(index)) }}</div>
                      <div v-if="workTags(index, work).length" class="mt-1">
                        <v-chip
                          v-for="tag in workTags(index, work)"
                          :key="tag"
                          size="x-small"
                          variant="tonal"
                          class="mr-1 mb-1"
                        >
                          {{ tag }}
                        </v-chip>
                      </div>
                    </div>
                  </div>
                  <v-spacer />
                  <div class="d-flex align-center mt-1">
                    <v-btn
                      v-if="work.url"
                      size="x-small"
                      variant="text"
                      :href="work.url"
                      target="_blank"
                      rel="noopener"
                    >
                      站点
                    </v-btn>
                    <v-btn
                      size="x-small"
                      variant="text"
                      :loading="workLoadingIndex === index"
                      :disabled="workComplete(index, work)"
                      :title="workComplete(index, work)
                        ? '已是作品页那份数据（完整标签 / 首播 / 版权方 / 时长 / 简介 / 剧照）'
                        : '演员页卡片是摘要（标签只印 1~3 个、没有版权方），抓一次详情页补全'"
                      @click="loadWorkDetail(index)"
                    >
                      {{ workComplete(index, work) ? '已补全' : '完整信息' }}
                    </v-btn>
                    <v-spacer />
                    <v-btn size="x-small" variant="text" @click="toggleWorkRaw(index)">
                      {{ openWorks.has(index) ? '收起' : '原始数据' }}
                    </v-btn>
                  </div>
                  <pre v-if="openWorks.has(index)" class="sdbs-pre mt-1">{{ pretty(workView(index)) }}</pre>
                </v-card>
              </v-col>
            </v-row>
          </div>

          <v-alert
            v-else-if="actorMessage"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            {{ actorMessage }}
          </v-alert>
        </v-card>
      </v-col>
    </v-row>

    <!-- ── 设置弹窗 ───────────────────────────────────────────── -->
    <v-dialog v-model="settingsOpen" max-width="1080" scrollable>
      <Config
        v-if="settingsOpen"
        :api="props.api"
        :initial-config="remoteConfig"
        @close="settingsOpen = false"
        @save="onConfigSaved"
      />
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 短剧百科数据源 —— 插件详情面板（联邦暴露名 `./Page`）。
 *
 * 为什么这个插件要从 Vuetify（JSON）改成联邦组件：面板上要放**会回传输入的搜索框**，
 * 而宿主的 JSON 页面只支持静态组件树与「点击 → 调接口」这类无参交互，承载不了输入框。
 *
 * 只有一个搜索框，片名与演员名都收：`/lookup` 用**一次**站外检索同时给出作品候选与
 * 演员候选，再分别喂 `/recognize` 与 `/actor` 拿详情。
 * 结果都以卡片呈现，并保留「原始数据」展开位 —— 卡片是给人看的，
 * 展开是给排障/核对用的，两者看的是同一份后端返回。
 */
import { computed, ref, watch } from 'vue'
import Config from './Config.vue'
import {
  clearCache,
  clearUrls,
  deleteCacheEntry,
  fetchActor,
  fetchCache,
  fetchConfig,
  fetchStatus,
  fetchUrls,
  proxyImage,
  lookupKeyword,
  recognizeTitle,
  resolveApi,
  saveConfig,
} from './api'
import type {
  ActorCandidate,
  ActorProfile,
  CacheEntry,
  CacheStatus,
  MediaRecord,
  PluginApi,
  PluginConfig,
  StatusPayload,
  TitleCandidate,
  UrlRecord,
  UrlsPayload,
  WorkItem,
} from './types'

const props = defineProps<{
  /** 宿主注入的 axios 实例 */
  api?: PluginApi
  /** 插件配置（宿主在详情页会传入） */
  config?: Partial<PluginConfig>
  /** 当前插件实例 ID */
  pluginId?: string
  /** 侧栏全页上下文（本插件不用，保留以兼容宿主传参） */
  navKey?: string
  /** 是否整页留白 */
  full?: boolean
}>()

const emit = defineEmits(['action', 'close'])

const enabled = ref(Boolean(props.config?.enabled))
const toggling = ref(false)
const loading = ref(false)
const configLoading = ref(false)
const settingsOpen = ref(false)
const remoteConfig = ref<Partial<PluginConfig>>({})
const status = ref<StatusPayload | null>(null)

// ── 搜索框（片名 / 演员名共用一个） ──
const keyword = ref('')
const searching = ref(false)
const hint = ref('')

// ── 作品结果 ──
const titleCandidates = ref<TitleCandidate[]>([])
const titleRecord = ref<MediaRecord | null>(null)
const titleMessage = ref('')
const titleRawOpen = ref(false)
const titleLoadingId = ref('')

// ── 演员结果 ──
const actorCandidates = ref<ActorCandidate[]>([])
const actorProfile = ref<ActorProfile | null>(null)
const actorMessage = ref('')
const actorRawOpen = ref(false)
const actorLoadingId = ref('')
/** 已展开原始数据的作品下标（作品可能几十部，逐个展开比一次全铺清爽） */
const openWorks = ref(new Set<number>())
/**
 * 作品墙里**已补全**的作品（下标 → 完整记录）。
 *
 * ⚠️ 演员页的卡片是**摘要视图**：站点在卡片上只印 1~3 个题材标签（实测《失控交易》
 * 卡片上只有「爱情」，而它详情页有 5 个），完整标签只有详情页的 JSON-LD 里才有。
 * 一个演员动辄几十部作品，一次性全抓既不现实也容易撞风控 —— 所以这里按需补：
 * 点卡片上的「完整标签」才抓这一部的详情页，抓到就整条替换进卡片。
 */
const workFull = ref<Record<number, MediaRecord>>({})
/** 正在补全的作品下标（按钮 loading 态） */
const workLoadingIndex = ref<number | null>(null)

// ── URL 库（插件自有数据库） ──
const libraryOpen = ref(false)
const libraryLoading = ref(false)
const libraryKeyword = ref('')
const libraryKind = ref<'all' | 'work' | 'actor'>('all')
const libraryRecords = ref<UrlRecord[]>([])
const libraryStats = ref('')
/** 后端的统计原始值（清空库的范围提示要报得准，不能拿「当前这一页 50 条」当总数） */
const libraryStatsRaw = ref<UrlsPayload['stats']>({})
/** 清库结果的一句话提示 */
const libraryNotice = ref('')
const libraryClearOpen = ref(false)
const libraryClearing = ref(false)
const libraryEmptyText = ref('库里还没有记录 —— 先在上面的搜索框搜一次片名或演员名。')

// ── 缓存管理（后端与有效期跟随宿主；不进宿主的缓存管理页） ──
const cacheOpen = ref(false)
const cacheLoading = ref(false)
const cacheKeyword = ref('')
const cacheKind = ref<'all' | string>('all')
const cacheEntries = ref<CacheEntry[]>([])
/** 后端给的缓存现状（后端类型 / 有效期来源 / 系统开关快照） */
const cacheStatus = ref<CacheStatus | null>(null)
const cacheNotice = ref('')
const cacheClearOpen = ref(false)
const cacheClearing = ref(false)
/** 正在删的那条（按钮 loading 态） */
const cacheDeleting = ref('')
const cacheEmptyText = ref('缓存还是空的 —— 搜一次片名或演员名就会写入。')

const pretty = (value: unknown) => JSON.stringify(value ?? null, null, 2)

/** 把大数字还原成人看得懂的量级（后端给的已经是绝对值：354万 → 3540000） */
function formatCount(value?: number): string {
  if (!value) return ''
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)} 亿`
  if (value >= 10000) return `${Math.round(value / 10000)} 万`
  return String(value)
}

/**
 * 标题栏的缓存 chip。
 *
 * 只报总条数：类型的细分在「缓存管理」里看 —— 这里要的是「有没有在攒东西」。
 */
const cacheChip = computed(() => {
  const cache = status.value?.cache
  if (!cache) return ''
  return `${cache.count ?? cache.detail ?? 0} 条`
})

const storeChip = computed(() => {
  const store = status.value?.store
  if (!store?.total) return ''
  return `${store.total} 条`
})

const titleMeta = computed(() => {
  const record = titleRecord.value
  if (!record) return ''
  const parts: string[] = []
  if (record.year) parts.push(record.year)
  if (record.release_date) parts.push(`首播 ${record.release_date}`)
  if (record.episode_count) parts.push(`共 ${record.episode_count} 集`)
  // ⚠️ 站点给的「时长」是**全集总时长**（77 集共 130 分钟那种），不是单集时长；
  // 旧版把它标成「单集 N 分钟」是错的。单集时长由后端按集数折算给出。
  if (record.duration_minutes) {
    parts.push(
      `全集 ${record.duration_minutes} 分钟`
      + (record.episode_minutes ? `（单集约 ${record.episode_minutes} 分钟）` : ''),
    )
  }
  if (record.studio) parts.push(record.studio)
  if (record.kind) parts.push(record.kind)
  if (record.rating) parts.push(`评分 ${record.rating}`)
  if (record.heat) parts.push(`热度 ${formatCount(record.heat)}`)
  if (record.play_count) parts.push(`播放 ${formatCount(record.play_count)}`)
  if (record.favorite_count) parts.push(`收藏 ${formatCount(record.favorite_count)}`)
  parts.push(`来源 ${record.origin === 'detail' ? '详情页' : '检索结果'}`)
  return parts.join(' ｜ ')
})

const titleCast = computed(() => {
  const actors = titleRecord.value?.actors || []
  if (!actors.length) return ''
  return actors
    .slice(0, 10)
    .map((actor) => (actor.character ? `${actor.name}（饰 ${actor.character}）` : actor.name))
    .join('、')
})

const actorMeta = computed(() => {
  const actor = actorProfile.value
  if (!actor) return ''
  const parts: string[] = []
  if (actor.job_title) parts.push(actor.job_title)
  if (actor.gender) parts.push(`性别 ${actor.gender}`)
  if (actor.nationality) parts.push(actor.nationality)
  parts.push(`作品 ${actor.works_count ?? (actor.works || []).length} 部`)
  return parts.join(' ｜ ')
})

/** 两块结果各自只有「有内容」时才占位；两边都没命中就靠顶部那行 hint 说话 */
const hasTitlePanel = computed(
  () => Boolean(titleCandidates.value.length || titleRecord.value || titleMessage.value),
)
const hasActorPanel = computed(
  () => Boolean(actorCandidates.value.length || actorProfile.value || actorMessage.value),
)
const hasResult = computed(() => hasTitlePanel.value || hasActorPanel.value)

function workMeta(work: WorkItem): string {
  const parts: string[] = []
  if (work.kind) parts.push(work.kind)
  if (work.release_date) parts.push(`首播 ${work.release_date}`)
  if (work.episode_count) parts.push(`${work.episode_count} 集`)
  // 站点给的「时长」是**全集**总时长，不点破会被当成单集时长
  if (work.duration_minutes) {
    parts.push(`全集 ${work.duration_minutes} 分钟` + (work.episode_minutes ? `（单集约 ${work.episode_minutes} 分钟）` : ''))
  }
  if (work.studio) parts.push(work.studio)
  if (work.rating) parts.push(`评分 ${work.rating}`)
  if (work.heat) parts.push(`热度 ${formatCount(work.heat)}`)
  if (work.play_count) parts.push(`播放 ${formatCount(work.play_count)}`)
  return parts.join(' ｜ ') || '—'
}

/** 拉运行状态；失败静默（面板不铺错误，只少一块信息） */
async function load(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  loading.value = true
  try {
    const payload = await fetchStatus(api)
    if (payload) {
      status.value = payload
      enabled.value = Boolean(payload.enabled)
    }
  } finally {
    loading.value = false
  }
}

/** 启用/停用：读当前配置 → 改一个键 → 存回（避免只提交 enabled 把其它键冲掉） */
async function toggleEnabled(value: unknown): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  toggling.value = true
  try {
    const current = await fetchConfig(api)
    const merged: Partial<PluginConfig> = { ...(current?.config || remoteConfig.value) }
    merged.enabled = Boolean(value)
    const report = await saveConfig(api, merged)
    if (!report?.success) {
      enabled.value = !value
      titleMessage.value = report?.message || '切换启用状态失败'
      return
    }
    remoteConfig.value = report.config || merged
    await load()
  } finally {
    toggling.value = false
  }
}

/**
 * 唯一的搜索动作：一个词同时试「片名」与「演员名」。
 *
 * 后端 `/lookup` 只打一次引擎（两次会被最小间隔挡掉一次），回来的两块结果各自渲染；
 * 每块只有一条候选时直接取详情 —— 一条候选没什么可选的。
 */
async function doLookup(): Promise<void> {
  const api = resolveApi(props)
  const query = keyword.value.trim()
  if (!api || !query) return
  searching.value = true
  hint.value = ''
  resetTitle()
  resetActor()
  try {
    const report = await lookupKeyword(api, query)
    const titles = report?.titles || []
    const actors = report?.actors || []
    titleCandidates.value = titles
    actorCandidates.value = actors
    if (!titles.length && !actors.length) {
      hint.value = report?.message || `没搜到「${query}」。`
      return
    }
    const parts: string[] = []
    if (titles.length) parts.push(`作品 ${titles.length} 条候选`)
    if (actors.length) parts.push(`演员 ${actors.length} 位候选`)
    hint.value = parts.join(' ｜ ')
    if (titles.length === 1) await pickTitle(titles[0])
    if (actors.length === 1) await pickActor(actors[0])
  } finally {
    searching.value = false
  }
}

async function pickTitle(candidate: TitleCandidate): Promise<void> {
  const api = resolveApi(props)
  if (!api || !candidate.media_id) return
  titleLoadingId.value = candidate.media_id
  titleMessage.value = ''
  titleRawOpen.value = false
  try {
    const report = await recognizeTitle(api, { media_id: candidate.media_id })
    if (report?.success && report.record) {
      titleRecord.value = report.record
    } else {
      titleMessage.value = report?.message || '取详情失败（多半是站点风控，稍后再试）'
    }
  } finally {
    titleLoadingId.value = ''
  }
}

/** 只清「作品」那一块的状态（搜新词时复用） */
function resetTitle(): void {
  titleCandidates.value = []
  titleRecord.value = null
  titleMessage.value = ''
  titleRawOpen.value = false
  titleLoadingId.value = ''
}

/** 只清「演员」那一块的状态（搜新词时复用） */
function resetActor(): void {
  actorCandidates.value = []
  actorProfile.value = null
  actorMessage.value = ''
  actorRawOpen.value = false
  actorLoadingId.value = ''
  openWorks.value = new Set<number>()
  workFull.value = {}
  workLoadingIndex.value = null
}

async function pickActor(candidate: ActorCandidate): Promise<void> {
  const api = resolveApi(props)
  if (!api || !candidate.actor_id) return
  actorLoadingId.value = candidate.actor_id
  actorMessage.value = ''
  actorRawOpen.value = false
  openWorks.value = new Set<number>()
  try {
    const report = await fetchActor(api, { actor_id: candidate.actor_id })
    if (report?.success && report.actor) {
      actorProfile.value = report.actor
    } else {
      actorMessage.value = report?.message || '拉演员页失败（多半是站点风控，稍后再试）'
    }
  } finally {
    actorLoadingId.value = ''
  }
}

/** 清空按钮：搜索词与两块结果一起清掉 */
function clearAll(): void {
  keyword.value = ''
  hint.value = ''
  resetTitle()
  resetActor()
}

/**
 * 卡片上真正用来渲染的那条记录：补全过就用完整记录，否则用演员页卡片的摘要。
 *
 * 两者字段一致（都出自同一套解析），只是完整记录多出标签 / 简介 / 剧照这些
 * 详情页才有的内容。
 */
function workView(index: number): WorkItem {
  const works = actorProfile.value?.works || []
  return (workFull.value[index] as WorkItem | undefined) ?? works[index] ?? {}
}

/**
 * 这部作品是否已是「作品页那份数据」。
 *
 * 后端**一贯**把全部作品补过详情（`origin === 'detail'`），这时面板不必再点
 * 「完整信息」—— 载荷里就是完整记录；只有 `enrich=0` 的老缓存 / 手动跳过时才需要
 * 按需补（点哪部补哪部）。
 */
function workComplete(index: number, work?: WorkItem): boolean {
  return Boolean(workFull.value[index]) || work?.origin === 'detail'
}

/**
 * 卡片上的标签：已是完整记录就全给，摘要则**照旧只给卡片上那 1~3 个**。
 *
 * 卡片印多少就是多少，不补齐也不假装 —— 摘要里没有的东西不能凭空造。
 */
function workTags(index: number, work: WorkItem): string[] {
  const tags = (workFull.value[index]?.tags ?? work.tags) || []
  return workComplete(index, work) ? tags : tags.slice(0, 3)
}

/**
 * 抓一部作品的详情页，把卡片补成完整记录（按需，一部一次请求）。
 *
 * 只在后端没补全时才有意义：演员页作品卡只印 1~3 个题材标签（《失控交易》只有
 * 「爱情」，详情页却有 5 个）。后端一贯全补，这个按钮是 `enrich=0` 老缓存时的兜底。
 */
async function loadWorkDetail(index: number): Promise<void> {
  const api = resolveApi(props)
  const work = (actorProfile.value?.works || [])[index]
  if (!api || !work?.media_id || workComplete(index, work)) return
  workLoadingIndex.value = index
  try {
    const report = await recognizeTitle(api, { media_id: work.media_id })
    if (report?.success && report.record) {
      workFull.value = { ...workFull.value, [index]: report.record }
    }
  } finally {
    workLoadingIndex.value = null
  }
}

function toggleWorkRaw(index: number): void {
  const next = new Set(openWorks.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  openWorks.value = next
}

// ── URL 库操作 ──

function toggleLibrary(): void {
  libraryOpen.value = !libraryOpen.value
  if (libraryOpen.value) void loadLibrary()
}

/**
 * 读 URL 库。
 *
 * 不给关键词时回最近入库的记录（这就是「库现在长什么样」），给了就按关键词查
 * （键 / 标题 / 命中词任一命中都算）；类型过滤走后端参数，前端不自己筛 ——
 * 免得两边的归一化规则不一致。
 */
async function loadLibrary(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  libraryLoading.value = true
  libraryNotice.value = ''
  try {
    const query = libraryKeyword.value.trim()
    const report = await fetchUrls(api, {
      keyword: query,
      kind: libraryKind.value === 'all' ? '' : libraryKind.value,
    })
    if (!report?.success) {
      libraryRecords.value = []
      libraryStats.value = ''
      libraryStatsRaw.value = {}
      libraryEmptyText.value = report?.message || 'URL 库暂时读不出来（插件数据库未就绪？）'
      return
    }
    libraryRecords.value = report.records || []
    const stats = report.stats || {}
    libraryStatsRaw.value = stats
    libraryStats.value = `共 ${stats.total ?? 0} 条（作品 ${stats.work ?? 0} / 演员 ${stats.actor ?? 0}，关键词 ${stats.keywords ?? 0} 个）`
    libraryEmptyText.value = query
      ? `库里没有「${query}」——换个完整片名或演员全名，或先在上面的搜索框搜一次。`
      : '库里还没有记录 —— 先在上面的搜索框搜一次片名或演员名。'
  } finally {
    libraryLoading.value = false
  }
}

/**
 * 一行记录右侧的补充信息。
 *
 * 正常情况下「键＝它自己的名字」，没什么好显示的；只有历史遗留行（键落在片名 / 搜索词上）
 * 或「命中词与名字不同」时才标出来 —— 用户看这一列就知道这条是搜哪个词带出来的。
 */
function rowKeyInfo(row: UrlRecord): string {
  const key = String(row.keyword || '')
  const name = String(row.label || '')
  const trigger = String(row.display || '')
  const parts: string[] = []
  if (key && key !== name) parts.push(`键 ${key}`)
  if (trigger && trigger !== key && trigger !== name) parts.push(`命中词 ${trigger}`)
  return parts.join('｜')
}

/** 清空范围：跟着当前的关键词 / 类型筛选走，面板上先说清楚要删什么 */
const libraryClearScope = computed(() => {
  const query = libraryKeyword.value.trim()
  const stats = libraryStatsRaw.value || {}
  if (query) return `「${query}」相关的记录`
  if (libraryKind.value === 'actor') return `全部 ${stats.actor ?? 0} 条演员记录`
  if (libraryKind.value === 'work') return `全部 ${stats.work ?? 0} 条作品记录`
  return `整库 ${stats.total ?? 0} 条记录`
})

/** 清库（后端会把「最近问过引擎」的时间戳一起清掉，所以清完马上就能重搜） */
async function clearLibrary(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  libraryClearing.value = true
  try {
    const report = await clearUrls(api, {
      keyword: libraryKeyword.value.trim(),
      kind: libraryKind.value === 'all' ? '' : libraryKind.value,
    })
    libraryClearOpen.value = false
    if (!report?.success) {
      libraryEmptyText.value = report?.message || '清库失败（后端没有响应）'
      return
    }
    await loadLibrary()
    libraryNotice.value = `${report.message || '已清空'}；再搜一次就会重新发现。`
  } finally {
    libraryClearing.value = false
  }
}

watch(libraryKind, () => {
  if (libraryOpen.value) void loadLibrary()
})

// ── 缓存管理操作 ──

/** 缓存现状：优先用 `/cache` 带回来的（最新），退回 `/status` 的 */
const cacheWhere = computed<CacheStatus>(() => cacheStatus.value || status.value?.cache || {})

/** 顶部统计：共 N 条（作品 x / 演员 y / TMDB z） */
const cacheSummary = computed(() => {
  const where = cacheWhere.value
  const kinds = where.kinds || {}
  const total = where.count ?? 0
  if (!total) return ''
  const parts = [`作品 ${kinds.detail ?? 0}`, `演员 ${kinds.actor ?? 0}`]
  if (kinds.tmdb) parts.push(`TMDB ${kinds.tmdb}`)
  return `共 ${total} 条（${parts.join(' / ')}）`
})

/** 有效期的人话版本（秒 → 小时） */
const cacheTtlText = computed(() => {
  const ttl = Number(cacheWhere.value.ttl || 0)
  if (!ttl) return '未生效'
  if (ttl < 3600) return `${ttl} 秒`
  const hours = ttl / 3600
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} 小时`
})

/** 有效期是从哪来的 —— 面板必须说清楚「这个值是系统哪个开关给的」 */
const cacheTtlSource = computed(() => {
  const where = cacheWhere.value
  if (where.disabled) return `插件配置关闭（cache_ttl = ${where.override_ttl ?? -1}）`
  const meta = Number(where.system?.meta_expire_hours || 0)
  if (where.ttl_source === 'plugin') return `插件配置覆盖（${where.override_ttl ?? 0} 秒）`
  if (where.ttl_source === 'system') return `系统设置「缓存有效期」= ${meta} 小时`
  return '系统自动（未设有效期：普通 24 小时 / 大内存 72 小时）'
})

/** 清空范围：跟着当前的类型筛选走 */
const cacheClearScope = computed(() => {
  if (!cacheWhere.value.blocked && cacheKind.value !== 'all') {
    const label = cacheWhere.value.kind_labels?.[cacheKind.value] || cacheKind.value
    return `全部「${label}」缓存`
  }
  return `本插件的全部缓存（${cacheWhere.value.count ?? 0} 条）`
})

/** 类型 → 颜色（与 URL 库那套 chip 的配色习惯一致） */
function cacheKindColor(kind?: string): string {
  if (kind === 'actor') return 'purple'
  if (kind === 'tmdb') return 'teal'
  return 'primary'
}

/** 写入时间（后端给的是秒级时间戳） */
function cacheTime(ts?: number): string {
  if (!ts) return ''
  const date = new Date(ts * 1000)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function toggleCache(): void {
  cacheOpen.value = !cacheOpen.value
  if (cacheOpen.value) void loadCache()
}

/**
 * 读缓存清单。
 *
 * 过滤走后端参数（类型 + 关键词），前端不自己筛 —— 与 URL 库那边同一个理由：
 * 免得两边的键 / 归一化规则不一致。
 */
async function loadCache(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  cacheLoading.value = true
  cacheNotice.value = ''
  try {
    const query = cacheKeyword.value.trim()
    const report = await fetchCache(api, {
      keyword: query,
      kind: cacheKind.value === 'all' ? '' : cacheKind.value,
    })
    if (!report?.success) {
      cacheEntries.value = []
      cacheEmptyText.value = report?.message || '缓存读不出来（宿主缓存后端未就绪？）'
      return
    }
    cacheEntries.value = report.data || []
    cacheStatus.value = report.cache || null
    cacheEmptyText.value = query
      ? `缓存里没有「${query}」——换个完整片名 / 演员名，或站点 ID 试试。`
      : '缓存还是空的 —— 搜一次片名或演员名就会写入。'
  } finally {
    cacheLoading.value = false
  }
}

/** 删一条缓存（键如 `detail:60017`） */
async function deleteCacheRow(key: string): Promise<void> {
  if (!key) return
  const api = resolveApi(props)
  if (!api) return
  cacheDeleting.value = key
  try {
    const report = await deleteCacheEntry(api, key)
    if (!report?.success) {
      cacheNotice.value = report?.message || '删除失败（后端没有响应）'
      return
    }
    await loadCache()
    cacheNotice.value = report.message || '已删除'
    void load()
  } finally {
    cacheDeleting.value = ''
  }
}

/** 清空缓存（可选只清当前类型） */
async function clearCacheAll(): Promise<void> {
  const api = resolveApi(props)
  if (!api) return
  cacheClearing.value = true
  try {
    const report = await clearCache(api, cacheKind.value === 'all' ? '' : cacheKind.value)
    cacheClearOpen.value = false
    if (!report?.success) {
      cacheEmptyText.value = report?.message || '清空失败（后端没有响应）'
      return
    }
    await loadCache()
    cacheNotice.value = report.message || '已清空'
    void load()
  } finally {
    cacheClearing.value = false
  }
}

/** 先取配置再挂载弹窗：Config 只在 onMounted 读一次 initialConfig，先挂载会拿到空快照 */
async function openSettings(): Promise<void> {
  const api = resolveApi(props)
  configLoading.value = true
  try {
    if (api) {
      const report = await fetchConfig(api)
      if (report?.config) remoteConfig.value = report.config
    }
  } finally {
    configLoading.value = false
  }
  settingsOpen.value = true
}

async function onConfigSaved(config?: Partial<PluginConfig>): Promise<void> {
  if (config) remoteConfig.value = config
  settingsOpen.value = false
  await load()
}

load()
</script>

<style scoped>
.sdbs-root {
  min-width: 0;
}
/* 详情弹窗里的 switch 会带默认的外边距，压紧一点 */
.sdbs-switch {
  margin: 0;
  flex: 0 0 auto;
}
.sdbs-dim {
  opacity: 0.7;
}
.sdbs-panel {
  height: 100%;
}
.sdbs-poster {
  background-color: rgba(128, 128, 128, 0.12);
}
/* 简介最多三行，避免一条简介把整列撑开 */
.sdbs-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.sdbs-work-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
/* URL 库 / 缓存：大屏并排各占一半（与宿主结果区的 md 断点一致），窄屏上下堆叠 */
.sdbs-duo {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-bottom: 4px;
}
@media (min-width: 960px) {
  .sdbs-duo {
    grid-template-columns: 1fr 1fr;
    align-items: start;
  }
}
/* 折叠卡片头：整行可点，悬停有反馈 */
.sdbs-fold {
  cursor: pointer;
  user-select: none;
}
.sdbs-fold:hover {
  background-color: rgba(128, 128, 128, 0.08);
}
/* URL 库：关键词输入框限宽，记录行的标题可省略号截断（地址可能很长） */
.sdbs-lib-search {
  max-width: 320px;
  min-width: 200px;
}.sdbs-lib-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 原始数据块：等宽、可横向滚动、限高避免长 JSON 顶掉整页 */
.sdbs-pre {
  margin: 0;
  padding: 8px;
  max-height: 260px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre;
  border-radius: 6px;
  background-color: rgba(128, 128, 128, 0.12);
}
</style>
