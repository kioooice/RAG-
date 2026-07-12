# Qwen3.5-9B 兼容性与资源记录

## 软件与模型

- Windows 11；评测Python 3.14.2（已有BGE环境）。
- llama.cpp b9968，沿用006的 `llama-server.exe`，没有更换runtime、CUDA Toolkit或PATH。
- 官方基座：`Qwen/Qwen3.5-9B`，revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`，Apache-2.0，9B参数。
- GGUF：`unsloth/Qwen3.5-9B-GGUF`，revision `3885219b6810b007914f3a7950a8d1b469d598a5`，README元数据指向 `Qwen/Qwen3.5-9B`，创建者为Unsloth。
- 文件：`Qwen3.5-9B-Q4_K_M.gguf`，5,680,522,464 bytes；本地SHA-256为 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`。
- 未下载 `mmproj` 或其他视觉文件；本轮只发送文本消息。

## 非思考模式

实际启动参数同时使用：

```text
--reasoning off
--chat-template-kwargs {"enable_thinking": false}
```

烟雾测试18/18次没有 `<think>`、`</think>` 或 `reasoning_content`。服务日志提示 `chat-template-kwargs` 在该版本已标记为deprecated，但 `--reasoning off`仍有效；本轮没有修改Prompt或升级llama.cpp。

## 硬件与资源

- RTX 4050 Laptop GPU 6,141 MiB；实际使用CPU后端（`-ngl 0`），未安装CUDA Toolkit。
- 物理内存约15.24GB；正式评测服务RSS峰值约11.03GB，评测进程约0.44GB。
- 页面文件初始使用约2.94GB，峰值约12.87GB；Windows系统管理的页面文件从约10.75GB自动扩展到约14.90GB，Codex没有修改页面文件设置。
- 正式评测稳定完成，没有OOM或崩溃，但页面文件压力属于当前设备不可接受的部署成本。
- D盘下载前约253.95GB可用；下载后约244.66GB可用。实际新增只有这一Q4_K_M文件，低于本轮6.5GB上限。

## 结论

可以在当前设备完成小规模离线评测，但不能把“可完成”解释成“适合日常默认部署”。质量门槛和资源门槛分别见 `RESULT.md` 与 `metrics.json`。
