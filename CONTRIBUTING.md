# Contribuyendo a rqtll-ide

¡Gracias por contribuir al frontend de RQTLL!

## Ciclo de Desarrollo y Estructura

1. **Estructura**: La IDE separa la interfaz visual de la lógica del controlador:
   - Modifica las interfaces visuales preferiblemente en el repositorio `rqtll-widgets`.
   - Modifica la lógica del controlador dentro de la carpeta `intern/`.
2. **Atajos e interacciones**: Cualquier cambio en los atajos de teclado globales o configuraciones de la aplicación principal debe manejarse en `main.py`.
3. **Caché y Renderizado**: Al interactuar con la vista de grafo, asegúrate de mantener habilitado el modo de caché de los items (`DeviceCoordinateCache`) para el rendimiento ordinario del paneo/zoom, y deshabilítalo temporalmente sólo al realizar exportaciones SVG vectoriales.
4. **Pull Requests**: Abre un PR detallando el controlador modificado y adjunta una captura de la pantalla afectada si hay cambios en el layout.
