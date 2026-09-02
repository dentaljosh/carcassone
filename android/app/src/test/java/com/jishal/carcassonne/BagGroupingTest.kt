package com.jishal.carcassonne

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The tile-bag view's grouping ([groupBagFaces]).
 *
 * The KEY itself comes from the engine — `android_bridge.tile_type_key`
 * canonicalises each tile's edges / city segments / road connections / farm slots /
 * pennant / cloister over its four `Tile.turn` rotations — and the engine-side
 * property (32 base descriptions collapse to 24 types, still summing to 72, with
 * every pennanted face on its own) is pinned in `tests/android/test_bridge.py`,
 * where the engine is importable.
 *
 * What is pinned HERE is the half that runs on the phone: that the collapse sums
 * correctly, picks a stable representative, never merges two different keys, and
 * degrades to the ungrouped list on a bridge that supplies no key at all.
 */
class BagGroupingTest {

    private fun face(desc: String, key: String, remaining: Int, total: Int, art: String = desc) =
        BagFace(description = desc, image = "$art.png", remaining = remaining,
            total = total, typeKey = key)

    /**
     * The real shape of the collapse: eight `*_flowers` garden faces fold into the
     * plain tile they are a drawing of, and the counts still add to the deck.
     */
    @Test
    fun `art variants merge and their counts add up`() {
        val faces = listOf(
            face("straight_road", key = "aaa", remaining = 5, total = 7),
            face("straight_road_flowers", key = "aaa", remaining = 1, total = 1),
            face("bent_road", key = "bbb", remaining = 6, total = 8),
            face("bent_road_flowers", key = "bbb", remaining = 0, total = 1),
        )
        val groups = groupBagFaces(faces)
        assertEquals(2, groups.size)
        assertEquals(faces.sumOf { it.remaining }, groups.sumOf { it.remaining })
        assertEquals(faces.sumOf { it.total }, groups.sumOf { it.total })
        assertTrue(groups.toString(), groups.all { it.variants == 2 })
    }

    /**
     * ⛔ A pennant is +1 point per tile in that city. Two faces that differ only by
     * the shield are DIFFERENT tiles and must never share a row — the bridge key
     * keeps `shield` for this reason, and the UI must not undo it by grouping on
     * anything looser (the art, say, which is nearly identical).
     */
    @Test
    fun `pennant variants never merge`() {
        val groups = groupBagFaces(
            listOf(
                face("city_diagonal_top_right", key = "plain", remaining = 2, total = 3),
                face("city_diagonal_top_right_shield", key = "pennant", remaining = 1, total = 2),
            )
        )
        assertEquals(2, groups.size)
        assertNotEquals(groups[0].key, groups[1].key)
    }

    /**
     * The representative is the group's most numerous face — so the plain tile wins
     * over its single garden twin, and the choice cannot flip between two calls on
     * the same data.
     */
    @Test
    fun `the representative art is stable and prefers the commonest face`() {
        val faces = listOf(
            face("straight_road_flowers", key = "aaa", remaining = 1, total = 1),
            face("straight_road", key = "aaa", remaining = 5, total = 7),
        )
        val once = groupBagFaces(faces).single()
        val again = groupBagFaces(faces.reversed()).single()
        assertEquals("straight_road.png", once.art)
        assertEquals(once, again)
    }

    /** Rows read "what is still likely to come" top-down; an exhausted type sinks. */
    @Test
    fun `groups sort by remaining, descending`() {
        val groups = groupBagFaces(
            listOf(
                face("a", key = "a", remaining = 0, total = 4),
                face("b", key = "b", remaining = 9, total = 9),
                face("c", key = "c", remaining = 3, total = 3),
            )
        )
        assertEquals(listOf(9, 3, 0), groups.map { it.remaining })
    }

    /**
     * A bundle older than the `type_key` field must degrade to the list it always
     * showed — one row per description — never to one giant row keyed on "".
     */
    @Test
    fun `a bridge with no type key falls back to one row per description`() {
        val groups = groupBagFaces(
            listOf(
                face("straight_road", key = "", remaining = 5, total = 7),
                face("straight_road_flowers", key = "", remaining = 1, total = 1),
            )
        )
        assertEquals(2, groups.size)
        assertTrue(groups.toString(), groups.all { it.variants == 1 })
    }

    /** The dialog's headline total must equal the sum of the rows it draws. */
    @Test
    fun `BagInfo groups preserve the reported total`() {
        val faces = listOf(
            face("a1", key = "a", remaining = 4, total = 5),
            face("a2", key = "a", remaining = 1, total = 1),
            face("b", key = "b", remaining = 7, total = 9),
        )
        val bag = BagInfo(faces = faces, totalRemaining = 12)
        assertEquals(bag.totalRemaining, bag.groups.sumOf { it.remaining })
    }
}
