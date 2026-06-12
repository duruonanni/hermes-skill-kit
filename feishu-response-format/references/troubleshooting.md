# Troubleshooting: Local Gateway Fixes & Known Issues

## 1. 本地网关修复记录

### 问题

`_MARKDOWN_TABLE_RE` 在 `_build_outbound_payload()` 中检测到 `|...|\n|---|` 后就强制降级为 `text` 类型，导致同消息内所有 Markdown 失效。

### 根因

```python
# gateway/gateway_feishu.py, commit 8e18d1031, Apr 22
_MARKDOWN_TABLE_RE = re.compile(r"^\|.*\|\n\|[-|: ]+\|", re.MULTILINE)
```

### 修复方案（PR #39955）

1. **移除** `_MARKDOWN_TABLE_RE` 强制降级逻辑
2. **增加** `(^\s*\|)` 到 `_MARKDOWN_HINT_RE`（作为表格格式提示）

**验证结果：** 实测 `post` 类型发送表格返回 `code=0`（不再空白）。飞书 API 版本 v1.0.0.3025 → v1.0.0.3356 之间已静默修复了该 bug。

**状态：** PR #39955 已提交上游。上游有 10+ 类似 PR 均未合并（#27922, #38867, #39510 等）。

关联 PR: https://github.com/NousResearch/hermes-agent/pull/39955

## 2. 表格对齐问题

### 症状

管道符表在飞书手机端视觉不对齐，内容溢出管道符边界。

### 根因

降级为 `text` 后：
1. 分隔线 `|------|------|` 用 `-` 数量定义每列宽度
2. 数据行不参与列宽计算
3. 中英文宽度差异（中文 2 格，英文/符号 1 格）

### 测试数据

5 种格式的测试结果见 `references/pipe-table-alignment.md`。

### 解决方案

- 短内容（每列 ≤6 字符）→ 方案 A 纯文本管道符，视觉对齐
- 长内容/含 URL → 方案 B 交互卡片 / 方案 C Table 组件

## 3. 常见错误码

| code | 含义 | 处理 |
|:----|:----|:-----|
| 0 | 成功 | — |
| 99992402 | `receive_id_type` 无效 | `thread_id` 不支持，用 reply 替代 |
| 230015 | 不能分享到自己 | `share_chat` 不能 share 当前会话 |
| 234010 | 文件大小为 0 | 检查文件是否生成成功 |
| 99993600 | 网络错误/超时 | 指数退避重试 |

## 4. API 限制

| 限制项 | 数值 |
|:------|:----:|
| Token 有效期 | ~3080 秒（~51 分钟） |
| 频率限制 | 1000 次/分钟，50 次/秒 |
| 交互卡片最大列数 | 50 列（Card JSON 2.0） |
| 卡片大小上限 | 约 30KB（JSON 序列化后） |
