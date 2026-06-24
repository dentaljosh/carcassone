### exact:4 vs h3200 (n=100)
- games **74** | **46W / 0D / 28L** | winrate **0.622** (z=+2.09) | Elo **+86.2** (±41.6)
- avg score margin (A−B) **+5.65** | **paired margin +5.141** (z=**+1.84**, 32 decks)
- seat split: A@seat0 wr 0.562 (n=32), A@seat1 wr 0.667 (n=42)
- A exact: exact-moves/game 4.00 (range 4-4); solver 346.34s/game (max 2931.7s); nodes/game 72428; timeouts 0 over 74; latched 74/74; K@latch dist {3: 42, 4: 32}

#### Part D slices (paired margin within slice; n=decks w/ both seats)
  - **by K@latch**
    - K@latch=3: n=42 wr=0.667 paired=None (z=None, 0 decks)
    - K@latch=4: n=32 wr=0.562 paired=None (z=None, 0 decks)
  - **by seat**
    - seat=0: n=32 wr=0.562 paired=None (z=None, 0 decks)
    - seat=1: n=42 wr=0.667 paired=None (z=None, 0 decks)
  - **by margin@latch**
    - margin@latch=ahead(>3): n=36 wr=0.917 paired=29.4 (z=7.65, 5 decks)
    - margin@latch=behind(<-3): n=30 wr=0.200 paired=-13.83 (z=-1.8, 3 decks)
    - margin@latch=close(-3..3): n=8 wr=0.875 paired=None (z=None, 1 decks)
  - **by meeples@latch**
    - meeples@latch=0-1: n=70 wr=0.614 paired=4.77 (z=1.61, 30 decks)
    - meeples@latch=2-3: n=4 wr=0.750 paired=None (z=None, 0 decks)
  - **by legal@latch**
    - legal@latch=hi(>45): n=21 wr=0.619 paired=8.0 (z=2.0, 2 decks)
    - legal@latch=lo(<20): n=5 wr=0.800 paired=None (z=None, 0 decks)
    - legal@latch=mid(20-45): n=48 wr=0.604 paired=4.4 (z=1.32, 15 decks)
  - **by game**
    - game=blowout(|d|>=20): n=36 wr=0.639 paired=11.69 (z=1.69, 8 decks)
    - game=close(|d|<20): n=38 wr=0.605 paired=2.67 (z=1.23, 9 decks)
  - **by timeout**
    - timeout=clean: n=74 wr=0.622 paired=5.14 (z=1.84, 32 decks)
  - **by solver_nodes**
    - solver_nodes=1k-5k: n=4 wr=0.500 paired=None (z=None, 0 decks)
    - solver_nodes=<1k: n=2 wr=1.000 paired=None (z=None, 0 decks)
    - solver_nodes=>5k: n=68 wr=0.618 paired=6.48 (z=2.23, 28 decks)

#### Part F — paired Δ vs baseline (same decks, same opponent; isolates the exact tail)
- overlapping games: 74 (32 decks w/ both seats) — baseline = RoD1-vs-h3200 cached
- mean per-game Δ(margin) +1.432; **paired Δ margin +1.203 (z=**+1.80**)**
  (Δ>0 ⇒ the exact tail improves RoD1's margin vs this opponent on these decks)
