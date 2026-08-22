param(
    [ValidateSet("quick", "full")]
    [string]$Profile = "full",
    [switch]$SkipChat,
    [switch]$KeepEnvironment
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $PSScriptRoot "compose.yaml"
$locustFile = Join-Path $PSScriptRoot "locustfile.py"
$reportFile = Join-Path $PSScriptRoot "压测报告.md"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$resultsDir = Join-Path $PSScriptRoot "results\$timestamp"
$metadataFile = Join-Path $resultsDir "metadata.json"
$accountsFile = Join-Path $resultsDir "accounts.json"
$target = "http://127.0.0.1:8876"

New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null

if ($Profile -eq "quick") {
    $seededUsers = 150
    $cooldownSeconds = 3
    $stages = @(
        [pscustomobject]@{ Name = "基础读接口"; Prefix = "01-read"; UserClass = "ReadApiUser"; Users = 20; SpawnRate = 10; Duration = "20s" },
        [pscustomobject]@{ Name = "认证突发"; Prefix = "02-auth"; UserClass = "AuthBurstUser"; Users = 10; SpawnRate = 5; Duration = "15s" },
        [pscustomobject]@{ Name = "业务写入"; Prefix = "03-write"; UserClass = "WriteApiUser"; Users = 10; SpawnRate = 5; Duration = "20s" },
        [pscustomobject]@{ Name = "复杂读写混合"; Prefix = "04-mixed"; UserClass = "MixedApiUser"; Users = 50; SpawnRate = 25; Duration = "25s" },
        [pscustomobject]@{ Name = "150 用户突发峰值"; Prefix = "05-peak"; UserClass = "PeakApiUser"; Users = 150; SpawnRate = 75; Duration = "20s" }
    )
} else {
    $seededUsers = 3200
    $cooldownSeconds = 15
    $stages = @(
        [pscustomobject]@{ Name = "500 用户基础读取"; Prefix = "01-read"; UserClass = "ReadApiUser"; Users = 500; SpawnRate = 100; Duration = "75s" },
        [pscustomobject]@{ Name = "200 用户认证突发"; Prefix = "02-auth"; UserClass = "AuthBurstUser"; Users = 200; SpawnRate = 100; Duration = "60s" },
        [pscustomobject]@{ Name = "300 用户业务写入"; Prefix = "03-write"; UserClass = "WriteApiUser"; Users = 300; SpawnRate = 75; Duration = "90s" },
        [pscustomobject]@{ Name = "1000 用户复杂读写"; Prefix = "04-mixed"; UserClass = "MixedApiUser"; Users = 1000; SpawnRate = 200; Duration = "120s" },
        [pscustomobject]@{ Name = "3000 用户突发峰值"; Prefix = "05-peak"; UserClass = "PeakApiUser"; Users = 3000; SpawnRate = 1000; Duration = "90s" }
    )
}

if (-not $SkipChat) {
    $chatDuration = if ($Profile -eq "quick") { "20s" } else { "60s" }
    $stages += [pscustomobject]@{
        Name = "真实聊天"
        Prefix = "06-chat"
        UserClass = "ChatApiUser"
        Users = if ($Profile -eq "quick") { 3 } else { 5 }
        SpawnRate = 1
        Duration = $chatDuration
    }
}

$computer = Get-CimInstance Win32_ComputerSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$metadata = [ordered]@{
    started_at = (Get-Date).ToString("o")
    profile = $Profile
    target = $target
    git_commit = (git -C $repoRoot rev-parse --short HEAD)
    git_dirty = -not [string]::IsNullOrWhiteSpace(
        (git -C $repoRoot status --porcelain | Out-String)
    )
    cpu = $processor.Name.Trim()
    memory_gb = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1)
    seeded_users = $seededUsers
    cooldown_seconds = $cooldownSeconds
    backend_workers = 1
    stages = @($stages | ForEach-Object {
        [ordered]@{
            name = $_.Name
            prefix = $_.Prefix
            user_class = $_.UserClass
            users = $_.Users
            spawn_rate = $_.SpawnRate
            duration = $_.Duration
        }
    })
}
$metadata | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metadataFile -Encoding utf8

