param([ValidateSet('Install','Remove','Check')][string]$Action = 'Check')
$ErrorActionPreference = 'Stop'
$labComment = 'Relevance lab domain DNS'
$labDomains = @('.localhost', '.preview.relevance.test')
if ($Action -ne 'Check') {
    $labAdmin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $labAdmin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Open PowerShell as Administrator to install or remove lab DNS rules.'
    }
    $labRules = @(Get-DnsClientNrptRule)
    foreach ($labRule in $labRules) {
        if ($labRule.Comment -ne $labComment -and @($labRule.Namespace | Where-Object { $_ -in $labDomains }).Count) {
            throw 'An existing DNS rule covers a lab domain. Inspect it before continuing.'
        }
    }
    foreach ($labRule in @($labRules | Where-Object { $_.Comment -eq $labComment })) {
        Remove-DnsClientNrptRule -Name $labRule.Name -Force
    }
    if ($Action -eq 'Install') {
        Add-DnsClientNrptRule -Namespace $labDomains -NameServers '127.0.0.1' -Comment $labComment -DisplayName 'Relevance lab DNS'
    }
    Clear-DnsClientCache
}
if ($Action -ne 'Remove') {
    foreach ($labName in @('gitea.localhost','argocd.localhost','control.localhost','signoz.localhost','nexus.localhost','headlamp.localhost','lab-dns-check.preview.relevance.test')) {
        $labAddresses = @([Net.Dns]::GetHostAddresses($labName) | ForEach-Object { $_.IPAddressToString })
        if ($labAddresses.Count -ne 1 -or $labAddresses[0] -ne '127.0.0.1') {
            throw "$labName did not resolve exclusively to 127.0.0.1"
        }
        Write-Output "$labName -> 127.0.0.1"
    }
}
