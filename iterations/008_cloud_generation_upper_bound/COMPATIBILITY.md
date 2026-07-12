# MiMo 兼容性与调用记录

记录对象为本轮实际使用的 `mimo-v2.5-pro` 普通按量付费接口。凭据来自项目外配置文件；报告只记录 `credential_source=file`，不记录Key、Header或任何可恢复信息。

## 已核对的接口行为

- Base URL：配置中的普通按量付费地址，路径为 `/v1`；Chat Completions 端点为 `/chat/completions`。
- 请求采用 OpenAI-compatible JSON；鉴权只放在 HTTP Header，不进入 JSON body。
- Structured Output 使用官方 JSON mode：`response_format: {"type":"json_object"}`，并在固定提示词中定义输出结构。
- `thinking: {"type":"disabled"}`，`stream=false`，未启用工具、Web、图片、音频、视频或文件。
- 本批次固定 `temperature=0`、`top_p=1`、`max_completion_tokens=256`。
- 响应中的模型名、JSON Schema、Citation ID 和 Token usage 均经过本地检查；60/60 结构化结果通过。

## 官方来源

- [Chat Completions API](https://mimo.mi.com/docs/en-US/api/chat/openai-api)
- [Structured Output](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/structured-output)
- [关闭深度思考](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/other/deep-thinking)
- [模型与超参数](https://mimo.mi.com/docs/en-US/api/guidance/model-hyperparameters)
- [MiMo 价格页](https://mimo.mi.com/docs/welcome)
- [Token Plan 使用限制](https://mimo.mi.com/docs/en-US/price/tokenplan/subscription)

## 未确认事项

当前账号的个人/企业归属没有在本轮调用中读取或推断；API 数据留存、存储区域、零数据留存和训练使用政策见 `PROVIDER_POLICY_GAPS.md`，没有用其他供应商条款类比。
