-- Compiled locally with the macOS-included osacompile, never distributed as binary.
-- No Finder/Terminal scripting, login item or Automation permission is required.
on run
    try
        do shell script "{{LAUNCH_COMMAND}}"
    on error number errorNumber
        if errorNumber is 4 then
            display alert "Cost Guard is running" message "The default browser could not open. Use Open Cost Guard from the CG menu to retry."
        else
            display alert "Cost Guard could not start" message "Use macos/Cost-Guard-Web.command for startup details or macos/Legacy/Cost-Guard.command for CLI. Run Cost Guard Diagnostics if needed. No extra packages or developer tools are required."
        end if
    end try
end run
