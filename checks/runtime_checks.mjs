// Production silent player exercised in a deterministic DOM; no layout emulation.
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync} from 'node:fs';
const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
const runtime=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].at(-1)[1];
const art=JSON.parse(html.match(/<script id="art-data"[^>]*>([\s\S]*?)<\/script>/)[1]);
const cases=[],instances=[];
function harness({reduced=false,auto=true}={}) {
  const h={now:0,frames:[],images:[],events:[],announcements:[],audioAttempts:0,bounds:{width:1280,height:650},maxOwned:0};instances.push(h);
  class Element {
    constructor(tag='div',attrs={}) {
      this.tagName=tag.toUpperCase();this.id=attrs.id||'';this.attrs={...attrs};this.dataset={};this.listeners=new Map();this.children=[];this._text='';
      for(const [k,v] of Object.entries(attrs))if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v;
      this.hidden='hidden' in attrs;this.disabled='disabled' in attrs;this.checked=false;
      this.style={setProperty(k,v){this[k]=v;}};
    }
    set textContent(v){this._text=String(v);if(this.attrs.id==='announcement')h.announcements.push(this._text);}
    get textContent(){return this._text;}
    setAttribute(k,v){this.attrs[k]=String(v);}
    getAttribute(k){return this.attrs[k]??null;}
    removeAttribute(k){delete this.attrs[k];if(k.startsWith('data-'))delete this.dataset[k.slice(5)];}
    addEventListener(k,fn){if(!this.listeners.has(k))this.listeners.set(k,[]);this.listeners.get(k).push(fn);}
    dispatch(type,extra={}){const event={type,target:this,preventDefault(){this.defaultPrevented=true;},defaultPrevented:false,...extra};for(const fn of this.listeners.get(type)||[])fn(event);return event;}
    click(){if(!this.disabled)this.dispatch('click');}
    closest(){return ['BUTTON','INPUT','SELECT','TEXTAREA','A'].includes(this.tagName)?this:null;}
    focus(){h.focus=this;}
    getBoundingClientRect(){return h.bounds;}
    replaceChildren(...children){this.children=children;}
  }
  const elements=new Map();
  for(const m of html.matchAll(/<([a-z]+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)) {
    const attrs=Object.fromEntries([...m[2].matchAll(/([\w:-]+)="([^"]*)"/g)].map(a=>[a[1],a[2]]));
    for(const key of ['hidden','disabled'])if(new RegExp('\\b'+key+'(?:\\s|$)').test(m[2]))attrs[key]='';
    elements.set(m[3],new Element(m[1],attrs));
  }
  elements.get('art-data')._text=JSON.stringify(art);
  for(const m of html.matchAll(/<section class="beat text-card" id="([^"]+)"[^>]*><p class="story">([^<]*)<\/p>/g))elements.get(m[1])._text=m[2];
  h.ui=id=>elements.get(id);h.body=new Element('body');h.beats=[...elements.values()].filter(e=>(e.attrs.class||'').split(' ').includes('beat'));
  h.slots=new Map(Object.keys(art).map(k=>[k,new Element()]));
  const document=new Element('document');document.hidden=false;document.getElementById=h.ui;document.querySelectorAll=()=>h.beats;document.querySelector=s=>h.slots.get(s.match(/data-slot="([^"]+)"/)[1]);
  const window=new Element('window');window.dispatchEvent=e=>{h.events.push(e);return true;};
  class ForbiddenAudio {constructor(){h.audioAttempts++;throw Error('Sound is forbidden in the silent release');}}
  window.AudioContext=window.webkitAudioContext=window.Audio=ForbiddenAudio;
  const motion={matches:reduced,callbacks:[],addEventListener(type,fn){this.callbacks.push(fn);}};
  class MockImage {
    constructor(){h.images.push(this);this._src='';}
    set src(value){this._src=value;h.maxOwned=Math.max(h.maxOwned,h.images.filter(i=>i.src).length);if(auto)Promise.resolve().then(()=>{if(this.src)this.resolve();});}
    get src(){return this._src;}
    removeAttribute(key){if(key==='src'){this._src='';this.cancelled=true;}}
    decode(){return this.loaded?Promise.resolve():new Promise((resolve,reject)=>{this.resolveDecode=resolve;this.rejectDecode=reject;});}
    resolve(){if(this.loaded||!this.src)return;this.loaded=true;this.onload?.();this.resolveDecode?.();}
    fail(){this.onerror?.(Error('Image unavailable'));this.rejectDecode?.(Error('Image unavailable'));}
  }
  class ResizeObserver {constructor(fn){h.resizeCallback=fn;}observe(){}}
  window.ResizeObserver=ResizeObserver;
  vm.runInNewContext(runtime,{window,document,Image:MockImage,Audio:ForbiddenAudio,AudioContext:ForbiddenAudio,ResizeObserver,matchMedia:()=>motion,performance:{now:()=>h.now},requestAnimationFrame:fn=>h.frames.push(fn),CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}}});
  h.flush=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};
  h.loadAll=async()=>{for(const image of h.images)image.resolve();await h.flush();};
  h.ready=async()=>{await h.loadAll();assert.equal(h.ui('play').disabled,false);};
  h.tick=(ms,stamp)=>{h.now+=ms;for(const fn of h.frames.splice(0))fn(stamp??h.now);};
  h.to=async(time)=>{assert(time>=h.now);while(h.now<time){h.tick(Math.min(50,time-h.now));await h.flush();}};
  h.owned=()=>h.images.filter(i=>i.src);
  h.phase=()=>h.ui('app').dataset.state;h.beat=()=>h.ui('app').dataset.beat;h.start=()=>h.ui('play').click();
  h.resize=(width,height)=>{h.bounds={width,height};h.resizeCallback();};
  h.visibility=value=>{document.hidden=value;document.dispatch('visibilitychange');};
  h.pagehide=()=>window.dispatch('pagehide');
  h.key=(key,code='',target=h.body)=>document.dispatch('keydown',{key,code,target});
  h.read=()=>{h.ui('read-mode').checked=true;h.ui('read-mode').dispatch('change');};
  h.changeMotion=value=>{motion.matches=value;for(const fn of motion.callbacks)fn();};
  return h;
}
async function test(name,fn){await fn();cases.push({name,status:'passed'});}
await test('Entry waits for just the first scene and does not eagerly allocate five images',async()=>{
  const h=harness({auto:false});assert.equal(h.images.length,1);assert(h.ui('play').disabled);
  h.tick(60000);assert.equal(h.phase(),'entry');await h.ready();assert.equal(h.owned().length,1);
});
await test('All ten exclusive beats keep exact boundaries and the title holds at 40000ms',async()=>{
  const h=harness();await h.ready();h.start();
  for(const [at,id] of [[0,'card-views'],[3000,'scene-live'],[8000,'card-legend'],[13000,'scene-legend'],[17000,'card-stream'],[20000,'scene-cut'],[24000,'card-brave'],[27000,'scene-gap'],[31000,'card-rolling'],[34000,'scene-descent']]) {
    await h.to(at);assert.equal(h.beat(),id);assert.equal(h.beats.filter(b=>!b.hidden).length,1);
    assert(h.beats.filter(b=>b.hidden).every(b=>b.attrs['aria-hidden']==='true'));
    assert(h.owned().length<=2);
  }
  await h.to(39999);assert.equal(h.phase(),'playing');await h.to(40000);assert.equal(h.phase(),'end');
  assert(h.beats.every(b=>b.hidden));assert.equal(h.owned().length,0);assert.equal(h.announcements.length,11);
  h.tick(60000);assert.equal(h.phase(),'end');assert.equal(h.owned().length,0);
});
await test('Fades, bounded zoom, text/art exclusion and per-beat announcements are retained',async()=>{
  const h=harness();await h.ready();h.start();await h.to(3125);
  assert.equal(h.ui('scene-live').style.opacity,'0.5');assert.equal(Number(h.ui('scene-live').style['--scale']),1.0005);
  await h.to(7990);assert.equal(h.ui('scene-live').style.opacity,'0.04');await h.to(8000);
  assert.equal(h.beat(),'card-legend');assert(h.ui('scene-live').hidden);assert(h.ui('card-legend').textContent.includes('“They say'));
  assert(h.slots.get('live').children.length===0);assert(!h.images[0].src);
});
await test('Pause/Resume retain elapsed time and zoom',async()=>{
  const h=harness();await h.ready();h.start();await h.to(13500);h.ui('pause').click();const zoom=h.ui('scene-legend').style['--scale'];
  h.tick(5000);assert.equal(h.phase(),'paused');assert.equal(h.ui('scene-legend').style['--scale'],zoom);
  h.ui('pause').click();await h.to(44999);assert.equal(h.phase(),'playing');await h.to(45000);assert.equal(h.phase(),'end');
});
await test('Visibility and pagehide require explicit Resume',async()=>{
  const h=harness();await h.ready();h.start();await h.to(4000);h.visibility(true);h.tick(5000);h.visibility(false);
  assert.equal(h.phase(),'paused');h.ui('pause').click();assert.equal(h.phase(),'playing');h.pagehide();assert.equal(h.phase(),'paused');
});
await test('Slow art freezes the cinematic at its image boundary, without consuming its fade',async()=>{
  const h=harness({auto:false});await h.ready();h.start();h.tick(3200);await h.loadAll();
  h.tick(4800);assert.equal(h.beat(),'card-legend');h.tick(5000);assert.equal(h.phase(),'playing');
  // Legend was resolved above; let the cut remain deliberately undecoded.
  h.tick(4000);assert.equal(h.beat(),'card-stream');h.tick(3000);assert.equal(h.phase(),'buffering');
  assert.equal(h.beat(),'scene-cut');assert.equal(h.ui('scene-cut').style.opacity,'0');
  h.tick(6000);assert.equal(h.phase(),'buffering');await h.loadAll();assert.equal(h.phase(),'playing');
  assert.equal(h.ui('scene-cut').style.opacity,'0');h.tick(125);assert.equal(h.ui('scene-cut').style.opacity,'0.5');
});
await test('Pause or background during buffering prevents auto-resume when decoding completes',async()=>{
  for(const background of [false,true]) {
    const h=harness({auto:false});await h.ready();h.read();h.start();h.ui('next').click();await h.flush();
    h.ui('next').click();h.ui('next').click();assert.equal(h.phase(),'buffering');
    if(background)h.visibility(true);else h.ui('pause').click();
    await h.loadAll();if(background)h.visibility(false);assert.equal(h.phase(),'paused');
    h.ui('pause').click();assert.equal(h.phase(),'reading');
  }
});
await test('Reading holds every card/image, supports Back and waits for Finish',async()=>{
  const h=harness();await h.ready();h.read();h.start();assert(h.ui('back').disabled);
  for(let i=0;i<10;i++){
    await h.flush();const id=h.beat();h.tick(30000);await h.flush();assert.equal(h.beat(),id);
    if(i===9)assert.equal(h.ui('next').textContent,'Finish');h.ui('next').click();
  }
  assert.equal(h.phase(),'end');assert.equal(h.owned().length,0);h.ui('replay').click();await h.flush();
  h.ui('next').click();await h.flush();h.ui('back').click();assert.equal(h.beat(),'card-views');
});
await test('Native keyboard controls, Space, Escape and reading arrows are preserved',async()=>{
  const h=harness();await h.ready();h.start();h.key(' ','Space');assert.equal(h.phase(),'paused');
  assert.equal(h.key(' ','Space',h.ui('pause')).defaultPrevented,false);assert.equal(h.phase(),'paused');
  h.key(' ','Space');assert.equal(h.phase(),'playing');h.key('Escape','',h.ui('pause'));assert.equal(h.phase(),'end');
  h.read();h.ui('replay').click();await h.flush();h.key('ArrowRight');assert.equal(h.beat(),'scene-live');
  h.key('ArrowLeft');assert.equal(h.beat(),'card-views');h.key('ArrowRight','',h.ui('read-mode'));assert.equal(h.beat(),'card-views');
});
await test('Paused rotation retains visible old art, beat, time and zoom during replacement',async()=>{
  const h=harness({auto:false});await h.ready();h.start();h.tick(3500);await h.loadAll();h.ui('pause').click();
  const zoom=h.ui('scene-live').style['--scale'];const old=h.slots.get('live').children[0];
  h.resize(390,740);assert.equal(h.slots.get('live').children[0],old);assert.equal(h.owned().length,2);
  h.tick(9000);await h.loadAll();assert.equal(h.ui('app').dataset.art,'mobile');assert.equal(h.phase(),'paused');
  assert.equal(h.beat(),'scene-live');assert.equal(h.ui('scene-live').style['--scale'],zoom);assert(!old.src);
});
await test('Playing rotation uses actual stage aspect and never resets progress',async()=>{
  const h=harness();await h.ready();h.start();await h.to(13500);h.resize(390,740);await h.flush();await h.to(14500);
  assert.equal(h.phase(),'playing');assert.equal(h.beat(),'scene-legend');assert.equal(h.ui('app').dataset.art,'mobile');
  assert(Number(h.ui('scene-legend').style['--scale'])>1);await h.to(40000);assert.equal(h.phase(),'end');
});
await test('Rapid rotations and reading navigation abort obsolete sources; stale loads never win',async()=>{
  const h=harness({auto:false});await h.ready();h.read();h.start();h.ui('next').click();
  h.resize(390,740);const obsolete=h.owned().find(i=>i.src.includes('_mobile'));h.resize(1280,650);
  obsolete.resolve();await h.flush();assert.equal(h.ui('app').dataset.art,'desktop');
  for(let i=0;i<7;i++)h.ui('next').click();assert.equal(h.beat(),'card-rolling');
  await h.loadAll();assert(h.owned().every(i=>i.src.includes('05_descent_desktop')));assert(h.maxOwned<=2);
});
await test('Loading failure exposes retry and does not strand the clock or navigation',async()=>{
  const h=harness({auto:false});h.images[0].fail();await h.flush();assert.equal(h.ui('play').textContent,'Try again');
  assert.equal(h.ui('play').disabled,false);h.start();await h.ready();h.read();h.start();h.ui('next').click();
  h.ui('next').click();const bad=h.owned()[0];bad.fail();await h.flush();h.ui('next').click();
  assert.equal(h.phase(),'buffering');assert.equal(h.ui('pause').textContent,'Try again');h.ui('pause').click();
  await h.loadAll();assert.equal(h.phase(),'reading');h.ui('skip').click();assert.equal(h.owned().length,0);
});
await test('Repeated Skip/Replay clears owned art, keeps mode, one RAF and stable listeners',async()=>{
  for(const reading of [false,true]) {
    const h=harness();await h.ready();if(reading)h.read();h.start();const listeners=h.ui('pause').listeners.get('click').length;
    for(let i=0;i<6;i++) {
      await h.flush();h.tick(4000);await h.flush();h.ui('skip').click();assert.equal(h.owned().length,0);
      h.ui('replay').click();await h.flush();assert.equal(h.beat(),'card-views');assert.equal(h.phase(),reading?'reading':'playing');assert.equal(h.frames.length,1);
    }
    assert.equal(h.ui('pause').listeners.get('click').length,listeners);
  }
});
await test('Reduced motion removes fades/zoom, including changes during playback',async()=>{
  const h=harness({reduced:true});await h.ready();h.start();await h.to(3125);
  assert.equal(h.ui('scene-live').style.opacity,'1');assert.equal(h.ui('scene-live').style['--scale'],'1');
  h.changeMotion(false);assert.equal(h.ui('scene-live').style.opacity,'0.5');h.changeMotion(true);assert.equal(h.ui('scene-live').style['--scale'],'1');
});
await test('Fresh callback time handles stale RAF timestamps; start hook fires once per activation',async()=>{
  const h=harness();await h.ready();h.start();await h.to(39900);h.tick(250,39950);assert.equal(h.phase(),'end');
  h.ui('enter').click();assert.equal(h.events.length,1);h.ui('enter').click();assert.equal(h.events.length,2);assert.equal(h.phase(),'end');
  assert(h.events.every(e=>e.type==='minegame:start'&&e.detail.source==='mine-game-intro'));
});
await test('Every tested path owns at most two sourced images and uses no audio engine',async()=>{
  assert(instances.every(h=>h.maxOwned<=2 && !h.ui('sound') && h.audioAttempts===0));
});
const report={status:'passed',release:'v6_lite',scope:'production JS in a deterministic DOM; not native layout or RAM measurement',runtime_sha256:createHash('sha256').update(runtime).digest('hex'),audio_attempts:instances.reduce((n,h)=>n+h.audioAttempts,0),max_owned_images:Math.max(...instances.map(h=>h.maxOwned)),cases};
writeFileSync(new URL('../runtime_checks.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
