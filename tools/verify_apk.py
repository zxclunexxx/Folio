#!/usr/bin/env python3
"""Structural/signature checks; not an Android installation/runtime test."""
import io,sys,json,hashlib,zlib,struct as s,zipfile
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
p=Path(sys.argv[1]);raw=p.read_bytes();checks=[]
u32=lambda b,o:s.unpack_from('<I',b,o)[0]
u16=lambda b,o:s.unpack_from('<H',b,o)[0]
u64=lambda b,o:s.unpack_from('<Q',b,o)[0]
def ok(text,test=True):
 assert test,text
 checks.append(text)
def lp(b,o=0):n=u32(b,o);assert o+4+n<=len(b);return b[o+4:o+4+n],o+4+n
end=raw.rfind(b'PK\x05\x06');cd=u32(raw,end+16)
ok('ZIP central directory points to valid header',raw[cd:cd+4]==b'PK\x01\x02')
ok('APK v2 magic',raw[cd-16:cd]==b'APK Sig Block 42')
blocksize=u64(raw,cd-24);start=cd-blocksize-8;ok('APK signing block length',u64(raw,start)==blocksize)
q=start+8;v2=None
while q<cd-24:
 n=u64(raw,q);ident=u32(raw,q+8)
 if ident==0x7109871a:v2=raw[q+12:q+8+n]
 q+=8+n
ok('One APK v2 block',v2 is not None)
signers,_=lp(v2);signer,_=lp(signers);signed,a=lp(signer);sigs,a=lp(signer,a);pub,a=lp(signer,a)
signature_record,_=lp(sigs);ok('RSA SHA-256 signature algorithm',u32(signature_record,0)==0x0103);signature,_=lp(signature_record,4)
key=serialization.load_der_public_key(pub);key.verify(signature,signed,padding.PKCS1v15(),hashes.SHA256());ok('Cryptographic APK v2 signature verifies')
digests,a=lp(signed);certs,a=lp(signed,a);certbytes,_=lp(certs);cert=x509.load_der_x509_certificate(certbytes)
ok('Signing certificate matches public key',cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)==pub)
dr,_=lp(digests);expected,_=lp(dr,4);tail=bytearray(raw[end:]);tail[16:20]=s.pack('<I',start)
h=[]
for section in [raw[:start],raw[cd:end],tail]:
 for x in range(0,len(section),1048576):
  b=section[x:x+1048576];h.append(hashlib.sha256(b'\xa5'+s.pack('<I',len(b))+b).digest())
