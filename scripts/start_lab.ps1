[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $JupyterArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

$cacheLocations = [ordered]@{
    HF_HOME = 'D:\AI-Lab\cache\huggingface'
    HF_HUB_CACHE = 'D:\AI-Lab\cache\huggingface\hub'
    HF_DATASETS_CACHE = 'D:\AI-Lab\cache\huggingface\datasets'
    TORCH_HOME = 'D:\AI-Lab\cache\torch'
    PIP_CACHE_DIR = 'D:\AI-Lab\cache\pip'
}

foreach ($entry in $cacheLocations.GetEnumerator()) {
    $path = [System.IO.Path]::GetFullPath($entry.Value)
    if ([System.IO.Path]::GetPathRoot($path) -ne 'D:\') {
        throw "$($entry.Key) 必须位于 D 盘，当前值：$path"
    }
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
