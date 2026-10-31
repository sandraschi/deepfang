# Per-repo fleet start config for deepfang
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'deepfang'
    BackendPort  = 10956
    FrontendPort = 10957
    HealthPath   = '/health'
    WebRoot      = 'dashboard'
    Backend = @{
        # Docker-Compose stack (sanitizer :10958, supervisor :10956, worker).
        # Started separately via `just up` - the fleet engine has no
        # docker-compose kind, so there is nothing to launch here.
        Kind = 'none'
    }
    Frontend = @{
        Kind           = 'vite-npm'
        PackageManager = 'npm'
        InstallOnStart = $true
    }
}
