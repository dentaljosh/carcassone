package com.jishal.carcassonne

import org.json.JSONArray
import org.json.JSONObject

/**
 * Kotlin mirrors of `android_bridge`'s JSON schemas, plus the parsers.
 *
 * Deliberately hand-parsed with `org.json` (ships with Android) instead of
 * kotlinx-serialization: it adds no plugin/dependency to a build that is
 * currently green, and the bridge's contract — *every* response carries `ok`,
 * failures carry `error{code,message}` and never raise across JNI — is small
 * enough to read at a glance.
 *
 * Every parser is total: a missing field falls back to a harmless default rather
 * than throwing inside a coroutine on the UI path.
 */

data class BridgeError(val code: String, val message: String) {
    override fun toString(): String = "$code: $message"
}

data class TileArt(
    val image: String?,
    val turns: Int,
    val description: String,
)

data class PlacedTile(
    val row: Int,
    val col: Int,
    val image: String?,
    val turns: Int,
) {
    val cell: Cell get() = Cell(row, col)
}

data class PlacedMeeple(
    val player: Int,
    val row: Int,
    val col: Int,
    val side: String,
    val type: String,
    val offsetX: Float,
    val offsetY: Float,
) {
    val isFarmer: Boolean get() = type == "farmer" || type == "big_farmer"
}

data class LegalTileCell(
    val row: Int,
    val col: Int,
    /** Legal rotations at this cell, ascending; parallel to [actionIds]. */
    val rotations: List<Int>,
    val actionIds: List<Int>,
) {
    val cell: Cell get() = Cell(row, col)
}

data class MeepleSlot(
    val actionId: Int,
    val side: String,
    val type: String,
    /** Uppercase engine `TerrainType.name`, e.g. `CITY`, `ROAD`, `GRASS`. */
    val terrain: String,
    val offsetX: Float,
    val offsetY: Float,
    val describe: String,
) {
    val isFarmer: Boolean get() = type == "farmer" || type == "big_farmer"
}

data class LegalBlock(
    val tileCells: List<LegalTileCell> = emptyList(),
    val meepleSlots: List<MeepleSlot> = emptyList(),
    val meepleTarget: Cell? = null,
    val tilePassId: Int? = null,
    val meeplePassId: Int? = null,
) {
    fun cellAt(cell: Cell): LegalTileCell? = tileCells.firstOrNull { it.cell == cell }
}

data class AiLastMove(
    val actionId: Int,
    val describe: String,
    val elapsedS: Double?,
)

data class GameResult(
    val scores: List<Int>,
    val diff: Int,
    val winner: Int?,
    val verdict: String,
    val budgetNote: String?,
)

/** The full UI state object (`get_state` / the tail of every mutating call). */
data class GameState(
    val generation: Int,
    val phase: String,
    val turn: Int,
    val currentPlayer: Int,
    val humanPlayer: Int,
    val aiPlayer: Int,
    val isHumanTurn: Boolean,
    val scores: List<Int>,
    val meeplesFree: List<Int>,
    val deckRemaining: Int,
    val tilesRemaining: Int,
    val nextTile: TileArt?,
    val board: List<PlacedTile>,
    val meeples: List<PlacedMeeple>,
    val legal: LegalBlock,
    val opponentName: String,
    val budgetNote: String?,
    val aiLastTile: Cell?,
    val aiLastMove: AiLastMove?,
    val isTerminated: Boolean,
    val result: GameResult?,
) {
    val isTilePhase: Boolean get() = phase == "tiles"
    val isMeeplePhase: Boolean get() = phase == "meeples"

    /** Score for the seat the human is sitting in. */
    val humanScore: Int get() = scores.getOrElse(humanPlayer) { 0 }
    val aiScore: Int get() = scores.getOrElse(aiPlayer) { 0 }
    val humanMeeples: Int get() = meeplesFree.getOrElse(humanPlayer) { 0 }
    val aiMeeples: Int get() = meeplesFree.getOrElse(aiPlayer) { 0 }

    fun boundsWithMargin(): BoardBounds? =
        BoardBounds.of(board.map { it.cell })?.expanded(1)
}

data class Progress(
    val leafCalls: Int,
    val expected: Int,
    val elapsedS: Double,
    /** `search` | `exact` | `idle`. */
    val phase: String,
    val fraction: Float?,
)

data class ProductionBudget(
    val championId: String,
    val simsPerDet: Int,
    val kDets: Int,
    val totalSims: Int,
)

/** Outcome of one `ai_move` call. */
sealed interface AiMoveResult {
    /** The reset landed mid-search; the answer belongs to a board that is gone. */
    data object Stale : AiMoveResult
    data class Applied(val state: GameState, val describe: String, val elapsedS: Double) : AiMoveResult
    data class Failed(val error: BridgeError) : AiMoveResult
}

object BridgeJson {

    fun parseOrError(raw: String): Result<JSONObject> = runCatching {
        val o = JSONObject(raw)
        if (!o.optBoolean("ok", false)) {
            val e = o.optJSONObject("error")
            throw BridgeFailure(
                BridgeError(
                    e?.optString("code").orEmpty().ifEmpty { "unknown" },
                    e?.optString("message").orEmpty().ifEmpty { raw.take(300) },
                )
            )
        }
        o
    }

    class BridgeFailure(val error: BridgeError) : Exception(error.toString())

    fun errorOf(t: Throwable): BridgeError = when (t) {
        is BridgeFailure -> t.error
        else -> BridgeError(t.javaClass.simpleName, t.message ?: "(no message)")
    }

