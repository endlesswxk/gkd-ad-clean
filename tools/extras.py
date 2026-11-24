#!/usr/bin/env python3
"""附加订阅：只挑"看激励视频换免广告/听书时长"相关的功能类规则。

和主订阅严格分开：
- 主订阅 dist/gkd.json5（id 6688）只有"关广告"，不含任何功能类；
- 本脚本产出 dist/extras/fanqie.json5（id 6689），只放白名单里点名的组。

白名单按「包名 + 组名」双重限定，上游新增的功能类组不会意外混进来。
仍然过 HARD_DANGER（安装/支付/授权/密码… 一律不要），但跳过 CTA_GUARD——
这类规则天生就是点"领取/关闭"，用主订阅那套 CTA 过滤会被全删。

用法：
  python3 tools/extras.py upstream.json5 dist/extras/fanqie.json5 \
      --owner <github用户> --repo <仓库名>
"""

import argparse
import json
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json5
import sanitize as S

SUB_ID = 6689
SUB_NAME = "附加-番茄看广告助手"
REV = 1

# 包名 -> 允许进入附加订阅的组名（完全匹配）
EXTRA_GROUPS = OrderedDict([
    (
        "com.dragon.read",
        [
            "功能类-看广告自动领奖励",
            "功能类-观看广告自动静音",
        ],
    ),
])


def build(sub):
    apps_out = []
    stats = {"apps": 0, "groups": 0, "rules": 0, "dropped_rule_hard": 0, "dropped_rule_other": 0,
             "missing_groups": []}
    for app in sub.get("apps") or []:
        if not isinstance(app, dict):
            continue
        wanted = EXTRA_GROUPS.get(app.get("id") or "")
        if not wanted:
            continue
        found = set()
        groups_out = []
        for group in S.as_list(app.get("groups")):
            if not isinstance(group, dict) or group.get("name") not in wanted:
                continue
            found.add(group["name"])
            rules_out = []
            for rule in S.norm_rules(group):
                ok, why = S.keep_rule(rule, check_cta=False)
                if not ok:
                    if why == "hard":
                        stats["dropped_rule_hard"] += 1
                    else:
                        stats["dropped_rule_other"] += 1
                    continue
                rules_out.append(S.clean_dict(rule, S.RULE_KEYS))
            if not rules_out:
                continue
            g = S.clean_dict(group, S.GROUP_KEYS)
            g.pop("rules", None)
            g["enable"] = True
            g["rules"] = rules_out
            groups_out.append(g)
            stats["groups"] += 1
            stats["rules"] += len(rules_out)
        stats["missing_groups"].extend(sorted(set(wanted) - found))
        if groups_out:
            a = S.clean_dict(app, S.APP_KEYS)
            a.pop("groups", None)
            a["groups"] = groups_out
            apps_out.append(a)
            stats["apps"] += 1

    for app_id, names in EXTRA_GROUPS.items():
        if app_id not in [a["id"] for a in apps_out]:
            stats["missing_groups"].extend(f"{app_id}:{n}" for n in names)
    return apps_out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("upstream")
    ap.add_argument("out")
    ap.add_argument("--owner", default="")
    ap.add_argument("--repo", default="")
    ap.add_argument("--author", default="")
    args = ap.parse_args()

    with open(args.upstream, encoding="utf-8") as f:
        sub = json5.loads(f.read(), args.upstream)

    upstream_version = int(sub.get("version") or 0)
    apps_out, stats = build(sub)
    if not apps_out:
        print("!! 白名单里一个组都没找到，上游可能改名了：", stats["missing_groups"])
        raise SystemExit(1)

    out = OrderedDict()
    out["id"] = SUB_ID
    out["name"] = SUB_NAME
    out["version"] = upstream_version * S.VERSION_STRIDE + REV
    out["author"] = args.author or sub.get("author") or S.DEFAULT_AUTHOR
    out["checkUpdateUrl"] = "./gkd.version.json5"
    if args.owner and args.repo:
        out["supportUri"] = f"https://github.com/{args.owner}/{args.repo}/issues"
    out["categories"] = [{"key": 0, "name": "功能类", "enable": True}]
    out["apps"] = apps_out

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    vpath = os.path.join(os.path.dirname(args.out), "gkd.version.json5")
    with open(vpath, "w", encoding="utf-8") as f:
        f.write("{id:%d,version:%d}\n" % (out["id"], out["version"]))

    # 自检：不得出现 globalGroups / 黑名单 App / 危险关键词
    got = json5.loads(open(args.out, encoding="utf-8").read(), args.out)
    assert "globalGroups" not in got
    n = 0
    for app in got["apps"]:
        assert not S.BLOCK_APPS.search(app["id"]), app["id"]
        for g in app["groups"]:
            assert g["enable"] is True
            assert g["name"] in EXTRA_GROUPS.get(app["id"], []), g["name"]
            for r in g["rules"]:
                n += 1
                ok, why = S.keep_rule(r, check_cta=False)
                assert ok, f"危险规则泄漏 {app['id']} {g['name']} {why}"

    print(json.dumps({
        "upstream_version": upstream_version,
        "published_version": out["version"],
        "apps": stats["apps"],
        "groups": stats["groups"],
        "rules": n,
        "dropped_hard": stats["dropped_rule_hard"],
        "missing_groups": stats["missing_groups"],
        "bytes": os.path.getsize(args.out),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
