# AIA V9 Hybrid Export Provenance

This directory holds the published normalized hybrid export currently used by
the Python-side hybrid comparison workflow.

The intended regeneration workflow is to run the exporter with an explicit
destination directory and an explicit source `.genx` pair, even when those
source names match the current defaults.

From the repository root, the supported command form is:

```bash
REPO_ROOT=$PWD
SSWIDL=/path/to/sswidl

cat <<EOF | "$SSWIDL"
.compile ${REPO_ROOT}/scripts/idl/ExportAIAHybridGenx.pro
ExportAIAHybridGenx, outdir='${REPO_ROOT}/benchmark-data/aia/genx-exports/aia_V9', response_dir='${SSW}/sdo/aia/response', fullinst_name='aia_V9_all_fullinst.genx', fullemiss_name='aia_V9_fullemiss.genx'
exit
EOF
```

For the current published artifact, that command selects:

- `response_dir='${SSW}/sdo/aia/response'`
- `fullinst_name='aia_V9_all_fullinst.genx'`
- `fullemiss_name='aia_V9_fullemiss.genx'`

If a future SSW release adds another compatible response pair, or if users need
to export a locally added pair, the export should be re-run in the same form
with a user-specified source pair and a matching preserved output directory.
Advanced users can either change `fullinst_name` and `fullemiss_name` while
keeping `response_dir`, or pass explicit `fullinst_file` and `fullemiss_file`
paths.