# Historical research reconciliation — final stabilisation

## Status: unresolved

The historical database copy used by the earlier M14.7 point-in-time rerun is not present in the isolated final-stabilisation environment. The available application database belongs to the existing single-user service and was not read, copied, migrated, or modified. The final-stabilisation PostgreSQL container is synthetic-only and contains no historical research corpus. Reconciliation was therefore not rerun or marked passed.

The preserved report [`docs/history/audits/2026-10-19-m14-pit-rerun-report.md`](../../docs/history/audits/2026-10-19-m14-pit-rerun-report.md) records an earlier read-only comparison against an isolated `momentum25_e2e` copy at revision 0. It sampled eight stored runs from 2020-11-27 through 2026-02-27. The report found 84–98% stored-to-live qualified-set Jaccard similarity and 22–25 of the stored Top-25 names retained, except the 2023-02-28 stored-to-live comparison, which retained 8. The live-to-point-in-time comparison retained 22–25 names in all eight samples and changed qualified counts by up to 17. It attributed differences to post-decision split/bonus factors, date-appropriate universe membership, and a raw-close RS defect subsequently fixed.

Those figures remain historical evidence only. They do not quantify the current code and data revision, prove reproducibility from a present copy, or establish that every legacy report has been rerun. Original snapshots and reports were preserved.
