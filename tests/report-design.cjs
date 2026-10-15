const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
for(const lang of ['ar','en','tr']){
const window=require('./i18n.cjs')(lang).window;
vm.runInNewContext(fs.readFileSync('nahda-fleet/report-design.js','utf8'),{window,document:{getElementById:()=>({textContent:'QA'})}});
const html=window.KhotwatiReport.render({rows:[{plate:'<img onerror=alert(1)>',company_id:'a',driver:'سائق',destination:'حلب',place:'سرمدا',note:'<script>bad</script>',last_update:'2026-10-14',status:'تم التسليم'}],date:'2026-10-15',company:{name:'شركة',logo_data:'javascript:alert(1)'},companyName:()=> 'شركة',stamp:x=>x,day:x=>x});
assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('<script>'));assert.ok(!html.includes('javascript:'));assert.ok(html.includes('سرمدا'));assert.ok(html.includes('report-stale'));assert.equal((html.match(/<th>/g)||[]).length,6);assert.ok(html.includes('report-signoff'));
}
console.log('PASS: report AR/EN/TR rendering, original location preserved, escaped data, safe logo, stale indicator and six-column layout');
