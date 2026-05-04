function GenerateCanonicalAIABenchmark__utc_now
  compile_opt idl2
  return, systime(/utc)
end


function GenerateCanonicalAIABenchmark__default_stamp
  compile_opt idl2
  return, '20251126T153431'
end


function GenerateCanonicalAIABenchmark__default_output_dir
  compile_opt idl2
  home_dir = getenv('HOME')
  tmp_dir = getenv('TMPDIR')
  if n_elements(home_dir) eq 0 or strtrim(home_dir, 2) eq '' then home_dir = ''
  if n_elements(tmp_dir) eq 0 or strtrim(tmp_dir, 2) eq '' then tmp_dir = '/tmp'

  if strtrim(home_dir, 2) ne '' then begin
    output_root = filepath('.pyeuvtools', root_dir=home_dir)
  endif else begin
    output_root = filepath('pyeuvtools', root_dir=tmp_dir)
  endelse

  return, file_expand_path(filepath(GenerateCanonicalAIABenchmark__default_stamp(), root_dir=filepath('aia', root_dir=filepath('benchmark-data', root_dir=output_root))))
end


function GenerateCanonicalAIABenchmark__join, dir, name
  compile_opt idl2
  return, file_expand_path(filepath(name, root_dir=dir))
end


function GenerateCanonicalAIABenchmark__requested_state_label, evenorm, chiantifix
  compile_opt idl2
  if keyword_set(chiantifix) and keyword_set(evenorm) then return, 'evenorm_chiantifix'
  if keyword_set(chiantifix) and ~keyword_set(evenorm) then return, 'chiantifix_request'
  if keyword_set(evenorm) then return, 'evenorm'
  return, 'raw'
end


function GenerateCanonicalAIABenchmark__effective_state_label, evenorm_applied, chiantifix_applied
  compile_opt idl2
  if strupcase(string(chiantifix_applied)) eq 'YES' then return, 'evenorm_chiantifix'
  if strupcase(string(evenorm_applied)) eq 'YES' then return, 'evenorm'
  return, 'raw'
end


function GenerateCanonicalAIABenchmark__default_basename, requested_state
  compile_opt idl2
  stamp = GenerateCanonicalAIABenchmark__default_stamp()
  if requested_state eq 'evenorm_chiantifix' then return, 'aia_raw_response_' + stamp
  return, 'aia_raw_response_' + stamp + '_' + requested_state
end


function GenerateCanonicalAIABenchmark__default_benchmark_role, effective_state
  compile_opt idl2
  return, effective_state + '_reference'
end


