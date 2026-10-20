# 퇴근여우 v2 — head-angle sprite sets (yaw 5 x pitch 3), redrawn per angle via simple head-sphere projection.
# Output: /workspace/orig/v2/angles/  sheets: rows = angle index (pitch p∈{-1 up,0,1 down} major, yaw k∈{-2..2} minor), cols = frames.
#   yaw k>0 = character faces SCREEN-RIGHT.
import math, json, os
from gen_v2 import *   # palette, helpers, front-view functions (eye_*, m_*, brow), body_core, tails, legs, spark
OUTD='/workspace/orig/v2/angles'; os.makedirs(OUTD,exist_ok=True)
YAW=[-2,-1,0,1,2]; PIT=[-1,0,1]; TH={-2:-50,-1:-25,0:0,1:25,2:50}
def X(u,z,th): return HX+u*math.cos(th)+z*math.sin(th)
def sz(u,R): return math.sqrt(max(0,R*R-u*u))
def head_layer(th,p):
    im=new(); s=math.sin(th); fy=3*p
    cx=HX+7*s; rx=21-3*abs(s)
    face=ell(cx,HY+fy*0.5,rx,18.5)|ell(cx+1.5*s,HY+5+fy*0.5,18-abs(s)*1.5,15)
    fill(im,face,SKIN,SKIN_SH,None,None,lx=-1 if s<=0.01 else -1,w_sh=1); outline(im,face)
    for u in (-15,15):   # blush
        w=math.cos(th+math.asin(u/20)); 
        if w<0.3: continue
        bx=X(u,13,th); n=max(2,round(5*w))
        for i in range(n):
            P(im,round(bx-n/2+i),53+fy+(i%2),BLUSH)
    if abs(s)>0.2:  # nose hint
        nx=round(X(0,21,th)); P(im,nx,51+fy,SKIN_DK); P(im,nx+(1 if s>0 else -1),52+fy,SKIN_DK) if abs(s)>0.6 else None
    return im
def hair_back_layer(th,p):
    im=new(); s=math.sin(th)
    def pl(pts,z): return poly([(X(x-HX,z,th) if True else x,y) for x,y in pts])
    hp=ell(HX-3*s,HY-6,24,21)
    for side in (-1,1):
        base=[(HX+side*24,40),(HX+side*18,40),(HX+side*18,62),(HX+side*22,64),(HX+side*25,58)]
        hp|=poly([(X(x-HX,-6,th),y) for x,y in base])
    fill(im,hp,HAIR_SH,HAIR_DK,None,None,w_sh=2); outline(im,hp); return im
def ears_layer(th,p,droop):
    im=new(); s=math.sin(th)
    def ear1(side):
        if not droop: pts=[(HX+side*6,24),(HX+side*28,3),(HX+side*26,36)]
        else: pts=[(HX+side*14,22),(HX+side*44,43),(HX+side*23,42)]
        pts=[(X(x-HX,-2,th),y-p) for x,y in pts]
        base_in,tip,base_out=pts
        t=poly(pts); fill(im,t,FUR,FUR_SH,FUR_HI,None,lx=-side,ly=-1,w_sh=2)
        cx_=(base_in[0]+tip[0]+base_out[0])/3;cy_=(base_in[1]+tip[1]+base_out[1])/3
        sh=lambda q,k:(q[0]+(cx_-q[0])*k,q[1]+(cy_-q[1])*k)
        # far-facing ear shows less inner (we see its back) when turned
        facing=-side*s   # >0 : ear's inner side faces viewer more
        k_in=.42+max(0,-facing)*0.35
        inn=poly([sh(base_in,k_in),sh(tip,k_in-.06),sh(base_out,k_in)])&t
        fill(im,inn,INNER,INNER_SH,None,None,lx=side,ly=-1,w_sh=1)
        bx0,by0=sh(base_in,k_in);bx1,by1=sh(base_out,k_in)
        for i in range(9):
            u=i/8;x=bx0+(bx1-bx0)*u;y=by0+(by1-by0)*u
            if (round(x),round(y)) in inn:
                for k in range(1+(i%3)): P(im,x+(tip[0]-x)*0.06*k,y+(tip[1]-y)*0.06*k,CREAM)
        outline(im,t)
    # draw far ear first
    order=(1,-1) if s>0 else (-1,1)
    for side in order: ear1(side)
    return im
