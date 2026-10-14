Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & Replace(WScript.ScriptFullName, "AEGIS_App.vbs", "Launch_AEGIS_App.bat") & chr(34), 0
Set WshShell = Nothing
