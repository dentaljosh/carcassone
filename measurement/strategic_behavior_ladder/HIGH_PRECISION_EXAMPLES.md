# High-precision strategic-trap examples (inspect for plausibility)

deck id = `seed` (deck is deterministic from seed). T=took, .=missed.


## MUST_BLOCK_CITY  (12 opportunities)

**1.** idx=8 regime=`h6400:random` seed=1982002 seat=P1 ply=114 TILES  
   phase-K=15 margin_before=-16 scores=[16, 0] free_meeples=[0, 0] legal=32 qualifying=1 mag=17  
   threat: opp city ~17pts, 1 tile from done at cell (3, 19); this placement spoils it (post open_n 1->3)  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`random`)=.  
   eventual: result L (-77)  

**2.** idx=30 regime=`rod1:h6400` seed=1988005 seat=P0 ply=56 TILES  
   phase-K=44 margin_before=-10 scores=[0, 10] free_meeples=[2, 0] legal=13 qualifying=1 mag=15  
   threat: opp city ~15pts, 1 tile from done at cell (3, 14); this placement spoils it (post open_n 1->2)  
   takes: random=T greedy=. h800=. h3200=. h6400=. rod1=.   actual(`h6400`)=.  
   eventual: result L (-6)  

**3.** idx=49 regime=`rod1:h6400` seed=1988006 seat=P0 ply=100 TILES  
   phase-K=22 margin_before=+13 scores=[23, 10] free_meeples=[0, 0] legal=13 qualifying=1 mag=12  
   threat: opp city ~12pts, 1 tile from done at cell (3, 15); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result D (+0)  

**4.** idx=29 regime=`rod1:h6400` seed=1988005 seat=P1 ply=34 TILES  
   phase-K=55 margin_before=+6 scores=[0, 6] free_meeples=[4, 0] legal=15 qualifying=1 mag=11  
   threat: opp city ~11pts, 1 tile from done at cell (4, 14); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+6)  

**5.** idx=225 regime=`greedy:greedy` seed=1987011 seat=P0 ply=124 TILES  
   phase-K=10 margin_before=+19 scores=[44, 25] free_meeples=[0, 0] legal=37 qualifying=1 mag=10  
   threat: opp city ~10pts, 1 tile from done at cell (3, 19); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=.   actual(`greedy`)=.  
   eventual: result W (+14)  

**6.** idx=218 regime=`greedy:greedy` seed=1987008 seat=P1 ply=114 TILES  
   phase-K=15 margin_before=+12 scores=[33, 45] free_meeples=[0, 0] legal=30 qualifying=1 mag=9  
   threat: opp city ~9pts, 1 tile from done at cell (7, 17); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result W (+18)  

**7.** idx=294 regime=`rod1:random` seed=1980012 seat=P1 ply=26 TILES  
   phase-K=59 margin_before=+0 scores=[0, 0] free_meeples=[5, 3] legal=14 qualifying=1 mag=9  
   threat: opp city ~9pts, 1 tile from done at cell (5, 16); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=.  
   eventual: result L (-70)  

**8.** idx=7 regime=`h6400:random` seed=1982002 seat=P1 ply=78 TILES  
   phase-K=33 margin_before=-16 scores=[16, 0] free_meeples=[1, 0] legal=35 qualifying=1 mag=13  
   threat: opp city ~13pts, 1 tile from done at cell (4, 21); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=. h800=. h3200=. h6400=. rod1=.   actual(`random`)=.  
   eventual: result L (-77)  

**9.** idx=148 regime=`rod1:rod1` seed=1985011 seat=P0 ply=28 TILES  
   phase-K=58 margin_before=-9 scores=[0, 9] free_meeples=[4, 4] legal=5 qualifying=3 mag=10  
   threat: opp city ~10pts, 1 tile from done at cell (5, 12); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=. h800=. h3200=. h6400=. rod1=.   actual(`rod1`)=.  
   eventual: result L (-3)  

**10.** idx=149 regime=`rod1:rod1` seed=1985011 seat=P1 ply=38 TILES  
   phase-K=53 margin_before=+5 scores=[4, 9] free_meeples=[4, 3] legal=19 qualifying=1 mag=10  
   threat: opp city ~10pts, 1 tile from done at cell (5, 12); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=. h800=. h3200=. h6400=. rod1=.   actual(`rod1`)=.  
   eventual: result W (+3)  

