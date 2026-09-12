# GENESIS — A Hadean Earth Titan-Mass Impact Model

**Companion computational framework for:**

**GENESIS: A Hadean Earth Titan-Mass Impact Model — A Quantitative Hypothesis
for Earth’s Volatile Budget, Atmospheric Reset, and Post-Impact Prebiotic
Chemistry**

*Theoretical Astrophysics and Planetary Science Working Paper — Expanded Revision*

This repository contains the local research software, frozen configurations,
tests, and verified reference outputs accompanying the working paper. It tests
the internal feasibility of a proposed ~4.1-Ga Titan-mass grazing impact through
a linked sequence of reduced-order delivery, impact-partition, atmospheric,
isotope, and prebiotic-chemistry calculations.

## What the software does

- `delivery_monte_carlo.py` samples possible late outer-system delivery
  trajectories and encounter conditions.
- `impact_scaling_laws.py` applies the 60°–75° grazing-impact window and computes
  an explicit analytical volatile-partition closure.
- `atmosphere_evolution.py` evolves the post-impact thermal state, hydrogen
  escape, nitrogen and 36Ar drag, and D/H fractionation.
- `quench_chemistry_network.py` follows the cooling atmosphere through redox,
  CN/HCN, and reduced-sulfur chemistry.
- `nbody/` contains REBOUND validation and exploratory transport integrations;
  it does not establish an absolute impact probability.
- `sph/` prepares and validates a 96-case SWIFT impact campaign and analyzes
  returned snapshots; it does not contain completed high-resolution impacts.

The package can replay every calculation in Appendix D of the accompanying paper
from frozen inputs, compare fresh outputs with the distributed reference tree,
and report numerical mismatches automatically. It is a reproducible specification
and screening engine, not observational proof of the proposed event and not a
replacement for full 3-D hydrodynamic simulation.

## AI-assisted development

This interdisciplinary research project and its accompanying code were developed
with substantial assistance from generative AI under the direction and
responsibility of the named human author. AI assisted with literature mapping,
mathematical and computational development, numerical analysis, documentation,
and manuscript revision. It is not presented as an author, an independent
scientific authority, a source of empirical evidence, or a substitute for
specialist validation. The named human author selected and revised the final
model assumptions, code, interpretations, and manuscript and retains
responsibility for the published work. The complete project statement is in
[`AI_DISCLOSURE.md`](AI_DISCLOSURE.md).

## Theatrical and Musical Materials

The dramatic and musical components of **GENESIS** have been developed as a single theatrical work rather than as independent illustrations of the scientific paper. The complete 544-verse bilingual libretto, together with the symphonic-theatrical score, follows the formal architecture of Greek tragedy and develops the project’s central themes through dramatic dialogue, choral writing, orchestral structure and separate Ancient Greek and English vocal settings.

Supporting musical materials — including the **Conductor Performance Score, Composer Dossier, Ancient Greek and English Vocal Performance Scores, editable vocal scores and related performance material** — may be accessed here:

https://github.com/ChristosTsirkas/genesis-earth-hadean-titan-impact-model/tree/main/music

The **complete theatrical libretto**, together with the scientific paper and associated documentation, is available here:

https://github.com/ChristosTsirkas/genesis-earth-hadean-titan-impact-model/tree/main/docs

A computer-generated preview of the musical score can be accessed at my SoundCloud profile:
https://soundcloud.com/chris-t-331652374/genesis

## Verification status

The complete D.1–D.10 replay passed: all 558 generated files matched the cached
reference tree with zero differences. The total comprises the original 543
Appendix D artifacts and 15 Run-9 artifacts stored within D.10. All 7 N-body
tests and both SPH local-preparation tests passed.

## Pipeline

```text
reproduce_appendix_d.py
  ├─ Core physical pipeline
  │    delivery_monte_carlo.py
  │      → impact_scaling_laws.py
  │      → atmosphere_evolution.py
  │      → quench_chemistry_network.py
  └─ Frozen-baseline validation branch
       run6_robustness_validation.py
         → run6_chemistry_propagation.py
       nbody/instability_ensemble/validate_campaign.py
         → nbody/run_ensemble.py
         → D.10 Run-9 validation and local smoke outputs
```

`impact_scaling_laws.py` is the second physical stage. The two `run6_*` files
do not add new stages to the impact scenario: they perturb the frozen baseline,
test failure structure, and propagate the tested atmospheric trajectories
through the chemistry calculation.

Two isolated extension modules sit beside that local pipeline:

- `nbody/`: genuine REBOUND gravitational integrations, configs, tests and
  archived validation/exploratory outputs;
