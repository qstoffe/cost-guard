# Python-independent Windows discovery, shared by Web, Legacy and Diagnostics.
# Never execute Store python aliases or ask a launcher to install/select a runtime.
function Invoke-CostGuardPythonProcess {
    param([string]$Executable, [string]$Arguments, [int]$Timeout = 2000, [scriptblock]$Activity = {})
    $process = $null
    try {
        $info = [Diagnostics.ProcessStartInfo]::new()
        $info.FileName = $Executable
        $info.Arguments = $Arguments
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardInput = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $info.EnvironmentVariables.Remove('PYLAUNCHER_ALLOW_INSTALL')
        $info.EnvironmentVariables['PYTHON_MANAGER_AUTOMATIC_INSTALL'] = 'false'
        $process = [Diagnostics.Process]::Start($info)
        $process.StandardInput.Close()
        # Fixed buffers: malformed executables cannot fill memory or block a pipe forever.
        $output = [char[]]::new(8193)
        $errors = [char[]]::new(8193)
        $read = $process.StandardOutput.ReadBlockAsync($output, 0, $output.Length)
        $errorRead = $process.StandardError.ReadBlockAsync($errors, 0, $errors.Length)
        $timer = [Diagnostics.Stopwatch]::StartNew()
        while (-not $process.WaitForExit(100)) {
            & $Activity
            if ($timer.ElapsedMilliseconds -ge $Timeout -or
                ($read.IsCompleted -and $read.Result -eq $output.Length) -or
                ($errorRead.IsCompleted -and $errorRead.Result -eq $errors.Length)) { return $null }
        }
        if (-not $read.Wait(100) -or -not $errorRead.Wait(100) -or
            $read.Result -eq $output.Length -or $errorRead.Result -eq $errors.Length) { return $null }
        return @{Code = $process.ExitCode; Output = [string]::new($output, 0, $read.Result)}
    } catch { return $null }
    finally {
        if ($process) {
            if (-not $process.HasExited) {
                $process.Kill() # This exact owned probe only; no process-name/PID discovery.
                $process.WaitForExit(1000) | Out-Null
            }
            $process.Dispose()
        }
    }
}

function Get-CostGuardRegisteredPython {
    # PEP 514: both user/machine hives and both views, including non-PythonCore vendors.
    foreach ($hive in @([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryHive]::LocalMachine)) {
        foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
            $base = $tree = $null
            try {
                $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($hive, $view)
                $tree = $base.OpenSubKey('Software\Python')
                if (-not $tree) { continue }
                foreach ($company in @($tree.GetSubKeyNames() | Sort-Object | Select-Object -First 32)) {
                    $vendor = $tree.OpenSubKey($company)
                    try {
                        foreach ($tag in @($vendor.GetSubKeyNames() | Sort-Object -Descending | Select-Object -First 64)) {
                            $install = $vendor.OpenSubKey($tag + '\InstallPath')
                            if (-not $install) { continue }
                            try {
                                $executable = $install.GetValue('ExecutablePath')
                                if ($executable -is [string] -and $executable) { $executable }
                                $directory = $install.GetValue('')
                                if ($directory -is [string] -and $directory) { Join-Path $directory 'python.exe' }
                            } finally { $install.Dispose() }
                        }
                    } finally { if ($vendor) { $vendor.Dispose() } }
                }
            } catch { continue }
            finally {
                if ($tree) { $tree.Dispose() }
                if ($base) { $base.Dispose() }
            }
        }
    }
}

