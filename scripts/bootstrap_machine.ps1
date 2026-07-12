[CmdletBinding()]
param(
    [switch] $SkipInstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$examplePath = Join-Path $projectRoot 'config\machine.local.ini.example'
$configPath = if ($env:MACHINE_CONFIG_PATH) { $env:MACHINE_CONFIG_PATH } else { Join-Path $projectRoot 'config\machine.local.ini' }

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    Copy-Item -LiteralPath $examplePath -Destination $configPath -Force
    Write-Warning "已创建本机配置模板：$configPath。请编辑路径后重新运行本脚本；不会猜测另一台电脑的路径。"
    exit 2
}

function Read-MachineIni([string] $path) {
    $values = @{}
    $section = ''
    foreach ($line in Get-Content -LiteralPath $path) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') {
            $section = $matches[1].ToLowerInvariant()
            continue
        }
        if ($trimmed -match '^([^=]+)=(.*)$') {
            $values["$section.$($matches[1].Trim().ToLowerInvariant())"] = $matches[2].Trim()
        }
    }
    return $values
}

$ini = Read-MachineIni $configPath
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
$codeCommand = Get-Command code -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw '未找到 Python。请先安装 Python，再运行机器引导。' }
if (-not $gitCommand) { throw '未找到 Git。请先安装 Git，再运行机器引导。' }
Write-Host "Python：$((& python --version) 2>&1)"
Write-Host "Git：$((& git --version) 2>&1)"
if ($codeCommand) { Write-Host "VS Code：$((& code --version | Select-Object -First 1) 2>&1)" }
else { Write-Warning '未找到 VS Code code 命令；不阻止环境创建。' }

$aiLabRoot = if ($env:AI_LAB_ROOT) { $env:AI_LAB_ROOT } elseif ($ini['machine.ai_lab_root']) { $ini['machine.ai_lab_root'] } else { 'D:\AI-Lab' }
$aiLabRoot = [System.IO.Path]::GetFullPath($aiLabRoot)
$cacheRoot = if ($ini['paths.cache_root']) { $ini['paths.cache_root'] } else { Join-Path $aiLabRoot 'cache' }
$dataRoot = if ($ini['paths.data_root']) { $ini['paths.data_root'] } else { Join-Path $aiLabRoot 'data' }
$modelsRoot = if ($ini['paths.models_root']) { $ini['paths.models_root'] } else { Join-Path $aiLabRoot 'models' }
$envsRoot = if ($ini['paths.envs_root']) { $ini['paths.envs_root'] } else { Join-Path $aiLabRoot 'envs' }
$runtimesRoot = if ($ini['paths.runtimes_root']) { $ini['paths.runtimes_root'] } else { Join-Path $aiLabRoot 'runtimes' }
$secretsRoot = if ($ini['paths.secrets_root']) { $ini['paths.secrets_root'] } else { Join-Path $aiLabRoot 'secrets' }
$paths = @($cacheRoot, $dataRoot, $modelsRoot, $envsRoot, $runtimesRoot, $secretsRoot)
foreach ($path in $paths) { $null = New-Item -ItemType Directory -Path $path -Force }

$env:AI_LAB_ROOT = $aiLabRoot
$env:MACHINE_CONFIG_PATH = $configPath
$env:PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
$env:HF_HOME = Join-Path $cacheRoot 'huggingface'
$env:HF_HUB_CACHE = Join-Path $cacheRoot 'huggingface\hub'
$env:HF_DATASETS_CACHE = Join-Path $cacheRoot 'huggingface\datasets'
$env:TRANSFORMERS_CACHE = Join-Path $cacheRoot 'huggingface\transformers'
$env:TORCH_HOME = Join-Path $cacheRoot 'torch'
foreach ($name in @('PIP_CACHE_DIR', 'HF_HOME', 'HF_HUB_CACHE', 'HF_DATASETS_CACHE', 'TRANSFORMERS_CACHE', 'TORCH_HOME')) {
    $null = New-Item -ItemType Directory -Path ([Environment]::GetEnvironmentVariable($name, 'Process')) -Force
}

$venvPath = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    Write-Host '创建主项目 .venv（不会复制任何旧环境）...'
    & python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw '创建 .venv 失败。' }
}
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) { throw "未找到新环境解释器：$venvPython" }

if (-not $SkipInstall) {
    Write-Host '使用本机 PIP_CACHE_DIR 安装 requirements.txt...'
    & $venvPython -m pip install --cache-dir $env:PIP_CACHE_DIR -r (Join-Path $projectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'requirements.txt 安装失败；没有回退到系统 Python。' }
}

& $venvPython scripts\verify_machine_sync.py
$syncExit = $LASTEXITCODE
& $venvPython scripts\verify_setup.py
$verifyExit = $LASTEXITCODE
if ($syncExit -ne 0 -or $verifyExit -ne 0) {
    throw "机器同步验证或项目验证失败（sync=$syncExit, verify=$verifyExit）。大型外部资产不会由本脚本自动下载。"
}
Write-Host '机器引导和项目验证完成。'
exit 0
