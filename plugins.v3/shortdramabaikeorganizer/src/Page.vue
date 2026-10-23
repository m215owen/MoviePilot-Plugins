<template>
  <v-card class="sdbo-panel" variant="flat">
    <v-alert
      v-if="errorText"
      type="error"
      variant="tonal"
      density="compact"
      class="ma-3 mb-0"
    >{{ errorText }}</v-alert>

    <v-card-title class="text-body-1 pb-1">
      短剧百科整理
      <v-chip :color="status.enabled ? 'success' : 'default'" size="small" variant="tonal" class="ml-2">
        {{ status.enabled ? '已启用' : '未启用' }}
      </v-chip>
      <v-chip :color="status.source_ready ? 'primary' : 'warning'" size="small" variant="tonal" class="ml-2">
        {{ status.source || 'djbaike' }}
      </v-chip>
      <span class="text-caption text-medium-emphasis ml-2">（前端 build a19）</span>
      <v-spacer></v-spacer>
      <v-btn variant="text" size="small" icon="mdi-refresh" title="刷新" :loading="loadingStatus" @click="refresh"></v-btn>
    </v-card-title>

    <v-card-text>
      <div class="text-caption text-medium-emphasis">扫描目录：{{ sourceText }}</div>
      <div class="text-caption text-medium-emphasis">目标库目录：{{ status.library_dir || '未配置' }}</div>
      <div class="text-caption text-medium-emphasis">
        搬运方式：{{ transferText }} ｜ 自动刮削：{{ status.scrape_enabled ? '开' : '关' }}
        ｜ 强制整理历史：{{ status.force_transfer ? '开' : '关' }}
      </div>

      <!--
        扫描与整理都是后台任务：点按钮只发「启动」，界面一律以轮询到的快照为准。
        整理曾经同步挂在 HTTP 上 → 130 部剧跑几分钟 → 反代先超时 → 前端只报 502。
      -->
      <div class="sdbo-actions">
        <v-btn color="primary" variant="flat" prepend-icon="mdi-magnify" :loading="starting" :disabled="running || organizeRunning" @click="startScan">扫描</v-btn>
        <v-btn variant="tonal" color="warning" prepend-icon="mdi-stop" :disabled="!running" @click="stopScan">停止扫描</v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-folder-move" :loading="orgStarting" :disabled="running || organizeRunning" @click="organizeAll">整理</v-btn>
        <v-btn v-if="organizeRunning" variant="tonal" color="warning" prepend-icon="mdi-stop" @click="stopOrganize">停止整理</v-btn>
        <v-btn variant="text" prepend-icon="mdi-clipboard-text" @click="openRunDetails">整理详情</v-btn>
        <v-chip size="small" variant="tonal" :color="stateColor">扫描 · {{ stateLabel }}</v-chip>
        <v-chip size="small" variant="tonal" :color="orgStateColor">整理 · {{ orgStateLabel }}</v-chip>
      </div>

      <v-progress-linear
        v-if="running"
        :model-value="percent"
        :indeterminate="!scan.total"
        color="primary"
        height="6"
        rounded
        class="mt-2"
      ></v-progress-linear>

      <v-progress-linear
        v-if="organizeRunning"
        :model-value="orgPercent"
        :indeterminate="!org.total"
        color="primary"
        height="6"
        rounded
        class="mt-2"
      ></v-progress-linear>

      <div class="text-caption text-medium-emphasis mt-2">
        {{ scan.message || '尚未扫描（点「扫描」只识别、不搬运）' }}
        <template v-if="running">
          <span> ｜ {{ scan.done }}/{{ scan.total || '?' }}</span>
          <span v-if="scan.current"> ｜ {{ scan.current }}</span>
        </template>
      </div>
      <div class="text-caption text-medium-emphasis">
        {{ org.message || '尚未整理（点「整理」= 识别 + 搬运，后台跑，结果看「整理详情」）' }}
        <template v-if="organizeRunning">
          <span> ｜ {{ orgPhaseLabel }} {{ org.done }}/{{ org.total || '?' }}</span>
          <span v-if="org.current"> ｜ {{ org.current }}</span>
        </template>
      </div>

      <!-- 五类统计（记录库，重启不丢）；点卡片筛选下方「整理记录」 -->
      <div class="sdbo-stats">
        <div
          class="sdbo-stat"
          role="button"
          tabindex="0"
          :class="{ active: statFilter === 'recognized' }"
          title="点击筛选：已识别"
          @click="toggleStatFilter('recognized')"
          @keyup.enter="toggleStatFilter('recognized')"
        >
          <div class="sdbo-stat-num">{{ storeData.stats.recognized }}</div>
          <div class="sdbo-stat-label">已识别</div>
        </div>
        <div
          class="sdbo-stat"
          role="button"
          tabindex="0"
          :class="{ active: statFilter === 'pending' }"
          title="点击筛选：待整理（已识别但还没整理过）"
          @click="toggleStatFilter('pending')"
          @keyup.enter="toggleStatFilter('pending')"
        >
          <div class="sdbo-stat-num">{{ storeData.stats.pending }}</div>
          <div class="sdbo-stat-label">待整理</div>
        </div>
        <div
          class="sdbo-stat"
          role="button"
          tabindex="0"
          :class="{ active: statFilter === 'transferred' }"
          title="点击筛选：整理中"
          @click="toggleStatFilter('transferred')"
          @keyup.enter="toggleStatFilter('transferred')"
        >
          <div class="sdbo-stat-num live">{{ storeData.stats.transferred }}</div>
          <div class="sdbo-stat-label">整理中</div>
        </div>
        <div
          class="sdbo-stat"
          role="button"
          tabindex="0"
          :class="{ active: statFilter === 'completed' }"
          title="点击筛选：整理完成（已整理集数与数据源集数对齐，或手动标记）"
          @click="toggleStatFilter('completed')"
          @keyup.enter="toggleStatFilter('completed')"
        >
          <div class="sdbo-stat-num ok">{{ storeData.stats.completed }}</div>
          <div class="sdbo-stat-label">整理完成</div>
        </div>
        <div
          class="sdbo-stat"
          role="button"
          tabindex="0"
          :class="{ active: statFilter === 'unrecognized' }"
          title="点击筛选：未识别"
          @click="toggleStatFilter('unrecognized')"
          @keyup.enter="toggleStatFilter('unrecognized')"
        >
          <div class="sdbo-stat-num warn">{{ storeData.stats.unrecognized }}</div>
          <div class="sdbo-stat-label">未识别</div>
        </div>
        <div
          class="sdbo-stat"
          role="button"
          tabindex="0"
          :class="{ active: statFilter === 'unscraped' }"
          title="点击筛选：未刮削"
          @click="toggleStatFilter('unscraped')"
          @keyup.enter="toggleStatFilter('unscraped')"
        >
          <div class="sdbo-stat-num warn">{{ storeData.stats.unscraped }}</div>
          <div class="sdbo-stat-label">未刮削</div>
        </div>
      </div>
      <div v-if="!storeData.available" class="text-caption text-medium-emphasis">
        记录库不可用（宿主未提供插件数据库），统计与记录仅在本次会话内有效。
      </div>

      <!-- 记录列表（记录库，卡片下方唯一列表；四张统计卡即它的筛选器） -->
      <div class="sdbo-section">
        <div class="sdbo-counts">
          <span class="text-body-2">记录</span>
          <v-chip size="x-small" variant="tonal">
            {{ storeRecords.length }}<template v-if="statFilter"> / {{ storeTotal }} 条</template><template v-else> 条</template>
          </v-chip>
          <v-spacer></v-spacer>
          <v-btn size="x-small" variant="text" :disabled="!storeRecords.length" @click="clearStore">清空</v-btn>
        </div>
        <div class="sdbo-list">
          <div v-for="rec in storeRecords" :key="rec.path" class="sdbo-item">
            <div class="sdbo-item-main">
              <span class="sdbo-item-name" :title="rec.path">{{ rec.drama }}</span>
              <span class="sdbo-item-tag" :class="rec.state === 'recognized' ? 'ok' : 'warn'">
                {{ rec.state === 'recognized' ? '已识别' : '未识别' }}
              </span>
              <span v-if="rec.done" class="sdbo-item-tag done" title="已整理集数与数据源集数对齐（或手动标记）">整理完成</span>
              <span v-else-if="rec.transferred" class="sdbo-item-tag live">整理中</span>
              <span v-if="rec.dest_exists && rec.scraped" class="sdbo-item-tag ok">已刮削</span>
              <span v-else-if="rec.dest_exists" class="sdbo-item-tag warn">未刮削</span>
              <span v-if="rec.episode_count" class="sdbo-item-tag" title="剧的总集数（短剧百科）">{{ rec.episode_count }} 集</span>
              <v-btn
                v-if="rec.transferred && !rec.done"
                size="x-small"
                variant="text"
                color="success"
                title="集数没对齐但确认已收齐：手动敲定为整理完成（扫描将跳过该剧）"
                :loading="completingPath === rec.path"
                @click="markComplete(rec, '1')"
              >标记完成</v-btn>
              <v-btn
                v-if="rec.completed && !autoDone(rec)"
                size="x-small"
                variant="text"
                title="撤销手动标记，回到整理中"
                :loading="completingPath === rec.path"
                @click="markComplete(rec, '0')"
              >取消标记</v-btn>
              <v-btn
                v-if="rec.dest_exists && !rec.scraped && rec.state === 'recognized'"
                size="x-small"
                variant="text"
                color="primary"
                :loading="scrapingPath === rec.path"
                @click="scrapeRecord(rec)"
              >立即刮削</v-btn>
              <v-btn
                v-if="rec.state === 'recognized' && !rec.transferred"
                size="x-small"
                variant="text"
                color="primary"
                title="按记录里的身份整理这部剧（已整理过的用「重新整理」）"
                :loading="organizingPath === rec.path"
                @click="organizeRecord(rec)"
              >整理</v-btn>
              <v-btn
                v-if="rec.state !== 'recognized' || !rec.episode_count"
                size="x-small"
                variant="text"
                color="primary"
                title="已识别但记录缺集数时也可重跑：选同一条目再整理一次即可补上（文件已整理过会跳过，只刷新记录）"
                @click="openFix(rec)"
              >人工处理</v-btn>
              <!-- 已整理过的：可换身份 / 换目标库 / 换搬运方式再整理一次 -->
              <v-btn
                v-if="rec.transferred"
                size="x-small"
                variant="text"
                color="primary"
                title="按指定身份 / 目标库 / 搬运方式重新整理这部剧"
                :loading="reorganizingPath === rec.path"
                @click="openReorganize(rec)"
              >重新整理</v-btn>
              <v-btn
                v-if="rec.transferred || rec.dest_exists"
                size="x-small"
                variant="text"
                title="查看这部剧的整理记录（哪些文件搬到了哪）"
                @click="openDramaDetails(rec)"
              >详情</v-btn>
              <v-btn
                size="x-small"
                variant="text"
                color="error"
                title="删除这条记录"
                @click="deleteRecord(rec)"
              >删除</v-btn>
            </div>
            <div class="sdbo-item-sub">
              <span v-if="rec.title">{{ rec.title }}<template v-if="rec.year">（{{ rec.year }}）</template></span>
              <span v-else class="text-medium-emphasis">—</span>
              <span v-if="rec.dest_dir" class="sdbo-item-reason" :title="rec.dest_dir">目标：{{ rec.dest_dir }}</span>
              <span v-if="rec.organized_episodes">
                已整理 {{ rec.organized_episodes }}<template v-if="rec.episode_count"> / {{ rec.episode_count }}</template> 集
              </span>
              <span v-if="rec.reason" class="sdbo-item-reason">{{ rec.reason }}</span>
            </div>
          </div>
          <div v-if="!storeRecords.length" class="text-caption text-medium-emphasis sdbo-empty">
            <template v-if="statFilter">「{{ statFilterLabel }}」分类下暂无记录</template>
            <template v-else>暂无记录（点「扫描」后自动入库；整理、刮削结果也会写回这里）</template>
          </div>
        </div>
      </div>
    </v-card-text>

    <!-- 未识别目录：人工指定百科身份后直接整理 -->
    <v-dialog v-model="fixOpen" max-width="640" scrollable>
      <v-card>
        <v-card-title class="text-body-2">人工指定身份</v-card-title>
        <v-card-text>
          <div class="text-caption text-medium-emphasis">目录：{{ fixItem ? fixItem.drama : '' }}</div>
          <div class="sdbo-actions">
            <v-text-field
              v-model="fixKeyword"
              density="compact"
              variant="outlined"
              hide-details
              label="搜索关键词（默认用目录名）"
              class="sdbo-grow"
              @keyup.enter="runSearch"
            ></v-text-field>
            <v-btn variant="tonal" :loading="fixLoading" @click="runSearch">搜索百科</v-btn>
          </div>
          <v-alert v-if="fixMessage" type="info" variant="tonal" density="compact" class="mt-2">{{ fixMessage }}</v-alert>

          <div v-if="fixCandidates.length" class="sdbo-list mt-2">
            <div
              v-for="cand in fixCandidates"
              :key="cand.media_id"
              class="sdbo-item sdbo-cand"
              :class="{ active: fixSelected && fixSelected.media_id === cand.media_id }"
              @click="fixSelected = cand"
            >
              <div class="sdbo-item-main">
                <span class="sdbo-item-name">{{ cand.title || cand.media_id }}</span>
                <span v-if="cand.year" class="sdbo-item-tag ok">{{ cand.year }}</span>
                <span v-if="cand.episode_count" class="sdbo-item-tag warn">{{ cand.episode_count }} 集</span>
              </div>
              <div class="sdbo-item-sub">{{ cand.media_id }}</div>
            </div>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="fixOpen = false">取消</v-btn>
          <v-spacer></v-spacer>
          <v-btn color="primary" variant="flat" :disabled="!fixSelected" :loading="fixApplying" @click="applyFix">
            按此身份整理
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 整理详情：本次整理运行（逐部剧结果）或单剧（文件级整理记录） -->
    <v-dialog v-model="detailOpen" max-width="820" scrollable>
      <v-card>
        <v-card-title class="text-body-2">
          {{ detailScope === 'drama' ? '整理详情 · ' + (detailDramaName || '') : '整理详情 · 本次整理' }}
        </v-card-title>
        <v-card-subtitle v-if="detailScope === 'drama'" class="text-caption pb-0">
          {{ dramaDetail.dest_dir || '（这条记录还没有目标目录）' }}
        </v-card-subtitle>
        <v-card-text>
          <v-alert v-if="detailMessage" type="info" variant="tonal" density="compact">{{ detailMessage }}</v-alert>

          <!-- 单剧：文件级整理记录（谁写的都算，含宿主内置短剧处理器） -->
          <template v-if="detailScope === 'drama'">
            <div class="sdbo-detail-head">
              <span>共 {{ dramaDetail.count }} 条整理记录</span>
              <span>目标：{{ dramaDetail.dest_dir || '—' }}</span>
            </div>
            <div class="sdbo-list">
              <div v-for="rec in dramaDetail.items" :key="rec.id ?? rec.dest" class="sdbo-item">
                <div class="sdbo-item-main">
                  <span class="sdbo-item-ep">{{ (rec.seasons || 'S01') + (rec.episodes || '') }}</span>
                  <span class="sdbo-item-name" :title="rec.src">{{ rec.src_name || rec.src }}</span>
                  <span class="sdbo-item-arrow">→</span>
                  <span class="sdbo-item-name" :title="rec.dest">{{ rec.dest_name || rec.dest }}</span>
                  <span class="sdbo-item-tag">{{ modeText(rec.mode) }}</span>
                  <span class="sdbo-item-tag" :class="rec.status ? 'ok' : 'warn'">{{ rec.status ? '成功' : '失败' }}</span>
                </div>
                <div class="sdbo-item-sub">
                  <span v-if="rec.date">{{ rec.date }}</span>
                  <span v-if="rec.media_source">{{ rec.media_source }}</span>
                  <span v-if="rec.media_id">id: {{ rec.media_id }}</span>
                </div>
              </div>
              <div v-if="!dramaDetail.count" class="text-caption text-medium-emphasis sdbo-empty">
                这部剧还没有整理记录（可回列表点「重新整理」）
              </div>
            </div>
          </template>

          <!-- 本次整理运行：逐部剧的结果 -->
          <template v-else>
            <div class="sdbo-detail-head">
              <span>整理 {{ runDetail.counts.dramas || 0 }} 部</span>
              <span>文件成功 {{ runDetail.counts.done || 0 }}</span>
              <span>跳过 {{ runDetail.counts.skipped || 0 }}</span>
              <span>失败 {{ runDetail.counts.failed || 0 }}</span>
              <span>未识别 {{ runDetail.counts.unrecognized || 0 }}</span>
            </div>
            <div class="sdbo-list">
              <div v-for="d in runDetail.details" :key="d.path" class="sdbo-item">
                <div class="sdbo-item-main">
                  <span class="sdbo-item-name" :title="d.path">{{ d.drama }}</span>
                  <span v-if="d.organized" class="sdbo-item-tag ok">整理 {{ d.done }}</span>
                  <span v-if="d.skipped" class="sdbo-item-tag">跳过 {{ d.skipped }}</span>
                  <span v-if="d.failed" class="sdbo-item-tag warn">失败 {{ d.failed }}</span>
                  <span v-if="d.unrecognized" class="sdbo-item-tag warn">未识别</span>
                </div>
                <div class="sdbo-item-sub">
                  <span v-if="d.title">{{ d.title }}</span>
                  <span v-if="d.dest_dir" class="sdbo-item-reason" :title="d.dest_dir">{{ d.dest_dir }}</span>
                  <span v-if="d.error" class="sdbo-item-reason">{{ d.error }}</span>
                  <span v-if="d.note" class="sdbo-item-reason">{{ d.note }}</span>
                </div>
              </div>
              <div v-if="!runDetail.details.length" class="text-caption text-medium-emphasis sdbo-empty">
                还没有整理记录：先在上方点「整理」，这里会留下那次整理的逐部结果
              </div>
            </div>
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="detailOpen = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 已整理的记录：按指定身份 / 目标库 / 搬运方式重新整理 -->
    <v-dialog v-model="reOpen" max-width="760" scrollable>
      <v-card>
        <v-card-title class="text-body-2">重新整理</v-card-title>
        <v-card-subtitle class="text-caption pb-0">
          {{ reItem ? reItem.drama : '' }}
          <span v-if="reItem" class="text-medium-emphasis">（{{ reItem.path }}）</span>
        </v-card-subtitle>
        <v-card-text>
          <div class="sdbo-field-label">身份（不换就沿用当前身份）</div>
          <div class="sdbo-actions">
            <v-text-field
              v-model="reKeyword"
              density="compact"
              variant="outlined"
              hide-details
              label="搜索关键词（默认用剧名）"
              class="sdbo-grow"
              @keyup.enter="runReSearch"
            ></v-text-field>
            <v-btn variant="tonal" :loading="reSearching" @click="runReSearch">搜索百科</v-btn>
            <v-btn variant="text" title="放弃候选，用记录里现有的身份" @click="useCurrentIdentity">用当前身份</v-btn>
          </div>
          <div v-if="reCandidates.length" class="sdbo-list mt-2">
            <div
              v-for="c in reCandidates"
              :key="c.media_id"
              class="sdbo-item sdbo-cand"
              :class="{ active: reSelected && reSelected.media_id === c.media_id }"
              @click="reSelected = c"
            >
              <div class="sdbo-item-main">
                <span class="sdbo-item-name">{{ c.title || c.media_id }}</span>
                <span v-if="c.year" class="sdbo-item-tag ok">{{ c.year }}</span>
                <span v-if="c.episode_count" class="sdbo-item-tag warn">{{ c.episode_count }} 集</span>
                <span v-if="reItem && c.media_id === reItem.media_id" class="sdbo-item-tag ok">当前</span>
              </div>
              <div class="sdbo-item-sub">{{ c.media_id }}</div>
            </div>
          </div>
          <div v-else class="text-caption text-medium-emphasis mt-1">
            当前身份：{{ reItem && reItem.title ? reItem.title + '（' + (reItem.year || '—') + '）' : '（无）' }}
          </div>

          <div class="sdbo-actions mt-2">
            <v-text-field
              v-model="reLibrary"
              density="compact"
              variant="outlined"
              hide-details
              label="目标库目录（留空用配置值）"
              class="sdbo-grow"
            ></v-text-field>
            <v-select
              v-model="reTransfer"
              :items="transferItems"
              density="compact"
              variant="outlined"
              hide-details
              label="搬运方式"
              class="sdbo-transfer"
            ></v-select>
          </div>
          <v-switch
            v-model="reForce"
            color="warning"
            density="compact"
            hide-details
            label="强制重整理（忽略整理历史去重，已在库的文件也重搬）"
            class="mt-1"
          ></v-switch>

          <div class="sdbo-actions">
            <v-btn variant="tonal" size="small" prepend-icon="mdi-eye" :loading="rePreviewing" @click="runPreview">预演</v-btn>
            <span class="text-caption text-medium-emphasis">{{ rePreviewText }}</span>
          </div>
          <div v-if="rePreviewItems.length" class="sdbo-list">
            <div v-for="p in rePreviewItems" :key="p.src" class="sdbo-item">
              <div class="sdbo-item-main">
                <span class="sdbo-item-ep">E{{ padEpisode(p.episode) }}</span>
                <span class="sdbo-item-name" :title="p.src">{{ p.src_name }}</span>
                <span class="sdbo-item-arrow">→</span>
                <span class="sdbo-item-name" :title="p.target">{{ p.target_name }}</span>
              </div>
            </div>
          </div>
          <div v-if="!reForce" class="text-caption text-medium-emphasis mt-1">
            预演列出的是源目录里的全部文件；真正执行时，已在整理历史里的文件会被跳过（除非勾上强制重整理）。
          </div>
          <v-alert v-if="reMessage" type="info" variant="tonal" density="compact" class="mt-2">{{ reMessage }}</v-alert>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="reOpen = false">取消</v-btn>
          <v-spacer></v-spacer>
          <v-btn color="primary" variant="flat" :loading="reApplying" @click="applyReorganize">开始重新整理</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