actual=hashlib.sha256(b'\x5a'+s.pack('<I',len(h))+b''.join(h)).digest()
ok('APK v2 content digests match all ZIP sections',actual==expected)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 ok('ZIP CRCs verify',z.testzip() is None)
 for name in ['AndroidManifest.xml','classes.dex','resources.arsc','assets/www/index.html','assets/www/app.js','assets/www/style.css','assets/www/assets/icons.js']:ok('Contains '+name,name in z.namelist())
 info=z.getinfo('resources.arsc');o=info.header_offset;dataoff=o+30+u16(raw,o+26)+u16(raw,o+28)
 ok('resources.arsc is stored and 4-byte aligned',info.compress_type==0 and dataoff%4==0)
 d=z.read('classes.dex');ok('DEX 035 header/file size',d[:8]==b'dex\n035\0' and u32(d,32)==len(d));ok('DEX SHA-1',d[12:32]==hashlib.sha1(d[32:]).digest());ok('DEX Adler-32',u32(d,8)==zlib.adler32(d[12:]))
 def leb(b,o):
  v=0;shift=0
  while True:
   x=b[o];o+=1;v|=(x&127)<<shift
   if not x&128:return v,o
   shift+=7
 ns,so=u32(d,56),u32(d,60);strings=[]
 for j in range(ns):
  off=u32(d,so+j*4);_,off=leb(d,off);strings.append(d[off:d.index(0,off)].decode())
 ok('DEX strings sorted without duplicates',strings==sorted(set(strings)))
 nt,to=u32(d,64),u32(d,68);types=[strings[u32(d,to+j*4)] for j in range(nt)]
 nm,mo=u32(d,88),u32(d,92);methods=[]
 for j in range(nm):
  o=mo+j*8;methods.append(types[u16(d,o)]+'->'+strings[u32(d,o+4)])
 classoff=u32(d,100);data=u32(d,classoff+24);sizes=[]
 for j in range(4):v,data=leb(d,data);sizes.append(v)
 for _ in range(sizes[0]+sizes[1]):_,data=leb(d,data);_,data=leb(d,data)
 codes=[]
 for count in sizes[2:]:
  idx=0
  for _ in range(count):diff,data=leb(d,data);idx+=diff;acc,data=leb(d,data);off,data=leb(d,data);codes.append((methods[idx],off))
 ok('Four expected MainActivity methods',sorted(x[0].split('->')[1] for x in codes)==['<init>','onBackPressed','onCreate','onDestroy'])
 widths={0x0e:1,0x12:1,0x14:3,0x6e:3,0x70:3,0x6f:3,0x22:2,0x0c:1,0x0a:1,0x5b:2,0x54:2,0x38:2,0x1a:2}
 for method,off in codes:
  regs=u16(d,off);count=u32(d,off+12);words=[u16(d,off+16+2*j) for j in range(count)];k=0;bounds=set();branches=[]
  while k<count:
   bounds.add(k);op=words[k]&255;assert op in widths,(method,hex(op));w=widths[op]
   if op in [0x6e,0x70,0x6f]:assert words[k+1]<nm
   if op==0x22:assert words[k+1]<nt
   if op==0x1a:assert words[k+1]<ns
   if op==0x38:branches.append(k+s.unpack('<h',s.pack('<H',words[k+1]))[0])
   k+=w
  ok('DEX instruction boundaries/references: '+method,k==count and all(x in bounds for x in branches))
 def pool(b,o):
  hs=u16(b,o+2);count=u32(b,o+8);data=o+u32(b,o+20);result=[]
  for j in range(count):
   q=data+u32(b,o+hs+j*4)
   n=b[q];q+=2 if n&128 else 1
   n=b[q];q+=1
   if n&128:n=((n&127)<<8)|b[q];q+=1
   result.append(b[q:q+n].decode('utf8'))
  return result
 m=z.read('AndroidManifest.xml');ok('Binary AndroidManifest header',u16(m,0)==3 and u32(m,4)==len(m));ms=pool(m,8);o=8;attrs={}
 while o<len(m):
  t,hs,sz=u16(m,o),u16(m,o+2),u32(m,o+4);assert sz>=8 and o+sz<=len(m)
  if t==0x102:
   tag=ms[u32(m,o+20)];count=u16(m,o+28);a=o+16+u16(m,o+24)
   for j in range(count):
    r=a+j*20;name=ms[u32(m,r+4)];typ=m[r+15];v=u32(m,r+16);attrs[tag+'.'+name]=ms[v] if typ==3 else v
  o+=sz
 ok('Manifest Android package',attrs['manifest.package']=='com.lunex.folio')
 ok('Manifest min SDK 26 / target SDK 34',attrs['uses-sdk.minSdkVersion']==26 and attrs['uses-sdk.targetSdkVersion']==34)
 ok('Manifest exported launcher Activity',attrs['activity.name']=='.MainActivity' and attrs['activity.exported']==1)
 ok('Manifest backups and cleartext disabled',attrs['application.allowBackup']==0 and attrs['application.usesCleartextTraffic']==0)
 ok('No Android permissions requested',not any(x.startswith('uses-permission') for x in attrs))
 res=z.read('resources.arsc');ok('Resource table header',u16(res,0)==2 and u32(res,4)==len(res));g=pool(res,12);ok('Launcher icon resource path',g==['res/drawable/ic_launcher.png'])
 # Validate every nested resource chunk and key/string offsets.
 o=12+u32(res,16);ok('Resource package ID',u16(res,o)==0x200 and u32(res,o+8)==0x7f)
 pkgsize=u32(res,o+4);inner=o+u16(res,o+2)
 while inner<o+pkgsize:
  t,hs,sz=u16(res,inner),u16(res,inner+2),u32(res,inner+4);assert sz>=hs and inner+sz<=o+pkgsize
  if t==0x201:
   entries=inner+u32(res,inner+16);index=u32(res,inner+hs);entry=entries+index;ok('Launcher resource type and entry',res[inner+8]==1 and u32(res,inner+12)==1 and u16(res,entry)==8 and res[entry+11]==3 and u32(res,entry+12)==0)
  inner+=sz
report={'apk':p.name,'sha256':hashlib.sha256(raw).hexdigest(),'checksPassed':len(checks),'checks':checks,'limitation':'Static structure and cryptographic checks only. No Android installation or execution performed.'}
(Path(__file__).resolve().parent.parent/'docs/apk-verification.json').write_text(json.dumps(report,indent=2))
print('APK:',len(checks),'static/signature checks passed.')
