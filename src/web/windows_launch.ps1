# Beta only: return to existing terminals; Explorer's transient console exits on success.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$message = 'Web launcher failed. Run development\user-tools\diagnostics\windows\Cost Guard Diagnostics.cmd.'
function Find-BetaPython {
    $tested = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in @(@{Name = 'py.exe'; Args = @('-3')}, @{Name = 'python.exe'; Args = @()})) {
        foreach ($application in @(Get-Command $candidate.Name -All -CommandType Application -ErrorAction SilentlyContinue)) {
            if (-not $application -or -not $application.Source -or -not $tested.Add($application.Source)) { continue }
            $arguments = $candidate.Args
            try {
                & $application.Source @arguments -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 1>$null 2>$null
                if ($LASTEXITCODE -eq 0) {
                    return @{Executable = $application.Source; Arguments = $arguments}
                }
            } catch { continue }
        }
    }
    return $null
}
$code = 1
try {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    Write-Host 'Cost Guard startup: Checking Python 3.11+...'
    Write-Progress -Activity 'Cost Guard Web Beta startup' -Status 'Checking Python' -PercentComplete -1
    $found = Find-BetaPython
    $python = if ($found) { $found.Executable } else { $null }
    [array]$pythonArgs = if ($found) { $found.Arguments } else { @() }
    if (-not $python) {
        $message = 'Python 3.11 or newer was not found. Install Python, then retry Cost Guard Web Beta.'
    } else {
        Write-Host ('Cost Guard startup: Python ready ({0:N1}s elapsed)' -f $timer.Elapsed.TotalSeconds)
        # Stream flushed, fixed progress instead of buffering the entire launch.
        # Keep only allowlisted failure text; raw subprocess exceptions stay private.
        $safe = @()
        & $python @pythonArgs -u (Join-Path $root 'cost-guard-web.py') --launch-windows 2>$null | ForEach-Object {
            if ($_ -match '^Cost Guard startup: [A-Za-z0-9 ;,+().-]+$') {
                Write-Host $_
                Write-Progress -Activity 'Cost Guard Web Beta startup' -Status $_ -PercentComplete -1
            } elseif ($_ -like 'Cost Guard Web Beta: *') {
                $safe += $_
            }
        }
        $code = $LASTEXITCODE
        Write-Progress -Activity 'Cost Guard Web Beta startup' -Completed
        if ($code -eq 0) { exit 0 }
        # Python emits only fixed allowlisted failure text; never display raw exceptions.
        if ($safe.Count -gt 0) { $message = $safe[-1] }
    }
} catch {
    $code = 1
}
Write-Progress -Activity 'Cost Guard Web Beta startup' -Completed

function Write-BetaStartupRecord {
    param([string]$Directory, [ValidateSet('python_unavailable', 'launcher_failed')][string]$Failure)
    # Reject linked ancestors; install the current user's DACL before writing.
    $ancestor = $directory
    while ($ancestor) {
        if ((Test-Path -LiteralPath $ancestor) -and
            ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Unsafe diagnostic path.'
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl.SetOwner($sid)
    $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
    [IO.DirectoryInfo]::new($directory).SetAccessControl($acl)
    $log = Join-Path $directory 'startup.log'
    if (Test-Path -LiteralPath $log) {
        if ((Get-Item -LiteralPath $log -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unsafe log.' }
        Remove-Item -LiteralPath $log
    }
    [IO.File]::WriteAllText($log, ([DateTime]::UtcNow.ToString('s') + ' ' + $failure))
}
# Record a minimal offline failure even when Python is missing.
try {
    $base = [Environment]::GetFolderPath('LocalApplicationData')
    $failure = if ($python) { 'launcher_failed' } else { 'python_unavailable' }
    Write-BetaStartupRecord -Directory (Join-Path $base 'CostGuard\Web\launcher') -Failure $failure
} catch {
    Write-Host 'Private startup diagnostic could not be recorded.'
}
Write-Host $message
Write-Host 'Diagnostics: development\user-tools\diagnostics\windows\Cost Guard Diagnostics.cmd'
try {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($message + "`nRun Cost Guard Diagnostics for details.", 'Cost Guard Web Beta') | Out-Null
} catch {
    # Without the native dialog, keep an Explorer-started console readable on failure.
    if (-not [Console]::IsInputRedirected) { Read-Host 'Press Enter to return' | Out-Null }
}
exit $code
