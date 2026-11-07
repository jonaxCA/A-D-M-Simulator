La app móvil se entrega en el tercer parcial (D10 de `docs/decisiones.md`) y se construye aquí:
un proyecto de Android Studio en Kotlin con Jetpack Compose. Antes de escribir código, lee
`README.md` de esta carpeta: los paquetes y lo que va en cada uno, cómo conectarla (directorio,
HTTP en desarrollo, cuenta CAPTURISTA y renovación de la sesión) y qué falta del lado del
servidor. Los servicios que va a usar, en JSON, están en `docs/arquitectura/microservicios.md`,
y sus contratos en `docs/contratos/`.

- Un solo módulo `app`. Pantallas con Compose, sin layouts XML. Dependencias armadas a mano en
  `Contenedor`, sin Hilt.
- Toda librería y versión nueva va en `gradle/libs.versions.toml`. Ahí `kotlin` fija la versión
  de Kotlin: AGP 9 compila Kotlin por su cuenta, así que no apliques `kotlin-android` en `app`.
- Tokens y contraseñas nunca en texto plano ni en el código.
- Antes de dar algo por terminado, `./gradlew assembleDebug testDebugUnitTest` pasa.
