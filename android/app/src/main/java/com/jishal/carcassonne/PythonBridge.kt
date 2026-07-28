package com.jishal.carcassonne

import com.chaquo.python.PyObject
import com.chaquo.python.Python
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.withContext
import java.util.concurrent.Executors

/**
 * Thin Kotlin face over the `android_bridge` Python module.
 *
 * Every *mutating* Python call is funnelled through ONE dedicated thread
 * ([dispatcher]). That is deliberate and load-bearing:
 *  - `android_bridge` keeps a single module-global session (game, board, agent,
 *    action log), so concurrent mutation would corrupt it;
 *  - CPython's GIL makes extra threads pointless for throughput anyway;
 *  - it keeps multi-second `ai_move` calls off the main thread.
 *
 * [getProgress] is the documented exception (it reads module-global ints and one
 * agent bool, never the session), so since M2 it gets its OWN single-thread
 * dispatcher. Routing it through the shared one — as M0 did — meant the 250 ms
 * thinking-poll simply queued behind the very `ai_move` it was trying to report
 * on, so the progress bar never moved. CPython releases the GIL every few
 * milliseconds (`sys.setswitchinterval`), so the poll gets through while the
 * search thread is running.
 *
 * Every function returns the raw JSON string the bridge produced; parsing lives
 * in [BridgeJson].
 */
object PythonBridge {

    private val executor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "py-bridge").apply { isDaemon = true }
    }

    private val progressExecutor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "py-progress").apply { isDaemon = true }
    }

    val dispatcher: CoroutineDispatcher = executor.asCoroutineDispatcher()

    /** Poll-only dispatcher; must never be used for a session-mutating call. */
    val progressDispatcher: CoroutineDispatcher = progressExecutor.asCoroutineDispatcher()

    /**
     * Resolved lazily on whichever bridge thread gets there first — importing
     * pulls in numpy + the engine. `@Volatile` + `synchronized` because two
     * threads can now reach it (the progress poll is the second).
     */
    @Volatile
    private var module: PyObject? = null

    private fun moduleBlocking(): PyObject {
        module?.let { return it }
        return synchronized(this) {
            module ?: Python.getInstance().getModule(MODULE_NAME).also { module = it }
        }
    }

    private suspend fun call(fn: String, vararg args: Any?): String =
        withContext(dispatcher) {
            moduleBlocking().callAttr(fn, *args).toString()
        }

    /** Forces the (slow, first-time) import of the bridge module. */
    suspend fun warmUp(): String = withContext(dispatcher) {
        moduleBlocking()
        "android_bridge imported"
    }

    // -- session-mutating: bridge dispatcher only -----------------------------

    suspend fun newGame(configJson: String): String = call("new_game", configJson)

    suspend fun getState(): String = call("get_state")

    suspend fun applyAction(actionId: Int): String = call("apply_action", actionId)

    suspend fun aiMove(generation: Int): String = call("ai_move", generation)

    suspend fun saveGame(): String = call("save_game")

    suspend fun restoreGame(json: String): String = call("restore_game", json)

    /**
     * Drops the session and bumps the generation so an in-flight `ai_move`'s
     * result is discarded. NOTE: this queues *behind* that `ai_move` on the
     * bridge thread (there is no mid-search cancellation), so it lands only once
     * the search returns. That is fine — the caller has already stopped caring
     * about the result, and the save file was written before the move started.
     */
    suspend fun reset(): String = call("reset")

    suspend fun getManifest(): String = call("get_manifest")

    /** The permanent record of a FINISHED game; refuses one still in progress. */
    suspend fun archiveRecord(): String = call("archive_record")

    /**
     * What meeple options a prospective tile placement would open.
     *
     * Read-only (it drives a private copy of the board), but it still goes on the
     * bridge dispatcher: it reads the live session, so it must not race a mutation.
     * One call per ghost selection change, which is a tap, not a frame.
     */
    suspend fun previewMeepleSlots(actionId: Int): String =
        call("preview_meeple_slots", actionId)

    /**
     * Take back the tile just placed, returning to the tile decision point.
     *
     * Legal only in the human's meeple sub-phase. The bridge rebuilds the session by
     * replaying `(deck_seed, action_log minus the last action)`, so the opponent that
     * plays on is bit-identical; the caller must persist afterwards (the ordinary
     * `runBridge` path does) so the autosave loses the undone action too.
     */
    suspend fun undoLastTile(): String = call("undo_last_tile")

    /** Every claimed feature + its owners, for the always-on shading. */
    suspend fun getOwnership(): String = call("get_ownership")

    /** Unseen tiles per face — public information, never the deck order. */
    suspend fun getBag(): String = call("get_bag")

    /**
     * DEBUG SCREEN ONLY. Plays the current game out so a finished state (and its
     * archive entry) can be reached without ~150 taps. The confirm token is the
     * bridge's own guard; keeping the single call site in [DebugScreen] is ours.
     */
    suspend fun debugFastForward(): String =
        call("debug_fast_forward", "yes-destroy-this-game")

    /** The YAML champion budget, so the UI never hardcodes a strength knob. */
    suspend fun productionBudget(): String = call("production_budget")

    // -- poll-only: safe concurrently with a blocking ai_move -----------------

    suspend fun getProgress(): String = withContext(progressDispatcher) {
        moduleBlocking().callAttr("get_progress").toString()
    }

    private const val MODULE_NAME = "android_bridge"
}
