package com.jishal.carcassonne

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import kotlin.math.abs
import kotlin.math.roundToInt

private const val MEEPLE_FRACTION = 0.34f      // sprite edge, as a fraction of a tile

/**
 * Slot dot radius, as a fraction of a tile.
 *
 * Adjacent slots can be a quarter of a tile apart (`top_left` at x=0.25 vs `top`
 * at x=0.5), so 0.105 is about as large as the dots can be drawn before two of
 * them touch. Everything else that makes the target thumb-sized has to come from
 * the tap radius below and from the meeple-phase close-up in GameScreen.
 */
private const val DOT_RADIUS = 0.105f

/**
 * Tap catchment for a slot, in tile fractions — deliberately LARGER than the
 * quarter-tile slot spacing, because [nearestWithin] resolves ties by distance:
 * overlapping catchments cost nothing and a generous one is what turns a ~30px
 * dot into something a thumb can hit. Kept under the ~0.41 distance from a corner
 * slot to the tile centre so a stray tap in the middle of the tile still misses
 * every corner rather than committing a meeple by accident.
 */
private const val SLOT_TAP_RADIUS = 0.25f

/**
 * Farmers lie down (the physical convention), knights stand up.
 *
 * A quarter turn, not a tilt: the point is to be unmistakable at a glance on a
 * board where the sprite is ~30px, and anything less reads as a rendering glitch.
 */
private const val FARMER_TILT = 90f

/** The ghost's prospective slots — present, clearly not yet real. */
private const val PREVIEW_ALPHA = 0.5f

/** Ownership wash. Low enough that the tile art underneath stays legible. */
private const val OWNER_FILL_ALPHA = 0.26f

/** Farm hatching sits over the same cells as a city/road fill, so it is stronger
 *  per stroke but covers only ~1/6 of the area. */
private const val OWNER_HATCH_ALPHA = 0.34f

/** Second tap must land within this of the first, in dp, to read as a double-tap. */
private val DOUBLE_TAP_SLOP = 36.dp

/** ...and within this long. Compose's own default is 300 ms. */
private const val DOUBLE_TAP_MS = 300L

/**
 * The board. Draws in **world units** (see [BoardGeometry]) inside a single
 * `translate + scale`, so every tile's destination rect is the same exact
 * integer square no matter the zoom — which is what stops hairline seams from
 * opening between tiles when [BoardTransform.scale] is fractional.
 *
 * Gestures are two separate `pointerInput` modifiers (tap, then transform).
 * They cooperate: the tap detector gives up as soon as a pointer travels past
 * touch slop or a second finger lands, and the transform detector takes over.
 */
