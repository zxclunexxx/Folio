#!/usr/bin/env python3
"""Minimal offline packaging for this specific WebView host (not a Java compiler).
Emits the 4 methods matching android/.../MainActivity.java, a binary manifest,
icon resource table, and an APK v2 signature. Requires Python cryptography.
The maintainable Android build is the standard Gradle project in /android.
Specifications: source.android.com/docs/core/runtime/dex-format
and source.android.com/docs/security/features/apksigning/v2.
"""
from __future__ import annotations
import struct as st, hashlib, zlib, io, zipfile, datetime, json, argparse
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
U=lambda x:st.pack('<I',x & 0xffffffff)
H=lambda x:st.pack('<H',x & 0xffff)
Q=lambda x:st.pack('<Q',x)
def uleb(v):
 b=bytearray()
 while v>127:b.append((v&127)|128);v>>=7
 b.append(v);return bytes(b)
def align(b,n=4):b.extend(b'\0'*((-len(b))%n))
def chunk(t,header,payload=b''):
 return H(t)+H(8+len(header))+U(8+len(header)+len(payload))+header+payload

def string_pool(strings):
 data=bytearray();offsets=[]
 for s in strings:
  raw=s.encode('utf-8');offsets.append(len(data))
  def lng(x):return bytes([x]) if x<128 else bytes([(x>>8)|128,x&255])
  data+=lng(len(s.encode('utf-16-le'))//2)+lng(len(raw))+raw+b'\0'
 align(data)
 return chunk(1,st.pack('<5I',len(strings),0,0x100,28+len(strings)*4,0),b''.join(U(x) for x in offsets)+data)

ATTR={'theme':0x01010000,'label':0x01010001,'icon':0x01010002,'name':0x01010003,'exported':0x01010010,'configChanges':0x0101001f,'versionCode':0x0101021b,'versionName':0x0101021c,'windowSoftInputMode':0x0101022b,'minSdkVersion':0x0101020c,'targetSdkVersion':0x01010270,'allowBackup':0x01010280,'hardwareAccelerated':0x010102d3,'supportsRtl':0x010103af,'usesCleartextTraffic':0x010104ec}
NS='http://schemas.android.com/apk/res/android'
def manifest():
 nodes=[]
 def start(tag,attrs):nodes.append(('start',tag,attrs))
 def end(tag):nodes.append(('end',tag,[]))
 # tuple: name, type, value; package is not namespaced.
 start('manifest',[('package',3,'com.lunex.folio'),('versionCode',16,1),('versionName',3,'1.0.0')])
 start('uses-sdk',[('minSdkVersion',16,26),('targetSdkVersion',16,34)]);end('uses-sdk')
 start('application',[('label',3,'Folio'),('icon',1,0x7f010000),('allowBackup',18,0),('hardwareAccelerated',18,1),('supportsRtl',18,1),('usesCleartextTraffic',18,0)])
 start('activity',[('name',3,'.MainActivity'),('exported',18,1),('configChanges',16,0xda0),('windowSoftInputMode',16,0x10)])
 start('intent-filter',[]);start('action',[('name',3,'android.intent.action.MAIN')]);end('action');start('category',[('name',3,'android.intent.category.LAUNCHER')]);end('category');end('intent-filter');end('activity');end('application');end('manifest')
 strings=list(ATTR)+['android',NS]
 for _,tag,attrs in nodes:
  if tag not in strings:strings.append(tag)
  for name,typ,val in attrs:
   if name not in strings:strings.append(name)
   if typ==3 and val not in strings:strings.append(val)
 idx={s:j for j,s in enumerate(strings)}
 data=string_pool(strings)+chunk(0x180,b'',b''.join(U(ATTR.get(s,0)) for s in strings[:len(ATTR)]))
 nodeheader=U(1)+U(0xffffffff)
 data+=chunk(0x100,nodeheader,U(idx['android'])+U(idx[NS]))
 for kind,tag,attrs in nodes:
  if kind=='end':data+=chunk(0x103,nodeheader,U(0xffffffff)+U(idx[tag]));continue
  attrs=sorted(attrs,key=lambda a:ATTR.get(a[0],0))
  ab=b''
  for name,typ,val in attrs:
   value=idx[val] if typ==3 else val
   ab+=U(idx[NS] if name in ATTR else 0xffffffff)+U(idx[name])+U(idx[val] if typ==3 else 0xffffffff)+H(8)+bytes([0,typ])+U(value)
  extension=U(0xffffffff)+U(idx[tag])+st.pack('<6H',20,20,len(attrs),0,0,0)
  data+=chunk(0x102,nodeheader,extension+ab)
 data+=chunk(0x101,nodeheader,U(idx['android'])+U(idx[NS]))
 return chunk(3,b'',data)

def resources():
 globalpool=string_pool(['res/drawable/ic_launcher.png'])
 types=string_pool(['drawable']);keys=string_pool(['ic_launcher'])
 spec=chunk(0x202,bytes([1,0,0,0])+U(1),U(0))
 config=U(64)+bytes(60)
 # Header size = 8 + 12 + 64 = 84; one entry offset, then 16 bytes entry/value.
 typechunk=chunk(0x201,bytes([1,0,0,0])+U(1)+U(88)+config,U(0)+H(8)+H(0)+U(0)+H(8)+bytes([0,3])+U(0))
 name='com.lunex.folio'.encode('utf-16-le').ljust(256,b'\0')
 ph=U(0x7f)+name+U(288)+U(1)+U(288+len(types))+U(1)+U(0)
 package=chunk(0x200,ph,types+keys+spec+typechunk)
 return chunk(2,U(1),globalpool+package)

A='Landroid/app/Activity;';B='Landroid/os/Bundle;';CTX='Landroid/content/Context;';V='Landroid/view/View;';W='Landroid/view/Window;';WV='Landroid/webkit/WebView;';WS='Landroid/webkit/WebSettings;';WC='Landroid/webkit/WebViewClient;';CH='Landroid/webkit/WebChromeClient;';S='Ljava/lang/String;';C='Lcom/lunex/folio/MainActivity;'
def dex():
 methods=set();protos=set();types={C,A,WV};fields={(C,'web',WV)}
 def meth(cls,name,ret='V',args=()):
  m=(cls,name,ret,tuple(args));methods.add(m);protos.add((ret,tuple(args)));types.update([cls,ret,*args]);return m
 refs={}
 def M(key,cls,name,ret='V',*args):refs[key]=meth(cls,name,ret,args)
 M('ctor',C,'<init>');M('onCreate',C,'onCreate','V',B);M('back',C,'onBackPressed');M('destroy',C,'onDestroy')
 M('a_ctor',A,'<init>');M('a_create',A,'onCreate','V',B);M('request',A,'requestWindowFeature','Z','I');M('window',A,'getWindow',W);M('status',W,'setStatusBarColor','V','I');M('nav',W,'setNavigationBarColor','V','I');M('decor',W,'getDecorView',V);M('systemui',V,'setSystemUiVisibility','V','I');M('wv_ctor',WV,'<init>','V',CTX);M('settings',WV,'getSettings',WS)
 for n in ['setJavaScriptEnabled','setDomStorageEnabled','setAllowFileAccess','setAllowContentAccess','setAllowFileAccessFromFileURLs','setAllowUniversalAccessFromFileURLs','setMediaPlaybackRequiresUserGesture']:M(n,WS,n,'V','Z')
 M('mixed',WS,'setMixedContentMode','V','I');M('wc_ctor',WC,'<init>');M('wc',WV,'setWebViewClient','V',WC);M('ch_ctor',CH,'<init>');M('ch',WV,'setWebChromeClient','V',CH);M('bg',WV,'setBackgroundColor','V','I');M('content',A,'setContentView','V',V);M('load',WV,'loadUrl','V',S);M('canback',WV,'canGoBack','Z');M('goback',WV,'goBack');M('a_back',A,'onBackPressed');M('wv_destroy',WV,'destroy');M('a_destroy',A,'onDestroy')
 shorty=lambda p:''.join('L' if s.startswith(('L','[')) else s for s in [p[0],*p[1]])
 strings=sorted(set(types)|{m[1] for m in methods}|{shorty(p) for p in protos}|{'web','MainActivity.java','file:///android_asset/www/index.html'})
 si={s:j for j,s in enumerate(strings)};tt=sorted(types,key=lambda x:si[x]);ti={s:j for j,s in enumerate(tt)}
 pp=sorted(protos,key=lambda p:(ti[p[0]],tuple(ti[s] for s in p[1])));pi={p:j for j,p in enumerate(pp)}
 mm=sorted(methods,key=lambda m:(ti[m[0]],si[m[1]],pi[(m[2],m[3])]))
 mi={m:j for j,m in enumerate(mm)};fields=sorted(fields,key=lambda f:(ti[f[0]],si[f[1]],ti[f[2]]));fi={f:j for j,f in enumerate(fields)}
 so=112;to=so+len(strings)*4;po=to+len(tt)*4;fo=po+len(pp)*12;mo=fo+len(fields)*8;co=mo+len(mm)*8;dataoff=co+32
 out=bytearray(dataoff);items=[(0,1,0),(1,len(strings),so),(2,len(tt),to),(3,len(pp),po),(4,len(fields),fo),(5,len(mm),mo),(6,1,co)]
 items.append((0x2002,len(strings),len(out)));str_offsets=[]
 for s in strings:str_offsets.append(len(out));out+=uleb(len(s))+s.encode()+b'\0'
 param_offsets={};align(out);start=len(out)
 for p in pp:
  args=p[1]
  if args and args not in param_offsets:
   align(out);param_offsets[args]=len(out);out+=U(len(args))+b''.join(H(ti[x]) for x in args);align(out)
 if param_offsets:items.append((0x1001,len(param_offsets),start))
 class ASM:
  def __init__(self):self.words=[];self.labels={};self.fix=[]
  def emit(self,*w):self.words.extend(w)
  def invoke(self,op,key,regs):
   rr=list(regs)+[0]*5;self.emit(op|(len(regs)<<12)|(rr[4]<<8),mi[refs[key]],rr[0]|rr[1]<<4|rr[2]<<8|rr[3]<<12)
  def c4(self,r,v):self.emit(0x12|(r<<8)|((v&15)<<12))
  def c32(self,r,v):self.emit(0x14|(r<<8),v&65535,(v>>16)&65535)
  def new(self,r,t):self.emit(0x22|(r<<8),ti[t])
  def result(self,r,obj=True):self.emit((0x0c if obj else 0x0a)|(r<<8))
  def get(self,a,b):self.emit(0x54|(a<<8)|(b<<12),fi[(C,'web',WV)])
  def put(self,a,b):self.emit(0x5b|(a<<8)|(b<<12),fi[(C,'web',WV)])
  def zero(self,r,label):self.fix.append((len(self.words),label));self.emit(0x38|(r<<8),0)
  def label(self,s):self.labels[s]=len(self.words)
  def bytes(self):
   for off,label in self.fix:self.words[off+1]=(self.labels[label]-off)&65535
   return b''.join(H(w) for w in self.words)
 ctor=ASM();ctor.invoke(0x70,'a_ctor',[0]);ctor.emit(0x0e)
 a=ASM();a.invoke(0x6f,'a_create',[6,7]);a.c4(2,1);a.invoke(0x6e,'request',[6,2]);a.invoke(0x6e,'window',[6]);a.result(3);a.c32(5,0xfff6f5f1);a.invoke(0x6e,'status',[3,5]);a.c32(5,0xfffffefa);a.invoke(0x6e,'nav',[3,5]);a.invoke(0x6e,'decor',[3]);a.result(4);a.c32(5,0x2010);a.invoke(0x6e,'systemui',[4,5]);a.new(0,WV);a.invoke(0x70,'wv_ctor',[0,6]);a.put(0,6);a.invoke(0x6e,'settings',[0]);a.result(1);a.c4(2,1)
 for key in ['setJavaScriptEnabled','setDomStorageEnabled']:a.invoke(0x6e,key,[1,2])
 a.c4(2,0)
 for key in ['setAllowFileAccess','setAllowContentAccess','setAllowFileAccessFromFileURLs','setAllowUniversalAccessFromFileURLs']:a.invoke(0x6e,key,[1,2])
 a.c4(2,1);a.invoke(0x6e,'mixed',[1,2]);a.invoke(0x6e,'setMediaPlaybackRequiresUserGesture',[1,2]);a.new(3,WC);a.invoke(0x70,'wc_ctor',[3]);a.invoke(0x6e,'wc',[0,3]);a.new(3,CH);a.invoke(0x70,'ch_ctor',[3]);a.invoke(0x6e,'ch',[0,3]);a.c32(5,0xfff6f5f1);a.invoke(0x6e,'bg',[0,5]);a.invoke(0x6e,'content',[6,0]);a.emit(0x1a|(2<<8),si['file:///android_asset/www/index.html']);a.invoke(0x6e,'load',[0,2]);a.emit(0x0e)
 back=ASM();back.get(0,1);back.invoke(0x6e,'canback',[0]);back.result(0,False);back.zero(0,'super');back.get(0,1);back.invoke(0x6e,'goback',[0]);back.emit(0x0e);back.label('super');back.invoke(0x6f,'a_back',[1]);back.emit(0x0e)
 destroy=ASM();destroy.get(0,1);destroy.invoke(0x6e,'wv_destroy',[0]);destroy.invoke(0x6f,'a_destroy',[1]);destroy.emit(0x0e)
 code={};align(out);start=len(out)
 for key,asm,regs,ins,outs in [('ctor',ctor,1,1,1),('onCreate',a,8,2,2),('back',back,2,1,1),('destroy',destroy,2,1,1)]:
  align(out);code[key]=len(out);b=asm.bytes();out+=st.pack('<HHHHII',regs,ins,outs,0,0,len(b)//2)+b
 items.append((0x2001,4,start));classdata=len(out);out+=uleb(0)+uleb(1)+uleb(1)+uleb(3)+uleb(fi[(C,'web',WV)])+uleb(2)
 out+=uleb(mi[refs['ctor']])+uleb(0x10001)+uleb(code['ctor'])
 last=0
 for key,acc in sorted([('onCreate',4),('back',1),('destroy',4)],key=lambda kv:mi[refs[kv[0]]]):
  idx=mi[refs[key]];out+=uleb(idx-last)+uleb(acc)+uleb(code[key]);last=idx
 items.append((0x2000,1,classdata));align(out);mapoff=len(out);items.append((0x1000,1,mapoff));items.sort(key=lambda t:t[2]);out+=U(len(items))+b''.join(H(t)+H(0)+U(n)+U(off) for t,n,off in items)
 for j,off in enumerate(str_offsets):out[so+j*4:so+j*4+4]=U(off)
 for j,t in enumerate(tt):out[to+j*4:to+j*4+4]=U(si[t])
 for j,p in enumerate(pp):out[po+j*12:po+j*12+12]=U(si[shorty(p)])+U(ti[p[0]])+U(param_offsets.get(p[1],0))
 for j,f in enumerate(fields):out[fo+j*8:fo+j*8+8]=H(ti[f[0]])+H(ti[f[2]])+U(si[f[1]])
 for j,m in enumerate(mm):out[mo+j*8:mo+j*8+8]=H(ti[m[0]])+H(pi[(m[2],m[3])])+U(si[m[1]])
 out[co:co+32]=st.pack('<8I',ti[C],0x11,ti[A],0,si['MainActivity.java'],0,classdata,0)
 out[:8]=b'dex\n035\0'
 out[32:112]=st.pack('<20I',len(out),112,0x12345678,0,0,mapoff,len(strings),so,len(tt),to,len(pp),po,len(fields),fo,len(mm),mo,1,co,len(out)-dataoff,dataoff)
 out[12:32]=hashlib.sha1(out[32:]).digest();out[8:12]=U(zlib.adler32(out[12:]));return bytes(out)

def lp(b):return U(len(b))+b

def sign_v2(raw):
 eocd=raw.rfind(b'PK\x05\x06');assert eocd>=0
 cd=st.unpack_from('<I',raw,eocd+16)[0]
 digests=[]
 for section in [raw[:cd],raw[cd:eocd],raw[eocd:]]:
  for x in range(0,len(section),1048576):
   part=section[x:x+1048576];digests.append(hashlib.sha256(b'\xa5'+U(len(part))+part).digest())
 digest=hashlib.sha256(b'\x5a'+U(len(digests))+b''.join(digests)).digest()
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Folio Portfolio Build'),x509.NameAttribute(NameOID.ORGANIZATION_NAME,'Folio Local Development')])
 now=datetime.datetime.now(datetime.timezone.utc)
 cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=3650)).sign(key,hashes.SHA256())
 certder=cert.public_bytes(serialization.Encoding.DER)
 signed=lp(lp(U(0x0103)+lp(digest)))+lp(lp(certder))+lp(b'')
 signature=key.sign(signed,padding.PKCS1v15(),hashes.SHA256())
 key.public_key().verify(signature,signed,padding.PKCS1v15(),hashes.SHA256())
 public=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
 signer=lp(signed)+lp(lp(U(0x0103)+lp(signature)))+lp(public)
 value=lp(lp(signer));pair=Q(4+len(value))+U(0x7109871a)+value
 size=len(pair)+24;block=Q(size)+pair+Q(size)+b'APK Sig Block 42'
 tail=bytearray(raw[eocd:]);tail[16:20]=U(cd+len(block))
 return raw[:cd]+block+raw[cd:eocd]+tail,cert.fingerprint(hashes.SHA256()).hex()

