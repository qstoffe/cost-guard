# This short-lived status process is never the managed host's lifetime owner.
param([switch]$Detached)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$message = 'Web launcher failed. Run development\user-tools\diagnostics\windows\Cost-Guard-Diagnostics.cmd.'
$script:frame = 0
$script:activity = $null
function Start-LaunchActivity {
    $label = 'Starting CostGuard web...'
    # Redirected/hidden hosts get plain deterministic text, never terminal controls.
    if (-not $Detached -and [Environment]::UserInteractive -and
        -not [Console]::IsOutputRedirected -and -not [Console]::IsInputRedirected) {
        try {
            if ([Console]::WindowWidth -gt ($label.Length + 3)) {
                if ([Console]::CursorLeft + $label.Length + 3 -ge [Console]::WindowWidth) { [Console]::WriteLine() }
                [Console]::Write($label + ' ')
                $script:activity = @{Left = [Console]::CursorLeft; Top = [Console]::CursorTop; Timer = [Diagnostics.Stopwatch]::StartNew()}
                [Console]::Write('|')
                return
            }
        } catch { $script:activity = $null }
    }
    Write-Host $label
}
function Write-LaunchActivity {
    if ($script:activity -and $script:activity.Timer.ElapsedMilliseconds -ge 120) {
        try {
            $script:frame++
            [Console]::SetCursorPosition($script:activity.Left, $script:activity.Top)
            [Console]::Write(@('|', '/', '-', '\')[$script:frame % 4])
            $script:activity.Timer.Restart()
        } catch { Stop-LaunchActivity }
    }
}
function Stop-LaunchActivity {
    if ($script:activity) {
        try {
            [Console]::SetCursorPosition($script:activity.Left, $script:activity.Top)
            [Console]::Write(' ')
            [Console]::WriteLine()
        } catch { } # Console loss must not hide actionable launcher failures.
        $script:activity = $null
    }
}
function Find-WebPython {
    $tested = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in @(@{Name = 'py.exe'; Args = @('-3')}, @{Name = 'python.exe'; Args = @()})) {
        foreach ($application in @(Get-Command $candidate.Name -All -CommandType Application -ErrorAction SilentlyContinue)) {
            if (-not $application -or -not $application.Source -or -not $tested.Add($application.Source)) { continue }
            $arguments = $candidate.Args
            $probe = $null
            try {
                # A broken launcher must not strand an invisible discovery process.
                $info = [Diagnostics.ProcessStartInfo]::new()
                $info.FileName = $application.Source
                $info.Arguments = (($arguments + @('-c', '"import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"')) -join ' ')
                $info.UseShellExecute = $false
                $info.CreateNoWindow = $true
                $info.RedirectStandardOutput = $true
                $info.RedirectStandardError = $true
                $probe = [Diagnostics.Process]::Start($info)
                $deadline = [Diagnostics.Stopwatch]::StartNew()
                while (-not $probe.WaitForExit(120) -and $deadline.ElapsedMilliseconds -lt 5000) {
                    Write-LaunchActivity
                }
                if (-not $probe.HasExited) {
                    $probe.Kill() # Only this exact discovery process, never a PID/name search.
                    $probe.WaitForExit(1000) | Out-Null
                    continue
                }
                if ($probe.ExitCode -eq 0) {
                    return @{Executable = $application.Source; Arguments = $arguments}
                }
            } catch { continue }
            finally { if ($probe) { $probe.Dispose() } }
        }
    }
    return $null
}
$code = 1
$python = $null
try {
    Start-LaunchActivity
    $found = Find-WebPython
    $python = if ($found) { $found.Executable } else { $null }
    [array]$pythonArgs = if ($found) { $found.Arguments } else { @() }
    if (-not $python) {
        $message = 'Python 3.11 or newer was not found. Install Python, then retry Cost Guard.'
    } else {
        # Drain internal stages without repainting the label or accumulating lines.
        # Keep only allowlisted failure text; raw subprocess exceptions stay private.
        $safe = @()
        $info = [Diagnostics.ProcessStartInfo]::new()
        $info.FileName = $python
        $info.Arguments = (($pythonArgs + @('-u', ('"' + (Join-Path $root 'cost-guard-web.py') + '"'), '--launch-windows')) -join ' ')
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $child = [Diagnostics.Process]::Start($info)
        try {
            $errors = $child.StandardError.ReadToEndAsync()
            while ($true) {
                $line = $child.StandardOutput.ReadLineAsync()
                while (-not $line.IsCompleted) { Write-LaunchActivity; Start-Sleep -Milliseconds 120 }
                $value = $line.GetAwaiter().GetResult()
                if ($null -eq $value) { break }
                if ($value -like 'Cost Guard: *') {
                    $safe += $value
                }
            }
            while (-not $child.WaitForExit(120)) { Write-LaunchActivity }
            $code = $child.ExitCode
        } finally { $child.Dispose() }
        if ($code -eq 0) { exit 0 }
        # Python emits only fixed allowlisted failure text; never display raw exceptions.
        if ($safe.Count -gt 0) { $message = $safe[-1] }
    }
} catch {
    $code = 1
} finally {
    Stop-LaunchActivity
}

function Write-WebStartupRecord {
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
    Write-WebStartupRecord -Directory (Join-Path $base 'CostGuard\Web\launcher') -Failure $failure
} catch {
    Write-Host 'Private startup diagnostic could not be recorded.'
}
Write-Host $message
Write-Host 'Diagnostics: development\user-tools\diagnostics\windows\Cost-Guard-Diagnostics.cmd'
Write-Host 'Legacy CLI: windows\Legacy\Cost-Guard.cmd or python cost-guard-cli.py (requires Python 3.11+).'
if (-not $Detached -and [Environment]::UserInteractive -and
    -not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($message + "`nRun Cost Guard Diagnostics for details.`nLegacy CLI: windows\Legacy\Cost-Guard.cmd", 'Cost Guard') | Out-Null
    } catch {
        # Only a genuinely interactive launcher can retain an error prompt.
        Read-Host 'Press Enter to return' | Out-Null
    }
}
exit $code
