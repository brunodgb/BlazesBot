$ErrorActionPreference = "Stop"
$py = "D:\Versoes do Bot\BlazesBot22 - Copia\.venv\Scripts\python.exe"
$script = "D:\Versoes do Bot\BlazesBot22 - Copia\teste_correlacao_alvo.py"
$outFile = "D:\Versoes do Bot\BlazesBot22 - Copia\admin_output.txt"
$errFile = "D:\Versoes do Bot\BlazesBot22 - Copia\admin_error.txt"
Write-Host "Starting admin process..."
Start-Process -FilePath $py -ArgumentList $script, "--pid", "27220" -WorkingDirectory "D:\Versoes do Bot\BlazesBot22 - Copia" -Verb RunAs -RedirectStandardOutput $outFile -RedirectStandardError $errFile -Wait
Write-Host "Admin process completed"
Get-Content $outFile
Get-Content $errFile
pause