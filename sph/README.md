# Planetary-SPH preparation module

This directory is intentionally separate from the local analytical Stage 2.
It prepares a future SWIFT planetary-SPH resolution study and analyzes returned
snapshots; it does not claim that SPH has already been executed.

## Execution boundary

Everything currently included here is preparation or post-processing code.
Matrix generation and small-file validation can run locally. The 96 physical
SWIFT impact simulations, especially the 1,000,000-particle resolution tier,
production-resolution hydrostatic relaxation, snapshot storage, and convergence
reruns are HPC/supercomputer work. They are intentionally not executed or cached
in this repository. No SPH outcome is reported until cluster snapshots return
and pass validation.

## Workflow

1. Generate the declared mass/speed/angle/composition/resolution matrix:

   ```bash
   python -m sph.generate_impact_matrix \
     --config sph/configs/impact_matrix.json \
     --output sph/generated
   ```

2. Build hydrostatically relaxed differentiated bodies with a planetary-profile
   generator such as WoMa, assign material IDs and planetary equations of state,
   and transform each relaxed pair to the contact state in the matrix.

3. Validate each HDF5 file before submitting it to SWIFT:

   ```bash
   python -m sph.validate_swift_ic initial_conditions/example.hdf5
   ```

4. Configure SWIFT with planetary hydrodynamics and planetary equations of
   state. Production runs require a resolution-convergence series and HPC job
   scripts specific to the target cluster.

5. Analyze snapshots with an iterative remnant/disk classifier. The included
   `analyze_snapshot.py` supplies only transparent mass and two-body binding
   diagnostics; it is deliberately not labeled a final remnant finder.

The 100,000-particle matrix entries are pipeline tests. The 1,000,000-particle
entries begin an HPC resolution study but are not automatically converged or
publication-grade merely because of their particle count.
