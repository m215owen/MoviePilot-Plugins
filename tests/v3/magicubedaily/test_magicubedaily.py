"""魔搭魔粒签到 —— 纯逻辑回归测试。

刻意**不 import pytest**：宿主容器里没有 pytest（宿主 venv 也没装），
所以全部用裸 ``assert``，既能被宿主的 pytest 收集，也能在容器里直接执行::

    docker exec moviepilot python /tmp/test_v3_magicubedaily.py

只测纯函数与纯逻辑，不出网、不碰宿主配置。
"""

from __future__ import annotations

import re
import sys

sys.path.insert(0, "/app/app/plugins")

from magicubedaily.chart import render_wave_svg  # noqa: E402
from magicubedaily.client import cookie_header, parse_cookie_input, pick_modelscope_cookies  # noqa: E402
from magicubedaily.service import (  # noqa: E402
    build_balance_samples,
    build_daily_series,
    build_days,
    summarize_records,
    today_str,
)


# ── cookie 解析 ───────────────────────────────────────────────────


def test_parse_cookie_header_text():
    jar = parse_cookie_input("m_session_id=abc123; t=xyz")
    assert jar == {"m_session_id": "abc123", "t": "xyz"}, jar


def test_parse_cookie_with_prefix_and_newlines():
    jar = parse_cookie_input("Cookie: a=1;\n b=2;\r\n c=3")
    assert jar == {"a": "1", "b": "2", "c": "3"}, jar


def test_parse_cookie_editor_json():
    raw = '[{"name":"m_session_id","value":"s1","domain":".modelscope.cn"},{"name":"t","value":"v2"}]'
    jar = parse_cookie_input(raw)
    assert jar == {"m_session_id": "s1", "t": "v2"}, jar


def test_parse_plain_json_object():
    assert parse_cookie_input('{"a":"1","b":2}') == {"a": "1", "b": "2"}


def test_parse_cookie_empty_and_garbage():
    assert parse_cookie_input("") == {}
    assert parse_cookie_input("   ") == {}
    # 没有等号的片段被丢弃，不会产出空名 cookie
    assert parse_cookie_input("noise; a=1") == {"a": "1"}


def test_parse_cookie_value_with_equals():
    jar = parse_cookie_input("token=a=b=c")
    assert jar == {"token": "a=b=c"}, jar


def test_cookie_header_round_trip():
    assert cookie_header({"a": "1", "b": "2"}) == "a=1;b=2"
    assert cookie_header({}) == ""


# ── CookieCloud 域名挑选 ──────────────────────────────────────────


def test_pick_modelscope_cookies_merges_subdomains():
    contents = {
        ".modelscope.cn": [
            {"name": "m_session_id", "value": "apex", "domain": ".modelscope.cn"},
            {"name": "modelscope-locale", "value": "zh", "domain": ".modelscope.cn"},
        ],
        "www.modelscope.cn": [
            # 更具体的域应覆盖宽域的同名值
            {"name": "m_session_id", "value": "www", "domain": "www.modelscope.cn"},
        ],
    }
    jar = pick_modelscope_cookies(contents)
    assert jar["m_session_id"] == "www", jar
    assert jar["modelscope-locale"] == "zh", jar


def test_pick_modelscope_cookies_ignores_other_domains():
    contents = {
        "douban.com": [{"name": "dbcl2", "value": "x", "domain": ".douban.com"}],
        ".modelscope.cn": [{"name": "m_session_id", "value": "s", "domain": ".modelscope.cn"}],
    }
    jar = pick_modelscope_cookies(contents)
    assert set(jar) == {"m_session_id"}, jar


def test_pick_modelscope_cookies_without_domain_field_uses_group_key():
    contents = {"passport.modelscope.cn": [{"name": "t", "value": "v1"}]}
    assert pick_modelscope_cookies(contents) == {"t": "v1"}


def test_pick_modelscope_cookies_handles_garbage():
    assert pick_modelscope_cookies(None) == {}
    assert pick_modelscope_cookies({"x": "not-a-list"}) == {}
    assert pick_modelscope_cookies({".modelscope.cn": [None, {"value": "no-name"}]}) == {}


# ── 流水汇总 ──────────────────────────────────────────────────────