def hair_front_layer(th,p):
    im=new(); s=math.sin(th); dy=2*p
    capc=HX+2*s
    capfull=ell(capc,HY-9,24.5,21)
    cap={(x,y) for x,y in capfull if y<=31}
    LOCKS=[(28,26,35,5),(34,26,37,5),(40,26,34,4),(46,26,37,5),(52,26,35,5),(58,26,37,5),(64,26,35,5),(68,26,33,4)]
    lk=set(); tips=[]
    clip=ell(capc,HY-6,25.5,24)
    for tx,ty,tip,w in LOCKS:
        u=tx-HX; z=sz(u,24.5); vis=math.cos(th+math.asin(max(-1,min(1,u/24.5))))
        if vis<0.15: continue
        x0=X(u,z,th); ww=max(2,w*(0.45+0.55*vis))
        lean=(HX-tx)*0.08
        pts=[(x0-ww,ty),(x0+ww,ty),(x0+lean+1,tip+dy),(x0+lean,tip+dy)]
        lk|=poly(pts)&clip; tips.append((tx,ty,tip+dy,x0,x0+lean))
    sides=set()
    for side in (-1,1):
        base=[(HX+side*25,26),(HX+side*16,28),(HX+side*17,44),(HX+side*20,56),(HX+side*23,52),(HX+side*26,40)]
        u0=side*21; vis=math.cos(th+math.asin(u0/24.5))
        if vis<0.3: continue
        back=(side*math.sin(th))<-0.3   # lock on the back side of a strongly turned head
        z=-8 if back else 2
        pts=[(X(x-HX,z,th),y) for x,y in base]
        if back:  # narrower lock hugging the back silhouette
            mx=sum(q[0] for q in pts)/len(pts); pts=[(mx+(q[0]-mx)*0.6,q[1]) for q in pts]
        sides|=poly(pts)
    hair=cap|lk|sides
    fill(im,hair,HAIR,HAIR_SH,HAIR_HI,None,w_sh=2)
    for tx,ty,tip,x0,xt in tips:
        for k in range(2,7): P(im,round(x0+(xt-x0)*(1-k/(tip-ty))),tip-k,HAIR_SH)
    sx=X(-6,23,th)
    streak=poly([(sx-4,14),(sx+3,14),(sx+2,26),(sx-1,36+dy),(sx-5,26)])&hair
    fill(im,streak,CREAM,CREAM_SH,None,None,w_sh=1)
    for a_ in range(48):
        t=a_/47; x=int(capc-19+t*38); y=int(22-5*math.sin(t*math.pi))
        if a_%7<5 and (x,y) in hair and (x,y) not in streak: P(im,x,y,HAIR_HI); P(im,x,y+1,HAIR_HI)
    outline(im,hair)
    ax=X(6,4,th)-52
    ah=poly([(52+ax,17),(54+ax,17),(55+ax,13),(58+ax,10),(61+ax,11),(60+ax,13),(58+ax,12),(56+ax,14),(55+ax,18)])
    for x,y in ah: P(im,x,y,HAIR)
    outline(im,ah)
    for x,y in ah:
        if y>=17 and (x,y) in hair: P(im,x,y,HAIR)
    return im
def paste_scaled(dst,src,box,cx_new,w,dy):
    """horizontal squeeze that keeps the outer outline columns (endpoint-inclusive column sampling of content bbox)"""
    part=src.crop(box); bb=part.getbbox()
    if not bb: return
    part=part.crop(bb); W_,H_=part.size; bx0=box[0]+bb[0]; by0=box[1]+bb[1]
    ocx=bx0+W_/2 - (box[0]+box[2])/2   # content center offset from anchor
    nw=W_ if w>=0.999 else max(3,round(W_*w))
    if nw!=W_:
        cols=[round(j*(W_-1)/(nw-1)) for j in range(nw)]
        q=Image.new('RGBA',(nw,H_))
        for j,c in enumerate(cols): q.paste(part.crop((c,0,c+1,H_)),(j,0))
        part=q
    dst.alpha_composite(part,(int(round(cx_new+ocx*w-nw/2)),by0+dy))
def eyes_layer(th,p,f):
    im=new(); fy=3*p
    for u,cx0,sd in ((-10,EL,-1),(10,ER,1)):
        w=math.cos(th+math.asin(u/20))
        if w<0.12: continue
        tmp=new(); f(tmp,cx0,sd)
        w=1 if w>0.9 else max(0.35,w)
        paste_scaled(im,tmp,(cx0-8,EY-10,cx0+8,EY+10),X(u,17.3,th),w,fy)
    return im
def mouth_layer(th,p,f):
    im=new(); tmp=new(); f(tmp); w=max(0.6,math.cos(th))
    paste_scaled(im,tmp,(MX-8,MY-5,MX+8,MY+9),X(0,19,th)+(0 if abs(th)<0.1 else 0),1 if w>0.95 else w,3*p); return im
BROWS=[((0,0),(0,0)),((2,2),(2,2)),((3,0),(3,0)),((0,0),(-1,3))]
def brows_layer(th,p,spec):
    im=new(); (a,b),(c,d)=spec
    for u,cx0,sd,(li,lo) in ((-10,EL,1,(a,b)),(10,ER,-1,(c,d))):
        w=math.cos(th+math.asin(u/20))
        if w<0.15: continue
        tmp=new(); brow(tmp,cx0,sd,li,lo)
        paste_scaled(im,tmp,(cx0-6,EY-16,cx0+6,EY-4),X(u,17.3,th),1 if w>0.9 else max(0.4,w),3*p)
    return im
