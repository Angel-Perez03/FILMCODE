# Operaciones locales del asistente. Compatible con Windows PowerShell 5.1.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-FilmCodeCatalogo {
    # Versiones y SHA256 auditados del API oficial de GitHub. No se actualizan
    # automaticamente: el consentimiento siempre corresponde a estos bytes.
    return @{
        Ollama = @{
            Nombre = 'Ollama 0.40.8'; Bytes = [long]1658535520
            Url = 'https://github.com/ollama/ollama/releases/download/v0.40.8/OllamaSetup.exe'
            Sha256 = '777f775abb9458ece249f8721db816ac38f7c457767843120ce4fb3d01380b56'
            Archivo = 'OllamaSetup.exe'
        }
        VoiceStudio = @{
            Nombre = 'VoiceStudio 0.5.6'; Bytes = [long]214447484
            Url = 'https://github.com/debpalash/VoiceStudio/releases/download/v0.5.6/VoiceStudio-Electron-0.5.6-win-x64.exe'
            Sha256 = '3d7ac1d6b54e7854ca7fff4dda838e402d1c5d31acc9656b1838432e29a97624'
            Archivo = 'VoiceStudio-Electron-0.5.6-win-x64.exe'
        }
    }
}

function Get-FilmCodeAplicacionRegistrada([string]$Nombre) {
    $raices = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
    )
    foreach ($raiz in $raices) {
        foreach ($item in @(Get-ItemProperty -Path ($raiz + '\*') -ErrorAction SilentlyContinue)) {
            $nombreProp = $item.PSObject.Properties['DisplayName']
            if ($nombreProp -and $nombreProp.Value -match ('^' + [regex]::Escape($Nombre) + '(\s|$)')) {
                $version = $item.PSObject.Properties['DisplayVersion']
                return @{ Instalada = $true; Version = $(if ($version) { [string]$version.Value } else { '' }) }
            }
        }
    }
    return @{ Instalada = $false; Version = '' }
}

function Get-FilmCodeOllamaExe {
    $candidatos = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'),
        (Join-Path $env:ProgramFiles 'Ollama\ollama.exe')
    )
    $comando = Get-Command ollama.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($comando) { $candidatos += $comando.Source }
    foreach ($ruta in $candidatos) {
        if (Test-Path -LiteralPath $ruta -PathType Leaf) { return [IO.Path]::GetFullPath($ruta) }
    }
    return $null
}

function Get-FilmCodeJsonLocal([ValidateSet('Ollama', 'VoiceStudio')][string]$Servicio) {
    $url = $(if ($Servicio -eq 'Ollama') { 'http://127.0.0.1:11434/api/tags' } else { 'http://127.0.0.1:3900/health' })
    $respuesta = $null
    try {
        $peticion = [Net.HttpWebRequest]::Create($url)
        $peticion.Method = 'GET'; $peticion.Proxy = $null
        $peticion.AllowAutoRedirect = $false; $peticion.Timeout = 2200; $peticion.ReadWriteTimeout = 2200
        $respuesta = $peticion.GetResponse()
        if ([int]$respuesta.StatusCode -ne 200) { return @{ Disponible = $false; Datos = $null } }
        $lector = New-Object IO.StreamReader($respuesta.GetResponseStream())
        try {
            # Solo tags y health; nunca perfiles, .env, audios o inferencia.
            $buffer = New-Object char[] 1048577
            $cantidad = $lector.ReadBlock($buffer, 0, $buffer.Length)
            if ($cantidad -gt 1048576) { throw 'Respuesta de estado demasiado grande.' }
            $contenido = -join $buffer[0..([Math]::Max(0, $cantidad - 1))]
            $datos = $null
            if ($cantidad -gt 0) { $datos = ConvertFrom-Json -InputObject $contenido }
            return @{ Disponible = $true; Datos = $datos }
        } finally { $lector.Dispose() }
    } catch { return @{ Disponible = $false; Datos = $null } }
    finally { if ($respuesta) { $respuesta.Dispose() } }
}

function Invoke-FilmCodeLecturaProceso([string]$Ruta, [string]$Argumentos) {
    $inicio = New-Object Diagnostics.ProcessStartInfo
    $inicio.FileName = $Ruta; $inicio.Arguments = $Argumentos
    $inicio.UseShellExecute = $false; $inicio.CreateNoWindow = $true
    $inicio.RedirectStandardOutput = $true; $inicio.RedirectStandardError = $true
    $proceso = New-Object Diagnostics.Process
    $proceso.StartInfo = $inicio
    try {
        [void]$proceso.Start()
        $salida = $proceso.StandardOutput.ReadToEndAsync()
        $errores = $proceso.StandardError.ReadToEndAsync()
        if (-not $proceso.WaitForExit(5500)) { $proceso.Kill(); return $null }
        if ($proceso.ExitCode -ne 0) { return $null }
        return [string]$salida.Result
    } catch { return $null } finally { $proceso.Dispose() }
}

