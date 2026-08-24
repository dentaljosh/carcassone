package com.jishal.carcassonne

/**
 * How hard the mobile tie-arbiter searches when the champion's top moves are
 * tied at the leaf.
 *
 * A second, independent axis from [Difficulty]: difficulty picks the *budget*
 * for ordinary search, this picks how much *extra* work the bridge spends
 * breaking a tie once ordinary search cannot separate the top moves. `id` is
 * the DataStore record's stable key AND the exact string the bridge's
 * `TIEARB_LEVELS` vocabulary expects in `new_game`'s `tiearb_level` — never
 * renumber or reuse.
 *
 * Ordered weakest-first (cheapest to strongest), matching [Difficulty]'s own
 * slider convention (`fromIndex` runs ascending in strength, INSTANT..CHAMPION)
 * so both sliders read left-to-right the same way.
 */
enum class TieArbLevel(
    /** Stable id for the DataStore record AND the bridge's `tiearb_level` value —
     *  never renumber or reuse. */
    val id: String,
    val label: String,
    /** Measured per-tied-tile think-time, for display next to the slider. */
    val perTileEstimate: String,
) {
    OFF(
        id = "off",
        label = "Off",
        perTileEstimate = "no tie-break search — fastest, weakest on ties",
    ),
    B8(
        id = "b8",
        label = "Light (B8)",
        perTileEstimate = "~7s per tied tile",
    ),
    B16(
        id = "b16",
        label = "Strong (B16)",
        perTileEstimate = "~15s per tied tile",
    ),
    B32(
        id = "b32",
        label = "Strongest (B32)",
        perTileEstimate = "~20-30s per tied tile (strongest)",
    ),
    ;

    companion object {
        val DEFAULT = B32

        fun fromId(id: String?): TieArbLevel = entries.firstOrNull { it.id == id } ?: DEFAULT

        /** Slider position (0..3), ascending in strength — mirrors [Difficulty.fromIndex]. */
        fun fromIndex(i: Int): TieArbLevel = entries[i.coerceIn(0, entries.lastIndex)]
    }
}