- `sph/`: SWIFT planetary-SPH run-matrix generation, HDF5 structural validation
  and transparent first-pass snapshot diagnostics.

Neither module silently promotes its outputs beyond the `evidence_class`
declared in its configuration or result summary.

### Stage 1 — Delivery
`delivery_monte_carlo.py` samples 10,000 outer-system trajectories using a
vectorized migration/scattering surrogate, vis-viva encounter speeds,
gravitational focusing, orbital phase, and a late-release timing weight. Its
`importance_weight` is a **surrogate likelihood**, not an absolute Nice-model
collision probability. A submission-grade dynamical prior still requires a
dedicated N-body ensemble.

### Stage 2 — Analytical grazing-impact partition
`impact_scaling_laws.py` deliberately bypasses high-resolution SPH. It enforces
the paper's Moon-survival search window of **60°–75°** and computes mutual escape
speed plus an analytical ground-velocity/loss kernel based on the
Schlichting/Yalinewich scaling framework. Surface-condition dependence follows
the Lock–Stewart result that impact loss changes strongly with ground velocity
and the atmosphere/ocean mass ratio.

The output water partition is:

```text
eta_vector = [
  eta_escape,
  eta_vapor_plume,
  eta_mantle_dissolution,
  eta_surface_retained,
  eta_reaccretion
]
```

and is normalized to unity.

**Scientific boundary:** no published analytical scaling law uniquely predicts
all five of those reservoirs for this Titan-mass grazing case. The five-way
partition is therefore an explicit paper-level closure that future SPH must calibrate,
not an invented "exact Stewart–Lock equation".

### Stages 3 & 4 — CPU 1-D atmosphere
`atmosphere_evolution.py` is intentionally one-dimensional and CPU-native. It
uses a simple time loop, a Simpson–Nakajima-like OLR ceiling near 280 W m^-2,
a pressure/temperature cold-trap closure, canonical Hunten crossover mass,
species-specific N and 36Ar drag, and D/H mixing + Rayleigh fractionation.

The canonical crossover form implemented is:

```text
m_c = m_1 + k_B T F_1 / (b_12 g X_1)
```

This is important: stronger hydrogen flux raises the crossover mass.

### Stage 5 — Redox and prebiotic quench
`quench_chemistry_network.py` post-processes the atmospheric thermal path using a
stiff ODE solver. It separates:

- H2 from `2 NH3 -> N2 + 3 H2`,
- H2 from `Fe + H2O -> FeO + H2`,
- CO from `Fe + CO2 -> FeO + CO`,
- CN/HCN production,
- reduced sulfur availability.

The paper's ~97-bar H2 value is retained as a **reference normalization for the
NH3-rich case**, not forced as a universal Fe-redox outcome.

## Installation

### Linux or macOS — Bash/Zsh

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows — PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The validated release environment uses Python 3.12.13, NumPy 2.3.5,
SciPy 1.17.0, Pandas 2.2.3, Matplotlib 3.10.8, h5py 3.16.0, and
REBOUND 5.1.1. Numerical comparisons use explicit tolerances so harmless
final-digit differences do not become false failures on another supported
platform.

Typical desktop runtime is controlled by:

- 10,000 vectorized Stage-1 objects,
- 4,096-point Stage-2 surface quadrature per accepted trajectory,
- ~2,000 Stage-3/4 time steps,
- a 1-D stiff Stage-5 ODE system.

No GPU is required for the local analytical pipeline or Appendix D replay.

## Computational methodology and configuration control

The paper has one computational methodology, defined by the frozen parameters in
`configs/appendix_d_replay.json`. The replay driver reads that configuration,
sets the deterministic seeds, runs the required kernels in dependency order,
places every output in the canonical Appendix D tree, compares the generated
metrics with `configs/appendix_d_expected_metrics.json`, and writes a
machine-readable PASS/FAIL report.

The four principal Python files are independently executable computational
kernels as well as components of the controlled replay workflow. Running one
directly is meaningful for inspecting a single model stage, debugging its
numerical behavior, regenerating a local diagnostic output, or studying how
that stage transforms its available inputs. It does not, by itself, reproduce
the complete paper, because it does not guarantee regeneration of every
upstream dependency, application of the complete frozen configuration, or
final baseline validation.

Alternative parameter studies are supported but are methodologically separate
from the paper baseline. The procedure, output-isolation requirements, and
scientific meaning of such runs are documented under “Creating controlled
custom configurations” below.

## Running individual computational kernels

