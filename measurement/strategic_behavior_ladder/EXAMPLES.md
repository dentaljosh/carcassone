# Representative strategic-behavior examples (Part E)

Selected for clear, consequential divergence (strong agent takes, weaker misses), high magnitude. Each is provenance-stamped for replay.


## block  (203 opportunities)

**1.** regime=`h6400:random` seed=1961000 g=0 ply=62 mover=P1(`random`) opp=`h6400`  
   phase=midgame k=41 scores=[13, 0] free_meeples=[0, 0] legal_n=33 magnitude=5.0 detail={'opp_eq_pre': 5.0, 'lo': 0.0, 'hi': 5.0, 'spread': 5.0}  
   takes: random=m greedy=T h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-40 result=L  

**2.** regime=`rod1:random` seed=1943008 g=8 ply=82 mover=P1(`random`) opp=`rod1`  
   phase=midgame k=31 scores=[27, 0] free_meeples=[0, 0] legal_n=35 magnitude=3.3 detail={'opp_eq_pre': 6.0, 'lo': 3.0, 'hi': 6.3, 'spread': 3.3}  
   takes: random=m greedy=T h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-40 result=L  

**3.** regime=`greedy:greedy` seed=1940009 g=9 ply=96 mover=P0(`greedy`) opp=`greedy`  
   phase=late_mid k=24 scores=[46, 51] free_meeples=[1, 1] legal_n=13 magnitude=2.2 detail={'opp_eq_pre': 4.5, 'lo': 2.3, 'hi': 4.5, 'spread': 2.2}  
   takes: random=T greedy=m h800=m h3200=m h6400=T rod1=m iter08=m  
   eventual: mover margin=23 result=W  

**4.** regime=`h3200:h6400` seed=1965005 g=5 ply=138 mover=P1(`h3200`) opp=`h6400`  
   phase=endgame k=3 scores=[65, 33] free_meeples=[0, 0] legal_n=53 magnitude=6.5 detail={'opp_eq_pre': 8.0, 'lo': 1.5, 'hi': 8.0, 'spread': 6.5}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=T iter08=T  
   eventual: mover margin=-1 result=L  

**5.** regime=`h3200:h6400` seed=1965006 g=6 ply=72 mover=P0(`h3200`) opp=`h6400`  
   phase=midgame k=36 scores=[22, 17] free_meeples=[1, 0] legal_n=16 magnitude=6.0 detail={'opp_eq_pre': 5.0, 'lo': 1.0, 'hi': 7.0, 'spread': 6.0}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=T iter08=T  
   eventual: mover margin=-22 result=L  

**6.** regime=`rod1:rod1` seed=1941005 g=5 ply=110 mover=P1(`rod1`) opp=`rod1`  
   phase=late_mid k=17 scores=[30, 47] free_meeples=[0, 0] legal_n=42 magnitude=3.5 detail={'opp_eq_pre': 5.9, 'lo': 2.8, 'hi': 6.3, 'spread': 3.5}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=T iter08=T  
   eventual: mover margin=9 result=W  


## avoid_feeding  (780 opportunities)

**1.** regime=`rod1:random` seed=1943005 g=5 ply=44 mover=P0(`random`) opp=`rod1`  
   phase=opening k=50 scores=[0, 14] free_meeples=[0, 2] legal_n=22 magnitude=2.4 detail={'lo': 1.5, 'hi': 3.9, 'spread': 2.4}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=T  
   eventual: mover margin=-50 result=L  

**2.** regime=`h6400:random` seed=1961000 g=0 ply=62 mover=P1(`random`) opp=`h6400`  
   phase=midgame k=41 scores=[13, 0] free_meeples=[0, 0] legal_n=33 magnitude=5.0 detail={'lo': 0.0, 'hi': 5.0, 'spread': 5.0}  
   takes: random=m greedy=T h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-40 result=L  

**3.** regime=`rod1:h6400` seed=1964000 g=0 ply=140 mover=P0(`rod1`) opp=`h6400`  
   phase=endgame k=2 scores=[60, 56] free_meeples=[0, 0] legal_n=20 magnitude=4.1 detail={'lo': 3.9, 'hi': 8.0, 'spread': 4.1}  
   takes: random=m greedy=T h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=9 result=W  

**4.** regime=`rod1:random` seed=1943008 g=8 ply=82 mover=P1(`random`) opp=`rod1`  
   phase=midgame k=31 scores=[27, 0] free_meeples=[0, 0] legal_n=35 magnitude=3.3 detail={'lo': 3.0, 'hi': 6.3, 'spread': 3.3}  
   takes: random=m greedy=T h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-40 result=L  

**5.** regime=`h6400:random` seed=1961003 g=3 ply=92 mover=P0(`random`) opp=`h6400`  
   phase=late_mid k=26 scores=[0, 37] free_meeples=[0, 0] legal_n=26 magnitude=2.6 detail={'lo': 2.2, 'hi': 4.8, 'spread': 2.6}  
   takes: random=T greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-82 result=L  

