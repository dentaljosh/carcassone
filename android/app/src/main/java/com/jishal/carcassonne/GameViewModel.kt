package com.jishal.carcassonne

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import kotlin.random.Random

/** Which seat the human takes. Player 0 always moves first. */
enum class Seat(val label: String) {
    HUMAN_FIRST("You first"),
    AI_FIRST("AI first"),
    RANDOM("Random"),
    ;

    fun humanPlayer(): Int = when (this) {
        HUMAN_FIRST -> 0
        AI_FIRST -> 1
        RANDOM -> Random.nextInt(2)
    }
}

/** The tile-placement ghost the human is currently aiming. */
data class Ghost(
    val cell: Cell,
    val rotation: Int,
    val actionId: Int,
    val rotationCount: Int,
)

data class GameUiState(
    val state: GameState? = null,
    /** A session-mutating bridge call is in flight (input is locked). */
    val busy: Boolean = false,
    /** Specifically: `ai_move` is blocking the bridge thread. */
    val thinking: Boolean = false,
    val progress: Progress? = null,
    val selected: Cell? = null,
    val rotationIndex: Int = 0,
    val error: BridgeError? = null,
    val budget: ProductionBudget? = null,
    val hasSave: Boolean = false,
    val showResult: Boolean = false,
    val warmingUp: Boolean = false,
) {
    /**
     * The live ghost, or `null` when nothing is aimed. Recomputed from the
     * authoritative legal block every time rather than cached, so a stale cell
     * (e.g. after the state advanced underneath) simply stops rendering instead
     * of offering an illegal Confirm.
     */
    val ghost: Ghost?
        get() {
            val st = state ?: return null
            val cell = selected ?: return null
            if (!st.isTilePhase || !st.isHumanTurn) return null
            val lc = st.legal.cellAt(cell) ?: return null
            if (lc.rotations.isEmpty() || lc.rotations.size != lc.actionIds.size) return null
            val i = rotationIndex.mod(lc.rotations.size)
            return Ghost(cell, lc.rotations[i], lc.actionIds[i], lc.rotations.size)
        }

    val canInteract: Boolean
        get() = state != null && !busy && !thinking && state.isHumanTurn && !state.isTerminated
}

/**
 * Owns the game session and the whole interaction state machine.
 *
 * ### Turn cycle
 * ```
 *  human tile tap -> ghost (cell + legal rotation) -> Confirm -> apply_action
 *      -> [bridge auto-passes a forced human pass]
 *      -> meeple phase: slot tap or Skip -> apply_action
 *      -> save_game -> persist            <-- ALWAYS before ai_move
 *      -> while (!terminated && !human turn) ai_move ; persist
 *      -> human turn again
 * ```
 * The AI leg is a *loop*, not a single call: `auto_pass_forced` in the bridge
 * only auto-passes the HUMAN seat (the agent must burn one `choose_action` per
 * decision to keep its `_move_idx` seeds aligned with a replayed restore), so
 * the champion's tile move and its meeple move are two separate `ai_move` calls
 * and `current_player` stays on the AI between them.
 *
 * ### Concurrency
 * At most one session-mutating operation is ever in flight ([opJob]); UI taps
 * during one are dropped, not queued. The 250 ms progress poll is a *separate*
 * job on a *separate* dispatcher so it cannot deadlock behind `ai_move`.
 */
class GameViewModel(app: Application) : AndroidViewModel(app) {

    private val saveStore = SaveStore(app)

    private val _ui = MutableStateFlow(GameUiState())
    val ui: StateFlow<GameUiState> = _ui

    private var opJob: Job? = null
    private var progressJob: Job? = null

    // ------------------------------------------------------------------ home

