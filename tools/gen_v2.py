# 퇴근여우 v2 — 96x96 layered pixel sprites (original character).
# App layers: body, head, hair_back, hair_front, eyes, mouth, brows  (frame size = image height = 96)
#  eyes : 0 open,1 half,2 closed,3 happy,4 tired,5 surprised,6 smug
#  mouth: 0 ':3' closed,1 slight,2 wide,3 smile,4 'O',5 shocked,6 smug-fang
#  brows: 0 neutral,1 raised,2 worried,3 smug(one raised)
# Extra (video): body_core, hair_back_core, ears(0 up,1 droop), tail(4 sway), sparkle(3), legs(96x56 drawn below)
from PIL import Image
import math, random
S=96; random.seed(3)
OUT=(42,28,24,255)
def C(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))+(255,)
pal=dict(FUR='#e39b52',FUR_SH='#b86f34',FUR_DK='#8a4f26',FUR_HI='#f7c27e',CREAM='#fff4df',CREAM_SH='#ead3b2',INNER='#f3b3a2',INNER_SH='#d98c80',
 SKIN='#ffe4cf',SKIN_SH='#f2c3a6',SKIN_DK='#dfa287',BLUSH='#ff9a8e',
 HAIR='#d58c45',HAIR_SH='#a7622c',HAIR_DK='#7c4420',HAIR_HI='#f2bb72',
 CARD='#93c4a1',CARD_SH='#6e9f80',CARD_DK='#527c63',CARD_HI='#b5dcbf',BTN='#f4e6c8',
 SHIRT='#ffffff',SHIRT_SH='#d6dae6',TIE='#4a3f63',TIE_SH='#30283f',TIE_ST='#8b7fb0',
 LAN='#4f80d6',LAN_SH='#36599a',CARDID='#f6f8ff',CARDID_SH='#cfd5e6',TXT='#9aa3b8',
 PANTS='#4c4956',PANTS_SH='#37343f',PANTS_HI='#625e6e',SLIP='#e39b52',
 EYE='#c76a1f',EYE_D='#6e3410',EYE_L='#f0a24a',EYE_HI='#ffffff',SCL='#ffffff',
 MOUTH='#9e3240',MOUTH_D='#6e1f2c',TONGUE='#ff8a8a',FANG='#ffffff',BAG='#b99aae',SPARK='#fff27a',SPARK2='#ffffff')
pal={k:C(v) for k,v in pal.items()}; globals().update(pal)
def new(w=S,h=S): return Image.new('RGBA',(w,h),(0,0,0,0))
def P(im,x,y,c):
    if 0<=x<im.width and 0<=y<im.height: im.putpixel((int(x),int(y)),c)
def ell(cx,cy,rx,ry): return {(x,y) for y in range(int(cy-ry-1),int(cy+ry+2)) for x in range(int(cx-rx-1),int(cx+rx+2)) if ((x+.5-cx)/rx)**2+((y+.5-cy)/ry)**2<=1}
def poly(pts):
    xs=[p[0] for p in pts];ys=[p[1] for p in pts];o=set()
    for y in range(int(min(ys))-1,int(max(ys))+2):
        for x in range(int(min(xs))-1,int(max(xs))+2):
            px,py=x+.5,y+.5;ins=False;j=len(pts)-1
            for i in range(len(pts)):
                xi,yi=pts[i];xj,yj=pts[j]
                if (yi>py)!=(yj>py) and px<(xj-xi)*(py-yi)/(yj-yi)+xi: ins=not ins
                j=i
            if ins:o.add((x,y))
    return o
