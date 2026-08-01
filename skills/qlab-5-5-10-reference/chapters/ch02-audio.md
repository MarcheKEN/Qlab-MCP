# Audio

## Audio cues

Un **Audio cue** necesita un `file target` y un `audio output patch`. El patch conecta el cue al hardware o a una salida de red y define routing y canales. QLab recomienda AIFF, WAV y CAF; MP3 puede introducir un retraso variable al iniciar y no es recomendable cuando el timing exacto importa.

Fuente: [Audio Cues](https://reference.qlab.app/docs/v5/audio/audio-cues/) y [Audio Output Patch Editor](https://reference.qlab.app/docs/v5/audio/audio-output-patch-editor/).

## Mic cues

Un **Mic cue** pasa audio en vivo desde un `audio input patch` a un `audio output patch`, con el mismo sistema de cueing, routing y efectos que Audio cues. Requiere permiso de micrófono de macOS y normalmente corre indefinidamente hasta detenerse o darle duración finita.

Fuente: [Mic Cues](https://reference.qlab.app/docs/v5/audio/mic-cues/).

## Configuración práctica

Para configurar un `Audio Output Patch`, abre `Workspace Settings → Audio → Audio Outputs`, crea el patch, define dispositivo y routing, y selecciónalo en el tab `I/O` del cue. No confundas el patch con el archivo objetivo ni con un `Audio Input Patch`.
