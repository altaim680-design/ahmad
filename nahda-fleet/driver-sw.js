'use strict';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('push',event=>{
 let data={};try{data=event.data?.json()||{};}catch{}
 let url='/driver.html';try{const u=new URL(data.url,self.location.origin);if(u.origin===self.location.origin&&u.pathname==='/driver.html')url=u.pathname+u.search;}catch{}
 event.waitUntil(self.registration.showNotification(data.title||'خطواتي',{body:data.body||'يرجى فتح الموقع وتحديث موقع السيارة',tag:data.tag||'khotwati-reminder',icon:'/app-icon.svg',data:{url}}));
});
self.addEventListener('notificationclick',event=>{event.notification.close();event.waitUntil(self.clients.openWindow(event.notification.data?.url||'/driver.html'));});
