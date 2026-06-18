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

`Pseudo-Object` is the experimental scene/object/layout-decoder line. It may
contain pseudo-object scene metadata, object-layer audio export, speaker layout
descriptors, DBAP/VBAP/hybrid renderers, and related tests.

Pseudo objects in that branch are DSP-derived spatial-function objects, not
clean stems or source-separated instruments.

## Merge Rule

Do not merge `Pseudo-Object` work into `main` unless the change is deliberately
split and proven to preserve the fixed-channel mainline contract.

If `main` needs cleanup, create a fresh branch from the latest `origin/main`
and remove pseudo-object code there. Avoid merging stale cleanup branches whose
base predates current `main`.
