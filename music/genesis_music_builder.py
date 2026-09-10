from __future__ import annotations

"""Exact reproducibility builder for the locked GENESIS Theatrical Pass 14R2.

Pass 14R2 is the approved / locked musical baseline.

This archival builder:
1. verifies the approved Pass-12 source milestone by SHA-256;
2. writes the frozen Pass-14R2 MIDI byte-for-byte;
3. verifies the resulting SHA-256;
4. performs structural MIDI validation.

The frozen payload is deliberate. It prevents later Python, mido, sorting,
rounding, helper-code, or refactoring changes from silently altering the
accepted musical master.

Musical status:
- G01 / PROLOGUE and G02 / PARODOS are the revised vocal-fit opening.
- Original opening bars 1-18 are preserved in the accepted R2 artifact.
- From v.71 / EPISODE I onward the accepted Pass-14 musical tail is preserved
  event-for-event under the fixed opening-section time displacement.
"""

import argparse
import base64
import hashlib
import zlib
from pathlib import Path

from mido import MidiFile

EXPECTED_SOURCE_SHA256 = "9f6b12365ad07e0840015ddc1467843c68ebdc3724bddbd398abeac3a6d91242"
EXPECTED_OUTPUT_SHA256 = "1cc80b4f2c13491fbfc7bce3442d7032249cf1346cf4f2be3d310da43dcc5857"
EXPECTED_OUTPUT_SIZE = 75408
EXPECTED_VERSE_MARKERS = 544
EXPECTED_TRACKS = 29
EXPECTED_NOTE_ONS = 7447
EXPECTED_NOTE_OFFS = 7447
EXPECTED_TICKS_PER_BEAT = 480

# Locked section-address checks in the accepted R2 MIDI.
EXPECTED_V30_TICK = 84480       # start PARODOS
EXPECTED_V71_TICK = 168933      # start EPISODE I

