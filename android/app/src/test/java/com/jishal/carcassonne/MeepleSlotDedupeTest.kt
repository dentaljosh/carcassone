package com.jishal.carcassonne

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * [dedupeByFeature] — the UI-side half of the "duplicate meeple choice" fix.
 *
 * The bridge decides WHICH slots are equivalent (`feature_group`, unit-tested against
 * the real base deck in `tests/android/test_bridge.py`); this decides which one of an
 * equivalent set gets drawn and hit-tested. The contract that matters: exactly one
 * dot per group, and the dot must carry a REAL action id — the champion's action
 * space is untouched, so every id rendered has to be one the bridge offered.
 */
class MeepleSlotDedupeTest {

    private fun slot(
        actionId: Int,
        side: String,
        group: Int,
        type: String = "normal",
        terrain: String = "CITY",
    ) = MeepleSlot(
        actionId = actionId, side = side, type = type, terrain = terrain,
        offsetX = 0.5f, offsetY = 0.5f, describe = "", featureGroup = group,
    )

    @Test
    fun `two openings onto one city collapse to a single dot`() {
        // The real case from the playtest: a city spanning TOP and RIGHT is offered
        // as two actions that claim the same city.
        val slots = listOf(
            slot(10, "top", group = 0),
            slot(11, "right", group = 0),
        )
        val shown = dedupeByFeature(slots)
        assertEquals(1, shown.size)
        assertEquals(10, shown[0].actionId)
    }

    @Test
    fun `two separate cities keep two dots`() {
        val slots = listOf(
            slot(10, "left", group = 0),
            slot(11, "right", group = 1),
        )
        assertEquals(2, dedupeByFeature(slots).size)
    }

    @Test
    fun `centre wins as the representative of its group`() {
        // A monastery's dot belongs in the middle of the tile, not on an edge,
        // regardless of which slot the bridge happened to list first.
        val slots = listOf(
            slot(10, "top", group = 0),
            slot(11, "center", group = 0),
        )
        val shown = dedupeByFeature(slots)
        assertEquals(1, shown.size)
        assertEquals("center", shown[0].side)
        assertEquals(11, shown[0].actionId)
    }

    @Test
    fun `every rendered slot is one the bridge actually offered`() {
        val slots = listOf(
            slot(10, "top", group = 0),
            slot(11, "right", group = 0),
            slot(12, "bottom_left", group = 1, type = "farmer", terrain = "GRASS"),
            slot(13, "bottom", group = 2, terrain = "ROAD"),
        )
        val offered = slots.map { it.actionId }.toSet()
        val shown = dedupeByFeature(slots)
        assertEquals(3, shown.size)
        assertTrue(shown.all { it.actionId in offered })
    }

    @Test
    fun `dots keep the bridge's order rather than reshuffling`() {
        // First-appearance order, so two renders of one position draw the same
        // dots in the same places.
        val slots = listOf(
            slot(30, "bottom", group = 2),
            slot(10, "top", group = 0),
            slot(20, "right", group = 1),
        )
        assertEquals(listOf(30, 10, 20), dedupeByFeature(slots).map { it.actionId })
    }

    @Test
    fun `ungrouped slots are never merged`() {
        // `feature_group` parses to -1 when the field is absent (a payload from a
        // bridge that predates it). Collapsing those into one dot would silently
        // hide legal choices, so an unclassified slot always gets its own dot —
        // i.e. exactly the behaviour from before the feature existed.
        val slots = listOf(
            slot(10, "top", group = -1),
            slot(11, "right", group = -1),
        )
        assertEquals(2, dedupeByFeature(slots).size)
        assertEquals(listOf(10, 11), dedupeByFeature(slots).map { it.actionId })
    }

    @Test
    fun `an empty slot list renders nothing`() {
        assertEquals(emptyList<MeepleSlot>(), dedupeByFeature(emptyList()))
    }
}