**11.** idx=58 regime=`h6400:random` seed=1982005 seat=P0 ply=72 TILES  
   phase-K=36 margin_before=-17 scores=[0, 17] free_meeples=[0, 0] legal=36 qualifying=3 mag=8  
   threat: opp city ~8pts, 1 tile from done at cell (10, 19); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=. h800=. h3200=. h6400=. rod1=.   actual(`random`)=.  
   eventual: result L (-75)  

**12.** idx=163 regime=`rod1:random` seed=1980000 seat=P1 ply=38 TILES  
   phase-K=53 margin_before=-2 scores=[2, 0] free_meeples=[3, 0] legal=21 qualifying=3 mag=8  
   threat: opp city ~8pts, 1 tile from done at cell (4, 18); this placement spoils it (post open_n 1->2)  
   takes: random=. greedy=. h800=. h3200=. h6400=. rod1=.   actual(`random`)=T  
   eventual: result L (-77)  


## MUST_NOT_FEED  (115 opportunities)

**1.** idx=49 regime=`rod1:h6400` seed=1988006 seat=P0 ply=100 TILES  
   phase-K=22 margin_before=+13 scores=[23, 10] free_meeples=[0, 0] legal=13 qualifying=1 mag=12  
   threat: a legal move hands opp a ~12pt completable city; 1/13 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result D (+0)  

**2.** idx=289 regime=`random:random` seed=1984007 seat=P1 ply=110 TILES  
   phase-K=17 margin_before=+2 scores=[0, 2] free_meeples=[0, 0] legal=39 qualifying=1 mag=12  
   threat: a legal move hands opp a ~12pt completable city; 1/39 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=.  
   eventual: result L (-17)  

**3.** idx=29 regime=`rod1:h6400` seed=1988005 seat=P1 ply=34 TILES  
   phase-K=55 margin_before=+6 scores=[0, 6] free_meeples=[4, 0] legal=15 qualifying=1 mag=11  
   threat: a legal move hands opp a ~11pt completable city; 1/15 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+6)  

**4.** idx=146 regime=`rod1:rod1` seed=1985011 seat=P0 ply=24 TILES  
   phase-K=60 margin_before=-7 scores=[0, 7] free_meeples=[4, 4] legal=26 qualifying=24 mag=10  
   threat: a legal move hands opp a ~10pt completable city; 24/26 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=.   actual(`rod1`)=.  
   eventual: result L (-3)  

**5.** idx=225 regime=`greedy:greedy` seed=1987011 seat=P0 ply=124 TILES  
   phase-K=10 margin_before=+19 scores=[44, 25] free_meeples=[0, 0] legal=37 qualifying=1 mag=10  
   threat: a legal move hands opp a ~10pt completable city; 1/37 placements avoid it  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=.   actual(`greedy`)=.  
   eventual: result W (+14)  

**6.** idx=219 regime=`greedy:greedy` seed=1987009 seat=P1 ply=22 TILES  
   phase-K=61 margin_before=+0 scores=[0, 0] free_meeples=[4, 3] legal=11 qualifying=10 mag=9  
   threat: a legal move hands opp a ~9pt completable city; 10/11 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result W (+7)  

**7.** idx=214 regime=`greedy:greedy` seed=1987010 seat=P1 ply=105 TILES  
   phase-K=19 margin_before=+15 scores=[19, 34] free_meeples=[0, 1] legal=44 qualifying=40 mag=9  
   threat: a legal move hands opp a ~9pt completable city; 40/44 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result W (+46)  

**8.** idx=218 regime=`greedy:greedy` seed=1987008 seat=P1 ply=114 TILES  
   phase-K=15 margin_before=+12 scores=[33, 45] free_meeples=[0, 0] legal=30 qualifying=1 mag=9  
   threat: a legal move hands opp a ~9pt completable city; 1/30 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result W (+18)  

**9.** idx=247 regime=`rod1:random` seed=1980008 seat=P1 ply=82 TILES  
   phase-K=31 margin_before=-10 scores=[10, 0] free_meeples=[0, 0] legal=17 qualifying=16 mag=9  
   threat: a legal move hands opp a ~9pt completable city; 16/17 placements avoid it  
   takes: random=T greedy=. h800=. h3200=. h6400=. rod1=.   actual(`random`)=T  
   eventual: result L (-51)  

