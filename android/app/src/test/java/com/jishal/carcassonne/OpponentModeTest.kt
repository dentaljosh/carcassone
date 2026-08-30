package com.jishal.carcassonne

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The remote-opponent selector, and the one property that protects the program.
 *
 * Two things are pinned here and neither is cosmetic:
 *
 * 1. **THE GOLDEN GATE** — with [OpponentMode.CHAMPION] selected,
 *    [Difficulty.newGameConfig] emits exactly the config it emitted before the
 *    remote opponent existed, for every difficulty stop: same keys, same values,
 *    no extras. The E4 stream is one continuous measurement of the owner against
 *    the champion; if this build changed the champion game's config in any way,
 *    that continuity would break silently and every trend read across the
 *    boundary would be wrong. The expected strings are written out LITERALLY
 *    rather than derived, because a derived expectation would move whenever the
 *    thing it is guarding moved.
 *
 * 2. **THE LABEL** — a remote game names an opponent that is not `"champion"`,
 *    so `scripts/e4_archives.py` (absent-or-different EXCLUDES) can keep it out
 *    of the owner-vs-champion anchor. `A = +13.265 pts/game` is the single
 *    number the Carcasum session's whole discriminator is chained through; one
 *    Carcasum game pooled into it moves the answer in the direction that
 *    manufactures the headline.
 */
class OpponentModeTest {

    private fun cfg(
        d: Difficulty,
        mode: OpponentMode = OpponentMode.DEFAULT,
        url: String = OpponentMode.DEFAULT_URL,
        seed: Int = 7,
        seat: Int = 0,
        tie: TieArbLevel = TieArbLevel.DEFAULT,
    ) = d.newGameConfig(
        seed = seed, humanPlayer = seat, tieArbLevel = tie,
        opponentMode = mode, remoteUrl = url,
    )

    // -- 1. the golden gate ------------------------------------------------- //

    /**
     * The config as a canonical, order-independent string: every key sorted,
     * `key=value` joined by `|`.
     *
     * ⚠️ Why not compare the raw JSON string. On DEVICE, `org.json.JSONObject` is
     * backed by a `LinkedHashMap` and preserves insertion order, so the raw text
     * is stable — but the JVM stub these unit tests run against is not, and it
     * reorders `seed` and `human_player`. A raw-text pin therefore fails for a
     * reason that has nothing to do with the app. Canonicalising keeps the pin
     * LITERAL (the expectations below are written out, not derived) while making
     * it a statement about the config's CONTENT, which is the property the bridge
     * actually reads.
     */
    private fun canon(s: String): String {
        val o = JSONObject(s)
        return o.keys().asSequence().sorted().joinToString("|") { k -> "$k=${o.get(k)}" }
    }

    @Test
    fun `champion mode emits an unchanged config for every preset`() {
        // Exactly what the app produced before the remote opponent existed.
        val expected = mapOf(
            Difficulty.INSTANT to
                "human_player=0|opponent=tier1|seed=7|tiearb_level=b64|verify=true",
            Difficulty.FAST to
                "human_player=0|k_dets=2|opponent=champion|seed=7|sims=172|" +
                "tiearb_level=b64|verify=true",
            Difficulty.MEDIUM to
                "human_player=0|k_dets=4|opponent=champion|seed=7|sims=172|" +
                "tiearb_level=b64|verify=true",
            Difficulty.STRONG to
                "human_player=0|k_dets=4|opponent=champion|seed=7|sims=344|" +
                "tiearb_level=b64|verify=true",
            Difficulty.CHAMPION to
                "human_player=0|opponent=champion|seed=7|tiearb_level=b64|verify=true",
        )
        for ((d, want) in expected) {
            assertEquals("preset ${d.id} config changed", want, canon(cfg(d)))
        }
    }

    @Test
    fun `champion mode is what the default argument gives`() {
        // i.e. every existing call site that does NOT pass opponentMode keeps
        // producing the champion config.
        for (d in Difficulty.entries) {
            assertEquals(
                d.newGameConfig(seed = 7, humanPlayer = 0),
                cfg(d, OpponentMode.CHAMPION),
            )
        }
    }

    @Test
    fun `champion mode never sends the remote keys`() {
        for (d in Difficulty.entries) {
            val c = JSONObject(cfg(d, OpponentMode.CHAMPION))
            assertFalse("remote_url leaked into a champion game", c.has("remote_url"))
            assertFalse("remote_budget_ms leaked", c.has("remote_budget_ms"))
        }
    }

    // -- 2. the label ------------------------------------------------------- //

    @Test
    fun `remote mode overrides the opponent for every preset`() {
        for (d in Difficulty.entries) {
            val c = JSONObject(cfg(d, OpponentMode.REMOTE_CARCASUM))
            assertEquals(OpponentMode.BRIDGE_REMOTE, c.getString("opponent"))
            assertNotEquals(
                "a remote game must NEVER be stamped as the champion",
                "champion", c.getString("opponent"),
            )
            assertEquals(OpponentMode.DEFAULT_URL, c.getString("remote_url"))
            assertEquals(OpponentMode.BUDGET_MS, c.getInt("remote_budget_ms"))
        }
    }

    @Test
    fun `remote mode carries the configured url`() {
        val c = JSONObject(
            cfg(Difficulty.CHAMPION, OpponentMode.REMOTE_CARCASUM, url = "http://10.0.0.5:9000"))
        assertEquals("http://10.0.0.5:9000", c.getString("remote_url"))
    }

    @Test
    fun `the budget is the calibrated 5000ms and is not a UI knob`() {
        // Changing it changes the opponent, and the session's B anchor
        // (champion - Carcasum@5s) stops applying. There is deliberately no
        // setter anywhere in the app.
        assertEquals(5000, OpponentMode.BUDGET_MS)
    }

    // -- selector plumbing --------------------------------------------------- //

    @Test
    fun `champion is the default and unknown ids fall back to it`() {
        assertEquals(OpponentMode.CHAMPION, OpponentMode.DEFAULT)
        assertEquals(OpponentMode.CHAMPION, OpponentMode.fromId(null))
        assertEquals(OpponentMode.CHAMPION, OpponentMode.fromId(""))
        assertEquals(OpponentMode.CHAMPION, OpponentMode.fromId("no-such-mode"))
        // An upgraded install, a corrupt preferences file and a rolled-back build
        // must all land on the opponent every E4 archive is about.
    }

    @Test
    fun `ids round trip`() {
        for (m in OpponentMode.entries) assertEquals(m, OpponentMode.fromId(m.id))
    }

    @Test
    fun `bridgeOpponent is null for champion so the preset decides`() {
        assertEquals(null, OpponentMode.CHAMPION.bridgeOpponent)
        assertEquals(OpponentMode.BRIDGE_REMOTE, OpponentMode.REMOTE_CARCASUM.bridgeOpponent)
    }

    @Test
    fun `url validation accepts real addresses and rejects junk`() {
        assertTrue(OpponentMode.looksLikeUrl(OpponentMode.DEFAULT_URL))
        assertTrue(OpponentMode.looksLikeUrl("http://100.109.88.103:8971"))
        assertTrue(OpponentMode.looksLikeUrl("https://laptop-wsl:8971"))
        assertTrue(OpponentMode.looksLikeUrl("  http://x:1  "))
        assertFalse(OpponentMode.looksLikeUrl(""))
        assertFalse(OpponentMode.looksLikeUrl("100.109.88.103:8971"))
        assertFalse(OpponentMode.looksLikeUrl("http://"))
        assertFalse(OpponentMode.looksLikeUrl("http://a b"))
    }
}
