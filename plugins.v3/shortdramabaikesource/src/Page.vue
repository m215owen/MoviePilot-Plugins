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

    <!-- ── 缓存 与 URL 库：并排各占一半（两张常开、等高、内部各自滚动） ─── -->
    <div class="sdbs-duo">
      <!-- ── URL 库（插件自有数据库；库里只存 URL，不存解析结果） ── -->
      <v-card variant="outlined" class="sdbs-panel sdbs-col">
        <div class="d-flex align-center flex-wrap pa-3 pb-2" style="gap: 8px">
          <v-icon icon="mdi-database-outline" size="18" />
          <span class="text-subtitle-2">URL 库</span>
          <v-chip v-if="storeChip" size="x-small" variant="tonal" color="teal">{{ storeChip }}</v-chip>
          <v-spacer />
          <span v-if="libraryStats" class="text-caption sdbs-dim">{{ libraryStats }}</span>
        </div>
        <v-divider />
        <div class="pa-3 pt-2 d-flex flex-column flex-grow-1">
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
            <v-btn-toggle v-model="libraryKind" density="compact" variant="outlined" divided mandatory>
              <v-btn size="small" value="all">全部</v-btn>
              <v-btn size="small" value="work">作品</v-btn>
              <v-btn size="small" value="actor">演员</v-btn>
            </v-btn-toggle>
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
          </div>
          <v-alert v-if="!libraryRecords.length" type="info" variant="tonal" density="compact">
            {{ libraryEmptyText }}
          </v-alert>
          <div class="sdbs-scroll">
            <div
              v-for="row in libraryRecords"
              :key="`${row.kind}:${row.url}`"
            >
              <div class="d-flex align-center py-1">
                <v-chip
                  size="x-small"
                  variant="tonal"
                  :color="row.kind === 'actor' ? 'purple' : 'primary'"
                  class="mr-2"
                >
                  {{ row.kind === 'actor' ? '演员' : '作品' }}
                </v-chip>
                <span
                  class="text-body-2 flex-grow-1 sdbs-lib-text sdbs-clickable"
                  :title="`点一下在下方展开${row.kind === 'actor' ? '这位演员' : '这部作品'}的内容`"
                  @click="toggleLibraryRow(row)"
                >
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
                <v-btn
                  size="x-small"
                  variant="text"
                  :icon="libraryOpenKey === rowId(row) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                  :title="libraryOpenKey === rowId(row) ? '收起' : '展开这条记录的内容'"
                  @click="toggleLibraryRow(row)"
                />
              </div>

              <!-- 展开区：库里只有 URL，所以这一下是真的抓页面（抓到即进缓存） -->
              <div
                v-if="libraryExpanded && libraryExpanded.id === rowId(row)"
                class="sdbs-expand mb-2"
              >
                <div class="text-caption sdbs-dim mb-1">{{ libraryMetaLine(row) }}</div>
                <div v-if="libraryExpanded.loading" class="d-flex align-center py-2">
                  <v-progress-circular size="16" width="2" indeterminate class="mr-2" />
                  <span class="text-caption sdbs-dim">正在抓页面（首次约 1~3 秒，抓到即进缓存）…</span>
                </div>
                <RecordCard
                  v-else-if="libraryExpanded.record"
                  :record="libraryExpanded.record"
                  :api="props.api"
                  :extra="`URL 库 · ${row.origin === 'page' ? '页面顺带' : '引擎'}`"
                />
                <ActorCard
                  v-else-if="libraryExpanded.actor"
                  :profile="libraryExpanded.actor"
                  :api="props.api"
                  compact
                />
                <v-alert
                  v-else-if="libraryExpanded.message"
                  type="warning"
                  variant="tonal"
                  density="compact"
                >
                  {{ libraryExpanded.message }}
                </v-alert>
              </div>
            </div>
          </div>
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
      </v-card>

      <!-- ── 缓存管理（后端与有效期跟随宿主，但不进宿主的缓存管理页） ── -->
      <v-card variant="outlined" class="sdbs-panel sdbs-col">
        <div class="d-flex align-center flex-wrap pa-3 pb-2" style="gap: 8px">
          <v-icon icon="mdi-cached" size="18" />
          <span class="text-subtitle-2">缓存管理</span>
          <v-chip v-if="cacheChip" size="x-small" variant="tonal" color="secondary">{{ cacheChip }}</v-chip>
          <v-spacer />
          <span v-if="cacheSummary" class="text-caption sdbs-dim">{{ cacheSummary }}</span>
        </div>
        <v-divider />
        <div class="pa-3 pt-2 d-flex flex-column flex-grow-1">
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
              :disabled="cacheLoading || cacheClearing || !cacheTotal"
              @click="cacheClearOpen = true"
            >
              清空缓存
            </v-btn>
            <v-spacer />
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
          </div>
          <v-alert v-if="!cacheEntries.length" type="info" variant="tonal" density="compact">
            {{ cacheEmptyText }}
          </v-alert>
          <div class="sdbs-scroll">
            <div v-for="row in cacheEntries" :key="row.key">
              <!-- 一条主记录一行；挂它的附属记录（同一部作品的 TMDB 身份）缩进跟在下面 -->
              <div v-for="(item, position) in rowsOf(row)" :key="item.key">
                <div class="d-flex align-center py-1" :class="{ 'sdbs-attached': position > 0 }">
                  <v-icon
                    v-if="position > 0"
                    icon="mdi-subdirectory-arrow-right"
                    size="14"
                    class="mr-1 sdbs-dim"
                  />
                  <v-chip
                    size="x-small"
                    variant="tonal"
                    :color="cacheKindColor(item.kind)"
                    class="mr-2"
                  >
                    {{ item.kind_label || item.kind }}
                  </v-chip>
                  <span
                    class="text-body-2 flex-grow-1 sdbs-lib-text sdbs-clickable"
                    :title="item.key"
                    @click="toggleCacheRow(item)"
                  >
                    {{ item.label || item.key }}
                  </span>
                  <span v-if="item.ref" class="text-caption sdbs-dim mr-2">{{ item.ref }}</span>
                  <span class="text-caption sdbs-dim mr-2">{{ cacheTime(item.cached_at) }}</span>
                  <v-btn
                    size="x-small"
                    variant="text"
                    color="error"
                    :loading="cacheDeleting === item.key"
                    @click="deleteCacheRow(item.key || '')"
                  >
                    删除
                  </v-btn>
                  <v-btn
                    size="x-small"
                    variant="text"
                    :icon="cacheOpenKey === item.key ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                    :title="cacheOpenKey === item.key ? '收起' : '展开这条缓存里的内容'"
                    @click="toggleCacheRow(item)"
                  />
                </div>

                <!-- 展开区：这条缓存里到底存了什么（与搜索卡片同一套渲染） -->
                <div v-if="cacheExpanded && cacheExpanded.key === item.key" class="sdbs-expand mb-2">
                  <div class="text-caption sdbs-dim mb-1">{{ cacheMetaLine(item) }}</div>
                  <div v-if="cacheExpanded.loading" class="d-flex align-center py-2">
                    <v-progress-circular size="16" width="2" indeterminate class="mr-2" />
                    <span class="text-caption sdbs-dim">正在读取缓存内容…</span>
                  </div>
                  <template v-else-if="cacheExpanded.payload">
                    <v-alert
                      v-if="cacheExpanded.message"
                      type="warning"
                      variant="tonal"
                      density="compact"
                    >
                      {{ cacheExpanded.message }}
                    </v-alert>
                    <template v-else>
                      <div v-if="cacheExpanded.payload.summary" class="text-caption sdbs-dim mb-2">
                        {{ cacheExpanded.payload.summary }}
                      </div>
                      <RecordCard
                        v-if="cacheExpanded.record"
                        :record="cacheExpanded.record"
                        :api="props.api"
                      />
                      <ActorCard
                        v-else-if="cacheExpanded.actor"
                        :profile="cacheExpanded.actor"
                        :api="props.api"
                        compact
                      />
                      <div class="d-flex align-center mb-1 flex-wrap" style="gap: 8px">
                        <v-btn size="x-small" variant="text" @click="cacheRawOpen = !cacheRawOpen">
                          {{ cacheRawOpen ? '收起缓存原文' : '缓存原文' }}
                        </v-btn>
                        <span class="text-caption sdbs-dim">
                          缓存里那份未投影的解析结果（含 tmdb_identity / stills 等内部字段）
                        </span>
                      </div>
                      <pre v-if="cacheRawOpen" class="sdbs-pre">{{ pretty(cacheExpanded.payload.data) }}</pre>
                    </template>
                  </template>
                </div>
              </div>
            </div>
          </div>
          <div v-if="cacheMoreText" class="text-caption sdbs-dim mt-1">{{ cacheMoreText }}</div>
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
      <!-- 只有一块结果时独占整行 —— 固定 md=6 会让单块结果右边空出一半 -->
      <v-col v-if="hasTitlePanel" cols="12" :md="hasActorPanel ? 6 : 12">
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

          <!-- 作品卡片（与展开区共用同一个组件：点开看到的和搜出来看到的一模一样） -->
          <div v-if="titleRecord" class="mt-3">
            <RecordCard :record="titleRecord" :api="props.api" />
          </div>

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
      <!-- 同上：只有演员结果时占满整行 -->
      <v-col v-if="hasActorPanel" cols="12" :md="hasTitlePanel ? 6 : 12">
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

          <!-- 演员档案 + 作品墙（与展开区共用同一个组件） -->
          <div v-if="actorProfile" class="mt-3">
            <ActorCard :profile="actorProfile" :api="props.api" />
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
import ActorCard from './ActorCard.vue'
import Config from './Config.vue'
import RecordCard from './RecordCard.vue'
import {
  clearCache,
  clearUrls,
  deleteCacheEntry,
  fetchActor,
  fetchCache,
  fetchCacheEntry,
  fetchConfig,
  fetchStatus,
  fetchUrls,
  lookupKeyword,
  recognizeTitle,
  resolveApi,
  saveConfig,
} from './api'
import { pretty } from './format'
import type {
  ActorCandidate,
  ActorProfile,
  CacheDetailPayload,
  CacheEntry,
  CacheStatus,
  MediaRecord,
  PluginApi,
  PluginConfig,
  StatusPayload,
  TitleCandidate,
  UrlRecord,
  UrlsPayload,
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
const titleLoadingId = ref('')

// ── 演员结果 ──
const actorCandidates = ref<ActorCandidate[]>([])
const actorProfile = ref<ActorProfile | null>(null)
const actorMessage = ref('')
const actorLoadingId = ref('')

// ── URL 库（插件自有数据库） ──
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
/** 本次铺出来的**条目数**（后端 `returned`：合并后的行把附属条目也算进去） */
const cacheShown = ref(0)

// ── 展开区：点名字就地看内容（两个列表各一条手风琴，展开结果缓存复用） ──
/** 当前展开的缓存条目键（同一时刻只开一条：作品卡 / 演员卡都不短） */
const cacheOpenKey = ref('')
/** 已取回来的缓存内容（键 → 载荷）；收起再展开直接复用，不重复请求 */
const cacheOpenData = ref<Record<string, CacheDetailPayload>>({})
/** 正在取的那条（loading 态） */
const cacheOpenLoading = ref('')
/** 「缓存原文」开关：显示缓存里那份**未投影**的解析结果 */
const cacheRawOpen = ref(false)
/** 当前展开的 URL 库记录 id（`kind:站点ID`） */
const libraryOpenKey = ref('')
/** 已抓回来的页面内容（id → 作品 / 演员 / 错误） */
const libraryOpenData = ref<
  Record<string, { record?: MediaRecord; actor?: ActorProfile; error?: string }>
>({})
/** 正在抓的那条（loading 态） */
const libraryOpenLoading = ref('')

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

/** 两块结果各自只有「有内容」时才占位；两边都没命中就靠顶部那行 hint 说话 */
const hasTitlePanel = computed(
  () => Boolean(titleCandidates.value.length || titleRecord.value || titleMessage.value),
)
const hasActorPanel = computed(
  () => Boolean(actorCandidates.value.length || actorProfile.value || actorMessage.value),
)
const hasResult = computed(() => hasTitlePanel.value || hasActorPanel.value)

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
  titleLoadingId.value = ''
}