SAMPLE_TODAY = [
    {
        "gmt_created": "2026-10-21",
        "type": "EARN",
        "rule_key": "daily_active",
        "title": "注册并登录",
        "total_amount": 200,
        "expire_at": "2026-10-22 21:45:20",
    },
    {
        "gmt_created": "2026-10-21",
        "type": "EARN",
        "rule_key": "aliyun_bindlogin",
        "title": "绑定阿里云账号",
        "total_amount": 50,
        "expire_at": "2026-10-22 21:45:20",
    },
    {
        "gmt_created": "2026-10-21",
        "type": "EXPIRE",
        "rule_key": "expire",
        "title": "魔粒过期",
        "total_amount": 250,
    },
    {
        "gmt_created": "2026-10-20",
        "type": "EARN",
        "rule_key": "daily_active",
        "title": "注册并登录",
        "total_amount": 200,
    },
]


def test_summarize_today_counts_only_earn():
    summary = summarize_records(SAMPLE_TODAY, "2026-10-21")
    assert summary.total == 250, summary
    assert summary.login_done is True
    assert summary.aliyun_done is True
    assert summary.expire_at == "2026-10-22 21:45:20"
    # 昨日记录不能混进今天
    assert all(item["rule_key"] != "expire" for item in summary.items)


def test_summarize_today_without_records():
    summary = summarize_records([], "2026-10-21")
    assert summary.total == 0
    assert summary.login_done is False
    assert summary.aliyun_done is False
    assert summary.items == []


def test_summarize_today_login_only():
    summary = summarize_records(SAMPLE_TODAY[:1], "2026-10-21")
    assert summary.total == 200
    assert summary.login_done is True
    assert summary.aliyun_done is False


def test_summarize_daily_items_first():
    records = SAMPLE_TODAY + [
        {
            "gmt_created": "2026-10-21",
            "type": "EARN",
            "rule_key": "like",
            "title": "收藏 / 点赞",
            "total_amount": 40,
        }
    ]
    summary = summarize_records(records, "2026-10-21")
    assert summary.total == 290
    keys = [item["rule_key"] for item in summary.items]
    # 每日发放两条排在前面，点赞这类跟在后面
    assert keys[:2] == ["daily_active", "aliyun_bindlogin"], keys
    assert keys[-1] == "like"
    assert summary.login_done is True


def test_summarize_accepts_datetime_string():
    records = [{"gmt_created": "2026-10-21 21:45:20", "type": "EARN",
                "rule_key": "daily_active", "total_amount": 200}]
    summary = summarize_records(records, "2026-10-21")
    assert summary.total == 200


def test_summarize_is_case_insensitive_on_type():
    records = [{"gmt_created": "2026-10-21", "type": "earn",
                "rule_key": "daily_active", "total_amount": 200}]
    assert summarize_records(records, "2026-10-21").total == 200


def test_summarize_ignores_bad_amount():
    records = [{"gmt_created": "2026-10-21", "type": "EARN",
                "rule_key": "daily_active", "total_amount": "oops"}]
    summary = summarize_records(records, "2026-10-21")
    assert summary.total == 0
    assert summary.login_done is False


# ── 按天聚合 ──────────────────────────────────────────────────────


def test_build_days_orders_desc_and_limits():
    days = build_days(SAMPLE_TODAY, 7)
    assert [row["date"] for row in days] == ["2026-10-21", "2026-10-20"], days
    assert days[0]["total"] == 250
    assert days[0]["login_done"] is True
    assert days[1]["total"] == 200


def test_build_days_respects_limit():
    days = build_days(SAMPLE_TODAY, 1)
    assert len(days) == 1
    assert days[0]["date"] == "2026-10-21"


def test_build_days_ignores_spend_only_days():
    records = [{"gmt_created": "2026-10-19", "type": "SPEND_CONFIRM",
                "rule_key": "api_inference", "total_amount": 90}]
    assert build_days(records, 7) == []


# ── 日期工具 ──────────────────────────────────────────────────────


def test_today_str_format():
    value = today_str()
    assert len(value) == 10 and value[4] == "-" and value[7] == "-", value


# ── 余额走势：只统计自动刷新的实测数据 ──────────────────────────


def test_daily_series_uses_only_local_samples():
    """走势只吃插件自己采到的数据：给了什么就画什么，不做任何推算。"""
    series = build_daily_series({"2026-10-20": 250, "2026-10-21": 260}, days=14)
    assert series == [
        {"date": "2026-10-20", "balance": 250},
        {"date": "2026-10-21", "balance": 260},
    ], series


def test_daily_series_empty_when_no_samples():
    assert build_daily_series({}, days=14) == []
    assert build_daily_series(None, days=14) == []


