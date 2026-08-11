package com.jishal.carcassonne

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The board canvas cannot be exercised without a device, so the parts of it that
 * are *arithmetic* are factored into [BoardGeometry] and pinned here instead.
 * These are the failures that would otherwise only show up as "taps land on the
 * wrong square" on a phone.
 */
class BoardGeometryTest {

    private val eps = 1e-3f

    // -- round trip ----------------------------------------------------------

    @Test
    fun `world screen round trip is identity`() {
        val t = BoardTransform(scale = 1.7f, offsetX = -321.5f, offsetY = 88f)
        assertEquals(123.5f, t.screenToWorldX(t.worldToScreenX(123.5f)), eps)
        assertEquals(-42.25f, t.screenToWorldY(t.worldToScreenY(-42.25f)), eps)
    }

    // -- hit testing ---------------------------------------------------------

    @Test
    fun `cellAt maps the centre of a drawn tile back to that tile`() {
        val t = BoardTransform(scale = 2f, offsetX = 30f, offsetY = -70f)
        for (row in intArrayOf(0, 3, 17, 34)) {
            for (col in intArrayOf(0, 5, 21, 34)) {
                val sx = t.worldToScreenX((col + 0.5f) * TILE)
                val sy = t.worldToScreenY((row + 0.5f) * TILE)
                assertEquals(Cell(row, col), t.cellAt(sx, sy))
            }
        }
    }

    /** `row` follows `y` and `col` follows `x` — swapping them is the classic bug. */
    @Test
    fun `cellAt does not transpose row and col`() {
        val t = BoardTransform(scale = 1f, offsetX = 0f, offsetY = 0f)
        // world x = 250 -> col 2 ; world y = 550 -> row 5
        assertEquals(Cell(row = 5, col = 2), t.cellAt(250f, 550f))
    }

    @Test
    fun `cellAt floors toward negative infinity`() {
        val t = BoardTransform(scale = 1f, offsetX = 0f, offsetY = 0f)
        // -0.5 of a tile must be cell -1, not cell 0 (integer truncation bug).
        assertEquals(Cell(row = -1, col = -1), t.cellAt(-50f, -50f))
        assertEquals(Cell(row = 0, col = 0), t.cellAt(1f, 1f))
    }

    // -- gestures ------------------------------------------------------------

    @Test
    fun `pinch keeps the point under the centroid fixed`() {
        val t = BoardTransform(scale = 1f, offsetX = 12f, offsetY = -8f)
        val cx = 400f
        val cy = 900f
        val before = t.screenToWorldX(cx) to t.screenToWorldY(cy)
        val after = t.gesture(cx, cy, panX = 0f, panY = 0f, zoom = 1.6f)
        assertEquals(before.first, after.screenToWorldX(cx), eps)
        assertEquals(before.second, after.screenToWorldY(cy), eps)
        assertEquals(1.6f, after.scale, eps)
    }

    @Test
    fun `zoom is clamped and the anchor still holds at the clamp`() {
        val t = BoardTransform(scale = 2.5f, offsetX = 0f, offsetY = 0f)
        val zoomedIn = t.gesture(100f, 100f, 0f, 0f, zoom = 100f)
        assertEquals(MAX_SCALE, zoomedIn.scale, eps)
        assertEquals(t.screenToWorldX(100f), zoomedIn.screenToWorldX(100f), eps)

        val zoomedOut = BoardTransform(scale = 0.5f).gesture(0f, 0f, 0f, 0f, zoom = 0.001f)
        assertEquals(MIN_SCALE, zoomedOut.scale, eps)
    }

    @Test
    fun `pan translates without changing scale`() {
        val t = BoardTransform(scale = 1.25f, offsetX = 5f, offsetY = 5f)
        val p = t.gesture(0f, 0f, panX = 40f, panY = -15f, zoom = 1f)
        assertEquals(1.25f, p.scale, eps)
        assertEquals(45f, p.offsetX, eps)
        assertEquals(-10f, p.offsetY, eps)
    }

    // -- fitting / centring --------------------------------------------------

    @Test
    fun `fit centres the bounding box in the viewport`() {
        val bounds = BoardBounds(minRow = 10, maxRow = 14, minCol = 20, maxCol = 24)
        val t = BoardTransform.fit(bounds, viewW = 1000f, viewH = 2000f, padding = 20f)
        val cx = t.worldToScreenX((20 + 2.5f) * TILE)
        val cy = t.worldToScreenY((10 + 2.5f) * TILE)
        assertEquals(500f, cx, eps)
        assertEquals(1000f, cy, eps)
        // 5 tiles = 500 world units into 960 usable px -> 1.92, under MAX_SCALE.
        assertEquals(1.92f, t.scale, eps)
    }

    @Test
    fun `fit clamps scale for a tiny board`() {
        val t = BoardTransform.fit(BoardBounds(0, 0, 0, 0), 1000f, 1000f, padding = 0f)
        assertEquals(MAX_SCALE, t.scale, eps)
    }

    @Test
    fun `fit of a whole 35x35 board stays above the minimum scale`() {
        val t = BoardTransform.fit(BoardBounds(0, 34, 0, 34), 1080f, 1920f)
        assertEquals(MIN_SCALE, t.scale, eps)
    }

    @Test
    fun `centeredOn puts the cell centre at the viewport centre`() {
        val t = BoardTransform.centeredOn(Cell(7, 3), scale = 1.4f, viewW = 800f, viewH = 600f)
        assertEquals(400f, t.worldToScreenX(3.5f * TILE), eps)
        assertEquals(300f, t.worldToScreenY(7.5f * TILE), eps)
        assertEquals(1.4f, t.scale, eps)
    }

