param(
    [string]$SourceBranch,
    [string]$TargetBranch = "ui-ux-branch",
    [string]$CommitMessage = "Integrate Matt_EDA service folders into ui-ux-branch",
    [switch]$Push,
    [switch]$KeepWorktree
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args,
        [string]$WorkingDirectory
    )

    $wd = if ($WorkingDirectory) { $WorkingDirectory } else { (Get-Location).Path }
    Push-Location $wd
    try {
        $oldPref = $ErrorActionPreference
        $hadNativePref = $false
        $oldNativePref = $null
        if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
            $hadNativePref = $true
            $oldNativePref = $PSNativeCommandUseErrorActionPreference
            $PSNativeCommandUseErrorActionPreference = $false
        }

        $ErrorActionPreference = "Continue"
        $output = & git @Args 2>&1 | ForEach-Object { $_.ToString() }
        $code = $LASTEXITCODE

        $ErrorActionPreference = $oldPref
        if ($hadNativePref) {
            $PSNativeCommandUseErrorActionPreference = $oldNativePref
        }

        if ($code -ne 0) {
            throw "git $($Args -join ' ') failed (exit $code):`n$output"
        }
        return $output
    }
    finally {
        Pop-Location
    }
}

function Assert-PathExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathToCheck,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $PathToCheck)) {
        throw "$Description not found: $PathToCheck"
    }
}

