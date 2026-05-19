$URL='https://context-aware-document-q-a-bot-rag.onrender.com'
for($i=1;$i -le 20;$i++){
  try{
    $resp=Invoke-WebRequest -Uri $URL -Method Head -TimeoutSec 15 -ErrorAction Stop
    $status=$resp.StatusCode
  } catch {
    if ($_.Exception.Response -ne $null) { $status=$_.Exception.Response.StatusCode.value__ } else { $status='ERR' }
  }
  Write-Output ("Attempt {0}: {1}" -f $i, $status)
  if ($status -eq 200) { Write-Output 'SITE_UP'; exit 0 }
  Start-Sleep -Seconds 30
}
Write-Output 'TIMEOUT_REACHED'
exit 2
