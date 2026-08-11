package com.jishal.carcassonne

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The camera arithmetic behind the round-2 playtest's biggest complaint: the fit
 * ran once, at game start, and by ~50 tiles half the board was off-screen or
 * behind the status panel with no way to get it back.
 *
 * Two separate defects live in here, and both are pinned:
 *
 *  1. nothing ever asked "does the board still fit?" — only "is the newest tile
 *     on screen?", which a board twice the size of the viewport passes happily;
 *  2. `fit` measured against the RAW canvas, but the canvas runs edge to edge
 *     underneath the floating status/action chrome, so the bottom rows landed
 *     under it. In landscape that chrome is a much larger share of a much shorter
 *     viewport, which is why it showed up there first.
 */
class ViewportFitTest {

    private val eps = 1e-3f

    // A portrait phone with the HUD banners on top and the action + status strip
    // floating over the bottom, at roughly the measured heights.
    private val viewW = 1080f
    private val viewH = 1900f
    private val insetTop = 240f
    private val insetBottom = 380f

    private fun board(rows: Int, cols: Int, atRow: Int = 10, atCol: Int = 10) =
        BoardBounds(atRow, atRow + rows - 1, atCol, atCol + cols - 1)

    // -- the growing board ---------------------------------------------------

    /** The heart of it: a fit that was right for 7x7 is wrong for 20x20. */
    @Test
    fun `a fit taken at game start stops being visible once the board grows`() {
        val opening = board(7, 7)
        val t = BoardTransform.fit(opening, viewW, viewH, insetTop, insetBottom)
        assertTrue(t.isBoundsVisible(opening, viewW, viewH, 4f, insetTop, insetBottom))

        val midgame = board(20, 20, atRow = 4, atCol = 4)
        assertFalse(
            "the stale transform must be detected as no longer fitting",
            t.isBoundsVisible(midgame, viewW, viewH, 4f, insetTop, insetBottom),
        )

        // ...and re-fitting must fix it, which is the whole recovery path.
        val refit = BoardTransform.fit(midgame, viewW, viewH, insetTop, insetBottom)
        assertTrue(refit.isBoundsVisible(midgame, viewW, viewH, 4f, insetTop, insetBottom))
    }

    /**
     * The old rule, in isolation: a single cell can be comfortably centred while
     * the board around it is off-screen in every direction. This is exactly why
     * `isCellVisible` alone could not have caught the bug.
     */
    @Test
    fun `centring the newest tile does not imply the board is visible`() {
        val newest = Cell(12, 12)
        val t = BoardTransform.centeredOn(newest, 1.5f, viewW, viewH, insetTop, insetBottom)
        assertTrue(t.isCellVisible(newest, viewW, viewH, 12f, insetTop, insetBottom))
        assertFalse(
            t.isBoundsVisible(board(20, 20, atRow = 4, atCol = 4), viewW, viewH,
                4f, insetTop, insetBottom),
        )
    }

    // -- the overlay insets --------------------------------------------------

    /** Landscape (r2_29 / r2_31): fitting to the raw canvas hides the bottom rows. */
    @Test
    fun `fitting the raw viewport puts the bottom rows under the status panel`() {
        val landW = 2200f
        val landH = 1000f
        val landBottom = 300f
        val b = board(12, 12)

        val naive = BoardTransform.fit(b, landW, landH)          // no insets: the old call
        assertFalse(
            "this is the landscape defect — it must be detectable",
            naive.isBoundsVisible(b, landW, landH, 0f, 0f, landBottom),
        )

        val fixed = BoardTransform.fit(b, landW, landH, 0f, landBottom)
        assertTrue(fixed.isBoundsVisible(b, landW, landH, 0f, 0f, landBottom))
    }

    /** The inset band, not the canvas, is what gets centred on. */
    @Test
    fun `fit centres the board in the usable band`() {
        val b = board(5, 5)
        val t = BoardTransform.fit(b, viewW, viewH, insetTop, insetBottom)
        val cy = t.worldToScreenY((10 + 2.5f) * TILE)
        assertEquals(insetTop + (viewH - insetTop - insetBottom) / 2f, cy, eps)
        assertEquals(viewW / 2f, t.worldToScreenX((10 + 2.5f) * TILE), eps)
    }

