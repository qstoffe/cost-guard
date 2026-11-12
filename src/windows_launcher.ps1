param([ValidateSet('report', 'watch', 'diagnostics')][string]$Mode = 'report')

# Shared Windows terminal boundary. No policy changes outside this PowerShell process.
$ErrorActionPreference = 'Stop'
$code = 1
# Feedback belongs only to this console, never to the caller's prompt.
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

    # Explicitly enable Ctrl+C before Python, including direct/legacy invocations.
    # The wrapper starts a separate console; no waiting batch owns this input.
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

    . (Join-Path $PSScriptRoot 'python_discovery.ps1')
    $found = Find-CostGuardPython
    $python = $found.Executable
    $pythonArgs = $found.Arguments
    if (-not $python) {
        Clear-LauncherStatus
        Write-Host (Get-CostGuardPythonFailure $found.Failure)
        Write-Host "`nDiagnostics: development\user-tools\diagnostics\windows\Cost-Guard-Diagnostics.cmd"
        $global:LASTEXITCODE = 9009
        return
    }

    $target = 'cost-guard-cli.py'
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
    Write-Host "COST GUARD COULD NOT START`n`nReason: The Windows launcher could not run the command.`n`nNext step: Retry from a local checkout; run Cost Guard Diagnostics if this repeats."
}
Clear-LauncherStatus
if ($code -ne 0) { Write-Host ('Cost Guard command exited with code ' + $code + '.') }
$global:LASTEXITCODE = $code
# Return to the ordinary interactive prompt; never exit or wait for Enter here.
