# 豆瓣书影音档案-修复版（`DouBanWatchingFix`）

原插件：[honue](https://github.com/honue) 的 `DouBanWatching`（豆瓣书影音档案）。
本副本是它的 **MoviePilot v3.1.x API 兼容修复版**，功能与用法完全不变，用于原版在 v3.1.8 / v3.1.9 上每个播放事件都抛异常、完全无法同步的场景。

> **为什么不叫原来那个名字**：这是修改他人插件的分叉版本，为避免和官方插件市场里的原版 `DouBanWatching`
> 重名冲突，插件 ID 改为 `DouBanWatchingFix`、名称改为「豆瓣书影音档案-修复版」。两者可以并存，
> **同时启用会重复同步**，请只保留一个处于启用状态。

## 原版在 v3.1.x 上的症状

每个播放事件都会抛异常，事件根本走不到豆瓣，插件日志里除了「开始播放」什么都没有：

```
TypeError: RecognitionMixin.recognize_media() got an unexpected keyword argument 'tmdbid'
```

## 修复内容（均在 `__init__.py`）

1. **媒体识别改用新的媒体身份模型**
   v3.1.x 的 `MediaChain().recognize_media()` 已移除 `tmdbid` 关键字，媒体身份改为
   `(media_source, media_id)` 成对传入：

   ```python
   # 旧
   MediaChain().recognize_media(meta=meta, mtype=meta.type, tmdbid=tmdb_id, cache=True)
   # 新
   MediaChain().recognize_media(meta=meta, mtype=meta.type,
                                media_source=media_source, media_id=media_id, cache=True)
   ```

2. **`WebhookEventInfo` 不再有 `tmdb_id` 字段**
   宿主侧已提供迁移器，把它转成 `media_source` + `media_id`；插件改为直接读这两个字段，
   并删掉旧写法 `meta.tmdbid = None`（该属性在 v3.1.x 已不存在，赋值无效）。

3. **缺季/集编号时不再崩溃**
   部分媒体服务器上报的事件没有 `season_id` / `episode_id`，旧代码 `int(None)` 直接抛 `TypeError`；
   标题没有 ` SxxExx` 标识时 `str.index(" S")` 也会抛 `ValueError`。
   现在改为打印一条 WARN 并跳过该条同步，不影响其它事件。

4. **首次运行自动继承原版的配置与已同步记录**
   插件 ID 变了，宿主会把本插件当成全新插件；`init_plugin` 里做了一次性继承：
   从旧 ID `DouBanWatching` 读取配置（用户名、排除关键词、豆瓣 cookie、是否仅自己可见等）与
   `data` / `wait` 记录，写入本插件。继承后仍需自行到配置页确认，并**手动启用本插件、停用原版**。

`DoubanHelper.py` 未改动（豆瓣搜索页 `div.title` 解析在 v3.1.9 上仍可用，电影标题带 `(2024)` 后缀也能命中）。

## 使用须知

- 配置项 `user`（媒体库用户名）填的是 **Emby/Jellyfin/Plex 的媒体库用户名**，
  **不是豆瓣 uid**。填错会导致插件把事件静默丢弃（连一行日志都不会有），是最常见的「完全失效」原因。
- 建议从本仓库（自建插件源）安装，避免 MoviePilot 升级或官方插件市场重装时被旧版覆盖。
- 豆瓣条目是按**标题**去豆瓣搜索匹配的第一条，同名/近似标题会认错片（例如匹配到另一部同字幕的电影），
  属上游既有行为，介意的话同步后自行到豆瓣核对。

## 版本

- `1.9.7` — v3.1.x API 兼容修复版（本仓库，ID 改为 `DouBanWatchingFix`）
- `1.9.6` — 上游原版
