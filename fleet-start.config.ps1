# Per-repo fleet start config for deepfang
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'deepfang'
    BackendPort  = 10956
    FrontendPort = 10957
    HealthPath   = '/health'
    WebRoot      = '.'
    Backend = @{
        Kind = 'none'
    }
    Frontend = @{
        Kind = 'none'
    }
}
