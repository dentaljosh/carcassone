### exact:2:clair vs h3200 (n=400)
- games **400** | **206W / 9D / 185L** | winrate **0.526** (z=+1.05) | Elo **+18.3** (±17.4)
- avg score margin (A−B) **+1.09** | **paired margin +1.090** (z=**+0.99**, 200 decks)
- seat split: A@seat0 wr 0.507 (n=200), A@seat1 wr 0.545 (n=200)
- A exact: exact-moves/game 2.00 (range 2-2); solver 7.58s/game (max 125.9s); nodes/game 783; timeouts 0 over 400; latched 400/400; K@latch dist {1: 200, 2: 200}

#### Part D slices (paired margin within slice; n=decks w/ both seats)
  - **by K@latch**
    - K@latch=1: n=200 wr=0.545 paired=None (z=None, 0 decks)
    - K@latch=2: n=200 wr=0.507 paired=None (z=None, 0 decks)
  - **by seat**
    - seat=0: n=200 wr=0.507 paired=None (z=None, 0 decks)
    - seat=1: n=200 wr=0.545 paired=None (z=None, 0 decks)
  - **by margin@latch**
    - margin@latch=ahead(>3): n=187 wr=0.837 paired=18.59 (z=10.85, 43 decks)
    - margin@latch=behind(<-3): n=165 wr=0.170 paired=-12.88 (z=-5.0, 28 decks)
    - margin@latch=close(-3..3): n=48 wr=0.542 paired=-2.38 (z=-0.41, 4 decks)
  - **by meeples@latch**
    - meeples@latch=0-1: n=384 wr=0.526 paired=0.63 (z=0.56, 184 decks)
    - meeples@latch=2-3: n=15 wr=0.500 paired=None (z=None, 0 decks)
    - meeples@latch=4+: n=1 wr=1.000 paired=None (z=None, 0 decks)
  - **by legal@latch**
    - legal@latch=hi(>45): n=137 wr=0.493 paired=-2.02 (z=-0.71, 27 decks)
    - legal@latch=lo(<20): n=6 wr=0.333 paired=None (z=None, 0 decks)
    - legal@latch=mid(20-45): n=257 wr=0.549 paired=2.16 (z=1.36, 87 decks)
  - **by game**
    - game=blowout(|d|>=20): n=162 wr=0.556 paired=2.96 (z=0.82, 37 decks)
    - game=close(|d|<20): n=238 wr=0.506 paired=-0.44 (z=-0.51, 75 decks)
  - **by timeout**
    - timeout=clean: n=400 wr=0.526 paired=1.09 (z=0.99, 200 decks)
  - **by solver_nodes**
    - solver_nodes=1k-5k: n=112 wr=0.473 paired=None (z=None, 0 decks)
    - solver_nodes=<1k: n=283 wr=0.553 paired=3.31 (z=1.83, 83 decks)
    - solver_nodes=>5k: n=5 wr=0.200 paired=None (z=None, 0 decks)

#### Part F — paired Δ vs baseline (same decks, same opponent; isolates the exact tail)
- overlapping games: 400 (200 decks w/ both seats) — baseline = RoD1-vs-h3200 cached (same decks)
- mean per-game Δ(margin) +0.652; **paired Δ margin +0.652 (z=**+4.47**)**
  (Δ>0 ⇒ the exact tail improves RoD1's margin vs this opponent on these decks)
