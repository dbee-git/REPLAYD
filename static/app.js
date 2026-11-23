/* REPLAYD — zero-API-key creator workspace. All backend work runs locally. */
const $ = (id) => document.getElementById(id);
const state = {project:null, analysis:null, selected:null, busy:false};
let toastTimeout;
function notify(message, error=false){
 const node=$('toast'); node.textContent=message;node.classList.toggle('error',error);node.classList.add('show');
 clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>node.classList.remove('show'),5500);
}
function showView(view,scroll=true){
 if(!['landing','studio','analytics','campaigns','library'].includes(view))view='landing';
 for(const node of document.querySelectorAll('.view'))node.classList.toggle('hidden',node.id!==view);
 if(scroll)window.scrollTo({top:0,behavior:'smooth'});
 if(view==='library')loadLibrary();
 if(view==='campaigns' && window.REPLAYD_campaigns)window.REPLAYD_campaigns.load();
 history.replaceState(null,'',view==='landing'?'#home':'#'+view);
}
function fmt(t){t=Math.max(0,Math.round(Number(t)||0));return `${Math.floor(t/60).toString().padStart(2,'0')}:${(t%60).toString().padStart(2,'0')}`;}
function editTime(seconds){
  const n=Math.max(0,Number(seconds)||0),minutes=Math.floor(n/60),secs=n-minutes*60;
  const whole=Math.floor(secs),frac=Math.round((secs-whole)*100);
  const safeFrac=frac===100?0:frac;
  const safeWhole=whole+(frac===100?1:0);
  const totalMinutes=minutes+Math.floor(safeWhole/60);
  return `${String(totalMinutes).padStart(2,'0')}:${String(safeWhole%60).padStart(2,'0')}${safeFrac?'.'+String(safeFrac).padStart(2,'0'):''}`;
}
function parseEditTime(value){
  const raw=String(value).trim(),parts=raw.split(':');
  // Backward compatibility with old unformatted seconds, always normalized on blur.
  if(parts.length===1) return /^\d+(?:\.\d{1,3})?$/.test(raw)?Number(raw):NaN;
  if(parts.length!==2 && parts.length!==3)return NaN;
  if(!parts.every((p,i)=>/^\d+$/.test(p)||(i===parts.length-1&&/^\d+\.\d{1,3}$/.test(p))))return NaN;
  const sec=Number(parts[parts.length-1]),min=Number(parts[parts.length-2]);
  if(sec>=60||min<0||(parts.length===3&&min>=60))return NaN;
  return parts.length===3?Number(parts[0])*3600+min*60+sec:min*60+sec;
}
function safeNum(n){return Number.isFinite(Number(n))?Number(n):0;}
for (const id of ['clip-start','clip-end']) {
  const input=$(id);
  input.addEventListener('blur',()=>{
    const secs=parseEditTime(input.value);
    if(Number.isFinite(secs)) input.value=editTime(secs);
  });
}

function setBusy(b,id=null,caption='Working…'){
 state.busy=b; ['analyze-btn','export-btn'].forEach(key=>{const button=$(key);button.disabled=b||!state.project;});
 if(id){const button=$(id); if(b){button.dataset.previous=button.textContent;button.textContent=caption;button.classList.add('loading');}else{button.textContent=button.dataset.previous||button.textContent;button.classList.remove('loading');}}
}
async function request(url,options={}){
 let response;
 try{response=await fetch(url,options);}catch(e){throw new Error('Cannot connect to the local backend. Check that REPLAYD is running.');}
 let data;try{data=await response.json();}catch(e){data=null;}
 if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:Array.isArray(data?.detail)?data.detail.map(e=>e.msg).join('; '):`Request failed (${response.status})`);
 return data;
}
function el(tag,klass,text){const n=document.createElement(tag);if(klass)n.className=klass;if(text!=null)n.textContent=String(text);return n;}
for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>showView(button.dataset.view));
$('brand-home').addEventListener('click',(e)=>{e.preventDefault();showView('landing')});
for(const item of document.querySelectorAll('[data-nav="landing"]'))item.addEventListener('click',()=>showView('landing',false));
$('hero-demo').addEventListener('click',()=>{showView('landing',false);$('workflow').scrollIntoView({behavior:'smooth'})});
$('threshold').addEventListener('input',e=>$('threshold-value').textContent=Number(e.target.value).toFixed(2));

