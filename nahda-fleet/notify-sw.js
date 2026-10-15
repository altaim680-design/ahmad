'use strict';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
function safeUrl(value){try{const u=new URL(value||'/',self.location.origin);if(u.origin!==self.location.origin)return '/';if(!['/','/index.html','/driver.html'].includes(u.pathname))return '/';return u.pathname+u.search;}catch{return '/';}}
self.addEventListener('push',event=>{
 let data={};try{data=event.data?.json()||{};}catch{}
 const url=safeUrl(data.url),title=data.title||'خطواتي';
 event.waitUntil(self.registration.showNotification(title,{body:data.body||'لديك إشعار جديد',tag:data.tag||'khotwati-notification',renotify:true,silent:false,vibrate:[180,90,180],icon:'/app-icon-192.png',badge:'/app-icon-192.png',data:{url}}));
});
self.addEventListener('notificationclick',event=>{
 event.notification.close();const url=safeUrl(event.notification.data?.url);
 event.waitUntil((async()=>{const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});for(const client of windows){try{const current=new URL(client.url);if(current.origin===self.location.origin){await client.focus();client.navigate(url);return;}}catch{}}await self.clients.openWindow(url);})());
});
