"""Walk every ipak entry the way t6zm's image streamer does (fixed 0x40000 windows from the
entry's first chunk) and report entries whose blocks overrun a window or whose offsets break."""
import sys,struct
f=open(sys.argv[1],'rb').read()
nsec=struct.unpack_from('<I',f,12)[0]
secs={struct.unpack_from('<I',f,16+16*i)[0]:struct.unpack_from('<3I',f,20+16*i) for i in range(nsec)}
io,_,ic=secs[1]; do=secs[2][0]
bad=0
for i in range(ic):
    dh,nh,off,a5=struct.unpack_from('<IIII',f,io+16*i); a1=do+off
    v6=a1&~0x7fff; v7=((a1+a5+0x7fff)&~0x7fff)-v6; v9=a1-v6; v32=v9+a5; err=None; expect=0
    for w in range((v7+0x3ffff)>>18):
        if w: v32-=0x40000; v6+=0x40000; v28=min(0x40000,v32); v9=0
        else: v28=min(0x40000-v9,a5)
        v16=0
        while True:
            hdr=v6+v9+v16; co,=struct.unpack_from('<I',f,hdr); cmds=struct.unpack_from('<31I',f,hdr+4)
            cnt=co>>24; v21=v16+128+sum(c&0xffffff for c in cmds[:cnt])
            if v9+v21>0x40000: err='block @%x overruns window by %d'%(hdr,v9+v21-0x40000); break
            if cnt and any((c>>24) in (0,1) for c in cmds[:cnt]) and (co&0xffffff)<expect: err='block @%x offset %x < %x'%(hdr,co&0xffffff,expect); break
            n=(v21+127)&~127
            if n>=v28: break
            v16=n
        if err: break
    if err: bad+=1; print(hex(nh),err)
print(ic,'entries,',bad,'bad')
