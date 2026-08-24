package com.jishal.carcassonne

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The tie-arbiter level -> `new_game` config mapping.
 *
 * The ids ("b32"/"b16"/"b8"/"off") must match the bridge's `TIEARB_LEVELS`
 * vocabulary byte-for-byte — that is the one thing every test here guards.
 */
class TieArbLevelTest {

    @Test
    fun `b32 is the default`() {
        assertEquals(TieArbLevel.B32, TieArbLevel.DEFAULT)
        assertEquals("b32", TieArbLevel.DEFAULT.id)
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
            listOf(TieArbLevel.OFF, TieArbLevel.B8, TieArbLevel.B16, TieArbLevel.B32),
            (0..3).map { TieArbLevel.fromIndex(it) },
        )
        // Out-of-range slider values clamp rather than crash.
        assertEquals(TieArbLevel.OFF, TieArbLevel.fromIndex(-3))
        assertEquals(TieArbLevel.B32, TieArbLevel.fromIndex(99))
    }

    // -- the new_game config carries the chosen level ------------------------

    @Test
    fun `new_game config carries tiearb_level for b32`() {
        val c = JSONObject(
            Difficulty.CHAMPION.newGameConfig(
                seed = 7, humanPlayer = 0, tieArbLevel = TieArbLevel.B32,
            )
        )
        assertEquals("b32", c.getString("tiearb_level"))
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
