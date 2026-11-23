/* REPLAYD Campaign Hub — no external account or API. Creator controls all entries. */
(() => {
  const $c = id => document.getElementById(id);
  const hub = { list: [], activeId: null, detail: null, editingCampaign: null, editingSubmission: null, busy: false, sourceFilter: 'All' };
  const money = v => '$' + Number(v || 0).toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2});
  const count = v => Number(v || 0).toLocaleString('en-US');
  const localDate = () => {const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`};
  const optionalNum = id => $c(id).value.trim()===''?null:Number($c(id).value);
  const labelType = v => ({logo:'LOGO PLACEMENT',music:'MUSIC PLACEMENT',both:'LOGO + MUSIC'})[v] || v;
  function field(elId,value){$c(elId).value=value ?? ''}
  function textNode(tag,klass,text){return el(tag,klass,text)}
  function turnOffForms(){ $c('campaign-form-panel').classList.add('hidden');$c('submission-form-panel').classList.add('hidden');}
  async function loadCampaigns(){
    try{
      hub.list=await request('/api/campaigns');
      drawRoster(); drawPortfolio();
      if(!hub.activeId && hub.list.length)hub.activeId=hub.list[0].id;
      if(hub.activeId && hub.list.some(x=>x.id===hub.activeId))await openCampaign(hub.activeId,false);
      else{
        hub.activeId=null;hub.detail=null;
        $c('campaign-detail').classList.add('hidden');$c('campaign-empty').classList.remove('hidden');
      }
    }catch(e){notify(e.message,true)}
  }
  function drawPortfolio(){
    const container=$c('campaign-overview');container.replaceChildren();
    const gross=hub.list.reduce((acc,x)=>acc+Number(x.confirmed_earnings_usd),0);
    const paid=hub.list.reduce((acc,x)=>acc+Number(x.settled_usd),0);
    const outstanding=hub.list.reduce((acc,x)=>acc+Number(x.outstanding_usd),0);
    const items=[['CAMPAIGNS',count(hub.list.length)],['CONFIRMED EARNINGS',money(gross)],['SETTLED PAYMENTS',money(paid)],['OUTSTANDING',money(outstanding)]];
    for(const [name,value] of items){const item=el('div','campaign-stat');item.append(el('small',null,name),el('strong',null,value));container.append(item)}
  }
  function drawRoster(){
    const container=$c('campaign-list');container.replaceChildren();
    if(!hub.list.length){container.append(el('div','empty-mini','No campaigns yet. Create your first paid clipping campaign.'));return}
    for(const c of hub.list){
      if(hub.sourceFilter!=='All'&&c.source_platform!==hub.sourceFilter)continue;
      const button=el('button','campaign-roster-item'+(c.id===hub.activeId?' selected':''));button.type='button';
      const head=el('div','campaign-roster-head');head.append(el('strong',null,c.title),el('span','status-label status-'+c.status,c.status.toUpperCase()));
      const sub=el('small',null,`${c.source_platform} · ${c.brand} · ${labelType(c.requirement_type)} · ${money(c.rpm_usd)}/1M`);
      const foot=el('div','campaign-roster-footer');foot.append(el('span',null,`${count(c.submission_count)} clips`),el('b',null,`${money(c.outstanding_usd)} due`));
      button.append(head,sub,foot);button.addEventListener('click',()=>openCampaign(c.id));container.append(button);
    }
  }
  async function openCampaign(id, closeForms=true){
    hub.activeId=id;
    if(closeForms)turnOffForms();
    try{hub.detail=await request('/api/campaigns/'+encodeURIComponent(id));renderDetails();drawRoster();}
    catch(e){notify(e.message,true)}
  }
  function renderDetails(){
    const c=hub.detail;
    $c('campaign-empty').classList.add('hidden');$c('campaign-detail').classList.remove('hidden');
    $c('campaign-active-name').textContent=c.title.toUpperCase();
    $c('campaign-active-subtitle').textContent=`${c.source_platform} · ${c.brand} · ${c.submission_count} logged submissions`;
    $c('campaign-marketplace-tag').textContent='SOURCE: '+c.source_platform.toUpperCase();
    $c('campaign-requirement-tag').textContent=labelType(c.requirement_type);
    $c('campaign-rpm-tag').textContent=money(c.rpm_usd)+' / 1M ELIGIBLE VIEWS';
    $c('campaign-duration-tag').textContent=`PREFERRED ${c.min_duration_sec}–${c.max_duration_sec}s`;
    $c('campaign-cap-tag').textContent=c.payout_cap_usd===null?'':`CAP ${money(c.payout_cap_usd)}`;
    $c('campaign-cap-tag').classList.toggle('hidden',c.payout_cap_usd===null);
    field('campaign-status',c.status);
    $c('campaign-notes-display').textContent=c.notes||'';
    $c('campaign-notes-display').classList.toggle('hidden',!c.notes);
    const metrics=[['APPROVED ELIGIBLE VIEWS',count(c.approved_eligible_views)],['CONFIRMED EARNINGS',money(c.confirmed_earnings_usd)],['PENDING / UNAPPROVED',money(c.additional_pending_usd)],['PAYMENTS RECEIVED',money(c.settled_usd)],['STILL OUTSTANDING',money(c.outstanding_usd)],['EARNED / EDIT HOUR',c.earned_usd_per_edit_hour==null?'—':money(c.earned_usd_per_edit_hour)]];
    const wrap=$c('campaign-metric-cards');wrap.replaceChildren();
    metrics.forEach(([label,value],i)=>{const node=el('div','campaign-stat'+(i===4?' focus':''));node.append(el('small',null,label),el('strong',null,value));wrap.append(node)});
    if(Number(c.advance_usd)>0){const note=el('p','campaign-advance',`Payments exceed currently confirmed earnings by ${money(c.advance_usd)} (possible advance or data mismatch).`);wrap.append(note)}
    drawSubmissions();drawPayments();
  }
  function drawSubmissions(){
    const wrap=$c('campaign-submissions-list');wrap.replaceChildren();
    const c=hub.detail;
    if(!c.submissions.length){wrap.append(el('p','empty-mini','No clips submitted yet. Add an edit or published Reel to begin tracking.'));return}
    const table=el('table','campaign-table');
    const head=el('thead');const row=el('tr');for(const k of ['CLIP / PLATFORM','PUBLIC / ELIGIBLE','STATUS','ESTIMATE','ACTION'])row.append(el('th',null,k));head.append(row);table.append(head);
    const body=el('tbody');
    for(const s of c.submissions){
      const tr=el('tr');const info=el('td');info.append(el('strong',null,s.title),el('small',null,s.platform+(s.posted_on?' · '+s.posted_on:'')+(s.clip_id?' · Linked export':'')));
      if(s.duration_within_preference===false)info.append(el('small','warning-text',`⚠ Duration ${s.duration_sec}s outside preferred range`));
      const view=el('td');view.append(el('strong',null,`${s.public_views==null?'—':count(s.public_views)} / ${count(s.eligible_views)}`),el('small',null,'Public / eligible'));
      const status=el('td');status.append(el('span','status-label status-'+s.status,s.status.toUpperCase()));
      const estimate=el('td');estimate.append(el('strong',null,money(s.estimated_usd)),el('small',null,s.status==='approved'?'Approved · before campaign cap':'Not yet confirmed'));
      const action=el('td');const editButton=el('button','campaign-small-button','EDIT ↗');editButton.type='button';editButton.addEventListener('click',()=>showSubmissionForm(s));action.append(editButton);
      tr.append(info,view,status,estimate,action);body.append(tr);
    }
    table.append(body);wrap.append(table);
  }
  function drawPayments(){
    const wrap=$c('campaign-payments-list');wrap.replaceChildren();
    if(!hub.detail.payments.length){wrap.append(el('p','empty-mini','No payments recorded. Approved earnings do not automatically count as received.'));return}
    for(const p of hub.detail.payments){const row=el('div','payment-row'+(p.voided_at?' voided':''));
      const info=el('div');info.append(el('strong',null,p.paid_on),el('small',null,(p.reference||'Payment received')+(p.voided_at?' · VOIDED: '+p.void_reason:'')));
      const amount=el('b',null,money(p.amount_usd));row.append(info,amount);
      if(!p.voided_at){const voidBtn=el('button','campaign-small-button danger-outline','VOID');voidBtn.type='button';voidBtn.addEventListener('click',async()=>{
          const reason=window.prompt('Reason for voiding this payment entry (required):');if(reason==null)return;
          if(reason.trim().length<3)return notify('Enter a reason of at least 3 characters.',true);
          try{await request(`/api/campaigns/${hub.activeId}/payments/${p.id}/void`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:reason.trim()})});await loadCampaigns();notify('Mistaken payment voided; original entry retained in history.');}
          catch(e){notify(e.message,true)}
        });row.append(voidBtn)}
      wrap.append(row)}
  }
  function newCampaign(c=null){
    turnOffForms();hub.editingCampaign=c?.id||null;
    $c('campaign-form-title').textContent=c?'EDIT CAMPAIGN SETTINGS':'NEW PAID CAMPAIGN';
    field('camp-title',c?.title||'');field('camp-brand',c?.brand||'');field('camp-source',c?.source_platform||'Direct');field('camp-type',c?.requirement_type||'logo');
    field('camp-rpm',c?.rpm_usd||'');field('camp-min',c?.min_duration_sec??15);field('camp-max',c?.max_duration_sec??60);
    field('camp-cap',c?.payout_cap_usd||'');field('camp-notes',c?.notes||'');
    $c('campaign-save').textContent=c?'Save changes ↗':'Create campaign ↗';
    $c('campaign-form-panel').classList.remove('hidden');$c('campaign-form-panel').scrollIntoView({behavior:'smooth',block:'start'});
  }
  async function submitCampaign(e){
    e.preventDefault();if(hub.busy)return;
    const data={title:$c('camp-title').value.trim(),brand:$c('camp-brand').value.trim(),source_platform:$c('camp-source').value,requirement_type:$c('camp-type').value,
      rpm_usd:$c('camp-rpm').value,min_duration_sec:Number($c('camp-min').value),max_duration_sec:Number($c('camp-max').value),
      payout_cap_usd:$c('camp-cap').value.trim()===''?null:$c('camp-cap').value,notes:$c('camp-notes').value.trim()};
    if(data.min_duration_sec>data.max_duration_sec)return notify('Minimum duration cannot exceed maximum duration.',true);
    hub.busy=true;$c('campaign-save').disabled=true;
    try{
      const url=hub.editingCampaign?'/api/campaigns/'+hub.editingCampaign:'/api/campaigns';
      const result=await request(url,{method:hub.editingCampaign?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      hub.activeId=result.id;hub.sourceFilter='All';field('campaign-source-filter','All');turnOffForms();await loadCampaigns();notify('Campaign saved in your local library.');
    }catch(err){notify(err.message,true)}finally{hub.busy=false;$c('campaign-save').disabled=false}
  }
  async function showSubmissionForm(s=null){
    if(!hub.activeId)return;
    turnOffForms();hub.editingSubmission=s?.id||null;
    $c('submission-form-title').textContent=s?'UPDATE CLIP / REEL':'LOG A CLIP / REEL';
    field('sub-title',s?.title||'');field('sub-platform',s?.platform||'Instagram');
    field('sub-url',s?.post_url||'');field('sub-date',s?.posted_on||'');field('sub-duration',s?.duration_sec??'');
    field('sub-public',s?.public_views??'');field('sub-eligible',s?.eligible_views??0);field('sub-status',s?.status||'submitted');
    field('sub-minutes',s?.edit_minutes??'');field('sub-notes',s?.notes||'');
    const sel=$c('sub-clip');sel.replaceChildren(new Option('Not linked / edited elsewhere',''));
    try{const clips=await request('/api/clips');for(const clip of clips)sel.append(new Option(`REPLAYD_${clip.id.slice(0,8)} · ${Math.round(clip.end-clip.start)}s`,clip.id));}
    catch(err){notify('Could not load library clips. You can still log this post.',true)}
    field('sub-clip',s?.clip_id||'');sel.disabled=Boolean(s);
    $c('submission-save').textContent=s?'Update submission ↗':'Save submission ↗';
    $c('submission-form-panel').classList.remove('hidden');$c('submission-form-panel').scrollIntoView({behavior:'smooth',block:'center'});
  }
  async function saveSubmission(e){
    e.preventDefault();if(hub.busy||!hub.activeId)return;
    const data={title:$c('sub-title').value.trim(),platform:$c('sub-platform').value,post_url:$c('sub-url').value.trim(),
      posted_on:$c('sub-date').value||null,duration_sec:optionalNum('sub-duration'),public_views:optionalNum('sub-public'),
      eligible_views:Number($c('sub-eligible').value),status:$c('sub-status').value,edit_minutes:optionalNum('sub-minutes'),notes:$c('sub-notes').value.trim()};
    if(!hub.editingSubmission)data.clip_id=$c('sub-clip').value||null;
    if(data.public_views!==null && data.eligible_views>data.public_views)return notify('Eligible views cannot exceed public views. Leave public views blank if unknown.',true);
    if(data.post_url&&!/^https?:\/\//i.test(data.post_url))return notify('Use an http(s) post link, or leave it blank.',true);
    hub.busy=true;$c('submission-save').disabled=true;
    try{
      const id=hub.activeId, url='/api/campaigns/'+id+'/submissions'+(hub.editingSubmission?'/'+hub.editingSubmission:'');
      await request(url,{method:hub.editingSubmission?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      $c('submission-form-panel').classList.add('hidden');await loadCampaigns();
      notify('Submission saved. Approved eligible views now determine confirmed earnings.');
    }catch(err){notify(err.message,true)}finally{hub.busy=false;$c('submission-save').disabled=false}
  }
  async function submitPayment(e){
    e.preventDefault();if(hub.busy||!hub.activeId)return;
    const amount=$c('pay-amount').value;if(!amount)return;
    hub.busy=true;
    try{await request(`/api/campaigns/${hub.activeId}/payments`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      amount_usd:amount,paid_on:$c('pay-date').value,reference:$c('pay-reference').value.trim(),notes:$c('pay-notes').value.trim()})});
      $c('payment-form').reset();field('pay-date',localDate());await loadCampaigns();notify('Payment logged. Settlement balance updated.');
    }catch(err){notify(err.message,true)}finally{hub.busy=false}
  }
  $c('campaign-source-filter').addEventListener('change',async e=>{
    hub.sourceFilter=e.target.value;
    const matching=hub.list.filter(x=>hub.sourceFilter==='All'||x.source_platform===hub.sourceFilter);
    if(!matching.length){hub.activeId=null;hub.detail=null;$c('campaign-detail').classList.add('hidden');$c('campaign-empty').classList.remove('hidden');$c('campaign-empty').querySelector('p').textContent='No campaigns for this marketplace yet. Create one or choose another source.';}
    else if(!matching.some(x=>x.id===hub.activeId)){hub.activeId=matching[0].id;await openCampaign(hub.activeId)}
    drawRoster();
  });
  $c('campaign-new').addEventListener('click',()=>newCampaign());
  $c('campaign-empty-new').addEventListener('click',()=>newCampaign());
  $c('campaign-edit').addEventListener('click',()=>newCampaign(hub.detail));
  $c('campaign-cancel').addEventListener('click',()=>turnOffForms());
  $c('submission-cancel').addEventListener('click',()=>turnOffForms());
  $c('campaign-form').addEventListener('submit',submitCampaign);
  $c('submission-form').addEventListener('submit',saveSubmission);
  $c('payment-form').addEventListener('submit',submitPayment);
  $c('campaign-add-submission').addEventListener('click',()=>showSubmissionForm());
  $c('campaign-demo-fields').addEventListener('click',()=>{field('camp-title','Matchday demo campaign');field('camp-brand','Example Sports (synthetic)');field('camp-source','Clipster');field('camp-type','both');field('camp-rpm','300');field('camp-min','15');field('camp-max','45');field('camp-cap','500');field('camp-notes','TEST DATA ONLY — logo top right, supplied soundtrack. Campaign terms must be confirmed with the real advertiser.');});
  $c('campaign-update-status').addEventListener('click',async()=>{
    if(!hub.activeId)return;
    try{await request(`/api/campaigns/${hub.activeId}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:$c('campaign-status').value})});await loadCampaigns();notify('Campaign status updated.');}catch(err){notify(err.message,true)}
  });
  field('pay-date',localDate());
  window.REPLAYD_campaigns={load:loadCampaigns};
  if(location.hash.slice(1)==='campaigns')loadCampaigns();
})();
