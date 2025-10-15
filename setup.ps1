#!/usr/bin/env pwsh
# Stop on first error
$ErrorActionPreference = "Stop"

Write-Host "`nStarting Slack Audit Bot setup (Windows PowerShell)...`n"

# Check if .env exists
if (-Not (Test-Path ".env")) {
    Write-Host "The .env file not found! Please create one.`n"
    exit 1
}

# Load .env variables (skip comments and empty lines)
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        $parts = $line -split "=", 2
        if ($parts.Count -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()

            # Remove surrounding quotes if present
            if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            }

            # Export variable to process environment
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

# Check if external DB is configured
if ($env:EXTERNAL_POSTGRES_HOST) {
    Write-Host "Using external PostgreSQL: $($env:EXTERNAL_POSTGRES_HOST):$($env:EXTERNAL_POSTGRES_PORT)`n"
    $env:POSTGRES_HOST = $env:EXTERNAL_POSTGRES_HOST
    $env:POSTGRES_PORT = $env:EXTERNAL_POSTGRES_PORT
    docker compose up -d bot
} else {
    Write-Host "Starting local PostgreSQL with Docker...`n"
    docker compose up -d db
    Start-Sleep -Seconds 5
    Write-Host "Starting Slack Bot...`n"
    docker compose up -d bot
}

Write-Host "`nSetup complete. Use 'docker compose logs -f bot' to see bot logs.`n"