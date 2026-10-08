# 推送前闸门：密钥扫描 + 大件检查 + 禁止路径（D-0052，防 2026-10-08 事故复发）
$ErrorActionPreference = 'Stop'
$fail = 0
$files = git ls-files
$big = @(); $secret = @(); $forbidden = @()
foreach ($f in $files) {
  if (-not (Test-Path -LiteralPath $f)) { continue }
  $i = Get-Item -LiteralPath $f
  if ($i.Length -gt 1MB) { $big += ("{0} ({1:N2} MB)" -f $f, ($i.Length/1MB)) }
  if ($f -match '^evidence/.*/(xml|mid)/' -or $f -match '\.musicxml$' -and $f -match 'G1-synthetic') { $forbidden += $f }
  if ($i.Length -lt 2MB) {
    $c = Get-Content -Raw -LiteralPath $f -ErrorAction SilentlyContinue
    if ($c -match 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY') { $secret += $f }
  }
}
if ($big.Count)      { Write-Host "REJECT: >1MB tracked files:";      $big      | ForEach-Object { Write-Host "  $_" }; $fail = 1 }
if ($forbidden.Count){ Write-Host "REJECT: forbidden intermediate paths:"; $forbidden | ForEach-Object { Write-Host "  $_" }; $fail = 1 }
if ($secret.Count)   { Write-Host "REJECT: secret patterns:";          $secret   | ForEach-Object { Write-Host "  $_" }; $fail = 1 }
if ($fail) { Write-Host "prepush_check: FAILED"; exit 1 }
Write-Host ("prepush_check: OK ({0} tracked files, no >1MB, no forbidden, no secrets)" -f ($files | Measure-Object).Count)
exit 0