    @Test
    fun `isCellVisible is true for a centred cell and false once panned away`() {
        val cell = Cell(4, 4)
        val t = BoardTransform.centeredOn(cell, 1f, 800f, 800f)
        assertTrue(t.isCellVisible(cell, 800f, 800f, margin = 8f))
        val panned = t.gesture(0f, 0f, panX = -5000f, panY = 0f, zoom = 1f)
        assertFalse(panned.isCellVisible(cell, 800f, 800f, margin = 8f))
    }

    /** A cell only half in view must count as NOT visible, or auto-recentre never fires. */
    @Test
    fun `isCellVisible is false when the cell straddles the edge`() {
        val t = BoardTransform(scale = 1f, offsetX = -50f, offsetY = 0f)
        assertFalse(t.isCellVisible(Cell(0, 0), viewW = 800f, viewH = 800f))
    }

    // -- bounds --------------------------------------------------------------

    @Test
    fun `bounds of a cell collection`() {
        val b = BoardBounds.of(listOf(Cell(3, 9), Cell(-1, 4), Cell(7, 4)))!!
        assertEquals(-1, b.minRow)
        assertEquals(7, b.maxRow)
        assertEquals(4, b.minCol)
        assertEquals(9, b.maxCol)
        assertEquals(9, b.rows)
        assertEquals(6, b.cols)
    }

    @Test
    fun `bounds of nothing is null`() {
        assertNull(BoardBounds.of(emptyList()))
    }

    @Test
    fun `expanded grows every side`() {
        val b = BoardBounds(5, 5, 5, 5).expanded(2)
        assertEquals(BoardBounds(3, 7, 3, 7), b)
    }

    @Test
    fun `atLeast grows symmetrically to the requested span`() {
        val b = BoardBounds(10, 10, 10, 10).atLeast(7)
        assertTrue(b.rows >= 7)
        assertTrue(b.cols >= 7)
        // still centred on the original cell
        assertEquals(10, (b.minRow + b.maxRow) / 2)
        assertEquals(10, (b.minCol + b.maxCol) / 2)
    }

    @Test
    fun `atLeast leaves a big board alone`() {
        val b = BoardBounds(0, 20, 0, 20)
        assertEquals(b, b.atLeast(7))
    }

    // -- slot hit testing ----------------------------------------------------

    @Test
    fun `nearestWithin picks the closer of two adjacent farmer corners`() {
        val cell = Cell(2, 2)
        val topLeft = slotCentre(cell, 0.25f, 0.175f)
        val topRight = slotCentre(cell, 0.75f, 0.175f)
        val slots = listOf("tl" to topLeft, "tr" to topRight)

        // A tap a little right of TOP_LEFT must still resolve to TOP_LEFT.
        val wx = topLeft.first + 8f
        val wy = topLeft.second
        val hit = nearestWithin(slots, wx, wy, 0.20f * TILE) { it.second }
        assertNotNull(hit)
        assertEquals("tl", hit!!.first)

        // Dead centre of the tile is out of range of both corners.
        val centre = slotCentre(cell, 0.5f, 0.5f)
        assertNull(nearestWithin(slots, centre.first, centre.second, 0.20f * TILE) { it.second })
    }

    @Test
    fun `slotCentre puts row on y and col on x`() {
        val (x, y) = slotCentre(Cell(row = 3, col = 8), 0.5f, 0.825f)
        assertEquals(8 * TILE + 0.5f * TILE, x, eps)
        assertEquals(3 * TILE + 0.825f * TILE, y, eps)
    }

    // -- interpolation -------------------------------------------------------

    @Test
    fun `lerpTransform hits both endpoints`() {
        val a = BoardTransform(1f, 0f, 0f)
        val b = BoardTransform(2f, 100f, -50f)
        assertEquals(a, lerpTransform(a, b, 0f))
        assertEquals(b.scale, lerpTransform(a, b, 1f).scale, eps)
        assertEquals(50f, lerpTransform(a, b, 0.5f).offsetX, eps)
    }
}

class EmptyBoardBoundsTest {
    private fun state(board: List<PlacedTile>, legal: LegalBlock) = GameState(
        generation = 1, phase = "tiles", turn = 0, currentPlayer = 0,
        humanPlayer = 0, aiPlayer = 1, isHumanTurn = true,
        scores = listOf(0, 0), meeplesFree = listOf(7, 7),
        deckRemaining = 72, tilesRemaining = 72, nextTile = null,
        board = board, meeples = emptyList(), legal = legal,
        opponentName = "champ", budgetNote = null, aiLastTile = null,
        aiLastMove = null, isTerminated = false, result = null,
    )

    @org.junit.Test
    fun emptyBoardFallsBackToLegalCells() {
        // "You first" start: no placed tiles, one legal start cell — the fit
        // transform must still get bounds or the board renders off-screen.
        val st = state(
            board = emptyList(),
            legal = LegalBlock(tileCells = listOf(
                LegalTileCell(row = 6, col = 15, rotations = listOf(0),
                              actionIds = listOf(0)))),
        )
        val b = st.boundsWithMargin()
        org.junit.Assert.assertNotNull(b)
        org.junit.Assert.assertTrue(b!!.minRow <= 6 && 6 <= b.maxRow && b.minCol <= 15 && 15 <= b.maxCol)
    }

    @org.junit.Test
    fun trulyEmptyStateStillNull() {
        org.junit.Assert.assertNull(
            state(board = emptyList(), legal = LegalBlock()).boundsWithMargin())
    }
}
