# Generates pixel-art sprite sheets (64x64 frames, transparent) for the test character.
from PIL import Image
S=64
OUT='#2b1d2e'; SKIN='#ffd9c0'; SKIN_SH='#f0b89c'; BLUSH='#ff9fae'
HAIR='#7a5cc4'; HAIR_HI='#a88be8'; HAIR_SH='#55409a'
CLOTH='#4fb3a9'; CLOTH_SH='#3a8a83'; WHITE='#ffffff'; EYE='#3a2a5a'; EYE_HI='#ffffff'
MOUTH='#a83a4a'; TONGUE='#ff7f8f'
def new(): return Image.new('RGBA',(S,S),(0,0,0,0))
def P(im,x,y,c):
    if 0<=x<S and 0<=y<S: im.putpixel((x,y),Image.new('RGBA',(1,1),c).getpixel((0,0)))
def ellipse(im,cx,cy,rx,ry,fill,outline=OUT):
    pts=set()
    for y in range(cy-ry-1,cy+ry+2):
        for x in range(cx-rx-1,cx+rx+2):
            if ((x-cx+.5)/ (rx+.5))**2+((y-cy+.5)/(ry+.5))**2<=1: pts.add((x,y))
    for (x,y) in pts: P(im,x,y,fill)
    for (x,y) in pts:
        if any((x+dx,y+dy) not in pts for dx,dy in((1,0),(-1,0),(0,1),(0,-1))): P(im,x,y,outline)
    return pts
def rect(im,x0,y0,x1,y1,c):
    for y in range(y0,y1+1):
        for x in range(x0,x1+1): P(im,x,y,c)
# body
body=new()
pts=set()
for y in range(45,64):
    w=9+min(y-45,6)
    for x in range(32-w,32+w): pts.add((x,y))
for x,y in pts: P(body,x,y,CLOTH if x>=26 or y<50 else CLOTH_SH)
for x,y in pts:
    if any((x+dx,y+dy) not in pts and y+dy<64 for dx,dy in((1,0),(-1,0),(0,-1))): P(body,x,y,OUT)
rect(body,29,43,34,46,SKIN); P(body,29,46,SKIN_SH); P(body,34,46,SKIN_SH)
for x in range(28,36): P(body,x,47,WHITE)  # collar
P(body,31,48,WHITE);P(body,32,48,WHITE)
# head
head=new(); ellipse(head,32,30,15,13,SKIN)
for x in range(20,25): P(head,x,36,BLUSH)
for x in range(40,45): P(head,x,36,BLUSH)
# hair back
hb=new(); ellipse(hb,32,27,18,16,HAIR_SH)
rect(hb,15,27,19,46,HAIR_SH); rect(hb,45,27,49,46,HAIR_SH)
for y in range(27,47): P(hb,14,y,OUT); P(hb,50,y,OUT)
for x in range(14,20): P(hb,x,47,OUT)
for x in range(45,51): P(hb,x,47,OUT)
# hair front (bangs)
hf=new(); pts=set()
for y in range(12,26):
    for x in range(15,50):
        if ((x-32+.5)/17.5)**2+((y-27+.5)/15.5)**2<=1:
            # jagged bang bottom
            edge=21+ (abs(((x-15)%7)-3))
            if y<=edge or x<19 or x>45: pts.add((x,y))
for y in range(26,34):
    for x in (17,18,46,47): pts.add((x,y))
for x,y in pts: P(hf,x,y,HAIR)
for x,y in pts:
    if any((x+dx,y+dy) not in pts for dx,dy in((1,0),(-1,0),(0,1),(0,-1))): P(hf,x,y,OUT)
for x in range(24,30): P(hf,x,15,HAIR_HI)
for x in range(25,28): P(hf,x,16,HAIR_HI)
# ahoge
for i,(x,y) in enumerate([(33,11),(34,10),(35,9),(36,9)]): P(hf,x,y,OUT)
# eyes: open, half, closed, happy  (eye centers x=26,38 y=29)
def eye_open(im,cx,cy):
    rect(im,cx-2,cy-3,cx+1,cy+2,EYE); rect(im,cx-1,cy-4,cx,cy-4,OUT)
    for y in range(cy-3,cy+3): P(im,cx-3,y,OUT); P(im,cx+2,y,OUT)
    rect(im,cx-2,cy+3,cx+1,cy+3,OUT); rect(im,cx-2,cy-4,cx+1,cy-4,OUT)
    P(im,cx-2,cy-2,EYE_HI); P(im,cx-1,cy-2,EYE_HI); P(im,cx-2,cy-1,EYE_HI); P(im,cx+1,cy+1,EYE_HI)
