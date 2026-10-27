Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory of the script
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Set the working directory to the project root
WshShell.CurrentDirectory = scriptDir

' Launch npm start silently without opening a terminal window (0 = hidden, False = non-blocking)
WshShell.Run "cmd /c npm start", 0, False
