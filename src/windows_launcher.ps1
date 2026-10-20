param([ValidateSet('report', 'watch', 'diagnostics')][string]$Mode = 'report')

# Shared Windows terminal boundary. No policy changes outside this PowerShell process.
$ErrorActionPreference = 'Stop'
$code = 1
# The batch wrapper already writes before PowerShell startup. Direct invocations
# get the same feedback here, before Add-Type or Python discovery.
$interactiveStatus = -not [Console]::IsOutputRedirected
if ($env:COST_GUARD_LAUNCHER_STATUS -ne 'pending') {
    if ($interactiveStatus) { Write-Host -NoNewline 'Cost Guard: Checking requirements...' }
    else { Write-Host 'Cost Guard: Checking requirements...' }
} elseif (-not $interactiveStatus) { Write-Host '' }
if ($interactiveStatus) { $env:COST_GUARD_LAUNCHER_STATUS = '1' }
else { Remove-Item Env:COST_GUARD_LAUNCHER_STATUS -ErrorAction SilentlyContinue }

function Clear-LauncherStatus {
    if ($env:COST_GUARD_LAUNCHER_STATUS -eq '1') {
        Write-Host -NoNewline ("`r" + (' ' * 40) + "`r")
        Remove-Item Env:COST_GUARD_LAUNCHER_STATUS
    }
}
try {
    Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

    # cmd's start /b inherits ignored Ctrl+C. Re-enable it before spawning Python;
    # cmd has already exited, so no outer batch can ask to terminate a batch job.
    if (-not ('CostGuardLauncherConsole' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CostGuardLauncherConsole {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetConsoleCtrlHandler(IntPtr handler, bool add);
}
'@
    }
    if (-not [CostGuardLauncherConsole]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)) {
        throw 'Cost Guard could not enable console Ctrl+C handling.'
    }

    $python = $null
    $pythonArgs = @()
    $tested = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in @(@{Name = 'py.exe'; Args = @('-3')}, @{Name = 'python.exe'; Args = @()})) {
        # Get-Command may return multiple PATH matches. Probe each executable independently.
        foreach ($application in @(Get-Command $candidate.Name -All -CommandType Application -ErrorAction SilentlyContinue)) {
            if (-not $application -or -not $application.Source) { continue }
            if (-not $tested.Add($application.Source)) { continue }
            $arguments = $candidate.Args
            try {
                & $application.Source @arguments -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 1>$null 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $python = $application.Source
                    $pythonArgs = $arguments
                    break
                }
            } catch { continue }
        }
        if ($python) { break }
    }
    if (-not $python) {
        Clear-LauncherStatus
        Write-Host 'Cost Guard could not find Python 3.11 or newer.'
        Write-Host 'Install Python 3.11+ and run this launcher again.'
        $global:LASTEXITCODE = 9009
        return
    }

    $target = 'cost-guard.py'
    $programArgs = @()
    if ($Mode -eq 'watch') { $programArgs = @('--watch') }
    if ($Mode -eq 'diagnostics') {
        $target = 'development\tools\collect_diagnostics.py'
        $programArgs = @('--test-service-start')
    }
    & $python @pythonArgs $target @programArgs
    $code = $LASTEXITCODE
} catch {
    Clear-LauncherStatus
    Write-Host 'Cost Guard - Windows launcher error'
    Write-Host $_.Exception.Message
}
Clear-LauncherStatus
if ($code -ne 0) { Write-Host ('Cost Guard command exited with code ' + $code + '.') }
$global:LASTEXITCODE = $code
# Return to the ordinary interactive prompt; never exit or wait for Enter here.