def eye_half(im,cx,cy):
    rect(im,cx-3,cy-1,cx+2,cy-1,OUT); rect(im,cx-2,cy,cx+1,cy+2,EYE)
    P(im,cx-3,cy,OUT);P(im,cx+2,cy,OUT);P(im,cx-3,cy+1,OUT);P(im,cx+2,cy+1,OUT)
    rect(im,cx-2,cy+3,cx+1,cy+3,OUT); P(im,cx-1,cy,EYE_HI)
def eye_closed(im,cx,cy):
    rect(im,cx-3,cy+1,cx+2,cy+1,OUT); P(im,cx-3,cy,OUT); P(im,cx+2,cy,OUT)
def eye_happy(im,cx,cy):
    P(im,cx-3,cy+1,OUT);P(im,cx-2,cy,OUT);P(im,cx-1,cy-1,OUT);P(im,cx,cy-1,OUT);P(im,cx+1,cy,OUT);P(im,cx+2,cy+1,OUT)
eyes=[]
for f in (eye_open,eye_half,eye_closed,eye_happy):
    im=new(); f(im,26,30); f(im,39,30); eyes.append(im)
# mouth: closed, slight, wide, smile, O   (center 32,37)
mouths=[]
im=new(); rect(im,31,37,33,37,OUT); mouths.append(im)
im=new(); rect(im,31,36,33,36,OUT); rect(im,30,37,34,37,OUT); rect(im,31,37,33,37,MOUTH); rect(im,31,38,33,38,OUT); mouths.append(im)
im=new(); pts=ellipse(im,32,38,3,3,MOUTH)
for x in range(30,35): 
    if (x,40) in pts and im.getpixel((x,40))[3] and x not in(29,35): P(im,x,40,TONGUE)
pts2=ellipse(new(),32,38,3,3,MOUTH)
for x,y in pts2:
    if any((x+dx,y+dy) not in pts2 for dx,dy in((1,0),(-1,0),(0,1),(0,-1))): P(im,x,y,OUT)
mouths.append(im)
im=new()
for x,y in [(29,36),(30,37),(31,38),(32,38),(33,38),(34,37),(35,36)]: P(im,x,y,OUT)
P(im,31,37,MOUTH);P(im,32,37,TONGUE);P(im,33,37,MOUTH);rect(im,30,36,34,36,OUT)
mouths.append(im)
im=new(); ellipse(im,32,38,1,2,MOUTH); mouths.append(im)
# brows: neutral, raised
brows=[]
for dy in (0,-2):
    im=new()
    for cx in (26,39):
        rect(im,cx-2,25+dy,cx+1,25+dy,HAIR_SH)
    brows.append(im)
def sheet(frames,name):
    sh=Image.new('RGBA',(S*len(frames),S),(0,0,0,0))
    for i,f in enumerate(frames): sh.paste(f,(i*S,0))
    sh.save(f'assets/{name}.png')
for n,fr in [('body',[body]),('head',[head]),('hair_back',[hb]),('hair_front',[hf]),('eyes',eyes),('mouth',mouths),('brows',brows)]: sheet(fr,n)
# preview
def comp(e,m,b):
    c=new()
    for l in (hb,body,head,eyes[e],mouths[m],hf,brows[b]): c=Image.alpha_composite(c,l)
    return c
combos=[(0,0,0,'기본'),(1,0,0,'반눈'),(2,0,0,'감음'),(3,3,0,'웃음'),(0,1,0,'입 살짝'),(0,2,1,'입 크게+눈썹'),(0,4,0,'O 입'),(0,3,1,'미소+눈썹')]
sc=4; pad=4
pv=Image.new('RGBA',((S*sc+pad)*len(combos)+pad,S*sc+2*pad),(40,40,60,255))
for i,(e,m,b,_) in enumerate(combos):
    bg=Image.new('RGBA',(S,S),(230,230,240,255))
    pv.paste(Image.alpha_composite(bg,comp(e,m,b)).resize((S*sc,S*sc),Image.NEAREST),(pad+i*(S*sc+pad),pad))
pv.save('screens/sprites.png')
