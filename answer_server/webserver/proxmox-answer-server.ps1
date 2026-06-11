param(
    [int]$Port = 8080,
    [string]$RepoRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:NodeMapPath = "vars/pve-node.yml"
$script:FirstbootPath = "scripts/firstboot.sh"
$script:NodeNamePattern = "^[A-Za-z0-9_-]+$"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
}

function Normalize-Mac {
    param([object]$Mac)

    if ($Mac -is [string]) {
        return $Mac.ToLowerInvariant().Replace("-", ":")
    }

    return ""
}

function Get-ContentBytes {
    param([string]$RelativePath)

    $fullPath = Join-Path $RepoRoot $RelativePath
    return [System.IO.File]::ReadAllBytes($fullPath)
}

function Get-ContentText {
    param([string]$RelativePath)

    $content = Get-ContentBytes -RelativePath $RelativePath
    if ($content -is [byte[]]) {
        return [System.Text.Encoding]::UTF8.GetString($content)
    }

    return [string]$content
}

function ConvertTo-ResponseBytes {
    param([object]$Content)

    if ($Content -is [byte[]]) {
        return $Content
    }

    return [System.Text.Encoding]::UTF8.GetBytes([string]$Content)
}

function Parse-NodeMap {
    param([string]$Text)

    $nodes = @{}
    $currentNode = $null

    foreach ($rawLine in ($Text -split "`r?`n")) {
        $line = ($rawLine -replace "#.*$", "").Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line -eq "nodes:") {
            continue
        }

        $nodeMatch = [regex]::Match($line, "^([A-Za-z0-9_-]+):$")
        if ($nodeMatch.Success) {
            $currentNode = $nodeMatch.Groups[1].Value
            continue
        }

        $macMatch = [regex]::Match($line, "^mac_address:\s*[""']?([^""']+)[""']?$")
        if ($macMatch.Success -and $currentNode) {
            $mac = Normalize-Mac $macMatch.Groups[1].Value.Trim()
            if ($mac) {
                $nodes[$mac] = $currentNode
            }
        }
    }

    return $nodes
}

function Select-NodeFromPost {
    param([byte[]]$Body)

    try {
        $jsonText = [System.Text.Encoding]::UTF8.GetString($Body)
        $systemInfo = $jsonText | ConvertFrom-Json
    }
    catch {
        return $null
    }

    if (-not $systemInfo.network_interfaces) {
        return $null
    }

    $nodeMap = Parse-NodeMap (Get-ContentText -RelativePath $script:NodeMapPath)
    foreach ($interface in $systemInfo.network_interfaces) {
        $mac = Normalize-Mac $interface.mac
        if ($mac -and $nodeMap.ContainsKey($mac)) {
            return $nodeMap[$mac]
        }
    }

    return $null
}

function Send-TextResponse {
    param(
        [System.Net.HttpListenerResponse]$Response,
        [int]$StatusCode,
        [string]$Message
    )

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Message)
    $Response.StatusCode = $StatusCode
    $Response.ContentType = "text/plain; charset=utf-8"
    $Response.ContentLength64 = $bytes.Length
    $Response.OutputStream.Write($bytes, 0, $bytes.Length)
}

function Send-FileResponse {
    param(
        [System.Net.HttpListenerResponse]$Response,
        [string]$RelativePath
    )

    $bytes = ConvertTo-ResponseBytes (Get-ContentBytes -RelativePath $RelativePath)
    $Response.StatusCode = 200
    $Response.ContentType = "text/plain; charset=utf-8"
    $Response.Headers["Cache-Control"] = "no-store"
    $Response.ContentLength64 = $bytes.Length
    $Response.OutputStream.Write($bytes, 0, $bytes.Length)
}

function Get-RequestBody {
    param([System.Net.HttpListenerRequest]$Request)

    $stream = New-Object System.IO.MemoryStream
    $Request.InputStream.CopyTo($stream)
    return $stream.ToArray()
}

function Handle-Request {
    param([System.Net.HttpListenerContext]$Context)

    $request = $Context.Request
    $response = $Context.Response
    $path = $request.Url.AbsolutePath.TrimEnd("/")
    if ([string]::IsNullOrWhiteSpace($path)) {
        $path = "/answer"
    }

    try {
        if ($path -eq "/nodes") {
            Send-FileResponse -Response $response -RelativePath $script:NodeMapPath
            return
        }

        if ($path -eq "/firstboot" -or $path -eq "/firstboot.sh") {
            Send-FileResponse -Response $response -RelativePath $script:FirstbootPath
            return
        }

        if ($path -ne "/answer") {
            Send-TextResponse -Response $response -StatusCode 404 -Message "Endpoint not found. Available: /nodes, /answer, /firstboot`n"
            return
        }

        if ($request.HttpMethod -eq "GET") {
            $nodeName = $request.QueryString["node"]
            if ([string]::IsNullOrWhiteSpace($nodeName) -or $nodeName -notmatch $script:NodeNamePattern) {
                Send-TextResponse -Response $response -StatusCode 400 -Message "Use /answer?node=pve-temp for GET testing`n"
                return
            }
        }
        elseif ($request.HttpMethod -eq "POST") {
            $nodeName = Select-NodeFromPost -Body (Get-RequestBody -Request $request)
            if ([string]::IsNullOrWhiteSpace($nodeName)) {
                Send-TextResponse -Response $response -StatusCode 404 -Message "No answer file configured for this machine`n"
                return
            }
        }
        else {
            Send-TextResponse -Response $response -StatusCode 405 -Message "GET or POST required`n"
            return
        }

        Send-FileResponse -Response $response -RelativePath "vars/$nodeName.toml"
    }
    catch {
        Send-TextResponse -Response $response -StatusCode 502 -Message "Answer server error: $($_.Exception.Message)`n"
    }
    finally {
        $response.OutputStream.Close()
    }
}

$prefix = "http://+:$Port/"
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($prefix)

try {
    $listener.Start()
    Write-Host "Windows Proxmox Answer Webserver Started"
    Write-Host "Listening on: $prefix"
    Write-Host "Serving local repo: $RepoRoot"
    Write-Host ""
    Write-Host "Endpoints:"
    Write-Host "  GET  /nodes                -> Serves vars/pve-node.yml"
    Write-Host "  POST /answer               -> Selects vars/<node>.toml by MAC address"
    Write-Host "  GET  /answer?node=pve-temp -> Serves one answer file for testing"
    Write-Host "  GET  /firstboot            -> Serves scripts/firstboot.sh"
    Write-Host ""

    while ($listener.IsListening) {
        Handle-Request -Context $listener.GetContext()
    }
}
finally {
    $listener.Stop()
    $listener.Close()
}