def test_daily_series_keeps_latest_days_only():
    history = {f"2026-10-{day:02d}": 100 + day for day in range(1, 21)}
    series = build_daily_series(history, days=3)
    assert [row["date"] for row in series] == ["2026-10-18", "2026-10-19", "2026-10-20"], series


def test_daily_series_skips_garbage_keys():
    series = build_daily_series({"bad": 1, "2026-10-21": "oops", "2026-10-20": 200}, days=14)
    assert series == [{"date": "2026-10-20", "balance": 200}], series


def test_samples_sorted_and_deduped():
    raw = [
        {"ts": "2026-10-21 22:30:00", "balance": 240},
        {"ts": "2026-10-21 22:00:00", "balance": 250},
        {"ts": "2026-10-21 22:30:00", "balance": 245},
    ]
    samples = build_balance_samples(raw, hours=2400)
    assert [row["ts"] for row in samples] == ["2026-10-21 22:00:00", "2026-10-21 22:30:00"]
    # 同一秒重复采样，保留最后一条
    assert samples[-1]["balance"] == 245


def test_samples_drop_out_of_window_and_bad_rows():
    raw = [
        {"ts": "2000-01-01 00:00:00", "balance": 1},
        {"ts": "not-a-time", "balance": 2},
        {"ts": "2026-10-21 22:00:00", "balance": "x"},
        {"ts": "2026-10-21 23:00:00", "balance": 250},
    ]
    samples = build_balance_samples(raw, hours=24)
    # 2000 年那条超出 24 小时窗口，其余三条格式非法
    assert [row["balance"] for row in samples] in ([], [250]), samples


def test_samples_accept_non_list():
    assert build_balance_samples(None) == []
    assert build_balance_samples({"a": 1}) == []


def test_wave_svg_contains_values_and_curve():
    svg = render_wave_svg([("2026-10-19", 100), ("2026-10-20", 250), ("2026-10-21", 250)])
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "250" in svg and "2026-10-21"[-5:] in svg
    # 平滑曲线 = 三次贝塞尔
    assert " C " in svg


def test_wave_svg_single_point_and_empty():
    one = render_wave_svg([("2026-10-21", 250)])
    assert "<svg" in one and "250" in one
    empty = render_wave_svg([])
    assert "暂无余额数据" in empty


def test_wave_svg_control_points_do_not_overshoot():
    """台阶数据（190 → 250）不得画出比两端更低/更高的假起伏。"""
    svg = render_wave_svg([("2026-10-19", 190), ("2026-10-20", 250), ("2026-10-21", 250)])
    dot_ys = [float(value) for value in re.findall(r'<circle cx="[\d.]+" cy="([\d.]+)"', svg)]
    assert dot_ys, svg
    low, high = min(dot_ys), max(dot_ys)
    ctrl_ys = [
        float(value)
        for value in re.findall(r"C\s+[\d.]+\s+([\d.]+)\s+[\d.]+\s+([\d.]+)", svg)
        for value in value
    ]
    assert ctrl_ys, svg
    assert all(low - 0.5 <= value <= high + 0.5 for value in ctrl_ys), (low, high, ctrl_ys)


def test_wave_svg_time_axis_uses_real_intervals():
    """刷新间隔不均时横轴按真实时间比例铺开 —— 刷新周期才真的体现在图上。"""
    svg = render_wave_svg(
        [
            ("2026-10-21 08:00:00", 100),
            ("2026-10-21 08:30:00", 200),
            ("2026-10-21 12:30:00", 200),
        ],
        time_axis=True,
    )
    xs = [float(value) for value in re.findall(r'<circle cx="([\d.]+)"', svg)]
    assert len(xs) == 3, svg
    first_gap, second_gap = xs[1] - xs[0], xs[2] - xs[1]
    # 30 分钟 vs 4 小时 ⇒ 第二段宽度应是第一段的 8 倍
    assert abs(second_gap / first_gap - 8) < 0.5, (first_gap, second_gap)


def test_wave_svg_time_labels_are_hour_minute():
    svg = render_wave_svg(
        [("2026-10-21 08:00:00", 100), ("2026-10-21 09:00:00", 200)], time_axis=True
    )
    assert ">08:00<" in svg and ">09:00<" in svg, svg


def main() -> None:
    """容器内直接执行时的入口（宿主 CI 用 pytest 收集同一批用例）。"""
    cases = [(name, obj) for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    for name, func in cases:
        func()
        print(f"  ok  {name}")
    print(f"全部通过：{len(cases)} 项")


if __name__ == "__main__":
    main()
