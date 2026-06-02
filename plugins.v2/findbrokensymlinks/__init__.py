import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.core.event import Event, eventmanager
from app.plugins import _PluginBase
from app.schemas.types import EventType


class FindBrokenSymlinks(_PluginBase):
    # ──────── 插件元数据 ────────
    plugin_name = "查找失效软链接"
    plugin_desc = "扫描指定目录中的失效软链接，并在详情面板展示结果。"
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "1.0.0"
    plugin_author = "AI"
    author_url = ""
    plugin_config_prefix = "findbrokensymlinks_"
    plugin_order = 0
    auth_level = 1

    # ──────── 运行时状态 ────────
    _enabled = False
    _scan_dirs: List[str] = []
    _ignore_paths: List[str] = []
    _max_depth: int = 10
    _results: List[Dict[str, str]] = []
    _last_scan_time: str = ""

    # ========================================================================
    # 生命周期
    # ========================================================================

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._scan_dirs = self._parse_path_list(config.get("scan_dirs", ""))
        self._ignore_paths = self._parse_path_list(config.get("ignore_paths", ""))
        try:
            self._max_depth = int(config.get("max_depth", 10))
        except (ValueError, TypeError):
            self._max_depth = 10

        self._results = self.get_data("last_results") or []
        self._last_scan_time = self.get_data("last_scan_time") or ""

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self):
        pass

    # ========================================================================
    # 远程命令
    # ========================================================================

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/scan_broken_links",
                "event": EventType.PluginAction,
                "desc": "立即扫描失效软链接",
                "category": "文件管理",
                "data": {"action": "scan_broken_links"},
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def run_command(self, event: Event):
        event_data = event.event_data or {}
        if event_data.get("action") != "scan_broken_links":
            return
        self.info("收到远程命令，开始扫描失效软链接...")
        results = self.scan_broken_links()
        if results:
            self.post_message(
                title="扫描完成 - 发现失效软链接",
                text=f"共发现 {len(results)} 个失效软链接，请查看详情页。",
            )
        else:
            self.post_message(
                title="扫描完成 - 未发现失效软链接",
                text="扫描范围内所有软链接均有效。",
            )

    # ========================================================================
    # API
    # ========================================================================

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/scan",
                "endpoint": self.api_scan,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "触发扫描",
            },
            {
                "path": "/results",
                "endpoint": self.api_get_results,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取扫描结果",
            },
        ]

    async def api_scan(self):
        results = self.scan_broken_links()
        return {"success": True, "count": len(results), "results": results}

    async def api_get_results(self):
        return {"success": True, "count": len(self._results), "results": self._results}

    # ========================================================================
    # 配置表单
    # ========================================================================

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "trigger_scan",
                                            "label": "触发扫描",
                                            "hint": "打开开关立即执行扫描",
                                            "persistent-hint": True,
                                        },
                                        "events": {
                                            "onchange": "form.plugin_action.trigger_scan_changed"
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "max_depth",
                                            "label": "扫描深度",
                                            "type": "number",
                                            "min": 1,
                                            "max": 50,
                                            "hint": "目录递归深度，默认 10",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "scan_dirs",
                                            "label": "扫描目录",
                                            "rows": 3,
                                            "placeholder": "每行一个目录，例如：\n/downloads\n/media/movies",
                                            "hint": "支持换行或逗号分隔",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "ignore_paths",
                                            "label": "忽略路径（支持通配符）",
                                            "rows": 3,
                                            "placeholder": "例如：\n*.tmp\n/downloads/temp/*",
                                            "hint": "每行一个，支持 * 通配符",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], {
            "enabled": False,
            "trigger_scan": False,
            "scan_dirs": "",
            "ignore_paths": "",
            "max_depth": 10,
        }

    # ========================================================================
    # 详情页（数据面板）
    # ========================================================================

    def get_page(self) -> List[dict]:
        # 无结果时的空状态
        if not self._results:
            return [
                {
                    "component": "VRow",
                    "content": [
                        {
                            "component": "VCol",
                            "props": {"cols": 12},
                            "content": [
                                {
                                    "component": "VAlert",
                                    "props": {
                                        "type": "info",
                                        "variant": "tonal",
                                        "text": "暂无扫描结果，请打开触发扫描开关或使用 /scan_broken_links 命令。",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ]

        # 构建表格行
        rows = []
        for i, item in enumerate(self._results):
            link = item.get("link", "")
            target = item.get("target", "")
            rows.append({
                "component": "tr",
                "content": [
                    {
                        "component": "td",
                        "props": {"class": "text-center text-caption"},
                        "content": [
                            {"component": "span", "text": str(i + 1)}
                        ],
                    },
                    {
                        "component": "td",
                        "props": {"class": "text-caption"},
                        "content": [
                            {
                                "component": "span",
                                "props": {"class": "text-break"},
                                "text": link,
                            }
                        ],
                    },
                    {
                        "component": "td",
                        "props": {"class": "text-caption"},
                        "content": [
                            {
                                "component": "span",
                                "props": {"class": "text-break"},
                                "text": target,
                            }
                        ],
                    },
                ],
            })

        return [
            # 摘要卡片
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "outlined"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "props": {"class": "text-center"},
                                        "content": [
                                            {
                                                "component": "span",
                                                "props": {"class": "text-caption text-medium-emphasis"},
                                                "text": "失效软链接总数",
                                            },
                                            {
                                                "component": "div",
                                                "props": {"class": "text-h4 text-primary font-weight-bold"},
                                                "text": str(len(self._results)),
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "outlined"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "props": {"class": "text-center"},
                                        "content": [
                                            {
                                                "component": "span",
                                                "props": {"class": "text-caption text-medium-emphasis"},
                                                "text": "扫描目录数",
                                            },
                                            {
                                                "component": "div",
                                                "props": {"class": "text-h4 font-weight-bold"},
                                                "text": str(len(self._scan_dirs)),
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "outlined"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "props": {"class": "text-center"},
                                        "content": [
                                            {
                                                "component": "span",
                                                "props": {"class": "text-caption text-medium-emphasis"},
                                                "text": "上次扫描时间",
                                            },
                                            {
                                                "component": "div",
                                                "props": {"class": "text-body-2 font-weight-bold"},
                                                "text": self._last_scan_time or "未知",
                                            },
                                        ],
                                    },
                                ],
                            }
                        ],
                    },
                ],
            },
            # 结果表格
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VTable",
                                "props": {
                                    "hover": True,
                                    "density": "compact",
                                    "fixed-header": True,
                                    "height": "calc(100vh - 300px)",
                                },
                                "content": [
                                    {
                                        "component": "thead",
                                        "content": [
                                            {
                                                "component": "tr",
                                                "content": [
                                                    {
                                                        "component": "th",
                                                        "props": {"width": "50px", "class": "text-center"},
                                                        "content": [
                                                            {"component": "span", "text": "#"}
                                                        ],
                                                    },
                                                    {
                                                        "component": "th",
                                                        "props": {"width": "45%"},
                                                        "content": [
                                                            {"component": "span", "text": "软链接路径"}
                                                        ],
                                                    },
                                                    {
                                                        "component": "th",
                                                        "props": {"width": "45%"},
                                                        "content": [
                                                            {"component": "span", "text": "目标路径"}
                                                        ],
                                                    },
                                                ],
                                            }
                                        ],
                                    },
                                    {"component": "tbody", "content": rows},
                                ],
                            }
                        ],
                    }
                ],
            },
        ]

    # ========================================================================
    # 核心业务逻辑
    # ========================================================================

    def scan_broken_links(self) -> List[Dict[str, str]]:
        """执行扫描，返回失效软链接列表"""
        if not self._scan_dirs:
            self.warn("未配置扫描目录")
            return []

        broken = []
        seen = set()

        for scan_dir in self._scan_dirs:
            scan_path = Path(scan_dir).expanduser().resolve()
            if not scan_path.exists():
                self.warn(f"扫描目录不存在，跳过: {scan_dir}")
                continue
            if not scan_path.is_dir():
                self.warn(f"路径不是目录，跳过: {scan_dir}")
                continue

            try:
                for entry in scan_path.rglob("*"):
                    try:
                        rel_depth = len(entry.relative_to(scan_path).parts)
                    except ValueError:
                        continue
                    if rel_depth > self._max_depth:
                        continue
                    if not entry.is_symlink():
                        continue
                    if self._should_ignore(str(entry)):
                        continue

                    try:
                        real_path = entry.resolve()
                    except OSError:
                        real_path = None
                    if real_path and real_path in seen:
                        continue
                    if real_path:
                        seen.add(real_path)

                    if real_path is None or not real_path.exists():
                        try:
                            target = os.readlink(str(entry))
                        except OSError:
                            target = "<读取失败>"
                        broken.append({
                            "link": str(entry),
                            "target": target if not os.path.isabs(target) else target,
                        })
            except PermissionError:
                self.warn(f"权限不足，部分路径跳过: {scan_dir}")
            except Exception as e:
                self.error(f"扫描异常 [{scan_dir}]: {e}")

        self._results = broken
        self._last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_data("last_results", broken)
        self.save_data("last_scan_time", self._last_scan_time)

        self.info(f"扫描完成，发现 {len(broken)} 个失效软链接")
        return broken

    def _should_ignore(self, path: str) -> bool:
        import fnmatch
        for pattern in self._ignore_paths:
            if not pattern.strip():
                continue
            if fnmatch.fnmatch(path, pattern):
                return True
            if fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        return False

    @staticmethod
    def _parse_path_list(raw: str) -> List[str]:
        if not raw or not raw.strip():
            return []
        result = []
        for line in raw.strip().splitlines():
            for item in line.split(","):
                item = item.strip()
                if item:
                    result.append(item)
        return result