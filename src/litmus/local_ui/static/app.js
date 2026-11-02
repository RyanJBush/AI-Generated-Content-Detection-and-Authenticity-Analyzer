"use strict";
const token = document.querySelector('meta[name="litmus-token"]').content;
const fileInput = document.getElementById("file");
const analyze = document.getElementById("analyze");
const statusLine = document.getElementById("status");
const results = document.getElementById("results");
const content = document.getElementById("report-content");
let chosen = null, running = false, report = null;
const labels = {supports_ai:"AI-generation signal",no_signal:"No AI-generation signal",inconclusive:"Inconclusive",not_supported:"Not supported",error:"Analysis error"};
function node(tag, text, className) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = text;
  if (className) el.className = className; return el;
}
function say(text, error = false) {statusLine.textContent = text; statusLine.classList.toggle("error",error);}
function selectFile(file) {
  if (running || !file) return;
  if (file.size > 50000000) {
    chosen = null; fileInput.value = ""; analyze.disabled = true;
    document.getElementById("file-name").textContent = "Select a file to inspect";
    document.getElementById("file-meta").textContent = "Text, Markdown, JPEG, PNG or WebP · up to 50 MB";
    say("Choose a file no larger than 50 MB.",true); return;
  }
  chosen = file; document.getElementById("file-name").textContent = file.name;
  document.getElementById("file-meta").textContent = `${new Intl.NumberFormat().format(file.size)} bytes · ready to inspect`;
  analyze.disabled = false; say("Ready. Choose your checks, then analyze the file.");
}
fileInput.addEventListener("change",()=>selectFile(fileInput.files[0]));
const drop = document.getElementById("drop");
drop.addEventListener("dragover",event=>{event.preventDefault(); if (!running) drop.classList.add("dragging");});
drop.addEventListener("dragleave",()=>drop.classList.remove("dragging"));
drop.addEventListener("drop",event=>{event.preventDefault();drop.classList.remove("dragging");selectFile(event.dataTransfer.files[0]);});
function list(parent, heading, values) {
  if (!values || !values.length) return;
  parent.append(node("h4",heading)); const ul = node("ul");
  values.forEach(value=>ul.append(node("li",String(value)))); parent.append(ul);
}
function render(value) {
  report = value; content.replaceChildren();
  document.getElementById("report-file").textContent = `${value.input.file_name} · ${value.input.detected_type || "unknown type"} · ${value.input.size_bytes} bytes`;
  if (!value.segments.length) {
    const card = node("div",undefined,"evidence");card.append(node("h3","File not analyzed"));
    card.append(node("p",value.input.ingestion.reason || value.input.ingestion.result));content.append(card);
  }
  value.segments.forEach(segment=>{
    segment.origin.forEach(origin=>{
      const card = node("article",undefined,"evidence");
      card.append(node("p",`${segment.modality} · ${origin.method_id}`,"eyebrow"));
      card.append(node("h3",labels[origin.result] || origin.result));
      if (origin.raw_score !== null && origin.raw_score !== undefined) card.append(node("p",`Raw detector score: ${origin.raw_score} — not a probability`,"score"));
      list(card,"Reasons",origin.reasons); list(card,"Limitations",origin.limitations);
      const details = node("details");details.append(node("summary","View evidence details"));
      details.append(node("pre",JSON.stringify({calibration:origin.calibration,provenance:origin.provenance,details:origin.details},null,2)));
      card.append(details);content.append(card);
    });
    if (segment.quality.length) {
      const card = node("article",undefined,"evidence quality");card.append(node("h3","Content observations"));
      card.append(node("p","These observations describe text patterns and do not establish AI origin."));
      segment.quality.forEach(observation=>{
        card.append(node("h4",observation.observer_id.replaceAll("_"," ")));
        card.append(node("p",`${observation.status}${observation.count === null ? "" : ` · ${observation.count} matches`}`));
        list(card,"Notes",observation.notes);
      });content.append(card);
    }
  });
  list(content,"Report limitations",value.limitations);
  results.hidden = false; document.getElementById("results-title").focus();
}
async function api(path,options={}) {
  const response = await fetch(path,{...options,headers:{"X-Litmus-Token":token,...options.headers}});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error?.message || "The local request did not finish. Try again.");
  return value;
}
analyze.addEventListener("click",async()=>{
  if (!chosen || running) return;
  running = true; analyze.disabled = true; fileInput.disabled = true;
  const switches = ["text-origin","quality","c2pa"].map(id=>document.getElementById(id));
  switches.forEach(el=>el.disabled=true); analyze.textContent = "Analyzing…";
  say("Analyzing locally. This may take a few minutes; no need to submit again.");
  try {
    const query = new URLSearchParams({text_origin:switches[0].checked ? "on":"off",quality:switches[1].checked ? "on":"off",c2pa:switches[2].checked ? "on":"off"});
    let job = await api(`/api/v1/jobs?${query}`,{method:"POST",body:chosen,headers:{"Content-Type":"application/octet-stream","X-Litmus-Filename":encodeURIComponent(chosen.name)}});
    report = null; results.hidden = true;
    while (job.status === "running") {
      await new Promise(resolve=>setTimeout(resolve,500)); job = await api(`/api/v1/jobs/${job.id}`);
    }
    if (job.status === "error") throw new Error(job.error);
    render(job.report); say("Analysis complete. Review the reasons and limitations below.");
  } catch (error) {say(`${error.message} Your file selection is kept.`,true);}
  finally {running=false;fileInput.disabled=false;switches.forEach(el=>el.disabled=false);analyze.disabled=!chosen;analyze.textContent="Analyze file →";}
});
document.getElementById("download").addEventListener("click",()=>{
  if (!report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(report,null,2)+"\n"],{type:"application/json"}));
  const link = node("a");link.href=url;link.download="litmus-report.json";document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