/**
 * 短剧百科整理 · 数据面板（2026-10-23 重写，单文件自包含）。
 *
 * 扫描是后台任务：POST /scan/start 起线程，GET /scan 拿进度快照（2 秒轮询）；
 * 扫描成果每部剧写入插件自有库（/store）。四张统计卡（已识别 / 已整理 /
 * 未识别 / 未刮削）就是下方**唯一记录列表**的筛选器：不选=全部记录，
 * 点某张=只看该分类，再点一次取消。列表行内提供立即刮削 / 人工处理 /
 * 删除；整理、刮削结果都会写回记录库，重启不丢。
 * 结构只用 v-card / v-btn / v-chip / v-alert / v-progress-linear 与普通 div，
 * 不依赖表格组件，避免宿主组件版本差异带来的白屏。
 */
import { computed, onBeforeUnmount, onErrorCaptured, onMounted, ref } from 'vue'

import {
  backend,
  hostApi,
  pickOrganize,
  pickScan,
  type DramaDetails,
  type HostApi,
  type OrganizeParams,
  type OrganizeSnapshot,
  type OrganizerStatus,
  type PreviewPlan,
  type RunDetails,
  type ScanSnapshot,
  type SearchCandidate,
  type StoreRecord,
  type StoreSnapshot,
} from './api'

