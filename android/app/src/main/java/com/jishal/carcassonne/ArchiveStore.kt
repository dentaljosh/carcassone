package com.jishal.carcassonne

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * The finished-game archive at `filesDir/games/<finishedAt>_<seed>.json`.
 *
 * Why it exists: the autosave is *deleted* at termination, which threw away the one
 * artefact of a game worth keeping — the `(deck_seed, action_log)` pair that
 * reproduces it exactly. Each file here is `archive_record()`'s payload, which is a
 * superset of a save, so it is simultaneously the scoreboard row the Past-games list
 * prints and a replayable record (`restore_game` accepts the archive schema, and
 * `scripts/root_replay.py` accepts the same two fields on the desktop).
 *
 * Deliberately NOT capped. A record is a few hundred ints — a thousand games is well
 * under a megabyte — and silently dropping the oldest game is exactly the behaviour
 * that lost the data in the first place.
 *
 * Newest first, by the filename's leading timestamp: the name is the sort key, so
 * listing never has to open a file to order it.
 */
class ArchiveStore(context: Context) {

    private val dir = File(context.filesDir, DIR_NAME)

    /**
     * Persist one finished game. [raw] is `archive_record()`'s JSON verbatim —
     * stored unparsed on purpose, so a field this build does not read yet still
     * survives to the next one.
     */
    suspend fun write(raw: String, finishedAt: Long, deckSeed: Int): Boolean =
        withContext(Dispatchers.IO) {
            runCatching {
                dir.mkdirs()
                val stamp = if (finishedAt > 0) finishedAt else System.currentTimeMillis() / 1000
                val file = File(dir, "${stamp}_$deckSeed.json")
                // Same tmp+rename as SaveStore: a half-written record would parse to
                // null and read as a lost game.
                val tmp = File(dir, "${file.name}.tmp")
                tmp.writeText(raw)
                if (!tmp.renameTo(file)) {
                    file.writeText(raw)
                    tmp.delete()
                }
                true
            }.onFailure { Log.w(TAG, "archive write failed", it) }.getOrDefault(false)
        }

    /** Every archived game, newest first. Unparseable files are skipped, not fatal. */
    suspend fun list(): List<ArchivedGame> = withContext(Dispatchers.IO) {
        runCatching {
            dir.listFiles { f -> f.isFile && f.name.endsWith(".json") }
                .orEmpty()
                .sortedByDescending { it.name }
                .mapNotNull { f ->
                    runCatching { BridgeJson.archived(f.name, f.readText()) }.getOrNull()
                }
        }.onFailure { Log.w(TAG, "archive list failed", it) }.getOrDefault(emptyList())
    }

    suspend fun count(): Int = withContext(Dispatchers.IO) {
        dir.listFiles { f -> f.isFile && f.name.endsWith(".json") }?.size ?: 0
    }

    suspend fun delete(fileName: String): Boolean = withContext(Dispatchers.IO) {
        runCatching { File(dir, fileName).delete() }.getOrDefault(false)
    }

    companion object {
        private const val TAG = "ArchiveStore"
        private const val DIR_NAME = "games"
    }
}