**10.** idx=248 regime=`rod1:random` seed=1980008 seat=P1 ply=94 TILES  
   phase-K=25 margin_before=-10 scores=[10, 0] free_meeples=[0, 0] legal=30 qualifying=29 mag=9  
   threat: a legal move hands opp a ~9pt completable city; 29/30 placements avoid it  
   takes: random=T greedy=T h800=. h3200=. h6400=. rod1=T   actual(`random`)=T  
   eventual: result L (-51)  

**11.** idx=294 regime=`rod1:random` seed=1980012 seat=P1 ply=26 TILES  
   phase-K=59 margin_before=+0 scores=[0, 0] free_meeples=[5, 3] legal=14 qualifying=1 mag=9  
   threat: a legal move hands opp a ~9pt completable city; 1/14 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=.  
   eventual: result L (-70)  

**12.** idx=127 regime=`rod1:rod1` seed=1985002 seat=P0 ply=36 TILES  
   phase-K=54 margin_before=-7 scores=[4, 11] free_meeples=[2, 4] legal=18 qualifying=17 mag=8  
   threat: a legal move hands opp a ~8pt completable city; 17/18 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result L (-16)  

**13.** idx=131 regime=`rod1:rod1` seed=1985007 seat=P1 ply=70 TILES  
   phase-K=37 margin_before=-11 scores=[24, 13] free_meeples=[1, 1] legal=13 qualifying=12 mag=8  
   threat: a legal move hands opp a ~8pt completable city; 12/13 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=.   actual(`rod1`)=.  
   eventual: result L (-27)  

**14.** idx=288 regime=`random:random` seed=1984004 seat=P1 ply=94 TILES  
   phase-K=25 margin_before=+0 scores=[0, 0] free_meeples=[0, 0] legal=45 qualifying=44 mag=8  
   threat: a legal move hands opp a ~8pt completable city; 44/45 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result W (+5)  

**15.** idx=310 regime=`rod1:random` seed=1980016 seat=P1 ply=74 TILES  
   phase-K=35 margin_before=-19 scores=[19, 0] free_meeples=[2, 0] legal=35 qualifying=33 mag=8  
   threat: a legal move hands opp a ~8pt completable city; 33/35 placements avoid it  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result L (-56)  

**16.** idx=237 regime=`greedy:random` seed=1981003 seat=P1 ply=138 TILES  
   phase-K=3 margin_before=+47 scores=[0, 47] free_meeples=[0, 1] legal=38 qualifying=36 mag=14  
   threat: a legal move hands opp a ~14pt completable city; 36/38 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=.   actual(`greedy`)=T  
   eventual: result W (+66)  

**17.** idx=307 regime=`rod1:random` seed=1980015 seat=P0 ply=72 TILES  
   phase-K=36 margin_before=-24 scores=[0, 24] free_meeples=[0, 1] legal=25 qualifying=24 mag=8  
   threat: a legal move hands opp a ~8pt completable city; 24/25 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=.   actual(`random`)=T  
   eventual: result L (-69)  

**18.** idx=181 regime=`greedy:greedy` seed=1987001 seat=P1 ply=102 TILES  
   phase-K=21 margin_before=-10 scores=[20, 10] free_meeples=[0, 0] legal=30 qualifying=29 mag=23  
   threat: a legal move hands opp a ~23pt completable city; 29/30 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result L (-24)  

**19.** idx=2 regime=`h6400:random` seed=1982000 seat=P1 ply=78 TILES  
   phase-K=33 margin_before=-6 scores=[6, 0] free_meeples=[0, 0] legal=34 qualifying=32 mag=18  
   threat: a legal move hands opp a ~18pt completable city; 32/34 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result L (-62)  

**20.** idx=1 regime=`h6400:random` seed=1982000 seat=P1 ply=66 TILES  
   phase-K=39 margin_before=-6 scores=[6, 0] free_meeples=[0, 0] legal=27 qualifying=25 mag=18  
   threat: a legal move hands opp a ~18pt completable city; 25/27 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result L (-62)  

**21.** idx=50 regime=`rod1:h6400` seed=1988006 seat=P0 ply=128 TILES  
   phase-K=8 margin_before=+13 scores=[23, 10] free_meeples=[0, 0] legal=39 qualifying=38 mag=18  
   threat: a legal move hands opp a ~18pt completable city; 38/39 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result D (+0)  