def build(root:Path,destination:Path):
 dexdata=dex();mf=manifest();res=resources()
 entries={'AndroidManifest.xml':mf,'classes.dex':dexdata,'resources.arsc':res,'res/drawable/ic_launcher.png':(root/'web/assets/icon-192.png').read_bytes()}
 for file in sorted((root/'web').rglob('*')):
  if file.is_file():entries['assets/www/'+file.relative_to(root/'web').as_posix()]=file.read_bytes()
 buff=io.BytesIO()
 with zipfile.ZipFile(buff,'w') as z:
  for name,data in entries.items():
   info=zipfile.ZipInfo(name,date_time=(2026,10,1,0,0,0));info.compress_type=zipfile.ZIP_STORED if name=='resources.arsc' else zipfile.ZIP_DEFLATED
   if name=='resources.arsc':
    rawoff=z.fp.tell()+30+len(name.encode());padding=(-rawoff)%4
    if padding:info.extra=H(0xd935)+H(padding)+bytes(padding)
   z.writestr(info,data)
 signed,fingerprint=sign_v2(buff.getvalue());destination.write_bytes(signed)
 (root/'docs/apk-build-info.json').write_text(json.dumps({'package':'com.lunex.folio','version':'1.0.0','minSdk':26,'targetSdk':34,'signature':'APK Signature Scheme v2, RSA-2048 / SHA-256','certificateSha256':fingerprint,'apkSha256':hashlib.sha256(signed).hexdigest(),'bytes':len(signed),'packager':'tools/package_apk.py; matching Java host supplied','runtimeTestedOnAndroid':False},indent=2))
 print(f'Built {destination}: {len(signed):,} bytes; certificate SHA256 {fingerprint}')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path('Folio.apk'));args=ap.parse_args();build(Path(__file__).resolve().parent.parent,args.output)