def edge(pts): return {(x,y) for x,y in pts if any((x+dx,y+dy) not in pts for dx,dy in((1,0),(-1,0),(0,1),(0,-1)))}
def fill(im,pts,base,sh=None,hi=None,dk=None,lx=-1,ly=-1,w_sh=2):
    """directional shading: light from top-left (lx,ly). highlight rim on lit side, shadow band on far side"""
    for x,y in pts:
        c=base
        if sh and any((x-lx*k,y-ly*k) not in pts for k in range(1,w_sh+1)): c=sh
        if dk and (x-lx,y-ly) not in pts and (x-2*lx,y-2*ly) not in pts and ((x-lx,y) not in pts or (x,y-ly) not in pts) : c=dk
        if hi and (x+lx*1,y+ly*1) not in pts and (x+lx*2,y+ly*2) in pts and c==base: c=hi
        P(im,x,y,c)
def outline(im,pts,c=OUT):
    for x,y in edge(pts): P(im,x,y,c)
def out_ext(im,pts,c=OUT):  # outline outside the shape (keeps interior)
    for x,y in pts:
        for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
            if (x+dx,y+dy) not in pts and im.getpixel((x+dx,y+dy))[3]==0 if 0<=x+dx<im.width and 0<=y+dy<im.height else False: P(im,x+dx,y+dy,c)
# ---------- HEAD ----------
HX,HY=48,45
head=new(); face=ell(HX,HY,21,18.5)|ell(HX,HY+5,18,15)
fill(head,face,SKIN,SKIN_SH,None,None,w_sh=1); outline(head,face)
for x,y in face:  # shadow under bangs
    if 28<=y<=31 and (x,y-1) in face: pass
for bx,by in ((31,53),(61,53)):  # hatched blush
    for i in range(5):
        P(head,bx+i,by,BLUSH) if i%2==0 else None; P(head,bx+i,by+1,BLUSH) if i%2==1 else None
# ---------- HAIR BACK core ----------
hbc=new(); hp=ell(HX,HY-6,24,21)|poly([(24,40),(30,40),(30,62),(26,64),(23,58)])|poly([(66,40),(72,40),(73,58),(70,64),(66,62)])
fill(hbc,hp,HAIR_SH,HAIR_DK,None,None,w_sh=2); outline(hbc,hp)
# ---------- EARS ----------
def ear(im,s,droop):
    if not droop: base_in,tip,base_out=(HX+s*6,24),(HX+s*28,3),(HX+s*26,36)
    else: base_in,tip,base_out=(HX+s*14,22),(HX+s*44,43),(HX+s*23,42)
    t=poly([base_in,tip,base_out]); fill(im,t,FUR,FUR_SH,FUR_HI,None,lx=-s,ly=-1,w_sh=2)
    cx=(base_in[0]+tip[0]+base_out[0])/3;cy=(base_in[1]+tip[1]+base_out[1])/3
    sh=lambda p,k:(p[0]+(cx-p[0])*k,p[1]+(cy-p[1])*k)
    inn=poly([sh(base_in,.42),sh(tip,.36),sh(base_out,.42)])&t
    fill(im,inn,INNER,INNER_SH,None,None,lx=s,ly=-1,w_sh=1)
    # cream fur tufts at inner base
    bx0,by0=sh(base_in,.42);bx1,by1=sh(base_out,.42)
    for i in range(9):
        u=i/8;x=bx0+(bx1-bx0)*u;y=by0+(by1-by0)*u
        for k in range(1+(i%3)):
            P(im,x+(tip[0]-x)*0.06*k,y+(tip[1]-y)*0.06*k-0,CREAM)
    outline(im,t)
ears=[]
for d in (0,1):
    im=new(); ear(im,-1,d); ear(im,1,d); ears.append(im)
hair_back=Image.alpha_composite(ears[0],hbc)
# ---------- HAIR FRONT ----------
hf=new()
cap={(x,y) for x,y in ell(HX,HY-9,24.5,21) if y<=31}
LOCKS=[(28,26,35,5),(34,26,37,5),(40,26,34,4),(46,26,37,5),(52,26,35,5),(58,26,37,5),(64,26,35,5),(68,26,33,4)]  # (top_x, top_y, tip_y, half_w)
lk=set(); tips=[]
for tx,ty,tip,w in LOCKS:
    lean=(HX-tx)*0.08; lk|=poly([(tx-w,ty),(tx+w,ty),(tx+lean+1,tip),(tx+lean,tip)]); tips.append((tx+lean,tip))