    fun state(o: JSONObject): GameState = GameState(
        generation = o.optInt("generation", 0),
        phase = o.optString("phase", "tiles"),
        turn = o.optInt("turn", 0),
        currentPlayer = o.optInt("current_player", 0),
        humanPlayer = o.optInt("human_player", 0),
        aiPlayer = o.optInt("ai_player", 1),
        isHumanTurn = o.optBoolean("is_human_turn", false),
        scores = intList(o.optJSONArray("scores")),
        meeplesFree = intList(o.optJSONArray("meeples_free")),
        deckRemaining = o.optInt("deck_remaining", 0),
        tilesRemaining = o.optInt("tiles_remaining", 0),
        nextTile = o.optJSONObject("next_tile")?.let(::tileArt),
        board = o.optJSONArray("board").map { placedTile(it) },
        meeples = o.optJSONArray("meeples").map { placedMeeple(it) },
        legal = o.optJSONObject("legal")?.let(::legalBlock) ?: LegalBlock(),
        opponentName = o.optString("opponent_name", "Champion"),
        budgetNote = o.optNullableString("budget_note"),
        aiLastTile = o.optJSONObject("ai_last_tile")?.let { Cell(it.optInt("row"), it.optInt("col")) },
        aiLastMove = o.optJSONObject("ai_last_move")?.let {
            AiLastMove(
                actionId = it.optInt("action_id", -1),
                describe = it.optString("describe", ""),
                elapsedS = if (it.isNull("elapsed_s")) null else it.optDouble("elapsed_s"),
            )
        },
        isTerminated = o.optBoolean("is_terminated", false),
        result = o.optJSONObject("result")?.let {
            GameResult(
                scores = intList(it.optJSONArray("scores")),
                diff = it.optInt("diff", 0),
                winner = if (it.isNull("winner")) null else it.optInt("winner"),
                verdict = it.optString("verdict", ""),
                budgetNote = it.optNullableString("budget_note"),
            )
        },
    )

    fun progress(o: JSONObject): Progress = Progress(
        leafCalls = o.optInt("leaf_calls", 0),
        expected = o.optInt("expected", 0),
        elapsedS = o.optDouble("elapsed_s", 0.0),
        phase = o.optString("phase", "idle"),
        fraction = if (o.isNull("fraction")) null else o.optDouble("fraction", 0.0).toFloat(),
    )

    fun budget(o: JSONObject): ProductionBudget = ProductionBudget(
        championId = o.optString("champion_id", "champion"),
        simsPerDet = o.optInt("sims_per_det", 0),
        kDets = o.optInt("k_dets", 0),
        totalSims = o.optInt("total_sims", 0),
    )

    // -- pieces --------------------------------------------------------------

    private fun tileArt(o: JSONObject) = TileArt(
        image = o.optNullableString("image"),
        turns = o.optInt("turns", 0),
        description = o.optString("description", ""),
    )

    private fun placedTile(o: JSONObject) = PlacedTile(
        row = o.optInt("row"),
        col = o.optInt("col"),
        image = o.optNullableString("image"),
        turns = o.optInt("turns", 0),
    )

    private fun placedMeeple(o: JSONObject): PlacedMeeple {
        val (ox, oy) = offsetRatio(o)
        return PlacedMeeple(
            player = o.optInt("player"),
            row = o.optInt("row"),
            col = o.optInt("col"),
            side = o.optString("side", "center"),
            type = o.optString("type", "normal"),
            offsetX = ox,
            offsetY = oy,
        )
    }

    private fun legalBlock(o: JSONObject) = LegalBlock(
        tileCells = o.optJSONArray("tile_cells").map {
            LegalTileCell(
                row = it.optInt("row"),
                col = it.optInt("col"),
                rotations = intList(it.optJSONArray("rotations")),
                actionIds = intList(it.optJSONArray("action_ids")),
            )
        },
        meepleSlots = o.optJSONArray("meeple_slots").map {
            val (ox, oy) = offsetRatio(it)
            MeepleSlot(
                actionId = it.optInt("action_id", -1),
                side = it.optString("side", "center"),
                type = it.optString("type", "normal"),
                terrain = it.optString("terrain", "GRASS"),
                offsetX = ox,
                offsetY = oy,
                describe = it.optString("describe", ""),
            )
        },
        meepleTarget = o.optJSONObject("meeple_target")
            ?.let { Cell(it.optInt("row"), it.optInt("col")) },
        tilePassId = o.optNullableInt("tile_pass_id"),
        meeplePassId = o.optNullableInt("meeple_pass_id"),
    )

    /**
     * `offset_ratio` is authored by the bridge (a copy of the visualiser's
     * `meeple_position_offsets` divided by tile size); centre is the fallback so
     * an unknown side still renders somewhere sane instead of at (0,0).
     */
    private fun offsetRatio(o: JSONObject): Pair<Float, Float> {
        val a = o.optJSONArray("offset_ratio") ?: return 0.5f to 0.5f
        if (a.length() < 2) return 0.5f to 0.5f
        return a.optDouble(0, 0.5).toFloat() to a.optDouble(1, 0.5).toFloat()
    }

    private fun intList(a: JSONArray?): List<Int> {
        if (a == null) return emptyList()
        return List(a.length()) { a.optInt(it) }
    }

    private inline fun <T> JSONArray?.map(f: (JSONObject) -> T): List<T> {
        if (this == null) return emptyList()
        val out = ArrayList<T>(length())
        for (i in 0 until length()) optJSONObject(i)?.let { out.add(f(it)) }
        return out
    }

    private fun JSONObject.optNullableString(key: String): String? =
        if (isNull(key)) null else optString(key).ifEmpty { null }

    private fun JSONObject.optNullableInt(key: String): Int? =
        if (isNull(key)) null else optInt(key)
}
