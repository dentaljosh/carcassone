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
 * Every Python call is funnelled through ONE dedicated thread ([dispatcher]).
 * That is deliberate and load-bearing:
 *  - `android_bridge` keeps a single module-global session (game, board, agent,
 *    action log), so concurrent mutation would corrupt it;
 *  - CPython's GIL makes extra threads pointless for throughput anyway;
 *  - it keeps multi-second `ai_move` calls off the main thread.
 *
 * Every function here is a `suspend fun` returning the raw JSON string the
 * bridge produced. Parsing is the caller's problem — M0 only displays it.
 *
 * `get_progress()` is the one exception to the single-thread rule by design
 * (it reads module-global ints), but it is still routed through the same
 * dispatcher here; polling it while `ai_move` occupies the thread would just
 * queue. A future milestone can give it its own dispatcher.
 */
object PythonBridge {

    private val executor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "py-bridge").apply { isDaemon = true }
    }

    val dispatcher: CoroutineDispatcher = executor.asCoroutineDispatcher()

    /** Resolved lazily on the bridge thread — importing pulls in numpy + the engine. */
    private var module: PyObject? = null

    private fun moduleBlocking(): PyObject =
        module ?: Python.getInstance().getModule(MODULE_NAME).also { module = it }

    private suspend fun call(fn: String, vararg args: Any?): String =
        withContext(dispatcher) {
            moduleBlocking().callAttr(fn, *args).toString()
        }

    /** Forces the (slow, first-time) import of the bridge module. */
    suspend fun warmUp(): String = withContext(dispatcher) {
        moduleBlocking()
        "android_bridge imported"
    }

    suspend fun newGame(configJson: String): String = call("new_game", configJson)

    suspend fun getState(): String = call("get_state")

    suspend fun applyAction(actionId: Int): String = call("apply_action", actionId)

    suspend fun aiMove(generation: Int): String = call("ai_move", generation)

    suspend fun getProgress(): String = call("get_progress")

    suspend fun saveGame(): String = call("save_game")

    suspend fun restoreGame(json: String): String = call("restore_game", json)

    private const val MODULE_NAME = "android_bridge"
}