/** 扫描与整理共用的状态字典（两个任务状态机一模一样） */
const STATE_LABEL: Record<string, string> = {
  idle: '空闲',
  running: '进行中',
  stopping: '停止中',
  stopped: '已停止',
  done: '已完成',
  error: '出错',
}
const STATE_COLOR: Record<string, string> = {
  running: 'primary',
  stopping: 'warning',
  stopped: 'warning',
  done: 'success',
  error: 'error',
}
/** 搬运方式下拉（与后端 transfer_type 取值一一对应） */
const transferItems = [
  { title: '移动', value: 'move' },
  { title: '复制', value: 'copy' },
  { title: '硬链接', value: 'link' },
  { title: '软链接', value: 'softlink' },
]

const props = defineProps<{
  api?: HostApi
  pluginId?: string
}>()

const emit = defineEmits(['action', 'switch', 'close'])

const emptyScan = (): ScanSnapshot => ({
  state: 'idle',
  total: 0,
  done: 0,
  current: '',
  message: '',
  counts: { pending: 0, unrecognized: 0 },
  items: [],
})

const emptyStore = (): StoreSnapshot => ({
  available: false,
  stats: {
    recognized: 0,
    pending: 0,
    transferred: 0,
    completed: 0,
    unrecognized: 0,
    unscraped: 0,
  },
  items: [],
})