/** 只清「演员」那一块的状态（搜新词时复用） */
function resetActor(): void {
  actorCandidates.value = []
  actorProfile.value = null
  actorMessage.value = ''
  actorLoadingId.value = ''
}

async function pickActor(candidate: ActorCandidate): Promise<void> {
  const api = resolveApi(props)
  if (!api || !candidate.actor_id) return
  actorLoadingId.value = candidate.actor_id
  actorMessage.value = ''
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

// ── URL 库操作 ──

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
    // 列表重拉过，展开区里可能已经是另一批记录 —— 一并收掉，免得显示已删掉的内容
    libraryOpenKey.value = ''
    libraryOpenData.value = {}
    libraryOpenLoading.value = ''
    const stats = report.stats || {}
    libraryStatsRaw.value = stats
    libraryStats.value = `作品 ${stats.work ?? 0} / 演员 ${stats.actor ?? 0}｜关键词 ${stats.keywords ?? 0} 个`
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
  void loadLibrary()
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
  return parts.join(' / ')
})

/**
 * 当前筛选下后端报的总条数。
 *
 * 「清空缓存」按它决定能不能点 —— 不能拿 `cacheEntries.length`：列表空可能只是
 * 这一页没数据（或筛选后为空），而总量仍是判断「有没有东西可清」的唯一依据。
 */
