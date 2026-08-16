# Video, Camera, and Text

## Video cues

A **Video cue** plays video or still images with control over timing, opacity, scale, position, 3D rotation, effects, and blending. It needs a `file target` and a `stage`. Still images run indefinitely unless given a finite duration.

Source: [Video Cues](https://reference.qlab.app/docs/v5/video/video-cues/).

Compatibility depends on the codec and container. `mov` and `mp4` are recommended containers; for transparency, ProRes 4444 or Hap Alpha and premultiplied alpha are recommended.

## Camera and Text

Use the official [Camera Cues](https://reference.qlab.app/docs/v5/video/camera-cues/) and [Text Cues](https://reference.qlab.app/docs/v5/video/text-cues/) pages for their tabs, permissions, formats, and properties. Keep their exact terms and do not infer an OSC path from a visual property; route the query to the OSC dictionary.

## Patches and geometry

`Stage`, `Video Output`, `Geometry`, `Levels`, and `Video FX` are separate layers. Verify each property in the inspector or corresponding scripting source before documenting an automation.
