on run
  set repoRoot to "__ROOT_DIR__"
  set pythonPath to repoRoot & "/.venv/bin/python"

  set targetDir to choose folder with prompt "Choose the folder to graphify"
  set targetPosix to POSIX path of targetDir

  set modeChoice to choose from list {"Full scan", "Update existing graph"} with prompt "Select Graphify mode" default items {"Full scan"}
  if modeChoice is false then
    return
  end if
  set selectedMode to item 1 of modeChoice

  if not (do shell script "test -x " & quoted form of pythonPath & " && echo ok || echo missing") is "ok" then
    display dialog "Graphify is not set up yet. Click Install to prepare the local environment." buttons {"Cancel", "Install"} default button "Install" with icon caution
    do shell script "cd " & quoted form of repoRoot & " && ./scripts/setup_local.sh recommended > /tmp/graphify_setup.log 2>&1"
  end if

  set logPath to "/tmp/graphify_gui_run.log"
  set modeArg to ""
  if selectedMode is "Update existing graph" then
    set modeArg to " --update"
  end if

  set runCmd to "cd " & quoted form of repoRoot & " && " & quoted form of pythonPath & " -m graphify " & quoted form of targetPosix & modeArg & " > " & quoted form of logPath & " 2>&1"

  with timeout of 86400 seconds
    try
      do shell script runCmd
    on error errMsg number errNum
      set tailLog to do shell script "tail -n 30 " & quoted form of logPath
      display dialog "Graphify failed (" & errNum & ")." & return & return & tailLog buttons {"OK"} default button "OK" with icon stop
      return
    end try
  end timeout

  set reportPath to targetPosix & "graphify-out/GRAPH_REPORT.md"
  set htmlPath to targetPosix & "graphify-out/graph.html"

  do shell script "if [ -f " & quoted form of reportPath & " ]; then open " & quoted form of reportPath & "; fi"
  do shell script "if [ -f " & quoted form of htmlPath & " ]; then open " & quoted form of htmlPath & "; fi"

  display dialog "Graphify finished successfully." buttons {"OK"} default button "OK"
end run
