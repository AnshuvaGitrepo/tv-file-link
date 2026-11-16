# Runs both suites (file manager, Wi-Fi transfer) on two Android TV emulators with the current APK.
# Usage: run_all.ps1 <v1.2 x86 APK> [first-avd] [second-avd]
# The first AVD must already be running. Logs: work/tests/results/*.log
$ErrorActionPreference = "Continue"
$tests = $PSScriptRoot
$res = Join-Path $tests "results"
$adb = "$env:ANDROID_HOME\platform-tools\adb.exe"
$emu = "$env:ANDROID_HOME\emulator\emulator.exe"
$env:OLD_APK = $args[0]
$avds = @($(if ($args[1]) { $args[1] } else { "TVFileLink_TV28" }), $(if ($args[2]) { $args[2] } else { "TVFileLink_TV30" }))
Set-Location $tests

function Wait-Boot {
    & $adb wait-for-device
    for ($i = 0; $i -lt 120; $i++) {
        if ((& $adb shell getprop sys.boot_completed 2>$null) -match "1") { Start-Sleep 15; return }
        Start-Sleep 3
    }
}

function Run-Suites {
    $api = (& $adb shell getprop ro.build.version.sdk).Trim()
    "== API $api $(Get-Date -Format HH:mm)"
    if ($api -eq "30") { Remove-Item Env:SHOTS_DIR -ErrorAction SilentlyContinue }  # guide screenshots
    else { $env:SHOTS_DIR = Join-Path $res "shots-api$api"; New-Item -ItemType Directory -Force $env:SHOTS_DIR | Out-Null }
    python -u filemanager_test.py *> (Join-Path $res "fm-run-api$api.log"); "fm$api exit=$LASTEXITCODE"
    python -u emulator_test.py *> (Join-Path $res "tr-run-api$api.log"); "tr$api exit=$LASTEXITCODE"
}

Run-Suites
"== switch to $($avds[1]) $(Get-Date -Format HH:mm)"
& $adb emu kill | Out-Null
Start-Sleep 10
Start-Process -FilePath $emu -ArgumentList "-avd $($avds[1]) -no-window -no-audio -no-snapshot -no-boot-anim -gpu swiftshader_indirect" -WindowStyle Hidden
Wait-Boot
Run-Suites
"== done $(Get-Date -Format HH:mm)"