async function useFile(file){
 if(!file)return;
 if(state.busy)return notify('Another operation is already running.',true);
 const ext=(file.name.split('.').pop()||'').toLowerCase();
 if(!['mp4','mov','mkv','webm'].includes(ext))return notify('Choose an MP4, MOV, MKV or WebM file.',true);
 if(file.size>350*1024*1024)return notify('This version supports video files up to 350 MB.',true);
 state.project=null;state.analysis=null;state.selected=null;
 $('video-name').textContent='UPLOADING VIDEO…';$('video-badge').textContent='UPLOAD IN PROGRESS';
 $('analyze-btn').disabled=true;$('export-btn').disabled=true;
 try{
   const form=new FormData();form.append('file',file,file.name);
   const project=await request('/api/projects',{method:'POST',body:form});
   applyProject(project);notify('Source loaded. Analyze moments or trim a clip manually.');
 }catch(err){$('video-name').textContent='NO SOURCE SELECTED';$('video-badge').textContent='UPLOAD FAILED';notify(err.message,true);}
}
$('video-file').addEventListener('change',e=>useFile(e.target.files[0]));
$('dropzone').addEventListener('dragover',e=>{e.preventDefault();e.currentTarget.classList.add('dragover')});
$('dropzone').addEventListener('dragleave',e=>e.currentTarget.classList.remove('dragover'));
$('dropzone').addEventListener('drop',e=>{e.preventDefault();e.currentTarget.classList.remove('dragover');useFile(e.dataTransfer.files[0])});
$('demo-file').addEventListener('click',async()=>{
 try{const r=await fetch('/api/demo-video');if(!r.ok)throw Error('Demo video unavailable');const blob=await r.blob();
 await useFile(new File([blob],'REPLAYD_demo.mp4',{type:'video/mp4'}));
 }catch(err){notify(err.message,true);}
});
function applyProject(project){
 state.project=project;state.analysis=project.analysis||null;state.selected=null;
 $('video-name').textContent=project.name.toUpperCase();
 $('video-badge').textContent='SOURCE READY';
 const player=$('player');player.src=project.preview_url;player.load();player.classList.remove('hidden');$('video-placeholder').classList.add('hidden');
 $('video-meta').textContent=`${fmt(project.duration)} • ${project.width} × ${project.height} • ${project.has_audio?'AUDIO DETECTED':'NO AUDIO TRACK'}`;
 $('clip-start').value='00:00';$('clip-end').value=editTime(Math.min(18,project.duration));
 $('selected-moment').textContent='MANUAL CLIP';$('analyze-btn').disabled=!project.has_audio;$('export-btn').disabled=false;
 $('candidate-count').textContent='0 CANDIDATES';$('signal-chart').className='signal-chart empty-chart';$('signal-chart').textContent='RUN ANALYSIS TO SEE THE SIGNAL';
 $('moments-list').replaceChildren(el('div','empty-moments','Run analysis to discover moments—or export a manual clip.'));
 if(state.analysis)showAnalysis(state.analysis);
}
$('analyze-btn').addEventListener('click',async()=>{
 if(!state.project)return notify('Select a source video first.',true);
 setBusy(true,'analyze-btn','Analyzing footage…');
 try{const data=await request(`/api/projects/${state.project.id}/analyze?threshold=${$('threshold').value}&max_candidates=${$('moment-limit').value}&mode=${$('footage-mode').value}`,{method:'POST'});
 state.analysis=data;showAnalysis(data);notify(`${data.candidates.length} suggested moments from audio and visual cuts. They are not confirmed goals; check the video before exporting.`);
 }catch(e){notify(e.message,true);}finally{setBusy(false,'analyze-btn');$('analyze-btn').disabled=!state.project?.has_audio;}
});
function showAnalysis(data){
 $('candidate-count').textContent=`${data.candidates.length} CANDIDATE${data.candidates.length!==1?'S':''}`;
 drawSignal(data);drawMoments(data.candidates);
}
function drawSignal(data){
 const root=$('signal-chart');root.replaceChildren();root.classList.remove('empty-chart');
 const w=900,h=152,pad=9,duration=data.duration||state.project.duration;
 const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('preserveAspectRatio','none');
 const grid=document.createElementNS(ns,'path');grid.setAttribute('d','M0 38H900 M0 76H900 M0 114H900');grid.setAttribute('stroke','#34503a');grid.setAttribute('stroke-width','1');grid.setAttribute('opacity','.6');svg.append(grid);
 const points=(data.waveform||[]).map(v=>`${(Math.min(1,v.time/duration)*w).toFixed(1)},${(h-pad-Math.min(1,Math.max(0,v.score))*(h-2*pad)).toFixed(1)}`);
 if(points.length){const line=document.createElementNS(ns,'polyline');line.setAttribute('points',points.join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','#a4ff39');line.setAttribute('stroke-width','2.7');line.setAttribute('vector-effect','non-scaling-stroke');svg.append(line);}
 for(const item of data.candidates){
 const x=Math.min(w-3,Math.max(3,item.timestamp/duration*w));const marker=document.createElementNS(ns,'line');marker.setAttribute('x1',x);marker.setAttribute('x2',x);marker.setAttribute('y1',0);marker.setAttribute('y2',h);marker.setAttribute('stroke',item.evidence?.startsWith('Visual-only')?'#91bed3':'#b9d388');marker.setAttribute('stroke-width',2);marker.style.cursor='pointer';
 marker.addEventListener('click',()=>selectCandidate(data.candidates.indexOf(item)));const title=document.createElementNS(ns,'title');title.textContent=`Candidate at ${fmt(item.timestamp)} — click to preview`;marker.append(title);svg.append(marker);
 }
 root.append(svg);
}
function drawMoments(items){
 const root=$('moments-list');root.replaceChildren();
 if(!items.length){root.append(el('div','empty-moments','No peaks above this threshold. Try a lower threshold or edit a manual clip.'));return;}
 items.forEach((item,i)=>{
 const row=el('button','moment-row');row.type='button';row.dataset.index=String(i);
 const number=el('span','moment-index',String(i+1).padStart(2,'0'));
 const info=el('div','moment-info');info.append(el('strong',null,`${item.evidence?.startsWith('Visual-only')?'Scene-change suggestion':'Audio activity'} · ${fmt(item.timestamp)}`),el('small',null,`${fmt(item.start)} – ${fmt(item.end)} · ${item.evidence||'Review suggested moment'}`));
 const score=el('span','moment-score',String(Math.round(item.fused_score*100)));
 row.append(number,info,score);row.addEventListener('click',()=>selectCandidate(i));root.append(row);
 });
 selectCandidate(0);
}
function selectCandidate(i){
 const item=state.analysis?.candidates?.[i];if(!item)return;
 state.selected=i;$('clip-start').value=editTime(item.start);$('clip-end').value=editTime(item.end);
 $('selected-moment').textContent=`CANDIDATE ${String(i+1).padStart(2,'0')} / ${fmt(item.timestamp)}`;
 document.querySelectorAll('.moment-row').forEach(n=>n.classList.toggle('active',Number(n.dataset.index)===i));
 const player=$('player');if(player.readyState>0)player.currentTime=item.timestamp;
}
$('export-btn').addEventListener('click',async()=>{
 if(!state.project)return notify('Upload footage first.',true);
 const start=parseEditTime($('clip-start').value),end=parseEditTime($('clip-end').value),dur=state.project.duration;
 if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||start>=end||end>dur+0.01)return notify('Use MM:SS (for example 03:45.25). Start must be before end and within the source.',true);
 if(end-start<1||end-start>90)return notify('Clips must be between 1 and 90 seconds.',true);
 $('clip-start').value=editTime(start);$('clip-end').value=editTime(end);
 setBusy(true,'export-btn','Rendering your clip…');$('export-feedback').textContent='Rendering locally with FFmpeg; longer exports may take time.';
 try{
  const out=await request(`/api/projects/${state.project.id}/clips`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start,end,layout:$('clip-layout').value})});
  const last=$('last-export');last.replaceChildren();const info=el('div','',`${fmt(out.start)} → ${fmt(out.end)} · ${out.layout}`);
  const a=el('a','btn btn-primary btn-sm','↓ Download MP4');a.href=out.url;last.append(info,a);
  $('export-feedback').textContent='Export complete. Download your new MP4 from the left.';
  notify('Clip rendered successfully. Your MP4 is ready.');
 }catch(e){$('export-feedback').textContent='Export failed; review the error and try again.';notify(e.message,true);}finally{setBusy(false,'export-btn');}
});

