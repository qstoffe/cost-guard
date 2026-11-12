# This short-lived status process is never the managed host's lifetime owner.
param([switch]$Detached)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$message = "COST GUARD COULD NOT START`n`nReason: The Windows Web launcher failed.`n`nNext step: Run Cost Guard Diagnostics, then retry."
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
function Get-WebFailureText {
    param([string]$Failure)
    $messages = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'launch_messages.json') -Raw | ConvertFrom-Json
    $entry = $messages.PSObject.Properties[$Failure]
    if (-not $entry) { return $null }
    $reason = if ($entry.Value -is [string]) { $entry.Value } else { $entry.Value.windows }
    $title = 'COST GUARD COULD NOT START'
    $action = 'Preserve Web state; run Diagnostics, then retry. Legacy CLI remains available.'
    if ($Failure -eq 'configuration_unavailable') { $action = 'Check config/user-config.jsonc, then retry.' }
    if ($Failure -eq 'browser_open_failed') {
        $title = 'COST GUARD WEB IS RUNNING'
        $action = 'Use tray Open Cost Guard to retry the browser.'
    }
    return "$title`n`nReason: $reason`n`nNext step: $action"
}
$code = 1
$python = $null
try {
    Start-LaunchActivity
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'python_discovery.ps1')
    $found = Find-CostGuardPython -Activity { Write-LaunchActivity }
    $python = if ($found) { $found.Executable } else { $null }
    [array]$pythonArgs = if ($found) { $found.Arguments } else { @() }
    if (-not $python) {
        $message = Get-CostGuardPythonFailure $found.Failure
    } else {
        # Drain internal stages without repainting the label or accumulating lines.
        # Keep only allowlisted failure text; raw subprocess exceptions stay private.
        $safe = $null
        $info = [Diagnostics.ProcessStartInfo]::new()
        $info.FileName = $python
        $info.Arguments = (($pythonArgs + @('-u', ('"' + (Join-Path $root 'cost-guard-web.py') + '"'), '--launch-windows')) -join ' ')
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $child = [Diagnostics.Process]::Start($info)
        try {
            $errors = $child.StandardError.BaseStream.CopyToAsync([IO.Stream]::Null)
            while ($true) {
                $line = $child.StandardOutput.ReadLineAsync()
                while (-not $line.IsCompleted) { Write-LaunchActivity; Start-Sleep -Milliseconds 120 }
                $value = $line.GetAwaiter().GetResult()
                if ($null -eq $value) { break }
                if ($value -match '^Cost Guard failure: ([a-z_]{1,64})$') {
                    $known = Get-WebFailureText $matches[1]
                    if ($known) { $safe = $known }
                }
            }
            while (-not $child.WaitForExit(120)) { Write-LaunchActivity }
            $code = $child.ExitCode
        } finally { $child.Dispose() }
        if ($code -eq 0) { exit 0 }
        # Python emits only fixed allowlisted failure text; never display raw exceptions.
        if ($safe) { $message = $safe }
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
$message += "`n`nDiagnostics: development\user-tools\diagnostics\windows\Cost-Guard-Diagnostics.cmd"
Write-Host $message
if (-not $Detached -and [Environment]::UserInteractive -and
    -not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($message, 'Cost Guard') | Out-Null
    } catch {
        # Only a genuinely interactive launcher can retain an error prompt.
        Read-Host 'Press Enter to return' | Out-Null
    }
}
exit $code
