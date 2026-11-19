package com.estudiante.simuladorepidemico.ui.tema

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

// Los colores del sistema web (frontend_web/app/static/css/styles.css), para que las dos se
// reconozcan como el mismo sistema. Sin los colores dinámicos de Android, que siguen al fondo de
// pantalla del teléfono.
val MARINO = Color(0xFF091426)
val AZUL = Color(0xFF1B6CE3)
val VERDE = Color(0xFF22C55E)
private val FONDO = Color(0xFFF7F9FB)
private val BORDE = Color(0xFFE6E9EF)
private val TEXTO = Color(0xFF111827)
private val TEXTO_SECUNDARIO = Color(0xFF6B7280)
private val ROJO = Color(0xFFDC2626)

private val CLARO = lightColorScheme(
    primary = AZUL,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDBEAFE),
    onPrimaryContainer = Color(0xFF0F4FB0),
    secondary = TEXTO_SECUNDARIO,
    secondaryContainer = Color(0xFFD1FAE5),
    onSecondaryContainer = Color(0xFF047857),
    tertiary = Color(0xFFB45309),
    tertiaryContainer = Color(0xFFFEF3C7),
    onTertiaryContainer = Color(0xFFB45309),
    background = FONDO,
    onBackground = TEXTO,
    surface = FONDO,
    onSurface = TEXTO,
    surfaceVariant = Color(0xFFEEF2F6),
    onSurfaceVariant = TEXTO_SECUNDARIO,
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color.White,
    surfaceContainer = Color.White,
    surfaceContainerHigh = Color.White,
    surfaceContainerHighest = Color.White,
    outline = Color(0xFFCBD2DC),
    outlineVariant = BORDE,
    error = ROJO,
    errorContainer = Color(0xFFFEE2E2),
    onErrorContainer = ROJO,
)

private val OSCURO = darkColorScheme(
    primary = Color(0xFF6EA8FE),
    onPrimary = MARINO,
    secondaryContainer = Color(0xFF064E3B),
    onSecondaryContainer = Color(0xFFA7F3D0),
    background = MARINO,
    surface = MARINO,
    surfaceVariant = Color(0xFF14213A),
    surfaceContainerLow = Color(0xFF14213A),
    surfaceContainer = Color(0xFF14213A),
    outlineVariant = Color(0xFF26324A),
)

@Composable
fun TemaEpidemia(oscuro: Boolean = isSystemInDarkTheme(), contenido: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (oscuro) OSCURO else CLARO,
        // El radio de las tarjetas y botones de la web (--radius: 10px).
        shapes = Shapes(small = RoundedCornerShape(8.dp), medium = RoundedCornerShape(10.dp), large = RoundedCornerShape(12.dp)),
        content = contenido,
    )
}
