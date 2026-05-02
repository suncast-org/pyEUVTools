function GenerateCanonicalAIABenchmark__utc_now
  compile_opt idl2
  return, systime(/utc)
end


function GenerateCanonicalAIABenchmark__default_output_dir
  compile_opt idl2
  script_dir = file_dirname(routine_filepath('GenerateCanonicalAIABenchmark', /find))
  repo_root = file_dirname(file_dirname(script_dir))
  return, file_expand_path(filepath('20251126T153431', root_dir=filepath('aia', root_dir=filepath('benchmark-data', root_dir=repo_root))))
end


function GenerateCanonicalAIABenchmark__join, dir, name
  compile_opt idl2
  return, file_expand_path(filepath(name, root_dir=dir))
end


pro GenerateCanonicalAIABenchmark, obs_time=obs_time, outdir=outdir, warnings_observed=warnings_observed, raw_name=raw_name, metadata_name=metadata_name
  compile_opt idl2

  response_tags = ''

  if n_elements(obs_time) eq 0 then obs_time = '2025-11-26T15:34:31.400'
  if n_elements(outdir) eq 0 then outdir = GenerateCanonicalAIABenchmark__default_output_dir()
  if n_elements(raw_name) eq 0 then raw_name = 'aia_raw_response_20251126T153431.sav'
  if n_elements(metadata_name) eq 0 then metadata_name = 'aia_raw_response_20251126T153431.metadata.txt'
  if n_elements(warnings_observed) eq 0 then warnings_observed = ''

  if ~file_test(outdir, /directory) then file_mkdir, outdir

  obs_time_vms = anytim(obs_time, /vms)
  generation_time_utc = GenerateCanonicalAIABenchmark__utc_now()
  on_error, 2

  ; The canonical scientific reference is the direct aia_get_response output.
  raw_response = aia_get_response(timedepend_date=obs_time_vms, /temperature, /dn, /evenorm, /chiantifix)
  response_tags = strupcase(tag_names(raw_response))

  metadata = { $
    instrument: 'AIA', $
    benchmark_role: 'raw_reference', $
    obs_time: string(obs_time), $
    timedepend_date: string(obs_time_vms), $
    evenorm: 1L, $
    chiantifix: 1L, $
    idl_version: !version.release, $
    idl_arch: !version.arch, $
    idl_os: !version.os, $
    ssw_root: getenv('SSW'), $
    generator: routine_filepath('GenerateCanonicalAIABenchmark', /find), $
    generation_time_utc: generation_time_utc, $
    source_effarea_file: '', $
    source_emissivity_file: '', $
    effarea_version: (where(response_tags eq 'EFFAREA_VERSION', /null) ne -1 ? raw_response.effarea_version : -1), $
    emiss_version: (where(response_tags eq 'EMISS_VERSION', /null) ne -1 ? raw_response.emiss_version : -1), $
    response_units: (where(response_tags eq 'UNITS', /null) ne -1 ? string(raw_response.units) : ''), $
    warnings_observed: warnings_observed, $
    notes: 'Direct aia_get_response benchmark for pyEUVTools parity validation.' $
  }

  raw_path = GenerateCanonicalAIABenchmark__join(outdir, raw_name)
  meta_path = GenerateCanonicalAIABenchmark__join(outdir, metadata_name)

  save, raw_response, metadata, filename=raw_path, /compress

  openw, lun, meta_path, /get_lun
  printf, lun, 'instrument=' + metadata.instrument
  printf, lun, 'benchmark_role=' + metadata.benchmark_role
  printf, lun, 'obs_time=' + metadata.obs_time
  printf, lun, 'timedepend_date=' + metadata.timedepend_date
  printf, lun, 'evenorm=' + strtrim(metadata.evenorm, 2)
  printf, lun, 'chiantifix=' + strtrim(metadata.chiantifix, 2)
  printf, lun, 'idl_version=' + metadata.idl_version
  printf, lun, 'idl_arch=' + metadata.idl_arch
  printf, lun, 'idl_os=' + metadata.idl_os
  printf, lun, 'ssw_root=' + metadata.ssw_root
  printf, lun, 'generator=' + metadata.generator
  printf, lun, 'generation_time_utc=' + metadata.generation_time_utc
  printf, lun, 'source_effarea_file=' + metadata.source_effarea_file
  printf, lun, 'source_emissivity_file=' + metadata.source_emissivity_file
  printf, lun, 'effarea_version=' + strtrim(metadata.effarea_version, 2)
  printf, lun, 'emiss_version=' + strtrim(metadata.emiss_version, 2)
  printf, lun, 'response_units=' + metadata.response_units
  printf, lun, 'warnings_observed=' + metadata.warnings_observed
  printf, lun, 'notes=' + metadata.notes
  free_lun, lun

  print, 'Wrote raw benchmark SAV: ' + raw_path
  print, 'Wrote metadata summary:  ' + meta_path
end
