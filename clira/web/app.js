'use strict';
const $ = id => document.getElementById(id);
let session, state, channelId, conversationId = null, activeView = 'chat', busy = false;
const views = ['chat', 'library', 'ideas', 'production', 'approvals', 'community', 'operations', 'settings'];
const crumbs = {chat:'Your channel, in good hands.',library:'Every story has a home.',ideas:'Make space for what comes next.',production:'From a finished file to a reviewed upload.',approvals:'Nothing consequential without your say.',community:'Stay close to your audience.',operations:'See what happened. Know what comes next.',settings:'A workspace that knows your channel.'};

function el(tag, cls, value) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (value !== undefined) node.textContent = value;
  return node;
}
function clear(id) { $(id).replaceChildren(); return $(id); }
function toast(message, error = false) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  $('toast').classList.toggle('error', error);
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => { $('toast').hidden = true; }, error ? 12000 : 6000);
}
async function api(path, body, method = 'POST') {
  const response = await fetch(path, {method: body === undefined ? 'GET' : method,
    headers: {'Content-Type':'application/json', ...(session ? {'X-Clira-Token': session.token} : {})},
    body: body === undefined ? undefined : JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok || value.ok === false) {
    const error = value.error;
    throw new Error(error ? `${error.code}: ${error.message}` : `Request failed (${response.status})`);
  }
  return value;
}
async function tool(name, args = {}) {
  const result = await api('/api/tool', {channel_id: channelId, tool: name, arguments: args});
  await refresh();
  return result.data;
}
function button(text, handler, cls) {
  const b = el('button', cls, text); b.type = 'button';
  b.addEventListener('click', async () => {
    b.disabled = true;
    try { await handler(b); } catch (error) { toast(error.message, true); }
    finally { b.disabled = false; if(b.isConnected && document.activeElement===document.body)b.focus(); }
  });
  return b;
}
function empty(container, message) { container.append(el('div', 'empty', message)); }
function card(title, badge, description) {
  const c = el('article', 'card');
  if (badge) c.append(el('span', 'badge neutral', badge));
  c.append(el('h3', '', title));
  if (description) c.append(el('p', '', description));
  return c;
}
function details(label, data) {
  const d = el('details'); d.append(el('summary', '', label), el('pre', '', JSON.stringify(data, null, 2)));
  return d;
}
function dateLabel(value) { return value ? new Date(value).toLocaleString(undefined, {dateStyle:'medium',timeStyle:'short'}) : '—'; }
function showView(view) {
  activeView = view;
  for (const v of views) $('view-' + v).hidden = v !== view || (!channelId && v !== 'settings');
  $('emptyWorkspace').hidden = Boolean(channelId) || view === 'settings';
  document.querySelectorAll('nav button').forEach(b => {b.classList.toggle('active', b.dataset.view === view); b.setAttribute('aria-current', b.dataset.view === view ? 'page' : 'false');});
  $('viewCrumb').textContent = crumbs[view];
}
function addMessage(role, text, receipts) {
  const m = el('article', 'message ' + role);
  m.append(el('div', 'speaker', role === 'user' ? 'You' : session.name), el('div', 'body', text));
  if (receipts?.length) m.append(details(`${receipts.length} tool receipts · sources & outcomes`, receipts));
  $('messages').append(m);
}
async function sendMessage(text) {
  if (busy || !channelId) return;
  busy = true;
  $('sendButton').disabled = true;
  $('channelSelect').disabled = true;
  $('newChat').disabled = true;
  $('renameSession').disabled=true;$('sessionSearch').disabled=true;
  document.querySelectorAll('#sessionList button').forEach(b=>b.disabled=true);
  $('sendButton').textContent = 'Working…';
  addMessage('user', text);
  $('message').value = '';
  try {
    const result = await api('/api/chat', {channel_id: channelId, message: text, conversation_id: conversationId});
    conversationId = result.conversation_id;
    updateSessionContext(); await loadSessions();
    addMessage('assistant', result.message, result.receipts);
    await refresh();
  } catch (error) {
    addMessage('assistant', 'The request could not finish. ' + error.message);
    toast(error.message, true);
  } finally {
    busy = false;
    $('renameSession').disabled=false;$('sessionSearch').disabled=false;
    document.querySelectorAll('#sessionList button').forEach(b=>b.disabled=false);
    $('sendButton').disabled = false;
    $('channelSelect').disabled = false;
    $('newChat').disabled = false;
    $('sendButton').textContent = 'Send message ↗';
    $('message').focus();
  }
}
function renderMetrics() {
  const container = clear('metrics');
  const report = state.records.analytics[0];
  const metrics = report?.metrics || {};
  const data = [['Views',metrics.views,'views'],['Watch time',metrics.estimatedMinutesWatched,'minutes'],['Avg. view duration',metrics.averageViewDuration,'seconds'],['Subscribers gained',metrics.subscribersGained,'subscribers']];
  for (const [name,value,unit] of data) {
    const c = el('article');
    c.append(el('span','',name),el('strong','',value == null ? '—' : Number(value).toLocaleString()),el('small','',report ? `${unit} · ${report.freshness} · ${report.range_start} – ${report.range_end}` : 'No metrics fetched'));
    container.append(c);
  }
}
function renderVideos() {
  const container = clear('videos');
  for (const {video,observed_at} of state.records.video_cache) {
    const c = card(video.snippet.title,video.status?.privacyStatus || 'unknown');
    const views = video.statistics?.viewCount;
    c.append(el('p','',views == null ? 'Views unavailable' : `${Number(views).toLocaleString()} lifetime views`), el('small','',`${video.id} · observed ${dateLabel(observed_at)}`));
    c.append(details('Metadata & source record', video));
    if (session.mode === 'live') {
      const a = el('a','','Open on YouTube ↗'); a.href = 'https://www.youtube.com/watch?v=' + encodeURIComponent(video.id); a.target = '_blank'; a.rel = 'noopener noreferrer'; c.append(a);
    }
    container.append(c);
  }
  if (!container.children.length) empty(container,'Refresh to fetch owned uploads. No channel statistics are guessed.');
  const uploaded = clear('uploadedVideos');
  for (const v of state.records.uploaded_video) {
    const c = card(v.video_id, v.source === 'mock' ? 'SIMULATED RECEIPT' : (v.privacy_status || 'receipt'));
    c.append(details('Exact receipt',v));
    c.append(button('Prepare public schedule', async () => {
      const at = window.prompt('Enter a future timestamp with timezone offset, e.g. 2026-12-01T18:00:00+05:30');
      if (!at) return;
      await tool('prepare_schedule',{video_id:v.video_id,at}); showView('approvals');
    },'secondary'));
    uploaded.append(c);
  }
  if (!uploaded.children.length) empty(uploaded,'Verified private uploads will appear here. Demo receipts are explicitly simulated.');
}
function renderIdeas() {
  const container = clear('ideas'); clear('calendarIdea');
  for (const idea of state.records.idea) {
    const c = card(idea.title,idea.format,idea.premise);
    c.append(el('small','',idea.evidence_status || 'Editorial hypothesis'));
    c.append(button('Develop with Clira ↗',async () => {showView('chat'); $('message').value = `Develop a script and a production brief for idea ${idea.id}. Save it with write_script and identify any claims needing source checks.`; $('message').focus();},'secondary'));
    container.append(c);
    const option = el('option','',idea.title); option.value = idea.id; $('calendarIdea').append(option);
  }
  if (!container.children.length) empty(container,'Your next ideas belong here. Start a conversation or add your own.');
  const calendar = clear('calendar');
  for (const item of [...state.records.calendar].sort((a,b)=>a.at.localeCompare(b.at))) calendar.append(card(item.title,'Editorial plan',dateLabel(item.at)));
  if (!calendar.children.length) empty(calendar,'No editorial plans yet.');
  const briefs = clear('briefs');
  for (const brief of state.records.brief) { const c = card(brief.title,brief.status,brief.script); c.append(details('Evidence, hook lint & production handoff',brief)); briefs.append(c); }
  if (!briefs.children.length) empty(briefs,'Scripts saved by the agent appear here. Source claims remain marked for review.');
}
function renderProduction() {
  renderPackageAssets();
  const assets = clear('assets');
  for (const asset of state.records.asset) {const c=card(asset.filename,asset.rights,`${asset.qc.width} × ${asset.qc.height} · ${asset.qc.duration_seconds.toFixed(1)} seconds · ${asset.qc.codec}`); c.append(details('Technical QC, rights & SHA-256',asset)); assets.append(c);}
  if (!assets.children.length) empty(assets,'No imported MP4s. Technical validation runs before an upload request can be created.');
  const metadata = clear('metadata');
  for (const draft of state.records.metadata) { const c = card(draft.title,'Metadata draft',draft.description); c.append(details('Disclosures & editorial lint', draft)); metadata.append(c); }
  if (!metadata.children.length) empty(metadata,'Metadata drafts stay local until an exact action is approved.');
}
async function approve(approval, trigger) {
  const dialog = $('approvalDialog');
  dialog.returnValue='cancel';
  $('confirmApproval').checked = false;
  $('approvalText').value = '';
  $('dialogTitle').textContent = 'Approve ' + approval.operation.replaceAll('_',' ');
  $('dialogChannel').textContent = `${state.channel.name} · ${channelId} · ${session.mode.toUpperCase()}`;
  $('dialogPayload').textContent = JSON.stringify(approval.payload,null,2);
  const answer = await new Promise(resolve => {dialog.addEventListener('close',()=>resolve(dialog.returnValue),{once:true}); dialog.showModal();});
  if (answer !== 'approve' || $('approvalText').value !== 'APPROVE') {if(trigger?.isConnected){trigger.disabled=false;trigger.focus();}return;}
  await api('/api/approvals/'+approval.id,{channel_id:channelId,approve:true});
  await refresh(); $('approvals').querySelector('button')?.focus(); toast('Approved exact payload. Run the job when ready.');
}
function renderApprovals() {
  const container = clear('approvals');
  $('approvalCount').textContent = state.approvals.filter(a=>a.status==='PENDING').length;
  for (const approval of state.approvals) {
    const job = state.jobs.find(j=>j.approval_id===approval.id);
    const expired = approval.expires_at < new Date().toISOString();
    const c = card(approval.operation.replaceAll('_',' '), expired && approval.status==='PENDING' ? 'EXPIRED' : approval.status);
    c.classList.add('approval-card');
    c.append(el('p','',`${state.channel.name} · ${channelId}`), el('small','',`Expires ${dateLabel(approval.expires_at)} · ${approval.payload_hash}`));
    c.append(el('pre','',JSON.stringify(approval.payload,null,2)));
    const actions = el('div','actions');
    if (approval.status==='PENDING' && !expired) {
      actions.append(button('Review & approve exact action',trigger=>approve(approval,trigger)),button('Reject',async()=>{await api('/api/approvals/'+approval.id,{channel_id:channelId,approve:false}); await refresh();},'secondary'));
    }
    if (expired && job && ['AWAITING_APPROVAL','QUEUED','FAILED_RETRYABLE','PAUSED'].includes(job.state)) {
      actions.append(button('Request fresh approval for this job',async()=>{await api('/api/approvals/'+approval.id+'/renew',{channel_id:channelId});await refresh();toast('Fresh consent requested. The same job and saved session are preserved.');},'secondary'));
    }
    if (job && ['QUEUED','FAILED_RETRYABLE'].includes(job.state)) {
      actions.append(button(session.mode==='demo'?'Run simulation':'Execute approved account action',async()=>{
        const result = await api('/api/jobs/'+job.id+'/run',{channel_id:channelId});
        await refresh(); toast(result.data?.source==='mock'?'Simulation complete. No real YouTube action occurred.':'Action completed. Review the verified receipt in Operations.');
      }));
    }
    if (job) c.append(el('small','',`${job.id} · ${job.state}`));
    c.append(actions); container.append(c);
  }
  if (!container.children.length) empty(container,'Nothing waiting for your say. Uploads and public actions will appear with an exact preview.');
}
function renderCommunity() {
  const container = clear('comments');
  for (const comment of state.records.comment) {
    const c = card('Viewer question','Untrusted viewer text');
    c.append(el('p','comment-text',comment.text));
    const reply = el('textarea'); reply.rows=3; reply.placeholder='Write a thoughtful reply…'; reply.setAttribute('aria-label','Reply to '+comment.comment_id);
    c.append(reply,button('Save reply & request approval',async()=>{
      if(!reply.value.trim()) throw new Error('Write a reply first.');
      await tool('draft_reply',{comment_id:comment.comment_id,text:reply.value}); toast('Reply saved locally. Posting requires approval.');
    })); container.append(c);
  }
  if (!container.children.length) empty(container,'Read recent comments to start. Comments are never posted or moderated automatically.');
  const replies = clear('replies');
  for (const reply of state.records.reply) replies.append(card(reply.comment_id,reply.status,reply.text));
  if (!replies.children.length) empty(replies,'No reply drafts.');
}
function renderOperations() {
  const jobs = clear('jobs');
  for (const job of state.jobs) {
    const c = card(job.operation.replaceAll('_',' '),job.state,`${job.attempts} attempts · ${job.id}`);
    if(job.last_error) c.append(el('p','error',job.last_error));
    c.append(details('Payload, progress & receipt',job));
    if(['QUEUED','FAILED_RETRYABLE','PAUSED'].includes(job.state)) {
      const action=job.state==='PAUSED'?'resume':'pause';
      c.append(button(action==='pause'?'Pause job':'Resume job',async()=>{await api(`/api/jobs/${job.id}/${action}`,{channel_id:channelId}); await refresh();},'secondary'));
    }
    jobs.append(c);
  }
  if (!jobs.children.length) empty(jobs,'No account jobs. Drafting and analytics actions are still recorded below.');
  const audit=clear('audit');
  for(const event of state.audit){const row=el('div','audit-row');row.append(el('time','',dateLabel(event.at)),el('span','',event.action),el('span','',event.decision));audit.append(row);}
}
function renderSettings() {
  for(const [id,mode] of [['copySource','draft'],['copyTarget','live']]){
    clear(id);for(const c of session.channels.filter(c=>c.mode===mode&&(mode!=='live'||c.connected))){const o=el('option','',c.name+' · '+c.id);o.value=c.id;$(id).append(o);}
  }
  for(const [key,value] of Object.entries(state.channel.profile)){const input=$('profileForm').elements.namedItem(key);if(input) input.value=value;}
}
async function refresh() {
  if(!channelId) return;
  const target=channelId; const loaded=await api('/api/state/'+encodeURIComponent(target));if(target!==channelId)return;state=loaded;
  $('onboarding').open=!session.channels.some(c=>c.mode==='live');
  $('notice').textContent=state.channel.mode==='draft'?'LOCAL DRAFT · No YouTube account connected. Plans remain local.':session.mode==='demo'?'DEMO · SYNTHETIC · No real channel operations occur.':`Live mode · ${session.writes_enabled?'Approved writes enabled':'Account writes disabled'}`;
  if(state.records.launch.length){const plan=state.records.launch[0];$('launchResult').textContent=plan.positioning+'\n\nName ideas: '+plan.name_suggestions.join(' · ')+'\n\nDescription: '+plan.description+'\n\nBrand direction: '+plan.brand_direction+'\n\n'+plan.evidence_status+'\n'+plan.channel_creation;}else $('launchResult').textContent='';
  renderMetrics(); renderVideos(); renderIdeas(); renderProduction(); renderApprovals(); renderCommunity(); renderOperations(); renderSettings();
}
async function changeChannel() {
  $('channelSelect').disabled=true;
  try {
  channelId=$('channelSelect').value || null;
  $('channelId').textContent=channelId || 'No connected channels';
  conversationId=null; clear('messages');
  if(channelId){
    await refresh();
    const history=await api('/api/conversations/'+encodeURIComponent(channelId));
    const requested = new URLSearchParams(location.search).get('session');
    const selected = history.find(s=>s.id===requested) || history[0];
    if(selected) await resumeSession(selected.id);
    else updateSessionContext();
    await loadSessions();
  }
  if(state?.channel?.mode==='draft') $('modeBadge').textContent='LOCAL DRAFT · NOT CONNECTED';
  else $('modeBadge').textContent=session.mode==='demo'?'DEMO · SYNTHETIC':'LIVE · OWNER ACCOUNT';
  showView(activeView);
  } finally {$('channelSelect').disabled=busy;}
}
function bindForm(id, handler) {
  $(id).addEventListener('submit',async event=>{
    event.preventDefault();const submit=event.submitter; if(submit)submit.disabled=true;
    try{await handler(Object.fromEntries(new FormData(event.target)),event.target);}catch(error){toast(error.message,true);}finally{if(submit)submit.disabled=false;}
  });
}
async function init() {
  session=await api('/api/session');
  $('brandName').firstChild.textContent=session.name;
  document.title=session.name+' · Storytelling meets strategic wisdom';
  $('modeBadge').textContent=session.mode==='demo'?'SYNTHETIC DEMO':'CONNECTED MODE';
  $('modelBadge').textContent=session.model==='offline'?'Offline router':(session.model_calls_enabled?'Gemini':'Gemini disabled');
  $('notice').textContent=session.mode==='demo'?'You’re exploring synthetic demo data. No real channel is connected and no Google operations will occur.':`Live channel mode · ${session.writes_enabled?'Approved writes enabled':'Advisor mode — account writes disabled'}`;
  $('modeExplanation').textContent=session.model==='offline'?'Offline mode uses fixed templates for a few requests. Configure Gemini in Settings for an open-ended AI partner.':'Gemini requests use your configured account and request cap. Tools run only within this channel.';
  $('importDir').textContent=session.import_dir;
  $('settingsStatus').textContent=`Mode: ${session.mode}. Model: ${session.model}. Live writes: ${session.writes_enabled?'enabled with approval':'disabled'}.`;
  if(session.paused){$('pauseAll').textContent='Resume approved writes';$('pauseTop').textContent='Resume writes';}
  initV1();
  for(const c of session.channels){const option=el('option','',c.name);option.value=c.id;$('channelSelect').append(option);}
  if(!session.channels.length){const option=el('option','','No channels connected');option.value='';$('channelSelect').append(option);}
  document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
  $('channelSelect').addEventListener('change',()=>changeChannel().catch(e=>toast(e.message,true)));
  $('newChat').addEventListener('click',async()=>{try{
    const result=await api('/api/conversations',{channel_id:channelId});conversationId=result.id;clear('messages');updateSessionContext(result);await loadSessions();$('message').focus();
  }catch(e){toast(e.message,true);}});
  $('chatForm').addEventListener('submit',event=>{event.preventDefault();const text=$('message').value.trim();if(text)sendMessage(text);});
  $('message').addEventListener('input',()=>{$('message').style.height='auto';$('message').style.height=Math.min($('message').scrollHeight,320)+'px';});
  $('message').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('chatForm').requestSubmit();}});
  document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>sendMessage(b.dataset.prompt)));
  $('suggestIdeas').addEventListener('click',()=>{showView('chat');sendMessage('Suggest three new topic ideas for this channel.');});
  $('refreshVideos').addEventListener('click',async()=>{try{await tool('list_videos',{count:20});toast('Owned videos refreshed.');}catch(e){toast(e.message,true);}});
  $('refreshComments').addEventListener('click',async()=>{try{await tool('list_comments',{count:20});}catch(e){toast(e.message,true);}});
  $('refreshState').addEventListener('click',()=>refresh().catch(e=>toast(e.message,true)));
  const togglePause=async()=>{try{const action=session.paused?'unpause':'pause';session.paused=(await api('/api/'+action,{})).paused;$('pauseAll').textContent=session.paused?'Resume approved writes':'Pause all writes';$('pauseTop').textContent=session.paused?'Resume writes':'Pause writes';toast(session.paused?'External writes paused.':'Approved writes may resume.');}catch(e){toast(e.message,true);}};
  $('pauseAll').addEventListener('click',togglePause);$('pauseTop').addEventListener('click',togglePause);
  bindForm('ideaForm',async values=>{await tool('save_idea',{...values,sources:[]});toast('Idea saved.');});
  bindForm('calendarForm',async values=>{await tool('calendar_add',{idea_id:values.idea_id,at:new Date(values.at).toISOString()});toast('Editorial plan added. No publication scheduled.');});
  bindForm('profileForm',async values=>{await api('/api/profile/'+encodeURIComponent(channelId),values,'PUT');toast('Channel memory saved.');await refresh();});
  bindForm('productionForm',async (values,form)=>{
    const asset=await tool('import_video',{path:values.path,rights:values.rights,rights_evidence:values.rights_evidence,creative_reviewed:form.elements.creative_reviewed.checked});
    const metadata=await tool('package_video',{title:values.title,description:values.description,tags:values.tags.split(',').map(t=>t.trim()).filter(Boolean),thumbnail_text:values.thumbnail_text,made_for_kids:values.made_for_kids==='true',synthetic_media:values.synthetic_media==='true',category_id:'22',
      hashtags:values.hashtags.split(/\s+/).filter(Boolean), chapters:parseChapters(values.chapters), asset_id:asset.id,
      thumbnail_id:values.thumbnail_id||null,captions_id:values.captions_id||null});
    await tool('prepare_upload',{asset_id:asset.id,metadata_id:metadata.id});showView('approvals');toast('Private-upload request ready for your exact review.');
  });
  const requestedChannel=new URLSearchParams(location.search).get('channel');
  if(session.channels.some(c=>c.id===requestedChannel)) $('channelSelect').value=requestedChannel;
  await changeChannel();
  if(channelId && session.mode==='demo' && !state.records.analytics.length){await tool('channel_report',{days:28});await tool('list_videos',{count:5});}
}
init().catch(error=>{toast(error.message,true);$('notice').textContent='The local workspace could not load. '+error.message;});


