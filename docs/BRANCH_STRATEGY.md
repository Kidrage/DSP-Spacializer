# Branch Strategy

## `main`

`main` is the stable fixed-channel DSP line:

```text
stereo input -> DSP spatial-function layers -> fixed 4.0 renderer -> optional binaural / CTC outputs
```

It should stay clean of pseudo-object scene, object audio, speaker-layout
decoder, DBAP, VBAP, and hybrid renderer code. Documentation on `main` must
match that scope.

## `Pseudo-Object`

`Pseudo-Object` is now an archival branch in this source repository. The active
experimental scene/object/layout-decoder line has been split into:

```text
https://github.com/Kidrage/Pseudo-Object-DSP-Spatializer
```

That standalone repository contains pseudo-object scene metadata, object-layer
audio export, speaker layout descriptors, DBAP/VBAP/hybrid renderers, and
related tests.

Pseudo objects in that branch are DSP-derived spatial-function objects, not
clean stems or source-separated instruments.

## Merge Rule

Do not merge `Pseudo-Object` work into `main` unless the change is deliberately
split and proven to preserve the fixed-channel mainline contract.

New pseudo-object development should happen in
`Kidrage/Pseudo-Object-DSP-Spatializer`, not on this repository's archival
`Pseudo-Object` branch.

If `main` needs cleanup, create a fresh branch from the latest `origin/main`
and remove pseudo-object code there. Avoid merging stale cleanup branches whose
base predates current `main`.
