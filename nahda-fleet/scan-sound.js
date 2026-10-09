'use strict';
(function(scope){let context=null;
 function unlock(){try{const Audio=scope.AudioContext||scope.webkitAudioContext;if(!Audio)return;if(!context)context=new Audio();if(context.state==='suspended')context.resume().catch(()=>{});}catch{}}
 function play(){try{if(!context||context.state!=='running')return;const tone=context.createOscillator(),gain=context.createGain(),now=context.currentTime;tone.type='sine';tone.frequency.setValueAtTime(1100,now);gain.gain.setValueAtTime(0,now);gain.gain.linearRampToValueAtTime(.12,now+.01);gain.gain.exponentialRampToValueAtTime(.001,now+.16);tone.connect(gain);gain.connect(context.destination);tone.start(now);tone.stop(now+.18);tone.onended=()=>{tone.disconnect();gain.disconnect();};}catch{}}
 scope.KhotwatiScanSound={unlock,play};
})(window);