function Get-FilmCodeDiagnostico {
    $ollamaExe = Get-FilmCodeOllamaExe
    $ollamaRegistro = Get-FilmCodeAplicacionRegistrada 'Ollama'
    $vozRegistro = Get-FilmCodeAplicacionRegistrada 'VoiceStudio'
    $vozCandidatos = @(
        (Join-Path $env:ProgramFiles 'VoiceStudio\VoiceStudio.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\VoiceStudio\VoiceStudio.exe')
    )
    $vozInstalada = $vozRegistro.Instalada
    foreach ($ruta in $vozCandidatos) { if (Test-Path -LiteralPath $ruta -PathType Leaf) { $vozInstalada = $true } }
    $ollama = Get-FilmCodeJsonLocal 'Ollama'
    $voz = Get-FilmCodeJsonLocal 'VoiceStudio'
    $gemma = $false
    if ($ollama.Disponible -and $ollama.Datos -and $ollama.Datos.PSObject.Properties['models']) {
        foreach ($modelo in @($ollama.Datos.models)) {
            if ($modelo -and $modelo.PSObject.Properties['name'] -and $modelo.name -eq 'gemma4:12b') { $gemma = $true }
        }
    }
    $docker = Get-Command docker.exe -CommandType Application -ErrorAction SilentlyContinue
    $dockerVersion = $null
    if ($docker) { $dockerVersion = Invoke-FilmCodeLecturaProceso $docker.Source 'info --format "{{.ServerVersion}}"' }
    return [ordered]@{
        Windows = ($env:OS -eq 'Windows_NT')
        Docker = @{ Instalada = [bool]$docker; Servicio = [bool]$dockerVersion }
        Ollama = @{ Instalada = [bool]($ollamaExe -or $ollamaRegistro.Instalada); Servicio = [bool]$ollama.Disponible; Version = $ollamaRegistro.Version }
        Gemma = @{ Instalada = $gemma; Comprobable = [bool]$ollama.Disponible; Modelo = 'gemma4:12b' }
        VoiceStudio = @{ Instalada = [bool]$vozInstalada; Servicio = [bool]$voz.Disponible; Version = $vozRegistro.Version }
        CosyVoiceWhisper = 'Comprueba sus modelos manualmente en VoiceStudio; esta consulta no los inicia.'
        DatosPersonales = 'No se consultaron perfiles, voces, grabaciones ni archivos .env.'
    }
}

function Assert-FilmCodeTrabajo([string]$Carpeta) {
    $ruta = [IO.Path]::GetFullPath($Carpeta).TrimEnd('\')
    $temporal = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($ruta) -ne $temporal -or
        [IO.Path]::GetFileName($ruta) -notmatch '^FilmCode-instalador-[a-f0-9]{32}$') {
        throw 'Carpeta temporal del asistente no valida.'
    }
    $item = Get-Item -LiteralPath $ruta -ErrorAction Stop
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'La carpeta temporal debe ser una carpeta normal.'
    }
    return $ruta
}

