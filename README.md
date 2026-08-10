# Photo to Chibi GIFs

一个供 Codex 使用的 Skill：根据 2–3 张真人照片生成身份一致、透明背景的 Q 版动态表情包。

## 默认输出

标准模式按以下顺序生成 9 个动作：

1. `eating` — 吃饭
2. `happy` — 开心
3. `busy-typing` — 忙碌打电脑
4. `angry` — 生气
5. `peace` — 比耶
6. `wave` — 打招呼
7. `crying` — 哭
8. `thumbs-up` — 点赞
9. `embarrassed` — 尴尬

快速测试模式生成 `eating`、`happy`、`busy-typing`。

每个成品 GIF 默认为：

- 240×240 像素
- 5 帧动画
- 透明背景
- 循环播放
- 不超过 500 KB
- 大比例半身构图

## 安装

将仓库中的 `photo-to-chibi-gifs` 文件夹复制到本机 Codex Skills 目录：

```text
%USERPROFILE%\.codex\skills\photo-to-chibi-gifs
```

重新打开 Codex 后，可在任务中直接说明使用 `$photo-to-chibi-gifs`，并上传 2–3 张人物参考照片。

## 使用示例

```text
请使用 $photo-to-chibi-gifs，根据我上传的三张照片生成默认九动作透明 GIF 表情包。
服装以第二张照片为准，保留透明圆框眼镜。
```

## 目录说明

- `SKILL.md`：完整工作流和执行规范
- `assets/action-presets.json`：动作预设与默认顺序
- `assets/identity-lock-template.json`：身份锁模板
- `assets/approved-samples/`：已确认的画风、动作节奏和半身构图样本
- `references/`：身份、动画和逐帧验收规则
- `scripts/`：任务生成、GIF 处理、验证和打包脚本

## 样本优先级

1. 当前用户照片和身份锁决定人物身份、脸型、发型与服装。
2. 已确认样本决定画风、半身比例、人物大小、动作节奏和构图。
3. 动作预设文字补充具体动作要求。

样本人物的身份与服装不得复制给其他用户。`lanku` 是可选身份预设，不会自动套用到其他人物。

## 说明

仓库包含用于构图和动作一致性参考的图片样本，以及 LanKu 的可选身份预设。公开使用或再分发前，请确认你拥有相关人物照片、肖像和样本素材的授权。