function Wait-Backend {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$target/health" -TimeoutSec 3
            if ($health.status -eq "ok") {
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "隔离压测后端未在 120 秒内就绪"
}

function Invoke-LocustStage($stage) {
    Write-Host "`n=== $($stage.Name)：$($stage.Users) users / $($stage.Duration) ==="
    $prefix = Join-Path $resultsDir $stage.Prefix
    $logFile = "$prefix.log"
    $statsFile = "$prefix-docker-stats.csv"
    "timestamp,name,cpu,memory" | Set-Content -LiteralPath $statsFile -Encoding utf8
    $statsJob = Start-Job -ArgumentList $statsFile -ScriptBlock {
        param($OutputPath)
        while ($true) {
            $capturedAt = Get-Date -Format "o"
            $rows = docker stats --no-stream `
                --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}}" `
                ecom-agent-loadtest-backend-1 `
                ecom-agent-loadtest-postgres-1 `
                ecom-agent-loadtest-redis-1
            foreach ($row in $rows) {
                "$capturedAt,$row" | Add-Content -LiteralPath $OutputPath -Encoding utf8
            }
            Start-Sleep -Seconds 5
        }
    }
    Push-Location $repoRoot
    try {
        & uv run locust `
            -f $locustFile `
            $stage.UserClass `
            --headless `
            --host $target `
            --users $stage.Users `
            --spawn-rate $stage.SpawnRate `
            --run-time $stage.Duration `
            --stop-timeout 10 `
            --exit-code-on-error 0 `
            --csv $prefix `
            --csv-full-history `
            --html "$prefix.html" 2>&1 | Tee-Object -FilePath $logFile
    } finally {
        Pop-Location
        Stop-Job -Job $statsJob -ErrorAction SilentlyContinue
        Receive-Job -Job $statsJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $statsJob -Force -ErrorAction SilentlyContinue
    }
}

$runError = $null
$previousAccountsFile = $env:LOAD_TEST_ACCOUNTS_FILE
try {
    docker compose -f $composeFile down -v --remove-orphans | Out-Host
    docker compose -f $composeFile up -d --build | Out-Host
    Wait-Backend

    docker compose -f $composeFile exec -T backend `
        uv run --no-sync python -m load_tests.seed_users `
        $seededUsers /tmp/load-test-accounts.json | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "隔离压测账号预置失败，退出码：$LASTEXITCODE"
    }

    $backendContainer = docker compose -f $composeFile ps -q backend
    $backendContainer = ($backendContainer | Select-Object -First 1).Trim()
    if (-not $backendContainer) {
        throw "没有找到隔离压测 backend 容器"
    }
    docker cp "${backendContainer}:/tmp/load-test-accounts.json" $accountsFile | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "压测账号文件复制失败，退出码：$LASTEXITCODE"
    }
    $env:LOAD_TEST_ACCOUNTS_FILE = $accountsFile

    for ($index = 0; $index -lt $stages.Count; $index++) {
        Invoke-LocustStage $stages[$index]
        if ($index -lt $stages.Count - 1) {
            Write-Host "阶段冷却 $cooldownSeconds 秒，避免上一阶段残留请求污染结果。"
            Start-Sleep -Seconds $cooldownSeconds
        }
    }
} catch {
    $runError = $_
} finally {
    docker compose -f $composeFile logs --no-color backend `
        | Set-Content -LiteralPath (Join-Path $resultsDir "backend.log") -Encoding utf8
    docker compose -f $composeFile ps `
        | Set-Content -LiteralPath (Join-Path $resultsDir "compose-ps.txt") -Encoding utf8

    if (-not $KeepEnvironment) {
        docker compose -f $composeFile down -v --remove-orphans | Out-Host
    }

    $env:LOAD_TEST_ACCOUNTS_FILE = $previousAccountsFile
    if (Test-Path -LiteralPath $accountsFile) {
        Remove-Item -LiteralPath $accountsFile -Force
    }
}

Push-Location $repoRoot
try {
    $generatedReportFile = if ($null -eq $runError) {
        $reportFile
    } else {
        Join-Path $PSScriptRoot "压测报告-失败.md"
    }
    uv run python load_tests\summarize.py `
        $resultsDir $metadataFile $generatedReportFile
    if ($LASTEXITCODE -ne 0) {
        throw "压测报告生成失败，退出码：$LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host "`n压测报告：$generatedReportFile"
Write-Host "原始结果：$resultsDir"

if ($null -ne $runError) {
    throw $runError
}
