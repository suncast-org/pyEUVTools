function ExportAIAChiantifix__utc_now
  compile_opt idl2
  return, systime(/utc)
end


function ExportAIAChiantifix__join, dir, name
  compile_opt idl2
  return, file_expand_path(filepath(name, root_dir=dir))
end


function ExportAIAChiantifix__extract_version_label, name
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


function ExportAIAChiantifix__default_response_dir
  compile_opt idl2
  ssw_root = getenv('SSW')
  if n_elements(ssw_root) eq 0 or strtrim(ssw_root, 2) eq '' then message, 'SSW environment variable is not set.'
  return, ExportAIAChiantifix__join(ssw_root, 'sdo/aia/response')
end


function ExportAIAChiantifix__default_chiantifix_name
  compile_opt idl2
  return, 'aia_V9_chiantifix.genx'
end


function ExportAIAChiantifix__default_output_dir, chiantifix_name
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

  version_label = ExportAIAChiantifix__extract_version_label(chiantifix_name)
  if strtrim(version_label, 2) eq '' then version_label = 'custom'
  return, file_expand_path(filepath(version_label, root_dir=filepath('chiantifix-exports', root_dir=filepath('aia', root_dir=output_root))))
end


pro ExportAIAChiantifix, outdir=outdir, response_dir=response_dir, chiantifix_name=chiantifix_name, chiantifix_file=chiantifix_file, output_name=output_name, metadata_name=metadata_name
  compile_opt idl2

  if n_elements(response_dir) eq 0 then response_dir = ExportAIAChiantifix__default_response_dir()
  if n_elements(chiantifix_name) eq 0 then chiantifix_name = ExportAIAChiantifix__default_chiantifix_name()
  if n_elements(outdir) eq 0 then outdir = ExportAIAChiantifix__default_output_dir(chiantifix_name)
  if n_elements(chiantifix_file) eq 0 then chiantifix_file = ExportAIAChiantifix__join(response_dir, chiantifix_name)
  if n_elements(output_name) eq 0 then output_name = 'aia_chiantifix_export_v1.sav'
  if n_elements(metadata_name) eq 0 then metadata_name = 'aia_chiantifix_export_v1.metadata.txt'

  if ~file_test(outdir, /directory) then file_mkdir, outdir
  if ~file_test(chiantifix_file) then message, 'Missing chiantifix file: ' + chiantifix_file

  on_error, 2
  restgen, file=chiantifix_file, str=fixstr

  export = create_struct($
    'Format', 'pyeuvtools_aia_chiantifix_export', $
    'Format_Version', 1L, $
    'Instrument', 'AIA', $
    'Version', ExportAIAChiantifix__extract_version_label(chiantifix_name), $
    'Generator', routine_filepath('ExportAIAChiantifix'), $
    'Generation_Time_UTC', ExportAIAChiantifix__utc_now(), $
    'Source_Chiantifix_File', string(chiantifix_file), $
    'Channels', reform(fixstr.channels), $
    'LogTE', reform(fixstr.logte), $
    'Empirical_Minus_Raw', reform(fixstr.empirical_minus_raw), $
    'Empirical_Minus_Raw_Units', 'DN cm^5 s^-1 pix^-1', $
    'Notes', 'Python-readable export of the SSW chiantifix correction grid. Apply channel-wise and scale by the time-dependent AIA degradation factor before adding to the folded temperature response.')

  chiantifix_export = export
  output_path = ExportAIAChiantifix__join(outdir, output_name)
  metadata_path = ExportAIAChiantifix__join(outdir, metadata_name)

  save, chiantifix_export, filename=output_path, /compress

  openw, lun, metadata_path, /get_lun
  printf, lun, 'format=' + export.format
  printf, lun, 'format_version=' + strtrim(export.format_version, 2)
  printf, lun, 'instrument=' + export.instrument
  printf, lun, 'version=' + export.version
  printf, lun, 'generator=' + export.generator
  printf, lun, 'generation_time_utc=' + export.generation_time_utc
  printf, lun, 'source_chiantifix_file=' + export.source_chiantifix_file
  printf, lun, 'channels=' + strjoin(export.channels, ',')
  printf, lun, 'empirical_minus_raw_units=' + export.empirical_minus_raw_units
  printf, lun, 'notes=' + export.notes
  free_lun, lun

  print, 'Wrote chiantifix export SAV:  ' + output_path
  print, 'Wrote metadata summary:       ' + metadata_path
end
