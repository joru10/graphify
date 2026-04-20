on run
  set repoRoot to "__ROOT_DIR__"
  set nativeRunner to repoRoot & "/scripts/run_graphify_native.sh"

  set targetDir to choose folder with prompt "Choose the folder to graphify"
  set targetPosix to POSIX path of targetDir

  set modeChoice to choose from list {"Full scan", "Update existing graph"} with prompt "Select Graphify mode" default items {"Full scan"}
  if modeChoice is false then
    return
  end if
  set selectedMode to item 1 of modeChoice

  if not (do shell script "test -x " & quoted form of nativeRunner & " && echo ok || echo missing") is "ok" then
    display dialog "Graphify is not set up yet. Click Install to prepare the local environment." buttons {"Cancel", "Install"} default button "Install" with icon caution
    do shell script "cd " & quoted form of repoRoot & " && ./scripts/setup_local.sh recommended > /tmp/graphify_setup.log 2>&1"
  end if

  set logPath to "/tmp/graphify_gui_run.log"
  set statusPath to "/tmp/graphify_gui_status.txt"
  set modeArg to "full"
  if selectedMode is "Update existing graph" then
    set modeArg to "update"
  end if

  do shell script "rm -f " & quoted form of logPath & " " & quoted form of statusPath
  do shell script "printf '%s\n' \"Graphify started at $(date)\" > " & quoted form of logPath

  set runCmd to quoted form of nativeRunner & space & quoted form of targetPosix & space & quoted form of modeArg
  set launchCmd to "cd " & quoted form of repoRoot & " && (" & runCmd & " >> " & quoted form of logPath & " 2>&1; echo $? > " & quoted form of statusPath & ") & echo $!"
  set runPid to do shell script launchCmd

  display notification "Processing started. You can keep using your Mac." with title "Graphify Launcher"

  set progress total steps to 100
  set progress completed steps to 0
  set progress description to "Graphify is running"
  set progress additional description to "Building graph and report..."

  repeat
    set doneFlag to do shell script "test -f " & quoted form of statusPath & " && echo yes || echo no"
    if doneFlag is "yes" then exit repeat
    set progress completed steps to ((progress completed steps + 1) mod 100)
    delay 1
  end repeat

  set exitCode to do shell script "cat " & quoted form of statusPath
  set progress completed steps to 100
  set progress description to ""
  set progress additional description to ""

  set reportPath to targetPosix & "graphify-out/GRAPH_REPORT.md"
  set htmlPath to targetPosix & "graphify-out/graph.html"
  set outPath to targetPosix & "graphify-out/"

  if exitCode is "0" then
    do shell script "if [ -f " & quoted form of reportPath & " ]; then open " & quoted form of reportPath & "; fi"
    do shell script "if [ -f " & quoted form of htmlPath & " ]; then open " & quoted form of htmlPath & "; fi"
    display notification "Completed successfully." with title "Graphify Launcher"
    display dialog "Graphify finished successfully." buttons {"Open Log", "Open Output Folder", "OK"} default button "OK"
    if button returned of result is "Open Log" then
      do shell script "open " & quoted form of logPath
    else if button returned of result is "Open Output Folder" then
      do shell script "open " & quoted form of outPath
    end if
  else
    set tailLog to do shell script "tail -n 40 " & quoted form of logPath
    display notification "Run failed. Open log for details." with title "Graphify Launcher"
    display dialog "Graphify failed (exit " & exitCode & ")." & return & return & tailLog buttons {"Open Log", "OK"} default button "Open Log" with icon stop
    if button returned of result is "Open Log" then
      do shell script "open " & quoted form of logPath
    end if
  end if
end run
