package com.jishal.carcassonne

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
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

/**
 * The Home screen's new-game form.
 *
 * Session state, deliberately NOT part of [GameUiState]: that object is rebuilt
 * wholesale by `newGame`/`leaveGame`, which is exactly what used to throw away a
 * hand-typed seed. Held by the activity-scoped [GameViewModel] instead of a
 * `rememberSaveable`, because the plain `when (screen)` navigation drops Home
 * out of the composition entirely — so the seed was re-rolled on every return
 * from Settings.
 */
data class NewGameForm(
    val seat: Seat = Seat.HUMAN_FIRST,
    val seedText: String = randomSeed().toString(),
)

/** Deck seeds are user-visible, so they stay short enough to read out and retype. */
const val SEED_MAX: Int = 1_000_000

fun randomSeed(): Int = Random.nextInt(1, SEED_MAX)

/**
 * The seed a Start tap actually uses: the typed digits when they parse to a
 * usable seed, a fresh random one when the field is blank or zero.
 */
fun resolveSeed(seedText: String, fallback: () -> Int = ::randomSeed): Int =
    seedText.toIntOrNull()?.takeIf { it > 0 } ?: fallback()

/** The tile-placement ghost the human is currently aiming. */
data class Ghost(
    val cell: Cell,
    /** The engine rotation value (0..3) — NOT an ordinal; the legal set at a cell
     *  is often sparse, e.g. {1, 3}. Use [index] to say "2nd of 2". */
    val rotation: Int,
    val actionId: Int,
    val rotationCount: Int,
    /** 0-based position of [rotation] within this cell's legal rotation list. */
    val index: Int,
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
    /**
     * An operation coroutine is still running. Distinct from [busy], which covers
     * only the bridge call itself: an op stays active through the post-move
     * bookkeeping (persist), and a tap accepted in that window would be silently
     * dropped by `launchOp`. Also the flag the Game screen's process-death probe
     * reads, so it is set SYNCHRONOUSLY in `launchOp` (before the coroutine runs).
     */
    val opActive: Boolean = false,
    /**
     * The champion's turn ended in an error rather than a move. The game is not
     * over and the position is intact — the turn is simply retryable, which is
     * what [GameViewModel.retryAiTurn] does. Without this the seat is stuck: it
     * is not the human's turn, so there is nothing to press.
     */
    val aiFailed: Boolean = false,
    /**
     * Set once after a restore whose save was stamped with a different champion
     * build; the message the bridge supplied. Advisory only — the game still plays.
     */
    val saveMismatch: String? = null,
    /** The persisted difficulty preset; the next [GameViewModel.newGame] uses it. */
    val difficulty: Difficulty = Difficulty.DEFAULT,
    /**
     * Rolling mean of the last [GameViewModel.ETA_WINDOW] AI move durations **for
     * the decision now in flight**, in seconds — `null` until there is a usable
     * sample of that kind.
     */
    val etaSeconds: Double? = null,
    /**
     * The cell of the most recently placed tile, whoever placed it — the single
     * input to the auto-camera. Was two fields (`lastHumanTile` here and
     * `GameState.aiLastTile` from the bridge), which forced two competing
     * LaunchedEffects that could animate the board in different directions at
     * once; the bridge's `ai_last_tile` also *persists* across the human's reply,
     * so "the AI's last tile" is not the same thing as "the last tile placed".
     */
    val lastPlacedTile: Cell? = null,
    /**
     * Set for [GameViewModel.PHASE_LOCK_MS] after the human's tile lands and the
     * meeple phase opens. Confirm-✓ and Skip-meeple occupy the same screen
     * position in consecutive phases, so an impatient second tap on ✓ used to
     * land on Skip and silently forfeit the meeple.
     */
    val phaseLock: Boolean = false,
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
            return Ghost(cell, lc.rotations[i], lc.actionIds[i], lc.rotations.size, i)
        }

    val canInteract: Boolean
        get() = state != null && !busy && !thinking && !opActive &&
            state.isHumanTurn && !state.isTerminated
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
    private val settings = SettingsStore(app)

    private val _ui = MutableStateFlow(GameUiState())
    val ui: StateFlow<GameUiState> = _ui

    private val _newGameForm = MutableStateFlow(NewGameForm())

    /** The Home screen's seat + seed, kept for the life of the process. */
    val newGameForm: StateFlow<NewGameForm> = _newGameForm

    fun setSeat(seat: Seat) {
        _newGameForm.update { it.copy(seat = seat) }
        // Touching the new-game config means the user has moved on from whatever
        // failed last; the banner would otherwise sit there for the whole session.
        clearError()
    }

    fun setSeedText(text: String) {
        _newGameForm.update { it.copy(seedText = text.filter(Char::isDigit).take(9)) }
        clearError()
    }

    fun rerollSeed() {
        _newGameForm.update { it.copy(seedText = randomSeed().toString()) }
        clearError()
    }

    private var opJob: Job? = null
    private var progressJob: Job? = null
    private var phaseLockJob: Job? = null

    /**
     * Durations of the last [ETA_WINDOW] AI moves, oldest first, **bucketed by the
     * phase the decision was made in**. Session-scoped because a preset change
     * makes older samples describe a different search budget entirely.
     *
     * Bucketed, not one window, because the champion's turn is two `ai_move` calls
     * on the same seat — a full search for the tile, then a near-instant meeple
     * decision. Averaging them together dragged the mean to ~0.02s and produced the
     * "2s of ~0.0s" read-out: an ETA for the wrong kind of decision entirely.
     */
    private val aiDurations = HashMap<String, ArrayDeque<Double>>()

    init {
        // The persisted preset is the source of truth for the whole app; the
        // Settings screen writes it, everything else reads this flow.
        viewModelScope.launch {
            settings.difficulty.collect { d -> _ui.update { it.copy(difficulty = d) } }
        }
    }

    /** Persist a new difficulty. The change applies to the NEXT game, not this one. */
    fun setDifficulty(d: Difficulty) {
        viewModelScope.launch {
            runCatching { settings.setDifficulty(d) }
                .onFailure { Log.w(TAG, "difficulty write failed", it) }
        }
    }

    // ------------------------------------------------------------------ home

    /** Import the bridge (slow, one-off) and read the YAML budget + save slot. */
    fun warmUpAndRefresh() {
        if (_ui.value.warmingUp) return
        _ui.update { it.copy(warmingUp = true) }
        viewModelScope.launch {
            // Same rule as `persist`: a real failure is survivable (the app falls back
            // to the previous budget), a cancellation means this scope is going away
            // and must not be swallowed into the `_ui.update` below.
            try {
                PythonBridge.warmUp()
            } catch (c: CancellationException) {
                throw c
            } catch (t: Throwable) {
                Log.e(TAG, "warmUp failed", t)
            }
            val budget = try {
                BridgeJson.parseOrError(PythonBridge.productionBudget())
                    .getOrNull()?.let(BridgeJson::budget)
            } catch (c: CancellationException) {
                throw c
            } catch (t: Throwable) {
                Log.w(TAG, "production_budget failed", t)
                null
            }
            val hasSave = saveStore.exists()
            _ui.update { it.copy(warmingUp = false, budget = budget ?: it.budget, hasSave = hasSave) }
        }
    }

    fun refreshSaveSlot() {
        viewModelScope.launch { _ui.update { it.copy(hasSave = saveStore.exists()) } }
    }

    /** Is there an autosave on disk? Used by the Game screen's process-death probe. */
    suspend fun hasSavedGame(): Boolean = saveStore.exists()

    fun dismissSaveMismatch() = _ui.update { it.copy(saveMismatch = null) }

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
        aiDurations.clear()
        // Read the PERSISTED value rather than the mirrored one: the DataStore
        // collect is asynchronous, so a Start tapped in the first moments after a
        // cold launch could otherwise silently start a game at the default budget
        // instead of the saved preset.
        val difficulty = runCatching { settings.difficulty.first() }
            .getOrElse { _ui.value.difficulty }
        _ui.update {
            GameUiState(budget = it.budget, busy = true, hasSave = false, difficulty = difficulty)
        }
        // The preset owns the whole opponent/budget decision, including the choice
        // to OMIT sims/k_dets at Champion so the bridge falls through to
        // governance/PRODUCTION.yaml — the only place a strength knob is allowed
        // to live. `budget` is read separately and used for DISPLAY only.
        val cfg = difficulty.newGameConfig(seed = seed, humanPlayer = seat.humanPlayer())
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
        // The save carries its OWN opponent/sims/k_dets, so resuming keeps the
        // difficulty the game was started at regardless of the current setting.
        aiDurations.clear()
        _ui.update { it.copy(busy = true, error = null, etaSeconds = null, lastPlacedTile = null) }
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
        // Recorded BEFORE the action is applied: `applyHumanAction` clears the
        // selection, and the board state carries no "human last tile" field. The
        // cell is all the recentre needs, and each placement is a fresh cell (the
        // square is occupied afterwards), so the value always changes.
        _ui.update { it.copy(lastPlacedTile = ghost.cell) }
        applyHumanAction(ghost.actionId)
    }

    // ----------------------------------------------------- human meeple phase

    fun onMeepleSlot(slot: MeepleSlot) {
        if (!_ui.value.canInteract || _ui.value.phaseLock) return
        if (_ui.value.state?.isMeeplePhase != true) return
        applyHumanAction(slot.actionId)
    }

    fun skipMeeple() {
        val st = _ui.value.state ?: return
        // `phaseLock`: Skip sits exactly where Confirm-✓ was a frame ago, so the
        // second half of a double-tap on ✓ would otherwise forfeit the meeple.
        if (!_ui.value.canInteract || _ui.value.phaseLock || !st.isMeeplePhase) return
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
     * Re-enter the champion's turn after it failed ([GameUiState.aiFailed]).
     *
     * Safe to repeat: the board never advanced, so this simply asks for the move
     * again. `ai_move` is idempotent from the caller's side — a stale generation
     * comes back flagged and is dropped.
     */
    fun retryAiTurn() {
        if (!_ui.value.aiFailed) return
        _ui.update { it.copy(aiFailed = false, error = null) }
        launchOp { e -> runAiTurns(e) }
    }

    /**
     * Leaving the game screen. Two cases need the session dropped:
     *
     *  - **mid-search** — the in-flight `ai_move` cannot be cancelled, so we drop
     *    the whole session instead. `reset()` bumps the bridge generation, and
     *    when the search finally returns it sees the mismatch and discards its
     *    move rather than applying it. The autosave already holds the position
     *    *before* that move, so Resume replays the human position and the
     *    champion simply thinks again.
     *  - **wedged on a failed AI turn** ([GameUiState.aiFailed]) — nothing is in
     *    flight, but keeping the session would reopen the Game screen straight
     *    back into the same stuck turn. Drop it; Resume rebuilds from the save.
     *
     * Otherwise this is a no-op and the Game screen reopens exactly as it was.
     */
    fun leaveGame() {
        if (!isInFlight() && !_ui.value.aiFailed) return
        dropSession()
        aiDurations.clear()
        _ui.update {
            GameUiState(budget = it.budget, hasSave = it.hasSave, difficulty = it.difficulty)
        }
    }

    /** Is a bridge operation running? Public so the Back handler and `leaveGame`
     *  agree on the answer — a mid-apply Back must confirm, not silently exit. */
    fun isInFlight(): Boolean = _ui.value.thinking || opJob?.isActive == true

    /**
     * Abandon whatever the bridge is doing. The blocking `ai_move` cannot be
     * interrupted, so `reset()` is queued *behind* it: when the search finally
     * returns, the generation no longer matches and the bridge discards the move
     * rather than applying it. Queued, not raced — that is the whole design.
     */
    private fun takeOver() {
        if (!isInFlight()) return
        dropSession()
        _ui.update { it.copy(thinking = false, busy = false, opActive = false, progress = null) }
    }

    /** Bump the epoch, cancel the local job, and queue a bridge `reset()`. */
    private fun dropSession() {
        epoch++                     // everything already in flight is now stale
        opJob?.cancel()
        opJob = null
        stopProgressPoll()
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
        // Set BEFORE launching, not inside the coroutine: the Game screen's
        // process-death probe reads this on its very first composition, which can
        // happen before the coroutine has had a chance to run.
        _ui.update { it.copy(opActive = true) }
        opJob = viewModelScope.launch {
            try {
                block(myEpoch)
            } catch (t: Throwable) {
                if (t is kotlinx.coroutines.CancellationException) throw t
                Log.e(TAG, "op failed", t)
                if (isCurrent(myEpoch)) {
                    _ui.update { it.copy(busy = false, error = BridgeJson.errorOf(t)) }
                }
            } finally {
                if (isCurrent(myEpoch)) _ui.update { it.copy(opActive = false) }
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
        val wasMeeplePhase = _ui.value.state?.isMeeplePhase == true
        // `opActive` stays true: the bridge call is done, but persist (and possibly
        // the whole AI leg) still is not, and a tap accepted now would be dropped.
        _ui.update {
            it.copy(
                state = st, busy = false, opActive = true, error = null, aiFailed = false,
                saveMismatch = obj.optJSONObject("save_mismatch")
                    ?.optString("message").orEmpty().ifEmpty { null } ?: it.saveMismatch,
            )
        }
        // The human's tile just landed and the meeple phase is now open under their
        // finger: swallow taps for a moment (see [GameUiState.phaseLock]).
        if (st.isHumanTurn && st.isMeeplePhase && !wasMeeplePhase) armPhaseLock()
        afterState(e, st)
    }

    /** Persist, surface a finished game, or hand the turn to the champion. */
    private suspend fun afterState(e: Int, st: GameState) {
        currentCoroutineContext().ensureActive()
        if (st.isTerminated) {
            saveStore.clear()
            if (isCurrent(e)) _ui.update { it.copy(hasSave = false, showResult = true) }
            return
        }
        persist(e)
        if (!st.isHumanTurn) runAiTurns(e)
    }

    /**
     * Write the autosave. Failures are non-fatal (the game plays on; only Resume
     * is affected) — but a CANCELLATION is not a failure, it is this coroutine
     * being torn down, and swallowing it would let the caller carry on into
     * [afterState] and start an AI turn for a game that no longer exists.
     */
    private suspend fun persist(e: Int) {
        val raw = try {
            PythonBridge.saveGame()
        } catch (c: CancellationException) {
            throw c
        } catch (t: Throwable) {
            Log.w(TAG, "save_game failed", t)
            return
        }
        if (BridgeJson.parseOrError(raw).isFailure) return
        saveStore.write(raw)
        if (isCurrent(e)) _ui.update { it.copy(hasSave = true) }
    }

    /**
     * Drive the champion until the turn comes back. Loops because tile and
     * meeple are two separate agent decisions on the same seat.
     */
    private suspend fun runAiTurns(e: Int) {
        currentCoroutineContext().ensureActive()
        var guard = 0
        while (true) {
            if (!isCurrent(e)) return
            val st = _ui.value.state ?: return
            if (st.isTerminated || st.isHumanTurn) return
            if (guard++ > MAX_AI_STEPS) {
                Log.e(TAG, "AI loop guard tripped at $guard steps")
                _ui.update {
                    it.copy(
                        aiFailed = true,
                        error = BridgeError("ai_loop", "The champion did not yield the turn."),
                    )
                }
                return
            }

            // The ETA is published BEFORE the search, from the bucket for the kind
            // of decision about to be made — so the banner never advertises a
            // meeple-decision mean while a full tile search is running.
            val decisionPhase = st.phase
            _ui.update {
                it.copy(thinking = true, progress = null, etaSeconds = etaFor(decisionPhase))
            }
            val myPoll = startProgressPoll()
            val raw = try {
                PythonBridge.aiMove(st.generation)
            } finally {
                // Epoch-guarded on BOTH counts: a stale continuation must neither
                // clear the thinking flag of the game that replaced it, nor cancel
                // that game's freshly started poll. `myPoll` is the job THIS turn
                // started, so cancelling it can never touch a newer one.
                myPoll.cancel()
                if (isCurrent(e)) {
                    if (progressJob === myPoll) progressJob = null
                    _ui.update { it.copy(thinking = false, progress = null) }
                }
            }
            if (!isCurrent(e)) return

            val obj = runCatching { JSONObject(raw) }.getOrNull()
            if (obj == null) {
                _ui.update {
                    it.copy(aiFailed = true, error = BridgeError("bad_json", raw.take(200)))
                }
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
                        aiFailed = true,
                        error = BridgeError(
                            // org.json's optString returns "" (never null) for a
                            // missing key, so the elvis below it was dead code.
                            errObj?.optString("code").orEmpty().ifEmpty { "ai_move" },
                            errObj?.optString("message").orEmpty()
                                .ifEmpty { raw.take(200) },
                        )
                    )
                }
                return
            }

            val next = BridgeJson.state(obj)
            recordAiDuration(decisionPhase, obj.optDouble("elapsed_s", Double.NaN))
            _ui.update {
                it.copy(
                    state = next, error = null, aiFailed = false,
                    // `ai_last_tile` PERSISTS across the human's reply, so it only
                    // counts as a fresh placement when it actually changed.
                    lastPlacedTile = next.aiLastTile ?: it.lastPlacedTile,
                )
            }
            if (next.isTerminated) {
                saveStore.clear()
                _ui.update { it.copy(hasSave = false, showResult = true) }
                return
            }
            persist(e)
        }
    }

    /**
     * Feed one `ai_move` duration into the rolling window for [phase].
     *
     * A *mean of the last few* rather than the last value alone: move cost swings
     * a lot with position (an endgame exact solve is nothing like a midgame
     * search), and a single sample makes the "~Ns" hint jump around enough to read
     * as broken.
     */
    private fun recordAiDuration(phase: String, seconds: Double) {
        if (!seconds.isFinite() || seconds <= 0.0) return
        val window = aiDurations.getOrPut(phase) { ArrayDeque() }
        window.addLast(seconds)
        while (window.size > ETA_WINDOW) window.removeFirst()
    }

    /**
     * The ETA to advertise for the next [phase] decision, or `null` for no suffix
     * at all.
     *
     * Null in two cases, both of which used to print nonsense: no sample yet (the
     * first think of a session), and a mean too small to survive one-decimal
     * rounding — an "Instant" preset answers in ~20ms, and `"of ~0.0s"` beside a
     * ticking elapsed counter reads as a broken estimate rather than as "fast".
     */
    private fun etaFor(phase: String): Double? =
        aiDurations[phase]?.takeIf { it.isNotEmpty() }?.average()?.takeIf { it >= ETA_MIN_S }

    /**
     * Swallow input for [PHASE_LOCK_MS] (see [GameUiState.phaseLock]).
     *
     * The button is deliberately left on screen and merely inert: hiding it would
     * make the row jump, and the whole complaint is about a tap that lands where
     * the eye has not caught up yet.
     */
    private fun armPhaseLock() {
        phaseLockJob?.cancel()
        _ui.update { it.copy(phaseLock = true) }
        phaseLockJob = viewModelScope.launch {
            delay(PHASE_LOCK_MS)
            _ui.update { it.copy(phaseLock = false) }
        }
    }

    /** Start the 250 ms progress poll and return ITS job, so the caller can stop
     *  exactly the poll it started rather than whatever is current by then. */
    private fun startProgressPoll(): Job {
        stopProgressPoll()
        val job = viewModelScope.launch {
            while (isActive) {
                // A poll failure is cosmetic (the bar just does not advance) — but a
                // cancellation must still unwind, so it is rethrown, not swallowed.
                val raw = try {
                    PythonBridge.getProgress()
                } catch (c: CancellationException) {
                    throw c
                } catch (t: Throwable) {
                    null
                }
                if (raw != null) {
                    BridgeJson.parseOrError(raw).getOrNull()?.let { o ->
                        val p = BridgeJson.progress(o)
                        _ui.update { if (it.thinking) it.copy(progress = p) else it }
                    }
                }
                delay(POLL_MS)
            }
        }
        progressJob = job
        return job
    }

    private fun stopProgressPoll() {
        progressJob?.cancel()
        progressJob = null
    }

    override fun onCleared() {
        phaseLockJob?.cancel()
        stopProgressPoll()
        super.onCleared()
    }

    companion object {
        private const val TAG = "GameVM"
        private const val POLL_MS = 250L

        /** A 72-tile game is ~150 plies; anything past this is a bug, not a game. */
        private const val MAX_AI_STEPS = 400

        /** How many AI move durations the ETA averages over, per phase. */
        const val ETA_WINDOW = 5

        /** Below this the "of ~Ns" suffix is suppressed rather than shown as 0.0s. */
        const val ETA_MIN_S = 0.15

        /** How long taps are swallowed across the tile -> meeple phase change. */
        const val PHASE_LOCK_MS = 400L
    }
}