**22.** idx=5 regime=`h6400:random` seed=1982002 seat=P1 ply=66 TILES  
   phase-K=39 margin_before=-8 scores=[8, 0] free_meeples=[1, 0] legal=40 qualifying=1 mag=13  
   threat: a legal move hands opp a ~13pt completable city; 1/40 placements avoid it  
   takes: random=. greedy=. h800=. h3200=. h6400=. rod1=.   actual(`random`)=.  
   eventual: result L (-77)  

**23.** idx=101 regime=`h800:h800` seed=1986008 seat=P1 ply=130 TILES  
   phase-K=7 margin_before=-2 scores=[31, 29] free_meeples=[0, 0] legal=50 qualifying=49 mag=13  
   threat: a legal move hands opp a ~13pt completable city; 49/50 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result L (-3)  

**24.** idx=102 regime=`h800:h800` seed=1986008 seat=P1 ply=134 TILES  
   phase-K=5 margin_before=-2 scores=[31, 29] free_meeples=[0, 0] legal=52 qualifying=51 mag=13  
   threat: a legal move hands opp a ~13pt completable city; 51/52 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result L (-3)  

**25.** idx=111 regime=`h800:h800` seed=1986009 seat=P1 ply=94 TILES  
   phase-K=25 margin_before=+0 scores=[26, 26] free_meeples=[1, 1] legal=38 qualifying=1 mag=13  
   threat: a legal move hands opp a ~13pt completable city; 1/38 placements avoid it  
   takes: random=. greedy=. h800=. h3200=. h6400=. rod1=.   actual(`h800`)=.  
   eventual: result L (-23)  

**26.** idx=277 regime=`greedy:random` seed=1981013 seat=P0 ply=96 TILES  
   phase-K=24 margin_before=-4 scores=[8, 12] free_meeples=[0, 0] legal=58 qualifying=57 mag=13  
   threat: a legal move hands opp a ~13pt completable city; 57/58 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result L (-39)  

**27.** idx=278 regime=`greedy:random` seed=1981013 seat=P0 ply=100 TILES  
   phase-K=22 margin_before=-4 scores=[8, 12] free_meeples=[0, 0] legal=49 qualifying=48 mag=13  
   threat: a legal move hands opp a ~13pt completable city; 48/49 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result L (-39)  

**28.** idx=309 regime=`rod1:random` seed=1980017 seat=P0 ply=36 TILES  
   phase-K=54 margin_before=-6 scores=[0, 6] free_meeples=[2, 0] legal=26 qualifying=24 mag=13  
   threat: a legal move hands opp a ~13pt completable city; 24/26 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result L (-76)  

**29.** idx=16 regime=`rod1:h6400` seed=1988001 seat=P1 ply=54 TILES  
   phase-K=45 margin_before=+16 scores=[11, 27] free_meeples=[4, 2] legal=21 qualifying=20 mag=12  
   threat: a legal move hands opp a ~12pt completable city; 20/21 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+31)  

**30.** idx=15 regime=`rod1:h6400` seed=1988001 seat=P0 ply=48 TILES  
   phase-K=48 margin_before=-18 scores=[9, 27] free_meeples=[4, 3] legal=26 qualifying=25 mag=12  
   threat: a legal move hands opp a ~12pt completable city; 25/26 placements avoid it  
   takes: random=T greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result L (-31)  


## MUST_PUNISH_WEAK  (179 opportunities)

**1.** idx=3 regime=`h6400:random` seed=1982000 seat=P0 ply=140 TILES  
   phase-K=2 margin_before=+2 scores=[6, 4] free_meeples=[0, 0] legal=40 qualifying=1 mag=40  
   threat: mover can COMPLETE its own ~40pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=.   actual(`h6400`)=T  
   eventual: result W (+62)  

**2.** idx=9 regime=`h6400:random` seed=1982002 seat=P0 ply=124 TILES  
   phase-K=10 margin_before=+16 scores=[16, 0] free_meeples=[0, 0] legal=28 qualifying=1 mag=36  
   threat: mover can COMPLETE its own ~36pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+77)  

**3.** idx=112 regime=`h800:h800` seed=1986009 seat=P0 ply=96 TILES  
   phase-K=24 margin_before=-4 scores=[26, 30] free_meeples=[1, 1] legal=17 qualifying=1 mag=28  
   threat: mover can COMPLETE its own ~28pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result W (+23)  

