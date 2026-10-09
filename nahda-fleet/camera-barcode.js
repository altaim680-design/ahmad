'use strict';
(function(scope){
 function decodeCanvas(canvas){
  const z=scope.ZXing,ctx=canvas.getContext('2d',{willReadFrequently:true});
  const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
  const luminance=new Uint8ClampedArray(canvas.width*canvas.height);
  for(let i=0,j=0;i<pixels.length;i+=4,j++)luminance[j]=(pixels[i]+2*pixels[i+1]+pixels[i+2])>>2;
  const hints=new Map([[z.DecodeHintType.POSSIBLE_FORMATS,[z.BarcodeFormat.CODE_128]],[z.DecodeHintType.TRY_HARDER,true]]);
  const reader=new z.MultiFormatReader();
  try{return reader.decode(new z.BinaryBitmap(new z.HybridBinarizer(new z.RGBLuminanceSource(luminance,canvas.width,canvas.height))),hints).getText();}
  catch(e){if(['NotFoundException','ChecksumException','FormatException'].includes(e?.name)||e instanceof z.NotFoundException||e instanceof z.ChecksumException||e instanceof z.FormatException)return '';throw e;}
 }
 function create(options){
  const {video,canvas,onResult,onError}=options;
  const getMedia=options.getUserMedia||((c)=>navigator.mediaDevices.getUserMedia(c));
  const decode=options.decode||decodeCanvas,schedule=options.setTimeout||setTimeout,cancel=options.clearTimeout||clearTimeout;
  let generation=0,stream=null,timer=null,last='',hits=0;
  const release=s=>s?.getTracks().forEach(track=>track.stop());
  function stop(){generation++;if(timer!==null)cancel(timer);timer=null;release(stream);stream=null;video.pause();video.srcObject=null;last='';hits=0;}
  async function start(){
   stop();const run=generation;
   try{
    const acquired=await getMedia({audio:false,video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}}});
    if(run!==generation){release(acquired);return;}
    stream=acquired;video.srcObject=stream;await video.play();if(run!==generation)return;
    options.onReady?.();
    const tick=async()=>{
     if(run!==generation)return;
     try{
      if(video.readyState>=2&&video.videoWidth){
       const scale=Math.min(1,1280/video.videoWidth);canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
       canvas.getContext('2d',{willReadFrequently:true}).drawImage(video,0,0,canvas.width,canvas.height);
       const code=String(await decode(canvas)||'').trim().toUpperCase();if(run!==generation)return;
       if(/^KW[0-9]{10}$/.test(code)){hits=last===code?hits+1:1;last=code;if(hits>=2){stop();onResult(code);return;}}
      }
     }catch(e){if(run===generation){stop();onError(e);}return;}
     if(run===generation)timer=schedule(tick,180);
    };
    await tick();
   }catch(e){if(run===generation){stop();onError(e);}}
  }
  return {start,stop};
 }
 scope.KhotwatiCamera={create,decodeCanvas};
 if(typeof module==='object'&&module.exports)module.exports=scope.KhotwatiCamera;
})(typeof window==='object'?window:globalThis);
