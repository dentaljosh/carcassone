package com.jishal.carcassonne

import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/**
 * Pure board <-> screen geometry. **No Android, Compose or JSON types on
 * purpose** — this is the part of the canvas that can actually be unit-tested on
 * the JVM (`app/src/test/.../BoardGeometryTest.kt`), and the part most likely to
 * be wrong in a way that is invisible without a device.
 *
 * Coordinate spaces
 * -----------------
 * * **engine cell** — `(row, col)` exactly as the bridge reports them (indices
 *   into the engine's 35x35 board; the origin is *not* the top-left of the play
 *   area, which is why every view starts by fitting to the bounding box).
 * * **world** — cell `(row, col)` occupies the square
 *   `x in [col*TILE, (col+1)*TILE)`, `y in [row*TILE, (row+1)*TILE)`.
 *   Note `x` follows `col` and `y` follows `row`.
 * * **screen** — `world * scale + offset`, in canvas pixels.
 */
const val TILE: Float = 100f

const val MIN_SCALE: Float = 0.4f
const val MAX_SCALE: Float = 3.0f

data class Cell(val row: Int, val col: Int)

/** Inclusive engine-cell bounding box. */
data class BoardBounds(
    val minRow: Int,
    val maxRow: Int,
    val minCol: Int,
    val maxCol: Int,
) {
    val rows: Int get() = maxRow - minRow + 1
    val cols: Int get() = maxCol - minCol + 1

    /** Grows the box by [n] cells on every side (cheap way to include the ring of legal cells). */
    fun expanded(n: Int): BoardBounds =
        BoardBounds(minRow - n, maxRow + n, minCol - n, maxCol + n)

    /**
     * Grows the box symmetrically until it is at least [side] cells across in
     * both axes. Without this the opening fit — a 1-tile board — would clamp to
     * [MAX_SCALE] and open absurdly zoomed in on the start tile.
     */
    fun atLeast(side: Int): BoardBounds {
        var b = this
        while (b.rows < side) b = BoardBounds(b.minRow - 1, b.maxRow + 1, b.minCol, b.maxCol)
        while (b.cols < side) b = BoardBounds(b.minRow, b.maxRow, b.minCol - 1, b.maxCol + 1)
        return b
    }

    companion object {
        fun of(cells: Collection<Cell>): BoardBounds? {
            if (cells.isEmpty()) return null
            var r0 = Int.MAX_VALUE
            var r1 = Int.MIN_VALUE
            var c0 = Int.MAX_VALUE
            var c1 = Int.MIN_VALUE
            for (c in cells) {
                if (c.row < r0) r0 = c.row
                if (c.row > r1) r1 = c.row
                if (c.col < c0) c0 = c.col
                if (c.col > c1) c1 = c.col
            }
            return BoardBounds(r0, r1, c0, c1)
        }
    }
}

/**
 * `screen = world * scale + offset`.
 *
 * The canvas applies this once (`translate` then `scale`) and then draws
 * everything in world units, so tile art never lands on fractional destination
 * rects — that is what keeps hairline gaps from opening between tiles at
 * arbitrary zoom.
 */
