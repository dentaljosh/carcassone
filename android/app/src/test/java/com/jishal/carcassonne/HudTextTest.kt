package com.jishal.carcassonne

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The HUD counters and the player-facing copy — the round-2 playtest's minor
 * findings, which are all "the app is speaking engine at the player".
 */
class HudTextTest {

    private fun state(phase: String, tilesRemaining: Int, placed: Int) = GameState(
        generation = 1, phase = phase, turn = 0, currentPlayer = 0,
        humanPlayer = 0, aiPlayer = 1, isHumanTurn = true,
        scores = listOf(0, 0), meeplesFree = listOf(7, 7),
        deckRemaining = tilesRemaining, tilesRemaining = tilesRemaining, nextTile = null,
        board = List(placed) { PlacedTile(row = it, col = 0, image = null, turns = 0) },
        meeples = emptyList(), legal = LegalBlock(),
        opponentName = "Champion", budgetNote = null, aiLastTile = null,
        aiLastMove = null, isTerminated = false, result = null,
    )

    // -- tiles left / placed -------------------------------------------------

    /**
     * The reported symptom: `36 tiles left` beside `37 placed`, which sums to one
     * MORE than the deck for the whole meeple sub-phase and then drops back.
     *
     * The cause is in the engine, not the bridge: `StateUpdater.play_tile` puts
     * the tile on the board but does NOT clear `next_tile` — that happens later,
     * in `draw_tile`, at the end of the meeple phase. So `len(deck) + 1` counts
     * the just-placed tile a second time.
     */
    @Test
    fun `tiles left plus placed is constant across the whole turn`() {
        // A turn, in the three states the player can observe it in.
        val beforePlacing = state(phase = "tiles", tilesRemaining = 37, placed = 36)
        val meepleSubPhase = state(phase = "meeples", tilesRemaining = 37, placed = 37)
        val nextPlayer = state(phase = "tiles", tilesRemaining = 36, placed = 37)

        val total = beforePlacing.tilesLeft + beforePlacing.board.size
        assertEquals(total, meepleSubPhase.tilesLeft + meepleSubPhase.board.size)
        assertEquals(total, nextPlayer.tilesLeft + nextPlayer.board.size)
    }

    @Test
    fun `the meeple sub-phase does not count the tile already on the board`() {
        assertEquals(36, state("meeples", tilesRemaining = 37, placed = 37).tilesLeft)
        // The tile phase is left alone: there the tile in hand really is in hand.
        assertEquals(37, state("tiles", tilesRemaining = 37, placed = 36).tilesLeft)
    }

    /** The last tile of the game: no negative count on the way out. */
    @Test
    fun `tiles left never goes negative`() {
        assertEquals(0, state("meeples", tilesRemaining = 0, placed = 72).tilesLeft)
    }

    @Test
    fun `labels singularise`() {
        assertEquals("1 tile left", tilesLeftLabel(1))
        assertEquals("2 tiles left", tilesLeftLabel(2))
        assertEquals("0 tiles left", tilesLeftLabel(0))
    }

    // -- action wording ------------------------------------------------------

    @Test
    fun `tile placements lose the engine coordinate syntax`() {
        assertEquals(
            "placed a tile (r6 c15)",
            MoveText.humanizeAction("tile @ (+6, +15) rot=0"),
        )
        assertEquals(
            "placed a tile (r-3 c15)",
            MoveText.humanizeAction("tile @ (-3, +15) rot=3"),
        )
    }

    @Test
    fun `meeple placements read as board language`() {
        assertEquals("meeple on the top edge", MoveText.humanizeAction("NORMAL on TOP"))
        assertEquals(
            "farmer on the bottom-left field",
            MoveText.humanizeAction("FARMER on BOTTOM_LEFT"),
        )
        assertEquals("meeple in the middle", MoveText.humanizeAction("NORMAL on CENTER"))
        assertEquals("big farmer on the top-right field",
            MoveText.humanizeAction("BIG_FARMER on TOP_RIGHT"))
    }

    @Test
    fun `passes and skips read as sentences`() {
        assertEquals("no meeple", MoveText.humanizeAction("skip meeple"))
        assertEquals(
            "passed — no legal placement",
            MoveText.humanizeAction("pass (no legal placement)"),
        )
    }

