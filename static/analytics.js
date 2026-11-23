/* REPLAYD Intelligence v0.4 — fully local, no external API, no fabricated analytics. */
(()=>{
'use strict';
const $=id=>document.getElementById(id);
const number=(value,digits=0)=>value==null?'—':Number(value).toLocaleString(undefined,{maximumFractionDigits:digits});
const safe=(str)=>String(str??'');
const median=(a)=>{if(!a.length)return null;const sorted=[...a].sort((x,y)=>x-y);const i=Math.floor(sorted.length/2);return Math.round((sorted.length%2?sorted[i]:(sorted[i-1]+sorted[i])/2)*100)/100;};
const ratio=(n,d,m=1)=>n==null||d==null||d<=0?null:Math.round(n/d*m*100)/100;
let store={posts:[],coverage:{},demo_posts:0};let selection={platform:'all',type:'all',metric:'median_saves_1000'};let busy=false;
function msg(text,isError=false){const box=$('analytics-import-feedback');box.textContent=text;box.classList.toggle('error',isError);}
function make(tag,cls,text){const element=document.createElement(tag);if(cls)element.className=cls;if(text!=null)element.textContent=String(text);return element;}
async function api(url,options={}){
  let response;try{response=await fetch(url,options);}catch(e){throw Error('REPLAYD local server is unavailable. Check Terminal.');}
  const data=await response.json().catch(()=>null);
  if(!response.ok)throw Error(typeof data?.detail==='string'?data.detail:`Request failed (${response.status})`);
  return data;
}
function rateFields(post){
  const v=post.views;
  return {...post,shares_per_1000_views:ratio(post.shares,v,1000),saves_per_1000_views:ratio(post.saves,v,1000),likes_per_100_views:ratio(post.likes,v,100),
    interactions_per_100_views:['likes','comments','shares','saves'].every(k=>post[k]!=null)?ratio(post.likes+post.comments+post.shares+post.saves,v,100):null,
    average_watch_to_length_pct:ratio(post.avg_watch_sec,post.duration_sec,100)};
}
function selectedPosts(){return store.posts.filter(p=>(selection.platform==='all'||p.platform===selection.platform)&&(selection.type==='all'||p.content_type===selection.type));}
function metricEntries(posts,key){return posts.map(p=>p[key]).filter(v=>v!=null&&Number.isFinite(Number(v))).map(Number);}
function totals(posts,key){const v=metricEntries(posts,key);return v.length?v.reduce((a,b)=>a+b,0):null;}
function count(posts,key){return posts.filter(p=>p[key]!=null&&p[key]!=='').length;}
function updateFilters(){
  const setSelect=(id,field,selected)=>{const select=$(id);const opts=[...new Set(store.posts.map(p=>p[field]).filter(Boolean))].sort();select.replaceChildren();select.add(new Option(field==='platform'?'All platforms':'All content types','all'));for(const value of opts)select.add(new Option(value.replaceAll('_',' '),value));select.value=opts.includes(selected)?selected:'all';return select.value;};
  selection.platform=setSelect('analytics-platform-filter','platform',selection.platform);
  selection.type=setSelect('analytics-type-filter','content_type',selection.type);
}
function renderStats(posts){
  $('analytics-post-count').textContent=`${number(posts.length)} POST${posts.length===1?'':'S'}`;
  const rates={shares:metricEntries(posts,'shares_per_1000_views'),saves:metricEntries(posts,'saves_per_1000_views'),likes:metricEntries(posts,'likes_per_100_views')};
  const cards=[
    ['REELS TRACKED',posts.length,'Recorded football posts','white'],
    ['TOTAL VIEWS',totals(posts,'views'),`${count(posts,'views')} / ${posts.length} posts`,'white'],
    ['TOTAL SAVES',totals(posts,'saves'),`${count(posts,'saves')} / ${posts.length} posts`,'white'],
    ['SAVES / 1K VIEWS',median(rates.saves),`${rates.saves.length} measurable reels · median`,'lime'],
    ['SHARES / 1K VIEWS',median(rates.shares),`${rates.shares.length} measurable reels · median`,'white'],
    ['LIKES / 100 VIEWS',median(rates.likes),`${rates.likes.length} measurable reels · median`,'white']
  ];
  const root=$('analytics-metric-cards');root.replaceChildren();
  for(const [label,value,detail,accent] of cards){const card=make('div',`analytics-mini-card ${accent}`);card.append(make('small',null,label),make('strong',null,number(value,2)),make('span',null,detail));root.append(card);}
  const coverage=$('analytics-coverage');coverage.replaceChildren();
  for(const [key,label] of [['views','Views'],['shares','Shares'],['saves','Saves'],['content_type','Category'],['duration_sec','Duration'],['avg_watch_sec','Watch time'],['published_at','Post date']]){
    const n=count(posts,key);const element=make('span','coverage-chip');if(n===posts.length&&posts.length)element.classList.add('complete');else if(n===0)element.classList.add('missing');element.textContent=`${label} ${n}/${posts.length}`;coverage.append(element);
  }
  $('analytics-source-badge').textContent=store.demo_posts?`${store.demo_posts} DEMO POST${store.demo_posts===1?'':'S'} · SYNTHETIC`:'CREATOR-ENTERED RECORDS';
  $('analytics-source-badge').classList.toggle('demo',store.demo_posts>0);
}
function bucket(post){const v=post.duration_sec;if(v==null||v<=0)return null;return v<15?'<15 sec':v<=30?'15–30 sec':v<=60?'31–60 sec':'>60 sec';}
function weekday(post){if(!post.published_at)return null;const date=new Date(`${String(post.published_at).slice(0,10)}T12:00:00`);return Number.isNaN(+date)?null:['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][date.getDay()];}
function group(posts,field){const groups=new Map();for(const p of posts){let key=field==='duration_bucket'?bucket(p):field==='weekday'?weekday(p):p[field];if(key==null||key==='unspecified'||key==='')continue;const k=String(key);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(p);}return [...groups].map(([name,items])=>({name,items,posts:items.length}));}
function graph(rootId,posts,field,metric='median_saves_1000'){
  const root=$(rootId);root.replaceChildren();let groups=group(posts,field);
  const metricKey=metric==='median_saves_1000'?'saves_per_1000_views':metric==='median_views'?'views':'shares_per_1000_views';
  const available=groups.map(g=>{const vals=metricEntries(g.items,metricKey);return {...g,value:vals.length>=3?median(vals):null,valid:vals.length};}).filter(g=>g.value!=null);
  if(!available.length){const div=make('div','chart-empty');div.append(make('span',null,'◌'),make('strong',null,'NOT ENOUGH MATCHED DATA'),make('p',null,'Add at least 3 posts in a group with the required metrics to compare reliably.'));root.append(div);return;}
  available.sort((a,b)=>b.value-a.value);const max=Math.max(1,...available.map(i=>i.value));
  for(const [index,g] of available.slice(0,7).entries()){
    const row=make('div','v3-chart-row');const title=make('div','v3-chart-meta');title.append(make('span',null,g.name),make('small',null,`${g.valid} matched · ${g.posts} posts`));
    const right=make('strong',null,number(g.value,2));title.append(right);const track=make('div','v3-bar-track');const bar=make('div',`v3-bar-fill bar-${index%4}`);bar.style.width=`${Math.max(3,g.value/max*100)}%`;track.append(bar);row.append(title,track);root.append(row);
  }
}
function takeaways(posts){const root=$('analytics-recommendations-list');root.replaceChildren();const notes=[];
  const types=group(posts,'content_type').map(g=>({label:g.name,n:metricEntries(g.items,'saves_per_1000_views').length,save:median(metricEntries(g.items,'saves_per_1000_views'))})).filter(g=>g.n>=3).sort((a,b)=>b.save-a.save);
  if(types.length>=2)notes.push(['✳','Football edits fans save',`${types[0].label} leads the measured football categories at ${number(types[0].save,2)} median saves per 1K views (${types[0].n} posts). Try a few more comparable edits before treating this as a trend.`]);
  if(count(posts,'saves')<posts.length)notes.push(['i','Save counts are missing for some Reels',`Saves were supplied for ${count(posts,'saves')}/${posts.length} posts. Missing saves are unknown, not zero. Some platforms do not expose saves.`]);
  const durations=count(posts,'duration_sec');
  if(durations<3)notes.push(['↗','Do shorter edits earn more saves?','Add duration for 3+ posts per length group to compare save rates for quick edits versus longer highlights.']);
  if(!types.length)notes.push(['↗','Compare goals, skills and comebacks','Add a content type and view/save counts for at least 3 similar posts in each category to see meaningful differences.']);
  if(store.demo_posts)notes.push(['!','Synthetic demo data present',`${store.demo_posts} demo posts are mixed into the local collection. Remove them before drawing conclusions about your real content.`]);
  if(!notes.length)notes.push(['✓','Use findings as experiments','These are descriptive associations, not proof that a particular editing choice causes more views.']);
  for(const [icon,title,body] of notes.slice(0,4)){const card=make('div','analytics-tip');card.append(make('span','tip-icon',icon));const text=make('div');text.append(make('strong',null,title),make('p',null,body));card.append(text);root.append(card);}
}
function topSavedReels(posts){
  const root=$('analytics-day-chart');root.replaceChildren();
  const eligible=posts.filter(p=>p.views>=1000&&p.saves!=null&&p.saves_per_1000_views!=null)
    .sort((a,b)=>b.saves_per_1000_views-a.saves_per_1000_views).slice(0,7);
  if(!eligible.length){root.append(make('div','chart-empty','Add views and saves to see the football posts your audience bookmarks most.'));return;}
  const max=Math.max(1,...eligible.map(p=>p.saves_per_1000_views));
  for(const [index,p] of eligible.entries()){
    const row=make('div','v3-chart-row');const title=make('div','v3-chart-meta');
    title.append(make('span',null,`${p.clip_id} · ${p.content_type||'football reel'}`),make('small',null,`${number(p.saves)} saves · ${number(p.views)} views`),make('strong',null,number(p.saves_per_1000_views,2)));
    const track=make('div','v3-bar-track'),bar=make('div',`v3-bar-fill bar-${index%4}`);bar.style.width=`${Math.max(3,p.saves_per_1000_views/max*100)}%`;
    track.append(bar);row.append(title,track);root.append(row);
  }
}
function watchDepth(posts){const root=$('analytics-watch-depth');root.replaceChildren();const measurable=posts.filter(p=>p.average_watch_to_length_pct!=null);if(!measurable.length){root.append(make('div','watch-no-data','Provide average watch time AND duration to reveal viewing-depth patterns. Both are optional.'));return;}
  const pct=median(measurable.map(p=>p.average_watch_to_length_pct));const stat=make('div','watch-stat');stat.append(make('strong',null,`${number(pct,1)}%`),make('span',null,'Median average watch time ÷ clip length'));root.append(stat);
  const progress=make('div','watch-progress');const fill=make('div');fill.style.width=`${Math.min(100,Math.max(0,pct))}%`;progress.append(fill);root.append(progress);
  root.append(make('p','hint',`Based on ${measurable.length} posts. This is a viewing-depth proxy, not completion rate; values above 100% can occur with replays.`));
}
function renderPosts(posts){const root=$('analytics-posts-table');root.replaceChildren();$('analytics-table-meta').textContent=`${posts.length} RECORDS · LATEST FIRST`;
  const table=make('table','analytics-records');const head=make('thead');const header=make('tr');for(const name of ['REEL','PLATFORM','FOOTBALL TYPE','VIEWS','SAVES','SAVES/1K','SHARES/1K','SOURCE',''])header.append(make('th',null,name));head.append(header);table.append(head);const body=make('tbody');
  for(const post of posts.slice(0,150)){const tr=make('tr');tr.append(make('td',null,post.clip_id),make('td',null,post.platform),make('td',null,post.content_type||'—'),make('td',null,number(post.views)),make('td',null,number(post.saves)),make('td',null,number(post.saves_per_1000_views,2)),make('td',null,number(post.shares_per_1000_views,2)));
    const source=make('td');source.append(make('span',post.is_demo?'demo-indicator':'real-indicator',post.is_demo?'SIMULATED':'ENTERED'));tr.append(source);
    const action=make('td');const button=make('button','delete-analytics-post','×');button.type='button';button.title=`Remove ${post.clip_id}`;button.setAttribute('aria-label',`Delete post ${post.clip_id}`);button.addEventListener('click',async()=>{if(!confirm(`Delete ${post.clip_id}? This only removes the analytics record.`))return;try{const r=await fetch(`/api/analytics/posts/${encodeURIComponent(post.id)}`,{method:'DELETE'});if(!r.ok)throw Error(`Delete failed (${r.status})`);msg('Post deleted.');await refresh();}catch(e){msg(e.message,true);}});action.append(button);tr.append(action);body.append(tr);
  }table.append(body);root.append(table);
}
function render(){const posts=selectedPosts();renderStats(posts);$('analytics-empty').classList.toggle('hidden',store.posts.length>0);$('analytics-filled').classList.toggle('hidden',store.posts.length===0);if(!store.posts.length)return;
  graph('analytics-content-chart',posts,'content_type',selection.metric);graph('analytics-platform-chart',posts,'platform','median_saves_1000');graph('analytics-length-chart',posts,'duration_bucket','median_saves_1000');topSavedReels(posts);takeaways(posts);watchDepth(posts);renderPosts(posts);
}
async function refresh(){const data=await api('/api/analytics/overview');store={...data,posts:data.posts.map(rateFields)};updateFilters();render();}
async function importFile(file){if(!file)return;if(busy)return;busy=true;msg(`Importing ${file.name}…`);try{const form=new FormData();form.append('file',file,file.name);const data=await api('/api/analytics/import',{method:'POST',body:form});const info=data.import_info;msg(`Imported ${info.new} new · updated ${info.updated} existing. Mapped: ${info.matched_columns.join(', ')}.`);await refresh();}catch(e){msg(e.message,true);}finally{busy=false;$('analytics-file').value='';}}
function entryMode(mode){for(const button of document.querySelectorAll('.entry-tab'))button.classList.toggle('active',button.dataset.entry===mode);for(const name of ['manual','upload','paste'])$(name==='manual'?'analytics-manual-form':`analytics-${name}-form`).classList.toggle('hidden',name!==mode);}
for(const button of document.querySelectorAll('.entry-tab'))button.addEventListener('click',()=>entryMode(button.dataset.entry));
$('analytics-platform-filter').addEventListener('change',e=>{selection.platform=e.target.value;render();});
$('analytics-type-filter').addEventListener('change',e=>{selection.type=e.target.value;render();});
$('analytics-metric-select').addEventListener('change',e=>{selection.metric=e.target.value;render();});
$('analytics-file').addEventListener('change',e=>importFile(e.target.files[0]));
$('analytics-manual-form').addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;const form=new FormData(e.target);const values=Object.fromEntries(form.entries());const numeric=['views','likes','shares','saves','comments','reach','duration_sec','avg_watch_sec'];for(const key of numeric){values[key]=values[key]!==''?Number(values[key]):null;}
  if(!numeric.some(key=>values[key]!=null)){msg('Add at least one count (views, likes, shares, saves, comments or reach).',true);return;}
  if(!values.published_at)values.published_at=null;if(!values.clip_id)values.clip_id=null;if(!values.content_type)values.content_type=null;
  busy=true;try{await api('/api/analytics/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});msg('Post saved locally. Analysis updated.');e.target.reset();await refresh();}catch(err){msg(err.message,true);}finally{busy=false;}
});
$('analytics-paste-submit').addEventListener('click',async()=>{
  const str=$('analytics-paste-input').value.trim();if(!str){msg('Paste a table with a header row first.',true);return;}
  await importFile(new File([str],'pasted-insights.csv',{type:'text/csv'}));
});
$('analytics-demo-btn').addEventListener('click',async()=>{if(busy)return;try{const response=await fetch('/api/sample-analytics');if(!response.ok)throw Error('Sample dataset unavailable');const blob=await response.blob();await importFile(new File([blob],'REPLAYD_SYNTHETIC_144_posts.csv',{type:'text/csv'}));}catch(e){msg(e.message,true);}});
refresh().catch(e=>msg(e.message,true));
})();
