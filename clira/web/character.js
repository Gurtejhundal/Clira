/* Clira companion: local presentation only. No account/API authority. */
(() => {
  'use strict';
  const root = document.getElementById('cliraCharacter');
  if (!root) return;
  const labels = {
    idle: 'Clira is here', hover: 'You have my attention', typing: 'Listening…',
    thinking: 'Thinking…', uploading: 'Account request in progress…', attached: 'A video to explore',
    preview: 'Your preview is ready', approval: 'Waiting for your review', reply: 'Ready for your next idea',
    happy: 'Hello, creator', delighted: 'Lovely to see you!', dizzy: 'You got me spinning',
    celebrate: 'Account action verified', demo: 'Demo simulation complete',
    error: 'That needs attention', greeting: 'Welcome back',
  };
  const priorities = {idle:0, hover:5, happy:10, delighted:11, dizzy:12, greeting:13,
    typing:20, attached:30, reply:35, preview:55, approval:50, thinking:70,
    uploading:75, demo:80, celebrate:85, error:90};
  const duration = {happy:1300, delighted:1700, dizzy:1800, greeting:1500,
    attached:1800, reply:1300, preview:2200, demo:2200, celebrate:2200, error:3600};
  const button = document.getElementById('characterInteract');
  const status = document.getElementById('characterStatus');
  const setting = document.getElementById('characterMotion');
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  const abort = new AbortController();
  const timers = new Map(), pending = new Map(), approvalSources = new Set();
  let artworkFailed=false, destroyed=false, hidden=document.hidden, hovering=false, keyboardFocused=false, typing=false, awaiting=false;
  let temporary=null, state='idle', raf=0, lastActive=Date.now(), hiddenAt=0;
  let points=[], lastCircle=-Infinity, lastPlay=-Infinity, lookX=0, lookY=0;
  let preference='full';
  try { preference=localStorage.getItem('clira-character-motion') || 'full'; } catch { /* Optional storage. */ }
  if (!['full','reduced','off'].includes(preference)) preference='full';
  setting.value=preference;
  const on=(target,event,handler)=>target.addEventListener(event,handler,{signal:abort.signal});
  function clear(name) { if(timers.has(name)){clearTimeout(timers.get(name));timers.delete(name);} }
  function later(name,callback,delay) {
    clear(name);if(destroyed||hidden)return;
    timers.set(name,setTimeout(()=>{timers.delete(name);if(!destroyed&&!hidden)callback();},delay));
  }
  function mode() { return artworkFailed||preference==='off'?'off':preference==='reduced'||media.matches?'reduced':'full'; }
  function choose() {
    let next=awaiting?'approval':typing?'typing':(hovering||keyboardFocused)?'hover':'idle';
    if(pending.size)next=[...pending.values()].includes('uploading')?'uploading':'thinking';
    if(temporary && priorities[temporary]>=priorities[next])next=temporary;
    return next;
  }
  function render() {
    const next=choose();state=next;
    root.dataset.state=mode()==='off'?'idle':next;
    root.dataset.motion=mode();root.dataset.paused=String(hidden);
    status.textContent=labels[next];
    if(mode()!=='full') {lookX=0;lookY=0;root.style.setProperty('--look-x','0px');root.style.setProperty('--look-y','0px');}
  }
  function react(next) {
    if(!duration[next]||destroyed||hidden)return;
    if(temporary===next)return; // Repeated refreshes never restart the same reaction.
    if(temporary&&priorities[temporary]>priorities[next])return;
    temporary=next;later('reaction',()=>{temporary=null;render();},duration[next]);render();
  }
  function play(next) {
    if(performance.now()-lastPlay<450||priorities[choose()]>=20)return;
    lastPlay=performance.now();react(next);
  }
  function blinkCycle() {
    later('blink',()=>{
      if(!['delighted','celebrate','dizzy'].includes(state))root.classList.add('is-blinking');
      later('unblink',()=>{root.classList.remove('is-blinking');blinkCycle();},150);
    },3500+Math.random()*2800);
  }
  function tiltCycle() {
    later('tilt',()=>{
      if(state==='idle')root.classList.add('is-tilting');
      later('untilt',()=>{root.classList.remove('is-tilting');tiltCycle();},1400);
    },14000+Math.random()*9000);
  }
  function idleTimers() {
    for(const name of ['blink','unblink','tilt','untilt'])clear(name);
    root.classList.remove('is-blinking','is-tilting');
    if(mode()!=='full'||hidden||destroyed)return;
    blinkCycle();tiltCycle();
  }
  function reset() {
    pending.clear();approvalSources.clear();temporary=null;awaiting=false;typing=false;hovering=false;keyboardFocused=false;points=[];lookX=0;lookY=0;cancelAnimationFrame(raf);raf=0;
    for(const name of ['reaction','typing','click'])clear(name);
    root.style.setProperty('--look-x','0px');root.style.setProperty('--look-y','0px');render();
  }
  function emit(event, detail={}) {
    if(destroyed)return;
    if(event==='typing'||event==='request:start'||event==='reply')lastActive=Date.now();
    switch(event) {
      case 'request:start': temporary=null;typing=false;clear('reaction');clear('typing');clear('click');if(detail.id)pending.set(detail.id,detail.kind==='uploading'?'uploading':'thinking');break;
      case 'request:end': pending.delete(detail.id);break;
      case 'typing': typing=Boolean(detail.active);if(typing)later('typing',()=>{typing=false;render();},1600);else clear('typing');break;
      case 'approval': if(detail.required)approvalSources.add(detail.source||'queue');else approvalSources.delete(detail.source||'queue');awaiting=approvalSources.size>0;break;
      case 'conversation': temporary=null;typing=false;clear('reaction');clear('typing');clear('click');for(const source of approvalSources)if(source!=='queue')approvalSources.delete(source);awaiting=approvalSources.size>0;break;
      case 'context': reset();return;
      case 'reply': case 'attached': case 'preview': case 'error': react(event);return;
      case 'outcome':
        if(detail.verified===true)react('celebrate');
        else if(detail.simulated===true)react('demo');
        return;
      default: return;
    }
    render();
  }
  function circle(x,y,rect,now) {
    const dx=x-(rect.left+rect.width/2),dy=y-(rect.top+rect.height/2),r=Math.hypot(dx,dy);
    const unit=Math.min(rect.width,rect.height);
    if(r<unit*.22||r>unit*.8){points=[];return;}
    points.push({angle:Math.atan2(dy,dx),r,at:now});
    points=points.filter(p=>now-p.at<1800).slice(-80);
    if(points.length<18||now-lastCircle<6000)return;
    const radii=points.map(p=>p.r);if(Math.max(...radii)/Math.min(...radii)>1.8)return;
    let sum=0,travel=0;
    for(let i=1;i<points.length;i++){
      let d=points[i].angle-points[i-1].angle;
      if(d>Math.PI)d-=2*Math.PI;if(d<-Math.PI)d+=2*Math.PI;
      if(Math.abs(d)>.65){points=[];return;} // A jump across the portrait is not a circle.
      sum+=d;travel+=Math.abs(d);
    }
    if(Math.abs(sum)>Math.PI*1.85 && Math.abs(sum)/travel>.85){lastCircle=now;points=[];play('dizzy');}
  }
  on(document,'pointermove',event=>{
    if(hidden||mode()!=='full'||event.pointerType==='touch')return;
    if(event.buttons||getSelection()?.toString()){points=[];return;}
    const rect=button.getBoundingClientRect();
    const x=event.clientX-(rect.left+rect.width/2),y=event.clientY-(rect.top+rect.height/2);
    const near=Math.hypot(x,y)<Math.max(rect.width,rect.height)*1.3;
    const nextX=near?Math.max(-3.5,Math.min(3.5,x/30)):0;
    const nextY=near?Math.max(-2,Math.min(2,y/40)):0;
    if(nextX!==lookX||nextY!==lookY){
      lookX=nextX;lookY=nextY;
      if(!raf)raf=requestAnimationFrame(()=>{raf=0;root.style.setProperty('--look-x',lookX+'px');root.style.setProperty('--look-y',lookY+'px');});
    }
    if(near)circle(event.clientX,event.clientY,rect,performance.now());else points=[];
    lastActive=Date.now();
  });
  on(button,'pointerenter',event=>{if(event.pointerType==='touch')return;hovering=true;lastActive=Date.now();render();});
  on(button,'pointerleave',()=>{hovering=false;lookX=0;lookY=0;root.style.setProperty('--look-x','0px');root.style.setProperty('--look-y','0px');render();});
  on(button,'focus',()=>{keyboardFocused=button.matches(':focus-visible');render();});
  on(button,'blur',()=>{keyboardFocused=false;render();});
  on(button,'click',event=>{
    lastActive=Date.now();
    if(event.detail===0){clear('click');play('happy');return;}
    if(timers.has('click')){clear('click');play('delighted');}
    else later('click',()=>play('happy'),360);
  });
  on(setting,'change',()=>{
    preference=setting.value;
    try{localStorage.setItem('clira-character-motion',preference);}catch{ /* Optional storage. */ }
    points=[];temporary=null;clear('reaction');render();idleTimers();
  });
  on(media,'change',()=>{points=[];render();idleTimers();});
  function suspend() {
    hidden=true;hiddenAt=Date.now();
    for(const id of timers.values())clearTimeout(id);timers.clear();
    cancelAnimationFrame(raf);raf=0;temporary=null;typing=false;hovering=false;keyboardFocused=false;points=[];lookX=0;lookY=0;root.style.setProperty('--look-x','0px');root.style.setProperty('--look-y','0px');
    root.classList.remove('is-blinking','is-tilting');render();
  }
  function resume() {
    hidden=document.hidden;
    if(hidden)return;
    if(Date.now()-Math.min(hiddenAt||Date.now(),lastActive)>30000)react('greeting');
    render();idleTimers();
  }
  on(document,'visibilitychange',()=>{if(document.hidden)suspend();else resume();});
  on(window,'pagehide',event=>{if(event.persisted)suspend();else destroy();});
  on(window,'pageshow',resume);
  on(window,'focus',()=>{if(!document.hidden&&Date.now()-lastActive>30000)react('greeting');lastActive=Date.now();});
  function destroy() {
    if(destroyed)return;destroyed=true;abort.abort();for(const id of timers.values())clearTimeout(id);
    timers.clear();pending.clear();approvalSources.clear();points=[];cancelAnimationFrame(raf);raf=0;root.classList.remove('is-blinking','is-tilting');root.dataset.motion='off';root.style.setProperty('--look-x','0px');root.style.setProperty('--look-y','0px');
  }
  window.cliraCharacter=Object.freeze({emit,destroy,get state(){return state;},get motion(){return mode();},
    get diagnostics(){return {pending:pending.size,timers:timers.size,points:points.length,destroyed};}});
  render();idleTimers();
  fetch('/static/assets/clira-live.svg',{signal:abort.signal}).then(response=>{
    if(!response.ok)throw new Error('Artwork unavailable');return response.text();
  }).then(text=>{
    if(destroyed)return;
    const svg=new DOMParser().parseFromString(text,'image/svg+xml').documentElement;
    if(svg.localName!=='svg'||svg.querySelector('script,foreignObject'))throw new Error('Invalid artwork');
    document.getElementById('characterArtwork').replaceChildren(document.importNode(svg,true));
    document.getElementById('characterFallback').hidden=true;root.dataset.ready='true';
  }).catch(error=>{if(error.name!=='AbortError'){artworkFailed=true;root.dataset.ready='false';idleTimers();render();status.textContent='Clira · portrait fallback';}});
})();
