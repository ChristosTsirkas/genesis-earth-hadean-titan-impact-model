# N-body delivery module

This directory adds a genuine gravitational integration path using REBOUND. It
does not rewrite or relabel `delivery_monte_carlo.py`; that root script remains
the historical reduced-order delivery surrogate used in Runs 1-6.

## Runs

```bash
python -m nbody.run_delivery \
  --config nbody/configs/collision_logger_validation.json \
  --output results/manual/nbody/collision_logger_validation

python -m nbody.run_delivery \
  --config nbody/configs/outer_reservoir_demo.json \
  --output results/manual/nbody/outer_reservoir_demo

python -m nbody.run_ensemble \
  --config nbody/configs/post_instability_injection_pilot.json \
  --output results/manual/nbody/post_instability_injection_pilot

python -m nbody.instability_ensemble.validate_campaign \
  --config nbody/instability_ensemble/configs/literature_anchored_campaign.json \
  --output results/manual/nbody/run9_campaign_validation

python -m nbody.run_ensemble \
  --config nbody/instability_ensemble/configs/local_smoke.json \
  --output results/manual/nbody/run9_local_smoke
```

The first configuration inflates Earth's collision radius and is therefore
strictly a pipeline test. The second uses Earth's physical radius, but only the
present planetary architecture over 200 yr. It is an exploratory integration,
not a Nice-model instability or a 4.1-Ga probability estimate.

The third configuration is a deterministic four-seed transport pilot. It
conditions on bodies that have already been released onto high-eccentricity
orbits (`a = 15-30 au`, `q = 0.75-1.75 au`) and uses IAS15, line collision
search, and Earth's physical radius. It tests post-release transport and
multi-run aggregation. It does **not** simulate the release mechanism or
giant-planet instability, and its collision fraction is conditional on the injected
distribution rather than an absolute source-to-Earth probability.

Run 9 adds a five-giant-planet period-ratio chain and a 20-Earth-mass outer disk
anchored to the five-planet experiments of Nesvorny and Morbidelli (2012). The
disk particles have mass and back-react on the planets. The production-candidate
configuration declares eight deterministic seeds and 10 Myr per seed. The
included two-year configuration is only a fast local execution smoke test.

The configuration does not implement the hydrodynamic inside-out gas-disk
rebound torques of Liu, Raymond and Jacobson (2022). Passing campaign validation
checks construction, disk mass and nominal period ratios; it does not prove
resonant-angle libration or that an instability occurred. Submission-grade
delivery still requires execution of the long campaign, resolution/seed
convergence, and high-resolution Earth-Moon encounter refinement.

Primary literature:

- Nesvorny & Morbidelli (2012), *Astronomical Journal* 144, 117,
  https://doi.org/10.1088/0004-6256/144/4/117
- Liu, Raymond & Jacobson (2022), *Nature* 604, 643-646,
  https://doi.org/10.1038/s41586-022-04535-1