data class BoardTransform(
    val scale: Float = 1f,
    val offsetX: Float = 0f,
    val offsetY: Float = 0f,
) {
    fun worldToScreenX(wx: Float): Float = wx * scale + offsetX
    fun worldToScreenY(wy: Float): Float = wy * scale + offsetY

    fun screenToWorldX(sx: Float): Float = (sx - offsetX) / scale
    fun screenToWorldY(sy: Float): Float = (sy - offsetY) / scale

    /** The engine cell under a screen point. Always defined (the plane is tiled). */
    fun cellAt(sx: Float, sy: Float): Cell {
        val wx = screenToWorldX(sx)
        val wy = screenToWorldY(sy)
        return Cell(row = floor(wy / TILE).toInt(), col = floor(wx / TILE).toInt())
    }

    /**
     * One `detectTransformGestures` step. [zoom] is the *relative* pinch factor;
     * the point under [centroidX]/[centroidY] stays put (after clamping), which
     * is what makes pinch feel anchored rather than springy.
     */
    fun gesture(
        centroidX: Float,
        centroidY: Float,
        panX: Float,
        panY: Float,
        zoom: Float,
    ): BoardTransform {
        val target = (scale * zoom).coerceIn(MIN_SCALE, MAX_SCALE)
        val actual = if (scale == 0f) 1f else target / scale
        return BoardTransform(
            scale = target,
            offsetX = centroidX - (centroidX - offsetX) * actual + panX,
            offsetY = centroidY - (centroidY - offsetY) * actual + panY,
        )
    }

    /**
     * True when the whole cell square is inside the *usable* viewport.
     *
     * The canvas runs edge to edge under the HUD and the action/status bars, so its
     * raw height is not what the player can see: a cell tucked under the top HUD is
     * "visible" by pixel arithmetic and invisible in fact. [insetTop] / [insetBottom]
     * carve those overlays back off, so the auto-recentre fires for a cell that has
     * slipped behind one. [margin] is the extra comfort slack on all four sides.
     */
    fun isCellVisible(
        cell: Cell,
        viewW: Float,
        viewH: Float,
        margin: Float = 0f,
        insetTop: Float = 0f,
        insetBottom: Float = 0f,
    ): Boolean {
        val x0 = worldToScreenX(cell.col * TILE)
        val y0 = worldToScreenY(cell.row * TILE)
        val x1 = x0 + TILE * scale
        val y1 = y0 + TILE * scale
        return x0 >= margin &&
            y0 >= insetTop + margin &&
            x1 <= viewW - margin &&
            y1 <= viewH - insetBottom - margin
    }

    companion object {
        /** Scale-preserving recentre so [cell] sits in the middle of the viewport. */
        fun centeredOn(cell: Cell, scale: Float, viewW: Float, viewH: Float): BoardTransform {
            val cx = (cell.col + 0.5f) * TILE
            val cy = (cell.row + 0.5f) * TILE
            return BoardTransform(scale, viewW / 2f - cx * scale, viewH / 2f - cy * scale)
        }

        /**
         * Fit [bounds] into the viewport with [padding] px of slack, centred.
         * Scale is clamped to [MIN_SCALE]..[MAX_SCALE], so a 1-tile board opens
         * at 3x rather than absurdly zoomed.
         */
        fun fit(
            bounds: BoardBounds,
            viewW: Float,
            viewH: Float,
            padding: Float = 24f,
        ): BoardTransform {
            val w = bounds.cols * TILE
            val h = bounds.rows * TILE
            val availW = max(1f, viewW - 2 * padding)
            val availH = max(1f, viewH - 2 * padding)
            val scale = min(availW / w, availH / h).coerceIn(MIN_SCALE, MAX_SCALE)
            val cx = (bounds.minCol * TILE + w / 2f)
            val cy = (bounds.minRow * TILE + h / 2f)
            return BoardTransform(scale, viewW / 2f - cx * scale, viewH / 2f - cy * scale)
        }
    }
}

/** Straight-line interpolation, for the gentle auto-recentre after an AI move. */
fun lerpTransform(a: BoardTransform, b: BoardTransform, t: Float): BoardTransform =
    BoardTransform(
        scale = a.scale + (b.scale - a.scale) * t,
        offsetX = a.offsetX + (b.offsetX - a.offsetX) * t,
        offsetY = a.offsetY + (b.offsetY - a.offsetY) * t,
    )

/**
 * Hit-test for a meeple slot dot. Slots are given as world-space centres; the
 * closest one within [radius] world units wins (nearest-wins, not
 * first-wins — adjacent farmer corners are only 0.25*TILE apart and a fat finger
 * covers several).
 */
fun <T> nearestWithin(
    items: List<T>,
    wx: Float,
    wy: Float,
    radius: Float,
    centre: (T) -> Pair<Float, Float>,
): T? {
    var best: T? = null
    var bestD2 = radius * radius
    for (item in items) {
        val (px, py) = centre(item)
        val dx = px - wx
        val dy = py - wy
        val d2 = dx * dx + dy * dy
        if (d2 <= bestD2) {
            bestD2 = d2
            best = item
        }
    }
    return best
}