    /** Import the bridge (slow, one-off) and read the YAML budget + save slot. */
    fun warmUpAndRefresh() {
        if (_ui.value.warmingUp) return
        _ui.update { it.copy(warmingUp = true) }
        viewModelScope.launch {
            runCatching { PythonBridge.warmUp() }
                .onFailure { Log.e(TAG, "warmUp failed", it) }
            val budget = runCatching { PythonBridge.productionBudget() }
                .getOrNull()
                ?.let { raw -> BridgeJson.parseOrError(raw).getOrNull() }
                ?.let(BridgeJson::budget)
            val hasSave = saveStore.exists()
            _ui.update { it.copy(warmingUp = false, budget = budget ?: it.budget, hasSave = hasSave) }
        }
    }

    fun refreshSaveSlot() {
        viewModelScope.launch { _ui.update { it.copy(hasSave = saveStore.exists()) } }
    }

    // ----------------------------------------------------------- game set-up

    fun newGame(seat: Seat, seed: Int) {
        // Starting a game must never be a no-op just because the previous game
        // left an operation in flight (e.g. the user backed out between two AI
        // decisions, when `thinking` is briefly false). Take the session over.
        takeOver()
        launchNewGame(seat, seed)
    }

    private fun launchNewGame(seat: Seat, seed: Int) = launchOp { e ->
        saveStore.clear()
        _ui.update {
            GameUiState(budget = it.budget, busy = true, hasSave = false)
        }
        // sims / k_dets are deliberately ABSENT from the config: omitting them
        // makes the bridge fall through to governance/PRODUCTION.yaml, which is
        // the only place a strength knob is allowed to live. `budget` is read
        // separately and used for DISPLAY only.
        val cfg = JSONObject().apply {
            put("seed", seed)
            put("human_player", seat.humanPlayer())
            put("opponent", "champion")
            put("verify", true)
        }.toString()
        runBridge(e) { PythonBridge.newGame(cfg) }
    }

    /** Same seat, fresh deck — the "New game" button on the end-of-game dialog. */
    fun rematch() {
        val seat = if ((_ui.value.state?.humanPlayer ?: 0) == 0) Seat.HUMAN_FIRST else Seat.AI_FIRST
        newGame(seat, Random.nextInt(1, Int.MAX_VALUE))
    }

    fun resume() {
        takeOver()
        launchResume()
    }

    private fun launchResume() = launchOp { e ->
        val json = saveStore.read()
        if (json == null) {
            _ui.update { it.copy(hasSave = false, error = BridgeError("no_save", "No saved game found.")) }
            return@launchOp
        }
        _ui.update { it.copy(busy = true, error = null) }
        runBridge(e) { PythonBridge.restoreGame(json) }
    }

    // ------------------------------------------------------- human tile phase

    /**
     * Tap on the board. Tapping a legal cell aims the ghost; tapping the SAME
     * cell again cycles to the next legal rotation (matching the desktop tool);
     * tapping anywhere illegal cancels.
     */
    fun onCellTap(cell: Cell) {
        val s = _ui.value
        if (!s.canInteract) return
        val st = s.state ?: return
        if (!st.isTilePhase) return
        val lc = st.legal.cellAt(cell)
        if (lc == null || lc.actionIds.isEmpty()) {
            _ui.update { it.copy(selected = null, rotationIndex = 0) }
            return
        }
        _ui.update {
            if (it.selected == cell) it.copy(rotationIndex = it.rotationIndex + 1)
            else it.copy(selected = cell, rotationIndex = 0)
        }
    }

    fun cycleRotation() {
        if (_ui.value.ghost == null) return
        _ui.update { it.copy(rotationIndex = it.rotationIndex + 1) }
    }

    fun cancelPlacement() {
        _ui.update { it.copy(selected = null, rotationIndex = 0) }
    }

    fun confirmPlacement() {
        val ghost = _ui.value.ghost ?: return
        applyHumanAction(ghost.actionId)
    }

    // ----------------------------------------------------- human meeple phase

    fun onMeepleSlot(slot: MeepleSlot) {
        if (!_ui.value.canInteract) return
        if (_ui.value.state?.isMeeplePhase != true) return
        applyHumanAction(slot.actionId)
    }

