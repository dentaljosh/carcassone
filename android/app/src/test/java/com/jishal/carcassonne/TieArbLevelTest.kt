package com.jishal.carcassonne

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The tie-arbiter level -> `new_game` config mapping.
 *
 * The ids ("b64"/"b16"/"b8"/"off") must match the bridge's `TIEARB_LEVELS`
 * vocabulary byte-for-byte — that is the one thing every test here guards.
 */
class TieArbLevelTest {

    @Test
    fun `b64 is the default`() {
        assertEquals(TieArbLevel.B64, TieArbLevel.DEFAULT)
        assertEquals("b64", TieArbLevel.DEFAULT.id)
    }

    /**
     * ⚠️ THE MIGRATION THAT MAKES THE 2026-08-29 B64 RULING REACH A PHONE.
     *
     * The device this ships to has `tie_arb_level = "b32"` already persisted in
     * its DataStore. B32 was retired from the menu rather than migrated, so the
     * stored value must resolve through the unknown-id fall-through to the new
     * default — otherwise the owner's phone keeps playing B32 and the ruling
     * silently does nothing. This is the whole reason no key rename was needed.
     */
    @Test
    fun `a persisted b32 from the retired rung upgrades to the default`() {
        assertEquals(TieArbLevel.B64, TieArbLevel.fromId("b32"))
    }

    @Test
    fun `ids round trip`() {
        for (l in TieArbLevel.entries) assertEquals(l, TieArbLevel.fromId(l.id))
    }

    @Test
    fun `fromId resolves a known id`() {
        assertEquals(TieArbLevel.B16, TieArbLevel.fromId("b16"))
    }

    @Test
    fun `fromId falls back to the default on an unknown id`() {
        assertEquals(TieArbLevel.DEFAULT, TieArbLevel.fromId("bogus"))
    }

    @Test
    fun `fromId falls back to the default on null`() {
        assertEquals(TieArbLevel.DEFAULT, TieArbLevel.fromId(null))
    }

    @Test
    fun `slider index maps to the four stops weakest-first`() {
        assertEquals(4, TieArbLevel.entries.size)
        assertEquals(
            listOf(TieArbLevel.OFF, TieArbLevel.B8, TieArbLevel.B16, TieArbLevel.B64),
            (0..3).map { TieArbLevel.fromIndex(it) },
        )
        // Out-of-range slider values clamp rather than crash.
        assertEquals(TieArbLevel.OFF, TieArbLevel.fromIndex(-3))
        assertEquals(TieArbLevel.B64, TieArbLevel.fromIndex(99))
    }

    // -- the new_game config carries the chosen level ------------------------

    @Test
    fun `new_game config carries tiearb_level for b64`() {
        val c = JSONObject(
            Difficulty.CHAMPION.newGameConfig(
                seed = 7, humanPlayer = 0, tieArbLevel = TieArbLevel.B64,
            )
        )
        assertEquals("b64", c.getString("tiearb_level"))
    }

    @Test
    fun `new_game config carries tiearb_level for off`() {
        val c = JSONObject(
            Difficulty.CHAMPION.newGameConfig(
                seed = 7, humanPlayer = 0, tieArbLevel = TieArbLevel.OFF,
            )
        )
        assertEquals("off", c.getString("tiearb_level"))
    }
}
