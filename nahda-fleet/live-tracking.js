'use strict';
(function(root){
class FleetLiveTracker {
 constructor({geo,send,onPosition=()=>{},onState=()=>{},now=()=>Date.now(),every=setInterval,cancel=clearInterval,interval=30000}){Object.assign(this,{geo,send,onPosition,onState,now,every,cancel,interval});this.active=false;this.generation=0;this.watch=null;this.timer=null;this.pending=null;this.lastAttempt=-Infinity;}
 start(trip){this.stop(false);this.active=true;this.trip=trip;this.lastAttempt=-Infinity;this.resume();}
 clear(){this.generation++;if(this.watch!==null)this.geo.clearWatch(this.watch);if(this.timer!==null)this.cancel(this.timer);this.watch=null;this.timer=null;this.pending?.abort();this.pending=null;}
 stop(announce=true){this.active=false;this.clear();if(announce)this.onState('stopped');}
 pause(){if(!this.active)return;this.clear();this.onState('paused');}
 resume(){if(!this.active)return;this.clear();const version=this.generation;this.onState('waiting');
  const good=p=>this.position(p,version),bad=e=>{if(version!==this.generation)return;if(e.code===1){this.stop(false);this.onState('denied');}else this.onState('gps-error');};
  const options={enableHighAccuracy:true,timeout:20000,maximumAge:0};
  try{this.watch=this.geo.watchPosition(good,bad,options);this.timer=this.every(()=>{if(version===this.generation)this.geo.getCurrentPosition(good,bad,options);},this.interval);}catch(e){this.stop(false);this.onState('denied');}
 }
 async position(p,version){
  if(!this.active||version!==this.generation)return;
  const point={latitude:p.coords.latitude,longitude:p.coords.longitude,accuracy:p.coords.accuracy,time:p.timestamp};
  if(!Number.isFinite(point.time)||this.now()-point.time>45000||!Number.isFinite(point.latitude)||!Number.isFinite(point.longitude)||!Number.isFinite(point.accuracy)){this.onState('gps-error');return;}
  this.onPosition(point);
  if(this.pending||this.now()-this.lastAttempt<this.interval)return;
  this.lastAttempt=this.now();const controller=new AbortController();this.pending=controller;this.onState('sending');
  try{const result=await this.send(point,this.trip,controller.signal);if(version===this.generation&&this.active)this.onState('sent',result);}
  catch(e){if(version!==this.generation)return;if(e.status===401||e.status===403){this.stop(false);this.onState('blocked',e);}else this.onState('network-error',e);}
  finally{if(this.pending===controller)this.pending=null;}
 }
}
if(typeof module!=='undefined'&&module.exports)module.exports=FleetLiveTracker;else root.FleetLiveTracker=FleetLiveTracker;
})(typeof window!=='undefined'?window:globalThis);
