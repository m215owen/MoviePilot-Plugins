"""短剧百科整理器 · 常量、默认值与枚举。

本模块刻意不依赖宿主任何模块，便于单测直接导入。

设计基线（与旧版市场插件 ShortDramaBaikeOrganizer 的差异，2026-10-22 重写）：

* **识别数据源 = 短剧百科（``djbaike``）**：调 ``ShortDramaBaikeScraper`` 的
  ``search_medias`` / ``recognize_media``（``media_source="djbaike"``）。
  旧版市场插件写死 ``ShortDramaNetSource``（``duanju``），这次按需求切到真正的
  短剧百科数据源。
* **整理完全不走系统的方式**：文件搬运由本插件自己直接做（``shutil`` / ``os.link`` /
  ``os.symlink``），**不**调宿主 ``TransferChain`` / ``manual_transfer``，也不进宿主
  整理队列。命名规则照搬宿主「短剧处理器」的 TV 惯例
  （``{剧名} ({年})/Season 1/{剧名} - S01E{NN}.ext``）。
* **整理历史读写改走 ``TransferHistoryOper``**：去重与落盘记录统一走宿主
  ``app.db.oper.transferhistory.TransferHistoryOper``，不再自持有 ``save_data`` 记录表
  （旧版市场的 ``ledger.py`` 三槽：records/pending/identity 取消，历史以系统整理历史为
  唯一真源）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------- 插件元数据
#
# ⚠️ 这几条必须写成**无注解的字面量赋值**（`PLUGIN_NAME = "..."`），
#    不能写成 `PLUGIN_NAME: Final[str] = "..."`：
#    仓库自检脚本走 AST 时只识别 `Assign`，
#    带注解的 `AnnAssign` 会被漏掉，最终报「plugin_name 无法静态解析」。

PLUGIN_ID = "ShortDramaBaikeOrganizer"
PLUGIN_NAME = "短剧百科整理"
PLUGIN_DESC = (
    "扫描待整理短剧目录，目录名即剧名，向短剧百科（djbaike）取身份，"
    "由插件直接按宿主短剧处理器命名规则搬运入库，并把整理历史写入系统 TransferHistoryOper。"
)
PLUGIN_ICON = "ShortDramaBaikeOrganizer.png"
PLUGIN_VERSION = "0.1.5"
PLUGIN_AUTHOR = "m215owen"
PLUGIN_CONFIG_PREFIX = "shortdramabaikeorganizer_"
PLUGIN_ORDER = 50
PLUGIN_AUTH_LEVEL = 1

# ------------------------------------------------------------ 数据源标识

# 短剧百科（duanjubaike.net）的稳定来源标识，由 ShortDramaBaikeScraper 注册。
BAIKE_MEDIA_SOURCE: Final[str] = "djbaike"
# 探活时核对的提供者插件 id：djbaike 必须由 ShortDramaBaikeScraper 提供，
# 避免与其它同名站点插件（旧站 ShortDramaBaikeSource 也注册过 duanju）串来源。
BAIKE_SOURCE_PLUGIN_ID: Final[str] = "ShortDramaBaikeScraper"
# 短剧在宿主里归到的媒体类别（目录配置的「短剧」分类名）。
CATEGORY_SHORT_DRAMA: Final[str] = "短剧"
# 写入整理历史的媒体类型（宿主 TV）。
MEDIA_TYPE_TV: Final[str] = "电视剧"

# ------------------------------------------------------ 前端（Vue 联邦）产物
#
# 插件面板/配置页是 Vue 模块联邦组件。``get_render_mode()`` 第二个返回值是
# **相对插件根**的产物目录，宿主拼
# ``/plugin/file/<id>/<该值>/remoteEntry.js?v=<plugin_version>``。
#
# ⚠️ 测试阶段版本号冻结（用户要求不升版本），``?v=`` 永远不变 → 浏览器强缓存 /
# Service Worker 会一直复用旧 remoteEntry（表现：改了前端界面不变或直接
# 「无法加载组件」）。所以把**目录名当缓存键**：前端有实质改动就把
# ``vite.config.ts`` 的 ``ASSETS_DIR`` 递增（a1 → a2），URL 随之变化。
FRONTEND_DIST: Final[str] = "dist/a20/assets"
_BUILD_DIR_RE = re.compile(r"a(\d+)")


def frontend_dist() -> str:
    """返回要注入宿主的产物目录（**含 ``remoteEntry.js`` 的那一层**）。

    产物结构是 ``dist/a<N>/assets/remoteEntry.js``（vite 的 chunkFileNames 把联邦入口
    也放进了 assets 子目录），所以这里扫 ``dist/a<N>`` 再拼 ``/assets``。
    找不到（首次构建前 / 老产物）时退回 :data:`FRONTEND_DIST`。
    """
    try:
        base = Path(__file__).resolve().parent / "dist"
        best: tuple[int, str] | None = None
        for child in base.iterdir():
            if not child.is_dir():
                continue
            matched = _BUILD_DIR_RE.fullmatch(child.name)
            # 只认里面有 remoteEntry.js 的目录，避免半成品目录把路径带偏
            if not matched or not (child / "assets" / "remoteEntry.js").exists():
                continue
            order = int(matched.group(1))
            if best is None or order > best[0]:
                best = (order, child.name)
        return f"dist/{best[1]}/assets" if best else FRONTEND_DIST
    except Exception:  # noqa: BLE001 - 扫目录失败不该影响插件加载
        return FRONTEND_DIST


# ------------------------------------------------------------ 配置键与默认值

CONF_ENABLED: Final[str] = "enabled"
CONF_SOURCE_DIRS: Final[str] = "source_dirs"
CONF_LIBRARY_DIR: Final[str] = "library_dir"
CONF_SCAN_DEPTH: Final[str] = "scan_depth"
CONF_TRANSFER_TYPE: Final[str] = "transfer_type"
CONF_EPISODE_WIDTH: Final[str] = "episode_width"
CONF_AUTO_RENAME_EPISODE: Final[str] = "auto_rename_episode"
CONF_SCRAPE_ENABLED: Final[str] = "scrape_enabled"
CONF_FORCE_TRANSFER: Final[str] = "force_transfer"
CONF_NOTIFY: Final[str] = "notify"
CONF_MONITOR_ENABLED: Final[str] = "monitor_enabled"
CONF_MONITOR_MODE: Final[str] = "monitor_mode"
CONF_MONITOR_INTERVAL: Final[str] = "monitor_interval"
CONF_FORCE_REORGANIZE: Final[str] = "force_reorganize"

DEFAULT_CONFIG: Final[dict] = {
    CONF_ENABLED: False,
    # 待整理短剧所在的根目录，每行一个（通常是下载器完成目录下的某层）
    CONF_SOURCE_DIRS: "",
    # 媒体库里的「短剧」根目录，作为整理目标根
    CONF_LIBRARY_DIR: "",
    # 从每个源目录向下扫描的层级：1 = 只把一级子目录当作一部剧
    CONF_SCAN_DEPTH: 1,
    # 缺失时按宿主目录配置推断
    CONF_TRANSFER_TYPE: "move",
    # 集号补零位数：2 -> E18；3 -> E018（2026-10-23 起默认 2，与短剧处理器一致）
    CONF_EPISODE_WIDTH: 2,
    # 源文件名提不到集号时按自然序补齐（绕过宿主集号解析，自包含模式默认开）
    CONF_AUTO_RENAME_EPISODE: True,
    # 整理完成后自动刮削（自包含：取 djbaike 素材写 tvshow.nfo + 海报，默认开）；
    # 面板对「已存在但未刮削」的目录另有「立即刮削」按钮，不受此开关限制
    CONF_SCRAPE_ENABLED: True,
    # 强制整理（2026-10-23 由「尊重整理历史」反转而来）：
    # 开 = 无视系统整理历史，已在历史里的源文件也照样重新整理（先删旧记录再搬）；
    # 关 = 尊重历史，命中历史记录的源文件跳过（默认）。
    # 语义改成「开 = 强制」是用户要求：开关名字必须是它打开后会发生的动作。
    CONF_FORCE_TRANSFER: False,
    CONF_NOTIFY: True,
    # 目录监控：常驻后台盯住源目录，发现新剧目录就自动跑完「扫描 → 识别 → 整理」
    CONF_MONITOR_ENABLED: False,
    # poll = 周期轮询（容器/网盘通用）；watch = 实时文件事件（优先 watchfiles）
    CONF_MONITOR_MODE: "watch",
    # 轮询间隔（秒）；watch 模式忽略
    CONF_MONITOR_INTERVAL: 60,
    # 历史里已有同一 src 的成功记录时仍强制重新整理（默认关：已在库就跳过）
    CONF_FORCE_REORGANIZE: False,
}

# ------------------------------------------------------------ 目录监控

MONITOR_MODE_POLL: Final[str] = "poll"
MONITOR_MODE_WATCH: Final[str] = "watch"
MONITOR_MODES: Final[tuple[str, ...]] = (MONITOR_MODE_POLL, MONITOR_MODE_WATCH)
MONITOR_INTERVAL_FLOOR: Final[int] = 10
MONITOR_INTERVAL_CEIL: Final[int] = 3600
MONITOR_INTERVAL_DEFAULT: Final[int] = 60
# 实时监控的事件去抖（秒）：文件落盘常伴随多次写事件，攒一攒再触发
MONITOR_WATCH_DEBOUNCE: Final[float] = 3.0

# ------------------------------------------------------------ 上限

MAX_SCAN_ITEMS: Final[int] = 2000
MAX_CONSECUTIVE_ERRORS: Final[int] = 20

# ---- 自包含刮削（scrape.py 用，2026-10-23 起不再走宿主刮削链）----
#
# 素材由数据源给全（nfo 是成品文本、图片是最终 URL），落盘就是两个文件写入。
# 图片下载**只借宿主** ``ImageHelper.fetch_image``（进程内直调）——它自带各图床
# 的 Referer（豆瓣 img*.doubanio.com → movie.douban.com，故直连不返 418）+ 磁盘
# 缓存 + 重试 + 代理；取不到如实报错，不再自包含回退（2026-10-23 用户要求）。
# 因此这里只需保留扩展名白名单，UA/Accept/Referer/重试/超时等常量随回退一并移除。
# 图片扩展名白名单：按 URL 后缀判定，白名单外一律回落 .jpg（与宿主口径一致）
SCRAPE_IMAGE_EXTENSIONS: Final[tuple[str, ...]] = (
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp",
)

# 整理进度快照里保留的「每部剧详情」条数上限（面板「整理详情」窗口用）
MAX_DETAIL_ITEMS: Final[int] = 500
# 单剧整理预演（/preview）最多列出多少条计划
MAX_PREVIEW_ITEMS: Final[int] = 300
# 从记录库里按源目录反查一条记录时最多扫多少条
MAX_STORE_SCAN: Final[int] = 2000

# ------------------------------------------------------ 配置页的目录候选
#
# 候选有两个来源：系统配置里的整理目录（下载/媒体库成对）与这些目录下的一级子目录
# （即「浏览」）。两者都塞进下拉，用户在页面上直接挑，也能手输任意路径。

# 每个根目录最多列出多少个子目录（够挑，又不至于把下拉撑成滚不到底的长列表）
DIR_OPTION_PER_ROOT: Final[int] = 30
# 下拉候选总条数上限（防止目录爆炸把表单撑死）
DIR_OPTION_TOTAL: Final[int] = 300
# 未配置整理目录时的兜底挂载点（存在才列出）
DOWNLOAD_ROOTS: Final[tuple[str, ...]] = ("/downloads",)
LIBRARY_ROOTS: Final[tuple[str, ...]] = ("/media",)

# 扫描/整理状态（前端进度条按此渲染）
STATE_IDLE: Final[str] = "idle"
STATE_SCANNING: Final[str] = "scanning"
STATE_ORGANIZING: Final[str] = "organizing"
STATE_STOPPING: Final[str] = "stopping"

# 单条记录的处理状态（扫描预览用；真正落库以系统整理历史为准）
RECORD_PENDING: Final[str] = "pending"        # 已识别，待整理
RECORD_DONE: Final[str] = "done"              # 整理成功（已写入系统历史）
RECORD_SKIPPED: Final[str] = "skipped"        # 已在历史中，跳过
RECORD_UNRECOGNIZED: Final[str] = "unrecognized"  # 百科无候选

# 集号提取正则源（naming.py 使用，放在常量便于集中维护）。
#
# ⚠️ 顺序即优先级（2026-10-23 实测撕夜 74 集全灭后定稿）：
#   1. `SxxExx` 必须放最前 —— 发行名里的年份（`撕夜.Si.Ye.2025.S01...`）会先被
#      通用 `E` 模式当成集号（`e.2025` → 2025），74 个文件全塌成一个集号；
#   2. 通用 `E` 模式限 1–3 位：4 位数字（1900/2025 这类年份）故意放过，
#      宁可提不到集号走自然序补齐，也不能把年份当集号。
EPISODE_PATTERNS: Final[tuple[str, ...]] = (
    r"[Ss]\d{1,2}[.\- ]?[Ee](\d{1,4})",
    r"[Ee][Pp]?\.?\s*0*(\d{1,3})",
    r"第\s*0*(\d{1,4})\s*[集话話期]",
    r"\[0*(\d{1,4})\]",
    r"[_\-\s]0*(\d{1,4})$",
    r"^0*(\d{1,4})$",
)

# 允许整理的媒体扩展名
VIDEO_EXTENSIONS: Final[tuple[str, ...]] = (
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m2ts",
    ".rmvb", ".webm", ".m4v", ".mpg", ".mpeg",
)

# 刮削检测（organize.is_scraped 用）：剧目录或任一季目录出现这些文件即视为已刮削。
# 只认「元数据产物」，不认视频本身 —— 判断的是「有没有被刮削过」，不是「有没有文件」。
SCRAPE_NFO_NAMES: Final[tuple[str, ...]] = ("tvshow.nfo", "season.nfo")
SCRAPE_IMAGE_NAMES: Final[tuple[str, ...]] = (
    "poster.jpg", "poster.png",
    "fanart.jpg", "fanart.png",
    "folder.jpg", "folder.png",
    "backdrop.jpg", "backdrop.png",
    "thumb.jpg",
)

# 记录状态（store.py 入库用）
STORE_RECOGNIZED: Final[str] = "recognized"        # 已识别（百科有身份）
STORE_UNRECOGNIZED: Final[str] = "unrecognized"    # 未识别