pro GenerateCanonicalAIABenchmark, obs_time=obs_time, outdir=outdir, warnings_observed=warnings_observed, raw_name=raw_name, metadata_name=metadata_name, source_effarea_file=source_effarea_file, source_emissivity_file=source_emissivity_file, evenorm=evenorm, chiantifix=chiantifix, benchmark_role=benchmark_role, notes=notes
  compile_opt idl2

  response_tags = ''
  emissinfo_tags = ''
  corrections_tags = ''
  requested_state = ''
  effective_state = ''
  evenorm_applied = ''
  chiantifix_applied = ''

  if n_elements(obs_time) eq 0 then obs_time = '2025-11-26T15:34:31.400'
  if n_elements(outdir) eq 0 then outdir = GenerateCanonicalAIABenchmark__default_output_dir()
  if n_elements(warnings_observed) eq 0 then warnings_observed = ''
  if n_elements(source_effarea_file) eq 0 then source_effarea_file = ''
  if n_elements(source_emissivity_file) eq 0 then source_emissivity_file = ''
  if n_elements(evenorm) eq 0 then evenorm = 1L
  if n_elements(chiantifix) eq 0 then chiantifix = 1L

  requested_state = GenerateCanonicalAIABenchmark__requested_state_label(evenorm, chiantifix)
  if n_elements(raw_name) eq 0 then raw_name = GenerateCanonicalAIABenchmark__default_basename(requested_state) + '.sav'
  if n_elements(metadata_name) eq 0 then metadata_name = GenerateCanonicalAIABenchmark__default_basename(requested_state) + '.metadata.txt'

  if ~file_test(outdir, /directory) then file_mkdir, outdir

  obs_time_vms = anytim(obs_time, /vms)
  generation_time_utc = GenerateCanonicalAIABenchmark__utc_now()
  on_error, 2

  ; The scientific reference is the direct aia_get_response output for the requested state.
  raw_response = aia_get_response(timedepend_date=obs_time_vms, /temperature, /dn, evenorm=evenorm, chiantifix=chiantifix)
  response_tags = strupcase(tag_names(raw_response))
  if where(response_tags eq 'EMISSINFO', /null) ne -1 then emissinfo_tags = strupcase(tag_names(raw_response.emissinfo))
  if where(response_tags eq 'CORRECTIONS', /null) ne -1 then corrections_tags = strupcase(tag_names(raw_response.corrections))
  evenorm_applied = (where(corrections_tags eq 'EVENORM_APPLIED', /null) ne -1 ? string(raw_response.corrections.evenorm_applied) : '')
  chiantifix_applied = (where(corrections_tags eq 'CHIANTIFIX_APPLIED', /null) ne -1 ? string(raw_response.corrections.chiantifix_applied) : '')
  effective_state = GenerateCanonicalAIABenchmark__effective_state_label(evenorm_applied, chiantifix_applied)
  if n_elements(benchmark_role) eq 0 then benchmark_role = GenerateCanonicalAIABenchmark__default_benchmark_role(effective_state)
  if n_elements(notes) eq 0 then notes = 'Direct aia_get_response benchmark for pyEUVTools parity validation. Requested state=' + requested_state + '; effective state=' + effective_state + '.'

  metadata = { $
    instrument: 'AIA', $
    benchmark_role: string(benchmark_role), $
    obs_time: string(obs_time), $
    timedepend_date: string(obs_time_vms), $
    evenorm: long(evenorm), $
    chiantifix: long(chiantifix), $
    requested_state: requested_state, $
    effective_state: effective_state, $
    idl_version: !version.release, $
    idl_arch: !version.arch, $
    idl_os: !version.os, $
    ssw_root: getenv('SSW'), $
    generator: routine_filepath('GenerateCanonicalAIABenchmark'), $
    generation_time_utc: generation_time_utc, $
    source_effarea_file: string(source_effarea_file), $
    source_emissivity_file: string(source_emissivity_file), $
    effarea_version: (where(response_tags eq 'EFFAREA_VERSION', /null) ne -1 ? raw_response.effarea_version : -1), $
    emiss_version: (where(response_tags eq 'EMISS_VERSION', /null) ne -1 ? raw_response.emiss_version : -1), $
    response_units: (where(response_tags eq 'UNITS', /null) ne -1 ? string(raw_response.units) : ''), $
    chianti_version: (where(emissinfo_tags eq 'VERSION', /null) ne -1 ? string(raw_response.emissinfo.version) : ''), $
    abundance_file: (where(emissinfo_tags eq 'ABUNDFILE', /null) ne -1 ? string(raw_response.emissinfo.abundfile) : ''), $
    ioneq_name: (where(emissinfo_tags eq 'IONEQ_NAME', /null) ne -1 ? string(raw_response.emissinfo.ioneq_name) : ''), $
    time_applied: (where(corrections_tags eq 'TIME_APPLIED', /null) ne -1 ? string(raw_response.corrections.time_applied) : ''), $
    evenorm_applied: evenorm_applied, $
    chiantifix_applied: chiantifix_applied, $
    warnings_observed: warnings_observed, $
    notes: string(notes) $
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
  printf, lun, 'requested_state=' + metadata.requested_state
  printf, lun, 'effective_state=' + metadata.effective_state
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
  printf, lun, 'chianti_version=' + metadata.chianti_version
  printf, lun, 'abundance_file=' + metadata.abundance_file
  printf, lun, 'ioneq_name=' + metadata.ioneq_name
  printf, lun, 'time_applied=' + metadata.time_applied
  printf, lun, 'evenorm_applied=' + metadata.evenorm_applied
  printf, lun, 'chiantifix_applied=' + metadata.chiantifix_applied
  printf, lun, 'warnings_observed=' + metadata.warnings_observed
  printf, lun, 'notes=' + metadata.notes
  free_lun, lun

  print, 'Wrote raw benchmark SAV: ' + raw_path
  print, 'Wrote metadata summary:  ' + meta_path
end