@Composable
fun BoardCanvas(
    state: GameState,
    ghost: Ghost?,
    assets: TileAssets,
    transform: BoardTransform,
    onTransform: (BoardTransform) -> Unit,
    onCellTap: (Cell) -> Unit,
    onMeepleSlot: (MeepleSlot) -> Unit,
    /** Screen-space point of a double-tap that hit nothing interactive. */
    onDoubleTap: (Float, Float) -> Unit,
    onViewportChanged: (Float, Float) -> Unit,
    modifier: Modifier = Modifier,
    /** Prospective slots for the aimed ghost; drawn faint, never tappable. */
    ghostPreview: List<MeepleSlot> = emptyList(),
    /** Claimed features to tint, or empty when the overlay is off. */
    ownership: List<OwnershipFeature> = emptyList(),
) {
    // Captured-once gesture lambdas must read these through State, not through a
    // stale closure, or panning would keep re-deriving from the first transform.
    val tf by rememberUpdatedState(transform)
    val st by rememberUpdatedState(state)
    val onTransformNow by rememberUpdatedState(onTransform)
    val onCellTapNow by rememberUpdatedState(onCellTap)
    val onMeepleSlotNow by rememberUpdatedState(onMeepleSlot)
    val onDoubleTapNow by rememberUpdatedState(onDoubleTap)
    val onViewport by rememberUpdatedState(onViewportChanged)

    Canvas(
        modifier = modifier
            .onSizeChanged { onViewport(it.width.toFloat(), it.height.toFloat()) }
            .pointerInput(Unit) {
                // Double-tap is tracked BY HAND rather than with
                // `detectTapGestures(onDoubleTap = …)`, which would hold every
                // single tap for ~300 ms to see whether a second one follows —
                // and single-tap cell selection is the primary interaction of the
                // whole screen. Instead each tap is dispatched immediately, and a
                // tap only becomes a double-tap CANDIDATE when it hit nothing
                // interactive (no meeple slot, no legal cell). That also keeps the
                // gesture off the one place it would be ambiguous: tapping the
                // same legal cell twice already means "next rotation".
                var lastIdleMs = 0L
                var lastIdleX = 0f
                var lastIdleY = 0f
                val slop = DOUBLE_TAP_SLOP.toPx()
                detectTapGestures { p ->
                    val t = tf
                    val s = st
                    if (s.isMeeplePhase && s.isHumanTurn) {
                        val target = s.legal.meepleTarget
                        if (target != null) {
                            val wx = t.screenToWorldX(p.x)
                            val wy = t.screenToWorldY(p.y)
                            // Hit-test the SAME deduped list that was drawn: aiming at
                            // a dot that is not on screen (a second opening onto a city
                            // already represented) would be a phantom target.
                            val hit = nearestWithin(
                                dedupeByFeature(s.legal.meepleSlots),
                                wx, wy, SLOT_TAP_RADIUS * TILE,
                            ) { slot -> slotCentre(target, slot.offsetX, slot.offsetY) }
                            if (hit != null) {
                                lastIdleMs = 0L
                                onMeepleSlotNow(hit)
                                return@detectTapGestures
                            }
                        }
                    }
                    val cell = t.cellAt(p.x, p.y)
                    if (s.isTilePhase && s.isHumanTurn && s.legal.cellAt(cell) != null) {
                        lastIdleMs = 0L
                        onCellTapNow(cell)
                        return@detectTapGestures
                    }
                    val now = System.currentTimeMillis()
                    if (now - lastIdleMs <= DOUBLE_TAP_MS &&
                        abs(p.x - lastIdleX) <= slop && abs(p.y - lastIdleY) <= slop
                    ) {
                        lastIdleMs = 0L
                        onDoubleTapNow(p.x, p.y)
                        return@detectTapGestures
                    }
                    lastIdleMs = now
                    lastIdleX = p.x
                    lastIdleY = p.y
                    // Unchanged behaviour: a tap on nothing cancels the ghost.
                    onCellTapNow(cell)
                }
            }
            .pointerInput(Unit) {
                detectTransformGestures { centroid, pan, zoom, _ ->
                    onTransformNow(tf.gesture(centroid.x, centroid.y, pan.x, pan.y, zoom))
                }
            },
    ) {
        drawRect(CarcColors.BoardBackdrop)

        val hair = 1.5.dp.toPx() / transform.scale
        withTransform({
            translate(transform.offsetX, transform.offsetY)
            scale(transform.scale, transform.scale, pivot = Offset.Zero)
        }) {
            drawPlacedTiles(state, assets)
            // Between the art and every marker: the overlay is a wash over the
            // terrain, not something that should dim the dots you aim at.
            drawOwnership(ownership, state.humanPlayer)
            drawLegalCells(state, ghost, hair)
            drawGhost(ghost, state, assets)
            drawAiLastTile(state, hair)
            drawPlacedMeeples(state, assets, hair)
            drawGhostPreview(ghost, ghostPreview, hair)
            drawMeepleSlots(state, hair)
        }
    }
}

// --------------------------------------------------------------------------- //
// Layers                                                                       //
// --------------------------------------------------------------------------- //

private fun DrawScope.drawPlacedTiles(state: GameState, assets: TileAssets) {
    for (t in state.board) {
        val bmp = assets.tile(t.image) ?: continue
        drawTileArt(bmp, t.row, t.col, t.turns, alpha = 1f)
    }
}

/**
 * One tile face.
 *
 * ROTATION — verified against the engine, not guessed: `Tile.turn()` maps
 * TOP -> RIGHT (`SideModificationUtil.turn_side`), i.e. `turns` counts
 * **clockwise** quarter-turns; the desktop visualiser renders that with PIL
 * `.rotate(-90 * turns)`, and PIL's positive angle is counter-clockwise, so it
 * too is drawing clockwise. Compose's `rotate(degrees)` is clockwise for
 * positive degrees, so the faithful port is `+90 * turns` (NOT `-90 * turns`,
 * which would be a mirror of the desktop board and silently mis-render every
 * asymmetric face).
 */
