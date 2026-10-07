param([ValidateSet('report', 'watch', 'diagnostics')][string]$Mode = 'report')

# Shared Windows terminal boundary. No policy changes outside this PowerShell process.
$ErrorActionPreference = 'Stop'
$code = 1
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
    foreach ($candidate in @(@{Name = 'py.exe'; Args = @('-3')}, @{Name = 'python.exe'; Args = @()})) {
        $application = Get-Command $candidate.Name -CommandType Application -ErrorAction SilentlyContinue
        if (-not $application) { continue }
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
    if (-not $python) {
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
    Write-Host 'Cost Guard - Windows launcher error'
    Write-Host $_.Exception.Message
}
if ($code -ne 0) { Write-Host ('Cost Guard command exited with code ' + $code + '.') }
$global:LASTEXITCODE = $code
# Return to the ordinary interactive prompt; never exit or wait for Enter here.
