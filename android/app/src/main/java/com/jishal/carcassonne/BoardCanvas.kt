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
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt

private const val MEEPLE_FRACTION = 0.34f      // sprite edge, as a fraction of a tile
private const val DOT_RADIUS = 0.085f          // slot dot radius, ditto
private const val SLOT_TAP_RADIUS = 0.20f      // finger-sized, in tile fractions

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
    onViewportChanged: (Float, Float) -> Unit,
    modifier: Modifier = Modifier,
) {
    // Captured-once gesture lambdas must read these through State, not through a
    // stale closure, or panning would keep re-deriving from the first transform.
    val tf by rememberUpdatedState(transform)
    val st by rememberUpdatedState(state)
    val onTransformNow by rememberUpdatedState(onTransform)
    val onCellTapNow by rememberUpdatedState(onCellTap)
    val onMeepleSlotNow by rememberUpdatedState(onMeepleSlot)
    val onViewport by rememberUpdatedState(onViewportChanged)

    Canvas(
        modifier = modifier
            .onSizeChanged { onViewport(it.width.toFloat(), it.height.toFloat()) }
            .pointerInput(Unit) {
                detectTapGestures { p ->
                    val t = tf
                    val s = st
                    if (s.isMeeplePhase && s.isHumanTurn) {
                        val target = s.legal.meepleTarget
                        if (target != null) {
                            val wx = t.screenToWorldX(p.x)
                            val wy = t.screenToWorldY(p.y)
                            val hit = nearestWithin(
                                s.legal.meepleSlots, wx, wy, SLOT_TAP_RADIUS * TILE,
                            ) { slot -> slotCentre(target, slot.offsetX, slot.offsetY) }
                            if (hit != null) {
                                onMeepleSlotNow(hit)
                                return@detectTapGestures
                            }
                        }
                    }
                    onCellTapNow(t.cellAt(p.x, p.y))
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
            drawLegalCells(state, ghost, hair)
            drawGhost(ghost, state, assets)
            drawAiLastTile(state, hair)
            drawPlacedMeeples(state, assets, hair)
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
            // Drawn UPRIGHT. The tkinter visualiser rotates meeple sprites by -90
            // before blitting, but the source art is already upright (checked), so
            // that rotation is a quirk of that tool and is deliberately not ported.
            val e = if (m.isFarmer) edge * 0.8f else edge
            drawImage(
                image = sprite,
                dstOffset = IntOffset((cx - e / 2f).roundToInt(), (cy - e / 2f).roundToInt()),
                dstSize = IntSize(e.roundToInt(), e.roundToInt()),
            )
        }
    }
}

private fun DrawScope.drawMeepleSlots(state: GameState, hair: Float) {
    if (!state.isHumanTurn || !state.isMeeplePhase) return
    val target = state.legal.meepleTarget ?: return
    for (slot in state.legal.meepleSlots) {
        val (cx, cy) = slotCentre(target, slot.offsetX, slot.offsetY)
        val colour = CarcColors.terrain(slot.terrain)
        if (slot.isFarmer) {
            // Farmers get a smaller diamond so a corner farm slot is never
            // confused with the road/city dot it sits beside.
            val r = TILE * DOT_RADIUS * 0.85f
            rotate(45f, pivot = Offset(cx, cy)) {
                drawRect(
                    color = colour,
                    topLeft = Offset(cx - r, cy - r),
                    size = Size(r * 2, r * 2),
                )
                drawRect(
                    color = Color.White,
                    topLeft = Offset(cx - r, cy - r),
                    size = Size(r * 2, r * 2),
                    style = Stroke(width = hair * 1.2f),
                )
            }
        } else {
            val r = TILE * DOT_RADIUS
            drawCircle(color = colour, radius = r, center = Offset(cx, cy))
            drawCircle(
                color = Color.White,
                radius = r,
                center = Offset(cx, cy),
                style = Stroke(width = hair * 1.2f),
            )
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
