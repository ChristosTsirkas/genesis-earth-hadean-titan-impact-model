# Run-9 instability ensemble

This subpackage contains the literature-anchored five-giant-planet/outer-disk
campaign requested after the Run-8 post-release pilot.

Local validation and smoke execution:

```bash
python -m nbody.instability_ensemble.validate_campaign \
  --config nbody/instability_ensemble/configs/literature_anchored_campaign.json \
  --output results/manual/nbody/run9_campaign_validation

python -m nbody.run_ensemble \
  --config nbody/instability_ensemble/configs/local_smoke.json \
  --output results/manual/nbody/run9_local_smoke
```

The full candidate config declares eight seeds, 1,000 massive disk particles,
20 Earth masses of disk material, and 10 Myr per seed. It is intentionally not
run by the default replay command. Its successful structural validation and the
two-year smoke test are cached under `results_cached/run9_nbody/`; neither is a
measured delivery probability.
