function ExportAIAHybridGenx__utc_now
  compile_opt idl2
  return, systime(/utc)
end


function ExportAIAHybridGenx__join, dir, name
  compile_opt idl2
  return, file_expand_path(filepath(name, root_dir=dir))
end


function ExportAIAHybridGenx__extract_version_label, name
  compile_opt idl2
  text = strupcase(strtrim(string(name), 2))
  anchor = strpos(text, 'AIA_V')
  if anchor lt 0 then return, ''

  value = 'aia_V'
  index = anchor + 5
  text_length = strlen(text)
  while index lt text_length do begin
    char = strmid(text, index, 1)
    if char lt '0' or char gt '9' then break
    value = value + char
    index = index + 1
  endwhile

  if strlen(value) le 5 then return, ''
  return, value
end


function ExportAIAHybridGenx__default_output_dir, fullinst_name, fullemiss_name
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

  version_label = ExportAIAHybridGenx__extract_version_label(fullinst_name)
  if strtrim(version_label, 2) eq '' then version_label = ExportAIAHybridGenx__extract_version_label(fullemiss_name)
  if strtrim(version_label, 2) eq '' then version_label = 'custom'
  return, file_expand_path(filepath(version_label, root_dir=filepath('genx-exports', root_dir=filepath('aia', root_dir=output_root))))
end


function ExportAIAHybridGenx__default_response_dir
  compile_opt idl2
  ssw_root = getenv('SSW')
  if n_elements(ssw_root) eq 0 or strtrim(ssw_root, 2) eq '' then message, 'SSW environment variable is not set.'
  return, ExportAIAHybridGenx__join(ssw_root, 'sdo/aia/response')
end


function ExportAIAHybridGenx__default_fullinst_name
  compile_opt idl2
  return, 'aia_V9_all_fullinst.genx'
end


function ExportAIAHybridGenx__default_fullemiss_name
  compile_opt idl2
  return, 'aia_V9_fullemiss.genx'
end


function ExportAIAHybridGenx__default_fullinst, response_dir, fullinst_name
  compile_opt idl2
  if n_elements(response_dir) eq 0 then response_dir = ExportAIAHybridGenx__default_response_dir()
  if n_elements(fullinst_name) eq 0 then fullinst_name = ExportAIAHybridGenx__default_fullinst_name()
  return, ExportAIAHybridGenx__join(response_dir, fullinst_name)
end


function ExportAIAHybridGenx__default_fullemiss, response_dir, fullemiss_name
  compile_opt idl2
  if n_elements(response_dir) eq 0 then response_dir = ExportAIAHybridGenx__default_response_dir()
  if n_elements(fullemiss_name) eq 0 then fullemiss_name = ExportAIAHybridGenx__default_fullemiss_name()
  return, ExportAIAHybridGenx__join(response_dir, fullemiss_name)
end


function ExportAIAHybridGenx__normalize_channels, channels
  compile_opt idl2
  out = strarr(n_elements(channels))
  for i = 0, n_elements(channels) - 1 do begin
    label = strupcase(strtrim(string(channels[i]), 2))
    if strpos(label, 'A') ne 0 then label = 'A' + label
    out[i] = label
  endfor
  return, out
end


function ExportAIAHybridGenx__select_euv_channels, channels
  compile_opt idl2
  want = ['A94', 'A131', 'A171', 'A193', 'A211', 'A304', 'A335']
  normalized = ExportAIAHybridGenx__normalize_channels(channels)
  use = bytarr(n_elements(normalized))
  for i = 0, n_elements(normalized) - 1 do begin
    if strpos(normalized[i], '_THICK') ge 0 then continue
    if total(byte(want eq normalized[i])) gt 0 then use[i] = 1b
  endfor
  return, normalized[where(use eq 1b)]
end