The principal kernels may be executed directly, in pipeline order:

```bash
python delivery_monte_carlo.py
python impact_scaling_laws.py
python atmosphere_evolution.py
python quench_chemistry_network.py
```

Each command has a specific stage-level meaning:

- `delivery_monte_carlo.py` runs the delivery surrogate and generates candidate
  encounter trajectories and conditions.
- `impact_scaling_laws.py` applies the grazing-impact filter and analytical
  volatile-partition model to the available Stage-1 inputs.
- `atmosphere_evolution.py` evolves the configured post-impact thermal,
  atmospheric-escape, nitrogen, argon, and D/H cases.
- `quench_chemistry_network.py` post-processes the available atmospheric thermal
  trajectories through the redox and prebiotic-chemistry network.

These direct commands are useful for code inspection, debugging, intermediate
output analysis, and development of an individual model component. Because later
stages depend on earlier outputs, they should normally be run in the order shown
when used outside the replay driver.

Direct kernel execution is not equivalent to Appendix D reproduction. It does
not automatically guarantee that all upstream inputs were regenerated, that the
complete frozen configuration was applied, or that the final outputs were
checked against the paper baseline. Results from direct execution must therefore
be identified as stage-level diagnostic or development results unless they are
subsequently reproduced and validated through the replay driver.

Custom scientific configurations must use the replay driver's `--config` and
`--results` options shown below. The README does not assume undocumented
per-kernel configuration flags. This preserves the complete dependency chain,
isolates experimental outputs, and prevents them from being confused with the
frozen paper baseline.

### Conditions used by direct execution of the individual computational kernels

Direct execution uses each kernel’s own default execution path rather than the
complete orchestration defined in `configs/appendix_d_replay.json`.

Under the distributed defaults:

- `delivery_monte_carlo.py` runs the 10,000-trajectory local delivery surrogate.
- `impact_scaling_laws.py` processes the available Stage-1 trajectories within
  the 60°–75° grazing window, using 4,096-point surface quadrature per accepted
  trajectory.
- `atmosphere_evolution.py` processes the available atmospheric cases through
  approximately 2,000 thermal and escape time steps.
- `quench_chemistry_network.py` applies the one-dimensional stiff chemistry
  system to the available atmospheric thermal trajectories.

These are default stage-level calculations. They allow a user to inspect each
kernel, its intermediate outputs, and its numerical behavior independently.
They are scientifically meaningful as component tests and diagnostic runs, but
they are not the frozen Appendix D calculation because the complete paper
configuration, deterministic orchestration, expected-metric comparison, and
final replay report are applied only by `reproduce_appendix_d.py`.

### Creating controlled custom configurations for the individual computational kernels

Custom conditions should not be created by editing the Python kernels. Copy the
authoritative configuration and edit the copy.

On Windows PowerShell:

```powershell
Copy-Item configs\appendix_d_replay.json configs\my_experiment.json
```

On Linux or macOS:

```bash
cp configs/appendix_d_replay.json configs/my_experiment.json
```

To run the complete pipeline with the modified configuration:

```bash
python reproduce_appendix_d.py --all \
  --config configs/my_experiment.json \
  --results results/experiments/my_experiment
```

To run only one controlled section with the modified configuration:

```bash
python reproduce_appendix_d.py --section D2 \
  --config configs/my_experiment.json \
  --results results/experiments/my_experiment
```

The principal section mappings are:

- `D1` — delivery calculation;
- `D2` — impact partition;
- `D3` and `D4` — thermal evolution, atmospheric escape, and isotopes;
- `D5` — quench chemistry.

A custom run preserves the software’s dependency handling while changing the
scientific conditions. Its results are meaningful as sensitivity analyses,
alternative parameter studies, or tests of the model’s behavior outside the
frozen baseline. They must be stored outside `results_cached/` and must be
reported as new experiments, not as reproductions of the paper’s published
results.

## Paper's Appendix D replay

This package is self-contained for every local calculation reported in Appendix
D of the accompanying paper. No earlier code archive is required. The numerical
kernels, frozen JSON configuration, deterministic seeds, generated CSV files,
and validation report are distributed together.

The verified reference tree is distributed under `results_cached/`. Fresh user
runs are written only to `results/`, which is empty in the distributed ZIP, so
a replay cannot overwrite the bundled evidence.

From the repository root:

```bash
python reproduce_appendix_d.py --all --clean
```

