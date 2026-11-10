'use strict';
const $ = id => document.getElementById(id);
const characterEvent = (event,detail) => window.cliraCharacter?.emit(event,detail);
let characterRequestId=0;
let session, state, channelId, conversationId = null, activeView = 'chat', busy = false, attachedVideo = null;
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
  if(error)characterEvent('error');
  $('toast').textContent = message;
  $('toast').hidden = false;
  $('toast').classList.toggle('error', error);
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => { $('toast').hidden = true; }, error ? 12000 : 6000);
}
async function api(path, body, method = 'POST') {
  const kind=body!==undefined && (/^\/api\/chat$/.test(path)?'thinking':(/^\/api\/(?:jobs\/[^/]+\/run|upload-drafts\/[^/]+\/approve)$/.test(path)?'uploading':null));
  const id=kind?'request-'+(++characterRequestId):null;
  if(id)characterEvent('request:start',{id,kind});
  try {
    const response = await fetch(path, {method: body === undefined ? 'GET' : method,
      headers: {'Content-Type':'application/json', ...(session ? {'X-Clira-Token': session.token} : {})},
      body: body === undefined ? undefined : JSON.stringify(body)});
    const value = await response.json();
    if (!response.ok || value.ok === false) {
      const error = value.error;
      throw new Error(error ? `${error.code}: ${error.message}` : `Request failed (${response.status})`);
    }
    if(kind==='uploading')characterEvent('outcome',{
      verified:value.data?.verified_remotely===true,
      simulated:value.data?.source==='mock' && value.data?.verified_remotely!==true,
    });
    return value;
  } catch(error) {if(id)characterEvent('error');throw error;}
  finally {if(id)characterEvent('request:end',{id});}
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
  $('viewLabel').textContent = 'CLIRA / ' + view.toUpperCase();
}
function addMessage(role, text, receipts) {
  const draft = receipts?.find(r=>r.tool==='prepare_video_upload' && r.ok)?.data;
  const m = el('article', 'message ' + role);
  const speaker=el('div','speaker',role === 'user' ? 'You' : session.name);
  const body=el('div','body',draft?'Your video package is ready. Review it below. Nothing has been uploaded.':text);
  if(role!=='user'&&!draft)renderAnswer(body,text);
  const actions=el('span','message-actions');
  actions.append(button('Copy',async b=>{
    try { await navigator.clipboard.writeText(text); }
    catch { const range=document.createRange();range.selectNodeContents(body);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);throw new Error('Reply selected. Press Ctrl+C or Command+C to copy.'); }
    b.textContent='Copied';setTimeout(()=>{b.textContent='Copy';},1800);
  },'quiet'));
  speaker.append(actions);m.append(speaker,body);
  if (receipts?.length) m.append(details(`${receipts.length} tool receipts · sources & outcomes`, receipts));
  $('messages').append(m);
  syncWelcome();
  if(draft) api('/api/upload-drafts/'+encodeURIComponent(draft.channel_id)+'/'+encodeURIComponent(draft.id)).then(current=>{if(m.isConnected)renderUploadPreview(m,current);}).catch(error=>toast(error.message,true));

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
  const submittedVideo=attachedVideo;
  const requestText=submittedVideo?'/upload '+submittedVideo.path+'\n'+text:text;
  addMessage('user', submittedVideo?'Upload '+submittedVideo.name+' · '+text:text);
  attachedVideo=null;$('composerHint').textContent='Draft freely. You approve account actions.';

  $('message').value = '';
  updateBlockCursor();
  try {
    const result = await api('/api/chat', {channel_id: channelId, message: requestText, conversation_id: conversationId});
    conversationId = result.conversation_id;
    updateSessionContext(); await loadSessions();
    addMessage('assistant', result.message, result.receipts);
    characterEvent('reply');
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
    $('sendButton').textContent = 'Send message';
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
  characterEvent('approval',{source:'queue',required:state.approvals.some(a=>a.status==='PENDING'&&a.expires_at>new Date().toISOString())});
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
  $('notice').textContent=state.channel.mode==='draft'?'LOCAL DRAFT · No YouTube account connected. Plans remain local.':session.mode==='demo'?'DEMO · SYNTHETIC · No real channel operations occur.':`Live mode · ${session.writes_enabled?'Approved writes enabled':'Account writes disabled'}`;
  if(state.records.launch.length){const plan=state.records.launch[0];$('launchResult').textContent=plan.positioning+'\n\nName ideas: '+plan.name_suggestions.join(' · ')+'\n\nDescription: '+plan.description+'\n\nBrand direction: '+plan.brand_direction+'\n\n'+plan.evidence_status+'\n'+plan.channel_creation;}else $('launchResult').textContent='';
  renderMetrics(); renderVideos(); renderIdeas(); renderProduction(); renderApprovals(); renderCommunity(); renderOperations(); renderSettings();
}
async function changeChannel() {
  characterEvent('context');
  $('channelSelect').disabled=true;
  try {
  attachedVideo=null;
  channelId=$('channelSelect').value || null;
  $('onboarding').open=!session.channels.length;
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
  $('brandName').textContent=session.name;
  document.title=session.name+' · Intelligence Behind Creation';
  $('modeBadge').textContent=session.mode==='demo'?'SYNTHETIC DEMO':'CONNECTED MODE';
  $('modelBadge').textContent=session.model==='offline'?'Offline router':(session.model_calls_enabled?'Gemini':'Gemini disabled');
  $('notice').textContent=session.mode==='demo'?'You’re exploring synthetic demo data. No real channel is connected and no Google operations will occur.':`Live channel mode · ${session.writes_enabled?'Approved writes enabled':'Advisor mode — account writes disabled'}`;
  $('modeExplanation').textContent=session.model==='offline'?'Offline mode uses fixed templates for a few requests. Configure Gemini in Settings for an open-ended AI partner.':'Gemini requests use your configured account and request cap. Tools run only within this channel.';
  $('importDir').textContent=session.import_dir;
  $('settingsStatus').textContent=`Mode: ${session.mode}. Model: ${session.model}. Live writes: ${session.writes_enabled?'enabled with approval':'disabled'}.`;
  if(session.paused){$('pauseAll').textContent='Resume approved writes';$('pauseTop').textContent='Resume writes';}
  initV1();
  initTerminalExperience();
  for(const c of session.channels){const option=el('option','',c.name);option.value=c.id;$('channelSelect').append(option);}
  if(!session.channels.length){const option=el('option','','No channels connected');option.value='';$('channelSelect').append(option);}
  document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
  $('channelSelect').addEventListener('change',()=>changeChannel().catch(e=>toast(e.message,true)));
  $('newChat').addEventListener('click',async()=>{try{
    const result=await api('/api/conversations',{channel_id:channelId});conversationId=result.id;clear('messages');characterEvent('conversation');updateSessionContext(result);await loadSessions();$('message').focus();
  }catch(e){toast(e.message,true);}});
  $('chatVideo').addEventListener('change',async()=>{
    const file=$('chatVideo').files[0];if(!file||busy||!channelId)return;
    const target=channelId;busy=true;$('sendButton').disabled=true;$('channelSelect').disabled=true;
    try{
      if(!file.name.toLowerCase().endsWith('.mp4')||file.size>256*1024*1024)throw new Error('Choose an MP4 up to 256 MiB.');
      const response=await fetch('/api/chat-video/'+encodeURIComponent(target),{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Clira-Token':session.token},body:file});
      const result=await response.json();if(!response.ok)throw new Error(result.error?.message||'Attachment failed.');
      if(target!==channelId)return;
      attachedVideo={path:result.path,name:file.name};
      characterEvent('attached');
      $('composerHint').textContent=file.name+' attached. Sampled frames will be sent to your configured AI provider when you send.';
      if(!$('message').value.trim())$('message').value='Upload this video';$('message').focus();
    }catch(error){toast(error.message,true);}finally{busy=false;$('sendButton').disabled=false;$('channelSelect').disabled=false;$('chatVideo').value='';}
  });
  $('chatForm').addEventListener('submit',event=>{event.preventDefault();const text=$('message').value.trim();if(text&&!busy){if(!attachedVideo&&navigateCommand(text)){$('message').value='';updateBlockCursor();}else sendMessage(text);}});
  $('message').addEventListener('input',()=>{characterEvent('typing',{active:Boolean($('message').value.trim())});$('message').style.height='auto';$('message').style.height=Math.min($('message').scrollHeight,320)+'px';});
  $('message').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('chatForm').requestSubmit();}});
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
  $('sessionTitle').textContent=record?.title||(conversationId?'Current conversation':'New conversation');
  $('renameSession').disabled=busy||!conversationId;
  $('terminalResume').textContent=conversationId?`clira --mode ${session.mode} --channel ${channelId} --resume ${conversationId}`:'';
  syncWelcome();
}
async function resumeSession(id) {
  if(busy)return;
  busy=true;$('sendButton').disabled=true;$('newChat').disabled=true;$('channelSelect').disabled=true;
  try {
    const record=await api(`/api/conversations/${encodeURIComponent(channelId)}/${encodeURIComponent(id)}`);
    conversationId=record.id;clear('messages');
    for(const m of record.messages)addMessage(m.role==='user'?'user':'assistant',m.text,m.receipts);
    updateSessionContext(record);
  } finally {busy=false;$('sendButton').disabled=false;$('newChat').disabled=false;$('channelSelect').disabled=false;$('renameSession').disabled=!conversationId;}
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
  const savedTheme=localStorage.getItem('clira-theme');const theme=['auto','light','dark'].includes(savedTheme)?savedTheme:'dark';$('themeSelect').value=theme;
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


function renderUploadPreview(container, draft) {
  characterEvent('approval',{source:'preview:'+draft.id,required:draft.state==='DRAFT'});
  if(draft.state==='DRAFT')characterEvent('preview');
  const c=card('Review your private upload','Draft · '+draft.source,'Destination: '+draft.destination+' · '+draft.destination_channel);
  const video=el('video');video.controls=true;video.preload='metadata';video.src='/api/upload-drafts/'+encodeURIComponent(draft.channel_id)+'/'+encodeURIComponent(draft.id)+'/video';video.setAttribute('aria-label','Exact video to upload');c.append(video);const download=el('a','','Open/download this exact video');download.href=video.src;download.target='_blank';download.rel='noopener';c.append(download);video.addEventListener('error',()=>c.insertBefore(el('p','','Your browser cannot play this codec. Open/download the video to review it before approving.'),download),{once:true});
  const fields={};
  function field(label,value,multi=false){const wrap=el('label','upload-field',label);const input=el(multi?'textarea':'input');input.value=value;input.setAttribute('aria-label',label);if(multi)input.rows=4;wrap.append(input);c.append(wrap);return input;}
  fields.title=field('Title',draft.copy.title);fields.description=field('Description',draft.copy.description,true);fields.tags=field('Tags (comma separated)',draft.copy.tags.join(', '));
  c.append(details('Suggested script outline (not a transcript)',draft.copy.script_outline));
  c.append(el('p','',draft.analysis+' '+draft.packaging_note));
  function select(label,options){const wrap=el('label','upload-field',label),input=el('select');input.setAttribute('aria-label',label);for(const [value,text]of options){const o=el('option','',text);o.value=value;input.append(o);}wrap.append(input);c.append(wrap);return input;}
  const rights=select('Video and audio rights',[['','Confirm rights…'],['original','I own the original material'],['licensed','I have licences for third-party material']]);
  const evidence=field('Rights evidence (including music and fonts)','');
  const kids=select('Made specifically for kids?',[['','Choose…'],['false','No'],['true','Yes']]);
  const synthetic=select('Realistic altered or synthetic media?',[['','Choose…'],['false','No'],['true','Yes']]);
  const reviewLabel=el('label','upload-field');const reviewed=el('input');reviewed.type='checkbox';reviewLabel.append(reviewed,document.createTextNode(' I watched this exact video and reviewed its package, rights and disclosures.'));c.append(reviewLabel);
  const status=el('p');status.setAttribute('role','status');c.append(status);
  c.append(button('Approve & upload privately',async b=>{
    if(!rights.value||!evidence.value.trim()||!kids.value||!synthetic.value||!reviewed.checked)throw new Error('Complete the owner review and both disclosure choices.');
    characterEvent('approval',{source:'preview:'+draft.id,required:false});
    const target=draft.channel_id;b.disabled=true;status.textContent='Uploading privately… Keep this page open.';
    c.querySelectorAll('input,textarea,select').forEach(n=>n.disabled=true);
    try{
      const result=await api('/api/upload-drafts/'+encodeURIComponent(draft.id)+'/approve',{channel_id:target,preview_hash:draft.preview_hash,copy:{...draft.copy,title:fields.title.value,description:fields.description.value,tags:fields.tags.value.split(',').map(v=>v.trim()).filter(Boolean)},rights:rights.value,rights_evidence:evidence.value,creative_reviewed:reviewed.checked,made_for_kids:kids.value==='true',synthetic_media:synthetic.value==='true',confirmation:'APPROVE PRIVATE UPLOAD'});
      status.textContent=result.message||(result.data?.verified_remotely?'Private upload verified.':'SYNTHETIC DEMO: simulated upload only; no real video exists.');
      if(result.data?.url){const link=el('a','',result.data.url);link.href=result.data.url;link.target='_blank';link.rel='noopener';status.append(document.createTextNode(' '),link);}
      b.remove();if(target===channelId)await refresh();
    }catch(error){status.textContent='Upload needs attention. '+error.message+' Inspect Operations before retrying; do not prepare another upload.';b.remove();throw error;}
  }));
  if(draft.state!=='DRAFT'){c.querySelectorAll('input,textarea,select,button').forEach(n=>n.disabled=true);status.textContent=draft.state==='COMPLETED'?'This upload is complete.':'This preview was already submitted. Check Operations for its saved receipt.';if(draft.result?.data?.url){const link=el('a','',draft.result.data.url);link.href=draft.result.data.url;link.target='_blank';link.rel='noopener';status.append(document.createTextNode(' '),link);}}
  container.append(c);
}

// Render a small Markdown subset with DOM text nodes only. Model HTML is never executed.
function inlineText(parent, text) {
  const parts=text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))/g);
  for(const part of parts){
    if(part.startsWith('**')&&part.endsWith('**'))parent.append(el('strong','',part.slice(2,-2)));
    else if(part.startsWith('`')&&part.endsWith('`'))parent.append(el('code','',part.slice(1,-1)));
    else {const link=part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);if(link){const a=el('a','',link[1]);a.href=link[2];a.target='_blank';a.rel='noopener noreferrer';parent.append(a);}else parent.append(document.createTextNode(part));}
  }
}
function renderAnswer(body,text) {
  body.replaceChildren();body.classList.add('rich');
  const lines=text.split('\n');let paragraph=[],list=null;
  const flush=()=>{if(paragraph.length){const p=el('p');inlineText(p,paragraph.join('\n'));body.append(p);paragraph=[];}list=null;};
  for(let i=0;i<lines.length;i++){
    const line=lines[i];
    if(line.startsWith('```')){flush();const code=[];while(++i<lines.length&&!lines[i].startsWith('```'))code.push(lines[i]);const pre=el('pre');pre.append(el('code','',code.join('\n')));body.append(pre);continue;}
    if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{3,}/.test(lines[i+1])){
      flush();const table=el('table'),head=el('thead'),row=el('tr');
      const cells=value=>value.trim().replace(/^\||\|$/g,'').split('|').map(v=>v.trim());
      for(const value of cells(line)){const th=el('th');th.scope='col';inlineText(th,value);row.append(th);}head.append(row);table.append(head);i++;
      const tbody=el('tbody');while(i+1<lines.length&&lines[i+1].includes('|')){const tr=el('tr');for(const value of cells(lines[++i])){const td=el('td');inlineText(td,value);tr.append(td);}tbody.append(tr);}table.append(tbody);const scroll=el('div','table-scroll');scroll.append(table);body.append(scroll);continue;
    }
    const heading=line.match(/^#{1,6}\s+(.+)/);if(heading){flush();const h=el('h3');inlineText(h,heading[1]);body.append(h);continue;}
    const item=line.match(/^\s*(?:([-*])|\d+[.)])\s+(.+)/);
    if(item){if(paragraph.length)flush();const type=item[1]?'UL':'OL';if(!list||list.tagName!==type){list=el(type.toLowerCase());body.append(list);}const li=el('li');inlineText(li,item[2]);list.append(li);continue;}
    if(!line.trim()||/^\s*[-*_]{3,}\s*$/.test(line)){flush();continue;}
    if(list)flush();paragraph.push(line);
  }
  flush();
}
function syncWelcome() {
  const hasMessages=$('messages').children.length>0;
  $('chatWelcome').hidden=hasMessages;
  document.querySelector('.suggestions').hidden=hasMessages;
}
function navigateCommand(text) {
  const command=text.toLowerCase();
  const destinations={'/chat':'chat','/videos':'library','/library':'library','/ideas':'ideas','/production':'production','/approvals':'approvals','/community':'community','/operations':'operations','/status':'operations','/settings':'settings'};
  if(destinations[command]){showView(destinations[command]);return true;}
  if(command==='/new'){$('newChat').click();return true;}
  if(command==='/sessions'){$('sessionPanel').open=true;$('sessionSearch').focus();return true;}
  if(command==='/channel'){$('channelSelect').focus();return true;}
  if(command==='/help'){toast('Workspace commands: /new · /sessions · /channel · /chat · /videos · /ideas · /production · /approvals · /community · /status · /settings. Attach an MP4 to prepare its upload in chat.');return true;}
  return false;
}
let cursorMirror, blockCursor=true, composing=false;
function updateBlockCursor() {
  const input=$('message'),surface=input.parentElement,cursor=$('blockCursor');
  if(!cursorMirror)return;
  const visible=blockCursor&&!composing&&input.selectionStart===input.selectionEnd;
  surface.classList.toggle('block-cursor',visible);
  if(!visible)return;
  const style=getComputedStyle(input);
  for(const key of ['fontFamily','fontSize','fontWeight','fontStyle','lineHeight','letterSpacing','paddingTop','paddingBottom','paddingLeft','paddingRight','borderWidth','boxSizing','tabSize'])cursorMirror.style[key]=style[key];
  cursorMirror.replaceChildren(document.createTextNode(input.value.slice(0,input.selectionStart)));
  const marker=el('span','',Array.from(input.value.slice(input.selectionStart))[0]||' ');cursorMirror.append(marker);
  const rect=marker.getBoundingClientRect(),base=cursorMirror.getBoundingClientRect();
  const top=rect.top-base.top-input.scrollTop,left=rect.left-base.left-input.scrollLeft;
  cursor.style.top=top+'px';cursor.style.left=left+'px';cursor.style.width=Math.max(rect.width,parseFloat(style.fontSize)*.6)+'px';cursor.style.height=style.lineHeight;
  cursor.style.visibility=top<0||top+rect.height>input.clientHeight||left>=input.clientWidth?'hidden':'visible';
}
function initTerminalExperience() {
  const input=$('message');cursorMirror=el('div');cursorMirror.setAttribute('aria-hidden','true');
  Object.assign(cursorMirror.style,{position:'absolute',top:'0',left:'0',width:'100%',overflow:'hidden',visibility:'hidden',pointerEvents:'none',whiteSpace:'pre-wrap',overflowWrap:'break-word'});input.parentElement.append(cursorMirror);
  try {blockCursor=localStorage.getItem('clira-cursor')!=='line';}catch {blockCursor=true;}
  const apply=()=>{$('cursorToggle').setAttribute('aria-pressed',String(blockCursor));$('cursorToggle').textContent=(blockCursor?'Block':'Line')+' cursor · Ins';updateBlockCursor();};
  const toggle=()=>{blockCursor=!blockCursor;try{localStorage.setItem('clira-cursor',blockCursor?'block':'line');}catch { /* Cursor preference remains usable without storage. */ }apply();};
  $('cursorToggle').addEventListener('click',()=>{toggle();input.focus();});
  input.addEventListener('keydown',event=>{if(event.key==='Insert'&&!event.ctrlKey&&!event.shiftKey&&!event.altKey&&!event.metaKey){event.preventDefault();toggle();}});
  input.addEventListener('compositionstart',()=>{composing=true;updateBlockCursor();});input.addEventListener('compositionend',()=>{composing=false;updateBlockCursor();});
  for(const event of ['input','click','keyup','scroll','focus','select'])input.addEventListener(event,()=>requestAnimationFrame(updateBlockCursor));
  document.addEventListener('selectionchange',()=>{if(document.activeElement===input)updateBlockCursor();});
  new ResizeObserver(updateBlockCursor).observe(input);apply();
}
