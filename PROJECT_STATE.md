# PROJECT_STATE

更新时间：2026-07-12

## 当前坐标

- 最后完成迭代：009 Claim-Level Grounding 离线声明审计。
- 本轮提交链：`a41e542417406f0e364c3875e6fa8b7bf3f0f9d4`（跨设备工作流）和 `94f92a1`（按授权删除遗留Notebook）；当前最新哈希以 `git rev-parse HEAD` 读取。
- 上一已提交哈希：`cf025a1a82b86578deeeda223c612d932ef2b4fc` (`feat: audit claim-level grounding`)。
- 当前分支：`main`；远程为私有仓库 `origin`；两个遗留Notebook已按用户明确授权删除。
- 当前工作区：`D:\Projects\study\retrieval-adaptation-lab`。

## 六大能力区域

| 区域 | 当前状态 | 当前结论 |
|---|---|---|
| Document Intelligence | 003已完成受控Docling验证 | 虚构多格式测试通过；不是生产资料建库；下一步筛选成熟方案并做最小集成，不自研OCR |
| 检索与知识访问 | 001、004已完成 | TF-IDF是稀疏对照；BGE-M3 Dense是当前默认检索结论；Hybrid未成为默认 |
| 生成与推理 | 005–009已完成阶段性验证 | 本地4B/9B均未达到完整可靠生成门槛；MiMo 008质量较高但严格口径未通过；009发现旧Unsupported规则存在误报，Claim协议尚未API验证 |
| 评测与可观测性 | 001–009持续建立 | 已有固定数据、指标、失败样本、成本、哈希和离线审计；下一步继续先固定口径再运行比较 |
| 模型适配与优化 | 尚未进入 | 没有微调、LoRA或蒸馏证据；只有出现稳定缺口后才评估 |
| 系统集成与治理 | 正在准备双电脑恢复 | 已建立机器配置、资产清单、恢复和同步检查入口；没有远程仓库或推送 |

## 当前默认结论

- 解析：002确定性解析器和003 Docling适配器并存；Document Intelligence下一阶段尚未选定生产方案。
- 检索：`BAAI/bge-m3` Dense（revision `5617a9f61b028005a4858fdac845db406aefb181`）。
- 生成：没有通过全部可靠性门槛的默认生成器；4B是低资源离线历史对照，9B是资源成本过高的历史对照，MiMo是未获验收的云端候选。

## 当前下一步

完成第二台电脑恢复后，优先进行 Document Intelligence 成熟方案筛选与最小集成；先使用002虚构材料和明确许可的候选方案，继续保持不自研OCR、不处理公司资料。

## 未解决问题

- 009需要先固定声明级评测口径，再决定是否批准Claim-Level API复测。
- MiMo服务的API留存、训练使用、零数据留存和存储区域政策仍有unknown项。
- Docling模型目录和llama.cpp发行包的独立SHA-256没有在历史报告中锁定。
- 运行代码默认值已支持机器配置/环境覆盖，但每台机器仍需填写自己的`machine.local.ini`和外部资产路径。
- 两个遗留Notebook已删除，不再作为同步内容；后续新Notebook仍需先确认用途再纳入项目。

## 外部资产身份

详见 [artifacts/EXTERNAL_ASSETS.md](artifacts/EXTERNAL_ASSETS.md)。外部模型、运行时和缓存不进入Git；缺失资产只按官方来源恢复。

## 第二台电脑最小恢复步骤

```powershell
git clone <私有远程URL>
Set-Location retrieval-adaptation-lab
Copy-Item config\machine.local.ini.example config\machine.local.ini
# 编辑 machine.local.ini，填写本机路径；不要填写Key
.\scripts\bootstrap_machine.ps1
.\.venv\Scripts\python.exe scripts\verify_machine_sync.py
.\.venv\Scripts\python.exe scripts\verify_setup.py
```

每个迭代完成后必须更新本文件的最后提交、六大区域状态、下一步和未解决问题。