The command regenerates all 558 files under `results/appendix_d/`. This includes
the Run-9 campaign validation and local smoke outputs under
`results/appendix_d/d10_calibration_extensions/run9_nbody/`. It compares all
generated summaries with `configs/appendix_d_expected_metrics.json`, writes
`results/appendix_d/replay_report.json` and
`results/appendix_d/replay_report.md`, and exits non-zero on a mismatch.

To compare the complete fresh tree with the bundled reference tree:

```bash
python compare_cached_results.py
```

This compares the complete 558-file `results/appendix_d/` tree with
`results_cached/appendix_d/`, writes `results/comparison_report.json`, and exits
non-zero if files are missing, unexpected, or different. Preserve or rename an
earlier `results/` directory before running `--clean` again if you want to keep
that replay.

## Replay by paper section

The cached reference outputs inside ``results_cached`` were produced on Linux. Native Windows runs
generate the complete Appendix D tree, but platform-dependent path separators,
line endings, and REBOUND output ordering or final-digit differences can prevent
literal byte identity. Use Linux or WSL2 for exact cached-reference verification.

Each command automatically regenerates any upstream input required by the
requested section and writes only beneath `results/appendix_d/`. Running
`--section D10` also regenerates the Run-9 campaign validation and local smoke
outputs because they are part of the controlled D.10 replay and its frozen
metrics.

```bash
python reproduce_appendix_d.py --section D1 --clean
python reproduce_appendix_d.py --section D2 --clean
python reproduce_appendix_d.py --section D3 --clean
python reproduce_appendix_d.py --section D4 --clean
python reproduce_appendix_d.py --section D5 --clean
python reproduce_appendix_d.py --section D6 --clean
python reproduce_appendix_d.py --section D7 --clean
python reproduce_appendix_d.py --section D8 --clean
python reproduce_appendix_d.py --section D9 --clean
python reproduce_appendix_d.py --section D10 --clean
```

Every section command uses the authoritative parameters in
`configs/appendix_d_replay.json`; section replay is not an alternative
configuration or methodology.

## Results layout

```text
results/appendix_d/
  d01_stage1_delivery/
  d02_stage2_partition/
  d03_thermal_diagnostic/
  d04_escape_isotopes/
  d05_chemistry_diagnostic/
  d06_integrated_interpretation/
  d07_calibration_run2/
  d08_reproducibility_run3/
  d09_calibration_run4/
  d10_calibration_extensions/
    run9_nbody/
      campaign_validation/
      local_smoke/
  replay_metrics.json
  replay_report.json
  replay_report.md
```

The identically structured paper baseline is under
`results_cached/appendix_d/`. Never use `results_cached/` as an output
destination.

Each numbered directory contains a machine-readable `summary.json` and
`summary.csv`. Raw trajectory, partition, atmosphere, chemistry, N-body, and
SPH-matrix CSV files are retained below the corresponding numbered directory.
No separate `outputs/` tree is used.

## Frozen reference baseline

The authoritative reduced-order baseline is the complete D.1–D.10 state produced
by `python reproduce_appendix_d.py --all --clean` from
`configs/appendix_d_replay.json`. Its principal verified outputs are:

- all eight representative atmosphere cases cool below 1500 K at approximately
  50.55 kyr;
- the reference nitrogen residual is approximately `1.83935e-3`, corresponding
  to approximately `4.322e18 kg`;
- final D/H is `0.94247–0.94630` SMOW across the preserved cases;
- the nominal `x_NH3 = 0.025` case produces approximately `97.74 bar` H2
  equivalent;
- the calibrated 36Ar protected fraction is `0.9805247566`, leaving
  `0.0194752434` exposed and producing approximately 12% 36Ar retention;
- HCN is non-zero in all 16 chemistry-grid cases.

The frozen package also contains non-recalibrating one-at-a-time perturbations,
explicit ablations, and chemistry propagation across the tested thermal cases.
These diagnose sensitivity and failure structure; they do not create a second
baseline.

Directory names containing `run2`, `run3`, `run4`, `run5`, or `run6` preserve
the historical calibration and validation sequence documented in Appendix D.
They are provenance labels inside the frozen replay tree, not software versions,
alternative methodologies, or execution modes that the user must select. The
paper baseline is the complete, frozen configuration and is reproduced as one
controlled workflow.

## Evidential boundary

Replay verifies that the distributed code produces the reported reduced-order,
pipeline-validation, and exploratory values. It does not convert those values
into observational proof of a 4.1-Ga event, an absolute delivery probability,
or a completed SPH calculation. The local results do not replace dedicated
N-body production ensembles, high-resolution SPH, radiative-convective
modeling, hydrodynamic escape calculations, laboratory chemistry, or
independent specialist validation.