**4.** idx=249 regime=`rod1:random` seed=1980008 seat=P0 ply=137 MEEPLES  
   phase-K=4 margin_before=+19 scores=[19, 0] free_meeples=[1, 0] legal=5 qualifying=1 mag=27  
   threat: mover can CLAIM a ~27pt live field the opp left exposed  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=.   actual(`rod1`)=.  
   eventual: result W (+51)  

**5.** idx=164 regime=`rod1:random` seed=1980000 seat=P0 ply=52 TILES  
   phase-K=46 margin_before=+2 scores=[2, 0] free_meeples=[1, 0] legal=16 qualifying=2 mag=22  
   threat: mover can COMPLETE its own ~22pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+77)  

**6.** idx=23 regime=`rod1:h6400` seed=1988009 seat=P0 ply=88 TILES  
   phase-K=28 margin_before=+3 scores=[31, 28] free_meeples=[0, 0] legal=29 qualifying=2 mag=20  
   threat: mover can COMPLETE its own ~20pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result D (+0)  

**7.** idx=126 regime=`rod1:rod1` seed=1985003 seat=P0 ply=76 TILES  
   phase-K=34 margin_before=-4 scores=[16, 20] free_meeples=[1, 2] legal=25 qualifying=1 mag=20  
   threat: mover can COMPLETE its own ~20pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+14)  

**8.** idx=295 regime=`rod1:random` seed=1980012 seat=P0 ply=36 TILES  
   phase-K=54 margin_before=+3 scores=[3, 0] free_meeples=[4, 2] legal=30 qualifying=2 mag=20  
   threat: mover can COMPLETE its own ~20pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+70)  

**9.** idx=82 regime=`h3200:random` seed=1983010 seat=P0 ply=16 TILES  
   phase-K=64 margin_before=+0 scores=[0, 0] free_meeples=[5, 5] legal=16 qualifying=1 mag=18  
   threat: mover can COMPLETE its own ~18pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h3200`)=T  
   eventual: result W (+87)  

**10.** idx=105 regime=`h800:h800` seed=1986007 seat=P1 ply=106 TILES  
   phase-K=19 margin_before=+7 scores=[14, 21] free_meeples=[0, 1] legal=34 qualifying=2 mag=18  
   threat: mover can COMPLETE its own ~18pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result W (+18)  

**11.** idx=121 regime=`rod1:rod1` seed=1985004 seat=P0 ply=55 TILES  
   phase-K=44 margin_before=-9 scores=[2, 11] free_meeples=[0, 0] legal=32 qualifying=1 mag=18  
   threat: mover can COMPLETE its own ~18pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result L (-18)  

**12.** idx=132 regime=`rod1:rod1` seed=1985007 seat=P0 ply=80 TILES  
   phase-K=32 margin_before=+11 scores=[28, 17] free_meeples=[2, 1] legal=43 qualifying=1 mag=18  
   threat: mover can COMPLETE its own ~18pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+27)  

**13.** idx=142 regime=`rod1:rod1` seed=1985009 seat=P1 ply=74 TILES  
   phase-K=35 margin_before=+11 scores=[4, 15] free_meeples=[0, 0] legal=34 qualifying=2 mag=18  
   threat: mover can COMPLETE its own ~18pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+42)  

**14.** idx=157 regime=`rod1:rod1` seed=1985010 seat=P0 ply=80 TILES  
   phase-K=32 margin_before=-13 scores=[19, 32] free_meeples=[0, 0] legal=30 qualifying=1 mag=16  
   threat: mover can COMPLETE its own ~16pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+22)  

**15.** idx=199 regime=`rod1:random` seed=1980007 seat=P1 ply=22 TILES  
   phase-K=61 margin_before=+0 scores=[0, 0] free_meeples=[2, 5] legal=11 qualifying=1 mag=16  
   threat: mover can COMPLETE its own ~16pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+53)  

**16.** idx=231 regime=`greedy:random` seed=1981001 seat=P1 ply=95 MEEPLES  
   phase-K=25 margin_before=+17 scores=[7, 24] free_meeples=[0, 1] legal=5 qualifying=1 mag=15  
   threat: mover can CLAIM a ~15pt live field the opp left exposed  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=.  
   eventual: result W (+79)  

**17.** idx=243 regime=`greedy:random` seed=1981004 seat=P1 ply=15 MEEPLES  
   phase-K=65 margin_before=-4 scores=[4, 0] free_meeples=[4, 5] legal=4 qualifying=1 mag=15  
   threat: mover can CLAIM a ~15pt live field the opp left exposed  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`random`)=.  
   eventual: result L (-62)  

**18.** idx=302 regime=`rod1:random` seed=1980014 seat=P0 ply=13 MEEPLES  
   phase-K=66 margin_before=+4 scores=[4, 0] free_meeples=[5, 5] legal=4 qualifying=1 mag=15  
   threat: mover can CLAIM a ~15pt live field the opp left exposed  
   takes: random=T greedy=. h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+63)  

**19.** idx=10 regime=`h6400:random` seed=1982003 seat=P1 ply=66 TILES  
   phase-K=39 margin_before=+13 scores=[0, 13] free_meeples=[0, 1] legal=31 qualifying=4 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+98)  

**20.** idx=70 regime=`h3200:random` seed=1983009 seat=P1 ply=29 TILES  
   phase-K=57 margin_before=-2 scores=[2, 0] free_meeples=[4, 4] legal=14 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h3200`)=T  
   eventual: result W (+87)  

