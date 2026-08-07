# Security Policy - rqtll-ide

Si detectas un problema de seguridad, vulnerabilidad o posible fuga de información dentro de `rqtll-ide`, por favor repórtalo siguiendo este procedimiento.

## Reporte responsable

1. Envía un reporte detallado al mantenedor del proyecto:
   - **adnKSharp** <adnksharp@gmail.com>

2. Incluye en tu mensaje:
   - Descripción de la vulnerabilidad y posibles escenarios de ataque.
   - Pasos para reproducirla de forma local.

3. Evita divulgar la vulnerabilidad públicamente hasta contar con un parche oficial.

## Respuesta y Tiempos

- Confirmaremos la recepción del reporte en un plazo de **36 horas**.
- Evaluaremos y publicaremos una versión parcheada en un plazo máximo de **7 días hábiles**.

## Políticas de seguridad específicas para rqtll-ide

- **Credenciales SSH**: Al configurar conexiones SSH en `ssh.py`, la IDE no debe almacenar contraseñas en texto claro de forma persistente. Las contraseñas deben transmitirse de forma cifrada en memoria y delegar la persistencia a claves SSH autorizadas del sistema.
- **Inyecciones en Terminal**: La terminal virtual y el compilador ejecutan comandos del sistema a través de gRPC. La IDE debe validar que los argumentos ingresados por el usuario en cuadros de diálogo de ejecución no contengan caracteres de inyección de comandos shell (`|`, `;`, `&&`, etc.).
- **Procesamiento de Archivos**: Al abrir archivos en el editor de código, la IDE debe limitar el tamaño máximo de los archivos cargados en memoria para evitar bloqueos y desbordamientos por denegación de servicio (DoS).
