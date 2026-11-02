$ErrorActionPreference = 'Stop'
$portalRoot = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $portalRoot '.env'
if (Test-Path -LiteralPath $envPath) { Write-Host '.env already exists; preserved.'; exit 0 }
function New-PortalSecret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    return [Convert]::ToBase64String($bytes)
}
$sessionKey = New-PortalSecret
$adminPassword = New-PortalSecret
$geminiKey = ''
$generatorEnv = Join-Path $portalRoot 'services/generator/backend/.env'
if (Test-Path -LiteralPath $generatorEnv) {
    foreach ($line in [IO.File]::ReadAllLines($generatorEnv)) {
        if ($line -match '^\s*GEMINI_API_KEY\s*=\s*(.*)$') { $geminiKey = $Matches[1].Trim().Trim('"').Trim("'") }
    }
}
$lines = @('APP_DOMAIN=localhost', "MORNITOR_SESSION_SECRET=$sessionKey", 'MORNITOR_COOKIE_SECURE=false',
    'PORTAL_ADMIN_USERNAME=admin', 'PORTAL_ADMIN_NAME=Portal Administrator', "PORTAL_ADMIN_PASSWORD=$adminPassword",
    "GEMINI_API_KEY=$geminiKey", 'GEMINI_CRITERIA_MODEL=gemini-2.5-flash')
[IO.File]::WriteAllLines($envPath, $lines, (New-Object Text.UTF8Encoding($false)))
Write-Host 'Created local .env with random secrets. The initial login is admin; read PORTAL_ADMIN_PASSWORD locally. No secrets were printed.'
if (!$geminiKey) {Write-Host 'GEMINI_API_KEY is missing. Import/Monitor remain usable; generation requires a real key.'}