const emptyOrganize = (): OrganizeSnapshot => ({
  state: 'idle',
  phase: '',
  total: 0,
  done: 0,
  current: '',
  message: '',
  counts: { dramas: 0, done: 0, skipped: 0, failed: 0, unrecognized: 0 },
  details: [],
})

const status = ref<OrganizerStatus>({
  enabled: false,
  source: 'djbaike',
  source_provider: 'ShortDramaBaikeScraper',
  source_ready: false,
  library_dir: '',
  source_dirs: [],
  transfer_type: '',
  episode_width: 2,
  scrape_enabled: true,
  force_transfer: false,
  monitor_enabled: false,
  history_backend: 'TransferHistoryOper',
  store_available: false,
  note: '',
})

const scan = ref<ScanSnapshot>(emptyScan())
/** 整理任务快照（后台任务；扫描与整理各自独立） */
const org = ref<OrganizeSnapshot>(emptyOrganize())
const storeData = ref<StoreSnapshot>(emptyStore())
/** 统计卡筛选：'' 不过滤（显示全部记录）；命中时下方列表只显示该分类 */
const statFilter = ref<'' | 'recognized' | 'pending' | 'transferred' | 'completed' | 'unrecognized' | 'unscraped'>('')
const errorText = ref('')
const loadingStatus = ref(false)
const starting = ref(false)
/** 整理按钮的 loading（只覆盖「启动请求」那一瞬，跑起来后靠快照驱动） */
const orgStarting = ref(false)
/** 正在刮削的源目录 path（按钮 loading 用） */
const scrapingPath = ref('')
/** 正在重新整理的源目录 path（按钮 loading 用） */
const reorganizingPath = ref('')
/** 正在整理的源目录 path（记录行「整理」按钮的 loading 用） */
const organizingPath = ref('')
/** 正在标记（取消）整理完成的源目录 path（按钮 loading 用） */
const completingPath = ref('')

