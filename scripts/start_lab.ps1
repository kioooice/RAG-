[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $JupyterArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$machineConfigPath = if ($env:MACHINE_CONFIG_PATH) { $env:MACHINE_CONFIG_PATH } else { Join-Path $projectRoot 'config\machine.local.ini' }

$ini = @{}
$section = ''
if (Test-Path -LiteralPath $machineConfigPath -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $machineConfigPath) {
        $trimmed = $line.Trim()
        if ($trimmed -match '^\[(.+)\]$') {
            $section = $matches[1].ToLowerInvariant()
            continue
        }
        if ($trimmed -match '^([^=]+)=(.*)$' -and $section -in @('machine', 'paths')) {
            $key = $matches[1].Trim().ToLowerInvariant()
            $ini["$section.$key"] = $matches[2].Trim()
        }
    }
}

$aiLabRoot = if ($env:AI_LAB_ROOT) { $env:AI_LAB_ROOT } elseif ($ini['machine.ai_lab_root']) { $ini['machine.ai_lab_root'] } else { 'D:\AI-Lab' }
$aiLabRoot = [System.IO.Path]::GetFullPath($aiLabRoot)
$env:AI_LAB_ROOT = $aiLabRoot
$env:MACHINE_CONFIG_PATH = $machineConfigPath

function Resolve-MachinePath([string] $value, [string] $fallback) {
    $candidate = if ($value) { $value } else { $fallback }
    if (-not [System.IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path $projectRoot $candidate
    }
    return [System.IO.Path]::GetFullPath($candidate)
}

$configuredCacheRoot = if ($env:AI_LAB_CACHE) { $env:AI_LAB_CACHE } else { $ini['paths.cache_root'] }
$cacheRoot = Resolve-MachinePath $configuredCacheRoot (Join-Path $aiLabRoot 'cache')
$cacheLocations = [ordered]@{
    HF_HOME = Join-Path $cacheRoot 'huggingface'
    HF_HUB_CACHE = Join-Path $cacheRoot 'huggingface\hub'
    HF_DATASETS_CACHE = Join-Path $cacheRoot 'huggingface\datasets'
    TORCH_HOME = Join-Path $cacheRoot 'torch'
    PIP_CACHE_DIR = Join-Path $cacheRoot 'pip'
}

foreach ($entry in $cacheLocations.GetEnumerator()) {
    $path = [System.IO.Path]::GetFullPath($entry.Value)
    $null = New-Item -ItemType Directory -Path $path -Force
    $probe = Join-Path $path ('.write-test-' + [guid]::NewGuid().ToString('N'))
    try {
        [System.IO.File]::WriteAllText($probe, 'ok')
    }
    catch {
        throw "$($entry.Key) 路径不可写：$path。$($_.Exception.Message)"
    }
    finally {
        if (Test-Path -LiteralPath $probe) {
            Remove-Item -LiteralPath $probe -Force
        }
    }
    [Environment]::SetEnvironmentVariable($entry.Key, $path, 'Process')
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw '未找到 Git。请先安装 Git，再运行启动脚本。'
}
if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
    Write-Warning '未找到 VS Code code 命令；不影响 Jupyter 启动，但跨设备开发体验需要手动安装或加入 PATH。'
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "项目虚拟环境不存在。请先在 $projectRoot 中创建 .venv 并安装 requirements.txt；不会回退到系统 Python。"
}

$actualPython = (& $python -c 'import pathlib, sys; print(pathlib.Path(sys.executable).resolve())').Trim()
$expectedPython = [System.IO.Path]::GetFullPath($python)
if ($LASTEXITCODE -ne 0 -or $actualPython -ne $expectedPython) {
    throw "虚拟环境解释器校验失败。期望：$expectedPython；实际：$actualPython。不会回退到系统 Python。"
}

Write-Host "项目根目录：$projectRoot"
Write-Host "Python：$actualPython"
foreach ($entry in $cacheLocations.GetEnumerator()) {
    Write-Host "$($entry.Key)：$([Environment]::GetEnvironmentVariable($entry.Key, 'Process'))"
}

& $python -m jupyter lab --notebook-dir $projectRoot @JupyterArgs
exit $LASTEXITCODE
