param([ValidateSet('all','image-converter','video-converter','dot-pattern','view-splitter')][string]$Tool='all',[string]$OutputDirectory,[string]$Python='python')
$ErrorActionPreference='Stop'
$arguments=@((Join-Path $PSScriptRoot 'build.py'),'--tool',$Tool)
if($OutputDirectory){$arguments+=@('--output-dir',$OutputDirectory)}
& $Python @arguments
if($LASTEXITCODE -ne 0){throw 'Small app build failed.'}