function ExportAIAHybridGenx__subset_general, general
  compile_opt idl2
  general_tags = strupcase(tag_names(general))
  subset = create_struct('AbundFile', (where(general_tags eq 'ABUNDFILE', /null) ne -1 ? string(general.abundfile) : ''), $
    'Source', (where(general_tags eq 'SOURCE', /null) ne -1 ? string(general.source) : ''), $
    'Ioneq_Name', (where(general_tags eq 'IONEQ_NAME', /null) ne -1 ? string(general.ioneq_name) : ''), $
    'Ioneq_Ref', (where(general_tags eq 'IONEQ_REF', /null) ne -1 ? string(general.ioneq_ref) : ''), $
    'Wvl_Units', (where(general_tags eq 'WVL_UNITS', /null) ne -1 ? string(general.wvl_units) : 'Angstrom'), $
    'Model_Name', (where(general_tags eq 'MODEL_NAME', /null) ne -1 ? string(general.model_name) : ''), $
    'Model_TE', (where(general_tags eq 'MODEL_TE', /null) ne -1 ? string(general.model_te) : ''), $
    'Model_NE', (where(general_tags eq 'MODEL_NE', /null) ne -1 ? string(general.model_ne) : ''), $
    'Add_Protons', (where(general_tags eq 'ADD_PROTONS', /null) ne -1 ? string(general.add_protons) : ''), $
    'PhotoExcitation', (where(general_tags eq 'PHOTOEXCITATION', /null) ne -1 ? string(general.photoexcitation) : ''), $
    'Version', (where(general_tags eq 'VERSION', /null) ne -1 ? string(general.version) : ''), $
    'Date', (where(general_tags eq 'DATE', /null) ne -1 ? string(general.date) : ''))
  return, subset
end


function ExportAIAHybridGenx__channel_struct, channel_label, channel_struct, channel_full_struct
  compile_opt idl2
  full_tags = strupcase(tag_names(channel_full_struct))
  short_tags = strupcase(tag_names(channel_struct))
  return, create_struct($
    'Channel', string(channel_label), $
    'Name', (where(full_tags eq 'NAME', /null) ne -1 ? string(channel_full_struct.name) : string(channel_label)), $
    'Units', (where(full_tags eq 'UNITS', /null) ne -1 ? string(channel_full_struct.units) : ''), $
    'Wave', (where(short_tags eq 'WAVE', /null) ne -1 ? reform(channel_struct.wave) : reform(channel_full_struct.wave)), $
    'EffArea', (where(short_tags eq 'EA', /null) ne -1 ? reform(channel_struct.ea) : reform(channel_full_struct.effarea)), $
    'GeoArea', (where(full_tags eq 'GEOAREA', /null) ne -1 ? double(channel_full_struct.geoarea) : !values.d_nan), $
    'PlateScale', (where(full_tags eq 'PLATESCALE', /null) ne -1 ? double(channel_full_struct.platescale) : !values.d_nan), $
    'ElecPerDN', (where(full_tags eq 'ELECPERDN', /null) ne -1 ? double(channel_full_struct.elecperdn) : !values.d_nan), $
    'ElecPerEV', (where(full_tags eq 'ELECPEREV', /null) ne -1 ? double(channel_full_struct.elecperev) : !values.d_nan), $
    'FP_Filter', (where(full_tags eq 'FP_FILTER', /null) ne -1 ? reform(channel_full_struct.fp_filter) : dblarr(n_elements(channel_full_struct.wave)) + !values.d_nan), $
    'Ent_Filter', (where(full_tags eq 'ENT_FILTER', /null) ne -1 ? reform(channel_full_struct.ent_filter) : dblarr(n_elements(channel_full_struct.wave)) + !values.d_nan), $
    'Primary', (where(full_tags eq 'PRIMARY', /null) ne -1 ? reform(channel_full_struct.primary) : dblarr(n_elements(channel_full_struct.wave)) + !values.d_nan), $
    'Secondary', (where(full_tags eq 'SECONDARY', /null) ne -1 ? reform(channel_full_struct.secondary) : dblarr(n_elements(channel_full_struct.wave)) + !values.d_nan), $
    'CCD', (where(full_tags eq 'CCD', /null) ne -1 ? reform(channel_full_struct.ccd) : dblarr(n_elements(channel_full_struct.wave)) + !values.d_nan), $
    'Contam', (where(full_tags eq 'CONTAM', /null) ne -1 ? reform(channel_full_struct.contam) : dblarr(n_elements(channel_full_struct.wave)) + !values.d_nan))
end


