package com.jishal.carcassonne

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
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
 * The per-move estimates are the plan's phone figures, not measurements; the HUD
 * shows a measured rolling mean once the champion has actually moved.
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
    val estPerMove: String,
    val blurb: String,
) {
    INSTANT(
        id = "instant",
        label = "Instant",
        opponent = "tier1",
        kDets = null,
        sims = null,
        estPerMove = "<0.1s",
        blurb = "Tier-1 rule-based player — a different, much weaker opponent. " +
            "No search at all.",
    ),
    FAST(
        id = "fast",
        label = "Fast",
        opponent = "champion",
        kDets = 2,
        sims = 172,
        estPerMove = "~1–2s",
        blurb = "The champion on a quarter of its determinizations and a quarter of " +
            "its sims.",
    ),
    MEDIUM(
        id = "medium",
        label = "Medium",
        opponent = "champion",
        kDets = 4,
        sims = 172,
        estPerMove = "~2–4s",
        blurb = "Full determinizations, a quarter of the sims each.",
    ),
    STRONG(
        id = "strong",
        label = "Strong",
        opponent = "champion",
        kDets = 4,
        sims = 344,
        estPerMove = "~4–8s",
        blurb = "Full determinizations, half the sims each.",
    ),
    CHAMPION(
        id = "champion",
        label = "Champion",
        opponent = "champion",
        kDets = null,
        sims = null,
        estPerMove = "~8–15s",
        blurb = "The production champion at its full fair budget, exactly as it is " +
            "measured in the repo. The only setting where a win is a real win.",
    ),
    ;

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
     */
    fun newGameConfig(seed: Int, humanPlayer: Int, verify: Boolean = true): String =
        JSONObject().apply {
            put("seed", seed)
            put("human_player", humanPlayer)
            put("opponent", opponent)
            put("verify", verify)
            kDets?.let { put("k_dets", it) }
            sims?.let { put("sims", it) }
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

    private companion object {
        val KEY_DIFFICULTY = stringPreferencesKey("difficulty")
    }
}