**21.** idx=78 regime=`h3200:random` seed=1983007 seat=P1 ply=34 TILES  
   phase-K=55 margin_before=+0 scores=[0, 0] free_meeples=[0, 3] legal=22 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h3200`)=T  
   eventual: result W (+91)  

**22.** idx=93 regime=`h800:h800` seed=1986004 seat=P0 ply=28 TILES  
   phase-K=58 margin_before=+0 scores=[0, 0] free_meeples=[3, 3] legal=22 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result D (+0)  

**23.** idx=100 regime=`h800:h800` seed=1986008 seat=P0 ply=52 TILES  
   phase-K=46 margin_before=-8 scores=[3, 11] free_meeples=[2, 2] legal=25 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result W (+3)  

**24.** idx=113 regime=`h800:h800` seed=1986011 seat=P0 ply=96 TILES  
   phase-K=24 margin_before=+11 scores=[26, 15] free_meeples=[0, 0] legal=27 qualifying=3 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result W (+29)  

**25.** idx=115 regime=`h800:h800` seed=1986010 seat=P1 ply=62 TILES  
   phase-K=41 margin_before=-6 scores=[24, 18] free_meeples=[1, 0] legal=30 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h800`)=T  
   eventual: result L (-14)  

**26.** idx=138 regime=`rod1:rod1` seed=1985006 seat=P0 ply=52 TILES  
   phase-K=46 margin_before=-17 scores=[4, 21] free_meeples=[0, 1] legal=31 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+30)  

**27.** idx=152 regime=`rod1:rod1` seed=1985012 seat=P0 ply=16 TILES  
   phase-K=64 margin_before=-2 scores=[0, 2] free_meeples=[4, 4] legal=20 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+20)  

**28.** idx=183 regime=`rod1:random` seed=1980005 seat=P1 ply=22 TILES  
   phase-K=61 margin_before=-4 scores=[4, 0] free_meeples=[2, 4] legal=20 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+50)  

**29.** idx=215 regime=`greedy:greedy` seed=1987008 seat=P1 ply=26 TILES  
   phase-K=59 margin_before=-9 scores=[9, 0] free_meeples=[3, 3] legal=14 qualifying=2 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result W (+18)  

**30.** idx=258 regime=`greedy:random` seed=1981005 seat=P1 ply=125 TILES  
   phase-K=9 margin_before=+10 scores=[2, 12] free_meeples=[0, 0] legal=38 qualifying=1 mag=14  
   threat: mover can COMPLETE its own ~14pt city this turn  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result W (+62)  


## HIGH_VALUE_FARM_CLAIM_REFINED  (95 opportunities)

**1.** idx=212 regime=`greedy:greedy` seed=1987010 seat=P1 ply=98 MEEPLES  
   phase-K=23 margin_before=+11 scores=[19, 30] free_meeples=[0, 2] legal=6 qualifying=1 mag=30  
   threat: sole-claim a field touching 10 cities (8 live/finishable), projected ~30pts  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=T  
   eventual: result W (+46)  

**2.** idx=249 regime=`rod1:random` seed=1980008 seat=P0 ply=137 MEEPLES  
   phase-K=4 margin_before=+19 scores=[19, 0] free_meeples=[1, 0] legal=5 qualifying=1 mag=27  
   threat: sole-claim a field touching 9 cities (9 live/finishable), projected ~27pts  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=.   actual(`rod1`)=.  
   eventual: result W (+51)  

