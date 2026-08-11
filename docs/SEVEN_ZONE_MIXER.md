# Seven-zone universal calibration mixer

## Goal

The mixer is a listening-calibration layer for Spatial Core V2.1. It helps one
listener produce one universal configuration, then checks that same immutable
configuration on nine tracks spanning at least six content classes. It does
not create per-song presets and does not automatically replace the repository
default renderer.

The local page deliberately uses listening language first. Algorithm-facing
extraction controls live on a separate Lab page because they change what audio
belongs to each zone and invalidate earlier comparisons.

## Mixing theory

The input is decomposed with a 2048-sample Hann STFT and 512-sample hop. The
construction is complementary: the seven zone signals reconstruct the dry
stereo input with an error below -80 dB. The first four zones become direct
objects; the last three become mirrored AmbiX ACN/SN3D FOA fields.

```text
stereo
  -> lossless M/S zone extraction
  -> 4 direct objects + 3 FOA fields
  -> direct HRTF + distance/DRR + early reflections + late field
  -> measured-SOFA binaural output
```

The renderer treats distance as a compound cue, not a volume control. Object
distance changes geometric attenuation and air absorption; direct ratio changes
the dry/wet energy split; the first-order image-source reflections provide
directional early arrival cues; the late FOA field supplies diffuse room energy.
Together these cues reduce headphone-bound presentation more reliably than an
EQ-only or stereo-width-only treatment.

The `balanced-depth` room is a fixed 6 x 5 x 3 metre calibration geometry. Its
first-order reflection candidates begin after 8 ms. Late energy starts after
the final early reflection plus 10 ms. The default levels are intentionally dry:
early reflections at -21 dB, late field at -27 dB, and RT60 at 0.35 s.

Measured HRTF remains mandatory. A minimum-phase frontal common-field correction
reduces common spectral coloration without replacing interaural cues. HRTF
accuracy can still affect timbre and front/back judgement, so human listening is
authoritative while objective clarity metrics remain visible as advisory risk.

## The seven zones

| Zone | Render type | Default placement | Controls that change the exported mix |
|---|---|---|---|
| Bass | Direct object | 0°, 0°, 1.6 m | Gain, azimuth, elevation, distance, size, diffusion, direct ratio, early/late trim |
| Center anchor | Direct object | 0°, 0°, 1.6 m | Same; this is the first place to protect vocal clarity |
| Front L residual | Direct object | +35°, 0°, 1.6 m | Same; linked to Front R by default in the page |
| Front R residual | Direct object | -35°, 0°, 1.6 m | Same; can be unlinked for intentional asymmetry |
| Side width | FOA field | mirrored ±75° | Field gain, mirrored azimuth, elevation |
| Rear ambience | FOA field | mirrored ±135° | Field gain, mirrored azimuth, elevation |
| High air | FOA field | mirrored ±110°, +35° | Field gain, mirrored azimuth, elevation |

FOA fields intentionally do not expose distance or direct ratio. Those controls
would imply a point source that does not exist. Mute and Solo are audition state:
they are never serialized into the universal profile.

## Practical listening order

1. Leave the Extraction Lab and Monitor page at their defaults.
2. Use a clear vocal excerpt and adjust Center distance in 5 cm steps. Stop when
   the vocal is outside the head but still intelligible.
3. Compare direct ratio and early reflection in small steps. Lower direct ratio
   or stronger early reflection increases externalization but can soften consonants.
4. Adjust Bass distance and gain while checking kick weight and vocal masking.
5. Add Side width, Rear ambience, and High air conservatively. These are sound-bed
   energy controls, not virtual speaker faders.
6. Validate the unchanged draft on all nine excerpts. Record clarity, bass,
   depth, and externalization before promoting it.

The page warns when front left/right angles differ by more than 5° or gains by
more than 1 dB. These are warnings rather than hard stops. Illegal values,
non-finite values, unsafe paths, a reconstruction error of -80 dB or worse, and
profile/schema mismatches fail closed.

## Blind comparison and monitor rules

- `REF` is the source stereo excerpt.
- Versions `1` and `2` conceal which render is the last accepted immutable
  profile and which is the current global draft. The server randomizes and
  records that mapping for each preview.
- All three decoded buffers start from one Web Audio clock event. Switching uses
  a 25 ms gain crossfade without restarting or seeking independent players.
- Preview level matching is monitor-only and enabled by default.
- Monitor output gain, L/R balance, and five-band EQ affect all three versions equally.
- Monitor settings are recorded in promotion evidence but never exported in the
  DSP profile.

Every draft change creates a new SHA-256 profile identity. Comparisons attached
to older hashes remain in the audit trail but are stale for promotion. The
campaign pins nine track IDs, their content classes, and their latest evaluated
excerpt. A comparison is accepted only when its server preview matches the
current track, accepted baseline, draft hash, monitor, and full level-matched
mix. The client cannot supply or replace objective gate results.

Promotion requires the complete pinned nine-track set spanning at least six
categories. Objective red warnings do not block a listener decision, but
promotion then requires a written override reason. The exported evidence retains
the preview ID, excerpt, concealed choice, resolved choice, monitor state, and
server-authored objective result for every track. This written override policy
supersedes the earlier experimental rule that required every objective gate to
pass; red status remains visible and auditable rather than silently ignored.

The transport shows the excerpt waveform. Extraction Lab adds seven-zone Solo,
per-zone RMS, an overlaid 36-band log-frequency spectrum, and the complementary
reconstruction error. Lab Solo is audition-only; calibration evidence requires
Solo and Mute to be cleared.

## Launch

Install the repository dependencies, then run:

```bash
python run_spatial_mixer.py \
  --library-dir /Users/saintpeter/Desktop/Coding/spatializer_outputs/曲库 \
  --sofa /absolute/path/to/measured-listener.sofa
```

Open `http://127.0.0.1:8765`. The server has no public bind option and makes no
external network requests. Campaign state, preview WAV files, immutable profile
revisions, and promotion evidence default to `~/.spatializer/calibration`.

For offline rendering with a promoted profile:

```bash
python run_spatializer.py input.wav \
  --engine spatial-v2 \
  --mixer-profile universal-profile.json \
  --sofa /absolute/path/to/measured-listener.sofa \
  --output-mode binaural
```

`--mixer-profile` and the older compact `--spatial-profile` are mutually
exclusive. The older format remains supported, and
`mixer_profile_from_spatial_core()` provides deterministic conversion into the
new seven-zone schema.

## Current scope

The first release calibrates 48 kHz, static-head, measured-SOFA binaural output.
The quad, VBAP, and CTC paths remain available in the existing command-line
workflow. This page is an offline 10-30 second cached preview tool, not a DAW or
real-time head-tracking interface.
