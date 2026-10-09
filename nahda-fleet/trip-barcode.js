'use strict';
(function(scope){
 const normalize=value=>String(value??'').trim().toUpperCase();
 const valid=value=>/^KW[0-9]{10}$/.test(normalize(value));
 function svg(value,encode=scope.JsBarcode){
  const code=normalize(value);if(!valid(code)||typeof encode!=='function')throw new Error('Barcode unavailable');
  const output={};encode(output,code,{format:'CODE128',displayValue:false,width:2,height:80,margin:20});
  const bits=output.encodings.map(e=>e.data).join('');const width=bits.length*2+40;
  let bars='';for(let i=0;i<bits.length;i++)if(bits[i]==='1')bars+='<rect x="'+(20+i*2)+'" y="12" width="2" height="80"/>';
  return '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="'+code+'" width="'+width+'" height="124" viewBox="0 0 '+width+' 124" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="white"/><g fill="black">'+bars+'</g><text x="'+width/2+'" y="115" text-anchor="middle" font-family="monospace" font-size="18" fill="black">'+code+'</text></svg>';
 }
 scope.KhotwatiBarcode={normalize,valid,svg};
 if(typeof module==='object'&&module.exports)module.exports=scope.KhotwatiBarcode;
})(typeof window==='object'?window:globalThis);
