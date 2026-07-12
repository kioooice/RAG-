# MODEL_PROVENANCE

记录日期：2026-07-12（Asia/Shanghai）

## 官方基座

- 页面：[Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- revision：`c202236235762e1c871ad0ccb60c8ee5ba337b9a`
- License：Apache-2.0
- 参数量：9B；模型卡同时描述视觉编码器，但本轮只使用文本输入，不下载视觉文件。
- 官方模型卡说明Qwen3.5默认思考，并给出通过 `chat_template_kwargs.enable_thinking=false` 获得直接响应的方式；本轮以llama.cpp `--reasoning off`为实际生效配置。

## GGUF来源

- 页面：[unsloth/Qwen3.5-9B-GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)
- 创建者：Unsloth；仓库metadata的 `base_model` 为 `Qwen/Qwen3.5-9B`。
- GGUF仓库revision：`3885219b6810b007914f3a7950a8d1b469d598a5`
- 文件：`Qwen3.5-9B-Q4_K_M.gguf`
- 文件大小：`5680522464` bytes（约5.68GB十进制）
- HTTP `X-Linked-ETag` 与本地SHA-256：`03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`
- 下载日期：2026-07-12
- 追溯结论：基座revision、GGUF仓库revision、base_model元数据和本地SHA均已记录；这是可追溯的第三方量化，不宣称为Qwen官方转换文件。

## 运行文件

- 模型：`D:\AI-Lab\models\qwen3.5-9b\unsloth-3885219b6810b007914f3a7950a8d1b469d598a5\Qwen3.5-9B-Q4_K_M.gguf`
- Runtime：`D:\AI-Lab\runtimes\llama.cpp\b9968\llama-server.exe`
- 运行模式：本地 `127.0.0.1`、`--offline`、CPU `-ngl 0`、无mmproj。
