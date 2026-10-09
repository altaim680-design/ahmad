"""Decode rendered bars independently using ReportLab's Code 128 symbol table."""
import subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from reportlab.graphics.barcode.code128 import _patterns
src=subprocess.check_output(['node',str(Path(__file__).with_name('trip-barcodes.cjs')),'--svg'],text=True)
svg=ET.fromstring(src[src.index('<svg'):])
rects=[r for r in svg.iter('{http://www.w3.org/2000/svg}rect') if 'x' in r.attrib]
n=int((max(float(r.attrib['x']) for r in rects)-20)/2)+1
bits=['0']*n
for r in rects:bits[int((float(r.attrib['x'])-20)/2)]='1'
bits=''.join(bits)
def pattern(s):return ''.join(('1' if c.isupper() else '0')*(ord(c.lower())-ord('a')+1) for c in s)
inverse={pattern(v):k for k,v in _patterns.items()}
assert bits[-13:]==pattern(_patterns[106])
words=[inverse[bits[i:i+11]] for i in range(0,len(bits)-13,11)]
assert (words[0]+sum(i*c for i,c in enumerate(words[1:-1],1)))%103==words[-1]
mode={103:'A',104:'B',105:'C'}[words[0]];decoded=''
for c in words[1:-1]:
 if c==99:mode='C'
 elif c==100:mode='B'
 elif c==101:mode='A'
 elif mode=='C':decoded+=f'{c:02d}'
 else:decoded+=chr(c+32)
assert decoded=='KW0000098765',decoded
print('PASS: independently decoded rendered SVG bars and verified CODE128 checksum:',decoded)