**3.** idx=185 regime=`rod1:random` seed=1980005 seat=P1 ply=95 MEEPLES  
   phase-K=25 margin_before=+16 scores=[4, 20] free_meeples=[0, 1] legal=5 qualifying=1 mag=15  
   threat: sole-claim a field touching 5 cities (4 live/finishable), projected ~15pts  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=.   actual(`rod1`)=.  
   eventual: result W (+50)  

**4.** idx=231 regime=`greedy:random` seed=1981001 seat=P1 ply=95 MEEPLES  
   phase-K=25 margin_before=+17 scores=[7, 24] free_meeples=[0, 1] legal=5 qualifying=1 mag=15  
   threat: sole-claim a field touching 5 cities (5 live/finishable), projected ~15pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=.  
   eventual: result W (+79)  

**5.** idx=243 regime=`greedy:random` seed=1981004 seat=P1 ply=15 MEEPLES  
   phase-K=65 margin_before=-4 scores=[4, 0] free_meeples=[4, 5] legal=4 qualifying=1 mag=15  
   threat: sole-claim a field touching 5 cities (5 live/finishable), projected ~15pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`random`)=.  
   eventual: result L (-62)  

**6.** idx=302 regime=`rod1:random` seed=1980014 seat=P0 ply=13 MEEPLES  
   phase-K=66 margin_before=+4 scores=[4, 0] free_meeples=[5, 5] legal=4 qualifying=1 mag=15  
   threat: sole-claim a field touching 5 cities (5 live/finishable), projected ~15pts  
   takes: random=T greedy=. h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+63)  

**7.** idx=14 regime=`rod1:h6400` seed=1988001 seat=P0 ply=29 MEEPLES  
   phase-K=58 margin_before=+0 scores=[9, 9] free_meeples=[6, 5] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (3 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result L (-31)  

**8.** idx=36 regime=`rod1:h6400` seed=1988000 seat=P1 ply=123 MEEPLES  
   phase-K=11 margin_before=-13 scores=[39, 26] free_meeples=[0, 1] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result L (-32)  

**9.** idx=43 regime=`rod1:h6400` seed=1988002 seat=P0 ply=37 MEEPLES  
   phase-K=54 margin_before=+0 scores=[8, 8] free_meeples=[2, 4] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=T greedy=. h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result L (-17)  

**10.** idx=48 regime=`rod1:h6400` seed=1988006 seat=P0 ply=37 MEEPLES  
   phase-K=54 margin_before=-8 scores=[0, 8] free_meeples=[2, 1] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result D (+0)  

**11.** idx=72 regime=`h3200:random` seed=1983009 seat=P0 ply=36 MEEPLES  
   phase-K=54 margin_before=-12 scores=[2, 14] free_meeples=[3, 3] legal=3 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`random`)=.  
   eventual: result L (-87)  

**12.** idx=133 regime=`rod1:rod1` seed=1985005 seat=P0 ply=17 MEEPLES  
   phase-K=64 margin_before=+2 scores=[4, 2] free_meeples=[6, 6] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=T greedy=. h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+2)  

**13.** idx=173 regime=`rod1:random` seed=1980002 seat=P0 ply=29 MEEPLES  
   phase-K=58 margin_before=+0 scores=[0, 0] free_meeples=[4, 3] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=T greedy=. h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+71)  

**14.** idx=188 regime=`greedy:greedy` seed=1987002 seat=P0 ply=25 MEEPLES  
   phase-K=60 margin_before=-6 scores=[0, 6] free_meeples=[4, 4] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=.  
   eventual: result L (-9)  

**15.** idx=220 regime=`greedy:greedy` seed=1987009 seat=P1 ply=31 MEEPLES  
   phase-K=57 margin_before=+0 scores=[0, 0] free_meeples=[4, 3] legal=4 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=.  
   eventual: result W (+7)  

