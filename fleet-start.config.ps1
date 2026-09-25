# Per-repo fleet start config for deepfang
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'deepfang'
    BackendPort  = 0
    FrontendPort = 0
    HealthPath   = '/health'
    WebRoot      = '.'
    Backend = @{
        Kind = 'none'
    }
    Frontend = @{
        Kind = 'none'
    }
}
