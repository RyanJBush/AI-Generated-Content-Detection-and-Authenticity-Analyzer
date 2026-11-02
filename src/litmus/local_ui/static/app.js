"use strict";
const byId = id => document.getElementById(id);
const token = document.querySelector('meta[name="litmus-token"]').content;
const fileInput = byId('file'), analyze = byId('analyze'), retry = byId('retry');
const statusLine = byId('status'), results = byId('results'), content = byId('report-content');
const switches = ['text-origin','quality','c2pa'].map(byId), storageKey = 'litmus-last-job';
let chosen = null, running = false, report = null, pending = null;
const labels = {supports_ai:'AI-generation signal',no_signal:'No signal above the calibrated threshold',inconclusive:'Inconclusive',not_supported:'Not supported',error:'Analysis error'};
const reasons = {
  not_above_calibrated_threshold:'The score did not cross this configuration’s calibrated threshold. This does not establish human authorship.',
  above_calibrated_threshold:'The score crossed this configuration’s calibrated threshold. False positives remain possible.',
  no_nonwhitespace_content:'There is no non-whitespace text to analyze.',
  untrusted_signed_ai_declaration:'The credentials declare AI use, but the signer is not trusted by Litmus’s current policy.',
  no_manifest:'No embedded Content Credentials were found. Their absence does not establish origin.',
  calibration_invalid:'Calibration could not be applied to this configuration. See the evidence details.',
  too_short:'The text is too short for this detector; at least 64 tokens are required.',
  'no calibration for this configuration':'No calibration matches this exact execution configuration.',
  execution_profile_changed:'The execution settings changed. Restart Litmus using the accepted local configuration.',
  execution_profile_incomplete:'The required execution settings could not be verified.'
};
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function say(text, error=false) { statusLine.textContent=text; statusLine.classList.toggle('error',error); }
function saveJob(value) {
  try { if (value) sessionStorage.setItem(storageKey,JSON.stringify(value)); else sessionStorage.removeItem(storageKey); }
  catch { /* Explicit retry still works when tab storage is unavailable. */ }
}
function controls() {
  const locked = running || pending !== null;
  fileInput.disabled=locked; switches.forEach(el=>el.disabled=locked);
  analyze.disabled=locked || !chosen; analyze.textContent=running ? 'Analyzing…' : 'Analyze file →';
  retry.hidden=!pending || running; byId('forget').hidden=!pending || running; analyze.setAttribute('aria-busy',String(running));
}
function selectFile(file) {
  if (running || pending || !file) return;
  report=null; results.hidden=true; saveJob(null);
  if (file.size>50000000) {
    chosen=null; fileInput.value=''; byId('file-name').textContent='Select a file to inspect';
    byId('file-meta').textContent='Text, Markdown, JPEG, PNG or WebP · up to 50 MB';
    say('Choose a file no larger than 50 MB.',true);
  } else {
    chosen=file; byId('file-name').textContent=file.name;
    byId('file-meta').textContent=`${new Intl.NumberFormat().format(file.size)} bytes · ready to inspect`;
    say('Ready. Choose your checks, then analyze the file.');
  }
  controls();
}
fileInput.addEventListener('change',()=>selectFile(fileInput.files[0]));
const drop=byId('drop');
drop.addEventListener('dragover',e=>{e.preventDefault();if(!running&&!pending)drop.classList.add('dragging');});
drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));
drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('dragging');selectFile(e.dataTransfer.files[0]);});
function list(parent,heading,values) {
  if(!values?.length)return;
  parent.append(node('h4',heading)); const ul=node('ul');
  values.forEach(value=>ul.append(node('li',String(value)))); parent.append(ul);
}
function readable(value){if(value.startsWith('numerical_error'))return 'The detector could not produce a valid numerical score. See the original evidence record.';return reasons[value] || value.replaceAll('_',' ');}
function render(value) {
  report=value;content.replaceChildren();
  byId('report-file').textContent=`${value.input.file_name} · ${value.input.detected_type||'unknown type'} · ${value.input.size_bytes} bytes`;
  if(!value.segments.length){const card=node('div',undefined,'evidence');card.append(node('h3','File not analyzed'));card.append(node('p',readable(value.input.ingestion.reason||value.input.ingestion.result)));content.append(card);}
  value.segments.forEach(segment=>{
    segment.origin.forEach(origin=>{
      const off=origin.method_id.endsWith('_placeholder'),card=node('article',undefined,'evidence');
      card.append(node('p',segment.modality==='text'?'Text origin':'Image provenance','eyebrow'));
      card.append(node('h3',off?'Not run':labels[origin.result]||origin.result));
      if(off)card.append(node('p',segment.modality==='text'
        ?'Text-origin analysis was not enabled. Enable Text origin signals with the required local models to run it.'
        :'Image credentials were not enabled. Litmus checks provenance metadata; it does not detect AI-generated image content.'));
      else {
        if(origin.raw_score!=null)card.append(node('p',`Raw detector score: ${origin.raw_score} — not a probability`,'score'));
        list(card,'What this means',origin.reasons.map(readable));list(card,'Limitations',origin.limitations);
      }
      const details=node('details');details.append(node('summary','View original evidence record'));
      details.append(node('pre',JSON.stringify(origin,null,2)));card.append(details);content.append(card);
    });
    const card=node('article',undefined,'evidence quality');card.append(node('h3','Content observations'));
    card.append(node('p','These observations describe text patterns and do not establish AI origin.'));
    if(!segment.quality.length)card.append(node('p',segment.modality==='text'?'Not run. Enable Content observations to inspect writing patterns.':'Not applicable. Content observations currently support text only.'));
    if(segment.quality.length)card.append(node('p','These English-oriented, provisional lexicons count surface patterns, not writing quality. Word counts assume space-separated scripts; rates are not comparable for scripts such as CJK. Homoglyphs and zero-width characters can evade matches. At most 1,000 spans are shown per observer; counts remain exact.','muted'));
    segment.quality.forEach(observation=>{
      card.append(node('h4',observation.observer_id.replaceAll('_',' ')));
      card.append(node('p',`${observation.status.replaceAll('_',' ')}${observation.count==null?'':` · ${observation.count} ${observation.count===1?'match':'matches'}`}`));
      if(observation.status==='error')card.append(node('p','This observation could not complete. See its original record.'));
      const detail=node('details');detail.append(node('summary','View original observation'));detail.append(node('pre',JSON.stringify(observation,null,2)));card.append(detail);
    });content.append(card);
  });
  // Preserve historical schema wording verbatim, separately from current UI copy.
  const raw=node('details');raw.append(node('summary','All recorded report limitations (verbatim)'));list(raw,'Recorded limitations',value.limitations);content.append(raw);
  results.hidden=false;byId('results-title').focus();
}
async function api(path,options={}) {
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
  try {
    const response=await fetch(path,{...options,signal:controller.signal,headers:{'X-Litmus-Token':token,...options.headers}});
    let value;try{value=await response.json();}catch{throw new Error('The local service returned an unreadable response.');}
    if(!response.ok){const error=new Error(value.error?.message||'The local request failed.');error.status=response.status;throw error;}
    return value;
  } catch(error) {
    if(error.name==='AbortError')throw new Error('The request timed out. This does not cancel analysis.');
    if(error instanceof TypeError)throw new Error('The local service could not be reached. Check that Litmus is still running.');
    throw error;
  } finally{clearTimeout(timer);}
}
async function followJob(job) {
  while(job.status==='running'){await new Promise(resolve=>setTimeout(resolve,500));job=await api(`/api/v1/jobs/${pending.id}`);}
  if(!['completed','error'].includes(job.status))throw new Error('The job returned an unknown state.');
  const saved=pending;pending=null;
  if(job.status==='error'){saveJob(null);throw new Error(job.error);}
  saveJob(null);render(job.report);saveJob(saved);say('Report ready. Review which checks ran, their reasons and limitations.');
}
function showFailure(error) {
  if(error.status===404||error.status===403){pending=null;saveJob(null);}
  say(`${error.message} ${pending?'Your analysis may still be running. Check its status below; do not submit it again.':error.uncertainPost?'Litmus may have started this analysis. Wait before trying again; another attempt may report that it is busy.':'Select your file or try again when the service is ready.'}`,true);
}
analyze.addEventListener('click',async()=>{
  if(!chosen||running||pending)return;
  running=true;controls();byId('status').focus();results.hidden=true;report=null;say('Analyzing locally. This may take a few minutes; no need to submit again.');
  const options={text_origin:switches[0].checked?'on':'off',quality:switches[1].checked?'on':'off',c2pa:switches[2].checked?'on':'off'};
  let accepted=false;
  try {
    const job=await api(`/api/v1/jobs?${new URLSearchParams(options)}`,{method:'POST',body:chosen,headers:{'Content-Type':'application/octet-stream','X-Litmus-Filename':encodeURIComponent(chosen.name)}});
    accepted=true;pending={id:job.id,options};saveJob(pending);await followJob(job);
  }catch(error){if(!accepted && !error.status)error.uncertainPost=true;showFailure(error);}finally{running=false;controls();}
});
async function recover() {
  if(!pending||running)return;
  running=true;controls();say('Checking the saved analysis. No file is being resubmitted.');
  try{await followJob(await api(`/api/v1/jobs/${pending.id}`));}catch(error){showFailure(error);}finally{running=false;controls();}
}
retry.addEventListener('click',recover);
byId('forget').addEventListener('click',()=>{pending=null;saveJob(null);controls();say('Status tracking dismissed. Local work is not cancelled; a new analysis may be busy until it finishes.');fileInput.focus();});
byId('download').addEventListener('click',()=>{
  if(!report)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json'}));
  const link=node('a');link.href=url;link.download='litmus-report.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
try{const saved=JSON.parse(sessionStorage.getItem(storageKey));if(saved&&/^[0-9a-f]{32}$/.test(saved.id)){pending=saved;if(saved.options){switches[0].checked=saved.options.text_origin==='on';switches[1].checked=saved.options.quality==='on';switches[2].checked=saved.options.c2pa==='on';}recover();}}catch{saveJob(null);}
