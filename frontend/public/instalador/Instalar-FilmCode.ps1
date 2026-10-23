[CmdletBinding()]
param(
    [switch]$ComprobarSolo,
    [switch]$DiagnosticoJson,
    [ValidateSet('Detectar', 'InstalarOllama', 'InstalarVoiceStudio', 'DescargarGemma')][string]$Operacion,
    [string]$CarpetaTrabajo
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Este asistente necesita Windows de 64 bits. Consulta el README para otros sistemas.'
}
if ($PSVersionTable.PSVersion -lt [version]'5.1' -or $PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Abre Instalar-FilmCode.cmd con Windows PowerShell 5.1 (Desktop).'
}
. (Join-Path $PSScriptRoot 'Operaciones-FilmCode.ps1')

if ($Operacion) {
    # Solo lo llama el proceso GUI despues del consentimiento. No instala al abrir.
    try { Invoke-FilmCodeOperacion $Operacion $CarpetaTrabajo; exit 0 } catch { exit 1 }
}
if ($ComprobarSolo -or $DiagnosticoJson) {
    $datos = Get-FilmCodeDiagnostico
    if ($DiagnosticoJson) { $datos | ConvertTo-Json -Depth 8 } else { $datos }
    exit 0
}
if ($env:OS -ne 'Windows_NT') { throw 'Este asistente necesita Windows. Consulta el README para Linux o macOS.' }
if ([Threading.Thread]::CurrentThread.ApartmentState -ne 'STA') { throw 'Abre Instalar-FilmCode.cmd para iniciar el asistente en modo STA.' }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()

$script:proceso = $null
$script:carpeta = $null
$script:operacionActual = ''
$script:diagnostico = $null
$script:botones = @{}
$script:etiquetas = @{}
$script:rutaScript = $PSCommandPath
$formulario = New-Object Windows.Forms.Form
$formulario.Text = 'FilmCode - Prepara tu equipo'
$formulario.Size = New-Object Drawing.Size(860, 620)
$formulario.MinimumSize = New-Object Drawing.Size(800, 620)
$formulario.StartPosition = 'CenterScreen'
$formulario.Font = New-Object Drawing.Font('Segoe UI', 10)
$formulario.AutoScaleMode = 'Dpi'

$cabecera = New-Object Windows.Forms.Label
$cabecera.Location = New-Object Drawing.Point(24, 20)
$cabecera.Size = New-Object Drawing.Size(790, 78)
$cabecera.Text = 'Instala solo lo que falte, con tu confirmacion. Cada descarga muestra origen y tamano. El asistente no incluye voces ni datos personales y no ejecuta modelos, guiones o renders.'
$formulario.Controls.Add($cabecera)
$y = 112
foreach ($nombre in @('Docker', 'Ollama', 'Gemma', 'VoiceStudio')) {
    $titulo = New-Object Windows.Forms.Label
    $titulo.Location = New-Object Drawing.Point(24, $y)
    $titulo.Size = New-Object Drawing.Size(130, 28)
    $titulo.Text = $(if ($nombre -eq 'Gemma') { 'Gemma 4 12B' } else { $nombre })
    $formulario.Controls.Add($titulo)
    $estado = New-Object Windows.Forms.Label
    $estado.Location = New-Object Drawing.Point(160, $y)
    $estado.Size = New-Object Drawing.Size(430, 58)
    $estado.Text = 'Sin comprobar'
    $formulario.Controls.Add($estado)
    $script:etiquetas[$nombre] = $estado
    $boton = New-Object Windows.Forms.Button
    $boton.Location = New-Object Drawing.Point(610, $y - 3)
    $boton.Size = New-Object Drawing.Size(190, 36)
    $boton.Tag = $nombre
    $boton.Text = $(if ($nombre -eq 'Docker') { 'Instrucciones oficiales' } elseif ($nombre -eq 'Gemma') { 'Descargar Gemma' } else { 'Descargar e instalar' })
    $boton.Enabled = $false
    $boton.Add_Click({ Invoke-FilmCodeAccion ([string]$this.Tag) })
    $formulario.Controls.Add($boton)
    $script:botones[$nombre] = $boton
    $y += 78
}
$nota = New-Object Windows.Forms.Label
$nota.Location = New-Object Drawing.Point(24, 425)
$nota.Size = New-Object Drawing.Size(780, 54)
$nota.Text = 'CosyVoice 3 (~5,4 GB), Whisper y Python 3.10 de VoiceStudio se preparan dentro de VoiceStudio. No se descargan aqui. Si un servicio esta cerrado, abre su aplicacion y vuelve a comprobar.'
$formulario.Controls.Add($nota)
$script:mensaje = New-Object Windows.Forms.Label
$script:mensaje.Location = New-Object Drawing.Point(24, 480)
$script:mensaje.Size = New-Object Drawing.Size(780, 48)
$script:mensaje.Text = 'Preparado para comprobar el equipo.'
$formulario.Controls.Add($script:mensaje)
$script:comprobar = New-Object Windows.Forms.Button
$script:comprobar.Location = New-Object Drawing.Point(24, 535)
$script:comprobar.Size = New-Object Drawing.Size(220, 34)
$script:comprobar.Text = 'Volver a comprobar'
$script:comprobar.Add_Click({ Start-FilmCodeTrabajo 'Detectar' })
$formulario.Controls.Add($script:comprobar)
$script:cancelar = New-Object Windows.Forms.Button
$script:cancelar.Location = New-Object Drawing.Point(265, 535)
$script:cancelar.Size = New-Object Drawing.Size(220, 34)
$script:cancelar.Text = 'Cancelar descarga'
$script:cancelar.Enabled = $false
$script:cancelar.Add_Click({
    if ($script:proceso -and $script:carpeta) {
        try {
            $ruta = Assert-FilmCodeTrabajo $script:carpeta
            [IO.File]::WriteAllText((Join-Path $ruta 'cancelar.flag'), 'cancelar')
            $script:cancelar.Enabled = $false
            $script:mensaje.Text = 'Cancelando descarga. Puede tardar hasta 30 segundos si la conexion no responde...'
        } catch { $script:mensaje.Text = 'No se pudo solicitar la cancelacion. Revisa permisos y espera a que termine.' }
    }
})
$formulario.Controls.Add($script:cancelar)
$cerrar = New-Object Windows.Forms.Button
$cerrar.Location = New-Object Drawing.Point(690, 535)
$cerrar.Size = New-Object Drawing.Size(110, 34)
$cerrar.Text = 'Cerrar'
$cerrar.Add_Click({ $formulario.Close() })
$formulario.Controls.Add($cerrar)