function Remove-StaleTargetWorktrees {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$TargetBranch,
        [Parameter(Mandatory = $true)]
        [string]$TempRoot
    )

    $lines = Invoke-Git -Args @("worktree", "list", "--porcelain") -WorkingDirectory $RepoRoot
    $normalizedTempRoot = ($TempRoot -replace '/', '\\').TrimEnd('\\')
    $currentWorktree = $null
    $currentBranch = $null

    foreach ($line in $lines) {
        if ($line -like "worktree *") {
            if ($currentWorktree -and $currentBranch -eq "refs/heads/$TargetBranch") {
                $normalizedCurrent = ($currentWorktree -replace '/', '\\').TrimEnd('\\')
                if ($normalizedCurrent.StartsWith($normalizedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                    Write-Host "Removing stale worktree for '$TargetBranch': $currentWorktree"
                    Invoke-Git -Args @("worktree", "remove", "--force", $currentWorktree) -WorkingDirectory $RepoRoot | Out-Null
                }
            }
            $currentWorktree = $line.Substring(9)
            $currentBranch = $null
        }
        elseif ($line -like "branch *") {
            $currentBranch = $line.Substring(7)
        }
    }

    if ($currentWorktree -and $currentBranch -eq "refs/heads/$TargetBranch") {
        $normalizedCurrent = ($currentWorktree -replace '/', '\\').TrimEnd('\\')
        if ($normalizedCurrent.StartsWith($normalizedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Host "Removing stale worktree for '$TargetBranch': $currentWorktree"
            Invoke-Git -Args @("worktree", "remove", "--force", $currentWorktree) -WorkingDirectory $RepoRoot | Out-Null
        }
    }
}

try {
    $isRepo = Invoke-Git -Args @("rev-parse", "--is-inside-work-tree")
    if (($isRepo | Select-Object -First 1).Trim() -ne "true") {
        throw "Current directory is not a git repository."
    }

    $repoRoot = (Invoke-Git -Args @("rev-parse", "--show-toplevel") | Select-Object -First 1).Trim()
    Write-Host "Repository root: $repoRoot"

    if (-not $SourceBranch) {
        $SourceBranch = (Invoke-Git -Args @("rev-parse", "--abbrev-ref", "HEAD") -WorkingDirectory $repoRoot | Select-Object -First 1).Trim()
    }
    Write-Host "Source branch: $SourceBranch"
    Write-Host "Target branch: $TargetBranch"

    # Ensure source branch exists.
    Invoke-Git -Args @("show-ref", "--verify", "--quiet", "refs/heads/$SourceBranch") -WorkingDirectory $repoRoot | Out-Null

    # Ensure target branch exists locally; if not, try to create from origin.
    $targetExistsLocal = $true
    try {
        Invoke-Git -Args @("show-ref", "--verify", "--quiet", "refs/heads/$TargetBranch") -WorkingDirectory $repoRoot | Out-Null
    }
    catch {
        $targetExistsLocal = $false
    }

    if (-not $targetExistsLocal) {
        Write-Host "Local branch '$TargetBranch' not found. Attempting to create from origin/$TargetBranch..."
        Invoke-Git -Args @("fetch", "origin", $TargetBranch) -WorkingDirectory $repoRoot | Out-Null
        Invoke-Git -Args @("branch", $TargetBranch, "origin/$TargetBranch") -WorkingDirectory $repoRoot | Out-Null
    }

    $serviceFolders = @(
        "GetCostForecast Service",
        "GetVolumeForecast Service",
        "KNN Quote Service Production"
    )

    $baseRelative = Join-Path "ml_pipeline" "Matt_EDA"
    $servicesRelative = Join-Path $baseRelative "services"

    foreach ($folder in $serviceFolders) {
        $sourcePath = Join-Path (Join-Path $repoRoot $servicesRelative) $folder
        Assert-PathExists -PathToCheck $sourcePath -Description "Source service folder"
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $tempRoot = Join-Path $env:TEMP "git-worktrees"
    if (-not (Test-Path -LiteralPath $tempRoot)) {
        New-Item -ItemType Directory -Path $tempRoot | Out-Null
    }

    # If a previous failed run left a temporary worktree on the target branch,
    # remove it so git worktree add can proceed.
    Remove-StaleTargetWorktrees -RepoRoot $repoRoot -TargetBranch $TargetBranch -TempRoot $tempRoot

    $worktreePath = Join-Path $tempRoot ("$TargetBranch-$timestamp")
    Write-Host "Creating temporary worktree at: $worktreePath"
    try {
        Invoke-Git -Args @("worktree", "add", "--checkout", $worktreePath, $TargetBranch) -WorkingDirectory $repoRoot | Out-Null
    }
    catch {
        $msg = if ($_.Exception) { $_.Exception.Message } else { $_.ToString() }
        if ($msg -match "already used by worktree at '([^']+)'") {
            $existingPath = $Matches[1].Trim()
            $normalizedTempRoot = ($tempRoot -replace '/', '\\').TrimEnd('\\')
            $normalizedExisting = ($existingPath -replace '/', '\\').TrimEnd('\\')
            $isTempWorktree = $normalizedExisting.StartsWith($normalizedTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or $normalizedExisting.ToLower().Contains("\git-worktrees\")

            if ($isTempWorktree) {
                Write-Host "Removing existing temp worktree using '$TargetBranch': $existingPath"
                Invoke-Git -Args @("worktree", "remove", "--force", $existingPath) -WorkingDirectory $repoRoot | Out-Null
                Invoke-Git -Args @("worktree", "add", "--checkout", $worktreePath, $TargetBranch) -WorkingDirectory $repoRoot | Out-Null
            }
            else {
                throw "Target branch '$TargetBranch' is already checked out at non-temp path: $existingPath. Remove that worktree manually or pick another target branch."
            }
        }
        else {
            throw
        }
    }

    try {
        foreach ($folder in $serviceFolders) {
            $src = Join-Path (Join-Path $repoRoot $servicesRelative) $folder
            $dst = Join-Path (Join-Path $worktreePath $servicesRelative) $folder

            if (Test-Path -LiteralPath $dst) {
                Remove-Item -LiteralPath $dst -Recurse -Force
            }
            New-Item -ItemType Directory -Path $dst | Out-Null

            Write-Host "Copying '$folder'..."
            $null = & robocopy $src $dst /E /COPY:DAT /R:2 /W:1 /NFL /NDL /NJH /NJS /NP
            $rc = $LASTEXITCODE
            if ($rc -gt 7) {
                throw "robocopy failed for '$folder' with exit code $rc"
            }
        }

        $pathsToAdd = @()
        foreach ($folder in $serviceFolders) {
            $pathsToAdd += (Join-Path $servicesRelative $folder)
        }

        Invoke-Git -Args (@("add", "--") + $pathsToAdd) -WorkingDirectory $worktreePath | Out-Null

        $status = Invoke-Git -Args @("status", "--porcelain") -WorkingDirectory $worktreePath
        if (-not $status) {
            Write-Host "No changes detected in target branch after copy. Nothing to commit."
            return
        }

        Invoke-Git -Args @("commit", "-m", $CommitMessage) -WorkingDirectory $worktreePath | Out-Null
        Write-Host "Committed changes to '$TargetBranch'."

        if ($Push) {
            Invoke-Git -Args @("push", "origin", $TargetBranch) -WorkingDirectory $worktreePath | Out-Null
            Write-Host "Pushed '$TargetBranch' to origin."
        }
        else {
            Write-Host "Push skipped. Re-run with -Push to publish remote changes."
        }
    }
    finally {
        if (-not $KeepWorktree) {
            if (Test-Path -LiteralPath $worktreePath) {
                Write-Host "Removing temporary worktree..."
                Invoke-Git -Args @("worktree", "remove", "--force", $worktreePath) -WorkingDirectory $repoRoot | Out-Null
            }
        }
        else {
            Write-Host "Keeping worktree at: $worktreePath"
        }
    }

    Write-Host "Done."
}
catch {
    $message = if ($_.Exception) { $_.Exception.Message } else { $_.ToString() }
    Write-Error $message
    exit 1
}