sides=set()
for s_ in (-1,1):
    sides|=poly([(HX+s_*25,26),(HX+s_*16,28),(HX+s_*17,44),(HX+s_*20,56),(HX+s_*23,52),(HX+s_*26,40)])
hair=cap|lk|sides
fill(hf,hair,HAIR,HAIR_SH,HAIR_HI,None,w_sh=2)
for (tx,ty,tip,w),(px,py) in zip(LOCKS,tips):   # strand lines up from each tip
    for k in range(2,7): P(hf,round(tx+(px-tx)*(1-k/(tip-ty))),tip-k,HAIR_SH)
for s_ in (-1,1):
    for k in range(6): P(hf,HAIR_X:=HX+s_*(20+k*0.4),44+k,HAIR_SH)
streak=(poly([(38,14),(45,14),(44,26),(41,36),(37,26)]))&hair
fill(hf,streak,CREAM,CREAM_SH,None,None,w_sh=1)
for a_ in range(48):   # broken shine band
    t=a_/47; x=int(29+t*38); y=int(22-5*math.sin(t*math.pi))
    if a_%7<5 and (x,y) in hair and (x,y) not in streak:
        P(hf,x,y,HAIR_HI); P(hf,x,y+1,HAIR_HI)
outline(hf,hair)
ah=poly([(52,17),(54,17),(55,13),(58,10),(61,11),(60,13),(58,12),(56,14),(55,18)])
for x,y in ah: P(hf,x,y,HAIR)
outline(hf,ah)
for x,y in ah:
    if y>=17 and (x,y) in hair: P(hf,x,y,HAIR)
# ---------- EYES ----------
EL,ER,EY=38,58,47
def eye_open(im,cx,s):
    e=ell(cx,EY,4,5.5)
    for x,y in e:
        r=y-(EY-5); c=EYE_D if r<3 else EYE if r<7 else EYE_L
        P(im,x,y,c)
    for x,y in ell(cx,EY+.5,1.2,2): P(im,x,y,EYE_D)
    outline(im,e)
    for x in range(cx-5,cx+5): P(im,x,EY-6,OUT)            # thick upper lash
    P(im,cx+s*5,EY-6,OUT); P(im,cx+s*6,EY-7,OUT)           # outer lash flick
    for p in [(cx-2,EY-3),(cx-1,EY-3),(cx-2,EY-2),(cx-1,EY-2)]: P(im,*p,EYE_HI)
    P(im,cx+1,EY+3,EYE_HI)
def eye_half(im,cx,s):
    e={(x,y) for x,y in ell(cx,EY,4,5.5) if y>=EY-1}
    for x,y in e: P(im,x,y,EYE if y<EY+3 else EYE_L)
    for x,y in ell(cx,EY+1,1.2,1.5): P(im,x,y,EYE_D)
    outline(im,e)
    for x in range(cx-5,cx+5): P(im,x,EY-2,OUT)
    P(im,cx+s*5,EY-2,OUT); P(im,cx-2,EY,EYE_HI); P(im,cx-1,EY,EYE_HI)
def eye_closed(im,cx,s):
    for i,x in enumerate(range(cx-5,cx+5)):
        y=EY+2+(0 if 2<=i<=7 else -1); P(im,x,y,OUT); P(im,x,y+1,OUT) if 3<=i<=6 else None
    P(im,cx+s*5,EY,OUT)
def eye_happy(im,cx,s):
    for i in range(-5,5):
        y=EY+1-int(3.2*math.cos(i/5.5*math.pi/2)**1)
        P(im,cx+i,y,OUT); P(im,cx+i,y+1,OUT)
