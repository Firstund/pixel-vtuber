(()=>{
const $=id=>document.getElementById(id),P=new URLSearchParams(location.search);
const OBS=P.get('obs')==='1';if(OBS)document.body.classList.add('obs');
const LS={get:k=>{try{return localStorage.getItem('pvp_'+k)}catch(e){}},set:(k,v)=>{try{localStorage.setItem('pvp_'+k,v)}catch(e){}}};
const audio=new Audio();audio.preload='auto';
let cats=[],ci=0,ti=0,order=[],oi=0,shuffle=P.get('shuffle')==='1';
let vol=parseFloat(P.get('vol')??LS.get('vol')??'0.6');if(isNaN(vol))vol=0.6;vol=Math.min(1,Math.max(0,vol));
let fadeT=null,playing=false;const N=30;
$('bar').innerHTML='<i></i>'.repeat(N);const cells=[...$('bar').children];
const fmt=s=>{s=Math.floor(s||0);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')};
function fade(to,ms=600){return new Promise(r=>{clearInterval(fadeT);const from=audio.volume,t0=performance.now();
 fadeT=setInterval(()=>{const k=Math.min(1,(performance.now()-t0)/ms);audio.volume=from+(to-from)*k;if(k>=1){clearInterval(fadeT);r()}},30)})}
// pixel fox
(function(){const c=$('fox').getContext('2d'),m=["....o......o....","...oo......oo...","...oco....oco...","..oooooooooooo..","..oooooooooooo..",".oowwooooooowwo.",".oowkwooooowkwo.",".ooowwooooowwoo.","..ooooooooooooo.","..oowwwwwwwwoo..","...owwwkkwwwo...","....owwwwwwo....",".....oooooo.....","....pp....pp....","...ppp....ppp...","................"],
 col={o:'#ff8a4c',c:'#fff1d6',w:'#fff1d6',k:'#3a2550',p:'#ffb36b'};m.forEach((r,y)=>[...r].forEach((ch,x)=>{if(col[ch]){c.fillStyle=col[ch];c.fillRect(x,y,1,1)}}))})();
function buildOrder(){const n=cats[ci]?.tracks.length||0;order=[...Array(n).keys()];
 if(shuffle)for(let i=n-1;i>0;i--){const j=Math.random()*(i+1)|0;[order[i],order[j]]=[order[j],order[i]]}oi=0}
function render(){const c=cats[ci];$('cat').textContent=c?c.name:'-';
 $('tabs').innerHTML='';cats.forEach((k,i)=>{const b=document.createElement('button');b.textContent=(i+1)+'. '+k.name;if(i===ci)b.className='act';b.onclick=()=>setCat(i,true);$('tabs').append(b)});
 const l=$('list');l.innerHTML='';if(!c||!c.tracks.length){l.innerHTML='<li class="empty">음악을 추가해 주세요</li>';}
 else c.tracks.forEach((t,i)=>{const li=document.createElement('li');li.textContent=t.title;if(i===ti&&audio.src)li.className='cur';li.onclick=()=>{oi=order.indexOf(i);load(i,true)};l.append(li)});
 $('pp').textContent=playing?'⏸ 일시정지':'▶ 재생';$('hpp').textContent=playing?'⏸':'▶';$('shuf').checked=shuffle;$('vol').value=vol}
function setTitle(t){const mq=$('mq'),s=$('title');s.textContent=t;mq.classList.remove('run');
 requestAnimationFrame(()=>{if(s.scrollWidth>mq.clientWidth){mq.style.setProperty('--d',(s.scrollWidth/40+4)+'s');mq.classList.add('run')}})}
async function load(i,play){const c=cats[ci];if(!c||!c.tracks.length){audio.pause();audio.removeAttribute('src');playing=false;setTitle('음악을 추가해 주세요');$('dur').textContent='00:00';$('cur').textContent='00:00';upd();render();return}
 if(playing&&!audio.paused)await fade(0,500);
 ti=i;const t=c.tracks[i];const w=$('widget');w.classList.remove('swap');void w.offsetWidth;w.classList.add('swap');
 setTimeout(()=>setTitle(t.title),300);audio.src=encodeURI(t.file);audio.volume=0;render();if(play)await start()}
async function start(){if(!audio.src)return;try{await audio.play();playing=true;$('start').classList.add('hidden');fade(vol,800)}
 catch(e){playing=false;$('start').classList.remove('hidden')}render()}
async function pause(){playing=false;render();await fade(0,500);audio.pause()}
function toggle(){playing?pause():(audio.src?start():load(order[oi]??0,true))}
function step(d){const n=order.length;if(!n)return;oi=(oi+d+n)%n;if(d>0&&oi===0&&shuffle)buildOrder();load(order[oi],true)}
function setCat(i,play){if(!cats[i])return;ci=i;LS.set('cat',cats[i].id);buildOrder();load(order[0]??0,play??playing)}
function setVol(v){vol=Math.round(Math.min(1,Math.max(0,v))*100)/100;LS.set('vol',vol);clearInterval(fadeT);if(playing)audio.volume=vol;render()}
function upd(){const d=audio.duration||0,t=audio.currentTime||0;$('cur').textContent=fmt(t);$('dur').textContent=fmt(d);
 const on=d?Math.floor(t/d*N):0;cells.forEach((c,i)=>c.classList.toggle('on',i<on))}
audio.addEventListener('timeupdate',upd);audio.addEventListener('loadedmetadata',upd);
audio.addEventListener('ended',()=>step(1));
audio.addEventListener('error',()=>{console.warn('재생 실패:',audio.src);if(order.length>1)setTimeout(()=>step(1),1000)});
document.addEventListener('click',e=>{const a=e.target.closest('[data-a]')?.dataset.a;if(!a)return;
 ({prev:()=>step(-1),next:()=>step(1),toggle,cat:()=>setCat((ci+1)%cats.length,playing)})[a]()});
$('shuf').onchange=e=>{shuffle=e.target.checked;buildOrder();oi=Math.max(0,order.indexOf(ti))};
$('vol').oninput=e=>setVol(+e.target.value);
$('start').onclick=()=>start();
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'&&e.target.type!=='checkbox'&&e.target.type!=='range')return;
 if(e.code==='Space'){e.preventDefault();toggle()}else if(e.key==='ArrowRight')step(1);else if(e.key==='ArrowLeft')step(-1);
 else if(e.key==='ArrowUp'){e.preventDefault();setVol(vol+.05)}else if(e.key==='ArrowDown'){e.preventDefault();setVol(vol-.05)}
 else if(/^[1-9]$/.test(e.key))setCat(+e.key-1,true)});
fetch(P.get('tracks')||'tracks.json',{cache:'no-cache'}).then(r=>r.json()).then(j=>{cats=j.categories||[];
 const want=P.get('cat')||LS.get('cat');let i=cats.findIndex(c=>c.id===want||c.name===want);ci=i<0?0:i;
 buildOrder();load(order[0]??0,true)}).catch(e=>{console.error('tracks.json 불러오기 실패',e);setTitle('tracks.json 오류')});
window.__pv={audio,step,get state(){return{ci,ti,playing}}};
})();