function Set-FilmCodeEstado([string]$Carpeta, [string]$Estado, [string]$Mensaje, $Datos = $null) {
    $ruta = Assert-FilmCodeTrabajo $Carpeta
    $json = @{ estado = $Estado; mensaje = $Mensaje; datos = $Datos } | ConvertTo-Json -Depth 8
    $destino = Join-Path $ruta 'estado.json'
    $temporal = Join-Path $ruta 'estado.tmp'
    [IO.File]::WriteAllText($temporal, $json, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $temporal -Destination $destino -Force
}

function Get-FilmCodeReferenciaConsentimiento([string]$Operacion) {
    if ($Operacion -eq 'DescargarGemma') { return 'ollama pull gemma4:12b' }
    $clave = $(if ($Operacion -eq 'InstalarOllama') { 'Ollama' } else { 'VoiceStudio' })
    return (Get-FilmCodeCatalogo)[$clave].Sha256
}

function Assert-FilmCodeConsentimiento([string]$Operacion, [string]$Carpeta) {
    $ruta = Assert-FilmCodeTrabajo $Carpeta
    $archivo = Join-Path $ruta 'consentimiento.json'
    if (-not (Test-Path -LiteralPath $archivo -PathType Leaf)) { throw 'Falta la confirmacion expresa del componente. Abre el asistente y revisa su dialogo.' }
    $dato = [IO.File]::ReadAllText($archivo) | ConvertFrom-Json
    if ($dato.aceptado -ne $true -or $dato.operacion -ne $Operacion -or
        $dato.referencia -ne (Get-FilmCodeReferenciaConsentimiento $Operacion)) {
        throw 'La confirmacion no corresponde al componente solicitado.'
    }
}

function Assert-FilmCodeDescargaUri([uri]$Uri) {
    $permitidos = @('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com')
    if ($Uri.Scheme -ne 'https' -or $Uri.Port -ne 443 -or $Uri.UserInfo -or $Uri.DnsSafeHost -notin $permitidos) {
        throw 'Se bloqueo un origen de descarga que no pertenece a los dominios oficiales permitidos.'
    }
}

function Assert-FilmCodeNoCancelado([string]$Carpeta) {
    $ruta = Assert-FilmCodeTrabajo $Carpeta
    if (Test-Path -LiteralPath (Join-Path $ruta 'cancelar.flag') -PathType Leaf) {
        throw (New-Object OperationCanceledException('Descarga cancelada por el usuario.'))
    }
}

function Throw-FilmCodeErrorSeguro([string]$Mensaje) {
    # Solo mensajes literales del asistente pueden llegar al estado visible.
    # Nunca se persisten WebException crudas con URL firmadas de redireccion.
    $excepcion = New-Object InvalidOperationException($Mensaje)
    $excepcion.Data['FilmCodeMensajeSeguro'] = $true
    throw $excepcion
}

function Test-FilmCodeFirmaOllama($Firma) {
    if ($Firma.Status -ne 'Valid' -or -not $Firma.SignerCertificate) { return $false }
    $nombre = $Firma.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    # Ollama instalado verifica como "Ollama Inc."; se admite tambien la
    # razon social con coma. Coincidencias exactas, nunca solo "contiene Ollama".
    return $nombre -in @('Ollama Inc.', 'Ollama, Inc.')
}

function Receive-FilmCodeInstalador($Componente, [string]$Carpeta) {
    $ruta = Assert-FilmCodeTrabajo $Carpeta
    $destino = Join-Path $ruta $Componente.Archivo
    $uri = [uri]$Componente.Url
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    for ($salto = 0; $salto -lt 6; $salto++) {
        Assert-FilmCodeNoCancelado $ruta
        Assert-FilmCodeDescargaUri $uri
        $respuesta = $null
        try {
            $peticion = [Net.HttpWebRequest]::Create($uri)
            $peticion.Method = 'GET'; $peticion.AllowAutoRedirect = $false
            $peticion.Timeout = 30000; $peticion.ReadWriteTimeout = 30000
            $peticion.UserAgent = 'FilmCode-Instalador/0.2'
            Set-FilmCodeEstado $ruta 'descargando' ('Conectando con el repositorio oficial de ' + $Componente.Nombre + '...')
            $respuesta = $peticion.GetResponse()
            Assert-FilmCodeNoCancelado $ruta
            $codigo = [int]$respuesta.StatusCode
            if ($codigo -in @(301, 302, 303, 307, 308)) {
                $ubicacion = $respuesta.Headers['Location']
                if (-not $ubicacion) { Throw-FilmCodeErrorSeguro 'El servidor oficial devolvio una redireccion sin destino.' }
                $uri = New-Object uri($uri, $ubicacion)
                continue
            }
            if ($codigo -ne 200) { Throw-FilmCodeErrorSeguro 'El servidor oficial no entrego el instalador.' }
            if ($respuesta.ContentLength -ge 0 -and $respuesta.ContentLength -ne $Componente.Bytes) {
                Throw-FilmCodeErrorSeguro 'El tamano publicado cambio. Se bloqueo la descarga hasta revisar el catalogo.'
            }
            Set-FilmCodeEstado $ruta 'descargando' ('Descargando ' + $Componente.Nombre + '...')
            $entrada = $respuesta.GetResponseStream()
            $salida = New-Object IO.FileStream($destino, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try {
                $buffer = New-Object byte[] 131072
                $total = [long]0; $anterior = [DateTime]::UtcNow
                while (($leidos = $entrada.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    Assert-FilmCodeNoCancelado $ruta
                    $total += $leidos
                    if ($total -gt $Componente.Bytes) { Throw-FilmCodeErrorSeguro 'La descarga excede el tamano autorizado y se bloqueo.' }
                    $salida.Write($buffer, 0, $leidos)
                    if (([DateTime]::UtcNow - $anterior).TotalSeconds -ge 1) {
                        $porcentaje = [Math]::Floor(100 * $total / $Componente.Bytes)
                        Set-FilmCodeEstado $ruta 'descargando' ('Descargando ' + $Componente.Nombre + ': ' + $porcentaje + ' %')
                        $anterior = [DateTime]::UtcNow
                    }
                }
                if ($total -ne $Componente.Bytes) { Throw-FilmCodeErrorSeguro 'La descarga esta incompleta. El archivo no se ejecutara.' }
            } finally { $salida.Dispose(); $entrada.Dispose() }
            Assert-FilmCodeNoCancelado $ruta
            Set-FilmCodeEstado $ruta 'verificando' 'Comprobando SHA256 del instalador...'
            $hash = (Get-FileHash -LiteralPath $destino -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($hash -ne $Componente.Sha256) { Throw-FilmCodeErrorSeguro 'SHA256 incorrecto. El archivo no se ejecutara.' }
            Assert-FilmCodeNoCancelado $ruta
            return $destino
        } catch [Net.WebException] {
            Assert-FilmCodeNoCancelado $ruta
            Throw-FilmCodeErrorSeguro 'No se pudo descargar desde el servidor oficial. Comprueba la conexion a internet y vuelve a intentarlo.'
        } catch [IO.IOException] {
            Throw-FilmCodeErrorSeguro 'No se pudo guardar o comprobar el instalador. Comprueba el espacio libre y los permisos de la carpeta temporal.'
        } catch [UnauthorizedAccessException] {
            Throw-FilmCodeErrorSeguro 'Windows no permite guardar el instalador en la carpeta temporal. Comprueba los permisos.'
        } finally { if ($respuesta) { $respuesta.Dispose() } }
    }
    throw 'Demasiadas redirecciones; la descarga se bloqueo.'
}

function Invoke-FilmCodeOperacion([ValidateSet('Detectar', 'InstalarOllama', 'InstalarVoiceStudio', 'DescargarGemma')][string]$Operacion, [string]$Carpeta) {
    $ruta = Assert-FilmCodeTrabajo $Carpeta
    $etapa = 'comprobar'
    try {
        Set-FilmCodeEstado $ruta 'trabajando' 'Comprobando el equipo...'
        if ($Operacion -eq 'Detectar') {
            $datos = Get-FilmCodeDiagnostico
            Set-FilmCodeEstado $ruta 'terminado' 'Comprobacion terminada.' $datos
            return
        }
        $etapa = 'consentimiento'
        Assert-FilmCodeConsentimiento $Operacion $ruta
        Assert-FilmCodeNoCancelado $ruta
        if ($Operacion -eq 'DescargarGemma') {
            $etapa = 'gemma'
            $ollama = Get-FilmCodeJsonLocal 'Ollama'
            $exe = Get-FilmCodeOllamaExe
            if (-not $exe -or -not $ollama.Disponible) { Throw-FilmCodeErrorSeguro 'Abre Ollama manualmente y vuelve a comprobar antes de descargar Gemma.' }
            if ($ollama.Datos -and $ollama.Datos.PSObject.Properties['models']) {
                foreach ($modelo in @($ollama.Datos.models)) {
                    if ($modelo -and $modelo.PSObject.Properties['name'] -and $modelo.name -eq 'gemma4:12b') {
                        $datos = Get-FilmCodeDiagnostico
                        Set-FilmCodeEstado $ruta 'terminado' 'Gemma ya esta descargada en el servicio local. No se ha descargado ni cargado de nuevo.' $datos
                        return
                    }
                }
            }
            Set-FilmCodeEstado $ruta 'descargando' 'Ollama descarga gemma4:12b. Puede tardar; no se carga ni ejecuta el modelo.'
            $inicio = New-Object Diagnostics.ProcessStartInfo
            $inicio.FileName = $exe; $inicio.Arguments = 'pull gemma4:12b'
            $inicio.UseShellExecute = $false; $inicio.CreateNoWindow = $true
            # Consulta y descarga al MISMO servicio local aunque el usuario
            # tenga OLLAMA_HOST apuntando a otro equipo en su entorno.
            $inicio.EnvironmentVariables['OLLAMA_HOST'] = 'http://127.0.0.1:11434'
            $inicio.EnvironmentVariables['NO_PROXY'] = '127.0.0.1,localhost,[::1]'
            $inicio.RedirectStandardOutput = $true; $inicio.RedirectStandardError = $true
            $descarga = New-Object Diagnostics.Process
            $descarga.StartInfo = $inicio
            try {
                Assert-FilmCodeNoCancelado $ruta
                [void]$descarga.Start()
                # Drena ambos canales para evitar bloqueos; no guarda rutas del
                # servicio o trazas crudas ni convierte progreso en errores PS5.
                $salida = $descarga.StandardOutput.ReadToEndAsync()
                $errores = $descarga.StandardError.ReadToEndAsync()
                while (-not $descarga.WaitForExit(400)) {
                    try { Assert-FilmCodeNoCancelado $ruta } catch [OperationCanceledException] {
                        # Solo se cierra este cliente pull; nunca el servicio de
                        # Ollama, otros procesos, los pesos o sus datos parciales.
                        if (-not $descarga.HasExited) { $descarga.Kill(); [void]$descarga.WaitForExit(3000) }
                        throw
                    }
                }
                Assert-FilmCodeNoCancelado $ruta
                if ($descarga.ExitCode -ne 0) { Throw-FilmCodeErrorSeguro 'Ollama no pudo descargar Gemma. Comprueba conexion, disco libre y vuelve a intentarlo.' }
            } finally { $descarga.Dispose() }
            $datos = Get-FilmCodeDiagnostico
            if (-not $datos.Gemma.Instalada) { Throw-FilmCodeErrorSeguro 'Ollama termino la descarga, pero no se pudo confirmar gemma4:12b en el servicio local. Vuelve a comprobar su estado.' }
            Set-FilmCodeEstado $ruta 'terminado' 'Gemma descargada y confirmada localmente. No se ha generado texto, audio ni video.' $datos
            return
        }
        $catalogo = Get-FilmCodeCatalogo
        $clave = $(if ($Operacion -eq 'InstalarOllama') { 'Ollama' } else { 'VoiceStudio' })
        $componente = $catalogo[$clave]
        $etapa = 'descarga'
        $archivo = Receive-FilmCodeInstalador $componente $ruta
        if ($clave -eq 'Ollama') {
            $etapa = 'firma'
            Set-FilmCodeEstado $ruta 'verificando' 'Comprobando la firma de Ollama...'
            $firma = Get-AuthenticodeSignature -LiteralPath $archivo
            if (-not (Test-FilmCodeFirmaOllama $firma)) {
                Throw-FilmCodeErrorSeguro 'La firma de Ollama no es valida o no corresponde a Ollama, Inc. No se ejecutara.'
            }
        }
        Assert-FilmCodeNoCancelado $ruta
        $etapa = 'instalacion'
        Set-FilmCodeEstado $ruta 'instalando' ('Instalador de ' + $componente.Nombre + ' abierto. Para cancelar, usa su boton Cancelar; el asistente no lo cerrara por ti.')
        # El instalador necesita ser visible para revisar sus opciones/UAC.
        # VoiceStudio no esta firmado; solo se abre tras verificar el SHA256 fijo.
        $instalacion = Start-Process -FilePath $archivo -PassThru
        $instalacion.WaitForExit()
        if ($instalacion.ExitCode -ne 0) { Throw-FilmCodeErrorSeguro 'El instalador se cerro sin completar correctamente o se cancelo. Puedes volver a intentarlo.' }
        Set-FilmCodeEstado $ruta 'terminado' 'Instalador cerrado. Pulsa Volver a comprobar para confirmar el resultado. Los modelos de VoiceStudio se preparan dentro de su aplicacion.'
    } catch [OperationCanceledException] {
        Set-FilmCodeEstado $ruta 'cancelado' 'Descarga cancelada. No se borraron modelos ni datos. Ollama puede conservar datos parciales para reintentar.'
    } catch {
        $mensaje = switch ($etapa) {
            'consentimiento' { 'No se pudo validar la confirmacion del componente. Abre el asistente y vuelve a confirmar.' }
            'gemma' { 'No se pudo completar la descarga de Gemma. Comprueba Ollama, la conexion y el espacio libre.' }
            'descarga' { 'No se pudo descargar o verificar el instalador oficial. Comprueba conexion, espacio libre y permisos.' }
            'firma' { 'No se pudo verificar la firma de Ollama, Inc. El instalador no se ejecutara.' }
            'instalacion' { 'Windows no pudo completar el instalador. Revisa su ventana y los avisos de seguridad.' }
            default { 'No se pudo completar la comprobacion. Vuelve a intentarlo.' }
        }
        if ($_.Exception.Data.Contains('FilmCodeMensajeSeguro')) { $mensaje = $_.Exception.Message }
        Set-FilmCodeEstado $ruta 'error' $mensaje
        throw
    }
}