const cacheTotal = computed(() => Number(cacheWhere.value.count ?? 0))

/**
 * 列表被截断时的一句话提示。
 *
 * 后端一次最多回 200 条（按写入时间倒序），超出部分不铺出来 —— 面板不假装
 * 「这就是全部」，老老实实说清楚还剩多少、怎么查到。
 *
 * ⚠️ 拿后端报的 `returned`（**条目数**）比，不能拿 `cacheEntries.length`（**行数**）：
 * 同一部作品的两条缓存会被合并成一行，行数天然少于条目数。
 */
const cacheMoreText = computed(() => {
  const total = cacheTotal.value
  const shown = cacheShown.value
  if (!total || !shown || shown >= total) return ''
  return `列表按写入时间倒序显示 ${shown} 条（共 ${total} 条）—— 用上面的框按片名 / 演员名 / 站点 ID 过滤。`
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
      cacheShown.value = 0
      cacheEmptyText.value = report?.message || '缓存读不出来（宿主缓存后端未就绪？）'
      return
    }
    cacheEntries.value = report.data || []
    cacheShown.value = Number(report.returned ?? cacheEntries.value.length)
    // 同上：列表重拉过就收掉展开区（清空 / 删除后不该还挂着那条的内容）
    cacheOpenKey.value = ''
    cacheOpenData.value = {}
    cacheOpenLoading.value = ''
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

// ── 展开区：点名字就地看内容 ──

/**
 * 缓存列表里一行要渲染的条目：主条目 + 挂它的附属条目。
 *
 * TMDB 身份是按「片名 + 年份」单独建键的，后端已按片名把它挂到作品详情这条下面
 * （``attached``），面板跟着缩进铺出来 —— 同一部剧不再占两行。
 */
function rowsOf(row: CacheEntry): CacheEntry[] {
  return [row, ...(row.attached || [])]
}

/** 一条 URL 库记录的身份：同一页面只留一条记录，所以 kind + 站点 ID 就能唯一定位 */
function rowId(row: UrlRecord): string {
  return `${row.kind || ''}:${row.native_id || row.url || ''}`
}

/**
 * 缓存展开区要渲染的东西（同一时刻只展开一条，所以是一个单值 computed）。
 *
 * 后端已经把缓存内容按类型拆好了：`record`（作品投影）/ `actor`（演员投影）/
 * `data`（原始解析结果）—— 这里只做「渲染哪一块」的分发，不再解析字段。
 */
const cacheExpanded = computed(() => {
  const key = cacheOpenKey.value
  if (!key) return null
  const payload = cacheOpenData.value[key] || null
  return {
    key,
    loading: cacheOpenLoading.value === key,
    payload,
    record: payload?.record || null,
    actor: payload?.actor || null,
    message: payload && payload.success === false ? payload.message || '这条缓存读不出来' : '',
  }
})

/** URL 库展开区同理：作品 / 演员 / 错误三选一 */
const libraryExpanded = computed(() => {
  const id = libraryOpenKey.value
  if (!id) return null
  const data = libraryOpenData.value[id]
  return {
    id,
    loading: libraryOpenLoading.value === id,
    record: data?.record || null,
    actor: data?.actor || null,
    message: data?.error || '',
  }
})

/**
 * 点缓存条目的名字：在它下方展开「这条缓存里到底存了什么」。
 *
 * 内容按需向后端取一次（``GET /cache/{key}``），取到就留着 —— 反复收放不重复请求。
 */
async function toggleCacheRow(row: CacheEntry): Promise<void> {
  const key = String(row.key || '')
  if (!key) return
  if (cacheOpenKey.value === key) {
    cacheOpenKey.value = ''
    return
  }
  cacheOpenKey.value = key
  cacheRawOpen.value = false
  if (cacheOpenData.value[key]) return
  const api = resolveApi(props)
  if (!api) return
  cacheOpenLoading.value = key
  try {
    const report = await fetchCacheEntry(api, key)
    cacheOpenData.value = {
      ...cacheOpenData.value,
      [key]: report || { success: false, message: '读不出这条缓存（接口没有响应）' },
    }
  } finally {
    cacheOpenLoading.value = ''
  }
}

/**
 * 点 URL 库条目的名字：在它下方展开「这个页面是什么」。
 *
 * ⚠️ 库里只存 URL、不存解析结果（站点内容随时在变），所以这一下是**真的抓一次页面**：
 * 作品走 `/recognize`、演员走 `/actor` —— 与搜索框里点「识别」「看作品」同一条路。
 * 结果留在展开区里（同时进了插件缓存），反复收放不重复抓。
 */
async function toggleLibraryRow(row: UrlRecord): Promise<void> {
  const id = rowId(row)
  if (libraryOpenKey.value === id) {
    libraryOpenKey.value = ''
    return
  }
  libraryOpenKey.value = id
  if (libraryOpenData.value[id]) return
  const api = resolveApi(props)
  if (!api) return
  const nativeId = String(row.native_id || '')
  if (!nativeId) {
    libraryOpenData.value = {
      ...libraryOpenData.value,
      [id]: { error: '这条记录没有站点 ID（老记录，或页面标题里没带），只能点「打开」去站点看。' },
    }
    return
  }
  libraryOpenLoading.value = id
  try {
    if (row.kind === 'actor') {
      const report = await fetchActor(api, { actor_id: nativeId })
      libraryOpenData.value = {
        ...libraryOpenData.value,
        [id]: report?.success && report.actor
          ? { actor: report.actor }
          : { error: report?.message || '抓演员页失败（多半是站点风控，稍后再试）' },
      }
    } else {
      const report = await recognizeTitle(api, { media_id: nativeId })
      libraryOpenData.value = {
        ...libraryOpenData.value,
        [id]: report?.success && report.record
          ? { record: report.record }
          : { error: report?.message || '抓作品页失败（多半是站点风控，稍后再试）' },
      }
    }
  } finally {
    libraryOpenLoading.value = ''
  }
}

/** URL 库展开区顶部那行：这条记录自己是谁、从哪来、用过几次 */
function libraryMetaLine(row: UrlRecord): string {
  const parts: string[] = []
  if (row.keyword && row.label && row.keyword !== row.label) parts.push(`键 ${row.keyword}`)
  const origin = row.origin === 'page' ? '页面顺带发现' : '引擎发现'
  parts.push(row.backend ? `${origin}（${row.backend}）` : origin)
  if (row.native_id) parts.push(`${row.kind === 'actor' ? 'actor' : 'work'}:${row.native_id}`)
  if (row.hits && row.hits > 1) parts.push(`用过 ${row.hits} 次`)
  const seen = cacheTime(row.last_used_at || row.first_seen_at)
  if (seen) parts.push(`最近 ${seen}`)
  return parts.join(' ｜ ')
}

/** 缓存展开区顶部那行：这条缓存的键与写入时间 */
function cacheMetaLine(row: CacheEntry): string {
  const parts: string[] = [String(row.key || '')]
  const at = cacheTime(row.cached_at)
  if (at) parts.push(`写入 ${at}`)
  if (row.kind_label || row.kind) parts.push(String(row.kind_label || row.kind))
  return parts.join(' ｜ ')
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

// 两张卡片常开：进面板就把状态、URL 库清单、缓存清单一起拉回来
load()
void loadLibrary()
void loadCache()
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
/* URL 库 / 缓存：并排各占一半。
   用 auto-fit 而不是固定断点 —— 宿主详情弹窗的宽度各处不同（全屏页 vs 侧栏），
   按「一张卡至少 360px」自适应：够宽就两列各半，不够就自动上下堆叠。 */
.sdbs-duo {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 12px;
  margin-bottom: 4px;
  align-items: stretch;
}
/* 并排卡片：按列排（列表区靠 flex-grow 撑开，短的那张也跟右边等高） */
.sdbs-col {
  display: flex;
  flex-direction: column;
}
/* 卡片内的记录列表：固定上限 + 内部滚动 —— 否则缓存几百条会把整页拉长，
   两张卡片也就谈不上「大小一致」 */
.sdbs-scroll {
  max-height: 320px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
}
/* 点名字就地展开：展开块用淡底 + 圆角与列表行区分开 */
.sdbs-expand {
  margin: 2px 0 6px 0;
  padding: 8px 10px;
  border-radius: 6px;
  background-color: rgba(128, 128, 128, 0.1);
}
/* 附属条目（同一部作品的 TMDB 身份）：缩进 + 淡一点，看得出它挂在上一行下面 */
.sdbs-attached {
  padding-left: 22px;
  opacity: 0.85;
}
/* 可点的名字：不加按钮外壳，靠指针与下划线提示「点得动」 */
.sdbs-clickable {
  cursor: pointer;
}
.sdbs-clickable:hover {
  text-decoration: underline;
}
/* URL 库：关键词输入框限宽，记录行的标题可省略号截断（地址可能很长） */
.sdbs-lib-search {
  max-width: 320px;
  min-width: 200px;
}
.sdbs-lib-text {
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