    fun skipMeeple() {
        val st = _ui.value.state ?: return
        if (!_ui.value.canInteract || !st.isMeeplePhase) return
        val pass = st.legal.meeplePassId ?: return
        applyHumanAction(pass)
    }

    private fun applyHumanAction(actionId: Int) = launchOp { e ->
        _ui.update { it.copy(busy = true, error = null, selected = null, rotationIndex = 0) }
        runBridge(e) { PythonBridge.applyAction(actionId) }
    }

    // -------------------------------------------------------------- teardown

    fun dismissResult() = _ui.update { it.copy(showResult = false) }

    fun clearError() = _ui.update { it.copy(error = null) }

    /**
     * Leaving the game screen. Only meaningful mid-search: the in-flight
     * `ai_move` cannot be cancelled, so we drop the whole session instead —
     * `reset()` bumps the bridge generation, and when the search finally returns
     * it sees the mismatch and discards its move rather than applying it.
     *
     * The autosave already holds the position *before* that move, so Resume
     * replays the human position and the champion simply thinks again.
     */
    fun leaveGame() {
        if (!isInFlight()) return   // idle: keep the session, Game reopens unchanged
        takeOver()
        _ui.update { GameUiState(budget = it.budget, hasSave = it.hasSave) }
    }

    private fun isInFlight(): Boolean = _ui.value.thinking || opJob?.isActive == true

    /**
     * Abandon whatever the bridge is doing. The blocking `ai_move` cannot be
     * interrupted, so `reset()` is queued *behind* it: when the search finally
     * returns, the generation no longer matches and the bridge discards the move
     * rather than applying it. Queued, not raced — that is the whole design.
     */
    private fun takeOver() {
        if (!isInFlight()) return
        epoch++                     // everything already in flight is now stale
        opJob?.cancel()
        opJob = null
        stopProgressPoll()
        _ui.update { it.copy(thinking = false, busy = false, progress = null) }
        viewModelScope.launch {
            runCatching { PythonBridge.reset() }
                .onFailure { Log.w(TAG, "reset failed", it) }
        }
    }

    // ------------------------------------------------------------- machinery

    /**
     * Guards against a *cancelled* operation still writing to [_ui].
     *
     * `Job.cancel()` is cooperative: the coroutine only unwinds at its next
     * suspension point, so a coroutine cancelled just after a bridge call
     * returned can still run the non-suspending code that follows it — including
     * a `_ui.update`. Without this guard that lands as a stale board flashing
     * over a freshly started game, and (worse) the `finally` in [runAiTurns]
     * clearing the NEW game's `thinking` flag, which strands the progress bar.
     *
     * Every operation captures the epoch it started in and refuses to touch
     * [_ui] once [takeOver] has moved on.
     */
    private var epoch = 0

    private fun isCurrent(e: Int): Boolean = e == epoch

    private fun launchOp(block: suspend (Int) -> Unit) {
        if (opJob?.isActive == true) return
        val myEpoch = epoch
        opJob = viewModelScope.launch {
            try {
                block(myEpoch)
            } catch (t: Throwable) {
                if (t is kotlinx.coroutines.CancellationException) throw t
                Log.e(TAG, "op failed", t)
                if (isCurrent(myEpoch)) {
                    _ui.update { it.copy(busy = false, error = BridgeJson.errorOf(t)) }
                }
            }
        }
    }

    /**
     * Run one state-returning bridge call, adopt the state, then drive the rest
     * of the turn (persist -> AI loop). Every mutating entry point funnels here
     * so the post-move bookkeeping can never be forgotten on one path.
     */
    private suspend fun runBridge(e: Int, call: suspend () -> String) {
        val raw = call()
        if (!isCurrent(e)) return
        val parsed = BridgeJson.parseOrError(raw)
        val obj = parsed.getOrElse { t ->
            _ui.update { it.copy(busy = false, error = BridgeJson.errorOf(t)) }
            return
        }
        val st = BridgeJson.state(obj)
        _ui.update { it.copy(state = st, busy = false, error = null) }
        afterState(e, st)
    }