def eye_tired(im,cx,s):
    e={(x,y) for x,y in ell(cx,EY,4,5.5) if y>=EY+1}
    for x,y in e: P(im,x,y,EYE)
    for x,y in ell(cx,EY+2.5,1.2,1): P(im,x,y,EYE_D)
    outline(im,e)
    for x in range(cx-5,cx+5): P(im,x,EY+1,OUT); P(im,x,EY,OUT) if abs(x-cx)<3 else None
    P(im,cx-2,EY+2,EYE_HI)
    for x in range(cx-4,cx+4): P(im,x,EY+7,BAG) if x%2==0 else None
    for x in range(cx-3,cx+3): P(im,x,EY+8,BAG)
def eye_surprised(im,cx,s):
    e=ell(cx,EY,4.5,6)
    for x,y in e: P(im,x,y,SCL)
    outline(im,e)
    for x,y in ell(cx,EY,1.5,2): P(im,x,y,EYE_D)
    P(im,cx-1,EY-1,EYE_HI)
    for x in range(cx-4,cx+4): P(im,x,EY-7,OUT)
def eye_smug(im,cx,s):
    e={(x,y) for x,y in ell(cx,EY,4,5.5) if EY-1<=y<=EY+2}
    for x,y in e: P(im,x,y,EYE)
    for x,y in e:
        if abs(x-(cx+s))<=1: P(im,x,y,EYE_D)
    outline(im,e)
    for x in range(cx-5,cx+5): P(im,x,EY-2,OUT)
    for i,x in enumerate(range(cx-4,cx+4)): P(im,x,EY+3-(1 if i in(0,7) else 0),OUT)
    P(im,cx-2,EY,EYE_HI)
EF=[eye_open,eye_half,eye_closed,eye_happy,eye_tired,eye_surprised,eye_smug]
eyes=[]
for f in EF:
    im=new(); f(im,EL,-1); f(im,ER,1); eyes.append(im)
# ---------- MOUTHS ---------- center (48,57)
MX,MY=48,57
def m_cat(im):
    for x,y in [(43,57),(44,58),(45,58),(46,58),(47,57),(48,56),(49,57),(50,58),(51,58),(52,58),(53,57)]: P(im,x,y,OUT)
def m_slight(im):
    m=ell(MX,MY+1,3,1.6); [P(im,x,y,MOUTH) for x,y in m]; [P(im,x,y,MOUTH_D) for x,y in m if y<MY+1]; outline(im,m)
def m_wide(im):
    m={(x,y) for x,y in ell(MX,MY+1,5,5) if y>=MY-1}
    for x,y in m: P(im,x,y,MOUTH_D if y<MY+2 else MOUTH if y<MY+4 else TONGUE)
    outline(im,m); P(im,MX-3,MY,FANG); P(im,MX-3,MY+1,FANG)
def m_smile(im):
    m={(x,y) for x,y in ell(MX,MY-1,5,4) if y>=MY-1}
    for x,y in m: P(im,x,y,MOUTH_D if y<MY+1 else TONGUE)
    outline(im,m); P(im,MX-3,MY,FANG)
def m_o(im):
    m=ell(MX,MY+1,2,2.6); [P(im,x,y,MOUTH_D) for x,y in m]; outline(im,m)
def m_shock(im):
    m=poly([(MX-5,MY-1),(MX+5,MY-1),(MX+4,MY+6),(MX-4,MY+6)])
    for x,y in m: P(im,x,y,MOUTH_D if y<MY+4 else TONGUE)
    outline(im,m); [P(im,x,MY,FANG) for x in (MX-3,MX+2)]
def m_smug(im):
    for x,y in [(43,58),(44,58),(45,58),(46,58),(47,57),(48,57),(49,57),(50,56),(51,55),(52,55)]: P(im,x,y,OUT)
    P(im,50,57,FANG); P(im,50,58,FANG); P(im,49,58,OUT); P(im,51,57,OUT); P(im,50,59,OUT)
mouths=[]
for f in (m_cat,m_slight,m_wide,m_smile,m_o,m_shock,m_smug):
    im=new(); f(im); mouths.append(im)