**16.** idx=221 regime=`greedy:greedy` seed=1987009 seat=P1 ply=35 MEEPLES  
   phase-K=55 margin_before=+0 scores=[0, 0] free_meeples=[3, 2] legal=5 qualifying=2 mag=12  
   threat: sole-claim a field touching 4 cities (4 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=.   actual(`greedy`)=.  
   eventual: result W (+7)  

**17.** idx=254 regime=`greedy:random` seed=1981006 seat=P0 ply=29 MEEPLES  
   phase-K=58 margin_before=+5 scores=[5, 0] free_meeples=[2, 2] legal=5 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (3 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=.   actual(`greedy`)=.  
   eventual: result W (+59)  

**18.** idx=276 regime=`greedy:random` seed=1981013 seat=P1 ply=27 MEEPLES  
   phase-K=59 margin_before=+0 scores=[8, 8] free_meeples=[1, 5] legal=6 qualifying=1 mag=12  
   threat: sole-claim a field touching 4 cities (3 live/finishable), projected ~12pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`greedy`)=.  
   eventual: result W (+39)  

**19.** idx=13 regime=`rod1:h6400` seed=1988001 seat=P0 ply=21 MEEPLES  
   phase-K=62 margin_before=+1 scores=[3, 2] free_meeples=[6, 5] legal=6 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=T greedy=. h800=. h3200=. h6400=. rod1=.   actual(`h6400`)=.  
   eventual: result L (-31)  

**20.** idx=0 regime=`h6400:random` seed=1982000 seat=P0 ply=49 MEEPLES  
   phase-K=48 margin_before=+6 scores=[6, 0] free_meeples=[2, 0] legal=5 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+62)  

**21.** idx=21 regime=`rod1:h6400` seed=1988007 seat=P0 ply=137 MEEPLES  
   phase-K=4 margin_before=+6 scores=[31, 25] free_meeples=[1, 0] legal=5 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+17)  

**22.** idx=27 regime=`rod1:h6400` seed=1988005 seat=P1 ply=7 MEEPLES  
   phase-K=69 margin_before=+0 scores=[0, 0] free_meeples=[6, 6] legal=4 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`rod1`)=T  
   eventual: result W (+6)  

**23.** idx=31 regime=`rod1:h6400` seed=1988005 seat=P0 ply=97 MEEPLES  
   phase-K=24 margin_before=+11 scores=[28, 17] free_meeples=[2, 0] legal=5 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (2 live/finishable), projected ~9pts  
   takes: random=. greedy=T h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result L (-6)  

**24.** idx=38 regime=`rod1:h6400` seed=1988008 seat=P1 ply=43 MEEPLES  
   phase-K=51 margin_before=-3 scores=[12, 9] free_meeples=[2, 4] legal=3 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+35)  

**25.** idx=40 regime=`rod1:h6400` seed=1988004 seat=P0 ply=49 MEEPLES  
   phase-K=48 margin_before=-5 scores=[6, 11] free_meeples=[1, 4] legal=2 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (2 live/finishable), projected ~9pts  
   takes: random=T greedy=. h800=. h3200=. h6400=T rod1=.   actual(`rod1`)=.  
   eventual: result W (+3)  

**26.** idx=42 regime=`rod1:h6400` seed=1988002 seat=P1 ply=23 MEEPLES  
   phase-K=61 margin_before=-4 scores=[4, 0] free_meeples=[3, 5] legal=3 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (2 live/finishable), projected ~9pts  
   takes: random=T greedy=. h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+17)  

**27.** idx=46 regime=`rod1:h6400` seed=1988006 seat=P1 ply=23 MEEPLES  
   phase-K=61 margin_before=+0 scores=[0, 0] free_meeples=[3, 3] legal=5 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (2 live/finishable), projected ~9pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result D (+0)  

**28.** idx=56 regime=`h6400:random` seed=1982005 seat=P1 ply=31 MEEPLES  
   phase-K=57 margin_before=+12 scores=[0, 12] free_meeples=[2, 3] legal=4 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+75)  

**29.** idx=60 regime=`h6400:random` seed=1982007 seat=P1 ply=43 MEEPLES  
   phase-K=51 margin_before=+14 scores=[0, 14] free_meeples=[0, 1] legal=3 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`h6400`)=T  
   eventual: result W (+53)  

**30.** idx=66 regime=`h3200:random` seed=1983004 seat=P1 ply=23 MEEPLES  
   phase-K=61 margin_before=-2 scores=[2, 0] free_meeples=[4, 2] legal=4 qualifying=1 mag=9  
   threat: sole-claim a field touching 3 cities (3 live/finishable), projected ~9pts  
   takes: random=. greedy=. h800=T h3200=T h6400=T rod1=T   actual(`random`)=T  
   eventual: result L (-54)  