private fun DrawScope.drawTileArt(
    bmp: androidx.compose.ui.graphics.ImageBitmap,
    row: Int,
    col: Int,
    turns: Int,
    alpha: Float,
) {
    val x = col * TILE
    val y = row * TILE
    val edge = TILE.toInt()
    rotate(90f * turns, pivot = Offset(x + TILE / 2f, y + TILE / 2f)) {
        drawImage(
            image = bmp,
            dstOffset = IntOffset(x.roundToInt(), y.roundToInt()),
            dstSize = IntSize(edge, edge),
            alpha = alpha,
        )
    }
}

private fun DrawScope.drawLegalCells(state: GameState, ghost: Ghost?, hair: Float) {
    if (!state.isHumanTurn || !state.isTilePhase) return
    for (lc in state.legal.tileCells) {
        val selected = ghost?.cell == lc.cell
        drawRect(
            color = if (selected) CarcColors.SelectedCell else CarcColors.LegalCell,
            topLeft = Offset(lc.col * TILE, lc.row * TILE),
            size = Size(TILE, TILE),
            style = Stroke(width = if (selected) hair * 2.5f else hair * 1.5f),
            alpha = if (selected) 1f else 0.85f,
        )
    }
}

private fun DrawScope.drawGhost(ghost: Ghost?, state: GameState, assets: TileAssets) {
    if (ghost == null) return
    val bmp = assets.tile(state.nextTile?.image) ?: return
    drawTileArt(bmp, ghost.cell.row, ghost.cell.col, ghost.rotation, alpha = 0.6f)
}

private fun DrawScope.drawAiLastTile(state: GameState, hair: Float) {
    val c = state.aiLastTile ?: return
    drawRect(
        color = CarcColors.AiLastTile,
        topLeft = Offset(c.col * TILE, c.row * TILE),
        size = Size(TILE, TILE),
        style = Stroke(width = hair * 2.5f),
    )
}

private fun DrawScope.drawPlacedMeeples(state: GameState, assets: TileAssets, hair: Float) {
    val edge = TILE * MEEPLE_FRACTION
    for (m in state.meeples) {
        val (cx, cy) = slotCentre(Cell(m.row, m.col), m.offsetX, m.offsetY)
        // A halo, because a blue meeple on a dark-green farm is near-invisible.
        drawCircle(
            color = Color.White,
            radius = edge * 0.62f,
            center = Offset(cx, cy),
            alpha = 0.75f,
        )
        drawCircle(
            color = CarcColors.player(m.player, state.humanPlayer),
            radius = edge * 0.62f,
            center = Offset(cx, cy),
            style = Stroke(width = hair * 1.5f),
        )
        val sprite = assets.meeple(m.player, state.humanPlayer)
        if (sprite != null) {
            // A knight/monk stands UPRIGHT. The tkinter visualiser rotates every
            // meeple sprite by -90 before blitting, but the source art is already
            // upright (checked), so that rotation is a quirk of that tool.
            //
            // A FARMER lies down — the physical convention every Carcassonne player
            // already knows, and the only cue that distinguishes the two at a glance
            // once the piece is on the board.
            val e = if (m.isFarmer) edge * 0.8f else edge
            val blit = {
                drawImage(
                    image = sprite,
                    dstOffset = IntOffset(
                        (cx - e / 2f).roundToInt(), (cy - e / 2f).roundToInt(),
                    ),
                    dstSize = IntSize(e.roundToInt(), e.roundToInt()),
                )
            }
            if (m.isFarmer) rotate(FARMER_TILT, pivot = Offset(cx, cy)) { blit() }
            else blit()
        }
    }
}

/**
 * The meeple slots on offer — ONE dot per on-tile feature.
 *
 * A city with two openings is two engine actions claiming the same city, which the
 * player reads as a decision that matters. [dedupeByFeature] collapses them; the
 * action applied is still the representative's real action id, so the champion's
 * action space is untouched.
 */
private fun DrawScope.drawMeepleSlots(state: GameState, hair: Float) {
    if (!state.isHumanTurn || !state.isMeeplePhase) return
    val target = state.legal.meepleTarget ?: return
    for (slot in dedupeByFeature(state.legal.meepleSlots)) {
        val (cx, cy) = slotCentre(target, slot.offsetX, slot.offsetY)
        drawSlotMark(slot, cx, cy, hair, alpha = 1f)
    }
}

/**
 * What a prospective placement would open, drawn on the ghost at half strength.
 *
 * Same marks as the real thing so the two are visibly the same language, but never
 * hit-tested: this is a consequence preview, and the tile is not down yet.
 */
