# Branch Strategy

> 2026-08 update: this repository is now the authoritative unified Spatial
> Core implementation. The Pseudo-Object repository remains reference material
> and is not a runtime dependency. Legacy V3.2 stays frozen/default while
> `spatial_core/` is developed and promoted through reviewable feature PRs.

## `main`

`main` contains the stable fixed-channel line and reviewed opt-in Spatial Core:

```text
legacy: stereo -> DSP layers -> fixed 4.0 -> optional binaural / CTC
V2: stereo/scene -> objects + FOA -> SOFA binaural or FOA/VBAP quad
```

Legacy behavior must remain default/frozen until the V2 listening gate passes.
V2 work belongs in `spatial_core/` behind explicit `--engine spatial-v2`.

## `Pseudo-Object`

`Pseudo-Object` is an archival branch. The standalone repository is retained
as reference material:

```text
https://github.com/Kidrage/Pseudo-Object-DSP-Spatializer
```

It is not a runtime dependency and is no longer the authoritative delivery
location.

## Merge Rule

Do not merge the archival branch wholesale. Port only deliberately reviewed
ideas into the unified `spatial_core/` package, with focused tests and no change
to the default legacy engine.

If `main` needs cleanup, create a fresh branch from the latest `origin/main`
and remove pseudo-object code there. Avoid merging stale cleanup branches whose
base predates current `main`.
