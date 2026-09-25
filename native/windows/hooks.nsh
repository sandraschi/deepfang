; Kill UI + backend before install/uninstall (backend locks resources/*.exe).
!macro KillDeepfangFleetProcesses
  DetailPrint "Stopping deepfang processes..."
  ExecWait 'taskkill /F /IM deepfang-backend.exe /T' $0
  ExecWait 'taskkill /F /IM deepfang-native.exe /T' $0
  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::KillProcessCurrentUser "deepfang-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcessCurrentUser "deepfang-native.exe"
    Pop $0
  !else
    nsis_tauri_utils::KillProcess "deepfang-backend.exe"
    Pop $0
    nsis_tauri_utils::KillProcess "deepfang-native.exe"
    Pop $0
  !endif
  Sleep 2000
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro KillDeepfangFleetProcesses
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro KillDeepfangFleetProcesses
!macroend

!macro NSIS_HOOK_POSTINSTALL
  IfFileExists "$INSTDIR\resources\install-mcp-clients.ps1" 0 mcp_hook_done
    DetailPrint "Optional: register deepfang in Cursor / Claude Desktop"
    ExecWait 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\resources\install-mcp-clients.ps1" -Interactive'
  mcp_hook_done:
!macroend