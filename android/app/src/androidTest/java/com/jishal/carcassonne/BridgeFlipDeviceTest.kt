package com.jishal.carcassonne

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.BeforeClass
import org.junit.FixMethodOrder
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.MethodSorters
import java.io.File

/**
 * ON-DEVICE ACCEPTANCE for the 2026-08-01 flip (Joshua: "2 yes").
 *
 * Distinct from `RustPortDeviceTest` on purpose. That one gates the PORT — it
 * drives `carc_p7_probe`, a measurement module, and asks "is the Rust core
 * correct and fast enough on this hardware". This one gates the SHIPPED APP: it
 * drives `android_bridge` exactly as the Kotlin UI does, and asks "does the
 * thing the user will hold actually play the champion of record on the Rust
 * backend, and does its save record say so honestly".
 *
 * It has to run in the app process for the same reason G7 did: the resolution
 * under test IS the device's — `carc_rs` as pip resolved it for this ABI, the
 * bundled `PRODUCTION.yaml` as Chaquopy packaged it, and `android_exp_fma()`
 * reading this ISA. A desktop run of the same bridge proves the wiring; only
 * this proves the artefact.
 *
 * Bars are asserted where a miss would mean the flip is WRONG (backend, budget,
 * start rule, save fidelity) and reported where a miss is a finding (s/move).
 */
@RunWith(AndroidJUnit4::class)
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
class BridgeFlipDeviceTest {

    private fun bridge(): PyObject = Python.getInstance().getModule(MODULE)

    private fun call(fn: String, vararg args: Any?): JSONObject {
        val raw = bridge().callAttr(fn, *args).toString()
        val o = JSONObject(raw)
        assertTrue("$fn failed: $raw", o.optBoolean("ok", false))
        return o
    }

    private fun emit(name: String, json: String) {
        val dir = File(appCtx().getExternalFilesDir(null), "flip").apply { mkdirs() }
        File(dir, "$name.json").writeText(json)
        Log.i(TAG, "$name = ${json.take(4000)}")
    }

    /**
     * Leg 1 — what the app resolved. The DEFAULT is under test, so the game is
     * started with an EMPTY config: anything passed here would be testing the
     * argument rather than the shipped default.
     */
    @Test
    fun t01_default_game_is_the_rust_champion_of_record() {
        call("reset")
        val st = call("new_game", "{}")
        val info = call("runtime_info")
        val budget = call("production_budget")
        emit("flip_resolution", JSONObject(mapOf(
            "backend" to st.optString("backend"),
            "backend_note" to st.opt("backend_note"),
            "budget_note" to st.opt("budget_note"),
            "rust" to info.getJSONObject("rust"),
            "budget" to budget,
        ).toMap()).toString())

        assertEquals("the shipped default must be the rust backend",
            "rust", st.getString("backend"))
        assertTrue("a degraded session left a note: ${st.opt("backend_note")}",
            st.isNull("backend_note"))
        assertEquals("rust", info.getJSONObject("rust").getString("default_backend"))
        assertTrue(info.getJSONObject("rust").getBoolean("active"))

        // THE UNPIN: the phone runs the champion of record, not a carve-out.
        assertEquals(11008, budget.getInt("total_sims"))
        assertEquals(budget.getInt("champion_of_record_total_sims"),
            budget.getInt("total_sims"))
        assertEquals(8, budget.getInt("k_dets"))
        assertEquals(1376, budget.getInt("sims_per_det"))
        assertTrue("the mobile profile must come from the bundled YAML",
            budget.getBoolean("profile_from_yaml"))

        // Full budget => NO runtime_budget_override. Its ABSENCE is the E4 signal
        // that a game was played at champion strength, so it is asserted, not read.
        val man = call("get_manifest").getJSONObject("manifest")
        assertTrue("a full-budget game must carry no runtime_budget_override",
            !man.has("runtime_budget_override"))
        assertTrue("the mobile profile is not below the champion any more",
            st.isNull("budget_note"))
    }

