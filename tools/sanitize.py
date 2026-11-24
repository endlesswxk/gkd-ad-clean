#!/usr/bin/env python3
"""把上游 GKD 订阅裁剪成"只关广告、不含任何安全相关点击"的纯净版。

输入：上游 dist 订阅文件（JSON5）
输出：dist/gkd.json5 + dist/gkd.version.json5（纯 JSON，JSON5 的子集）

策略
----
1. 只保留组名前缀属于【开屏广告 / 全屏广告 / 局部广告 / 分段广告】的规则组；
   其余分类（功能类/其他/更新提示/权限提示/青少年模式/通知提示/评价提示）整组丢弃。
2. 删除 globalGroups（跨 App 生效的全局规则），一条不留。
3. 在保留下来的组里，逐条规则做两道过滤：
   - HARD_DANGER：选择器里出现安装/卸载/授权/允许/同意/确认/支付/密码/验证码/
     USB调试/屏幕共享/远程/无障碍/购买/下单 等字样 → 删除该规则；
   - CTA_GUARD：选择器里有广告 CTA 字样（立即下载/领取/红包/查看详情…）但整条规则
     没有任何"关闭类"锚点（关闭/跳过/close/取消…）→ 删除，避免把广告点开而不是关掉。
4. 保留下来的组一律 enable=true，分类也全部 enable=true（GKD 里分类开关优先级高于
   组开关，两边写一致才不会出现"看着是开其实没开"）。
5. version = 上游 version * 100 + REV，保证单调递增（上游升版本 / 本脚本改策略都能让
   手机端正确收到更新）。

用法
----
  python3 tools/sanitize.py upstream.json5 dist/gkd.json5 \
      --owner <github用户> --repo <仓库名> [--id 6688] [--name 订阅名]
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json5

# ---------------------------------------------------------------- 配置区

DEFAULT_ID = 6688
DEFAULT_NAME = "纯净去广告订阅"
DEFAULT_AUTHOR = "self"

# 只保留这些分类（按组名前缀匹配，GKD 的 RawSubscription.getCategory 就是这么判定的）
KEEP_CATEGORIES = ["开屏广告", "全屏广告", "局部广告", "分段广告"]

# 消毒器自身的修订号：改了过滤策略就 +1，手机端才会收到更新
REV = 1
VERSION_STRIDE = 100

# 出现即删（安全相关：点下去可能造成损失或放行权限）
# 注意：不要放 root / adb / su / 更新 / 升级 / 权限 这类过于宽泛的词——
# 广告 SDK 的节点 id 里满是 root_view、ksad_*_root_container，会误杀正常规则。
HARD_DANGER = re.compile(
    "|".join(
        [
            "安装", "卸载", "应用市场", "未知来源", "外部来源",
            "允许", "同意", "授权", "确认", "确定", "已了解", "我已阅读",
            "支付", "付款", "免密", "刷脸", "钱包", "银行卡",
            "密码", "验证码", "短信", "SIM卡", "身份验证",
            "USB", "调试", "投屏", "共享屏幕", "共享整个屏幕", "录屏", "屏幕录制", "远程",
            "无障碍", "设备管理",
            "清除", "删除", "格式化", "恢复出厂", "注销",
            "购买", "下单", "结算", "充值", "提现",
        ]
    ),
    re.I,
)

# 广告 CTA（点下去是"打开广告"而不是"关广告"）
CTA = re.compile(
    "|".join(
        [
            "领取", "红包", "抽奖", "奖励", "金币", "签到", "立即", "下载", "详情", "查看",
            "去看看", "去逛逛", "逛逛", "优惠", "进入", "前往", "打开", "试用", "体验",
            "报名", "参与", "点击即可", "了解",
        ]
    ),
    re.I,
)

# 关闭类锚点：只要规则里出现这些，就认为点击目标大概率是关闭按钮
DISMISS = re.compile(
    "|".join(
        [
            "关闭", "关闭广告", "跳过", "跳 过", "跳過", "skip", "close", "cancel",
            "取消", "忽略", "不再", "别显示", "dismiss", "dimiss", "later", "×",
            "返回", "back", "不感兴趣", "dislike", "feed_back", "feedback",
        ]
    ),
    re.I,
)

# 目标节点本身就是"小叉号"的特征（很多规则靠 @ImageView[width<90 && height<90] 定位关闭按钮，
# 旁边的 CTA 文案只是锚点，这类规则必须保留）
SMALL_BOX = re.compile(r"width\s*<=?\s*\d{1,3}(?!\d)", re.I)
SMALL_BOX_H = re.compile(r"height\s*<=?\s*\d{1,3}(?!\d)", re.I)

# 这些 App 里的任何规则都不保留（系统安装器 / 权限 / 系统界面 / 安全管家）
BLOCK_APPS = re.compile(
    r"packageinstaller|permissioncontroller|^com\.android\.settings$|systemui|securitycenter|"
    r"securityadd|systemmanager|safecenter|lool|devicepolicy|com\.android\.shell|providers\.settings",
    re.I,
)

ALLOWED_ACTIONS = {None, "click", "clickCenter", "longClick", "longClickCenter", "back", "swipe", "none"}

# 输出里允许出现的字段（防止上游塞奇怪的东西进来）
RULE_KEYS = {
    "key", "name", "desc", "matches", "anyMatches", "excludeMatches", "excludeAllMatches",
    "action", "position", "actionCd", "actionDelay", "actionMaximum", "actionMaximumKey",
    "actionCdKey", "matchTime", "matchDelay", "resetMatch", "fastQuery", "matchRoot",
    "activityIds", "excludeActivityIds", "versionCode", "versionName", "preKeys",
    "snapshotUrls", "exampleUrls", "excludeSnapshotUrls", "order", "forcedTime",
    "priorityTime", "priorityActionMaximum",
}
GROUP_KEYS = RULE_KEYS | {"rules", "enable", "scopeKeys", "ignoreGlobalGroupMatch"}
APP_KEYS = {"id", "name", "groups", "enable", "versionCode", "versionName"}

report = {"dropped_group_other_category": 0, "dropped_rule_hard": 0, "dropped_rule_cta": 0,
          "dropped_rule_empty": 0, "dropped_app_empty": 0, "dropped_app_blocked": 0,
          "dropped_global_groups": 0, "dropped_unknown_action": 0,
          "kept_rules": 0, "kept_groups": 0, "kept_apps": 0}


def as_list(v):
    return [] if v is None else (v if isinstance(v, list) else [v])


def norm_rules(group):
    """GKD 允许组内单条规则写成字符串 / 对象 / 数组，统一成 list[dict]。"""
    raw = group.get("rules")
    if raw is None:
        return []
    if isinstance(raw, str):
        return [{"matches": raw}]
    if isinstance(raw, dict):
        return [dict(raw)]
    out = []
    for item in raw:
        if isinstance(item, str):
            out.append({"matches": item})
        elif isinstance(item, dict):
            out.append(dict(item))
    return out


def selector_text(rule):
    parts = []
    for k in ("matches", "anyMatches", "excludeMatches", "excludeAllMatches"):
        parts.extend(str(x) for x in as_list(rule.get(k)))
    return " ".join(parts)


def target_expr(txt):
    """粗略取"点击目标节点"所在的片段：最后一个 @ 之后（没有 @ 就看整条）。"""
    i = txt.rfind("@")
    return txt[i:] if i >= 0 else txt


def looks_like_close(txt):
    """点击目标本身像关闭控件（小叉号/close 类 id/关闭文案）。"""
    t = target_expr(txt)
    if DISMISS.search(t):
        return True
    return bool(SMALL_BOX.search(t) and SMALL_BOX_H.search(t))


def keep_rule(rule, check_cta=True):
    """返回 (保留?, 丢弃原因)

    check_cta=False 时跳过 CTA_GUARD（附加订阅里的"看广告领奖励"这类规则本身就是
    点奖励/关闭，天然带 CTA 词，但仍要过 HARD_DANGER）。
    """
    action = rule.get("action")
    if action not in ALLOWED_ACTIONS:
        return False, "unknown_action"
    txt = selector_text(rule)
    if not txt.strip():
        return False, "empty"
    if HARD_DANGER.search(txt):
        return False, "hard"
    if check_cta and CTA.search(txt) and not (DISMISS.search(txt) or looks_like_close(txt)):
        return False, "cta"
    return True, None


def clean_dict(d, allowed):
    return {k: v for k, v in d.items() if k in allowed}


def sanitize(sub, sub_id, sub_name, author, support_uri):
    out = {
        "id": sub_id,
        "name": sub_name,
        "version": 0,
        "author": author,
        "checkUpdateUrl": "./gkd.version.json5",
    }
    if support_uri:
        out["supportUri"] = support_uri

    # 分类：只留四个广告分类，且全部显式启用
    out["categories"] = [{"key": i, "name": name, "enable": True} for i, name in enumerate(KEEP_CATEGORIES)]

    # 全局规则：全部丢弃
    report["dropped_global_groups"] = len(sub.get("globalGroups") or [])

    apps_out = []
    for app in sub.get("apps") or []:
        if not isinstance(app, dict) or not app.get("id"):
            continue
        if BLOCK_APPS.search(app["id"]):
            report["dropped_app_blocked"] += 1
            continue
        groups_out = []
        for group in as_list(app.get("groups")):
            if not isinstance(group, dict):
                continue
            gname = group.get("name") or ""
            if not any(gname.startswith(c) for c in KEEP_CATEGORIES):
                report["dropped_group_other_category"] += 1
                continue
            rules_out = []
            for rule in norm_rules(group):
                ok, why = keep_rule(rule)
                if not ok:
                    if why == "hard":
                        report["dropped_rule_hard"] += 1
                    elif why == "cta":
                        report["dropped_rule_cta"] += 1
                    elif why == "unknown_action":
                        report["dropped_unknown_action"] += 1
                    else:
                        report["dropped_rule_empty"] += 1
                    continue
                rules_out.append(clean_dict(rule, RULE_KEYS))
            if not rules_out:
                report["dropped_rule_empty"] += 1
                continue
            g = clean_dict(group, GROUP_KEYS)
            g.pop("rules", None)
            g["enable"] = True
            g["rules"] = rules_out
            groups_out.append(g)
            report["kept_groups"] += 1
            report["kept_rules"] += len(rules_out)
        if not groups_out:
            report["dropped_app_empty"] += 1
            continue
        a = clean_dict(app, APP_KEYS)
        a.pop("groups", None)
        a["groups"] = groups_out
        apps_out.append(a)
        report["kept_apps"] += 1

    out["apps"] = apps_out
    return out


def self_check(path, sub_id):
    with open(path, encoding="utf-8") as f:
        got = json5.loads(f.read(), path)
    assert got["id"] == sub_id, "id mismatch"
    assert "globalGroups" not in got, "globalGroups 没清干净"
    bad = []
    n = 0
    for app in got["apps"]:
        assert not BLOCK_APPS.search(app["id"]), f"黑名单 App 泄漏: {app['id']}"
        for g in app["groups"]:
            assert g["enable"] is True, "有组没被启用"
            assert any(g["name"].startswith(c) for c in KEEP_CATEGORIES), f"非广告组泄漏: {g['name']}"
            for r in g["rules"]:
                n += 1
                ok, why = keep_rule(r)
                if not ok:
                    bad.append((app["id"], g["name"], why, selector_text(r)[:120]))
    if bad:
        print("!! 自检失败，仍有 %d 条危险规则：" % len(bad))
        for b in bad[:10]:
            print("   ", b)
        raise SystemExit(1)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("upstream")
    ap.add_argument("out")
    ap.add_argument("--owner", default="", help="GitHub 用户名，用于生成 supportUri")
    ap.add_argument("--repo", default="", help="仓库名，用于生成 supportUri")
    ap.add_argument("--id", type=int, default=DEFAULT_ID)
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--author", default="")
    args = ap.parse_args()

    with open(args.upstream, encoding="utf-8") as f:
        sub = json5.loads(f.read(), args.upstream)

    upstream_version = int(sub.get("version") or 0)
    author = args.author or sub.get("author") or DEFAULT_AUTHOR
    support_uri = f"https://github.com/{args.owner}/{args.repo}/issues" if args.owner and args.repo else None

    out = sanitize(sub, args.id, args.name, author, support_uri)
    out["version"] = upstream_version * VERSION_STRIDE + REV
    out = {"id": out.pop("id"), "name": out.pop("name"), "version": out.pop("version"),
           "author": out.pop("author"), **out}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    vpath = os.path.join(os.path.dirname(args.out), "gkd.version.json5")
    with open(vpath, "w", encoding="utf-8") as f:
        f.write("{id:%d,version:%d}\n" % (out["id"], out["version"]))

    n = self_check(args.out, args.id)

    print(json.dumps({
        "upstream_version": upstream_version,
        "published_version": out["version"],
        "apps": report["kept_apps"],
        "groups": report["kept_groups"],
        "rules": n,
        "dropped": {k: v for k, v in report.items() if k.startswith("dropped")},
        "output": args.out,
        "bytes": os.path.getsize(args.out),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