function updateSessionContext(record) {
  const url=new URL(location.href);if(channelId)url.searchParams.set('channel',channelId);
  if(conversationId)url.searchParams.set('session',conversationId);else url.searchParams.delete('session');
  history.replaceState(null,'',url);
  $('sessionTitle').textContent=record?.title||conversationId||'New conversation';
  $('renameSession').disabled=busy||!conversationId;
  $('terminalResume').textContent=conversationId?`clira --mode ${session.mode} --channel ${channelId} --resume ${conversationId}`:'';
}
async function resumeSession(id) {
  if(busy)return;
  const record=await api(`/api/conversations/${encodeURIComponent(channelId)}/${encodeURIComponent(id)}`);
  conversationId=record.id;clear('messages');
  for(const m of record.messages)addMessage(m.role==='user'?'user':'assistant',m.text,m.receipts);
  updateSessionContext(record);
}
async function loadSessions() {
  if(!channelId)return;
  const current=channelId;
  const records=await api('/api/conversations/'+encodeURIComponent(current));
  if(current!==channelId)return;
  const search=$('sessionSearch').value.toLocaleLowerCase();const list=clear('sessionList');
  for(const r of records.filter(r=>(r.title||'').toLocaleLowerCase().includes(search))) {
    const b=button(`${r.title||'Untitled'} · ${dateLabel(r.updated_at)} · ${r.id}`,async()=>{await resumeSession(r.id);showView('chat');},'secondary');b.disabled=busy;list.append(b);
  }
  if(!list.children.length)empty(list,'No matching conversations.');
}
function parseChapters(text) {
  if(!text.trim())return [];
  return text.trim().split('\n').map(line=>{
    const match=line.match(/^(\d{1,2}:)?(\d{2}):(\d{2})\s+(.+)$/);
    if(!match||Number(match[2])>59||Number(match[3])>59)throw new Error('Use MM:SS Title or HH:MM:SS Title for chapters.');
    return {seconds:(match[1]?Number(match[1].slice(0,-1))*3600:0)+Number(match[2])*60+Number(match[3]),title:match[4]};
  });
}
function renderPackageAssets() {
  for(const id of ['packageThumbnail','packageCaptions','captionVideo']){
    const selected=$(id).value;clear(id);const none=el('option','','None');none.value='';$(id).append(none);
    const records=id==='captionVideo'?state.records.asset:state.records.package_asset.filter(a=>a.type===(id==='packageThumbnail'?'thumbnail':'captions'));
    for(const a of records){const o=el('option','',`${a.filename} · ${a.id}`);o.value=a.id;$(id).append(o);}
    if(records.some(a=>a.id===selected))$(id).value=selected;
  }
  const container=clear('packageAssets');
  for(const record of state.records.package_asset){
    const c=card(record.filename,record.type,`${record.size} bytes · ${record.sha256}`);
    if(record.type==='thumbnail'){
      const img=el('img','package-preview');img.src=`/api/preview/${encodeURIComponent(channelId)}/${encodeURIComponent(record.id)}`;img.alt='Actual local thumbnail preview';c.append(img);
    }else{
      c.append(el('pre','',record.text));const edit=el('textarea','package-editor',record.text);edit.setAttribute('aria-label','Edit timed captions '+record.id);
      c.append(edit,button('Save edited captions as new unreviewed file',async()=>{await tool('edit_captions',{package_asset_id:record.id,text:edit.value});}));
    }
    c.append(el('p','',`Rights: ${record.rights} · Creative review: ${record.creative_reviewed?'owner reviewed':'required'}`));
    const evidence=el('input');evidence.placeholder='Rights evidence for this exact file';evidence.setAttribute('aria-label','Rights evidence '+record.id);
    const rights=el('select');rights.setAttribute('aria-label','Rights '+record.id);
    for(const val of ['original','licensed']){const o=el('option','',val);o.value=val;rights.append(o);}
    c.append(evidence,rights,button('Attest rights & creative review',async()=>{
      if(!evidence.value.trim())throw new Error('Document rights evidence first.');
      if(!window.confirm('I reviewed this exact image/caption file and its rights.'))return;
      await tool('review_package_asset',{package_asset_id:record.id,rights:rights.value,rights_evidence:evidence.value,creative_reviewed:true});
    },'secondary'));
    const trackName=el('input');trackName.value='Manual captions';trackName.setAttribute('aria-label','Caption track name '+record.id);
    const draftLabel=el('label','checkbox');const draft=el('input');draft.type='checkbox';draft.checked=true;draftLabel.append(draft,document.createTextNode('Keep caption track as draft (owner reviews in Studio)'));
    if(record.type==='captions')c.append(trackName,draftLabel);
    const target=el('input');target.placeholder='Exact owned YouTube video ID';target.setAttribute('aria-label','Attachment target '+record.id);
    c.append(target,button('Prepare separate upload approval',async()=>{
      if(!target.value.trim())throw new Error('Enter the exact owned private video ID after upload.');
      await tool('prepare_attachment',{video_id:target.value.trim(),package_asset_id:record.id,name:trackName.value,is_draft:draft.checked});showView('approvals');
    },'secondary'),details('Exact file facts',record));container.append(c);
  }
  if(!container.children.length)empty(container,'No thumbnail or caption files imported. Concepts are not images.');
}
function initV1() {
  $('connectOAuth').addEventListener('click',async()=>{
    const button=$('connectOAuth');button.disabled=true;
    try{
      let current=await api('/api/connect/start',{});
      while(['authorizing','awaiting_confirmation','saving'].includes(current.state)){
        $('connectState').textContent=current.notice+' State: '+current.state;
        if(current.state==='awaiting_confirmation'){
          const confirmed=window.prompt(`Connect ${current.name}? Type exact channel ID ${current.channel_id}. Read-only scopes: ${current.scopes.join(', ')}`);
          if(confirmed!==current.channel_id)throw new Error('Channel not confirmed. No credentials saved. Sign-in expires after five minutes.');
          current=await api('/api/connect/'+current.id+'/confirm',{channel_id:confirmed});
        }
        await new Promise(resolve=>setTimeout(resolve,1000));
        current=await api('/api/connect/status');
      }
      $('connectState').textContent=current.state+' · '+(current.notice||'');
      if(current.state==='connected')location.reload();
    }catch(e){$('connectState').textContent=e.message;toast(e.message,true);}finally{button.disabled=false;}
  });
  $('titleOptions').addEventListener('click',async()=>{try{
    const input=$('productionForm').elements.title;if(!input.value.trim())throw new Error('Enter the factual subject first (up to 65 characters).');
    const result=await tool('title_options',{subject:input.value.trim()});const choices=clear('titleChoices');
    choices.append(el('small','',result.status));for(const title of result.titles)choices.append(button(title,async()=>{input.value=title;},'secondary'));
  }catch(e){toast(e.message,true);}});
  const media=matchMedia('(prefers-color-scheme: dark)');
  const theme=localStorage.getItem('clira-theme')||'auto';$('themeSelect').value=theme;
  const apply=()=>{const value=$('themeSelect').value;document.documentElement.dataset.theme=value==='auto'?(media.matches?'dark':'light'):value;};apply();media.addEventListener('change',apply);
  $('themeSelect').addEventListener('change',()=>{localStorage.setItem('clira-theme',$('themeSelect').value);apply();});
  $('sessionSearch').addEventListener('input',()=>loadSessions().catch(e=>toast(e.message,true)));
  $('renameSession').addEventListener('click',async()=>{
    if(!conversationId)return toast('Send a message or create a session first.');
    const title=window.prompt('Conversation title');if(!title?.trim())return;
    try{const record=await api('/api/conversations/'+encodeURIComponent(conversationId),{channel_id:channelId,title:title.trim()},'PUT');updateSessionContext(record);await loadSessions();}catch(e){toast(e.message,true);}
  });
  const launchQuestions=['What subject interests you?','Who is the viewer?','What language?','How much time per week?','What format: short or long?'];let step=0,answers=[];
  const start=()=>{step=0;answers=[];$('launchForm').hidden=false;$('onboarding').open=true;$('launchLabel').firstChild.textContent='1 of 5 · '+launchQuestions[0];$('launchAnswer').value='';$('launchAnswer').focus();};
  $('startLaunch').addEventListener('click',start);$('emptyLaunch').addEventListener('click',()=>{showView('chat');$('view-chat').hidden=false;start();});
  $('connectGuide').addEventListener('click',()=>showView('settings'));
  $('emptyConnect').addEventListener('click',()=>showView('settings'));
  $('emptyDemo').addEventListener('click',()=>toast('Start clira --mode demo serve for explicitly synthetic examples.'));
  $('exploreDemo').addEventListener('click',async()=>{if(session.mode!=='demo')return toast('Restart clira --mode demo serve to explore synthetic fixtures.');$('channelSelect').value='DEMO_CHANNEL_TECH';await changeChannel();});
  bindForm('launchForm',async()=>{
    answers[step]=$('launchAnswer').value.trim();step++;
    if(step<5){$('launchLabel').firstChild.textContent=`${step+1} of 5 · ${launchQuestions[step]}`;$('launchAnswer').value='';$('launchAnswer').focus();return;}
    const result=await api('/api/workspaces',Object.fromEntries(['interest','viewer','language','time','format'].map((key,i)=>[key,answers[i]])));
    session.channels.push(result.workspace);const o=el('option','',result.workspace.name);o.value=result.workspace.id;$('channelSelect').append(o);$('channelSelect').value=result.workspace.id;
    $('launchForm').hidden=true;await changeChannel();toast('Local draft workspace, three ideas and draft calendar saved. No YouTube account created.');
  });
  bindForm('copyWorkspaceForm',async values=>{const result=await api('/api/workspaces/copy',values);toast('Copied '+result.copied.length+' local drafts. Original workspace preserved.');await refresh();});
  bindForm('packageAssetForm',async(values,form)=>{await tool('import_package_asset',{...values,asset_id:values.asset_id||null,creative_reviewed:form.elements.creative_reviewed.checked});toast('Actual packaging file validated and saved.');});
  bindForm('templateForm',async values=>{await tool('thumbnail_template',values);toast('PNG generated using the local deterministic template. Review its rights and creative quality.');});
}