    /** An unrecognised shape is passed through, not mangled into a wrong claim. */
    @Test
    fun `unknown strings survive verbatim`() {
        assertEquals("something new", MoveText.humanizeAction("something new"))
        assertEquals("", MoveText.humanizeAction("   "))
    }

    @Test
    fun `no engine vocabulary survives humanising`() {
        val raws = listOf(
            "tile @ (+6, +15) rot=0", "NORMAL on TOP", "FARMER on BOTTOM_LEFT",
            "skip meeple", "pass (no legal placement)",
        )
        for (raw in raws) {
            val out = MoveText.humanizeAction(raw)
            assertFalse(out, out.any { it.isUpperCase() })
            assertFalse(out, "rot=" in out)
            assertFalse(out, "_" in out)
        }
    }

    // -- the rest of the copy ------------------------------------------------

    /** The rotate button is HIDDEN at one rotation, so the copy must not name it. */
    @Test
    fun `the rotation hint does not promise a button that is not there`() {
        val single = MoveText.tilePhaseHint(index = 0, rotationCount = 1)
        assertFalse(single, "⟳" in single)
        assertTrue(single, "✓" in single)

        val many = MoveText.tilePhaseHint(index = 1, rotationCount = 3)
        assertTrue(many, "⟳" in many)
        assertEquals("Rotation 2 of 3 — ✓ to place, ⟳ to rotate", many)
    }

    /** A Tier-1 game must not report its moves as the champion's. */
    @Test
    fun `the last-move line names the actual opponent`() {
        val line = MoveText.lastMoveLine("Tier-1", "NORMAL on TOP", 1.25)
        assertTrue(line, line.startsWith("Last Tier-1 move:"))
        assertFalse(line, "champion" in line.lowercase())
        assertTrue(line, line.endsWith("(1.3s)"))
    }

    @Test
    fun `the opponent short name drops the budget parenthetical`() {
        assertEquals("Champion", MoveText.shortOpponent("Champion(weakened k4x172)"))
        assertEquals("Tier-1", MoveText.shortOpponent("Tier-1"))
        // The remote opponent names itself the same way, so the same cut has to
        // leave an identity short enough for the 14-char HUD chip.
        assertEquals("Carcasum", MoveText.shortOpponent("Carcasum(103.5k playouts)"))
    }

    /**
     * ⛔ The empty-name fallback is "Opponent", NOT "Champion" (2026-09-02 text
     * audit). It is reached only when the bridge supplied no name — the first
     * frames of a session, or a failed start — and in a remote game calling the
     * opponent "Champion" there is exactly the class of stale copy this build was
     * asked to remove. No word in the app may name the opponent from a constant.
     */
    @Test
    fun `an unnamed opponent is never called the champion`() {
        assertEquals("Opponent", MoveText.shortOpponent(""))
        assertEquals("Opponent", MoveText.shortOpponent("   "))
    }

    // -- tile descriptions ---------------------------------------------------

    @Test
    fun `tile descriptions lose the engine underscores`() {
        assertEquals("city bottom road", MoveText.tileDescription("city_bottom_road"))
        assertEquals("straight road", MoveText.tileDescription("straight_road"))
    }

    /** A pennant is a scoring fact, so it is named rather than left as "shield". */
    @Test
    fun `a shield reads as a pennant`() {
        assertEquals(
            "city bottom road · pennant",
            MoveText.tileDescription("city_bottom_road_shield"),
        )
    }

    /**
     * A garden carries no rule at all in the locked 2p Base+Farmers scope, which
     * is exactly why the bag groups a garden face with its plain twin. The wording
     * has to agree with the grouping, or the same tile reads as two things.
     */
    @Test
    fun `a garden is dropped, matching the bag grouping`() {
        assertEquals(
            MoveText.tileDescription("straight_road"),
            MoveText.tileDescription("straight_road_flowers"),
        )
    }

    @Test
    fun `an elapsed-less move prints no timing`() {
        assertEquals(
            "Last Champion move: no meeple",
            MoveText.lastMoveLine("Champion", "skip meeple", null),
        )
    }
}