function Set-FilmCodeControles([bool]$Ocupado) {
    $script:comprobar.Enabled = -not $Ocupado
    $script:cancelar.Enabled = $false
    foreach ($boton in $script:botones.Values) { $boton.Enabled = -not $Ocupado }
    if (-not $Ocupado -and $script:diagnostico) {
        $script:botones['Ollama'].Enabled = -not $script:diagnostico.Ollama.Instalada -and -not $script:diagnostico.Ollama.Servicio
        $script:botones['VoiceStudio'].Enabled = -not $script:diagnostico.VoiceStudio.Instalada -and -not $script:diagnostico.VoiceStudio.Servicio
        $script:botones['Gemma'].Enabled = $script:diagnostico.Ollama.Instalada -and $script:diagnostico.Ollama.Servicio -and -not $script:diagnostico.Gemma.Instalada
    }
}

function Show-FilmCodeDiagnostico($Datos) {
    $script:diagnostico = $Datos
    foreach ($nombre in @('Docker', 'Ollama', 'VoiceStudio')) {
        $dato = $Datos.$nombre
        $script:etiquetas[$nombre].Text = $(if ($dato.Servicio) { 'Servicio disponible' } elseif ($dato.Instalada) { 'Instalado; servicio cerrado o no accesible. Abrelo manualmente.' } else { 'No detectado. Puedes instalarlo.' })
    }
    $script:etiquetas['Gemma'].Text = $(if ($Datos.Gemma.Instalada) { 'Ya descargada en Ollama; no se ha cargado.' } elseif (-not $Datos.Gemma.Comprobable) { 'No se puede consultar: primero abre Ollama.' } else { 'Falta gemma4:12b. Descarga aproximada: 8 GB.' })
}