# ---------- BROWS ----------
def brow(im,cx,s,lift_in,lift_out,dy=0):
    for i in range(7):
        u=i/6; x=cx-3+i if s>0 else cx+3-i
        y=EY-10+dy-round(lift_in*(1-u)+lift_out*u)
        P(im,x,y,HAIR_DK); P(im,x,y+1,HAIR_DK) if 1<=i<=4 else None
brows=[]
for spec in [((0,0),(0,0)),((2,2),(2,2)),((3,0),(3,0)),((0,0),(-1,3))]:
    im=new(); brow(im,EL,1,*spec[0]) if False else None
    (a,b),(c,d)=spec
    brow(im,EL,1,a,b); brow(im,ER,-1,c,d); brows.append(im)
# ---------- TAIL (4 frames) ----------
def tail(sway):
    im=new(); pts=[];
    for i in range(26):
        t=i/25; bx=62+19*t+sway*t*t*5; by=90-40*t-8*t*t+abs(sway)*t*2
        r=4+8.5*math.sin(min(1,t*1.1)*math.pi*0.8)
        pts.append((bx,by,r,t))
    allp=set();cream=set()
    for bx,by,r,t in pts:
        e=ell(bx,by,r,r*1.05); allp|=e
        if t>0.84: cream|=e
    fill(im,allp,FUR,FUR_SH,FUR_HI,FUR_DK,lx=-1,ly=-1,w_sh=3)
    cr=cream&allp; fill(im,cr,CREAM,CREAM_SH,None,None,w_sh=2)
    for k in range(14):  # fur flick strokes
        bx,by,r,t=pts[4+k];P(im,bx-r*0.3,by+r*0.3,FUR_SH)
    outline(im,allp)
    E=edge(allp)
    for i,(x,y) in enumerate(sorted(E)):   # fluffy notches: carve tiny V's along outline
        if (x*7+y*13)%11==0:
            P(im,x,y,(0,0,0,0))
            for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
                q=(x+dx,y+dy)
                if q in allp and q not in E: P(im,*q,OUT)
    return im
tails=[tail(s) for s in (-1,0,1,0)]
# ---------- BODY core ----------
bc=new()
neck=poly([(43,60),(53,60),(53,70),(43,70)]); fill(bc,neck,SKIN_SH,SKIN_DK,None,None,w_sh=1)
torso=poly([(33,68),(63,68),(70,78),(72,96),(24,96),(26,78)])
fill(bc,torso,CARD,CARD_SH,CARD_HI,None,lx=-1,ly=-1,w_sh=3)
for x,y in torso:  # knit rib texture
    if x%3==0 and y%2==0 and bc.getpixel((x,y))==CARD: P(bc,x,y,CARD_SH)
# sleeves hanging down at sides (cover hands)
SLEEVES=[]
for s in (-1,1):
    sl=poly([(48+s*14,68),(48+s*22,74),(48+s*30,88),(48+s*30,93),(48+s*20,93),(48+s*18,80)])
    SLEEVES.append(sl)
# shirt V + collar
shirt=poly([(40,68),(56,68),(53,96),(43,96)])
fill(bc,shirt,SHIRT,SHIRT_SH,None,None,lx=-1,ly=-1,w_sh=1)
for s in (-1,1):
    col=poly([(48,69),(48+s*9,66),(48+s*7,74)]); fill(bc,col,SHIRT,SHIRT_SH,None,None,w_sh=1); outline(bc,col)