/** 整理详情窗口 */
const detailOpen = ref(false)
const detailScope = ref<'run' | 'drama'>('run')
const detailDramaName = ref('')
const detailMessage = ref('')
const runDetail = ref<RunDetails>({
  scope: 'run',
  state: 'idle',
  message: '',
  counts: { dramas: 0, done: 0, skipped: 0, failed: 0, unrecognized: 0 },
  details: [],
})
const dramaDetail = ref<DramaDetails>({ scope: 'drama', dest_dir: '', count: 0, items: [] })

/** 重新整理（已整理的记录 → 指定身份 / 目标库 / 搬运方式） */
const reOpen = ref(false)
const reItem = ref<StoreRecord | null>(null)
const reKeyword = ref('')
const reSearching = ref(false)
const reCandidates = ref<SearchCandidate[]>([])
const reSelected = ref<SearchCandidate | null>(null)
const reLibrary = ref('')
const reTransfer = ref('move')
const reForce = ref(false)
const rePreviewing = ref(false)
const reApplying = ref(false)
const reMessage = ref('')
const rePreviewText = ref('')
const rePreviewItems = ref<PreviewPlan[]>([])

/** 人工处理（未识别记录手动指定百科身份） */
const fixOpen = ref(false)
const fixItem = ref<StoreRecord | null>(null)
const fixKeyword = ref('')
const fixLoading = ref(false)
const fixApplying = ref(false)
const fixMessage = ref('')
const fixCandidates = ref<SearchCandidate[]>([])
const fixSelected = ref<SearchCandidate | null>(null)

let timer = 0
/** 点过扫描后的强制轮询窗口（即使快照解析失败也能持续拉，30 秒足够 136 部跑完） */
let pollUntil = 0
/** 点过整理后的强制轮询窗口（整理比扫描慢，给 60 秒） */
let orgPollUntil = 0

const running = computed(() => scan.value.state === 'running' || scan.value.state === 'stopping')
const percent = computed(() => {
  const total = scan.value.total || 0
  if (!total) return 0
  return Math.min(100, Math.round((scan.value.done / total) * 100))
})
const sourceText = computed(() => {
  const list = status.value.source_dirs || []
  return list.length ? list.join('、') : '未配置'
})
const transferText = computed(() => {
  const map: Record<string, string> = { move: '移动', copy: '复制', link: '硬链接', softlink: '软链接' }
  return map[status.value.transfer_type] || status.value.transfer_type || '—'
})
const stateLabel = computed(() => STATE_LABEL[scan.value.state] || scan.value.state)
const stateColor = computed(() => STATE_COLOR[scan.value.state] || 'default')
/** 整理任务：单独一套快照与状态（与扫描互不干扰） */
const organizeRunning = computed(
  () => org.value.state === 'running' || org.value.state === 'stopping',
)
const orgPercent = computed(() => {
  const total = org.value.total || 0
  if (!total) return 0
  return Math.min(100, Math.round((org.value.done / total) * 100))
})
const orgStateLabel = computed(() => STATE_LABEL[org.value.state] || org.value.state)
const orgStateColor = computed(() => STATE_COLOR[org.value.state] || 'default')
/** 整理分两段：先逐部识别，再逐部搬运 */
const orgPhaseLabel = computed(() => (org.value.phase === 'scan' ? '识别' : '整理'))
const statFilterLabel = computed<string>(() => {
  const map: Record<string, string> = {
    recognized: '已识别',
    pending: '待整理',
    transferred: '整理中',
    completed: '整理完成',
    unrecognized: '未识别',
    unscraped: '未刮削',
  }
  return map[statFilter.value] || ''
})
const storeTotal = computed<number>(() => (storeData.value.items || []).length)
/** 记录列表：按统计卡筛选；口径与后端 stats 一致 */
const storeRecords = computed<StoreRecord[]>(() => {
  const items = storeData.value.items || []
  const key = statFilter.value
  if (!key) return items
  return items.filter((rec) => {
    if (key === 'recognized') return rec.state === 'recognized'
    if (key === 'pending') return rec.state === 'recognized' && !rec.transferred
    if (key === 'transferred') return !!rec.transferred && !isDone(rec)
    if (key === 'completed') return isDone(rec)
    if (key === 'unrecognized') return rec.state !== 'recognized'
    if (key === 'unscraped') return rec.dest_exists && !rec.scraped
    return true
  })
})

/** 集数是否对齐（自动判定整理完成的口径，与后端一致） */
function isDone(rec: StoreRecord): boolean {
  if (rec.done) return true
  const total = rec.episode_count || 0
  return total > 0 && (rec.organized_episodes || 0) >= total
}

/** 手动标记口径下的 done（= completed），用于「取消标记」按钮显隐 */
function autoDone(rec: StoreRecord): boolean {
  const total = rec.episode_count || 0
  return total > 0 && (rec.organized_episodes || 0) >= total
}

/** 点统计卡：再点一次同一张取消筛选 */
function toggleStatFilter(
  key: '' | 'recognized' | 'pending' | 'transferred' | 'completed' | 'unrecognized' | 'unscraped',
): void {
  statFilter.value = statFilter.value === key ? '' : key
}

/** 手动标记 / 取消「整理完成」 */
async function markComplete(rec: StoreRecord, value: string): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  completingPath.value = rec.path
  try {
    await backend.storeComplete(api, rec.path, value)
    await loadStore()
    scan.value = {
      ...scan.value,
      message: value === '0' ? `已取消 ${rec.drama} 的完成标记` : `已将 ${rec.drama} 标记为整理完成`,
    }
  } catch (err) {
    errorText.value = `标记失败：${(err as Error)?.message || String(err)}`
  } finally {
    completingPath.value = ''
  }
}

