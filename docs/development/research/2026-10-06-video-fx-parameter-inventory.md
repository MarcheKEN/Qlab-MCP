# Documentary inventory of Video FX

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-10-06. Factual data from the [official Parameter Reference](https://qlab.app/docs/v5/scripting/parameter-reference/#video-effects), cross-checked by the researcher against the local PDF `docs/sources/qlab-5.5.10/reference/QLab_5_Reference_Manual.local-snapshot.pdf`, pages 678–687. The folder name does not prove the PDF's exact date/version or a 5.5.10 runtime trial.

**60 effects, 262 `(effect,key)` targets: 229 numbers, 21 enums, 11 vectors of four floats and one boolean.** This is not a catalog obtained from runtime; there were no writes. FalseColor has no scriptable parameters and GaborGradients has no parameters.

Notation: `N[a,b]` finite number and published range; `V` four floats [0,1]; `B` boolean; `E{...}` enum. Comma-grouped keys are independent targets. `PXY` expands to `_protocolInput_X,_protocolInput_Y`, both `N[0,1]`. Ranges are not necessarily hard QLab limits; some can be exceeded. Complete units and defaults are not published: do not infer them from names.

| OSC name | Keys and types/ranges |
|---|---|
| `ColorControls` | inputBrightness:N[-1,1]; inputContrast:N[0.25,4]; inputAngle:N[-180,180]; inputSaturation:N[0,2] |
| `Exposure` | inputEV:N[-10,10] |
| `Gamma` | inputPower:N[-0.1,3] |
| `SepiaMonochrome` | Choose_Effect:E{0:Sepia,1:Monochrome}; inputColor:V; inputIntensity:N[0,1] |
| `MinMaxInvert` | Choose_Effect:E{0:Minimum Component,1:Maximum Component,2:Color Invert} |
| `WhitePoint` | inputColor:V |
| `HighlightShadow` | inputHighlightAmount:N[0,1]; inputShadowAmount:N[-1,1]; inputRadius:N[0,100] |
| `TemperatureTint` | Source_Temperature,Target_Temperature:N[2000,10000]; Source_Tint,Target_Tint:N[-500,500] |
| `Vibrance` | inputAmount:N[-1,1] |
| `ToneCurve` | Point_0_X,Point_0_Y,Point_1_X,Point_1_Y,Point_2_X,Point_2_Y,Point_3_X,Point_3_Y,Point_4_X,Point_4_Y:N[0,1] |
| `ColorClamp` | Min_R,Max_R,Min_G,Max_G,Min_B,Max_B,Min_A,Max_A:N[0,1] |
| `ColorMatrix` | R_R,G_R,B_R,A_R,R_Bias,R_G,G_G,B_G,A_G,G_Bias,R_B,G_B,B_B,A_B,B_Bias,R_A,G_A,B_A,A_A,A_Bias:N[-1,1] |
| `ColorThreshold` | inputThreshold:N[0,1] |
| `SpotColor` | inputCenterColor1,inputReplacementColor1,inputCenterColor2,inputReplacementColor2,inputCenterColor3,inputReplacementColor3:V; inputCloseness1,inputCloseness2,inputCloseness3:N[0,1]; inputContrast1,inputContrast2,inputContrast3:N[0,10] |
| `LinearKey` | inputKeyColor:E{0:Green,1:Blue}; inputCutoff:N[0,4]; inputContrast:N[0,10] |
| `BoxDiscGaussianBlur` | Choose_Blur:E{0:Box Blur,1:Disc Blur,2:Gaussian Blur}; inputRadius:N[0,400] |
| `BokehBlur` | inputRadius:N[0,500]; inputRingAmount:N[0,1]; inputRingSize:N[0,500]; inputSoftness:N[0,10] |
| `MotionBlur` | inputRadius:N[0,400]; inputAngle:N[-360,360] |
| `SharpenLuminance` | inputSharpness:N[0,2] |
| `UnsharpMask` | inputRadius:N[0,100]; inputIntensity:N[0,1] |
| `ZoomBlur` | PXY; inputAmount:N[0,200] |
| `MorphologyGradient` | inputRadius:N[0,100] |
| `MorphologyMinMax` | Choose_Effect:E{0:Morphology Minimum,1:Morphology Maximum}; inputWidth,inputHeight:N[1,101] |
| `DepthOfField` | Point_0_X,Point_0_Y,Point_1_X,Point_1_Y:N[0,1]; inputRadius:N[0,100]; inputSaturation:N[0,5]; inputUnsharpMaskIntensity:N[0,10]; inputUnsharpMaskRadius:N[0,20] |
| `Pixellation` | Choose_Effect:E{0:Pixellate,1:Hexagonal Pixellate}; PXY; inputScale:N[1,100] |
| `Screen` | Choose_Effect:E{0:Dot Screen,1:Line Screen,2:Hatched Screen,3:Circular Screen}; PXY; inputAngle:N[-360,360]; inputWidth:N[2,50]; inputSharpness:N[0,1] |
| `BloomGloom` | Choose_Effect:E{0:Bloom,1:Gloom}; inputRadius:N[0,100]; inputIntensity:N[0,1] |
| `CMYKHalftone` | PXY; inputAngle:N[-360,360]; inputWidth:N[0,100]; inputSharpness,inputGCR,inputUCR:N[0,1] |
| `PhotoEffects` | Choose_Effect:E{0:Chrome,1:Fade,2:Instant,3:Mono,4:Noir,5:Process,6:Tonal,7:Transfer} |
| `ColorPosterize` | inputLevels:N[2,30] |
| `CrystallizePointillize` | Choose_Effect:E{0:Crystallize,1:Pointillize}; PXY; inputRadius:N[0,100] |
| `EdgeWork` | Choose_Effect:E{0:Edge Work,1:Edges}; inputIntensity:N[0,10]; inputRadius:N[0,20] |
| `LineOverlay` | inputContrast:N[0.25,10]; inputEdgeIntensity,inputThreshold,inputNRSharpness:N[0,1]; inputNRNoiseLevel:N[0,4] |
| `Kaleidoscope` | PXY; inputAngle:N[-360,360]; inputCount:N[1,64] |
| `TriangleKaleidoscope` | Point_X,Point_Y:N[0,1]; inputRotation:N[-360,360]; inputSize:N[1,4000]; inputDecay:N[0,1] |
| `Droste` | Point_0_X,Point_0_Y,Point_1_X,Point_1_Y:N[0,1]; inputPeriodicity:N[1,400]; inputStrands:N[0,20]; inputZoom:N[0,5]; inputRotation:N[-360,360] |
| `LightTunnel` | Center_X,Center_Y:N[0,1]; inputRadius:N[1,4000]; inputRotation:N[-360,360] |
| `MedianComicEffect` | Choose_Effect:E{0:Median,1:Comic Effect} |
| `FalseColor` | — |
| `ThermalXRay` | Choose_Effect:E{0:Thermal,1:X-Ray} |
| `GaborGradients` | — |
| `Spotlight` | inputColor:V; inputBrightness:N[0,2]; inputConcentration:N[0,5]; Light_Pos_X,Light_Pos_Y,Light_Pos_Z,Light_Points_X,Light_Points_Y,Light_Points_Z:N[-1,2] |
| `Dither` | inputIntensity:N[0,5] |
| `NoiseReduction` | inputNoiseLevel:N[0,0.1]; inputSharpness:N[0,2] |
| `CircleSplashHoleDistortion` | Choose_Effect:E{0:Circle Splash,1:Hole}; PXY; inputRadius:N[0,1000] |
| `PinchBumpDistortion` | Choose_Effect:E{0:Pinch,1:Bump,2:Bump Linear}; PXY; inputRadius:N[0,1000]; inputAngle:N[-360,360]; inputScale:N[0,2] |
| `TorusLensDistortion` | PXY; inputRadius:N[0,500]; inputWidth:N[0,200]; inputRefraction:N[-5,5] |
| `TwirlVortexDistortion` | Choose_Effect:E{0:Twirl,1:Circular Wrap,2:Vortex}; PXY; inputRadius:N[0,1000]; inputAngle:N[-360,360] |
| `GlassLozenge` | Point_0_X,Point_0_Y,Point_1_X,Point_1_Y:N[0,1]; inputRadius:N[0,1000]; inputRefraction:N[-5,5] |
| `KeystoneCorrection` | Choose_Effect:E{0:Combined,1:Horizontal,2:Vertical}; UL_X,UL_Y,UR_X,UR_Y,LL_X,LL_Y,LR_X,LR_Y:N[0,1]; inputFocalLength:N[0,30] |
| `OpTile` | PXY; inputAngle:N[-360,360]; inputScale:N[0.1,10]; inputWidth:N[0,1000] |
| `PerspectiveTile` | Bottom_Left_X,Bottom_Left_Y,Bottom_Right_X,Bottom_Right_Y,Top_Left_X,Top_Left_Y,Top_Right_X,Top_Right_Y:N[0,1] |
| `QuadTiles` | Choose_Effect:E{0:Fourfold Translated Tile,1:Fourfold Reflected Tile,2:Parallelogram Tile}; PXY; inputAngle,inputAcuteAngle:N[-360,360]; inputWidth:N[1,200] |
| `ReflectedTiles` | Choose_Effect:E{0:Glide Tile,1:Sixfold Reflected Tile,2:Eightfold Reflected Tile,3:Twelvefold Reflected Tile}; PXY; inputAngle:N[-360,360]; inputWidth:N[1,200] |
| `RotatedTiles` | Choose_Effect:E{0:Triangle Tile,1:Fourfold Reflected Tile,2:Sixfold Reflected Tile}; PXY; inputAngle:N[-360,360]; inputWidth:N[1,200] |
| `NinePartStretched` | LL_X,LL_Y,UR_X,UR_Y:N[0,1]; Grow_X,Grow_Y:N[0,1000] |
| `NinePartTiled` | LL_X,LL_Y,UR_X,UR_Y:N[0,1]; Grow_X,Grow_Y:N[0,5000]; inputFlipYTiles:B |
| `Shutter` | Shape:E{0:Rectangle,1:Ellipse}; Left,Right,Bottom,Top:N[0,1]; Feather:N[0,800] |
| `Window` | Origin_X,Origin_Y,Size_W,Size_H:N[0,1]; inputRectangle:V |
| `DropShadow` | Distance,BlurRadius:N[0,400]; Angle:N[-360,360]; Alpha:N[0,1]; inputColor:V |

## Rules before turning the inventory into validators

- Use exact OSC names and keys, not UI labels. Keep enums as published by the source; the Reflected labels inside RotatedTiles must be cross-checked with runtime before correcting them by intuition.
- Window/inputRectangle is a vector of four floats, **not a color**, despite sharing its format. Declare a conflict with its components and check order/semantics, without inferring them from Core Image.
- Numbers are not ints because of their names: `inputCount`/`inputLevels` are published as numeric ranges.
- Choose_Effect/Choose_Blur/Shape change submode: snapshot dependent parameters and verify normalization. Do not assume the rest stays unchanged.
- There is no documented native catalog/default/unit/range metadata. Query instance parameters and cross-check type/key before writing; if the payload does not identify the type, the key alone does not authorize it.
- Do not extrapolate Video/Camera/Text paths to Fade. A documented and tested contract for the target's per-parameter activation flags is missing.
- Video FX requires a Video license; reading the docs does not prove licensing or runtime acceptance of each target.

The catalog matches between the PDF and current web documentation, but the 262 targets were not tested. Relevant preceding changes: QLab5.3 added DropShadow and Shutter feather/ellipse, 5.3.1 fixed grayscale DropShadow and 5.3.2 fixed Shutter on Big Sur. Source: [official Change Log](https://qlab.app/docs/v5/general/change-log/).

Plan and tests: [FX/Text/Group/AppleScript migration research](2026-10-06-cue-edit-migration-fx-text-plan.md).
