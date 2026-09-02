package com.jishal.carcassonne

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import org.json.JSONObject
import java.io.IOException

/**
 * The five difficulty stops.
 *
 * Two different things live on this one axis, and the UI must not blur them:
 *
 *  - [INSTANT] swaps the **agent** for the Tier-1 rule-based player. It is not a
 *    weakened champion, so it carries no budget warning — it is a different
 *    opponent entirely.
 *  - [FAST]/[MEDIUM]/[STRONG] are the champion at a **reduced search budget**.
 *    The bridge stamps its own `BELOW CHAMPION BUDGET` note on these (see
 *    `_Session._build_opponent`); [belowChampionBudget] is the *client-side*
 *    prediction of that, used to warn before the game exists.
 *  - [CHAMPION] deliberately sends NO `sims`/`k_dets`, so the budget falls
 *    through to `governance/PRODUCTION.yaml`. That is why [sims] and [kDets] are
 *    null here rather than 688/4: a strength knob is never hardcoded in the app,
 *    it is read back for display via `production_budget()`.
 *
 * ⚠️ NO PER-MOVE SECONDS LIVE HERE ANY MORE (2026-09-02 text audit). The old
 * `estPerMove` strings ("~8-15s") were the 2026-07 PLAN's guesses for the Python
 * search; the phone has run the Rust core since 2026-08-01 and, since 2026-08-25,
 * a doubled mobile budget — so every one of those figures was wrong in both
 * directions at once, on the Home chip and in Settings. What replaces them is the
 * one thing this file can state exactly: the SEARCH SIZE, computed from the same
 * numbers that are sent to the bridge. Actual seconds are MEASURED in play and
 * shown as a rolling mean in the thinking banner.
 */
enum class Difficulty(
    /** Stable id for the DataStore record — never renumber or reuse. */
    val id: String,
    val label: String,
    /** `champion` | `tier1` — the bridge's `opponent` config field. */
    val opponent: String,
    /** Determinizations, or null to inherit the YAML budget. */
    val kDets: Int?,
    /** Sims per determinization, or null to inherit the YAML budget. */
    val sims: Int?,
    val blurb: String,
) {
    INSTANT(
        id = "instant",
        label = "Instant",
        opponent = "tier1",
        kDets = null,
        sims = null,
        blurb = "Tier-1 rule-based player — a different, much weaker opponent. " +
            "No search at all.",
    ),
    FAST(
        id = "fast",
        label = "Fast",
        opponent = "champion",
        kDets = 2,
        sims = 172,
        blurb = "The champion on a small fraction of its search — the narrowest and " +
            "shallowest stop that is still the champion.",
    ),
    MEDIUM(
        id = "medium",
        label = "Medium",
        opponent = "champion",
        kDets = 4,
        sims = 172,
        blurb = "Twice Fast's determinizations, at the same depth each.",
    ),
    STRONG(
        id = "strong",
        label = "Strong",
        opponent = "champion",
        kDets = 4,
        sims = 344,
        blurb = "Medium's determinizations, at twice the depth each.",
    ),
    CHAMPION(
        id = "champion",
        label = "Champion",
        opponent = "champion",
        kDets = null,
        sims = null,
        blurb = "The champion at the full budget this device is configured for " +
            "(PRODUCTION.yaml decides it, not the app). The only setting where " +
            "a win is a win against the champion.",
    ),
    ;

    /**
     * How big this stop's search is, in the units the bridge is actually given.
     *
     * DERIVED from [kDets]/[sims], so it cannot drift from what `newGameConfig`
     * sends — and deliberately not a duration. See the class kdoc for why the old
     * per-move second estimates were removed rather than re-guessed.
     */
    val searchLabel: String
        get() = when {
            isTier1 -> "no search"
            kDets != null && sims != null -> "k$kDets × $sims = $totalSims sims/move"
            else -> "this device's full budget"
        }

    /** True when this stop weakens the champion (and so must be labelled as such). */
    val belowChampionBudget: Boolean
        get() = opponent == "champion" && (kDets != null || sims != null)

    /** True for the one stop that is a *different agent* rather than a weaker one. */
    val isTier1: Boolean get() = opponent == "tier1"

    /** Total sims per move, or null when the YAML budget decides. */
    val totalSims: Int? get() = if (kDets != null && sims != null) kDets * sims else null

    /**
     * The `new_game` config for this preset.
     *
     * `sims`/`k_dets` are OMITTED (not null-valued) for [CHAMPION]: the bridge
     * treats an absent key as "use the YAML budget", and this is the single place
     * that decision is expressed.
     *
     * [tieArbLevel] is a SEPARATE settings axis (see [TieArbLevel]) folded in
     * here only because this is the one place the `new_game` JSON gets built —
     * it always sends `tiearb_level` explicitly (unlike `sims`/`k_dets`, there is
     * no "let the bridge decide" case to omit it for).
     */
    fun newGameConfig(
        seed: Int,
        humanPlayer: Int,
        verify: Boolean = true,
        tieArbLevel: TieArbLevel = TieArbLevel.DEFAULT,
        opponentMode: OpponentMode = OpponentMode.DEFAULT,
        remoteUrl: String = OpponentMode.DEFAULT_URL,
    ): String =
        JSONObject().apply {
            put("seed", seed)
            put("human_player", humanPlayer)
            put("opponent", opponentMode.bridgeOpponent ?: opponent)
            put("verify", verify)
            kDets?.let { put("k_dets", it) }
            sims?.let { put("sims", it) }
            put("tiearb_level", tieArbLevel.id)
            // ⛔ GOLDEN GATE. Everything above this line is EXACTLY what it was
            // before the remote opponent existed, and `opponentMode` defaults to
            // CHAMPION whose `bridgeOpponent` is null — so a champion game emits
            // the byte-identical JSON it always did, and the E4 stream stays one
            // continuous measurement across this build. `OpponentModeTest` pins
            // that against literal strings; do not "tidy" the two keys below into
            // the unconditional block.
            if (opponentMode == OpponentMode.REMOTE_CARCASUM) {
                put("remote_url", remoteUrl)
                put("remote_budget_ms", OpponentMode.BUDGET_MS)
            }
        }.toString()

    companion object {
        val DEFAULT = CHAMPION

        fun fromId(id: String?): Difficulty = entries.firstOrNull { it.id == id } ?: DEFAULT

        /** Slider position (0..4), ascending in strength. */
        fun fromIndex(i: Int): Difficulty = entries[i.coerceIn(0, entries.lastIndex)]
    }
}

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "carc_settings",
)

