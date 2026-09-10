# SWIFT/SPH production campaign

This folder marks the boundary between the local preparation utilities and the
physical 96-case SWIFT campaign.

The repository already supplies the matrix generator, HDF5 structure validator,
and first-pass snapshot diagnostics one directory above. The following work is
not executed locally and requires an HPC/supercomputer allocation:

1. production-resolution hydrostatic relaxation of differentiated bodies;
2. the 96 SWIFT impacts, including the 1,000,000-particle tier;
3. snapshot storage and checkpoint/restart management;
4. resolution-convergence reruns;
5. remnant/disk, volatile-partition and Earth-Moon outcome analysis.

Cluster job scripts are scheduler- and installation-specific, so no fabricated
SLURM/PBS script is distributed. No files in this folder are physical SPH
results, and `results_cached/` contains no claimed production-SPH output.