    /**
     * Leg 2 — the retail start tile is pre-placed before anyone draws, AND it
     * sits on the RECENTRED grid (2026-08-02, app-only).
     *
     * Row 18 of 35, not row 6: the walled grid left 6 rows of headroom above and
     * 28 below, which is what produced the "invisible border" Joshua hit on this
     * very device — a rule-legal placement above row 0 is silently never offered.
     * The shift is 12, i.e. EVEN, which is what makes it representation-neutral
     * (tests/test_start_tile_grid_bound.py). Asserted, not reported: a miss here
     * means the shipped app is back on the walled grid.
     */
    @Test
    fun t02_new_game_starts_from_the_retail_tile_on_the_centred_grid() {
        call("reset")
        val st = call("new_game", "{}")
        val board = st.getJSONArray("board")
        assertEquals("retail: exactly one tile is pre-placed", 1, board.length())
        val tile = board.getJSONObject(0)
        assertEquals("the app default grid is centered18", 18, tile.getInt("row"))
        assertEquals(15, tile.getInt("col"))
        // Every legal first placement is clear of the top wall by a mile.
        val cells = st.getJSONObject("legal").getJSONArray("tile_cells")
        var minRow = Int.MAX_VALUE
        for (i in 0 until cells.length()) {
            minRow = minOf(minRow, cells.getJSONObject(i).getInt("row"))
        }
        assertTrue("lowest legal row was $minRow; the top wall is at 0", minRow >= 17)
        // Nobody spends a turn on it and no meeple goes on it.
        assertEquals("retail: the start tile carries no meeple",
            0, st.getJSONArray("meeples").length())
        assertEquals("[7,7]", st.getJSONArray("meeples_free").toString())
        assertEquals("retail: the deck is the remaining 71", 71,
            st.getInt("tiles_remaining"))
        emit("flip_start_tile", JSONObject(mapOf(
            "description" to tile.getString("description"),
            "row" to tile.getInt("row"), "col" to tile.getInt("col"),
            "tiles_remaining" to st.getInt("tiles_remaining"),
        ).toMap()).toString())
        Log.w(TAG, "start tile = ${tile.getString("description")} " +
            "@(${tile.getInt("row")},${tile.getInt("col")})")
    }

    /**
     * Leg 3 — real champion moves at the real budget, timed. The bar is G7's
     * (<=2 s); reported, not asserted, because a slow move is a finding for the
     * write-up and a red test here would hide legs 4's save evidence.
     */
    @Test
    fun t03_champion_moves_at_the_full_budget() {
        call("reset")
        var st = call("new_game", """{"human_player": 0}""")
        val times = mutableListOf<Double>()
        var guard = 0
        while (times.size < N_MOVES && guard++ < 40 && !st.getBoolean("is_terminated")) {
            st = if (st.getBoolean("is_human_turn")) {
                call("apply_action",
                    st.getJSONObject("legal").getJSONArray("action_ids").getInt(0))
            } else {
                val t0 = System.nanoTime()
                val r = call("ai_move")
                times += (System.nanoTime() - t0) / 1e9
                r
            }
        }
        assertTrue("no champion move was played", times.size >= N_MOVES)
        val sorted = times.sorted()
        val median = sorted[sorted.size / 2]
        emit("flip_s_per_move", JSONObject(mapOf(
            "s_per_move" to times, "median" to median,
            "total_sims" to 11008, "threads" to 4,
        ).toMap()).toString())
        Log.w(TAG, "champion s/move = $times median=$median (G7 ref 1.551, bar 2.0)")
    }

