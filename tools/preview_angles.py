from gen_angles import *
from PIL import ImageDraw,ImageFont
import sys
L=build()
F=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',18)
BG=(236,232,222,255)
EXP=[('기본',0,0,0,0,None),('말하기',0,2,1,0,None),('웃음+반짝',3,3,1,0,0),('피곤(귀처짐)',4,0,2,1,None),('놀람',5,5,1,0,None),('의기양양',6,6,3,0,None)]
def comp(a,e,m,b,ea,sp):
    c=Image.new('RGBA',(S,S),BG); c.alpha_composite(tails[1])
    for lay in (['ears','hair_back'] if ea==0 else ['hair_back','ears']): c.alpha_composite(L[lay][a][ea if lay=='ears' else 0])
    c.alpha_composite(bc)
    for lay,fi in (('head',0),('eyes',e),('mouth',m),('hair_front',0),('brows',b)): c.alpha_composite(L[lay][a][fi])
    if sp is not None: c.alpha_composite(spark[sp])
    return c
def sheet(sc,path,exps=EXP,bw=2):
    cell=S*sc+4; blk_w=5*cell+10; blk_h=3*cell+34
    W=bw*blk_w+60; Hh=((len(exps)+bw-1)//bw)*blk_h+10
    pv=Image.new('RGBA',(W,Hh),(36,30,40,255)); d=ImageDraw.Draw(pv)
    for ei,(lab,e,m,b,ea,sp) in enumerate(exps):
        bx=60+(ei%bw)*blk_w; by=10+(ei//bw)*blk_h
        d.text((bx,by),lab+'   ← 화면 왼쪽을 봄 · 정면 · 화면 오른쪽을 봄 →',font=F,fill=(255,200,140))
        for pi in range(3):
            if ei%bw==0: d.text((8,by+30+pi*cell+cell//2-10),['위','정면','아래'][pi],font=F,fill='white')
            for ki in range(5):
                pv.paste(comp(pi*5+ki,e,m,b,ea,sp).resize((S*sc,S*sc),Image.NEAREST),(bx+ki*cell,by+30+pi*cell))
    pv.save(path)
if __name__=='__main__':
    sheet(2,'/workspace/fox-tts/orig_v2_angles.png')
    sheet(3,sys.argv[1] if len(sys.argv)>1 else '/tmp/angA.png',EXP[:2],bw=1)
