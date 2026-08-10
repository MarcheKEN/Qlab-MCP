# Video, Camera y Text

## Video cues

Un **Video cue** reproduce vídeo o imágenes fijas con control de timing, opacity, scale, position, 3D rotation, effects y blending. Necesita un `file target` y un `stage`. Las imágenes fijas corren indefinidamente salvo duración finita.

Fuente: [Video Cues](https://reference.qlab.app/docs/v5/video/video-cues/).

La compatibilidad depende del codec y del container. `mov` y `mp4` son containers recomendados; para transparencia se recomiendan ProRes 4444 o Hap Alpha y alpha premultiplicado.

## Camera y Text

Usa las páginas oficiales [Camera Cues](https://reference.qlab.app/docs/v5/video/camera-cues/) y [Text Cues](https://reference.qlab.app/docs/v5/video/text-cues/) para sus tabs, permisos, formatos y propiedades. Mantén sus términos exactos y no deduzcas una ruta OSC desde una propiedad visual: deriva la consulta al diccionario OSC.

## Patches y geometry

`Stage`, `Video Output`, `Geometry`, `Levels` y `Video FX` son capas distintas. Verifica cada propiedad en el inspector o en la fuente de scripting correspondiente antes de documentar una automatización.
