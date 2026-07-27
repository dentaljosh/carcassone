package com.jishal.carcassonne

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chaquo.python.PyException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.json.JSONObject

/** One line in the debug log. */
data class LogLine(
    val label: String,
    val elapsedMs: Long?,
    val body: String,
    val isError: Boolean = false,
)

data class DebugUiState(
    val busy: Boolean = false,
    val lines: List<LogLine> = emptyList(),
    val generation: Int = 0,
)

/**
 * M0 debug driver. No game model, no board — it just fires bridge calls and
 * shows the raw JSON that comes back, with per-call wall-clock.
 */
class DebugViewModel : ViewModel() {

    private val _state = MutableStateFlow(DebugUiState())
    val state: StateFlow<DebugUiState> = _state

    /**
     * Bumped on every new game so a late `ai_move` result from the previous
     * game can be identified and dropped (the bridge echoes it back).
     */
    private var generation = 0

    // --- presets -----------------------------------------------------------

    /** Fast sanity config: rule-based opponent, negligible search. */
    private fun tinyConfig(): String = JSONObject().apply {
        put("seed", System.currentTimeMillis().toInt() and 0x7fffffff)
        put("human_player", 0)
        put("opponent", "tier1")
        put("sims", 16)
        put("k_dets", 1)
        put("verify", false)
    }.toString()

    /**
     * The full fair champion budget: k_dets=4 x 688 sims = 2752 determinized
     * simulations, verify=True so the on-device fingerprint guard runs.
     * This is the M0 latency measurement that gates the whole project.
     */
    private fun championConfig(): String = JSONObject().apply {
        put("seed", System.currentTimeMillis().toInt() and 0x7fffffff)
        put("human_player", 0)
        put("opponent", "champion")
        put("sims", 688)
        put("k_dets", 4)
        put("verify", true)
    }.toString()

    // --- actions -----------------------------------------------------------

    fun warmUp() = run("import android_bridge") { PythonBridge.warmUp() }

    fun newGameTiny() {
        generation++
        val cfg = tinyConfig()
        append(LogLine("config (tiny)", null, cfg))
        run("new_game tier1 k1x16") { PythonBridge.newGame(cfg) }
    }

    fun newGameChampion() {
        generation++
        val cfg = championConfig()
        append(LogLine("config (champion)", null, cfg))
        run("new_game champion k4x688") { PythonBridge.newGame(cfg) }
    }

    fun aiMove() {
        val gen = generation
        run("ai_move gen=$gen") { PythonBridge.aiMove(gen) }
    }

    fun getState() = run("get_state") { PythonBridge.getState() }

    fun getProgress() = run("get_progress") { PythonBridge.getProgress() }

    fun saveGame() = run("save_game") { PythonBridge.saveGame() }

    fun clear() = _state.update { it.copy(lines = emptyList()) }

    // --- plumbing ----------------------------------------------------------

    private fun run(label: String, block: suspend () -> String) {
        if (_state.value.busy) {
            append(LogLine(label, null, "BUSY — bridge thread is occupied", isError = true))
            return
        }
        _state.update { it.copy(busy = true) }
        viewModelScope.launch {
            val t0 = System.nanoTime()
            val line = try {
                val result = block()
                LogLine(label, elapsedMsSince(t0), result)
            } catch (e: PyException) {
                // Python-side traceback: the message carries the full chain.
                Log.e(TAG, "PyException in $label", e)
                LogLine(label, elapsedMsSince(t0), "PyException: ${e.message}", isError = true)
            } catch (e: Throwable) {
                Log.e(TAG, "Error in $label", e)
                LogLine(label, elapsedMsSince(t0), "${e.javaClass.simpleName}: ${e.message}", isError = true)
            }
            append(line)
            _state.update { it.copy(busy = false, generation = generation) }
        }
    }

    private fun elapsedMsSince(t0: Long) = (System.nanoTime() - t0) / 1_000_000

    private fun append(line: LogLine) {
        _state.update { it.copy(lines = it.lines + line) }
    }

    companion object {
        private const val TAG = "DebugVM"
    }
}