## N-body extension

The first three commands below run named N-body validation or exploratory
configurations outside the frozen baseline. The final two commands are the
individual Run-9 components that the replay driver executes automatically as
part of D.10.

```bash
python -m unittest discover -s nbody/tests -v
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
  --output results/appendix_d/d10_calibration_extensions/run9_nbody/campaign_validation

python -m nbody.run_ensemble \
  --config nbody/instability_ensemble/configs/local_smoke.json \
  --output results/appendix_d/d10_calibration_extensions/run9_nbody/local_smoke
```

The generated N-body validation uses an explicitly inflated Earth radius solely
to test collision logging. The archived 200-year outer-reservoir control uses
Earth's physical radius and records zero Earth collisions; this is an expected
short-control result and is not a delivery-probability constraint. See
`nbody/README.md` for the detailed N-body claim boundaries and commands.

The post-instability injection pilot adds four deterministic IAS15 seeds with
256 high-eccentricity test particles each. Across 500 yr per seed it integrates
1,024 conditioned trajectories (512,000 particle-years) with Earth's physical
radius. This remains an exploratory post-release transport kernel: it does not
generate the giant-planet instability and its collision fraction is not an
absolute outer-reservoir delivery probability.

Run 9 uses a five-giant-planet period-ratio template and a 20-Earth-mass outer
disk with gravitational back-reaction. Its deterministic campaign validation
and two-seed local smoke test are generated automatically by the complete replay
and by `--section D10`. Their verified artifacts are stored under
`results_cached/appendix_d/d10_calibration_extensions/run9_nbody/` and form part
of the unified 558-file baseline verification. The declared eight-seed,
10-Myr-per-seed production campaign is not executed by the local replay and
must not be cited as a measured delivery probability.

## SPH campaign preparation and external HPC execution

The Python code under `sph/` is executable workflow software, but it does not
perform the physical high-resolution impacts. The locally documented commands
are:

```bash
python -m unittest discover -s sph/tests -v
python -m sph.generate_impact_matrix \
  --config sph/configs/impact_matrix.json \
  --output results/manual/sph_matrix
```

These commands test the SPH preparation utilities and generate the configured
96-case SWIFT campaign matrix. The local tools also provide HDF5 structural
validation and first-pass diagnostics for snapshots returned by an external
simulation campaign. They are therefore operational preparation and analysis
code, not merely reference pseudocode.

None of the repository's Python files is the high-resolution hydrodynamics
solver. The `sph/production_campaign/` stage retains campaign preparation and
validation artifacts; the physical SWIFT campaign is external.

The commands above do **not** launch SWIFT, relax million-particle planetary
models, execute impacts, or produce a convergence series. Those operations
require an installed SWIFT solver and a cluster-specific MPI or scheduler
submission workflow. No universal direct-Python command can replace that
external execution. See `sph/README.md` for the generated campaign structure,
snapshot handoff, and local diagnostic procedures.

High-resolution 3-D SPH simulations with **>1,000,000 particles** remain the
external collaboration HPC phase required to calibrate or reject the analytical
partition closure, measure ejecta and reaccretion, resolve mantle coupling, and
test Earth–Moon angular-momentum and orbital survival. The campaign should ingest
the local parameter vectors `(M_i, v_i, theta, b/R_E)` and return its snapshots
for validation and comparison with the analytical predictions. No placeholder
SPH output is presented as a physical result in this repository.

## Geological forward predictions

The model should be compared against Jack Hills zircon data only through
**forward predictions**, not by assuming the desired signature has already been
observed.

Predictions to test include:

1. a possible thermal-resetting or age-population perturbation near the proposed
   ~4.1-Ga event;
2. an impact-driven oxygen-isotope mixing excursion whose sign and amplitude
   must be calculated from pre-impact crust, impactor water, mantle exchange,
   hydrothermal alteration and post-impact crystallization;
3. correlated volatile/isotope consequences rather than a zircon-only fit.

The current paper itself states that no known zircon signature uniquely
identifies a Titan-mass impact. Therefore, a "heavy δ18O spike at 4.1 Ga" must be
treated as a falsifiable forward hypothesis, **not** as established evidence.

## Failure hierarchy

1. No dynamically plausible late Earth-crossing source.
2. No 60°–75° grazing solution compatible with Earth–Moon survival.
3. No acceptable volatile partition.
4. D/H, N and noble gases cannot be fit jointly.
5. Quench chemistry fails to create useful reduced-N/HCN conditions.
6. Predicted geochemical/chronological signatures conflict with the Hadean record.