async function loadLibrary(){
 try{const [projects,clips]=await Promise.all([request('/api/projects'),request('/api/clips')]);
 const p=$('projects-list'),c=$('clips-list');p.replaceChildren();c.replaceChildren();
 if(!projects.length)p.append(el('div','empty-mini','No local projects yet. Start in Creator Studio.'));
 for(const item of projects){const row=el('div','library-row');const info=el('div');info.append(el('strong',null,item.name),el('small',null,`${fmt(item.duration)} · ${item.analyzed?'Analyzed':'Not analyzed'}`));const button=el('button',null,'OPEN ↗');button.addEventListener('click',async()=>{try{applyProject(await request(`/api/projects/${item.id}`));showView('studio');}catch(e){notify(e.message,true);}});row.append(info,button);p.append(row);}
 if(!clips.length)c.append(el('div','empty-mini','No rendered clips yet.'));
 for(const item of clips){const row=el('div','library-row');const info=el('div');info.append(el('strong',null,`REPLAYD_${item.id.slice(0,8)}.mp4`),el('small',null,`${fmt(item.start)} — ${fmt(item.end)} · ${item.layout}`));const link=el('a',null,'DOWNLOAD ↓');link.href=item.url;row.append(info,link);c.append(row);}
 }catch(e){notify(e.message,true);}
}
if(['studio','analytics','campaigns','library'].includes(location.hash.slice(1)))showView(location.hash.slice(1),false);