function Get-CostGuardCanonicalPython {
    $patterns = @()
    if ($env:LOCALAPPDATA) {
        $patterns += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe')
        $patterns += (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-*\python.exe')
    }
    foreach ($directory in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:SystemDrive)) {
        if ($directory) { $patterns += (Join-Path ($directory.TrimEnd('\') + '\') 'Python*\python.exe') }
    }
    foreach ($pattern in $patterns) {
        Get-Item -Path $pattern -ErrorAction SilentlyContinue | Sort-Object FullName -Descending |
            Select-Object -First 64 -ExpandProperty FullName
    }
}

function Get-CostGuardPythonCandidates {
    param([Diagnostics.Stopwatch]$Timer, [scriptblock]$Activity, [switch]$Installed)
    if (-not $Installed) {
        foreach ($name in @('python.exe', 'python3.exe')) {
            Get-Command $name -All -CommandType Application -ErrorAction SilentlyContinue |
                Select-Object -First 16 -ExpandProperty Source
        }
        return
    }
    $launchers = @()
    foreach ($name in @('py.exe', 'pymanager.exe')) {
        $launchers += @(Get-Command $name -All -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 8 -ExpandProperty Source)
    }
    if ($env:WINDIR) { $launchers += (Join-Path $env:WINDIR 'py.exe') }
    if ($env:LOCALAPPDATA) {
        $launchers += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe')
        foreach ($package in @('PythonSoftwareFoundation.PythonManager_3847v3x7pw1km',
                               'PythonSoftwareFoundation.PythonManager_qbz5n2kfra8p0')) {
            $launchers += (Join-Path $env:LOCALAPPDATA ('Microsoft\WindowsApps\' + $package + '\py.exe'))
        }
    }
    foreach ($launcher in @($launchers | Select-Object -Unique | Select-Object -First 4)) {
        if (-not [IO.File]::Exists($launcher) -or $Timer.ElapsedMilliseconds -ge 20000) { continue }
        # -0p is an installed-only listing in both the legacy launcher and install manager.
        $listing = Invoke-CostGuardPythonProcess $launcher '-0p' ([Math]::Min(2000, 20000 - $Timer.ElapsedMilliseconds)) $Activity
        if ($listing -and $listing.Code -eq 0) {
            foreach ($line in ($listing.Output -split '\r?\n')) {
                if ($line -match '^\s*-\S+\s+(?:\*\s*)?([A-Za-z]:\\[^\r\n]+\.exe)\s*$') { $matches[1].Trim() }
            }
        }
    }
    Get-CostGuardRegisteredPython
    Get-CostGuardCanonicalPython
}

function Find-CostGuardPython {
    param([scriptblock]$Activity = {})
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $tested = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $old = $broken = $false
    $probeCode = 'import sys,json,sqlite3,ssl,ctypes; print(json.dumps([sys.version_info[0],sys.version_info[1],sys.platform,sys.executable]))'
    foreach ($installed in @($false, $true)) {
      foreach ($candidate in @(Get-CostGuardPythonCandidates $timer $Activity -Installed:$installed | Select-Object -First 128)) {
        if ($timer.ElapsedMilliseconds -ge 20000) { $broken = $true; break }
        # Do not launch python.exe execution aliases (which can open the Store).
        if (-not $candidate -or $candidate -notmatch '^[A-Za-z]:\\' -or
            $candidate -match '[\r\n"]|\\Microsoft\\WindowsApps\\' -or
            [IO.Path]::GetExtension($candidate) -ne '.exe') { continue }
        $candidate = [IO.Path]::GetFullPath($candidate)
        if (-not $tested.Add($candidate)) { continue }
        $result = Invoke-CostGuardPythonProcess $candidate ('-I -S -c "' + $probeCode + '"') ([Math]::Min(2000, 20000 - $timer.ElapsedMilliseconds)) $Activity
        try {
            if (-not $result -or $result.Code -ne 0) { $broken = $true; continue }
            $facts = ConvertFrom-Json -InputObject $result.Output -ErrorAction Stop
            if ($facts.Count -ne 4 -or $facts[2] -ne 'win32' -or $facts[0] -isnot [ValueType] -or
                $facts[1] -isnot [ValueType] -or $facts[3] -notmatch '^[A-Za-z]:\\[^\r\n"]+\.exe$') {
                $broken = $true; continue
            }
            if ($facts[0] -lt 3 -or ($facts[0] -eq 3 -and $facts[1] -lt 11)) { $old = $true; continue }
            $real = [IO.Path]::GetFullPath($facts[3])
            if ($real -match '\\Microsoft\\WindowsApps\\' -or -not [IO.File]::Exists($real)) { $broken = $true; continue }
            # Resolve shims/launchers to a real interpreter; validate the direct invocation too.
            if ($real -ne $candidate) {
                $direct = Invoke-CostGuardPythonProcess $real ('-I -S -c "' + $probeCode + '"') 2000 $Activity
                if (-not $direct -or $direct.Code -ne 0 -or $direct.Output.Trim() -ne $result.Output.Trim()) { $broken = $true; continue }
            }
            return @{Executable = $real; Arguments = @(); Failure = $null}
        } catch { $broken = $true }
      }
    }
    $failure = if ($broken) { 'broken' } elseif ($old) { 'old' } else { 'missing' }
    return @{Executable = $null; Arguments = @(); Failure = $failure}
}

function Get-CostGuardPythonFailure {
    param([string]$Failure)
    $reason = switch ($Failure) {
        'old' { 'Only Python versions older than 3.11 were usable.' }
        'broken' { 'Discovered Python candidates could not run correctly or timed out.' }
        default { 'No usable Python 3.11+ installation could be located.' }
    }
    return "COST GUARD COULD NOT START`n`nReason: $reason`n`nNext step: Use an installed Python 3.11+ executable directly (see README), or install Python 3.11+."
}
