package com.jishal.carcassonne

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * The single-slot autosave at `filesDir/current_game.json`.
 *
 * The payload is whatever `save_game()` returned — `{deck_seed, actions[],
 * human_player, opponent, sims, k_dets, verify}`, a few hundred ints — and
 * `restore_game()` replays it. Because the save is (seed, action log) and not a
 * board snapshot, writing it is cheap enough to do after *every* applied action.
 *
 * Ordering rule (matters for the leave-mid-think path): the save is written
 * BEFORE `ai_move` is launched, never during. So an abandoned search resumes at
 * the human position that preceded it, and a champion move that was computed but
 * discarded can never be half-committed to disk.
 */
class SaveStore(context: Context) {

    private val file = File(context.filesDir, FILE_NAME)

    fun exists(): Boolean = file.isFile && file.length() > 0

    suspend fun read(): String? = withContext(Dispatchers.IO) {
        runCatching { if (file.isFile) file.readText() else null }
            .onFailure { Log.w(TAG, "read failed", it) }
            .getOrNull()
    }

    suspend fun write(json: String) = withContext(Dispatchers.IO) {
        runCatching {
            val tmp = File(file.parentFile, "$FILE_NAME.tmp")
            tmp.writeText(json)
            if (!tmp.renameTo(file)) {          // rename is atomic on the same fs
                file.writeText(json)
                tmp.delete()
            }
        }.onFailure { Log.w(TAG, "write failed", it) }
        Unit
    }

    suspend fun clear() = withContext(Dispatchers.IO) {
        runCatching { file.delete() }
        Unit
    }

    companion object {
        private const val TAG = "SaveStore"
        private const val FILE_NAME = "current_game.json"
    }
}
