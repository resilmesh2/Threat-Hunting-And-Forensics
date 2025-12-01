# DFIR Report Generator - Web Interface

Interfaz web simple y estética para el sistema de análisis DFIR.

## Características

- ✅ **Carga de archivos**: Sube archivos (JSON, TXT, LOG, CSV, XML) mediante drag & drop o selección
- ✅ **Análisis con un clic**: Botón para ejecutar el análisis completo
- ✅ **Visualización de reportes**: Visualiza los reportes HTML generados directamente en el navegador
- ✅ **Monitoreo en tiempo real**: Muestra el estado del análisis, avisos de timeout y errores
- ✅ **Logs en tiempo real**: Visualiza los mensajes de log durante la ejecución

## Iniciar la aplicación

### Desde el contenedor Docker:

```bash
# Entrar al contenedor
docker exec -it cai-dfir-container bash

# Iniciar el frontend
cd /app/frontend
python app.py
```

### O ejecutar en segundo plano:

```bash
docker exec -d cai-dfir-container bash -c "cd /app/frontend && python app.py"
```

## Acceder a la interfaz

Una vez iniciado, accede a:
- **URL**: http://localhost:5000
- **Desde otra máquina**: http://TU_IP:5000

## Uso

1. **Cargar archivo**: Arrastra un archivo o haz clic en el área de carga
2. **Configurar análisis** (opcional):
   - Título del incidente
   - Prompt personalizado (deja vacío para usar el predeterminado)
3. **Iniciar análisis**: Haz clic en "Iniciar Análisis"
4. **Monitorear progreso**: Observa el estado, avisos y logs en tiempo real
5. **Ver reporte**: Una vez completado, el reporte aparecerá automáticamente

## Avisos de Timeout

El sistema detecta y muestra automáticamente:
- ⚠️ Timeouts durante el análisis
- ⚠️ Límites de contexto/tokens excedidos
- ⚠️ Errores relacionados con el tiempo de procesamiento

Todos los avisos se muestran en la sección de "Estado del Análisis" con iconos y colores distintivos.