    /**
     * Leg 4 — the save record is honest and lossless. `start_rule` and the budget
     * fields have to survive, because `(deck_seed, actions)` only reproduces a
     * game under the rules it was played under.
     */
    @Test
    fun t04_save_restore_round_trip_carries_the_new_truth() {
        call("reset")
        var st = call("new_game", """{"seed": 909, "human_player": 0}""")
        var guard = 0
        var aiMoves = 0
        while (aiMoves < 2 && guard++ < 30 && !st.getBoolean("is_terminated")) {
            st = if (st.getBoolean("is_human_turn")) {
                call("apply_action",
                    st.getJSONObject("legal").getJSONArray("action_ids").getInt(0))
            } else { aiMoves++; call("ai_move") }
        }
        val save = call("save_game")
        assertEquals("retail", save.getString("start_rule"))
        assertEquals("the save must record WHICH GRID the game was played on",
            "centered18", save.getString("grid_rule"))
        assertTrue("the save must stamp the champion identity",
            save.getString("leaf_hash").isNotEmpty())

        val before = call("get_state")
        val restored = call("restore_game", save.toString())
        val after = call("get_state")
        assertEquals(before.getJSONArray("scores").toString(),
            after.getJSONArray("scores").toString())
        assertEquals(before.getInt("n_actions"), after.getInt("n_actions"))
        assertEquals(before.getString("phase"), after.getString("phase"))
        assertEquals("a restore must stay on the rust backend",
            "rust", after.getString("backend"))
        emit("flip_save_round_trip", JSONObject(mapOf(
            "start_rule" to save.getString("start_rule"),
            "grid_rule" to save.getString("grid_rule"),
            "leaf_hash" to save.getString("leaf_hash"),
            "champion_id" to save.getString("champion_id"),
            "n_actions" to after.getInt("n_actions"),
            "ai_decisions" to restored.getJSONObject("restored").getInt("ai_decisions"),
            "scores" to after.getJSONArray("scores").toString(),
        ).toMap()).toString())
    }

    /**
     * Leg 5 — THE BACKWARD-COMPAT LEG for the 2026-08-02 recentring.
     *
     * The two real E4 archives are the only human-vs-champion games that exist.
     * They were written by an app that had neither `grid_rule` nor the recentred
     * grid, so the ABSENT field must mean "engine6" forever — and it has to mean
     * that on the DEVICE, through the same `restore_game` the Past-games list
     * calls, not just in a desktop test. If it silently resolved to the new
     * default instead, the identical action log would decode different board
     * cells (an action index is a WINDOW cell) and the replay would either
     * diverge on score or be outright illegal. Unrecoverable data, so asserted.
     */
    @Test
    fun t05_old_archives_still_replay_on_the_walled_grid() {
        val names = listOf("1785205383_867966", "1785466497_161583")
        val report = mutableMapOf<String, Any>()
        for (name in names) {
            call("reset")
            val blob = JSONObject(asset("e4/$name.json").readText())
            assertTrue("fixture is not a pre-recentring archive",
                !blob.has("grid_rule") && !blob.has("start_rule"))
            val restored = call("restore_game", blob.toString())
            val st = call("get_state")
            assertEquals("$name: replay diverged",
                blob.getJSONArray("scores").toString(),
                st.getJSONArray("scores").toString())
            assertEquals("$name: not every action replayed",
                blob.getJSONArray("actions").length(),
                restored.getJSONObject("restored").getInt("actions"))
            // The grid the archive replayed on, read back the way the payload
            // records it: a fresh save of the restored session.
            val save = call("save_game")
            assertEquals("$name: an archive with no grid_rule must be engine6",
                "engine6", save.getString("grid_rule"))
            assertEquals("$name: an archive with no start_rule must be engine",
                "engine", save.getString("start_rule"))
            report[name] = JSONObject(mapOf(
                "scores" to st.getJSONArray("scores").toString(),
                "actions" to restored.getJSONObject("restored").getInt("actions"),
                "grid_rule" to save.getString("grid_rule"),
                "start_rule" to save.getString("start_rule"),
            ).toMap())
        }
        emit("grid_legacy_archives", JSONObject(report.toMap()).toString())
    }

    companion object {
        private const val TAG = "FlipDevice"
        private const val MODULE = "android_bridge"
        private const val N_MOVES = 3

        private fun appCtx() =
            InstrumentationRegistry.getInstrumentation().targetContext

        /** Copy an androidTest asset out to a readable file (same trick as P7). */
        private fun asset(path: String): File {
            val out = File(appCtx().cacheDir, "flipassets/$path")
            if (out.isFile && out.length() > 0) return out
            out.parentFile?.mkdirs()
            InstrumentationRegistry.getInstrumentation().context.assets.open(path)
                .use { input -> out.outputStream().use { input.copyTo(it) } }
            return out
        }

        @BeforeClass
        @JvmStatic
        fun startPython() {
            if (!Python.isStarted()) {
                Python.start(com.chaquo.python.android.AndroidPlatform(appCtx()))
            }
        }
    }
}
