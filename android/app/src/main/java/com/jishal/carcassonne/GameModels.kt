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
    /**
     * Intra-tile feature id from the bridge. Slots sharing one are openings onto the
     * SAME feature (a city spanning two edges, a road running through), so choosing
     * between them is a choice without a difference. Dense over the offered slots.
     */
    val featureGroup: Int = -1,
) {
    val isFarmer: Boolean get() = type == "farmer" || type == "big_farmer"
}

/**
 * One dot per on-tile feature, in stable group order.
 *
 * The engine offers a meeple action per *side*, so a city with two openings arrives
 * as two actions that claim the same city — a duplicate choice the player reads as a
 * decision. This collapses them for RENDERING and HIT-TESTING only: the JSON keeps
 * every slot, and the chosen representative carries a real `actionId`, so what is
 * applied is an action the champion's action space already contained.
 *
 * CENTER wins when present (a monastery dot belongs in the middle of the tile, not
 * on an edge); otherwise the first slot in bridge order, which is ascending action id.
 */
fun dedupeByFeature(slots: List<MeepleSlot>): List<MeepleSlot> {
    // LinkedHashMap: groups come out in FIRST-APPEARANCE order, which is the
    // bridge's order (ascending action id). Stable without needing to sort, so the
    // dots do not reshuffle between two renders of the same position.
    val byGroup = LinkedHashMap<Int, MutableList<MeepleSlot>>()
    slots.forEachIndexed { i, s ->
        // A NEGATIVE group means "the bridge could not classify this slot". Such a
        // slot must never be merged with anything — hiding a legal choice is a far
        // worse failure than showing a duplicate one — so it is keyed by its own
        // position instead. (The bridge already hands out a private group per
        // unknown slot; this is the belt to that pair of braces, and it is what stops
        // a payload with the field missing entirely from collapsing to a single dot.)
        val key = if (s.featureGroup >= 0) s.featureGroup else UNGROUPED_KEY_BASE + i
        byGroup.getOrPut(key) { mutableListOf() }.add(s)
    }
    return byGroup.values.map { members ->
        members.firstOrNull { it.side == "center" } ?: members.first()
    }
}

/** Far above any real dense group id, so a synthetic key can never collide. */
private const val UNGROUPED_KEY_BASE = 1_000_000

/**
 * The part of ONE tile a claimed feature occupies.
 *
 * [side] is the engine's own `Side` value, and which values can appear is decided by
 * the kind of feature: an edge (`top`/`right`/`bottom`/`left`) for a city band or a
 * road, `center` for a monastery, and a farmer corner
 * (`top_left`/`top_right`/`bottom_left`/`bottom_right`) for a field. The renderer
 * turns each into a shape — see `BoardCanvas.regionPath`.
 */
data class FeatureRegion(val row: Int, val col: Int, val side: String) {
    val cell: Cell get() = Cell(row, col)
}

/** One claimed feature, for the ownership shading (`get_ownership`). */
data class OwnershipFeature(
    /** `city` | `road` | `chapel` | `farm`. */
    val kind: String,
    val cells: List<Cell>,
    /**
     * Which *part* of each cell the feature covers. Preferred over [cells] for
     * drawing — a tile usually carries several features at once, and whole-tile
     * washes stacked on one tile are unreadable. Empty only on a bridge too old to
     * report it, in which case the renderer falls back to [cells].
     */
    val regions: List<FeatureRegion>,
    /** Majority owners: empty (nobody), one seat, or BOTH on a tie = contested. */
    val owners: List<Int>,
    val meepleCountPerPlayer: List<Int>,
    val finished: Boolean?,
    val points: Int,
) {
    val isContested: Boolean get() = owners.size > 1
    val isFarm: Boolean get() = kind == "farm"
}

/** One of the 32 base faces, with how many are still unseen (`get_bag`). */
data class BagFace(
    val description: String,
    val image: String?,
    val remaining: Int,
    val total: Int,
)

data class BagInfo(
    val faces: List<BagFace>,
    val totalRemaining: Int,
)

/**
 * A finished game as stored in `filesDir/games/`.
 *
 * [raw] is the whole archive JSON verbatim — it is also a valid `restore_game`
 * payload (the bridge accepts the archive schema), so the record stays replayable
 * rather than being flattened into just the numbers the list happens to show.
 */
