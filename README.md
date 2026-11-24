# gkd-ad-clean

> 自用的 GKD 订阅：**只保留"关广告"类规则，删掉所有会点"安装 / 允许 / 授权 / 支付 / 密码 / USB调试 / 屏幕共享"之类的东西。**

上游是 [Lin-arm/GKD_subscription](https://github.com/Lin-arm/GKD_subscription)（AIsouler 那套规则集的社区续更 Fork，覆盖 1000+ 应用）。
本仓库每天自动拉一次上游产物 → 按下面的规则消毒 → 提交。你手机上订阅的是**消毒后的产物**，不是上游原版。

## 订阅地址（三选一，建议第一个）

```
https://raw.githubusercontent.com/endlesswxk/gkd-ad-clean/main/dist/gkd.json5
https://cdn.jsdelivr.net/gh/endlesswxk/gkd-ad-clean@main/dist/gkd.json5
https://fastly.jsdelivr.net/gh/endlesswxk/gkd-ad-clean@main/dist/gkd.json5
```

GKD 里操作：**订阅 → 右下角 + → 粘贴上面的链接 → 确定**。导入后 id 是 `6688`，重复导入会提示已存在。

> 国内网络如果 raw.githubusercontent.com 打不开，用 jsdelivr 那两条。

## 附加订阅（可选，默认不用加）

主订阅刻意不收「功能类」，但有一类需求单独放在附加订阅里：**看激励视频换免广告时长时的自动收尾**（自动静音、得奖励后点关闭、隔 10 秒点右上角叉）。

```
https://raw.githubusercontent.com/endlesswxk/gkd-ad-clean/main/dist/extras/fanqie.json5
https://cdn.jsdelivr.net/gh/endlesswxk/gkd-ad-clean@main/dist/extras/fanqie.json5
```

- 独立 id **6689**，独立版本号，和主订阅互不影响，随时可以删掉或单独关闭。
- 内容只有白名单点名的组（`tools/extras.py` 顶部 `EXTRA_GROUPS`，按 **包名 + 组名** 双重锁定，上游新增的功能类组不会混进来），当前是：
  - `com.dragon.read`（番茄免费小说）/ `功能类-看广告自动领奖励`、`功能类-观看广告自动静音`，共 2 组 7 条。
- 仍然要过安全过滤（安装/支付/授权/密码等一律剔除），但**跳过 CTA 过滤**——这类规则天生就是点"领取/关闭"，用主订阅那套过滤会被全删。
- 需要提醒：这是**帮你把广告流程跑完**，和主订阅"只关广告"的定位相反；番茄有激励反作弊，未播完就关、长时间静音挂机都可能判奖励无效甚至风控，风险在账号不在手机。番茄改版也最容易让这类规则失效。


## 这个订阅里有什么

| 项目 | 数量 |
|---|---|
| App | ~758 |
| 规则组 | ~1314 |
| 规则 | ~2354 |
| 分类 | 只有 开屏广告 / 全屏广告 / 局部广告 / 分段广告 四类，全部默认启用 |
| 全局规则（跨 App） | **0 条**（整块删除） |

`version` 形如 `64201` = 上游版本 `642` × 100 + 消毒器修订号 `1`，保证单调递增，上游一更新你这边就能收到。

## 消毒策略（`tools/sanitize.py`）

1. **只留四个广告分类**：组名前缀不是 `开屏广告` / `全屏广告` / `局部广告` / `分段广告` 的组，**整组丢弃**——
   于是「功能类」「其他」「更新提示」「权限提示」「通知提示」「青年少模式」里那些
   *自动安装应用*、*无视风险继续安装*、*自动允许USB调试*、*自动允许共享整个屏幕*、
   *自动授权登录*、*高敏感权限自动确定*、*自动同意远程协助*、*谷歌填充密码自动授权*
   全部不会进入你的订阅。
2. **全局规则组一条不留**：上游有 3 个跨 App 生效的组（每个覆盖 300+ 个 App 的白名单，
   含支付宝 / 微信 / 密码管理器），会在里面盲点 `确认 / 更新 / 取消` 之类的文本节点，整块删除。
3. **系统类 App 直接拉黑**：`packageinstaller` / `permissioncontroller` / `com.android.settings` /
   `systemui` / `*securitycenter` / `*systemmanager` / `*safecenter` / `devicepolicy` 等包名下不留任何规则。
4. **规则级过滤（保留的组里逐条过）**：
   - `HARD_DANGER`：选择器里出现 安装 / 卸载 / 允许 / 同意 / 授权 / 确认 / 确定 / 支付 / 付款 /
     免密 / 刷脸 / 密码 / 验证码 / USB / 调试 / 投屏 / 屏幕共享 / 录屏 / 远程 / 无障碍 /
     设备管理 / 清除 / 删除 / 格式化 / 恢复出厂 / 购买 / 下单 / 结算 / 充值 / 提现 … → 删除该条。
   - `CTA_GUARD`：选择器里有广告 CTA 字样（立即 / 下载 / 领取 / 红包 / 详情 / 进入 / 试用 …）
     而整条规则**既没有关闭类锚点**（关闭 / 跳过 / close / 取消 / dislike …）
     **点击目标也不像小叉号**（`@ImageView[width<90 && height<90]` 这类）→ 删除，
     避免把广告点开而不是关掉。
5. **输出前自检**：重新解析产物，断言「无 globalGroups」「每个组 enable=true」「所有 action 在白名单内」
   「没有任何规则再命中上面两类过滤器」「命中黑名单 App 数为 0」，任一条不满足就直接构建失败。

规则是**纯声明式数据**，不含 JS、不含网络请求、不含 shell——它只能"看到某个界面时点某个节点"。

## 目录

```
dist/gkd.json5            主订阅产物（GKD 下载的就是这个）
dist/gkd.version.json5    主订阅版本文件 {id:6688,version}
dist/extras/fanqie.json5  附加订阅产物（看广告换权益，id 6689）
dist/extras/gkd.version.json5  附加订阅版本文件
tools/sanitize.py         主订阅消毒器（纯 Python3 标准库 + 自带 JSON5 解析器，无第三方依赖）
tools/extras.py           附加订阅生成器（白名单挑组）
tools/json5.py            JSON5 解析器
.github/workflows/sync.yml  每天拉上游 → 消毒 → 提交
```

## 想改策略

改 `tools/sanitize.py` 顶部：

- `KEEP_CATEGORIES`：想多要"通知提示/评价提示"就加进列表；
- `HARD_DANGER` / `CTA` / `DISMISS`：增删过滤词；
- `BLOCK_APPS`：再加系统类包名；
- **`REV` 必须 +1**：否则上游版本没变时 `version` 不变，手机端不会更新。

改完 commit 即可，Action 会在 push 时自动跑一遍（也可以到 Actions 页面手动 `Run workflow`）。

## 已知限制

- 只覆盖"关广告"，去不掉「功能类」（自动签到/自动领红包/去更新提示等）——那些是主动帮你点按钮，
  风险最高，本仓库刻意不要。
- 广告关闭按钮随 App 改版会失效，上游更新后本仓库会自动跟进，但不是即时的（T+1 天）。
- 只按包名/文案匹配，App 改版后仍可能误点，重要 App（银行、支付）里建议在 GKD 里单独把该 App 的组关掉。
- 上游仓库没有 LICENSE 文件。**个人自用（fork 给自己订阅）没有问题**；如果要公开分发规则本体，
  请自行评估版权风险并保留 `UPSTREAM.md` 里的署名。

## 免责

自用配置，不保证正确性与时效性，使用风险自负。规则的原始版权归上游作者所有，见 [UPSTREAM.md](UPSTREAM.md)。