onErrorCaptured((err) => {
  errorText.value = `渲染异常：${(err as Error)?.message || String(err)}`
  return false
})

function apiOrNull(): HostApi | null {
  return hostApi({ api: props.api })
}

async function loadStore(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    const data = await backend.store(api)
    if (data) storeData.value = { ...emptyStore(), ...data }
  } catch (err) {
    errorText.value = `读取记录库失败：${(err as Error)?.message || String(err)}`
  }
}

async function refresh(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  loadingStatus.value = true
  try {
    const nextStatus = await backend.status(api)
    status.value = nextStatus || status.value
    const snapshot = pickScan(await backend.scan(api))
    if (snapshot) scan.value = { ...emptyScan(), ...snapshot }
    await loadStore()
  } catch (err) {
    errorText.value = `读取状态失败：${(err as Error)?.message || String(err)}`
  } finally {
    loadingStatus.value = false
  }
}

async function poll(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    const snapshot = pickScan(await backend.scan(api))
    if (snapshot) {
      scan.value = { ...emptyScan(), ...snapshot }
      // 拿到终止态就收掉强制轮询窗口，别再无谓打接口
      if (snapshot.state !== 'running' && snapshot.state !== 'stopping') {
        pollUntil = 0
        // 扫描一结束就把成果同步进记录库展示
        await loadStore()
      }
    }
  } catch {
    /* 轮询失败忽略，下一轮再试 */
  }
}

async function startScan(): Promise<void> {
  const api = apiOrNull()
  if (!api) {
    errorText.value = '宿主 api 实例不可用，请刷新页面重试'
    return
  }
  starting.value = true
  errorText.value = ''
  try {
    // 只把 POST 当作「按下开关」，界面状态一律以随后的 GET /scan 快照为准 ——
    // 不同宿主版本对 POST 返回的解包深度不一致，靠它驱动 UI 很容易空转
    const result = await backend.scanStart(api)
    scan.value = { ...scan.value, state: 'running', message: '扫描已启动，等待进度…' }
    pollUntil = Date.now() + 30_000
    if (result && result.started === false && result.message) {
      errorText.value = result.message
    }
    await poll()
  } catch (err) {
    errorText.value = `启动扫描失败：${(err as Error)?.message || String(err)}`
  } finally {
    starting.value = false
  }
}

async function stopScan(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    await backend.scanStop(api)
    scan.value = { ...scan.value, state: 'stopping', message: '正在停止…' }
    pollUntil = Date.now() + 10_000
    await poll()
  } catch (err) {
    errorText.value = `停止失败：${(err as Error)?.message || String(err)}`
  }
}

async function pollOrganize(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    const snapshot = pickOrganize(await backend.organizeProgress(api))
    if (snapshot) {
      org.value = { ...emptyOrganize(), ...snapshot }
      // 拿到终止态就收掉强制轮询窗口，别再无谓打接口
      if (snapshot.state !== 'running' && snapshot.state !== 'stopping') {
        orgPollUntil = 0
        await loadStore()
      }
    }
  } catch {
    /* 轮询失败忽略，下一轮再试 */
  }
}

async function organizeAll(): Promise<void> {
  const api = apiOrNull()
  if (!api) {
    errorText.value = '宿主 api 实例不可用，请刷新页面重试'
    return
  }
  orgStarting.value = true
  errorText.value = ''
  try {
    // 同扫描：POST 只当「按下开关」，界面状态一律以随后的 /organize 快照为准。
    // 整理必须先后台化 —— 同步跑会被反代掐断，前端只收到 502。
    const result = await backend.organizeStart(api, false)
    const snapshot = pickOrganize(result)
    org.value = snapshot
      ? { ...emptyOrganize(), ...snapshot }
      : { ...org.value, state: 'running', message: '整理已启动，等待进度…' }
    // 整理比扫描更慢（多了逐文件搬运），强制轮询窗口给 60 秒
    orgPollUntil = Date.now() + 60_000
    if (result && result.started === false && result.message) {
      errorText.value = result.message
    }
    await pollOrganize()
  } catch (err) {
    errorText.value = `启动整理失败：${(err as Error)?.message || String(err)}`
  } finally {
    orgStarting.value = false
  }
}

async function stopOrganize(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    await backend.organizeStop(api)
    org.value = { ...org.value, state: 'stopping', message: '正在停止…' }
    orgPollUntil = Date.now() + 10_000
    await pollOrganize()
  } catch (err) {
    errorText.value = `停止整理失败：${(err as Error)?.message || String(err)}`
  }
}

/** 打开「整理详情」：本次整理运行的逐部结果 */
async function openRunDetails(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  detailScope.value = 'run'
  detailDramaName.value = ''
  detailMessage.value = ''
  detailOpen.value = true
  try {
    const data = await backend.details(api)
    if (data && data.scope === 'run') runDetail.value = data
  } catch (err) {
    detailMessage.value = `读取整理详情失败：${(err as Error)?.message || String(err)}`
  }
}

/** 打开「整理详情」：某部剧的文件级整理记录 */
async function openDramaDetails(rec: StoreRecord): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  detailScope.value = 'drama'
  detailDramaName.value = rec.title || rec.drama
  detailMessage.value = ''
  dramaDetail.value = { scope: 'drama', dest_dir: rec.dest_dir || '', count: 0, items: [] }
  detailOpen.value = true
  try {
    const data = await backend.details(api, { path: rec.path })
    if (data && data.scope === 'drama') dramaDetail.value = data
  } catch (err) {
    detailMessage.value = `读取整理详情失败：${(err as Error)?.message || String(err)}`
  }
}

/** 打开「重新整理」：先按当前身份 + 配置预演一次，让人看清会搬什么 */
function openReorganize(rec: StoreRecord): void {
  reItem.value = rec
  reKeyword.value = rec.title || rec.drama || ''
  reCandidates.value = []
  reSelected.value = null
  reLibrary.value = ''
  reTransfer.value = status.value.transfer_type || 'move'
  reForce.value = false
  reMessage.value = ''
  rePreviewText.value = ''
  rePreviewItems.value = []
  reOpen.value = true
  void runPreview()
}