**6.** regime=`greedy:greedy` seed=1940009 g=9 ply=96 mover=P0(`greedy`) opp=`greedy`  
   phase=late_mid k=24 scores=[46, 51] free_meeples=[1, 1] legal_n=13 magnitude=2.2 detail={'lo': 2.3, 'hi': 4.5, 'spread': 2.2}  
   takes: random=T greedy=m h800=m h3200=m h6400=T rod1=m iter08=m  
   eventual: mover margin=23 result=W  


## contest_merge  (391 opportunities)

**1.** regime=`h6400:random` seed=1961002 g=2 ply=94 mover=P1(`random`) opp=`h6400`  
   phase=late_mid k=25 scores=[8, 0] free_meeples=[0, 0] legal_n=46 magnitude=27.0 detail={'n_yes': 1, 'n_legal': 46}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-59 result=L  

**2.** regime=`h6400:random` seed=1961003 g=3 ply=140 mover=P0(`random`) opp=`h6400`  
   phase=endgame k=2 scores=[0, 59] free_meeples=[0, 0] legal_n=57 magnitude=27.0 detail={'n_yes': 1, 'n_legal': 57}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-82 result=L  

**3.** regime=`h6400:random` seed=1961002 g=2 ply=34 mover=P1(`random`) opp=`h6400`  
   phase=opening k=55 scores=[0, 0] free_meeples=[3, 0] legal_n=28 magnitude=24.0 detail={'n_yes': 1, 'n_legal': 28}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-59 result=L  

**4.** regime=`rod1:random` seed=1943003 g=3 ply=57 mover=P1(`rod1`) opp=`random`  
   phase=midgame k=43 scores=[0, 23] free_meeples=[0, 1] legal_n=29 magnitude=24.0 detail={'n_yes': 1, 'n_legal': 29}  
   takes: random=m greedy=m h800=m h3200=m h6400=T rod1=m iter08=T  
   eventual: mover margin=61 result=W  

**5.** regime=`rod1:rod1` seed=1941011 g=11 ply=66 mover=P1(`rod1`) opp=`rod1`  
   phase=midgame k=39 scores=[24, 14] free_meeples=[0, 0] legal_n=32 magnitude=21.0 detail={'n_yes': 1, 'n_legal': 32}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=-39 result=L  

**6.** regime=`greedy:random` seed=1944007 g=7 ply=138 mover=P1(`greedy`) opp=`random`  
   phase=endgame k=3 scores=[0, 16] free_meeples=[0, 0] legal_n=55 magnitude=15.0 detail={'n_yes': 2, 'n_legal': 55}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=28 result=W  


## farm_claim  (777 opportunities)

**1.** regime=`h200:random` seed=1963002 g=2 ply=89 mover=P0(`h200`) opp=`random`  
   phase=late_mid k=28 scores=[21, 0] free_meeples=[1, 0] legal_n=3 magnitude=12.0 detail={'finished_adj': 0, 'adj_n': 4}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=88 result=W  

**2.** regime=`greedy:greedy` seed=1940005 g=5 ply=17 mover=P0(`greedy`) opp=`greedy`  
   phase=opening k=64 scores=[0, 0] free_meeples=[3, 3] legal_n=3 magnitude=12.0 detail={'finished_adj': 0, 'adj_n': 4}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=T  
   eventual: mover margin=33 result=W  

**3.** regime=`greedy:random` seed=1944004 g=4 ply=97 mover=P0(`greedy`) opp=`random`  
   phase=late_mid k=24 scores=[35, 0] free_meeples=[1, 0] legal_n=4 magnitude=9.0 detail={'finished_adj': 0, 'adj_n': 3}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=73 result=W  

**4.** regime=`greedy:random` seed=1944006 g=6 ply=13 mover=P0(`greedy`) opp=`random`  
   phase=opening k=66 scores=[0, 0] free_meeples=[5, 5] legal_n=3 magnitude=9.0 detail={'finished_adj': 0, 'adj_n': 3}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=65 result=W  

**5.** regime=`h3200:random` seed=1962001 g=1 ply=5 mover=P0(`random`) opp=`h3200`  
   phase=opening k=70 scores=[0, 0] free_meeples=[6, 7] legal_n=7 magnitude=9.0 detail={'finished_adj': 0, 'adj_n': 3}  
   takes: random=m greedy=m h800=m h3200=m h6400=T rod1=m iter08=m  
   eventual: mover margin=-74 result=L  

**6.** regime=`h3200:random` seed=1962001 g=1 ply=7 mover=P1(`h3200`) opp=`random`  
   phase=opening k=69 scores=[0, 0] free_meeples=[5, 7] legal_n=5 magnitude=9.0 detail={'finished_adj': 0, 'adj_n': 3}  
   takes: random=m greedy=m h800=T h3200=T h6400=T rod1=m iter08=m  
   eventual: mover margin=74 result=W  

