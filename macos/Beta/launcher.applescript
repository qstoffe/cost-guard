-- Compiled locally with the macOS-included osacompile, never distributed as binary.
-- No Finder/Terminal scripting, login item or Automation permission is required.
on run
    try
        do shell script "{{LAUNCH_COMMAND}}"
    on error number errorNumber
        if errorNumber is 4 then
            display alert "Cost Guard Web is running" message "The default browser could not open. Use Open Cost Guard from the CG menu to retry."
        else
            display alert "Cost Guard Web could not start" message "Use macos/Beta/Cost-Guard-Web.command for startup details. Run the existing Cost Guard Diagnostics launcher if needed. No extra packages or developer tools are required."
        end if
    end try
end run
