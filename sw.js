const CACHE='seek-shell-v5';
const SHELL=['./','./index.html','./manifest.webmanifest','./icon.svg','./opensearch.xml','./seek-index.json'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('seek-shell-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET')return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin)return;
  if(req.mode==='navigate'||url.pathname.endsWith('/index.html')){
    event.respondWith(fetch(req,{cache:'no-store'}).then(response=>{
      if(response.ok)caches.open(CACHE).then(cache=>cache.put('./index.html',response.clone()));
      return response;
    }).catch(()=>caches.match('./index.html').then(hit=>hit||caches.match('./')));
    return;
  }
  if(url.pathname.endsWith('/seek-index.json')){
    event.respondWith(fetch(req,{cache:'no-store'}).then(response=>{
      if(response.ok)caches.open(CACHE).then(cache=>cache.put('./seek-index.json',response.clone()));
      return response;
    }).catch(()=>caches.match('./seek-index.json')));
    return;
  }
  event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(response=>{
    if(response.ok)caches.open(CACHE).then(cache=>cache.put(req,response.clone()));
    return response;
  })));
});