private fun DrawScope.drawGhostPreview(
    ghost: Ghost?,
    slots: List<MeepleSlot>,
    hair: Float,
) {
    if (ghost == null || slots.isEmpty()) return
    for (slot in dedupeByFeature(slots)) {
        val (cx, cy) = slotCentre(ghost.cell, slot.offsetX, slot.offsetY)
        drawSlotMark(slot, cx, cy, hair, alpha = PREVIEW_ALPHA)
    }
}

/**
 * One slot mark. Circle for a knight/monk, diamond for a farmer.
 *
 * The farmer diamond additionally gets an earth-toned ring instead of the white one
 * every other dot wears — shape alone was doing all the work, and at a whole-board
 * fit a small rotated square and a small circle are the same handful of pixels.
 */
private fun DrawScope.drawSlotMark(
    slot: MeepleSlot,
    cx: Float,
    cy: Float,
    hair: Float,
    alpha: Float,
) {
    val colour = CarcColors.terrain(slot.terrain)
    if (slot.isFarmer) {
        val r = TILE * DOT_RADIUS * 0.85f
        rotate(45f, pivot = Offset(cx, cy)) {
            drawRect(
                color = colour, alpha = alpha,
                topLeft = Offset(cx - r, cy - r), size = Size(r * 2, r * 2),
            )
            drawRect(
                color = CarcColors.FarmerRing, alpha = alpha,
                topLeft = Offset(cx - r, cy - r), size = Size(r * 2, r * 2),
                style = Stroke(width = hair * 1.8f),
            )
        }
    } else {
        val r = TILE * DOT_RADIUS
        drawCircle(color = colour, radius = r, center = Offset(cx, cy), alpha = alpha)
        drawCircle(
            color = Color.White, radius = r, center = Offset(cx, cy),
            style = Stroke(width = hair * 1.2f), alpha = alpha,
        )
    }
}

/**
 * Tint every cell of a claimed feature in its owner's colour.
 *
 * Rendering rules, in the order they resolve:
 *  * **contested** (a tie — the engine pays BOTH seats) → purple, so a shared
 *    feature never reads as either player's;
 *  * **farms** → a hatch of diagonal strokes rather than a fill, because a farm
 *    covers whole tiles that also carry a city or a road, and two solid washes on
 *    one cell would be indistinguishable from one strong one;
 *  * everything else → a flat low-alpha fill in the owner's colour.
 *
 * Cells are drawn per feature, so a tile belonging to both a city and a farm gets
 * both marks — which is the truth about that tile.
 */
private fun DrawScope.drawOwnership(features: List<OwnershipFeature>, humanPlayer: Int) {
    if (features.isEmpty()) return
    for (f in features) {
        if (f.owners.isEmpty()) continue
        val colour = when {
            f.isContested -> CarcColors.Contested
            else -> CarcColors.player(f.owners.first(), humanPlayer)
        }
        for (cell in f.cells) {
            val x = cell.col * TILE
            val y = cell.row * TILE
            if (f.isFarm) {
                hatchCell(x, y, colour)
            } else {
                drawRect(
                    color = colour,
                    topLeft = Offset(x, y),
                    size = Size(TILE, TILE),
                    alpha = OWNER_FILL_ALPHA,
                )
            }
        }
    }
}

/** Diagonal hatching inside one cell — the farm marker. */
private fun DrawScope.hatchCell(x: Float, y: Float, colour: Color) {
    val step = TILE / 6f
    val w = TILE / 26f
    // The strokes are full-diagonal and would bleed into the neighbouring cells, so
    // the whole family is clipped to this square. `i` walks from -TILE to +TILE so
    // both triangles of the square are covered.
    clipRect(left = x, top = y, right = x + TILE, bottom = y + TILE) {
        var i = -TILE
        while (i <= TILE) {
            drawLine(
                color = colour,
                start = Offset(x + i, y),
                end = Offset(x + i + TILE, y + TILE),
                strokeWidth = w,
                alpha = OWNER_HATCH_ALPHA,
            )
            i += step
        }
    }
}

/**
 * World-space centre of a meeple slot.
 *
 * The offsets are NOT rotated with the tile art: `coordinate_with_side.side` is
 * already expressed on the *placed* (rotated) tile, so `top` means the top edge
 * as it appears on screen.
 */
fun slotCentre(cell: Cell, ratioX: Float, ratioY: Float): Pair<Float, Float> =
    (cell.col * TILE + ratioX * TILE) to (cell.row * TILE + ratioY * TILE)
