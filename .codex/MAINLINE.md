# Mainline and staged roadmap

## Frozen baseline

- Legacy V3.2 remains the default `run_spatializer.py` engine.
- Feedback-loop records and tuning profiles remain external and reviewable.

## Spatial Core V2 S1

- Public `spatial_core_scene` 2.0 JSON plus external mono/FOA WAV assets.
- Existing DSP buses become static omni objects and an AmbiX ACN/SN3D FOA bed.
- Strict measured-SOFA binaural with delay-aware 3-neighbor interpolation.
- Distance/DRR, fixed early reflections, small/dry late FOA field, SLERP head trajectory, optional seeded micro-motion.
- FOA + 2D VBAP quad backend and existing CTC as a post adapter.
- Opt-in CLI only; no AI separation, moving objects, HOA, non-omni directivity, or bundled HRTF data.

## Spatial Core V2.1 clarity/depth candidate

- Lossless seven-zone M/S intermediate scene with a coherence-derived center anchor.
- Compact validated `spatial_core_profile` 1.0 parameter surface.
- Optional `balanced-depth` 6 x 5 x 3 m first-order image-source room.
- Minimum-phase shared HRTF common-field compensation.
- Static optimization remains the default; real listener tracking stays a later stage.

## Promotion

Do not change the default engine until at least three paired tracks show mean
externalization and depth gains of 0.5 or more, with no important timbre
utility regression greater than 0.5.
