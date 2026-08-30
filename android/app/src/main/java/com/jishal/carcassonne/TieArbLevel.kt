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
    B64(
        id = "b64",
        label = "Strongest (B64)",
        perTileEstimate = "~5-7s per tied tile (strongest)",
    ),
    ;

    companion object {
        /**
         * ⭐ RAISED B32 -> B64 on 2026-08-29 (owner, verbatim: "set phone APK to b64").
         *
         * The B32 rung is RETIRED FROM THIS MENU, not renamed: `id = "b64"` is a new
         * stable id and no existing id changed meaning. Licensed by the tier1
         * flat-score swap (`carc_core::tier1`, merged b4d4eecd), which made the
         * playout scorer ~8.5x cheaper BIT-IDENTICALLY — so a B=64 fire is now
         * *faster* than the B=32 fire it replaces (~5-7s vs ~20-30s).
         *
         * ⚠️ MIGRATION, AND IT IS LOAD-BEARING: a device that already persisted
         * `"b32"` resolves it through [fromId], which finds no matching entry and
         * falls through to [DEFAULT] — so the retired rung upgrades to B64 with no
         * DataStore migration and no key rename. That fall-through is the same
         * tested path as an unknown id; `TieArbLevelTest` pins it explicitly for
         * "b32" so this cannot regress silently.
         *
         * ⚠️ The PYTHON side deliberately still resolves `"b32"`
         * (`android_bridge.TIEARB_LEVELS`): a save or archive written by the B32
         * epoch must restore at B=32, not degrade to an unarmed game. Menu vocabulary
         * and resolver vocabulary are different sets on purpose.
         */
        val DEFAULT = B64

        fun fromId(id: String?): TieArbLevel = entries.firstOrNull { it.id == id } ?: DEFAULT

        /** Slider position (0..3), ascending in strength — mirrors [Difficulty.fromIndex]. */
        fun fromIndex(i: Int): TieArbLevel = entries[i.coerceIn(0, entries.lastIndex)]
    }
}