    /** Insets shrink the usable height, so they can only shrink the scale. */
    @Test
    fun `insets never produce a larger scale than the raw viewport would`() {
        val b = board(14, 6)     // tall: height is the binding constraint
        val raw = BoardTransform.fit(b, viewW, viewH)
        val inset = BoardTransform.fit(b, viewW, viewH, insetTop, insetBottom)
        assertTrue(inset.scale < raw.scale)
    }

    @Test
    fun `centeredOn without insets is unchanged`() {
        val a = BoardTransform.centeredOn(Cell(7, 3), 1.4f, 800f, 600f)
        assertEquals(300f, a.worldToScreenY(7.5f * TILE), eps)
    }

    // -- the visibility predicate itself -------------------------------------

    @Test
    fun `isBoundsVisible spans the full extent of the box, not just its origin`() {
        // A transform that shows the top-left cell but runs off the right edge.
        val b = board(3, 3, atRow = 0, atCol = 0)
        val t = BoardTransform(scale = 4f, offsetX = 0f, offsetY = 0f)
        assertTrue(t.isCellVisible(Cell(0, 0), 1000f, 1000f))
        assertFalse(t.isBoundsVisible(b, 1000f, 1000f))   // 3 tiles * 100 * 4 = 1200 px
    }

    @Test
    fun `isCellVisible agrees with isBoundsVisible on a one-cell box`() {
        val t = BoardTransform(scale = 1.3f, offsetX = 40f, offsetY = -25f)
        for (cell in listOf(Cell(0, 0), Cell(5, 9), Cell(-2, 3))) {
            assertEquals(
                t.isCellVisible(cell, viewW, viewH, 6f, insetTop, insetBottom),
                t.isBoundsVisible(
                    BoardBounds(cell.row, cell.row, cell.col, cell.col),
                    viewW, viewH, 6f, insetTop, insetBottom,
                ),
            )
        }
    }

    /** A whole-board fit is clamped, not infinite — the recovery has a floor. */
    @Test
    fun `fit clamps rather than shrinking without bound`() {
        val huge = BoardBounds(0, 200, 0, 200)
        val t = BoardTransform.fit(huge, viewW, viewH, insetTop, insetBottom)
        assertEquals(MIN_SCALE, t.scale, eps)
    }
}

/**
 * The automatic-camera rule table ([cameraDecision]).
 *
 * These four rows are the whole behavioural contract of the fix, and the two that
 * matter most are the ones about a player who has taken manual control: the round-1
 * build had no such notion at all, and the naive repair (always re-fit) would have
 * replaced "the board runs away" with "the board yanks itself out of your hands".
 */
class CameraDecisionTest {

    @Test
    fun `nothing moves when everything is already in view`() {
        assertEquals(
            CameraMove.NONE,
            cameraDecision(boardVisible = true, focusVisible = true,
                userAdjusted = false, hasFocus = true),
        )
    }

    /** The reported bug: the board outgrew the viewport and nothing noticed. */
    @Test
    fun `an outgrown board is re-fitted`() {
        assertEquals(
            CameraMove.REFIT,
            cameraDecision(boardVisible = false, focusVisible = true,
                userAdjusted = false, hasFocus = true),
        )
    }

    /** Manual control is respected while the player can still see their move. */
    @Test
    fun `a player who took the camera is not yanked out of it`() {
        assertEquals(
            CameraMove.NONE,
            cameraDecision(boardVisible = false, focusVisible = true,
                userAdjusted = true, hasFocus = true),
        )
    }

    /** ...but not to the point of stranding them: once the camera has to move
     *  anyway, fitting beats panning blind. This is the escape hatch that stops
     *  one stray pan from disabling the auto-fit for the rest of the game. */
    @Test
    fun `manual control yields once the new tile is off-screen too`() {
        assertEquals(
            CameraMove.REFIT,
            cameraDecision(boardVisible = false, focusVisible = false,
                userAdjusted = true, hasFocus = true),
        )
    }

    /** The original round-1 behaviour, preserved for the case it was right for. */
    @Test
    fun `a fitting board with an off-screen tile only recentres`() {
        assertEquals(
            CameraMove.RECENTRE,
            cameraDecision(boardVisible = true, focusVisible = false,
                userAdjusted = false, hasFocus = true),
        )
    }

    /** No placement to centre on (a fresh session) — never a recentre. */
    @Test
    fun `no focus means no recentre`() {
        assertEquals(
            CameraMove.NONE,
            cameraDecision(boardVisible = true, focusVisible = true,
                userAdjusted = false, hasFocus = false),
        )
    }
}
