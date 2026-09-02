package com.jishal.carcassonne

/**
 * WHO the app plays against — a separate axis from [Difficulty] and [TieArbLevel].
 *
 * [CHAMPION] is the default and is the app as it has always been: the whole
 * opponent decision belongs to the [Difficulty] preset, the search runs on the
 * phone, and the archive stamps `opponent: "champion"`.
 *
 * [REMOTE_CARCASUM] forwards every opponent move over the tailnet to
 * `scripts/carcasum_remote/server.py` on the laptop, which drives the CALIBRATED
 * Carcasum (MCTS / Portion / Random / 5000 ms / Cp 0.5) through the existing
 * engine-vs-engine bridge. Nothing about Carcasum runs on the phone. It exists
 * for the owner session in `measurement/carcasum_owner_session_prep/` — the
 * adaptation-share discriminator needs the owner to play an opponent he has
 * never mined, under his NORMAL PHONE CONDITIONS.
 *
 * ## ⛔ Why this is an OPPONENT axis and not a difficulty stop
 *
 * Because of the archive. A remote game is stamped
 * `opponent: "carcasum_remote_5000ms"`, never `"champion"`, and
 * `scripts/e4_archives.py` excludes anything that is not exactly `"champion"`
 * from the owner-vs-champion E4 anchor. That anchor (`A = +13.265 pts/game`) is
 * the single number the whole session's read is chained through, so one Carcasum
 * game pooled into it would move the result in the direction that manufactures
 * the headline. Keeping the two on one axis would have made "which opponent
 * played" a *derived* fact; keeping them apart makes it a *stamped* one.
 *
 * ## The golden gate
 *
 * When [CHAMPION] is selected, [Difficulty.newGameConfig] must produce the
 * BYTE-IDENTICAL JSON it produced before this enum existed. `OpponentModeTest`
 * pins that against literal expected strings for every difficulty stop, because
 * "the champion path is unchanged" is the property that lets the E4 stream keep
 * being one continuous measurement across this app build.
 */
enum class OpponentMode(
    /** Stable id for the DataStore record — never renumber or reuse. */
    val id: String,
    val label: String,
    val blurb: String,
) {
    CHAMPION(
        id = "champion",
        label = "Champion",
        blurb = "The on-device champion, at the Difficulty setting above. " +
            "Archived as an E4 game.",
    ),
    REMOTE_CARCASUM(
        id = "remote_carcasum",
        label = "Remote Carcasum",
        // ⚠️ NO PER-MOVE NUMBER (2026-09-02 text audit). This said "~5s per move",
        // which stopped being true the moment the server grew a fixed-PLAYOUT mode
        // — there `budget_ms` is null on its side and the phone's 5000 default
        // describes nothing. The server self-describes at `/health`, the bridge
        // renders that into `opponent_name`, and the app shows THAT once a game
        // starts. Nothing here may name a budget.
        blurb = "Carcasum (2014 MCTS, out of lineage) running on the laptop, " +
            "reached over the tailnet. Its search budget is whatever the server " +
            "was started with — the game screen names it. Archived separately — " +
            "NEVER counted in the champion record.",
    ),
    ;

    /** The bridge's `opponent` config value, when this mode overrides the preset. */
    val bridgeOpponent: String? get() = when (this) {
        CHAMPION -> null                       // the Difficulty preset decides
        REMOTE_CARCASUM -> BRIDGE_REMOTE
    }

    companion object {
        val DEFAULT = CHAMPION

        /** `android_bridge.REMOTE_OPPONENT_PREFIX` — the bare, unlabelled kind. */
        const val BRIDGE_REMOTE = "carcasum_remote"

        /**
         * The calibrated per-turn budget. ⚠️ NOT a knob the UI exposes: changing
         * it changes the opponent, and the session's `B` anchor
         * (`champion - Carcasum@5s = +3.4075 pts/deck`) would no longer apply.
         */
        const val BUDGET_MS = 5000

        /** Default server address — the laptop's tailnet IP and the daemon's port. */
        const val DEFAULT_URL = "http://100.109.88.103:8971"

        fun fromId(id: String?): OpponentMode = entries.firstOrNull { it.id == id } ?: DEFAULT

        /**
         * True for a string that could be a reachable base URL. Deliberately
         * permissive (any `http(s)://host[:port]`) — the real check is the
         * bridge's `/health` ping at game start, which fails with the server's
         * own words instead of a guess about what a valid address looks like.
         */
        fun looksLikeUrl(s: String): Boolean {
            val t = s.trim()
            if (!t.startsWith("http://") && !t.startsWith("https://")) return false
            val rest = t.removePrefix("https://").removePrefix("http://")
            return rest.isNotEmpty() && !rest.contains(' ')
        }
    }
}
