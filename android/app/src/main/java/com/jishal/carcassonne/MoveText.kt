package com.jishal.carcassonne

import java.util.Locale

/**
 * Player-facing wording. **No Android or Compose types on purpose** — like
 * [BoardGeometry] this is the part of the UI that can be pinned by a JVM test,
 * and copy is exactly the kind of thing that rots silently.
 *
 * The rule this file exists to enforce: the *bridge* speaks engine (`NORMAL on
 * TOP`, `tile @ (+6, +15) rot=0`, uppercase `Side` names), and that vocabulary
 * stops here. The JSON contract is deliberately left alone — the debug screen
 * and the python tests read it, and an engine-shaped log line is the right thing
 * for them. Only the strings a player reads are translated.
 */
object MoveText {

    /**
     * Humanise one `format_action` string from the bridge.
     *
     * The three shapes the bridge emits (`android_bridge.format_action`):
     *
     * | bridge                       | player                        |
     * |------------------------------|-------------------------------|
     * | `tile @ (+6, +15) rot=0`     | `placed a tile (r6 c15)`      |
     * | `NORMAL on TOP`              | `meeple on the top edge`      |
     * | `FARMER on BOTTOM_LEFT`      | `farmer on the bottom-left field` |
     * | `skip meeple`                | `no meeple`                   |
     * | `pass (no legal placement)`  | `passed — no legal placement` |
     *
     * Anything unrecognised is returned verbatim: a wrong-but-honest engine
     * string beats a confidently mangled one.
     */
    fun humanizeAction(raw: String): String {
        val s = raw.trim()
        if (s.isEmpty()) return s
        if (s == "skip meeple") return "no meeple"
        if (s.startsWith("pass")) return "passed — no legal placement"
        TILE_RE.matchEntire(s)?.let { m ->
            // The bridge prints the engine's signed coordinates (`+6`); the sign
            // is an artefact of the format string, not information.
            val row = m.groupValues[1].removePrefix("+")
            val col = m.groupValues[2].removePrefix("+")
            return "placed a tile (r$row c$col)"
        }
        MEEPLE_RE.matchEntire(s)?.let { m ->
            val (type, side) = m.destructured
            return "${meepleNoun(type)} ${placementPhrase(type, side)}"
        }
        return s
    }

    /** `NORMAL` -> `meeple`, `FARMER` -> `farmer`, … (lower case: it sits mid-sentence). */
    fun meepleNoun(type: String): String = when (type.uppercase(Locale.US)) {
        "NORMAL" -> "meeple"
        "FARMER" -> "farmer"
        "ABBOT" -> "abbot"
        "BIG" -> "big meeple"
        "BIG_FARMER" -> "big farmer"
        else -> type.lowercase(Locale.US).replace('_', ' ')
    }

    /**
     * Where the piece went, in board language rather than enum language.
     *
     * The same [side] means different things to different pieces, which is why
     * the type is needed: `TOP` under a knight is the city/road running off the
     * top edge, `TOP_LEFT` under a farmer is the field in that corner. A
     * `CENTER` slot is the monastery.
     */
    fun placementPhrase(type: String, side: String): String {
        val s = side.uppercase(Locale.US)
        if (s == "CENTER" || s == "CENTRE") return "in the middle"
        val where = s.lowercase(Locale.US).replace('_', '-')
        val isCorner = '-' in where
        val noun = if (isCorner || isFarmerType(type)) "field" else "edge"
        return "on the $where $noun"
    }

    private fun isFarmerType(type: String): Boolean =
        type.uppercase(Locale.US) in setOf("FARMER", "BIG_FARMER")

    /**
     * The status line under the board during the human tile phase.
     *
     * [rotationCount] of 1 is its own sentence, not "Rotation 1 of 1": the rotate
     * button is *hidden* in that case, so the old copy promised a control that was
     * not on screen.
     */
    fun tilePhaseHint(index: Int, rotationCount: Int): String =
        if (rotationCount <= 1) "✓ to place — only one rotation fits here"
        // 1-based POSITION in the legal list, not the raw engine rotation value:
        // the legal set is often sparse ({1,3}), which printed as "Rotation 3 of 2".
        else "Rotation ${index + 1} of $rotationCount — ✓ to place, ⟳ to rotate"

    /** `Last Tier-1 move: …` — the opponent is not always the champion. */
    fun lastMoveLine(opponentName: String, describe: String, elapsedS: Double?): String {
        val who = shortOpponent(opponentName)
        // A Tier-1 reply lands in under a millisecond, and "(0.0s)" reads as a
        // broken timer rather than as "instant". Same rule as the ETA suffix.
        val secs = elapsedS?.takeIf { it >= 0.05 }
            ?.let { " (${"%.1f".format(Locale.US, it)}s)" } ?: ""
        return "Last $who move: ${humanizeAction(describe)}$secs"
    }

    /**
     * The chip/status form of an opponent name: a weakened preset calls itself
     * `Champion(weakened k4x172)`, and the parenthetical belongs in the budget
     * note, not in every sentence that names the opponent.
     */
    fun shortOpponent(name: String): String =
        name.substringBefore('(').trim().ifEmpty { "Champion" }

    private val TILE_RE = Regex("""tile @ \(([+-]?\d+),\s*([+-]?\d+)\) rot=\d+""")
    private val MEEPLE_RE = Regex("""([A-Z_]+) on ([A-Z_]+)""")
}