function Start-FilmCodeTrabajo([string]$Accion) {
    if ($script:proceso) { return }
    $script:carpeta = Join-Path ([IO.Path]::GetTempPath()) ('FilmCode-instalador-' + [guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($script:carpeta)
    if ($Accion -ne 'Detectar') {
        # Esta funcion solo se alcanza despues de responder Si al dialogo.
        $consentimiento = @{
            aceptado = $true; operacion = $Accion
            referencia = (Get-FilmCodeReferenciaConsentimiento $Accion)
        } | ConvertTo-Json
        [IO.File]::WriteAllText((Join-Path $script:carpeta 'consentimiento.json'), $consentimiento, (New-Object Text.UTF8Encoding($false)))
    }
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $argumentos = '-NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "' + $script:rutaScript + '" -Operacion ' + $Accion + ' -CarpetaTrabajo "' + $script:carpeta + '"'
    try {
        $script:proceso = Start-Process -FilePath $powershell -ArgumentList $argumentos -WindowStyle Hidden -PassThru
        $script:operacionActual = $Accion
        Set-FilmCodeControles $true
        $script:mensaje.Text = 'Comprobando...' 
    } catch {
        $script:proceso = $null
        $script:mensaje.Text = 'No se pudo iniciar la tarea. Comprueba los permisos de Windows.'
        Set-FilmCodeControles $false
    }
}

function Invoke-FilmCodeAccion([string]$Nombre) {
    if ($script:proceso) { return }
    if ($Nombre -eq 'Docker') {
        $aceptar = [Windows.Forms.MessageBox]::Show($formulario, 'Docker Desktop se instala por separado. Se abrira su pagina oficial; no se descargara ni instalara nada automaticamente. Revisa sus requisitos y licencia. Abrir la pagina?', 'Docker Desktop', 'YesNo', 'Question', 'Button2')
        if ($aceptar -eq 'Yes') { Start-Process 'https://docs.docker.com/desktop/setup/install/windows-install/' }
        return
    }
    if ($Nombre -eq 'Gemma') {
        $texto = "Descargar gemma4:12b mediante Ollama (ollama pull gemma4:12b).`r`nOrigen: biblioteca oficial de Ollama, https://ollama.com/library/gemma4:12b`r`nTamano aproximado: 8 GB; se recomienda al menos 10 GB libres. El tamano puede variar con la revision oficial.`r`nLa descarga se guardara en la carpeta de modelos que tengas configurada en Ollama. No se generara texto ni se cargara el modelo.`r`n`r`nAutorizas esta descarga?"
        $accion = 'DescargarGemma'
    } else {
        $componente = (Get-FilmCodeCatalogo)[$Nombre]
        $tamano = '{0:N2}' -f ($componente.Bytes / 1GB)
        $texto = "Descargar $($componente.Nombre).`r`nOrigen: $($componente.Url)`r`nTamano: $tamano GiB ($($componente.Bytes) bytes).`r`nSe comprobara SHA256 y despues se abrira su instalador interactivo. Tu decides sus opciones y los permisos de Windows. No se aceptaran avisos ni descargas de modelos por ti."
        if ($Nombre -eq 'Ollama') { $texto += "`r`nTambien se exigira una firma Authenticode valida de Ollama." }
        else { $texto += "`r`nVoiceStudio publica este instalador sin firma. Se comprobara el SHA256 fijado del lanzamiento oficial; no se desactivara SmartScreen. Dentro de VoiceStudio revisa y desactiva las analiticas antes de usarlo.`r`nEste EXE no incluye CosyVoice 3 (~5,4 GB), Whisper ni el entorno Python 3.10. Debes autorizar y preparar esas descargas dentro de VoiceStudio; no se iniciaran desde este asistente." }
        $texto += "`r`n`r`nAutorizas descargarlo y abrir su instalador?"
        $accion = $(if ($Nombre -eq 'Ollama') { 'InstalarOllama' } else { 'InstalarVoiceStudio' })
    }
    $decision = [Windows.Forms.MessageBox]::Show($formulario, $texto, 'Confirmar componente', 'YesNo', 'Question', 'Button2')
    if ($decision -eq 'Yes') { Start-FilmCodeTrabajo $accion }
}

$timer = New-Object Windows.Forms.Timer
$timer.Interval = 500
$timer.Add_Tick({
    if (-not $script:proceso) { return }
    $estado = $null
    $rutaEstado = Join-Path $script:carpeta 'estado.json'
    if (Test-Path -LiteralPath $rutaEstado -PathType Leaf) {
        try { $estado = [IO.File]::ReadAllText($rutaEstado) | ConvertFrom-Json } catch { }
    }
    if ($estado) {
        $cancelacion = Test-Path -LiteralPath (Join-Path $script:carpeta 'cancelar.flag') -PathType Leaf
        if (-not $cancelacion -or $estado.estado -in @('instalando', 'cancelado', 'error', 'terminado')) { $script:mensaje.Text = [string]$estado.mensaje }
        $script:cancelar.Enabled = -not $cancelacion -and $estado.estado -in @('descargando', 'verificando')
    }
    if ($script:proceso.HasExited) {
        $codigo = $script:proceso.ExitCode
        $script:proceso.Dispose(); $script:proceso = $null
        if ($estado -and $estado.estado -eq 'terminado' -and $estado.datos) { Show-FilmCodeDiagnostico $estado.datos }
        if ($codigo -ne 0 -and (-not $estado -or $estado.estado -notin @('error', 'cancelado'))) { $script:mensaje.Text = 'La tarea no termino correctamente. Pulsa Volver a comprobar y revisa permisos, conexion y disco.' }
        Set-FilmCodeControles $false
    }
})
$formulario.Add_FormClosing({
    if ($script:proceso -and -not $script:proceso.HasExited) {
        $_.Cancel = $true
        [void][Windows.Forms.MessageBox]::Show($formulario, 'Hay una tarea en curso. Usa Cancelar descarga o, si ya se abrio un instalador, cancela desde su propia ventana. No cierres Docker, Ollama ni VoiceStudio para cancelar este asistente.', 'Tarea en curso', 'OK', 'Information')
    }
})
$formulario.Add_Shown({ $timer.Start(); Start-FilmCodeTrabajo 'Detectar' })
try { [void]$formulario.ShowDialog() } finally { $timer.Stop(); $timer.Dispose(); $formulario.Dispose() }
