function Invoke-CheckedNative {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter()]
        [string[]]$ArgumentList = @()
    )

    & $FilePath @ArgumentList
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    if ($exitCode -ne 0) {
        $displayArguments = $ArgumentList -join " "
        throw ("Native command failed with exit code {0}: {1} {2}" -f $exitCode, $FilePath, $displayArguments)
    }
}