/** 按关键词重搜百科候选（换身份用） */
async function runReSearch(): Promise<void> {
  const api = apiOrNull()
  if (!api) {
    reMessage.value = '宿主 api 实例不可用，请刷新页面重试'
    return
  }
  const keyword = reKeyword.value.trim()
  if (!keyword) {
    reMessage.value = '请输入搜索关键词'
    return
  }
  reSearching.value = true
  reMessage.value = ''
  reSelected.value = null
  try {
    const data = await backend.search(api, keyword)
    reCandidates.value = data?.items || []
    if (!reCandidates.value.length) {
      reMessage.value = '百科没有搜到候选，换个关键词再试'
    }
  } catch (err) {
    reMessage.value = `搜索失败：${(err as Error)?.message || String(err)}`
  } finally {
    reSearching.value = false
  }
}

/** 放弃选中的候选，回到记录里现有的身份 */
function useCurrentIdentity(): void {
  reSelected.value = null
  reCandidates.value = []
  reMessage.value = ''
  void runPreview()
}

/** 按当前选中的身份 / 目标库预演整理计划（真正动手前先看清楚） */
async function runPreview(): Promise<void> {
  const api = apiOrNull()
  const rec = reItem.value
  if (!api || !rec) return
  rePreviewing.value = true
  rePreviewText.value = ''
  try {
    const picked = reSelected.value
    const data = await backend.preview(api, {
      path: rec.path,
      title: picked?.title || rec.title || rec.drama || '',
      ...((picked?.year ?? rec.year ?? null) !== null
        ? { year: String(picked?.year ?? rec.year) }
        : {}),
      library_dir: reLibrary.value || '',
      ...((picked?.media_id || rec.media_id)
        ? { media_id: picked?.media_id || rec.media_id }
        : {}),
    })
    if (!data.exists) {
      rePreviewText.value = '源目录已不存在，无法整理（移动方式搬完源目录就空了）'
      rePreviewItems.value = []
      return
    }
    rePreviewText.value = data.count
      ? `将整理 ${data.count} 个文件 → ${data.library_dir}`
      : '源目录里没有可整理的视频文件'
    rePreviewItems.value = data.items || []
  } catch (err) {
    rePreviewText.value = `预演失败：${(err as Error)?.message || String(err)}`
  } finally {
    rePreviewing.value = false
  }
}

/** 按指定参数重新整理这部剧 */
async function applyReorganize(): Promise<void> {
  const api = apiOrNull()
  const rec = reItem.value
  if (!api || !rec) return
  reApplying.value = true
  reorganizingPath.value = rec.path
  reMessage.value = ''
  try {
    const picked = reSelected.value
    const params: OrganizeParams = {
      path: rec.path,
      force: reForce.value ? '1' : '0',
      title: picked?.title || rec.title || rec.drama || '',
    }
    const mediaId = picked?.media_id || rec.media_id || ''
    if (mediaId) params.media_id = mediaId
    const year = picked?.year ?? rec.year
    if (year !== null && year !== undefined && year !== 0) params.year = String(year)
    if (reLibrary.value) params.library_dir = reLibrary.value
    if (reTransfer.value) params.transfer_type = reTransfer.value
    const result = await backend.organize(api, params)
    reOpen.value = false
    await loadStore()
    const note = result?.note
    scan.value = {
      ...scan.value,
      message: note
        ? `重新整理 ${rec.drama}：${note}`
        : `已重新整理 ${rec.drama}：成功 ${result?.done ?? 0}，跳过 ${result?.skipped ?? 0}，失败 ${result?.failed ?? 0}`,
    }
  } catch (err) {
    reMessage.value = `整理失败：${(err as Error)?.message || String(err)}`
  } finally {
    reApplying.value = false
    reorganizingPath.value = ''
  }
}

/** 搬运方式显示名 */
function modeText(mode: string): string {
  const map: Record<string, string> = { move: '移动', copy: '复制', link: '硬链接', softlink: '软链接' }
  return map[mode] || mode || '—'
}

/** 集号按配置位数补零（E018 / E18） */
function padEpisode(episode: number): string {
  return String(Number(episode) || 0).padStart(status.value.episode_width || 2, '0')
}

/** 立即刮削（扫描结果行 / 记录行共用）：发 /scrape，成功后就地更新状态 */
async function scrapeBy(path: string, dest: string): Promise<void> {
  const api = apiOrNull()
  if (!api || !path) return
  scrapingPath.value = path
  errorText.value = ''
  try {
    const result = await backend.scrape(api, { path, dest })
    if (result && result.success === false && result.error) {
      errorText.value = `刮削失败：${result.error}`
      return
    }
    // 就地刷新：库记录 + 扫描快照里这一行的刮削状态
    await loadStore()
    const item = scan.value.items.find((entry) => entry.path === path)
    if (item) {
      item.scraped = true
      item.dest_exists = true
    }
    const message = result?.message || '刮削已处理'
    scan.value = { ...scan.value, message }
  } catch (err) {
    errorText.value = `刮削失败：${(err as Error)?.message || String(err)}`
  } finally {
    scrapingPath.value = ''
  }
}

function scrapeRecord(rec: StoreRecord): void {
  void scrapeBy(rec.path, rec.dest_dir || '')
}

/**
 * 直接整理一部剧（记录行「整理」）。
 *
 * 与「重新整理」的区别：那个要先预演、可换身份/目标库/搬运方式；这里就用
 * 记录里已有的身份同步整理一部，一部剧够快，撑不到反代超时。
 */
async function organizeRecord(rec: StoreRecord): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  organizingPath.value = rec.path
  errorText.value = ''
  try {
    // 带上记录里已识别的身份（media_id 直取不联网）：后端没有 media_id 会按
    // 目录名重新走一遍百科识别，等于按钮按下又「扫」了一次（2026-10-23 用户
    // 「整理按钮按下为什么要再扫描一次？应该执行对已识别的整理」）
    const params: OrganizeParams = { path: rec.path }
    if (rec.media_id) params.media_id = rec.media_id
    if (rec.title) params.title = rec.title
    if (rec.year) params.year = String(rec.year)
    const result = await backend.organize(api, params)
    await loadStore()
    const note = result?.note
    scan.value = {
      ...scan.value,
      message: note
        ? `整理 ${rec.drama}：${note}`
        : `已整理 ${rec.drama}：成功 ${result?.done ?? 0}，跳过 ${result?.skipped ?? 0}，失败 ${result?.failed ?? 0}`,
    }
  } catch (err) {
    errorText.value = `整理失败：${(err as Error)?.message || String(err)}`
  } finally {
    organizingPath.value = ''
  }
}