EF=[eye_open,eye_half,eye_closed,eye_happy,eye_tired,eye_surprised,eye_smug]
MF=[m_cat,m_slight,m_wide,m_smile,m_o,m_shock,m_smug]
def build():
    angles=[(p,k) for p in PIT for k in YAW]; A=len(angles)
    layers={'head':[],'hair_back':[],'hair_front':[],'ears':[],'eyes':[],'mouth':[],'brows':[]}
    for p,k in angles:
        th=math.radians(TH[k])
        layers['head'].append([head_layer(th,p)])
        layers['hair_back'].append([hair_back_layer(th,p)])
        layers['hair_front'].append([hair_front_layer(th,p)])
        layers['ears'].append([ears_layer(th,p,0),ears_layer(th,p,1)])
        layers['eyes'].append([eyes_layer(th,p,f) for f in EF])
        layers['mouth'].append([mouth_layer(th,p,f) for f in MF])
        layers['brows'].append([brows_layer(th,p,sp) for sp in BROWS])
    for n,rows in layers.items():
        nf=len(rows[0]); sh=Image.new('RGBA',(S*nf,S*A),(0,0,0,0))
        for r,fr in enumerate(rows):
            for c,f in enumerate(fr): sh.paste(f,(c*S,r*S))
        sh.save(f'{OUTD}/{n}.png')
    body_core.save(f'{OUTD}/body.png') if False else bc.save(f'{OUTD}/body.png')
    o=Image.new('RGBA',(S*4,S));[o.paste(t,(i*S,0)) for i,t in enumerate(tails)];o.save(f'{OUTD}/tail.png')
    o=Image.new('RGBA',(S*3,S));[o.paste(t,(i*S,0)) for i,t in enumerate(spark)];o.save(f'{OUTD}/sparkle.png')
    legs.save(f'{OUTD}/legs.png')
    man=dict(name='퇴근여우',S=S,yaw=YAW,pitch=PIT,angleIndex='(pitch+1)*5+(yaw+2)',
      eyes=['open','half','closed','happy','tired','surprised','smug'],mouth=['cat','slight','wide','smile','o','shock','smug'],
      brows=['neutral','raised','worried','smug'],ears=['up','droop'],tail=4,sparkle=3,neckPivot=[48,66])
    json.dump(man,open(f'{OUTD}/manifest.json','w'),ensure_ascii=False,indent=1)
    return layers
if __name__=='__main__':
    L=build()
    # angle sheet preview
    from PIL import ImageDraw,ImageFont
    F=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',16)
    BG=(236,232,222,255); sc=2
    EXP=[('기본',0,0,0,0,None),('말하기',0,2,1,0,None),('웃음+반짝',3,3,1,0,0),('피곤',4,0,2,1,None),('놀람',5,5,1,0,None),('의기양양',6,6,3,0,None)]
    cols=len(YAW)*len(EXP); W=cols*(S*sc+4)+70; Hh=len(PIT)*(S*sc+4)+40
    pv=Image.new('RGBA',(W,Hh),(36,30,40,255)); d=ImageDraw.Draw(pv)
    for ei,(lab,e,m,b,ea,sp) in enumerate(EXP):
        d.text((70+ei*len(YAW)*(S*sc+4),4),lab+'  (yaw -2 … +2)',font=F,fill=(255,200,140))
    for pi,p in enumerate(PIT):
        d.text((6,40+pi*(S*sc+4)+S),['위','정면','아래'][pi],font=F,fill='white')
        for ei,(lab,e,m,b,ea,sp) in enumerate(EXP):
            for ki,k in enumerate(YAW):
                a=pi*5+ki; c=Image.new('RGBA',(S,S),BG)
                c.alpha_composite(tails[1])
                for lay in (['ears','hair_back'] if ea==0 else ['hair_back','ears']):
                    c.alpha_composite(L[lay][a][ea if lay=='ears' else 0])
                c.alpha_composite(bc); c.alpha_composite(L['head'][a][0]); c.alpha_composite(L['eyes'][a][e]); c.alpha_composite(L['mouth'][a][m])
                c.alpha_composite(L['hair_front'][a][0]); c.alpha_composite(L['brows'][a][b])
                if sp is not None: c.alpha_composite(spark[sp])
                pv.paste(c.resize((S*sc,S*sc),Image.NEAREST),(70+(ei*len(YAW)+ki)*(S*sc+4),30+pi*(S*sc+4)))
    pv.save('/workspace/fox-tts/orig_v2_angles.png'); pv.save('/tmp/ang1.png')
    # zoom of neutral pitch, normal expr
    z=Image.new('RGBA',(S*5*4,S*4),BG)
    for ki in range(5):
        a=5+ki; c=Image.new('RGBA',(S,S),BG)
        for lay,fi in (('ears',0),('hair_back',0)): c.alpha_composite(L[lay][a][fi])
        c.alpha_composite(bc)
        for lay,fi in (('head',0),('eyes',0),('mouth',2),('hair_front',0),('brows',0)): c.alpha_composite(L[lay][a][fi])
        z.paste(c.resize((S*4,S*4),Image.NEAREST),(ki*S*4,0))
    z.save('/tmp/angz1.png')