pro ExportAIAHybridGenx, outdir=outdir, response_dir=response_dir, fullinst_name=fullinst_name, fullemiss_name=fullemiss_name, fullinst_file=fullinst_file, fullemiss_file=fullemiss_file, output_name=output_name, metadata_name=metadata_name
  compile_opt idl2

  if n_elements(response_dir) eq 0 then response_dir = ExportAIAHybridGenx__default_response_dir()
  if n_elements(fullinst_name) eq 0 then fullinst_name = ExportAIAHybridGenx__default_fullinst_name()
  if n_elements(fullemiss_name) eq 0 then fullemiss_name = ExportAIAHybridGenx__default_fullemiss_name()
  if n_elements(outdir) eq 0 then outdir = ExportAIAHybridGenx__default_output_dir(fullinst_name, fullemiss_name)
  if n_elements(fullinst_file) eq 0 then fullinst_file = ExportAIAHybridGenx__default_fullinst(response_dir, fullinst_name)
  if n_elements(fullemiss_file) eq 0 then fullemiss_file = ExportAIAHybridGenx__default_fullemiss(response_dir, fullemiss_name)
  if n_elements(output_name) eq 0 then output_name = 'aia_hybrid_genx_export_v1.sav'
  if n_elements(metadata_name) eq 0 then metadata_name = 'aia_hybrid_genx_export_v1.metadata.txt'

  if ~file_test(outdir, /directory) then file_mkdir, outdir
  if ~file_test(fullinst_file) then message, 'Missing fullinst file: ' + fullinst_file
  if ~file_test(fullemiss_file) then message, 'Missing fullemiss file: ' + fullemiss_file

  on_error, 2
  restgen, file=fullinst_file, str=inststr
  restgen, file=fullemiss_file, str=emissstr

  euv_channels = ExportAIAHybridGenx__select_euv_channels(inststr.channels)
  emiss_general = ExportAIAHybridGenx__subset_general(emissstr.general)
  export = create_struct($
    'Format', 'pyeuvtools_aia_hybrid_genx_export', $
    'Format_Version', 1L, $
    'Instrument', 'AIA', $
    'Generator', routine_filepath('ExportAIAHybridGenx'), $
    'Generation_Time_UTC', ExportAIAHybridGenx__utc_now(), $
    'Source_Fullinst_File', string(fullinst_file), $
    'Source_Fullemiss_File', string(fullemiss_file), $
    'Channels', euv_channels, $
    'Emiss_Logte', reform(emissstr.total.logte), $
    'Emiss_Wave', reform(emissstr.total.wave), $
    'Emissivity', reform(emissstr.total.emissivity), $
    'Emiss_Units', string(emissstr.total.units), $
    'Emiss_Source', emiss_general.source, $
    'AbundFile', emiss_general.abundfile, $
    'Ioneq_Name', emiss_general.ioneq_name, $
    'Ioneq_Ref', emiss_general.ioneq_ref, $
    'Wvl_Units', emiss_general.wvl_units, $
    'Model_Name', emiss_general.model_name, $
    'Model_TE', emiss_general.model_te, $
    'Model_NE', emiss_general.model_ne, $
    'Add_Protons', emiss_general.add_protons, $
    'PhotoExcitation', emiss_general.photoexcitation, $
    'Emiss_Version_Name', emiss_general.version, $
    'Notes', 'Normalized hybrid export for pyEUVTools. Source .genx content flattened into a stable SAVE contract for Python loading.')

  inst_tags = strupcase(tag_names(inststr))
  for i = 0, n_elements(euv_channels) - 1 do begin
    channel_label = euv_channels[i]
    short_index = where(inst_tags eq channel_label, short_count)
    full_index = where(inst_tags eq channel_label + '_FULL', full_count)
    if short_count eq 0 or full_count eq 0 then message, 'Missing channel tags in fullinst export for ' + channel_label
    channel_export = ExportAIAHybridGenx__channel_struct(channel_label, inststr.(short_index[0]), inststr.(full_index[0]))
    export = create_struct(export, channel_label, channel_export)
  endfor

  hybrid_export = export
  output_path = ExportAIAHybridGenx__join(outdir, output_name)
  metadata_path = ExportAIAHybridGenx__join(outdir, metadata_name)

  save, hybrid_export, filename=output_path, /compress

  openw, lun, metadata_path, /get_lun
  printf, lun, 'format=' + export.format
  printf, lun, 'format_version=' + strtrim(export.format_version, 2)
  printf, lun, 'instrument=' + export.instrument
  printf, lun, 'generator=' + export.generator
  printf, lun, 'generation_time_utc=' + export.generation_time_utc
  printf, lun, 'source_fullinst_file=' + export.source_fullinst_file
  printf, lun, 'source_fullemiss_file=' + export.source_fullemiss_file
  printf, lun, 'channels=' + strjoin(export.channels, ',')
  printf, lun, 'emiss_units=' + export.emiss_units
  printf, lun, 'abundfile=' + export.abundfile
  printf, lun, 'ioneq_name=' + export.ioneq_name
  printf, lun, 'emiss_version_name=' + export.emiss_version_name
  printf, lun, 'notes=' + export.notes
  free_lun, lun

  print, 'Wrote hybrid export SAV:  ' + output_path
  print, 'Wrote metadata summary:  ' + metadata_path
end