# noinspection SpellCheckingInspection
_PAYLOAD_B85 = """\
c-
pMJdvqMvc_;W$BH0uG15_J=0Ei@71lYu@8`afST~&=jq2FvY8vq{=1yK}5kN`<YBtU}TLvQvI0AHwP1E3_zk{w%iCK*krmowQoYf
ln8dm?9&_3q}(I+<NR*50#c{@8P7_v~g*X4m`OTXh@N4N#&TokOX9_q*TsyWf3(w;qkbk<;S<uo*VM_6<K99GQ6$pk)z$v;X0(&q
U!j54Y@z4n+?R9CWxGv5RNUI7UuSjLptWo)|mhh|G+goQ2<PZrXQXI61uMsVM54n7(j!@`Pjh+{D!6)G5q-
=#po76S?rqo5{snxQN_!p+Lq(lEO-qT*Nnh<l<Wx#mw5FZ8wjQr1T~=kym!0^edM>OkE~P<?hqJ+5GS&5BFA#UOm|}m|gS7;_@Y$
=I5)3`v2To@Y1yR&6D&h6iyNHztr*rG%en7(yPzBO8FO!THl(cX_@$qSA{tK@Fkuz(!9sK@=LFhn*2BaM-@$amnY~|Sf<7C;+-
LS^_g<%3Ss|0_Y{3JDKG7!R|T)sTWqVAeZd36kzvx-
lV{J3otSm>IF3)w%${~kpLAT97z1MA<!(Mfub$#*dgZTgpjWRc7tE`;DAKFX%$LlxJohXqv0lmqXj-{N^9AlUZCAl_-MI3m+-
s(V>xbx7G}AsaEnWASokrV9klz}nSLN1A<SKGS>W}ETLH!l^Yt&x!-
qGk)Xf_5!agrv*TMyBzZ^^hyh8v=6%9Ry*^>KQw(Qxz6(6q;>o{u+pd}ed_1f%*s@y%`Y>ND-7+%R!_zHh-
r)AF(*S8hE^t`bMCyQBLC4h~16jv)5Q<+0g`8SIjilQS1)9cLy_PGBN9H8%C)1nn8g^Mo;guG1cu_#1}UYhDHODw<cHd6mqoY+e=
PDs$%5V_r=@+2oT=KH21xO+MM=lTAL^<Wo#O#pF{=KE>oyOg_crQ+!Vt9b;5SF=-W(R-
v>TaUODaUo(J*0iFRb1H#)T5ShfsBoYHM1B$8RVay)J>|x9v#_SOoV9XxI>|x9vnPn-aglEjWr<E;rn|JRE9z5vqaM;zSW~MLCp7
uLVo|(QlGkM`Ou4RtP)6?UZC#S|Qyc0D{`L|~c;C;&^6PQF~z{h~ZfXsmMRyze=&XjmPcONzYZxVXFZ%GCan1nHV8MBu$dl|D=F@
eCC1rGy^S@1H6@b(4+h;R4eT7GaOcyM5Fc!-
Ypsfo+Sr)Q?<ST{Ob@U<FiF(zASdr7EwaCYp%<k{&dG&(swa~Ai8iK*F{v8fZps)MR2jxy#m7tc;kO<%m=n3<fti2CD1`K{AN8Pa
<@3?RRI(g4cWyD1R4Z#-@Q&(~fx0M8`ecUue~y!(m)M3&`yZ^8hKS(M*%89@2^BNX_!_x2mWW9s;L)5_;HOZN#Tp-
(hR_xZljYXHeC-
6xx+`xH}I;>=n|j9KEpzRv(&vvf%?%aTMU@x2!^fW(w#MyQw)nYD)OVG`afLS{b8tTkkj>G<9a8$cpDkFq5$gxwOs&Hc2|)3WTxo
__4d&tkHjcA?;RM54iwIO?68!QJWN%)~hBzf&_~XU~q!psvT5MIORNwEd1V)0ZcR>g>eXbJMtFo|~CGJ2^XfX~J<~dTR2-
g<=yMOVlcO@yzrE$H0JN^1}3sGh?%p7aYeYPEAf-
(Bp<<%1VF&g=4_O0MCGz0f7OL0UrYr12O|9GtY57Soels9=p?Gq&+NyXTZyVz<|hrj{%7RnE_UShg+;OT6b=fAz&qVSP33hf`^sh
VI_E22_9NPb7^LgF1$Q__PAqg3Y!}N7;3aDzxuy!TYu7q)|s?Dm6MiGpS(CVF@t(zQ?rxjPESuEJUe}9;w;*s3Aeg@u2TCQGt(zt
G?ve^$9srRRvUh`+e;-44EU`jtlAkvt>`l9q%4n9fN|MY19+BSH2}{f-
sKSk2+Ixwh)l<~(ro}~>3IXl%dG}bOdT(0ntMHFSzgBM^)elSNkpdXGt2TyOh-
1$@+xLo0%w*bFrNi}d9MMyEK6WOTz=62K4va0oil*UvXo^n1tQ0Q$J7ydvk1|<QeyyN1w)}-
Y~F{l@h2`#pSd_Yi9ObXA^g;Z6O*_$Pfc97U<@Epbl?E0`n4OAZEP)w9vV(QH8Oxb=5mZ(c<Jof334uQoV$4D!s-
a3U0c%hTNR}q+0o??@&DB1%}Yj6z7JkDfb@aU=%W0ucN;)4B|eS;4+A^{UIqjP#LRi({Heoao!P!RNTa1XlU<$cakI-
W7$&}dGiv~e0hs~i12+W{XG$c`A5|NGXA&<10?QKT`p}2!&feeOX9#>B@CJ}R*k%Bk0mTF|$AE``cGh1J5}!<uU%;+9NapJ)8kFv
vnZ|ZKJ#o?OGMV=p=Z$YS8ENlZVFL&Zhz$4`klxyF0GUY?6DS-
59tL;@ymQ!fzSV|Zb;XaTmNOG4=vvRhC&$dh<P<JAC+Heb7&JJTQ;LX-
{La!EwMtc5oE(@uO9oi?>Hxz7=wNgt9)0SdpX?fEFi;<7`v@*Kvy&&^e8r$=RaGPg<Tn!rFsth2I0ifn@J73MIqw2Wg!K!iv0)EZ
?DWJ1bk*3j9B0N}nwY`$PX~iRV4R{+u9x#MiNt_>#0b36#K~scYDpw|n#Ki{v;*#rCmdrlC+=J^ES0;>6kz0R0uKZH-
A)5|nM7bfWWdLO#DL7K6cg}_nP<#A&w%&sdIK<KjDt-HW9At%FEhY=_A+KKWA-
v;uh%TyE2K6V@#kBc41xGHzX5y<NDRmfD5*27B`XHi)Yw@ZDY)X{nT|B(^wixUY9nx_vEX5VXTZyVzyNbX@O>?50Oo`szw@L46jL
HHX3=w3FaU4rh+flN6j&Bx7FqQ~iDfZnkum!ivyb`gV?O(s&pzg}k1_igvyb`gV-4qH%o1ak7_-
EfCB`fXrauy8b_NfQ92njg$L(P-
nxywM&Q6@2o_Pt!?acJWQ>Pu{rC8G|`N%CB`|wpv+DrWu#A!55qJa0#8d}nw9R`r^bQwUo(?@~K-
H8~$V`j<xoqhv&O)FWrBO5?u5+9RDciIgg-
w7E&F@eIFJc@?_9?KftxbdOJEnq~6==D~%I+L4V@#%BMamlNA@v0c>1@8zYhr@dv0@-
^^?SVs%a~EDZaeDg9^eK8zZFXYn!UQf^Q`584Q!nAkYzJEa;=}vs4Yt!`XOH8GKRa=S1mM6l=*mk9cAPjfh6~QbEDmdOdMzF?JQ0
e|89-#fS3GI}iAiJz6a*~z-*`#jIJ~-9HIkTi2^?AfVq>^-
pT?D)6y`cJacXMXF>~=8@ysX})r?XEjxQcFfR_P*0TIFehZ`UN3$r*MUR{>rd{~@J>UZ(%*py>(>Jn}SI9D%VT`{`6JU#Pb@sMFD
F(4NYmpX@}6}&cEC>3_vah#hN$EcE4T<~zFy~k60#sEBRibwDI3?h%W6hxPLR79@u^bBeG$+Kfu9LFzCo*6IB82Uo-ya7Z8d<;nC
VN!BnDC$6|-!U>gIDFv1@YA@j({4XW?z|f0rPCO#hKJ0PlJ>-vbGYS^hz2*x)6+A>2@-
UC?{Cp&*V?du0FPK}1Ak9t;7`<W*iBv{u^k5U7!*#Hh5nD=WZ3*LnGBn|Dy&Y^{yIBG4*)%E0l*M*a`q*&IpxwOS87gQkh)3cJ{}
QqR*W4#GvPQGe1FU^QQoJ!oxpSN*BHR_t%nT2e|x6^yx%gEdEtGZ0mN^bI==S@4InWc`CF0!lyB0*h2Z6or&KE<@Zhzx!cB4{3gS
S#Q0eMO$aK}qo6KIX>8e*?Kr~(T`b;;xlIf~fHeK~9^Jk5)@g2J63j+84WdnG=-DUv(TZ#d^-
wC11n@TPV!fK3Ea+$>X(R0(|6OOSnvlBB@xaDEbkQf}J@%OhQfo+vQ#KOuLeN<r4kiI=xuCazgK|ie;B8UE3HAGJZhseL5DA({(Q
j3OAsUd#nv2qPxWhqkWMiiYlVnrNqcJd4cZPQaYg>l}DSJKI)bB|#yy96IuZx2mRjyo<~JU%%)?Kn3%HZ}dN^X0`V6_xXG1u`e=|
NSS{yDEDR3=h#A^1_+v%h)rM6H_FpJ3To&al%~WEivZ+YCEFOL~$O45t7go7vJ%9?3TFFKDD`xZ8?Vq=y~k~&Rk^JJA+#dIZBL7&
W=r)PI|1>HAW6yInIq?_#HeoL0S$6{E3%Vj8)UeGvH-FU_fNR$AH9u%z$D7iDSUS0ArRIvm|7vjD@{8Y6wK@I8S2QB}hJWclaWXa
My*GF3e7xCBX*v6!tQ%a*T<2Br%U9=8>dWS0&_BT!Kv6esBW!-zmCN4`9nVqAxKvnfWd=-
(}{z%zT$wtH`WXWafh`&Bu*_apRI9V7|yo`OuZo7lrsjd(1&b@EDHUb2GRwW1pK=3Ufzc?kLP18k4lF5-
MIKJ1}<HF^+5V_~aOdA{QrCMoYKFw^@$NSEk2tw3x>@Y=txB=dkD~d3@z}oSMO%6*X`Wk~<3H6DQC+9C72*8&^kUlc9}frXo(F>6
uA9G#SHC5lZ`3X&B0@PDJVYb;gmLo<8^19>YRpz{h~ZfXsmM<}Lz6jx+8!h@5A28^-p)v`ZA|9Vxb+pLhxP-
V=_KlcYSdKwP|VXU4GQ-yAZ4_s!!55LlLY=coaEZ~6@&-
PvvcnOP}!JQR31Q{wTM<{rlE@sg*Y1TbcgX!3Y`*V~M^`Q|f*Kw7CcfV^_d0LqG!0-
n3W8^B}g@H~@v84#GV$aLt_G6JL(*#I(AR#psmyk_hzdOfC&muC{M$>SAnn!|gc#t?|hM)kbDl?DSy%R3ApFB=W#RhH=8Em7c>o;
85SbWq^2&&1U}6L{=15?IG4#%5-ZlhKFq@#NGA^PZMv#HPv9;-
;w=7m{VcS8QM?m~>zuPL|*>nw(yT$(Wm>;9asCKqw2x3>RW_m|UE~AwPZQ5*{xZ>22;en;V!iy*nOp92`hShr-
c?bEPa#MHc*~2aLz^vAb~3_AFEdpn50R4#5vFDu1{R10}MDNAcWn76&Wn{0>k$LF<HICqz5n*~&i&iW^in1l<sGr_SB0?o2zb@&F
2e1`q^@!dvHbt_>s}R30=Q!aPyqQ(H|nm8!+yF6g2Y6d!0l2>KxEBWiwB;{YV8hJ<0FCi#Ky0KXqJKhX)Hj#ySA>i9JfyFt|;s1c
n6>L3Z0=qGBZAh>~ZgA@QY09t_P96%k+6-}2=hvz_vfXG20LKF_8f&gIg2X(wW_+!u?gK&)K952-
ic>+X%^MVuyH4a)lUCaAx6@RVfuMPTZqkjKYFLkJ&RP5STUFoUOdTOFQn=4u{v)M>QA-hd?OLo6x*CcyTy0-
PI+pG~PUeP7BR#R)kYHdudO{jir%OShwsR?^(5}wVZC1_h>t3v|WjYNX5i;6v{*rSR)u3V$dN*#bWvU{~!zgF9?)rPg&n077U_tx
}#YhvEb)><HCX0wrq5k9`xuJzi3z4mDDHQF+)PFHkSpjHUfDuG%pP#X<gO9*0(BGyF3%~xFj0&4(Ldm~}gzR&LOvul0!U|(hJxlp
YXs#Qa^{h``$=vqROYE-EvENxzG2kK&Gvyli>|N8A(zdhJ*kM>vkCq`=3NNq4u8;#V)Bi9nDQWI2a;>zZ$Y={^wli6$};)Kr|wD$
+?;h;ShL_Y6otE3vRdm1#gA*?pU)P{t5ldI^5E4o{25VZ!s)}Uz(K@An$bQrBx(G_SA0u4%_K?^iQ1E^5mQs}eXpvnzFxgjby#AQ
?{cNII)-
{AK*^!ppa{)U(z70UbWiq5MI3iUInHbjY&<wFsj6dFaL(JwS=LSs<4*}ld}&f6$?8&z*(zqc{$MTPR_$0GPfg>TgO#vtDq<x!!s2
+`B1dK!bC#;B(;?m>k$wcr~4Tw_1i80H#d94f4-
MNgyB)2Q_{274N#J?j+Vb~lRdM!&mJb2kRv>(qjGH7c$~&D9umHAY=)7!K=PpiT<Zse!uwKwUU67pSOa>ZC6Ds``CZVPBT^G?gCK
J;6FTSl1V<3kK^VK{WFK$N+tmH$u#0sVXQ{MI<znO(~WZs*^%>YN)P1R2L4dTbf+eFIR=-veMk)Ix$@557+gD>w;l4D^-&gh-RWv
)u&Vil`I`AREkbU>f}gWU!*P=sf$F`b<$rI^jAgvWloCGIyG7sjMhb>b@3>gmHI70`VGz0-
l|A%RlFC?R8xv|i`7Z7IyF|;AFB(;)~%ab)vs2C)v~&E@2T_dsgw8Ase9`B_n=uffS3A7Ez!)|SEcq<_4j4zFsIVPx;I|ukJt6b>
%#H6SRBpD#}1nLwW_dI71PknZ%VOA2I}O2y1s$B;6PnuVBIF^uL|~8Mf%H{q$^R!C+eg`otmf%C(x{m?m}z@LNh*4r3R|Pfh?VBs
!=y?Z=JNaPTgDAzqc;DcikolRP~!?mhMj0iOD*DvaT;#7fi0(-
GQpUKvghM*4=2M5`(%(vM!!nx8DL)kw8^EP}XmrWSwjlg_i3!2`LIK%ZGBZPND_&C+ot=2dvu_y<4vL%Js5bugdlP@=dv-yK&u7>
LsOKRqFed`mllumFtezU+?$V_xtO^{(4;d<Ta~?*jumm)(3m*Bfa(UUQ{S=hby{At(VpMKD9om)<;xSD6cU(*;nuFtC#!g)xP@vz
IB}J(&~AwUefAStv;-
wLiu>Wg{i+@?63Ft*Z1|;2m4W>ybH0Ka=m0WLVZ|Xr<x*dgrHI%QR?H$I<@%1cJTDp%f0n|W>c)G=A_PXO%m6na!vhQQ<%FMs_+5
lrl-m4X_7rns;8;nlkbUj=iq7#(qAoa4;*@Ylgc**`KAcp6z7qt+*zEi-X_1dso&ca_BO@5`JO>HG7TbAxzjirg(g{O>JyrRLQ_O
QrgEooDvC|K*d&Qfs@N13^F8}HWZI8R<z0ZY$k!zLn*6?|K3`MNhfL*NfVJbAyj+uPwgA?y^M19X4G{D+MLbQok*!lZzRAxw_47?
(zA46I?Yi$*J8zThZR+zj1-(rX?>e>PgeFO7QiY~|p(!lndlICb63A59HN05IcULK*UFo)I;$vF(#-
P|3?A{O+pNMwfc)4Pqb5(A8yswV$tWtb-rPHSQ9@9EE27Qge&J9uD6Vc9meUdb45-
0H&(QtMA?ka_|E4ytP_n5YOV~}eM?%ojPo`~*#053dsd~22Bu`8`M&GVSnx)Gy=VC#mc=ZR=5deI4dCy1TouoCEmaOZ<K<+8-
>q}lJ;5@3rNrvMH#JOywN<-
P~2z6EGNqT_+Fmxlm3+Q1$j6)+_0Wh{G8K@>n0ASggofVhAP<?##_!GmHRjv&Tci!g#ioNyp<psxB*>Q&Q+UIBapXaa-
?KbG#J<{`)^y5a=E391tU&V}Grg@%mOGE=SNc}wtt>Vtr9(Q{wL+v@#E<{q^qoO+;n;kl~;$UdVh4iFrmIw0W4Z?#%9>RRKx<En<
*T4Qb#f?J0Xr7sd>)1}?O?}pyppzX$zj8j`LsSUa-$-v9dD}yF4daR0*R>eZSe&4*gNlW5;PF-zIKaG1@s$Ca5fa?II1Jn*ISEL6
$dOpQ+ML%$UQ2e0!7d`h?#Adp0-
rS>>L@yS*5XWLOO}f|$Tq`K8ptjEKvsw_}GCV51*{An5X18OnV(SQ<(Ax=8C$byEOd|dX$f<&)E_zD&lcjuYj&-
DSlMMY}m(F*A(gk7{va(r#th@#ao};xz56i#SUCPJGGU@!jl63BIh6<X_?*e5Ph`Z9!QhuYZHqITsN^94cdI7=WE2J^Lf`~&f*G4
*Hd&yx?JCU7vimj5qP^v7bmin$yyxn$xl7(tZ;?G1~>;jI~MJ08y^Z}M8YQWKUP_Z4XiqDsIeOnpHC2QXNAxk1VK!)62tmVSP1YI
HMG!Fl4Ee`+rUPPH{M2pS3<O1FWy)MvP=#^#IqE}J?_yF{hdlxtn?x%=e-8XNc+LHMG2Ay}4TREZ|0&Yux;&jE*_z)-
|5JM0M;aIqzB9>;&yJXFqpRgou9n|@DP})Ikhd_I}#j4n-
A0Pwd01l7?jU#x~TlE8Ed>p{>aiDo#MS$ZYyd4tTVR$<n*gpUGReJXVh5-
(sxA$yuuth)*cS52QhCAUv=gp%Q{e@S<O^|4U;U+lH6tUW#vfx|e)-
rNsWn?Gx`%&Z`wj{nU>xY`tFJC<bH+uEhb{Hg7aA<qhhS35H5*0WE3y<otCKx1CaHuJL(wgT)f`!XSkka&6Ck&Fxz@g5Zc3-
xnm8?7~9ku3V#;tj`Ub?@7xqeH+cYpq$9nkkT&nHMswF^-;h6w!*ZihIf-oJgm<0`#TLQM8U)`MF45mT!Z;<SSMJFmTTUz4OBY=S
s-
V1HA7$eOkIthJ={q%|)WxF5${zg6!CpeLKNuVJjPa7b6TLzogKx2MisrLiGVOhREAwdUGMM4{;_2``B2$<FjM_ca;U)g}njVv|kf
S=l4^&l`WxtdKPeTjIWs<dgTOY_RHySjWsmSjTssMwFgF^uz5q0n_6+0do=S<jC8tGa%!zPLABHH4o=>b8Z8f!J2h?&ez|UEomkD
oUGKiH49t7I(g4q^PaT&da8_mQ>CxjcJ%chUcgD1_2DGMVST81ZkstBSEtK0!8#4*H(RIb&0&k;!mF0aBbUvwLzcwiZc9SYAB^B-
OX3e+(?=UK?N>+PolW{E>9bKtKd;AWgN$s4(e0U6uEuFaM*v1)VY?oujWE&#qhtxP<T;Vx+GZrcI>%{;jda3jXRhbIY)LCwc~*M=
{qqW;`#YG~Y$bW+{v<!QVYgjt!fwOP!VZ+o!DiVmwwEpC?WmQnT{9%Fy>MTX@*z27&6?}BBo@x<56CfAIqot?(4j)us#I>DdG(&n
4YoFT1pq<fT<Sj_#UK%ajSC!!{)4a*_}Qy+=9nXvIR=6B9Eq(U+`I_Jg#XhSOYTnw@8N!F>jaw*bZsXDcS3Y0?AZy4ow{Emq!4X{
J&llPOr5>Tj!WcZlYqj@dbvjCxeAT><K^j_4SJ$^t`E<q3&(YTBN*l}Vw;}5%5K0Kx5S;On%;t{*M@ZePB46n5y$d1<))dv6{dw~
1$kz$QsZ)Y`VYHxsSymLD79!K@si)XxsDq7Bf7K`3`e5GiyPe)7R?nF=tYIbwhE0KN_qNj0s~_RG(xx$;<U*-uBz-
X87CUIUAnpx0y`nR6XL{+)azehvDEuToOhloPv30Q6OGv>Z24>m`yeOKKEN@9p;twJ4_5Sd?xCMKV%by3Rxy_5cT`wDTRE1Z72G%
;$~AO%dHREi%1+)^(aD*Cih*-W`+_l7+)_Cz!xb6}C(6_B#w$8G{YFJ6-
>R<|IN7Zg7AGn!(2FnNES@Y+U!T&GjrmU8r!&uzD2D9VsSVg=*;CjbCn1pODH{dJ#!PqFC`iKG(`6$ox$_$L1s1n$m7HA_8aEG=r
@!%t9w5^{fZ=?gIlmD>YJ)B~q1Oo#xx0|5Up=Ye;X}A*8v)~AA_ltPgI*s<<bK7cBNnTCx78}MPZu1}>i~(|eZY;-
k_Q(2rrml+0mAZp#B$>R!n^ab^~gjX9!AQT?N;WmAJWUMbE6g3$JUVHu;6z>FC7`-otZ#|!MiW&N(Tt!b^-
)CAlk9;YK2AFofRAj50w)v4(o~^1ajj70)B}43${u^r4<Bn_W=T}5N%ycSf2dai{<I`S`U9aLZ=>W&JJFU!rc=(p4NTz^@30*?CD
&?WVhbfA}hc;Os^nQ>P5X*1)mC<3LzEtsBa}InS0y7*9KY}gxX+F+gj%G<Z^p?`np^Hmk~PkJ<T{eka?rdX&{li3lPvCtU+AMjc{
Eck^2Y`=z?$;#JjSMWq17OWXg@}<%OnqRuqZ@^1+xKYeW&9+Xd1tP<KIK7ld~~d{?$=t))|sH|K*GfW2+gc^4?;HUk7*5OqPqwea
d1j&l_^cF79eyoUAmsLlsKAvZT57=UO15`kL{>+thVP@JGSA?Spt6B5pK`PYcv8($+zRq4Mge`1a3-
7Dnvl3sEb1j26E<A$Vr9WrdtiaW(gI(N&-u05s;A?PLdULYKTJt0VjR-RdhUucJ3az6#a?XagElI__i*Wq6yxl^@9v@ote5P#K!@
H@#tavC?Iw=U^o1k?xwBM^;1JOYD}^a+vP)((=}+7RbpkV{>uygfb$^BeUCD*fwI`h)U`bj1pi6$|1WFxcT*tCrfkMwA}b2b;5du
Odf4A8yP#uMWfF<GSPl%>!W%#5|Djz_4dNS@CuU#_cI?ZK>;d_vQs%ih)L6DS}vxY<t78>&^!)LZYh@9%W+YX(oMUt=`uYYhA`|a
*bZD?ZJvTw2mts`fzhr!}fXmgs#x%BT*jWJS2J8&*MI}4vE5^XV6dq_S1!-
oHpI2?{ChWzq%jtgSrxjKpdiRh{qurhyC&5>2*p{=;{|Gs~;r0V1L)TC9RR%jja*oHtJs<zmwekN@7Lk-
#~P;6A_0X)kJQHoz(djP+CB2S%<%-
bi*{ASVNm_AvZvEz8jQo5W8<azDmS5gVGFQ^Q!&AIeo1#WiQ>s_pQ1imh$uMrTmk+(m3bC+B$z{kRsq_ozBsiN^oRPo7;>4sbd%f
qoRb0Qe*b32%gu;TYGL0-1**hERs664Ww-
#Y|Cya3H4h2K~=ARg`q}k(GLQ$FC!>C_uHDS1sU?z!;MiqfT4(<fmeZy*Xw83WZmdpBbsZ_H3tM85OqMpfpM&Lvy0-
HE`J`iQjhBzeR(tLhJ<@QdS8>Iu5E+hHi&M6#J1G-
GPZh4;%2|@rw>bU1&(p)Vawqwb=rE4%5AeUrae|h?6CXVZMNX~D|)OsGjKHq*Xwm7N({F`yp=vwS&eSC>Hh7YZHM4?h;2{xSlMpi
`Gq~Yjq_RCeMwTPuI_-q4hZjn_>S_t+mBld_gS;jAxk3jIULzBU1Qr;g1hc39i8#qJZf#5YrJkeNKObaDC7dcHi))Cq74SyQUR-C
I?fPoDNC{?k$PCSSY@|dwdAE$J=g-#7D%+fU`zVEH4nQ5&su&O!-
So=#?=F9nA}vim>sv8Ei~wOUh~rzd&9o`mCxb8IqG)+4#Kb_x6zt)!(mBe?fUP+@roX8%zXuq2iH1vWjFNghQMx!?#{Q9#k$X2M$
7CovsU{6+UG~n{smo;p-+Z@3{iQW`y4K1C-
l(+b#!NTqc!W=s3nm*tUnkB`eVt$V}61>M>i&YW;cQtbd5z9iH^C732Y%sk6Vcv(LA@uF!w`{oDw17Uzq$HF0B=U<VXgIR^+lyUE
b<KpEWE0%7ammn|=$&&>apzc7)t{QmxvlkxK1M7?tikV{ML9KZ2EqtfKT+5adEuk%HITC#;g(Nd${WtRf0l_K{5TM$KGvS+nmzu+
&~g5h9E93szD71t!WJS?gDv6d7M%Kif+5FPByA;2Mh5B+-
8v(SnP4F>Ev(YP~^Rl!&Yw(VMkpY9#aKC2Yj&o6RQA5Pwpdu603>h8>Bn`772Y&u%7K4pWP~Vh>Rb6592n_cg)p-
UY#35ZwidU731o*23czy_q}p1?7JZ866GPq)Hy$&kl1jJjq!sYOEVTdY|<uw^#SGLuV{-
^YJnUKRdg{oD~d~#N1I!Vqv5H+cS_8HFgE=2-
UjE4t?=Zs!L_ZvAFwm<@UBpoFB0=>&Nx`nWdp(cVmaEczc;1Zdz<M8^;yvX0e$$%OOYy5Tsw%*(PS3y{zipzf&p6vaF+JjK}dbwr
~_rW8?`kJys^@v2y&rP9z_+pf4e-z?U^fk2P=LLD?-g3^H5Fr@;gI^qe)zi7l3KV~btir(5oI{1()o<B%l_Po35n@dSxDXK-
R>&g+)DI@xXa^#O;(1C~@4_TZ4WP<EC@L`SW=QTP4n-+2P#N*vcQ9M`etbQJ;|UpSY=)#*I9#r#-^&9(d%)Xg0<bps%-
t|SXxUtsGkPd1SmEv`=L+>Q$UMm<iJaGbb%bS?x^2rNrQ#%COnEHghXuf27btSDrSQ+PmX2dNz_b2bfYd9cABu)MW&>!^KeWQ{1h
$+}}b2$<VIw#cn(@~~%0Z*#Jlxn=Dwy}41VWy(%=(x}cy$k$*RyML94a1X*YU!(K%g+NPKw2s>H4*g4HyYtWksogxcM%1{b=06(H
2OH-P;firXMTD7j5i!8RlrGW_`-1GA$RIzzW$i63vg%+QLf2`Lehn97_iYB_*M=X6BT3${Q&~_D?}EWD464_t;duNq>E>G2-
WI%swaM3EZ8FE#lB`!&I)N5xQvbI_T_a7W!F3NqPAkYvBe<gTI|1W$k(`2WjIO>Pr$J`tJzIdilq{0*a<|i>oa(YF|5=wMQFxKuy
b^fe_@9FLOooF6QRf7Z1Q5te%0GqDtq}5>WT!65z{!B;9aV;){8O;L*N8QA>fz@3tyja4>b+O(-(cGZHVrD)gU>1#jkHZi-
v#r1=Fh<Td?>wX^<`+<fuBLexJ}pU=xVP30Rh4S>=8bzeBnCvvM$nhn(1ex5chpn`NnnXC34b9_(AeR*bjUBfBDM24ed}JfDJCFc
4c1MAVYQXjSVVPtLfJ_#G!gL_4<YbP<<fv#)iXCeG-
K)K=li6Y&Zkevzf$(SE2fK*zg8azu~o=gX&A5M^8iY5bQq<hfafb8WN`$PmnDp0UpV8GqWSg?hPISFU<q`uoKtRxEqGuFye+$_Z4
zGuljIdmmVE}qzd~7;LreQ1CSV4copOBqyYOhIHZ9_V(_`AuUc5aU|l28_gP+<x#`!}(B$ja(&$cov@xq(9fhwSWazyChJKVN<-
W$yyQSQ3)R%JGOSZ2wl=;Iw_Y$vuyDc&F;}QKp<Mmea_0Q~a1k2m4qO~Bk1;OoSt)jVu<h{`=R?)Q?1UKUAGlcJ-mrmS2@A>;@W$
HesxN{`$5P3Uk2YK)4q~1^VU)bw}1J3J@U8SGS!d~_+P~K)L`5@+ly*@bLyAh~V%5<z@T6neJ0Wk;cb-
)2fs>y1Rf5MVT@6rQg3P92i2mMGLV2^SRBK1K+eUMNGI$%!+Bs<_>M<unzA`cd7Ji-LY15FszU_?Xe(yNvuNIgQRM+kM$TsmQ-Yv
I*EE9_~7WGftOMQV#h9xUagw(8nZh#rN+QP_VJ4jpX?g<v2ALm_x7ge8Rl1^|Wto`Upw_KJitn$r<o3qdpli4g1$!J$xN$PEK-
7;?i??uGFnc}@v~yI^Ej%2UQOSk9Aq!s1-
!%)ROzP;LK%di^PKFaIeF9W7w)6aszgJ)0kFJo%Tnw8T~KgzETTzoff;fa?`c?vde2WqfR8e5tN?(YF(NWRT={;b(4TE-
)3H3qasqFh3mYp)0HTeS*vX8C#%T;MTn=xK-
#<i=*TVFXTm&d)4rPzq$=dnb$j3Gj&0O9u2xRT2}Vad(~SqJwGdzDA3}%iCgsT^PT`mfzK*Dantw2`4IR+e;wo^&=mo11SIm{uis
j?|7y%q9o*02;EDr=1`7F5{utRYy6DGLbl-UAg?rWZmFKDfo`scB+YotEEfFWbQ&2sQw)D#kk-Xrrfov8oS_<7V9==yCz_Z&x*Vq
lu{cVLES`$R+n|1q}a?f0~^lEWRzi-
~#n&mC^!XZn}wKw!2d1sw$hrz}Sc`G^lgf4ahM?XMP$*(13<%*qip%!&>PonM#T~vWnK_MSBKv2!SR$(etn4*_oK%Q}sjimY*Zdm
VcuE?8j#e%anSnyIv4>x8VxO?jzy3_@H7xZ?4MqU&^$I9O$nR`f=G~hMpr8`7eyFOfD@s$dT+xsgxv&jmLcMg(Itg1)zLPf@n?Ru
2B7=@e9-?I&2^rW~zaDnQA06Ew_RPjd19SkS}Akg1(2#}Ly`{(P=x#^yYEfg>8_yX>awv?y;ja&EAFB~-
UM=!FzigVMAv$~&70$gQ+A&7-
?FMol>(w<7r$^+kbUMx@FeH2fC>3XuBRL7vYF9moQ)OVD9Cl)3Tz>#Uqc`Dy|&xVl=?&zF3Ga(RxFnJ_@J-LP<b9ya9F`++@-
nZ7i+wtKUo%eu3A3g^?5G4<vv!S(TlTn?IfkGdH2V)Q=kHHH&)>vYpYb?>ZwIv8^_1+x6XX}J&A5?R>#<khMr>#9lWL{qXXp=sGq
5ZYP_iWuz?T57|oZOW)RM;_Vs0x?X7Kxs((ffnI8qwQ|9&JvY$0?I;WN5y}e5b{@^$>Msyw<}3d4w>F6D{pP-NAddZBX3~=8HGR&
5LN@dZK~>Dj4ukQLd3bSD}H-b|8CW%Zl^aGf6%EM7jY7>%yUXwi>8z%yJd_^Ka<GkEdR`It<_1io4b7Pt>%G!H2fzp-KkZDEzxl_
|3zc!V_oCOhUoc4Se^zkaE#gq~LM`?_N!IkrNLlyXZ1laFN~C$i*THxOsH>G0D>nryy$J#_ca9(mk=j1)vMJzLc>Y6<iVEBdg5bI
Jo1Oq#LMO;3c~v-5gEP`lN({Tg-Qge7ZK}h8!=#l|q+n=Ver&8)mAZAj)=?q-
k%Wfmh0R`UN!bqJbX`c*U+LCB}w=%WoI_n5IAbK}wLZ1kq9g*K3!0QGrf7G~j#fO0UHw(Vy?+Bs37wfI|bXYWJ(CK)*LegRVY1-
&b-
GOX$TCWJ?Jy%`Rvq7qAYRUDd30=)*ert##<PEB%%_xC3@EfN2^FpaG}lJEdMU;Lt!K20^<Lv>1p%yBf5X5Wo`ptR;l(O2}G5*e-
@GCGf#~r=p<&j|K{9CB-
f&mR9m8cA2E<H`SP~%y%nxQ7I9w)fW}Js+2rjYu~Ndy(CRP5684uvHKNEqgV2EDRy45jFT_&r?UJns!z9Q_lg#OIMFVNmVB>h_lp
+)MA5E_R({bgix&P$zAn+uix&UgqFod%{#KS($zNH1WqBNLmw0P^c)ORklrQpjmACToc0X_B<LxqUZExPr^HzU(yU1Jo{g?7r`pf
fnh3|BA-gFydc880MVnf)zo^aQC!YA`_7k%AW+?_vJ%2tiF30?b;#K|ML!gYeH^LuoK!@Ppf2|XlfMDqo)8@TT8(FKpJjupxnWOk
9Hx&HOI!RN+g4|&ZrqZC}^otlN9u^42k$;vCZ7d>U-
+iJPm+@tj3EC|gD&!HFDX9_Oz7EXR^%FN&!<{jt&0olt4Zk<MyK1GnN&_!N<MlRY{SY#ImJh$jE#FK`&P+urZ&rQ<H_nZZ>IsG(N
HPv3ApIsvltvB+BWS3a<l!?*xvb6aPcQ4W`#8H%KDu_FP+cCG#$S3?69`T!d3qnJ-4r_-
V3$4&YC}@LYNdgZ&Sdt;0G{op}S(<*F-2*?^Rp6cAa-ucu5VXc)qRY4Fq2g=Zh8X>%>G^#|ntp`sf`V4y9pG}LqlOrpykYKeine`
2>Ij0xS4b~>1rdi}t_?wIdqHS}o;Kv7E~GCM1Oa*kbl57s-Bzwfzo_nkKNAb06FA}tZ4tD_qb-LH8{+59hHW#|E*WX_3+e0t>7cz
RTX>kDD+FC4!+;FP`2jKvUPH9lT<9VrA4{Pfi>1(mG7bZ)7)vQjFI3aZ_cs*y4sdm_)<SEZoSm^ztzxt`(wB@h{esyAw+<HgR&ce
ZTUet?q){abVtCbC3leEl3ENa^o>viIn@VkYK$NTc(3T{3_zIGcKZ1g}hgeqT)q>QL>LTh#3mVDQFj6mQBv&(Xb9;!Ms}Lr+VaOd
Qgh_6g<Z3Os^F*(W*^U;p=JW{!DUFe&?S*g)HAqj8+?P>yqnG6-k;4T3mh{P#AFJeVUbu_^Df~iC^S7mTU@AT7w<-
r)GNDuuu8D=9kUbe}OI^ZLDj9^lABnQI6w!{gq<T^@xLI9@3EA3MTY3mnJu%3?!R*tug<x~`B}DmM$dnO-ZD|=((@3@n?Xl-
k{X8nAiBh%(Q7%Z(69rRsE`nqfrDh9aOX?7gA1A8KCkX#8!XG1<T0taL7D>CA21G4CVrG&C6d}8vsiiL>8%6mo1(oEgkck#llB-
&Cr_piD#lp^_PbkBqc(S0j<l0bgzJuAO>zOTefa;|lDyYrb*HE@_h~*Mf3g*6A;F{;!aT!MUI3fKE*Ooemsc}@mcEy>qpJ=o3(^2
4BR`WwhaPu$@xbz08jVfd~{BO*vbP{!P8_<KyLx`?dp{J=1wT+0ggXm^I<IdYqDLp|bHKg1pwLM9O^@~V&&g9AN!EvA2hhpp_sX3
<*mr$8%E<B4&1l+oWdFgRt9AQ)7sF|1clEFS}OseMG29v;;F)7)qZUU_(HI9REzJ-ncV>qgFg9x(SOsflre6}4$xl?QgZNUkY+ft
f9MBj;8nSL_&b`h>>t!+P<Rx^|-+(NZeGpIBlAxh`5oNU;fJrtlCPM^zk`e1=RGVhS8d2X9A7yZO}zfmGJ$h?A+3*GTU{(>df-
$GG(hK;HG6Qwa#%FRsUe8Suq<U)lQ$&Eqg5{@Zc3~**V#%xCm!G=sTf-
8(8y&2~e)lWT5CdM98!X%kp<0SWark7*`lnll+>0c*~fNPr(U}aPx*Q2(jTx3uWsaEB1OU8#yb(6!k&ORM(OK&0#=LthThD4cH=<
trWq<T|vxcNjOE@WPhx22C_>Z@^>t7i7;u0oiM{4nW{u#j;gQ#WC%3d1F|PoGbj>ZvD)QZ1_Est_h)&s3e;gSm#$Va&bOL}-
z$IV%yFR$72BFg+(`=4;JNW7K79nOb_14XC-N*l5f6N=s}hH)TVX%n^gd9B=98*os|RKl4o=+76K486scu9w1-
xZbrN7n^A`&b!kCx?J}BWE+hJ@O&DV>k^|^UprCc9$Z-
A}xe(+K1>x)R&sV?d{S$XVb)y&;6bu=;MY4sWk&8S6ynW1wwLXACKaV>7@So8kH>LZy(L!?XSiwaDEc48J`>eTt;s23z-ixF+-
zX^Eh!j|St)TIUuo=!3wARdCI-iv0xjxKHRWY?)1*IiDi-
6>%w;;GSRB&_o8u!lhZVb9pZEm==5hK$~P;5z)*emV9#nnNosbV$fA1(O#i@}|=&iMvE+&o?|Q@JB(hJ~Pd6j$X;8$m}fNJLo|WM
0C!5T`*G%#9cLZtDG_T9Ej;$D~%=+OX3O;mV|y^3E1GV#&c0b|DW^H<pis>@xQKP$Aq3xG0jLnM&d+cCet5y3_g5kgZ0rzo3#fP>
oegAoLpw5}`)a{B!a#Ee@8<AXx(+`nmbhENRsp{LaU)_)Lt4>oeGDxr5kX$FQC170@?e8)s}<Yr38cyhaW52&$+`%cH0;cT#~Hrw
c|RKZ31_rD2OU7Xqa10+104*vhjgn|q8k)#5m|Cn7)07W}Q5Z3wP+l`>V<diukxU2dK)@GY+*$hxrcXnjcZli!YDe?e-
+u!BhW=IjJ2r8Zzyv0mNTQ&`DNl8BmrPQFJ)mJA7D=bmQmjE;td6Wq>c$YeRl!L^;N!4@B3?W@<98d1cC#ldBSTKSD;3%8_Bk?B1
4p=}h5e~Fm>MnT}-YQ|voYfs~O?=3P2-
i;PqLg9p~ZBD|`osJf|c4Pu%oOi*UhYLMERO*30I#=Kb;^0;QH{t9cqU&;jmr;fd5GA#I1<~@Rg5akGy!~=P=*S*Jl-q_;ea3D?+
|9XB5?;Sp5LHwY;cHJ7B!X~l*@*KXAH*J8t}7@S$`ttM(So2-
x_9del6KQCbuGLqw6&8es<;R_u_8SMB|w$Ga|8)8)1=Ff6ncrQ7v6iSpoVTdq`DXCvCU2wdY#y@xMpwar3-
kLjLZ3<g4U32#Bp?UYe9>kodzGCE(8b)zyb}JG@Mm>Qz008tC@yL(dNwgR21GiS%}7mqr3z0!jVF-GkplNm%5{HV@IJRj&>1{M$n
v3rpUcLL^nGTaR^dP2yQ?9q3y{3AQYkvb3RNue`kO*F$%>At0=n(!KcxJLPT`Ac_5HIgP`!@Z)>&|WOgFBadJ)GjlF9{y=z2sTM7
!Fm&wu@B?II<L5~-
d_<U61Q?Fnu+o#}0qI9J_n7Ce3P!qX_R3S4;0?TeD&kx`ZfWfLEpQ|N9WdP;#TtSJY#}!ZN3ennDP`fdd#PF>ji;frQL$$1pzD9%
xG2`BvT2MNv`pq*1DUu#D#OXvq;xbpr-l&qpk<!Wx(sj6;Zeh7Mo-c^8xeKBvM-Fy#kBM-
@S1?n_g4l_Bxd_+%1wNh|;dvaFxKL2}ag<-j-6vODSe5f#6n(9ZoDbh1Gw>Lqd;-zOkKqA#-
eI0}GffDtUqOVSr~v=?WI=GEKLX4-t!gO`f)@&cFV|(}lj-ZgxKe=ZbB4~U@*9S-p*Y2|iXp2Ko$$C(h`VJ{-|>P-
^2m|I1gXw~C{G#LSeUqzfLogljqD62UNDXGo2|x~tz=<-
!8FL?dPwq&MVRh0SX+yT1~4xaq>eeVd}K}%tsz6?Ul=jPNwRK}kUL@+m8{c#vP8uTm3q!KMbJ{Sj}dek2TJBN8N_5bqna_UQ&9vj
6cjc0xS5aDR@$(Q5p6JZR+XPMlnq53=WP^Z9>Tl@m#LH^%Vu6>nbfKCBsSYa96n99)&^2vvbm#s{%cNCOzYt!%jxSz6_C<w!Sjah
s$RCuJc?jgX6!YYIH@I`-
CHyDW?qK0Mdt4|7hHtO1%H=h$oYUEe}TkxJJ#eal!;Os5&Uqn;BuxK5zS+S=AbA$vqtSo!R1R$nwlAvX(k!S)VrXaB?=9NHJb12E
U98{!+adkjYOe`l+%OdAlQvy;bfu5iASRz$e^rw{tZOA4%|ZX<EDJ92huMVdK}q}n9z@x)RRoM@E98A>xc|<9W*zGB{ioB+1p`O=
5<e5=?rAX2=B~?ws>Zxm%NFF`~HDN0T0Xc>CJo?C-
%GKrssSFL*Ti?g1q7+wR%|~cb%A4sKEQ^v!MAn&P@6kXnvq%=`WDCFtC@8BbYlZ%D2h=p6h;*WGUn!l0uKJKIkH^bKJZvsf!UsUe
?G2I*!Zd1$zHU!!Z~C(DJ(3bV1WHwIBXV-
Z^`LymMCIkArd?qQ^lye)}urw7H8ne>tDLUiP8w5ZLxXLG@kv5U<sT(|d5azjd_0M?r}~GzwaD;Z?pDlwOGTg4R3tbc)%NM{^eZZ
dJjem#??#=>my=yO8?pV+_6bG($fcC2It^lkkmdhTeU;B-
_c**L@{a!%*sxLYD`44@jPyFQ?eA_GVfNT`}NeAjKB<txEsPvxWYK>#caSaU#f$AXx6Qiq?Xc@p^mGDw&HSC~UThu8kwOacEtFlz
9KVw0i%%{rAtxZ1|kwj+=SS*&QkJgXaZr8~EFxzwP>CDfR=xsMwshnb`vP1?U%U1j@2A9p%;wuX<a+-
va$D7@;x6{1Xh}*;$~!m=chYh`oC0ECdKqfDj4vCr|>r%ZQj_9vD%!8e?JOofjlxkF?31I3yy!R*rkW@q!D6zVs(g0y~k2DdtPRH
IV8l_yW)ufKUL5eDuq<5ah&y&jo!h2)Pzs727~<gJ2ulv;2JNPkm(0d|18X59$jc5}Sr_fwzFUQwa2}^kK@7`Px?c`)?SpQQ?1E(
%){jzMC{!dNFAuef21H?{z%ZS05$w_z!#N`z}8`g~$DB6vk8kX@?DGeFUoe?w+LYWTgIT%7!b00M*=|?4+*~{PW`lt|4v5<!SIk`
i%aYGwgx-
?;WL&&`}o(ob&F!53AeKkplNbY8yF9jec0|K>5xTdGM4S`mnkozq`8TV0B~WZ1u)eYc=GzR@cxwfT?pIS|7A;dImnS9fK-
?9Q6OZ3x4x(O?aC86~E(S7cNX(fZNWxcku)Q7SPs&pbbIC69_sGboCUR^^K{4bUj>u6ldk_ojm63M9}U<&`zv<ruA+G!EPeqZbeX
{-
rh;TP6S;Z1YHO^2<Sktn@6x4fs;3tpY$Sll3007t2O~a8_^L=oeq(ii>7&(&t%@|Gp(MKOr8#jDa))ZnK`DgA{17HpB3R}R=v!sm
szQ%l~Xk(ZM<o|i-28L$xhx>E@gG_CUZ&0L4d>B8YSf}-
mKSJ!V=HgLLF|Cu+42scDqgH4mY!Mn^q;|E;nmKH)|GVUa~6jl+4?@SfO1ePe&J1?qbSatU6t+h%U2;2eB#@;p_tE?pqwTdA-
w2?kZ32EKly33pm^I=S&ff&W~&n9GKnzWDL~~_dglqyRG|s#)xm_QPK+k)1})j0-_d3y>t9_yYHXK7*D;)m!R&r-
QqVCZclt<3tju9o~$W;a^o*?F7<aqw_CYI!j$=Mr?JfZ-Ay*~($m5ZgSPn6@1L>7%)mxV|LNZ9Bj`Z<$EVSOKYQw<FYV3sV<d{W?
HmQyDDb02p46D$_Va#Zi(jFyp<n;|+3FqtvEO#YTnbamFWqhlq*h41+_!g!ilbyAe`LO8ih>XPA60Mp{b@SATOz6DU|YN&b-
!8vi$EXhZ6htY68OcIeoPP`1QBS(6TdheLNJsOs_pQLBkD1%>hfzJ(Nz|HaUi%d`jIVJT5307?!zA$uX_Fh0=VXWgl$`WxO~wKLG
_Ti==z{KRKDmsp_*S^bpPK=_g`vnx3%5f_fd6QPR8~1cAFzLilt|VKDy8PikYc%==gO<X@RYBz{j@ZP^AJk`Cq7HfsM^fOr1FGh)
>T<UHFSYk=Jf+&0ru?R6+|}21CblMStYFBjYDXjA5n-3tUl(Ba%=}OQ4!YGW(OL)=v$FFw;-
egd|8wP?L+05zP1TGRKPi0Z<Nrb^xX9<u{ayhd?<5fkU(i<3~%rbq@WhQMBT$p?D37QlLf)V4D6s3#PrH8h;4WbZf`7D^epwFir0
=W15TANHI*)Hy|)A#%t6#rs)nmf2=6^w`%^ae*djw?%u6p@7BKFOu!&VzUz*nOWi7{TU8aM#yiA)L@M@eRr|KeeJFLAFKMFGt8Mj
bTSFR3jSXHVQoety(!Vv>k5VK42ob5<Zx{WUA+rI3L`0sA(K75sNxC(~3t)I{FDk;VDbZuLmc6KYZcTaJU=(66`rWst4C)WCzM&c
^biLlN#8&l$YveGd=^G)K<{~vx#FFoh)`(F|(}Ib9tVWJm^u;|j>K;ssX5Vq~8YynE?;fb}4q%$Tp@L~|qQ;-
VH1&t@?X8jbTKJ@7jh4i;WcE5YSR)Nu{TZqehb;bxLpAD<rF_p&jXY$n&rpptWc5d@^J=%wbG=}=R9BRGZ=LtbW?R-
3{qn8zB2rTa>x!y)>%50I+p?}G^S91-
<4KUx*A=}zx6T_p=|$|xR=d)=FlBT@4vPGfcI8QHdWT)v!P1L3(_&!rr9Tc7dpPiM(95j^GV}!&3?BdHY>_??0fk>-
gGhn@@_MmL0G@mng;I8;NWFKu*g;-q0MUoy4*J532&s=ADmuyg1Hk*=c4XL+nfmYi#dZ~XR1j1Yx6`+61W5henWFLbycBpBO5Fc-
OHn1iKd7I~(BEhMtnOp-kVXCHZAHoaX~G+W8TMmH>7Tq-
6zNa;1^p;yVQl&*iK0Y*^e(Jgwg1QGifRDD0f+}s%zorKHRt#k7dc$`$de~$CU>OBlUK^wa*$q_Ez%zmVuH-sk8K**c7Uxj_v2$l
mHe6q#C@2}D8Ik!WAZGE{QHM0oYT~aTU~}z3oV96?qV<Tt`}B%i<*WN*5LoyS5#C85EZ)M{Nn*kqmBZ1UMi{@bvmCc1_G!ZfQ43M
fDqB{CDS<dQEO2pbw&a8<l7GydjqtH{9sWFA=2QjmSQ-
9=3)5DM~m1(QKC)XH%;9cE@}~~baT8IAU_v~S@csAS1}mFj3C_c6r=ICnln-O)n#0{Q#bpI#xLD#?%T&ot7rQ6BDfHr$&g37#c-
0A_TFeQI)o?+@0~2h_uYm}9Oe%eqx3`4a0Ew2)a)j{7)?^ecb_kY6V&+K7mC3o77&E@XNua;(mtfl{cp9!@PXSGF#9`ait!OtjKd
wSm^g$e0pHnE92{M$&kVxvzg|p?7_w)I@dH%v+pc14WEnCs_~{!+P3yLF1f8bcfVOH9N45&7zu#2U=(iZb_{vty%5J60<1%(xV(}
FeEDoUk^=@L{h*pSHf_js=<LVFuhaftXOJEPY>0|FHr*fM<wgt=}#s{|U%r&7X(Z5*|7T(`32?Z4gNctjej8vNh$3M2-
Bf;^Osr~r3if;Nd<ZpL;To&S7At6qYzXZx9&@Msrl2?;&yGmVX+$uTnF~&ExBUkYM)rT{G62*NMusOo<#eJn&m0RMAlKGo9xZ^VM
Tdx&m1^N|;C@7WbU)_no-HpZo$6<$3_LE(2H5L8+5bTFoKi%5RSNjKwy&(vZU;0C7ulZAsZ+8|Ya)SoK(TdXI&>x3L+)^6qDtjTY
7ovMDrQN-V5drC$*pQ{PH;0S-
I4I+wjYD)i(Yqf)`(e+1OUap&md3dg{kYnW;opcc%i%A2;g?6$CGKPMTc%$g34R7wdZFl}e|Mv=^E3FRBZv!~kH#H+@PYf6jeSs*
>BlSmowv6WuNC_D+Il}WqsG<T$zL{x(3q)w68NP<#o(h8Wb)&2KMDL&AlwrDQ%D+o{Nyi3kQ+_?<j?;6bpm~zyYx#4+&c9!4IJm5
A+6!3e}dwTk8MXu^o`-
y$25lgV{C~K&I2A6CyPpiE<cM;6#X%j`Qc7OQH<bJ6d{ev=03m(yezg1;JCyV_}ksK(bV0`HVy}9d3=dMWaoPEWffF6tj3og%hrS
V!>_|9w!=^rBT?>O$`~hZ8JW3w_T0qmh1CCYY)K>EMJ#YxV;MWQ)Nk}{mVSYkIkpr&0DBK$I!r#t%lwgJNljLTli5pIx=Q{rEUEj
d!uweIN0@%9D*Ti+|Cy@rGc29?cHk4+PO#Z;{Ar!74X@+?V+VAb>>o9`5Btb&QiYHlT{xis=;<Z*&CaES9|rxm4rl3aNGzTs>0!T
qGE0Bc?`OkH$pGxf<vmM3InDp8k)^>H?8m0h(!a})y8HUlZ~{hfoyyYBR@1+lUW&?)z+EwG{J_Lq?-
Kpc5H*aCw7<4_DG`DFk!8rzue5$}<P+NtbNOimTW#h?TfVe|(=4tkCzcYkuzwZ~&BAlDsmBtBVgF$`bXb2e%RU%{=U@}VuYE!$(8
v|?nbzTjf3GeL@-V{BC$scx!gseX4f)_HAExQ2hwr>j8f?EG)0E(y{Y!gsnbI&#KeWXBWC#w1FipRXe0PAf-$;z{z1_Z)I1c-
d!=dA;=uiTlN-*YJKlA8L^b<O@LtqP;-zNUwFD)fB*ssk6jAB!_0;G|LiNN@PcqvZ$5yv1+exu<NV+#M<j-
{jq2Z<i_2bK~l>{n6G;K^+*CkE302Lm`(srrB3i>@sCmgr}rbGtvGlefvJ3K%t81S2`u{|R{^g-qbohY!)Ox-
7Gj+*>2ZJ#t6QG8gd}*S2ONZh`9hb!Xw`*WgoJE2=c|CczICoQ02!%uJs>K0P&Y;s4sY+(iOEko@|&9E;{|Ze4bhzncVp4W;a_$D
y=61oY=R79rPe{vqK-Sa#BHANlz0V>uQ*{=0q4?pT!=tMbI=x=jWTydPNJJy7KysPYY<bT|D(#Yd#>WR;k#@+8Z3JBF*c;VO9;rA
DwSQ{7mt7_0Th7RF6oFMJc0cgJcmLncy#SBBI=V42(Zh_vq!@4h*A&iIncODPUMA|8Cia}cGhxK9Gh-A_N_efp8!r%`JB9lTzm+j
aO6{_rFI!zk@CKmA1AT}L13KKh7o6s5c9C#87G`ZVw<_K?k){%ct7>4Z*<L~|H3cfxy{mgxf(kbE}=OO2fR>2u3n-
QeujPZF6E?jBfX;W?_Y@H{>L*s_znGmQi&W(~ZwdD+Q<i$h~7O8o;YxBH-
n{5dpKW8wPkCzspF>)NPBMX8@QuII~bJCQnl*n`xSpB(>`eCgXrmdFF-zA;%MhyKIRGJQe*x+6zV8s9&*>>}mm%=DYbmODA{aG2j
o+Vo#JmYqELvvfR<O~E{$3oLia;E{8t)<3(KUE~+O8Oslmg$ECRbE}d69s6>p3Lcf||0nyhQveq^-
;}euG!V3sFK0i+J&oL;+D4Xh-uP^pEa%BTcP~4;fqrvk8L_E<JG<<5Lx&ri3I|08q;DNuHonZ&aG}q!AmVSgFZ1*VB{1$fR+4_>(
6U<vQ3bzh*wY!4T6}7m{SdT8Is5<hEVCbDS%#80HUHEy``ug=vluD!!KG!6{$#xBLoxdxG5y`(atHltTEt^pX}J9F4}EHj|9R)K(
+%`9GD{7A&M&(-Xy;Ib>2~-JhnL%UpkJ4vsEvLh!NCu-<<&!CiT2v5PszT68>Icq+;?a+yX?FIt}DP_0p*ItUGl!hrccS@s9qr}-
{I?j^!&2(B)Coje-f0Fi~FpqccPzG+yC~l4YAebDBZr=xtl-TFoHQF;2Hsbq$1}y<{SgpG2o9?<ebBtGvGP{{26P`6|$b%j*)*q?
1f*Q#{K3~Gl2ZnNZ)7B7KY_cH*~qd<NgeO)uz1*WbAg4;roI6S6d>m+)ew(>%P66EH*CsVNUO-
W&pXGJNc{bJ~U=3p9Fr@9fD;f?k1i4lfbWDCD~nc3F0w;{8bW*MpHMLr+=OJlmw8!A_3&5W&laL-c2URtv5a;Q`=2;gilNRPm*-
s>i$E%&L#T~`OK8<Kk3c3<PT5VnxWeHMSIZl*40gD2EL22LKUtmJK;w$+=OhQu?rWbr>Cy{KIU}Npo}ax<ADFjax<RVyuvqJ-<-
z*iXhj5Af>JFp#_C^XP(BCgNIuaD;_+O<UP0mthg}1&AZ^<u@w%t;yeereJedAw}+t4$kM)iC;Z($q*w$r&s}1+d70V%y<>&bO1A
!zZ3uHa;V1PgeBkC*V!Lm}<6kWonO*ST_kEWvnn%nfryb}&vgCA=``?@yyS06J6KJW?=FI$f|4LU&syW{U>DN~{f;dQjb%iGg8z`
~T)t&0b-0VXu96^}-
(h5%y51E%g&o;GvrK`D=+g!?Rwv!fkY^9r!bQ59^K^{WvCCE#Ny9r4*G4&ASA*Nn}yz3I@x30K|t&8xP?jfH*kU;oc#MVVDO!tsa
Ac%bPv(nvMDy^B8mY-
O06I(aoGrdASksy)qxrwctSeRZRpGc5M_*~7U(wb>$$oDU4NOyCov}Rh`+$&#l`}x1z_M5Bwa@#Na?3deq`Io=k_M-
!P8yVP7ez^@viftaiQjz$}9g+4gw?#>5%^R?=75Hseh3wy){;o{`n^5+4L3*+8*Nz~3w|X0_babu+eys*D(T%{_k3cJ)_%)ugzDp
jG<uTCsZnYhLeLA%A+;@$qWSF@!`dt!I)3*_R4T1DOy1q-dru2_rq?=JXwbi-
<{b=7h$DgKQ_+#AZs^S>Cz+bs>=h+w^n>m+#XZ#MoGaXQN9-
hNWoxGzVPzVSj&<Kbk2tqm#1^wh5t}Pvq+78cgBu7Oc5zvo7B_NETA9ce-
*X>LPL?<2@NRA(YNDDyVrv*4k0qH=H^0p&yJL7FPd9`-N+ivKRzbk)-??8V$n7<v&-
wx()2lE#b@wT)*+%`TJhm;%L9G?plpd#oeKtiArz#)(zZRbGe?s%MOyX+jF^N^fA1Tq0Z1bqZV5CjPrKoCKr0b=BBPuu<N<8xkG5
&}N~;dZm6Si4#FUIZ~T+DnWEJJa@f=lI+p<?S^640aM;;%BE>lGsW7Oxs0b#CNCdO7}Razx$4cK%qtmGy<aCrcnYx6phF)gpiK2l
iG5u{t{~uTK_O>kvMH5^oke_U_+4F4zT)1Sc}jCWY!`c+D2)+=XY)h5gUTkR%G>8S&RJt?R|T2Q&*bjM|hYRk`Q8uF~(MGBipiNW
FbE!%NNPAgb<QtgQFM-#sq8(F_?hEBY`mYUOoNfmB_M@)JacwPxmC9-hL4tf$p7}-
As2n>FwF+?&;aB>6z`>?iuK0W@=_@t9EO9zwhdv>uVc3z@)nNkFBDL-
}xTD^PTT}=iG;{?v;9SvyAwp90@CZ<mACb&}cnu{7#k;$;r$zVw7?utTaA!A|9$Dwqhb^v|HKuT`VKg_$@3W8>JixD>puLA|9$D{
{PbW{Vt6$?^Wq~X$<1*uTJ2^E7OST#{7gP&gp_3j!Mx@5wD0ls}MN|c?^i05bW?kZroG}4V7T4gw1&I9#P(#xEbEl#A~E?HrnY0t
`VCJ*_^~?BaY2g{LzT=(iu!>hm*u!qTY<uUU(-
rp84bmR|&34b#N}Y*o9dScG!u|N`4Ls&Q8c}kirahxQRh}zW{xBsELNh{zwZ=@K-
D14eNyNNCQL=<wP}zv<QL+5gdv)=)`_m?~OOC;Q;~PO$}R~&?~)O0L=Md%P+*?0Q)m94%`&qoFnYOAsmX^Dn*}kdxkP>s}eRgRS6
n27rWw{4g5M=A-
^!vgsgGtZ3bYb@4xXKXpkFk(g+pEv0g>Y_o^C8o8V%1+*XL8+{?E$qINvm1i#x6FE0Xv^h!@_5x+jdZX;m+$M?j`4PcPo{b@Dur{
^>rYf?3aR?p4ojhC+j!#b#02iA4dRhLi2&6rv<rPe&d5Kyvy8V#2hEX3k7#mzav1*koQ3n@&g)I{hZgSZpZ$Wa<Gsf`?t-
9~xC)wIe+`QZwKwn#>dzy=@eiEE2MFMaOLT!bRk?TX>Uaq0FQNbf<7wa#f6Y*jTb9-
f==rYr8qiR{E$)FR+p5WIOhZe175!;<CV_CoO#og5s;N)Cg)630XjLSQ8$!b*NpZTd7ii+k-5YR3A;T6IIv7Izn+-
VJZ;WGGe;m+mdn;|Esbh_#Gf0Fn9L9qQQ~NP5FawyJS?QG8CrUs~f_j(7}{7<~?r(2wYAkH<NRjKjzrSb-JAU@V5ZV&IDT6&NS5d
ziRX!=1Q^guziM%^0tbSJ1sjsH3;B@~63V0;Pwy-4B&$z#S-
fAfgiSYj7(<W+#Nf1MP9A2E%e9m!}AG>w$|UvqX0ui+gBNJUA(yoO=BK>yE4R;oHuU&bXsk?8090XkIKVL)B1g++jq2`f+gFV-
(IfiunSR3r#8`ac|sF!2AmMIuwPv;(qe;g9!0$Mq#hNm^VkZfl%tl)fnGa%%7lE?KH=|=s0>h?xz^kX5P5JKoJ#4qK^;6U1a7$Pa
gpvg!jZ<1^fmSiCo-8ox3P#A0ZzGjA8J*T*bmBbmyN@ISR|sk#QC9WF6ie50GB~FJs~XG7Df7Dl5tH;vS|8=f?vD68e@VZYP-?-
dGs769*RZGfWm*6}J~iD2QjnMyX^4hZ5tfaW~oFp}@w1^D>9fl6V`LwLz>g-
bTtc>egMLI27<!bif44TA?rARv@8oKNq)>%!;wgGc0Q2)&eFf;H&9)f#>>0X}$4}Dzjcc%aeaZ?J1lg&n?Pe&c(fiym(2b4CZLuO
UR3ZQF)$3M-28JMr=$dDhQzD-FobsKaBQ6ehQWj{3A;+MB!PKJF!*ffar2kk<nlYRw~Beq14J%xEgB}Nj;P(tgl=Yd6|7|A(jSOZ
G&(JmK>UGgU}OLkcvYAZ$gK$T};bwz&e!B)kEq!<j>&*TyQDX_bAS+aM)GM>uGj3s*J?L(`t@H;ip&_n8bil*oM{b#)=Yhw^1qr#
rz>^S*JPfMMqU!ikX)MNFp)|z@G!lwSg_M@OI2K-+&^qh0P!?898UTWZI4VR(G-
BkF?`%ta8L9BTtfnvQvSg*z$M>`E`JJJl;WO9aB?jU@I6MI|}%<sKcmbD;#)7frNMw&&skPYbm@6^tW#fWObak#QlXhPksn4i~B2
a3&VZjAf7Wyo0+%=Pb2I6g`x$;Sx$%@#q&$)s1j_T<BJ8+wP)f!l3|Mb<8DH3@^cZw6Wl#<H`$@=Ddu~1Vcb(FQUyi!v!1X|Cm|;
+C1pNsax3s)j3N$#JL48Y7SQ7%R~SIirKO0FmxHgo7WWduHSuiROJ-hTW0BzTu2OJ&3wZ-Au4XSp9dzDwicS*G#ces_SwwAkrh^n
V`0hy-
B)<y>h+W|U)XhReGCADf(YUivETJ=jVwSe=_A`&jDuv~cl87~=bx`Vn1sB}GQYUPpH07i0VirSR*0WKEUS*k(CPa$m1sZ<^CFh8e
!*h7V2|t0T4Ra{$i_kZjDVvpasLG--R^k{3i<AT$!sH;r<-
I_OX(vnKH{dEghv@p^s<=r94fK2pY}So|`V?H;6gRDdhIL?D2b<T0wbOKgxM>YEtO45^*t|w8Q|tIYa>mVtV3R(;<t+@AMU;;Mdf
`n2Ue3}9zq1m&m1CgRed*}je!=#*IS*`k;LHPWp14x2<G;ExZlw=ofm;K9P1qM<PXK}+&aaMJ<<CHXzY054>E2sBx1YEnZp{ZrKD
hJ2pC8Ot>-cnIoMT^7X)_FWvhQd^Tai!{QN4>dSfOelCASWo>%g-
P+SVbZO2>cwmAL9v)4dVZ%ccLgFm5x#X6XZu+l@E`l`g$`PPbT2+*Saa3&2|d+Y6?t_>sL=vviSvvBXs$y^~INr#|eqAkLM6y$qa
X;3*s4p)#yf+XWw0HSlb5PD1`lD`nIsCspW(s9wW*d4F8>Ar7%~PQy@sT=j)-
o>S}iJoR@#TITM}tLB)l`tN7v9>M6V>Xd~2YQt00hPp-FI38C%Bk#!#mPDp~9VR{}iD;eMFZ!?At64enU!Y!qto^Bjahr6xEEjs^
FjYyoOI5VPOXKYIxS3TT4f*TaX?aMOnDo&_uWp!h;V#wknzY8*S3uB_MUgIv+vQ7t@Kixt6*}6{QB~7lI~vctjd!ylQ?$}|2FB<r
g}Rfz;|tr#(SeSt^1P1wsr<#<F=EZUR<=PBR%Je;3+;yCDHY%Ws;eD-
P<xdg1>^XemGO3iP)5hzC2>C?Jbo^SdkJ|7xe2*pa3uGt^!t%)y3?IJ9p6>Smqm8LpLN8$w1~Rk*B$ZQIz+qSZs%3@E4y6~h<8=t
MMf7~K6#Z|`>C~`wRTf$H~f=7zMok3!*5T=yL1xY<rl81f1X#Axf}lLm*Q=7VbO*c7Hv7A5y6GCh(e1Ir5DHBa)qUcLakTjpXzNJ
S`f#*rVNGR%S`?HA%+A!(Huo|xf4-v5u)?uOgrYghi`zP^wU?RoARUev)Klh-
@{Yk4V7J$UjXg?>Ix>LZfCi?#?U)iie1NSyUWWN`kLY)<X|xTDZ1=hW|3YsO>x~L8&TU;>5mFSUM6|_d4@(8%-fk!$<$-_uv4-
eEVzp2S<5P6nc*u+`o;>;W&Ks@?-
;_uxq8TBXym2YJzQF?jA8jz=`SH)s9_Sm=BoV5pTc{UfCyK2^?Bp%YlYQV{INjB7%xv`eb^q~^)!DPOZ*R4T%Go8=UR9VOEKF9Sv
l~534XV5iKDmw*vrTHe?)~l^kWz|6lv;;G}fY|Ey|u+8H4eST8%}k*`!4&`ynk#D|MQUI!(P!W7WN_iDsU^s+T>gsx&oK8cWsNwk
UhD2Bijrrp}<T8Z?^>=%Ku)TVgX-YRr`yt`hrTxA90?rZJakxH65s>`GZw^}_72Q}59umAUi~0&b4k@{^%O(sKw!;{V7WucL3%j6
qbo5fJ&0+V`?nL)L2g+kQU%ZGS(Kb6}QUEpO*0G-
`4_d)!z7X6YsJ_6oj2t$RIZ+#r3##Y!*#zt|O3y>5K8Y@9t(1e`Sm%GlBM(y?*rX(#H^%DrKWDmUP)aPie~_5%%Qu)Wz8Rc>K4z}
UfY_Fx}|iv6iLN7s)VBq!-
5^w^&&mP?)E#wIY!uY`ZYrXItkC&p`BV3l8U{v}&f^=|K>r^lVEqAQ|K;2YkfL(fX_FHdKkpr?M8ox_|BfO!D80dNk0^zi8=6*D_
1tbdQ@Wa%mTC0pj_d$4Q`c#h&GjB~V7deqZn!!2a~Uo~gxrk=9I-
6}Bs@n?A#;=k+7YX9~&`L*heGak9T*W=GiVA;w!AAddt*XhAa8$EdWgAMe|OZ&mYNB15%_-
)&S)*!SFYGKkaQDQ<=La4kRQ8~QcGf{EQFjxV?VHxmeCn`9;H`A!EAls^Dw5=kf^+-
&Yj!tN|NhsPnQPLrC@+&5^J(BEusCA!0aAWC&ww1u!OD9SKr_d;gU?+h)y%So?5mK$3(3%*iB5>i@gf>84f9OVTGA8$3%zZZjQgz
8d`vMu0YClQBDCs82AC+Mj`-wS!LR-gxiGgYY0)OUuR=scoCN@+Gn!ybqh@}%1Rf2;u@_#5aglKl5bE2#kVHpUMwG$Oq$>2{{U(a
fWtSVZ<R{7VdS(bn4oX}Sxmmc`P<0iC5DJ6o~JfW?X;D_t3({sZXm@roHFAN$X^evb$84;S`SN7}lB%zJ}MeRgcmGBt$$A6MHQDH
!c0SR3bdLu%l{@3b>4JL#efdBc138Mv}5#Bs{J<An*r(r^0FO;E`@J;W8o|E9<cUO|tDYO!P-Z@dzgs=wQt)W<`K6){-
zh6l7y=eVQA5}^(X7iU#R4Kh!DL<~6DCZ<J(s!NK7d_ujORSfc*o5(%(1YaX&t0b<JT$|E!E%byvux*qK?6jtbWIpe2)hvm#~LP#
M=&TO@IoaOZC0oJ>)46HX3;Q6Kl*)bqSS-16wa4j&n&c`mQNJ6$l50-O4<>Yz^^RVm6aFSF;UVfNr(K`*>lb~Hj4-
}0hhb6ti`7=jo&w4mzE;`LDxi86Kbn~=a*e)Pn=B{-6%7{|IWUyUVq5cEHV8_>-
BrAzoi<uM(+WT*5B_IKJM*5scG##w(sTR#}D=&`Ja#|@djcgF!oBK<eULPxBNf9mw`SR2peVa)~-
ZJ2RYr)B}z^}^?t%o4Ig8(Z71R%XcHv?0&gSOL4g13C5e)*J*0akQPR!8Ap$oL93ddSZ@-pRH1yYbiRz}Uv1<4$-
8H&R+yV(BXOGdVe-j3iJ!XK{tqG%rBoqF`##(!9BgB@=HWN?FHj}$$8&qX%uDE5JM5Sy)lIb>yR>s3@h*`2h<BZMZ>Y4Fi7;-
$F%*MiOma}*snKNc2oEh`7SuyKb%zY0M^Jduw(=sC-
CFUy&=8k!_Y=bH}=4Gs}<1C&9bLJUUbLII8n^O#9M$DK5Ip)fl@hE*I23X9yuVv-oNsF|@<wC+#))h0s7poHGwSibUgbyWbRhF0y
;wKUnhCmDtB6$gKttIA#q$^=HSYlR)EJ^6=12H`eTM{K6D&_Ne317V>=7WpcM7fE0lDdS=L_C*QCn_w&gBkH!i02J-
H<Ej@Il&nlV;p>;G*NCPulUY{&q_SlMM*0$U(8Nan8^LjY?*K}kkE7F{?;oAZ#@ydsg;BOLTAEiqzJ!=om$BYZG0RNhE^v^+KCWj
&IEtelPGtQmzbR>al2_Xt-nTxdpF=lnlRLZ$>78kt~J5P_Jj?yXoH)EgctMbg-
e=*(dfjyzTckU>g_m&uNV`CTC#t?1;=2=F5j$7Y($%l@S$IJkMBtsEM)Uj2j-M`M)oF*CgS<)6A8`=28n8s0sh-@oG$W>n-
e}8vHfWOHM-`M{w2ItFja0v|5YX!eIjA2C3gN&DJn>MKA(xcqM0qSGtpWm`r6uAR&PH(OY}!eXFC4&(6uZR9;6c9W~g?PYFRZ1-
!4d0V^vf`=)5^my$yU`+M4jvIr{B=*Rm?*y9sy_mW_v;gtr4q&N<OF2Y19o^|@k`yAI9QnBd}?YxJn`PMixDB`xx&)`a&2Wi9y2O
;{c$X@{*#lswNsF9QPv#B$ojrC&5k$E5J-M7666sYf-qgLk3DZ!`(Lr3*{p?G}u)7gZOJUdtS!hRPGwUNZgx8VAVuh6YQj3rp(fd
lS{qlj<#;qhb!{NYEur2uuW2l2z5)%28NX4g6<V{y!~Qb4_(z#w0^^ALyIAG6yhvGkoE-tme#1f1Xe1tL&K1#F7U9@%=IohkE6S`
R4J2-i8(BMClSdN*+$=t%QGAj%$~|cedkdCd=f`gx*AwpKeO%4Fo=DPv|QNyla%_X=GbMuO-PhbqT$OKp49;QJ2B>3B8WM<*bChh
(HKyB9}n4KB3Pm*RRM&yj~A)yoQw#J38$LQvU^R&=Z1Q_+c}iC*;{*?(09U*`m>FdJi7x)$H$o`Gvl2&9Uz8{dl%F=`n>3Lmr46o
%C=bed7olB22n!VaQFuZGj;d0ylgE8=PSC7)c}8CVjPJi(o67_y~A77}|=!1Mk`-
Iv=C+*OCbWAKKDic6~(WLzAsWS>vfCXSqkuRF5KLdX$5b=$vv;PBL+#3B8)vDLL0>G?N}n#>oS35~bMX;v_-Wq|+#wbfL3m(p@iX
M6qvjO9O%}2(}s#Y(?O%kyPJ6QN2L1;gA~yiq=L(8OfF!1X~ce$tDvrqukmcGx><phoF@xTZz(7Mt;&Y$U3FpEj3akXe4vmD7Z{7
O257u7D*;H?00KDBVa>u8|6q`MCp<#=L&9XjU+)MUp*5sqb){8sU$@S&PBnw5HwS8%?KP6oP#9wk_3Zu)k_heTLVk@Y)U5?IVs)-
X3a+6AtMi5B#}t{V&&F|R1RH}-
g*RH7=HhW8(BsHr`u}`Ek=RxY4N0oAXe!wj!gOq`a!rha07SwANIoy&r#SMfCYG|2sZK0@+V!UkOsRIG?Pw)*oBes|8>EQtjB-
*)SX3*aASe#Z#;JvH6gI^f7^1$WJP4*-#K{4Ml$YyH6ROu%J0=?tsG9Z-
&w(73(tbM=Apeq9GpKe>1ZB2fq5C}xzjGW2ro@KN#um{&rQ0UM{GE*Xw@ArIo4lRD;>?j19wUsC~pcsffVOEChg55^+R^Jkdx`wa
Q-{yJGm65HCi<3sgKm-uzzK}lS@6-)53_Dkp5SX+_9071<0ljZT|D483G-
xuV^`rfBdx@%PerGgo8<|?pn)`75FVui=!3?yhmy^Qmc{aHt9a>9ohs!uIz^`^m}!hABR2NXul!-
Ttxn%2>wSu5yAiHw;}kS>Q^C`bF(U=SC`*uwqST(m~^y<p3fwqH~i?Gb{fX>;)|FKzA`fetN7dE%q^7pZk}|}4d;E6p4E|^ID9Pv
(T3ncKcdi6h`zl0hV;wTcj`#@8cHs=A_}fV^f$RT=&G;d;vS}ZH~U5wN7r?4;ufkshLTH%a5LlUGmYVZ2V%LhW^nnW+cZ?>E)hF$
E>^g)clT;x36?D^<9I6Tp|g|D+Tb%zt+*U#K4O(3@rWm>@$955{^O2Gw^nRM^O09@VuQVME8LC*XP8dx#)2N*;VLP`ISsCL!QlEy
M{T6dp%r^EX^~O~3>Qy2v_TWL#`oXAtL<e~UkOkruV5$IN#|-|8!dvzF{GIH2K{{35;{ftd=fw6#8Z|@he-
@LO3)D5>XFqmDYpjKPIC3py<Dkq6z6`_&q46HNo*a*R`8KYZZ-cBA|aQdv15~5j<5)k?*{!sm~Ka{fMxk_b<*9c8P~##I^iZ>fM=
WFL#OH(M+dn+yeyu6jJv|=qMBh2Mr>C&z1WIKFkG=15Lw`xhAUQsxMCP<_2?D54w0P@+O0sluOrei4+r@=$iq&^PBP9QX)`RX$U@
9I#%v~JCYe<)X}^d_7c?LeS6ngc5t-rL)+?LzA`EZBgB7s=YQF_n8V!PNxDgMg7!@Kre47wz?UJ3I*-iO6$k#zKyFv0m-
$tFpg1%Or<RK~^WT#j7RQ)1qB$?bB%Ib)vj`%EkMD&y4D~)<)XCV&@*~u&@Gn20wUI)r#7iMVq=7yVDIhi}rANIpdW$V2Qwo7ZCx
5CW@TDVeC88cTDiYJFFU}EuI+-q+xs7=9L+z@XrsJgrr#jzT6z*Z3%{{m0~cb7J!zyeqFm1v7w;LQcPn=q`0y&2O2#Z-
ScrvU|4xT2FxiQj;xI)IF637P(7`&}&Lo47q8V<oyJ+wZQR2r4C3Pz8{B>}FQwjpJzZ#g%tY$=p@cSrrT~zuQY47~frkmftvV_ly
+TSJ$BR&9w@No~-q7bLrgyxl=jVSl8Wl@~HYo4N|^qks};-
A@|pcZ(<%ZlAJe#y|`W9HQC`xZP~S!;ac31rIwjmX56l&RvoqKn9fr6VJ}XakSqIP3;kZ5=EvQo?fT{eY}d<&e%6=CgAvD}`@@$q
b66HUivxPIFEf$(7yOyXm#@CR&075?fk5U4x3uAY*L#Jl{E`i;Yi#9BX$zg~k+#bp9=T#Ag%y5kyD4pJ?*^`zt76`p(jN9j6OQf|
O*cPtmsxWN-p}$tb~F4)kGsse)`PFSa&X_?fqu>Qfnx`c95{~Kjq^l*-^&9B`;WYFcUQ8mN+=t_93M*7X@sSSA_K{~e7*uvxH-
v@mV?l#Bu82<qm}H!eMtvtaRXh??953AnK>X-j}H6^6uFXIzT`P{Jn1AW+@_PxJYgRKo=ZB(-
U;FCq$6MP%s+?r!A`~+eU|keY)(4!B?m+@?}d|0D{N&l)LIBxAhI-RAr=coY0+e41I!LR?D_nL5!_I?q@C>SWalE}0=_3{Cl5OX<
s#$)6C)PgN&48-2z~E~xrPRqgHVFRifg{)s!h^|r!o$1a&SwckbN3QP0~#iZgRA1_~R(r!nlytozDkQd11}H%-
s2s=%OiEQ^o6RGzUj&U}X(NUSXQio}`t!!42=Jq?HJ)5I&r&$tTO<B}xjOVdIE2C$0GzvrguU36dwCe}R!;6!OfQSg=Di%pr7?nF
SR(a>(cF&|z#B(|VZ_%?yMLQz8O<6N2bK(m=EZ2yRLmG?G==G-
W1NXS9%2cBBO3;LGbY=SJvR&pPVbs_Bu8<zCMBFk|tFY0E%DB9?ca*g8UIgRCUAC<>Wn(ae<*+0W>PDi~cbz-mqj@nW}1Da$0p@2
6hP$^ew*rDqPA<#kxiHfm(E611|p2%k~L@FK1`aZ_f^$!y5$tm4-r(L$0h=7`p*p@r#Xt1);iN#CiOHg<6t8?u<i21TCv8BbYq-
lIwklPzS6k>5FcF%GpU>!??$zX4?-A7IN8Csel6u~nH_1cy-MW#u=#pDi*|(w!qNM{r76Gq15V8S*FHdBM#nn_7WU7waACP+mBQW
M15E*c#u&WK(4wJEg3WRjjOW3~c>wqM~oWyoxQV%~Ot(52$ueIZ~yt#T`ldiWMz7j=6@qnFDSNQ`@H;vMK4w=hu#SK(r-
2<bW3rN&2+aG!AXjLlmCO3g!=>NSXZ0)%Q|*@+Hymzq2Iu&AfL+55av&Q!OGB2<=HThsaE5gB#cP1_+)`)>;tNf^aOkfjl-qs3lo
T9<?CmB^$`2flxJhR6}TAvYtHZL3lQ~!NAuNOJ1^8iwIdxB=zNp^bkIjG!UPG`09wSj##Y3XC-
7LJ|pp&i4UVHO&W;LKzwz?S4Vss%B4Ock0g!6XCyvztuzi~;fRkTWFkHj@ih=%1MsJlM&dIPpPBf~#Ahg%`Uo9Qnwq7&AYVf*8>N
l-Y#^>p*1Dy<gkDHC5+7ceZcUnq&qRC;#MeN4#&W5TNN2K!_-
csHTFXXhCq6sz)e&DE@o~h5i*{YIhWKiT&q{n&;xm;?eMFZh>zbvkAs<)EM(H3v2l1KRQr3{qMtnBtPu3Zvq#+$gbR5yuluKPiEl
G2;lr*HX)n*2nmvj=Hljs`UQqqvFiRhZZo-
`YzoFSc!=xjt+S1xrC?Pc|abaH(mom^i?C)XF!$@TSAQg4t71L;g!X^2Q?E|<E9J*^a<Pbt2&a~0p(4TgNIKR)l?l^1g=mFH6`Z|
xkFci3R?U;ushF1px4rRaQ0(XE}M=r$P*r!ZRX-t{(At<;-OskgOCz2zzOHZWh6g-
@|+6b(wf`ILHFtJGVbQg5zgV>w@p9zvs1Z#}HaBBiVv#SQb;Tb@#Hxk--rIO1ak*OP24R{AL4iCy4vNG?kxp0D!qSmgx|C2d4(BN
A46JxQ)u>8xBw(QRM_ip2L-
gTaPm6A?EN2`j>$q^(%#tlUn~?PjHl#Pe;1Ygsi0A4}E}aV?Rst*|HARIGG{5#vs{jP006Jl~$UmQ|*>Cs|L#^+dw<#GYhrvC<h5
Z-B6wZJkIw-
{!cM)u~ubE3TLdvr*X`dy@6VN@th~JY_q;_E03guU%4Hm~0^81|nhg+mkdGE1k)^WYL4xFCJy?Rlg0zQg65qvHCSA_3KmWckS%@#
iPtT^&11FYz<1;`joO=JG*T0C^Jvl#;TNRH7M2UQ>t~XQmuKcTJb0|PqoILSBlhde_JLVW#%c;L8Ug|XkaxL-
N7pD;z5;6E|U0{UwVI;Mfd|3rspt5&Oe&8A+Ql}B5<lCOYg(x(R<o7SelJ!)?lHg9p!ccE(9)>1TP;E%y0APJ#88qklzIj4b*Hxc
@u%n2sQ(sJtb*C@US+*r>>;i#IGKq-
}59LgdBuygs@z4lU71__4Xg|=;XH370{xj!)>E;z(q+9N<0LtD6!6v%xQctcRO>pp(On4mG8^%ANlik^_>yv>A$b)lE!t1aG?tNq
#1#k_FJRwByCD7lV${F0-TQS9tb_MMA$piD~Q)tsH)2tpQN?8GU-
4s2YF>A=v9Ztb>zh%zzdbEWDTln$k>X&O2Cd@cJj(d(5nWGYskxr0IycpCJm@Ekg?LK6}_zFm64#A0gVmhmFW~Ce3)@P{V?MS9)F
l|i2-
?BPrsjetIMkoFg#4<Lkv$m^!uAOoPdXzwuc*6aMMFgTgAU=+8%6NwGT5c!S^uZ64yM;xP(0qI<7WaW{du9<68K>^pN8d_c^>anzl
s`I=nV2$3+h_ZJ3nb+q4M{4>fHs{r;v+eBfPw-$TvU!;Nd-{Nr-HpZSf6=JQ@{k3Hz{mXoCW0fraqd4Smp9(mAF<ddYEjbicp(!<
4%efD7R!t4IW@Ic4o^MUu}AL7iMqp!8Sul|e6vR1f7e{pGnkG8<?7Oryjy*$uOf7CsF?BKq=eVUU8kL*8w;e#!=vaJ8>wUkF2TtD
i8^M_KN+EBMgE3{yXf6fDA{V8vKxXWA0Zy)u7X!OG9s+7+X+370}W{vuQ@ASdzPo#Y1p>AybnI+{djo8pKbO!yR8xaK`XR=^J%5O
oLA3~3&{N*U~LvTr|%{uHGZ3F&Ls!bPdMRc)*p%0cTc4wJyc#$Goh`uOmgD|ApZLhWIP}~Ngrgj)PmXce8`%-NfZd>^dQY~)-
Z>p_CD8xq0k518N+x4M}(RSeT+ToHl)vgaau@!XQ$|`tcqTrL|R!Dhk`4=#J{>7A^L*xfu|B2Pf=cTs0u(=(?MX5jw|J)~FTQ(Yi
k(QKK%X`S7Amy(>gbqEa?bV33gOHc<Y835y8pam_58$9f<%efeK63DpsEr)j$f2Da+F__l3ff0O`zYu(3c5`Rx}Ab<r=UAn&>b+m
dOk{w!KYEQ7(*Kc{a_9sSyFy&W^4ti?G@74&>=t$0T@0Y1?{iR<o8f&J13=<ucDyWqyiLl0GD8D2Mc-
!4DOzf5@Yad6fMTEor1nEhaVTE+O(M=6{OlLq#>bQ2ibMN*aj)qw%SZuUre=gQbt*VJ1Eu;O7Jcg>n@0`pN|r|Zqq2*^?VU(zi{M
1JV^Va0oCwkd7OW3T8ifhdp8SvH$)E4M>#FUQ(-
@#$H%8t0}WJ2bAcW^$YTdwGEd9)p;UmAN`Y0z4hnk*RYoTZyA#5u`6#F5F0g(PD!<^lKL_#Gfm>O%e5g3(DG9o9j~qFg@|eOaJtg
8}v|~1SK(MAfg+ev9hL)#%^`S?6rD6xJ1g8&#157o%7Pl_(c$-
e>rEO_R8$>!%9%JmRr`Un&$YPJQPw^X2JDi1EUogvGE}WvgA$<YwM<g0OF#04-<5|pe8D=ts+huXassvYfW6Eb5v|-
mLQofQX#V~e^p+9*9r^$_$iB>9!M>362K2DDW3jHwVmrcTzvh-3XWvPQAW`-
9w;?xKYQ({cilcV&d6}Z^KtdRi4gc3~*@&8bk@|T2jkz=?g<u^t1{Ut&P4Qs%UWA_&Zwb&TTW=4`|5rT0oB4L0A`J>)cdpQmKiaF
J8*^$A~<*D{!0%C4ETyUjkNK-{JxN|1eRvN0uP|oj7wbe(SX)6`!upq2ygJ5&2tw?yDbT2R~oR1<2yjzc)fJJf&Ss(!6R%C?0de-
*J&CX17<TZ>90-
UganwR(9PScw!Xz}z)lJx;7oo;i%n3|6<sJV9!yEDzVJ5vE&=+vlW7$^~Jh@$<efHiVFpbPG#`Y*r@*NQrk!`5gMv(L!3Ao?O6C3
XByaMHCAH)dw&Wh{o+**2{M8<E9Q&NRVhIgJ?`MRd`HND}dXTas!o#j0qB7zSM=q0tSg_IjZ~mV23a4)6$qfQ(BJV}CO}-
+G22aboW+={IrwsZUIHNVVkhOGaDZaojw<tR+D!30gCPQWE${;8$6wTrR9j`He#wRL6Qhndz;Y>0LR)`;DhkZ6@@_n(LqCoj=pNa
EABfBbcNSs*<ZO-unFB9j+PrS>LjPf9jwAfugFZ?*KRB=_db^nv`c<$bj1yE;f%Y_OfSPunSv4>n-
VLw8Oiw5p<BzGl>4UFy$!@)sT4(ZheD|o?>AIw!|kraIuYa`PllG%3IR!^Cx@od?T^lXY%3Z745`rOzcGz^7&u{Plrl^20Gb@J$_
629sRojT&!QB(?32ma4YL^SeAF8Amzysf#O;E$qEiqp8N|1o}BQ~jAXf;e;m<hKW3GG22FYD{qoXVGk+7X@&??_aznNeKHf~{)sD
Ws#||Fp9>7!UlY5UHR?e$$XW7Q8)0{TiJ;p(_G0oKuxi~GKg{{aI4hB7GTYY4wtyJh4vw?8V2HrHM5uB(V>`vP);Uar^@Yyjtifu
)FHUeS24Uz}aPU|R)IpOM>w5>GSioU^KWE!*)%NdfrL^4y_VL_P#ct_e%j&=@+>_Featxlcr2>OQ?I$^jV?dHN=?uyXjF*k^7-
Ed)dT5f%P1M?G(Gp-AL#9%{j(VTYT89JiSKI9m-
yDOHXQ?%KQXVqyBo>hDF;fgU2<Y5jsq_N?|1|KWDjc3)rDoNW)cp5hENjr3i9E3I-
5N(Fok=t0VX`2bd#37ZY9acmRLYtcrZ3ba~+T(fk_JVv&CLUx@%*V#prfr3awqyk=Q!n11!^b^oJK5Pu>m)lTAvf8%VMr^5X{Rvl
6r9s4<rR^e!gS+xW7^BY^ul1{d~DdOy-?D=^~n9%VRViXC3amVc2C+vc9@iYDLRKqNu4#5y3(|VqVrG^TUc~05L-
MS8}{lbRJ0{KQTc@<59sjm3u$MGG8$cGG@i7V9Oy@KQoK%+l0$1IhoxyR#p|Vb{VZNTM11qHVfW5LMT_0LDc<{ccnOsl@8%L^Sh~
!xJn0s4Xo2&4q<A-*l&o4aSuIVsP`oWP`)w><JORp?j}5!uT&QTVdpxc5rQ33X+2}g<^aHp`+K==&24#f0%m_VcKY94!yiE$-
ZBi0!%_O)q?WfTFl<Ms)^z9IQem*wr-(4ta-
?ZGH9siw2)7x_*wMeafXu#(oxO7}C5>F!d&h|7%A`V6O2ZEglE}T}2!j9Wnmg5h=p#U)l!SKK=-
SF1gqJ~+b@GEJDHq^=$_u|3<4r0Evqc)Pq8Tkr_Hn@~llRK?wy=jL=s3ze84#pmv?y4w53y@>zF^9IDjsW`|Ff@>MT0&1d%f(*W$
6K7xiMIR(RG)u5EsMQrXR!ogTW}>tI^DWpKTh3gcSf^dj9$8&cGeEnI<@@M*oxSlcx{n(YNH+4`iHe?XHM`XM6csEkrTEe`L~J@M
Ky@D2*hOwhL<1;RUrDtt7*sTSQjD#f*{4pm*EBzb<^(ULYe50Wu~ELaO0_@(d0X5oQ3>;Y?##Sd@+LXDn_6fg`S*d^%99XnP_xL+
EyG|iW|QvZ6lElt!z0V4}wE!n=!m!RtraFm`Fg#X6|^vE|5SB-ExBa5k+d%_97kFE;nP2P~=3BGbf})fca2~!Yxb`q9g7ghuIY<y
RoHeGocc}A)E`bQ`U#_(@xE+w3qF6LhCHbLyQNfQX>OLVNfF_5vMInvcWt*<|q+;C=I^okZdu9&KY^GqdYI5Jl9XlbImj>A_*0sG
TbcBR7@}HLK_hbc98i#M3=Xdj1JP{y0n|j+-
T;`3GGAhlLcw_>d*n&LNFJl;4Y8kj!EzA3iY4{OA60nUP?Rb!EK4zBm?oWj6raj^dD|)&LVIZ3(sf7=U<r4GgF`JLf)Yz$Q#1#t6
c0rbQxuq&?9oon|2qAr3k8J+>wbm<7Ge~*l3r1Ev<GSAg(~fcari2G>Z{>^LgChbI0htk+_!=5Unx@;z`tMv5F4u%kW_1%-
AVvp>mc3o<(cXCwvSW(Z^)s@H9J&jb0pwx@a#VudE9fU=KqcJk~74R-
`+l5x0zG7;$JG9GYjfkWGgoPVFw%%0{8>lJ0hv?)*8FhYGN1N_%KZJ@8{ML)!ZU;cf(PRAPOiC{xT5h!v<sC-DEjI6YG$?8QSrZl
8z@c$k-
vmyY*d1Vcr5(h;)B1|$~Dv~>KLhG@VBmC2M|0<==17FwVk(_&gfzQa2SmJqvTR>TCv?X>lNMSq(vLXG^XPrEogSHr71Ed0kmrAtf
_I7#5l2uexNOoC>Wg~}y{r}<SwwB#-{eLB-yr}BO@?KUn(;m}$vxXCAHc0Gy_8-
{4Z7<SL%$)6ELus`joMPr<r6*Gx0m0?FCE3lK>&fA~km8tk)Te>d)>=-
@Rn6@IIABv^9{4;m}9W$ou%J}7|3l^oVgsdR0NpofVGSrH5JMs<bx?HBpWvbkjs0!^#*Ar7caW)caB+gC5xrsRIk*b~?8xb^;<0j
<XbPvw($+VdW%tXZzqCZHdZA4`wDl;<B<9is@*)jT|T-
t_IHlnJ}WxeE5FA;CrLIf6~+C*p*QQ3*gPE;0Tu#o*G1e=J;j#PG{GUu{ha;X=jdg!ECa#=6A)Jyb*&n;JxXFk7No%q~x6>9q2au
wP8x#dc#)qD!?#m_Bi)Lrft><&3Uuk3|Se{R{MUUC;;FK@sDENbx|UAG_nw$?wbmhN6%C`fZfp=T)4ZE4Oh3W(03DA+}dXax>qxR
c8d)nIGrFb;M<h9Q~r;l*h?ole{FFnwFPnI%@I?X)@C;b%|b<$kc&zD8`u*2UJej6{tcexbQ7-
OS?uDqFsTmF8B8)UUAg(^EFFD$V7M9OYJqmu5tkO?)4s(I-
EpTUcnzQ&C)AdVA(AtVb3~H?E|YGHUD^Z+8#fy=p#q>_GRIKj`|v1n*_9gshgBS9vF3_()X+)Kq|_f<LUh8gQhWq2Q`<rWbcB`d^
<MH&j4f1z0P@UCK)XV=dzb4(jOjgprd>FAOO9p=TM2Y@G5hQS`srIbKl#Mp9s3>=lNwtnmsCj70o~O_4@g6<h3qN&kN7xV{2R^y)
?AWiLpKf%4|W!KI2mZ%SXlP_%T)KVQ-RCP&GEuusWB<fM|rp(m9b<th5;Du!Z)sT@`)`k$<x%0Y#a17VMn!_l65<S^L7&}h+=|Dv
fEH%^tpQY?klN-1nRc%WBZ3qLZ!``Jez%X{9E+$ep0ev^(rJi=bj89kQVD7}VqlQp)K>BZfOKDJA-tW^BPt&0BF&SZ@atU9pkgn<
$EddTR>WQ`T9R<K(KpJaNmMA65VDd?=?FXk!we_ok1SfP$6hVl$Ls3Q~PXQPiA85*Pq)-
rmGN~y5DNuv(TI^c+vy>>EGlr&nwOt0J=E>`sUiaxS{p`j&;KlaL`|5&HwYNS%hMTL@!&_RZVo>y`u>{ImbA5q4dtqk?@MkQ4nXK
P<Sb`O^<1|}Up(&OwlLzYMNW=g7ub#gs4v8~~`-
h;=Fb|2HUYqn}yu`E8Sfm_+jA<O;os+2<;7{yETS5i)0$ta%IZus5e#Xe{IHanyowOyzZT2fAH7pjEADR+I>s2d`$sl5WI8ana2#
Y@_E_?rCNXSwk`Gp&UKGSS~Xu2y-
;c>QO0AIq8<^rfXUyWr2x9gxr`6Gfk!>2{HuDY<!KR`e(CBSX7qdJUJ(lOgA<S$IJv`qfccHPrIiz4G3f>AaXVE5Rq{Nem;3)~MZ
{nw4P>O1{i&F7(Wb%rC2gkI!WO?yRAPkKD&h1#N0K)2x7+$=LMK7A)(Q>FeP+Tn`1xdSLtG%mwjr4cyKikQM|U&wY3RkLZ<ArR}B
w9nx2&U6#O@3&ibdM{R)aY+2H7Yk+P6ES0^4jcHf;R<s!@n;I4KUyc6N_LB9eE|X0kMI0KKNf&)7?a<O)7yiYxTjxW`#kFdQ6(zT
xQg@k;Ji?g=h**45c7J_?n#V`R`q`n+CNi_3@15y?@#&e#xY;(-Ca9ei>*_hX;1A4nA9-
$8h|%Ub{iCh2+v|H|aJyP&9I2W+XHU#bFn@Mt7Kck_PL$YvKgm<-W)qu*0(ED3Xnfs0GqT95bB-
`vDG%&&4+F(A;b7l=1jO%9cfW{Kc{24_t~|2fs~>O1MPj74FDlCmzC))Uu4DbLbRW?)9ou{SxW>`<^6>#&THYW1#&;`o%V4l(0lm
g~Wc=BW8gPZKrjL_<(rkg0Rr~iaYK8BYry2+~z&ll`M(w4J(MEt<@+Z?#@Q&ryGB<p3ssU0B(($lKCvHHS@AWoF$HFGy<K`5n{ek
C}>P2{?cq)DF6R-i>7OG-z>C~su^8~*QgTFm9_>UWK{D&y`Py3o7-H0LMmDcym(=-
gcJb4FC=rMRaXNTKz@F;l4avOvH)a!sWM&76c2L_Ke-|NN58|h037<_sY27g-
>JYFM>p2O<^U`d}9d<zD@#?jr^cM$h8M}Hq4>kl01*Vy;%>pn7Y{G)%~alv>L%twJc%4hTJB<A9_3pGc<dKBy=Ro>@4#p<V52+{Z
3yN}O7dr><8`T;Nw@HqneO5H{G#qt3#3_uM@l~3<Y(VijNsW*jef4NW7+J9s~(|)Y`aDQL_&%gHgdB6AMANXPC`BwbD6?Vw&UD!T
>?OoVDq0;Z1VXxLRd(uBS^`4}&sx##+0gA#-
FE8mo+S~n~e&!!{xWMBAziUVnbx1EL_d{ssxT6|8)!?s=opI>EqXWM#TTw@R42e18P8WDx&_?dkr!t_8+@00nt%kN~?o1udX70fw
<1QEYT(FJYUGySO*aoKYZ8^bp(QUv#I_|0lUo~t)9;XhxI%q>4W*0ui7%>bt4FTGTNBYzUv?EVD@w5|<o5lj|$m7z1PY2tOhuMYq
Fh-
$x+(To50P#rgYKH*w1c)a<JRTYp1dzu~gMxPCVRm5?W5jXYBOXl4R2Uu_3k1|*_!tom=f2Z26$Z156fwqo&yH!ljd<FKXKI?J(xS
|wIxY7o64SV!c>KgORV`D~q!iO0#)xUT?|AM}HtMRo@9Cb3N6B-ss%-
u()1A#2F+Vt{?Jnpb9_jNf&_UCUW7%E}9n+?pslz5l^m?z#5QE*WgASEp#K(~M?+xP}IYY(K4$vY9x)8i>R*PnXKK%dUNwp+Whu}
hvS~M6yFuebs1bpe-I-zQAodf?@osND)8=-
m=YH!lmj|?0<p4o{0;;pmeb=AOCgQI$IN#>&zc!U@#8n1H!=K=?1mPs+Q%r<tWjxJa6*pjWNBR+<3g3T_l(N`SMoqf*--
Obfts|M#Zccu;(tK2QpM<86}Zjp`{E^@b2gS{GD=x&xi8|FlJrVgKCMCfj%$iYqS>@!5@Zl%b<jqVn@#03|+Gj;eBBSLqMBFBY??
(Fjs=+05(xZYxCtQ0x8(VeNoCPsvd?X!C4C~{n8s@{E!=sw0i)jLy1iWt#-WPWPwih2(t!WH#d^FEb%MZJ*`;n*L1-
XqT`^RD^K)J^ry)X_!CylWm};v!ElB0)Efk#DAr65ZJ+q0k*8-%R_Xdg7QmVr4{cfXYz%q#bU6Q-
<NQ4DtW?^0=4Qs~6X+3JAv$;G({lj&G-
JY3lUGhO0VPy{er@`}cR_Ic4|Wf!@FTz6Vdio3=Ua?QR%%?*#u&Xy4hVY{X9>&;JE|E50H
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verse_marker_ticks(midi: MidiFile) -> dict[int, int]:
    ticks: dict[int, int] = {}
    for track in midi.tracks:
        absolute_tick = 0
        for message in track:
            absolute_tick += message.time
            if (
                message.type == "marker"
                and message.text.startswith("v")
                and message.text[1:].isdigit()
            ):
                ticks[int(message.text[1:])] = absolute_tick
    return ticks


def validate_midi(path: Path) -> None:
    if path.stat().st_size != EXPECTED_OUTPUT_SIZE:
        raise RuntimeError(
            f"File-size mismatch: {path.stat().st_size} != {EXPECTED_OUTPUT_SIZE}"
        )

    midi = MidiFile(path)

    if midi.ticks_per_beat != EXPECTED_TICKS_PER_BEAT:
        raise RuntimeError(
            f"Ticks-per-beat mismatch: {midi.ticks_per_beat} != {EXPECTED_TICKS_PER_BEAT}"
        )
    if len(midi.tracks) != EXPECTED_TRACKS:
        raise RuntimeError(
            f"Track-count mismatch: {len(midi.tracks)} != {EXPECTED_TRACKS}"
        )

    verse_markers = 0
    note_ons = 0
    note_offs = 0

    for track_index, track in enumerate(midi.tracks):
        active: dict[tuple[int, int], int] = {}

        for message in track:
            if (
                message.type == "marker"
                and message.text.startswith("v")
                and message.text[1:].isdigit()
            ):
                verse_markers += 1

            if message.type == "note_on" and message.velocity > 0:
                note_ons += 1
                key = (message.channel, message.note)
                active[key] = active.get(key, 0) + 1

            elif message.type == "note_off" or (
                message.type == "note_on" and message.velocity == 0
            ):
                note_offs += 1
                key = (message.channel, message.note)
                if active.get(key, 0) <= 0:
                    raise RuntimeError(
                        f"Orphan note-off in track {track_index}: "
                        f"ch={key[0]} note={key[1]}"
                    )
                active[key] -= 1

        leftovers = sum(active.values())
        if leftovers:
            raise RuntimeError(
                f"Unclosed notes in track {track_index}: {leftovers}"
            )

    if verse_markers != EXPECTED_VERSE_MARKERS:
        raise RuntimeError(
            f"Verse-marker mismatch: {verse_markers} != {EXPECTED_VERSE_MARKERS}"
        )
    if note_ons != EXPECTED_NOTE_ONS:
        raise RuntimeError(
            f"Note-on mismatch: {note_ons} != {EXPECTED_NOTE_ONS}"
        )
    if note_offs != EXPECTED_NOTE_OFFS:
        raise RuntimeError(
            f"Note-off mismatch: {note_offs} != {EXPECTED_NOTE_OFFS}"
        )

    marker_ticks = _verse_marker_ticks(midi)
    if marker_ticks.get(30) != EXPECTED_V30_TICK:
        raise RuntimeError(
            f"v30 tick mismatch: {marker_ticks.get(30)} != {EXPECTED_V30_TICK}"
        )
    if marker_ticks.get(71) != EXPECTED_V71_TICK:
        raise RuntimeError(
            f"v71 tick mismatch: {marker_ticks.get(71)} != {EXPECTED_V71_TICK}"
        )


# noinspection string-format
def build(source: Path, output: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)

    actual_source_hash = sha256(source)
    if actual_source_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            "The source MIDI is not the approved Pass-12 milestone.\n"
            f"Expected: {EXPECTED_SOURCE_SHA256}\n"
            f"Actual:   {actual_source_hash}"
        )

    payload = "".join(_PAYLOAD_B85.split())
    frozen_master = zlib.decompress(base64.b85decode(payload.encode("ascii")))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(frozen_master)

    actual_output_hash = sha256(output)
    if actual_output_hash != EXPECTED_OUTPUT_SHA256:
        output.unlink(missing_ok=True)
        raise RuntimeError(
            "Output hash mismatch; refusing to keep a non-identical artifact.\n"
            f"Expected: {EXPECTED_OUTPUT_SHA256}\n"
            f"Actual:   {actual_output_hash}"
        )

    validate_midi(output)

    midi = MidiFile(output)
    print(f"PASS: {output}")
    print(f"SHA-256: {actual_output_hash}")
    print(f"Duration: {midi.length:.6f} s ({midi.length / 60:.3f} min)")
    print(f"Tracks: {len(midi.tracks)}")
    print(f"Verse markers: {EXPECTED_VERSE_MARKERS}")
    print(f"Note-on events: {EXPECTED_NOTE_ONS}")
    print("Locked master: GENESIS Theatrical Pass 14R2")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce the locked GENESIS Theatrical Pass 14R2 MIDI exactly."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("GENESIS_Theatrical_Pass_12_MILESTONE_1.mid"),
        help="Approved Pass-12 milestone used as the provenance guard.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("GENESIS_Theatrical_Pass_14R2.mid"),
    )
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()