# cardigan front edges with buttons
for s in (-1,1):
    for y in range(70,96):
        x=48+s*(5+(y-68)//5); P(bc,x,y,CARD_DK); P(bc,x+s,y,CARD_HI)
    for by in (78,86,94):
        x=48+s*(6+(by-68)//5)+s; P(bc,x,by,BTN); P(bc,x+1,by,BTN); P(bc,x,by+1,CREAM_SH); P(bc,x+1,by+1,CREAM_SH)
# crooked tie (knot left of center, blade drifting right)
knot=poly([(45,69),(50,69),(49,73),(46,73)]); fill(bc,knot,TIE,TIE_SH,None,None,w_sh=1); outline(bc,knot)
blade=poly([(46,73),(49,73),(53,89),(51,93),(49,90)]); fill(bc,blade,TIE,TIE_SH,None,None,lx=-1,ly=0,w_sh=1)
for x,y in blade:
    if (x+y)%5==0: P(bc,x,y,TIE_ST)
outline(bc,blade)
# lanyard + ID badge (left chest)
for i in range(16):
    P(bc,42-i//4,70+i,LAN); P(bc,54+i//5,70+i,LAN_SH) if i<9 else None
badge=poly([(32,84),(43,84),(43,96),(32,96)])
fill(bc,badge,CARDID,CARDID_SH,None,None,w_sh=1); outline(bc,badge)
for x in range(33,43): P(bc,x,85,LAN); P(bc,x,86,LAN)
P(bc,37,83,OUT);P(bc,38,83,OUT);P(bc,37,84,(150,150,160,255));P(bc,38,84,(150,150,160,255))  # clip
ph=poly([(33,88),(37,88),(37,93),(33,93)]); [P(bc,x,y,FUR) for x,y in ph]; P(bc,34,90,OUT);P(bc,36,90,OUT);P(bc,33,88,FUR_SH);P(bc,36,88,FUR_SH)
for x in range(38,42): P(bc,x,89,TXT)
for x in range(38,41): P(bc,x,91,TXT)
for x in range(38,42): P(bc,x,93,(220,90,90,255)) if x%2==0 else None
outline(bc,torso|neck)
for s_,sl in zip((-1,1),SLEEVES):
    fill(bc,sl,CARD,CARD_SH,CARD_HI,None,lx=-1,ly=-1,w_sh=2)
    for x,y in sl:
        if x%3==0 and y%2==0 and bc.getpixel((x,y))==CARD: P(bc,x,y,CARD_SH)
        if y>=89: P(bc,x,y,CARD_DK if x%2 else CARD_SH)
    outline(bc,sl)
    for i in range(3):
        fx=48+s_*(23+i*2); P(bc,fx,94,SKIN); P(bc,fx,95,SKIN_SH); P(bc,fx+1,94,OUT) 

for x,y in neck: 
    if (x,y) in edge(neck) and y<70: P(bc,x,y,OUT)
body=Image.alpha_composite(tails[1],bc)
# ---------- LEGS (96x56) ----------
legs=new(S,56)
hem=poly([(24,0),(72,0),(72,4),(24,4)]); fill(legs,hem,CARD_SH,CARD_DK,None,None,w_sh=1)
for x,y in hem:
    if x%2==0: P(legs,x,y,CARD_DK)
outline(legs,hem)
for s in (-1,1):
    pl=poly([(48+s*1,4),(48+s*15,4),(48+s*16,44),(48+s*2,44)])
    fill(legs,pl,PANTS,PANTS_SH,PANTS_HI,None,lx=-1,ly=-1,w_sh=2)
    for y in range(10,42): P(legs,48+s*8,y,PANTS_SH)
    outline(legs,pl)
    sl=ell(48+s*9,48,9,5.5)
    fill(legs,sl,SLIP,FUR_SH,FUR_HI,None,w_sh=2)
    fr=ell(48+s*9,50,7,3.5)&sl
    for x,y in fr: P(legs,x,y,CREAM) if y>=50 else None
    outline(legs,sl)
    for ex in (-5,3):  # tiny fox ears on slippers
        t=poly([(48+s*9+ex,45),(48+s*9+ex+3,45),(48+s*9+ex+1.5,40)]); [P(legs,x,y,FUR) for x,y in t]; outline(legs,t)
    P(legs,48+s*9-1,49,OUT);P(legs,48+s*9+1,49,OUT)
# ---------- SPARKLES (3 frames) ----------
def star(im,x,y,r):
    for i in range(-r,r+1): P(im,x+i,y,SPARK); P(im,x,y+i,SPARK)
    if r>=2:
        for d in (-1,1): P(im,x+d,y+d,SPARK); P(im,x+d,y-d,SPARK)
    P(im,x,y,SPARK2)
spark=[]
spots=[(10,14),(84,10),(88,40),(8,44),(20,4),(76,28)]
for f in range(3):
    im=new()
    for i,(x,y) in enumerate(spots):
        r=[4,2,3][(i+f)%3]; star(im,x,y,r)
    spark.append(im)
# ---------- save ----------
def sheet(fr,n):
    w,h=fr[0].size; o=Image.new('RGBA',(w*len(fr),h),(0,0,0,0))
    for i,f in enumerate(fr): o.paste(f,(i*w,0))
    o.save(f'assets/{n}.png')
for n,fr in [('body',[body]),('head',[head]),('hair_back',[hair_back]),('hair_front',[hf]),('eyes',eyes),('mouth',mouths),('brows',brows),
             ('body_core',[bc]),('hair_back_core',[hbc]),('ears',ears),('tail',tails),('sparkle',spark),('legs',[legs])]: sheet(fr,n)
# ---------- preview ----------
H=S+56
def comp(e,m,b,ea=0,t=1,sp=None,full=True):
    c=Image.new('RGBA',(S,H),(0,0,0,0)); c.alpha_composite(legs,(0,S))
    lay=[tails[t]]+([ears[0],hbc] if ea==0 else [hbc,ears[1]])+[bc,head,eyes[e],mouths[m],hf,brows[b]]
    for l in lay: c.alpha_composite(l,(0,0))
    if sp is not None: c.alpha_composite(spark[sp],(0,0))
    return c if full else c.crop((0,0,S,S))
if __name__=='__main__':
    from PIL import ImageDraw,ImageFont
    F=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',20)
    BG=(236,232,222,255)
    v1=Image.open('/workspace/fox-tts/orig_sprites.png').crop((4,4,4+256,4+416))
    full=Image.alpha_composite(Image.new('RGBA',(S,H),BG),comp(0,0,0)).resize((S*3,H*3),Image.NEAREST)
    ex=[('기본',0,0,0,0,None),('말하기',0,2,1,0,None),('반눈',1,0,0,0,None),('감음',2,0,0,0,None),('웃음+반짝',3,3,1,0,0),
        ('피곤(귀처짐)',4,0,2,1,None),('놀람',5,5,1,0,None),('의기양양 :3',6,6,3,0,None),('O입',0,4,0,0,None),('흥분',3,2,1,0,1)]
    sc=3;cw=S*sc
    W=20+256+20+S*3+30+5*(cw+8); Hh=max(H*3,2*(cw+30))+60
    pv=Image.new('RGBA',(W,Hh),(36,30,40,255)); d=ImageDraw.Draw(pv)
    d.text((20,10),'v1 (64px)',font=F,fill='white'); pv.paste(v1,(20,40))
    x2=20+256+20; d.text((x2,10),'v2 (96px)',font=F,fill='white'); pv.paste(full,(x2,40))
    x3=x2+S*3+30
    for i,(lab,e,m,b,ea,sp) in enumerate(ex):
        c=Image.alpha_composite(Image.new('RGBA',(S,S),BG),comp(e,m,b,ea,i%4,sp,False)).resize((cw,cw),Image.NEAREST)
        X=x3+(i%5)*(cw+8);Y=40+(i//5)*(cw+30); pv.paste(c,(X,Y)); d.text((X+4,Y+cw+2),lab,font=F,fill=(255,200,140))
    pv.save('/workspace/fox-tts/orig_v2_sprites.png'); pv.save('/tmp/v2d.png')
    # tail frames strip
    st=Image.new('RGBA',(S*4*2,S*2),BG)
    for i,t in enumerate(tails): st.alpha_composite(t.resize((S*2,S*2),Image.NEAREST),(i*S*2,0))
    st.save('/tmp/v2tail.png')
