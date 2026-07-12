# 双电脑机器恢复说明

本项目的Git仓库只同步代码、配置示例、测试定义、实验报告和小型结果。模型、缓存、环境、密钥和大型数据必须在每台电脑独立恢复。

## 内容分类

### Git同步内容

- `src/`、`scripts/`、测试、README/路线/规则文件；
- `iterations/001–009` 的小型指标、报告和虚构测试定义；
- `config/*.example`、`artifacts/EXTERNAL_ASSETS.md`、`PROJECT_STATE.md`；
- `.vscode`中不含用户密钥和机器绝对路径的配置。

### 可重新生成内容

- `data/processed/emanual_tfidf` 的Corpus、Query和TF-IDF评测输出；
- 002 MX-100虚构资料包和KnowledgeUnit导出；
- `experiments/results`下被忽略的临时结果；
- `.venv`之外的测试报告和静态检查页。

生成前必须使用固定dataset revision、脚本版本和随机种子；生成的大文件不提交。

### 必须重新下载内容

- Docling模型 artifacts和独立环境依赖；
- BGE-M3模型及其独立环境依赖；
- llama.cpp运行时和Qwen GGUF；
- Hugging Face、Torch、pip缓存内容。

下载来源、revision、许可、预计大小和SHA-256见 [artifacts/EXTERNAL_ASSETS.md](artifacts/EXTERNAL_ASSETS.md)。`bootstrap_machine.ps1`不会自动下载超过500MB的模型。

### 每台机器独立配置内容

- `config/machine.local.ini`：路径和环境位置；
- `MACHINE_CONFIG_PATH`、`AI_LAB_ROOT`等进程级覆盖；
- 外部 `mimo.ini`：只在需要008/后续云端实验的机器配置；
- Jupyter/VS Code解释器、端口和本机GPU/CPU选择。

### 禁止同步内容

- `.venv`、独立环境、运行时、模型、缓存、原始数据和下载临时文件；
- `mimo.ini`、API Key、Authorization Header、`.env`、本地日志；
- 公司资料、真实文档、用户Notebook临时内容和完整网络调试记录。

## Windows新机器恢复流程

1. 安装Git、Python（建议与当前环境兼容的3.14.2；若不兼容，使用项目级隔离Python，不改系统Python）和VS Code。管理员权限不是必需条件。
2. 从私有远程Clone仓库：

   ```powershell
   git clone <私有远程URL>
   Set-Location retrieval-adaptation-lab
   git switch main
   ```

3. 创建本机配置：

   ```powershell
   Copy-Item config\machine.local.ini.example config\machine.local.ini
   # 用文本编辑器修改 machine.local.ini 的路径；不要写Key
   ```

4. 执行机器引导。它会检查Python/Git/VS Code、创建缓存/数据/模型目录、创建主`.venv`、使用本机pip缓存安装`requirements.txt`，然后运行环境验证；不会复制旧`.venv`或下载大型模型：

   ```powershell
   .\scripts\bootstrap_machine.ps1
   ```

5. 查看机器同步状态和缺失资产：

   ```powershell
   .\.venv\Scripts\python.exe scripts\verify_machine_sync.py
   ```

6. 运行项目结构和依赖验证：

   ```powershell
   .\.venv\Scripts\python.exe scripts\verify_setup.py
   .\.venv\Scripts\python.exe -m pip check
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

7. 只有下一阶段明确需要时，按照资产清单中的官方命令恢复Docling/BGE/llama.cpp/Qwen；每次先报告下载量，不让引导脚本自动下载超过500MB的内容。

## 绝对路径可移植性审计

- **必须保留的默认本地路径**：当前电脑默认`D:\AI-Lab`缓存、模型、运行时和外部秘密目录；它们只作为`machine.local.ini.example`默认值，不是另一台机器的固定要求。
- **应改为项目相对路径**：项目内脚本和实验输入已使用`Path(__file__).resolve()`定位项目根目录；新恢复入口沿用该规则。
- **应进入机器本地配置**：运行时目录、模型目录、Docling artifacts、BGE模型、缓存根目录和外部秘密路径。`src/machine_config.py`支持`machine.local.ini`、`MACHINE_CONFIG_PATH`和`AI_LAB_ROOT`覆盖。
- **仅存在于历史报告、不需要修改**：`experiments/reports/`和`iterations/001–009`中记录的C/D盘路径、旧环境路径和旧命令。它们是迁移前或实验当时的证据，保持原样。

本轮只读扫描确认：历史报告包含C盘旧项目路径；运行代码中的D盘默认路径已增加本地配置或环境覆盖。没有把另一台电脑的路径写入新的同步入口。

## 日常切换电脑

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe scripts\verify_machine_sync.py
# 需要时再运行 verify_setup 或对应迭代的复现命令
```

切换前先保存代码和报告：

```powershell
git status
git add <明确的代码和报告文件>
git commit -m "<本次变更>"
```

不提交本地配置、模型、缓存、Key或用户Notebook临时改动。
