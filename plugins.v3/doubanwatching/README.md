# 豆瓣书影音档案（MoviePilot v3 兼容修补版）

原插件：[honue](https://github.com/honue) 的 `DouBanWatching`。
本副本仅做 **v3.1.x API 兼容修补**，功能与用法完全不变，用于原版在 MoviePilot v3.1.8 上直接崩溃、无法同步的场景。

## 原版在 v3.1.8 上的症状

每个播放事件都会抛异常，事件根本走不到豆瓣，插件日志里除了「开始播放」什么都没有：

```
TypeError: RecognitionMixin.recognize_media() got an unexpected keyword argument 'tmdbid'
```

## 修补内容（共 3 处，均在 `__init__.py`）

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
   部分媒体服务器上报的事件没有 `season_id` / `episode_id`，旧代码 `int(None)` 直接抛 `TypeError`。
   现在改为打印一条 WARN 并跳过该条同步，不影响其它事件。

`DoubanHelper.py` 未改动（豆瓣搜索页 `div.title` 解析在 v3.1.8 上仍可用，电影标题带 `(2024)` 后缀也能命中）。

## 使用须知

- 配置项 `user`（媒体库用户名）填的是 **Emby/Jellyfin/Plex 的媒体库用户名**，
  **不是豆瓣 uid**。填错会导致插件把事件静默丢弃（连一行日志都不会有），是最常见的「完全失效」原因。
- 建议从本仓库（自建插件源）安装，避免 MoviePilot 升级或官方插件市场重装时被旧版覆盖。

## 版本

- `1.9.7` — v3.1.x API 兼容修补（本仓库）
- `1.9.6` — 上游原版
