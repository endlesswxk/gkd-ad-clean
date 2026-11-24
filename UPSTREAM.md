# 上游与署名

本仓库的规则内容来自以下项目，仅做「删减」（不新增任何规则）：

- **[Lin-arm/GKD_subscription](https://github.com/Lin-arm/GKD_subscription)** —— 直接上游，本仓库每天拉取它的 `dist/gkd.json5`。
- **[AIsouler/GKD_subscription](https://github.com/AIsouler/GKD_subscription)** —— Lin-arm 的上游（原仓库，已停止维护）。
- **[gkd-kit/subscription](https://github.com/gkd-kit/subscription)** —— 上述两者的规则模板与初始来源。

## 本仓库做了什么

只做减法：

1. 删除非广告分类的所有规则组（功能类 / 其他 / 更新提示 / 权限提示 / 通知提示 / 青少年模式 / 评价提示）；
2. 删除全部 `globalGroups`（跨 App 全局规则）；
3. 删除系统类 App（安装器 / 权限控制器 / 系统设置 / 系统界面 / 安全管家 / 设备管理）下的全部规则；
4. 在剩余广告规则里，按关键词与目标节点特征删除与「安装、权限、授权、支付、密码、USB 调试、
   屏幕共享、远程协助」等相关的单条规则。

不新增、不改写任何选择器的语义；`snapshotUrls` 等溯源信息原样保留。

## 许可

上游仓库（Lin-arm/GKD_subscription、AIsouler/GKD_subscription）**没有附带 LICENSE 文件**，
因此严格意义上未授予再分发许可。本仓库为**个人自用**而存在：

- 如果你只是 fork 给自己订阅，属于个人使用范畴；
- 如果打算把规则本体对外分发/商用，请先联系上游作者取得授权。

消毒脚本 `tools/sanitize.py`、`tools/json5.py`、workflow 与文档由本仓库作者编写，可自由使用。