async function deleteRecord(rec: StoreRecord): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    await backend.storeDelete(api, rec.path)
    await loadStore()
  } catch (err) {
    errorText.value = `删除记录失败：${(err as Error)?.message || String(err)}`
  }
}

async function clearStore(): Promise<void> {
  const api = apiOrNull()
  if (!api) return
  try {
    await backend.storeClear(api)
    await loadStore()
  } catch (err) {
    errorText.value = `清空记录失败：${(err as Error)?.message || String(err)}`
  }
}

/** 打开人工处理弹窗：默认用目录名搜一次 */
function openFix(rec: StoreRecord): void {
  fixItem.value = rec
  fixKeyword.value = rec.drama || ''
  fixCandidates.value = []
  fixSelected.value = null
  fixMessage.value = ''
  fixOpen.value = true
  void runSearch()
}

/** 按关键词搜百科候选 */
async function runSearch(): Promise<void> {
  const api = apiOrNull()
  if (!api) {
    fixMessage.value = '宿主 api 实例不可用，请刷新页面重试'
    return
  }
  const keyword = fixKeyword.value.trim()
  if (!keyword) {
    fixMessage.value = '请输入搜索关键词'
    return
  }
  fixLoading.value = true
  fixMessage.value = ''
  fixSelected.value = null
  try {
    const data = await backend.search(api, keyword)
    fixCandidates.value = data?.items || []
    if (!fixCandidates.value.length) {
      fixMessage.value = '百科没有搜到候选，换个关键词（去掉集数/演员等噪声）再试'
    }
  } catch (err) {
    fixMessage.value = `搜索失败：${(err as Error)?.message || String(err)}`
  } finally {
    fixLoading.value = false
  }
}

/** 用选中的候选身份直接整理该目录，并刷新记录库 */
async function applyFix(): Promise<void> {
  const api = apiOrNull()
  const rec = fixItem.value
  const candidate = fixSelected.value
  if (!api || !rec || !candidate) return
  fixApplying.value = true
  fixMessage.value = ''
  try {
    const params: OrganizeParams = {
      path: rec.path,
      media_id: candidate.media_id,
      title: candidate.title || rec.drama,
    }
    if (candidate.year !== null && candidate.year !== undefined) {
      params.year = String(candidate.year)
    }
    if (candidate.episode_count !== null && candidate.episode_count !== undefined) {
      params.episode_count = String(candidate.episode_count)
    }
    const result = await backend.organize(api, params)
    if (result && result.error) {
      fixMessage.value = `整理失败：${result.error}`
      return
    }
    fixOpen.value = false
    // 后端整理成功即写库（含自动刮削），拉一次最新记录
    await loadStore()
    scan.value = {
      ...scan.value,
      message: `已按「${candidate.title || candidate.media_id}」整理 ${rec.drama}`,
    }
  } catch (err) {
    fixMessage.value = `整理失败：${(err as Error)?.message || String(err)}`
  } finally {
    fixApplying.value = false
  }
}

onMounted(() => {
  void refresh()
  // 整理状态也要拉一次：面板打开时可能正有后台整理在跑（扫到一半刷新页面等场景）
  void pollOrganize()
  timer = window.setInterval(() => {
    // 扫描中，或刚点过扫描的 30 秒窗口内，都持续拉快照
    if (running.value || Date.now() < pollUntil) void poll()
    if (organizeRunning.value || Date.now() < orgPollUntil) void pollOrganize()
  }, 2000)
})

onBeforeUnmount(() => {
  if (timer) {
    window.clearInterval(timer)
    timer = 0
  }
})
</script>

<style scoped>
.sdbo-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.sdbo-counts {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.sdbo-stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-top: 12px;
}

.sdbo-stat {
  text-align: center;
  padding: 8px 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: rgba(25, 118, 210, 0.04);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s, border-color 0.15s;
}

.sdbo-stat:hover {
  background: rgba(25, 118, 210, 0.1);
  border-color: rgba(25, 118, 210, 0.3);
}

.sdbo-stat:focus-visible {
  outline: 2px solid rgba(25, 118, 210, 0.6);
  outline-offset: 1px;
}

.sdbo-stat.active {
  background: rgba(25, 118, 210, 0.16);
  border-color: #1976d2;
}

.sdbo-stat-num {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.2;
}

.sdbo-stat-num.ok {
  color: #1b5e20;
}

.sdbo-stat-num.live {
  color: #e65100;
}

.sdbo-stat-num.warn {
  color: #e65100;
}

.sdbo-stat-label {
  font-size: 11px;
  opacity: 0.7;
  margin-top: 2px;
}

.sdbo-section {
  margin-top: 16px;
}

.sdbo-list {
  margin-top: 6px;
  max-height: 380px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 6px;
}

.sdbo-empty {
  padding: 12px;
}

.sdbo-item {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.sdbo-item:last-child {
  border-bottom: 0;
}

.sdbo-item-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sdbo-item-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.sdbo-item-tag {
  flex: 0 0 auto;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
}

.sdbo-item-tag.ok {
  color: #1b5e20;
  background: rgba(76, 175, 80, 0.15);
}

/* 整理完成：实底绿（与「已刮削」等一般 ok 态区分开） */
.sdbo-item-tag.done {
  color: #ffffff;
  background: #2e7d32;
}

/* 整理中：橙色调（进行中的事，还没收齐） */
.sdbo-item-tag.live {
  color: #e65100;
  background: rgba(255, 152, 0, 0.18);
}

.sdbo-item-tag.warn {
  color: #e65100;
  background: rgba(255, 152, 0, 0.18);
}

.sdbo-item-sub {
  display: flex;
  gap: 8px;
  font-size: 11px;
  opacity: 0.75;
  margin-top: 2px;
}

.sdbo-item-reason {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sdbo-cand {
  cursor: pointer;
}

.sdbo-cand:hover {
  background: rgba(25, 118, 210, 0.06);
}

.sdbo-cand.active {
  background: rgba(25, 118, 210, 0.14);
}

.sdbo-grow {
  flex: 1 1 240px;
  min-width: 160px;
}

.sdbo-transfer {
  flex: 0 0 150px;
  min-width: 120px;
}

.sdbo-field-label {
  font-size: 11px;
  opacity: 0.7;
  margin-top: 8px;
}

.sdbo-detail-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  opacity: 0.8;
  margin-bottom: 2px;
}

.sdbo-item-ep {
  flex: 0 0 auto;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(25, 118, 210, 0.12);
  color: #1976d2;
}

.sdbo-item-arrow {
  flex: 0 0 auto;
  font-size: 11px;
  opacity: 0.6;
}
</style>