/**
 * Preferences DataStore holding the (currently single) persistent app setting.
 *
 * Reads swallow [IOException] and fall back to the default: a corrupt or missing
 * preferences file must degrade to "Champion", never crash the Home screen.
 */
class SettingsStore(context: Context) {

    private val store = context.applicationContext.settingsDataStore

    val difficulty: Flow<Difficulty> = store.data
        .catch { t -> if (t is IOException) emit(emptyPreferences()) else throw t }
        .map { prefs -> Difficulty.fromId(prefs[KEY_DIFFICULTY]) }

    suspend fun setDifficulty(d: Difficulty) {
        store.edit { it[KEY_DIFFICULTY] = d.id }
    }

    val tieArbLevel: Flow<TieArbLevel> = store.data
        .catch { t -> if (t is IOException) emit(emptyPreferences()) else throw t }
        .map { prefs -> TieArbLevel.fromId(prefs[KEY_TIE_ARB_LEVEL]) }

    suspend fun setTieArbLevel(level: TieArbLevel) {
        store.edit { it[KEY_TIE_ARB_LEVEL] = level.id }
    }

    /**
     * WHO to play (see [OpponentMode]). A missing or unknown record reads as
     * [OpponentMode.CHAMPION] — the safe default in the strongest sense: an
     * upgraded install, a corrupt preferences file and a rolled-back build all
     * land on the champion, which is the opponent every E4 archive is about.
     */
    val opponentMode: Flow<OpponentMode> = store.data
        .catch { t -> if (t is IOException) emit(emptyPreferences()) else throw t }
        .map { prefs -> OpponentMode.fromId(prefs[KEY_OPPONENT_MODE]) }

    suspend fun setOpponentMode(mode: OpponentMode) {
        store.edit { it[KEY_OPPONENT_MODE] = mode.id }
    }

    /** The remote-opponent server address; blank/absent falls back to the default. */
    val remoteUrl: Flow<String> = store.data
        .catch { t -> if (t is IOException) emit(emptyPreferences()) else throw t }
        .map { prefs ->
            prefs[KEY_REMOTE_URL]?.takeIf { it.isNotBlank() } ?: OpponentMode.DEFAULT_URL
        }

    suspend fun setRemoteUrl(url: String) {
        store.edit { it[KEY_REMOTE_URL] = url.trim() }
    }

    /**
     * Show the human's UPCOMING tile during the opponent's turn (the "next" panel).
     *
     * DEFAULT ON. The human has no legal action while the opponent is thinking, so
     * the panel cannot change a decision that is being made — but it does change
     * what the player KNOWS, so it is stamped into the archive
     * (`preview_next_tile`) rather than assumed invisible. Off is honoured
     * immediately: the panel disappears and the bridge is not asked again.
     */
    val previewNextTile: Flow<Boolean> = store.data
        .catch { t -> if (t is IOException) emit(emptyPreferences()) else throw t }
        .map { prefs -> prefs[KEY_PREVIEW_NEXT_TILE] ?: true }

    suspend fun setPreviewNextTile(on: Boolean) {
        store.edit { it[KEY_PREVIEW_NEXT_TILE] = on }
    }

    /**
     * Hold the process in the foreground while the opponent thinks (see
     * [ThinkingService]).
     *
     * DEFAULT ON. Purely a scheduling/notification setting — a move is never lost
     * either way, because the autosave is written before every search.
     */
    val backgroundThinking: Flow<Boolean> = store.data
        .catch { t -> if (t is IOException) emit(emptyPreferences()) else throw t }
        .map { prefs -> prefs[KEY_BACKGROUND_THINKING] ?: true }

    suspend fun setBackgroundThinking(on: Boolean) {
        store.edit { it[KEY_BACKGROUND_THINKING] = on }
    }

    private companion object {
        val KEY_DIFFICULTY = stringPreferencesKey("difficulty")
        val KEY_TIE_ARB_LEVEL = stringPreferencesKey("tie_arb_level")
        val KEY_OPPONENT_MODE = stringPreferencesKey("opponent_mode")
        val KEY_REMOTE_URL = stringPreferencesKey("remote_url")
        val KEY_PREVIEW_NEXT_TILE = booleanPreferencesKey("preview_next_tile")
        val KEY_BACKGROUND_THINKING = booleanPreferencesKey("background_thinking")
    }
}
