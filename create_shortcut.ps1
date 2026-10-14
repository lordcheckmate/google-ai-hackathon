$desktop = [Environment]::GetFolderPath('Desktop')
$targetDir = $PSScriptRoot
$vbsPath = Join-Path $targetDir "AEGIS_App.vbs"
$shortcutPath = Join-Path $desktop "AEGIS AI Meeting Agent.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$vbsPath`""
$shortcut.WorkingDirectory = $targetDir
$shortcut.Description = "AEGIS AI Hearing & Visual Meeting Agent"
if (Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe") {
    $shortcut.IconLocation = "C:\Program Files\Google\Chrome\Application\chrome.exe,0"
}
$shortcut.Save()

Write-Host "Desktop shortcut created successfully at: $shortcutPath"
