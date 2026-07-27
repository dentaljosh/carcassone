package com.jishal.carcassonne

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The preset -> `new_game` config mapping.
 *
 * The one that really matters is [`champion omits the budget keys entirely`]: the
 * bridge treats an ABSENT `sims`/`k_dets` as "use governance/PRODUCTION.yaml", so
 * a preset that helpfully sent `null` — or worse, a hardcoded 688 — would either
 * error or silently freeze the champion's budget at whatever this file said on
 * the day it was written.
 */
class DifficultyTest {

    private fun cfg(d: Difficulty, seed: Int = 7, seat: Int = 0) =
        JSONObject(d.newGameConfig(seed = seed, humanPlayer = seat))

    @Test
    fun `champion is the default`() {
        assertEquals(Difficulty.CHAMPION, Difficulty.DEFAULT)
        assertEquals(Difficulty.CHAMPION, Difficulty.fromId(null))
        assertEquals(Difficulty.CHAMPION, Difficulty.fromId("no-such-preset"))
    }

    @Test
    fun `ids round trip`() {
        for (d in Difficulty.entries) assertEquals(d, Difficulty.fromId(d.id))
    }

    @Test
    fun `slider index maps to the five stops in strength order`() {
        assertEquals(5, Difficulty.entries.size)
        assertEquals(
            listOf(
                Difficulty.INSTANT, Difficulty.FAST, Difficulty.MEDIUM,
                Difficulty.STRONG, Difficulty.CHAMPION,
            ),
            (0..4).map { Difficulty.fromIndex(it) },
        )
        // Out-of-range slider values clamp rather than crash.
        assertEquals(Difficulty.INSTANT, Difficulty.fromIndex(-3))
        assertEquals(Difficulty.CHAMPION, Difficulty.fromIndex(99))
    }

    @Test
    fun `champion omits the budget keys entirely`() {
        val c = cfg(Difficulty.CHAMPION)
        assertFalse("sims must be ABSENT, not null", c.has("sims"))
        assertFalse("k_dets must be ABSENT, not null", c.has("k_dets"))
        assertEquals("champion", c.getString("opponent"))
        assertTrue(c.getBoolean("verify"))
    }

    @Test
    fun `instant swaps the agent and sends no budget`() {
        val c = cfg(Difficulty.INSTANT)
        assertEquals("tier1", c.getString("opponent"))
        assertFalse(c.has("sims"))
        assertFalse(c.has("k_dets"))
        assertTrue(Difficulty.INSTANT.isTier1)
        // A different agent is NOT a weakened champion: no budget warning.
        assertFalse(Difficulty.INSTANT.belowChampionBudget)
    }

    @Test
    fun `weakened presets carry the plan's budgets`() {
        assertEquals(344, Difficulty.FAST.totalSims)
        assertEquals(688, Difficulty.MEDIUM.totalSims)
        assertEquals(1376, Difficulty.STRONG.totalSims)
        for (d in listOf(Difficulty.FAST, Difficulty.MEDIUM, Difficulty.STRONG)) {
            val c = cfg(d)
            assertEquals("champion", c.getString("opponent"))
            assertEquals(d.kDets, c.getInt("k_dets"))
            assertEquals(d.sims, c.getInt("sims"))
            assertTrue("${d.label} must be flagged below budget", d.belowChampionBudget)
        }
    }

    @Test
    fun `champion is the only unflagged champion stop`() {
        assertFalse(Difficulty.CHAMPION.belowChampionBudget)
        assertEquals(null, Difficulty.CHAMPION.totalSims)
    }

    @Test
    fun `seat and seed are passed through`() {
        val c = cfg(Difficulty.MEDIUM, seed = 4321, seat = 1)
        assertEquals(4321, c.getInt("seed"))
        assertEquals(1, c.getInt("human_player"))
    }

    // -- the manifest sheet's JSON unwrap ------------------------------------

    @Test
    fun `pretty manifest unwraps the envelope`() {
        val raw = JSONObject(
            mapOf(
                "ok" to true,
                "manifest_source" to "spec",
                "opponent_name" to "Champion",
                "manifest" to JSONObject(mapOf("champion_id" to "puct_x", "mode" to "fair")),
            )
        ).toString()
        val out = prettyManifest(raw)
        assertTrue(out.contains("source: spec"))
        assertTrue(out.contains("opponent: Champion"))
        assertTrue(out.contains("\"champion_id\": \"puct_x\""))
    }

    @Test
    fun `pretty manifest reports a bridge error instead of throwing`() {
        val raw = """{"ok":false,"error":{"code":"boom","message":"no yaml"}}"""
        val out = prettyManifest(raw)
        assertTrue(out.contains("boom"))
        assertTrue(out.contains("no yaml"))
    }

    @Test
    fun `seconds format drops the decimal above ten`() {
        assertEquals("1.5s", formatSeconds(1.52))
        assertEquals("12s", formatSeconds(12.4))
    }

    // -- the HUD's game-progress read-out ------------------------------------
    //
    // These replaced `turn N`, which printed a count of applied ACTIONS and so
    // stepped 2, 3, 6, 7, 10 through a normal game. Both labels below are derived
    // from quantities the player can count on the board.

    @Test
    fun `tiles-left label singularises`() {
        assertEquals("71 tiles left", tilesLeftLabel(71))
        assertEquals("1 tile left", tilesLeftLabel(1))
        assertEquals("0 tiles left", tilesLeftLabel(0))
    }

    @Test
    fun `tiles-placed label counts the board`() {
        // The start tile is on the board before anyone has moved.
        assertEquals("1 placed", tilesPlacedLabel(1))
        assertEquals("36 placed", tilesPlacedLabel(36))
    }

    // -- the Home screen's seed field ----------------------------------------

    @Test
    fun `a typed seed is used verbatim`() {
        assertEquals(12345, resolveSeed("12345") { 999 })
    }

    @Test
    fun `an unusable seed field falls back to a fresh random one`() {
        // Blank, zero and overflowing-Int all mean "just pick one" rather than
        // starting a game at seed 0 (or crashing on toInt()).
        assertEquals(999, resolveSeed("") { 999 })
        assertEquals(999, resolveSeed("0") { 999 })
        assertEquals(999, resolveSeed("999999999999") { 999 })
    }

    @Test
    fun `random seeds stay inside the typeable range`() {
        repeat(200) {
            val s = randomSeed()
            assertTrue("seed $s out of range", s in 1 until SEED_MAX)
        }
    }

    @Test
    fun `the new-game form defaults to a usable seat and seed`() {
        val form = NewGameForm()
        assertEquals(Seat.HUMAN_FIRST, form.seat)
        assertTrue(form.seedText.isNotEmpty())
        assertEquals(form.seedText.toInt(), resolveSeed(form.seedText) { -1 })
    }
}
