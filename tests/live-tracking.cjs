const assert=require('node:assert/strict');
const Tracker=require('../nahda-fleet/live-tracking.js');
(async()=>{
let now=100000,good,bad,tick,clears=0,requests=[],mode='ok',resolvePending;
const geo={watchPosition(g,b){good=g;bad=b;return 1},clearWatch(){clears++},getCurrentPosition(g){g(point())}};
const point=(age=0)=>({timestamp:now-age,coords:{latitude:36,longitude:37,accuracy:12}});
const events=[];
const tracker=new Tracker({geo,now:()=>now,every:f=>(tick=f,1),cancel:()=>{},onState:s=>events.push(s),send:async(p,trip,signal)=>{requests.push({trip,signal});if(mode==='wait')await new Promise(r=>resolvePending=r);if(mode==='blocked')throw Object.assign(new Error('closed'),{status:403});return {time:now};}});
tracker.start('a');await good(point());assert.equal(requests.length,1);
await good(point());assert.equal(requests.length,1,'throttle');
now+=30000;await good(point(50000));assert.equal(requests.length,1,'stale GPS ignored');
await good(point());assert.equal(requests.length,2,'recurring send');
const oldGood=good;tracker.pause();now+=30000;await oldGood(point());assert.equal(requests.length,2,'hidden callbacks ignored');
tracker.resume();await good(point());assert.equal(requests.length,3);
mode='wait';now+=30000;const pending=good(point());assert.equal(requests.length,4);tracker.stop();assert.equal(requests[3].signal.aborted,true);resolvePending();await pending;assert.equal(events.at(-1),'stopped');
mode='ok';tracker.start('b');await good(point());assert.equal(requests.at(-1).trip,'b');bad({code:1});assert.equal(tracker.active,false);
mode='blocked';tracker.start('b');await good(point());assert.equal(tracker.active,false);assert.equal(events.at(-1),'blocked');assert.ok(clears>0);
console.log('PASS: recurrent updates, throttle, stale GPS, pause/resume, cancellation, trip isolation, permission denial, revoked trip');
})().catch(e=>{console.error(e);process.exit(1)});
