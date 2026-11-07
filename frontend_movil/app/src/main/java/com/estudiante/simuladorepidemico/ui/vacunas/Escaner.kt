package com.estudiante.simuladorepidemico.ui.vacunas

import androidx.camera.compose.CameraXViewfinder
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.SurfaceRequest
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.lifecycle.awaitInstance
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.awaitCancellation
import java.util.concurrent.Executors

// QR y los códigos de barras que traen las cajas de vacunas. Menos formatos, menos lecturas falsas.
val FORMATOS_DE_LOTE = listOf(
    Barcode.FORMAT_QR_CODE,
    Barcode.FORMAT_DATA_MATRIX,
    Barcode.FORMAT_CODE_128,
    Barcode.FORMAT_CODE_39,
    Barcode.FORMAT_EAN_13,
)

// ML Kit con el modelo dentro de la app: lee sin red y sin Google Play.
fun lectorDeLotes(): BarcodeScanner = BarcodeScanning.getClient(
    BarcodeScannerOptions.Builder()
        .setBarcodeFormats(FORMATOS_DE_LOTE.first(), *FORMATOS_DE_LOTE.drop(1).toIntArray())
        .build()
)

// La vista de la cámara trasera; cada código que lee va a `alLeer` (varias veces por segundo: quien
// lo recibe decide si le hace caso). Quien la usa ya tiene el permiso de cámara.
@Composable
fun VistaDeCamara(alLeer: (String) -> Unit, modifier: Modifier = Modifier) {
    val contexto = LocalContext.current
    val ciclo = LocalLifecycleOwner.current
    val leer by rememberUpdatedState(alLeer)
    var superficie by remember { mutableStateOf<SurfaceRequest?>(null) }
    LaunchedEffect(ciclo) {
        val proveedor = ProcessCameraProvider.awaitInstance(contexto)
        val lector = lectorDeLotes()
        val hilo = Executors.newSingleThreadExecutor()
        val vista = Preview.Builder().build().apply { setSurfaceProvider { superficie = it } }
        val analisis = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
        analisis.setAnalyzer(hilo) { cuadro ->
            val imagen = cuadro.image
            if (imagen == null) {
                cuadro.close()
                return@setAnalyzer
            }
            lector.process(InputImage.fromMediaImage(imagen, cuadro.imageInfo.rotationDegrees))
                .addOnSuccessListener { codigos -> codigos.firstNotNullOfOrNull { it.rawValue }?.let { leer(it) } }
                .addOnCompleteListener { cuadro.close() }
        }
        try {
            proveedor.bindToLifecycle(ciclo, CameraSelector.DEFAULT_BACK_CAMERA, vista, analisis)
            awaitCancellation()
        } finally {
            proveedor.unbind(vista, analisis)
            lector.close()
            hilo.shutdown()
        }
    }
    Box(modifier) {
        superficie?.let { CameraXViewfinder(surfaceRequest = it, modifier = Modifier.fillMaxSize()) }
    }
}