data class ArchivedGame(
    val fileName: String,
    val finishedAt: Long,
    val deckSeed: Int,
    val humanPlayer: Int,
    val opponentName: String,
    val scores: List<Int>,
    val result: GameResult?,
    val tilesPlaced: Int,
    val raw: String,
) {
    val humanScore: Int get() = scores.getOrElse(humanPlayer) { 0 }
    val aiScore: Int get() = scores.getOrElse(1 - humanPlayer) { 0 }

    /** `W` / `L` / `D` from the human's seat — the list's leading glyph. */
    val outcome: String
        get() = when {
            humanScore > aiScore -> "W"
            humanScore < aiScore -> "L"
            else -> "D"
        }

    val seatLabel: String get() = if (humanPlayer == 0) "You first" else "AI first"
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

/**
 * One thing the last decision materially did — a feature completing and paying out.
 *
 * The board only shows that a number changed, and Base+Farmers pays in lumps big
 * enough that an unexplained 11 -> 17 is the most confusing moment of watching the
 * champion play. The bridge derives these by diffing the state across the applied
 * action (`android_bridge.scoring_events`) and hands over [text] ready to print, so
 * the UI never re-derives scoring rules it would get subtly wrong.
 *
 * [kind] is `city` | `road` | `cloister`, or `score` for the deliberately coarse
 * fallback the bridge emits when its itemisation does not reconcile with the real
 * score delta.
 */
data class MoveEvent(
    val kind: String,
    val points: Int,
    val winners: List<Int>,
    val meeplesReturned: Int,
    val text: String,
)

/**
 * One seat's share of the final scoring pass, in ENGINE SEAT ORDER.
 *
 * `duringPlay + incomplete + farms == total` is a bridge-side invariant (the
 * bridge drops the whole block rather than emit one that does not balance), so
 * the UI can print it without re-deriving anything.
 */
data class ScoreBreakdownRow(
    /** Points banked before the final pass — completed features, as they closed. */
    val duringPlay: Int,
    /** Cities/roads/monasteries still open at the end, scored at the reduced rate. */
    val incomplete: Int,
    val farms: Int,
    val total: Int,
)

data class GameResult(
    val scores: List<Int>,
    val diff: Int,
    val winner: Int?,
    val verdict: String,
    val budgetNote: String?,
    /** Null on any bridge that does not supply it, or when it did not balance. */
    val breakdown: List<ScoreBreakdownRow>? = null,
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
    /** What the LAST decision paid out. Usually empty — most moves score nothing. */
    val events: List<MoveEvent> = emptyList(),
) {
    val isTilePhase: Boolean get() = phase == "tiles"
    val isMeeplePhase: Boolean get() = phase == "meeples"

    /**
     * Tiles still to come, counted so that **`tilesLeft + board.size` is the same
     * number at every instant of the game**.
     *
     * The bridge's `tiles_remaining` is `len(deck) + (1 if next_tile)` — the
     * fair-agent `k_remaining` band, which is the right quantity for the search and
     * the wrong one for the HUD. The engine does not clear `next_tile` when a tile
     * is played (`StateUpdater.play_tile`); it is replaced later, by `draw_tile`, at
     * the *end* of the meeple phase. So for the whole meeple sub-phase the tile the
     * player just placed is counted twice — once on the board and once "in hand" —
     * and the HUD read `36 tiles left / 37 placed` for a 72-tile game.
     *
     * Subtracting the in-hand tile during the meeple phase is the "delay the
     * increment" fix without hardcoding a deck size: the pair stays consistent for
     * any deck, including the tile-phase pass (which stays in `tiles` and keeps a
     * genuinely unplaced tile in hand).
     */
    val tilesLeft: Int
        get() = if (isMeeplePhase) (tilesRemaining - 1).coerceAtLeast(0) else tilesRemaining

    /** Score for the seat the human is sitting in. */
    val humanScore: Int get() = scores.getOrElse(humanPlayer) { 0 }
    val aiScore: Int get() = scores.getOrElse(aiPlayer) { 0 }
    val humanMeeples: Int get() = meeplesFree.getOrElse(humanPlayer) { 0 }
    val aiMeeples: Int get() = meeplesFree.getOrElse(aiPlayer) { 0 }

    // Falls back to the legal cells when no tile is placed yet: a "You first" game
    // starts with an empty board list, and a null here would leave the identity
    // transform showing empty space (the start position is at world ~(6,15)).
    fun boundsWithMargin(): BoardBounds? =
        (BoardBounds.of(board.map { it.cell })
            ?: BoardBounds.of(legal.tileCells.map { it.cell }))?.expanded(1)
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
        result = o.optJSONObject("result")?.let(::gameResult),
        events = o.optJSONArray("events").map { e ->
            MoveEvent(
                kind = e.optString("kind", "score"),
                points = e.optInt("points", 0),
                winners = intList(e.optJSONArray("winners")),
                meeplesReturned = e.optInt("meeples_returned", 0),
                text = e.optString("text", ""),
            )
        }.filter { it.text.isNotEmpty() },
    )

    /** Shared by the live state and by an archived record, which stores the same
     *  object verbatim — so the Past-games summary renders from one parser. */
    fun gameResult(o: JSONObject): GameResult = GameResult(
        scores = intList(o.optJSONArray("scores")),
        diff = o.optInt("diff", 0),
        winner = if (o.isNull("winner")) null else o.optInt("winner"),
        verdict = o.optString("verdict", ""),
        budgetNote = o.optNullableString("budget_note"),
        breakdown = o.optJSONArray("breakdown")
            ?.map { row ->
                ScoreBreakdownRow(
                    duringPlay = row.optInt("during_play"),
                    incomplete = row.optInt("incomplete"),
                    farms = row.optInt("farms"),
                    total = row.optInt("total"),
                )
            }
            ?.takeIf { rows -> rows.isNotEmpty() },
    )

    fun progress(o: JSONObject): Progress = Progress(
        leafCalls = o.optInt("leaf_calls", 0),
        expected = o.optInt("expected", 0),
        elapsedS = o.optDouble("elapsed_s", 0.0),
        phase = o.optString("phase", "idle"),
        fraction = if (o.isNull("fraction")) null else o.optDouble("fraction", 0.0).toFloat(),
    )

    /** `preview_meeple_slots` -> the dots to draw on the ghost. */
    fun previewSlots(o: JSONObject): List<MeepleSlot> =
        o.optJSONArray("slots").map { meepleSlot(it) }

    fun ownership(o: JSONObject): List<OwnershipFeature> =
        o.optJSONArray("features").map { f ->
            OwnershipFeature(
                kind = f.optString("kind", ""),
                cells = f.optJSONArray("cells").let { a ->
                    if (a == null) emptyList() else List(a.length()) { i ->
                        val pair = a.optJSONArray(i)
                        Cell(pair?.optInt(0) ?: 0, pair?.optInt(1) ?: 0)
                    }
                },
                regions = f.optJSONArray("regions").let { a ->
                    if (a == null) emptyList() else List(a.length()) { i ->
                        val t = a.optJSONArray(i)
                        FeatureRegion(
                            t?.optInt(0) ?: 0,
                            t?.optInt(1) ?: 0,
                            t?.optString(2).orEmpty().ifEmpty { "center" },
                        )
                    }
                },
                owners = intList(f.optJSONArray("owners")),
                meepleCountPerPlayer = intList(f.optJSONArray("meeple_count_per_player")),
                finished = if (f.isNull("finished")) null else f.optBoolean("finished"),
                points = f.optInt("points", 0),
            )
        }

    fun bag(o: JSONObject): BagInfo = BagInfo(
        faces = o.optJSONArray("faces").map {
            BagFace(
                description = it.optString("description", ""),
                image = it.optNullableString("image"),
                remaining = it.optInt("remaining", 0),
                total = it.optInt("total", 0),
            )
        },
        totalRemaining = o.optInt("total_remaining", 0),
    )

    /**
     * One archive file. Total like every parser here: a record written by an older
     * build (or a half-written one) degrades to zeros rather than throwing inside the
     * list's coroutine.
     */
    fun archived(fileName: String, raw: String): ArchivedGame? = runCatching {
        val o = JSONObject(raw)
        ArchivedGame(
            fileName = fileName,
            finishedAt = o.optLong("finished_at", 0L),
            deckSeed = o.optInt("deck_seed", 0),
            humanPlayer = o.optInt("human_player", 0),
            opponentName = o.optString("opponent_name", "Champion"),
            scores = intList(o.optJSONArray("scores")),
            result = o.optJSONObject("result")?.let(::gameResult),
            tilesPlaced = o.optInt("tiles_placed", 0),
            raw = raw,
        )
    }.getOrNull()

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

    /** Shared by `legal.meeple_slots` and by `preview_meeple_slots`, which the
     *  bridge builds with the same function — so the ghost's dots and the real
     *  sub-phase's dots can never disagree about shape. */
    private fun meepleSlot(o: JSONObject): MeepleSlot {
        val (ox, oy) = offsetRatio(o)
        return MeepleSlot(
            actionId = o.optInt("action_id", -1),
            side = o.optString("side", "center"),
            type = o.optString("type", "normal"),
            terrain = o.optString("terrain", "GRASS"),
            offsetX = ox,
            offsetY = oy,
            describe = o.optString("describe", ""),
            featureGroup = o.optInt("feature_group", -1),
        )
    }

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
        meepleSlots = o.optJSONArray("meeple_slots").map { meepleSlot(it) },
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