    /** Persist, surface a finished game, or hand the turn to the champion. */
    private suspend fun afterState(e: Int, st: GameState) {
        if (st.isTerminated) {
            saveStore.clear()
            if (isCurrent(e)) _ui.update { it.copy(hasSave = false, showResult = true) }
            return
        }
        persist(e)
        if (!st.isHumanTurn) runAiTurns(e)
    }

    private suspend fun persist(e: Int) {
        val raw = runCatching { PythonBridge.saveGame() }.getOrNull() ?: return
        if (BridgeJson.parseOrError(raw).isFailure) return
        saveStore.write(raw)
        if (isCurrent(e)) _ui.update { it.copy(hasSave = true) }
    }

    /**
     * Drive the champion until the turn comes back. Loops because tile and
     * meeple are two separate agent decisions on the same seat.
     */
    private suspend fun runAiTurns(e: Int) {
        var guard = 0
        while (true) {
            if (!isCurrent(e)) return
            val st = _ui.value.state ?: return
            if (st.isTerminated || st.isHumanTurn) return
            if (guard++ > MAX_AI_STEPS) {
                Log.e(TAG, "AI loop guard tripped at $guard steps")
                _ui.update {
                    it.copy(error = BridgeError("ai_loop", "The champion did not yield the turn."))
                }
                return
            }

            _ui.update { it.copy(thinking = true, progress = null) }
            startProgressPoll()
            val raw = try {
                PythonBridge.aiMove(st.generation)
            } finally {
                stopProgressPoll()
                // Epoch-guarded: a cancelled turn must NOT clear the thinking
                // flag of the game that replaced it.
                if (isCurrent(e)) _ui.update { it.copy(thinking = false, progress = null) }
            }
            if (!isCurrent(e)) return

            val obj = runCatching { JSONObject(raw) }.getOrNull()
            if (obj == null) {
                _ui.update { it.copy(error = BridgeError("bad_json", raw.take(200))) }
                return
            }
            // Stale is checked BEFORE ok: a discarded move comes back as
            // {"ok":true,"stale":true} with no state fields, and a refused one as
            // {"ok":false,"stale":true}. Either way: drop it silently.
            if (obj.optBoolean("stale", false)) {
                Log.i(TAG, "dropped a stale ai_move result")
                return
            }
            if (!obj.optBoolean("ok", false)) {
                val errObj = obj.optJSONObject("error")
                _ui.update {
                    it.copy(
                        error = BridgeError(
                            errObj?.optString("code") ?: "ai_move",
                            errObj?.optString("message") ?: raw.take(200),
                        )
                    )
                }
                return
            }

            val next = BridgeJson.state(obj)
            _ui.update { it.copy(state = next, error = null) }
            if (next.isTerminated) {
                saveStore.clear()
                _ui.update { it.copy(hasSave = false, showResult = true) }
                return
            }
            persist(e)
        }
    }

    private fun startProgressPoll() {
        stopProgressPoll()
        progressJob = viewModelScope.launch {
            while (isActive) {
                val raw = runCatching { PythonBridge.getProgress() }.getOrNull()
                if (raw != null) {
                    BridgeJson.parseOrError(raw).getOrNull()?.let { o ->
                        val p = BridgeJson.progress(o)
                        _ui.update { if (it.thinking) it.copy(progress = p) else it }
                    }
                }
                delay(POLL_MS)
            }
        }
    }

    private fun stopProgressPoll() {
        progressJob?.cancel()
        progressJob = null
    }

    override fun onCleared() {
        stopProgressPoll()
        super.onCleared()
    }

    companion object {
        private const val TAG = "GameVM"
        private const val POLL_MS = 250L

        /** A 72-tile game is ~150 plies; anything past this is a bug, not a game. */
        private const val MAX_AI_STEPS = 400
    }
}
